# -*- coding: utf-8 -*-
"""
CTA 趋势跟踪模型
================
三种信号合成：双均线交叉 + 唐奇安通道突破 + ATR 波动率调整仓位
资产池: 沪深300、中证500、黄金、铜、原油
数据源: akshare（不依赖 Wind）
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
    "gold":      "黄金",
    "copper":    "铜",
    "crude_oil": "原油",
}

RF = 0.015  # 无风险利率年化


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
    cutoff = prices.index.max() - pd.DateOffset(years=5)
    prices = prices[prices.index >= cutoff]
    print(f"\n合并后: {len(prices)} 个交易日，区间: {prices.index[0].date()} ~ {prices.index[-1].date()}")
    return prices


# ============================================================
# 信号计算
# ============================================================

def signal_ma_cross(price: pd.Series, short=20, long=60) -> pd.Series:
    """双均线交叉：短>长 → +1，短<长 → -1"""
    ma_s = price.rolling(short).mean()
    ma_l = price.rolling(long).mean()
    sig = pd.Series(np.where(ma_s > ma_l, 1.0, -1.0), index=price.index)
    sig[ma_s.isna() | ma_l.isna()] = np.nan
    return sig


def signal_donchian(price: pd.Series, window=20) -> pd.Series:
    """唐奇安通道突破：突破高点 → +1，跌破低点 → -1，否则持仓不变（前值填充）"""
    high = price.rolling(window).max().shift(1)
    low  = price.rolling(window).min().shift(1)
    sig = pd.Series(np.nan, index=price.index)
    sig[price > high] = 1.0
    sig[price < low]  = -1.0
    sig = sig.ffill().fillna(0.0)
    return sig


def signal_atr_position(price: pd.Series, atr_window=14, target_vol=0.01) -> pd.Series:
    """ATR 波动率调整仓位：仓位 = 目标日波动率 / ATR，结合均线方向"""
    high = price  # 只有收盘价，用收盘价近似 high/low
    low  = price
    tr = pd.concat([
        (high - low).abs(),
        (high - price.shift(1)).abs(),
        (low  - price.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_window).mean()
    daily_ret_std = np.log(price / price.shift(1)).rolling(atr_window).std()
    # 用收益率标准差代替 ATR（因为只有收盘价）
    pos = (target_vol / daily_ret_std.replace(0, np.nan)).clip(0, 1.0)
    # 均线方向决定多空
    ma_sig = signal_ma_cross(price)
    pos = pos * ma_sig.clip(0, 1)  # 均线空头时仓位=0
    return pos.fillna(0.0)


def compute_composite(price: pd.Series) -> pd.DataFrame:
    """计算三种信号并合成"""
    ma   = signal_ma_cross(price)
    don  = signal_donchian(price)
    atr  = signal_atr_position(price)

    # 合成：均线(-1/+1) × 0.4 + 通道(-1/0/+1) × 0.3 + ATR仓位(0~1) × 0.3
    composite = (ma * 0.4 + don * 0.3 + atr * 0.3)
    composite = composite.apply(lambda x: float(np.tanh(x)) if not np.isnan(x) else np.nan)

    return pd.DataFrame({
        "ma_signal":   ma,
        "don_signal":  don,
        "atr_position": atr,
        "composite":   composite,
    })


def trend_label(val: float) -> str:
    if val > 0.5:   return "强多头"
    if val > 0.2:   return "弱多头"
    if val > -0.2:  return "震荡观望"
    if val > -0.5:  return "弱空头"
    return "强空头"


def trend_strength(val: float) -> str:
    if abs(val) > 0.5:  return "强趋势"
    if abs(val) > 0.2:  return "弱趋势"
    return "震荡"


# ============================================================
# 回测
# ============================================================

def backtest(price: pd.Series, signals: pd.DataFrame, years: int = 2) -> dict:
    """用合成信号（前一日）× 当日收益率，计算策略绩效"""
    cutoff = price.index.max() - pd.DateOffset(years=years)
    p = price[price.index >= cutoff].dropna()
    sig = signals["composite"].reindex(p.index).shift(1).fillna(0)

    log_ret = np.log(p / p.shift(1)).dropna()
    sig = sig.reindex(log_ret.index)

    strat_ret = sig * log_ret
    bh_ret    = log_ret

    ann = 252
    strat_ann = float(strat_ret.mean() * ann)
    strat_vol = float(strat_ret.std() * np.sqrt(ann))
    strat_sharpe = (strat_ann - RF) / strat_vol if strat_vol > 0 else np.nan

    bh_ann = float(bh_ret.mean() * ann)

    return {
        "strat_annual_ret": strat_ann * 100,
        "strat_sharpe":     strat_sharpe,
        "bh_annual_ret":    bh_ann * 100,
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


def plot_signals(prices: pd.DataFrame, all_signals: dict) -> Path:
    path = ASSET_DIR / "cta_signals.png"
    assets = list(prices.columns)
    n = len(assets)
    palette = [COLORS["navy"], COLORS["gold"], COLORS["teal"], COLORS["orange"], COLORS["danger"]]

    fig, axes = plt.subplots(n, 1, figsize=(10, 2.8 * n), sharex=False)
    if n == 1:
        axes = [axes]

    for idx, asset in enumerate(assets):
        ax = axes[idx]
        sig = all_signals[asset]["composite"].dropna().tail(130)  # 约6个月
        label = ASSET_LABELS.get(asset, asset)
        color = palette[idx % len(palette)]

        ax.fill_between(sig.index, sig.values, 0,
                        where=sig.values >= 0, color=color, alpha=0.35)
        ax.fill_between(sig.index, sig.values, 0,
                        where=sig.values < 0, color=COLORS["danger"], alpha=0.25)
        ax.plot(sig.index, sig.values, color=color, linewidth=1.6)
        ax.axhline(0, color=COLORS["grid"], linewidth=0.8)
        ax.axhline(0.5,  color=color, linestyle="--", linewidth=0.8, alpha=0.5)
        ax.axhline(-0.5, color=COLORS["danger"], linestyle="--", linewidth=0.8, alpha=0.5)
        ax.set_ylim(-1.1, 1.1)
        ax.set_ylabel("合成信号", fontsize=8, color=COLORS["muted"])
        ax.set_facecolor("white")
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        ax.spines["left"].set_color(COLORS["grid"])
        ax.spines["bottom"].set_color(COLORS["grid"])
        ax.tick_params(colors=COLORS["muted"], labelsize=8)
        ax.grid(axis="y", color=COLORS["grid"], linestyle="-", linewidth=0.5, alpha=0.6)

        latest_val = float(sig.iloc[-1]) if len(sig) else 0
        ax.text(0.01, 0.88, f"{label}  {latest_val:+.3f}  {trend_label(latest_val)}",
                transform=ax.transAxes, fontsize=10, fontweight="bold",
                color=color, va="top")

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        fig.autofmt_xdate(rotation=20)

    fig.suptitle("CTA 趋势信号（近6个月）", fontsize=13, fontweight="bold",
                 color=COLORS["navy"], y=1.01)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("  CTA 趋势跟踪模型")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    _set_style()
    prices = load_prices()

    print("\n[步骤2] 计算趋势信号...")
    all_signals = {}
    rows = []

    for asset in prices.columns:
        price = prices[asset].dropna()
        sigs  = compute_composite(price)
        all_signals[asset] = sigs
        bt    = backtest(price, sigs)

        latest = sigs.dropna().iloc[-1] if len(sigs.dropna()) else sigs.iloc[-1]
        comp   = float(latest["composite"]) if not np.isnan(latest["composite"]) else 0.0

        rows.append({
            "资产":        ASSET_LABELS.get(asset, asset),
            "均线信号":    int(latest["ma_signal"]) if not np.isnan(latest["ma_signal"]) else 0,
            "通道信号":    round(float(latest["don_signal"]), 2),
            "ATR仓位":     round(float(latest["atr_position"]), 3),
            "合成信号":    round(comp, 3),
            "趋势强度":    trend_strength(comp),
            "操作建议":    trend_label(comp),
            "策略年化收益%": round(bt["strat_annual_ret"], 2),
            "策略夏普比率": round(bt["strat_sharpe"], 3) if not np.isnan(bt["strat_sharpe"]) else "-",
            "买持年化收益%": round(bt["bh_annual_ret"], 2),
        })

    df = pd.DataFrame(rows)

    print(f"\n{'='*70}")
    print("  当前趋势信号汇总")
    print(f"{'='*70}")
    print(f"  {'资产':<8} {'均线':>5} {'通道':>6} {'ATR仓位':>8} {'合成':>7} {'强度':<6} {'建议':<8} {'策略年化%':>9} {'夏普':>7}")
    print(f"  {'-'*68}")
    for _, r in df.iterrows():
        print(f"  {r['资产']:<8} {r['均线信号']:>5} {r['通道信号']:>6.2f} {r['ATR仓位']:>8.3f} "
              f"{r['合成信号']:>7.3f} {r['趋势强度']:<6} {r['操作建议']:<8} "
              f"{r['策略年化收益%']:>9.2f} {str(r['策略夏普比率']):>7}")

    # 趋势最强
    strongest = df.loc[df["合成信号"].abs().idxmax(), "资产"]
    print(f"\n  趋势最强资产: {strongest}（合成信号 {df.loc[df['合成信号'].abs().idxmax(), '合成信号']:+.3f}）")

    # 保存 CSV
    out_path = ROOT / "cta_results.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n  已保存: {out_path}")

    # 图表
    print("\n[步骤3] 生成图表...")
    chart_path = plot_signals(prices, all_signals)
    print(f"  信号图: {chart_path}")

    print("\n完成。")


if __name__ == "__main__":
    main()
