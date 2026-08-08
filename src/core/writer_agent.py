"""
写作 Agent — 根据写作简报、风格参数和文种模板生成初稿

核心改进（V2）：
1. 写作原则不再硬编码为"五大原则"，而是根据 WritingMode 动态注入
2. 每种模式有独立的内容取舍法则和语言规范
3. 兼容旧版API（不传mode时默认使用STRATEGIC_NARRATIVE）
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any

from .writing_mode import (
    WritingMode,
    get_mode_profile,
)
from ..config.tool_definitions import get_tool_definitions_for_prompt
from ..config.system_prompt import get_core_prompt
from ..utils.response_cache import cached_prompt, store_prompt


@dataclass
class WriterConfig:
    writing_brief: Any = None
    style_profile: Any = None
    doc_type_profile: Any = None
    raw_materials: str = ""
    audience: str = "external"
    writing_mode: WritingMode = WritingMode.STRATEGIC_NARRATIVE
    env_state: Any = None  # EnvState 对象，由 orchestrator 构建
    user_memory: str = ""
    style_adapter: Any = None  # StyleAdapter 实例，用于风格注入（含强度缩放/混合）
    style_blend: Any = None    # StyleBlend 混合风格建议（可选）


class WriterAgent:

    def __init__(self, knowledge_base=None):
        self.config: Optional[WriterConfig] = None
        # 可选集成知识库，用于注入范文参考（修复文档承诺但未实现的功能）
        self.knowledge_base = knowledge_base

    def configure(self, config: WriterConfig):
        self.config = config

    def set_knowledge_base(self, knowledge_base):
        """注入知识库实例（用于范文参考）"""
        self.knowledge_base = knowledge_base

    def _get_mode(self) -> WritingMode:
        if self.config and self.config.writing_mode:
            return self.config.writing_mode
        return WritingMode.STRATEGIC_NARRATIVE

    def _get_principles(self) -> str:
        """根据模式获取写作原则（注入到System Prompt）"""
        mode = self._get_mode()
        profile = get_mode_profile(mode)

        lines = [f"【写作原则 — {profile.name}】", ""]
        for i, p in enumerate(profile.principles, 1):
            lines.append(f"{i}. {p['name']}：{p['description']}")
            if p.get("check"):
                lines.append(f"   自查：{p['check']}")
            lines.append("")

        return "\n".join(lines)

    def _get_content_rules(self) -> str:
        """根据模式获取内容取舍法则"""
        mode = self._get_mode()
        profile = get_mode_profile(mode)

        lines = ["【内容取舍法则】", ""]
        lines.append("必须写：")
        for item in profile.content_rules.get("must_write", []):
            lines.append(f"  - {item}")
        lines.append("")
        lines.append("必须掠过：")
        for item in profile.content_rules.get("must_skip", []):
            lines.append(f"  - {item}")

        return "\n".join(lines)

    def _get_forbidden_patterns(self) -> str:
        """根据模式获取禁止表述"""
        mode = self._get_mode()
        profile = get_mode_profile(mode)

        lines = ["【禁止使用以下表述】", ""]
        for pattern in profile.forbidden_patterns[:10]:
            lines.append(f"  ✗ {pattern}")

        return "\n".join(lines)

    def _get_language_guidelines(self) -> str:
        """根据模式获取语言规范"""
        mode = self._get_mode()
        profile = get_mode_profile(mode)

        lines = ["【语言规范】", ""]
        for i, guideline in enumerate(profile.language_guidelines, 1):
            lines.append(f"  {i}. {guideline}")

        return "\n".join(lines)

    def _get_core_philosophy(self) -> str:
        """根据模式获取核心理念（分类化）"""
        mode = self._get_mode()
        # 按文体类别分类的核心理念，避免"一刀切"bias
        philosophy_map = {
            WritingMode.ADMINISTRATIVE: (
                "以文辅政——说清楚事情、说清楚意图、格式规范、语言四要求。"
                "原则：一文一旨、开门见山、直笔不曲。"
                "公文是工具不是艺术品，不渲染不拔高不抒情。"
            ),
            WritingMode.STRATEGIC_NARRATIVE: (
                "以事叙事、以事明理——回答三个问题："
                "（1）这件事证明了我们是谁？"
                "（2）我们正走向何方？"
                "（3）这件事对组织有什么价值？"
                "流水账是最大的失败。"
            ),
            WritingMode.OBJECTIVE_REPORT: (
                "实事求是——让事实自己说话，交叉验证、矛盾分析、对策可操作。"
                "绝不渲染拔高，单一信源不可作为核心结论的唯一支撑。"
            ),
            WritingMode.INFORMATIONAL: (
                "信息优先——5W1H完整、新闻价值判断、倒金字塔结构。"
                "客观陈述，不渲染不拔高，剥离主观性。"
            ),
            WritingMode.YOUTH_ENGAGEMENT: (
                "思想引领+青年话语——娱乐外壳下必有价值内核（立德树人）。"
                "用青年听得进的方式说话，去爹味去官腔去AI味。"
            ),
        }
        return philosophy_map.get(mode, get_mode_profile(mode).tagline)

    def _get_format_constraints(self) -> str:
        """获取格式约束（仅行政公文模式生效）"""
        mode = self._get_mode()
        if mode != WritingMode.ADMINISTRATIVE:
            return ""
        return (
            "# 格式约束（严格执行GB/T 9704-2012）\n"
            "- 标题三要素：发文机关+事由+文种（'XX单位关于XX的通知'）\n"
            "- 主送机关：使用全称或规范化简称，顶格\n"
            "- 正文：一文一旨，层次清晰，条理清楚，段落层次（一、（一）、1、（1））\n"
            "- 成文日期：阿拉伯数字（2025年7月27日，不写07月）\n"
            "- 引文格式：先引标题全称，后括号注文号\n"
            "- 数字用法：全文统一（GB/T 15835）\n"
            "- 结尾用语：请示'妥否，请批示'；函'请予函复'；通知'特此通知'；批复'此复'\n"
            "- 表达方式：用直笔不用曲笔，不用比喻拟人夸张，不抒情\n"
        )

    def build_system_prompt(self) -> str:
        if not self.config:
            raise ValueError("请先调用configure()设置配置")

        brief = self.config.writing_brief
        style = self.config.style_profile
        doc = self.config.doc_type_profile
        mode = self._get_mode()
        profile = get_mode_profile(mode)

        cache_key = f"sys_{mode.value}_{style.style.value if style else 'none'}"
        cached = cached_prompt("writer_system", cache_key)
        if cached:
            prompt_parts = [cached]
        else:
            prompt_parts = [
                "# 全局岗位说明书（系统提示词核心）",
                get_core_prompt(),
                "",
                "# 模式专属配置",
                f"当前模式：{profile.name}",
                f"核心理念：{self._get_core_philosophy()}",
                "",
                self._get_principles(),
                "",
                self._get_content_rules(),
                "",
            ]
            # 行政公文模式注入格式约束
            format_constraints = self._get_format_constraints()
            if format_constraints:
                prompt_parts.extend([format_constraints, ""])
            prompt_parts.append("# 写作简报（本次任务的核心输入）")
            static_part = "\n".join(prompt_parts)
            store_prompt("writer_system", static_part, cache_key)

        # 环境状态（EnvState 动态注入）
        # 注意：purpose/audience/doc_type/style/length 在下游"写作简报""文种规范""风格要求"段落有详细版本，
        # render() 只注入下游没有的维度（模式/子类型/阶段/风格强度/extra），避免重复
        env_state = getattr(self.config, "env_state", None)
        if env_state is not None:
            from ..config.system_prompt import EnvState
            if isinstance(env_state, EnvState):
                env_text = env_state.render(
                    exclude_fields=["purpose", "primary_audience", "doc_type", "length_hint"]
                )
                if env_text:
                    prompt_parts.extend([
                        "# 环境状态（当前任务上下文）",
                        env_text,
                        "",
                    ])

        # 用户记忆（跨会话个性化注入）
        memory_text = getattr(self.config, "user_memory", "")
        if memory_text:
            prompt_parts.extend([
                "# 用户记忆（该用户的写作偏好与历史，写作时请自然贴合，不要生硬提及）",
                memory_text,
                "",
            ])

        if brief:
            prompt_parts.extend([
                f"核心目的：{getattr(brief, 'purpose', '未指定')}",
                f"第一读者：{getattr(brief, 'primary_audience', '未指定')}",
                f"深层含义/核心发现：{getattr(brief, 'deep_meaning', '未指定')}",
                f"战略关联/依据：{getattr(brief, 'strategic_anchor', '未指定')}",
                f"借势机会/背景：{getattr(brief, 'opportunity_context', '未指定')}",
                f"核心素材/数据：{getattr(brief, 'key_materials', '未指定')}",
                f"差异化视角：{getattr(brief, 'differentiator', '未指定')}",
                "",
            ])

        if doc:
            prompt_parts.extend([
                "# 文种规范",
                f"当前文种：{doc.name_cn}",
                f"篇幅范围：{doc.typical_length_range[0]}-{doc.typical_length_range[1]}字",
                f"结构模式：{doc.structure_mode}",
                f"对标媒体：{doc.benchmark_media}",
                "",
                f"【开篇模板】{doc.opening_template}",
                f"【正文模板】{doc.body_template}",
                f"【结尾模板】{doc.closing_template}",
                "",
            ])
            # 注入格式化用语（行政公文模式，来自知识库工具）
            formulaic_text = self._get_formulaic_reference()
            if formulaic_text:
                prompt_parts.extend([
                    "【工具结果：格式化用语检索】",
                    formulaic_text,
                    "【/工具结果】",
                    "",
                ])

        if style:
            # 优先使用 StyleAdapter 风格注入（含强度缩放/混合风格逻辑，修复 N6 死代码）
            style_adapter = getattr(self.config, "style_adapter", None)
            if style_adapter is not None:
                style_blend = getattr(self.config, "style_blend", None)
                try:
                    injection = style_adapter.get_system_prompt_injection(style, style_blend)
                except Exception:
                    injection = ""
                if injection:
                    prompt_parts.extend(["# 风格要求", injection, ""])
            else:
                prompt_parts.extend([
                    "# 风格要求",
                    f"当前风格：{style.name}",
                    f"叙事视角：{style.narrative_perspective}",
                    f"情感基调：{style.emotional_tone}",
                    "",
                    "【参考开头示例】",
                    style.example_opening,
                    "",
                    "【参考结尾示例】",
                    style.example_closing,
                    "",
                ])

        prompt_parts.extend([
            self._get_language_guidelines(),
            "",
            self._get_forbidden_patterns(),
            "",
        ])

        # 注入范文参考（来自知识库工具）
        exemplar_text = self._get_exemplar_reference()
        if exemplar_text:
            prompt_parts.extend([
                "【工具结果：范文检索】",
                "以下内容由知识库工具返回，仅供学习结构和语言风格，禁止照抄：",
                exemplar_text,
                "【/工具结果】",
                "",
            ])

        # 注入可用工具清单（工具定义，来自 tool_definitions）
        prompt_parts.extend([
            get_tool_definitions_for_prompt(phases=["pre_writing", "during_writing"]),
            "",
        ])

        return "\n".join(prompt_parts)

    def _get_exemplar_reference(self) -> str:
        """从知识库获取当前模式的压缩范文摘要"""
        if not self.knowledge_base:
            return ""
        try:
            mode = self._get_mode()
            mode_value = mode.value if hasattr(mode, 'value') else str(mode)
            exemplars_text = self.knowledge_base.get_exemplars_for_prompt(mode_value, max_exemplars=1)
            return exemplars_text if exemplars_text else ""
        except Exception:
            return ""

    def _get_formulaic_reference(self) -> str:
        """从知识库获取当前文种的格式化用语（仅行政公文模式）"""
        mode = self._get_mode()
        if mode != WritingMode.ADMINISTRATIVE:
            return ""
        if not self.knowledge_base:
            return ""
        try:
            doc = self.config.doc_type_profile
            if not doc:
                return ""
            return self.knowledge_base.get_formulaic_for_prompt(doc.name_cn)
        except Exception:
            return ""

    def build_user_prompt(self) -> str:
        if not self.config:
            raise ValueError("请先调用configure()设置配置")

        mode = self._get_mode()
        profile = get_mode_profile(mode)

        return f"""
