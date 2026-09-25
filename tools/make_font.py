#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OLED 字库自动生成器 —— 打什么字就生成什么字库
================================================
用法:
    python make_font.py "周锴运 时间 正转 反转 停止 电机正常运作"
    python make_font.py "速度 占空比" --out "C:/Users/ABC/Documents/STM32/bisai/Other"
    python make_font.py "状态 异常" --preview

参数:
    <词组>      空格分隔的词, 每个词会生成一个 W_XXX 整词枚举
    --out DIR   生成后自动复制到 DIR (你的工程 Other 目录)
    --preview   额外生成 preview.png 预览效果
    --reset     清空已有字库, 只按本次输入重新生成

追加模式 (默认):
    脚本会读取 --out 目录里 oledfont.h 的 @WORDS 元数据行, 自动把已有词组
    保留下来, 再合并本次输入的新词。所以重复运行不会丢字, 直接加新词即可。
    想从零开始就加 --reset。

ASCII 字库:
    95 个可打印 ASCII (0x20~0x7E, 数字/大小写字母/常用符号) 已硬编码在脚本内,
    每次生成都会完整输出, 不会因为只输入中文而丢失。

输出:
    oledfont.h / oledfont.c   (纯 ASCII, Keil AC5 可直接编译)

字体来源:
    汉字   Windows 宋体 simsun.ttc 内嵌 16x16 点阵 (横细竖粗)
    ASCII  内置 Unifont 8x16 点阵 (硬编码, 不依赖任何外部文件)

