"""
中国版 Crisis Score 危机评分模型
================================
基于尽调笔记的 Crisis Score 框架，将美国指标替换为中国本土指标。

原版指标（美国）→ 本土化替换：
  1. VIX              → 沪深300 实现波动率（20日滚动）
  2. 信用利差(IG-UST) → AA级信用债-国债利差（5Y）
  3. 汇率波动率(DXY)  → USD/CNY 实现波动率（20日滚动）
  4. 商品波动率(CRB)  → 南华商品指数 实现波动率（20日滚动）
  5. 流动性(TED)      → DR007 与7天逆回购利率的偏离度

数据源: Wind API (w.wsd / w.edb)
输出: 每日 Crisis Score + 历史分位数 + 状态判断
"""

import sys
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from pathlib import Path
import os

_PKG = Path(__file__).resolve().parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
from paths import OUTPUT_DIR

# ============================================================
# Wind API 连接
# ============================================================

def connect_wind():
    """连接 Wind，返回 w 对象"""
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


def wind_wsd(w, codes: str, field: str, start: str, end: str, options: str = "Fill=Previous"):
    """安全的 w.wsd 调用，返回 DataFrame"""
    result = w.wsd(codes, field, start, end, options)
    if result.ErrorCode != 0:
        print(f"[WARN] w.wsd 错误 {result.ErrorCode}: codes={codes}")
        return None

    times = result.Times
    data = result.Data
    codes_list = result.Codes if hasattr(result, 'Codes') else [codes]

    if len(codes_list) == 1:
        df = pd.DataFrame({'date': times, codes_list[0]: data[0]})
    else:
        df = pd.DataFrame({'date': times})
        for i, code in enumerate(codes_list):
            df[code] = data[i]

    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()

    # NaN 清理
    df = df.replace([float('inf'), float('-inf')], np.nan)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


# ============================================================
# 指标定义
# ============================================================

# Wind 代码
WIND_CODES = {
    # 沪深300 收盘价（用于计算实现波动率）
    'hs300': '000300.SH',

    # 信用利差: AA 中短期票据 5Y - 国债 5Y
    'credit_aa_5y': 'S0059760',     # 中债中短期票据到期收益率(AA):5年
    'treasury_5y':  'S0059747',     # 中债国债到期收益率:5年

    # USD/CNY 即期汇率
    'usdcny': 'M0067855',          # 美元兑人民币:即期汇率(中间价)

    # 南华商品指数
    'nanhua': 'NH0100.NHF',        # 南华商品指数

    # DR007
    'dr007': 'DR007.IB',           # 银行间质押式回购利率(7天)

    # 7天逆回购利率（央行政策利率）
    'reverse_repo_7d': 'M0041653', # 央行逆回购利率:7天
}


# ============================================================
# 数据获取
# ============================================================

