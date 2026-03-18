"""
core/fingerprint.py
指纹识别模块 - 识别游戏中的指纹密码
"""

import os
import re
import time
import numpy as np
import cv2
import ctypes
from ctypes import wintypes, windll
from PIL import ImageGrab

# 直接导入 core.ocr 模块
from core import ocr as ocr_module

# OCR 模块引用（备用）
_wechat_ocr = None


def set_wechat_ocr(ocr_module):
    """设置微信OCR模块实例"""
    global _wechat_ocr
    _wechat_ocr = ocr_module


# ── 配置（在 run_fingerprint_pipeline 中从 app_cfg 加载）──────

NAME_REGION = None  # 人名区域
NUMBER_REGION = None  # 数字区域
CANDIDATE_BOXES = None  # 候选指纹区域
MODE_CONFIG = None  # 模式配置


# ── 辅助函数 ─────────────────────────────────────────────

# Windows API 鼠标点击常量
_MOUSEEVENTF_MOVE       = 0x0001
_MOUSEEVENTF_LEFTDOWN   = 0x0002
_MOUSEEVENTF_LEFTUP     = 0x0004
_MOUSEEVENTF_ABSOLUTE   = 0x8000

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_shell32 = ctypes.WinDLL("shell32", use_last_error=True)

# 声明 DPI 感知：让进程直接使用物理像素坐标，消除系统缩放换算
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        _user32.SetProcessDPIAware()
    except Exception:
        pass


def _activate_window(hwnd: int) -> None:
    """将窗口置前并激活"""
    if hwnd:
        # 检查窗口是否最小化，如果是则还原
        if _user32.IsIconic(hwnd):
            _user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        # 置前并激活
        _user32.SetForegroundWindow(hwnd)
        _shell32.SHGetKnownFolderIDList


def _find_game_window() -> int:
    """查找游戏窗口句柄"""
    # 尝试多种可能的窗口标题
    titles = ["三角洲", "Delta Force", "游戏"]
    for title in titles:
        hwnd = _user32.FindWindowW(None, title)
        if hwnd:
            return hwnd
    return 0


def _win_click(x: int, y: int) -> None:
    """使用 Windows SendMessage + mouse_event 执行可靠点击。
    
    进程已声明 DPI 感知，坐标直接对应物理像素。
    增加移动后等待，确保游戏响应。
    """
    # 移动鼠标
    _user32.SetCursorPos(x, y)
    # time.sleep(0.05)  # 等待鼠标移动完成

    # 按下
    _user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
    time.sleep(0.05)  # 等待按下生效
    # 释放
    _user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP




def pil_to_cv2(pil_img):
    """PIL Image 转换为 OpenCV 格式"""
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def crop_region(img, x1, y1, x2, y2):
    """裁剪图片区域"""
    h, w = img.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return img[y1:y2, x1:x2]


def save_image_chinese(path, img):
    """保存图片（支持中文路径）"""
    ext = os.path.splitext(path)[1].lower()
    if ext in [".png", ".jpg", ".jpeg"]:
        _, buf = cv2.imencode(ext, img)
        buf.tofile(path)
    else:
        cv2.imwrite(path, img)


def save_temp_image(img):
    """保存临时图片供OCR使用"""
    import tempfile

    temp_path = os.path.join(tempfile.gettempdir(), "temp_ocr.png")
    # 转换为BGR保存
    if len(img.shape) == 3 and img.shape[2] == 3:
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    else:
        img_bgr = img
    cv2.imwrite(temp_path, img_bgr)
    return temp_path


def ocr_recognize(img):
    """
    使用微信OCR识别图片中的文字
    返回: 识别到的文本列表
    """
    try:
        # 转换 cv2 图片为 PIL Image
        if len(img.shape) == 3:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = img
        from PIL import Image
        pil_img = Image.fromarray(img_rgb)

        # 调用 OCR 的 recognize 方法
        result = ocr_module.recognize(pil_img)

        if result:
            return [result]
        return []
    except Exception as e:
        print(f"[WARNING] OCR识别失败: {e}")
        return []


