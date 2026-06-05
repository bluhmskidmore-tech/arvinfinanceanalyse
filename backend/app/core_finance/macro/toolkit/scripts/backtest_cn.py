# -*- coding: utf-8 -*-
"""
全策略综合回测框架
==================
对比5种策略：买持等权 / 风险平价 / CTA趋势 / 状态切换 / 全模型综合
资产池: 沪深300、中证500、黄金、铜、原油、国债ETF、十年国债ETF、国开债ETF
数据源: akshare（股票/商品）+ Wind（债券ETF）
回测区间: 近5年
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
from scipy.optimize import minimize

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

STRATEGY_COLORS = {
    "买持等权":   COLORS["muted"],
    "风险平价":   COLORS["teal"],
    "CTA趋势":    COLORS["gold"],
    "状态切换":   COLORS["orange"],
    "全模型综合": COLORS["navy"],
}

RF = 0.015          # 无风险利率年化
COST = 0.002        # 单边交易成本
RP_WINDOW = 60      # 风险平价滚动窗口
HURST_WINDOW = 60   # Hurst 计算窗口
AUTOCORR_WINDOW = 20


# ============================================================
# 数据获取
# ============================================================

def load_prices() -> pd.DataFrame:
    print("\n[步骤1] 拉取资产价格...")
    series = {}
    try:
        # 股票指数（akshare）
        for symbol, name in [("sh000300", "hs300"), ("sh000905", "csi500")]:
            df = ak.stock_zh_index_daily(symbol=symbol)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            series[name] = pd.to_numeric(df["close"], errors="coerce")
            print(f"  {name}: {len(series[name])} 条，最新 {series[name].index[-1].date()}")

        # 期货（akshare）
        today = datetime.now().strftime("%Y%m%d")
        for symbol, name in [("AU0", "gold"), ("CU0", "copper"), ("SC0", "crude_oil")]:
            df = ak.futures_main_sina(symbol=symbol, start_date="20150101", end_date=today)
            df = df[["日期", "收盘价"]].copy()
            df.columns = ["date", name]
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            df[name] = pd.to_numeric(df[name], errors="coerce")
            series[name] = df[name]
            print(f"  {name}: {len(series[name])} 条，最新 {series[name].index[-1].date()}")
    except Exception as e:
        print(f"[致命] akshare 数据获取失败: {e}")
        sys.exit(1)

    # 债券 ETF（Wind，失败时跳过）
    BOND_ETFS = [
        ("511010.SH", "bond_gov"),    # 国债ETF
        ("511260.SH", "bond_10y"),    # 十年国债ETF
        ("511090.SH", "bond_cdb"),    # 国开债ETF
    ]
    wind_ok = False
    try:
        from WindPy import w as wind
        r = wind.start(waitTime=8)
        if r.ErrorCode == 0:
            codes = ",".join(c for c, _ in BOND_ETFS)
            data = wind.wsd(codes, "close", "2015-01-01",
                            datetime.now().strftime("%Y-%m-%d"), "Fill=Previous")
            if data.ErrorCode == 0:
                import datetime as dt
                dates = [pd.Timestamp(d) for d in data.Times]
                for i, (_, name) in enumerate(BOND_ETFS):
                    s = pd.Series(data.Data[i], index=dates, name=name, dtype=float)
                    s = s[s.notna()]
                    series[name] = s
                    print(f"  {name}({BOND_ETFS[i][0]}): {len(s)} 条，最新 {s.index[-1].date()}")
                wind_ok = True
            else:
                print(f"  [警告] Wind wsd 返回错误码 {data.ErrorCode}，跳过债券ETF")
        else:
            print(f"  [警告] Wind 启动失败（ErrorCode={r.ErrorCode}），跳过债券ETF")
    except Exception as e:
        print(f"  [警告] Wind 不可用（{str(e)[:60]}），跳过债券ETF")

    if not wind_ok:
        # 尝试 akshare 备用
        try:
            today = datetime.now().strftime("%Y%m%d")
            for symbol, name in [("511010", "bond_gov")]:
                df = ak.fund_etf_hist_em(symbol=symbol, period="daily",
                                         start_date="20150101", end_date=today, adjust="qfq")
                df["date"] = pd.to_datetime(df["日期"])
                df = df.set_index("date").sort_index()
                series[name] = pd.to_numeric(df["收盘"], errors="coerce")
                print(f"  {name}({symbol}) [akshare备用]: {len(series[name])} 条")
        except Exception:
            print("  [警告] 债券ETF备用接口也失败，将以5资产运行")

    prices = pd.concat(series.values(), axis=1)
    prices.columns = list(series.keys())
    prices = prices.sort_index()

    # 近5年，核心5资产要求完整，债券ETF允许部分缺失（上市前用 NaN，回测时动态处理）
    cutoff = prices.index.max() - pd.DateOffset(years=5)
    prices = prices[prices.index >= cutoff]
    core = ["hs300", "csi500", "gold", "copper", "crude_oil"]
    core_cols = [c for c in core if c in prices.columns]
    prices = prices.dropna(subset=core_cols)

    # 债券ETF：上市前用国债ETF(bond_gov)替代，保持权重可计算
    bond_cols = [c for c in prices.columns if c.startswith("bond_")]
    if "bond_gov" in prices.columns:
        for col in bond_cols:
            if col != "bond_gov":
                # 上市前用 bond_gov 填充（相关性高，近似替代）
                prices[col] = prices[col].fillna(prices["bond_gov"])

    print(f"\n合并后: {len(prices)} 个交易日，{len(prices.columns)} 个资产")
    print(f"  资产: {', '.join(prices.columns)}")
    print(f"  区间: {prices.index[0].date()} ~ {prices.index[-1].date()}")
    return prices


# ============================================================
# 信号与权重计算
# ============================================================

def calc_rp_weights(ret_window: pd.DataFrame, asset_names: list) -> np.ndarray:
    """等风险贡献权重，加入资产类别上限约束"""
    cov = ret_window.cov().values * 252
    n = len(cov)

    def objective(w):
        port_var = float(w @ cov @ w)
        if port_var < 1e-12:
            return 1e6
        rc = w * (cov @ w) / port_var
        return float(np.sum((rc - rc.mean()) ** 2))

    w0 = np.ones(n) / n
    # 单资产上限 40%，债券类合计上限 50%，股票类合计下限 15%
    bounds = [(0.03, 0.40)] * n
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]

    # 债券类合计 ≤ 50%
    bond_idx = [i for i, a in enumerate(asset_names) if a.startswith("bond_")]
    if bond_idx:
        cons.append({"type": "ineq",
                     "fun": lambda w, bi=bond_idx: 0.50 - sum(w[i] for i in bi)})

    # 股票类合计 ≥ 15%
    equity_idx = [i for i, a in enumerate(asset_names) if a in ("hs300", "csi500")]
    if equity_idx:
        cons.append({"type": "ineq",
                     "fun": lambda w, ei=equity_idx: sum(w[i] for i in ei) - 0.15})

    res = minimize(objective, w0, method="SLSQP", bounds=bounds, constraints=cons,
                   options={"maxiter": 500, "ftol": 1e-9})
    return res.x if res.success else w0


def signal_ma_cross(price: pd.Series, short=20, long=60) -> pd.Series:
    ma_s = price.rolling(short).mean()
    ma_l = price.rolling(long).mean()
    sig = pd.Series(np.where(ma_s > ma_l, 1.0, -1.0), index=price.index)
    sig[ma_s.isna() | ma_l.isna()] = np.nan
    return sig


def signal_donchian(price: pd.Series, window=20) -> pd.Series:
    high = price.rolling(window).max().shift(1)
    low  = price.rolling(window).min().shift(1)
    sig = pd.Series(np.nan, index=price.index)
    sig[price > high] = 1.0
    sig[price < low]  = -1.0
    return sig.ffill().fillna(0.0)


def signal_atr_pos(price: pd.Series, window=14, target_vol=0.01) -> pd.Series:
    ret_std = np.log(price / price.shift(1)).rolling(window).std()
    pos = (target_vol / ret_std.replace(0, np.nan)).clip(0, 1.0)
    ma_sig = signal_ma_cross(price)
    return (pos * ma_sig.clip(0, 1)).fillna(0.0)


def cta_composite(price: pd.Series) -> pd.Series:
    ma  = signal_ma_cross(price)
    don = signal_donchian(price)
    atr = signal_atr_pos(price)
    raw = ma * 0.4 + don * 0.3 + atr * 0.3
    return raw.apply(lambda x: float(np.tanh(x)) if not np.isnan(x) else np.nan)


def hurst_exp(ts: np.ndarray) -> float:
    n = len(ts)
    if n < 20:
        return 0.5
    lags, rs_vals = [], []
    for lag in range(2, min(n // 2, 40)):
        segs = n // lag
        if segs < 2:
            continue
        rs_list = []
        for i in range(segs):
            seg = ts[i * lag:(i + 1) * lag]
            s = np.std(seg, ddof=1)
            if s > 0:
                dev = np.cumsum(seg - np.mean(seg))
                rs_list.append((np.max(dev) - np.min(dev)) / s)
        if rs_list:
            rs_vals.append(np.log(np.mean(rs_list)))
            lags.append(np.log(lag))
    if len(lags) < 2:
        return 0.5
    return float(np.clip(np.polyfit(lags, rs_vals, 1)[0], 0.0, 1.0))


def market_regime(ret: pd.Series, i: int) -> str:
    """识别 i 时刻的市场状态（用前 HURST_WINDOW 日数据）"""
    start = max(0, i - HURST_WINDOW)
    window_ret = ret.iloc[start:i].dropna()
    if len(window_ret) < 20:
        return "未知"

    vol = window_ret.std() * np.sqrt(252)
    vol_hist = ret.iloc[:i].rolling(20).std().dropna() * np.sqrt(252)
    vol_high = float(vol_hist.quantile(0.75)) if len(vol_hist) >= 20 else 0.3

    if vol > vol_high:
        return "高波动"

    ac_window = window_ret.tail(AUTOCORR_WINDOW)
    autocorr = float(ac_window.autocorr(lag=1)) if len(ac_window) >= 5 else 0.0
    h = hurst_exp(window_ret.values)

    if autocorr > 0.10 and h > 0.55:
        return "趋势市"
    if autocorr < -0.10 or h < 0.45:
        return "震荡市"
    return "中性"


def load_merrill_clock() -> pd.DataFrame:
    """加载美林时钟历史数据，用于股债动态配置"""
    path = ROOT / "merrill_clock_history.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df


# ============================================================
# 回测引擎
# ============================================================

def run_backtest(prices: pd.DataFrame) -> dict:
    assets = list(prices.columns)
    n_assets = len(assets)
    n_days = len(prices)
    log_ret = np.log(prices / prices.shift(1))

    # 预计算 CTA 合成信号
    print("  预计算 CTA 信号...")
    cta_signals = pd.DataFrame(index=prices.index, columns=assets, dtype=float)
    for a in assets:
        cta_signals[a] = cta_composite(prices[a])

    # 预计算市场状态
    print("  预计算市场状态...")
    hs300_ret = log_ret["hs300"].fillna(0)
    regimes = []
    for i in range(n_days):
        regimes.append(market_regime(hs300_ret, i))
    regime_series = pd.Series(regimes, index=prices.index)

    # 加载美林时钟历史（月频，用于股债动态配置）
    clock_df = load_merrill_clock()
    # 将月频信号前向填充到日频
    if len(clock_df):
        clock_daily = clock_df.reindex(prices.index, method="ffill")
    else:
        clock_daily = pd.DataFrame(index=prices.index)

    # 资产分类索引
    equity_idx = [j for j, a in enumerate(assets) if a in ("hs300", "csi500")]
    bond_idx   = [j for j, a in enumerate(assets) if a.startswith("bond_")]
    commod_idx = [j for j, a in enumerate(assets) if a in ("gold", "copper", "crude_oil")]

    # 初始化权重矩阵
    w_bh       = np.ones(n_assets) / n_assets
    w_rp       = np.ones(n_assets) / n_assets
    w_cta      = np.ones(n_assets) / n_assets
    w_regime   = np.ones(n_assets) / n_assets
    w_combined = np.ones(n_assets) / n_assets

    ret_records = {k: [] for k in ["买持等权", "风险平价", "CTA趋势", "状态切换", "全模型综合"]}
    dates = []

    prev_w = {
        "买持等权":   w_bh.copy(),
        "风险平价":   w_rp.copy(),
        "CTA趋势":    w_cta.copy(),
        "状态切换":   w_regime.copy(),
        "全模型综合": w_combined.copy(),
    }

    last_rp_month = -1

    print("  运行回测...")
    for i in range(1, n_days):
        date = prices.index[i]
        daily_ret = log_ret.iloc[i].fillna(0).values

        # ── 风险平价：月末重新优化 ──
        if date.month != last_rp_month and i >= RP_WINDOW:
            ret_win = log_ret.iloc[max(0, i - RP_WINDOW):i].dropna()
            if len(ret_win) >= 20:
                w_rp = calc_rp_weights(ret_win, assets)
            last_rp_month = date.month

        # ── CTA 权重：前一日信号归一化 ──
        sig_prev = cta_signals.iloc[i - 1].fillna(0).values
        pos = np.clip(sig_prev, 0, None)
        total_pos = pos.sum()
        w_cta = pos / total_pos if total_pos > 1e-6 else np.ones(n_assets) / n_assets

        # ── 状态切换权重 ──
        regime = regimes[i - 1]  # 前一日状态
        if regime in ("趋势市", "弱趋势"):
            # CTA 信号
            w_regime = w_cta.copy()
        elif regime in ("震荡市", "弱震荡"):
            # 均值回归：低配强趋势资产，等权持有，整体仓位 80%
            w_regime = np.ones(n_assets) / n_assets * 0.80
        elif regime == "高波动":
            # 防御：等权 × 0.5，剩余现金
            w_regime = np.ones(n_assets) / n_assets * 0.5
        else:
            w_regime = np.ones(n_assets) / n_assets

        # ── 全模型综合权重 ──
        w_base = w_rp.copy()

        # 1. 美林时钟象限驱动的股债配置调整（月频信号，低换手）
        if len(clock_daily) and date in clock_daily.index:
            row = clock_daily.loc[date]
            clock_regime = str(row.get("regime", "")) if "regime" in row.index else ""
            # 滞胀：减股票+减债券，加黄金+商品
            if clock_regime == "滞胀":
                for j in equity_idx: w_base[j] *= 0.70
                for j in bond_idx:   w_base[j] *= 0.80
                gold_j = [j for j, a in enumerate(assets) if a == "gold"]
                for j in gold_j:     w_base[j] *= 1.40
            # 衰退：减股票+减商品，加债券
            elif clock_regime == "衰退":
                for j in equity_idx: w_base[j] *= 0.65
                for j in commod_idx: w_base[j] *= 0.75
                for j in bond_idx:   w_base[j] *= 1.35
            # 复苏：加股票，减债券
            elif clock_regime == "复苏":
                for j in equity_idx: w_base[j] *= 1.30
                for j in bond_idx:   w_base[j] *= 0.75
            # 过热：加商品，减债券
            elif clock_regime == "过热":
                for j in commod_idx: w_base[j] *= 1.25
                for j in bond_idx:   w_base[j] *= 0.80

        # 2. CTA 信号微调（±8%，幅度小于美林时钟调整）
        for j, a in enumerate(assets):
            s = float(cta_signals.iloc[i - 1, j]) if not np.isnan(cta_signals.iloc[i - 1, j]) else 0.0
            if s > 0.4:
                w_base[j] *= 1.08
            elif s < -0.4:
                w_base[j] *= 0.92

        # 3. 高波动防御：股票减仓，债券保持
        if regime == "高波动":
            for j in equity_idx:
                w_base[j] *= 0.55

        # 归一化
        w_base = np.clip(w_base, 0, None)
        total = w_base.sum()
        w_combined = w_base / total if total > 1e-6 else np.ones(n_assets) / n_assets

        # ── 计算各策略当日收益（扣交易成本）──
        current_weights = {
            "买持等权":   np.ones(n_assets) / n_assets,
            "风险平价":   w_rp,
            "CTA趋势":    w_cta,
            "状态切换":   w_regime,
            "全模型综合": w_combined,
        }

        dates.append(date)
        for name, w in current_weights.items():
            gross = float(w @ daily_ret)
            turnover = float(np.abs(w - prev_w[name]).sum())
            cost = turnover * COST
            ret_records[name].append(gross - cost)
            prev_w[name] = w.copy()

    # 构建收益率 DataFrame
    ret_df = pd.DataFrame(ret_records, index=dates)
    return ret_df, regime_series


# ============================================================
# 绩效计算
# ============================================================

def calc_metrics(ret: pd.Series, name: str) -> dict:
    ann = 252
    r = ret.dropna()
    cum = (1 + r).cumprod()
    total_ret = float(cum.iloc[-1] - 1)
    years = len(r) / ann
    annual_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
    annual_vol = float(r.std() * np.sqrt(ann))
    sharpe = (annual_ret - RF) / annual_vol if annual_vol > 0 else 0

    # 索提诺
    downside = r[r < 0].std() * np.sqrt(ann)
    sortino = (annual_ret - RF) / downside if downside > 0 else 0

    # 最大回撤
    roll_max = cum.cummax()
    dd = (cum - roll_max) / roll_max
    max_dd = float(dd.min())

    calmar = annual_ret / abs(max_dd) if max_dd < 0 else 0
    win_rate = float((r > 0).mean())

    return {
        "策略": name,
        "年化收益%": round(annual_ret * 100, 2),
        "年化波动%": round(annual_vol * 100, 2),
        "夏普比率":  round(sharpe, 3),
        "索提诺比率": round(sortino, 3),
        "最大回撤%": round(max_dd * 100, 2),
        "Calmar比率": round(calmar, 3),
        "胜率%":     round(win_rate * 100, 1),
        "累计收益%": round(total_ret * 100, 2),
    }


def calc_annual_returns(ret_df: pd.DataFrame) -> pd.DataFrame:
    """分年度收益"""
    ret_df = ret_df.copy()
    ret_df["year"] = ret_df.index.year
    rows = []
    for year, grp in ret_df.groupby("year"):
        row = {"年份": year}
        for col in ret_df.columns:
            if col == "year":
                continue
            cum = (1 + grp[col]).prod() - 1
            row[col] = round(float(cum) * 100, 2)
        rows.append(row)
    return pd.DataFrame(rows)


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


def plot_nav(ret_df: pd.DataFrame) -> Path:
    path = ASSET_DIR / "backtest_nav.png"
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8),
                                    gridspec_kw={"height_ratios": [3, 1]}, sharex=True)

    for name, color in STRATEGY_COLORS.items():
        if name not in ret_df.columns:
            continue
        r = ret_df[name]
        nav = (1 + r).cumprod()
        lw = 2.5 if name == "全模型综合" else 1.8
        ax1.plot(nav.index, nav.values, color=color, linewidth=lw, label=name,
                 alpha=0.95 if name == "全模型综合" else 0.80)

        # 回撤
        roll_max = nav.cummax()
        dd = (nav - roll_max) / roll_max
        ax2.plot(dd.index, dd.values * 100, color=color, linewidth=1.2, alpha=0.75)

    ax1.set_ylabel("累计净值", fontsize=10, color=COLORS["text"])
    ax1.legend(loc="upper left", frameon=False, fontsize=9)
    ax1.grid(axis="y", color=COLORS["grid"], linewidth=0.6, alpha=0.7)
    for spine in ["top", "right"]:
        ax1.spines[spine].set_visible(False)
    ax1.spines["left"].set_color(COLORS["grid"])
    ax1.spines["bottom"].set_color(COLORS["grid"])
    ax1.tick_params(colors=COLORS["muted"], labelsize=9)
    ax1.text(0.0, 1.06, "全策略综合回测 — 净值曲线", transform=ax1.transAxes,
             fontsize=13, fontweight="bold", color=COLORS["navy"], ha="left")
    ax1.text(0.0, 1.01, f"近5年，扣除单边 {COST*100:.1f}% 交易成本，RF={RF*100:.1f}%",
             transform=ax1.transAxes, fontsize=8.5, color=COLORS["muted"], ha="left")

    ax2.axhline(0, color=COLORS["grid"], linewidth=0.8)
    ax2.set_ylabel("回撤 (%)", fontsize=9, color=COLORS["text"])
    ax2.grid(axis="y", color=COLORS["grid"], linewidth=0.5, alpha=0.6)
    for spine in ["top", "right"]:
        ax2.spines[spine].set_visible(False)
    ax2.spines["left"].set_color(COLORS["grid"])
    ax2.spines["bottom"].set_color(COLORS["grid"])
    ax2.tick_params(colors=COLORS["muted"], labelsize=8)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_annual(annual_df: pd.DataFrame) -> Path:
    path = ASSET_DIR / "backtest_annual.png"
    strategies = [c for c in annual_df.columns if c != "年份"]
    years = annual_df["年份"].tolist()
    n_strat = len(strategies)
    x = np.arange(len(years))
    width = 0.15
    offsets = np.linspace(-(n_strat - 1) / 2, (n_strat - 1) / 2, n_strat) * width

    fig, ax = plt.subplots(figsize=(12, 5.5))
    for idx, (name, offset) in enumerate(zip(strategies, offsets)):
        color = STRATEGY_COLORS.get(name, COLORS["muted"])
        vals = annual_df[name].values
        bars = ax.bar(x + offset, vals, width=width * 0.9, color=color,
                      alpha=0.85, label=name)

    ax.axhline(0, color=COLORS["grid"], linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels([str(y) for y in years], fontsize=9)
    ax.set_ylabel("年度收益 (%)", fontsize=10, color=COLORS["text"])
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, ncol=3)
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.6, alpha=0.6)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])
    ax.tick_params(colors=COLORS["muted"], labelsize=9)
    ax.text(0.0, 1.06, "分年度收益对比", transform=ax.transAxes,
            fontsize=13, fontweight="bold", color=COLORS["navy"], ha="left")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_metrics_heatmap(metrics_df: pd.DataFrame) -> Path:
    path = ASSET_DIR / "backtest_metrics.png"
    cols = ["年化收益%", "年化波动%", "夏普比率", "索提诺比率", "最大回撤%", "Calmar比率", "胜率%"]
    data = metrics_df.set_index("策略")[cols]

    # 归一化（每列 min-max，最大回撤取绝对值后反向）
    norm = data.copy().astype(float)
    for col in cols:
        col_data = norm[col].copy()
        if col == "最大回撤%":
            col_data = -col_data  # 回撤越小越好
        if col == "年化波动%":
            col_data = -col_data  # 波动越小越好
        mn, mx = col_data.min(), col_data.max()
        norm[col] = (col_data - mn) / (mx - mn + 1e-9)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    import matplotlib.colors as mcolors
    cmap = mcolors.LinearSegmentedColormap.from_list(
        "perf", [COLORS["danger"], COLORS["mist"], COLORS["teal"]]
    )
    im = ax.imshow(norm.values, cmap=cmap, vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(data.index)))
    ax.set_xticklabels(cols, fontsize=9, color=COLORS["text"])
    ax.set_yticklabels(data.index.tolist(), fontsize=9.5, color=COLORS["text"])

    for i in range(len(data.index)):
        for j, col in enumerate(cols):
            val = float(data.iloc[i, j])
            txt = f"{val:.1f}" if "%" in col else f"{val:.3f}"
            fc = "white" if norm.values[i, j] > 0.6 or norm.values[i, j] < 0.25 else COLORS["text"]
            ax.text(j, i, txt, ha="center", va="center", fontsize=8.5,
                    color=fc, fontweight="bold")

    ax.set_title("策略绩效热力图（颜色越深=越优）", fontsize=11,
                 color=COLORS["navy"], pad=12, fontweight="bold")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 65)
    print("  全策略综合回测框架")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 65)

    _set_style()
    prices = load_prices()

    print("\n[步骤2] 运行回测...")
    ret_df, regime_series = run_backtest(prices)

    print("\n[步骤3] 计算绩效指标...")
    metrics_rows = []
    for name in ["买持等权", "风险平价", "CTA趋势", "状态切换", "全模型综合"]:
        if name in ret_df.columns:
            m = calc_metrics(ret_df[name], name)
            metrics_rows.append(m)

    metrics_df = pd.DataFrame(metrics_rows)

    print(f"\n{'='*75}")
    print("  策略绩效汇总")
    print(f"{'='*75}")
    print(f"  {'策略':<10} {'年化收益%':>9} {'年化波动%':>9} {'夏普':>7} {'索提诺':>7} {'最大回撤%':>9} {'Calmar':>7} {'胜率%':>7}")
    print(f"  {'-'*73}")
    for _, r in metrics_df.iterrows():
        print(f"  {r['策略']:<10} {r['年化收益%']:>9.2f} {r['年化波动%']:>9.2f} "
              f"{r['夏普比率']:>7.3f} {r['索提诺比率']:>7.3f} "
              f"{r['最大回撤%']:>9.2f} {r['Calmar比率']:>7.3f} {r['胜率%']:>7.1f}")

    # 最优策略
    best_idx = metrics_df["夏普比率"].idxmax()
    best = metrics_df.iloc[best_idx]
    print(f"\n  最优策略: {best['策略']}（夏普 {best['夏普比率']:.3f}，年化收益 {best['年化收益%']:.2f}%）")

    # 分年度收益
    annual_df = calc_annual_returns(ret_df)
    print(f"\n  分年度收益 (%):")
    print("  " + annual_df.to_string(index=False))

    # 保存 CSV
    metrics_path = ROOT / "backtest_results.csv"
    metrics_df.to_csv(metrics_path, index=False, encoding="utf-8-sig", float_format="%.4f")
    print(f"\n  绩效汇总: {metrics_path}")

    annual_path = ROOT / "backtest_annual.csv"
    annual_df.to_csv(annual_path, index=False, encoding="utf-8-sig", float_format="%.2f")
    print(f"  分年度收益: {annual_path}")

    # 图表
    print("\n[步骤4] 生成图表...")
    nav_path = plot_nav(ret_df)
    print(f"  净值曲线: {nav_path}")

    annual_chart = plot_annual(annual_df)
    print(f"  年度收益: {annual_chart}")

    metrics_chart = plot_metrics_heatmap(metrics_df)
    print(f"  绩效热力图: {metrics_chart}")

    print("\n完成。")


if __name__ == "__main__":
    main()
