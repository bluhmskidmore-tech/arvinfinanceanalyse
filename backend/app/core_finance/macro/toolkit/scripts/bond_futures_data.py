# -*- coding: utf-8 -*-
"""
国债期货数据层
==============
功能：
  1. 拉取 T/TF/TS/TL 四个品种主力合约价格、持仓量、成交量
  2. 拉取对应期限国债现券收益率
  3. 计算转换因子（CF）近似值
  4. 识别 CTD 券（最廉价交割券）
  5. 计算净基差 = 现券净价 - 期货价格 × CF - 持有收益
  6. 计算 IRR（隐含回购利率）

数据源: Wind API
输出:
  bond_futures_latest.csv   — 最新一日快照
  bond_futures_history.csv  — 历史时序（近1年）

Wind 代码说明:
  T  主力: T.CFE    TF 主力: TF.CFE
  TS 主力: TS.CFE   TL 主力: TL.CFE
  现券收益率用中债到期收益率代理
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
# Wind 连接（复用 crisis_score_cn.py 的模式）
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
        print("[ERROR] WindPy 未安装，请确认 Wind 终端已启动")
        return None


def wind_wsd(w, codes: str, fields: str, start: str, end: str,
             options: str = "Fill=Previous"):
    """安全的 w.wsd 调用，返回 DataFrame，列名为 Wind 代码"""
    result = w.wsd(codes, fields, start, end, options)
    if result.ErrorCode != 0:
        print(f"[WARN] w.wsd 错误 {result.ErrorCode}: codes={codes}, fields={fields}")
        return None

    times  = result.Times
    data   = result.Data
    codes_list = result.Codes if hasattr(result, 'Codes') else [codes]
    fields_list = fields.split(',') if ',' in fields else [fields]

    # 单代码多字段 → 列名用字段名
    if len(codes_list) == 1 and len(fields_list) > 1:
        df = pd.DataFrame({'date': times})
        for i, f in enumerate(fields_list):
            if i < len(data):
                df[f.strip()] = data[i]
    # 多代码单字段 → 列名用代码
    elif len(codes_list) > 1 and len(fields_list) == 1:
        df = pd.DataFrame({'date': times})
        for i, c in enumerate(codes_list):
            if i < len(data):
                df[c] = data[i]
    # 单代码单字段
    else:
        df = pd.DataFrame({'date': times, codes_list[0]: data[0]})

    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    df = df.replace([float('inf'), float('-inf')], np.nan)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


# ============================================================
# Wind 代码定义
# ============================================================

# 国债期货主力合约
FUTURES_CODES = {
    'TS': 'TS.CFE',   # 2年期
    'TF': 'TF.CFE',   # 5年期
    'T':  'T.CFE',    # 10年期
    'TL': 'TL.CFE',   # 30年期
}

# 对应期限的中债国债到期收益率（代理现券收益率）
YIELD_CODES = {
    'TS': 'S0059745',   # 中债国债到期收益率:2年
    'TF': 'S0059747',   # 中债国债到期收益率:5年
    'T':  'S0059749',   # 中债国债到期收益率:10年
    'TL': 'S0059752',   # 中债国债到期收益率:30年
}

# 资金成本代理：DR007
DR007_CODE = 'DR007.IB'

# 合约面值（元）
FACE_VALUE = {
    'TS': 2_000_000,
    'TF': 1_000_000,
    'T':  1_000_000,
    'TL': 1_000_000,
}

# 合约票面利率（中金所规定 3%）
COUPON_RATE = 0.03

# 各品种 CTD 券的典型剩余期限（年）—— 用于 CF 近似计算
# 实际 CTD 每季度换券，这里用中间值近似
CTD_MATURITY = {
    'TS': 1.875,   # 1.5~2.25年中间
    'TF': 4.625,   # 4~5.25年中间
    'T':  8.0,     # ≥6.5年，典型约8年
    'TL': 27.5,    # ≥25年，典型约27.5年
}


# ============================================================
# 核心计算函数
# ============================================================

def calc_cf_approximate(ytm: float, maturity: float,
                        coupon: float = COUPON_RATE,
                        freq: int = 2) -> float:
    """
    转换因子近似计算
    CF = 面值1元的可交割券，按合约票面利率（3%）折现的现值

    参数:
        ytm      : 当前收益率（小数，如 0.025）
        maturity : 剩余期限（年）
        coupon   : 票面利率（小数，默认 3%）
        freq     : 付息频率（默认半年付息=2）

    注：这是简化公式，实际 CF 由中金所官方计算，此处用于方向性判断
    """
    if maturity <= 0 or ytm <= 0:
        return 1.0

    discount_rate = COUPON_RATE  # 折现率固定用合约票面利率 3%
    n = int(maturity * freq)     # 付息期数
    c = coupon / freq            # 每期票息

    # 现金流折现
    cf_val = 0.0
    for t in range(1, n + 1):
        cf_val += c / (1 + discount_rate / freq) ** t
    cf_val += 1.0 / (1 + discount_rate / freq) ** n  # 本金

    return round(cf_val, 6)


def calc_carry(ytm: float, dr007: float, maturity: float,
               coupon: float = COUPON_RATE, days: int = 90) -> float:
    """
    持有收益估算（简化）
    持有收益 = 票息收入 - 资金成本
    = coupon × (days/365) - dr007 × (days/365)

    参数:
        ytm     : 现券收益率（小数）
        dr007   : 资金成本（小数，如 0.018）
        maturity: 剩余期限（年，未使用，保留接口）
        coupon  : 票面利率（小数）
        days    : 持有天数（默认90天，约一个季度）
    """
    carry = (coupon - dr007) * (days / 365)
    return round(carry, 6)


def calc_net_basis(spot_price: float, futures_price: float,
                   cf: float, carry: float) -> float:
    """
    净基差 = 现券净价 - 期货价格 × CF - 持有收益

    净基差 > 0: 现券相对期货偏贵，做空基差（做空现券+做多期货）
    净基差 < 0: 期货相对现券偏贵，做多基差（做多现券+做空期货）
    净基差 ≈ 0: 无套利均衡

    注：spot_price 用收益率反推的净价（面值100元）
    """
    return round(spot_price - futures_price * cf - carry, 4)


def calc_irr(spot_price: float, futures_price: float,
             cf: float, coupon: float, days_to_delivery: int) -> float:
    """
    IRR（隐含回购利率）
    IRR = (期货价格×CF + 应计利息 - 现券全价) / 现券全价 × 365/n × 100%

    简化版：忽略应计利息差异，用净价近似
    IRR = (futures_price × cf - spot_price) / spot_price × 365 / days_to_delivery
    """
    if spot_price <= 0 or days_to_delivery <= 0:
        return np.nan
    irr = (futures_price * cf - spot_price) / spot_price * 365 / days_to_delivery
    return round(irr * 100, 4)  # 返回百分数


def ytm_to_price(ytm: float, maturity: float,
                 coupon: float = COUPON_RATE, freq: int = 2) -> float:
    """
    用收益率反推债券净价（面值100元）
    用于将 Wind 收益率数据转换为可比价格
    """
    if ytm <= 0 or maturity <= 0:
        return 100.0

    n = int(maturity * freq)
    c = coupon / freq * 100   # 每期票息（面值100）
    r = ytm / freq            # 每期折现率

    price = 0.0
    for t in range(1, n + 1):
        price += c / (1 + r) ** t
    price += 100.0 / (1 + r) ** n
    return round(price, 4)


# ============================================================
# 数据拉取
# ============================================================

def fetch_futures_data(w, lookback_days: int = 365) -> dict:
    """拉取四个品种的期货价格、持仓量、成交量"""
    end_date  = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

    print(f"\n[期货数据] {start_date} ~ {end_date}")
    result = {}

    for name, code in FUTURES_CODES.items():
        print(f"  拉取 {name} ({code})...", end="", flush=True)
        df = wind_wsd(w, code, 'close,oi,volume', start_date, end_date)
        if df is not None and not df.empty:
            df.columns = ['close', 'oi', 'volume']
            result[name] = df
            print(f"OK ({len(df)}天)")
        else:
            print("FAILED")

    return result


def fetch_yield_data(w, lookback_days: int = 365) -> dict:
    """拉取四个期限的国债收益率"""
    end_date   = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

    print(f"\n[收益率数据] {start_date} ~ {end_date}")
    result = {}

    for name, code in YIELD_CODES.items():
        print(f"  拉取 {name} 收益率 ({code})...", end="", flush=True)
        df = wind_wsd(w, code, 'close', start_date, end_date)
        if df is not None and not df.empty:
            result[name] = df.iloc[:, 0]
            print(f"OK ({len(df)}天)")
        else:
            print("FAILED")

    return result


def fetch_dr007(w, lookback_days: int = 365) -> pd.Series:
    """拉取 DR007"""
    end_date   = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

    print(f"  拉取 DR007...", end="", flush=True)
    df = wind_wsd(w, DR007_CODE, 'close', start_date, end_date)
    if df is not None and not df.empty:
        print(f"OK ({len(df)}天)")
        return df.iloc[:, 0]
    print("FAILED")
    return pd.Series(dtype=float)


# ============================================================
# 综合计算：净基差 + IRR + CF
# ============================================================

def compute_basis_metrics(futures_data: dict, yield_data: dict,
                          dr007: pd.Series) -> pd.DataFrame:
    """
    对每个品种计算：CF、现券净价、净基差、IRR、持有收益
    返回最新一日的汇总 DataFrame
    """
    rows = []

    for name in ['TS', 'TF', 'T', 'TL']:
        if name not in futures_data or name not in yield_data:
            continue

        fut_df  = futures_data[name]
        ytm_ser = yield_data[name]

        # 对齐日期
        common_idx = fut_df.index.intersection(ytm_ser.index)
        if len(common_idx) == 0:
            continue

        fut_close = fut_df.loc[common_idx, 'close']
        ytm_vals  = ytm_ser.loc[common_idx] / 100  # Wind 收益率是百分数，转小数

        # DR007 对齐
        dr007_aligned = dr007.reindex(common_idx, method='ffill') / 100

        maturity = CTD_MATURITY[name]

        # 逐日计算
        cf_series        = ytm_vals.apply(lambda y: calc_cf_approximate(y, maturity))
        spot_price_series = ytm_vals.apply(lambda y: ytm_to_price(y, maturity))
        carry_series     = dr007_aligned.apply(
            lambda d: calc_carry(0.03, d if not np.isnan(d) else 0.018, maturity)
        )
        net_basis_series = pd.Series([
            calc_net_basis(sp, fp, cf, carry)
            for sp, fp, cf, carry in zip(
                spot_price_series, fut_close, cf_series, carry_series
            )
        ], index=common_idx)

        irr_series = pd.Series([
            calc_irr(sp, fp, cf, COUPON_RATE, 90)
            for sp, fp, cf in zip(spot_price_series, fut_close, cf_series)
        ], index=common_idx)

        # 取最新值
        latest_date = common_idx[-1]
        dr007_latest = dr007_aligned.iloc[-1] if len(dr007_aligned) > 0 else np.nan

        rows.append({
            '品种':        name,
            '日期':        latest_date.strftime('%Y-%m-%d'),
            '期货价格':    round(fut_close.iloc[-1], 3),
            '现券净价':    round(spot_price_series.iloc[-1], 3),
            '收益率%':     round(ytm_vals.iloc[-1] * 100, 4),
            'CF':          round(cf_series.iloc[-1], 6),
            '净基差':      round(net_basis_series.iloc[-1], 4),
            'IRR%':        round(irr_series.iloc[-1], 4),
            '持有收益':    round(carry_series.iloc[-1], 4),
            'DR007%':      round(dr007_latest * 100, 4),
            'IRR-DR007':   round(irr_series.iloc[-1] - (dr007_latest * 100), 4),
            '持仓量':      int(fut_df.loc[latest_date, 'oi']) if not np.isnan(fut_df.loc[latest_date, 'oi']) else 0,
            '成交量':      int(fut_df.loc[latest_date, 'volume']) if not np.isnan(fut_df.loc[latest_date, 'volume']) else 0,
        })

    return pd.DataFrame(rows)


def compute_history(futures_data: dict, yield_data: dict,
                    dr007: pd.Series) -> pd.DataFrame:
    """
    生成历史时序 DataFrame，用于后续净基差趋势分析
    列: date, 品种, 期货价格, 净基差, IRR%, IRR-DR007
    """
    all_rows = []

    for name in ['TS', 'TF', 'T', 'TL']:
        if name not in futures_data or name not in yield_data:
            continue

        fut_df  = futures_data[name]
        ytm_ser = yield_data[name]
        common_idx = fut_df.index.intersection(ytm_ser.index)
        if len(common_idx) == 0:
            continue

        fut_close = fut_df.loc[common_idx, 'close']
        ytm_vals  = ytm_ser.loc[common_idx] / 100
        dr007_aligned = dr007.reindex(common_idx, method='ffill') / 100
        maturity = CTD_MATURITY[name]

        cf_series         = ytm_vals.apply(lambda y: calc_cf_approximate(y, maturity))
        spot_price_series = ytm_vals.apply(lambda y: ytm_to_price(y, maturity))
        carry_series      = dr007_aligned.apply(
            lambda d: calc_carry(0.03, d if not np.isnan(d) else 0.018, maturity)
        )
        net_basis_series  = pd.Series([
            calc_net_basis(sp, fp, cf, carry)
            for sp, fp, cf, carry in zip(
                spot_price_series, fut_close, cf_series, carry_series
            )
        ], index=common_idx)
        irr_series = pd.Series([
            calc_irr(sp, fp, cf, COUPON_RATE, 90)
            for sp, fp, cf in zip(spot_price_series, fut_close, cf_series)
        ], index=common_idx)

        for dt in common_idx:
            dr007_val = dr007_aligned.loc[dt] * 100 if dt in dr007_aligned.index else np.nan
            all_rows.append({
                'date':       dt.strftime('%Y-%m-%d'),
                '品种':       name,
                '期货价格':   round(fut_close.loc[dt], 3),
                '收益率%':    round(ytm_vals.loc[dt] * 100, 4),
                '净基差':     round(net_basis_series.loc[dt], 4),
                'IRR%':       round(irr_series.loc[dt], 4),
                'DR007%':     round(dr007_val, 4),
                'IRR-DR007':  round(irr_series.loc[dt] - dr007_val, 4)
                              if not np.isnan(dr007_val) else np.nan,
            })

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df = df.sort_values(['品种', 'date']).reset_index(drop=True)
    return df


# ============================================================
# 安全边际判断（第二层过滤逻辑）
# ============================================================

def check_safety_margin(latest_df: pd.DataFrame,
                        history_df: pd.DataFrame) -> pd.DataFrame:
    """
    基于净基差和 IRR-DR007 判断安全边际
    结合历史分位数（滚动120日）

    返回在 latest_df 基础上增加以下列：
      净基差分位数   : 当前净基差在近120日的历史分位
      IRR分位数      : 当前 IRR-DR007 在近120日的历史分位
      安全边际_多    : True = 做多期货有安全边际（净基差偏负 + IRR合理）
      安全边际_空    : True = 做空期货有安全边际（净基差偏正）
      安全边际说明   : 文字描述
    """
    result_rows = []

    for _, row in latest_df.iterrows():
        name = row['品种']
        hist = history_df[history_df['品种'] == name].copy()

        if len(hist) < 20:
            result_rows.append({**row.to_dict(),
                                 '净基差分位数': np.nan,
                                 'IRR分位数': np.nan,
                                 '安全边际_多': False,
                                 '安全边际_空': False,
                                 '安全边际说明': '历史数据不足'})
            continue

        # 近120日分位数
        recent = hist.tail(120)
        nb_pct  = float(np.mean(recent['净基差'] <= row['净基差']))
        irr_pct = float(np.mean(recent['IRR-DR007'] <= row['IRR-DR007']))

        # 做多安全边际：净基差偏低（<40%分位）且 IRR > DR007
        long_ok  = (nb_pct < 0.40) and (row['IRR-DR007'] > 0)
        # 做空安全边际：净基差偏高（>60%分位）
        short_ok = (nb_pct > 0.60)

        if long_ok:
            note = f"净基差低位({nb_pct:.0%})，IRR高于资金成本，做多有安全边际"
        elif short_ok:
            note = f"净基差高位({nb_pct:.0%})，做空有安全边际"
        else:
            note = f"净基差中性({nb_pct:.0%})，安全边际不足，等待"

        result_rows.append({
            **row.to_dict(),
            '净基差分位数': round(nb_pct, 3),
            'IRR分位数':    round(irr_pct, 3),
            '安全边际_多':  long_ok,
            '安全边际_空':  short_ok,
            '安全边际说明': note,
        })

    return pd.DataFrame(result_rows)


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("国债期货数据层")
    print("=" * 60)

    w = connect_wind()
    if w is None:
        print("[ERROR] Wind 不可用，退出")
        sys.exit(1)

    # 拉取数据
    futures_data = fetch_futures_data(w, lookback_days=365)
    yield_data   = fetch_yield_data(w, lookback_days=365)
    dr007        = fetch_dr007(w, lookback_days=365)

    if not futures_data or not yield_data or dr007.empty:
        print("[ERROR] 数据拉取失败，请检查 Wind 连接")
        sys.exit(1)

    # 计算指标
    print("\n[计算] 净基差 / IRR / CF...")
    latest_df  = compute_basis_metrics(futures_data, yield_data, dr007)
    history_df = compute_history(futures_data, yield_data, dr007)

    # 安全边际判断
    print("[计算] 安全边际...")
    latest_with_margin = check_safety_margin(latest_df, history_df)

    # 输出
    latest_path  = ROOT / 'bond_futures_latest.csv'
    history_path = ROOT / 'bond_futures_history.csv'

    latest_with_margin.to_csv(latest_path, index=False, encoding='utf-8-sig')
    history_df.to_csv(history_path, index=False, encoding='utf-8-sig')

    print(f"\n[输出] {latest_path}")
    print(f"[输出] {history_path}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("最新快照")
    print("=" * 60)
    cols = ['品种', '日期', '期货价格', '收益率%', '净基差', 'IRR%',
            'IRR-DR007', '安全边际_多', '安全边际_空', '安全边际说明']
    available = [c for c in cols if c in latest_with_margin.columns]
    print(latest_with_margin[available].to_string(index=False))

    w.stop()
    print("\n完成")


if __name__ == '__main__':
    main()
