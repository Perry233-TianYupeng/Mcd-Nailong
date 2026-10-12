#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""功能一：每日自动领取全部优惠券。

流程
----
now-time-info → campaign-calendar → available-coupons → auto-bind-coupons → my-coupons
最后输出「战报」：今日领到几张、卡包里有什么、哪些快过期、今天有什么活动。

用法
----
    python daily_coupons.py                 # 真实调用
    python daily_coupons.py --dry-run       # 只看有哪些券可领，不真的领
    python daily_coupons.py --mock          # 无 Token 离线跑通
    python daily_coupons.py --json          # 给上游 Agent 消费的结构化输出
    python daily_coupons.py --force         # 忽略"今天已领过"的幂等保护，强制再领一次

幂等
----
默认当天只跑一次（状态记录在 scripts/.mcd_state.json），避免重复请求触发限流。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcd_mcp import McdMcpError, McdMcpClient  # noqa: E402
from mcd_schema import normalize_coupons  # noqa: E402

STATE_FILE = Path(__file__).resolve().parent / ".mcd_state.json"
WARN_DAYS = 3


# --------------------------------------------------------------------------- #
# 状态
# --------------------------------------------------------------------------- #
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_state(state: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def collect(client: McdMcpClient, dry_run: bool = False) -> dict:
    today = dt.date.today().isoformat()

    server_time = client.now()
    today = str(server_time.get("date") or today)

    campaigns_all = normalize_campaigns(client.campaign_calendar())
    today_campaigns = [c for c in campaigns_all if c.get("date") == today]
    upcoming = [c for c in campaigns_all if c.get("date", "") > today][:3]

    available = normalize_coupons(client.available_coupons())

    bound: list[dict] = []
    bind_message = ""
    if dry_run or not available:
        bind_message = "（试运行，未实际领取）" if dry_run else "当前没有可领取的券"
    else:
        raw = client.auto_bind_coupons()
        if isinstance(raw, dict):
            bind_message = str(raw.get("message") or raw.get("msg") or "")
            bound = normalize_coupons(raw) or available
        if not bound:
            bound = available

    wallet = normalize_coupons(client.my_coupons())
    expiring = [c for c in wallet if _days_left(c.get("expire"), today) is not None and _days_left(c.get("expire"), today) <= WARN_DAYS]
    expiring.sort(key=lambda c: c.get("expire", ""))

    return {
        "date": today,
        "serverTime": server_time,
        "todayCampaigns": today_campaigns,
        "upcomingCampaigns": upcoming,
        "available": available,
        "bound": bound,
        "wallet": wallet,
        "expiring": expiring,
        "bindMessage": bind_message,
        "dryRun": dry_run,
        "apiCalls": client.call_count,
    }


def normalize_campaigns(raw) -> list[dict]:
    payload = raw if isinstance(raw, dict) else {}
    rows = payload.get("campaigns") or payload.get("list") or payload.get("items") or []
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "date": str(row.get("date") or row.get("startDate") or "")[:10],
                "title": str(row.get("title") or row.get("name") or ""),
                "desc": str(row.get("desc") or row.get("description") or ""),
            }
        )
    out.sort(key=lambda c: c["date"])
    return out


def _days_left(expire: str, today: str) -> int | None:
    if not expire:
        return None
    text = str(expire)[:10].replace("/", "-")
    try:
        end = dt.date.fromisoformat(text)
        start = dt.date.fromisoformat(today)
    except ValueError:
        return None
    return (end - start).days


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #
def render(report: dict) -> str:
    lines: list[str] = []
    bar = "─" * 46
    lines.append(f"┌{bar}┐")
    lines.append(f"│ 🍟 麦麦每日领券战报   {report['date']:<22}│")
    lines.append(f"└{bar}┘")

    if report["dryRun"]:
        lines.append("模式：试运行（未实际领取）")

    lines.append("")
    lines.append(f"① 今日活动  ({len(report['todayCampaigns'])} 条)")
    if report["todayCampaigns"]:
        for c in report["todayCampaigns"]:
            lines.append(f"   · {c['title']} — {c['desc']}")
    else:
        lines.append("   · 今天暂无专属活动")

    lines.append("")
    if report["bound"]:
        lines.append(f"② 本次领取  {len(report['bound'])} 张")
        for c in report["bound"]:
            lines.append(f"   ✓ {c['name']}" + (f"（{c['scope']}）" if c["scope"] else ""))
    else:
        lines.append(f"② 本次领取  —  {report['bindMessage']}")
        if report["available"]:
            lines.append(f"   可领取 {len(report['available'])} 张：")
            for c in report["available"]:
                lines.append(f"   · {c['name']}")

    lines.append("")
    lines.append(f"③ 我的卡包  共 {len(report['wallet'])} 张")
    for c in report["wallet"][:8]:
        left = _days_left(c.get("expire"), report["date"])
        suffix = f"  剩 {left} 天" if left is not None else ""
        lines.append(f"   · {c['name']}{suffix}")

    if report["expiring"]:
        lines.append("")
        lines.append(f"⚠️ 临期提醒  {len(report['expiring'])} 张将在 {WARN_DAYS} 天内过期")
        for c in report["expiring"]:
            lines.append(f"   ! {c['name']}  {c['expire']}")

    if report["upcomingCampaigns"]:
        lines.append("")
        lines.append("④ 近期预告")
        for c in report["upcomingCampaigns"]:
            lines.append(f"   · {c['date']}  {c['title']}")

    lines.append("")
    lines.append(f"[MCP 调用 {report['apiCalls']} 次]")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="每日自动领取麦当劳全部优惠券")
    parser.add_argument("--mock", action="store_true", help="使用内置假数据（无需 Token）")
    parser.add_argument("--dry-run", action="store_true", help="只查询不领取")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--force", action="store_true", help="忽略当日幂等保护")
    args = parser.parse_args(argv)

    state = load_state()
    today = dt.date.today().isoformat()
    if not args.force and not args.mock and state.get("lastCouponRun") == today:
        print(f"今天（{today}）已经领过券了。如需强制再领一次，加 --force。")
        if state.get("lastReport"):
            print(state["lastReport"])
        return 0

    try:
        client = McdMcpClient(mock=args.mock)
        report = collect(client, dry_run=args.dry_run)
    except McdMcpError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2

    text = render(report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(text)

    if not args.dry_run and not args.mock:
        state["lastCouponRun"] = report["date"]
        state["lastReport"] = text
        save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
