# 《三角洲行动》密码工具

本项目整合了**摩斯码识别**和**指纹密码破解**两大功能，用于辅助破解《三角洲行动》游戏中的密码破解小游戏。

---

## 功能介绍

| 功能 | 热键 | 说明 |
|------|------|------|
| 摩斯码识别 | F1 | 识别屏幕上的摩斯码，输出数字并自动按键 |
| 指纹识别 | F6 | 识别游戏中的指纹密码，输出匹配结果 |
| 退出程序 | End | 退出程序 |

---

## 环境要求

- Python 3.9+
- Windows 系统
- 微信（版本 4.1.8.28，用于 OCR 识别）
- 微信 OCR 插件（首次登录微信后自动释放）
- **2k显示器（其他分辨率的电脑没做适配）**

### 依赖安装

```bash
pip install mss opencv-python numpy pillow keyboard
```

> `wcocr.pyd` 为本地私有模块，已放置在项目根目录，无需额外安装。

---

## 快速开始

### 1. 运行程序

```bash
python main.py
```

### 2. 程序界面

```
=======================================================
  《三角洲行动》游戏辅助工具
=======================================================
  配置文件 : config/settings.json
  F1      : 截图 + OCR + 摩斯解码 + 按键
  F6      : 指纹识别
  END     : 退出程序
  p       : 预览当前配置区域（截图标注后打开）
  r       : 重新加载配置文件

```

### 3. 使用流程

**摩斯码识别（F1）：**
1. 打开游戏，进入摩斯码输入界面
2. 按 F1 键触发识别
3. 程序自动识别并输入数字

**指纹识别（F6）：**
1. 打开游戏，进入指纹破解界面
2. 按 F6 键触发识别
3. 程序输出指纹匹配结果
4. 手动模式：自动保存标注图到 temp 目录
5. 自动点击模式：按模板顺序依次点击候选区域

---

## 项目结构

```
fingerprint/
├── main.py                 # 主程序入口
├── README.md               # 本文档
├── wcocr.pyd              # 微信OCR本地模块
├── config/
│   └── settings.json      # 配置文件
├── core/
│   ├── __init__.py
│   ├── capture.py         # 屏幕截图
│   ├── fingerprint.py     # 指纹识别模块
│   ├── hotkey.py          # 全局热键
│   ├── morse.py           # 摩斯码解码
│   ├── ocr.py             # 微信OCR封装
│   └── selector.py        # 区域预览
├── utils/
│   └── config.py          # 配置读写
├── temp/                  # 临时文件和截图目录
└── images/               # 指纹模板目录
```

---

## 配置文件说明

配置文件路径：`config/settings.json`

```json
{
  "wechat_path": "D:\\Program Files\\Tencent\\Weixin\\4.1.8.28",
  "wechatocr_path": "%APPDATA%\\Tencent\\xwechat\\XPlugin\\plugins\\WeChatOcr\\8082\\extracted\\wxocr.dll",
  "save_dir": "temp",
  "temp_dir": "temp",
  "hotkeys": {
    "morse": "f1",
    "fingerprint": "f6",
    "exit": "end"
  },
  "fingerprint_images_dir": "images",
  "fingerprint_auto_click": false,
  "fingerprint": {
    "name_region": {"x1": 706, "y1": 657, "x2": 866, "y2": 689},
    "number_region": {"x1": 1030, "y1": 530, "x2": 1365, "y2": 930},
    "candidate_boxes": [
      [1522, 560, 1627, 665],
      [1650, 560, 1755, 665],
      [1778, 560, 1883, 665],
      [1522, 687, 1627, 792],
      [1650, 687, 1755, 792],
      [1778, 687, 1883, 792],
      [1522, 815, 1627, 920],
      [1650, 815, 1755, 920],
      [1778, 815, 1883, 920]
    ],
    "match_threshold": 0.5,
    "mode_config": {
      "8": {"mode": "C", "candidates": 9},
      "6": {"mode": "B", "candidates": 7},
      "4": {"mode": "A", "candidates": 5}
    }
  },
  "regions": [
    { "name": "区域1", "left": 699, "top": 514, "width": 200, "height": 50 },
    { "name": "区域2", "left": 967, "top": 514, "width": 200, "height": 50 },
    { "name": "区域3", "left": 1234, "top": 514, "width": 200, "height": 50 }
  ]
}
```

### 配置说明