def fetch_all_data(w, lookback_years: int = 3) -> dict:
    """拉取所有指标的历史数据"""
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=lookback_years * 365)).strftime('%Y-%m-%d')

    print(f"\n数据区间: {start_date} ~ {end_date}")
    data = {}

    # 1. 沪深300
    print("  拉取沪深300...", end="", flush=True)
    df = wind_wsd(w, WIND_CODES['hs300'], 'close', start_date, end_date)
    if df is not None:
        data['hs300'] = df.iloc[:, 0]
        print(f"OK ({len(df)}天)")
    else:
        print("FAILED")

    # 2. 信用利差 = AA 5Y - 国债 5Y
    print("  拉取信用利差...", end="", flush=True)
    codes_str = f"{WIND_CODES['credit_aa_5y']},{WIND_CODES['treasury_5y']}"
    df = wind_wsd(w, codes_str, 'close', start_date, end_date)
    if df is not None:
        aa = df.iloc[:, 0]
        gov = df.iloc[:, 1]
        data['credit_spread'] = (aa - gov).dropna()  # 单位: 百分点
        print(f"OK ({len(data['credit_spread'])}天)")
    else:
        print("FAILED")

    # 3. USD/CNY
    print("  拉取USD/CNY...", end="", flush=True)
    df = wind_wsd(w, WIND_CODES['usdcny'], 'close', start_date, end_date)
    if df is not None:
        data['usdcny'] = df.iloc[:, 0]
        print(f"OK ({len(df)}天)")
    else:
        print("FAILED")

    # 4. 南华商品指数
    print("  拉取南华商品指数...", end="", flush=True)
    df = wind_wsd(w, WIND_CODES['nanhua'], 'close', start_date, end_date)
    if df is not None:
        data['nanhua'] = df.iloc[:, 0]
        print(f"OK ({len(df)}天)")
    else:
        print("FAILED")

    # 5. DR007
    print("  拉取DR007...", end="", flush=True)
    df = wind_wsd(w, WIND_CODES['dr007'], 'close', start_date, end_date)
    if df is not None:
        data['dr007'] = df.iloc[:, 0]
        print(f"OK ({len(df)}天)")
    else:
        print("FAILED")

    # 6. 7天逆回购利率
    print("  拉取逆回购利率...", end="", flush=True)
    df = wind_wsd(w, WIND_CODES['reverse_repo_7d'], 'close', start_date, end_date)
    if df is not None:
        data['reverse_repo'] = df.iloc[:, 0]
        print(f"OK ({len(df)}天)")
    else:
        print("FAILED")

    return data


# ============================================================
# 指标计算
# ============================================================

def compute_indicators(data: dict, vol_window: int = 20) -> pd.DataFrame:
    """
    从原始数据计算5个危机指标:
      1. equity_vol:   沪深300 实现波动率（年化）
      2. credit_spread: AA-国债信用利差（百分点）
      3. fx_vol:       USD/CNY 实现波动率（年化）
      4. commodity_vol: 南华商品指数实现波动率（年化）
      5. liquidity_stress: DR007 - 逆回购利率 偏离度（百分点）
    """
    indicators = pd.DataFrame()

    # 1. 沪深300 实现波动率
    if 'hs300' in data:
        log_ret = np.log(data['hs300'] / data['hs300'].shift(1))
        indicators['equity_vol'] = log_ret.rolling(vol_window).std() * np.sqrt(252) * 100
        # 单位: 百分比年化波动率

    # 2. 信用利差（已经是百分点）
    if 'credit_spread' in data:
        indicators['credit_spread'] = data['credit_spread']

    # 3. USD/CNY 实现波动率
    if 'usdcny' in data:
        log_ret = np.log(data['usdcny'] / data['usdcny'].shift(1))
        indicators['fx_vol'] = log_ret.rolling(vol_window).std() * np.sqrt(252) * 100

    # 4. 南华商品指数实现波动率
    if 'nanhua' in data:
        log_ret = np.log(data['nanhua'] / data['nanhua'].shift(1))
        indicators['commodity_vol'] = log_ret.rolling(vol_window).std() * np.sqrt(252) * 100

    # 5. 流动性压力: DR007 - 逆回购利率
    if 'dr007' in data and 'reverse_repo' in data:
        # 对齐日期
        aligned = pd.DataFrame({
            'dr007': data['dr007'],
            'repo': data['reverse_repo']
        }).ffill()
        indicators['liquidity_stress'] = aligned['dr007'] - aligned['repo']
        # 单位: 百分点。正值=资金紧张，负值=资金宽松

    indicators = indicators.dropna(how='all')
    return indicators


# ============================================================
# Crisis Score 计算
# ============================================================

