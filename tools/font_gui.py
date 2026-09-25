# -*- coding: utf-8 -*-
"""
字库图形化管理器
================
- 列出 oledfont.c 里所有字模, 每个右侧有 ✕ 可删除
- 输入框可添加新字/新词
- 点"生成字库"写回 oledfont.h / oledfont.c

启动: 双击 字库管理器.bat  或  python font_gui.py
"""
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox

# 打包成 exe 后 __file__ 指向临时解压目录, 要用 exe 自身所在目录
if getattr(sys, "frozen", False):
    HERE = os.path.dirname(os.path.abspath(sys.executable))
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_font  # noqa: E402

MAT = 16          # 点阵 16x16
CELL = 4          # 预览放大倍数 -> 64x64
UI_FONT = ("Microsoft YaHei UI", 10)
GLYPH_FONT = ("Microsoft YaHei UI", 13, "bold")


# ---------------- 文件解析 ----------------
PROJECT_OTHER = r"C:\Users\ABC\Documents\STM32\bisai\Other"


def find_target():
    """定位含 oledfont.h 的目录, 找不到返回 None (调用方让用户手动选)"""
    cands = [
        PROJECT_OTHER,                           # 开发机已知工程 (别的电脑上不存在, 自动跳过)
        os.path.join(HERE, "Other"),             # exe 旁边的 Other/
        os.path.join(os.getcwd(), "Other"),
        HERE,                                    # exe 同目录
        os.getcwd(),
    ]
    for d in cands:
        if d and os.path.exists(os.path.join(d, "oledfont.h")):
            return d
    return None


def parse_hzlib(c_path):
    """从 oledfont.c 解析 {字符: 32字节字模}
       兼容两种 HZItem 布局:
         旧: utf8[4] + gbk[2] + mat[32] = 38 字节
         新: utf8[4] + mat[32]          = 36 字节
    """
    out = {}
    if not os.path.exists(c_path):
        return out
    with open(c_path, encoding="utf-8", errors="ignore") as fp:
        for line in fp:
            if "U+" not in line:
                continue
            hexs = re.findall(r"0x([0-9A-Fa-f]{2})", line)
            b = [int(h, 16) for h in hexs]
            if len(b) >= 38:            # 旧布局
                mat = b[6:38]
            elif len(b) >= 36:          # 新布局
                mat = b[4:36]
            else:
                continue
            try:
                ch = bytes(b[0:3]).decode("utf-8")
            except Exception:
                continue
            out[ch] = mat
    return out


def parse_words(h_path):
    """从 oledfont.h 的 @WORDS 元数据行恢复词组"""
    if not os.path.exists(h_path):
        return []
    with open(h_path, encoding="utf-8", errors="ignore") as fp:
        for line in fp:
            m = re.search(r"@WORDS:\s*([0-9A-Fa-f,|]+)", line)
            if m:
                res = []
                for grp in m.group(1).split("|"):
                    grp = grp.strip()
                    if grp:
                        try:
                            res.append("".join(chr(int(x, 16))
                                               for x in grp.split(",") if x))
                        except ValueError:
                            pass
                return [w for w in res if w]
    return []


ASCII_GROUPS = [
    ("数字", [chr(i) for i in range(0x30, 0x3A)]),
    ("大写字母", [chr(i) for i in range(0x41, 0x5B)]),
    ("小写字母", [chr(i) for i in range(0x61, 0x7B)]),
    ("标点符号", [chr(i) for i in range(0x20, 0x30)]
                + [chr(i) for i in range(0x3A, 0x41)]
                + [chr(i) for i in range(0x5B, 0x61)]
                + [chr(i) for i in range(0x7B, 0x7F)]),
]
ASCII_ALL = [c for _, cs in ASCII_GROUPS for c in cs]


def parse_ascii(h_path):
    """读 @ASCII 元数据行, 返回启用的符号; 无则返回全部 95 个"""
    if os.path.exists(h_path):
        try:
            with open(h_path, encoding="utf-8", errors="ignore") as fp:
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
        except Exception:
            pass
    return list(ASCII_ALL)


