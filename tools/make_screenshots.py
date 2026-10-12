#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 README 用的界面截图（开发/文档工具，非技能运行时脚本）。

做法：把 demo/index.html 复制成临时 harness（注入一段自动点按钮的驱动脚本），
用本机 Chrome 无头模式截图，写完就删掉 harness。**不改动 demo 本体**。

    python tools/make_screenshots.py
    python tools/make_screenshots.py --chrome "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    python tools/make_screenshots.py --only quiz

产物落在 docs/images/*.png，README 直接相对路径引用。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
# 与 make_previews.py 保持一致：平铺在 docs/ 下（平台只支持两层目录，不能用 docs/images/）
OUT_DIR = ROOT / "docs"

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]

# 每条：截哪个页面 / 先切到哪个 tab / 点什么 / 等多久（虚拟时间预算，毫秒）/ 窗口尺寸
DEMO_SHOTS = [
    ("01-daily-coupons", "coupon", "document.querySelector('#btnCoupon').click();", 9000, (1440, 1240)),
    ("02-nailong-card", "quiz", "document.querySelector('#btnQuizRandom').click();", 4000, (1440, 1400)),
    ("03-budget-lock", "budget", "document.querySelector('#btnSolve').click();", 3500, (1440, 1620)),
]
PLAIN_SHOTS = [
    ("04-card-namecard", "out/card-quiz.html", 1500, (1440, 960)),
]

DRIVER = """
<script>
(function () {
  function fire() {
    try {
      var tab = document.querySelector('.tab[data-tab="%(tab)s"]');
      if (tab) tab.click();
      setTimeout(function () { try { %(js)s } catch (e) {} }, 260);
    } catch (e) {}
  }
  if (document.readyState === 'complete') setTimeout(fire, 220);
  else window.addEventListener('load', function () { setTimeout(fire, 220); });
})();
</script>
"""


def find_chrome(explicit: str = "") -> str:
    if explicit:
        return explicit if Path(explicit).exists() else ""
    from shutil import which

    for name in ("google-chrome", "chromium", "chrome", "msedge"):
        found = which(name)
        if found:
            return found
    return next((p for p in CHROME_CANDIDATES if Path(p).exists()), "")


def shoot(chrome: str, target: Path, out: Path, size: tuple[int, int], budget_ms: int) -> bool:
    out.parent.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="mcd-shot-profile-"))
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        f"--user-data-dir={profile}",
        f"--window-size={size[0]},{size[1]}",
        f"--virtual-time-budget={budget_ms}",
        f"--screenshot={out}",
        target.resolve().as_uri(),
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError):
        return False
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    return out.exists() and out.stat().st_size > 2000


def build_harness(name: str, tab: str, js: str) -> Path:
    """在 demo/ 下生成临时 harness，保证 picture-manifest.js 等相对路径能解析。"""
    html = (DEMO / "index.html").read_text(encoding="utf-8")
    injected = html.replace("</body>", DRIVER % {"tab": tab, "js": js} + "</body>")
    harness = DEMO / f"_shot-{name}.html"
    harness.write_text(injected, encoding="utf-8")
    return harness


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 README 界面截图")
    parser.add_argument("--chrome", default="", help="浏览器可执行文件路径，缺省自动探测")
    parser.add_argument("--only", default="", help="只生成名字包含该关键字的截图")
    args = parser.parse_args(argv)

    chrome = find_chrome(args.chrome)
    if not chrome:
        print("[错误] 没找到 Chrome / Edge。请用 --chrome 指定可执行文件路径。", file=sys.stderr)
        return 2
    print(f"浏览器：{chrome}")
    print(f"输出目录：{OUT_DIR}\n")

    ok = 0
    total = 0

    for name, tab, js, budget, size in DEMO_SHOTS:
        if args.only and args.only not in name:
            continue
        total += 1
        harness = build_harness(name, tab, js)
        try:
            result = shoot(chrome, harness, OUT_DIR / f"{name}.png", size, budget)
        finally:
            harness.unlink(missing_ok=True)
        size_kb = round((OUT_DIR / f"{name}.png").stat().st_size / 1024) if result else 0
        print(f"  {'OK  ' if result else 'FAIL'} {name}.png  {size[0]}x{size[1]}  {size_kb}KB")
        ok += result

    for name, rel, budget, size in PLAIN_SHOTS:
        if args.only and args.only not in name:
            continue
        source = ROOT / rel
        if not source.exists():
            print(f"  SKIP {name}.png  （{rel} 不存在，先跑一次 card_gen.py）")
            continue
        total += 1
        result = shoot(chrome, source, OUT_DIR / f"{name}.png", size, budget)
        size_kb = round((OUT_DIR / f"{name}.png").stat().st_size / 1024) if result else 0
        print(f"  {'OK  ' if result else 'FAIL'} {name}.png  {size[0]}x{size[1]}  {size_kb}KB")
        ok += result

    print(f"\n完成：{ok}/{total}")
    return 0 if ok == total and total else 1


if __name__ == "__main__":
    raise SystemExit(main())
