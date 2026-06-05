"""
中国版美林时钟（连续信号 + 流动性维度）
==========================================
改造要点（vs 经典美林时钟）:
  1. 二分法 → 连续信号: 增长/通胀动量为 -1~+1 的连续值，不做硬切割
  2. 加入第三维度: 流动性（M2增速 - 名义GDP增速）
  3. 多指标合成: 增长不只看工业增加值，通胀不只看CPI
  4. 输出资产偏好得分，而非简单的四象限标签

数据源: Wind EDB（宏观经济数据库）
输出: 增长动量 / 通胀动量 / 流动性动量 + 各资产偏好得分
"""

import sys
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os
from pathlib import Path

_PKG = Path(__file__).resolve().parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
from paths import OUTPUT_DIR

# ============================================================
# Wind 连接
# ============================================================

def connect_wind():
    """连接 Wind"""
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


def wind_edb(w, codes: dict, start: str, end: str) -> pd.DataFrame:
    """
    从 Wind EDB 拉取宏观指标，返回 DataFrame。
    codes: {指标名: Wind代码}
    """
    codes_list = list(codes.values())
    names_list = list(codes.keys())
    codes_str = ",".join(codes_list)

    result = w.edb(codes_str, start, end, "Fill=Previous")
    if result.ErrorCode != 0:
        print(f"[WARN] w.edb 错误 {result.ErrorCode}")
        return pd.DataFrame()

    times = result.Times
    data = result.Data

    df = pd.DataFrame({'date': times})
    for i, name in enumerate(names_list):
        if i < len(data):
            df[name] = data[i]

    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()

    # 清理
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


# ============================================================
# 指标定义
# ============================================================

# 增长代理指标（多指标合成）
GROWTH_INDICATORS = {
    'pmi':              'M0017126',   # 制造业PMI
    'industrial_va':    'M0000545',   # 工业增加值:当月同比
    'pmi_new_orders':   'M0017127',   # PMI:新订单
    'electricity':      'M0000543',   # 发电量:当月同比
    'freight':          'M5524813',   # 货运量:当月同比
}

# 通胀代理指标
INFLATION_INDICATORS = {
    'cpi_yoy':   'M0000612',   # CPI:当月同比
    'ppi_yoy':   'M0001227',   # PPI:全部工业品:当月同比
}

# 流动性代理指标
LIQUIDITY_INDICATORS = {
    'm2_yoy':             'M0001385',   # M2:同比
    'social_financing':   'M5525763',   # 社会融资规模存量:同比
}

# 增长指标权重
GROWTH_WEIGHTS = {
    'pmi':            0.30,   # PMI 最及时
    'industrial_va':  0.25,   # 工业增加值最直接
    'pmi_new_orders': 0.25,   # 新订单是领先指标
    'electricity':    0.10,   # 发电量不可造假
    'freight':        0.10,   # 货运量同理
}


# ============================================================
# 动量计算
# ============================================================

def compute_momentum(series: pd.Series, short_window: int = 3,
                     long_window: int = 12) -> pd.Series:
    """
    计算动量信号: 短期均值 vs 长期均值，归一化到 [-1, +1]

    > 0: 加速（短期高于长期）
    < 0: 减速（短期低于长期）

    用 tanh 压缩到 [-1, +1]，避免极端值主导
    """
    short_ma = series.rolling(short_window, min_periods=1).mean()
    long_ma = series.rolling(long_window, min_periods=3).mean()
    long_std = series.rolling(long_window, min_periods=3).std()

    # 防除零
    long_std = long_std.replace(0, np.nan)

    # 标准化差值
    raw = (short_ma - long_ma) / long_std

    # tanh 压缩到 [-1, +1]
    momentum = np.tanh(raw)

    return momentum


def compute_growth_momentum(df: pd.DataFrame) -> pd.Series:
    """合成增长动量（多指标加权）"""
    momentums = {}
    for name, weight in GROWTH_WEIGHTS.items():
        if name in df.columns:
            m = compute_momentum(df[name])
            momentums[name] = m * weight

    if not momentums:
        return pd.Series(dtype=float)

    # 加权求和
    result = pd.DataFrame(momentums).sum(axis=1)
    total_weight = sum(GROWTH_WEIGHTS[k] for k in momentums.keys())
    if total_weight > 0:
        result = result / total_weight

    return result


def compute_inflation_momentum(df: pd.DataFrame) -> pd.Series:
    """合成通胀动量: CPI×0.4 + PPI×0.6（中国PPI比CPI更重要）"""
    cpi_m = compute_momentum(df['cpi_yoy']) if 'cpi_yoy' in df.columns else None
    ppi_m = compute_momentum(df['ppi_yoy']) if 'ppi_yoy' in df.columns else None

    if cpi_m is not None and ppi_m is not None:
        return 0.4 * cpi_m + 0.6 * ppi_m
    elif cpi_m is not None:
        return cpi_m
    elif ppi_m is not None:
        return ppi_m
    else:
        return pd.Series(dtype=float)


