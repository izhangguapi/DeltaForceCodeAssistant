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
_DOT_CHARS  = set("·•。｡．")    # → '.'
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


# ── 以下为跨模块依赖，需要在 core/__init__.py 中避免循环导入 ──────────────

def run_morse(regions: list[dict], app_cfg: dict) -> None:
    """
    截图 → OCR → 摩斯解码 → 按下数字键 → 确认点击（三个数字全成功才触发）。
    """
    # 延迟导入避免循环
    from core import capture, ocr
    from utils.mouse import click_sequence
    import keyboard
    import time
    from datetime import datetime

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ── 开始识别 ──")

    screenshots = capture.grab_regions(regions)
    digits: list[str] = []

    for name, img in screenshots:
        raw = ocr.recognize(img)
        digit = decode(raw)
        print(f"  [{name}]  OCR: {repr(raw):<30}  解码 → {digit}")
        digits.append(digit)

    password = "".join(digits)
    print(f"\n  ★ 识别密码：{password}\n")

    all_ok = all(d.isdigit() for d in digits)

    for d in digits:
        if d.isdigit():
            keyboard.press_and_release(d)
            print(f"  → 已按下: {d}")
        else:
            print(f"  → 识别失败，跳过: {d}")
        time.sleep(0.05)

    # 确认点击：三个数字全部成功才触发
    clicks = app_cfg.get("morse_confirm_clicks", [])
    if clicks:
        if all_ok:
            time.sleep(0.6)
            print("  点击下载")
            click_sequence(clicks, delay=0.1)
        else:
            print("  → 存在识别失败的数字，跳过点击")

    print()
