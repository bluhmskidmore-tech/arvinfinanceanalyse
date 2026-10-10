"""
CTA 趋势跟踪模型
================
三种信号合成：双均线交叉 + 唐奇安通道突破 + ATR 波动率调整仓位
资产池: 沪深300、中证500、黄金、铜、原油
数据源: akshare（不依赖 Wind）

口径说明（相对尽调笔记定义，仅观察口径）：
- 笔记两条量化风控规则已实现（仅回测层 backtest_with_stops，信号纯函数不变）：
  1) 单笔止损 2×ATR：执行信号方向翻转或从 0 变非 0 的当日收盘价为进场价；持仓期间
     收盘价相对进场价的逆向变动幅度 > 2×ATR（取进场日 ATR，比例化为 2×ATR/进场价）
     时当日按收盘价止损，次日起仓位为 0，直到信号方向变化（翻转或归零再重新出信号）
     才允许重新进场，多空对称。
  2) 组合止损（单日回撤>5% 减仓 50%）：策略单日收益 < -5% 的次日起仓位 ×0.5，
     持续到该资产信号方向变化时复原；本脚本为单资产分别回测，"组合"按单资产
     策略日收益口径近似。
  配套观点23（波动急升且无效震荡/资产共振下跌时降仓）为定性规则，不在量化范围。
- 主表"策略年化收益%/策略夏普比率/买持年化收益%"为含止损口径；stdout 另打印
  无止损 vs 含止损对照，便于评估止损贡献。
- ATR 以 14 日对数收益率滚动标准差近似（上游数据源仅提供收盘价，无高低价）；
  止损阈值沿用该近似（2×ATR ≈ 2×近似日波动×价格）。
- 回测口径：合成信号滞后一期执行（T-1 信号 × T 日对数收益），连续信号值即仓位
  权重（非满仓、含负仓位做空），未计交易成本与滑点；对照买持为同窗口满仓持有。
- 信号纯函数与 backend/app/core_finance/macro/cta_trend.py（rv_macro_cta_trend_cn_v1）
  保持一致，修改需同步评审该适配器。
"""

import warnings

warnings.filterwarnings("ignore")

import importlib.util
import sys

import numpy as np
import pandas as pd

if __package__:
    from backend.app.core_finance.macro.toolkit import akshare as ak
else:
    import akshare as ak

if importlib.util.find_spec("matplotlib") is None:
    matplotlib = None
    mdates = None
    plt = None
else:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

from datetime import datetime
from pathlib import Path

if __package__:
    from backend.app.core_finance.macro.toolkit.paths import ASSET_DIR, OUTPUT_DIR
else:
    _PKG = Path(__file__).resolve().parent.parent
    if str(_PKG) not in sys.path:
        sys.path.insert(0, str(_PKG))
    from paths import ASSET_DIR, OUTPUT_DIR

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


def _require_matplotlib() -> None:
    if plt is None or mdates is None:
        raise RuntimeError("matplotlib is required for CTA chart generation")


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
    if val > 0.5:
        return "强多头"
    if val > 0.2:
        return "弱多头"
    if val > -0.2:
        return "震荡观望"
    if val > -0.5:
        return "弱空头"
    return "强空头"


def trend_strength(val: float) -> str:
    if abs(val) > 0.5:
        return "强趋势"
    if abs(val) > 0.2:
        return "弱趋势"
    return "震荡"


# ============================================================
# 回测
# ============================================================

def backtest(price: pd.Series, signals: pd.DataFrame, years: int = 2) -> dict:
    """用合成信号（前一日）× 当日对数收益率，计算策略绩效（无止损对照口径）。

    无交易成本/滑点假设，不含止损规则；含止损主口径见 backtest_with_stops，
    本函数保留用于 stdout 的止损贡献对照。
    """
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