def extract_numbers_from_region(img):
    """从数字区域提取所有数字"""

    try:
        # 转换 cv2 图片为 PIL Image
        if len(img.shape) == 3:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = img
        from PIL import Image

        pil_img = Image.fromarray(img_rgb)

        # 调用 OCR
        result = ocr_module.recognize(pil_img)

        numbers = []
        if result:
            nums = re.findall(r"\d+", result)
            for n in nums:
                numbers.append(int(n))

        return numbers
    except Exception as e:
        print(f"[WARNING] 数字识别失败: {e}")
        return []


def _imread_chinese(path):
    """读取图片（支持中文路径）"""
    if not os.path.exists(path):
        return None
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    return img


def load_fingerprint_templates(person_name, images_dir, max_templates=8):
    """
    根据人名加载指纹模板（灰度图）
    Args:
        person_name: 人名
        images_dir: 模板目录
        max_templates: 最大模板数量，根据模式确定
    返回: 模板列表，每项包含 (index, 灰度图)
    """
    templates = []

    # 优先查找同名文件夹
    person_dir = os.path.join(images_dir, person_name)

    if os.path.exists(person_dir):
        for i in range(1, max_templates + 1):
            template_path = os.path.join(person_dir, f"{i}.png")
            if os.path.exists(template_path):
                img = _imread_chinese(template_path)
                if img is not None:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    templates.append({
                        'index': i,
                        'image': gray
                    })
        if templates:
            return templates

    # 查找根目录下的同名文件
    for fname in os.listdir(images_dir):
        if fname.startswith(person_name) and fname.endswith(".png"):
            template_path = os.path.join(images_dir, fname)
            img = _imread_chinese(template_path)
            if img is not None:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                idx = int(fname.split('.')[0]) if fname[0].isdigit() else len(templates) + 1
                templates.append({
                    'index': idx,
                    'image': gray
                })

    return templates


def find_best_match(candidate_img, templates, threshold=0.5):
    """
    使用像素模板匹配找到最佳匹配
    返回: (最佳模板索引, 匹配分数)
    """
    if not templates:
        return None, 0

    # 转为灰度图
    if len(candidate_img.shape) == 3:
        candidate_gray = cv2.cvtColor(candidate_img, cv2.COLOR_BGR2GRAY)
    else:
        candidate_gray = candidate_img

    best_idx = None
    best_score = 0

    for template in templates:
        template_img = template['image']

        # 调整模板大小与候选图像一致
        h, w = candidate_gray.shape
        template_resized = cv2.resize(template_img, (w, h))

        # 像素模板匹配
        result = cv2.matchTemplate(
            candidate_gray, template_resized, cv2.TM_CCOEFF_NORMED
        )
        _, max_val, _, _ = cv2.minMaxLoc(result)

        if max_val > best_score:
            best_score = max_val
            best_idx = template['index'] - 1  # 转回0索引

    if best_score > threshold:
        return best_idx, best_score
    return None, best_score


# ── 主流程 ─────────────────────────────────────────────