依赖: pip install Pillow pypinyin
"""
import os
import re
import sys
import json

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("需要 Pillow:  pip install Pillow")

CN_W, CN_H = 16, 16
EN_W, EN_H = 8, 16
ASCII_FROM, ASCII_TO = 0x20, 0x7E

# ---- 内置 Unifont 8x16 ASCII 点阵 (硬编码, 自包含) ----
ASCII_HEX = [
    "00000000000000000000000000000000",  # 0x20
    "00000000F00000000000000037000000",  # 0x21
    "00003C0000003C000000000000000000",  # 0x22
    "008080F08080F000003C07043C070400",  # 0x23
    "00C02020F0202040000811113F12120C",  # 0x24
    "0060909060806010002018041B242418",  # 0x25
    "0000609010906000001C222123141826",  # 0x26
    "000000003C0000000000000000000000",  # 0x27
    "000000C0300800000000000F30400000",  # 0x28
    "00000830C0000000000040300F000000",  # 0x29
    "00800000C0000080000805021F020508",  # 0x2A
    "00000000C0000000000202021F020202",  # 0x2B
    "00000000000000000000009070000000",  # 0x2C
    "00000000000000000000020202020000",  # 0x2D
    "00000000000000000000003030000000",  # 0x2E
    "00000000804030000030080601000000",  # 0x2F
    "00C0201010A0C000000F142221100F00",  # 0x30 0
    "00004020F0000000000020203F202000",  # 0x31 1
    "006010101010E0000038242221212000",  # 0x32 2
    "006010101010E0000018202121211E00",  # 0x33 3
    "0000804020F0000000070404043F0400",  # 0x34 4
    "00F01010101010000011212121211E00",  # 0x35 5
    "00C0201010100000001F212121211E00",  # 0x36 6
    "0010101010907000000000003C030000",  # 0x37 7
    "00E010101010E000001E212121211E00",  # 0x38 8
    "00E010101010E0000000212121110F00",  # 0x39 9
    "000000C0C00000000000001818000000",  # 0x3A
    "000000C0C00000000000004838000000",  # 0x3B
    "00000000804020000000020508102000",  # 0x3C
    "00808080808080000008080808080800",  # 0x3D
    "00204080000000000020100805020000",  # 0x3E
    "006010101010E0000000000036010000",  # 0x3F
    "00C020905090E000000F102728282F00",  # 0x40
    "0080601010608000003F020202023F00",  # 0x41 A
    "00F010101010E000003F212121211E00",  # 0x42 B
    "00E0101010106000001F202020201800",  # 0x43 C
    "00F010101020C000003F202020100F00",  # 0x44 D
    "00F0101010101000003F212121212000",  # 0x45 E
    "00F0101010101000003F010101010000",  # 0x46 F
    "00E0101010106000001F202022123E00",  # 0x47 G
    "00F000000000F000003F010101013F00",  # 0x48 H
    "00001010F0101000000020203F202000",  # 0x49 I
    "0000001010F0101000182020201F0000",  # 0x4A J
    "00F0008040201000003F030408102000",  # 0x4B K
    "00F0000000000000003F202020202000",  # 0x4C L
    "00F0C00000C0F000003F000303003F00",  # 0x4D M
    "00F060800000F000003F000106183F00",  # 0x4E N
    "00E010101010E000001F202020201F00",  # 0x4F O
    "00F010101010E000003F010101010000",  # 0x50 P
    "00E010101010E000001F302828305F40",  # 0x51 Q
    "00F010101010E000003F0101030D3000",  # 0x52 R
    "00E01010101060000018212122221C00",  # 0x53 S
    "00101010F0101010000000003F000000",  # 0x54 T
    "00F000000000F000001F202020201F00",  # 0x55 U
    "00708000000080700000030C300C0300",  # 0x56 V
    "00F000000000F000003F0C03030C3F00",  # 0x57 W
    "0030C00000C0300000300C03030C3000",  # 0x58 X
    "0030C0000000C030000000013E010000",  # 0x59 Y
    "00101010109070000038242221202000",  # 0x5A Z
    "00000000F8080800000000007F404000",  # 0x5B
    "00304080000000000000000106083000",  # 0x5C
    "000808F8000000000040407F00000000",  # 0x5D
    "00100804040810000000000000000000",  # 0x5E
    "00000000000000000040404040404040",  # 0x5F
    "00000204080000000000000000000000",  # 0x60
    "0080404040408000001C222222123F00",  # 0x61 a
    "00F8804040408000003F102020201F00",  # 0x62 b
    "0080404040408000001F202020201000",  # 0x63 c
    "008040404080F800001F202020103F00",  # 0x64 d
    "0080404040408000001F222222221300",  # 0x65 e
    "008080F0888800000000003F00000000",  # 0x66 f
    "008040404080600000639C9494936000",  # 0x67 g
    "00F8804040408000003F000000003F00",  # 0x68 h
    "00000040D8000000000020203F202000",  # 0x69 i
    "0000000040D8000000408080403F0000",  # 0x6A j
    "00F8000080400000003F020508102000",  # 0x6B k
    "00000008F8000000000020203F202000",  # 0x6C l
    "00C0404080404080003F00003F00003F",  # 0x6D m
    "00C0804040408000003F000000003F00",  # 0x6E n
    "0080404040408000001F202020201F00",  # 0x6F o
    "00C080404040800000FF102020201F00",  # 0x70 p
    "008040404080C000001F20202010FF00",  # 0x71 q
    "00C0804040408000003F000000000100",  # 0x72 r
    "00804040404080000011222224241800",  # 0x73 s
    "008080F0808000000000001F20200000",  # 0x74 t
    "00C000000000C000001F202020103F00",  # 0x75 u
    "00C000000000C00000010E30300E0100",  # 0x76 v
    "00C00000800000C0001F20201F20201F",  # 0x77 w
    "00C000000000C0000030090606093000",  # 0x78 x
    "00C000000000C0000007889090887F00",  # 0x79 y
    "004040404040C0000030282422212000",  # 0x7A z
    "00000030C80800000000026598800000",  # 0x7B
    "00000000FC00000000000000FF000000",  # 0x7C
    "000008C8300000000000809865020000",  # 0x7D
    "00300808102020180000000000000000",  # 0x7E
]
# ------------------------------------------------------

CANDIDATE_FONTS = [
    (r"C:\Windows\Fonts\simsun.ttc", 0, "simsun"),      # 宋体点阵, 最佳
    (r"C:\Windows\Fonts\simhei.ttf", 0, "simhei"),      # 黑体(矢量, 兜底)
    (r"/System/Library/Fonts/PingFang.ttc", 0, "pingfang"),
    (r"/usr/share/fonts/truetype/arphic/uming.ttc", 0, "uming"),
]


def pick_font():
    for path, idx, name in CANDIDATE_FONTS:
        if os.path.exists(path):
            return path, idx, name
    return None, 0, None


def pinyin_upper(s):
    """汉字串 -> 拼音大写, 失败则回退到码点"""
    try:
        from pypinyin import lazy_pinyin
        return "".join(lazy_pinyin(s)).upper().replace(" ", "")
    except Exception:
        return "".join(f"{ord(c):04X}" for c in s)


def render_cn(ch, font_path, font_idx, font_name):
    """渲染单个汉字为 16x16 点阵"""
    f = ImageFont.truetype(font_path, CN_H, index=font_idx)
    img = Image.new("L", (48, 48), 0)
    ImageDraw.Draw(img).text((12, 12), ch, font=f, fill=255)
    bb = img.getbbox()
    if bb is None:
        return None
    g = img.crop(bb)
    canvas = Image.new("L", (CN_W, CN_H), 0)
    w = min(g.width, CN_W)
    h = min(g.height, CN_H)
    canvas.paste(g.crop((0, 0, w, h)), ((CN_W - w) // 2, (CN_H - h) // 2))
    return [[1 if canvas.getpixel((x, y)) > 127 else 0
             for x in range(CN_W)] for y in range(CN_H)]


def pack(bits, w, h):
    """纵向取模, LSB在上, 先上半后下半 (HZK16 标准)"""
    out = []
    half = h // 2
    for seg in range(2):
        for x in range(w):
            b = 0
            for r in range(half):
                if bits[seg * half + r][x]:
                    b |= (1 << r)
            out.append(b)
    return out


def hexs(arr):
    return ", ".join(f"0x{b:02X}" for b in arr)


def read_existing_words(out_dir):
    """从已有 oledfont.h 的元数据行读回词组, 实现"追加"而不是"覆盖"
       元数据格式: /* @WORDS: 5468,9534,8FD0|65F6,95F4 */  (纯 ASCII, AC5 安全)
    """
    if not out_dir:
        return []
    p = os.path.join(out_dir, "oledfont.h")
    if not os.path.exists(p):
        return []
    try:
        with open(p, encoding="utf-8", errors="ignore") as fp:
            for line in fp:
                m = re.search(r"@WORDS:\s*([0-9A-Fa-f,|]+)", line)
                if m:
                    out = []
                    for grp in m.group(1).split("|"):
                        grp = grp.strip()
                        if grp:
                            try:
                                out.append("".join(chr(int(x, 16))
                                                   for x in grp.split(",") if x))
                            except ValueError:
                                pass
                    return [w for w in out if w]
    except Exception as e:
        print("  (读取已有词表失败, 按新词处理):", e)
    return []


def read_existing_ascii(out_dir):
    """读 @ASCII 元数据行, 返回启用的字符列表
       格式: /* @ASCII: 20,21,22,2E,30,31 */  (十六进制码点, 纯 ASCII)
       没找到则返回全部 95 个可打印字符
    """
    allc = [chr(i) for i in range(ASCII_FROM, ASCII_TO + 1)]
    if not out_dir:
        return allc
    p = os.path.join(out_dir, "oledfont.h")
    if not os.path.exists(p):
        return allc
    try:
        with open(p, encoding="utf-8", errors="ignore") as fp:
            for line in fp:
                m = re.search(r"@ASCII:\s*([0-9A-Fa-f,]+)", line)
                if m:
                    out = []
                    for x in m.group(1).split(","):
                        x = x.strip()
                        if x:
                            try:
                                out.append(chr(int(x, 16)))
                            except ValueError:
                                pass
                    if out:
                        return out
    except Exception as e:
        print("  (读取 @ASCII 失败, 用全部字符):", e)
    return allc


def build(words, out_dir=None, preview=False, reset=False, ascii_chars=None):
    # ---- 追加模式: 保留目标工程里已有的词组 ----
    if not reset:
        old = read_existing_words(out_dir)
        if old:
            merged = list(words)
            for w in old:
                if w not in merged:
                    merged.append(w)
            print(f"  追加模式: 已有 {len(old)} 个词, 本次输入 {len(words)} 个, "
                  f"合并后 {len(merged)} 个   (清空重来请加 --reset)")
            words = merged

    # 收集汉字, 去重保序
    cn_chars = []
    for w in words:
        for c in w:
            if ord(c) > 0x2000 and c not in cn_chars:
                cn_chars.append(c)
    if not cn_chars:
        print("  没有汉字 -> 生成纯 ASCII 字库 (只有数字/字母/符号)")

    font_path, font_idx, font_name = pick_font()
    if font_path is None:
        sys.exit("找不到中文字体 (simsun/simhei/pingfang/uming)")
    print(f"字体: {font_name}")

    cn_data, missing = [], []
    for c in cn_chars:
        bits = render_cn(c, font_path, font_idx, font_name)
        if bits is None:
            missing.append(c)
            bits = [[0] * CN_W for _ in range(CN_H)]
        cn_data.append(pack(bits, CN_W, CN_H))
    if missing:
        print("!! 字体缺字:", "".join(missing))

    # ---- ASCII 字符集: 支持自定义启用哪些符号 ----
    if ascii_chars is None:
        ascii_chars = read_existing_ascii(out_dir)
    ascii_chars = sorted(set(c for c in ascii_chars
                             if ASCII_FROM <= ord(c) <= ASCII_TO), key=ord)
    if not ascii_chars:
        ascii_chars = [chr(i) for i in range(ASCII_FROM, ASCII_TO + 1)]
    _full = [[int(ASCII_HEX[i][j * 2:j * 2 + 2], 16) for j in range(16)]
             for i in range(ASCII_TO - ASCII_FROM + 1)]
    _sel = [ord(c) - ASCII_FROM for c in ascii_chars]
    ascii_data = [_full[i] for i in _sel]
    # 若启用的符号是连续的一段, 用 base+count 定位即可, 不需要 95 字节查找表
    _codes = sorted(ord(c) for c in ascii_chars)
    ascii_contig = (_codes == list(range(_codes[0], _codes[0] + len(_codes))))
    ascii_base = _codes[0] if ascii_contig else 0
    # 非连续时才生成索引表: 95 字节, 字符码 -> 紧凑数组下标, 0xFF 表示未启用
    ascii_idx = [0xFF] * (ASCII_TO - ASCII_FROM + 1)
    for j, i in enumerate(_sel):
        ascii_idx[i] = j
    _extra = 0 if ascii_contig else 95
    print(f"  ASCII 符号: {len(ascii_chars)} / {ASCII_TO - ASCII_FROM + 1} 个启用"
          f"  ({'连续, 无查找表' if ascii_contig else '离散, 含 95 字节查找表'})"
          f"  占用 {len(ascii_chars) * 16 + _extra} 字节")

    idx_rows = "\n".join(
        "    " + ", ".join("0x%02X" % b for b in ascii_idx[i:i + 16]) + ","
        for i in range(0, len(ascii_idx), 16))

    # 连续字符集用 base+count 定位, 不生成查找表 (省 95 字节)
    if ascii_contig:
        ascii_decl = ("#define ASCII_BASE    0x%02X\n#define ASCII_COUNT   %d"
                      % (ascii_base, len(ascii_chars)))
        idx_decl = ""
        showchar_body = "\n".join([
            "static void OLED_ShowChar(uint8_t x, uint8_t y, char c) {",
            "    uint8_t i;",
            "    if ((unsigned)c < ASCII_BASE ||",
            "        (unsigned)c >= ASCII_BASE + ASCII_COUNT) return;",
            "    i = (uint8_t)(c - ASCII_BASE);",
            "    OLED_BufMat(x, y, OLED_ASCII_8x16[i], 8);",
            "}",
        ])
    else:
        ascii_decl = ("#define ASCII_COUNT   %d\n"
                      "extern const uint8_t ASCII_IDX[95];   /* ch-0x20 -> index, 0xFF = disabled */"
                      % len(ascii_chars))
        idx_decl = ("/* ch - 0x20 -> compact index; 0xFF means that symbol is disabled */\n"
                    "const uint8_t ASCII_IDX[95] = {\n" + idx_rows + "\n};")
        showchar_body = "\n".join([
            "static void OLED_ShowChar(uint8_t x, uint8_t y, char c) {",
            "    uint8_t i;",
            "    if ((unsigned)c - 0x20 > 0x5E) return;",
            "    i = ASCII_IDX[c - 0x20];",
            "    if (i != 0xFF) OLED_BufMat(x, y, OLED_ASCII_8x16[i], 8);",
            "}",
        ])

    # 枚举名 (拼音可能撞名, 如 止/知 都是 zhi -> 自动加数字后缀)
    def uniq_names(items):
        seen, out = {}, []
        for s in items:
            base = pinyin_upper(s)
            n = seen.get(base, 0) + 1
            seen[base] = n
            out.append(base if n == 1 else f"{base}{n}")
        return out

    hz_names = uniq_names(cn_chars)
    word_names = uniq_names(words)
    dup = [n for n in hz_names if hz_names.count(n) > 1]
    if dup:
        print("!! 枚举名冲突未解决:", dup)

    print(f"汉字 {len(cn_chars)} 个: {''.join(cn_chars)}")
    print(f"词组 {len(words)} 个")

    # ---------------- 生成 .h ----------------
    # 空枚举在 C 里非法 -> 无汉字时用占位项, 并把数组长度设为 1
    if cn_chars:
        hz_enum = "\n".join(f"    HZ_{n} = 0x{ord(c):04X},   /* U+{ord(c):04X} */"
                            for c, n in zip(cn_chars, hz_names))
        hz_count = len(cn_chars)
    else:
        hz_enum = "    HZ_NONE = 0xFFFF,   /* placeholder: no Chinese */"
        hz_count = 1
    # 注释必须纯 ASCII, 否则 Keil AC5 报 invalid multibyte character sequence
    # 空枚举 / 空数组在 C 里是非法的, 所以没有内容时放一个占位项
    if words:
        word_enum = "\n".join(f"    W_{n},   /* {len(w)} chars */"
                              for w, n in zip(words, word_names))
        word_rows = "\n".join(
            "    { " + ", ".join(f"HZ_{hz_names[cn_chars.index(c)]}" for c in w) + ", 0 },"
            for w in words)
    else:
        word_enum = "    W_NONE,   /* placeholder: no words */"
        word_rows = "    { 0 },   /* placeholder: no words */"

    # 元数据行: 记录词组构成(码点) + 启用的 ASCII 符号, 供下次运行时继承
    meta = "|".join(",".join(f"{ord(c):04X}" for c in w) for w in words)
    ascii_meta = ",".join(f"{ord(c):02X}" for c in ascii_chars)

    h = f"""/**
 * @file    oledfont.h
 * @brief   Auto-generated OLED font: {len(cn_chars)} Chinese glyphs (16x16) + 95 ASCII (8x16)
 * @note    Modulo: column-major, byte-reversed (LSB = top pixel), upper 8 rows first.
 *          32 bytes/HZ, 16 bytes/ASCII. Compatible with HZK16.
 *          Generated by make_font.py - source is pure ASCII (Keil AC5 safe).
 *          CN font: {font_name}   ASCII font: Unifont
 *
 *          DO NOT EDIT the @WORDS line below - make_font.py uses it to
 *          accumulate new words on top of the existing font instead of
 *          overwriting it.  Delete the line to start from scratch.
 *
 * @WORDS: {meta}
 * @ASCII: {ascii_meta}
 */
