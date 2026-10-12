#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""奶龙名片卡生成器（1600×900，16:9）。

设计
----
梗图**满幅不裁切**（1600×900 = 标准 16:9），底部叠一块浅色信息面板放文字，
页脚用浅色字写仓库地址 —— 这样 16:9 的奶龙梗图可以原样呈现，适配朋友圈 / QQ 空间。

零第三方依赖：直接吐 SVG，图片以 base64 内嵌，**单文件可传**。
同时输出一个 HTML 包装页，内置「下载 PNG」按钮（浏览器端 canvas 导出）。

用法
----
    python card_gen.py --list-images
    python card_gen.py --quiz-result out/quiz.json --out out/card-quiz.svg
    python card_gen.py --budget-pay 28.0 --burger "双层吉士中套餐" --out out/card-budget.svg
    python card_gen.py --name "省钱天才·巨无霸辣王·单人成军奶龙" --out out/card.svg
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_pictures import image_size  # noqa: E402
from mcd_naming import card_name_for_budget, spend_tier  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PICTURE_DIR = ROOT / "picture"
W, H = 1600, 900
REPO_URL = "github.com/Perry233-TianYupeng/mcd-nailong"

RED = "#DB0007"
YELLOW = "#FFC72C"
INK = "#2B2118"
MUTED = "#8A7A6A"
FOOTER = "#B0A395"
PANEL = "#FFF9F0"
FONT = "Microsoft YaHei,PingFang SC,Hiragino Sans GB,sans-serif"

Y_EYEBROW = 534
Y_TITLE = 596
Y_CHIPS = 722
Y_INFO = 792
Y_FOOTER = 866
PANEL_TOP = 470

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml"}


# --------------------------------------------------------------------------- #
# 素材
# --------------------------------------------------------------------------- #
def list_images() -> list[Path]:
    if not PICTURE_DIR.exists():
        return []
    exts = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
    return sorted(p for p in PICTURE_DIR.iterdir() if p.suffix.lower() in exts and p.is_file())


# 素材文件名关键词 -> 语义角色（见 picture/README.md）
ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "spicy": ("spicy",),
    "gentle": ("gentle",),
    "feast": ("feast",),
    "lightmeal": ("lightmeal",),
    "thrifty": ("thrifty",),
    "freedom": ("freedom",),
    "hero": ("hero",),
    "coupon": ("coupon",),
    "number": ("number",),
    "burger": ("burger",),
}

# 堡格 -> 优先使用的素材角色（取不到时顺延）
BOGE_ROLE: dict[str, tuple[str, ...]] = {
    "巨无霸辣王": ("spicy", "feast"),
    "椒香小钢炮": ("spicy", "lightmeal"),
    "温柔巨塔": ("gentle", "feast"),
    "云朵轻食家": ("gentle", "lightmeal"),
}

# 消费等级 -> 素材角色
TIER_ROLE: dict[str, tuple[str, ...]] = {
    "节俭度日": ("thrifty", "burger"),
    "吃堡自由": ("freedom", "burger"),
    "豪情在天": ("hero", "burger"),
}


def image_for_role(role: str) -> list[Path]:
    """按角色返回所有匹配的素材（可能有多张）。"""
    keys = ROLE_KEYWORDS.get(role, (role,))
    return [p for p in list_images() if any(k.lower() in p.stem.lower() for k in keys)]


def pick_image(explicit: str | None = None, seed: str | None = None, roles: tuple[str, ...] | None = None) -> Path | None:
    """挑底图。

    优先级：显式指定 > 按语义角色匹配 > 全量随机 > 内置占位图。
    同一角色有多张时用 seed 做**确定性**轮换，保证同一个人格每次抽到同一张。
    """
    if explicit:
        path = Path(explicit)
        return path if path.exists() else None

    rng = random.Random(seed) if seed else random

    if roles:
        # 按角色优先级取**第一个有素材的**角色，避免"豪情在天"被兜底的 burger 抢走
        for role in roles:
            matches = image_for_role(role)
            if matches:
                return rng.choice(matches) if len(matches) > 1 else matches[0]

    images = list_images()
    return rng.choice(images) if images else None


def data_uri(path: Path) -> str:
    mime = MIME.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


