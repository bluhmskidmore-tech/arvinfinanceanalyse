# -*- coding: utf-8 -*-
"""
DCC-GARCH 动态相关模型（滚动相关矩阵近似）
==========================================
用 GARCH 标准化残差 + 滚动窗口相关矩阵近似 DCC-GARCH，
监测多资产间动态条件相关性，识别相关性危机。

资产池: 沪深300、中证500、黄金、铜、原油
数据源: akshare（不依赖 Wind）
输出: 相关矩阵热力图 + 关键对时序图 + 预警状态
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
import matplotlib.colors as mcolors
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
    "steel":  "#4E6B8A",
    "mist":   "#EEF3F7",
    "grid":   "#C9D4E2",
    "text":   "#102235",
    "muted":  "#6C7A89",
}

ASSET_LABELS = {
    "hs300":     "沪深300",
    "csi500":    "中证500",
    "gold":      "黄金",
    "copper":    "铜",
    "crude_oil": "原油",
}

WINDOW = 60  # 滚动相关窗口（交易日）


# ============================================================
# 字体
# ============================================================

def _set_style():
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 160
    plt.rcParams["savefig.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["figure.facecolor"] = "white"


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

    if len(series) < 3:
        print("[致命] 有效资产不足3个，退出")
        sys.exit(1)

    prices = pd.concat(series.values(), axis=1).sort_index().dropna()
    cutoff = prices.index.max() - pd.DateOffset(years=5)
    prices = prices[prices.index >= cutoff]
    print(f"\n合并后: {len(prices)} 个交易日，资产: {list(prices.columns)}")
    print(f"区间: {prices.index[0].date()} ~ {prices.index[-1].date()}")
    return prices


# ============================================================
# GARCH 标准化 + 滚动相关
# ============================================================

def _garch_standardize(series: pd.Series, omega=1e-6, alpha=0.10, beta=0.85) -> pd.Series:
    """简化 GARCH(1,1) 标准化，得到标准化残差"""
    r = series.dropna().values.astype(float)
    n = len(r)
    sigma2 = np.empty(n)
    sigma2[0] = max(float(np.var(r)), 1e-8)
    for t in range(1, n):
        sigma2[t] = max(omega + alpha * r[t - 1] ** 2 + beta * sigma2[t - 1], 1e-10)
    return pd.Series(r / np.sqrt(sigma2), index=series.dropna().index, name=series.name)


def compute_dcc(log_ret: pd.DataFrame):
    print("\n[步骤2] GARCH 标准化残差...")
    std_resid = pd.DataFrame(
        {col: _garch_standardize(log_ret[col]) for col in log_ret.columns}
    ).dropna()
    print(f"  标准化残差矩阵: {std_resid.shape}")

    print(f"[步骤3] 滚动相关矩阵（窗口={WINDOW}日）...")
    cols = std_resid.columns.tolist()
    pairs = [(cols[i], cols[j]) for i in range(len(cols)) for j in range(i + 1, len(cols))]

    rolling = std_resid.rolling(window=WINDOW, min_periods=WINDOW // 2).corr()

    pair_series = {}
    for a, b in pairs:
        key = f"{a}_{b}"
        try:
            s = rolling.loc[(slice(None), a), b]
            s.index = s.index.droplevel(1)
            pair_series[key] = s.rename(key)
        except Exception:
            pair_series[key] = pd.Series(dtype=float, name=key)

    pair_df = pd.DataFrame(pair_series)
    avg_series = pair_df.mean(axis=1)

    # 最新相关矩阵
    n = len(cols)
    latest_corr = pd.DataFrame(np.eye(n), index=cols, columns=cols)
    for a, b in pairs:
        val = pair_series[f"{a}_{b}"].dropna()
        if len(val):
            v = float(val.iloc[-1])
            latest_corr.loc[a, b] = v
            latest_corr.loc[b, a] = v

    return pair_series, avg_series, latest_corr


def classify_warning(avg: float) -> str:
    if avg > 0.85:
        return "红色预警"
    elif avg > 0.70:
        return "黄色预警"
    return "正常"


# ============================================================
# 图表
# ============================================================

def plot_heatmap(corr_matrix: pd.DataFrame, date_str: str, avg: float, warning: str) -> Path:
    path = ASSET_DIR / "dcc_heatmap.png"
    labels = [ASSET_LABELS.get(c, c) for c in corr_matrix.columns]
    n = len(labels)
    data = corr_matrix.values.astype(float)

    fig, ax = plt.subplots(figsize=(7, 6))
    cmap = mcolors.LinearSegmentedColormap.from_list("corr", [COLORS["teal"], "#EEF3F7", COLORS["danger"]])
    im = ax.imshow(data, cmap=cmap, vmin=-1, vmax=1, aspect="auto")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=9)

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(labels, fontsize=10, color=COLORS["text"])
    ax.set_yticklabels(labels, fontsize=10, color=COLORS["text"])

    for i in range(n):
        for j in range(n):
            v = data[i, j]
            fc = "white" if abs(v) > 0.55 else COLORS["text"]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=10, color=fc, fontweight="bold")

    warn_color = COLORS["danger"] if warning == "红色预警" else (COLORS["gold"] if warning == "黄色预警" else COLORS["teal"])
    ax.set_title(
        f"DCC 动态相关矩阵  {date_str}\n平均相关系数: {avg:.3f}  [{warning}]",
        fontsize=11, color=warn_color, pad=12, fontweight="bold"
    )

    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_timeseries(pair_series: dict) -> Path:
    path = ASSET_DIR / "dcc_timeseries.png"
    key_pairs = [
        ("hs300", "gold"),
        ("hs300", "crude_oil"),
        ("gold", "crude_oil"),
        ("hs300", "csi500"),
    ]
    available = [(a, b) for a, b in key_pairs if f"{a}_{b}" in pair_series]

    fig, ax = plt.subplots(figsize=(9, 5))
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])
    ax.grid(axis="y", color=COLORS["grid"], linestyle="-", linewidth=0.7, alpha=0.7)

    palette = [COLORS["navy"], COLORS["gold"], COLORS["teal"], COLORS["orange"]]
    for idx, (a, b) in enumerate(available):
        s = pair_series[f"{a}_{b}"].dropna().tail(500)
        label = f"{ASSET_LABELS.get(a, a)} / {ASSET_LABELS.get(b, b)}"
        ax.plot(s.index, s.values, linewidth=1.8, color=palette[idx % len(palette)], label=label, alpha=0.9)

    ax.axhline(0.70, color=COLORS["gold"], linestyle="--", linewidth=1.2, alpha=0.8, label="黄色预警(0.70)")
    ax.axhline(0.85, color=COLORS["danger"], linestyle="--", linewidth=1.2, alpha=0.8, label="红色预警(0.85)")
    ax.axhline(0, color=COLORS["grid"], linewidth=0.8)

    ax.set_ylabel("滚动相关系数", color=COLORS["text"], fontsize=10)
    ax.set_ylim(-1.05, 1.05)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, ncol=2)
    ax.text(0.0, 1.08, "关键资产对动态相关性", transform=ax.transAxes,
            fontsize=13, fontweight="bold", color=COLORS["navy"], ha="left")
    ax.text(0.0, 1.02, f"GARCH 标准化残差滚动 {WINDOW} 日相关，相关性上升意味着分散化效果减弱",
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
    print("  DCC-GARCH 动态相关模型")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    _set_style()

    prices = load_prices()
    log_ret = np.log(prices / prices.shift(1)).dropna() * 100

    pair_series, avg_series, latest_corr = compute_dcc(log_ret)

    latest_date = log_ret.index[-1].strftime("%Y-%m-%d")
    avg = float(avg_series.dropna().iloc[-1])
    warning = classify_warning(avg)

    # 打印结果
    print(f"\n{'='*60}")
    print(f"  当前相关矩阵（{latest_date}，滚动{WINDOW}日）")
    print(f"{'='*60}")
    display = latest_corr.copy()
    display.index = [ASSET_LABELS.get(c, c) for c in display.index]
    display.columns = [ASSET_LABELS.get(c, c) for c in display.columns]
    print(display.round(3).to_string())

    print(f"\n  平均相关系数: {avg:.3f}")
    print(f"  预警状态: {warning}")
    if warning == "红色预警":
        print("  → 相关性极高，分散化失效，必须降仓或对冲")
    elif warning == "黄色预警":
        print("  → 相关性偏高，需警惕相关性跃升风险")
    else:
        print("  → 相关性处于合理水平，分散化有效")

    print(f"\n  关键资产对详情:")
    key_pairs = [("hs300", "gold"), ("hs300", "crude_oil"), ("gold", "crude_oil"),
                 ("hs300", "csi500"), ("hs300", "copper")]
    for a, b in key_pairs:
        key = f"{a}_{b}"
        if key in pair_series:
            s = pair_series[key].dropna()
            if len(s) == 0:
                continue
            latest_val = float(s.iloc[-1])
            trend_s = s.tail(30)
            if len(trend_s) >= 2:
                delta = trend_s.iloc[-1] - trend_s.iloc[0]
                trend = "↑上升" if delta > 0.05 else "↓下降" if delta < -0.05 else "→平稳"
            else:
                trend = "→"
            la = ASSET_LABELS.get(a, a)
            lb = ASSET_LABELS.get(b, b)
            print(f"    {la:<6} / {lb:<6}: {latest_val:+.3f}  {trend}")

    # 生成图表
    print("\n[步骤4] 生成图表...")
    heatmap_path = plot_heatmap(latest_corr, latest_date, avg, warning)
    print(f"  热力图: {heatmap_path}")
    ts_path = plot_timeseries(pair_series)
    print(f"  时序图: {ts_path}")

    # 保存 CSV
    cols = list(log_ret.columns)
    row = {"日期": latest_date}
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a, b = cols[i], cols[j]
            key = f"{a}_{b}"
            if key in pair_series:
                s = pair_series[key].dropna()
                row[key] = round(float(s.iloc[-1]), 4) if len(s) else None
    row["平均相关系数"] = round(avg, 4)
    row["预警状态"] = warning

    latest_path = ROOT / "dcc_latest.csv"
    pd.DataFrame([row]).to_csv(latest_path, index=False, encoding="utf-8-sig")
    print(f"  快照: {latest_path}")

    # 历史平均相关系数
    results_path = ROOT / "dcc_results.csv"
    avg_df = avg_series.dropna().reset_index()
    avg_df.columns = ["date", "avg_corr"]
    avg_df["warning"] = avg_df["avg_corr"].apply(classify_warning)
    avg_df.to_csv(results_path, index=False, encoding="utf-8-sig", float_format="%.4f")
    print(f"  历史序列: {results_path}")

    print("\n完成。")


if __name__ == "__main__":
    main()
