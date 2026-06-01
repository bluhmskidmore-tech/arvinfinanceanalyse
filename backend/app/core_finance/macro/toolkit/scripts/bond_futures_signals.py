# -*- coding: utf-8 -*-
"""
国债期货技术信号模块
====================
复用 CTA 趋势跟踪逻辑，针对 T/TF/TS/TL 四个品种生成技术信号。

信号体系：
  1. 双均线交叉（20日/60日）
  2. 唐奇安通道突破（20日）
  3. MACD 金叉/死叉
  4. 布林带突破
  5. 多信号投票：≥2个信号同向才触发

数据源: Wind API（期货主力合约价格）
输出: bond_signals_latest.csv
"""

import sys
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

_PKG = Path(__file__).resolve().parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
from paths import OUTPUT_DIR

ROOT = OUTPUT_DIR

# ============================================================
# Wind 连接
# ============================================================

def connect_wind():
    try:
        from WindPy import w
        if not w.isconnected():
            ret = w.start()
            if ret.ErrorCode != 0:
                print(f"[ERROR] Wind 连接失败: {ret.ErrorCode}")
                return None
        print("Wind 已连接")
        return w
    except ImportError:
        print("[ERROR] WindPy 未安装")
        return None


def wind_wsd(w, codes: str, field: str, start: str, end: str,
             options: str = "Fill=Previous"):
    """安全的 w.wsd 调用"""
    result = w.wsd(codes, field, start, end, options)
    if result.ErrorCode != 0:
        print(f"[WARN] w.wsd 错误 {result.ErrorCode}: {codes}")
        return None

    times = result.Times
    data  = result.Data
    codes_list = result.Codes if hasattr(result, 'Codes') else [codes]

    if len(codes_list) == 1:
        df = pd.DataFrame({'date': times, codes_list[0]: data[0]})
    else:
        df = pd.DataFrame({'date': times})
        for i, c in enumerate(codes_list):
            if i < len(data):
                df[c] = data[i]

    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    df = df.replace([float('inf'), float('-inf')], np.nan)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


# ============================================================
# 数据拉取
# ============================================================

FUTURES_CODES = {
    'TS': 'TS.CFE',
    'TF': 'TF.CFE',
    'T':  'T.CFE',
    'TL': 'TL.CFE',
}


def fetch_futures_prices(w, lookback_days: int = 365) -> dict:
    """拉取四个品种的期货价格"""
    end_date   = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

    print(f"\n[数据] 拉取期货价格 {start_date} ~ {end_date}")
    result = {}

    for name, code in FUTURES_CODES.items():
        print(f"  {name} ({code})...", end="", flush=True)
        df = wind_wsd(w, code, 'close', start_date, end_date)
        if df is not None and not df.empty:
            result[name] = df.iloc[:, 0]
            print(f"OK ({len(df)}天)")
        else:
            print("FAILED")

    return result


# ============================================================
# 技术指标计算
# ============================================================

def signal_ma_cross(price: pd.Series, short: int = 20, long: int = 60) -> pd.Series:
    """双均线交叉：短>长 → +1，短<长 → -1"""
    ma_s = price.rolling(short, min_periods=1).mean()
    ma_l = price.rolling(long, min_periods=1).mean()
    sig = pd.Series(np.where(ma_s > ma_l, 1.0, -1.0), index=price.index)
    sig[ma_s.isna() | ma_l.isna()] = 0.0
    return sig


def signal_donchian(price: pd.Series, window: int = 20) -> pd.Series:
    """唐奇安通道突破：突破高点 → +1，跌破低点 → -1"""
    high = price.rolling(window, min_periods=1).max().shift(1)
    low  = price.rolling(window, min_periods=1).min().shift(1)
    sig = pd.Series(0.0, index=price.index)
    sig[price > high] = 1.0
    sig[price < low]  = -1.0
    sig = sig.replace(0, np.nan).ffill().fillna(0.0)
    return sig


def signal_macd(price: pd.Series, fast: int = 12, slow: int = 26,
                signal: int = 9) -> pd.Series:
    """MACD 金叉/死叉：DIF上穿DEA → +1，下穿 → -1"""
    ema_fast = price.ewm(span=fast, adjust=False).mean()
    ema_slow = price.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()

    sig = pd.Series(0.0, index=price.index)
    sig[(dif > dea) & (dif.shift(1) <= dea.shift(1))] = 1.0   # 金叉
    sig[(dif < dea) & (dif.shift(1) >= dea.shift(1))] = -1.0  # 死叉
    sig = sig.replace(0, np.nan).ffill().fillna(0.0)
    return sig