def run_fingerprint_pipeline(app_cfg: dict, save_dir: str = None):
    """
    指纹识别主流程

    Args:
        app_cfg: 应用配置字典
        save_dir: 调试图片保存目录（可选，默认从配置读取）
    """
    from datetime import datetime

    # 加载全局配置
    global NAME_REGION, NUMBER_REGION, CANDIDATE_BOXES, MODE_CONFIG

    fp_cfg = app_cfg.get("fingerprint", {})

    # 人名区域
    name_region = fp_cfg.get(
        "name_region", {"x1": 706, "y1": 657, "x2": 866, "y2": 689}
    )
    NAME_REGION = name_region

    # 数字区域
    number_region = fp_cfg.get(
        "number_region", {"x1": 1030, "y1": 530, "x2": 1365, "y2": 930}
    )
    NUMBER_REGION = number_region

    # 候选指纹区域
    candidate_boxes = fp_cfg.get(
        "candidate_boxes",
        [
            [1522, 560, 1627, 665],
            [1650, 560, 1755, 665],
            [1778, 560, 1883, 665],
            [1522, 687, 1627, 792],
            [1650, 687, 1755, 792],
            [1778, 687, 1883, 792],
            [1522, 815, 1627, 920],
            [1650, 815, 1755, 920],
            [1778, 815, 1883, 920],
        ],
    )
    CANDIDATE_BOXES = [tuple(box) for box in candidate_boxes]

    # 模式配置
    mode_cfg = fp_cfg.get(
        "mode_config",
        {
            "8": {"mode": "C", "candidates": 9, "indices": [0, 1, 2, 3, 4, 5, 6, 7, 8]},
            "6": {"mode": "B", "candidates": 7, "indices": [0, 1, 2, 3, 4, 5, 6]},
            "4": {"mode": "A", "candidates": 5, "indices": [0, 1, 2, 3, 4]},
        },
    )
    MODE_CONFIG = {
        int(k): (v["mode"], v["candidates"], v["indices"]) for k, v in mode_cfg.items()
    }

    # 匹配阈值
    match_threshold = fp_cfg.get("match_threshold", 0.5)

    # 保存目录
    if save_dir is None:
        save_dir = app_cfg.get("save_dir", "captures")

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ── 指纹识别开始 ──")

    # 1. 截取屏幕
    screen_pil = ImageGrab.grab()
    screen = pil_to_cv2(screen_pil)

    # 2. 识别人名
    print("  识别人名...")
    name_img = crop_region(
        screen,
        NAME_REGION["x1"],
        NAME_REGION["y1"],
        NAME_REGION["x2"],
        NAME_REGION["y2"],
    )

    if name_img is None:
        print("  [ERROR] 人名区域裁剪失败")
        return

    # 识别人名
    name_texts = ocr_recognize(name_img)

    if not name_texts:
        print("  [ERROR] 未识别到人名")
        return

    person_name = name_texts[0].strip()
    print(f"  识别到人名: {person_name}")

    # 3. 识别数字区域，判断模式
    print("  识别数字区域...")
    num_img = crop_region(
        screen,
        NUMBER_REGION["x1"],
        NUMBER_REGION["y1"],
        NUMBER_REGION["x2"],
        NUMBER_REGION["y2"],
    )

    if num_img is None:
        print("  [ERROR] 数字区域裁剪失败")
        return

    numbers = extract_numbers_from_region(num_img)
    print(f"  识别到的数字: {numbers}")

    if not numbers:
        print("  [ERROR] 未识别到数字")
        return

    max_num = max(numbers)

    if max_num not in MODE_CONFIG:
        print(f"  [ERROR] 无法识别的数字: {max_num}")
        return

    mode_name, n_candidates, candidate_indices = MODE_CONFIG[max_num]
    print(f"  模式: {mode_name} ({n_candidates}个候选)")

    # 4. 根据模式加载对应数量的指纹模板
    # 模式A(4个候选)→加载4个模板, 模式B(6个候选)→加载6个, 模式C(8个候选)→加载8个
    images_dir = app_cfg.get("fingerprint_images_dir", "images")
    print(f"  加载模板目录: {images_dir}")

    max_templates = n_candidates - 1  # 候选数-1 = 模板数
    templates = load_fingerprint_templates(person_name, images_dir, max_templates)

    if not templates:
        print(f"  [ERROR] 未找到人名 '{person_name}' 的指纹模板")
        # 保存截图用于调试
        os.makedirs(save_dir, exist_ok=True)
        screenshot_path = os.path.join(
            save_dir, f"fp_{datetime.now().strftime('%H%M%S')}_error.png"
        )
        save_image_chinese(screenshot_path, screen)
        print(f"  截图已保存: {screenshot_path}")
        return

    print(f"  加载了 {len(templates)} 个模板")

    # 5. 像素模板匹配
    print("  像素模板匹配...")
    matches = {}

    for cand_idx in candidate_indices:
        x1, y1, x2, y2 = CANDIDATE_BOXES[cand_idx]
        candidate_img = crop_region(screen, x1, y1, x2, y2)

        if candidate_img is None:
            continue

        best_idx, best_score = find_best_match(
            candidate_img, templates, threshold=match_threshold
        )

        if best_idx is not None:
            matches[cand_idx + 1] = best_idx + 1
            print(
                f"    候选 {cand_idx + 1}: 匹配模板 {best_idx + 1}, 分数={best_score:.3f}"
            )
        else:
            print(f"    候选 {cand_idx + 1}: 未匹配 (分数={best_score:.3f})")

    # 输出结果
    print(f"\n  ★ 指纹密码答案:")
    for cand_no in sorted(matches.keys()):
        template_no = matches[cand_no]
        print(f"    候选 {cand_no}  →  模板 {template_no}")

    # 6. 自动点击（如果启用）
    if app_cfg.get("fingerprint_auto_click", False):
        print("\n  执行自动点击...")
        # 尝试激活游戏窗口
        game_hwnd = _find_game_window()
        if game_hwnd:
            print(f"  找到游戏窗口: {game_hwnd}")
            _activate_window(game_hwnd)
            time.sleep(0.1)  # 等待窗口激活
        else:
            print("  未找到游戏窗口，将直接点击")

        # 按模板编号顺序点击：反转 matches 为 {模板编号: 候选编号}
        template_to_cand = {template_no: cand_no for cand_no, template_no in matches.items()}
        for template_no in sorted(template_to_cand.keys()):
            cand_no = template_to_cand[template_no]
            x1, y1, x2, y2 = CANDIDATE_BOXES[cand_no - 1]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            _win_click(cx, cy)
            print(f"    模板 {template_no} → 点击候选 {cand_no} @ ({cx}, {cy})")
            time.sleep(0.05)  # 增加等待时间，确保游戏响应
        print("  点击完成!")
    else:
        # 保存标注图（手动模式）- 使用PIL绘制
        print("\n  保存标注图...")
        from PIL import Image, ImageDraw, ImageFont

        # cv2 (BGR) 转 PIL (RGB)
        annotated_pil = Image.fromarray(cv2.cvtColor(screen, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(annotated_pil)

        # 尝试加载字体，失败则用默认
        try:
            font = ImageFont.truetype("simsun.ttc", 16)
        except:
            font = ImageFont.load_default()

        # 标注颜色
        NAME_COLOR = (255,120,120)      # 红色 - 人名区域
        NUMBER_COLOR = (120,255,255)  # 青色 - 数字区域
        CANDIDATE_COLOR = (120,255,120)  # 绿色 - 候选指纹区域

        # 标注人名区域
        draw.rectangle(
            [NAME_REGION["x1"], NAME_REGION["y1"], NAME_REGION["x2"], NAME_REGION["y2"]],
            outline=NAME_COLOR, width=1
        )
        draw.text((NAME_REGION["x1"], NAME_REGION["y1"] - 25), f" 人名:{person_name} ",
                  fill=NAME_COLOR, font=font)

        # 标注数字区域
        draw.rectangle(
            [NUMBER_REGION["x1"], NUMBER_REGION["y1"], NUMBER_REGION["x2"], NUMBER_REGION["y2"]],
            outline=NUMBER_COLOR, width=1
        )
        draw.text((NUMBER_REGION["x1"], NUMBER_REGION["y1"] - 25), f" 数字:{numbers} ",
                  fill=NUMBER_COLOR, font=font)

        # 标注候选指纹区域
        for cand_no in sorted(matches.keys()):
            x1, y1, x2, y2 = CANDIDATE_BOXES[cand_no - 1]
            template_no = matches[cand_no]

            # 画矩形框
            draw.rectangle([x1, y1, x2, y2], outline=CANDIDATE_COLOR, width=1)

            # 标签
            label = f" 候选{cand_no}→模板{template_no} "
            draw.text((x1, y1 - 25), label, fill=CANDIDATE_COLOR, font=font)

        os.makedirs(save_dir, exist_ok=True)
        annotated_path = os.path.join(
            save_dir, f"fp_{datetime.now().strftime('%H%M%S')}_annotated.png"
        )
        annotated_pil.save(annotated_path)
        print(f"  标注图已保存: {annotated_path}")

    print()