#ifndef __OLEDFONT_H__
#define __OLEDFONT_H__

#include <stdint.h>

typedef enum {{
{hz_enum}
}} HZCode;

typedef enum {{
{word_enum}
}} WordID;

typedef struct {{
    const char     utf8[4];     /* UTF-8 bytes + NUL */
    const uint8_t  mat[32];     /* 16x16 bitmap */
}} HZItem;

#define HZLIB_COUNT   {hz_count}
{ascii_decl}

/* Font data is DEFINED in oledfont.c so only ONE copy lands in Flash */
extern const uint8_t OLED_ASCII_8x16[ASCII_COUNT][16];
extern const HZItem  HzLib[HZLIB_COUNT];

/* NOTE: all of the following draw into the GRAM buffer.
 *       Call OLED_Refresh() to push the whole screen, or
 *       OLED_RefreshPage(y) / OLED_RefreshPages(y0,y1) for partial updates. */

void OLED_ShowHz  (uint8_t x, uint8_t y, uint16_t code);  /* one glyph, HZ_XXX  */
void OLED_ShowWord(uint8_t x, uint8_t y, WordID w);       /* whole word, W_XXX */
void OLED_ShowStr (uint8_t x, uint8_t y, const char *s);  /* ASCII + UTF-8 mix */