def signal_bollinger(price: pd.Series, window: int = 20,
                     num_std: float = 2.0) -> pd.Series:
    """布林带突破：突破上轨 → +1（超买，反向做空），跌破下轨 → -1（超卖，反向做多）"""
    ma  = price.rolling(window, min_periods=1).mean()
    std = price.rolling(window, min_periods=1).std()
    upper = ma + num_std * std
    lower = ma - num_std * std

    sig = pd.Series(0.0, index=price.index)
    # 国债期货：突破上轨视为超买（做空信号），跌破下轨视为超卖（做多信号）
    sig[price > upper] = -1.0  # 超买 → 做空
    sig[price < lower] = 1.0   # 超卖 → 做多
    sig = sig.replace(0, np.nan).ffill().fillna(0.0)
    return sig


# ============================================================
# 多信号投票
# ============================================================

def compute_signals(price: pd.Series) -> pd.DataFrame:
    """计算四种技术信号"""
    ma   = signal_ma_cross(price)
    don  = signal_donchian(price)
    macd = signal_macd(price)
    bb   = signal_bollinger(price)

    return pd.DataFrame({
        'ma':   ma,
        'don':  don,
        'macd': macd,
        'bb':   bb,
    })


def vote_signal(signals_df: pd.DataFrame, threshold: int = 2) -> pd.Series:
    """
    多信号投票：≥threshold 个信号同向才触发

    返回: -1（做空）/ 0（观望）/ +1（做多）
    """
    long_votes  = (signals_df > 0).sum(axis=1)
    short_votes = (signals_df < 0).sum(axis=1)

    result = pd.Series(0, index=signals_df.index)
    result[long_votes >= threshold]  = 1
    result[short_votes >= threshold] = -1

    return result


def signal_strength(vote: int, signals_df: pd.DataFrame) -> str:
    """信号强度：强/弱/观望"""
    if vote == 0:
        return '观望'

    count = (signals_df.iloc[-1] == vote).sum()
    if count >= 3:
        return '强'
    elif count >= 2:
        return '中'
    else:
        return '弱'


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("国债期货技术信号模块")
    print("=" * 60)

    w = connect_wind()
    if w is None:
        print("[ERROR] Wind 不可用，退出")
        sys.exit(1)

    # 拉取数据
    prices = fetch_futures_prices(w, lookback_days=365)
    if not prices:
        print("[ERROR] 未能获取任何价格数据")
        w.stop()
        sys.exit(1)

    # 计算信号
    print("\n[计算] 技术信号...")
    rows = []

    for name, price in prices.items():
        if len(price) < 60:
            print(f"  {name}: 数据不足，跳过")
            continue

        signals_df = compute_signals(price)
        vote = vote_signal(signals_df, threshold=2)

        latest_vote = int(vote.iloc[-1])
        latest_signals = signals_df.iloc[-1]

        # 信号方向
        if latest_vote == 1:
            direction = '多'
        elif latest_vote == -1:
            direction = '空'
        else:
            direction = '观望'

        # 信号强度
        strength = signal_strength(latest_vote, signals_df)

        # 各指标状态
        ma_status   = '多' if latest_signals['ma'] > 0 else '空' if latest_signals['ma'] < 0 else '中性'
        don_status  = '多' if latest_signals['don'] > 0 else '空' if latest_signals['don'] < 0 else '中性'
        macd_status = '多' if latest_signals['macd'] > 0 else '空' if latest_signals['macd'] < 0 else '中性'
        bb_status   = '多' if latest_signals['bb'] > 0 else '空' if latest_signals['bb'] < 0 else '中性'

        # 投票统计
        long_count  = int((latest_signals > 0).sum())
        short_count = int((latest_signals < 0).sum())

        rows.append({
            '品种':       name,
            '日期':       price.index[-1].strftime('%Y-%m-%d'),
            '最新价':     round(price.iloc[-1], 3),
            '信号方向':   direction,
            '信号强度':   strength,
            '多头票数':   long_count,
            '空头票数':   short_count,
            '双均线':     ma_status,
            '唐奇安':     don_status,
            'MACD':       macd_status,
            '布林带':     bb_status,
            '说明':       f'{long_count}多/{short_count}空，{strength}势{direction}',
        })

        print(f"  {name}: {direction}  {strength}势  ({long_count}多/{short_count}空)")

    # 输出
    result_df = pd.DataFrame(rows)
    output_path = ROOT / 'bond_signals_latest.csv'
    result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n[输出] {output_path}")

    # 摘要
    print("\n" + "=" * 60)
    print("技术信号摘要")
    print("=" * 60)
    cols = ['品种', '信号方向', '信号强度', '多头票数', '空头票数', '说明']
    print(result_df[cols].to_string(index=False))

    w.stop()
    print("\n完成")


if __name__ == '__main__':
    main()
