"""
ReviewPipeline — 审查流程 Mixin（重构阶段 1，从 Orchestrator 提取）

以 Mixin 方式注入 Orchestrator，负责：
- 多智能体协作审查（规则诊断 + LLM 深度审查迭代闭环）
- 审查分歧检测与辩论协商（共识落实到稿件）
- HITL（人在回路）：问题列表、手动修复、重新审查、草稿更新

依赖：本 Mixin 与 Orchestrator 共享 self 命名空间，可直接访问
reviewer/draft/writing_mode/coordinator/_build_env_state/_call_llm 等。
"""

import re
from typing import List, Dict, Optional, Any, Tuple


class ReviewPipeline:
    """审查流程 Mixin：审查迭代、辩论协商与 HITL 方法。"""

    # ═══════════════════════════════════════════════════════════
    # 审查阶段（模式感知 + 迭代式审查 V2.1 + HITL 循环 V2.2）
    # ═══════════════════════════════════════════════════════════

    def review(self, progress_callback=None, llm_depth_review: bool = True) -> List[Dict[str, Any]]:
        """
        多智能体协作审查流程（V3.1 核心改进：辩论 + LLM 审查真正生效）

        流程：
          1. Writer 自检 + Reviewer 规则审查 + 自动修复
          2. LLM 深度审查（每轮真正调用 LLM）
          3. Writer vs Reviewer 分歧时自动触发辩论
          4. 生成审查总结

        Args:
            progress_callback: 可选进度回调
            llm_depth_review: 是否启用 LLM 深度审查（默认 True）
        """
        def _notify(progress, desc):
            if progress_callback:
                progress_callback(progress, desc)

        if not self.draft:
            raise ValueError("请先调用write()生成初稿")

        try:
            self.reviewer.set_mode(self.writing_mode)
            self.review_results = []

            self._log_agent("系统", "开始多轮迭代审查（规则诊断 + LLM 深度审查）")

            # 更新 coordinator 上下文
            mode_value = self.writing_mode.value if hasattr(self.writing_mode, 'value') else str(self.writing_mode)
            self.coordinator.set_context(
                raw_materials="",  # 审查阶段不再关注原始素材
                writing_mode=mode_value,
                draft_word_count=len(self.draft) if self.draft else 0,
                has_style_conflict=self._detect_style_conflict(),
            )

            # 第1步：规则诊断 + 自动修复
            original_draft = self.draft
            review_env_text = self._build_env_state(
                "审查阶段：规则引擎逐轮诊断并自动修复，随后进行 LLM 深度审查。"
            ).render(exclude_fields=["purpose", "primary_audience", "length_hint"])
            final_draft, iteration_results = self.reviewer.iterate_review(
                draft=original_draft,
                mode=self.writing_mode,
                brief=self.brief,
                env_state=review_env_text,
            )

            if final_draft != original_draft:
                self.draft = final_draft
                self._log_agent("Reviewer", f"规则修复完成，草稿从 {len(original_draft)} 字 → {len(final_draft)} 字")

            # 第2步：LLM 真迭代审查 — 审→改→审 闭环
            if llm_depth_review:
                _notify(0.4, "LLM 迭代审查中（审→改→审）...")
                iteration_results = self._run_llm_iterative_review(iteration_results)

            # 第3步：检测 Writer 与 Reviewer 分歧，触发辩论（共识落实到稿件）
            _notify(0.7, "检测Agent分歧，必要时启动辩论...")
            debate_triggered, _ = self._check_and_run_debate(iteration_results)
            if debate_triggered:
                self._log_agent("Debater", "辩论完成，已达成共识并记录")

            # 更新最终审查结果
            self.review_results = self.reviewer.review_history
            self.review_summary_display = self._build_review_summary_display(iteration_results)
            self._last_iteration_results = iteration_results

            self._log_agent("系统", f"审查完成，共 {len(iteration_results)} 轮（含 {'AI深度审查' if llm_depth_review else '规则审查'}）")

            if self._on_review_done:
                self._on_review_done(iteration_results)

            return iteration_results
        except Exception as e:
            # 惰性导入：避免 Mixin 模块与 orchestrator 模块循环导入（运行时 orchestrator 已加载完毕）
            from .orchestrator import OrchestratorState
            self.state = OrchestratorState.ERROR
            self._log_agent("系统", f"审查流程异常: {e}")
            return []

    def _build_llm_review_prompt(
        self,
        draft: str,
        iteration_count: int,
        version: int,
        auto_findings: List[Dict[str, Any]],
    ) -> str:
        """构建 LLM 深度审查的 system prompt（核心提示词 + 环境状态 + 记忆 + 工具清单 + 审查员指令）"""
        from ..config.tool_definitions import get_tool_definitions_for_prompt
        from ..config.system_prompt import get_core_prompt
        # 1.4：注入迭代维度（总轮数/当前版本/上一轮问题），避免重复报告同一问题
        env_state = self._build_env_state(
            "审查阶段：按当前模式的多维标准逐轮检查稿件，针对上一轮发现的问题持续改进。"
        )
        env_state.iteration_count = iteration_count
        env_state.draft_version = version
        env_state.previous_issues = "；".join(
            str(f.get("diagnosis", "")) for f in (auto_findings or [])[:5]
        )
        env_text = env_state.render(exclude_fields=["purpose", "primary_audience", "length_hint"])
        # 1.3：审查只注入"常见错误"类记忆，避免偏好信息干扰审查标准
        memory_text = ""
        pdb = self._get_pdb()
        if pdb:
            try:
                mem = pdb.get_memory_summary(None, focus="errors")
                if mem and mem != "无用户数据":
                    memory_text = mem
            except Exception:
                pass
        memory_text = memory_text or self.user_memory or "（暂无历史记忆）"
        return (
            get_core_prompt()
            + "\n\n# 环境状态（审查阶段）\n" + env_text
            + "\n\n# 用户历史常见错误（审查时针对性核对，不要生硬提及）\n" + memory_text
            + "\n\n# 审查员专属指令\n"
            "你是公文审查员。按给定维度逐段检查稿件，标注问题位置、严重程度和修改建议。"
            "审查标准按文体区分：法定公文查格式规范（GB/T 9704-2012）和语言四要求（准确、简明、朴实、得体），"
            "新闻通讯查主体性和叙事质量，事务文书查信息完整性和结构，新媒体查话语方式。"
            "发现问题要具体：指出哪一段哪一句，说明为什么是问题，给出修改方向。不要泛泛而谈。"
            "\n\n可调用工具（需要查术语定义、范文、格式化用语、文种规范时，在输出末尾追加工具调用标记）：\n"
            + get_tool_definitions_for_prompt(phases=["during_writing", "post_writing"])
            + "\n工具调用标记格式：[TOOL_CALL: 工具名(参数=值, 参数=值)]\n"
            "\n\n输出格式（每个问题一段）：\n"
            "问题1：<问题描述>\n"
            "  位置：<哪一段/哪一句>\n"
            "  严重程度：<严重/重要/轻微>\n"
            "  建议：<修改方向>\n"
            "（没有问题时输出：无问题）"
        )

    def _llm_revise_draft(self, draft: str, instruction: str) -> str:
        """
        让主笔 LLM 基于审查意见/辩论共识修订稿件，返回修订后的完整文本。

        返回空串表示修订失败或修订无变化（调用方保留原稿，防死循环）。
        """
        if not draft or not instruction:
            return ""
        from ..config.system_prompt import get_core_prompt
        system_prompt = (
            get_core_prompt()
            + "\n\n# 修订员专属指令\n"
            "你是主笔（Writer Agent）。请基于给定的修订指令对稿件进行修订："
            "逐条采纳合理的意见，保留原稿的合理内容与风格，"
            "输出修订后的完整稿件。只输出正文，不要输出任何说明、列表或元信息。"
        )
        user_prompt = f"## 修订指令\n{instruction}\n\n## 当前稿件\n{draft}"
        try:
            revised = self._call_llm_with_tool_loop(
                system_prompt, user_prompt, temperature=0.4, max_tokens=8000, use_cache=False
            )
            # 防死循环/防降级污染：修订无变化或 LLM 降级占位输出均视为未修改
            if not revised or revised.strip() == draft.strip():
                return ""
            if "【占位文本" in revised or "API 未配置" in revised:
                return ""
            return revised
        except Exception:
            return ""

    def _run_llm_iterative_review(
        self,
        iteration_results: List[Dict[str, Any]],
        max_llm_rounds: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        LLM 真迭代审查闭环：审→改→审

        以规则 iterate_review 的最终稿为起点：
          每轮：LLM 审查当前稿 → 无严重问题则停 → 否则 LLM 修订 → 再审修订版
        审查发现会触发新一轮修复（替代原"循环后并行审查、结果仅存储"的假迭代）。

        注意：循环有早停（无"严重/重要"问题即停），实际通常只消耗 1 轮；
        上限 3 轮仅在连续多轮仍有阻塞问题时才会用满，用于收敛顽固问题。

        Args:
            iteration_results: 规则 iterate_review 的轮次结果
            max_llm_rounds: LLM 迭代轮数上限（默认 3，有早停，控制成本）

        Returns:
            更新后的 iteration_results（在原列表上追加 LLM 迭代轮信息）
        """
        if not self.draft:
            return iteration_results

        current_draft = self.draft
        total_rounds = len(iteration_results)
        last_rule_findings = (
            iteration_results[-1].get("auto_findings_summary", [])
            if iteration_results else []
        )

        for r in range(max_llm_rounds):
            # 1. LLM 审查当前稿
            reviewer_system = self._build_llm_review_prompt(
                current_draft, total_rounds + r, total_rounds + r + 1, last_rule_findings
            )
            base_prompt = self.reviewer.build_review_prompt(current_draft, 0, self.brief)
            if not base_prompt:
                break
            full_prompt = f"{base_prompt}\n\n请按要求的格式输出审查结果。"
            # TR板块：审查阶段工具闭环（执行工具并把结果回传模型整合）
            raw = self._call_llm_with_tool_loop(reviewer_system, full_prompt, temperature=0.3, max_tokens=4000)
            parsed = self._parse_llm_review(raw)

            llm_round = {
                "round": f"LLM迭代审查第{r+1}轮",
                "draft_snapshot": current_draft,
                "findings_count": len(parsed),
                "auto_findings_summary": [],
                "fixes_applied": 0,
                "review_prompt": full_prompt,
                "passed": len(parsed) == 0,
                "llm_review": {"raw_response": raw, "parsed_findings": parsed, "round": f"LLM第{r+1}轮"},
            }
            self._log_agent("Reviewer", f"LLM迭代第{r+1}轮：发现 {len(parsed)} 个问题")

            # 2. 无阻塞问题（严重/重要）或达轮次上限 → 停
            has_blocking = any(f.get("severity") in ("严重", "重要") for f in parsed)
            if not has_blocking or r == max_llm_rounds - 1:
                iteration_results.append(llm_round)
                break

            # 3. LLM 基于审查发现修订稿件（真正的"改"）
            instruction_lines = []
            for f in parsed[:5]:
                instruction_lines.append(f"- [{f.get('severity', '')}] {f.get('issue', '')}")
                if f.get("location"):
                    instruction_lines.append(f"  位置：{f['location']}")
                if f.get("suggestion"):
                    instruction_lines.append(f"  建议：{f['suggestion']}")
            instruction = "请针对以下审查意见修订稿件：\n" + "\n".join(instruction_lines)
            revised = self._llm_revise_draft(current_draft, instruction)
            if not revised:
                iteration_results.append(llm_round)
                break

            llm_round["llm_revision"] = revised
            current_draft = revised
            self.draft = revised
            iteration_results.append(llm_round)
            self._log_agent("Writer", f"LLM迭代第{r+1}轮修订完成（{len(revised)} 字）")

        return iteration_results

    def _parse_llm_review(self, raw: str) -> List[Dict[str, str]]:
        """
        将 LLM 审查的原始文本解析为结构化问题列表。

        兼容两种格式：
        1. 规范格式（prompt中要求）：
           问题1：<问题描述>
             位置：<哪一段/哪一句>
             严重程度：<严重/重要/轻微>
             建议：<修改方向>
        2. 自由文本：按行智能拆分，尽力提取位置/严重程度/建议
        """
        if not raw or "无问题" in raw.strip():
            return []
        # LLM 不可用的降级/占位文本不应被当作审查发现（避免污染审查结果）
        if "【占位文本" in raw or "API 未配置" in raw:
            return []

        findings = []
        lines = raw.strip().splitlines()
        current = {}

        # 正则：匹配"问题N：..."或"- 问题：..."或"问题：..."
        problem_pattern = re.compile(r'^\s*(?:问题\s*\d*\s*[：:]\s*|\d+[、.．]\s*)')
        location_pattern = re.compile(r'^\s*(?:位置|出处|在哪|哪一段|哪一句)\s*[：:]\s*(.+)$')
        severity_pattern = re.compile(r'^\s*(?:严重程度|严重性|程度)\s*[：:]\s*(.+)$')
        suggestion_pattern = re.compile(r'^\s*(?:建议|修改建议|如何改|修改方向|建议修改)\s*[：:]\s*(.+)$')

        def flush():
            if current and current.get("issue"):
                findings.append(current.copy())
            current.clear()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 严重程度行
            m = severity_pattern.match(line)
            if m:
                current["severity"] = m.group(1).strip()
                continue

            # 位置行
            m = location_pattern.match(line)
            if m:
                current["location"] = m.group(1).strip()
                continue

            # 建议行
            m = suggestion_pattern.match(line)
            if m:
                current["suggestion"] = m.group(1).strip()
                continue

            # 问题行（新问题开始）
            if problem_pattern.match(line) or line.startswith("问题"):
                flush()
                issue_text = re.sub(r'^\s*问题\s*\d*\s*[：:]\s*', '', line)
                issue_text = re.sub(r'^\s*\d+[、.．]\s*', '', issue_text)
                current = {"issue": issue_text}
                continue

            # 普通行：追加到当前问题的描述或建议
            if current:
                if current.get("suggestion"):
                    current["suggestion"] += line
                elif current.get("issue"):
                    # 无标签的后续行，归入问题描述
                    current["issue"] += line

        flush()

        # 兜底：解析不出结构化问题时返回空（宁缺毋滥），
        # 避免把 LLM 的自由输出或降级文本误当作审查发现
        if not findings:
            return []

        # 补全缺失字段
        for f in findings:
            f.setdefault("severity", "轻微")
            f.setdefault("location", "")
            f.setdefault("suggestion", "")
        return findings

    def _check_and_run_debate(
        self, iteration_results: List[Dict[str, Any]]
    ) -> Tuple[bool, str]:
        """
        检测审查结果中是否存在 Writer 与 Reviewer 的分歧，
        如果发现问题较多且未通过，自动触发辩论，并把辩论共识落实到稿件修订。

        Returns:
            (是否触发辩论, 共识文本)。触发且达成共识时，self.draft 已按共识修订。
        """
        total_findings = sum(ir.get("findings_count", 0) for ir in iteration_results)
        failed_rounds = sum(1 for ir in iteration_results if not ir.get("passed", True))

        # 触发条件：未通过轮次 >= 2 或 发现问题 >= 5
        if failed_rounds < 2 and total_findings < 5:
            return False, ""

        # 构建双方立场
        writer_position = (
            f"撰写方认为：文稿基本符合要求，{total_findings}个问题中大部分属于格式修正。"
            f"建议在保持内容完整性的前提下，选择性采纳审查意见。"
        )
        reviewer_position = (
            f"审查方认为：发现{total_findings}个问题，{failed_rounds}轮未通过。"
            f"这些问题影响文稿质量和合规性，建议全部修正后再定稿。"
        )

        try:
            debate_result = self.coordinator.run_debate(
                topic=f"审查分歧：{total_findings}个问题待决议",
                writer_position=writer_position,
                reviewer_position=reviewer_position,
                max_rounds=1,
                llm_call=self._call_llm,
            )
            # 安全访问 consensus（可能是 str 或 dict）
            consensus_text = debate_result.consensus if isinstance(debate_result.consensus, str) else str(debate_result.consensus)
            self._log_agent("Debater", f"辩论共识: {consensus_text[:150]}")

            # 共识闭环：基于共识修订稿件，让辩论结果真正作用于内容
            if consensus_text and consensus_text.strip() and consensus_text != "None":
                instruction = f"以下是审查分歧的辩论共识，请据此修订稿件：\n{consensus_text}"
                revised = self._llm_revise_draft(self.draft, instruction)
                if revised:
                    self.draft = revised
                    self._log_agent("Debater", f"已按辩论共识修订稿件（{len(revised)} 字）")
            return True, consensus_text
        except Exception as e:
            self._log_agent("Debater", f"辩论异常: {e}")
            return False, ""

    def get_review_issues(self) -> List[Dict[str, Any]]:
        """获取当前审查中发现的所有问题（供 HITL 展示，含规则引擎与 LLM 深度审查）"""
        issues = []
        for i, summary in enumerate(self.reviewer.review_history):
            round_name = summary.round_name
            for finding in summary.findings:
                issues.append({
                    "round_index": i,
                    "round_name": round_name,
                    "draft_version": getattr(summary, 'draft_version', i + 1),
                    "source": "规则引擎",
                    "severity": finding.severity.value,
                    "issue": finding.issue,
                    "location": finding.location,
                    "suggestion": finding.suggestion,
                    "original_text": finding.original_text,
                    "suggested_revision": finding.suggested_revision,
                })

        # 合并 LLM 深度审查的结构化发现（parsed_findings）
        if self._last_iteration_results:
            for i, ir in enumerate(self._last_iteration_results):
                llm_data = ir.get("llm_review") or {}
                parsed = llm_data.get("parsed_findings") or []
                if not parsed:
                    continue
                round_name = ir.get("round", f"第{i+1}轮")
                for f in parsed:
                    issues.append({
                        "round_index": i,
                        "round_name": f"{round_name}（AI深度审查）",
                        "draft_version": i + 1,
                        "source": "AI深度审查",
                        "severity": f.get("severity", "轻微"),
                        "issue": f.get("issue", ""),
                        "location": f.get("location", ""),
                        "suggestion": f.get("suggestion", ""),
                        "original_text": "",
                        "suggested_revision": "",
                    })
        return issues

    def apply_manual_fix(self, round_index: int, finding_index: int) -> str:
        """手动触发对某个问题的自动修复，返回修复后的草稿"""
        if round_index >= len(self.reviewer.review_history):
            raise ValueError(f"审查轮次 {round_index} 不存在")
        result = self.reviewer.review_history[round_index]
        if finding_index >= len(result.findings):
            raise ValueError(f"问题索引 {finding_index} 不存在")
        finding = result.findings[finding_index]
        self.draft = self.reviewer._apply_fix(
            self.draft,
            {
                "error_key": finding.error_key,
                "matched_pattern": finding.original_text,
                "prescription": finding.suggestion,
                "severity": finding.severity.value,
            }
        )
        return self.draft

    def re_review(self, llm_depth_review: bool = True) -> List[Dict[str, Any]]:
        """
        在用户手动修改草稿后，重新执行审查（V3.1：与 review() 对齐）

        Args:
            llm_depth_review: 是否启用 LLM 深度审查（默认 True）
        """
        if not self.draft:
            raise ValueError("当前无草稿可审查")

        self.reviewer.set_mode(self.writing_mode)
        self.review_results = []

        # 更新 coordinator 上下文
        mode_value = self.writing_mode.value if hasattr(self.writing_mode, 'value') else str(self.writing_mode)
        self.coordinator.set_context(
            raw_materials="",
            writing_mode=mode_value,
            draft_word_count=len(self.draft),
            has_style_conflict=self._detect_style_conflict(),
        )

        self._log_agent("系统", "重新执行审查（规则诊断 + LLM 深度审查）")
        original_draft = self.draft
        self.draft, iteration_results = self.reviewer.iterate_review(
            draft=original_draft,
            mode=self.writing_mode,
            brief=self.brief,
        )

        if self.draft != original_draft:
            self._log_agent("Reviewer", f"重新修复完成，{len(original_draft)} 字 -> {len(self.draft)} 字")

        # LLM 真迭代审查（审→改→审）
        if llm_depth_review:
            iteration_results = self._run_llm_iterative_review(iteration_results)

        # 分歧检测与辩论（共识落实到稿件）
        self._check_and_run_debate(iteration_results)

        self.review_results = self.reviewer.review_history
        self.review_summary_display = self._build_review_summary_display(iteration_results)
        self._last_iteration_results = iteration_results

        if self._on_review_done:
            self._on_review_done(iteration_results)
        return iteration_results

    def update_draft(self, new_draft: str):
        """用户手动替换草稿"""
        self.draft = new_draft
