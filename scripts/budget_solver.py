#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""功能三：穷鬼预算锁 —— “我只有 25 块，吃饱”。

不是简单比价，而是**约束求解**：在「预算 ≤ X 元」的硬约束下，对菜单做组合枚举与
试算，输出 Pareto 前沿上的 3 套方案（极致省钱 / 性价比之王 / 最满足）。

算法
----
1. 拉菜单 → 按口味过滤
2. 生成候选组合（单品 / 汉堡+小食 / 汉堡+饮料 / 汉堡+小食+饮料 / 套餐）
3. 用本地启发式打分（口味匹配 + 单位价格饱腹度 + 保真度 + 组合丰富度）
4. 本地预估优惠做预筛，只把最有希望的 N 个候选交给 MCP ``calculate-price`` 复核
5. 在 (实付价 ↑, 满足度 ↑) 上求 Pareto 前沿，从前沿里取 3 个代表点

用法
----
    python budget_solver.py --budget 25 --taste 辣,鸡 --mock
    python budget_solver.py --budget 40 --taste 牛 --mode delivery --store S002 --mock
    python budget_solver.py --items B004:1,S001:1,D001:1 --budget 40 --mock   # 复核自定义订单
    python budget_solver.py --budget 25 --taste 辣 --mock --json
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcd_mcp import McdMcpError, McdMcpClient  # noqa: E402
from mcd_naming import spend_tier  # noqa: E402
from mcd_schema import normalize_coupons, normalize_menu, normalize_price  # noqa: E402

MAX_VERIFY = 24          # 最多向 calculate-price 发起的复核次数（控调用量）
TASTE_TAGS = ("辣", "不辣", "鸡", "牛", "鱼", "素", "甜", "冷", "热", "量足")
MODE_TEXT = {"dine_in": "到店取餐", "take_out": "外带", "delivery": "麦乐送"}


# --------------------------------------------------------------------------- #
# 候选生成
# --------------------------------------------------------------------------- #
def parse_taste(text: str) -> tuple[list[str], list[str]]:
    """把 "辣,鸡,-素" 解析成 (想要, 排除)。带 - 前缀的是排除项。"""
    wants, avoids = [], []
    for raw in (text or "").replace("，", ",").split(","):
        token = raw.strip()
        if not token:
            continue
        if token.startswith("-"):
            avoids.append(token[1:].strip())
        elif token in TASTE_TAGS:
            wants.append(token)
        else:
            wants.append(token)
    return wants, avoids


def _matches(item: dict, token: str) -> bool:
    if token == "量足":
        return item["satiety"] >= 1.0
    return token in item["tags"]


def item_score(item: dict, wants: list[str], avoids: list[str]) -> float:
    """单品口味分。命中 +2，硬冲突 -3/-2。"""
    score = 0.0
    for token in wants:
        if _matches(item, token):
            score += 2.0
    for token in avoids:
        if _matches(item, token):
            score -= 3.0
    hard = {"辣": "不辣", "不辣": "辣", "甜": "甜", "素": "牛"}
    for token in wants:
        opposite = hard.get(token)
        if opposite and token != "甜" and _matches(item, opposite):
            score -= 3.0
    return score


def taste_gate(item: dict, wants: list[str], avoids: list[str] | None = None, strict: bool = True) -> bool:
    """硬过滤。

    strict=True：主品类（汉堡/套餐）上，若用户明确要辣/不辣，直接排除冲突单品。
    strict=False：配餐（小食/饮料/甜品）只按排除项过滤，避免"要辣就连薯条都不能点"。
    """
    for token in avoids or []:
        if _matches(item, token):
            return False
    if not strict:
        return True
    if "辣" in wants and "不辣" in item["tags"]:
        return False
    if "不辣" in wants and "辣" in item["tags"]:
        return False
    if "素" in wants and ("牛" in item["tags"] or "鸡" in item["tags"] or "鱼" in item["tags"]):
        return False
    return True


