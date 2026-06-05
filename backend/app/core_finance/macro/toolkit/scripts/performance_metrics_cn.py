# -*- coding: utf-8 -*-
import sys, os, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime, timedelta
from pathlib import Path

_PKG = Path(__file__).resolve().parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
from paths import OUTPUT_DIR, ASSET_DIR

COLORS = {"navy":"#0B1F33","gold":"#C99A2E","danger":"#B83B3B","teal":"#2E6F72","sage":"#6E8B6B"}
ASSET_COLORS = ["#0B1F33","#C99A2E","#B83B3B","#2E6F72","#6E8B6B"]
RF_ANNUAL = 0.015
TRADING_DAYS = 252
LOOKBACK_YEARS = 3
ASSETS = {
    "沪深300": {"type": "index",   "symbol": "sh000300"},
    "中诅500": {"type": "index",   "symbol": "sh000905"},
    "黄金期货": {"type": "futures", "symbol": "AU0"},
    "铜期货":  {"type": "futures", "symbol": "CU0"},
    "原油期货": {"type": "futures", "symbol": "SC0"},
}
CSV_OUT    = str(OUTPUT_DIR / "performance_results.csv")
IMG_OUT    = str(ASSET_DIR / "performance.png")
RP_CSV     = str(OUTPUT_DIR / "risk_parity_results.csv")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def fetch_price_series(name, info):
    import akshare as ak
    today_str = datetime.today().strftime("%Y%m%d")
    try:
        if info["type"] == "index":
            df = ak.stock_zh_index_daily(symbol=info["symbol"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            series = df["close"].rename(name)
        else:
            df = ak.futures_main_sina(symbol=info["symbol"], start_date="20150101", end_date=today_str)
            date_col = [c for c in df.columns if "date" in c.lower() or "日期" in c][0]
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.set_index(date_col).sort_index()
            close_col = [c for c in df.columns if "close" in c.lower() or "收盘" in c][0]
            series = df[close_col].rename(name)
        series = series.dropna()
        print(f"  [{name}] 获取成功，共 {len(series)} 条，最新日期 {series.index[-1].date()}")
        return series
    except Exception as e:
        print(f"  [{name}] 获取失败：{e}")
        return None


def calc_metrics(returns, label):
    r = returns.dropna()
    if len(r) < 20:
        return None
    ann_ret = r.mean() * TRADING_DAYS
    ann_vol = r.std() * (TRADING_DAYS ** 0.5)
    cum = (1 + r).cumprod()
    roll_max = cum.cummax()
    drawdown = (cum - roll_max) / roll_max
    max_dd = drawdown.min()
    sharpe = (ann_ret - RF_ANNUAL) / ann_vol if ann_vol > 0 else float("nan")
    neg_r = r[r < 0]
    if len(neg_r) > 1:
        ds = neg_r.std() * (TRADING_DAYS ** 0.5)
        sortino = (ann_ret - RF_ANNUAL) / ds if ds > 0 else float("nan")
    else:
        sortino = float("nan")
    calmar = ann_ret / abs(max_dd) if max_dd != 0 else float("nan")
    if sharpe >= 1.0:
        rating = "优秀"
    elif sharpe >= 0.5:
        rating = "良好"
    else:
        rating = "需优化"
    return {
        "资产/组合":  label,
        "年化收益%":  round(ann_ret * 100, 2),
        "年化波动%":  round(ann_vol * 100, 2),
        "最大回撤%":  round(max_dd * 100, 2),
        "夏普比率":   round(sharpe, 4),
        "索提诺比率": round(sortino, 4),
        "Calmar比率": round(calmar, 4),
        "评级":       rating,
    }


def portfolio_returns(returns_df, weights):
    aligned = returns_df.dropna()
    w = weights / weights.sum()
    return (aligned * w).sum(axis=1)

def plot_performance(df, path):
    fig = plt.figure(figsize=(14, 6), facecolor="white")
    gs = gridspec.GridSpec(1, 2, figure=fig, wspace=0.38)
    labels   = df["资产/组合"].tolist()
    sharpes  = df["夏普比率"].tolist()
    ann_rets = df["年化收益%"].tolist()
    max_dds  = df["最大回撤%"].abs().tolist()
    palette  = (ASSET_COLORS * 4)[:len(labels)]

    ax1 = fig.add_subplot(gs[0])
    bars = ax1.barh(labels, sharpes, color=palette, edgecolor="white", height=0.55)
    ax1.axvline(0,   color="gray",         lw=0.8, ls="--")
    ax1.axvline(0.5, color=COLORS["gold"], lw=1.0, ls="--", alpha=0.8, label="良好 0.5")
    ax1.axvline(1.0, color=COLORS["teal"], lw=1.0, ls="--", alpha=0.8, label="优秀 1.0")
    for bar, val in zip(bars, sharpes):
        ax1.text(val + 0.02, bar.get_y() + bar.get_height() / 2,
                 f"{val:.3f}", va="center", fontsize=8.5, color=COLORS["navy"])
    ax1.set_xlabel("夏普比率", fontsize=10)
    ax1.set_title("夏普比率对比", fontsize=12, fontweight="bold", color=COLORS["navy"])
    ax1.legend(fontsize=8, loc="lower right")
    ax1.invert_yaxis()
    ax1.spines[["top", "right"]].set_visible(False)

    ax2 = fig.add_subplot(gs[1])
    for lbl, x, y, c in zip(labels, max_dds, ann_rets, palette):
        ax2.scatter(x, y, color=c, s=130, zorder=3, edgecolors="white", linewidths=0.8)
        ax2.annotate(lbl, (x, y), textcoords="offset points", xytext=(6, 4), fontsize=8, color=COLORS["navy"])
    ax2.axhline(0, color="gray", lw=0.8, ls="--")
    ax2.set_xlabel("最大回撤（绝对値 %）", fontsize=10)
    ax2.set_ylabel("年化收益 %", fontsize=10)
    ax2.set_title("收益 / 回撤 散点图", fontsize=12, fontweight="bold", color=COLORS["navy"])
    ax2.spines[["top", "right"]].set_visible(False)

    fig.suptitle("宏观策略绩效评估（最近3年）", fontsize=14, fontweight="bold", color=COLORS["navy"], y=1.01)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  图表已保存 → {path}")


def main():
    print("=" * 60)
    print("  模型五：夏普比率与索提诺比率绩效评估")
    print(f"  无风险利率：{RF_ANNUAL*100:.1f}%（DR007 近似値）")
    print(f"  评估区间：最近 {LOOKBACK_YEARS} 年")
    print("=" * 60)
    os.makedirs(ASSET_DIR, exist_ok=True)

    print("[1/4] 获取行情数据...")
    price_dict = {}
    for name, info in ASSETS.items():
        s = fetch_price_series(name, info)
        if s is not None:
            price_dict[name] = s
    if not price_dict:
        print("所有资产数据获取失败，退出。")
        sys.exit(1)

    cutoff = pd.Timestamp(datetime.today() - timedelta(days=LOOKBACK_YEARS * 365))
    returns_dict = {}
    for name, prices in price_dict.items():
        r = prices.pct_change().dropna()
        r = r[r.index >= cutoff]
        if len(r) > 20:
            returns_dict[name] = r
    if not returns_dict:
        print("截取后无有效数据，退出。")
        sys.exit(1)

    print("[2/4] 计算单资产绩效...")
    results = []
    for name, r in returns_dict.items():
        m = calc_metrics(r, name)
        if m:
            results.append(m)
            sharpe_val = m["夏普比率"]
            sortino_val = m["索提诺比率"]
            ret_val = m["年化收益%"]
            rating_val = m["评级"]
            print(f"  {name:8s}  夏普={sharpe_val:6.3f}  索提诺={sortino_val:6.3f}  年化收益={ret_val:6.2f}%  评级={rating_val}")

    print("[3/4] 计算组合绩效...")
    asset_names = list(returns_dict.keys())
    n = len(asset_names)
    returns_df = pd.DataFrame(returns_dict).dropna()

    eq_w = np.ones(n) / n
    eq_ret = portfolio_returns(returns_df, eq_w)
    m_eq = calc_metrics(eq_ret, "等权组合")
    if m_eq:
        results.append(m_eq)
        print(f"  等权组合  夏普={m_eq["夏普比率"]:6.3f}  索提诺={m_eq["索提诺比率"]:6.3f}  年化收益={m_eq["年化收益%"]:6.2f}%  评级={m_eq["评级"]}")

    rp_label = "风险平价组合"
    rp_w = None
    if os.path.exists(RP_CSV):
        try:
            rp_df = pd.read_csv(RP_CSV)
            w_map = {}
            for col in rp_df.columns:
                for aname in asset_names:
                    if aname in col or col in aname:
                        w_map[aname] = float(rp_df[col].iloc[-1])
            if len(w_map) == n:
                rp_w = np.array([w_map[a] for a in asset_names])
                print(f"  已读取风险平价权重：{dict(zip(asset_names, rp_w.round(4)))}")
        except Exception as e:
            print(f"  读取 risk_parity_results.csv 失败（{e}），使用等权替代")
    if rp_w is None:
        rp_w = eq_w.copy()
        rp_label = "风险平价(等权替代)"
        print("未找到风险平价权重，使用等权替代")
    rp_ret = portfolio_returns(returns_df, rp_w)
    m_rp = calc_metrics(rp_ret, rp_label)
    if m_rp:
        results.append(m_rp)
        print(f"  风险平价  夏普={m_rp["夏普比率"]:6.3f}  索提诺={m_rp["索提诺比率"]:6.3f}  年化收益={m_rp["年化收益%"]:6.2f}%  评级={m_rp["评级"]}")

    df_out = pd.DataFrame(results)
    print("=" * 60)
    print("  完整绩效对比表")
    print("=" * 60)
    print(df_out.to_string(index=False))
    best_idx = df_out["夏普比率"].idxmax()
    best_name = df_out.loc[best_idx, "资产/组合"]
    best_sharpe = df_out.loc[best_idx, "夏普比率"]
    best_rating = df_out.loc[best_idx, "评级"]
    print(f"  最佳夏普：{best_name}  夏普={best_sharpe:.4f}  评级={best_rating}")

    df_out.to_csv(CSV_OUT, index=False, encoding="utf-8-sig")
    print(f"  已保存 → {CSV_OUT}")

    print("[4/4] 生成图表...")
    plot_performance(df_out, IMG_OUT)
    print("完成。")


if __name__ == "__main__":
    main()