def compute_crisis_score(indicators: pd.DataFrame,
                         z_window: int = 252,
                         weights: dict = None) -> pd.DataFrame:
    """
    计算 Crisis Score:
      1. 对每个指标做滚动 z-score 标准化（lookback = z_window 天）
      2. 加权求和得到综合评分

    weights: 各指标权重，默认等权
    """
    if weights is None:
        weights = {
            'equity_vol':       0.25,   # 股市波动率权重最高
            'credit_spread':    0.25,   # 信用利差同等重要
            'fx_vol':           0.15,   # 汇率波动
            'commodity_vol':    0.15,   # 商品波动
            'liquidity_stress': 0.20,   # 流动性压力
        }

    z_scores = pd.DataFrame(index=indicators.index)

    for col in indicators.columns:
        if col not in weights:
            continue
        rolling_mean = indicators[col].rolling(z_window, min_periods=60).mean()
        rolling_std = indicators[col].rolling(z_window, min_periods=60).std()
        # 防止除零
        rolling_std = rolling_std.replace(0, np.nan)
        z_scores[f'{col}_z'] = (indicators[col] - rolling_mean) / rolling_std

    z_scores = z_scores.dropna(how='all')

    # 加权求和
    score = pd.Series(0.0, index=z_scores.index)
    total_weight = 0
    for col in indicators.columns:
        z_col = f'{col}_z'
        if z_col in z_scores.columns and col in weights:
            score += weights[col] * z_scores[z_col].fillna(0)
            total_weight += weights[col]

    if total_weight > 0:
        score = score / total_weight  # 归一化

    result = pd.DataFrame({
        'crisis_score': score,
    }, index=z_scores.index)

    # 合并 z-score 明细
    result = result.join(z_scores)

    return result


def classify_regime(score: float) -> tuple:
    """
    根据 Crisis Score 判断市场状态

    阈值说明（基于 z-score 分布）:
      < 0:    正常偏宽松
      0 ~ 1:  正常
      1 ~ 2:  警惕
      2 ~ 3:  高风险
      >= 3:   危机
    """
    if score < 0:
        return "宽松", "可适当加仓，风险偏好环境"
    elif score < 1:
        return "正常", "维持当前配置"
    elif score < 2:
        return "警惕", "降低风险敞口，增加对冲"
    elif score < 3:
        return "高风险", "大幅降仓，启动CTA保护"
    else:
        return "危机", "最低仓位，全面防御，买入期权对冲"


# ============================================================
# 历史回测验证
# ============================================================

