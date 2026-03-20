# 《三角洲行动》密码工具

整合**摩斯码识别**与**指纹密码破解**两大功能，辅助完成《三角洲行动》骇客电脑小游戏。程序仅读取屏幕截图，不修改任何游戏数据。

> [!WARNING]
> **当前仅适配 2K 分辨率（2560×1440）显示器，其他分辨率需自行修改坐标配置。**

---

## 热键一览

| 热键  | 功能                                                                          |
| ----- | ----------------------------------------------------------------------------- |
| `Ctrl+Alt+Q` | 摩斯码识别 → OCR 解码 → 自动输入数字 → 延迟 0.6s → 点击确认坐标 |
| `Ctrl+Alt+W` | 指纹识别 → 模板匹配 → 自动点击 / 保存标注图                |
| `End` | 退出程序                                                                      |
| `p`   | 预览配置区域（截图标注后自动打开）                                            |
| `r`   | 重新加载配置文件                                                              |

---

## 环境要求

- Python 3.9+ / Windows 系统
- 微信 4.1.8.28（OCR 依赖，需登录过一次以释放插件）

```bash
pip install mss opencv-python numpy pillow keyboard
```

> `wcocr.pyd` 已放置于项目根目录，无需额外安装。

---

## 快速开始

```bash
# 以管理员身份运行（keyboard 库需要）
python main.py
```

启动后控制台输出：

```
=======================================================
  《三角洲行动》游戏辅助工具
=======================================================
  配置文件 : config/settings.json
  Ctrl+Alt+Q: 截图 + OCR + 摩斯解码 + 按键
  Ctrl+Alt+W: 指纹识别
  END     : 退出程序
  p       : 预览当前配置区域
  r       : 重新加载配置文件
```

---

## 项目结构

```
fingerprint/
├── main.py              # 程序入口
├── wcocr.pyd            # 微信 OCR 本地模块
├── config/
│   └── settings.json    # 配置文件
├── core/
│   ├── capture.py       # 屏幕截图
│   ├── fingerprint.py   # 指纹识别（含自动点击）
│   ├── hotkey.py        # 全局热键监听
│   ├── morse.py         # 摩斯码解码
│   ├── ocr.py           # 微信 OCR 封装
│   └── selector.py      # 区域预览工具
├── utils/
│   └── config.py        # 配置读写
├── images/              # 指纹模板（按人名分子目录）
└── temp/                # 运行时输出：标注图、错误截图
```

---

## 配置文件

路径：`config/settings.json`

```json
{
  "wechat_path": "D:\\Program Files\\Tencent\\Weixin\\4.1.8.28",
  "wechatocr_path": "%APPDATA%\\Tencent\\xwechat\\XPlugin\\plugins\\WeChatOcr\\8082\\extracted\\wxocr.dll",
  "save_dir": "temp",
  "temp_dir": "temp",
  "hotkeys": {
    "morse": "ctrl+alt+q",
    "fingerprint": "ctrl+alt+w",
    "exit": "end"
  },
  "fingerprint_images_dir": "images",
  "fingerprint_auto_click": true,
  "morse_confirm_clicks": [
    { "x": 1359, "y": 1060 },
    { "x": 1241, "y": 1060 }
  ],
  "fingerprint": {
    "name_region": { "x1": 706, "y1": 657, "x2": 866, "y2": 689 },
    "number_region": { "x1": 1030, "y1": 530, "x2": 1365, "y2": 930 },
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
      "8": {
        "mode": "C",
        "candidates": 9,
        "indices": [0, 1, 2, 3, 4, 5, 6, 7, 8]
      },
      "6": { "mode": "B", "candidates": 7, "indices": [0, 1, 2, 3, 4, 5, 6] },
      "4": { "mode": "A", "candidates": 5, "indices": [0, 1, 2, 3, 4] }
    }
  },
  "regions": [
    { "name": "区域1", "left": 699, "top": 514, "width": 200, "height": 50 },
    { "name": "区域2", "left": 967, "top": 514, "width": 200, "height": 50 },
    { "name": "区域3", "left": 1234, "top": 514, "width": 200, "height": 50 }
  ]
}
```

### 关键配置说明

| 字段                          | 说明                                                               |
| ----------------------------- | ------------------------------------------------------------------ |
| `wechat_path`                 | 微信安装目录，需与本机版本一致                                     |
| `fingerprint_auto_click`      | `true` 自动点击 / `false` 仅保存标注图                             |
| `morse_confirm_clicks`        | 摩斯码输入完成后延迟 1.5s 依次点击的坐标列表，留空数组 `[]` 则跳过 |
| `fingerprint.name_region`     | 人名 OCR 截取区域                                                  |
| `fingerprint.number_region`   | 模式判断数字区域                                                   |
| `fingerprint.candidate_boxes` | 9 个候选指纹格子坐标 `[x1,y1,x2,y2]`                               |
| `fingerprint.match_threshold` | 模板匹配阈值（0~1，默认 0.5）                                      |
| `fingerprint.mode_config`     | 游戏模式对应的候选数与格子索引                                     |

---

## 指纹识别详解

### 完整流程

