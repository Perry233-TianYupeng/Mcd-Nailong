#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成矢量界面预览图（docs/images/*.svg）。

用途：在没有浏览器可用的环境里，也能给 README 提供可直接渲染的界面预览。
SVG 里的文案、配色、布局全部对照 demo/index.html 与 mock 数据的真实输出。

    python tools/make_previews.py

想要**真实浏览器截图**（PNG）请用 tools/make_screenshots.py。
"""
from __future__ import annotations

import base64
import html
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 注意：**不能**用 docs/images/ —— 平台只允许「根/一级子目录/文件」两层，
# 三层会被上传闸门以「目录层级超限」(S7) 直接拦下。所以平铺在 docs/ 下。
OUT = ROOT / "docs"
PICTURE = ROOT / "picture"
RASTER = {".png", ".jpg", ".jpeg", ".webp"}


def role_image(role: str) -> Path | None:
    """按文件名关键词找素材，与 scripts/card_gen.py 的 ROLE_KEYWORDS 口径一致。"""
    if not PICTURE.exists():
        return None
    return next(
        (p for p in sorted(PICTURE.iterdir()) if p.suffix.lower() in RASTER and role in p.stem.lower()),
        None,
    )


def data_uri(path: Path | None) -> str:
    if not path:
        return ""
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")

FONT = "Microsoft YaHei,PingFang SC,Hiragino Sans GB,sans-serif"
RED = "#DB0007"
YELLOW = "#FFC72C"
INK = "#2B2118"
MUTED = "#7A6A5A"
LINE = "#EADFCB"
BG = "#FBF7F0"
SOFT = "#FFF4E0"
PANEL = "#FFF9F0"

X0, X1 = 200, 1240
W = X1 - X0
PAD = 20
COL_GAP = 40
COL = (W - PAD * 2 - COL_GAP) / 2      # 两栏宽度 = 480
LX = X0 + PAD
RX = X0 + PAD + COL + COL_GAP          # 740

REPO = "github.com/Perry233-TianYupeng/mcd-nailong"


# --------------------------------------------------------------------------- #
# 基础绘制
# --------------------------------------------------------------------------- #
def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def tw(text: str, size: float) -> float:
    return sum(size * (0.55 if ord(ch) < 0x2E80 else 1.0) for ch in text)


def text(x, y, content, size=13, fill=INK, weight=400, anchor="start") -> str:
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return (
        f'<text x="{x:.0f}" y="{y:.0f}" font-family="{FONT}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}"{a}>{esc(content)}</text>'
    )


def rect(x, y, w, h, fill="#FFFFFF", stroke="", rx=12, sw=1, opacity=None, dash=None) -> str:
    s = f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{rx}" fill="{fill}"'
    if stroke:
        s += f' stroke="{stroke}" stroke-width="{sw}"'
    if dash:
        s += f' stroke-dasharray="{dash}"'
    if opacity is not None:
        s += f' opacity="{opacity}"'
    return s + "/>"


def hline(x, y, w, color=LINE, dash="3 3", sw=1) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{x + w:.0f}" y2="{y:.0f}" stroke="{color}" stroke-width="{sw}"{d}/>'


def mascot_icon(cx, cy, s=1.0) -> str:
    """小奶龙图标，中心 (cx, cy)，s 缩放。带腮红，与 demo/index.html 的 logo 一致。"""
    parts = [f'<ellipse cx="{cx:.0f}" cy="{cy + 2 * s:.0f}" rx="{11 * s:.0f}" ry="{12 * s:.0f}" fill="#FFD84D"/>']
    for dx in (-5, 5):
        parts.append(f'<ellipse cx="{cx + dx * s:.0f}" cy="{cy - 2 * s:.0f}" rx="{3 * s:.0f}" ry="{3.4 * s:.0f}" fill="#FFFFFF"/>')
        parts.append(f'<circle cx="{cx + (dx + 1) * s:.0f}" cy="{cy - 1 * s:.0f}" r="{1.4 * s:.0f}" fill="#2B2118"/>')
    for dx in (-6.5, 6.5):
        parts.append(f'<ellipse cx="{cx + dx * s:.0f}" cy="{cy + 3 * s:.0f}" rx="{2.1 * s:.0f}" ry="{1.3 * s:.0f}" fill="rgba(240,140,140,.55)"/>')
    parts.append(
        f'<path d="M{cx - 3.5 * s:.0f} {cy + 5 * s:.0f} Q{cx:.0f} {cy + 8.5 * s:.0f} {cx + 3.5 * s:.0f} {cy + 5 * s:.0f}"'
        f' stroke="#2B2118" stroke-width="{1.6 * s:.0f}" fill="none" stroke-linecap="round"/>'
    )
    return "".join(parts)


def shadow(x, y, w, h, rx=14, dy=5) -> str:
    """柔和的卡片投影（SVG 无真阴影，用 5% 黑的偏移矩形代替）。"""
    return rect(x, y + dy, w, h, "#000000", rx=rx, opacity=0.05)


def card(y, h, x=X0, w=W) -> str:
    return shadow(x, y, w, h) + rect(x, y, w, h, "#FFFFFF", LINE, rx=14)


def h2(x, y, content) -> str:
    return text(x, y, content, 17, INK, 700)


def h3(x, y, content) -> str:
    return text(x, y, content, 14, INK, 700)


def sub(x, y, content, size=13) -> str:
    return text(x, y, content, size, MUTED)


def pill(x, y, label, active=False, size=13):
    w, h = tw(label, size) + 36, 38
    if active:
        return rect(x, y, w, h, RED, rx=19) + text(x + 18, y + 25, label, size, "#FFFFFF", 700), w
    return rect(x, y, w, h, "#FFFFFF", LINE, rx=19) + text(x + 18, y + 25, label, size, INK), w


def chip(x, y, label, kind="warm", size=12):
    w, h = tw(label, size) + 28, 30
    if kind == "red":
        return rect(x, y, w, h, "#FDECEC", "#F3C4C4", rx=15) + text(x + 14, y + 20, label, size, "#A33"), w
    if kind == "green":
        return rect(x, y, w, h, "#EAF3DE", "#C0DD97", rx=15) + text(x + 14, y + 20, label, size, "#3B6D11"), w
    return rect(x, y, w, h, "#FFF0CC", LINE, rx=15) + text(x + 14, y + 20, label, size, "#8A5A12"), w


def chip_line(x, y, labels, max_w, kind="warm", size=12, gap=8) -> str:
    parts, cx = [], x
    for label in labels:
        w = tw(label, size) + 28
        if cx + w > x + max_w:
            break
        svg, _ = chip(cx, y, label, kind, size)
        parts.append(svg)
        cx += w + gap
    return "".join(parts)


def button(x, y, label, primary=True, size=14, pad=44, h=42):
    w = tw(label, size) + pad
    if primary:
        return rect(x, y, w, h, RED, RED, rx=10) + text(x + (w - tw(label, size)) / 2, y + h * 0.64, label, size, "#FFFFFF", 700), w
    return rect(x, y, w, h, "#FFFFFF", LINE, rx=10) + text(x + (w - tw(label, size)) / 2, y + h * 0.64, label, size, INK), w


def select(x, y, w, label, h=38) -> str:
    return (
        rect(x, y, w, h, "#FFFFFF", LINE, rx=10)
        + text(x + 12, y + 24, label, 13, INK)
        + text(x + w - 12, y + 24, "▾", 12, MUTED, anchor="end")
    )


def input_box(x, y, w, label, h=36) -> str:
    return rect(x, y, w, h, "#FFFFFF", LINE, rx=8) + text(x + 12, y + 23, label, 12, MUTED)


def log_box(x, y, w, lines, h=None) -> str:
    h = h or (len(lines) * 22 + 24)
    parts = [rect(x, y, w, h, "#FCFAF5", LINE, rx=10, dash="5 4")]
    cy = y + 24
    for content, color in lines:
        parts.append(text(x + 14, cy, content, 12.5, color))
        cy += 22
    return "".join(parts)


def kv_row(x, y, left, right, w) -> str:
    return text(x, y, left, 13, INK) + text(x + w, y, right, 12, MUTED, anchor="end") + hline(x, y + 8, w)


def metric(x, y, w, label, value, h=70) -> str:
    return (
        rect(x, y, w, h, SOFT, rx=10)
        + text(x + 14, y + 26, label, 12, MUTED)
        + text(x + 14, y + 54, value, 20, INK, 700)
    )


def note_box(x, y, w, content, h=40) -> str:
    """新 UI 的 .note：米白底 + 黄色左边条的趣味提示条。"""
    return (
        rect(x, y, w, h, "#FFFCF5", rx=8)
        + rect(x, y, 3, h, YELLOW, rx=0)
        + text(x + 16, y + h / 2 + 4.5, content, 12.5, "#6B5B4B")
    )


def header() -> str:
    """对照新 UI 的 .brand：奶龙 logo（腮红版）+ 渐变标题 + tagline + 右侧参赛徽章。"""
    badge = "✨ M-CODE 参赛作品"
    bw = tw(badge, 12) + 30
    p = [
        # logo：黄色圆角方块 + 奶龙脸（带腮红）
        shadow(X0, 40, 52, 52, rx=18, dy=3),
        rect(X0, 40, 52, 52, "#FFF0CC", "#F0DCB4", rx=18),
        mascot_icon(X0 + 26, 64, 1.3),
        # 标题（红→橙→黄渐变，对应 CSS background-clip:text）与 tagline
        f'<defs><linearGradient id="h1grad" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="15%" stop-color="{RED}"/><stop offset="55%" stop-color="#F08300"/>'
        f'<stop offset="95%" stop-color="{YELLOW}"/></linearGradient></defs>',
        f'<text x="{X0 + 66}" y="70" font-family="{FONT}" font-size="25" font-weight="700" fill="url(#h1grad)">麦麦奶龙</text>',
        sub(X0 + 66, 92, "🍔 今天吃什么堡？", 13),
        # 右侧：参赛徽章 + 仓库地址
        rect(X1 - bw, 44, bw, 26, RED, rx=13),
        text(X1 - bw / 2, 61, badge, 12, "#FFFFFF", 700, anchor="middle"),
        text(X1, 88, REPO, 12, MUTED, anchor="end"),
        # 底部黄色分隔线
        rect(X0, 112, W, 3, YELLOW, rx=0),
    ]
    return "".join(p)


def tabs(active: int) -> str:
    parts, x = [], X0
    for index, label in enumerate(["① 每日自动领券", "② 麦麦奶龙抽卡", "③ 穷鬼预算锁"]):
        svg, w = pill(x, 146, label, active == index)
        parts.append(svg)
        x += w + 10
    return "".join(parts)


def footer(note: str, y: int) -> str:
    return hline(X0, y, W, LINE, dash=None) + text(X0 + W / 2, y + 30, note, 12, MUTED, anchor="middle")


def wrap(parts: list[str], height: int) -> str:
    return "\n".join(
        [f'<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="{height}" viewBox="0 0 1440 {height}">',
         "<title>麦麦奶龙 · 界面预览</title>",
         '<defs><pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse">'
         '<circle cx="1.1" cy="1.1" r="1.1" fill="#F3E7CC"/></pattern></defs>',
         rect(0, 0, 1440, height, BG, rx=0),
         f'<rect x="0" y="0" width="1440" height="{height}" fill="url(#dots)"/>']
        + parts
        + ["</svg>"]
    )


# --------------------------------------------------------------------------- #
# 画面 1：每日自动领券
# --------------------------------------------------------------------------- #
def screen_coupons() -> str:
    p = [header(), tabs(0)]

    y, h = 196, 384
    p.append(card(y, h))
    p.append(h2(LX, y + 36, "每日一键领券"))
    p.append(sub(LX, y + 62, "对应脚本 scripts/daily_coupons.py。真实调用链：now-time-info → campaign-calendar → available-coupons → auto-bind-coupons → my-coupons。"))
    p.append(note_box(LX, y + 76, W - PAD * 2, "领完记得用——麦麦省的券躺过期就白给了。"))
    svg, bw = button(LX, y + 138, "一键领取今日全部优惠券")
    p.append(svg)
    p.append(rect(LX + bw + 24, y + 152, 13, 13, "#FFFFFF", LINE, rx=3))
    p.append(text(LX + bw + 44, y + 164, "试运行（不实际领取）", 13, INK))
    p.append(rect(LX, y + 200, W - PAD * 2, 8, "#F1EAE0", rx=4))
    p.append(rect(LX, y + 200, W - PAD * 2, 8, RED, rx=4))
    p.append(log_box(LX, y + 224, W - PAD * 2, [
        ("→ now-time-info        读取服务器时间…", "#4A3E33"),
        ("→ campaign-calendar    拉取本月营销日历…", "#4A3E33"),
        ("→ available-coupons    查询可领取优惠券…", "#4A3E33"),
        ("→ auto-bind-coupons    一键领取中…", "#4A3E33"),
        ("→ my-coupons           同步卡包并核算有效期…", "#4A3E33"),
        ("✓ 领取完成：本次领到 6 张，卡包共 6 张。", "#2E7D32"),
    ], h=140))

    y, h = 596, 470
    p.append(card(y, h))
    p.append(h2(LX, y + 34, "今日战报"))
    mw = (W - PAD * 2 - 36) / 4
    for i, (label, value) in enumerate([("本次领取", "6 张"), ("卡包总数", "6 张"), ("临期（3 天内）", "3 张"), ("今日活动", "1 个")]):
        p.append(metric(LX + i * (mw + 12), y + 54, mw, label, value))

    p.append(h3(LX, y + 160, "领取明细"))
    for i, (label, right) in enumerate([
        ("满 30 元减 5 元（全场）", "已领取"),
        ("麦辣鸡腿堡第二份半价（麦辣鸡腿堡）", "已领取"),
        ("中薯条 1 元购（中薯条）", "已领取"),
        ("圆筒冰淇淋免费券（圆筒冰淇淋）", "已领取"),
        ("巨无霸立减 5 元（巨无霸）", "已领取"),
        ("外送免配送费（麦乐送）", "已领取"),
    ]):
        p.append(kv_row(LX, y + 186 + i * 26, label, right, COL))

    p.append(h3(RX, y + 160, "临期提醒"))
    for i, (label, right) in enumerate([("麦辣鸡腿堡第二份半价", "剩 8 天"), ("中薯条 1 元购", "剩 6 天"), ("圆筒冰淇淋免费券", "剩 3 天")]):
        p.append(kv_row(RX, y + 186 + i * 26, label, right, COL))
    p.append(text(RX, y + 282, "⚠ 3 张将在 3 天内过期，记得用掉。", 12, "#A33"))

    p.append(h3(LX, y + 344, "近期活动预告"))
    for i, (date, title, desc) in enumerate([
        ("2026-10-13", "麦麦省上新", "9.9 元专区上新，麦辣鸡翅 2 块 9.9 元"),
        ("2026-10-14", "麦乐送日", "外送满 39 元免配送费"),
        ("2026-10-16", "周末全家桶", "双人套餐买一送一"),
    ]):
        cy = y + 370 + i * 26
        p.append(text(LX, cy, date, 12, MUTED))
        p.append(text(LX + 92, cy, title, 13, INK))
        p.append(text(LX + 218, cy, desc, 12, MUTED))

    return wrap(p + [footer("本 Demo 为离线可跑版本（内置 mock 数据），真实调用请配置 MCD_MCP_TOKEN 后使用 scripts/ 下的 CLI。", 1090)], 1146)


# --------------------------------------------------------------------------- #
# 画面 2：麦麦奶龙抽卡
# --------------------------------------------------------------------------- #
def mini_card(x, y, w, img_uri: str = "") -> str:
    h = w * 9 / 16
    pt = y + h * (470 / 900)
    cx = x + w / 2
    art = (
        f'<image x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" '
        f'preserveAspectRatio="xMidYMid slice" href="{img_uri}"/>'
        if img_uri
        else "".join([
            f'<ellipse cx="{cx:.0f}" cy="{y + h * 0.40:.0f}" rx="{w * 0.15:.0f}" ry="{h * 0.28:.0f}" fill="#FFD84D"/>',
            f'<ellipse cx="{cx - w * 0.052:.0f}" cy="{y + h * 0.29:.0f}" rx="{w * 0.030:.0f}" ry="{h * 0.058:.0f}" fill="#FFFFFF"/>',
            f'<ellipse cx="{cx + w * 0.052:.0f}" cy="{y + h * 0.29:.0f}" rx="{w * 0.030:.0f}" ry="{h * 0.058:.0f}" fill="#FFFFFF"/>',
            f'<circle cx="{cx - w * 0.045:.0f}" cy="{y + h * 0.305:.0f}" r="{w * 0.014:.0f}" fill="#2B2118"/>',
            f'<circle cx="{cx + w * 0.059:.0f}" cy="{y + h * 0.305:.0f}" r="{w * 0.014:.0f}" fill="#2B2118"/>',
            f'<path d="M{cx - w * 0.05:.0f} {y + h * 0.50:.0f} Q{cx:.0f} {y + h * 0.57:.0f} {cx + w * 0.05:.0f} {y + h * 0.50:.0f}" stroke="#2B2118" stroke-width="{max(2, w * 0.008):.0f}" fill="none" stroke-linecap="round"/>',
        ])
    )
    p = [
        rect(x, y, w, h, PANEL, rx=12),
        art,
        rect(x, y, w, h * 12 / 900, RED, rx=0),
        rect(x, y + h - h * 12 / 900, w, h * 12 / 900, YELLOW, rx=0),
        rect(x, pt, w, h - (pt - y), PANEL, rx=0, opacity=0.96),
        rect(x, pt, w, 3, YELLOW, rx=0),
        rect(x + w * 0.035, y + h * 0.06, 44, 22, RED, rx=11, opacity=0.95),
        text(x + w * 0.035 + 12, y + h * 0.06 + 15, "抽卡", 11, "#FFFFFF", 700),
        text(x + w * 0.04, pt + 26, "麦麦奶龙 · 堡格名片", 11, RED),
        text(x + w * 0.04, pt + 56, "省钱天才·巨无霸辣王·单人成军奶龙", 15, INK, 700),
    ]
    cxx = x + w * 0.04
    for label in ["性格 · 省钱天才", "辣度 · 辣党", "食量 · 巨胃"]:
        svg, cw = chip(cxx, pt + 68, label, "warm", 9)
        p.append(svg)
        cxx += cw + 6
    p.append(text(x + w * 0.04, pt + 122, "堡格", 10, MUTED))
    p.append(text(x + w * 0.04 + 36, pt + 122, "巨无霸辣王·单人成军", 11, INK))
    p.append(text(x + w * 0.04, pt + 142, "推荐", 10, MUTED))
    p.append(text(x + w * 0.04 + 36, pt + 142, "麦辣鸡腿堡中套餐　实付 ¥24.50", 11, INK))
    p.append(text(cx, y + h - 12, f"开源仓库：{REPO}", 9, "#B0A395", anchor="middle"))
    return "".join(p)


def screen_quiz() -> str:
    p = [header(), tabs(1)]

    y, h = 196, 150
    p.append(card(y, h))
    p.append(h2(LX, y + 36, "麦麦奶龙 · 汉堡抽卡"))
    p.append(sub(LX, y + 62, "10 道题（麦当劳 5 : 日常 5），或直接读历史订单。答完立刻出「堡格」与奶龙名片。"))
    bx = LX
    for label, primary in [("开始答题", True), ("不想答题，读我的历史订单", False), ("随机来一套（看看别人抽到啥）", False)]:
        svg, bw = button(bx, y + 82, label, primary, 13, 36, 40)
        p.append(svg)
        bx += bw + 10

    y, h = 362, 648
    p.append(card(y, h))
    p.append(h2(LX, y + 36, "💳 你的奶龙名片"))
    left_w = 560
    p.append(mini_card(LX, y + 56, left_w, data_uri(role_image("spicy"))))
    sx = LX
    for label, primary in [("下载 PNG", True), ("分享到微信 / QQ", False), ("复制文案", False)]:
        svg, bw = button(sx, y + 392, label, primary, 13, 32, 40)
        p.append(svg)
        sx += bw + 10
    p.append(sub(LX, y + 458, "16:9 尺寸，微信、QQ、朋友圈、QQ 空间可直接发送。", 12))

    rw = X1 - PAD - RX
    cy = y + 62
    p.append(h3(RX, cy, "四轴画像"))
    p.append(chip_line(RX, cy + 14, ["辣度 · 辣党", "食量 · 巨胃", "决策 · 果决派", "社交 · 独食型"], rw))
    cy += 72
    p.append(h3(RX, cy, "性格关键词"))
    p.append(chip_line(RX, cy + 14, ["省钱天才", "计划控"], rw, "red"))
    cy += 72
    p.append(h3(RX, cy, "堡格解读"))
    p.append(text(RX, cy + 26, "巨无霸辣王·单人成军", 13, INK, 700))
    p.append(sub(RX, cy + 48, "辣度与分量双高，你的字典里没有「小份」。", 12))
    cy += 88
    p.append(h3(RX, cy, "推荐套餐"))
    for i, (name, price) in enumerate([("不素之霸", "¥25.00"), ("那么大鸡排", "¥16.00"), ("大杯可乐", "¥11.00")]):
        p.append(kv_row(RX, cy + 26 + i * 26, name, price, rw))
    p.append(text(RX, cy + 128, "实付", 13, INK, 700))
    p.append(text(RX + rw, cy + 128, "¥47.00", 14, RED, 700, anchor="end"))
    cy += 162
    p.append(h3(RX, cy, "底图"))
    p.append(sub(RX, cy + 26, "按堡格自动匹配奶龙梗图，也可上传自己的 16:9 图替换。", 12))
    # 预设素材缩略 chips（对应 #imgPresets）
    px = RX
    for label in ["辣堡出击", "温柔巨塔", "干饭盛宴"]:
        svg, cw = chip(px, cy + 40, label, "warm", 11)
        p.append(svg)
        px += cw + 6
    p.append(input_box(RX, cy + 82, rw, "选择文件　未选择任何文件"))
    svg, bw = button(RX, cy + 132, "再抽一次", False, 13, 34, 40)
    p.append(svg)

    return wrap(p + [footer("名片名格式固定为 {性格}+{堡格}+奶龙　·　画布 1600×900，梗图满幅不裁切，页脚浅色小字写仓库地址", 1034)], 1090)


# --------------------------------------------------------------------------- #
# 画面 3：穷鬼预算锁
# --------------------------------------------------------------------------- #
def plan_card(x, y, w, tag, price, items, meta, tier) -> str:
    h = 280
    p = [shadow(x, y, w, h, rx=12, dy=4), rect(x, y, w, h, "#FFFFFF", LINE, rx=12)]
    p.append(rect(x + 16, y + 16, tw(tag, 12) + 28, 30, "#FFF0CC", LINE, rx=15))
    p.append(text(x + 30, y + 36, tag, 12, "#8A5A12"))
    p.append(text(x + w - 16, y + 42, price, 22, RED, 700, anchor="end"))
    iy = y + 80
    for item in items:
        p.append(text(x + 16, iy, item, 13, INK))
        iy += 24
    iy += 10
    for line in meta:
        p.append(text(x + 16, iy, line, 11.5, MUTED))
        iy += 20
    p.append(text(x + 16, iy + 6, tier, 11.5, "#A33"))
    p.append(rect(x + 16, y + h - 52, 112, 36, "#FFFFFF", LINE, rx=10))
    p.append(text(x + 32, y + h - 29, "载入购物车", 13, INK))
    return "".join(p)


def screen_budget() -> str:
    p = [header(), tabs(2)]

    y, h = 196, 296
    p.append(card(y, h))
    p.append(h2(LX, y + 36, "穷鬼预算锁 —— “我只有 X 块，吃饱”"))
    p.append(sub(LX, y + 62, "在预算硬约束下枚举组合 → 本地试算 → 求 Pareto 前沿 → 给你 3 套最优解。真实 Skill 会再走一次 MCP calculate-price 复核。"))

    p.append(text(LX, y + 102, "预算上限：", 13, MUTED))
    p.append(text(LX + 72, y + 102, "¥25", 15, RED, 700))
    track = COL - 110
    p.append(rect(LX + 110, y + 92, track, 8, "#F1EAE0", rx=4))
    p.append(rect(LX + 110, y + 92, track * 0.26, 8, RED, rx=4))
    p.append(f'<circle cx="{LX + 110 + track * 0.26:.0f}" cy="{y + 96}" r="9" fill="{RED}" stroke="#FFFFFF" stroke-width="3"/>')

    p.append(text(LX, y + 168, "口味偏好（可多选，再点一次变成“排除”）", 13, MUTED))
    p.append(chip_line(LX, y + 180, ["辣", "鸡", "不辣", "牛", "鱼", "素", "甜"], COL))
    p.append(chip_line(LX, y + 218, ["冷", "热", "量足"], COL))
    svg, bw = button(LX, y + 250, "开始求解", True, 14)
    p.append(svg)

    p.append(text(RX, y + 102, "就餐方式", 13, MUTED))
    p.append(select(RX, y + 112, COL, "到店取餐"))
    p.append(text(RX, y + 186, "门店", 13, MUTED))
    p.append(select(RX, y + 196, COL, "麦当劳（南京东路店）　·　320m　·　07:00-23:00", h=38))

    y, h = 508, 412
    p.append(card(y, h))
    p.append(h2(LX, y + 36, "🥇 Pareto 最优 3 套方案"))
    p.append(sub(LX, y + 60, "门店 麦当劳（南京东路店）　·　枚举 40 种组合 → 可行 6 种 → Pareto 前沿 2 个"))
    pw = (W - PAD * 2 - 24) / 3
    plans = [
        ("极致省钱", "¥13.90", ["1+1 随心配 ×1", "圆筒冰淇淋 ×1"],
         ["原价 ¥19.90　优惠 ¥6.00", "满足度 0.95　每元饱腹 14.63", "610 kcal　蛋白 16g"], "消费等级：节俭度日"),
        ("最满足", "¥22.50", ["麦辣鸡腿堡 ×1", "圆筒冰淇淋 ×1"],
         ["原价 ¥28.50　优惠 ¥6.00", "满足度 1.10　每元饱腹 20.45", "660 kcal　蛋白 26g"], "消费等级：节俭度日"),
        ("备选方案", "¥22.50", ["麦辣鸡腿堡 ×1"],
         ["原价 ¥22.50　优惠 ¥0.00", "满足度 0.95　每元饱腹 23.68", "500 kcal　蛋白 23g"], "消费等级：节俭度日"),
    ]
    for i, plan in enumerate(plans):
        p.append(plan_card(LX + i * (pw + 12), y + 78, pw, *plan))
    p.append(sub(LX, y + 386, "点方案即可载入下方购物车，然后自由增删改。", 12))

    y, h = 936, 380
    p.append(card(y, h))
    p.append(h2(LX, y + 36, "我的订单"))
    for i, (name, qty, price) in enumerate([("1+1 随心配", "1", "¥13.90"), ("圆筒冰淇淋", "1", "¥6.00")]):
        cy = y + 72 + i * 34
        p.append(text(LX, cy, name, 13, INK))
        p.append(text(LX + COL - 152, cy, "−", 14, MUTED))
        p.append(text(LX + COL - 124, cy, qty, 13, INK, 700))
        p.append(text(LX + COL - 98, cy, "+", 14, MUTED))
        p.append(text(LX + COL, cy, price, 13, MUTED, anchor="end"))
        p.append(hline(LX, cy + 10, COL))
    p.append(text(LX, y + 168, "加购一件", 12, MUTED))
    p.append(select(LX, y + 180, COL, "巨无霸　¥26.00"))
    svg, bw = button(LX, y + 232, "加入购物车", False, 13, 34)
    p.append(svg)

    mw = (COL - 36) / 4
    for i, (label, value, color) in enumerate([("原价", "¥19.90", INK), ("优惠", "-¥6.00", "#2E7D32"), ("配送费", "¥0.00", INK), ("实付", "¥13.90", RED)]):
        mx = RX + i * (mw + 12)
        p.append(rect(mx, y + 60, mw, 70, SOFT, rx=10))
        p.append(text(mx + 12, y + 86, label, 12, MUTED))
        p.append(text(mx + 12, y + 114, value, 18, color, 700))

    p.append(rect(RX, y + 146, tw("消费等级 · 节俭度日", 12) + 28, 30, "#FDECEC", "#F3C4C4", rx=15))
    p.append(text(RX + 14, y + 166, "消费等级 · 节俭度日", 12, "#A33"))
    p.append(sub(RX, y + 198, "钱要花在刀刃上，吃饱是唯一 KPI。（区间 ¥25 以下）", 12))

    bx = RX
    for label, primary in [("确认下单", True), ("生成本单奶龙名片", False)]:
        svg, bw = button(bx, y + 216, label, primary, 13, 34, 40)
        p.append(svg)
        bx += bw + 10

    p.append(log_box(RX, y + 272, COL, [
        ("→ create-order   创建待支付订单中…", "#4A3E33"),
        ("订单已创建：MO64577028", "#4A3E33"),
        ("状态：待支付（leftPaySecond ≈ 899）", "#4A3E33"),
        ("⚠ create-order 不会扣款，请自行付款", "#A33"),
    ], h=112))

    return wrap(p + [footer("所有价格、券、活动以麦当劳 MCP 实时查询为准　·　下单前必须经用户确认，且不会静默扣款", 1340)], 1396)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    count = 0

    for name, svg in [("01-daily-coupons", screen_coupons()), ("02-nailong-card", screen_quiz()), ("03-budget-lock", screen_budget())]:
        path = OUT / f"{name}.svg"
        path.write_text(svg, encoding="utf-8")
        print(f"  {path.relative_to(ROOT)}  {round(len(svg) / 1024, 1)}KB")
        count += 1

    # 真实生成的名片直接搬进 docs：它本身就是自包含 SVG（素材已 base64 内嵌）
    card = ROOT / "out" / "card-quiz.svg"
    if card.exists():
        target = OUT / "04-namecard.svg"
        shutil.copyfile(card, target)
        print(f"  {target.relative_to(ROOT)}  {round(target.stat().st_size / 1024, 1)}KB")
        count += 1
    else:
        print("  SKIP 04-namecard.svg（先跑一次 quiz_engine.py + card_gen.py）")

    print(f"\n共 {count} 张，输出到 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