/* old names kept as aliases so existing code still compiles */
#define OLED_ShowString  OLED_ShowStr
#define OLED_ShowHzStr   OLED_ShowStr

/* numbers - width is the number of 8px digit cells */
void OLED_ShowNum    (uint8_t x, uint8_t y, uint32_t num, uint8_t width);
void OLED_ShowFloat1 (uint8_t x, uint8_t y, uint32_t scaled10, uint8_t width);
void OLED_ShowSigned (uint8_t x, uint8_t y, int32_t num, uint8_t width);

#endif
"""

    # ---------------- 生成 .c ----------------
    def _lbl(c):
        return c if (c.isalnum() and c.isascii()) else ""

    # 注意: 这里是普通字符串不是 f-string, "}" 就是一个右括号, 不要写 "}}"
    ascii_rows = "\n".join(
        "    { " + hexs(ascii_data[i])
        + " },   /* 0x%02X %s */" % (ord(ascii_chars[i]), _lbl(ascii_chars[i]))
        for i in range(len(ascii_data)))

    if cn_chars:
        hz_rows = "\n".join(
            "    { { " + hexs(list(c.encode("utf-8")) + [0]) + " }, { " +
            hexs(cn_data[i]) + " } },   /* U+%04X */" % ord(c)
            for i, c in enumerate(cn_chars))
    else:
        hz_rows = ("    { { 0x00, 0x00, 0x00, 0x00 }, { "
                   + ", ".join(["0x00"] * 32)
                   + " } },   /* placeholder: no Chinese */")

    c = f"""/**
 * @file    oledfont.c  Auto-generated by make_font.py
 */
