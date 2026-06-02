"""
文本安全处理器 — 中文语料的 Python 兼容性预处理

解决中文文本在 Python 源代码中的常见问题：
1. 中文双引号 "" (U+201C/U+201D) 与 Python 字符串界定符冲突
2. ASCII 双引号 " (U+0022) 在中文语境中用作引号时的歧义
3. 中文省略号 …… (U+2026) 在某些编码环境下的兼容性问题
4. 中文顿号 、 (U+3001) 和全角逗号 ， (U+FF0C) 的处理

核心策略：
- 所有需要在 Python 源码中呈现的中文文本，内部引号统一使用 「」(U+300C/U+300D)
- 或者使用 single-quoted Python 字符串包裹含双引号的中文内容
- 提供 .sanitize() 方法一次性处理所有问题

用法：
    from utils.text_sanitizer import sanitize_text, safe_str

    # 方式1：安全化任意文本
    text = sanitize_text('他说"这个项目很好"')
    # → '他说「这个项目很好」'

    # 方式2：生成安全的Python代码片段
    code = safe_str('传递"我们有方向、有资源、有行动力、有成果"')
"""

import re
import unicodedata
from typing import Union


# ═══════════════════════════════════════════════════════════════
# 字符映射表
# ═══════════════════════════════════════════════════════════════

CHAR_MAP = {
    # 中文双引号 → 书名号（在Python字符串中更安全）
    '\u201c': '\u300c',  # " → 「
    '\u201d': '\u300d',  # " → 」

    # 中文单引号 → 保留或转义
    '\u2018': '\u2018',  # ' → ' (保留)
    '\u2019': '\u2019',  # ' → ' (保留)

    # 中文省略号 → 三个点（避免 U+2026 在某些Python版本的问题）
    # 注意：Python 3.x 都支持 U+2026，但为了保险可替换
    # '\u2026': '...',  # 默认保留，按需开启
}

# 当文本需要放入 Python 双引号字符串时，替换内部的 ASCII 双引号
ASCII_QUOTE_REPLACEMENT = '\u300c'  # 「

# 成对替换：奇数位置的 " → 「, 偶数位置的 " → 」
LEFT_ANGLE = '\u300c'
RIGHT_ANGLE = '\u300d'


def sanitize_text(text: str) -> str:
    """
    安全化中文文本，替换可能导致Python语法错误的字符。
    
    Args:
        text: 原始中文文本
        
    Returns:
        安全化后的文本
    """
    if not text:
        return text

    # 1. 替换中文双引号为书名号
    for old, new in CHAR_MAP.items():
        text = text.replace(old, new)

    return text


def safe_quotes(text: str, prefer_single: bool = True) -> str:
    """
    将文本中的引号处理为Python安全的格式。
    
    检测文本中是否有ASCII双引号被用作中文引号（即引号内容为中文），
    并将其替换为 「」。

    如果 prefer_single=True 且文本不含单引号，返回用单引号包裹的字符串；
    否则返回用双引号包裹但内部引号已替换的字符串。
    
    Args:
        text: 原始文本
        prefer_single: 是否优先使用单引号包裹
        
    Returns:
        安全的字符串表示（带引号）
    """
    if not text:
        return '""'

    # 先替换中文双引号
    text = sanitize_text(text)

    # 处理 ASCII 双引号用作中文引号的情况
    # 成对替换："text" → 「text」
    result = []
    in_quote = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '"':
            # 判断是否为中文引号：前后是否有中文字符或中文标点
            prev_is_cjk = i > 0 and _is_cjk(text[i - 1])
            next_is_cjk = i + 1 < len(text) and _is_cjk(text[i + 1])

            if prev_is_cjk or next_is_cjk:
                result.append(RIGHT_ANGLE if in_quote else LEFT_ANGLE)
                in_quote = not in_quote
            else:
                result.append(ch)
        else:
            result.append(ch)
        i += 1

    result_text = ''.join(result)

    # 选择包裹方式
    if prefer_single and "'" not in result_text:
        return f"'{result_text}'"
    elif '"' not in result_text:
        return f'"{result_text}"'
    else:
        # 两种引号都出现，使用转义
        escaped = result_text.replace('"', '\\"')
        return f'"{escaped}"'