| 字段 | 说明 |
|------|------|
| `wechat_path` | 微信安装目录 |
| `wechatocr_path` | 微信OCR插件路径 |
| `save_dir` | 截图保存目录（默认 temp） |
| `temp_dir` | 临时文件目录 |
| `hotkeys.morse` | 摩斯码识别热键 |
| `hotkeys.fingerprint` | 指纹识别热键 |
| `hotkeys.exit` | 退出程序热键 |
| `fingerprint_images_dir` | 指纹模板目录 |
| `fingerprint_auto_click` | 指纹识别后是否自动点击 |
| `fingerprint.name_region` | 人名识别区域坐标 |
| `fingerprint.number_region` | 数字区域坐标 |
| `fingerprint.candidate_boxes` | 候选指纹区域坐标列表 |
| `fingerprint.match_threshold` | 模板匹配阈值 |
| `fingerprint.mode_config` | 游戏模式配置 |
| `regions` | 摩斯码识别区域配置 |

---

## 指纹识别详解

### 识别流程

```
F6键触发
    ↓
1. 截取屏幕
    ↓
2. OCR识别左侧人名区域 → 获取人物名称
    ↓
3. OCR识别数字区域 → 取最大值判断模式
    ↓
4. 根据人名加载 images/ 下的指纹模板
    ↓
5. cv2.matchTemplate 模板匹配
    ↓
6. 输出答案 / 保存标注图 / 自动点击
```

### 模式判断

| 最大数字 | 模式 | 候选数 | 模板数 |
|----------|------|--------|--------|
| 8 | C（困难） | 9 | 8 |
| 6 | B（普通） | 7 | 6 |
| 4 | A（简单） | 5 | 4 |

### 自动点击顺序

当 `fingerprint_auto_click = true` 时，程序会**按模板编号顺序**依次点击：
- 模板1对应的候选 → 模板2对应的候选 → 模板3对应的候选...

这是因为游戏中需要按正确顺序输入指纹密码。

### 标注图说明

当 `fingerprint_auto_click = false`（手动模式）时，程序会自动保存一张标注图到 temp 目录，包含：
- 红色框：人名识别区域
- 青色框：数字区域
- 绿色框：候选指纹区域（标注 `候选X→模板Y`）

### 指纹模板目录结构

```
images/
├── 格赫罗斯/          # 人名文件夹
│   ├── 1.png          # 模板1
│   ├── 2.png
│   └── ...
├── 埃德温/
│   └── ...
└── ...
```

每个文件夹存放同一个人物的指纹模板图片（1.png ~ 8.png），程序会根据模式自动加载对应数量的模板。

---

## 摩斯码识别详解

### 摩斯码对照表

| 数字 | 摩斯码 |
|------|--------|
| 0 | `-----` |
| 1 | `.----` |
| 2 | `..---` |
| 3 | `...--` |
| 4 | `....-` |
| 5 | `.....` |
| 6 | `-....` |
| 7 | `--...` |
| 8 | `---..` |
| 9 | `----.` |

---

## 调试命令

程序启动后支持以下控制台命令：

| 命令 | 说明 |
|------|------|
| `p` | 预览当前配置区域（截图标注后打开） |
| `r` | 重新加载配置文件 |

---

## 常见问题

**Q：按 F1/F6 没反应？**
> `keyboard` 库在 Windows 上可能需要管理员权限。请右键 PowerShell / 命令提示符，选择「以管理员身份运行」后再启动程序。

**Q：提示"找不到微信 OCR 组件"？**
> 检查 `settings.json` 中的 `wechat_path` 是否与本机微信安装路径一致，以及微信是否已登录过（OCR 插件需登录后才会释放）。

**Q：指纹识别结果不准确？**
> 1. 确认 `images/` 目录下有对应人名的指纹模板
> 2. 检查 `temp/` 目录下的截图和标注图
> 3. 调整 `fingerprint_auto_click` 设置为 `true` 开启自动点击

**Q：摩斯码识别结果返回 `?`？**
> 使用 `p` 命令预览截图区域，确认框住了完整的摩斯码内容。

**Q：自动点击位置偏移？**
> 程序使用 Windows 原生 API 进行点击，已处理 DPI 缩放问题。如仍有问题，检查游戏窗口是否正常激活。

---

## 预览模式

```bash
python main.py --preview
```

预览模式会截取全屏并标注配置区域，方便确认坐标是否正确。

---

## 技术说明

### 点击实现

程序使用 Windows API 实现高精度鼠标点击：
- `SetCursorPos` - 设置鼠标位置
- `mouse_event` - 触发点击事件
- `SetProcessDpiAwareness` - 声明 DPI 感知，消除缩放偏移

相比 pyautogui，原生 API 更底层，响应更快，兼容性好。

### 模板匹配

指纹识别采用 OpenCV 的 `cv2.matchTemplate` 进行像素级模板匹配，使用 `TM_CCOEFF_NORMED` 算法计算相似度。

---

## 更新日志

- **v2.1**: 优化自动点击，改用 Windows API 提高点击精度
- **v2.0**: 整合摩斯码识别 + 指纹识别，统一入口
- **v1.0**: 初始版本，仅支持指纹识别（SSIM方案）
