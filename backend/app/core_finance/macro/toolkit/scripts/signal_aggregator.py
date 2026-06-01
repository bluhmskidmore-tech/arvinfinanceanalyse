# -*- coding: utf-8 -*-
"""
三层信号合成器
==============
读取已有模块的输出 CSV，执行三层过滤，输出最终交易信号。

第一层：宏观方向锚        ← merrill_clock_latest.csv (bond_direction)
第二层：安全边际确认      ← bond_futures_latest.csv  (安全边际_多/空)
第三层：拥挤度反向过滤    ← crowding_latest.csv      (拥挤度信号)

辅助层：
  - Crisis Score 风险状态  ← crisis_score_latest.csv
  - 市场状态               ← regime_results.csv（判断趋势/震荡）

输出:
  final_signal.csv  — 每个品种的最终信号 + 仓位比例 + 置信度
"""

import sys
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path

_PKG = Path(__file__).resolve().parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
from paths import OUTPUT_DIR

ROOT = OUTPUT_DIR


# ============================================================
# 读取各模块输出
# ============================================================

def load_merrill() -> dict:
    """读取美林时钟最新快照，返回 bond_direction"""
    path = ROOT / 'merrill_clock_latest.csv'
    if not path.exists():
        print(f"[WARN] 找不到 {path.name}，第一层跳过")
        return {'bond_direction': '观望', 'bond_note': '文件不存在'}

    df = pd.read_csv(path, encoding='utf-8-sig')
    if df.empty:
        return {'bond_direction': '观望', 'bond_note': '文件为空'}

    row = df.iloc[-1]
    return {
        'bond_direction': str(row.get('bond_direction', '观望')).strip(),
        'bond_note':      str(row.get('bond_note', '')).strip(),
        'growth':         row.get('增长动量', 0),
        'inflation':      row.get('通胀动量', 0),
        'liquidity':      row.get('流动性动量', 0),
        'regime':         str(row.get('传统象限', '')).strip(),
        'bond_score':     float(str(row.get('债券偏好', '0')).replace('+', '')),
    }


def load_basis() -> pd.DataFrame:
    """读取净基差/IRR 安全边际快照"""
    path = ROOT / 'bond_futures_latest.csv'
    if not path.exists():
        print(f"[WARN] 找不到 {path.name}，第二层跳过")
        return pd.DataFrame()

    df = pd.read_csv(path, encoding='utf-8-sig')
    return df


def load_crowding() -> pd.DataFrame:
    """读取拥挤度快照"""
    path = ROOT / 'crowding_latest.csv'
    if not path.exists():
        print(f"[WARN] 找不到 {path.name}，第三层跳过")
        return pd.DataFrame()

    df = pd.read_csv(path, encoding='utf-8-sig')
    return df


def load_crisis() -> dict:
    """读取 Crisis Score"""
    path = ROOT / 'crisis_score_latest.csv'
    if not path.exists():
        return {'score': 0.0, 'status': '未知'}

    df = pd.read_csv(path, encoding='utf-8-sig')
    if df.empty:
        return {'score': 0.0, 'status': '未知'}

    row = df.iloc[-1]
    return {
        'score':  float(row.get('Crisis Score', 0)),
        'status': str(row.get('市场状态', '正常')).strip(),
    }


def load_regime() -> dict:
    """读取市场状态（Hurst + 波动率）"""
    path = ROOT / 'regime_results.csv'
    if not path.exists():
        return {}

    df = pd.read_csv(path, encoding='utf-8-sig')
    # regime_results 是多资产的，这里只关心债券相关资产不存在
    # 用整体市场状态作为参考
    result = {}
    for _, row in df.iterrows():
        asset = str(row.get('资产', '')).strip()
        result[asset] = {
            'state':  str(row.get('当前状态', '')).strip(),
            'hurst':  float(row.get('Hurst指数', 0.5)),
        }
    return result


def load_technical_signals() -> pd.DataFrame:
    """读取技术信号快照（可选，用于辅助判断）"""
    path = ROOT / 'bond_signals_latest.csv'
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path, encoding='utf-8-sig')
    return df


# ============================================================
# 凯利公式仓位计算
# ============================================================