#include "oledfont.h"
#include "oled.h"

const uint8_t OLED_ASCII_8x16[ASCII_COUNT][16] = {{
{ascii_rows}
}};

{idx_decl}

const HZItem HzLib[HZLIB_COUNT] = {{
{hz_rows}
}};

static const uint16_t Words[][8] = {{
{word_rows}
}};

/* ---- glyph lookup: Unicode code point -> bitmap ---- */
static const uint8_t *HzFind(uint16_t cp) {{
    uint8_t b1, b2, b3;
    if (cp < 0x800) return 0;
    b1 = 0xE0 | ((cp >> 12) & 0x0F);
    b2 = 0x80 | ((cp >>  6) & 0x3F);
    b3 = 0x80 |  (cp        & 0x3F);
    for (uint16_t i = 0; i < HZLIB_COUNT; i++)
        if ((uint8_t)HzLib[i].utf8[0] == b1 &&
            (uint8_t)HzLib[i].utf8[1] == b2 &&
            (uint8_t)HzLib[i].utf8[2] == b3) return HzLib[i].mat;
    return 0;
}}

{showchar_body}

/* ---- public API (all draw into the GRAM buffer, then OLED_Refresh) ---- */

void OLED_ShowHz(uint8_t x, uint8_t y, uint16_t code) {{
    const uint8_t *m = HzFind(code);
    if (m && x <= 111 && y <= 6) OLED_BufMat(x, y, m, 16);
}}

