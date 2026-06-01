# -*- coding: utf-8 -*-
"""
再平衡策略模型
================
模拟组合权重漂移，评估时间触发（月度/季度）和阈值触发（偏离>5%）两种再平衡策略。
计算再平衡频率、交易成本、收益改善。

资产池: 沪深300、中证500、黄金、铜、原油
数据源: akshare（不依赖 Wind）
目标权重: 读取 risk_parity_results.csv（风险平价权重）
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import numpy as np
import pandas as pd
import akshare as ak
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from pathlib import Path

_PKG = Path(__file__).resolve().parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
from paths import OUTPUT_DIR, ASSET_DIR

ROOT = OUTPUT_DIR

COLORS = {
    "navy":   "#0B1F33",
    "gold":   "#C99A2E",
    "teal":   "#2E6F72",
    "orange": "#C76433",
    "danger": "#B83B3B",
    "sage":   "#6E8B6B",
    "grid":   "#C9D4E2",
    "text":   "#102235",
    "muted":  "#6C7A89",
    "mist":   "#EEF3F7",
}

ASSET_LABELS = {
    "hs300":     "沪深300",
    "csi500":    "中证500",
    "gold":      "黄金期货",
    "copper":    "铜期货",
    "crude_oil": "原油期货",
}

TRANSACTION_COST = 0.002  # 单边交易成本 0.2%
THRESHOLD = 0.05  # 阈值触发：偏离目标权重 5%


# ============================================================
# 数据获取
# ============================================================

def _fetch_index(symbol: str, name: str):
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        s = pd.to_numeric(df["close"], errors="coerce").rename(name)
        print(f"  {name}({symbol}): {len(s)} 条，最新 {s.index[-1].date()}")
        return s
    except Exception as e:
        print(f"  {name} 获取失败: {e}")
        return None


def _fetch_futures(symbol: str, name: str):
    try:
        today = datetime.now().strftime("%Y%m%d")
        df = ak.futures_main_sina(symbol=symbol, start_date="20150101", end_date=today)
        df = df[["日期", "收盘价"]].copy()
        df.columns = ["date", name]
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        df[name] = pd.to_numeric(df[name], errors="coerce")
        s = df[name]
        print(f"  {name}({symbol}): {len(s)} 条，最新 {s.index[-1].date()}")
        return s
    except Exception as e:
        print(f"  {name} 获取失败: {e}")
        return None


def load_prices() -> pd.DataFrame:
    print("\n[步骤1] 拉取资产价格...")
    series = {}
    for symbol, name in [("sh000300", "hs300"), ("sh000905", "csi500")]:
        s = _fetch_index(symbol, name)
        if s is not None:
            series[name] = s
    for symbol, name in [("AU0", "gold"), ("CU0", "copper"), ("SC0", "crude_oil")]:
        s = _fetch_futures(symbol, name)
        if s is not None:
            series[name] = s

    if len(series) < 2:
        print("[致命] 有效资产不足，退出")
        sys.exit(1)

    prices = pd.concat(series.values(), axis=1).sort_index()
    cutoff = prices.index.max() - pd.DateOffset(years=3)
    prices = prices[prices.index >= cutoff]
    print(f"\n合并后: {len(prices)} 个交易日，区间: {prices.index[0].date()} ~ {prices.index[-1].date()}")
    return prices


def load_target_weights() -> dict:
    """读取风险平价权重作为目标权重"""
    path = ROOT / "risk_parity_results.csv"
    if not path.exists():
        print(f"[警告] {path} 不存在，使用等权重")
        return {
            "hs300": 0.20,
            "csi500": 0.20,
            "gold": 0.20,
            "copper": 0.20,
            "crude_oil": 0.20,
        }

    df = pd.read_csv(path, encoding="utf-8-sig")
    weights = {}
    for _, row in df.iterrows():
        asset = row["资产"]
        weight = float(row["风险平价权重%"]) / 100.0
        # 映射中文名到英文 key
        for k, v in ASSET_LABELS.items():
            if v == asset:
                weights[k] = weight
                break

    print(f"\n目标权重（风险平价）:")
    for k, v in weights.items():
        print(f"  {ASSET_LABELS.get(k, k)}: {v*100:.2f}%")

    return weights


# ============================================================
# 再平衡策略
# ============================================================

def simulate_drift(prices: pd.DataFrame, target_weights: dict):
    """模拟权重漂移（不再平衡）"""
    assets = list(prices.columns)
    n = len(prices)

    # 初始权重
    weights = pd.DataFrame(index=prices.index, columns=assets, dtype=float)
    weights.iloc[0] = [target_weights.get(a, 0) for a in assets]

    # 每日权重漂移
    for i in range(1, n):
        prev_w = weights.iloc[i - 1].values
        ret = (prices.iloc[i] / prices.iloc[i - 1] - 1).values
        new_val = prev_w * (1 + ret)
        weights.iloc[i] = new_val / new_val.sum()

    return weights


def rebalance_time(prices: pd.DataFrame, target_weights: dict, freq="M"):
    """时间触发再平衡：月度(M)或季度(Q)"""
    assets = list(prices.columns)
    n = len(prices)

    weights = pd.DataFrame(index=prices.index, columns=assets, dtype=float)
    weights.iloc[0] = [target_weights.get(a, 0) for a in assets]

    rebalance_dates = []
    turnover = []

    last_rebal = prices.index[0]

    for i in range(1, n):
        prev_w = weights.iloc[i - 1].values
        ret = (prices.iloc[i] / prices.iloc[i - 1] - 1).values
        new_val = prev_w * (1 + ret)
        drifted_w = new_val / new_val.sum()

        # 检查是否到达再平衡周期
        current = prices.index[i]
        if freq == "M":
            trigger = (current.year > last_rebal.year) or (current.month > last_rebal.month)
        elif freq == "Q":
            trigger = (current.year > last_rebal.year) or (current.quarter > last_rebal.quarter)
        else:
            trigger = False

        if trigger:
            # 再平衡到目标权重
            target_w = np.array([target_weights.get(a, 0) for a in assets])
            turn = np.abs(target_w - drifted_w).sum()
            weights.iloc[i] = target_w
            rebalance_dates.append(current)
            turnover.append(turn)
            last_rebal = current
        else:
            weights.iloc[i] = drifted_w

    return weights, rebalance_dates, turnover


def rebalance_threshold(prices: pd.DataFrame, target_weights: dict, threshold=THRESHOLD):
    """阈值触发再平衡：任一资产偏离目标权重超过阈值"""
    assets = list(prices.columns)
    n = len(prices)

    weights = pd.DataFrame(index=prices.index, columns=assets, dtype=float)
    weights.iloc[0] = [target_weights.get(a, 0) for a in assets]

    rebalance_dates = []
    turnover = []

    for i in range(1, n):
        prev_w = weights.iloc[i - 1].values
        ret = (prices.iloc[i] / prices.iloc[i - 1] - 1).values
        new_val = prev_w * (1 + ret)
        drifted_w = new_val / new_val.sum()

        # 检查偏离
        target_w = np.array([target_weights.get(a, 0) for a in assets])
        deviation = np.abs(drifted_w - target_w)

        if deviation.max() > threshold:
            # 再平衡
            turn = np.abs(target_w - drifted_w).sum()
            weights.iloc[i] = target_w
            rebalance_dates.append(prices.index[i])
            turnover.append(turn)
        else:
            weights.iloc[i] = drifted_w

    return weights, rebalance_dates, turnover


def calculate_portfolio_return(prices: pd.DataFrame, weights: pd.DataFrame) -> pd.Series:
    """计算组合收益率"""
    ret = prices.pct_change().fillna(0)
    port_ret = (ret * weights.shift(1)).sum(axis=1)
    return port_ret


def evaluate_strategy(port_ret: pd.Series, turnover: list, name: str) -> dict:
    """评估策略绩效"""
    # 扣除交易成本
    total_cost = sum(turnover) * TRANSACTION_COST
    net_ret = port_ret.copy()
    # 简化：将总成本均摊到每日
    daily_cost = total_cost / len(net_ret) if len(net_ret) > 0 else 0
    net_ret = net_ret - daily_cost

    cum_ret = (1 + net_ret).cumprod()
    total_ret = float(cum_ret.iloc[-1] - 1) if len(cum_ret) else 0

    ann = 252
    years = len(net_ret) / ann
    annual_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
    annual_vol = float(net_ret.std() * np.sqrt(ann))
    sharpe = (annual_ret - 0.015) / annual_vol if annual_vol > 0 else 0

    rebal_count = len(turnover)
    avg_turnover = float(np.mean(turnover)) if turnover else 0

    return {
        "策略": name,
        "年化收益%": annual_ret * 100,
        "年化波动%": annual_vol * 100,
        "夏普比率": sharpe,
        "再平衡次数": rebal_count,
        "平均换手率%": avg_turnover * 100,
        "总交易成本%": total_cost * 100,
        "累计收益%": total_ret * 100,
    }


# ============================================================
# 图表
# ============================================================

def _set_style():
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 160
    plt.rcParams["savefig.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["figure.facecolor"] = "white"


def plot_comparison(prices: pd.DataFrame, results: dict) -> Path:
    """对比不同再平衡策略的累计收益"""
    path = ASSET_DIR / "rebalance_comparison.png"

    fig, ax = plt.subplots(figsize=(10, 6))

    palette = [COLORS["navy"], COLORS["gold"], COLORS["teal"], COLORS["orange"]]

    for idx, (name, data) in enumerate(results.items()):
        ret = data["returns"]
        cum = (1 + ret).cumprod()
        ax.plot(cum.index, cum.values, linewidth=2, color=palette[idx % len(palette)],
                label=name, alpha=0.9)

    ax.set_ylabel("累计净值", fontsize=10, color=COLORS["text"])
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    ax.grid(axis="y", color=COLORS["grid"], linestyle="-", linewidth=0.6, alpha=0.7)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])
    ax.tick_params(colors=COLORS["muted"], labelsize=9)

    ax.text(0.0, 1.06, "再平衡策略对比", transform=ax.transAxes,
            fontsize=13, fontweight="bold", color=COLORS["navy"], ha="left")
    ax.text(0.0, 1.01, "扣除交易成本后的累计净值曲线",
            transform=ax.transAxes, fontsize=8.5, color=COLORS["muted"], ha="left")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_weight_drift(weights_drift: pd.DataFrame, target_weights: dict) -> Path:
    """展示权重漂移（不再平衡情况）"""
    path = ASSET_DIR / "weight_drift.png"

    fig, ax = plt.subplots(figsize=(10, 6))

    palette = [COLORS["navy"], COLORS["gold"], COLORS["teal"], COLORS["orange"], COLORS["danger"]]

    for idx, col in enumerate(weights_drift.columns):
        label = ASSET_LABELS.get(col, col)
        ax.plot(weights_drift.index, weights_drift[col] * 100,
                linewidth=1.8, color=palette[idx % len(palette)], label=label, alpha=0.85)

        # 目标权重虚线
        target = target_weights.get(col, 0) * 100
        ax.axhline(target, color=palette[idx % len(palette)], linestyle="--",
                   linewidth=1, alpha=0.4)

    ax.set_ylabel("权重 (%)", fontsize=10, color=COLORS["text"])
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, ncol=2)
    ax.grid(axis="y", color=COLORS["grid"], linestyle="-", linewidth=0.6, alpha=0.7)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])
    ax.tick_params(colors=COLORS["muted"], labelsize=9)

    ax.text(0.0, 1.06, "权重漂移（不再平衡）", transform=ax.transAxes,
            fontsize=13, fontweight="bold", color=COLORS["navy"], ha="left")
    ax.text(0.0, 1.01, "虚线为目标权重，实线为实际权重漂移",
            transform=ax.transAxes, fontsize=8.5, color=COLORS["muted"], ha="left")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("  再平衡策略模型")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    _set_style()

    prices = load_prices()
    target_weights = load_target_weights()

    print("\n[步骤2] 模拟不同再平衡策略...")

    # 策略1: 不再平衡（权重漂移）
    weights_drift = simulate_drift(prices, target_weights)
    ret_drift = calculate_portfolio_return(prices, weights_drift)
    result_drift = evaluate_strategy(ret_drift, [], "不再平衡")

    # 策略2: 月度再平衡
    weights_monthly, dates_monthly, turn_monthly = rebalance_time(prices, target_weights, freq="M")
    ret_monthly = calculate_portfolio_return(prices, weights_monthly)
    result_monthly = evaluate_strategy(ret_monthly, turn_monthly, "月度再平衡")

    # 策略3: 季度再平衡
    weights_quarterly, dates_quarterly, turn_quarterly = rebalance_time(prices, target_weights, freq="Q")
    ret_quarterly = calculate_portfolio_return(prices, weights_quarterly)
    result_quarterly = evaluate_strategy(ret_quarterly, turn_quarterly, "季度再平衡")

    # 策略4: 阈值触发（5%）
    weights_threshold, dates_threshold, turn_threshold = rebalance_threshold(prices, target_weights, THRESHOLD)
    ret_threshold = calculate_portfolio_return(prices, weights_threshold)
    result_threshold = evaluate_strategy(ret_threshold, turn_threshold, f"阈值触发({THRESHOLD*100:.0f}%)")

    # 汇总结果
    results_df = pd.DataFrame([result_drift, result_monthly, result_quarterly, result_threshold])

    print(f"\n{'='*80}")
    print("  再平衡策略对比")
    print(f"{'='*80}")
    print(results_df.to_string(index=False))

    # 最优策略
    best_idx = results_df["夏普比率"].idxmax()
    best = results_df.iloc[best_idx]
    print(f"\n  最优策略: {best['策略']}（夏普比率 {best['夏普比率']:.3f}）")

    # 保存 CSV
    out_path = ROOT / "rebalance_results.csv"
    results_df.to_csv(out_path, index=False, encoding="utf-8-sig", float_format="%.4f")
    print(f"\n  已保存: {out_path}")

    # 图表
    print("\n[步骤3] 生成图表...")

    results_dict = {
        "不再平衡": {"returns": ret_drift},
        "月度再平衡": {"returns": ret_monthly},
        "季度再平衡": {"returns": ret_quarterly},
        f"阈值触发({THRESHOLD*100:.0f}%)": {"returns": ret_threshold},
    }

    comp_path = plot_comparison(prices, results_dict)
    print(f"  对比图: {comp_path}")

    drift_path = plot_weight_drift(weights_drift, target_weights)
    print(f"  漂移图: {drift_path}")

    print("\n完成。")


if __name__ == "__main__":
    main()