def backtest_with_stops(
    price: pd.Series,
    signals: pd.DataFrame,
    years: int = 2,
    atr_window: int = 14,
    atr_mult: float = 2.0,
    daily_loss_limit: float = -0.05,
    deleverage_factor: float = 0.5,
) -> dict:
    """含笔记止损规则的回测（主口径）：在 backtest 的滞后一期、无成本口径上叠加两条规则。

    1) 单笔止损 2×ATR：执行信号（T-1 合成信号）方向翻转或从 0 变非 0 的当日收盘价
       记为进场价，同日 ATR 记为进场 ATR。ATR 沿用收盘价近似（atr_window 日对数收益率
       滚动标准差，与 signal_atr_position 同式），本身即比例量，故阈值"2×ATR/进场价"
       直接取 atr_mult×进场ATR。持仓期间收盘价相对进场价的逆向变动幅度（多头=下跌
       幅度、空头=上涨幅度，多空对称）> 该阈值时，当日按收盘价止损（当日收益仍按
       原仓位承受），次日起仓位为 0，直到执行信号方向变化（翻转或归零再重新出信号）
       才允许重新进场。进场日 ATR 缺失（历史不足 atr_window 日）时该持仓段不触发。
    2) 组合止损（单日回撤>5% 减仓 50%）：策略单日收益 < daily_loss_limit 时，次日起
       仓位 ×deleverage_factor，持续到该资产执行信号方向变化时复原；减仓期间再次
       触发不叠加。本脚本为单资产分别回测，"组合"按单资产策略日收益口径实现
       （单资产近似）。
    3) 两规则并存时单笔止损优先（仓位为 0）；信号方向变化同时解除两种状态。

    返回 backtest 同名指标（含止损口径）之外，另含：
    - stop_loss_count:  单笔止损触发次数；
    - deleverage_days:  组合止损减仓状态生效的交易日数；
    - daily:            执行仓位与策略日收益明细 DataFrame（测试/诊断用）。
    """
    cutoff = price.index.max() - pd.DateOffset(years=years)
    p = price[price.index >= cutoff].dropna()
    sig = signals["composite"].reindex(p.index).shift(1).fillna(0)

    log_ret = np.log(p / p.shift(1)).dropna()
    sig = sig.reindex(log_ret.index)
    close = p.reindex(log_ret.index)
    # ATR 近似按全量价格历史计算后取回测窗口值，保证窗口首日即有有效 ATR
    atr_proxy = np.log(price / price.shift(1)).rolling(atr_window).std().reindex(log_ret.index)

    sig_arr   = sig.to_numpy(dtype=float)
    ret_arr   = log_ret.to_numpy(dtype=float)
    close_arr = close.to_numpy(dtype=float)
    atr_arr   = atr_proxy.to_numpy(dtype=float)

    n = len(ret_arr)
    pos_arr   = np.zeros(n)
    strat_arr = np.zeros(n)

    prev_dir = 0
    entry_price = np.nan
    entry_atr   = np.nan
    stopped = False   # 单笔止损锁定：方向变化前禁止重新进场
    halved  = False   # 组合止损减仓状态
    stop_count = 0
    deleverage_days = 0

    for i in range(n):
        s = sig_arr[i]
        d = 0 if s == 0.0 else (1 if s > 0.0 else -1)

        if d != prev_dir:
            # 信号方向变化（翻转或归零/重新出信号）：解除止损锁定、复原减仓、重置进场价
            stopped = False
            halved = False
            if d != 0:
                entry_price = close_arr[i]
                entry_atr = atr_arr[i]
            else:
                entry_price = np.nan
                entry_atr = np.nan

        if stopped:
            pos = 0.0
        elif halved:
            pos = s * deleverage_factor
        else:
            pos = s
        pos_arr[i] = pos
        day_ret = pos * ret_arr[i]
        strat_arr[i] = day_ret
        if halved:
            deleverage_days += 1

        # 收盘后检查单笔止损：当日按收盘价离场（当日收益已承受），次日起仓位为 0
        if d != 0 and not stopped and np.isfinite(entry_price) and np.isfinite(entry_atr) and entry_price > 0:
            adverse_frac = d * (entry_price - close_arr[i]) / entry_price
            if adverse_frac > atr_mult * entry_atr:
                stop_count += 1
                stopped = True

        # 收盘后检查组合止损：单日收益 < -5% → 次日起减仓 50%（已减仓则不叠加）
        if day_ret < daily_loss_limit and not halved:
            halved = True

        prev_dir = d

    strat_ret = pd.Series(strat_arr, index=log_ret.index)
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
        "stop_loss_count":  stop_count,
        "deleverage_days":  deleverage_days,
        "daily": pd.DataFrame({"position": pos_arr, "strategy_ret": strat_arr}, index=log_ret.index),
    }


# ============================================================
# 图表
# ============================================================

