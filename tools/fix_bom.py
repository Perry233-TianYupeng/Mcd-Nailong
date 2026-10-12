#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""去掉文本文件的 UTF-8 BOM。

BOM 会让 SKILL.md 的 frontmatter 解析失败（平台报 `---` 不在开头），
也会让 audit 判「字段缺失」。用 PowerShell 的 `Set-Content -Encoding UTF8` 改文件就会中招。

    python tools/fix_bom.py            # 体检 + 修复
    python tools/fix_bom.py --check    # 只体检
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUFFIXES = {".md", ".json", ".js", ".py", ".html", ".svg", ".txt", ".yml", ".yaml"}
SKIP_DIRS = {".git", ".workbuddy", "out", "node_modules", "__pycache__"}
BOM = b"\xef\xbb\xbf"


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    dirty: list[Path] = []

    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        raw = path.read_bytes()
        if raw.startswith(BOM):
            dirty.append(path)
            if not check_only:
                path.write_bytes(raw[len(BOM):])

    if not dirty:
        print("未发现 BOM，文件编码干净。")
        return 0

    for path in dirty:
        print(f"  {'[需修复]' if check_only else '[已修复]'} {path.relative_to(ROOT)}")
    print(f"\n共 {len(dirty)} 个文件带 BOM" + ("（加 --check 之外不带参数即修复）" if check_only else "，已全部去除"))
    return 1 if check_only else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