void OLED_ShowWord(uint8_t x, uint8_t y, WordID w) {{
    const uint16_t *p = Words[w];
    while (*p && x < 128) {{ OLED_ShowHz(x, y, *p++); x += 16; }}
}}

/** ASCII + UTF-8 mixed string */
void OLED_ShowStr(uint8_t x, uint8_t y, const char *s) {{
    while (*s && x < 128) {{
        uint8_t b = (uint8_t)*s;
        if (b >= 0xE0 && b <= 0xEF && s[1] && s[2]) {{          /* 3-byte UTF-8 */
            OLED_ShowHz(x, y, ((b & 0x0F) << 12) | ((s[1] & 0x3F) << 6) | (s[2] & 0x3F));
            x += 16; s += 3;
        }} else if (b < 0x80) {{                                 /* ASCII */
            OLED_ShowChar(x, y, *s); x += 8; s++;
        }} else s++;                                             /* skip bad byte */
    }}
}}

/* ---------------- numbers (for live values: rpm, duty, etc.) ---------------- */

/** Right-aligned unsigned number, width = number of digit cells (8px each).
 *  Left-pads with spaces so old digits get erased. */
void OLED_ShowNum(uint8_t x, uint8_t y, uint32_t num, uint8_t width) {{
    for (uint8_t i = 0; i < width; i++) {{
        uint8_t cell = width - 1 - i;
        char c = (num > 0 || i == 0) ? (char)('0' + num % 10) : ' ';
        if (num == 0 && i > 0) c = ' ';
        OLED_ShowChar(x + cell * 8, y, c);
        num /= 10;
    }}
}}

