"""
写作 Agent — 根据写作简报、风格参数和文种模板生成初稿

核心改进（V2）：
1. 写作原则不再硬编码为"五大原则"，而是根据 WritingMode 动态注入
2. 每种模式有独立的内容取舍法则和语言规范
3. 兼容旧版API（不传mode时默认使用STRATEGIC_NARRATIVE）
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from .writing_mode import (
    WritingMode,
    ALL_PRINCIPLES,
    get_mode_profile,
)
from ..utils.response_cache import cached_prompt, store_prompt


FIVE_PRINCIPLES_LEGACY = """
【五大写作原则 — 硬约束（战略叙事模式专用）】

1. 主体性原则：镜头始终对准"我们"
   - 每句话的主语或叙述重心调整为"我们"
   - 落笔前自问：这句话是在讲对方，还是在讲我们？
   - 如果是在讲对方，那么这件事对我们意味着什么？

2. 赋能性原则：每段行程都必须回扣培养理念
   - 为每个板块设置"战略锚点"——点明"为什么是这里"
   - 不让任何一段行程成为脱离组织语境的"孤岛"

3. 借势性原则：以外部权威为组织背书
   - 记录外部权威观点后，主动建立与自身的关联
   - 借外部之锤，敲自家之钟

4. 成长性原则：用真实证据替代空泛表态
   - 用真实感言、具体体悟作为"证据"
   - 严禁使用"大家纷纷表示""深刻感受到"等空泛套话
   - 如果一段感言去掉后不影响叙事，果断删除

5. 战略性原则：全文服务于组织的长期发展
   - 结尾含蓄但坚定地传递"我们有方向、有资源、有行动力、有成果"
   - 读者读完后应产生"应该继续支持"的印象
"""


@dataclass
class WriterConfig:
    writing_brief: Any = None
    style_profile: Any = None
    doc_type_profile: Any = None
    raw_materials: str = ""
    audience: str = "external"
    writing_mode: WritingMode = WritingMode.STRATEGIC_NARRATIVE


class WriterAgent:

    def __init__(self):
        self.config: Optional[WriterConfig] = None

    def configure(self, config: WriterConfig):
        self.config = config

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
        """根据模式获取核心理念"""
        mode = self._get_mode()
        profile = get_mode_profile(mode)
        return profile.tagline

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
                "# 角色定义",
                f"你是一位资深的公文写作专家，当前工作在【{profile.name}】模式下。",
                f"核心理念：{self._get_core_philosophy()}",
                "",
                self._get_principles(),
                "",
                self._get_content_rules(),
                "",
                "# 写作简报（本次任务的核心输入）",
            ]
            static_part = "\n".join(prompt_parts)
            store_prompt("writer_system", static_part, cache_key)

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

        if style:
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
        ])

        return "\n".join(prompt_parts)

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
4. 严禁出现该模式禁止的表述（见System Prompt中的禁止列表）
5. 如有真实素材，优先使用直接引语和具体数据
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