def compute_liquidity_momentum(df: pd.DataFrame) -> pd.Series:
    """
    流动性动量: M2增速 和 社融增速 的动量均值

    这是经典美林时钟缺失的第三维度。
    中国市场很多行情是流动性驱动而非基本面驱动（如2024.09）。
    """
    m2_m = compute_momentum(df['m2_yoy']) if 'm2_yoy' in df.columns else None
    sf_m = compute_momentum(df['social_financing']) if 'social_financing' in df.columns else None

    if m2_m is not None and sf_m is not None:
        return 0.5 * m2_m + 0.5 * sf_m
    elif m2_m is not None:
        return m2_m
    elif sf_m is not None:
        return sf_m
    else:
        return pd.Series(dtype=float)


# ============================================================
# 资产偏好评分
# ============================================================

def compute_asset_scores(growth: float, inflation: float,
                         liquidity: float) -> dict:
    """
    根据三维动量计算各资产的偏好得分 [-1, +1]

    逻辑（基于尽调笔记的宏观对冲框架）:
      股票: 增长↑ 有利, 通胀适度有利, 流动性↑ 有利
      债券: 增长↓ 有利, 通胀↓ 有利, 流动性↑ 有利
      商品: 增长↑ 有利, 通胀↑ 有利, 流动性影响小
      现金: 增长↓ 有利, 通胀↑ 有利（滞胀避险）, 流动性↓ 有利
      黄金: 增长↓ 有利, 通胀↑ 有利, 流动性↑ 有利（货币宽松利好金价）
    """
    scores = {}

    # 股票: +growth, -extreme_inflation, +liquidity
    inflation_penalty = -0.3 * max(0, inflation - 0.5)  # 通胀过高才惩罚
    scores['股票'] = 0.45 * growth + 0.15 * inflation + inflation_penalty + 0.40 * liquidity

    # 债券: -growth, -inflation, +liquidity
    scores['债券'] = -0.35 * growth - 0.35 * inflation + 0.30 * liquidity

    # 商品: +growth, +inflation, 流动性中性
    scores['商品'] = 0.40 * growth + 0.50 * inflation + 0.10 * liquidity

    # 现金: -growth, +inflation(滞胀), -liquidity
    scores['现金'] = -0.30 * growth + 0.30 * inflation - 0.40 * liquidity

    # 黄金: -growth, +inflation, +liquidity
    scores['黄金'] = -0.25 * growth + 0.40 * inflation + 0.35 * liquidity

    # 压缩到 [-1, +1]
    for k in scores:
        scores[k] = float(np.tanh(scores[k]))

    return scores


