#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字段兼容层：把真实 MCP 返回（字段名可能变化）统一成内部结构。

真实服务字段与文档有出入时，**只改这里**，上层脚本无需改动。
"""
from __future__ import annotations

from typing import Any

# 名称关键词 -> 标签
_TAG_RULES: list[tuple[tuple[str, ...], list[str]]] = [
    (("辣", "麻辣", "香辣"), ["辣"]),
    (("鸡",), ["鸡"]),
    (("牛", "巨无霸", "吉士"), ["牛"]),
    (("鱼",), ["鱼"]),
    (("薯", "玉米", "苹果", "派"), ["素"]),
    (("鸡翅", "鸡排", "麦乐鸡"), ["鸡", "炸物"]),
    (("可乐", "雪碧", "美式", "拿铁", "咖啡", "矿泉水", "水"), ["饮"]),
    (("冰淇淋", "麦旋风", "圣代"), ["甜", "冷"]),
    (("套餐", "随心配", "分享盒"), ["套餐"]),
    (("冰", "冷"), ["冷"]),
    (("热", "拿铁", "美式"), ["热"]),
]

_CATEGORY_RULES: list[tuple[tuple[str, ...], str]] = [
    (("套餐", "随心配", "分享盒", "组合", "三件套", "两件套"), "set"),
    (("可乐", "雪碧", "美式", "拿铁", "咖啡", "矿泉水", "水", "茶", "奶昔"), "drink"),
    (("冰淇淋", "麦旋风", "圣代", "派"), "dessert"),
    (("薯条", "薯", "鸡翅", "鸡排", "麦乐鸡", "玉米", "苹果", "沙拉"), "side"),
]

# 品类基准饱腹系数（用于价值评估，纯启发式）
_SATIETY_BASE = {
    "burger": 0.85,
    "set": 1.45,
    "side": 0.35,
    "drink": 0.18,
    "dessert": 0.18,
    "unknown": 0.6,
}

# --------------------------------------------------------------------------- #
# 官方下单契约（来自 https://open.mcd.cn/mcp/doc）
#
# calculate-price / create-order 的必填入参并不是 storeCode + items 这么简单：
#   orderType : 到店=1，外送=2
#   beType    : 1=到店取餐，2=麦乐送，5=得来速(DT)，6=企业团餐
#   beCode    : 门店所属 BE 编码，必须来自 query-nearby-stores / delivery-query-addresses
#   takeWayCode: 到店场景 create-order 必填，来自 calculate-price 的返回
#   addressId : 外送场景 create-order 必填，来自 delivery-query-addresses
#   items[]   : 商品项字段是 productCode + quantity（不是 mealCode + qty）
# --------------------------------------------------------------------------- #
MODE_TO_ORDER_TYPE = {"dine_in": 1, "take_out": 1, "delivery": 2}
MODE_TO_BE_TYPE = {"dine_in": 1, "take_out": 1, "delivery": 2}
BE_TYPE_TEXT = {1: "到店取餐", 2: "麦乐送", 5: "得来速", 6: "企业团餐"}

_ITEM_PASSTHROUGH = ("couponId", "couponCode", "modification", "roundList")


def build_items(items: Any) -> list[dict]:
    """内部商品项 -> 官方 ``items`` 数组。

    兼容三种输入写法，避免上层因为字段名不同而全部重写：
      {"mealCode": "B004", "qty": 1}
      {"code": "B004", "quantity": 1}
      {"productCode": "B004", "quantity": 1}
    """
    out: list[dict] = []
    rows = items if isinstance(items, list) else (items.get("items") if isinstance(items, dict) else [])
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        code = row.get("productCode") or row.get("mealCode") or row.get("code")
        if not code:
            continue
        try:
            qty = int(row.get("quantity", row.get("qty", 1)) or 1)
        except (TypeError, ValueError):
            qty = 1
        item: dict[str, Any] = {"productCode": str(code), "quantity": max(qty, 1)}
        for key in _ITEM_PASSTHROUGH:
            if row.get(key) not in (None, "", [], {}):
                item[key] = row[key]
        out.append(item)
    return out


def order_params(mode: str) -> dict:
    """就餐方式 -> 官方 orderType / beType。"""
    mode = (mode or "dine_in").lower()
    return {
        "orderType": MODE_TO_ORDER_TYPE.get(mode, 1),
        "beType": MODE_TO_BE_TYPE.get(mode, 1),
    }


def detect_mode(order_type: Any, be_type: Any = None) -> str:
    """从官方返回反推就餐方式，用于展示。"""
    try:
        ot = int(order_type)
    except (TypeError, ValueError):
        return "dine_in"
    return "delivery" if ot == 2 else "dine_in"


def derive_tags(name: str, category: str = "") -> list[str]:
    tags: list[str] = []
    for keywords, mapped in _TAG_RULES:
        if any(k in name for k in keywords):
            tags.extend(mapped)
    if category == "set":
        tags.append("套餐")
    seen: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.append(tag)
    return seen


def guess_category(name: str, raw_category: str = "") -> str:
    if raw_category and raw_category.lower() in _SATIETY_BASE:
        return raw_category.lower()
    for keywords, category in _CATEGORY_RULES:
        if any(k in name for k in keywords):
            return category
    if name:
        return "burger"
    return "unknown"


def _first(mapping: dict, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace("元", "").replace("¥", "").strip())
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def normalize_menu(raw: Any) -> list[dict]:
    """统一菜单项结构。"""
    payload = raw if isinstance(raw, dict) else {}
    rows = (
        payload.get("meals")
        or payload.get("items")
        or payload.get("products")
        or payload.get("list")
        or (raw if isinstance(raw, list) else [])
    )
    if isinstance(rows, dict):
        rows = list(rows.values())

    menu: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = str(_first(row, "name", "mealName", "productName", "title", default="") or "").strip()
        code = str(_first(row, "code", "mealCode", "productCode", "sku", "id", default="") or "").strip()
        if not name:
            continue

        price = _to_float(
            _first(row, "price", "salePrice", "currentPrice", "unitPrice", "amount", default=0)
        )
        raw_category = str(_first(row, "category", "categoryName", "type", default="") or "")
        category = guess_category(name, raw_category)
        if category == "burger" and raw_category and raw_category.lower() in _SATIETY_BASE:
            category = raw_category.lower()

        tags = row.get("tags") if isinstance(row.get("tags"), list) else []
        tags = [str(t) for t in tags] + derive_tags(name, category)
        ordered: list[str] = []
        for tag in tags:
            if tag not in ordered:
                ordered.append(tag)

        menu.append(
            {
                "code": code or name,
                "name": name,
                "price": round(price, 2),
                "category": category,
                "tags": ordered,
                "kcal": _to_int(_first(row, "kcal", "calorie", "energy", "calories", default=0)),
                "protein": _to_int(_first(row, "protein", "proteinGram", default=0)),
                "satiety": _to_float(_first(row, "satiety", default=0)) or _SATIETY_BASE.get(category, 0.6),
                "available": bool(_first(row, "available", "onSale", "isAvailable", default=True)),
            }
        )
    return menu


def normalize_coupons(raw: Any) -> list[dict]:
    payload = raw if isinstance(raw, dict) else {}
    rows = payload.get("coupons") or payload.get("list") or payload.get("items") or (raw if isinstance(raw, list) else [])
    if isinstance(rows, dict):
        rows = list(rows.values())

    coupons: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = str(_first(row, "name", "couponName", "title", "desc", "description", default="") or "").strip()
        if not name:
            continue
        coupons.append(
            {
                "id": str(_first(row, "couponId", "id", "code", default="") or ""),
                "name": name,
                "threshold": _to_float(_first(row, "threshold", "minAmount", "condition", default=0)),
                "discount": _to_float(_first(row, "discount", "amount", "discountAmount", "value", default=0)),
                "expire": str(_first(row, "expireDate", "expireTime", "endTime", "validUntil", default="") or ""),
                "scope": str(_first(row, "scope", "useScope", "limitDesc", default="") or ""),
            }
        )
    return coupons


def normalize_stores(raw: Any) -> list[dict]:
    payload = raw if isinstance(raw, dict) else {}
    rows = payload.get("stores") or payload.get("list") or payload.get("items") or (raw if isinstance(raw, list) else [])
    if isinstance(rows, dict):
        rows = list(rows.values())

    stores: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = str(_first(row, "name", "storeName", "shopName", default="") or "").strip()
        code = str(_first(row, "storeCode", "code", "id", "shopCode", default="") or "").strip()
        if not name and not code:
            continue
        stores.append(
            {
                "code": code or name,
                "name": name or code,
                "address": str(_first(row, "address", "addr", "detail", default="") or ""),
                "distance": _to_int(_first(row, "distance", "distanceMeter", default=0)),
                "hours": str(_first(row, "businessHours", "hours", "openTime", default="") or ""),
                "modes": _first(row, "dineModes", "modes", "supportModes", default=["dine_in"]) or ["dine_in"],
                # 下单必需：BE 编码与门店业务类型，必须从门店接口取，不能凭空生成
                "beCode": str(_first(row, "beCode", "be_code", "bizCode", default="") or ""),
                "beType": _to_int(_first(row, "beType", "be_type", default=0)),
                "takeWayCode": str(_first(row, "takeWayCode", "takeWay", "takeWayId", default="") or ""),
                "addressId": str(_first(row, "addressId", "addrId", default="") or ""),
            }
        )
    return stores


def normalize_price(raw: Any) -> dict:
    payload = raw if isinstance(raw, dict) else {}
    subtotal = _to_float(_first(payload, "subtotal", "originalPrice", "totalPrice", "total", default=0))
    discount = _to_float(_first(payload, "discount", "discountAmount", "couponAmount", "promotionAmount", default=0))
    delivery = _to_float(_first(payload, "deliveryFee", "deliveryPrice", "shippingFee", default=0))
    pay = _to_float(_first(payload, "payPrice", "payablePrice", "finalPrice", "actualPrice", default=0))
    if pay <= 0 and subtotal > 0:
        pay = round(max(subtotal - discount, 0) + delivery, 2)
    if subtotal <= 0 and pay > 0:
        subtotal = round(pay + discount - delivery, 2)
    return {
        "subtotal": round(subtotal, 2),
        "discount": round(discount, 2),
        "delivery": round(delivery, 2),
        "pay": round(pay, 2),
        "coupons": _first(payload, "appliedCoupons", "coupons", default=[]) or [],
        # 下单必需：create-order 在到店场景要带 takeWayCode，它是算价结果的产物
        "takeWayCode": str(_first(payload, "takeWayCode", "takeWay", default="") or ""),
        "beCode": str(_first(payload, "beCode", default="") or ""),
        "orderType": _first(payload, "orderType", default=None),
        "beType": _first(payload, "beType", default=None),
        "realTotalAmount": _to_float(_first(payload, "realTotalAmount", default=pay)),
    }


def normalize_order(raw: Any) -> dict:
    payload = raw if isinstance(raw, dict) else {}
    return {
        "orderId": str(_first(payload, "orderId", "orderNo", "id", default="") or ""),
        "status": str(_first(payload, "status", "orderStatus", "orderStatusTitle", "state", default="") or ""),
        "statusTitle": str(_first(payload, "orderStatusTitle", "orderStatusSubTitle", default="") or ""),
        "payUrl": str(_first(payload, "payH5Url", "payUrl", "paymentUrl", "payLink", default="") or ""),
        "payId": str(_first(payload, "payId", default="") or ""),
        "pickupNumber": _first(payload, "pickupNumber", "mealNumber", "number", "takeMealCode", default=None),
        "payPrice": _to_float(_first(payload, "payPrice", "payablePrice", "realTotalAmount", default=0)),
        # 未支付订单会在倒计时结束后自动取消，提醒用户时要用到
        "leftPaySecond": _to_int(_first(payload, "leftPaySecond", "leftPayTime", default=0)),
    }


# 订单状态 -> 中文 + 是否可取餐
# 同时收录英文枚举与中文文案：真实服务可能直接返回中文 orderStatusTitle
STATUS_TEXT = {
    "PENDING_PAYMENT": ("待支付", False),
    "PENDINGPAY": ("待支付", False),
    "UNPAID": ("待支付", False),
    "待支付": ("待支付", False),
    "PAID": ("已支付，等待制作", False),
    "已支付": ("已支付，等待制作", False),
    "PREPARING": ("制作中", False),
    "MAKING": ("制作中", False),
    "制作中": ("制作中", False),
    "READY": ("餐品已就绪，请取餐", True),
    "READY_FOR_PICKUP": ("餐品已就绪，请取餐", True),
    "待取餐": ("餐品已就绪，请取餐", True),
    "COMPLETED": ("已完成", True),
    "已完成": ("已完成", True),
    "CANCELLED": ("已取消", False),
    "CANCELED": ("已取消", False),
    "已取消": ("已取消", False),
    "NOT_FOUND": ("未找到订单", False),
}
_PAYING_STATES = {"PENDING_PAYMENT", "PENDINGPAY", "UNPAID", "待支付"}


def status_text(status: str) -> tuple[str, bool]:
    key = (status or "").strip()
    if key in STATUS_TEXT:
        return STATUS_TEXT[key]
    upper = key.upper()
    if upper in STATUS_TEXT:
        return STATUS_TEXT[upper]
    for token, value in STATUS_TEXT.items():
        if token and token in key:
            return value
    return (key or "未知状态", False)


def is_awaiting_payment(status: str) -> bool:
    """订单是否仍处于「待支付」——这类订单永远不会变成可取餐，必须先引导用户付款。"""
    key = (status or "").strip()
    return key in _PAYING_STATES or key.upper() in _PAYING_STATES or "待支付" in key
