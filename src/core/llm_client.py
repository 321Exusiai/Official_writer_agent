"""
LLMClient — LLM 调用客户端（组合模式）

从 Orchestrator 提取（重构阶段 1），负责：
- LLM API 调用：集成六大 Token 优化策略、任务分级路由、LRU 缓存、重试与分类错误处理
- 工具执行闭环：解析 [TOOL_CALL] 标记 → 执行工具 → 结果回传模型整合
- API 调用统计与 Token 优化报告

设计：Orchestrator 持有 self.llm_client 并委托调用；本类通过 host 反向引用读取
写作模式/温度/知识库/个性化库等协调器级状态，避免大量构造参数传递。
"""

import json
import threading
import requests
import time
from typing import List, Dict, Optional, Any

from ..utils.response_cache import cached_prompt, store_prompt, make_cache_key
from ..utils.token_optimizer import (
    TokenOptimizer, CacheAligner, ContextManager,
    CompressionMode, ModelRouter,
)


class LLMClient:
    """LLM 调用客户端：封装调用、重试、缓存、Token 优化与工具执行闭环。"""

    def __init__(self, host, api_manager=None):
        self.host = host
        # API 配置管理器：优先使用传入的，否则创建默认实例
        if api_manager is not None:
            self.api_manager = api_manager
        else:
            from ..config.api_config import APIConfigManager
            self.api_manager = APIConfigManager()

        # Token 优化器集成（六大策略）
        self._token_optimizer = TokenOptimizer(mode=CompressionMode.STANDARD)
        self._cache_aligner = CacheAligner()
        self._context_manager = ContextManager()
        self._api_call_count: int = 0
        self._api_fail_count: int = 0
        self._total_tokens_saved: int = 0
        self._llm_reasonings: List[Dict[str, str]] = []
        self._tool_execution_log: List[Dict[str, Any]] = []
        self._task_level_counts: Dict[str, int] = {}
        self._counter_lock = threading.Lock()

    def call_llm(self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None, max_tokens: int = 8000, history: Optional[List[Dict[str, str]]] = None, use_cache: bool = True) -> str:
        """
        调用 LLM API 生成内容（集成六大 Token 优化策略 + 健壮性机制）

        Args:
            temperature: None 时使用 host.temperature（支持 UI 温度调节，修复语义断裂）
            history: 多轮对话消息列表（由 ContextManager 组装，含 system/user/assistant/工具结果），
                     传入时跳过单轮 prompt 优化与 LRU 缓存，直接按历史调用（工具闭环用）
            use_cache: 是否启用 LLM 响应 LRU 缓存。主稿生成等"每次要全新输出"的调用传 False，
                       避免相同 prompt 直接返回上一次的旧内容；审查/协商等稳定调用保持 True 省 token。
        """
        # 优先使用传入温度，否则用实例温度（修复 temperature 语义断裂）
        if temperature is None:
            temperature = self.host.temperature
        with self._counter_lock:
            self._api_call_count += 1

        # ── 0. 任务分级路由（Strategy F：按复杂度分类，记录用于统计）──
        task_desc = (system_prompt + user_prompt)[:200]
        task_level = ModelRouter.classify_task(task_desc)
        with self._counter_lock:
            level_name = task_level.name if hasattr(task_level, 'name') else str(task_level)
            self._task_level_counts[level_name] = self._task_level_counts.get(level_name, 0) + 1

        # ── 1. 配置校验 ──
        config = self.api_manager.config
        if not config.enable or not config.api_key or not config.api_base:
            return self._generate_fallback(system_prompt, user_prompt)

        if history:
            # ── 多轮历史模式：消息已由 ContextManager 组装（含 system），
            #    跳过单轮 prompt 压缩/缓存对齐/LRU，直接按历史调用 ──
            payload = {
                "model": config.model,
                "messages": history,
                "temperature": temperature,
                "max_tokens": min(max_tokens, config.max_tokens),
            }
            return self._do_llm_request(config, payload, system_prompt, user_prompt)

        # ── 2. Prompt 压缩（Strategy A）──
        system_opt, user_opt, stats = self._token_optimizer.optimize_prompt(system_prompt, user_prompt)
        with self._counter_lock:
            self._total_tokens_saved += stats.estimated_input_tokens_saved

        # ── 3. 缓存对齐（Strategy D：静态前置 + 动态后置）──
        self._cache_aligner.check_cache_hit(system_opt)

        # ── 4. LRU 缓存检查（相同 prompt 直接返回；key 含 temperature/model，防止串结果）──
        cache_key = None
        if use_cache:
            cache_key = make_cache_key(system_opt, user_opt, temperature, config.model)
            try:
                cached = cached_prompt("llm_response", cache_key)
                if cached:
                    return cached
            except Exception:
                pass

        # ── 5. API 调用（带重试 + 分类错误处理）──
        payload = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_opt},
                {"role": "user", "content": user_opt},
            ],
            "temperature": temperature,
            "max_tokens": min(max_tokens, config.max_tokens),
        }
        return self._do_llm_request(config, payload, system_prompt, user_prompt, cache_key)

    def _do_llm_request(
        self, config, payload: Dict[str, Any], system_prompt: str, user_prompt: str, cache_key: Optional[str] = None
    ) -> str:
        """执行一次 LLM HTTP 请求（重试 + 分类错误处理 + 响应验证 + 缓存）"""
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        url = config.api_base.rstrip("/") + "/chat/completions"

        max_retries = 3
        last_error: Optional[str] = None

        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=config.timeout)

                # ── 分类 HTTP 错误 ──
                if response.status_code == 401:
                    return self._generate_fallback(system_prompt, user_prompt, "API Key 无效或已过期，请在设置中检查")
                if response.status_code == 403:
                    return self._generate_fallback(system_prompt, user_prompt, "API Key 无权限访问该模型")
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait = (attempt + 1) * 5
                        time.sleep(wait)
                        continue
                    return self._generate_fallback(system_prompt, user_prompt, "请求频率过高，请稍后重试")
                if response.status_code >= 500:
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return self._generate_fallback(system_prompt, user_prompt, "API 服务器内部错误，请稍后重试")

                response.raise_for_status()

                # ── 6. 响应验证 ──
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    return self._generate_fallback(system_prompt, user_prompt, "API 返回空结果")

                content = choices[0].get("message", {}).get("content", "")
                if not content or len(content.strip()) < 2:
                    return self._generate_fallback(system_prompt, user_prompt, "API 返回内容为空")

                # 提取 reasoning（如 DeepSeek-R1 的思考链），保存用于调试和教学
                reasoning = choices[0].get("message", {}).get("reasoning_content", "")
                if reasoning:
                    self._llm_reasonings.append({
                        "system_prompt_preview": system_prompt[:200],
                        "reasoning": reasoning,
                    })

                # ── 7. 缓存成功响应（仅单轮模式传入 cache_key）──
                if cache_key:
                    try:
                        store_prompt("llm_response", content, cache_key)
                    except Exception:
                        pass
                return content

            except requests.exceptions.Timeout:
                last_error = f"请求超时（{config.timeout}秒）"
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            except requests.exceptions.ConnectionError:
                last_error = "无法连接到 API 服务器，请检查网络或 Base URL"
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            except json.JSONDecodeError:
                last_error = "API 返回的数据格式异常（非有效 JSON）"
                break  # JSON 解析错误不重试
            except Exception as e:
                last_error = str(e)[:200]
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue

        # ── 8. 所有重试失败，优雅降级 ──
        with self._counter_lock:
            self._api_fail_count += 1
        return self._generate_fallback(system_prompt, user_prompt, last_error)

    def _generate_fallback(self, system_prompt: str, user_prompt: str, error_msg: str = "") -> str:
        """LLM 不可用时的占位文本"""
        from .writing_mode import get_mode_profile
        error_line = f"\n错误信息：{error_msg}\n" if error_msg else "\n"
        return f"""【占位文本 - LLM API 未配置或调用失败】{error_line}
系统已构建以下 Prompt 准备调用 LLM：

写作模式: {get_mode_profile(self.host.writing_mode).name}
System Prompt:
{system_prompt[:500]}

User Prompt:
{user_prompt[:500]}

请前往「API设置」页面配置 LLM API Key 以生成真实公文。"""

    def get_api_stats(self) -> Dict[str, Any]:
        """获取 API 调用统计与 Token 优化报告"""
        return {
            "api_calls": self._api_call_count,
            "api_failures": self._api_fail_count,
            "tokens_saved": self._total_tokens_saved,
            "cache_stats": self._cache_aligner.get_cache_stats(),
            "optimization_report": self._token_optimizer.get_optimization_report(),
            # Strategy F: 任务分级路由统计
            "task_routing": self._task_level_counts,
        }

    # ═══════════════════════════════════════════════════════════
    # 工具执行（TR板块：解析LLM工具调用并执行，形成闭环）
    # ═══════════════════════════════════════════════════════════

    def call_llm_with_tool_loop(self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None, max_tokens: int = 8000, max_tool_rounds: int = 3, use_cache: bool = True) -> str:
        """
        工具闭环：调用 LLM，若输出含 [TOOL_CALL: ...] 标记则执行工具，
        并把工具结果经 ContextManager 作为消息回传模型，再次调用 LLM 整合，
        直到输出无工具调用或达到轮次上限。

        修复 N3：工具结果不再内联进稿件，而是回传模型由 LLM 整合；
        修复 1.5：接通 ContextManager 作为多轮对话的消息历史层（build_context 真正被调用）。

        Args:
            max_tool_rounds: 工具调用的最大后续轮次，防止死循环

        Returns:
            LLM 整合后的最终文本（不含工具调用标记）
        """
        # ── 接通 ContextManager：作为本次会话的消息历史层 ──
        self._context_manager.reset()
        self._context_manager.add_message("system", system_prompt)
        self._context_manager.add_message("user", user_prompt)

        from ..config.tool_definitions import parse_tool_call
        result = self.call_llm(system_prompt, user_prompt, temperature=temperature, max_tokens=max_tokens, use_cache=use_cache)

        for _ in range(max_tool_rounds):
            calls = parse_tool_call(result or "")
            if not calls:
                break
            # 记录 LLM 的带工具调用的回复，再回传工具结果
            self._context_manager.add_message("assistant", result or "")
            for tool_name, params in calls:
                tool_result = self._execute_tool_call(tool_name, params)
                self._tool_execution_log.append({
                    "tool": tool_name,
                    "params": params,
                    "result_preview": tool_result[:200],
                    "status": "ok" if tool_result else "empty",
                })
                self.host._log_agent("Tool", f"执行工具 [{tool_name}] 参数={params} -> 返回 {len(tool_result)} 字")
                self._context_manager.add_message(
                    "user", f"[工具 {tool_name} 执行结果，请基于此结果整合进正文]\n{tool_result}"
                )
            # 基于完整历史再次调用 LLM 整合工具结果
            history = self._context_manager.build_context()
            result = self.call_llm(
                system_prompt, "", temperature=temperature, max_tokens=max_tokens, history=history
            )

        # 防御：若达轮次上限仍残留工具标记，剥离避免污染最终稿件
        if result and "[TOOL_CALL:" in result:
            import re as _re
            result = _re.sub(r'\[TOOL_CALL:[^\]]*\]', '', result)
        return result or ""

    def _execute_tool_call(self, tool_name: str, params: Dict[str, str]) -> str:
        """执行单个工具调用，返回结果文本。工具不可用时返回空字符串。"""
        host = self.host
        kb = host._get_knowledge_base()
        try:
            # ── 知识库工具 ──
            if tool_name == "lookup_term":
                term = params.get("term", "")
                info = kb.lookup_term(term) if kb else None
                if not info:
                    return f"未找到术语：{term}"
                return "\n".join([
                    f"定义：{info.get('definition', '')}",
                    f"出处：{info.get('context', '')}",
                    f"使用注意：{info.get('usage_note', '')}",
                    f"常见误用：{info.get('common_misuse', '')}",
                ])
            if tool_name == "search_exemplars":
                mode = params.get("writing_mode", "")
                doc_type = params.get("doc_type", "")
                style = params.get("style", "")
                results = kb.search_exemplars(
                    writing_mode=mode or None,
                    doc_type=doc_type or None,
                    style=style or None,
                ) if kb else []
                if not results:
                    return "未找到匹配的范文"
                lines = []
                for e in results[:3]:
                    lines.append(f"- 《{e.title}》（{e.source}）\n  结构：{e.structure_skeleton}")
                return "\n".join(lines)
            if tool_name == "get_writing_tips":
                doc_type = params.get("doc_type", "")
                style = params.get("style", "")
                tips = kb.get_writing_tips(doc_type, style) if kb else []
                return "\n".join(f"- {t}" for t in tips) if tips else "暂无该文种/风格的写作提示"
            if tool_name == "get_formulaic":
                doc_type = params.get("doc_type", "")
                return kb.get_formulaic_for_prompt(doc_type) if kb else ""
            if tool_name == "get_transitions":
                style = params.get("style", "")
                count = int(params.get("count", "3") or "3")
                phrases = kb.get_transitions(style, count) if kb else []
                return "\n".join(phrases) if phrases else "暂无该风格的过渡词"

            # ── 文种识别工具 ──
            if tool_name == "identify_doc_type":
                from ..questionnaire.questionnaire import WritingBrief as _WB
                brief = _WB(
                    purpose=params.get("purpose", ""),
                    primary_audience=params.get("audience", ""),
                    length_hint=int(params.get("length", "0") or "0"),
                    key_materials=params.get("key_materials", ""),
                )
                ranked = host.doc_identifier.identify(brief)
                lines = []
                for profile, score in ranked[:3]:
                    if score <= 0:
                        continue
                    lines.append(f"- {profile.name_cn}（匹配度{score:.0%}）：{profile.structure_mode}")
                return "\n".join(lines) if lines else "无法确定文种，请补充更多信息"
            if tool_name == "analyze_materials":
                materials = params.get("key_materials", "")
                ratio = host.doc_identifier.analyze_materials(materials)
                return "\n".join(f"{k}: {v:.0%}" for k, v in ratio.items())

            # ── 风格适配工具 ──
            if tool_name == "list_styles":
                styles = host.style_adapter.list_styles() if hasattr(host.style_adapter, "list_styles") else []
                if not styles:
                    return "暂无风格列表"
                return "\n".join(f"- {s}" for s in styles)
            if tool_name == "auto_select_style":
                result = host.style_adapter.auto_select_style(
                    audience=params.get("audience", ""),
                    purpose=params.get("purpose", ""),
                ) if hasattr(host.style_adapter, "auto_select_style") else {}
                if isinstance(result, dict):
                    return f"推荐风格：{result.get('style', result)}"
                return str(result)
            if tool_name == "suggest_style_blend":
                primary = params.get("primary_audience", "")
                purpose = params.get("purpose", "")
                secondary = [s.strip() for s in params.get("secondary_audiences", "").split("|") if s.strip()]
                blend = host.style_adapter.suggest_blend(primary, purpose, secondary or None)
                from ..core.style_adapter import STYLE_PROFILES
                primary_name = STYLE_PROFILES[blend.primary_style].name
                parts = [f"主风格：{primary_name}（{blend.primary_weight:.0%}）"]
                if blend.secondary_style and blend.secondary_weight > 0:
                    secondary_name = STYLE_PROFILES[blend.secondary_style].name
                    parts.append(f"次风格：{secondary_name}（{blend.secondary_weight:.0%}，应用于{blend.secondary_apply_to}）")
                if blend.reasoning:
                    parts.append(f"推理：{blend.reasoning}")
                return "\n".join(parts)

            # ── 个性化数据库工具 ──
            if tool_name == "get_memory_summary":
                # 修复 2.2c：尊重 project_id，从持久化实例读项目记忆，与注入的跨会话记忆合并
                pid = params.get("project_id", "")
                pdb = host._get_pdb()
                db_memory = ""
                if pdb and pid:
                    try:
                        db_memory = pdb.get_memory_summary(pid) or ""
                    except Exception:
                        db_memory = ""
                if host.user_memory and db_memory:
                    return f"{host.user_memory}\n\n【项目记忆】\n{db_memory}"
                return host.user_memory or db_memory or "暂无用户记忆数据"
            if tool_name == "get_style_recommendation":
                # 需要项目ID，从当前上下文取
                pid = params.get("project_id", "")
                rec = {}
                pdb = host._get_pdb()
                if pdb and pid:
                    try:
                        rec = pdb.get_style_recommendation(pid)
                    except Exception:
                        rec = {}
                if not rec:
                    return "暂无风格推荐数据（需要项目ID）"
                lines = []
                if rec.get("suggested_style"):
                    lines.append(f"推荐风格：{rec['suggested_style']}")
                if rec.get("suggested_vocabulary"):
                    lines.append(f"建议词汇：{', '.join(rec['suggested_vocabulary'][:5])}")
                if rec.get("bias_warnings"):
                    lines.append(f"偏见预警：{'; '.join(rec['bias_warnings'][:3])}")
                if rec.get("creative_suggestions"):
                    lines.append(f"创新建议：{'; '.join(rec['creative_suggestions'][:3])}")
                return "\n".join(lines) if lines else "暂无推荐"
            if tool_name == "analyze_weaknesses":
                draft = params.get("draft", host.draft or "")
                pid = params.get("project_id", "")
                if not draft:
                    return "无草稿可分析"
                pdb = host._get_pdb()
                if not pdb:
                    return "个性化数据库不可用，无法分析"
                if not pid:
                    return "未提供项目ID，无法分析"
                try:
                    return pdb.analyze_weaknesses(pid, draft)
                except Exception as e:
                    return f"分析异常：{e}"

            # ── 诊断工具 ──
            if tool_name == "diagnose_text":
                text = params.get("text", host.draft or "")
                if not text:
                    return "无文本可诊断"
                findings = kb.diagnose_text(text) if kb else []
                if not findings:
                    return "未发现文本错误"
                lines = []
                for f in findings[:8]:
                    lines.append(f"- [{f.get('severity', '')}] {f.get('diagnosis', '')} -> {f.get('prescription', '')}")
                return "\n".join(lines)
            if tool_name == "diagnose_format":
                text = params.get("text", host.draft or "")
                if not text:
                    return "无文本可诊断"
                findings = kb.diagnose_format(text) if kb else []
                if not findings:
                    return "格式符合规范"
                lines = []
                for f in findings[:8]:
                    lines.append(f"- [{f.get('severity', '')}] {f.get('diagnosis', '')} -> {f.get('prescription', '')}")
                return "\n".join(lines)

            # ── 导入工具 ──
            if tool_name == "import_from_url":
                url = params.get("url", "")
                if not url:
                    return "请提供URL"
                try:
                    from ..utils.url_importer import URLDocumentImporter
                    importer = URLDocumentImporter()
                    doc = importer.import_from_url(url)
                    if doc.import_notes and "无法" in doc.import_notes:
                        return doc.import_notes
                    parts = [f"标题：{doc.title}", f"来源：{doc.source_site}", f"字数：{doc.word_count}"]
                    if doc.keywords:
                        parts.append(f"关键词：{', '.join(doc.keywords[:5])}")
                    if doc.style_patterns:
                        parts.append(f"语言特征：{', '.join(doc.style_patterns[:3])}")
                    parts.append(f"正文预览：{doc.content[:200]}...")
                    return "\n".join(parts)
                except Exception as e:
                    return f"导入失败：{e}"
            if tool_name == "import_from_text":
                title = params.get("title", "未命名素材")
                content = params.get("content", "")
                if not content:
                    return "请提供文本内容"
                try:
                    from ..utils.url_importer import URLDocumentImporter
                    importer = URLDocumentImporter()
                    doc = importer.import_from_text(title, content, source=params.get("source", "手动导入"))
                    # 如定义了 project_id，同步保存到该项目资料库（修复 N8：真实存储 + 特征提取）
                    pid = params.get("project_id", "")
                    pdb = host._get_pdb()
                    if pdb and pid:
                        try:
                            pdb.add_reference_article(
                                pid,
                                title=doc.title,
                                content=doc.content,
                                style_notes="；".join((doc.style_patterns or [])[:3]),
                            )
                        except Exception:
                            pass
                    fmt = doc.format.value if hasattr(doc.format, "value") else str(doc.format)
                    parts = [f"标题：{doc.title}", f"格式类型：{fmt}", f"字数：{doc.word_count}"]
                    if doc.keywords:
                        parts.append(f"关键词：{', '.join(doc.keywords[:5])}")
                    if doc.style_patterns:
                        parts.append(f"语言特征：{', '.join(doc.style_patterns[:3])}")
                    return "\n".join(parts)
                except Exception as e:
                    return f"导入失败：{e}"

            return ""
        except Exception as e:
            host._log_agent("Tool", f"工具 [{tool_name}] 执行异常: {e}")
            return ""

    def get_tool_execution_log(self) -> List[Dict[str, Any]]:
        """获取工具执行日志（供前端展示）"""
        return self._tool_execution_log
