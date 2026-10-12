#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""功能二：麦麦奶龙 · 汉堡抽卡。

两条输入路径
------------
1. **答题**：10 道题（麦当劳 5 : 日常 5）→ 四轴人格（辣度 / 食量 / 决策 / 社交）→「堡格」
2. **读历史订单**：从订单结构直接反推四轴（不想答题的人也能抽卡）

产出
----
堡格 + 性格关键词 + 推荐套餐 + 名片名（{性格}+{堡格}+奶龙）。

用法
----
    python quiz_engine.py --mock --answers 1A,2B,3A,4C,5B,6C,7A,8A,9A,10D
    python quiz_engine.py --mock --history
    python quiz_engine.py --mock --interactive
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcd_mcp import McdMcpError, McdMcpClient  # noqa: E402
from mcd_naming import boge_name, card_name_for_quiz, top_personalities  # noqa: E402
from mcd_schema import normalize_menu  # noqa: E402

DATA_FILE = Path(__file__).resolve().parent / "quiz_data.json"
PERSONALITY_KEYS = {
    "efficient",
    "nightowl",
    "planner",
    "social",
    "saver",
    "ritual",
    "casual",
    "caffeine",
    "procrastinate",
    "morning",
    "stable",
    "toughsoft",
}
AXIS_KEYS = {"spicy", "big", "light", "decisive", "hesitant", "party", "solo", "mild"}


def load_quiz() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 计分
# --------------------------------------------------------------------------- #
def score_answers(answers: dict[int, str], quiz: dict | None = None) -> dict:
    """answers: {题号: 选项key} -> 四轴 + 性格分。"""
    quiz = quiz or load_quiz()
    raw: Counter[str] = Counter()

    for question in quiz["questions"]:
        picked = answers.get(question["id"])
        if not picked:
            continue
        option = next((o for o in question["options"] if o["key"] == str(picked).strip().upper()), None)
        if not option:
            continue
        for key, value in option["scores"].items():
            raw[key] += int(value)

    return _finalize(raw)


def analyze_history(orders: list[dict]) -> dict:
    """从历史订单反推四轴。"""
    raw: Counter[str] = Counter()
    if not orders:
        return _finalize(raw)

    for order in orders:
        names = [item.get("name", "") for item in order.get("items", [])]
        joined = " ".join(names)
        qty = sum(int(item.get("qty", 1)) for item in order.get("items", []))
        price = float(order.get("payPrice") or 0)

        if "辣" in joined:
            raw["spicy"] += 2
        if any(key in joined for key in ("板烧", "吉士", "巨无霸", "麦香鱼")):
            raw["mild"] += 1
        if qty >= 3 or price >= 40:
            raw["big"] += 2
        elif qty <= 2:
            raw["light"] += 1
        if any(key in joined for key in ("套餐", "随心配")):
            raw["big"] += 1
        if sum(1 for n in names if "辣" in n) >= 2:
            raw["spicy"] += 1
        if len(set(names)) <= 2:
            raw["decisive"] += 1  # 老一套，不折腾
        if qty >= 4:
            raw["party"] += 1  # 点这么多，多半不是一个人吃
        else:
            raw["solo"] += 1

    # 频次特征 -> 性格
    if len(orders) >= 5:
        raw["saver"] += 2
        raw["planner"] += 1
    hours = []
    for order in orders:
        stamp = str(order.get("time") or order.get("createTime") or "")
        if ":" in stamp and len(stamp) >= 13:
            digits = "".join(ch for ch in stamp.split(" ")[-1][:2] if ch.isdigit())
            if digits:
                hours.append(int(digits))
    if any(h >= 21 or h < 5 for h in hours):
        raw["nightowl"] += 1
    if any(5 <= h <= 8 for h in hours):
        raw["morning"] += 1

    return _finalize(raw)