请根据以上System Prompt中的全部要求，使用以下原始材料，生成一篇完整的公文。

【写作模式】{profile.name}
【当前模式对标参考】{'、'.join(profile.benchmark_sources[:3])}

【原始材料】
{self.config.raw_materials if self.config.raw_materials else '（无原始材料，请根据写作简报中的核心素材自行组织内容）'}

【输出要求】
1. 严格遵循System Prompt中指定的文种规范和风格要求
2. 标题格式：发文机关名称 + 事由 + 文种
3. 字数控制在{self.config.doc_type_profile.typical_length_range[0] if self.config.doc_type_profile else 800}-{self.config.doc_type_profile.typical_length_range[1] if self.config.doc_type_profile else 2000}字之间
4. 避免出现该模式不推荐的表述（见System Prompt中的禁止列表）
5. 如有真实素材，优先使用直接引语和具体数据
6. 遵循“高级行文策略”，避免解释自身的写作逻辑，像真正的高级人类作者一样用事实、结构和细节说话。
"""

    def generate_outline(self) -> str:
        if not self.config:
            raise ValueError("请先调用configure()设置配置")

        doc = self.config.doc_type_profile
        brief = self.config.writing_brief
        mode = self._get_mode()
        profile = get_mode_profile(mode)

        return f"""
═══════════════════════════════════════════
  文 章 大 纲
═══════════════════════════════════════════

【写作模式】{profile.name}
【文种】{doc.name_cn if doc else '未指定'}（{doc.benchmark_media if doc else '通用'}风格）
【篇幅】{doc.typical_length_range[0] if doc else 800}-{doc.typical_length_range[1] if doc else 2000}字
【核心目的】{getattr(brief, 'purpose', '未指定') if brief else '未指定'}
【第一读者】{getattr(brief, 'primary_audience', '未指定') if brief else '未指定'}

【适用写作原则】
{chr(10).join(f'  {i+1}. {p["name"]}' for i, p in enumerate(profile.principles))}

【结构规划】
{doc.opening_template if doc else '【开篇】待指定'}

{doc.body_template if doc else '【正文】待指定'}

{doc.closing_template if doc else '【结尾】待指定'}

【关键素材提醒】
{getattr(brief, 'key_materials', '未指定') if brief else '未指定'}

═══════════════════════════════════════════
以上大纲是否确认？确认后将生成完整初稿。
"""

    def get_full_prompt(self) -> Dict[str, str]:
        return {
            "system": self.build_system_prompt(),
            "user": self.build_user_prompt(),
        }
