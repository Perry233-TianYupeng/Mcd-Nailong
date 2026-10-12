#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线假数据，用于在没有 MCP Token 的情况下跑通全流程 / 单元验证 / Demo。

真实 MCP 服务（https://mcp.mcd.cn）的字段名以官方为准；本项目所有消费点都走了
``mcd_mcp.normalize_*`` 兼容层，字段有出入时改这里的映射即可。
"""
from __future__ import annotations

import datetime as _dt
import json
import random
from pathlib import Path
from typing import Any

# 假订单状态要跨进程可见：create 与 watch 是两次独立调用，只存内存会让 watch 查不到单
MOCK_STATE_FILE = Path(__file__).resolve().parent / ".mcd_mock_orders.json"

# --------------------------------------------------------------------------- #
# 菜单（价格与品类为参考值，真实价格一律以 MCP 实时查询为准）
# --------------------------------------------------------------------------- #
MENU: list[dict[str, Any]] = [
    # 汉堡
    {"code": "B001", "name": "巨无霸", "price": 26.0, "category": "burger", "tags": ["牛", "不辣", "大份"], "kcal": 550, "protein": 25, "satiety": 1.0},
    {"code": "B002", "name": "麦辣鸡腿堡", "price": 22.5, "category": "burger", "tags": ["鸡", "辣", "大份"], "kcal": 500, "protein": 23, "satiety": 0.95},
    {"code": "B003", "name": "板烧鸡腿堡", "price": 23.5, "category": "burger", "tags": ["鸡", "不辣", "大份"], "kcal": 470, "protein": 24, "satiety": 0.95},
    {"code": "B004", "name": "双层吉士汉堡", "price": 19.0, "category": "burger", "tags": ["牛", "不辣", "中份"], "kcal": 440, "protein": 22, "satiety": 0.85},
    {"code": "B005", "name": "吉士汉堡", "price": 13.5, "category": "burger", "tags": ["牛", "不辣", "小份"], "kcal": 300, "protein": 15, "satiety": 0.6},
    {"code": "B006", "name": "麦香鸡", "price": 12.5, "category": "burger", "tags": ["鸡", "不辣", "小份"], "kcal": 320, "protein": 14, "satiety": 0.6},
    {"code": "B007", "name": "麦香鱼", "price": 14.5, "category": "burger", "tags": ["鱼", "不辣", "小份"], "kcal": 330, "protein": 15, "satiety": 0.6},
    {"code": "B008", "name": "不素之霸", "price": 25.0, "category": "burger", "tags": ["牛", "辣", "大份"], "kcal": 610, "protein": 30, "satiety": 1.05},
    {"code": "B009", "name": "麦辣鸡翅（2块）", "price": 13.0, "category": "side", "tags": ["鸡", "辣", "小份"], "kcal": 230, "protein": 12, "satiety": 0.35},
    {"code": "B010", "name": "那么大鸡排", "price": 16.0, "category": "side", "tags": ["鸡", "辣", "中份"], "kcal": 300, "protein": 16, "satiety": 0.5},
    # 小食
    {"code": "S001", "name": "中薯条", "price": 12.5, "category": "side", "tags": ["素", "不辣", "小份"], "kcal": 340, "protein": 4, "satiety": 0.4},
    {"code": "S002", "name": "大薯条", "price": 15.0, "category": "side", "tags": ["素", "不辣", "中份"], "kcal": 420, "protein": 5, "satiety": 0.5},
    {"code": "S003", "name": "麦乐鸡（5块）", "price": 13.0, "category": "side", "tags": ["鸡", "不辣", "小份"], "kcal": 250, "protein": 14, "satiety": 0.4},
    {"code": "S004", "name": "玉米杯", "price": 9.5, "category": "side", "tags": ["素", "不辣", "小份"], "kcal": 120, "protein": 4, "satiety": 0.25},
    {"code": "S005", "name": "苹果片", "price": 8.0, "category": "side", "tags": ["素", "不辣", "小份"], "kcal": 35, "protein": 0, "satiety": 0.1},
    # 饮品
    {"code": "D001", "name": "中杯可乐", "price": 9.5, "category": "drink", "tags": ["冷", "素"], "kcal": 150, "protein": 0, "satiety": 0.2},
    {"code": "D002", "name": "大杯可乐", "price": 11.0, "category": "drink", "tags": ["冷", "素"], "kcal": 210, "protein": 0, "satiety": 0.25},
    {"code": "D003", "name": "中杯雪碧", "price": 9.5, "category": "drink", "tags": ["冷", "素"], "kcal": 140, "protein": 0, "satiety": 0.2},
    {"code": "D004", "name": "热美式", "price": 12.0, "category": "drink", "tags": ["热", "素"], "kcal": 5, "protein": 0, "satiety": 0.05},
    {"code": "D005", "name": "热拿铁", "price": 16.0, "category": "drink", "tags": ["热", "素", "奶"], "kcal": 130, "protein": 7, "satiety": 0.2},
    {"code": "D006", "name": "矿泉水", "price": 6.0, "category": "drink", "tags": ["素"], "kcal": 0, "protein": 0, "satiety": 0.05},
    # 甜品
    {"code": "T001", "name": "圆筒冰淇淋", "price": 6.0, "category": "dessert", "tags": ["冷", "素", "甜"], "kcal": 160, "protein": 3, "satiety": 0.15},
    {"code": "T002", "name": "奥利奥麦旋风", "price": 12.5, "category": "dessert", "tags": ["冷", "素", "甜"], "kcal": 300, "protein": 5, "satiety": 0.25},
    {"code": "T003", "name": "香芋派", "price": 8.5, "category": "dessert", "tags": ["热", "素", "甜"], "kcal": 220, "protein": 3, "satiety": 0.2},
    # 套餐
    {"code": "C001", "name": "巨无霸中套餐", "price": 39.5, "category": "set", "tags": ["牛", "不辣", "大份"], "kcal": 1040, "protein": 30, "satiety": 1.6},
    {"code": "C002", "name": "麦辣鸡腿堡中套餐", "price": 36.0, "category": "set", "tags": ["鸡", "辣", "大份"], "kcal": 990, "protein": 28, "satiety": 1.55},
    {"code": "C003", "name": "板烧鸡腿堡中套餐", "price": 37.0, "category": "set", "tags": ["鸡", "不辣", "大份"], "kcal": 960, "protein": 29, "satiety": 1.55},
    {"code": "C004", "name": "双层吉士中套餐", "price": 33.5, "category": "set", "tags": ["牛", "不辣", "大份"], "kcal": 930, "protein": 26, "satiety": 1.45},
    {"code": "C005", "name": "1+1 随心配", "price": 13.9, "category": "set", "tags": ["混搭", "小份"], "kcal": 450, "protein": 13, "satiety": 0.8},
    {"code": "C006", "name": "麦乐鸡分享盒", "price": 32.0, "category": "set", "tags": ["鸡", "不辣", "大份"], "kcal": 780, "protein": 38, "satiety": 1.2},
]

STORES = [
    {"storeCode": "S001", "beCode": "BE1001", "beType": 1, "takeWayCode": "TW01", "name": "麦当劳（南京东路店）", "address": "上海市黄浦区南京东路 300 号", "distance": 320, "businessHours": "07:00-23:00", "dineModes": ["dine_in", "take_out", "delivery"]},
    {"storeCode": "S002", "beCode": "BE1002", "beType": 1, "takeWayCode": "TW01", "name": "麦当劳（人民广场店）", "address": "上海市黄浦区西藏中路 268 号", "distance": 780, "businessHours": "24小时", "dineModes": ["dine_in", "take_out", "delivery"]},
    {"storeCode": "S003", "beCode": "BE1003", "beType": 1, "takeWayCode": "TW01", "name": "麦当劳（陆家嘴环路店）", "address": "上海市浦东新区陆家嘴环路 1000 号", "distance": 1500, "businessHours": "07:00-22:30", "dineModes": ["dine_in", "take_out"]},
]

DELIVERY_ADDRESSES = [
    {"addressId": "ADDR001", "storeCode": "S001", "beCode": "BE1001", "detail": "上海市黄浦区南京东路 300 号 12 楼", "isDefault": True, "contactName": "张先生"},
    {"addressId": "ADDR002", "storeCode": "S002", "beCode": "BE1002", "detail": "上海市黄浦区西藏中路 268 号 8 楼", "isDefault": False, "contactName": "张先生"},
]

CAMPAIGNS = [
    {"date": "2026-10-12", "title": "周一会员日", "desc": "任意套餐立减 5 元，会员专享"},
    {"date": "2026-10-13", "title": "麦麦省上新", "desc": "9.9 元专区上新，麦辣鸡翅 2 块 9.9 元"},
    {"date": "2026-10-14", "title": "麦乐送日", "desc": "外送满 39 元免配送费"},
    {"date": "2026-10-16", "title": "周末全家桶", "desc": "双人套餐买一送一"},
    {"date": "2026-10-20", "title": "早餐周", "desc": "早餐时段咖啡 + 派 12 元起"},
]

AVAILABLE_COUPONS = [
    {"couponId": "CP001", "name": "满 30 元减 5 元", "threshold": 30, "discount": 5, "expireDate": "2026-10-31", "scope": "全场"},
    {"couponId": "CP002", "name": "麦辣鸡腿堡第二份半价", "threshold": 0, "discount": 11.25, "expireDate": "2026-10-20", "scope": "麦辣鸡腿堡"},
    {"couponId": "CP003", "name": "中薯条 1 元购", "threshold": 20, "discount": 11.5, "expireDate": "2026-10-18", "scope": "中薯条"},
    {"couponId": "CP004", "name": "圆筒冰淇淋免费券", "threshold": 15, "discount": 6, "expireDate": "2026-10-15", "scope": "圆筒冰淇淋"},
    {"couponId": "CP005", "name": "巨无霸立减 5 元", "threshold": 0, "discount": 5, "expireDate": "2026-10-25", "scope": "巨无霸"},
    {"couponId": "CP006", "name": "外送免配送费", "threshold": 39, "discount": 9, "expireDate": "2026-11-30", "scope": "麦乐送"},
]

HISTORY_ORDERS = [
    {"orderId": "H20261001", "date": "2026-10-01", "items": [{"name": "麦辣鸡腿堡", "qty": 1}, {"name": "中薯条", "qty": 1}, {"name": "中杯可乐", "qty": 1}], "payPrice": 44.5},
    {"orderId": "H20261003", "date": "2026-10-03", "items": [{"name": "巨无霸", "qty": 2}, {"name": "大薯条", "qty": 1}], "payPrice": 65.0},
    {"orderId": "H20261005", "date": "2026-10-05", "items": [{"name": "双层吉士汉堡", "qty": 1}, {"name": "热美式", "qty": 1}], "payPrice": 31.0},
    {"orderId": "H20261007", "date": "2026-10-07", "items": [{"name": "麦辣鸡翅（2块）", "qty": 2}, {"name": "中杯雪碧", "qty": 1}], "payPrice": 34.5},
    {"orderId": "H20261009", "date": "2026-10-09", "items": [{"name": "板烧鸡腿堡", "qty": 1}, {"name": "玉米杯", "qty": 1}], "payPrice": 33.0},
    {"orderId": "H20261010", "date": "2026-10-10", "items": [{"name": "1+1 随心配", "qty": 1}], "payPrice": 13.9},
]

MOCK_TOOLS = [
    {"name": "now-time-info", "description": "获取服务器当前时间（用于活动判断）"},
    {"name": "query-nearby-stores", "description": "查询附近麦当劳门店"},
    {"name": "query-meals", "description": "查询门店在售餐品列表"},
    {"name": "query-meal-detail", "description": "查询餐品详情"},
    {"name": "calculate-price", "description": "计算订单金额、优惠与总价"},
    {"name": "create-order", "description": "创建订单并返回支付链接"},
    {"name": "query-order", "description": "查询订单状态与取餐号"},
    {"name": "query-store-coupons", "description": "查询门店可用优惠券"},
    {"name": "available-coupons", "description": "查询可领取的优惠券"},
    {"name": "auto-bind-coupons", "description": "一键领取全部可用优惠券"},
    {"name": "my-coupons", "description": "查询我的卡包"},
    {"name": "campaign-calendar", "description": "查询月度营销活动日历"},
    {"name": "list-nutrition-foods", "description": "查询餐品营养成分"},
    {"name": "delivery-query-addresses", "description": "查询配送地址"},
]

def _load_orders() -> dict[str, dict]:
    if not MOCK_STATE_FILE.exists():
        return {}
    try:
        raw = json.loads(MOCK_STATE_FILE.read_text(encoding="utf-8"))
        return {key: {"created": _dt.datetime.fromisoformat(value["created"])} for key, value in raw.items()}
    except (json.JSONDecodeError, OSError, KeyError, ValueError):
        return {}


def _save_orders() -> None:
    try:
        data = {
            key: {"created": value["created"].isoformat()}
            for key, value in list(_ORDER_STORE.items())[-50:]
        }
        MOCK_STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


_ORDER_STORE: dict[str, dict] = _load_orders()
_rng = random.Random(20261012)


def _best_coupon(subtotal: float, names: str = "") -> dict | None:
    """按门槛 + 适用范围挑一张最优券（尽量贴近真实服务的判定逻辑）。"""
    best: dict | None = None
    for coupon in AVAILABLE_COUPONS:
        if subtotal < coupon["threshold"]:
            continue
        scope = coupon.get("scope") or ""
        if scope and scope != "全场":
            if scope not in names:
                continue
            if coupon["couponId"] == "CP002" and names.count("麦辣鸡腿堡") < 2:
                continue
        if best is None or coupon["discount"] > best["discount"]:
            best = coupon
    return best


def _price(args: dict) -> dict:
    """按官方契约算价：``items[].productCode / quantity``，``orderType`` 1=到店 2=外送。"""
    lines = []
    subtotal = 0.0
    for entry in args.get("items") or []:
        if not isinstance(entry, dict):
            continue
        code = entry.get("productCode") or entry.get("mealCode") or entry.get("code")
        try:
            qty = int(entry.get("quantity", entry.get("qty", 1)) or 1)
        except (TypeError, ValueError):
            qty = 1
        found = next((m for m in MENU if m["code"] == code), None)
        if not found:
            continue
        amount = round(found["price"] * qty, 2)
        subtotal += amount
        lines.append(
            {"productCode": code, "name": found["name"], "quantity": qty, "price": found["price"], "amount": amount}
        )

    subtotal = round(subtotal, 2)
    coupon = _best_coupon(subtotal, " ".join(line["name"] for line in lines))
    discount = round(coupon["discount"], 2) if coupon else 0.0

    order_type = int(args.get("orderType") or 1)
    is_delivery = order_type == 2
    delivery_fee = 9.0 if is_delivery else 0.0
    if is_delivery and subtotal >= 39:
        delivery_fee = 0.0
    pay = round(max(subtotal - discount, 0) + delivery_fee, 2)

    store = next((s for s in STORES if s["storeCode"] == args.get("storeCode")), STORES[0])
    return {
        "storeCode": args.get("storeCode"),
        "beCode": args.get("beCode") or store["beCode"],
        "orderType": order_type,
        "beType": args.get("beType") or store["beType"],
        "takeWayCode": args.get("takeWayCode") or store["takeWayCode"],
        "items": lines,
        "totalPrice": subtotal,
        "subtotal": subtotal,
        "discountAmount": discount,
        "deliveryFee": delivery_fee,
        "payPrice": pay,
        "realTotalAmount": pay,
        "appliedCoupons": [coupon] if coupon else [],
    }


def mock_call(name: str, args: dict) -> Any:
    """按工具名返回假数据。"""
    if name == "now-time-info":
        now = _dt.datetime.now()
        return {
            "timestamp": int(now.timestamp()),
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()],
        }

    if name == "query-nearby-stores":
        return {"stores": STORES}

    if name == "query-meals":
        return {"storeCode": args.get("storeCode", "S001"), "meals": MENU}

    if name == "query-meal-detail":
        code = args.get("mealCode") or args.get("code")
        for item in MENU:
            if item["code"] == code:
                return {"meal": {**item, "desc": f"{item['name']}，参考热量 {item['kcal']} kcal"}}
        return {"meal": None}

    if name == "calculate-price":
        return _price(args)

    if name == "create-order":
        order_id = f"MO{_rng.randint(10**7, 10**8 - 1)}"
        _ORDER_STORE[order_id] = {"created": _dt.datetime.now(), "picked": False}
        _save_orders()
        return {
            "orderId": order_id,
            "payId": f"PAY{order_id}",
            "orderStatus": "PENDING_PAYMENT",
            "orderStatusTitle": "待支付",
            "orderStatusSubTitle": "15 分钟内未支付将自动取消订单",
            "leftPaySecond": 899,
            # 2026-04 起官方支付链接改为扫码支付页，不再提供网页收银台
            "payH5Url": f"https://m.mcd.cn/mcp/scanToPay?orderId={order_id}",
            "beCode": args.get("beCode"),
            "orderType": args.get("orderType"),
            "beType": args.get("beType"),
        }

    if name == "query-order":
        order_id = args.get("orderId") or ""
        state = _ORDER_STORE.get(order_id)
        if not state:
            return {"orderId": order_id, "status": "NOT_FOUND", "orderStatusTitle": "未找到订单", "pickupNumber": None}
        elapsed = (_dt.datetime.now() - state["created"]).total_seconds()
        if elapsed < 6:
            status, title, left = "PENDING_PAYMENT", "待支付", max(899 - int(elapsed), 0)
        elif elapsed < 22:
            status, title, left = "PREPARING", "制作中", 0
        elif elapsed < 40:
            status, title, left = "READY", "餐品已就绪，请取餐", 0
        else:
            status, title, left = "COMPLETED", "已完成", 0
        return {
            "orderId": order_id,
            "status": status,
            "orderStatusTitle": title,
            "leftPaySecond": left,
            "pickupNumber": f"A{abs(hash(order_id)) % 900 + 100}",
            "elapsedSeconds": int(elapsed),
            "storeName": "麦当劳（南京东路店）",
            "payH5Url": f"https://m.mcd.cn/mcp/scanToPay?orderId={order_id}",
        }

    if name == "query-store-coupons":
        return {"storeCode": args.get("storeCode"), "coupons": AVAILABLE_COUPONS[:4]}

    if name == "available-coupons":
        return {"coupons": AVAILABLE_COUPONS}

    if name == "auto-bind-coupons":
        return {
            "success": True,
            "bound": len(AVAILABLE_COUPONS),
            "coupons": AVAILABLE_COUPONS,
            "message": f"已成功领取 {len(AVAILABLE_COUPONS)} 张优惠券",
        }

    if name == "my-coupons":
        return {"coupons": AVAILABLE_COUPONS[:3], "total": 3}

    if name == "campaign-calendar":
        return {"month": "2026-10", "campaigns": CAMPAIGNS}

    if name == "list-nutrition-foods":
        return {"foods": [{"name": m["name"], "kcal": m["kcal"], "protein": m["protein"]} for m in MENU]}

    if name in {"query-my-orders", "order-history"}:
        return {"orders": HISTORY_ORDERS}

    if name == "delivery-query-addresses":
        return {"addresses": DELIVERY_ADDRESSES}

    return {"mock": True, "tool": name, "arguments": args}
