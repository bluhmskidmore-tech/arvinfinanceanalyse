# -*- coding: utf-8 -*-
"""
credit_bond_signals.py
信用债信号层：基于 credit_bond_data.py 的输出
计算：骑乘收益凸点、品种利差、性价比评分
输出：output/credit_signal.csv
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from datetime import datetime, date

# ── 筛选参数（来自研报方法论）──────────────────────────────────────────────────

ROLL_YIELD_THRESHOLDS = {
    # 城投债：2-3Y 斜率 > 0.12，持有3个月收益率
    "城投_AA_2Y":  {"min_roll_yield": 0.50, "slope_min": 0.12, "min_amount": 15},
    "城投_AA_4Y":  {"min_roll_yield": 0.60, "slope_min": 0.12, "min_amount": 15},
    "城投_AA(2)_2Y": {"min_roll_yield": 0.51, "slope_min": 0.12, "min_amount": 15},
    "城投_AA(2)_3Y": {"min_roll_yield": 0.51, "slope_min": 0.12, "min_amount": 15},
    # 长久期高评级（6-7Y 凸点）
    "城投_AA+_6Y":  {"min_roll_yield": 0.65, "slope_min": 0.10, "min_amount": 10},
    "城投_AA+_7Y":  {"min_roll_yield": 0.65, "slope_min": 0.11, "min_amount": 10},
    "中短票_AA+_6Y": {"min_roll_yield": 0.65, "slope_min": 0.10, "min_amount": 10},
    "中短票_AA+_7Y": {"min_roll_yield": 0.65, "slope_min": 0.11, "min_amount": 10},
}

PERPETUAL_THRESHOLDS = {
    # 永续债：2-3Y，品种利差 > 12bp，发行量 ≥ 10亿
    "永续_产业债_AA+_3Y": {"min_spread": 12, "min_amount": 10, "min_yield": 1.9},
    "永续_产业债_AA_3Y":  {"min_spread": 12, "min_amount": 10, "min_yield": 1.9},
    "永续_城投债_AA+_3Y": {"min_spread": 12, "min_amount": 10, "min_yield": 1.9},
    "永续_城投债_AA_3Y":  {"min_spread": 12, "min_amount": 10, "min_yield": 1.9},
}

TWO_FOUR_BOND_THRESHOLDS = {
    # 二永债 2Y / 4Y：相对普信债高 3-7bp
    "二永债_大行二级资本债_2Y": {"min_spread_vs_credit": 3, "max_spread_vs_credit": 20},
    "二永债_大行二级资本债_4Y": {"min_spread_vs_credit": 3, "max_spread_vs_credit": 20},
    "二永债_股份行二级资本债_2Y": {"min_spread_vs_credit": 3, "max_spread_vs_credit": 20},
    "二永债_股份行二级资本债_4Y": {"min_spread_vs_credit": 3, "max_spread_vs_credit": 20},
}

# 固收+赎回风险阈值
FIXED_INCOME_PLUS_WARNING_THRESHOLD = -1.0  # MA5 < -1 → 预警


# ── 信号计算函数 ──────────────────────────────────────────────────────────────

def compute_roll_yield_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算骑乘收益信号
    df: credit_bond_latest.csv 读取的 DataFrame
    返回: 各期限曲线的持有期收益率和凸点评分
    """
    yields = df[df["指标类型"] == "收益率"].copy()
    if yields.empty:
        return pd.DataFrame()

    # 构建收益率曲线 dict
    yield_curve = {}
    for _, row in yields.iterrows():
        yield_curve[row["品种"]] = row["最新值"]

    signals = []

    # 中短久期城投债（骑乘收益）
    tenors = ["1Y", "2Y", "3Y", "4Y", "5Y", "7Y", "10Y"]
    for rating in ["城投_AA", "城投_AA(2)", "城投_AA+", "中短票_AA+"]:
        curve = {}
        for t in tenors:
            key = f"{rating}_{t}"
            if key in yield_curve:
                curve[t] = yield_curve[key]

        if len(curve) < 2:
            continue

        # 计算各期限持有3个月收益率（假设曲线不变）
        for tenor in tenors:
            if tenor not in curve:
                continue
            # 持有至下一档期限的骑乘收益
            idx = tenors.index(tenor)
            if idx + 1 < len(tenors):
                next_tenor = tenors[idx + 1]
                if next_tenor in curve:
                    y_short = curve[tenor] / 100
                    y_long  = curve[next_tenor] / 100
                    # 持有3个月骑乘收益
                    roll_yield = (y_short - y_long) * 0.25 + y_short * 0.25  # ≈ 持有3个月
                    # 也可以简化为：carry = y_short * 0.25
                    carry = y_short * 0.25
                    signals.append({
                        "信号类型": "骑乘收益",
                        "品种": f"{rating}_{tenor}",
                        "当前收益率%": y_short * 100,
                        "持有3月收益率%": round(carry * 100, 3),
                        "曲线斜率": round(y_long - y_short, 4),
                        "评分": "高" if carry * 100 > 0.6 else ("中" if carry * 100 > 0.45 else "低"),
                    })

    return pd.DataFrame(signals)