def build_candidates(menu: list[dict], wants: list[str], avoids: list[str] | None = None) -> list[list[dict]]:
    avoids = avoids or []
    burgers = [m for m in menu if m["category"] in ("burger", "set") and taste_gate(m, wants, avoids, strict=True)]
    sides = [m for m in menu if m["category"] == "side" and taste_gate(m, wants, avoids, strict=False)]
    drinks = [m for m in menu if m["category"] == "drink" and taste_gate(m, wants, avoids, strict=False)]
    desserts = [m for m in menu if m["category"] == "dessert" and taste_gate(m, wants, avoids, strict=False)]

    ranked_sides = sorted(sides, key=lambda m: (-m["satiety"], m["price"]))[:3]
    ranked_drinks = sorted(drinks, key=lambda m: m["price"])[:3]
    ranked_desserts = sorted(desserts, key=lambda m: m["price"])[:2]

    bundles: list[list[dict]] = []
    for burger in burgers:
        bundles.append([burger])
        for side in ranked_sides:
            bundles.append([burger, side])
        for drink in ranked_drinks:
            bundles.append([burger, drink])
        if ranked_sides and ranked_drinks:
            bundles.append([burger, ranked_sides[0], ranked_drinks[0]])
        for dessert in ranked_desserts:
            bundles.append([burger, dessert])

    # 去重
    seen: set[tuple] = set()
    unique: list[list[dict]] = []
    for bundle in bundles:
        key = tuple(sorted(item["code"] for item in bundle))
        if key in seen:
            continue
        seen.add(key)
        unique.append(bundle)
    return unique


def row_key(row: dict) -> tuple:
    return tuple(sorted((i["code"], i["qty"]) for i in row["items"]))


# --------------------------------------------------------------------------- #
# 本地估价与打分
# --------------------------------------------------------------------------- #
def estimate_discount(bundle: list[dict], coupons: list[dict], mode: str) -> float:
    subtotal = sum(item["price"] for item in bundle)
    names = " ".join(item["name"] for item in bundle)
    best = 0.0
    for coupon in coupons:
        scope = coupon.get("scope") or ""
        if coupon.get("threshold") and subtotal < coupon["threshold"]:
            continue
        if scope and "全场" not in scope:
            if not any(part and part in names for part in scope.replace("麦乐送", "").split("、")):
                continue
        best = max(best, float(coupon.get("discount") or 0))
    if mode == "delivery" and subtotal >= 39:
        best += 0.0
    return round(best, 2)


def score_bundles(candidates: list[list[dict]], wants: list[str], avoids: list[str]) -> list[dict]:
    rows: list[dict] = []
    for bundle in candidates:
        raw = round(sum(item["price"] for item in bundle), 2)
        satiety = sum(item["satiety"] for item in bundle)
        taste = sum(item_score(item, wants, avoids) for item in bundle)
        categories = {item["category"] for item in bundle}
        variety = len(categories)
        kcal = sum(item["kcal"] for item in bundle)
        protein = sum(item["protein"] for item in bundle)
        rows.append(
            {
                "bundle": bundle,
                "items": [{"code": i["code"], "name": i["name"], "price": i["price"], "qty": 1} for i in bundle],
                "raw": raw,
                "satiety": round(satiety, 2),
                "taste": taste,
                "variety": variety,
                "kcal": kcal,
                "protein": protein,
                "value": satiety / raw if raw else 0,
            }
        )

    if not rows:
        return []

    max_satiety = max(r["satiety"] for r in rows) or 1
    max_value = max(r["value"] for r in rows) or 1
    want_count = max(len(wants), 1)
    best_taste = max(abs(r["taste"]) for r in rows) or 1

    for row in rows:
        taste_norm = max(min(row["taste"] / (2 * want_count), 1.0), -1.0)
        value_norm = row["value"] / max_value
        satiety_norm = row["satiety"] / max_satiety
        variety_bonus = (row["variety"] - 1) * 3.0
        row["score"] = round(
            100 * (0.45 * taste_norm + 0.25 * value_norm + 0.30 * satiety_norm) + variety_bonus,
            1,
        )
        row["tasteNorm"] = round(taste_norm, 2)
        row["bestTaste"] = best_taste
    return rows


