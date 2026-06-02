# -*- coding: utf-8 -*-
"""
国债期货拥挤度模块
==================
数据源: 中金所每日结算会员成交持仓排名（Wind w.wset）

指标体系:
  1. 成交持仓比  Ratio = TV / OI          → 越大投机越强
  2. 对冲压力比  Ratio = ΔOI / TV         → 绝对值越近1套保越强
  3. 投机性多空拥挤度  SC = (多头OI - 空头OI) / (多头OI + 空头OI)
  4. 套保性多空拥挤度  HC（偏套保会员子集）
  5. 综合拥挤度  C = 0.9×SC + 0.1×HC
  6. 滚动243日分位数 → 信号：>80% 做空，<20% 做多

输出:
  crowding_latest.csv   — 最新一日快照（四品种）
  crowding_history.csv  — 历史时序
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


# ============================================================
# 中金所席位持仓数据拉取
# ============================================================

# 品种代码映射（w.wset 用的合约代码）
FUTURES_WSET = {
    'TS': 'TS.CFE',
    'TF': 'TF.CFE',
    'T':  'T.CFE',
    'TL': 'TL.CFE',
}

# 已知偏套保机构关键词（用于 HC 计算）
HEDGER_KEYWORDS = [
    '国泰君安', '中信证券', '华泰证券', '招商证券',
    '中金公司', '申万宏源', '广发证券', '兴业证券',
    '银河证券', '光大证券',
]


def fetch_cffe_positions(w, contract: str, trade_date: str) -> pd.DataFrame:
    """
    拉取中金所单日席位持仓排名
    w.wset("cffexmemberrank", "date=YYYY-MM-DD;windcode=T.CFE;rankby=volume")

    返回 DataFrame，列: member, long_oi, short_oi, volume, long_chg, short_chg
    """
    # 拉取多头持仓排名
    def _fetch(rankby: str):
        result = w.wset(
            "cffexmemberrank",
            f"date={trade_date};windcode={contract};rankby={rankby}"
        )
        if result.ErrorCode != 0:
            return None
        fields = result.Fields
        data   = result.Data
        if not fields or not data:
            return None
        df = pd.DataFrame(dict(zip(fields, data)))
        return df

    df_long  = _fetch("longholdingvolume")
    df_short = _fetch("shortholdingvolume")
    df_vol   = _fetch("volume")

    if df_long is None or df_short is None:
        return pd.DataFrame()

    # 标准化列名（Wind 返回字段名可能有大小写差异）
    def _normalize(df, rename_map):
        df.columns = [c.lower() for c in df.columns]
        return df.rename(columns=rename_map)

    col_map_long  = {'membername': 'member', 'longholdingvolume': 'long_oi',
                     'longholdingchange': 'long_chg'}
    col_map_short = {'membername': 'member', 'shortholdingvolume': 'short_oi',
                     'shortholdingchange': 'short_chg'}
    col_map_vol   = {'membername': 'member', 'volume': 'volume'}

    df_long  = _normalize(df_long,  col_map_long)
    df_short = _normalize(df_short, col_map_short)

    # 合并
    keep_long  = [c for c in ['member', 'long_oi', 'long_chg']  if c in df_long.columns]
    keep_short = [c for c in ['member', 'short_oi', 'short_chg'] if c in df_short.columns]

    merged = pd.merge(
        df_long[keep_long],
        df_short[keep_short],
        on='member', how='outer'
    ).fillna(0)

    if df_vol is not None:
        df_vol = _normalize(df_vol, col_map_vol)
        keep_vol = [c for c in ['member', 'volume'] if c in df_vol.columns]
        merged = pd.merge(merged, df_vol[keep_vol], on='member', how='left').fillna(0)
    else:
        merged['volume'] = 0

    return merged


# ============================================================
# 拥挤度计算
# ============================================================

def classify_hedger(member_name: str) -> bool:
    """判断是否为偏套保机构（简单关键词匹配）"""
    for kw in HEDGER_KEYWORDS:
        if kw in str(member_name):
            return True
    return False


def calc_crowding(positions_df: pd.DataFrame) -> dict:
    """
    输入: 单日席位持仓 DataFrame
    输出: 拥挤度指标字典
    """
    if positions_df.empty:
        return {}

    total_long  = positions_df['long_oi'].sum()
    total_short = positions_df['short_oi'].sum()
    total_vol   = positions_df.get('volume', pd.Series([0])).sum()
    total_oi    = total_long + total_short

    # 防除零
    if total_oi == 0:
        return {}

    # 1. 投机性多空拥挤度 SC（全部席位）
    SC = (total_long - total_short) / total_oi

    # 2. 套保性多空拥挤度 HC（偏套保机构子集）
    hedger_mask = positions_df['member'].apply(classify_hedger)
    hedger_df   = positions_df[hedger_mask]
    if len(hedger_df) > 0:
        h_long  = hedger_df['long_oi'].sum()
        h_short = hedger_df['short_oi'].sum()
        h_total = h_long + h_short
        HC = (h_long - h_short) / h_total if h_total > 0 else 0.0
    else:
        HC = 0.0

    # 3. 综合拥挤度
    C = 0.9 * SC + 0.1 * HC

    # 4. 成交持仓比（投机强度）
    total_oi_single = (total_long + total_short) / 2  # 单边持仓
    tv_oi_ratio = total_vol / total_oi_single if total_oi_single > 0 else np.nan

    # 5. 对冲压力比（需要昨日OI，此处用变化量近似）
    delta_oi = positions_df['long_chg'].sum() - positions_df['short_chg'].sum() \
               if 'long_chg' in positions_df.columns else np.nan
    hedge_ratio = abs(delta_oi) / total_vol if total_vol > 0 and not np.isnan(delta_oi) else np.nan

    return {
        'SC':           round(SC, 4),
        'HC':           round(HC, 4),
        'C':            round(C, 4),
        'tv_oi_ratio':  round(tv_oi_ratio, 4) if not np.isnan(tv_oi_ratio) else np.nan,
        'hedge_ratio':  round(hedge_ratio, 4) if not np.isnan(hedge_ratio) else np.nan,
        'total_long':   int(total_long),
        'total_short':  int(total_short),
        'total_vol':    int(total_vol),
    }


# ============================================================
# 历史拥挤度时序构建
# ============================================================

def fetch_crowding_history(w, lookback_days: int = 365) -> pd.DataFrame:
    """
    逐日拉取近 lookback_days 个交易日的拥挤度数据
    注意：w.wset 每次只能拉单日，需要循环
    """
    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(days=lookback_days)

    # 生成交易日列表（跳过周末，Wind 会自动处理非交易日）
    date_range = pd.bdate_range(start=start_dt, end=end_dt)
    trade_dates = [d.strftime('%Y-%m-%d') for d in date_range]

    print(f"\n[拥挤度] 拉取 {len(trade_dates)} 个交易日数据...")

    all_rows = []
    failed   = 0

    for i, td in enumerate(trade_dates):
        if (i + 1) % 20 == 0:
            print(f"  进度: {i+1}/{len(trade_dates)}")

        for name, code in FUTURES_WSET.items():
            pos_df = fetch_cffe_positions(w, code, td)
            if pos_df.empty:
                failed += 1
                continue

            metrics = calc_crowding(pos_df)
            if not metrics:
                continue

            all_rows.append({
                'date':   td,
                '品种':   name,
                **metrics,
            })

    print(f"  完成，失败 {failed} 次（非交易日正常）")

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df = df.sort_values(['品种', 'date']).reset_index(drop=True)
    return df


# ============================================================
# 分位数信号生成
# ============================================================

def generate_crowding_signal(history_df: pd.DataFrame,
                              window: int = 243) -> pd.DataFrame:
    """
    对每个品种计算滚动 window 日分位数，生成多空信号

    信号规则（来自 PDF 第4.6节）:
      C > 80% 分位 且 连续2日上涨 → 做空（多头过度拥挤）
      C < 20% 分位 且 连续2日下跌 → 做多（空头过度拥挤）
      其余 → 中性

    返回每个品种最新一日的信号
    """
    result_rows = []

    for name in ['TS', 'TF', 'T', 'TL']:
        sub = history_df[history_df['品种'] == name].copy()
        if len(sub) < 10:
            continue

        sub = sub.sort_values('date').reset_index(drop=True)
        sub['C_smooth'] = sub['C'].rolling(5, min_periods=1).mean()  # 近1周平滑

        # 滚动分位数
        sub['C_pct'] = sub['C_smooth'].rolling(window, min_periods=20).apply(
            lambda x: float(np.mean(x <= x.iloc[-1])), raw=False
        )

        # 连续上涨/下跌判断（最近2日）
        sub['C_up2']   = (sub['C_smooth'].diff() > 0) & (sub['C_smooth'].diff().shift(1) > 0)
        sub['C_down2'] = (sub['C_smooth'].diff() < 0) & (sub['C_smooth'].diff().shift(1) < 0)

        latest = sub.iloc[-1]
        c_pct  = latest['C_pct']

        if not np.isnan(c_pct):
            if c_pct > 0.80 and latest['C_up2']:
                signal = '做空'
                note   = f"多头拥挤({c_pct:.0%})且连续上升，反向做空"
            elif c_pct < 0.20 and latest['C_down2']:
                signal = '做多'
                note   = f"空头拥挤({c_pct:.0%})且连续下降，反向做多"
            elif c_pct > 0.80:
                signal = '警惕多头'
                note   = f"多头拥挤({c_pct:.0%})，尚未连续上升，观察"
            elif c_pct < 0.20:
                signal = '警惕空头'
                note   = f"空头拥挤({c_pct:.0%})，尚未连续下降，观察"
            else:
                signal = '中性'
                note   = f"拥挤度中性({c_pct:.0%})"
        else:
            signal = '数据不足'
            note   = '历史数据不足以计算分位数'

        result_rows.append({
            '品种':       name,
            '日期':       latest['date'],
            'SC':         round(latest['SC'], 4),
            'HC':         round(latest['HC'], 4),
            'C':          round(latest['C'], 4),
            'C_smooth':   round(latest['C_smooth'], 4),
            'C分位数':    round(c_pct, 3) if not np.isnan(c_pct) else np.nan,
            '拥挤度信号': signal,
            '说明':       note,
            '多头持仓':   int(latest['total_long']),
            '空头持仓':   int(latest['total_short']),
        })

    return pd.DataFrame(result_rows)


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("国债期货拥挤度模块")
    print("=" * 60)

    w = connect_wind()
    if w is None:
        print("[ERROR] Wind 不可用，退出")
        sys.exit(1)

    # 拉取历史数据
    history_df = fetch_crowding_history(w, lookback_days=365)

    if history_df.empty:
        print("[ERROR] 未能获取任何拥挤度数据")
        w.stop()
        sys.exit(1)

    # 生成信号
    print("\n[计算] 分位数信号...")
    latest_df = generate_crowding_signal(history_df, window=243)

    # 输出
    history_path = ROOT / 'crowding_history.csv'
    latest_path  = ROOT / 'crowding_latest.csv'

    history_df.to_csv(history_path, index=False, encoding='utf-8-sig')
    latest_df.to_csv(latest_path,   index=False, encoding='utf-8-sig')

    print(f"\n[输出] {history_path}  ({len(history_df)} 行)")
    print(f"[输出] {latest_path}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("拥挤度快照")
    print("=" * 60)
    cols = ['品种', '日期', 'C', 'C_smooth', 'C分位数', '拥挤度信号', '说明']
    available = [c for c in cols if c in latest_df.columns]
    print(latest_df[available].to_string(index=False))

    w.stop()
    print("\n完成")


if __name__ == '__main__':
    main()
