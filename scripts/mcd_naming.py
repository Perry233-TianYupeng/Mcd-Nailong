#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""命名体系：堡格表、性格关键词、消费等级、名片命名规则。

被 quiz_engine / budget_solver / card_gen 共同引用，保证三个功能产出的
「堡格」「性格」「消费等级」口径完全一致。
"""
from __future__ import annotations

# --------------------------------------------------------------------------- #
# 一、消费等级（穷鬼预算锁用）
# --------------------------------------------------------------------------- #
SPEND_TIERS: list[tuple[str, float, float, str]] = [
    ("节俭度日", 0.0, 25.0, "钱要花在刀刃上，吃饱是唯一KPI。"),
    ("吃堡自由", 25.0, 40.0, "想加薯条就加薯条，这就是自由的味道。"),
    ("豪情在天", 40.0, float("inf"), "点单不看价的快乐，你值得拥有。"),
]


def spend_tier(amount: float) -> dict:
    """按实付金额返回消费等级。<25 节俭度日，25-40 吃堡自由，>40 豪情在天。"""
    value = float(amount or 0)
    for label, low, high, desc in SPEND_TIERS:
        if low <= value < high:
            return {"level": label, "desc": desc, "min": low, "max": high, "amount": round(value, 2)}
    label, low, high, desc = SPEND_TIERS[-1]
    return {"level": label, "desc": desc, "min": low, "max": high, "amount": round(value, 2)}


# --------------------------------------------------------------------------- #
# 二、堡格表（4 轴 -> 16 型）
# --------------------------------------------------------------------------- #
_SPICY = {"spicy": "辣党", "mild": "温柔党"}
_APPETITE = {"big": "巨胃", "light": "轻食"}

# (辣度, 食量) -> 基础堡格
BOGE_BASE: dict[tuple[str, str], str] = {
    ("spicy", "big"): "巨无霸辣王",
    ("spicy", "light"): "椒香小钢炮",
    ("mild", "big"): "温柔巨塔",
    ("mild", "light"): "云朵轻食家",
}

# (决策, 社交) -> 修饰后缀
BOGE_SUFFIX: dict[tuple[str, str], str] = {
    ("decisive", "solo"): "单人成军",
    ("decisive", "party"): "组队指挥官",
    ("hesitant", "solo"): "午夜纠结体",
    ("hesitant", "party"): "选择困难队长",
}

BOGE_BLURB: dict[str, str] = {
    "巨无霸辣王": "辣度与分量双高，你的字典里没有“小份”。",
    "椒香小钢炮": "个子不大，火力不小，二两肉三层辣。",
    "温柔巨塔": "不辣但管饱，团队里那个最靠得住的人。",
    "云朵轻食家": "吃的是氛围，不是热量。",
}


def boge_name(spicy: str, appetite: str, decision: str, social: str) -> dict:
    """四个维度（值见上方常量）-> 堡格名称。"""
    base = BOGE_BASE.get((spicy, appetite), "神秘堡格")
    suffix = BOGE_SUFFIX.get((decision, social), "未定义人格")
    return {
        "name": f"{base}·{suffix}",
        "base": base,
        "suffix": suffix,
        "spicy": _SPICY.get(spicy, spicy),
        "appetite": _APPETITE.get(appetite, appetite),
        "blurb": BOGE_BLURB.get(base, ""),
    }


# --------------------------------------------------------------------------- #
# 三、性格关键词（日常习惯题映射，取 top-2 作为名片前缀）
# --------------------------------------------------------------------------- #
PERSONALITY_LIBRARY: dict[str, str] = {
    "efficient": "效率至上",
    "nightowl": "深夜活跃",
    "planner": "计划控",
    "social": "社交充电",
    "saver": "省钱天才",
    "ritual": "仪式感",
    "casual": "随性派",
    "caffeine": "咖啡因依赖",
    "procrastinate": "拖延症晚期",
    "morning": "早八战神",
    "stable": "情绪稳定",
    "toughsoft": "嘴硬心软",
}


def top_personalities(scores: dict[str, int], limit: int = 2) -> list[str]:
    """按分数取前 limit 个关键词（同分按库中定义顺序，保证可复现）。"""
    order = list(PERSONALITY_LIBRARY.keys())
    ranked = sorted(
        order,
        key=lambda key: (-int(scores.get(key, 0)), order.index(key)),
    )
    picked = [PERSONALITY_LIBRARY[k] for k in ranked if scores.get(k, 0) > 0][:limit]
    if not picked:
        picked = [PERSONALITY_LIBRARY[order[0]]]
    return picked


# --------------------------------------------------------------------------- #
# 四、名片命名
# --------------------------------------------------------------------------- #
def card_name_for_quiz(personalities: list[str], boge: dict) -> str:
    """抽卡名片名：{性格}+{堡格}+奶龙。"""
    prefix = personalities[0] if personalities else "神秘"
    return f"{prefix}·{boge['name']}奶龙"


def card_name_for_budget(tier: dict, burger_name: str) -> str:
    """消费名片名：{消费等级}+{汉堡名}+奶龙。"""
    return f"{tier['level']}·{burger_name}奶龙"
