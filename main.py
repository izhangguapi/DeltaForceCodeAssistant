"""
main.py —— 三角洲密码工具

用法：
    python main.py            正常启动，使用已保存的区域配置
    python main.py --preview  预览模式：截全屏标注配置区域 → 打开图片 → 退出，不启动识别

运行时热键（可在 settings.json 中自定义）：
    F1   截图 → OCR → 摩斯解码 → 输出密码 → 按下数字键
    F6   指纹识别
    End  退出程序
"""

import os
import sys
import time
import keyboard
from datetime import datetime

from utils import config as cfg_util
from core import capture, ocr, morse, hotkey, fingerprint
from core.selector import preview_regions


# ── 核心流程 ─────────────────────────────────────────────────

def run_pipeline(regions: list[dict]) -> None:
    """截图 → OCR → 摩斯解码 → 输出密码 → 按下数字键。"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ── 开始识别 ──")

    screenshots = capture.grab_regions(regions)
    password_digits: list[str] = []

    for name, img in screenshots:
        raw_text = ocr.recognize(img)
        digit    = morse.decode(raw_text)
        print(f"  [{name}]  OCR: {repr(raw_text):<30}  解码 → {digit}")
        password_digits.append(digit)

    password = "".join(password_digits)
    print(f"\n  ★ 识别密码：{password}\n")

    for digit in password_digits:
        if digit.isdigit():
            keyboard.press_and_release(digit)
            print(f"  → 已按下: {digit}")
            time.sleep(0.1)
        else:
            print(f"  → 识别失败，跳过: {digit}")

    print()


def print_status(regions: list[dict]) -> None:
    print("\n当前截图区域：")
    for r in regions:
        print(f"  {r.get('name','?'):6s}  left={r['left']}, top={r['top']}, "
              f"width={r['width']}, height={r['height']}")
    print()


# ── 主入口 ───────────────────────────────────────────────────

def main() -> None:
    show_preview = "--preview" in sys.argv or "-p" in sys.argv

    # ── 预览模式：截图标注 → 打开 → 退出，不启动识别 ──────
    if show_preview:
        print("=" * 55)
        print("  三角洲密码工具  [预览模式]")
        print("=" * 55)
        app_cfg = cfg_util.load()
        print(f"  配置文件 : {cfg_util.CONFIG_PATH}\n")
        # print_status(app_cfg["regions"])
        preview_regions(app_cfg["regions"], save_dir=app_cfg.get("save_dir", "captures"))
        return

    print("=" * 55)
    print("  三角洲密码工具")
    print("=" * 55)

    # 加载配置
    app_cfg = cfg_util.load()
    regions = app_cfg["regions"]
    hk_morse  = app_cfg["hotkeys"].get("morse", "f1")
    hk_fingerprint = app_cfg["hotkeys"].get("fingerprint", "f6")
    hk_exit = app_cfg["hotkeys"]["exit"]

    print(f"  配置文件 : {cfg_util.CONFIG_PATH}")
    print(f"  {hk_morse.upper():<5}: 摩斯解码")
    print(f"  {hk_fingerprint.upper():<5}: 指纹识别")
    print(f"  {hk_exit.upper():<5}: 退出程序")
    print(f"  p       : 预览当前配置区域（截图标注后打开）")
    print(f"  r       : 重新加载配置文件\n")

    # 初始化 OCR
    if not ocr.init(temp_dir=app_cfg.get("temp_dir")):
        print("[错误] OCR 初始化失败，程序退出。")
        return
    
    # 设置指纹模块的OCR引用
    fingerprint.set_wechat_ocr(ocr)

    # print_status(regions)

    # 注册热键
    running = True

    def on_run():
        run_pipeline(regions)

    def on_fingerprint():
        fingerprint.run_fingerprint_pipeline(app_cfg, app_cfg.get("save_dir", "captures"))

    def on_exit():
        print(f"\n{hk_exit.upper()} 键按下，程序退出。")
        hotkey.unregister_all()
        ocr.destroy()
        print("已退出。")
        os._exit(0)

    hotkey.register({hk_morse: on_run, hk_fingerprint: on_fingerprint, hk_exit: on_exit})
    # print(f"监听中，等待 {hk_morse.upper()} 触发……\n")

    # 主循环
    while running:
        try:
            cmd = input().strip().lower()

            if cmd == "p":
                preview_regions(regions, save_dir=app_cfg.get("save_dir", "captures"))

            elif cmd == "r":
                app_cfg = cfg_util.load()
                regions = app_cfg["regions"]
                print("配置已重新加载。")
                # print_status(regions)

        except (EOFError, KeyboardInterrupt):
            break

    # Ctrl+C 退出时的兜底清理
    hotkey.unregister_all()
    ocr.destroy()
    print("已退出。")


if __name__ == "__main__":
    main()