def backtest_validation(result: pd.DataFrame, data: dict):
    """
    用已知的历史危机事件验证 Crisis Score 是否有效:
    - 2022.03 俄乌战争
    - 2022.10 地产危机
    - 2023.08 汇率贬值压力
    - 2024.01 小盘股流动性危机
    - 2024.09 政策转向前的极端悲观
    """
    crisis_events = {
        '2022-03': '俄乌战争冲击',
        '2022-10': '地产危机+二十大',
        '2023-08': '汇率贬值压力',
        '2024-01': '小盘股流动性危机',
        '2024-09': '924政策转向前',
    }

    print("\n历史危机事件验证:")
    print(f"  {'时间':<12} {'事件':<20} {'Crisis Score':>14} {'状态':<8}")
    print(f"  {'-'*58}")

    for month, event in crisis_events.items():
        mask = result.index.strftime('%Y-%m') == month
        if mask.any():
            month_scores = result.loc[mask, 'crisis_score']
            peak = month_scores.max()
            regime, _ = classify_regime(peak)
            marker = " <<<" if peak >= 1.5 else ""
            print(f"  {month:<12} {event:<20} {peak:>14.3f} {regime:<8}{marker}")
        else:
            print(f"  {month:<12} {event:<20} {'无数据':>14}")

    # 统计分布
    scores = result['crisis_score'].dropna()
    print(f"\n  Crisis Score 分布统计:")
    print(f"    均值: {scores.mean():.3f}")
    print(f"    标准差: {scores.std():.3f}")
    print(f"    25%分位: {scores.quantile(0.25):.3f}")
    print(f"    50%分位: {scores.quantile(0.50):.3f}")
    print(f"    75%分位: {scores.quantile(0.75):.3f}")
    print(f"    90%分位: {scores.quantile(0.90):.3f}")
    print(f"    95%分位: {scores.quantile(0.95):.3f}")
    print(f"    最大值: {scores.max():.3f} ({scores.idxmax().strftime('%Y-%m-%d')})")


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("  中国版 Crisis Score 危机评分模型")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 连接 Wind
    w = connect_wind()
    if w is None:
        print("\nWind 不可用，退出。")
        return

    # 拉数据（5年历史，覆盖2021年以来的主要危机事件）
    data = fetch_all_data(w, lookback_years=5)

    if not data:
        print("\n未获取到任何数据，退出。")
        return

    # 计算指标
    print("\n计算危机指标...")
    indicators = compute_indicators(data)
    print(f"  有效数据天数: {len(indicators)}")

    # 计算 Crisis Score
    print("计算 Crisis Score...")
    result = compute_crisis_score(indicators, z_window=120)
    print(f"  有效评分天数: {len(result)}")

    # 当前状态
    latest = result.iloc[-1]
    score = latest['crisis_score']
    regime, action = classify_regime(score)

    print(f"\n{'='*60}")
    print(f"  当前 Crisis Score: {score:.3f}")
    print(f"  市场状态: {regime}")
    print(f"  操作建议: {action}")
    print(f"{'='*60}")

    # 各分项 z-score
    print(f"\n  分项 z-score 明细:")
    z_cols = [c for c in result.columns if c.endswith('_z')]
    labels = {
        'equity_vol_z':       '股市波动率',
        'credit_spread_z':    '信用利差',
        'fx_vol_z':           '汇率波动率',
        'commodity_vol_z':    '商品波动率',
        'liquidity_stress_z': '流动性压力',
    }
    for col in z_cols:
        val = latest.get(col, np.nan)
        label = labels.get(col, col)
        if not np.isnan(val):
            bar = "+" * int(max(0, val) * 5) if val >= 0 else "-" * int(abs(val) * 5)
            print(f"    {label:<12}: {val:>+7.3f}  {bar}")

    # 最近30天趋势
    recent = result['crisis_score'].tail(30)
    trend_start = recent.iloc[0] if len(recent) > 0 else np.nan
    trend_end = recent.iloc[-1] if len(recent) > 0 else np.nan
    trend_dir = "上升" if trend_end > trend_start + 0.1 else "下降" if trend_end < trend_start - 0.1 else "平稳"
    print(f"\n  30日趋势: {trend_start:.3f} → {trend_end:.3f} ({trend_dir})")

    # 历史验证
    backtest_validation(result, data)

    # 保存结果
    output_dir = str(OUTPUT_DIR)

    # 完整历史
    history_path = os.path.join(output_dir, 'crisis_score_history.csv')
    export = result.copy()
    export.index.name = 'date'
    # 加上原始指标
    export = export.join(indicators, rsuffix='_raw')
    export.to_csv(history_path, encoding='utf-8-sig', float_format='%.4f')
    print(f"\n历史数据已保存: {history_path}")

    # 最新快照
    snapshot_path = os.path.join(output_dir, 'crisis_score_latest.csv')
    snapshot = pd.DataFrame([{
        '日期': result.index[-1].strftime('%Y-%m-%d'),
        'Crisis Score': f"{score:.3f}",
        '市场状态': regime,
        '操作建议': action,
        '股市波动率z': f"{latest.get('equity_vol_z', np.nan):.3f}",
        '信用利差z': f"{latest.get('credit_spread_z', np.nan):.3f}",
        '汇率波动率z': f"{latest.get('fx_vol_z', np.nan):.3f}",
        '商品波动率z': f"{latest.get('commodity_vol_z', np.nan):.3f}",
        '流动性压力z': f"{latest.get('liquidity_stress_z', np.nan):.3f}",
    }])
    snapshot.to_csv(snapshot_path, index=False, encoding='utf-8-sig')
    print(f"最新快照已保存: {snapshot_path}")

    print("\n完成。")


if __name__ == '__main__':
    main()