def parse_enum_names(h_path):
    """从 oledfont.h 解析枚举名
       返回 (hz_names: {码点: 'ZHOU'}, w_names: ['ZHOUKAIYUN', ...] 按词序)
    """
    hz, ws = {}, []
    if not os.path.exists(h_path):
        return hz, ws
    txt = open(h_path, encoding="utf-8", errors="ignore").read()
    mh = re.search(r"typedef enum\s*\{(.*?)\}\s*HZCode;", txt, re.S)
    if mh:
        for m in re.finditer(r"HZ_([A-Z0-9]+)\s*=\s*0x([0-9A-Fa-f]{4})", mh.group(1)):
            hz[int(m.group(2), 16)] = m.group(1)
    mw = re.search(r"typedef enum\s*\{(.*?)\}\s*WordID;", txt, re.S)
    if mw:
        ws = re.findall(r"W_([A-Z0-9]+)\s*,", mw.group(1))
    return hz, ws


def mat_to_bits(mat):
    """纵向取模(LSB在上,先上后下) -> bits[y][x]"""
    bits = [[0] * MAT for _ in range(MAT)]
    for seg in range(2):
        for x in range(MAT):
            b = mat[seg * MAT + x]
            for r in range(8):
                if b & (1 << r):
                    bits[seg * 8 + r][x] = 1
    return bits


