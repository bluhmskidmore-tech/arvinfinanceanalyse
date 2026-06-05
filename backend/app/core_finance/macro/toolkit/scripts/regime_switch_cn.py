# -*- coding: utf-8 -*-
"""
市场状态转换模型
================
识别市场所处状态：趋势市 / 震荡市 / 高波动市
使用指标：滚动波动率、收益率自相关、ADX 近似、Hurst 指数
根据状态输出策略建议（趋势跟踪 / 均值回归 / 防御）

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

# 状态判断阈值
VOL_HIGH_PCTILE  = 75   # 波动率高于历史 75 分位 → 高波动
VOL_LOW_PCTILE   = 40   # 波动率低于历史 40 分位 → 低波动
AUTOCORR_TREND   = 0.10  # 自相关 > 0.10 → 趋势
AUTOCORR_MEAN_REV = -0.10  # 自相关 < -0.10 → 均值回归
HURST_TREND      = 0.55  # Hurst > 0.55 → 趋势持续
HURST_MEAN_REV   = 0.45  # Hurst < 0.45 → 均值回归


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
# 状态指标计算
# ============================================================

def rolling_volatility(ret: pd.Series, window: int = 20) -> pd.Series:
    """滚动年化波动率"""
    return ret.rolling(window).std() * np.sqrt(252)


def rolling_autocorr(ret: pd.Series, window: int = 20, lag: int = 1) -> pd.Series:
    """滚动自相关系数（lag=1）"""
    return ret.rolling(window).apply(
        lambda x: pd.Series(x).autocorr(lag=lag) if len(x) >= lag + 2 else np.nan,
        raw=False
    )


def hurst_exponent(ts: np.ndarray) -> float:
    """
    R/S 分析估计 Hurst 指数
    H > 0.5: 趋势持续（动量）
    H < 0.5: 均值回归
    H ≈ 0.5: 随机游走
    """
    n = len(ts)
    if n < 20:
        return 0.5

    lags = range(2, min(n // 2, 50))
    rs_vals = []
    lag_vals = []

    for lag in lags:
        # 分段 R/S
        segments = n // lag
        if segments < 2:
            continue
        rs_list = []
        for i in range(segments):
            seg = ts[i * lag:(i + 1) * lag]
            mean_seg = np.mean(seg)
            dev = np.cumsum(seg - mean_seg)
            r = np.max(dev) - np.min(dev)
            s = np.std(seg, ddof=1)
            if s > 0:
                rs_list.append(r / s)
        if rs_list:
            rs_vals.append(np.log(np.mean(rs_list)))
            lag_vals.append(np.log(lag))

    if len(lag_vals) < 2:
        return 0.5

    # 线性回归斜率 = Hurst 指数
    coeffs = np.polyfit(lag_vals, rs_vals, 1)
    return float(np.clip(coeffs[0], 0.0, 1.0))


def rolling_hurst(ret: pd.Series, window: int = 60) -> pd.Series:
    """滚动 Hurst 指数"""
    return ret.rolling(window).apply(
        lambda x: hurst_exponent(x.values),
        raw=False
    )


def adx_approx(price: pd.Series, window: int = 14) -> pd.Series:
    """
    ADX 近似（仅用收盘价）
    用绝对收益率的平滑均值 / 波动率 近似趋势强度
    """
    ret = price.pct_change().abs()
    smooth_ret = ret.rolling(window).mean()
    vol = price.pct_change().rolling(window).std()
    adx = (smooth_ret / vol.replace(0, np.nan)).clip(0, 3)
    return adx


# ============================================================
# 状态分类
# ============================================================

def classify_regime(
    vol: float,
    vol_low: float,
    vol_high: float,
    autocorr: float,
    hurst: float,
) -> str:
    """
    三状态分类：
    - 高波动市: 波动率 > 历史 75 分位
    - 趋势市:   低波动 + 正自相关 + Hurst > 0.55
    - 震荡市:   低波动 + 负自相关 or Hurst < 0.45
    - 中性:     其他
    """
    if np.isnan(vol) or np.isnan(autocorr) or np.isnan(hurst):
        return "未知"

    if vol > vol_high:
        return "高波动"

    if autocorr > AUTOCORR_TREND and hurst > HURST_TREND:
        return "趋势市"

    if autocorr < AUTOCORR_MEAN_REV or hurst < HURST_MEAN_REV:
        return "震荡市"

    # 弱趋势 / 弱震荡
    if autocorr > 0:
        return "弱趋势"
    return "弱震荡"


REGIME_STRATEGY = {
    "趋势市":  "趋势跟踪（CTA 多头）",
    "弱趋势":  "轻仓趋势跟踪",
    "震荡市":  "均值回归（高抛低吸）",
    "弱震荡":  "轻仓均值回归",
    "高波动":  "防御（降仓 / 对冲）",
    "未知":    "观望",
}

REGIME_COLORS = {
    "趋势市":  "#2E6F72",   # teal
    "弱趋势":  "#6E8B6B",   # sage
    "震荡市":  "#C99A2E",   # gold
    "弱震荡":  "#C76433",   # orange
    "高波动":  "#B83B3B",   # danger
    "未知":    "#6C7A89",   # muted
}


def compute_regime(price: pd.Series, vol_window=20, autocorr_window=20, hurst_window=60) -> pd.DataFrame:
    """计算单资产的状态序列"""
    ret = np.log(price / price.shift(1))

    vol = rolling_volatility(ret, vol_window)
    autocorr = rolling_autocorr(ret, autocorr_window)
    hurst = rolling_hurst(ret, hurst_window)
    adx = adx_approx(price)

    # 历史分位数（用于波动率阈值）
    vol_low_thresh  = vol.quantile(VOL_LOW_PCTILE / 100)
    vol_high_thresh = vol.quantile(VOL_HIGH_PCTILE / 100)

    regime = pd.Series(index=price.index, dtype=str)
    for i in range(len(price)):
        regime.iloc[i] = classify_regime(
            vol.iloc[i] if not np.isnan(vol.iloc[i]) else np.nan,
            vol_low_thresh,
            vol_high_thresh,
            autocorr.iloc[i] if not np.isnan(autocorr.iloc[i]) else np.nan,
            hurst.iloc[i] if not np.isnan(hurst.iloc[i]) else np.nan,
        )

    return pd.DataFrame({
        "vol":      vol,
        "autocorr": autocorr,
        "hurst":    hurst,
        "adx":      adx,
        "regime":   regime,
    })


def regime_stats(regime_series: pd.Series) -> dict:
    """统计各状态占比"""
    counts = regime_series.value_counts()
    total = len(regime_series.dropna())
    stats = {}
    for r in ["趋势市", "弱趋势", "震荡市", "弱震荡", "高波动", "未知"]:
        stats[r] = counts.get(r, 0) / total * 100 if total > 0 else 0
    return stats


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


def plot_regime_overview(prices: pd.DataFrame, all_regimes: dict) -> Path:
    """每个资产的价格 + 状态背景色"""
    path = ASSET_DIR / "regime_overview.png"
    assets = list(prices.columns)
    n = len(assets)

    fig, axes = plt.subplots(n, 1, figsize=(11, 3.2 * n), sharex=False)
    if n == 1:
        axes = [axes]

    for idx, asset in enumerate(assets):
        ax = axes[idx]
        price = prices[asset].dropna().tail(500)
        reg_df = all_regimes[asset].reindex(price.index)
        label = ASSET_LABELS.get(asset, asset)

        # 背景色块
        prev_regime = None
        start_i = 0
        dates = price.index.tolist()
        regimes = reg_df["regime"].tolist()

        for i, (d, r) in enumerate(zip(dates, regimes)):
            if r != prev_regime:
                if prev_regime is not None and prev_regime in REGIME_COLORS:
                    ax.axvspan(dates[start_i], d,
                               color=REGIME_COLORS[prev_regime], alpha=0.15, linewidth=0)
                start_i = i
                prev_regime = r
        # 最后一段
        if prev_regime and prev_regime in REGIME_COLORS and start_i < len(dates):
            ax.axvspan(dates[start_i], dates[-1],
                       color=REGIME_COLORS[prev_regime], alpha=0.15, linewidth=0)

        ax.plot(price.index, price.values, color=COLORS["navy"], linewidth=1.5)
        ax.set_ylabel("价格", fontsize=8, color=COLORS["muted"])
        ax.set_facecolor("white")
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        ax.spines["left"].set_color(COLORS["grid"])
        ax.spines["bottom"].set_color(COLORS["grid"])
        ax.tick_params(colors=COLORS["muted"], labelsize=8)
        ax.grid(axis="y", color=COLORS["grid"], linestyle="-", linewidth=0.5, alpha=0.5)

        # 当前状态标注
        latest_regime = reg_df["regime"].dropna().iloc[-1] if len(reg_df["regime"].dropna()) else "未知"
        latest_hurst  = reg_df["hurst"].dropna().iloc[-1] if len(reg_df["hurst"].dropna()) else np.nan
        latest_autocorr = reg_df["autocorr"].dropna().iloc[-1] if len(reg_df["autocorr"].dropna()) else np.nan
        rc = REGIME_COLORS.get(latest_regime, COLORS["muted"])
        ax.text(0.01, 0.92,
                f"{label}  [{latest_regime}]  Hurst={latest_hurst:.2f}  AC={latest_autocorr:.2f}",
                transform=ax.transAxes, fontsize=9.5, fontweight="bold",
                color=rc, va="top")

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        fig.autofmt_xdate(rotation=20)

    fig.suptitle("市场状态识别（近2年）", fontsize=13, fontweight="bold",
                 color=COLORS["navy"], y=1.005)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_regime_distribution(all_regimes: dict) -> Path:
    """各资产状态分布堆叠柱状图"""
    path = ASSET_DIR / "regime_distribution.png"

    regime_order = ["趋势市", "弱趋势", "震荡市", "弱震荡", "高波动"]
    assets = list(all_regimes.keys())
    labels = [ASSET_LABELS.get(a, a) for a in assets]

    data = {}
    for r in regime_order:
        data[r] = []
        for asset in assets:
            reg_series = all_regimes[asset]["regime"].dropna()
            pct = (reg_series == r).sum() / len(reg_series) * 100 if len(reg_series) > 0 else 0
            data[r].append(pct)

    fig, ax = plt.subplots(figsize=(9, 5))

    bottoms = np.zeros(len(assets))
    bar_colors = [REGIME_COLORS[r] for r in regime_order]

    for r, color in zip(regime_order, bar_colors):
        vals = np.array(data[r])
        bars = ax.bar(labels, vals, bottom=bottoms, color=color, alpha=0.85, label=r, width=0.55)
        # 标注百分比（>5% 才显示）
        for bar, val, bot in zip(bars, vals, bottoms):
            if val > 5:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bot + val / 2,
                        f"{val:.0f}%",
                        ha="center", va="center", fontsize=8.5,
                        color="white", fontweight="bold")
        bottoms += vals

    ax.set_ylabel("占比 (%)", fontsize=10, color=COLORS["text"])
    ax.set_ylim(0, 105)
    ax.legend(loc="upper right", frameon=False, fontsize=9, ncol=2)
    ax.grid(axis="y", color=COLORS["grid"], linestyle="-", linewidth=0.6, alpha=0.6)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])
    ax.tick_params(colors=COLORS["muted"], labelsize=9)

    ax.text(0.0, 1.06, "市场状态分布（近5年）", transform=ax.transAxes,
            fontsize=13, fontweight="bold", color=COLORS["navy"], ha="left")
    ax.text(0.0, 1.01, "各资产处于不同状态的历史占比",
            transform=ax.transAxes, fontsize=8.5, color=COLORS["muted"], ha="left")

    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_hurst_timeseries(prices: pd.DataFrame, all_regimes: dict) -> Path:
    """关键资产的 Hurst 指数时序"""
    path = ASSET_DIR / "hurst_timeseries.png"

    key_assets = ["hs300", "gold", "crude_oil"]
    available = [a for a in key_assets if a in all_regimes]

    fig, ax = plt.subplots(figsize=(10, 5))

    palette = [COLORS["navy"], COLORS["gold"], COLORS["danger"]]
    for idx, asset in enumerate(available):
        h = all_regimes[asset]["hurst"].dropna().tail(500)
        label = ASSET_LABELS.get(asset, asset)
        ax.plot(h.index, h.values, linewidth=1.8,
                color=palette[idx % len(palette)], label=label, alpha=0.9)

    ax.axhline(HURST_TREND, color=COLORS["teal"], linestyle="--", linewidth=1.2,
               alpha=0.8, label=f"趋势阈值({HURST_TREND})")
    ax.axhline(HURST_MEAN_REV, color=COLORS["orange"], linestyle="--", linewidth=1.2,
               alpha=0.8, label=f"均值回归阈值({HURST_MEAN_REV})")
    ax.axhline(0.5, color=COLORS["grid"], linewidth=0.8)

    ax.set_ylabel("Hurst 指数", fontsize=10, color=COLORS["text"])
    ax.set_ylim(0.2, 0.85)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, ncol=2)
    ax.grid(axis="y", color=COLORS["grid"], linestyle="-", linewidth=0.6, alpha=0.6)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])
    ax.tick_params(colors=COLORS["muted"], labelsize=9)

    ax.text(0.0, 1.06, "Hurst 指数时序", transform=ax.transAxes,
            fontsize=13, fontweight="bold", color=COLORS["navy"], ha="left")
    ax.text(0.0, 1.01, ">0.55 趋势持续，<0.45 均值回归，≈0.5 随机游走",
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
    print("  市场状态转换模型")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    _set_style()
    prices = load_prices()

    print("\n[步骤2] 计算市场状态指标...")
    all_regimes = {}
    rows = []

    for asset in prices.columns:
        price = prices[asset].dropna()
        print(f"  计算 {ASSET_LABELS.get(asset, asset)}...")
        reg_df = compute_regime(price)
        all_regimes[asset] = reg_df

        # 最新状态
        latest = reg_df.dropna(subset=["regime"]).iloc[-1] if len(reg_df.dropna(subset=["regime"])) else None
        if latest is None:
            continue

        regime = latest["regime"]
        stats = regime_stats(reg_df["regime"])

        rows.append({
            "资产":       ASSET_LABELS.get(asset, asset),
            "当前状态":   regime,
            "策略建议":   REGIME_STRATEGY.get(regime, "观望"),
            "Hurst指数":  round(float(latest["hurst"]), 3) if not np.isnan(latest["hurst"]) else "-",
            "自相关(1日)": round(float(latest["autocorr"]), 3) if not np.isnan(latest["autocorr"]) else "-",
            "年化波动率%": round(float(latest["vol"]) * 100, 2) if not np.isnan(latest["vol"]) else "-",
            "趋势市占比%": round(stats["趋势市"] + stats["弱趋势"], 1),
            "震荡市占比%": round(stats["震荡市"] + stats["弱震荡"], 1),
            "高波动占比%": round(stats["高波动"], 1),
        })

    df = pd.DataFrame(rows)

    print(f"\n{'='*75}")
    print("  当前市场状态汇总")
    print(f"{'='*75}")
    for _, r in df.iterrows():
        rc = REGIME_COLORS.get(r["当前状态"], "")
        print(f"  {r['资产']:<8}  [{r['当前状态']:<5}]  Hurst={r['Hurst指数']}  "
              f"AC={r['自相关(1日)']}  波动={r['年化波动率%']}%  → {r['策略建议']}")

    # 整体市场状态（以沪深300为基准）
    if "hs300" in all_regimes:
        hs300_regime = all_regimes["hs300"]["regime"].dropna().iloc[-1]
        print(f"\n  A股整体状态: [{hs300_regime}] → {REGIME_STRATEGY.get(hs300_regime, '观望')}")

    # 保存 CSV
    out_path = ROOT / "regime_results.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n  已保存: {out_path}")

    # 图表
    print("\n[步骤3] 生成图表...")
    overview_path = plot_regime_overview(prices, all_regimes)
    print(f"  状态概览图: {overview_path}")

    dist_path = plot_regime_distribution(all_regimes)
    print(f"  分布图: {dist_path}")

    hurst_path = plot_hurst_timeseries(prices, all_regimes)
    print(f"  Hurst时序图: {hurst_path}")

    print("\n完成。")


if __name__ == "__main__":
    main()