```
按下 Ctrl+Alt+W
  │
  ├─ 1. 截取全屏
  ├─ 2. OCR 识别人名 → 两级纠错（精确映射 + 模糊匹配）
  ├─ 3. OCR 识别数字区域 → 取最大值 → 确定游戏模式
  ├─ 4. 按模式加载 images/<人名>/ 下的指纹模板
  ├─ 5. cv2.matchTemplate 逐格匹配
  │
  ├─ [auto_click=true]  按模板顺序依次点击候选格子
  │     └─ [morse_confirm_clicks 非空] 延迟 1.7s → 依次点击确认坐标
  └─ [auto_click=false] 保存标注图到 temp/fp_HHMMSS_annotated.png
```

### 游戏模式

| 数字区域最大值 |  模式  | 候选格子数 | 加载模板数 |
| :------------: | :----: | :--------: | :--------: |
|       8        | C 困难 |     9      |     8      |
|       6        | B 普通 |     7      |     6      |
|       4        | A 简单 |     5      |     4      |

### 自动点击顺序

程序**按模板编号从小到大**点击，而非按格子位置顺序。

```
匹配结果：候选1→模板3  候选2→模板1  候选3→模板2

点击顺序：模板1 → 点候选2
        模板2 → 点候选3
        模板3 → 点候选1
```

### OCR 纠错

微信 OCR 对形近字偶有误识别，程序内置两级纠错：

1. **精确映射**：`_OCR_CORRECTION_MAP`，如 `克菜尔` → `克莱尔`
2. **模糊兜底**：与 `images/` 下所有人名目录比较字符相似度，≥ 0.6 时自动纠正

### 手动模式标注图

`fingerprint_auto_click = false` 时保存的标注图颜色说明：

| 颜色 | 区域                              |
| ---- | --------------------------------- |
| 红色 | 人名 OCR 区域                     |
| 青色 | 数字 OCR 区域                     |
| 绿色 | 候选格子（含 `候选X→模板Y` 标签） |

### 模板目录结构

```
images/
├── 格赫罗斯/
│   ├── 1.png  ← 模板编号从 1 开始
│   ├── 2.png
│   └── ...（最多 8.png）
├── 克莱尔/
└── ...
```

---

## 摩斯码识别详解

### 完整流程

```
按下 Ctrl+Alt+Q
  │
  ├─ 1. 截取三个区域截图
  ├─ 2. OCR 识别各区域摩斯码内容
  ├─ 3. 解码为数字（失败返回 ?）
  ├─ 4. 依次模拟按下数字键（间隔 50ms）
  │
  └─ [morse_confirm_clicks 非空 且 三个数字全部识别成功]
       等待 0.6s → 依次点击确认坐标（间隔 50ms）
```

> 若任意一个区域识别失败（返回 `?`），跳过确认点击步骤。  
> `morse_confirm_clicks` 设为 `[]` 时同样跳过。

---

## 摩斯码对照表

| 数字 | 摩斯码  | 数字 | 摩斯码  |
| :--: | ------- | :--: | ------- |
|  0   | `-----` |  5   | `.....` |
|  1   | `.----` |  6   | `-....` |
|  2   | `..---` |  7   | `--...` |
|  3   | `...--` |  8   | `---..` |
|  4   | `....-` |  9   | `----.` |

---

## 常见问题

**Q：按 Ctrl+Alt+Q/W 没反应？**

> 请以**管理员身份**运行程序（`keyboard` 库需要）。

**Q：找不到微信 OCR 组件？**

> 确认 `wechat_path` 与本机微信版本一致，且微信已完成登录（OCR 插件在首次登录后释放）。

**Q：识别到的人名不正确？**

> 在 `core/fingerprint.py` 的 `_OCR_CORRECTION_MAP` 中添加纠错映射：
>
> ```python
> _OCR_CORRECTION_MAP = {
>     "误识别的名字": "正确名字",
> }
> ```

**Q：指纹匹配结果不准？**

> 1. 确认 `images/<人名>/` 目录下有对应模板图片
> 2. 开启手动模式，查看 `temp/` 下的标注图，确认候选区域坐标正确
> 3. 适当降低 `match_threshold`（如 `0.3`）

**Q：自动点击位置偏移？**

> 程序启动时声明 Per-Monitor DPI 感知，坐标直接对应物理像素。若仍偏移，请用 `p` 命令预览确认坐标配置是否与当前分辨率匹配。

**Q：摩斯码识别返回 `?`？**

> 用 `p` 命令预览截图区域，确认识别框完整覆盖了摩斯码内容。

---

## 技术实现

### 鼠标点击

```
SetProcessDpiAwareness(2)   # 启动时：Per-Monitor DPI 感知，坐标 = 物理像素
SetCursorPos(x, y)          # 移动光标
mouse_event(LEFTDOWN)       # 按下，等待 50ms
mouse_event(LEFTUP)         # 释放
```

点击前自动搜索并激活游戏窗口（匹配标题含 "三角洲" 或 "Delta Force"）。

### 模板匹配

`cv2.matchTemplate` + `TM_CCOEFF_NORMED`：候选图像与模板均转灰度，模板缩放至候选尺寸后计算相似度，超过阈值即匹配成功。

---

## 更新日志

| 版本 | 变更                                                         |
| ---- | ------------------------------------------------------------ |
| v2.3 | 摩斯码输入后增加 0.6s 延迟确认点击（`morse_confirm_clicks` 可配置） |
| v2.2 | 新增 OCR 人名纠错（精确映射 + 模糊匹配）                     |
| v2.1 | 改用 Windows 原生 API 点击；自动点击改为按模板顺序；手动模式保存标注图 |
| v2.0 | 整合摩斯码 + 指纹识别，统一入口                              |
| v1.0 | 初始版本，指纹识别（SSIM 方案）                              |