def _set_style():
    _require_matplotlib()
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 160
    plt.rcParams["savefig.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["figure.facecolor"] = "white"


def plot_signals(prices: pd.DataFrame, all_signals: dict) -> Path:
    _require_matplotlib()
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

def summary_row(asset_label: str, latest: pd.Series, bt_stop: dict) -> dict:
    """构造主表一行。列名为下游契约（generate_bond_macro_report 按列名消费），
    既有列全部保留；三个回测列为含止损口径，另附止损统计两列。"""
    comp = float(latest["composite"]) if not np.isnan(latest["composite"]) else 0.0
    return {
        "资产":        asset_label,
        "均线信号":    int(latest["ma_signal"]) if not np.isnan(latest["ma_signal"]) else 0,
        "通道信号":    round(float(latest["don_signal"]), 2),
        "ATR仓位":     round(float(latest["atr_position"]), 3),
        "合成信号":    round(comp, 3),
        "趋势强度":    trend_strength(comp),
        "操作建议":    trend_label(comp),
        "策略年化收益%": round(bt_stop["strat_annual_ret"], 2),
        "策略夏普比率": round(bt_stop["strat_sharpe"], 3) if not np.isnan(bt_stop["strat_sharpe"]) else "-",
        "买持年化收益%": round(bt_stop["bh_annual_ret"], 2),
        "止损次数":    int(bt_stop["stop_loss_count"]),
        "减仓天数":    int(bt_stop["deleverage_days"]),
    }


def main():
    print("=" * 60)
    print("  CTA 趋势跟踪模型")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    prices = load_prices()

    print("\n[步骤2] 计算趋势信号...")
    all_signals = {}
    rows = []
    compare_rows = []

    for asset in prices.columns:
        price = prices[asset].dropna()
        sigs  = compute_composite(price)
        all_signals[asset] = sigs
        bt      = backtest(price, sigs)             # 无止损对照
        bt_stop = backtest_with_stops(price, sigs)  # 含止损（主口径）

        latest = sigs.dropna().iloc[-1] if len(sigs.dropna()) else sigs.iloc[-1]
        label  = ASSET_LABELS.get(asset, asset)
        rows.append(summary_row(label, latest, bt_stop))
        compare_rows.append((label, bt, bt_stop))

    df = pd.DataFrame(rows)

    print(f"\n{'='*80}")
    print("  当前趋势信号汇总（回测三列为含止损口径）")
    print(f"{'='*80}")
    print(f"  {'资产':<8} {'均线':>5} {'通道':>6} {'ATR仓位':>8} {'合成':>7} {'强度':<6} {'建议':<8} "
          f"{'策略年化%':>9} {'夏普':>7} {'止损':>4} {'减仓':>4}")
    print(f"  {'-'*78}")
    for _, r in df.iterrows():
        print(f"  {r['资产']:<8} {r['均线信号']:>5} {r['通道信号']:>6.2f} {r['ATR仓位']:>8.3f} "
              f"{r['合成信号']:>7.3f} {r['趋势强度']:<6} {r['操作建议']:<8} "
              f"{r['策略年化收益%']:>9.2f} {str(r['策略夏普比率']):>7} "
              f"{r['止损次数']:>4d} {r['减仓天数']:>4d}")

    # 止损贡献对照（无止损 vs 含止损）
    print("\n  止损贡献对照（近2年，年化%/夏普，无止损 → 含止损）:")
    for label, bt, bt_stop in compare_rows:
        base_sharpe = f"{bt['strat_sharpe']:.3f}" if not np.isnan(bt["strat_sharpe"]) else "-"
        stop_sharpe = f"{bt_stop['strat_sharpe']:.3f}" if not np.isnan(bt_stop["strat_sharpe"]) else "-"
        print(f"    {label:<8} 年化 {bt['strat_annual_ret']:+8.2f}% → {bt_stop['strat_annual_ret']:+8.2f}%   "
              f"夏普 {base_sharpe:>7} → {stop_sharpe:>7}   "
              f"止损{bt_stop['stop_loss_count']}次 减仓{bt_stop['deleverage_days']}天")

    # 趋势最强
    strongest = df.loc[df["合成信号"].abs().idxmax(), "资产"]
    print(f"\n  趋势最强资产: {strongest}（合成信号 {df.loc[df['合成信号'].abs().idxmax(), '合成信号']:+.3f}）")
    print("  注: 主表回测为含止损口径（单笔 2×ATR、组合单日回撤>5%减仓50%，单资产近似）；"
          "信号滞后一期、无成本，ATR 以收盘价收益率标准差近似。")

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
