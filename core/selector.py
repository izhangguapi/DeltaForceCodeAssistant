"""
core/selector.py
截取当前全屏，将配置文件中的区域用彩色框标注后保存，
并用系统默认图片查看器打开，方便核对坐标是否正确。

用法：
    from core.selector import preview_regions
    preview_regions(regions, save_dir="captures")
"""

import os
import subprocess
import sys
from datetime import datetime
from PIL import Image, ImageGrab, ImageDraw, ImageFont

# 每个区域依次使用不同颜色，循环取用
_PALETTE = [
    "#FF4444",  # 红
    "#44AAFF",  # 蓝
    "#44DD44",  # 绿
]
_LINE_WIDTH  = 3
_FONT_SIZE   = 20
_LABEL_PAD   = 4   # 标签文字与框边的间距


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """尝试加载系统字体，失败则回退到默认字体。"""
    candidates = [
        "msyh.ttc",          # 微软雅黑（Windows）
        "simhei.ttf",        # 黑体
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def preview_regions(regions: list[dict], save_dir: str = "captures") -> str:
    """
    截取当前全屏，在图上标注 regions 中每个区域的彩色矩形框与名称，
    将结果保存到 save_dir 目录，然后用系统默认图片程序打开。

    Args:
        regions:  区域列表，每项含 name / left / top / width / height。
        save_dir: 截图保存目录，默认为 captures/。

    Returns:
        保存的文件路径。
    """
    # 1. 截全屏
    screenshot: Image.Image = ImageGrab.grab()
    draw = ImageDraw.Draw(screenshot)
    font = _get_font(_FONT_SIZE)

    # 2. 逐区域画框 + 标签
    for idx, region in enumerate(regions):
        name   = region.get("name", f"区域{idx + 1}")
        left   = region["left"]
        top    = region["top"]
        right  = left + region["width"]
        bottom = top  + region["height"]
        color  = _PALETTE[idx % len(_PALETTE)]

        # 画矩形框（粗细 _LINE_WIDTH）
        for offset in range(_LINE_WIDTH):
            draw.rectangle(
                [left - offset, top - offset, right + offset, bottom + offset],
                outline=color,
            )

        # 计算标签背景区域
        label = f" {name} "
        bbox = font.getbbox(label)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        lx = left
        ly = max(0, top - text_h - _LABEL_PAD * 2 - _LINE_WIDTH)

        # 标签背景色块
        draw.rectangle(
            [lx, ly, lx + text_w + _LABEL_PAD * 2, ly + text_h + _LABEL_PAD * 2],
            fill=color,
        )
        # 标签文字（白色）
        draw.text(
            (lx + _LABEL_PAD, ly + _LABEL_PAD),
            label,
            fill="white",
            font=font,
        )

    # 3. 保存到 captures 目录
    os.makedirs(save_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(save_dir, f"preview_{timestamp}.png")
    screenshot.save(save_path)

    # 4. 用系统默认程序打开
    _open_image(save_path)
    print(f"[预览] 已保存并打开标注图：{save_path}")

    return save_path


def _open_image(path: str) -> None:
    """跨平台用系统默认程序打开图片。"""
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