def get_regime_label(growth: float, inflation: float) -> str:
    """传统四象限标签（仅供参考，不作为交易信号）"""
    if growth > 0 and inflation <= 0:
        return "复苏"
    elif growth > 0 and inflation > 0:
        return "过热"
    elif growth <= 0 and inflation > 0:
        return "滞胀"
    else:
        return "衰退"


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("  中国版美林时钟（连续信号 + 流动性维度）")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    w = connect_wind()
    if w is None:
        return

    # 拉取5年宏观数据
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=5 * 365)).strftime('%Y-%m-%d')
    print(f"\n数据区间: {start_date} ~ {end_date}")

    # 合并所有指标代码
    all_codes = {}
    all_codes.update(GROWTH_INDICATORS)
    all_codes.update(INFLATION_INDICATORS)
    all_codes.update(LIQUIDITY_INDICATORS)

    print("拉取宏观指标...", flush=True)
    df = wind_edb(w, all_codes, start_date, end_date)

    if df.empty:
        print("未获取到数据，退出。")
        return

    print(f"  获取到 {len(df)} 个月度数据点")
    print(f"  指标列: {list(df.columns)}")

    # 检查数据完整性
    print("\n数据完整性:")
    for col in df.columns:
        valid = df[col].notna().sum()
        print(f"  {col:<20}: {valid}/{len(df)} 有效")

    # 计算三维动量
    print("\n计算动量信号...")
    growth_m = compute_growth_momentum(df)
    inflation_m = compute_inflation_momentum(df)
    liquidity_m = compute_liquidity_momentum(df)

    # 合并结果
    result = pd.DataFrame({
        'growth_momentum': growth_m,
        'inflation_momentum': inflation_m,
        'liquidity_momentum': liquidity_m,
    }).dropna()

    if result.empty:
        print("动量计算结果为空，退出。")
        return

    # 添加传统象限标签
    result['regime'] = result.apply(
        lambda r: get_regime_label(r['growth_momentum'], r['inflation_momentum']),
        axis=1
    )

    # 当前状态
    latest = result.iloc[-1]
    g = latest['growth_momentum']
    i = latest['inflation_momentum']
    l = latest['liquidity_momentum']
    regime = latest['regime']

    print(f"\n{'='*60}")
    print(f"  当前宏观状态 ({result.index[-1].strftime('%Y-%m')})")
    print(f"{'='*60}")
    print(f"  增长动量:   {g:+.3f}  {'↑加速' if g > 0.1 else '↓减速' if g < -0.1 else '→平稳'}")
    print(f"  通胀动量:   {i:+.3f}  {'↑升温' if i > 0.1 else '↓降温' if i < -0.1 else '→平稳'}")
    print(f"  流动性动量: {l:+.3f}  {'↑宽松' if l > 0.1 else '↓收紧' if l < -0.1 else '→中性'}")
    print(f"  传统象限:   {regime}")

    # 资产偏好得分
    scores = compute_asset_scores(g, i, l)

    print(f"\n  资产偏好得分 [-1, +1]:")
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for asset, score in sorted_scores:
        bar_len = int(abs(score) * 20)
        bar = ("+" * bar_len) if score >= 0 else ("-" * bar_len)
        print(f"    {asset:<6}: {score:+.3f}  {bar}")

    # 排名
    ranking = " > ".join([f"{a}" for a, _ in sorted_scores])
    print(f"\n  资产排序: {ranking}")

    # 最近12个月趋势
    print(f"\n  最近12个月动量趋势:")
    recent = result.tail(12)
    print(f"  {'月份':<10} {'增长':>8} {'通胀':>8} {'流动性':>8} {'象限':<6}")
    print(f"  {'-'*44}")
    for idx, row in recent.iterrows():
        print(f"  {idx.strftime('%Y-%m'):<10} {row['growth_momentum']:>+8.3f} "
              f"{row['inflation_momentum']:>+8.3f} {row['liquidity_momentum']:>+8.3f} "
              f"{row['regime']:<6}")

    # 保存（与 paths.output 一致）
    output_dir = str(OUTPUT_DIR)

    # 完整历史
    history_path = os.path.join(output_dir, 'merrill_clock_history.csv')
    export = result.copy()
    export.index.name = 'date'
    # 加上资产得分
    for idx in export.index:
        row = export.loc[idx]
        s = compute_asset_scores(
            row['growth_momentum'],
            row['inflation_momentum'],
            row['liquidity_momentum']
        )
        for asset, score in s.items():
            export.loc[idx, f'score_{asset}'] = score

    export.to_csv(history_path, encoding='utf-8-sig', float_format='%.4f')
    print(f"\n历史数据已保存: {history_path}")

    # 最新快照
    snapshot_path = os.path.join(output_dir, 'merrill_clock_latest.csv')
    # 国债期货方向信号（第一层过滤）
    # 逻辑：增长减速 + 流动性宽松 → 利率下行 → 做多期货
    #       增长加速 + 通胀升温     → 利率上行 → 做空期货
    #       其余                   → 观望
    if g < -0.2 and l > 0:
        bond_direction = '多'
        bond_note = f'增长减速({g:+.2f})+流动性宽松({l:+.2f})，利率下行预期'
    elif g > 0.2 and i > 0.2:
        bond_direction = '空'
        bond_note = f'增长加速({g:+.2f})+通胀升温({i:+.2f})，利率上行压力'
    elif g < -0.2 and i < -0.1:
        bond_direction = '多'
        bond_note = f'增长减速({g:+.2f})+通胀降温({i:+.2f})，债券强势'
    else:
        bond_direction = '观望'
        bond_note = f'宏观信号不明确(g={g:+.2f},i={i:+.2f},l={l:+.2f})'

    print(f"\n  国债期货方向: {bond_direction}  ({bond_note})")

    snapshot_data = {
        '日期': result.index[-1].strftime('%Y-%m'),
        '增长动量': f"{g:+.3f}",
        '通胀动量': f"{i:+.3f}",
        '流动性动量': f"{l:+.3f}",
        '传统象限': regime,
        'bond_direction': bond_direction,
        'bond_note': bond_note,
    }
    for asset, score in sorted_scores:
        snapshot_data[f'{asset}偏好'] = f"{score:+.3f}"

    pd.DataFrame([snapshot_data]).to_csv(snapshot_path, index=False, encoding='utf-8-sig')
    print(f"最新快照已保存: {snapshot_path}")

    print("\n完成。")


if __name__ == '__main__':
    main()