# ---------------- 主界面 ----------------
class FontGUI:
    def __init__(self, root, target):
        self.root = root
        self.target = target
        self.h_path = os.path.join(target, "oledfont.h")
        self.c_path = os.path.join(target, "oledfont.c")
        self.words = []
        self.glyphs = {}
        self.hz_names = {}
        self.w_names = []
        self.ascii_chars = list(ASCII_ALL)
        self.font = make_font.pick_font()

        root.title("OLED 字库管理器")
        root.geometry("860x680")
        root.configure(bg="#f5f5f5")
        self._build_ui()
        self.reload()

    # ---------- 界面骨架 ----------
    def _build_ui(self):
        top = tk.Frame(self.root, bg="#f5f5f5")
        top.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(top, text="字库目录:", font=UI_FONT, bg="#f5f5f5").pack(side="left")
        self.path_lbl = tk.Label(top, text=self.target, font=("Consolas", 9),
                                 fg="#0a6", bg="#f5f5f5")
        self.path_lbl.pack(side="left", padx=6)
        tk.Button(top, text="重新加载", font=UI_FONT, command=self.reload
                  ).pack(side="right")
        tk.Button(top, text="选择目录", font=UI_FONT, command=self.on_pick_dir
                  ).pack(side="right", padx=6)
        tk.Button(top, text="📂 打开目录", font=UI_FONT, bg="#e8f4ff",
                  command=self.on_open_dir).pack(side="right", padx=(0, 6))

        add = tk.Frame(self.root, bg="#f5f5f5")
        add.pack(fill="x", padx=12, pady=4)
        tk.Label(add, text="添加:", font=UI_FONT, bg="#f5f5f5").pack(side="left")
        self.entry = tk.Entry(add, font=UI_FONT, width=46)
        self.entry.pack(side="left", padx=6, ipady=3)
        self.entry.bind("<Return>", lambda e: self.on_add())
        tk.Button(add, text="＋ 添加", font=UI_FONT, bg="#e8f4ff",
                  command=self.on_add).pack(side="left")
        tk.Label(add, text="(空格分词, 例: 温度 报警)", font=("Microsoft YaHei UI", 9),
                 fg="#888", bg="#f5f5f5").pack(side="left", padx=8)

        self.info = tk.Label(self.root, text="", font=UI_FONT, bg="#f5f5f5", anchor="w")
        self.info.pack(fill="x", padx=14, pady=(2, 0))

        # 滚动区
        wrap = tk.Frame(self.root, bg="#fff", bd=1, relief="solid")
        wrap.pack(fill="both", expand=True, padx=12, pady=6)
        self.canvas = tk.Canvas(wrap, bg="#fff", highlightthickness=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.grid_frame = tk.Frame(self.canvas, bg="#fff")
        self.grid_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))

        # 词表显示
        self.words_lbl = tk.Label(self.root, text="", font=("Microsoft YaHei UI", 9),
                                  bg="#f5f5f5", fg="#555", anchor="w",
                                  justify="left", wraplength=820)
        self.words_lbl.pack(fill="x", padx=14, pady=(2, 4))

        bot = tk.Frame(self.root, bg="#f5f5f5")
        bot.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(bot, text="💾 生成字库", font=("Microsoft YaHei UI", 11, "bold"),
                  bg="#d9f0d9", padx=16, pady=5, command=self.on_generate
                  ).pack(side="left")
        tk.Button(bot, text="清空全部", font=UI_FONT, command=self.on_clear
                  ).pack(side="left", padx=10)
        tk.Button(bot, text="📂 打开目录", font=UI_FONT,
                  command=self.on_open_dir).pack(side="left", padx=(6, 0))
        tk.Button(bot, text="🔤 符号设置", font=UI_FONT, bg="#e8f0ff",
                  command=self.on_symbols).pack(side="left", padx=(6, 0))
        tk.Button(bot, text="📖 语法规则", font=UI_FONT, bg="#e8f0ff",
                  command=self.on_show_syntax).pack(side="left", padx=(6, 0))
        self.status = tk.Label(bot, text="", font=UI_FONT, bg="#f5f5f5", fg="#080")
        self.status.pack(side="left", padx=12)

    # ---------- 数据 ----------
    def chars(self):
        seen = []
        for w in self.words:
            for c in w:
                if c not in seen:
                    seen.append(c)
        return seen

    def reload(self):
        self.words = parse_words(self.h_path)
        self.glyphs = parse_hzlib(self.c_path)
        self.hz_names, self.w_names = parse_enum_names(self.h_path)
        self.ascii_chars = parse_ascii(self.h_path)
        self.refresh()

    def refresh(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()

        cs = self.chars()
        self.info.config(text=f"汉字 {len(cs)} 个   词组 {len(self.words)} 个")

        w = self.canvas.winfo_width()
        if w < 200:                     # window not laid out yet
            w = 820
        cols = max(1, w // 84)
        for i, ch in enumerate(cs):
            self._make_card(ch, i // cols, i % cols)

        self.words_lbl.config(
            text="词组: " + ("  ".join(self.words) if self.words else "(空)"))
        self.grid_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _make_card(self, ch, r, c):
        card = tk.Frame(self.grid_frame, bg="#fafafa", bd=1, relief="solid")
        card.grid(row=r, column=c, padx=3, pady=3)

        cv = tk.Canvas(card, width=MAT * CELL, height=MAT * CELL,
                       bg="#111", highlightthickness=0, cursor="hand2")
        cv.pack(padx=4, pady=(4, 0))
        cv.bind("<Button-1>", lambda e, c=ch: self.on_glyph_click(c))
        mat = self.glyphs.get(ch)
        if mat:
            bits = mat_to_bits(mat)
            for y in range(MAT):
                for x in range(MAT):
                    if bits[y][x]:
                        cv.create_rectangle(x * CELL, y * CELL,
                                            x * CELL + CELL, y * CELL + CELL,
                                            fill="#7fd6ff", outline="")
        else:
            cv.create_text(MAT * CELL // 2, MAT * CELL // 2, text="未生成",
                           fill="#666", font=("Microsoft YaHei UI", 8))

        tk.Label(card, text=ch, font=GLYPH_FONT, bg="#fafafa").pack()

        tk.Button(card, text="✕", font=("Microsoft YaHei UI", 9),
                  fg="#c00", bg="#fafafa", bd=0, activebackground="#ffdddd",
                  cursor="hand2",
                  command=lambda c=ch: self.on_delete(c)).pack(pady=(0, 3))

    # ---------- 点击字形 -> 显示调用代码 ----------
    def on_glyph_click(self, ch):
        hz = self.hz_names.get(ord(ch))
        lines = []
        if hz:
            lines.append(f"OLED_ShowHz(0, 0, HZ_{hz});          /* {ch} */")
        else:
            lines.append(f"/* 未在 oledfont.h 找到 {ch} 的枚举, 请先生成字库 */")

        hits = [(w, n) for w, n in zip(self.words, self.w_names) if ch in w]
        if hits:
            lines.append("")
            lines.append("/* 包含该字的词组 */")
            for w, n in hits:
                lines.append(f"OLED_ShowWord(0, 0, W_{n});"
                             + " " * max(1, 22 - len(n)) + f"/* {w} */")
        self._show_code(ch, "\n".join(lines))

    def _show_code(self, ch, code):
        win = tk.Toplevel(self.root)
        win.title(f"调用代码  -  {ch}")
        win.geometry("560x330")
        win.configure(bg="#f5f5f5")
        win.transient(self.root)

        top = tk.Frame(win, bg="#f5f5f5")
        top.pack(pady=10)
        cv = tk.Canvas(top, width=MAT * 6, height=MAT * 6, bg="#111",
                       highlightthickness=0)
        cv.pack(side="left", padx=12)
        mat = self.glyphs.get(ch)
        if mat:
            bits = mat_to_bits(mat)
            for y in range(MAT):
                for x in range(MAT):
                    if bits[y][x]:
                        cv.create_rectangle(x * 6, y * 6, x * 6 + 6, y * 6 + 6,
                                            fill="#7fd6ff", outline="")
        tk.Label(top, text=ch, font=("Microsoft YaHei UI", 30, "bold"),
                 bg="#f5f5f5").pack(side="left", padx=12)

        txt = tk.Text(win, font=("Consolas", 10), height=8, wrap="none",
                      bg="#fff", bd=1, relief="solid")
        txt.pack(fill="both", expand=True, padx=12)
        txt.insert("1.0", code)
        txt.configure(state="disabled")

        bar = tk.Frame(win, bg="#f5f5f5")
        bar.pack(fill="x", pady=10)
        btn = tk.Button(bar, text="复制代码", font=UI_FONT, bg="#d9f0d9", padx=16)

        def copy():
            win.clipboard_clear()
            win.clipboard_append(code)
            btn.config(text="已复制 ✓")
            win.after(1200, lambda: btn.config(text="复制代码"))

        btn.config(command=copy)
        btn.pack(side="left", padx=(12, 8))
        tk.Button(bar, text="关闭", font=UI_FONT, padx=16,
                  command=win.destroy).pack(side="left")

    # ---------- 打开字库目录 ----------
    def on_open_dir(self):
        try:
            os.startfile(self.target)          # Windows
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", self.target])
        except Exception as e:
            messagebox.showerror("打不开", str(e))

    # ---------- 符号设置 ----------
    def on_symbols(self):
        win = tk.Toplevel(self.root)
        win.title("可显示符号设置")
        win.geometry("880x500")
        win.configure(bg="#f5f5f5")
        win.transient(self.root)

        cur = set(self.ascii_chars)
        vars_ = {}

        info = tk.Label(win, text="", font=UI_FONT, bg="#f5f5f5", fg="#06c")

        def update_info():
            n = sum(1 for v in vars_.values() if v.get())
            info.config(text="已启用 %d / %d 个符号      Flash 占用 %d 字节"
                             % (n, len(ASCII_ALL), n * 16 + 95))

        body = tk.Frame(win, bg="#f5f5f5")
        body.pack(fill="both", expand=True, padx=14, pady=(12, 4))
        for gname, chars in ASCII_GROUPS:
            row = tk.Frame(body, bg="#f5f5f5")
            row.pack(fill="x", pady=3, anchor="w")
            tk.Label(row, text="%s (%d)" % (gname, len(chars)), font=UI_FONT,
                     width=11, anchor="w", bg="#f5f5f5").pack(side="left")
            grid = tk.Frame(row, bg="#f5f5f5")
            grid.pack(side="left")
            for i, c in enumerate(chars):
                v = tk.BooleanVar(value=c in cur)
                vars_[c] = v
                tk.Checkbutton(grid, text=("SP" if c == " " else c), variable=v,
                               font=("Consolas", 10), bg="#f5f5f5",
                               activebackground="#f5f5f5", width=3,
                               command=update_info).grid(row=0, column=i)

        info.pack(pady=6)
        tk.Label(win, text="取消勾选的符号将无法显示 (Flash 也会相应减少)",
                 font=("Microsoft YaHei UI", 9), fg="#888",
                 bg="#f5f5f5").pack()

        def set_sel(chars):
            for c, v in vars_.items():
                v.set(c in chars)
            update_info()

        bar = tk.Frame(win, bg="#f5f5f5")
        bar.pack(fill="x", pady=12, padx=14)
        presets = [
            ("全选", ASCII_ALL),
            ("只要数字", ASCII_GROUPS[0][1]),
            ("数字+字母", ASCII_GROUPS[0][1] + ASCII_GROUPS[1][1] + ASCII_GROUPS[2][1]),
            ("数字+常用符号", ASCII_GROUPS[0][1] + list(".:%+-/= ")),
        ]
        for text, sel in presets:
            tk.Button(bar, text=text, font=UI_FONT,
                      command=lambda s=sel: set_sel(s)).pack(side="left", padx=3)

        def save():
            sel = [c for c, v in vars_.items() if v.get()]
            if not sel:
                messagebox.showwarning("提示", "至少要保留一个符号")
                return
            self.ascii_chars = sorted(sel, key=ord)
            win.destroy()
            self.on_generate()

        tk.Button(bar, text="保存并生成", font=("Microsoft YaHei UI", 10, "bold"),
                  bg="#d9f0d9", padx=14, command=save).pack(side="right", padx=3)
        tk.Button(bar, text="取消", font=UI_FONT, padx=14,
                  command=win.destroy).pack(side="right", padx=3)

        update_info()

    # ---------- 语法规则 ----------
    def on_show_syntax(self):
        self._show_text_window("OLED 字库语法规则", self._syntax_text(),
                               w=780, h=620)

    def _syntax_text(self):
        cs = self.chars()
        L = []
        A = L.append
        bar = "=" * 64
        sep = "-" * 64

        A(bar)
        A("  OLED 字库语法规则")
        A(bar)
        A("字库目录: " + self.target)
        A("当前内容: %d 汉字 / %d 词组" % (len(cs), len(self.words)))
        A("")

        A(sep); A("【一】坐标规则"); A(sep)
        A("  x = 像素列, 范围 0 ~ 127")
        A("  y = 页号,   范围 0 ~ 7    (每页 = 8 像素行)")
        A("")
        A("  汉字宽 16px, ASCII 宽 8px")
        A("  字符高 16px = 跨两页, 所以 y 最大只能到 6")
        A("")
        A("  y 与像素行的对应:")
        A("      y=0 -> 第 0 行      y=4 -> 第 32 行")
        A("      y=1 -> 第 8 行      y=5 -> 第 40 行")
        A("      y=2 -> 第 16 行     y=6 -> 第 48 行")
        A("      y=3 -> 第 24 行     y=7 -> 第 56 行 (下半页越界)")
        A("")

        A(sep); A("【二】显示函数 (全部 7 个)"); A(sep)
        A("  OLED_ShowHz    (x, y, HZ_XXX)            单个汉字  HZCode 枚举")
        A("  OLED_ShowWord  (x, y, W_XXX)             整词      WordID 枚举")
        A('  OLED_ShowStr   (x, y, "ABC123")          ASCII + UTF-8 混合')
        A("  OLED_ShowNum   (x, y, num, width)        无符号数字")
        A("  OLED_ShowFloat1(x, y, scaled10, width)   一位小数  505 -> 50.5")
        A("  OLED_ShowSigned(x, y, num, width)        带 +/- 符号")
        A("")
        A("  旧名字保留为宏别名, 老代码不用改:")
        A("      OLED_ShowString  =  OLED_ShowStr")
        A("      OLED_ShowHzStr   =  OLED_ShowStr")
        A("")
        A("  常见错误:")
        A('      OLED_ShowWord(0, 0, "PWM")   <- 字符串不能传给 WordID')
        A('      OLED_ShowStr (0, 0, "PWM")   <- 应该用这个')
        A("      OLED_ShowWord(0, 0, W_SHI)   <- 单字别用 W_XXX, 词表里没有")
        A("")

        A(sep); A("【三】数字 width 参数"); A(sep)
        A("  width = 占几个字符位 (每位 8px):")
        A('      num=7    width=3  ->  "  7"')
        A('      num=50   width=3  ->  " 50"')
        A('      num=100  width=3  ->  "100"')
        A('      num=1000 width=3  ->  "000"    <- 溢出, 只显示低 3 位')
        A("")

        A(sep); A("【四】刷新 (画完必须调, 否则屏幕不显示)"); A(sep)
        A("  OLED_Refresh()              整屏推屏")
        A("  OLED_RefreshDirty()         只推被改动的页   <-- 主循环用这个")
        A("  OLED_RefreshPage(p)         推指定一页")
        A("  OLED_RefreshPages(a, b)     推连续多页")
        A("  OLED_RefreshArea(x,y,w,h)   推像素区域")
        A("")
        A("  所有 OLED_ShowXxx 先写 1KB 内存缓冲, 不直接写屏。")
        A("  忘记调刷新函数 = 屏幕全黑。")
        A("")
        A("  手工刷页要注意字符跨两页, 得刷 y 和 y+1:")
        A("      错: OLED_RefreshPage(2)      数字下半截留在旧值")
        A("      对: OLED_RefreshDirty()     自动处理")
        A("")

        A(sep); A("【五】缓冲区与绘图"); A(sep)
        A("  OLED_BufClear()              只清内存缓冲")
        A("  OLED_Clear()                 清缓冲 + 清屏")
        A("  OLED_DrawPoint(x, y, on)     画点 (on: 1=亮, 0=灭)")
        A("  OLED_DrawHLine(x, y, w)      画横线")
        A("")

        A(sep); A("【六】典型用法"); A(sep)
        A("  /* 静态部分: 画一次 */")
        A("  OLED_ShowWord(0, 0, W_ZHUANSU);")
        A('  OLED_ShowStr (48, 0, ":");')
        A("  OLED_Refresh();")
        A("")
        A("  /* 动态部分: 只重画变化的数字 */")
        A("  while (1) {")
        A("      OLED_ShowNum(56, 0, rpm, 5);")
        A("      OLED_RefreshDirty();")
        A("      delay_ms(100);")
        A("  }")
        A("")

        A(sep); A("【七】本字库可用枚举"); A(sep)
        A("  HZ_XXX (单个汉字):")
        hz = [("HZ_" + self.hz_names[ord(c)]) for c in cs if ord(c) in self.hz_names]
        if hz:
            for i in range(0, len(hz), 5):
                A("      " + "  ".join("%-12s" % x for x in hz[i:i + 5]))
        else:
            A("      (无, 当前是纯 ASCII 字库)")
        A("")
        A("  W_XXX (整词):")
        if self.words:
            for w, n in zip(self.words, self.w_names):
                A("      %-26s /* %s */" % ("W_" + n, w))
        else:
            A("      (无)")
        A("")
        A("  ASCII 符号: %d / 95 个已启用" % len(self.ascii_chars))
        A("")
        A(sep); A("【八】已删除的冗余函数 (老版本有)"); A(sep)
        A("  OLED_ShowCH       -> 用 OLED_ShowHz")
        A("  OLED_ShowStrGBK   -> 用 OLED_ShowStr")
        A("  OLED_ShowHzStr    -> 用 OLED_ShowStr (保留宏别名)")
        A("  OLED_ShowString   -> 用 OLED_ShowStr (保留宏别名)")
        A("")
        A(bar)
        return "\n".join(L)

    def _show_text_window(self, title, text, w=760, h=560):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("%dx%d" % (w, h))
        win.configure(bg="#f5f5f5")
        win.transient(self.root)

        frame = tk.Frame(win, bg="#f5f5f5")
        frame.pack(fill="both", expand=True, padx=12, pady=10)
        txt = tk.Text(frame, font=("Consolas", 10), wrap="none",
                      bg="#fff", bd=1, relief="solid")
        sb = tk.Scrollbar(frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        txt.insert("1.0", text)
        txt.configure(state="disabled")

        bar = tk.Frame(win, bg="#f5f5f5")
        bar.pack(fill="x", pady=(0, 10))
        btn = tk.Button(bar, text="复制全部", font=UI_FONT, bg="#d9f0d9", padx=16)

        def copy():
            win.clipboard_clear()
            win.clipboard_append(text)
            btn.config(text="已复制 ✓")
            win.after(1200, lambda: btn.config(text="复制全部"))

        btn.config(command=copy)
        btn.pack(side="left", padx=(12, 8))
        tk.Button(bar, text="关闭", font=UI_FONT, padx=16,
                  command=win.destroy).pack(side="left")

    # ---------- 操作 ----------
    def on_delete(self, ch):
        hit = [w for w in self.words if ch in w]
        if hit and not messagebox.askyesno(
                "确认删除",
                f"删除「{ch}」会同时移除包含它的 {len(hit)} 个词组:\n"
                f"{'  '.join(hit)}\n\n继续?"):
            return
        self.words = [w for w in self.words if ch not in w]
        self.glyphs.pop(ch, None)
        self.refresh()
        self.status.config(text=f"已删除 {ch}", fg="#c60")

    def on_add(self):
        text = self.entry.get().strip()
        if not text:
            return
        new_words = [w for w in text.split() if w]
        added = []
        for w in new_words:
            if w not in self.words:
                self.words.append(w)
                added.append(w)
        self.entry.delete(0, "end")

        # 为新字生成预览点阵(不写文件)
        if self.font[0]:
            fp, fi, fn = self.font
            for ch in self.chars():
                if ch not in self.glyphs:
                    bits = make_font.render_cn(ch, fp, fi, fn)
                    if bits:
                        self.glyphs[ch] = make_font.pack(bits, MAT, MAT)
        self.refresh()
        self.status.config(
            text=f"已添加 {len(added)} 个词" if added else "词已存在",
            fg="#080" if added else "#c60")

    def on_clear(self):
        if self.words and messagebox.askyesno("确认", "清空全部字模和词组?"):
            self.words = []
            self.glyphs = {}
            self.refresh()
            self.status.config(text="已清空(未写入文件)", fg="#c60")

    def on_generate(self):
        if not self.words and not self.ascii_chars:
            messagebox.showwarning("提示", "字库是空的 (既没有汉字也没有符号)")
            return
        import io
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf          # build() prints a lot; swallow it
        try:
            make_font.build(self.words, self.target, False, True, self.ascii_chars)
        except Exception as e:
            sys.stdout = old
            messagebox.showerror("生成失败", f"{e}\n\n{buf.getvalue()}")
            return
        finally:
            sys.stdout = old
        self.reload()
        self.status.config(
            text=f"✓ 已生成 {len(self.chars())} 字 / {len(self.words)} 词", fg="#080")
        messagebox.showinfo("完成",
                            f"已写入:\n{self.h_path}\n{self.c_path}\n\n"
                            f"记得在 EIDE 里 Reload + Rebuild")

    def on_open_dir(self):
        """用系统文件管理器打开当前字库目录"""
        p = os.path.abspath(self.target)
        if not os.path.isdir(p):
            messagebox.showwarning("提示", "目录不存在:\n" + p)
            return
        try:
            if sys.platform == "win32":
                os.startfile(p)                       # 资源管理器
            elif sys.platform == "darwin":
                subprocess.Popen(["open", p])         # Finder
            else:
                subprocess.Popen(["xdg-open", p])     # Linux
        except Exception as e:
            messagebox.showerror("打开失败", "%s\n\n路径: %s" % (e, p))

    def on_pick_dir(self):
        from tkinter import filedialog
        d = filedialog.askdirectory(title="选择含 oledfont.h 的目录",
                                    initialdir=self.target)
        if not d:
            return
        if not os.path.exists(os.path.join(d, "oledfont.h")):
            if not messagebox.askyesno("提示",
                                       "该目录没有 oledfont.h, 仍要使用?\n"
                                       "(首次生成会新建)"):
                return
        self.target = d
        self.h_path = os.path.join(d, "oledfont.h")
        self.c_path = os.path.join(d, "oledfont.c")
        self.path_lbl.config(text=d)
        self.reload()


def main():
    root = tk.Tk()
    target = find_target()

    if not target:
        # 便携版换电脑后没有已知路径 -> 让用户选一次
        from tkinter import filedialog
        root.withdraw()
        messagebox.showinfo(
            "选择字库目录",
            "没有自动找到 oledfont.h。\n\n"
            "请选择包含 oledfont.h / oledfont.c 的目录\n"
            "(通常是你工程里的 Other 文件夹)。\n\n"
            "如果是全新的工程, 随便选一个空目录也行,\n"
            "点\"生成字库\"会在那里创建这两个文件。")
        d = filedialog.askdirectory(title="选择字库目录")
        root.deiconify()
        if not d:
            root.destroy()
            return
        target = d

    if "--selftest" in sys.argv:
        root.withdraw()
        app = FontGUI(root, target)
        root.update_idletasks()
        root.update()
        n = len(app.grid_frame.winfo_children())
        print(f"界面构建成功")
        print(f"  目标目录: {target}")
        print(f"  汉字卡片: {n}")
        print(f"  词组: {len(app.words)}")
        print(f"  字模: {len(app.glyphs)}")
        root.destroy()
        return

    FontGUI(root, target)
    root.mainloop()


if __name__ == "__main__":
    main()