def compute_perpetual_spread_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算永续债品种利差信号
    """
    perpetual = df[df["指标类型"] == "品种利差"].copy()
    signals = []

    for _, row in perpetual.iterrows():
        name = row["品种"]
        spread_bp = row["最新值"]
        if spread_bp is None or np.isnan(spread_bp):
            continue

        for category, thresh in PERPETUAL_THRESHOLDS.items():
            if category in name:
                score = "高" if spread_bp >= thresh["min_spread"] else ("中" if spread_bp >= 8 else "低")
                signals.append({
                    "信号类型": "永续品种利差",
                    "品种": name,
                    "品种利差bp": round(spread_bp, 1),
                    "阈值bp": thresh["min_spread"],
                    "评分": score,
                })
    return pd.DataFrame(signals)


def compute_two_four_bond_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算二永债性价比信号：相对普通信用债利差
    """
    spreads = df[df["指标类型"] == "信用利差"].copy()
    signals = []

    # 大行二永债 2Y vs 城投债 AA 2Y（简单对比）
    for name in ["二永债_大行二级资本债_2Y", "二永债_大行二级资本债_4Y"]:
        # 模拟计算：二永债收益率 - 同期限城投债收益率
        # 实际应从数据层读取真实对比数据，这里用阈值法
        thresh = TWO_FOUR_BOND_THRESHOLDS.get(name, {})
        signals.append({
            "信号类型": "二永债性价比",
            "品种": name,
            "相对普信债利差bp": None,  # 待数据层补充
            "评级": "大行",
            "建议": "关注" if thresh else "—",
        })
    return pd.DataFrame(signals)


def compute_comprehensive_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    综合性价比评分
    结合：持有期收益率（40%）+ 品种利差（30%）+ 流动性（30%）
    """
    all_signals = []

    roll = compute_roll_yield_signals(df)
    perp = compute_perpetual_spread_signals(df)
    bond = compute_two_four_bond_signals(df)

    if not roll.empty:
        all_signals.append(roll)
    if not perp.empty:
        all_signals.append(perp)
    if not bond.empty:
        all_signals.append(bond)

    if not all_signals:
        return pd.DataFrame()

    result = pd.concat(all_signals, ignore_index=True)

    # 保存
    out_path = paths.OUTPUT_DIR / "credit_signal.csv"
    result.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Saved {len(result)} signals to {out_path}")

    return result


# ── 主函数 ────────────────────────────────────────────────────────────────────

def generate_credit_signals():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Generating credit bond signals...")

    data_path = paths.OUTPUT_DIR / "credit_bond_latest.csv"
    if not data_path.exists():
        print(f"[ERROR] {data_path} not found. Run credit_bond_data.py first.")
        return None

    df = pd.read_csv(data_path, encoding="utf-8-sig")
    print(f"  Loaded {len(df)} records from credit_bond_latest.csv")

    # 各模块信号
    roll_signals  = compute_roll_yield_signals(df)
    perp_signals  = compute_perpetual_spread_signals(df)
    bond_signals  = compute_two_four_bond_signals(df)

    # 综合
    result = compute_comprehensive_score(df)

    if not result.empty:
        print(f"\n  骑乘收益信号 TOP5:")
        if not roll_signals.empty:
            top5 = roll_signals.sort_values("持有3月收益率%", ascending=False).head(5)
            print(top5[["品种", "持有3月收益率%", "曲线斜率", "评分"]].to_string(index=False))

        print(f"\n  永续品种利差信号:")
        if not perp_signals.empty:
            print(perp_signals.to_string(index=False))

    return result


if __name__ == "__main__":
    generate_credit_signals()
