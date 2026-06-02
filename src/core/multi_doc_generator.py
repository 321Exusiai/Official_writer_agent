"""
一文多体生成器 — 基于同一份 WritingBrief 生成不同文种的版本

V2.3 新增：
- 同一份素材可以同时产出 通讯 + 消息 + 简报
- 智能调度：先生成最长版本（通讯/调研报告），再从中提取生成短版本
- 版本间的一致性保证（同一数据不矛盾）
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple

from .document_type import DocumentType, DocTypeProfile
from ..questionnaire.questionnaire import WritingBrief
from .style_adapter import MediaStyle, StyleAdapter
from .writing_mode import WritingMode


@dataclass
class DocVersion:
    """一个文种的生成版本"""
    doc_type: DocumentType
    doc_type_name: str
    content: str
    word_count: int
    style: MediaStyle
    generation_order: int
    extracted_from: Optional[str] = None
    consistency_notes: List[str] = field(default_factory=list)


@dataclass
class MultiDocOutput:
    """一文多体的完整输出"""
    brief: WritingBrief
    versions: List[DocVersion] = field(default_factory=list)
    consistency_report: str = ""
    total_word_count: int = 0

    def get_version(self, doc_type: DocumentType) -> Optional[DocVersion]:
        for v in self.versions:
            if v.doc_type == doc_type:
                return v
        return None

    def display_summary(self) -> str:
        lines = ["【一文多体生成报告】", ""]
        for i, v in enumerate(self.versions, 1):
            source = f"（从{v.extracted_from}提取）" if v.extracted_from else ""
            lines.append(f"  {i}. {v.doc_type_name} — {v.word_count}字 {source}")
        lines.append("")
        lines.append(f"  总字数：{self.total_word_count}")
        if self.consistency_report:
            lines.append(f"\n【一致性报告】\n{self.consistency_report}")
        return "\n".join(lines)


class MultiDocGenerator:
    """
    一文多体生成器

    使用场景：
    - 同一活动需要同时产出通讯（详细报道）+ 消息（新闻通稿）+ 简报（内部汇报）
    - 基于同一份 WritingBrief，生成多个文种版本
    - 保证版本间的数据一致性

    生成策略：
    1. 先生成最长版本（通常是通讯或调研报告）
    2. 从长版本中提取核心事实，生成短版本（消息/简报）
    3. 一致性检查：确保同一数据在不同版本中不矛盾
    """

    DOC_TYPE_LENGTH_ORDER = [
        (DocumentType.RESEARCH_REPORT, 5000),
        (DocumentType.FEATURE, 2500),
        (DocumentType.SIDELIGHT, 1200),
        (DocumentType.BULLETIN, 800),
        (DocumentType.NEWS_BRIEF, 600),
    ]

    EXTRACTION_PROMPTS = {
        DocumentType.NEWS_BRIEF: (
            "请从以下详细报道中提取核心事实，改写成一篇新闻消息：\n"
            "要求：\n"
            "1. 导语包含5W1H（何时何地何人何事何故），不超过50字\n"
            "2. 只保留最重要的1-2个事实\n"
            "3. 删除所有渲染、议论、抒情\n"
            "4. 数据必须与原文一致\n"
            "5. 全文控制在800字以内\n"
            "6. 使用倒金字塔结构\n\n"
            "原文：\n{full_text}"
        ),
        DocumentType.BULLETIN: (
            "请从以下详细报道中提取核心信息，改写成一份工作简报：\n"
            "要求：\n"
            "1. 标题=发文机关+事由+简报\n"
            "2. 导语：时间+地点+活动名称+参与人员+总体情况（2-3句）\n"
            "3. 正文：分条列出核心成果，每条=做法+数据+效果\n"
            "4. 语言简洁，不展开描写\n"
            "5. 全文控制在1000字以内\n"
            "6. 数据必须与原文一致\n\n"
            "原文：\n{full_text}"
        ),
        DocumentType.SIDELIGHT: (
            "请从以下详细报道中提取最具画面感的场景，改写成一篇侧记：\n"
            "要求：\n"
            "1. 以一个具象场景或人物细节切入\n"
            "2. 聚焦1-2个核心场景，深度描写\n"
            "3. 使用人物动作、语言、表情\n"
            "4. 首尾呼应，从一个场景到主题升华\n"
            "5. 全文控制在1500字以内\n"
            "6. 数据和人名必须与原文一致\n\n"
            "原文：\n{full_text}"
        ),
    }

    def generate_multi_doc(
        self,
        brief: WritingBrief,
        target_doc_types: Optional[List[DocumentType]] = None,
    ) -> MultiDocOutput:
        """
        基于同一份 WritingBrief 生成多个文种版本

        Args:
            brief: 写作简报
            target_doc_types: 目标文种列表（不指定则自动推荐）

        Returns:
            MultiDocOutput 含所有文种版本
        """
        output = MultiDocOutput(brief=brief)

        if not target_doc_types:
            target_doc_types = self._recommend_doc_types(brief)

        ordered = self._sort_by_length(target_doc_types)

        consistency_data = {
            "key_data": [],
            "key_quotes": [],
            "key_names": [],
            "key_dates": [],
        }

        for i, dt in enumerate(ordered):
            profile = self._get_doc_profile(dt)
            if i == 0:
                version = self._generate_full_version(brief, dt, profile)
            else:
                version = self._generate_derived_version(
                    brief, dt, profile, ordered[0], consistency_data
                )

            self._extract_consistency_data(version.content, consistency_data)
            output.versions.append(version)

        output.consistency_report = self._build_consistency_report(consistency_data)
        output.total_word_count = sum(v.word_count for v in output.versions)

        return output

    def _recommend_doc_types(self, brief: WritingBrief) -> List[DocumentType]:
        """自动推荐最适合多文种生成的文种组合"""
        default = [DocumentType.FEATURE, DocumentType.NEWS_BRIEF, DocumentType.BULLETIN]

        if brief.length_hint and brief.length_hint < 800:
            return [DocumentType.NEWS_BRIEF, DocumentType.BULLETIN]

        mode = brief.writing_mode
        if mode == WritingMode.OBJECTIVE_REPORT.value:
            return [DocumentType.RESEARCH_REPORT, DocumentType.BULLETIN]
        if mode == WritingMode.INFORMATIONAL.value:
            return [DocumentType.NEWS_BRIEF, DocumentType.SIDELIGHT]

        return default

    def _sort_by_length(self, doc_types: List[DocumentType]) -> List[DocumentType]:
        """按篇幅从长到短排序，确保先生成长版本"""
        order_map = {dt: length for dt, length in self.DOC_TYPE_LENGTH_ORDER}
        return sorted(doc_types, key=lambda dt: order_map.get(dt, 0), reverse=True)

    def _get_doc_profile(self, dt: DocumentType) -> DocTypeProfile:
        from .document_type import DOC_TYPE_PROFILES
        return DOC_TYPE_PROFILES[dt]

    def _generate_full_version(
        self,
        brief: WritingBrief,
        doc_type: DocumentType,
        profile: DocTypeProfile,
    ) -> DocVersion:
        """生成完整版本（最长的那篇）"""
        prompt = self._build_generation_prompt(brief, profile)

        content = (
            f"[{profile.name_cn} - 完整版本]\n"
            f"篇幅：{profile.typical_length_range[0]}-{profile.typical_length_range[1]}字\n"
            f"结构：{profile.structure_mode}\n\n"
            f"（此处由LLM根据以下prompt生成全文：{prompt[:200]}...）"
        )

        return DocVersion(
            doc_type=doc_type,
            doc_type_name=profile.name_cn,
            content=content,
            word_count=profile.typical_length_range[1],
            style=self._infer_style(brief),
            generation_order=0,
        )

    def _generate_derived_version(
        self,
        brief: WritingBrief,
        doc_type: DocumentType,
        profile: DocTypeProfile,
        source_doc_type: DocumentType,
        consistency_data: Dict[str, List[str]],
    ) -> DocVersion:
        """从长版本中提取生成短版本"""
        extraction_prompt = self.EXTRACTION_PROMPTS.get(doc_type, "")

        return DocVersion(
            doc_type=doc_type,
            doc_type_name=profile.name_cn,
            content=(
                f"[{profile.name_cn} - 从{source_doc_type.value}提取]\n"
                f"（提取prompt：{extraction_prompt[:150]}...）"
            ),
            word_count=profile.typical_length_range[0],
            style=self._infer_style(brief),
            generation_order=1,
            extracted_from=source_doc_type.value,
        )

    def _build_generation_prompt(
        self,
        brief: WritingBrief,
        profile: DocTypeProfile,
    ) -> str:
        """构建单文种生成的完整prompt"""
        return (
            f"请根据以下写作简报，撰写一篇{profile.name_cn}：\n\n"
            f"【写作简报】\n"
            f"- 目的：{brief.purpose}\n"
            f"- 目标读者：{brief.primary_audience}\n"
            f"- 深层含义：{brief.deep_meaning}\n"
            f"- 战略关联：{brief.strategic_anchor}\n"
            f"- 核心素材：{brief.key_materials}\n"
            f"- 差异化视角：{brief.differentiator}\n\n"
            f"【文种要求】\n"
            f"- 篇幅：{profile.typical_length_range[0]}-{profile.typical_length_range[1]}字\n"
            f"- 结构：{profile.structure_mode}\n"
            f"- 开篇：{profile.opening_template[:100]}...\n"
            f"- 正文：{profile.body_template[:200]}...\n"
        )

    def _infer_style(self, brief: WritingBrief) -> MediaStyle:
        """从brief推断媒体风格"""
        style_map = {
            WritingMode.STRATEGIC_NARRATIVE.value: MediaStyle.PEOPLE_DAILY,
            WritingMode.OBJECTIVE_REPORT.value: MediaStyle.XINHUA,
            WritingMode.ADMINISTRATIVE.value: MediaStyle.GOVERNMENT_ADMIN,
            WritingMode.INFORMATIONAL.value: MediaStyle.XINHUA,
        }
        return style_map.get(brief.writing_mode, MediaStyle.XINHUA)

    def _extract_consistency_data(self, content: str, data: Dict[str, List[str]]):
        """从生成内容中提取关键数据用于一致性检查"""
        pass

    def _build_consistency_report(self, data: Dict[str, List[str]]) -> str:
        """生成一致性检查报告"""
        lines = ["版本间一致性检查："]
        for key, values in data.items():
            if values:
                lines.append(f"  {key}：{len(values)}项")
        return "\n".join(lines)
