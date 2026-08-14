"""
知识库模块 — 范文库 + 错误诊断库 + 术语库 + 格式化用语库

V3.0 重大更新：
1. 新增压缩格式范文库（高保真低token）：提取骨架+语言特征+关键句式，不存储原文
2. 新增公文格式化用语库：按文种分类（批复/请示/函/通知/报告/纪要）
3. 新增格式错误模式：标题不规范、日期格式错误、引文不规范等
4. 每个写作模式至少2篇标杆范文（新闻奖+公文大赛双来源）

V3.1 架构调整（阶段0重构）：
- 将全部结构化数据从源码中剥离，存储到 data/*.json 外部文件
- 非开发者无需改代码即可维护知识库（编辑 JSON 即可）
- 源码仅保留：数据模型（dataclass）+ 检索逻辑

来源标注：
- 第33-34届中国新闻奖获奖作品
- 中央机关公文大赛特等奖作品
- 中央机关公文大赛16类分类标准
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
from enum import Enum


class KnowledgeCategory(Enum):
    EXEMPLAR = "exemplar"
    ERROR_PATTERN = "error_pattern"
    TERMINOLOGY = "terminology"
    TRANSITION = "transition"
    FORMULAIC = "formulaic"
    FORMAT_ERROR = "format_error"


# ═══════════════════════════════════════════════════════════════
# 压缩格式范文库（Compact Exemplar）
#
# 设计原则：
#   - 不存储原文（token消耗大）
#   - 提取骨架 + 关键句式 + 模式特征
#   - 注入时只取匹配当前写作模式/风格的部分
# ==================================================================

@dataclass
class CompactExemplar:
    """压缩格式标杆范文 — 只保留骨架和模式信息"""
    id: str
    title: str
    source: str
    doc_type: str
    style: str
    writing_mode: str
    award: str
    word_count: int

    # 结构化骨架（替代全文，token节省90%+）
    structure_skeleton: str = ""
    # 关键句式（3-5句最有代表性的句子）
    key_sentences: List[str] = field(default_factory=list)
    # 语言特征标签
    language_tags: List[str] = field(default_factory=list)
    # 可复用模式
    reusable_pattern: str = ""


@dataclass
class FormatError:
    """格式错误诊断条目"""
    id: str
    name: str
    description: str
    prescription: str
    severity: str
    category: str
    check_method: str


# ═══════════════════════════════════════════════════════════════
# 数据加载（数据与代码分离：全部数据存放于 data/*.json）
# ==================================================================

_DATA_DIR = Path(__file__).parent / "data"


def _load_data(filename: str):
    """从外部 JSON 数据文件加载知识库数据（非开发者可直接编辑 JSON 维护知识库）"""
    with open(_DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


# 范文库：data/exemplars.json
COMPACT_EXEMPLARS: Dict[str, CompactExemplar] = {
    eid: CompactExemplar(**data) for eid, data in _load_data("exemplars.json").items()
}
# 格式化用语库：data/formulaic.json
FORMULAIC_EXPRESSIONS: Dict[str, Dict[str, List[str]]] = _load_data("formulaic.json")
# 格式错误模式库：data/format_errors.json
FORMAT_ERRORS_DB: Dict[str, FormatError] = {
    fid: FormatError(**data) for fid, data in _load_data("format_errors.json").items()
}
# 常见写作错误模式库：data/error_patterns.json
ERROR_PATTERNS_DB: Dict[str, Dict] = _load_data("error_patterns.json")
# 术语库：data/terminology.json
TERMINOLOGY_DB = _load_data("terminology.json")
# 过渡词库：data/transitions.json
TRANSITION_PHRASES = _load_data("transitions.json")


# ═══════════════════════════════════════════════════════════════
# 知识库统一检索类
# ==================================================================

class KnowledgeBase:
    """知识库 — 统一知识检索接口（V3.0 增强版）"""

    def __init__(self):
        self.compact_exemplars = COMPACT_EXEMPLARS
        self.error_patterns = ERROR_PATTERNS_DB
        self.format_errors = FORMAT_ERRORS_DB
        self.terminology = TERMINOLOGY_DB
        self.transitions = TRANSITION_PHRASES
        self.formulaic = FORMULAIC_EXPRESSIONS

    # ── 范文检索 ──

    def search_exemplars(
        self,
        writing_mode: Optional[str] = None,
        doc_type: Optional[str] = None,
        style: Optional[str] = None,
    ) -> List[CompactExemplar]:
        """多条件检索压缩格式范文"""
        results = list(self.compact_exemplars.values())
        if writing_mode:
            results = [e for e in results if e.writing_mode == writing_mode]
        if doc_type:
            results = [e for e in results if e.doc_type == doc_type]
        if style:
            results = [e for e in results if e.style == style]
        return results

    def get_exemplar(self, exemplar_id: str) -> Optional[CompactExemplar]:
        return self.compact_exemplars.get(exemplar_id)

    def get_exemplars_for_prompt(
        self,
        writing_mode: str,
        max_exemplars: int = 2,
    ) -> str:
        """
        获取指定写作模式的范文注入文本（高保真低token）
        只输出骨架和关键句式，不输出原文，token节省90%+
        """
        exemplars = self.search_exemplars(writing_mode=writing_mode)
        if not exemplars:
            return ""

        selected = exemplars[:max_exemplars]
        lines = ["【标杆范文参考】", ""]

        for i, e in enumerate(selected, 1):
            lines.append(f"--- 范文{i}：{e.title} ---")
            lines.append(f"来源：{e.source}（{e.award},{e.word_count}字）")
            lines.append(f"结构：{e.structure_skeleton}")
            if e.key_sentences:
                lines.append("关键句式示例：")
                for s in e.key_sentences[:3]:
                    lines.append(f"  · {s}")
            if e.reusable_pattern:
                lines.append("可复用模式：")
                lines.append(e.reusable_pattern)
            lines.append("")

        return "\n".join(lines)

    def get_formulaic_for_prompt(self, doc_type: str) -> str:
        """获取指定文种的格式化用语注入文本"""
        expressions = self.formulaic.get(doc_type)
        if not expressions:
            return ""

        lines = [f"【{doc_type}格式化用语规范】", ""]
        for category, phrases in expressions.items():
            lines.append(f"  {category}：")
            for p in phrases[:3]:
                lines.append(f"    · {p}")
        lines.append("")
        return "\n".join(lines)

    # ── 错误诊断 ──

    def diagnose_text(self, text: str) -> List[Dict[str, str]]:
        """基于模式匹配的自动错误诊断"""
        findings = []
        for err_id, pattern in self.error_patterns.items():
            # 标记为不可自动检测的错误类型直接跳过（需语义理解，无法靠模式匹配）
            if not pattern.get("auto_detectable", True):
                continue
            for p in pattern.get("patterns", []):
                # 高频短词（<=2字）误报率高，需多次出现才判定为模式
                if len(p) <= 2:
                    if text.count(p) < 3:
                        continue
                elif p not in text:
                    continue
                findings.append({
                    "error_id": err_id,
                    "name": pattern["name"],
                    "diagnosis": pattern["diagnosis"],
                    "prescription": pattern["prescription"],
                    "example_good": pattern.get("example_good", ""),
                    "severity": pattern["severity"],
                    "category": pattern["category"],
                })
                break
        return findings

    def diagnose_format(self, text: str) -> List[Dict[str, str]]:
        """格式错误诊断：根据 check_method 对 text 执行实际检查"""
        findings = []
        for err_id, fmt_err in self.format_errors.items():
            if not self._check_format_error(err_id, text):
                continue
            findings.append({
                "error_id": err_id,
                "name": fmt_err.name,
                "diagnosis": fmt_err.description,
                "prescription": fmt_err.prescription,
                "severity": fmt_err.severity,
                "category": fmt_err.category,
            })
        return findings

    def _check_format_error(self, err_id: str, text: str) -> bool:
        """根据 check_method 对单个格式错误执行实际检查（保守策略，避免误报）"""
        if not text:
            return False
        fmt_err = self.format_errors.get(err_id)
        if fmt_err is None:
            return False
        if fmt_err.check_method == "pattern":
            return self._check_format_pattern(err_id, text)
        return self._check_format_structural(err_id, text)

    def _check_format_structural(self, err_id: str, text: str) -> bool:
        """结构性检查：标题三要素、日期、引文、结尾等"""
        if err_id == "title_3elements_missing":
            # 取首个非空行作为标题候选
            title = ""
            for line in text.splitlines():
                if line.strip():
                    title = line.strip()
                    break
            doc_types = ["通知", "请示", "批复", "函", "纪要", "报告", "决定", "意见"]
            if not any(dt in title for dt in doc_types):
                return False
            # 以"关于"开头 -> 缺发文机关
            if title.startswith("关于"):
                return True
            # 含文种但无"关于"且标题过短 -> 缺事由
            if "关于" not in title and len(title) <= 4:
                return True
            return False
        if err_id == "date_format_wrong":
            # 汉字数字年份
            if re.search(r"二[〇零一三四五六七八九]+年", text):
                return True
            # 编虚位（如 05月、05日）
            if re.search(r"\d{4}年0\d月", text):
                return True
            if re.search(r"\d{4}年\d{1,2}月0\d日", text):
                return True
            return False
        if err_id == "citation_format_wrong":
            # 文号〔〕号未配合书名号《》
            if re.search(r"根据[^《]*〔\d{4}〕\d+号", text):
                return True
            return False
        if err_id == "closing_missing":
            # 仅当首行标题明确为某文种时才校验结尾用语
            title = ""
            for line in text.splitlines():
                if line.strip():
                    title = line.strip()
                    break
            if "请示" in title and "请批示" not in text and "请批复" not in text:
                return True
            if "通知" in title and "特此通知" not in text:
                return True
            if "批复" in title and "此复" not in text:
                return True
            if "报告" in title and "特此报告" not in text:
                return True
            return False
        # indent_wrong / signer_missing_on_upward 仅凭纯文本难以可靠判定，保守跳过
        return False

    def _check_format_pattern(self, err_id: str, text: str) -> bool:
        """模式型检查：引号、数字用法等"""
        if err_id == "quotation_mark_wrong":
            # 书名号《》未成对出现
            if text.count("《") != text.count("》") and (text.count("《") > 0 or text.count("》") > 0):
                return True
            return False
        if err_id == "number_usage_inconsistent":
            # 阿拉伯数字与汉字数字修饰同一类量词（个/项/条/方面/问题）
            if re.search(r"\d+个", text) and re.search(r"[一二三四五六七八九十]+个", text):
                return True
            if re.search(r"\d+项", text) and re.search(r"[一二三四五六七八九十]+项", text):
                return True
            return False
        return False

    # ── 过渡词检索 ──

    def get_transitions(self, style: str, count: int = 3) -> List[str]:
        phrases = self.transitions.get(style, [])
        if not phrases:
            phrases = self.transitions.get("新华社", [])
        return phrases[:count]

    def get_style_exemplar_summary(self, style: str) -> str:
        """获取指定风格的范文简要总结（用于测试及检索）"""
        results = self.search_exemplars(style=style)
        if not results:
            return f"暂无 {style} 风格的范文参考。"

        lines = []
        for e in results:
            lines.append(f"风格：{e.style}，标题：《{e.title}》，来源：{e.source}，荣誉：{e.award}")
        return "\n".join(lines)

    # ── 术语检索 ──

    def lookup_term(self, term: str) -> Optional[Dict[str, str]]:
        return self.terminology.get(term)

    # ── 综合写作提示 ──

    def get_writing_tips(self, doc_type: str, style: str) -> List[str]:
        tips = []

        if doc_type == "消息":
            tips.extend([
                "导语必须五要素齐全",
                "最重要的事实放在最前面",
                "一段一事，段落简短",
                "字数严格控制在800字以内",
            ])
        elif doc_type == "通讯":
            tips.extend([
                "采用总—分—总递进式布局",
                "行程之间要有递进逻辑（知→学→志）",
                "每段行程必须包含战略锚点句",
                "善用真实感言替代空泛表态",
            ])
        elif doc_type == "侧记":
            tips.extend([
                "从一个具体场景或人物切入",
                "主题事件化、事件人物化",
                "细节叙事，用画面感代替概述",
            ])
        elif doc_type == "调研报告":
            tips.extend([
                "问题导向，以一个矛盾或问题开篇",
                "不回避'不完美的真实'",
                "注重学理深度和思想性",
            ])
        elif doc_type in ("通知", "请示", "批复", "函", "纪要"):
            tips.extend([
                "严格遵循《党政机关公文格式》(GB/T 9704-2012)",
                "标题=发文机关+事由+文种",
                "正文采用三段式：依据→事项→要求",
                "使用格式化用语，不得口语化",
            ])

        if style == "新华社":
            tips.append("语言简洁，严禁'高位推动''高度重视'等套话")
        elif style == "人民日报":
            tips.append("宏观起笔，将具体事件上升到国家叙事")
        elif style == "央视新闻":
            tips.append("场景驱动，让读者'看到'现场")
        elif style == "光明日报":
            tips.append("从'小角度讲大道理'，注重思想性")
        elif style == "党政机关行文规范":
            tips.append("信息优先，格式严格，不渲染不拔高不借势")

        return tips

    def get_formatted_prompt_for_mode(
        self, writing_mode: str, doc_type: str
    ) -> str:
        """
        一键获取某个写作模式和文种的完整知识注入
        包含：标杆范文 + 格式化用语
        token消耗约300-500，远低于原版2000+
        """
        parts = []

        exemplar_text = self.get_exemplars_for_prompt(writing_mode, max_exemplars=2)
        if exemplar_text:
            parts.append(exemplar_text)

        formulaic_text = self.get_formulaic_for_prompt(doc_type)
        if formulaic_text:
            parts.append(formulaic_text)

        return "\n".join(parts) if parts else ""
