"""
utils/config.py
配置文件的读取与写入。
"""

import os
import json
from typing import Any

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "settings.json")

# 最小默认配置（仅包含必要字段，配置已迁移到 settings.json）
_DEFAULT_CONFIG: dict[str, Any] = {
    "wechat_path": "",
    "wechatocr_path": "",
    "save_dir": "temp",
    "temp_dir": "temp",
    "hotkeys": {
        "morse": "f1",
        "fingerprint": "f6",
        "exit": "end"
    },
    "fingerprint_images_dir": "images",
    "fingerprint_auto_click": False,
    "regions": []
}


def _expand_env(path: str) -> str:
    """展开路径中的 %ENV% 变量。"""
    return os.path.expandvars(path)


def load() -> dict[str, Any]:
    """
    读取配置文件。若文件不存在，自动生成默认配置后再读取。
    返回已展开环境变量的配置字典。
    """
    if not os.path.exists(CONFIG_PATH):
        save(_DEFAULT_CONFIG)
        print(f"[Config] 已生成默认配置文件：{CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 展开环境变量
    cfg["wechat_path"] = _expand_env(cfg.get("wechat_path", ""))
    cfg["wechatocr_path"] = _expand_env(cfg.get("wechatocr_path", ""))

    # save_dir 支持相对路径（相对项目根目录）
    save_dir = cfg.get("save_dir", "captures")
    if not os.path.isabs(save_dir):
        save_dir = os.path.join(BASE_DIR, save_dir)
    cfg["save_dir"] = save_dir

    return cfg


def save(cfg: dict[str, Any]) -> None:
    """将配置字典写回 settings.json。"""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"[Config] 配置已保存至 {CONFIG_PATH}")