def safe_dict_value(text: str) -> str:
    """
    将文本安全化后返回，作为Python字典的字符串值。
    
    这是一个便捷方法，相当于 sanitize_text + 自动引号处理。
    用于在代码生成场景中确保字典值的字符串安全。
    
    Args:
        text: 原始文本
        
    Returns:
        安全化的文本（不含引号包裹，用于放入已存在的字符串中）
    
    Example:
        # 在 f-string 或模板中使用
        d = {"description": f"{safe_dict_value(user_input)}"}
    """
    if not text:
        return text
    text = sanitize_text(text)

    # 成对替换 ASCII 双引号
    result = []
    in_quote = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '"':
            prev_is_cjk = i > 0 and _is_cjk(text[i - 1])
            next_is_cjk = i + 1 < len(text) and _is_cjk(text[i + 1])
            if prev_is_cjk or next_is_cjk:
                result.append(RIGHT_ANGLE if in_quote else LEFT_ANGLE)
                in_quote = not in_quote
            else:
                result.append(ch)
        else:
            result.append(ch)
        i += 1

    return ''.join(result)


def _is_cjk(ch: str) -> bool:
    """判断字符是否为CJK字符或中文标点"""
    cp = ord(ch)
    return (
        (0x4E00 <= cp <= 0x9FFF) or
        (0x3400 <= cp <= 0x4DBF) or
        (0x3000 <= cp <= 0x303F) or  # CJK标点
        (0xFF00 <= cp <= 0xFFEF) or  # 全角字符
        (0x2000 <= cp <= 0x206F) or  # 通用标点
        cp in (0x2018, 0x2019, 0x201C, 0x201D)
    )


def safe_writing_for_python(text: str) -> str:
    """
    最高安全级别：为Python源码文件准备文本。
    
    - 替换所有中文双引号 → 「」
    - 替换ASCII双引号用于中文语境 → 「」
    - 规范省略号
    
    Args:
        text: 任意中文文本
        
    Returns:
        可以在Python源码中安全使用的文本
    """
    if not text:
        return text

    text = sanitize_text(text)
    text = safe_dict_value(text)  # 处理ASCII引号
    return text


# ═══════════════════════════════════════════════════════════════
# 批处理工具
# ═══════════════════════════════════════════════════════════════

def sanitize_python_file(filepath: str, dry_run: bool = True) -> str:
    """
    安全化Python文件中的中文文本。
    
    扫描Python源码，找到所有字符串字面量中的中文文本，
    将可能导致语法问题的引号进行替换。
    
    Args:
        filepath: Python文件路径
        dry_run: 如果为True，只返回修改后的内容而不写入文件
        
    Returns:
        修改后的文件内容（dry_run=True）或空字符串（dry_run=False）
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    fixed_lines = []
    changes = 0

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        # 跳过注释、空行、import语句
        if (not stripped or stripped.startswith('#') or
            stripped.startswith('from ') or stripped.startswith('import ')):
            fixed_lines.append(line)
            continue

        # 检测是否是字符串赋值行
        dq_count = line.count('"')
        if dq_count <= 4:
            fixed_lines.append(line)
            continue

        # 处理 "key": "value" 模式
        idx = line.find('": "')
        if idx < 0:
            fixed_lines.append(line)
            continue

        prefix = line[:idx + 4]
        rest = line[idx + 4:]

        # 找到末尾的 ",
        last_quote = rest.rfind('",')
        if last_quote < 0:
            last_quote = rest.rfind('"')
            if last_quote < 0:
                fixed_lines.append(line)
                continue

        value = rest[:last_quote]
        suffix = rest[last_quote:]

        # 如果值内部有双引号，且内容包含中文
        if '"' in value and _contains_cjk(value):
            new_value = safe_dict_value(value)
            new_line = prefix + new_value + suffix
            if new_line != line:
                changes += 1
                print(f"  Line {line_num}: fixed")
            fixed_lines.append(new_line)
        else:
            fixed_lines.append(line)

    new_content = '\n'.join(fixed_lines)

    if not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

    print(f"\nTotal changes: {changes}")
    return new_content


def _contains_cjk(text: str) -> bool:
    """检查文本是否包含中文字符"""
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff':
            return True
    return False


# ═══════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════

# 在模块中可以直接使用的安全字符串构建器
def S(text: str) -> str:
    """S() = safe writing. 快速安全化任意文本。"""
    return safe_writing_for_python(text)


# 预定义的常用来替换的模式
REPLACEMENT_PATTERNS = [
    # (原始模式, 替换后模式, 描述)
    ('"大家纷纷表示"', '「大家纷纷表示」', '空泛表态'),
    ('"深刻感受到"', '「深刻感受到」', '空泛表态'),
    ('"一致认为"', '「一致认为」', '空泛表态'),
    ('"证据"', '「证据」', '引号强调'),
    ('"战略锚点"', '「战略锚点」', '术语'),
    ('"我们"', '「我们」', '强调'),
    ('"流程记录"', '「流程记录」', '术语'),
    ('"战略叙事"', '「战略叙事」', '术语'),
]


def batch_replace(text: str) -> str:
    """批量应用预设的替换模式。"""
    for old, new, _ in REPLACEMENT_PATTERNS:
        text = text.replace(old, new)
    return text