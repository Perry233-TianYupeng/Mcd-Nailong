#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键自检：不需要 MCP Token，全部用内置假数据跑通三条能力 + 下单闭环。

    python tests/selfcheck.py

覆盖：
  1. MCP 客户端与工具清单
  2. 每日领券战报
  3. 抽卡（答题 / 读历史订单两条路径）
  4. 名片卡生成（抽卡名片 / 消费名片）
  5. 穷鬼预算锁（3 套方案、实付不超预算、消费等级边界）
  6. 下单闭环（门店 → 算价 → 建单 → 支付提示 → 到号提醒）
  7. 打包结构自查：包内文件深度不得超过 1 层（__pycache__ 陷阱）

退出码 0 = 全部通过。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PY = sys.executable

# 打包时不算作交付内容的目录
SKIP_DIRS = {".git", ".workbuddy", "out", "node_modules", "__pycache__", ".venv", "venv"}

results: list[tuple[str, bool, str]] = []


def run(args: list[str], timeout: int = 120) -> tuple[int, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    proc = subprocess.run(
        [PY, *args],
        cwd=str(ROOT),
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    text = (proc.stdout or b"").decode("utf-8", "replace") + (proc.stderr or b"").decode("utf-8", "replace")
    return proc.returncode, text


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail.replace("\n", " ")[:120]))
    flag = "PASS" if ok else "FAIL"
    print(f"  [{flag}] {name}" + (f"   -> {detail.strip()[:110]}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{title}")
    print("-" * 62)


REQUIRED_FIELDS = ("description", "description_zh", "description_en", "version", "author")

TEXT_SUFFIXES = {".md", ".json", ".js", ".cjs", ".py", ".html", ".svg", ".txt", ".yaml", ".yml"}
# GBK 往返损坏后的典型残字，正常中文里几乎不会出现。
# 用码点定义而不是字面量，否则本文件自己就会命中。
MOJIBAKE_MARKS = tuple(chr(cp) for cp in (
    0xFFFD,  # 替换字符
    0x951F, 0x9520, 0x9225, 0x9279, 0x951B, 0x6D93, 0x6374, 0x935C, 0x9259,
))
ENCODING_SKIP = {".git", ".workbuddy", "out", "node_modules", "__pycache__", "docs"}


def _encoding_issues() -> tuple[list[str], list[str]]:
    """返回 (带 BOM 的文件, 疑似乱码的文件)。"""
    bom_files: list[str] = []
    mojibake: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(ROOT)
        if any(part in ENCODING_SKIP for part in rel.parts):
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            bom_files.append(str(rel))
        text = raw.decode("utf-8", "replace")
        if any(mark in text for mark in MOJIBAKE_MARKS):
            mojibake.append(str(rel))
    return bom_files, mojibake


def _frontmatter_ok() -> bool:
    """SKILL.md frontmatter 是否含平台要求的必填字段（缺任一即会被上传闸门拦下）。"""
    path = ROOT / "SKILL.md"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end == -1:
        return False
    keys = {
        line.split(":", 1)[0].strip()
        for line in text[3:end].splitlines()
        if line[:1] not in (" ", "\t") and ":" in line
    }
    return all(field in keys for field in REQUIRED_FIELDS)


def main() -> int:
    print("=" * 62)
    print("麦麦奶龙 · 一键自检（离线，无需 Token）")
    print("=" * 62)
    tmp = Path(tempfile.mkdtemp(prefix="mcd-selfcheck-"))
    quiz_json = tmp / "quiz.json"

    # ---------------------------------------------------------------- 1
    section("[1] MCP 客户端")
    code, out = run([str(SCRIPTS / "mcd_mcp.py"), "list", "--mock"])
    check("工具清单可列出", code == 0 and "now-time-info" in out, f"{len(out.splitlines())} 行")
    check("工具数 >= 14", out.count("\n- ") >= 14)

    code, out = run([str(SCRIPTS / "mcd_mcp.py"), "ask", "query-meals", "storeCode=S001", "--mock"])
    check("单工具调用可用", code == 0 and "巨无霸" in out)

    # ---------------------------------------------------------------- 2
    section("[2] 每日自动领券")
    code, out = run([str(SCRIPTS / "daily_coupons.py"), "--mock"])
    check("战报已生成", code == 0 and "本次领取" in out)
    check("含临期提醒", "临期提醒" in out or "剩" in out)
    check("含今日活动", "今日活动" in out)

    code, out = run([str(SCRIPTS / "daily_coupons.py"), "--mock", "--dry-run"])
    check("试运行不实际领取", "试运行" in out)

    # ---------------------------------------------------------------- 3
    section("[3] 麦麦奶龙抽卡")
    code, out = run(
        [str(SCRIPTS / "quiz_engine.py"), "--mock", "--answers", "1A,2B,3A,4C,5B,6C,7A,8A,9A,10D",
         "--out", str(quiz_json)]
    )
    check("答题路径出结果", code == 0 and "堡格" in out)
    names = re.findall(r"名片名：(.+)", out)
    check("名片名格式 {性格}+{堡格}+奶龙", bool(names) and names[0].strip().endswith("奶龙"),
          names[0].strip() if names else "未找到")
    check("含四轴画像", all(k in out for k in ("辣度", "食量", "决策", "社交")))
    check("结果 JSON 已落盘", quiz_json.exists())

    code, out = run([str(SCRIPTS / "quiz_engine.py"), "--mock", "--history"])
    check("历史订单路径出结果", code == 0 and "堡格" in out)

    # ---------------------------------------------------------------- 4
    section("[4] 名片卡生成（1600x900）")
    card_svg = tmp / "card-quiz.svg"
    code, out = run([str(SCRIPTS / "card_gen.py"), "--quiz-result", str(quiz_json), "--out", str(card_svg)])
    check("抽卡名片已生成", code == 0 and card_svg.exists())
    check("配套 HTML 已生成", card_svg.with_suffix(".html").exists())
    svg = card_svg.read_text(encoding="utf-8") if card_svg.exists() else ""
    check("画布 1600x900", 'width="1600"' in svg and 'height="900"' in svg)
    check("页脚含仓库地址", "开源仓库" in svg and "github.com" in svg)
    check("占位图已内嵌", "data:image/svg+xml;base64," in svg or "data:image/" in svg)

    code, out = run([str(SCRIPTS / "card_gen.py"), "--budget-pay", "45.5",
                     "--burger", "巨无霸中套餐", "--out", str(tmp / "card-budget.svg")])
    check("消费名片 >40 元 → 豪情在天", code == 0 and "豪情在天" in out, out.splitlines()[0] if out else "")
    code, out = run([str(SCRIPTS / "card_gen.py"), "--budget-pay", "12.0",
                     "--burger", "吉士汉堡", "--out", str(tmp / "card-low.svg")])
    check("消费名片 <25 元 → 节俭度日", code == 0 and "节俭度日" in out)

    # ---------------------------------------------------------------- 5
    section("[5] 穷鬼预算锁（Pareto 求解）")
    cases = [("25", "辣,鸡"), ("15", ""), ("30", "牛"), ("60", "不辣")]
    for budget, taste in cases:
        args = [str(SCRIPTS / "budget_solver.py"), "--budget", budget, "--mock", "--json"]
        if taste:
            args += ["--taste", taste]
        code, out = run(args)
        try:
            import json

            data = json.loads(out)
        except Exception:
            check(f"预算 {budget} {taste or '不限'}", False, out[:90])
            continue
        if not data.get("ok"):
            check(f"预算 {budget} {taste or '不限'}", True, f"无解（可接受）：{data.get('reason', '')[:50]}")
            continue
        plans = data["plans"]
        overspend = [p for p in plans if p["pay"] > float(budget)]
        uniq = {p["signature"] for p in plans}
        check(
            f"预算 {budget} {taste or '不限'}",
            len(plans) == 3 and not overspend and len(uniq) == 3,
            " | ".join(f"{p['tag']} ¥{p['pay']:.2f}" for p in plans),
        )

    code, out = run([str(SCRIPTS / "budget_solver.py"), "--items", "B004:1,S001:1,D001:1",
                     "--budget", "40", "--mock"])
    check("改单复核可用", code == 0 and "消费等级" in out)

    # ---------------------------------------------------------------- 6
    section("[6] 下单闭环与支付")
    code, out = run([str(SCRIPTS / "order_flow.py"), "stores", "--mock"])
    check("门店列表含 beCode", code == 0 and "BE1001" in out)

    code, out = run([str(SCRIPTS / "order_flow.py"), "price", "--mock",
                     "--store", "S001", "--items", "B004:1,S001:1"])
    check("算价含 takeWayCode", code == 0 and "takeWayCode" in out)

    code, out = run([str(SCRIPTS / "order_flow.py"), "create", "--mock",
                     "--store", "S001", "--items", "B004:1,S001:1", "--yes"])
    check("建单返回支付链接", code == 0 and "scanToPay" in out)
    check("明确提示不扣款", "不会扣款" in out)
    check("明确提示自动取消", "自动取消" in out)
    order_ids = re.findall(r"订单已创建：(MO\d+)", out)
    order_id = order_ids[0] if order_ids else ""

    if order_id:
        code, out = run([str(SCRIPTS / "order_flow.py"), "watch", "--mock",
                         "--order", order_id, "--interval", "3", "--timeout", "60"], timeout=90)
        check("到号提醒可触发", "可以取餐了" in out or "取餐号" in out)

    # ---------------------------------------------------------------- 7
    section("[7] 打包结构自查（平台仅支持两级目录）")

    # 字节码缓存在包内深度是 2 层（根/scripts/__pycache__/x.pyc），
    # 会命中平台「目录层级超限」校验，且本地文件系统不会报错 —— 这里直接帮用户清掉。
    removed = 0
    for cache in list(ROOT.rglob("__pycache__")):
        rel = cache.relative_to(ROOT)
        if any(part in {".git", ".workbuddy", "out", "node_modules"} for part in rel.parts):
            continue
        try:
            shutil.rmtree(cache)
            removed += 1
        except OSError:
            pass
    leftover = [
        str(p.relative_to(ROOT)).replace("\\", "/")
        for p in ROOT.rglob("__pycache__")
        if not any(part in {".git", ".workbuddy", "out", "node_modules"} for part in p.relative_to(ROOT).parts)
    ]
    check(
        "字节码缓存已清理（否则平台判「目录层级超限」）",
        not leftover,
        f"本次清理 {removed} 个" if removed else "无残留",
    )

    deep: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if len(rel.parts) > 2:
            deep.append(str(rel).replace("\\", "/"))
    check("包内无超过 1 层的嵌套", not deep, "；".join(deep[:4]))
    check("SKILL.md 在包根", (ROOT / "SKILL.md").exists())
    check("SKILL.md frontmatter 必填字段齐全", _frontmatter_ok(), "description_zh/en + version + author")

    # 编码守卫：PowerShell 的 Get-Content(ANSI/GBK) -> Set-Content(UTF8) 会把中文
    # 变成**不可逆**乱码，且不影响结构校验，极易静默逃逸。这里直接拦。
    bad_bom, bad_text = _encoding_issues()
    check("文本文件无 BOM", not bad_bom, "；".join(bad_bom[:4]))
    check("文本文件无中文乱码", not bad_text, "；".join(bad_text[:4]))

    # ---------------------------------------------------------------- 汇总
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("\n" + "=" * 62)
    print(f"自检结果：{passed}/{total} 通过" + ("  ✅ 全部通过" if passed == total else "  ❌ 存在失败项"))
    print("=" * 62)
    if passed != total:
        print("\n失败项：")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}   {detail}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
