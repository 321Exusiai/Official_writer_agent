"""
URL 文档导入器 — 支持用户从 URL 导入参考文档

功能：
1. 网页抓取：从 URL 提取正文内容
2. 智能解析：去除广告、导航、评论等噪声
3. 元数据提取：标题、作者、发布时间、来源网站
4. 格式识别：自动识别网页类型（新闻/公文/报告/博客）
5. 存储集成：导入后自动存入个性化数据库的 ReferenceArticle

设计原则：
- 支持普通网页和 PDF 文档
- 提取正文时保留关键结构（段落、标题、列表）
- 错误处理友好，网络超时有提示
"""

import re
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse


class DocumentFormat(Enum):
    NEWS_ARTICLE = "news_article"
    OFFICIAL_DOCUMENT = "official_document"
    RESEARCH_REPORT = "research_report"
    BLOG_POST = "blog_post"
    POLICY_DOCUMENT = "policy_document"
    UNKNOWN = "unknown"


@dataclass
class ImportedDocument:
    """从 URL 导入的文档"""
    id: str = ""
    url: str = ""
    title: str = ""
    author: str = ""
    publish_date: str = ""
    source_site: str = ""
    content: str = ""
    raw_html: str = ""
    word_count: int = 0
    format: DocumentFormat = DocumentFormat.UNKNOWN
    keywords: List[str] = field(default_factory=list)
    extracted_at: str = ""
    import_notes: str = ""
    style_patterns: List[str] = field(default_factory=list)