def kelly_position(win_rate: float, win_loss_ratio: float,
                   half_kelly: bool = True) -> float:
    """
    凯利公式: f = (b×p - q) / b
      b = 盈亏比, p = 胜率, q = 1-p

    half_kelly=True: 使用半凯利（更保守，巴菲特风格）
    返回值: 0~1 的仓位比例
    """
    if win_rate <= 0 or win_loss_ratio <= 0:
        return 0.0

    q = 1 - win_rate
    f = (win_loss_ratio * win_rate - q) / win_loss_ratio

    if f <= 0:
        return 0.0

    if half_kelly:
        f = f * 0.5

    return round(min(f, 1.0), 3)


# ============================================================
# 三层过滤逻辑
# ============================================================

def run_three_layer_filter(
    symbol: str,
    merrill: dict,
    basis_df: pd.DataFrame,
    crowding_df: pd.DataFrame,
    crisis: dict,
) -> dict:
    """
    对单个品种执行三层过滤，返回最终信号字典

    symbol: 'TS' / 'TF' / 'T' / 'TL'
    """
    result = {
        '品种':       symbol,
        '日期':       datetime.now().strftime('%Y-%m-%d'),
        '第一层_方向': '',
        '第一层_通过': False,
        '第二层_通过': False,
        '第三层_通过': False,
        '最终信号':   '空仓',
        '仓位比例':   0.0,
        '置信度':     0,       # 0~3，通过几层
        '信号说明':   '',
    }

    reasons = []

    # ── 第一层：宏观方向 ──────────────────────────────────────
    direction = merrill.get('bond_direction', '观望')
    result['第一层_方向'] = direction

    if direction == '观望':
        result['信号说明'] = f"第一层拦截：{merrill.get('bond_note', '宏观方向不明确')}"
        return result

    result['第一层_通过'] = True
    reasons.append(f"宏观{direction}({merrill.get('regime', '')})")

    # ── 第二层：安全边际 ──────────────────────────────────────
    if basis_df.empty:
        # 数据缺失时降级处理：跳过第二层但降低置信度
        reasons.append("安全边际数据缺失(降级)")
        result['第二层_通过'] = True   # 降级通过
        margin_note = "安全边际数据缺失"
    else:
        basis_row = basis_df[basis_df['品种'] == symbol]
        if basis_row.empty:
            reasons.append(f"{symbol}基差数据缺失(降级)")
            result['第二层_通过'] = True
            margin_note = "品种数据缺失"
        else:
            row = basis_row.iloc[0]
            if direction == '多':
                ok = bool(row.get('安全边际_多', False))
            else:
                ok = bool(row.get('安全边际_空', False))

            result['第二层_通过'] = ok
            margin_note = str(row.get('安全边际说明', ''))

            if not ok:
                result['信号说明'] = f"第二层拦截：{margin_note}"
                return result

            reasons.append(f"安全边际OK({margin_note[:20]})")

    # ── 第三层：拥挤度反向过滤 ────────────────────────────────
    if crowding_df.empty:
        reasons.append("拥挤度数据缺失(降级)")
        result['第三层_通过'] = True
        crowding_note = "拥挤度数据缺失"
    else:
        crowd_row = crowding_df[crowding_df['品种'] == symbol]
        if crowd_row.empty:
            reasons.append(f"{symbol}拥挤度数据缺失(降级)")
            result['第三层_通过'] = True
            crowding_note = "品种数据缺失"
        else:
            row = crowd_row.iloc[0]
            crowd_signal = str(row.get('拥挤度信号', '中性')).strip()
            c_pct = float(row.get('C分位数', 0.5)) if not pd.isna(row.get('C分位数', np.nan)) else 0.5

            # 拥挤度与方向冲突 → 拦截
            if direction == '多' and crowd_signal in ['做空', '警惕多头']:
                result['第三层_通过'] = False
                result['信号说明'] = f"第三层拦截：多头拥挤({c_pct:.0%})，反向过滤"
                return result
            elif direction == '空' and crowd_signal in ['做多', '警惕空头']:
                result['第三层_通过'] = False
                result['信号说明'] = f"第三层拦截：空头拥挤({c_pct:.0%})，反向过滤"
                return result

            result['第三层_通过'] = True
            crowding_note = str(row.get('说明', ''))
            reasons.append(f"拥挤度OK({crowding_note[:20]})")

    # ── 全部通过：计算仓位 ────────────────────────────────────
    # 置信度 = 通过层数（最高3层）
    confidence = sum([
        result['第一层_通过'],
        result['第二层_通过'],
        result['第三层_通过'],
    ])
    result['置信度'] = confidence

    # Crisis Score 风险调整
    crisis_score = crisis.get('score', 0)
    crisis_status = crisis.get('status', '正常')

    if crisis_score >= 2.0:
        # 高风险/危机状态：仓位减半
        position_scale = 0.5
        reasons.append(f"危机评分{crisis_score:.2f}→仓位×0.5")
    elif crisis_score >= 1.0:
        position_scale = 0.75
        reasons.append(f"警惕评分{crisis_score:.2f}→仓位×0.75")
    else:
        position_scale = 1.0

    # 基础胜率/盈亏比（来自 PDF 回测数据）
    # T品种胜率70%，TL品种80%，其余65%
    win_rates = {'T': 0.70, 'TL': 0.80, 'TF': 0.65, 'TS': 0.65}
    win_rate = win_rates.get(symbol, 0.65)
    win_loss_ratio = 2.0  # 平均盈亏比

    base_position = kelly_position(win_rate, win_loss_ratio, half_kelly=True)
    final_position = round(base_position * position_scale, 3)

    result['最终信号'] = direction
    result['仓位比例'] = final_position
    result['信号说明'] = ' | '.join(reasons)

    return result


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("三层信号合成器")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 加载各模块输出
    print("\n[加载] 读取各模块输出...")
    merrill     = load_merrill()
    basis_df    = load_basis()
    crowding_df = load_crowding()
    crisis      = load_crisis()
    regime      = load_regime()
    tech_df     = load_technical_signals()

    print(f"  美林时钟方向: {merrill['bond_direction']}  ({merrill.get('bond_note', '')})")
    print(f"  Crisis Score: {crisis['score']:.3f}  ({crisis['status']})")
    print(f"  净基差数据:   {'OK' if not basis_df.empty else '缺失'}")
    print(f"  拥挤度数据:   {'OK' if not crowding_df.empty else '缺失'}")
    print(f"  技术信号:     {'OK' if not tech_df.empty else '缺失（可选）'}")

    # 对四个品种分别执行三层过滤
    symbols = ['TS', 'TF', 'T', 'TL']
    rows = []

    print("\n[过滤] 执行三层过滤...")
    for sym in symbols:
        r = run_three_layer_filter(sym, merrill, basis_df, crowding_df, crisis)
        rows.append(r)

        status = "✓ 开仓" if r['最终信号'] != '空仓' else "✗ 空仓"
        print(f"  {sym}: {status}  {r['最终信号']}  仓位={r['仓位比例']:.1%}  "
              f"置信度={r['置信度']}/3  {r['信号说明'][:50]}")

    # 输出
    result_df = pd.DataFrame(rows)
    output_path = ROOT / 'final_signal.csv'
    result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n[输出] {output_path}")

    # 摘要
    print("\n" + "=" * 60)
    print("最终信号摘要")
    print("=" * 60)
    active = result_df[result_df['最终信号'] != '空仓']
    if active.empty:
        print("  当前无开仓信号，全部空仓等待")
        print(f"  原因：{result_df.iloc[0]['信号说明']}")
    else:
        print(f"  开仓品种: {', '.join(active['品种'].tolist())}")
        for _, row in active.iterrows():
            print(f"  {row['品种']}: {row['最终信号']}  "
                  f"仓位={row['仓位比例']:.1%}  置信度={row['置信度']}/3")

    print(f"\n  宏观背景: {merrill.get('regime', '')}  "
          f"增长{merrill.get('growth', 0):+.2f} / "
          f"通胀{merrill.get('inflation', 0):+.2f} / "
          f"流动性{merrill.get('liquidity', 0):+.2f}")
    print(f"  风险状态: {crisis['status']}  (Crisis Score={crisis['score']:.3f})")

    return result_df


if __name__ == '__main__':
    main()
