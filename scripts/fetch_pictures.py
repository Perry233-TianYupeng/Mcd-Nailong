#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""奶龙素材导入 / 体检 / 清单生成。

零第三方依赖：用标准库读图片头拿宽高，无需 Pillow。

    python fetch_pictures.py --scan
    python fetch_pictures.py --from-dir "D:/我的奶龙图"
    python fetch_pictures.py --urls "https://a.jpg,https://b.png"
    python fetch_pictures.py --manifest
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PICTURE_DIR = ROOT / "picture"
MANIFEST = ROOT / "demo" / "picture-manifest.js"
EXTS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
TARGET_RATIO = 16 / 9


# --------------------------------------------------------------------------- #
# 尺寸探测（读文件头，不依赖 Pillow）
# --------------------------------------------------------------------------- #
def image_size(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            head = handle.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                width, height = struct.unpack(">II", head[16:24])
                return int(width), int(height)
            if head[:2] == b"\xff\xd8":
                handle.seek(2)
                while True:
                    marker = handle.read(2)
                    if len(marker) < 2:
                        return None
                    while marker[0] != 0xFF:
                        marker = marker[1:] + handle.read(1)
                    code = marker[1]
                    if code in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        length = struct.unpack(">H", handle.read(2))[0]
                        data = handle.read(5)
                        height, width = struct.unpack(">HH", data[1:5])
                        return int(width), int(height)
                    if code in (0xD8, 0xD9) or 0xD0 <= code <= 0xD7:
                        continue
                    length = struct.unpack(">H", handle.read(2))[0]
                    handle.seek(length - 2, 1)
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                fmt = head[12:16]
                if fmt == b"VP8X":
                    width = int.from_bytes(head[24:27], "little") + 1
                    height = int.from_bytes(head[27:30], "little") + 1
                    return width, height
                if fmt == b"VP8 ":
                    width = int.from_bytes(head[26:28], "little") & 0x3FFF
                    height = int.from_bytes(head[28:30], "little") & 0x3FFF
                    return width, height
            if head.lstrip()[:5] == b"<svg " or b"<svg" in head[:200]:
                text = path.read_text(encoding="utf-8", errors="ignore")[:600]
                import re

                wm = re.search(r'viewBox="[\d.\s]*?([\d.]+)\s+([\d.]+)"', text)
                if wm:
                    return int(float(wm.group(1))), int(float(wm.group(2)))
    except (OSError, struct.error, ValueError):
        return None
    return None


def scan() -> list[dict]:
    rows = []
    if not PICTURE_DIR.exists():
        return rows
    for path in sorted(PICTURE_DIR.iterdir()):
        if path.suffix.lower() not in EXTS or not path.is_file():
            continue
        size = image_size(path)
        ratio = (size[0] / size[1]) if size and size[1] else 0
        ok = bool(size) and abs(ratio - TARGET_RATIO) < 0.02
        rows.append(
            {
                "name": path.name,
                "size": size,
                "ratio": round(ratio, 3),
                "ok": ok,
                "kb": round(path.stat().st_size / 1024, 1),
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# 导入
# --------------------------------------------------------------------------- #
def import_from_dir(src: str) -> int:
    source = Path(src)
    if not source.exists():
        print(f"[错误] 目录不存在：{source}", file=sys.stderr)
        return 1
    PICTURE_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(source.rglob("*")):
        if path.suffix.lower() not in EXTS or not path.is_file():
            continue
        target = PICTURE_DIR / path.name
        index = 1
        while target.exists():
            target = PICTURE_DIR / f"{path.stem}-{index}{path.suffix}"
            index += 1
        shutil.copy2(path, target)
        count += 1
        print(f"  导入 {target.name}")
    print(f"共导入 {count} 个文件到 {PICTURE_DIR}")
    return 0


def import_from_urls(urls: str) -> int:
    PICTURE_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for index, url in enumerate([u.strip() for u in urls.split(",") if u.strip()], start=1):
        suffix = Path(url.split("?")[0]).suffix.lower()
        if suffix not in EXTS:
            suffix = ".jpg"
        target = PICTURE_DIR / f"nailong-{index:02d}{suffix}"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=25) as resp:
                target.write_bytes(resp.read())
            print(f"  下载 {target.name}  ({round(target.stat().st_size / 1024, 1)} KB)")
            count += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  [失败] {url} - {exc}", file=sys.stderr)
    print(f"共下载 {count} 个文件到 {PICTURE_DIR}")
    return 0


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #
def write_manifest() -> int:
    names = [row["name"] for row in scan()]
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    body = "// 由 scripts/fetch_pictures.py --manifest 自动生成，请勿手改\n"
    body += "window.MCD_PICTURES = " + json.dumps([f"../picture/{n}" for n in names], ensure_ascii=False, indent=2) + ";\n"
    MANIFEST.write_text(body, encoding="utf-8")
    print(f"已写入 {MANIFEST}（{len(names)} 张）")
    if not names:
        print("提示：picture/ 为空，Demo 将使用内置占位图。")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="奶龙素材导入 / 体检 / 清单")
    parser.add_argument("--scan", action="store_true", help="列出图片并检查是否为 16:9")
    parser.add_argument("--from-dir", default="", help="从本地目录批量导入")
    parser.add_argument("--urls", default="", help="从直链批量下载，逗号分隔")
    parser.add_argument("--manifest", action="store_true", help="生成 demo/picture-manifest.js")
    args = parser.parse_args(argv)

    if args.from_dir:
        return import_from_dir(args.from_dir)
    if args.urls:
        return import_from_urls(args.urls)
    if args.manifest:
        return write_manifest()

    rows = scan()
    if not rows:
        print(f"picture/ 为空（{PICTURE_DIR}）。")
        print("把 16:9 奶龙梗图放进去，或参考 picture/README.md 用 AI 生成。")
        return 0
    print(f"{'文件':<28}{'尺寸':<14}{'比例':<10}{'大小':<10}状态")
    print("-" * 74)
    for row in rows:
        size = f"{row['size'][0]}x{row['size'][1]}" if row["size"] else "未知"
        flag = "16:9 OK" if row["ok"] else "非 16:9（会被裁切）"
        print(f"{row['name']:<28}{size:<14}{row['ratio']:<10}{str(row['kb']) + 'KB':<10}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
