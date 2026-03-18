"""
core/morse.py
摩斯码 ↔ 数字（0-9）的解码逻辑。
"""

# 数字 0-9 的标准摩斯码
MORSE_TABLE: dict[str, str] = {
    "-----": "0",
    ".----": "1",
    "..---": "2",
    "...--": "3",
    "....-": "4",
    ".....": "5",
    "-....": "6",
    "--...": "7",
    "---..": "8",
    "----.": "9",
}

# OCR 常见误识字符的映射
_DOT_CHARS  = set("·•。｡．")   # → '.'
_DASH_CHARS = set("—－一_–")   # → '-'


def normalize(text: str) -> str:
    """
    将 OCR 输出的原始文本规范化为仅含 '.' '-' ' ' 的摩斯码字符串。
    过滤掉其他 OCR 噪声字符。
    """
    buf: list[str] = []
    for ch in text:
        if ch == "." or ch in _DOT_CHARS:
            buf.append(".")
        elif ch == "-" or ch in _DASH_CHARS:
            buf.append("-")
        elif ch == " ":
            buf.append(" ")
        # 其余字符视为噪声，丢弃
    return "".join(buf).strip()


def decode(raw_text: str) -> str:
    """
    从 OCR 原始文本中解析出摩斯码并转换为对应数字。
    - 先按空格分词，逐 token 查表
    - 兜底：去除所有空格后整体查表
    返回数字字符（'0'-'9'），识别失败返回 '?'。
    """
    normalized = normalize(raw_text)

    # 按空格分词逐一匹配
    for token in normalized.split():
        digit = MORSE_TABLE.get(token)
        if digit is not None:
            return digit

    # 兜底：拼合后整体匹配
    digit = MORSE_TABLE.get(normalized.replace(" ", ""))
    return digit if digit else "?"
