#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下单闭环：选门店 → 改单试算 → 确认下单 → 支付指引 → 到号提醒。

关于支付（重要）
----------------
调用 ``create-order`` **不会扣款**。它只生成一笔「待支付」订单并返回 ``payH5Url``；
真实扣款发生在**用户自己打开该链接完成支付**时。2026-04 起官方支付链接已改为
扫码支付页（``https://m.mcd.cn/mcp/scanToPay?orderId=...``），不再提供网页收银台。
订单在 ``leftPaySecond`` 倒计时内未支付会被自动取消。

安全约定
--------
**任何写操作（下单/领券）都必须显式确认**：命令行要带 ``--yes``，或在交互模式下回车确认。
本项目永远不会静默下单，也不会代替用户付款。

用法
----
    python order_flow.py stores --keyword 南京东路
    python order_flow.py price  --store S001 --items B004:1,S001:1,D001:1
    python order_flow.py create --store S001 --items B004:1,S001:1 --yes
    python order_flow.py pay    --order MO12345678 [--open]
    python order_flow.py watch  --order MO12345678 --interval 8 --timeout 300
    python order_flow.py order  --store S001 --items B004:1,S001:1 --yes --watch
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from budget_solver import parse_items  # noqa: E402
from mcd_mcp import McdMcpError, McdMcpClient  # noqa: E402
from mcd_naming import spend_tier  # noqa: E402
from mcd_schema import (  # noqa: E402
    is_awaiting_payment,
    normalize_order,
    normalize_price,
    normalize_stores,
    status_text,
)

MODE_TEXT = {"dine_in": "到店取餐", "take_out": "外带", "delivery": "麦乐送"}
READY_STATES = {"READY", "COMPLETED"}
PAY_NOTICE = (
    "注意：create-order 只生成一笔「待支付」订单，不会扣款。\n"
    "      请自行打开支付链接完成付款；超时未支付订单会被自动取消。"
)
LOG_FILE = Path(__file__).resolve().parent / ".mcd_orders.json"