PLACEHOLDER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
<rect width="1600" height="900" fill="#FFF3CC"/>
<circle cx="300" cy="180" r="130" fill="#FFE9A8"/>
<circle cx="1330" cy="240" r="170" fill="#FFE9A8"/>
<ellipse cx="760" cy="640" rx="300" ry="80" fill="#F2CE55"/>
<ellipse cx="760" cy="400" rx="250" ry="270" fill="#FFD84D"/>
<ellipse cx="672" cy="330" rx="52" ry="58" fill="#FFFFFF"/>
<ellipse cx="850" cy="330" rx="52" ry="58" fill="#FFFFFF"/>
<circle cx="682" cy="344" r="24" fill="#2B2118"/>
<circle cx="860" cy="344" r="24" fill="#2B2118"/>
<path d="M690 470 Q760 528 830 470" stroke="#2B2118" stroke-width="16" fill="none" stroke-linecap="round"/>
<ellipse cx="560" cy="250" rx="66" ry="38" fill="#FFD84D" transform="rotate(-14 560 250)"/>
<ellipse cx="960" cy="250" rx="66" ry="38" fill="#FFD84D" transform="rotate(14 960 250)"/>
<text x="800" y="300" text-anchor="middle" font-family="Microsoft YaHei,sans-serif" font-size="34" fill="#A8811A">占位图 · 把 16:9 奶龙梗图放进 picture/ 即自动替换</text>
</svg>"""


# --------------------------------------------------------------------------- #
# 排版工具
# --------------------------------------------------------------------------- #
def text_width(text: str, size: float) -> float:
    return sum(size * (0.55 if ord(ch) < 0x2E80 else 1.0) for ch in text)


def wrap(text: str, max_width: float, size: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
        if current and text_width(current + ch, size) > max_width:
            lines.append(current)
            current = ch
        else:
            current += ch
    if current:
        lines.append(current)
    return lines


def fit_title(text: str, max_width: float, max_lines: int = 2) -> tuple[float, list[str]]:
    for size in (64, 58, 52, 46, 40, 36):
        lines = wrap(text, max_width, size)
        if len(lines) <= max_lines:
            return size, lines
    return 36, wrap(text, max_width, 36)[:max_lines]


def ellipsis(text: str, max_width: float, size: float) -> str:
    if text_width(text, size) <= max_width:
        return text
    out = ""
    for ch in text:
        if text_width(out + ch + "…", size) > max_width:
            break
        out += ch
    return out + "…"


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


# --------------------------------------------------------------------------- #
# 字段组装
# --------------------------------------------------------------------------- #
def fields_from_quiz(result: dict) -> dict:
    boge = result.get("boge", {})
    rec = result.get("recommend", {})
    items = rec.get("items") or []
    price = rec.get("price") or {}
    personalities = result.get("personalities") or []
    axes_text = result.get("axesText") or {}

    combo = " + ".join(i.get("name", "") for i in items) or "随心配一份"
    pay = price.get("pay")
    pay_text = f"实付 ¥{float(pay):.2f}" if pay not in (None, "") else ""

    chips = [f"性格 · {p}" for p in personalities[:2]] + [f"{k} · {v}" for k, v in list(axes_text.items())[:2]]
    info = [
        ("堡格", boge.get("name", "神秘堡格")),
        ("推荐", " ".join(x for x in [combo, pay_text] if x)),
    ]
    return {
        "eyebrow": "麦麦奶龙 · 堡格名片",
        "title": result.get("cardName") or "神秘堡格奶龙",
        "chips": chips,
        "info": info,
        "note": boge.get("blurb", ""),
        "badge": "抽卡",
        "roles": BOGE_ROLE.get(boge.get("base", ""), ("burger",)),
    }


def fields_from_budget(pay: float, burger: str, name: str | None = None) -> dict:
    tier = spend_tier(pay)
    span = "¥25 以下" if tier["max"] <= 25 else ("¥25 - 40" if tier["max"] <= 40 else "¥40 以上")
    return {
        "eyebrow": "麦麦奶龙 · 消费名片",
        "title": name or card_name_for_budget(tier, burger),
        "chips": [f"消费等级 · {tier['level']}", f"实付 ¥{pay:.2f}", f"区间 · {span}"],
        "info": [("主餐", burger), ("等级", tier["desc"])],
        "note": "预算锁定的胜利，每一分钱都花在刀刃上。",
        "badge": "消费",
        "roles": TIER_ROLE.get(tier["level"], ("burger",)),
    }


# --------------------------------------------------------------------------- #
# 渲染
# --------------------------------------------------------------------------- #
def render_svg(fields: dict, image: Path | None, repo_url: str = REPO_URL) -> str:
    if image:
        img_uri = data_uri(image)
    else:
        img_uri = "data:image/svg+xml;base64," + base64.b64encode(PLACEHOLDER_SVG.encode("utf-8")).decode("ascii")

    p: list[str] = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    p.append(f'<rect width="{W}" height="{H}" fill="{PANEL}"/>')

    # 满幅梗图（16:9 原样呈现，非 16:9 素材才做最小裁切）
    # 只用 href（SVG 2）：同时写 xlink:href 会让同一张图被 base64 存两份，文件直接翻倍
    p.append(f'<image x="0" y="0" width="{W}" height="{H}" preserveAspectRatio="xMidYMid slice" href="{img_uri}"/>')

    # 顶部/底部品牌色条
    p.append(f'<rect x="0" y="0" width="{W}" height="12" fill="{RED}"/>')
    p.append(f'<rect x="0" y="{H - 12}" width="{W}" height="12" fill="{YELLOW}"/>')

    # 角标
    badge = fields.get("badge", "")
    if badge:
        bw = 40 + text_width(badge, 28)
        p.append(f'<rect x="56" y="52" width="{bw:.0f}" height="58" rx="29" fill="{RED}" opacity="0.93"/>')
        p.append(f'<text x="{56 + 20}" y="91" font-family="{FONT}" font-size="28" font-weight="700" fill="#FFFFFF">{esc(badge)}</text>')

    # 底部信息面板
    p.append(f'<rect x="0" y="{PANEL_TOP}" width="{W}" height="{H - PANEL_TOP}" fill="{PANEL}" opacity="0.95"/>')
    p.append(f'<rect x="0" y="{PANEL_TOP}" width="{W}" height="5" fill="{YELLOW}"/>')

    left = 64
    right = W - 64

    p.append(f'<text x="{left}" y="{Y_EYEBROW}" font-family="{FONT}" font-size="26" letter-spacing="6" fill="{RED}">{esc(fields["eyebrow"])}</text>')

    size, lines = fit_title(fields["title"], right - left, max_lines=2)
    y = Y_TITLE
    for line in lines:
        p.append(f'<text x="{left}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="700" fill="{INK}">{esc(line)}</text>')
        y += size * 1.2

    # chips
    cx = left
    for chip in fields.get("chips", [])[:5]:
        cw = text_width(chip, 24) + 36
        if cx + cw > right:
            break
        p.append(f'<rect x="{cx:.0f}" y="{Y_CHIPS - 34}" width="{cw:.0f}" height="46" rx="23" fill="#FFEFD0" stroke="#F0DCB4" stroke-width="2"/>')
        p.append(f'<text x="{cx + 18:.0f}" y="{Y_CHIPS}" font-family="{FONT}" font-size="24" fill="#8A5A12">{esc(chip)}</text>')
        cx += cw + 14

    # 信息行（标签 + 值）
    info = fields.get("info", [])
    iy = Y_INFO
    for label, value in info[:2]:
        if not value:
            continue
        p.append(f'<text x="{left}" y="{iy}" font-family="{FONT}" font-size="26" fill="{MUTED}">{esc(label)}</text>')
        p.append(f'<text x="{left + 92}" y="{iy}" font-family="{FONT}" font-size="28" fill="{INK}">{esc(ellipsis(str(value), right - left - 92, 28))}</text>')
        iy += 40

    # 页脚：仓库地址（浅色小字）
    p.append(f'<text x="{W / 2:.0f}" y="{Y_FOOTER}" text-anchor="middle" font-family="{FONT}" font-size="22" fill="{FOOTER}">开源仓库：{esc(repo_url)}　·　麦麦奶龙 汉堡抽卡 &amp; 穷鬼预算锁</text>')
    p.append("</svg>")
    return "\n".join(p)


def render_html(svg: str, title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(title)} · 麦麦奶龙名片</title>
<style>
  body {{ margin:0; background:#F5F2EC; font-family:"Microsoft YaHei","PingFang SC",sans-serif;
         display:flex; flex-direction:column; align-items:center; gap:14px; padding:24px; }}
  .card {{ width:min(96vw,1120px); box-shadow:0 10px 34px rgba(0,0,0,.14); border-radius:18px;
          overflow:hidden; background:#fff; }}
  .card svg {{ display:block; width:100%; height:auto; }}
  .actions {{ display:flex; gap:12px; flex-wrap:wrap; justify-content:center; }}
  button {{ font-size:15px; padding:12px 22px; border-radius:10px; border:1px solid #ddd;
           background:#fff; cursor:pointer; -webkit-tap-highlight-color:transparent; }}
  button.primary {{ background:#DB0007; color:#fff; border-color:#DB0007; }}
  .tip {{ color:#888; font-size:13px; margin:0; text-align:center; line-height:1.7; max-width:640px; }}
  @media (max-width:720px) {{
    body {{ padding:12px; gap:10px; }}
    .card {{ border-radius:12px; }}
    button {{ width:100%; }}
  }}
</style>
</head>
<body>
<h2 style="font-size:16px;color:#333;margin:4px 0;text-align:center;">{esc(title)}</h2>
<div class="card" id="cardWrap">{svg}</div>
<div class="actions">
  <button class="primary" onclick="downloadPng()">下载 PNG（可直接发微信 / QQ）</button>
</div>
<p class="tip">16:9 尺寸在朋友圈 / QQ 空间展示效果最佳。<br>
手机端若下载被拦截，可长按卡片图片选择「保存图片」，或直接截图。</p>
<script>
function downloadPng() {{
  const svgEl = document.querySelector('.card svg');
  const data = new XMLSerializer().serializeToString(svgEl);
  const blob = new Blob([data], {{ type: 'image/svg+xml;charset=utf-8' }});
  const url = URL.createObjectURL(blob);
  const img = new Image();
  img.onload = function () {{
    const canvas = document.createElement('canvas');
    canvas.width = {W}; canvas.height = {H};
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#FFF9F0'; ctx.fillRect(0, 0, {W}, {H});
    ctx.drawImage(img, 0, 0, {W}, {H});
    URL.revokeObjectURL(url);
    try {{
      const a = document.createElement('a');
      a.download = {json.dumps(title, ensure_ascii=False)} + '.png';
      a.href = canvas.toDataURL('image/png');
      a.click();
    }} catch (err) {{ alert('导出失败，请直接截图保存：' + err.message); }}
  }};
  img.onerror = function () {{ alert('图片渲染失败，请直接截图保存。'); }};
  img.src = url;
}}
</script>
</body>
</html>
"""