def _finalize(raw: Counter[str]) -> dict:
    axes = {
        "spicy": "spicy" if raw["spicy"] >= raw["mild"] else "mild",
        "appetite": "big" if raw["big"] >= raw["light"] else "light",
        "decision": "decisive" if raw["decisive"] >= raw["hesitant"] else "hesitant",
        "social": "party" if raw["party"] >= raw["solo"] else "solo",
    }
    personality_scores = {k: raw[k] for k in PERSONALITY_KEYS if raw[k] > 0}
    return {"axes": axes, "raw": dict(raw), "personalityScores": personality_scores}


# --------------------------------------------------------------------------- #
# 推荐套餐
# --------------------------------------------------------------------------- #
def recommend(menu: list[dict], axes: dict) -> list[dict]:
    spicy = axes["spicy"] == "spicy"
    big = axes["appetite"] == "big"

    burgers = [m for m in menu if m["category"] == "burger"]
    if spicy:
        pool = [m for m in burgers if "辣" in m["tags"]] or burgers
    else:
        pool = [m for m in burgers if "辣" not in m["tags"]] or burgers
    pool.sort(key=lambda m: (-m["satiety"]) if big else m["satiety"])
    main = pool[0]

    matched_set = next(
        (m for m in menu if m["category"] == "set" and main["name"] in m["name"]),
        None,
    )
    if matched_set:
        combo = [matched_set]
    else:
        combo = [main]
        sides = sorted((m for m in menu if m["category"] == "side"), key=lambda m: -m["satiety"])
        drinks = sorted(
            (m for m in menu if m["category"] == "drink" and ("冷" in m["tags"] or "热" in m["tags"])),
            key=lambda m: -m["satiety"],
        )
        if sides:
            combo.append(sides[0] if big else sides[-1])
        if drinks and big:
            combo.append(drinks[0])

    return [{"code": m["code"], "name": m["name"], "qty": 1, "price": m["price"]} for m in combo]


def recommend_reason(axes: dict, boge: dict) -> str:
    bits = []
    bits.append("辣度优先" if axes["spicy"] == "spicy" else "温和不刺激")
    bits.append("分量拉满" if axes["appetite"] == "big" else "轻负担")
    bits.append("快速决策" if axes["decision"] == "decisive" else "选择困难，直接抄作业")
    return f"按你的「{boge['name']}」画像：{' + '.join(bits)}"


