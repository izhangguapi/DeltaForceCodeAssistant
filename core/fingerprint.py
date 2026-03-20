"""
core/fingerprint.py
指纹识别模块：
  截屏 → OCR识别人名/数字 → 模式判断 → 模板匹配 → 自动点击 / 保存标注图
"""

import os
import re
import time
import numpy as np
import cv2
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageGrab

from core import ocr as _ocr


# ── OCR 纠错映射表 ───────────────────────────────────────────
# 微信 OCR 偶有字形相似的误识别，在此做强制纠正

_OCR_CORRECTION_MAP = {
    "克菜尔": "克莱尔",
}


# ── 图片工具函数 ─────────────────────────────────────────────


def _crop(img: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray | None:
    """安全裁剪图片，超出边界时自动截断。"""
    h, w = img.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    return img[y1:y2, x1:x2] if x2 > x1 and y2 > y1 else None


def _cv2_read(path: str) -> np.ndarray | None:
    """读取图片（支持中文路径）。"""
    if not os.path.exists(path):
        return None
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _cv2_save(path: str, img: np.ndarray) -> None:
    """保存图片（支持中文路径）。"""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg"):
        _, buf = cv2.imencode(ext, img)
        buf.tofile(path)
    else:
        cv2.imwrite(path, img)


def _pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
    """PIL Image → OpenCV BGR 格式。"""
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


# ── 人名纠错 ─────────────────────────────────────────────────


def _correct_person_name(raw_name: str, images_dir: str) -> str:
    """
    对 OCR 识别的原始人名进行纠错：
      1. 精确映射表
      2. 模糊匹配（字符相似度 ≥ 0.6 → 匹配 images/ 下同名目录）
    返回纠错后的人名，无法确定时返回原始值。
    """
    name = raw_name.strip()

    # 精确映射
    if name in _OCR_CORRECTION_MAP:
        corrected = _OCR_CORRECTION_MAP[name]
        if corrected != name:
            print(f"  [纠错] '{name}' → '{corrected}'")
        return corrected

    # 目录精确匹配
    if os.path.isdir(os.path.join(images_dir, name)):
        return name

    # 模糊匹配
    try:
        candidates = [
            d
            for d in os.listdir(images_dir)
            if os.path.isdir(os.path.join(images_dir, d))
        ]
    except OSError:
        return name

    def _similarity(a: str, b: str) -> float:
        return sum(1 for c in a if c in b) / max(len(a), len(b), 1)

    best = max(candidates, key=lambda c: _similarity(name, c), default=None)
    if best and _similarity(name, best) >= 0.6:
        print(f"  [纠错] 模糊匹配 '{name}' → '{best}'")
        return best

    return name


# ── 模板加载 ─────────────────────────────────────────────────


def load_templates(person_name: str, images_dir: str, max_count: int = 8) -> list[dict]:
    """
    加载指定人名目录下的指纹模板（灰度图）。
    返回 [{"index": int, "image": np.ndarray}, ...]，按编号排序。
    """
    templates = []
    person_dir = os.path.join(images_dir, person_name)

    # 优先查找同名文件夹
    if os.path.isdir(person_dir):
        for i in range(1, max_count + 1):
            path = os.path.join(person_dir, f"{i}.png")
            img = _cv2_read(path)
            if img is not None:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                templates.append({"index": i, "image": gray})
        if templates:
            return templates

    # 兜底：根目录下同名文件
    for fname in os.listdir(images_dir):
        if fname.startswith(person_name) and fname.endswith(".png"):
            img = _cv2_read(os.path.join(images_dir, fname))
            if img is not None:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                idx = (
                    int(fname.split(".")[0])
                    if fname[0].isdigit()
                    else len(templates) + 1
                )
                templates.append({"index": idx, "image": gray})

    return templates


# ── 模板匹配 ─────────────────────────────────────────────────


def find_best_match(
    candidate_img: np.ndarray, templates: list[dict], threshold: float = 0.5
) -> tuple[int | None, float]:
    """
    在候选图像中寻找最佳匹配的模板。
    返回 (模板索引, 匹配分数)，不命中返回 (None, best_score)。
    """
    if not templates:
        return None, 0.0

    cand_gray = (
        cv2.cvtColor(candidate_img, cv2.COLOR_BGR2GRAY)
        if len(candidate_img.shape) == 3
        else candidate_img
    )

    best_idx, best_score = None, 0.0
    h, w = cand_gray.shape

    for tmpl in templates:
        resized = cv2.resize(tmpl["image"], (w, h))
        _, max_val, _, _ = cv2.minMaxLoc(
            cv2.matchTemplate(cand_gray, resized, cv2.TM_CCOEFF_NORMED)
        )
        if max_val > best_score:
            best_score = max_val
            best_idx = tmpl["index"] - 1  # 转回 0 索引

    return (best_idx, best_score) if best_score > threshold else (None, best_score)


# ── 标注图 ───────────────────────────────────────────────────


def _draw_annotated(
    screen_bgr: np.ndarray,
    person_name: str,
    numbers: list[int],
    matches: dict[int, int],
    name_reg: dict,
    num_reg: dict,
    boxes: list[tuple],
) -> Image.Image:
    """在截图上绘制标注框并返回 PIL 图片。"""
    pil_img = Image.fromarray(cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    try:
        font = ImageFont.truetype("msyh.ttc", 16)
    except Exception:
        font = ImageFont.load_default()

    C = {
        "name": (255, 120, 120),  # 红色
        "number": (120, 255, 255),  # 青色
        "candidate": (120, 255, 120),  # 绿色
    }

    # 人名区域
    draw.rectangle(
        [name_reg["x1"], name_reg["y1"], name_reg["x2"], name_reg["y2"]],
        outline=C["name"],
        width=1,
    )
    draw.text(
        (name_reg["x1"], name_reg["y1"] - 25),
        f" 人名:{person_name} ",
        fill=C["name"],
        font=font,
    )

    # 数字区域
    draw.rectangle(
        [num_reg["x1"], num_reg["y1"], num_reg["x2"], num_reg["y2"]],
        outline=C["number"],
        width=1,
    )
    draw.text(
        (num_reg["x1"], num_reg["y1"] - 25),
        f" 数字:{numbers} ",
        fill=C["number"],
        font=font,
    )

    # 候选格子
    for cand_no in sorted(matches):
        x1, y1, x2, y2 = boxes[cand_no - 1]
        draw.rectangle([x1, y1, x2, y2], outline=C["candidate"], width=1)
        draw.text(
            (x1, y1 - 25),
            f" 候选{cand_no}→模板{matches[cand_no]} ",
            fill=C["candidate"],
            font=font,
        )

    return pil_img


# ── 主流程 ───────────────────────────────────────────────────


def run_fingerprint_pipeline(app_cfg: dict, save_dir: str = None) -> None:
    """
    指纹识别主流程。
    Args:
        app_cfg:  完整配置字典（含 fingerprint.* 子配置）
        save_dir: 调试图片保存目录，默认取 app_cfg["save_dir"]
    """
    from utils.mouse import win_click, find_game_window, activate_window, click_sequence

    # ── 解析配置 ────────────────────────────────────────────
    fp_cfg = app_cfg.get("fingerprint", {})
    name_reg = fp_cfg.get("name_region", {"x1": 706, "y1": 657, "x2": 866, "y2": 689})
    num_reg = fp_cfg.get(
        "number_region", {"x1": 1030, "y1": 530, "x2": 1365, "y2": 930}
    )
    boxes_cfg = fp_cfg.get(
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
    boxes = [tuple(b) for b in boxes_cfg]

    mode_cfg = fp_cfg.get(
        "mode_config",
        {
            "8": {"mode": "C", "candidates": 9, "indices": list(range(9))},
            "6": {"mode": "B", "candidates": 7, "indices": list(range(7))},
            "4": {"mode": "A", "candidates": 5, "indices": list(range(5))},
        },
    )
    mode_map = {
        int(k): (v["mode"], v["candidates"], v["indices"]) for k, v in mode_cfg.items()
    }

    threshold = fp_cfg.get("match_threshold", 0.5)
    images_dir = app_cfg.get("fingerprint_images_dir", "images")
    save_dir = save_dir or app_cfg.get("save_dir", "temp")

    # ── 1. 截屏 ─────────────────────────────────────────────
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ── 指纹识别开始 ──")
    screen_bgr = _pil_to_cv2(ImageGrab.grab())

    # ── 2. OCR 人名 ─────────────────────────────────────────
    print("  识别人名...")
    name_img = _crop(
        screen_bgr, name_reg["x1"], name_reg["y1"], name_reg["x2"], name_reg["y2"]
    )
    if name_img is None:
        print("  [ERROR] 人名区域裁剪失败")
        return

    name_pil = Image.fromarray(cv2.cvtColor(name_img, cv2.COLOR_BGR2RGB))
    raw_name = _ocr.recognize(name_pil).strip()
    if not raw_name:
        print("  [ERROR] 未识别到人名")
        return

    person_name = _correct_person_name(raw_name, images_dir)
    print(f"  识别到人名: {person_name}")

    # ── 3. OCR 数字区域 ────────────────────────────────────
    print("  识别数字区域...")
    num_img = _crop(
        screen_bgr, num_reg["x1"], num_reg["y1"], num_reg["x2"], num_reg["y2"]
    )
    if num_img is None:
        print("  [ERROR] 数字区域裁剪失败")
        return

    num_pil = Image.fromarray(cv2.cvtColor(num_img, cv2.COLOR_BGR2RGB))
    raw_text = _ocr.recognize(num_pil)
    numbers = [int(n) for n in re.findall(r"\d+", raw_text)]
    print(f"  识别到的数字: {numbers}")
    if not numbers:
        print("  [ERROR] 未识别到数字")
        return

    max_num = max(numbers)
    if max_num not in mode_map:
        print(f"  [ERROR] 无法识别的数字: {max_num}")
        return

    mode_name, n_candidates, indices = mode_map[max_num]
    print(f"  模式: {mode_name}（{n_candidates} 个候选）")

    # ── 4. 加载模板 ─────────────────────────────────────────
    print(f"  加载模板目录: {images_dir}")
    templates = load_templates(person_name, images_dir, n_candidates - 1)
    if not templates:
        print(f"  [ERROR] 未找到人名 '{person_name}' 的指纹模板")
        _save_debug(screen_bgr, save_dir)
        return
    print(f"  加载了 {len(templates)} 个模板")

    # ── 5. 模板匹配 ────────────────────────────────────────
    print("  像素模板匹配...")
    matches: dict[int, int] = {}
    for ci in indices:
        cand = _crop(screen_bgr, *boxes[ci])
        if cand is None:
            continue
        idx, score = find_best_match(cand, templates, threshold)
        if idx is not None:
            matches[ci + 1] = idx + 1
            print(f"    候选 {ci + 1}: 匹配模板 {idx + 1}, 分数={score:.3f}")
        else:
            print(f"    候选 {ci + 1}: 未匹配 (分数={score:.3f})")

    print(f"\n  ★ 指纹密码答案:")
    for cn in sorted(matches):
        print(f"    候选 {cn}  →  模板 {matches[cn]}")

    # ── 6. 后处理：点击 / 标注图 ─────────────────────────────
    if app_cfg.get("fingerprint_auto_click", False):
        _do_auto_click(boxes, matches, save_dir, app_cfg, mode_name)
    else:
        _do_annotated(
            screen_bgr,
            person_name,
            numbers,
            matches,
            name_reg,
            num_reg,
            boxes,
            save_dir,
        )


# ── 内部后处理 ───────────────────────────────────────────────


def _do_auto_click(boxes, matches, save_dir, app_cfg, mode_name):
    """自动点击模式：按模板顺序点击候选格子 → 延迟确认点击。"""
    from utils.mouse import win_click, find_game_window, activate_window, click_sequence

    print("\n  执行自动点击...")
    hwnd = find_game_window()
    if hwnd:
        print(f"  找到游戏窗口: {hwnd}")
        activate_window(hwnd)
        time.sleep(0.1)
    else:
        print("  未找到游戏窗口，将直接点击")

    t2c = {tn: cn for cn, tn in matches.items()}
    for tn in sorted(t2c):
        cn = t2c[tn]
        x1, y1, x2, y2 = boxes[cn - 1]
        win_click((x1 + x2) // 2, (y1 + y2) // 2)
        print(f"    模板 {tn} → 点击候选 {cn}")
        time.sleep(0.05)

    confirm = app_cfg.get("morse_confirm_clicks", [])
    if confirm:
        time.sleep(1.7)
        print("  点击下载")
        click_sequence(confirm, delay=0.05)


def _do_annotated(
    screen_bgr, person_name, numbers, matches, name_reg, num_reg, boxes, save_dir
):
    """手动模式：保存标注图。"""
    print("\n  保存标注图...")
    pil = _draw_annotated(
        screen_bgr, person_name, numbers, matches, name_reg, num_reg, boxes
    )
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(
        save_dir, f"fp_{datetime.now().strftime('%H%M%S')}_annotated.png"
    )
    pil.save(path)
    print(f"  标注图已保存: {path}")


def _save_debug(screen_bgr, save_dir):
    """调试截图：匹配失败时保存。"""
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, f"fp_{datetime.now().strftime('%H%M%S')}_error.png")
    _cv2_save(path, screen_bgr)
    print(f"  截图已保存: {path}")