def write_card(fields: dict, image: Path | None, out_path: Path, repo_url: str = REPO_URL) -> tuple[Path, Path]:
    svg = render_svg(fields, image, repo_url)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    html_path = out_path.with_suffix(".html")
    html_path.write_text(render_html(svg, fields["title"]), encoding="utf-8")
    return out_path, html_path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成奶龙名片卡（SVG + HTML，1600×900）")
    parser.add_argument("--quiz-result", default="", help="quiz_engine 输出的 JSON")
    parser.add_argument("--budget-pay", type=float, default=None, help="消费名片：实付金额")
    parser.add_argument("--burger", default="", help="消费名片：主餐名")
    parser.add_argument("--name", default="", help="直接指定名片名")
    parser.add_argument("--image", default="", help="指定奶龙图（默认按语义角色从 picture/ 抽）")
    parser.add_argument("--role", default="", help="强制素材角色，如 spicy / feast / thrifty / hero / coupon / number")
    parser.add_argument("--repo-url", default=REPO_URL)
    parser.add_argument("--out", default="out/card.svg")
    parser.add_argument("--list-images", action="store_true")
    args = parser.parse_args(argv)

    if args.list_images:
        images = list_images()
        if not images:
            print(f"picture/ 下暂无图片。请把 16:9 奶龙梗图放进去：{PICTURE_DIR}")
            print("生成提示词见 picture/README.md")
            return 0
        print(f"{'文件':<28}{'尺寸':<14}{'语义角色'}")
        print("-" * 62)
        for path in images:
            size = image_size(path)
            roles = [r for r in ROLE_KEYWORDS if r in path.stem.lower()]
            print(f"{path.name:<28}{(f'{size[0]}x{size[1]}' if size else '未知'):<14}{'、'.join(roles) or '（未识别，按通用素材使用）'}")
        print("\n角色映射规则见 picture/README.md；堡格/消费等级到角色的对应见 scripts/card_gen.py 的 BOGE_ROLE / TIER_ROLE。")
        return 0

    if args.quiz_result:
        result = json.loads(Path(args.quiz_result).read_text(encoding="utf-8"))
        fields = fields_from_quiz(result)
        seed = result.get("cardName")
    elif args.budget_pay is not None:
        fields = fields_from_budget(args.budget_pay, args.burger or "汉堡")
        seed = fields["title"]
    elif args.name:
        fields = {"eyebrow": "麦麦奶龙 · 名片", "title": args.name, "chips": [], "info": [], "note": "", "badge": "名片"}
        seed = args.name
    else:
        parser.error("需要 --quiz-result / --budget-pay / --name 之一")

    roles = (args.role,) if args.role else fields.get("roles")
    image = pick_image(args.image or None, seed=seed, roles=roles)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    svg_path, html_path = write_card(fields, image, out_path, args.repo_url)

    print(f"名片名：{fields['title']}")
    if roles:
        print(f"素材角色：{'、'.join(roles)}")
    print(f"素材：{image.name if image else '内置占位图（把 16:9 奶龙图放进 picture/ 即自动替换）'}")
    print(f"SVG ：{svg_path}")
    print(f"HTML：{html_path}  ← 打开后点「下载 PNG」即可发微信/QQ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