def _log_order(record: dict) -> None:
    try:
        data = json.loads(LOG_FILE.read_text(encoding="utf-8")) if LOG_FILE.exists() else []
    except (json.JSONDecodeError, OSError):
        data = []
    data.append(record)
    try:
        LOG_FILE.write_text(json.dumps(data[-50:], ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _beep(times: int = 3) -> None:
    try:
        import winsound  # type: ignore

        for _ in range(times):
            winsound.Beep(880, 220)
            winsound.Beep(1180, 220)
    except Exception:  # noqa: BLE001
        sys.stdout.write("\a")
        sys.stdout.flush()


def _confirm(question: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print("非交互环境请显式加 --yes 确认下单。", file=sys.stderr)
        return False
    answer = input(f"{question} [y/N] ").strip().lower()
    return answer in {"y", "yes"}


# --------------------------------------------------------------------------- #
# 子命令
# --------------------------------------------------------------------------- #
def _resolve_address_id(client: McdMcpClient, store_code: str, explicit: str = "") -> str:
    """麦乐送下单必须带 addressId，只能来自 delivery-query-addresses，不可凭空生成。"""
    if explicit:
        return explicit
    try:
        payload = client.delivery_addresses()
    except McdMcpError:
        return ""
    rows = payload.get("addresses") or payload.get("list") or payload.get("items") or []
    if not isinstance(rows, list) or not rows:
        return ""
    dicts = [r for r in rows if isinstance(r, dict)]
    picked = (
        next((r for r in dicts if store_code and r.get("storeCode") == store_code), None)
        or next((r for r in dicts if r.get("isDefault")), None)
        or (dicts[0] if dicts else None)
    )
    return str((picked or {}).get("addressId") or "")


def cmd_stores(client: McdMcpClient, args) -> int:
    stores = normalize_stores(client.nearby_stores())
    if args.keyword:
        stores = [s for s in stores if args.keyword in s["name"] or args.keyword in s["address"]]
    if not stores:
        print("没有匹配的门店。")
        return 1
    print(f"{'序号':<5}{'门店编码':<11}{'BE编码':<11}{'名称':<26}{'距离':<9}{'营业时间':<13}地址")
    print("-" * 112)
    for index, store in enumerate(stores, start=1):
        distance = f"{store['distance']}m" if store["distance"] else "-"
        print(
            f"{index:<5}{store['code']:<11}{(store.get('beCode') or '-'):<11}"
            f"{store['name']:<26}{distance:<9}{(store['hours'] or '-'):<13}{store['address']}"
        )
    print(f"\n用 --store <门店编码> 指定，例如 --store {stores[0]['code']}")
    print("beCode 已缓存到 scripts/.mcd_stores.json，后续算价/下单会自动带上。")
    return 0


def cmd_price(client: McdMcpClient, args) -> int:
    items = parse_items(args.items)
    price = normalize_price(client.calculate_price(args.store, items, dining_mode=args.mode))
    tier = spend_tier(price["pay"])
    print(f"门店 {args.store}　{MODE_TEXT.get(args.mode, args.mode)}")
    print(f"原价 ¥{price['subtotal']:.2f}　优惠 ¥{price['discount']:.2f}　配送 ¥{price['delivery']:.2f}　→　实付 ¥{price['pay']:.2f}")
    print(f"消费等级：{tier['level']} —— {tier['desc']}")
    if price.get("takeWayCode"):
        print(f"取餐方式码 takeWayCode={price['takeWayCode']}（下单时会自动带上）")
    for coupon in price["coupons"] or []:
        if isinstance(coupon, dict):
            print(f"  已用券：{coupon.get('name') or coupon.get('couponName')}")
    return 0


def cmd_create(client: McdMcpClient, args) -> int:
    items = parse_items(args.items)

    address_id = ""
    if args.mode == "delivery":
        address_id = _resolve_address_id(client, args.store, args.address_id)
        if not address_id:
            print("[错误] 麦乐送下单需要 addressId，但未从 delivery-query-addresses 取到。", file=sys.stderr)
            return 2
    elif args.address_id:
        address_id = args.address_id

    price = normalize_price(client.calculate_price(args.store, items, dining_mode=args.mode))
    tier = spend_tier(price["pay"])
    take_way = price.get("takeWayCode") or ""

    print("─" * 56)
    print(f"门店　　{args.store}")
    print(f"就餐　　{MODE_TEXT.get(args.mode, args.mode)}" + (f"　地址 {address_id}" if address_id else ""))
    print(f"商品　　{args.items}")
    print(f"实付　　¥{price['pay']:.2f}（优惠 ¥{price['discount']:.2f}）")
    print(f"消费等级 {tier['level']}")
    print("─" * 56)
    print(PAY_NOTICE)
    print("─" * 56)

    if not _confirm("确认创建这笔待支付订单？", args.yes):
        print("已取消，未创建订单。")
        return 1

    order = normalize_order(
        client.create_order(
            args.store,
            items,
            dining_mode=args.mode,
            take_way_code=take_way,
            address_id=address_id,
            remark=args.remark,
        )
    )
    _log_order(
        {
            "orderId": order["orderId"],
            "store": args.store,
            "items": args.items,
            "mode": args.mode,
            "pay": price["pay"],
            "tier": tier["level"],
            "payUrl": order["payUrl"],
            "createdAt": dt.datetime.now().isoformat(timespec="seconds"),
        }
    )

    print(f"订单已创建：{order['orderId']}")
    print(f"状态：{order.get('statusTitle') or '待支付'}")
    if order["payUrl"]:
        print(f"支付链接：{order['payUrl']}")
    if order["leftPaySecond"]:
        print(f"请在 {order['leftPaySecond'] // 60} 分钟内完成支付，否则订单会自动取消。")
    print("")
    print("下一步（二选一）：")
    print(f"  用手机打开上面的支付链接完成付款（官方扫码支付页）")
    print(f"  python order_flow.py pay --order {order['orderId']} --open")
    print(f"  付款成功后再蹲号：python order_flow.py watch --order {order['orderId']}")
    return 0


def cmd_pay(client: McdMcpClient, args) -> int:
    url = args.url
    if not url and args.order:
        order = normalize_order(client.query_order(args.order))
        url = order.get("payUrl") or ""
        if order.get("statusTitle"):
            print(f"当前状态：{order['statusTitle']}")
    if not url:
        print("[错误] 没拿到支付链接。请用 --order <订单号> 指定已创建的订单。", file=sys.stderr)
        return 1

    print("支付链接（官方扫码支付页）：")
    print(url)
    print("")
    print("说明：本工具不会替你付款。请在手机浏览器或微信 / 支付宝中打开该链接，")
    print("      确认金额后自行完成支付；未支付订单会在倒计时结束后自动取消。")
    if args.open:
        try:
            webbrowser.open(url)
            print("已在默认浏览器中打开。")
        except Exception as exc:  # noqa: BLE001
            print(f"自动打开失败（{exc}），请手动复制上面的链接。")
    return 0


def cmd_watch(client: McdMcpClient, args) -> int:
    started = time.time()
    last_status = ""
    warned_pay = False
    print(f"开始蹲号：订单 {args.order}，每 {args.interval}s 查一次，最多等 {args.timeout}s")

    while True:
        try:
            order = normalize_order(client.query_order(args.order))
        except McdMcpError as exc:
            print(f"  查询失败（{exc}），{args.interval}s 后重试")
            order = {}

        status = order.get("status", "")
        text, ready = status_text(status)
        stamp = dt.datetime.now().strftime("%H:%M:%S")

        # 待支付订单永远不会进入制作，必须先引导用户付款
        if is_awaiting_payment(status):
            left = order.get("leftPaySecond") or 0
            if not warned_pay or status != last_status:
                print(f"[{stamp}] {text} —— 这笔订单还没付款，不会进入制作。")
                if order.get("payUrl"):
                    print(f"          请在 {left // 60} 分钟内付款，否则订单自动取消：{order['payUrl']}")
                warned_pay = True
            last_status = status
            if time.time() - started > args.timeout:
                print(f"超时（{args.timeout}s）：订单仍在待支付状态，已停止蹲号。")
                return 1
            time.sleep(args.interval)
            continue

        if status != last_status:
            print(f"[{stamp}] {text}" + (f"　取餐号 {order['pickupNumber']}" if order.get("pickupNumber") else ""))
            last_status = status

        if ready:
            print("")
            print("█" * 46)
            print(f"█  🍔 可以取餐了！取餐号：{order.get('pickupNumber') or '见店内屏幕'}")
            print(f"█  订单号：{order.get('orderId') or args.order}")
            print("█" * 46)
            _beep(3)
            return 0

        if time.time() - started > args.timeout:
            print(f"超时（{args.timeout}s）仍未就绪，请手动查询订单 {args.order}。")
            return 1
        time.sleep(args.interval)


def cmd_order(client: McdMcpClient, args) -> int:
    """一条龙：下单 → 可选立即蹲号。"""
    code = cmd_create(client, args)
    if code != 0 or not args.watch:
        return code

    log = json.loads(LOG_FILE.read_text(encoding="utf-8")) if LOG_FILE.exists() else []
    if not log:
        return code
    order_id = log[-1]["orderId"]
    args.order = order_id
    print("")
    return cmd_watch(client, args)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="麦当劳下单闭环（含支付指引与到号提醒）")
    parser.add_argument("command", choices=["stores", "price", "create", "pay", "watch", "order"])
    parser.add_argument("--store", default="S001")
    parser.add_argument("--items", default="", help="如 B004:1,S001:1")
    parser.add_argument("--mode", default="dine_in", choices=["dine_in", "take_out", "delivery"])
    parser.add_argument("--order", default="", help="订单号（pay / watch 用）")
    parser.add_argument("--url", default="", help="直接指定支付链接（pay 用）")
    parser.add_argument("--address-id", default="", help="麦乐送地址 ID，缺省自动从接口取")
    parser.add_argument("--remark", default="", help="订单备注，最多 50 字")
    parser.add_argument("--open", action="store_true", help="pay：用默认浏览器打开支付链接")
    parser.add_argument("--keyword", default="", help="门店关键词过滤")
    parser.add_argument("--interval", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--yes", action="store_true", help="跳过下单确认（非交互环境必填）")
    parser.add_argument("--watch", action="store_true", help="order 子命令：下单后立即蹲号")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args(argv)

    if args.command in {"price", "create", "order"} and not args.items:
        parser.error(f"{args.command} 需要 --items，如 --items B004:1,S001:1")
    if args.command == "watch" and not args.order:
        parser.error("watch 需要 --order <订单号>")
    if args.command == "pay" and not (args.order or args.url):
        parser.error("pay 需要 --order <订单号> 或 --url <支付链接>")

    try:
        client = McdMcpClient(mock=args.mock)
        handler = {
            "stores": cmd_stores,
            "price": cmd_price,
            "create": cmd_create,
            "pay": cmd_pay,
            "watch": cmd_watch,
            "order": cmd_order,
        }[args.command]
        return handler(client, args)
    except McdMcpError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