# --------------------------------------------------------------------------- #
# 组装结果
# --------------------------------------------------------------------------- #
def build_result(
    client: McdMcpClient,
    store_code: str,
    answers: dict[int, str] | None = None,
    use_history: bool = False,
    dining_mode: str = "dine_in",
) -> dict:
    quiz = load_quiz()
    if use_history:
        history = client.call_tool("query-my-orders", {})
        orders = history.get("orders") if isinstance(history, dict) else (history or [])
        scored = analyze_history(orders or [])
        source = "history"
        source_detail = f"读取 {len(orders or [])} 条历史订单"
    else:
        scored = score_answers(answers or {}, quiz)
        source = "quiz"
        answered = len([q for q in quiz["questions"] if q["id"] in (answers or {})])
        source_detail = f"完成 {answered}/{len(quiz['questions'])} 道题"

    axes = scored["axes"]
    boge = boge_name(axes["spicy"], axes["appetite"], axes["decision"], axes["social"])
    personalities = top_personalities(scored["personalityScores"], limit=2)

    menu = normalize_menu(client.meals(store_code))
    combo = recommend(menu, axes) if menu else []
    price = {}
    if combo:
        raw_price = client.calculate_price(
            store_code,
            [{"mealCode": item["code"], "qty": item["qty"]} for item in combo],
            dining_mode=dining_mode,
        )
        if isinstance(raw_price, dict):
            price = {
                "subtotal": raw_price.get("subtotal"),
                "discount": raw_price.get("discount"),
                "delivery": raw_price.get("deliveryFee"),
                "pay": raw_price.get("payPrice"),
            }

    return {
        "source": source,
        "sourceDetail": source_detail,
        "axes": axes,
        "axesText": {
            "辣度": "辣党" if axes["spicy"] == "spicy" else "温柔党",
            "食量": "巨胃" if axes["appetite"] == "big" else "轻食",
            "决策": "果决派" if axes["decision"] == "decisive" else "纠结派",
            "社交": "组队型" if axes["social"] == "party" else "独食型",
        },
        "personalities": personalities,
        "personalityScores": scored["personalityScores"],
        "boge": boge,
        "cardName": card_name_for_quiz(personalities, boge),
        "recommend": {
            "items": combo,
            "price": price,
            "reason": recommend_reason(axes, boge),
        },
        "apiCalls": client.call_count,
    }


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #
def render(result: dict) -> str:
    boge = result["boge"]
    lines = [
        "🎴 麦麦奶龙 · 汉堡抽卡",
        f"依据：{result['sourceDetail']}",
        "─" * 52,
        "",
        f"🧬 你的四轴：{' | '.join(f'{k} {v}' for k, v in result['axesText'].items())}",
        f"🎭 性格关键词：{'、'.join(result['personalities'])}",
        "",
        f"🍔 堡格：{boge['name']}",
        f"   {boge['blurb']}",
        "",
    ]
    rec = result["recommend"]
    if rec["items"]:
        lines.append("▸ 推荐套餐")
        for item in rec["items"]:
            lines.append(f"   · {item['name']} ×{item['qty']}")
        price = rec.get("price") or {}
        if price.get("pay") is not None:
            lines.append(f"   实付 ¥{float(price['pay']):.2f}（优惠 ¥{float(price.get('discount') or 0):.2f}）")
        lines.append(f"   {rec['reason']}")
    lines.append("")
    lines.append(f"🎴 名片名：{result['cardName']}")
    lines.append("")
    lines.append("生成名片图：python card_gen.py --quiz-result <result.json>")
    return "\n".join(lines)


def parse_answers(text: str) -> dict[int, str]:
    answers: dict[int, str] = {}
    for chunk in (text or "").replace("，", ",").split(","):
        chunk = chunk.strip()
        if len(chunk) < 2:
            continue
        digits = "".join(ch for ch in chunk if ch.isdigit())
        letters = "".join(ch for ch in chunk if ch.isalpha())
        if digits and letters:
            answers[int(digits)] = letters.upper()
    return answers


def interactive(quiz: dict) -> dict[int, str]:
    answers: dict[int, str] = {}
    for question in quiz["questions"]:
        tag = "麦" if question["kind"] == "mcd" else "日"
        print(f"\n[{tag}] Q{question['id']}. {question['title']}")
        for option in question["options"]:
            print(f"   {option['key']}. {option['text']}")
        while True:
            picked = input("你的选择：").strip().upper()
            if any(o["key"] == picked for o in question["options"]):
                answers[question["id"]] = picked
                break
            print("  请输入 A/B/C/D")
    return answers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="麦麦奶龙汉堡抽卡")
    parser.add_argument("--answers", default="", help="如 1A,2B,3A,4C,5B,6C,7A,8A,9A,10D")
    parser.add_argument("--history", action="store_true", help="改为读取历史订单")
    parser.add_argument("--interactive", action="store_true", help="交互式答题")
    parser.add_argument("--store", default="S001")
    parser.add_argument("--mode", default="dine_in", choices=["dine_in", "take_out", "delivery"])
    parser.add_argument("--out", default="", help="把结果 JSON 写到指定路径（供 card_gen 使用）")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    quiz = load_quiz()
    answers = parse_answers(args.answers)
    if args.interactive:
        answers = interactive(quiz)
    if not args.history and not answers:
        print("未提供答案。用法：--answers 1A,2B,... 或 --history 或 --interactive", file=sys.stderr)
        return 2

    try:
        client = McdMcpClient(mock=args.mock)
        result = build_result(client, args.store, answers, use_history=args.history, dining_mode=args.mode)
    except McdMcpError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入 {args.out}")
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
