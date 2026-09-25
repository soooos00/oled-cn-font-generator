# OLED 中文字库生成器

> 为 STM32 + SSD1306 项目一键生成中文点阵字库。输出**纯 ASCII 源码**，Keil AC5 / AC6 / GCC 直接编译，不会乱码。

<p>
  <img alt="platform" src="https://img.shields.io/badge/platform-Windows-0078D4">
  <img alt="mcu" src="https://img.shields.io/badge/MCU-STM32F103-03234B">
  <img alt="font" src="https://img.shields.io/badge/font-16x16%20HZK16--compatible-2ea44f">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-blue">
</p>

---

## 目录

- [解决什么问题](#解决什么问题)
- [特性](#特性)
- [快速开始](#快速开始)
- [图形界面](#图形界面)
- [命令行用法](#命令行用法)
- [API 参考](#api-参考)
- [硬件接线](#硬件接线)
- [项目结构](#项目结构)
- [常见问题](#常见问题)

---

## 解决什么问题

在 STM32 上显示中文，几乎每个人都会撞上这三堵墙：

### 1. 源码里写中文，Keil 编译报错

ARM Compiler 5 按 **GBK/ANSI** 读源码。如果文件存成 UTF-8：

```c
OLED_ShowString(0, 0, "温度");   // ✗ error: missing closing quote
```

原因很隐蔽——某个汉字的 UTF-8 字节恰好是 `0x22`（引号），把字符串提前截断了。

**本项目的做法**：生成的代码里**一个中文字符都没有**，全部用枚举调用：

```c
OLED_ShowWord(0, 0, W_WENDU);    // ✓ 纯 ASCII, 永不出错
```

### 2. 整字库太大，Flash 装不下

标准 HZK16 字库有 260KB，C8T6 只有 64KB Flash。

**本项目的做法**：按需取字。20 个常用汉字只占 **720 字节**，ASCII 可裁剪到 **16 字节**。

### 3. 刷新数值时屏幕闪烁

直接写屏的写法，每个汉字要 16 次 I2C 事务；改一个数字得先擦后画，中间那段空白就是闪烁。

**本项目的做法**：1KB 显存缓冲 + 脏页刷新，一页 128 字节**一次事务**推完。

```c
OLED_ShowNum(56, 2, duty, 3);
OLED_RefreshDirty();          // 只推被改动的页
```

---

## 特性

| 特性 | 说明 |
|------|------|
| **任意汉字** | 从系统字体取 16×16 点阵，HZK16 兼容取模（纵向、LSB 在上、先上后下） |
| **纯 ASCII 源码** | 生成的 `.c` / `.h` 非 ASCII 行数为 **0**，AC5/AC6/GCC 通用 |
| **追加模式** | 重复运行只加新字，不覆盖已有字库（靠 `@WORDS` 元数据行） |
| **图形化管理器** | 点阵预览、**点击字形直接给调用代码**、✕ 删字、勾选符号 |
| **ASCII 可裁剪** | 连续字符集自动免查找表，最低 16 字节 |
| **无闪烁刷新** | GRAM 缓冲 + 脏页追踪，主循环一行搞定 |
| **零依赖运行** | 便携版打包了 Python 运行时，换电脑双击即用 |

**体积参考**

| 内容 | 大小 |
|------|------|
| 单个汉字 | 36 字节 |
| 单个 ASCII 字符 | 16 字节 |
| 全部 95 个 ASCII | 1520 字节 |
| 20 个常用汉字 + 数字符号 | 约 1 KB |

---

## 快速开始

### 方式一：便携版（推荐，无需装 Python）

1. 从 [Releases](../../releases) 下载 `OLED字库管理器_便携版.zip`
2. 解压后双击 `OLED字库管理器.exe`
3. 第一次运行会让你选字库目录 → 选工程里的 `Other` 文件夹
4. 输入框加字（如 `温度 报警`）→ 点「💾 生成字库」
5. 回到 Keil/EIDE：**Reload + Rebuild**

> ⚠️ `_internal` 文件夹必须和 exe 放在同一级，不能只复制 exe。

### 方式二：源码运行

```bash
pip install Pillow pypinyin
python tools/font_gui.py
```

需要 Python 自带 tkinter（官方安装包默认包含）。

### 方式三：命令行

```bash
# 生成字库并复制到工程
python tools/make_font.py "温度 报警 转速" --out "C:/你的工程/Other"

# 追加新字（旧字自动保留）
python tools/make_font.py "占空比" --out "C:/你的工程/Other"

# 清空重来
python tools/make_font.py "温度" --out "C:/你的工程/Other" --reset
```

---

## 图形界面

界面分为四块：字模网格、添加栏、词组列表、操作按钮。

**字模网格** — 每个汉字显示真实点阵预览（从 `oledfont.c` 解析，不是重新渲染），右侧 ✕ 删除。删除一个字会连带移除包含它的词组（删除前会列出受影响项）。

**点击字形** — 弹出可复制的调用代码：

```
点击「转」→
    OLED_ShowHz(0, 0, HZ_ZHUAN);          /* 转 */

    /* 包含该字的词组 */
    OLED_ShowWord(0, 0, W_ZHUANSU);       /* 转速 */
```

**🔤 符号设置** — 勾选要编译进字库的 ASCII 符号，实时显示 Flash 占用。提供「只要数字」「数字+字母」「数字+常用符号」快捷预设。

**📖 语法规则** — 一键列出全部 API 用法、坐标规则、常见错误，末尾自动附上当前字库的所有可用枚举。

---

## 命令行用法

```
python tools/make_font.py <词组...> [选项]

选项:
  --out DIR     生成后复制到 DIR（你的工程 Other 目录）
  --preview     额外生成 preview.png 预览效果
  --reset       清空已有字库，只按本次输入重新生成
```

**追加模式**（默认）：脚本读取 `--out` 目录里 `oledfont.h` 的元数据行，自动保留已有词组：

```c
/* @WORDS: 6E29,5EA6|62A5,8B66 */      ← 词组构成（码点）
 * @ASCII: 30,31,32,33,34,35,36,37,38,39
 */
```

所以重复运行不会丢字，直接加新词即可。想从零开始加 `--reset`。

---

## API 参考

全部 7 个函数，都在 `oledfont.h` 里声明。

### 坐标规则

```
x = 像素列, 范围 0 ~ 127
y = 页号,   范围 0 ~ 7    (每页 8 像素行)

汉字宽 16px, ASCII 宽 8px
字符高 16px = 跨两页, 所以 y 最大只能到 6
```

| y | 像素行 | | y | 像素行 |
|---|--------|---|----|--------|
| 0 | 0 | | 4 | 32 |
| 1 | 8 | | 5 | 40 |
| 2 | 16 | | 6 | 48 |
| 3 | 24 | | 7 | 56（下半页越界）|

### 显示函数

| 函数 | 用途 |
|------|------|
| `OLED_ShowHz(x, y, HZ_XXX)` | 单个汉字 |
| `OLED_ShowWord(x, y, W_XXX)` | 整词 |
| `OLED_ShowStr(x, y, "文本")` | ASCII + UTF-8 混合 |
| `OLED_ShowNum(x, y, num, width)` | 无符号数字，右对齐，左补空格 |
| `OLED_ShowFloat1(x, y, scaled10, width)` | 一位小数，`505` → `50.5` |
| `OLED_ShowSigned(x, y, num, width)` | 带 `+` / `-` 符号 |
| `OLED_ShowChar(x, y, c)` | 单个 ASCII（内部使用） |

`width` 是占几个字符位（每位 8px），作用是**擦除旧值**：

```c
OLED_ShowNum(x, y, 7,    3);   // "  7"
OLED_ShowNum(x, y, 50,   3);   // " 50"
OLED_ShowNum(x, y, 100,  3);   // "100"
OLED_ShowNum(x, y, 1000, 3);   // "000"  ← 溢出，只显示低 3 位
```

### 刷新函数

所有 `OLED_ShowXxx()` 先写入 1KB 内存缓冲，**必须调刷新函数才会显示**。

| 函数 | 用途 |
|------|------|
| `OLED_Refresh()` | 整屏推屏，布局完成后调一次 |
| `OLED_RefreshDirty()` | **只推被改动的页 —— 主循环用这个** |
| `OLED_RefreshPage(p)` | 推指定一页（0~7） |
| `OLED_RefreshPages(y0, y1)` | 推连续多页 |
| `OLED_RefreshArea(x, y, w, h)` | 推像素区域 |

> ⚠️ 一个字符跨**两页**。手工只刷 `OLED_RefreshPage(2)` 会让数字下半截留在旧值。
> `OLED_RefreshDirty()` 会自动追踪哪些页被改动，不用自己算。

### 缓冲区操作

| 函数 | 用途 |
|------|------|
| `OLED_BufClear()` | 只清内存缓冲 |
| `OLED_Clear()` | 清缓冲 + 清屏 |
| `OLED_DrawPoint(x, y, on)` | 画点（`on`: 1=亮, 0=灭）|
| `OLED_DrawHLine(x, y, w)` | 画横线 |

### 完整示例

```c
#include "oled.h"
#include "oledfont.h"

int main(void) {
    uint32_t rpm = 0;

    SystemInit();
    delay_init();
    OLED_Init();

    /* 静态部分：画一次，整屏推一次 */
    OLED_ShowWord(0, 0, W_ZHUANSU);      /* 转速 */
    OLED_ShowStr (48, 0, ":");
    OLED_ShowStr (96, 0, "RPM");

    OLED_ShowWord(0, 2, W_ZHANKONGBI);   /* 占空比 */
    OLED_ShowStr (48, 2, ":");
    OLED_ShowStr (80, 2, "%");

    OLED_Refresh();

    /* 动态部分：只重画数字，只推变化的页 */
    while (1) {
        OLED_ShowNum(56, 0, rpm, 5);
        OLED_ShowNum(56, 2, 50, 3);
        OLED_RefreshDirty();

        rpm += 10;
        if (rpm > 99999) rpm = 0;
        delay_ms(100);
    }
}
```

---

## 硬件接线

默认软件 I2C，引脚在 `oled.c` 顶部可改：

```c
#define OLED_GPIO_PORT   GPIOB
#define OLED_SCL_PIN     GPIO_Pin_8      /* PB8 -> OLED SCL */
#define OLED_SDA_PIN     GPIO_Pin_9      /* PB9 -> OLED SDA */
#define OLED_ADDR        0x78            /* 0x3C << 1; 不亮就试 0x7A */
```

需要**上拉电阻**（模块一般自带 4.7kΩ）。屏幕不亮先确认地址是 `0x78` 还是 `0x7A`。

---

## 项目结构

```
.
├── README.md
├── LICENSE
├── driver/                 SSD1306 驱动（复制到你的 STM32 工程里）
│   ├── oled.c              软件 I²C + 1KB 显存缓冲 + 脏页刷新
│   ├── oled.h
│   ├── delay.c
│   └── delay.h
├── tools/                  字库生成工具（在电脑上跑，不参与单片机编译）
│   ├── make_font.py        命令行字库生成器
│   ├── font_gui.py         图形化管理器
│   ├── 字库管理器.bat        双击启动 GUI
│   └── 生成字库.bat          双击跑命令行版
└── examples/
    └── main.c              在 OLED 上显示动态数值的完整示例
```

生成到工程里的两个文件：

| 文件 | 内容 |
|------|------|
| `oledfont.h` | 枚举定义 + API 声明 + `@WORDS`/`@ASCII` 元数据行 |
| `oledfont.c` | 字模数据 + 显示函数实现 |

字模数据放 `.c`、`.h` 里只 `extern`，避免每个 include 的源文件都生成一份副本。

---

## 常见问题

**Q: 编译报 `missing closing quote` 或 `invalid multibyte character sequence`**

源码里写了中文字符串，且文件编码与编译器不匹配。改用枚举调用：

```c
OLED_ShowWord(0, 0, W_WENDU);    // 而不是 OLED_ShowStr(0, 0, "温度")
```

**Q: 屏幕上什么都不显示**

漏了刷新函数。所有绘制只写内存缓冲，必须调 `OLED_Refresh()` 或 `OLED_RefreshDirty()`。

**Q: 数字上半截对、下半截是旧值**

手工刷新时只刷了一页。字符 16px 高跨两页，用 `OLED_RefreshDirty()` 让它自动处理。

**Q: 某个字显示不出来**

该字不在字库里。用 GUI 添加后重新生成，或者查 `@WORDS` 元数据行确认。

**Q: 怎么改汉字大小 / 字体**

编辑 `make_font.py`：

```python
CN_W, CN_H = 16, 16           # 尺寸（注意：改尺寸要同步改驱动）
CANDIDATE_FONTS = [ ... ]     # 字体优先级
```

**Q: 想省 Flash**

「🔤 符号设置」里只勾选实际用到的符号。只显示数字的话，ASCII 部分只占 160 字节。

---

## 依赖

**便携版**：无（已打包 Python 3.11 + tkinter + Pillow + pypinyin）

**源码运行**：

```
Python 3.8+
tkinter      (标准库，编译期选项，pip 装不了)
Pillow       pip install Pillow
pypinyin     pip install pypinyin    (可选，缺失时枚举名退化成码点)
```

汉字点阵取系统字体，按以下顺序查找：

```
C:\Windows\Fonts\simsun.ttc          (Windows 宋体，内嵌 16x16 点阵，效果最佳)
C:\Windows\Fonts\simhei.ttf
/System/Library/Fonts/PingFang.ttc   (macOS)
/usr/share/fonts/truetype/arphic/uming.ttc   (Linux)
```

---

## License

[MIT](LICENSE)