/** Fixed-point number with 1 decimal, e.g. 505 -> "50.5". width = total cells. */
void OLED_ShowFloat1(uint8_t x, uint8_t y, uint32_t scaled10, uint8_t width) {{
    /* scaled10 = value * 10  (505 means 50.5) */
    uint8_t intw = (width >= 3) ? (uint8_t)(width - 2) : 1;
    OLED_ShowNum(x, y, scaled10 / 10, intw);
    OLED_ShowChar(x + intw * 8, y, '.');
    OLED_ShowChar(x + (intw + 1) * 8, y, (char)('0' + scaled10 % 10));
}}

/** Signed number with a leading +/- sign. width = digit cells (sign is extra). */
void OLED_ShowSigned(uint8_t x, uint8_t y, int32_t num, uint8_t width) {{
    if (num < 0) {{
        OLED_ShowChar(x, y, '-');
        OLED_ShowNum(x + 8, y, (uint32_t)(-num), width);
    }} else {{
        OLED_ShowChar(x, y, '+');
        OLED_ShowNum(x + 8, y, (uint32_t)num, width);
    }}
}}
"""

    here = os.path.dirname(os.path.abspath(__file__))
    for name, content in (("oledfont.h", h), ("oledfont.c", c)):
        p = os.path.join(here, name)
        with open(p, "w", encoding="utf-8") as fp:
            fp.write(content)
        bad = sum(1 for line in content.splitlines() if any(ord(ch) > 127 for ch in line))
        # 自检: 花括号必须平衡 (注释里不含花括号, 所以直接数即可)
        ob, cb = content.count("{"), content.count("}")
        flag = "OK" if ob == cb else f"!! 括号不平衡 {ob} vs {cb}"
        print(f"  {name}: {len(content)} bytes, 非ASCII行={bad}, 花括号 {ob}/{cb} {flag}")

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        for name in ("oledfont.h", "oledfont.c"):
            src = os.path.join(here, name)
            dst = os.path.join(out_dir, name)
            with open(src, "rb") as a, open(dst, "wb") as b:
                b.write(a.read())
        print(f"  已复制到 {out_dir}")

    if preview:
        img = Image.new("1", (128, 16 * len(words) + 16), 0)
        d = ImageDraw.Draw(img)
        for i, w in enumerate(words):
            x = 0
            for ch in w:
                if ch in cn_chars:
                    m = cn_data[cn_chars.index(ch)]
                    for seg in range(2):
                        for col in range(16):
                            b = m[seg * 16 + col]
                            for r in range(8):
                                if b & (1 << r):
                                    d.point((x + col, i * 16 + seg * 8 + r), fill=1)
                    x += 16
        img.resize((img.width * 4, img.height * 4), Image.NEAREST).save(
            os.path.join(here, "preview.png"))
        print("  preview.png")

    print("\n词表枚举:")
    for w, n in zip(words, word_names):
        print(f"    W_{n:<28} /* {w} */")
    print("\n完成。在代码里: OLED_ShowWord(x, y, W_XXX);")


def main():
    args = sys.argv[1:]
    out_dir = None
    preview = False
    reset = False
    words = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--out":
            i += 1
            out_dir = args[i]
        elif a == "--preview":
            preview = True
        elif a == "--reset":
            reset = True
        else:
            words.extend(a.split())
        i += 1

    if not words and not reset:
        print(__doc__)
        sys.exit(1)
    build(words, out_dir, preview, reset)


if __name__ == "__main__":
    main()
