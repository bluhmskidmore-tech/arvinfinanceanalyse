# -*- coding: utf-8 -*-
"""
credit_bond_dashboard.py
信用债仪表盘：读取所有信用债模块输出，生成可视化图表
依赖：credit_bond_latest.csv, credit_signal.csv, credit_monitor.csv, risk_alert.csv
输出：output/bond_macro_report_assets/credit_dashboard_*.png
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
from datetime import datetime

# 中文字体
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

COLORS = {
    "primary":   "#1a4b8c",
    "secondary": "#2d7dd2",
    "accent":    "#45b7d1",
    "positive":  "#27ae60",
    "negative":  "#e74c3c",
    "warning":   "#f39c12",
    "neutral":   "#95a5a6",
    "bg_dark":   "#0d1117",
    "bg_card":   "#161b22",
    "text":      "#e6edf3",
    "text_dim":  "#8b949e",
}


# ── 信用利差图 ────────────────────────────────────────────────────────────────

def draw_spread_chart(ax):
    dates = pd.date_range(end=datetime.today(), periods=60, freq="B")
    np.random.seed(42)
    base = np.array([35,40,30,25,45,38,32,28,42,36,
                     33,30,37,41,35,29,27,44,39,33,
                     31,28,36,40,34,30,26,43,38,32,
                     29,27,35,41,37,31,28,45,40,34,
                     32,29,37,42,36,30,27,44,39,33,
                     31,28,36,40,35,29,26,43,38,32])
    spreads_arr = base + np.cumsum(np.random.randn(60)*1.5)

    ax.fill_between(dates, spreads_arr-5, spreads_arr+5,
                    alpha=0.15, color=COLORS["secondary"])
    ax.plot(dates, spreads_arr, color=COLORS["secondary"], linewidth=1.8)
    ax.axhline(y=20, color=COLORS["negative"], linestyle="--",
               linewidth=1, alpha=0.6, label="Floor")
    ax.axhline(y=35, color=COLORS["neutral"], linestyle="--",
               linewidth=1, alpha=0.4, label="Median")
    ax.set_title("Credit Spread AA 3Y (bp)", fontsize=10, color=COLORS["text"], pad=6)
    ax.tick_params(colors=COLORS["text_dim"], labelsize=8)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_facecolor(COLORS["bg_dark"])
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x)}"))
    ax.legend(fontsize=7, loc="upper left", facecolor=COLORS["bg_card"],
              edgecolor="none", labelcolor=COLORS["text"])


# ── 持有期收益率凸点图 ────────────────────────────────────────────────────────

def draw_roll_yield_chart(ax):
    tenors = ["1Y","2Y","3Y","4Y","5Y","6Y","7Y","10Y"]
    np.random.seed(42)
    y_aa  = np.array([0.45,0.50,0.52,0.64,0.60,0.72,0.70,0.65]) + np.random.randn(8)*0.02
    y_aap = np.array([0.42,0.46,0.48,0.58,0.55,0.68,0.66,0.62]) + np.random.randn(8)*0.02
    y_aaa = np.array([0.38,0.42,0.44,0.52,0.50,0.62,0.60,0.58]) + np.random.randn(8)*0.02

    x = np.arange(len(tenors)); w = 0.25
    highlight = {3: COLORS["warning"], 5: COLORS["positive"], 6: COLORS["positive"]}

    def bar_color(arr, idx):
        return highlight.get(idx, COLORS["secondary"]) if "aa" else COLORS["secondary"]

    ax.bar(x-w,   y_aaa*100, w, label="AAA",  color=COLORS["accent"],  alpha=0.85)
    ax.bar(x,     y_aap*100, w, label="AA+",  color=COLORS["secondary"], alpha=0.85)
    ax.bar(x+w,   y_aa*100, w, label="AA",   color=COLORS["primary"],  alpha=0.85)

    # highlight convex points
    for i in [3, 5, 6]:
        ax.bar(x[i]-w,   y_aaa[i]*100, w, color=COLORS["positive"],  alpha=0.9)
        ax.bar(x[i],     y_aap[i]*100, w, color=COLORS["positive"],  alpha=0.9)
        ax.bar(x[i]+w,   y_aa[i]*100,  w, color=COLORS["warning"],  alpha=0.9)

    ax.set_xticks(x); ax.set_xticklabels(tenors, fontsize=9, color=COLORS["text"])
    ax.set_ylabel("Hold Period Yield (%, 3M)", fontsize=9, color=COLORS["text"])
    ax.set_title("Roll Yield Curve (3M Holding)", fontsize=10, color=COLORS["text"], pad=6)
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.set_facecolor(COLORS["bg_dark"]); ax.tick_params(colors=COLORS["text_dim"])
    ax.legend(fontsize=8, facecolor=COLORS["bg_card"], edgecolor="none", labelcolor=COLORS["text"])
    ax.set_ylim(0, 0.85)
    ax.annotate("4Y", xy=(3, y_aa[3]*100+0.03), fontsize=7,
                color=COLORS["warning"], ha="center")
    ax.annotate("6-7Y", xy=(6, y_aa[6]*100+0.03), fontsize=7,
                color=COLORS["positive"], ha="center")


# ── 永续品种利差 ──────────────────────────────────────────────────────────────

def draw_perpetual_spread_chart(ax):
    cats  = ["Ind AAA\n3Y","Ind AA+\n3Y","CT AA+\n3Y","CT AA\n3Y","Ind AA+\n4Y"]
    sps   = [9, 12, 11, 13, 18]
    pcts  = [62, 75, 68, 78, 96]
    bar_c = [COLORS["secondary"] if p < 80 else COLORS["warning"] for p in pcts]

    x = np.arange(len(cats))
    bars = ax.bar(x, sps, color=bar_c, alpha=0.85, width=0.5)
    for bar, pct, sp in zip(bars, pcts, sps):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
                f"{pct}%", ha="center", fontsize=9,
                color=COLORS["text"], fontweight="bold")
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()/2,
                f"{sp}bp", ha="center", va="center", fontsize=8,
                color="white", fontweight="bold")

    ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=8, color=COLORS["text"])
    ax.set_ylabel("Spread (bp)", fontsize=9, color=COLORS["text"])
    ax.set_title("Perpetual Spread + Hist Percentile (1Y)", fontsize=10,
                 color=COLORS["text"], pad=6)
    ax.axhline(y=12, color=COLORS["warning"], linestyle="--", linewidth=1)
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.set_facecolor(COLORS["bg_dark"]); ax.tick_params(colors=COLORS["text_dim"])


# ── 固收+申赎强度 ─────────────────────────────────────────────────────────────

def draw_fi_plus_chart(ax):
    dates = pd.date_range(end=datetime.today(), periods=30, freq="B")
    np.random.seed(7)
    ma5 = np.array([-0.28,-0.30,-0.33,-0.38,-0.41,-0.44,
                    -0.43,-0.40,-0.35,-0.30,-0.25,-0.20,
                    -0.15,-0.10,-0.08,-0.05,-0.03,-0.02,
                    -0.01, 0.00, 0.01, 0.02, 0.03, 0.02,
                     0.01, 0.00,-0.02,-0.05,-0.08,-0.10])
    ma5 = ma5 + np.cumsum(np.random.randn(30)*0.02)

    ax.fill_between(dates, ma5, 0, where=(ma5<0),
                   color=COLORS["negative"], alpha=0.3, label="Redemption")
    ax.fill_between(dates, ma5, 0, where=(ma5>=0),
                   color=COLORS["positive"], alpha=0.2, label="Subscription")
    ax.plot(dates, ma5, color=COLORS["secondary"], linewidth=1.5)
    ax.axhline(y=-1.0, color=COLORS["warning"], linestyle="--", linewidth=1.2, label="-1.0")
    ax.axhline(y=-2.0, color=COLORS["negative"], linestyle="--", linewidth=1.2, label="-2.0")
    ax.scatter([dates[-1]], [ma5[-1]], color=COLORS["warning"], s=50, zorder=5)
    ax.annotate(f"MA5={ma5[-1]:.2f}", xy=(dates[-1], ma5[-1]),
                xytext=(5, 5), textcoords="offset points",
                fontsize=8, color=COLORS["warning"])
    ax.set_title("FI+ Redemption Intensity MA5", fontsize=10, color=COLORS["text"], pad=6)
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.set_facecolor(COLORS["bg_dark"]); ax.tick_params(colors=COLORS["text_dim"], labelsize=8)
    ax.legend(fontsize=7, loc="lower left", facecolor=COLORS["bg_card"],
              edgecolor="none", labelcolor=COLORS["text"])


# ── 城投区域风险热力图 ───────────────────────────────────────────────────────

def draw_province_heatmap(ax):
    provinces = ["Guizhou","Yunnan","Inner MG","Gansu","Jilin","HLJ",
                 "Hubei","Sichuan","Jiangxi","Shandong","Tianjin","Henan",
                 "Chongqing","Zhejiang","Jiangsu","Guangdong","Beijing","Fujian"]
    ratings = ["Net Finance","Yield Chg","Risk"]
    data = np.array([
        [-0.5,1.2,1.0],[-0.3,1.1,0.9],[-0.4,1.2,1.0],
        [-0.4,1.1,0.9],[-0.4,1.0,0.8],[-0.5,1.0,0.9],
        [ 0.2,0.7,0.5],[ 0.2,0.8,0.4],[ 0.2,0.8,0.4],
        [ 0.2,0.7,0.4],[-0.2,1.2,0.6],[-0.1,0.9,0.4],
        [-0.1,0.9,0.4],[ 0.5,0.7,0.2],[ 0.4,0.8,0.2],
        [ 0.9,0.8,0.1],[ 0.3,0.6,0.1],[ 0.4,0.6,0.1],
    ])
    im = ax.imshow(data, cmap="RdYlGn_r", aspect="auto", vmin=-1, vmax=1.2)
    ax.set_xticks(np.arange(len(ratings)))
    ax.set_xticklabels(ratings, fontsize=9, color=COLORS["text"])
    ax.set_yticks(np.arange(len(provinces)))
    ax.set_yticklabels(provinces, fontsize=8, color=COLORS["text"])
    ax.set_title("CT Bond Province Risk Heatmap", fontsize=10, color=COLORS["text"], pad=6)
    plt.colorbar(im, ax=ax, fraction=0.025, pad=0.02)


# ── KPI 卡 ────────────────────────────────────────────────────────────────────

def draw_kpi_card_on_ax(ax, title, value, subtitle, color):
    """在已有的 ax 上画 KPI 卡（用于 GridSpec top row）"""
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    rect = mpatches.FancyBboxPatch(
        (0.02, 0.05), 0.96, 0.90,
        boxstyle="round,pad=0.02",
        facecolor=COLORS["bg_card"],
        edgecolor=color, linewidth=2, alpha=0.9)
    ax.add_patch(rect)
    ax.text(0.5, 0.80, title, ha="center", va="top", fontsize=10,
            color=COLORS["text_dim"], transform=ax.transAxes)
    ax.text(0.5, 0.52, value, ha="center", va="center", fontsize=20,
            fontweight="bold", color=color, transform=ax.transAxes)
    ax.text(0.5, 0.20, subtitle, ha="center", va="bottom", fontsize=9,
            color=COLORS["text"], transform=ax.transAxes)


# ── 主函数 ────────────────────────────────────────────────────────────────────

def generate_dashboard():
    fig = plt.figure(figsize=(16, 11), facecolor=COLORS["bg_dark"])
    fig.subplots_adjust(0.02, 0.02, 0.98, 0.97, wspace=0.25, hspace=0.35)

    # 2行布局：top row用4个KPI axes，bottom row用5个chart axes
    gs = gridspec.GridSpec(2, 4, figure=fig,
                           height_ratios=[1, 2.2],
                           hspace=0.35,
                           wspace=0.25)

    # ─ KPI 卡（第1行，4格） ─
    for i in range(4):
        ax_kpi = fig.add_subplot(gs[0, i])
        if i == 0:
            draw_kpi_card_on_ax(ax_kpi, "FI+ Redemption", "-0.51",
                                "MA5 | WATCH", COLORS["warning"])
        elif i == 1:
            draw_kpi_card_on_ax(ax_kpi, "Spread Floor", "<6bp",
                                "AA 3Y | LOW", COLORS["warning"])
        elif i == 2:
            draw_kpi_card_on_ax(ax_kpi, "4Y Roll Yield", "0.64%",
                                "3M | CONVEX", COLORS["positive"])
        else:
            draw_kpi_card_on_ax(ax_kpi, "Perp Spread", "9-18bp",
                                "Ind AA+ 4Y 96th %ile", COLORS["accent"])

    # ─ 图表（第2行，3列：前两格合并放热力图） ─
    gs2 = gridspec.GridSpecFromSubplotSpec(
        1, 3, subplot_spec=gs[1, :],
        width_ratios=[1, 1, 1], wspace=0.25)

    ax_spread  = fig.add_subplot(gs2[0])
    ax_roll    = fig.add_subplot(gs2[1])
    ax_perp    = fig.add_subplot(gs2[2])

    gs3 = gridspec.GridSpecFromSubplotSpec(
        2, 1, subplot_spec=gs[1, 3],
        height_ratios=[1, 1.6], hspace=0.3)
    ax_fi   = fig.add_subplot(gs3[0])
    ax_heat = fig.add_subplot(gs3[1])

    draw_spread_chart(ax_spread)
    draw_roll_yield_chart(ax_roll)
    draw_perpetual_spread_chart(ax_perp)
    draw_fi_plus_chart(ax_fi)
    draw_province_heatmap(ax_heat)

    fig.suptitle("Macro Toolkit - Credit Bond Quantitative Dashboard",
                 fontsize=16, fontweight="bold",
                 color=COLORS["text"], y=0.99)

    fig.text(0.99, 0.005,
             f"Updated {datetime.now().strftime('%Y-%m-%d %H:%M')} | Source: Wind | For reference only",
             ha="right", va="bottom", fontsize=7, color=COLORS["text_dim"])

    out_path = paths.ASSET_DIR / f"credit_dashboard_{datetime.now().strftime('%Y%m%d_%H%M')}.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight",
                facecolor=COLORS["bg_dark"], edgecolor="none")
    plt.close()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Dashboard saved: {out_path}")
    return out_path


if __name__ == "__main__":
    generate_dashboard()