def select_verify_pool(rows: list[dict], limit: int = MAX_VERIFY) -> list[dict]:
    """挑出值得花钱去 calculate-price 复核的候选。

    只按分数取 Top-N 会**把便宜的组合全部饿死**（高分往往属于大套餐），
    导致 Pareto 前沿退化成一个点。所以同时保三个方向：
    高分 / 最低预估实付 / 最高性价比。
    """
    if not rows:
        return []
    by_score = sorted(rows, key=lambda r: -r["score"])[:16]
    by_price = sorted(rows, key=lambda r: r["est"])[:8]
    by_ratio = sorted(rows, key=lambda r: -(r["score"] / r["est"] if r["est"] else 0))[:6]

    # 价格分档代表：每 5 元一档取该档内分数最高的，保证前沿在每个价位都有点
    bands: dict[int, dict] = {}
    for row in rows:
        band = int(row["est"] // 5)
        if band not in bands or row["score"] > bands[band]["score"]:
            bands[band] = row
    by_band = sorted(bands.values(), key=lambda r: r["est"])[:8]

    pool: list[dict] = []
    seen: set[tuple] = set()
    for row in by_score + by_band + by_price + by_ratio:
        key = row_key(row)
        if key in seen:
            continue
        seen.add(key)
        pool.append(row)
        if len(pool) >= limit:
            break
    return pool


def pareto_front(rows: list[dict]) -> list[dict]:
    """(实付价 ↑, 分数 ↑) 的非支配集。"""
    front = []
    for row in rows:
        dominated = any(
            other["pay"] <= row["pay"]
            and other["score"] >= row["score"]
            and (other["pay"] < row["pay"] or other["score"] > row["score"])
            for other in rows
            if other is not row
        )
        if not dominated:
            front.append(row)
    front.sort(key=lambda r: (r["pay"], -r["score"]))
    return front


TAG_ORDER = ["极致省钱", "性价比之王", "最满足"]
TAG_REASON = {
    "极致省钱": "花最少的钱把肚子填上，预算红线的守门人。",
    "性价比之王": "每块钱换到的满足感最高，学生党最优解。",
    "最满足": "预算内的天花板，吃到扶墙走。",
    "备选方案": "预算内的另一个可行解。",
}


def pick_three(front: list[dict], limit: int = 3) -> list[tuple[str, str, dict]]:
    """从前沿里取 3 个**互不重复**的代表点，再按属性贴标签。"""
    if not front:
        return []

    cheapest = min(front, key=lambda r: (r["pay"], -r["score"]))
    richest = max(front, key=lambda r: r["score"])
    best_value = max(front, key=lambda r: (r["score"] / r["pay"]) if r["pay"] else 0)

    chosen: list[dict] = []
    used: set[tuple] = set()
    for row in [cheapest, best_value, richest] + sorted(front, key=lambda r: (-r["score"], r["pay"])):
        key = row_key(row)
        if key in used:
            continue
        used.add(key)
        chosen.append(row)
        if len(chosen) >= limit:
            break

    min_pay = min(r["pay"] for r in chosen)
    max_score = max(r["score"] for r in chosen)
    tagged: list[tuple[str, str, dict]] = []
    taken: set[str] = set()
    for row in chosen:
        if row["pay"] == min_pay and "极致省钱" not in taken:
            tag = "极致省钱"
        elif row["score"] == max_score and "最满足" not in taken:
            tag = "最满足"
        elif "性价比之王" not in taken:
            tag = "性价比之王"
        else:
            tag = "备选方案"
        taken.add(tag)
        tagged.append((tag, TAG_REASON[tag], row))

    tagged.sort(key=lambda item: TAG_ORDER.index(item[0]) if item[0] in TAG_ORDER else 99)
    return tagged


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def solve(
    client: McdMcpClient,
    store_code: str,
    budget: float,
    taste: str,
    mode: str,
    top_n: int = 3,
) -> dict:
    wants, avoids = parse_taste(taste)
    menu = normalize_menu(client.meals(store_code))
    if not menu:
        raise McdMcpError(f"门店 {store_code} 未返回任何餐品，请确认门店编码")

    coupons = normalize_coupons(client.available_coupons()) + normalize_coupons(client.my_coupons())
    candidates = build_candidates(menu, wants, avoids)
    rows = score_bundles(candidates, wants, avoids)

    # 本地预估优惠做预筛（放宽 15% 余量 + 10 元，防止把券后达标的组合筛掉）
    ceiling = budget * 1.15 + 10
    for row in rows:
        row["est"] = round(row["raw"] - estimate_discount(row["bundle"], coupons, mode), 2)
    prefiltered = [row for row in rows if row["est"] <= ceiling]
    verify_pool = select_verify_pool(prefiltered)

    verified: list[dict] = []
    for row in verify_pool:
        price = normalize_price(
            client.calculate_price(
                store_code,
                [{"mealCode": item["code"], "qty": 1} for item in row["bundle"]],
                dining_mode=mode,
            )
        )
        if price["pay"] <= 0:
            price["pay"] = round(row["raw"] - price["discount"] + price["delivery"], 2)
        row.update({"pay": price["pay"], "subtotal": price["subtotal"], "discount": price["discount"], "delivery": price["delivery"], "coupons": price["coupons"]})
        if row["pay"] <= budget:
            verified.append(row)

    if not verified:
        return {
            "ok": False,
            "reason": f"预算 ¥{budget:.2f} 内没有可行组合，试试放宽到 ¥{budget + 5:.2f}。",
            "storeCode": store_code,
            "budget": budget,
            "taste": wants,
            "mode": mode,
            "scanned": len(candidates),
            "apiCalls": client.call_count,
        }

    # 在「实付价」维度上重打一次分（前端只认实付）
    for row in verified:
        row["yuanPerSatiety"] = round(row["pay"] / row["satiety"], 2) if row["satiety"] else 0
        row["value"] = row["satiety"] / row["pay"] if row["pay"] else 0

    front = pareto_front(verified)
    picks = pick_three(front)[:top_n]

    # 前沿点不足（预算很紧时常见）就用可行解里次优的补齐，保证用户总能看到 3 个选择
    if len(picks) < top_n:
        used = {row_key(row) for _, _, row in picks}
        for row in sorted(verified, key=lambda r: (-r["score"], r["pay"])):
            if len(picks) >= top_n:
                break
            key = row_key(row)
            if key in used:
                continue
            used.add(key)
            picks.append(("备选方案", TAG_REASON["备选方案"], row))

    plans = []
    for index, (tag, reason, row) in enumerate(picks):
        plans.append(
            {
                "id": "ABC"[index],
                "tag": tag,
                "reason": reason,
                "items": row["items"],
                "signature": "|".join(f"{i['code']}x{i['qty']}" for i in row["items"]),
                "subtotal": row.get("subtotal", row["raw"]),
                "discount": row.get("discount", 0),
                "delivery": row.get("delivery", 0),
                "pay": row["pay"],
                "satiety": row["satiety"],
                "kcal": row["kcal"],
                "protein": row["protein"],
                "score": row["score"],
                "yuanPerSatiety": row["yuanPerSatiety"],
                "tier": spend_tier(row["pay"]),
                "mainBurger": next((i["name"] for i in row["items"]), ""),
            }
        )

    return {
        "ok": True,
        "storeCode": store_code,
        "budget": budget,
        "taste": wants,
        "avoid": avoids,
        "mode": mode,
        "scanned": len(candidates),
        "verified": len(verified),
        "frontSize": len(front),
        "plans": plans,
        "apiCalls": client.call_count,
    }


def price_custom(client: McdMcpClient, store_code: str, items: list[dict], mode: str) -> dict:
    """复核用户自己改过的订单。"""
    price = normalize_price(client.calculate_price(store_code, items, dining_mode=mode))
    return {
        "items": items,
        "subtotal": price["subtotal"],
        "discount": price["discount"],
        "delivery": price["delivery"],
        "pay": price["pay"],
        "tier": spend_tier(price["pay"]),
        "coupons": price["coupons"],
        "apiCalls": client.call_count,
    }


def parse_items(text: str) -> list[dict]:
    """解析 "B004:1,S001:2" -> [{"mealCode":"B004","qty":1}, ...]"""
    items = []
    for chunk in (text or "").replace("，", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        code, _, qty = chunk.partition(":")
        items.append({"mealCode": code.strip(), "qty": int(qty or 1)})
    return items


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #
def render(result: dict) -> str:
    if not result.get("ok"):
        return f"❌ {result['reason']}"

    lines = []
    lines.append(f"🎯 穷鬼预算锁 · 预算 ¥{result['budget']:.2f}  |  门店 {result['storeCode']}")
    lines.append(
        f"口味：{'、'.join(result['taste']) or '不限'}"
        + (f"（排除 {'、'.join(result['avoid'])}）" if result["avoid"] else "")
        + f"   就餐方式：{MODE_TEXT.get(result['mode'], result['mode'])}"
    )
    lines.append(f"枚举 {result['scanned']} 种组合 → 试算 {result['verified']} 种可行 → Pareto 前沿 {result['frontSize']} 个")
    lines.append("─" * 52)

    for plan in result["plans"]:
        lines.append("")
        lines.append(f"【方案 {plan['id']}｜{plan['tag']}】  实付 ¥{plan['pay']:.2f}")
        for item in plan["items"]:
            lines.append(f"   · {item['name']} ×{item['qty']}")
        if plan["discount"]:
            lines.append(f"   原价 ¥{plan['subtotal']:.2f}  −  优惠 ¥{plan['discount']:.2f}")
        if plan["delivery"]:
            lines.append(f"   配送费 ¥{plan['delivery']:.2f}")
        lines.append(f"   满足度 {plan['satiety']:.2f}  |  每元饱腹 {plan['yuanPerSatiety']:.2f} 元/点  |  {plan['kcal']} kcal / 蛋白 {plan['protein']}g")
        lines.append(f"   名片等级：{plan['tier']['level']}　{plan['tier']['desc']}")
        lines.append(f"   {plan['reason']}")

    lines.append("")
    lines.append("想改单？把方案里的菜品改完再复核：")
    lines.append(f"   python budget_solver.py --items {result['plans'][0]['signature'].replace('x', ':').replace('|', ',')} --budget {result['budget']:.0f} --mock")
    lines.append(f"[MCP 调用 {result['apiCalls']} 次]")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="穷鬼预算锁：预算内 Pareto 最优点餐方案")
    parser.add_argument("--budget", type=float, required=True, help="预算上限（元）")
    parser.add_argument(
        "--taste",
        nargs="?",
        const="",
        default="",
        help="口味，逗号分隔，如 辣,鸡；- 前缀表示排除，如 -素",
    )
    parser.add_argument("--mode", default="dine_in", choices=["dine_in", "take_out", "delivery"])
    parser.add_argument("--store", default="S001", help="门店编码")
    parser.add_argument("--items", default="", help="改为复核自定义订单，如 B004:1,S001:1")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        client = McdMcpClient(mock=args.mock)
        if args.items:
            result = price_custom(client, args.store, parse_items(args.items), args.mode)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"自定义订单 门店 {args.store}  实付 ¥{result['pay']:.2f}（优惠 ¥{result['discount']:.2f}）")
                print(f"消费等级：{result['tier']['level']} — {result['tier']['desc']}")
            return 0
        result = solve(client, args.store, args.budget, args.taste, args.mode)
    except McdMcpError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
