"""
core/ocr.py
微信本地 OCR 的初始化与调用封装。
支持传入文件路径（str）或 PIL Image 对象。
"""

import os
import sys
from datetime import datetime

# 添加根目录到 Python 路径，以便导入 wcocr
_OCR_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_OCR_DIR)

# 导入 wcocr
sys.path.insert(0, _PROJECT_ROOT)
import wcocr

from PIL import Image

_initialized = False
_temp_dir = "captures"  # OCR 中转图存放目录，识别完毕后立即删除


def init(
    wechatocr_path: str = None, wechat_path: str = None, temp_dir: str = None
) -> bool:
    """
    初始化微信 OCR 引擎。
    成功返回 True，路径不合法返回 False。

    Args:
        wechatocr_path: wxocr.dll 路径，默认从配置读取
        wechat_path: 微信安装目录，默认从配置读取
        temp_dir: 临时文件目录
    """
    global _initialized, _temp_dir

    # 从配置读取默认路径
    from utils.config import load as load_config

    cfg = load_config()

    # 设置临时目录（转换为绝对路径）
    if temp_dir:
        _temp_dir = temp_dir
    else:
        _temp_dir = cfg.get("temp_dir", "temp")

    # 相对路径转换为绝对路径
    if not os.path.isabs(_temp_dir):
        _temp_dir = os.path.join(_PROJECT_ROOT, _temp_dir)

    if not wechatocr_path:
        wechatocr_path = cfg.get("wechatocr_path", "")
    if not wechat_path:
        wechat_path = cfg.get("wechat_path", "")

    if not os.path.isfile(wechatocr_path):
        print(f"[OCR] 找不到 wxocr.dll：{wechatocr_path}")
        return False
    if not os.path.isdir(wechat_path):
        print(f"[OCR] 找不到微信目录：{wechat_path}")
        return False

    wcocr.init(wechatocr_path, wechat_path)
    _initialized = True
    # print("[OCR] 微信 OCR 初始化成功")
    return True


def destroy() -> None:
    """释放 OCR 引擎资源。"""
    global _initialized
    if _initialized:
        wcocr.destroy()
        _initialized = False


def _parse_result(result) -> str:
    """将 wcocr.ocr() 的返回值统一解析为文本字符串。"""
    texts: list[str] = []
    if isinstance(result, dict):
        for item in result.get("ocr_response", []):
            t = item.get("text", "").strip()
            if t:
                texts.append(t)
    elif isinstance(result, list):
        for item in result:
            t = (
                item.get("text", "").strip()
                if isinstance(item, dict)
                else str(item).strip()
            )
            if t:
                texts.append(t)
    else:
        texts.append(str(result).strip())
    return " ".join(texts)


def recognize(source: str | Image.Image) -> str:
    """
    对图片执行 OCR，返回拼接后的文本字符串。

    Args:
        source: 文件路径（str）或 PIL Image 对象。
                传入 Image 时使用系统临时文件中转，识别完毕后立即删除，不落盘保存。

    Raises:
        RuntimeError: OCR 引擎未初始化时抛出。
    """
    if not _initialized:
        raise RuntimeError("[OCR] 引擎未初始化，请先调用 ocr.init()")

    if isinstance(source, str):
        # 直接使用文件路径
        return _parse_result(wcocr.ocr(source))

    # PIL Image：写入临时文件 → OCR → 立即删除
    os.makedirs(_temp_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
    tmp_path = os.path.join(_temp_dir, f"_ocr_tmp_{timestamp}.png")
    try:
        source.save(tmp_path)
        return _parse_result(wcocr.ocr(tmp_path))
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