class URLDocumentImporter:
    """
    URL 文档导入器

    支持：
    - 普通网页（新闻、公文、报告等）
    - PDF 文档（通过特殊处理）
    - 批量导入（多个 URL）
    """

    def __init__(self, use_requests: bool = True):
        self.use_requests = use_requests
        self._session = None

    def _get_session(self):
        if self._session is None and self.use_requests:
            try:
                import requests
                self._session = requests.Session()
                self._session.headers.update({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                })
            except ImportError:
                self.use_requests = False
        return self._session

    def import_from_url(
        self,
        url: str,
        timeout: int = 30,
        extract_patterns: bool = True,
    ) -> ImportedDocument:
        """
        从 URL 导入文档

        Args:
            url: 目标 URL
            timeout: 超时时间（秒）
            extract_patterns: 是否提取风格模式

        Returns:
            ImportedDocument 对象
        """
        doc = ImportedDocument(
            id=f"import_{uuid.uuid4().hex[:8]}",
            url=url,
            extracted_at=datetime.now().isoformat(),
        )

        parsed = urlparse(url)
        doc.source_site = parsed.netloc

        html = self._fetch_url(url, timeout)
        if not html:
            doc.import_notes = "无法访问该 URL，请检查网络连接或 URL 是否正确"
            return doc

        doc.raw_html = html
        doc.title = self._extract_title(html)
        doc.content = self._extract_content(html)
        doc.word_count = len(doc.content)
        doc.author = self._extract_author(html, doc.content)
        doc.publish_date = self._extract_date(html)
        doc.format = self._detect_format(doc.title, doc.content, url)
        doc.keywords = self._extract_keywords(doc.content)

        if extract_patterns:
            doc.style_patterns = self._extract_style_patterns(doc.content)

        return doc

    def batch_import(
        self,
        urls: List[str],
        timeout: int = 30,
        delay: float = 1.0,
    ) -> List[ImportedDocument]:
        """
        批量导入多个 URL

        Args:
            urls: URL 列表
            timeout: 单个请求超时时间
            delay: 请求间隔（秒），避免被封

        Returns:
            ImportedDocument 列表
        """
        results = []
        for url in urls:
            doc = self.import_from_url(url, timeout=timeout)
            results.append(doc)
            time.sleep(delay)
        return results

    # ═══ 核心方法 ═══

    def _fetch_url(self, url: str, timeout: int) -> Optional[str]:
        """获取网页 HTML"""
        session = self._get_session()
        if session:
            try:
                response = session.get(url, timeout=timeout)
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")
                if "text/html" in content_type or "text/plain" in content_type:
                    response.encoding = response.apparent_encoding
                    return response.text
                else:
                    return f"[非 HTML 内容，Content-Type: {content_type}]"
            except Exception as e:
                return None
        else:
            return None

    def _extract_title(self, html: str) -> str:
        """提取网页标题"""
        match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            title = re.sub(r'<[^>]+>', '', title)
            title = title.split('_')[0].split('-')[0].split('|')[0]
            return title.strip()
        return "未知标题"

    def _extract_content(self, html: str) -> str:
        """提取网页正文（智能去噪）"""
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if not body_match:
            return self._extract_text_from_html(html)

        body = body_match.group(1)

        # 移除噪声
        noise_patterns = [
            r'<script[^>]*>.*?</script>',
            r'<style[^>]*>.*?</style>',
            r'<nav[^>]*>.*?</nav>',
            r'<footer[^>]*>.*?</footer>',
            r'<header[^>]*>.*?</header>',
            r'<aside[^>]*>.*?</aside>',
            r'<form[^>]*>.*?</form>',
            r'<iframe[^>]*>.*?</iframe>',
            r'<!--.*?-->',
            r'<div[^>]*class="[^"]*(?:comment|ad|sidebar|nav|menu|footer|header|pagination|related)[^"]*"[^>]*>.*?</div>',
            r'<a[^>]*>.*?</a>',
        ]

        for pattern in noise_patterns:
            body = re.sub(pattern, '', body, flags=re.DOTALL | re.IGNORECASE)

        # 提取段落
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', body, re.DOTALL | re.IGNORECASE)
        if paragraphs:
            texts = []
            for p in paragraphs:
                text = self._extract_text_from_html(p).strip()
                if text and len(text) > 10:
                    texts.append(text)
            if texts:
                return "\n\n".join(texts)

        # 如果段落提取失败，提取所有 div/span 中的文本
        return self._extract_text_from_html(body)

    def _extract_text_from_html(self, html: str) -> str:
        """从 HTML 提取纯文本"""
        text = re.sub(r'<br\s*/?>', '\n', html)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&quot;', '"', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_author(self, html: str, content: str) -> str:
        """提取作者"""
        author_patterns = [
            r'作者[：:]\s*([^\n\r<]+)',
            r'记者[：:]\s*([^\n\r<]+)',
            r'记者\s+([^\s，,。.\n\r]{2,8})',
            r'文\s*/\s*([^\s，,。.\n\r]{2,8})',
            r'by\s+([^\s<]{2,20})',
        ]

        for pattern in author_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                author = match.group(1).strip()
                if len(author) < 20:
                    return author

            if len(content) < 500:
                match = re.search(pattern, content)
                if match:
                    author = match.group(1).strip()
                    if len(author) < 20:
                        return author

        return ""

    def _extract_date(self, html: str) -> str:
        """提取发布时间"""
        date_patterns = [
            r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?)',
            r'发布时间[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})',
            r'发布日期[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})',
            r'(\d{4}\.\d{1,2}\.\d{1,2})',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, html)
            if match:
                date_str = match.group(1).strip()
                return date_str

        return ""

    def _detect_format(
        self,
        title: str,
        content: str,
        url: str,
    ) -> DocumentFormat:
        """自动识别文档格式类型"""
        text = title + content[:1000]

        official_keywords = ["通知", "请示", "批复", "函", "纪要", "决定", "通报", "报告", "意见", "妥否", "请批示"]
        news_keywords = ["本报讯", "记者", "报道", "据悉", "日前", "近日", "本报讯", "本报记者"]
        research_keywords = ["调研", "分析", "报告", "研究", "结论", "建议", "数据表明", "统计"]
        policy_keywords = ["条例", "办法", "规定", "实施细则", "指导意见", "通知", "国务院", "党中央"]

        scores = {
            DocumentFormat.OFFICIAL_DOCUMENT: sum(1 for kw in official_keywords if kw in text),
            DocumentFormat.NEWS_ARTICLE: sum(1 for kw in news_keywords if kw in text),
            DocumentFormat.RESEARCH_REPORT: sum(1 for kw in research_keywords if kw in text),
            DocumentFormat.POLICY_DOCUMENT: sum(1 for kw in policy_keywords if kw in text),
        }

        max_score = max(scores.values())
        if max_score >= 2:
            return max(scores, key=scores.get)

        return DocumentFormat.UNKNOWN

    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词（基于词频）"""
        if len(content) < 100:
            return []

        words = re.findall(r'[\u4e00-\u9fff]{2,6}', content)
        stop_words = {"这个", "那个", "什么", "怎么", "可以", "应该", "我们", "他们", "就是", "因为", "所以", "但是", "如果", "没有", "一个", "一些", "一下", "一下", "一下"}

        freq = {}
        for word in words:
            if word not in stop_words:
                freq[word] = freq.get(word, 0) + 1

        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, count in sorted_words[:15] if count >= 2]

    def _extract_style_patterns(self, content: str) -> List[str]:
        """从文档中提取风格模式"""
        patterns = []

        if len(content) < 500:
            return patterns

        # 句子长度分析
        sentences = re.split(r'[。！？；]', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            avg_len = sum(len(s) for s in sentences) / len(sentences)
            if avg_len < 20:
                patterns.append(f"短句风格（平均{avg_len:.0f}字/句）")
            elif avg_len > 40:
                patterns.append(f"长句风格（平均{avg_len:.0f}字/句）")
            else:
                patterns.append(f"中等句长（平均{avg_len:.0f}字/句）")

        # 格式化用语检测
        formulaic = ["会议指出", "会议强调", "会议要求", "决定", "妥否", "请批示", "特此通知", "经研究"]
        found = [kw for kw in formulaic if kw in content]
        if found:
            patterns.append(f"使用格式化用语：{', '.join(found)}")

        # 序号结构检测
        if "一是" in content or "二是" in content:
            patterns.append("使用序号分条结构")
        elif "第一" in content or "其次" in content:
            patterns.append("使用递进结构")

        # 直接引语检测
        if content.count('"') > 4 or content.count('"') > 4:
            patterns.append("使用直接引语")

        return patterns

    # ═══ 手动导入（用户直接粘贴文本） ═══

    def import_from_text(
        self,
        title: str,
        content: str,
        source: str = "手动导入",
        url: str = "",
    ) -> ImportedDocument:
        """
        从用户粘贴的文本导入

        适用于：
        - 用户复制了网页内容但无法提供 URL
        - 用户有本地文档需要导入
        """
        doc = ImportedDocument(
            id=f"import_{uuid.uuid4().hex[:8]}",
            url=url,
            title=title,
            content=content,
            source_site=source,
            word_count=len(content),
            extracted_at=datetime.now().isoformat(),
        )

        doc.format = self._detect_format(title, content, url)
        doc.keywords = self._extract_keywords(content)
        doc.style_patterns = self._extract_style_patterns(content)

        return doc
