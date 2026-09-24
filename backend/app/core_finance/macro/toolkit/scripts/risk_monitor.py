"""
风控监控器
==========
功能：
  1. 读取 final_signal.csv 的持仓方向和仓位
  2. 读取当前期货价格，计算持仓盈亏
  3. 最大回撤 3% 硬约束 → 触发强制平仓
  4. 冷静期机制（强制平仓后停止交易 N 个交易日）
  5. 单笔止损（入场价 ±1.5%）
  6. 所有事件写入 risk_log.csv
  7. 事中动态监测（观察口径）：波动率(GARCH)/相关性(DCC)/Crisis Score
     超阈值只告警写日志、给降仓建议，不改仓位状态机

使用方式：
  每日收盘后运行，检查是否需要强制平仓（在 macro_toolkit 根目录下）
  python -X utf8 scripts/risk_monitor.py

  也可在 signal_aggregator.py 之后调用：
  from risk_monitor import RiskMonitor
  monitor = RiskMonitor()
  monitor.check(current_prices, positions)
"""

import os
import sys
import warnings

warnings.filterwarnings('ignore')

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

_PKG = Path(__file__).resolve().parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
from paths import OUTPUT_DIR

ROOT = OUTPUT_DIR

# ============================================================
# 配置
# ============================================================

MAX_DRAWDOWN      = 0.03    # 最大回撤硬约束 3%
STOP_LOSS_PCT     = 0.015   # 单笔止损 1.5%
COOLING_DAYS      = 3       # 强制平仓后冷静期（交易日）
STATE_FILE        = ROOT / 'risk_state.csv'
LOG_FILE          = ROOT / 'risk_log.csv'

# ── 事中动态监测阈值（尽调笔记观点23/24 与 Step4）─────────────
VOL_ANNUAL_PCT_LIMIT   = 30.0   # 年化波动率% > 30 → 高波动，降仓防御
CORR_WARNING_LIMIT     = 0.70   # DCC 平均相关 > 0.70 → 黄色预警
CORR_CRITICAL_LIMIT    = 0.85   # DCC 平均相关 > 0.85 → 红色预警，启动降仓
CRISIS_WATCH_LIMIT     = 1.0    # Crisis Score ≥1 警惕
CRISIS_HIGH_LIMIT      = 2.0    # Crisis Score ≥2 高风险
CRISIS_EMERGENCY_LIMIT = 3.0    # Crisis Score ≥3 危机，启动应急预案

GARCH_FILE  = 'garch_results.csv'        # 波动率维度产物
DCC_FILE    = 'dcc_latest.csv'           # 相关性维度产物
CRISIS_FILE = 'crisis_score_latest.csv'  # 系统性风险维度产物


# ============================================================
# 风控状态管理
# ============================================================

class RiskMonitor:
    """
    风控监控器

    状态持久化到 risk_state.csv，跨日保持：
      peak_value      : 历史净值峰值
      cooling_until   : 冷静期结束日期（YYYY-MM-DD）
      entry_prices    : 各品种入场价格（JSON格式）
    """

    def __init__(self, initial_capital: float = 1_000_000.0):
        self.initial_capital = initial_capital
        self.state = self._load_state()

    # ── 状态读写 ──────────────────────────────────────────────

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            try:
                df = pd.read_csv(STATE_FILE, encoding='utf-8-sig')
                row = df.iloc[-1]
                import json
                entry_prices = {}
                raw = row.get('entry_prices', '{}')
                if pd.notna(raw) and raw:
                    try:
                        entry_prices = json.loads(str(raw))
                    except Exception:
                        entry_prices = {}
                return {
                    'peak_value':    float(row.get('peak_value', self.initial_capital)),
                    'cooling_until': str(row.get('cooling_until', '')).strip(),
                    'entry_prices':  entry_prices,
                }
            except Exception as e:
                print(f"[WARN] 读取风控状态失败: {e}，使用初始状态")

        return {
            'peak_value':    self.initial_capital,
            'cooling_until': '',
            'entry_prices':  {},
        }

    def _save_state(self):
        import json
        row = {
            'date':          datetime.now().strftime('%Y-%m-%d'),
            'peak_value':    self.state['peak_value'],
            'cooling_until': self.state['cooling_until'],
            'entry_prices':  json.dumps(self.state['entry_prices'], ensure_ascii=False),
        }
        df = pd.DataFrame([row])
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_path = STATE_FILE.with_name(f"{STATE_FILE.name}.{os.getpid()}.tmp")
        try:
            df.to_csv(temp_path, index=False, encoding='utf-8-sig')
            temp_path.replace(STATE_FILE)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _log_event(self, event_type: str, symbol: str, detail: str,
                   current_value: float = 0.0, drawdown: float = 0.0):
        row = {
            'datetime':     datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'event_type':   event_type,
            'symbol':       symbol,
            'detail':       detail,
            'current_value': round(current_value, 2),
            'drawdown_pct': round(drawdown * 100, 4),
        }
        df_new = pd.DataFrame([row])
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        write_header = not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0
        df_new.to_csv(LOG_FILE, mode='a', header=write_header, index=False, encoding='utf-8-sig')
        print(f"  [LOG] {event_type} | {symbol} | {detail}")

    # ── 冷静期检查 ────────────────────────────────────────────

    def in_cooling_period(self) -> bool:
        """是否在冷静期内"""
        cooling_until = self.state.get('cooling_until', '')
        if not cooling_until:
            return False
        try:
            until_dt = datetime.strptime(cooling_until, '%Y-%m-%d')
            return datetime.now() < until_dt
        except Exception:
            return False

    def set_cooling_period(self, days: int = COOLING_DAYS):
        """设置冷静期"""
        # 跳过周末，计算 N 个交易日后
        end_dt = datetime.now()
        count  = 0
        while count < days:
            end_dt += timedelta(days=1)
            if end_dt.weekday() < 5:  # 周一到周五
                count += 1
        self.state['cooling_until'] = end_dt.strftime('%Y-%m-%d')
        print(f"  [冷静期] 设置至 {self.state['cooling_until']} ({days}个交易日)")

    # ── 核心检查逻辑 ──────────────────────────────────────────

    def check_portfolio(self, current_value: float) -> dict:
        """
        检查组合级别风控（最大回撤硬约束）

        参数:
            current_value: 当前组合净值（元）

        返回:
            {
              'action':   'hold' / 'force_close_all',
              'drawdown': 当前回撤比例,
              'reason':   说明文字,
            }
        """
        peak = self.state['peak_value']

        # 更新峰值
        if current_value > peak:
            self.state['peak_value'] = current_value
            peak = current_value

        drawdown = (peak - current_value) / peak if peak > 0 else 0.0

        if drawdown >= MAX_DRAWDOWN:
            self._log_event(
                'FORCE_CLOSE_ALL', 'ALL',
                f'最大回撤{drawdown:.2%}触发硬约束{MAX_DRAWDOWN:.0%}',
                current_value, drawdown
            )
            self.set_cooling_period(COOLING_DAYS)
            self._save_state()
            return {
                'action':   'force_close_all',
                'drawdown': drawdown,
                'reason':   f'最大回撤{drawdown:.2%} ≥ 硬约束{MAX_DRAWDOWN:.0%}，强制全平',
            }

        self._save_state()
        return {
            'action':   'hold',
            'drawdown': drawdown,
            'reason':   f'回撤{drawdown:.2%} < {MAX_DRAWDOWN:.0%}，正常',
        }

    def check_position(self, symbol: str, direction: str,
                       entry_price: float, current_price: float) -> dict:
        """
        检查单笔持仓止损

        参数:
            symbol:        品种 'T' / 'TL' 等
            direction:     '多' / '空'
            entry_price:   入场价格
            current_price: 当前价格

        返回:
            {'action': 'hold'/'stop_loss', 'pnl_pct': 盈亏比例, 'reason': 说明}
        """
        if entry_price <= 0:
            return {'action': 'hold', 'pnl_pct': 0.0, 'reason': '无入场价'}

        if direction == '多':
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price

        if pnl_pct <= -STOP_LOSS_PCT:
            self._log_event(
                'STOP_LOSS', symbol,
                f'{direction}仓止损: 入场{entry_price:.3f} 当前{current_price:.3f} '
                f'亏损{pnl_pct:.2%}',
                drawdown=pnl_pct
            )
            # 清除入场价
            if symbol in self.state['entry_prices']:
                del self.state['entry_prices'][symbol]
            self._save_state()
            return {
                'action':  'stop_loss',
                'pnl_pct': pnl_pct,
                'reason':  f'亏损{pnl_pct:.2%} ≤ -{STOP_LOSS_PCT:.0%}，触发止损',
            }

        return {
            'action':  'hold',
            'pnl_pct': pnl_pct,
            'reason':  f'盈亏{pnl_pct:+.2%}，正常持有',
        }

    def record_entry(self, symbol: str, price: float):
        """记录入场价格"""
        self.state['entry_prices'][symbol] = price
        self._save_state()
        self._log_event('ENTRY', symbol, f'入场价={price:.3f}')

    def record_exit(self, symbol: str, price: float, reason: str = '',
                    direction: str = '多'):
        """记录出场（direction='空' 时盈亏符号取反）"""
        entry = self.state['entry_prices'].get(symbol, 0)
        if entry > 0:
            pnl = (price - entry) / entry
            if direction == '空':
                pnl = -pnl
            self._log_event('EXIT', symbol,
                            f'出场价={price:.3f} 入场={entry:.3f} 盈亏={pnl:+.2%} {reason}')
        if symbol in self.state['entry_prices']:
            del self.state['entry_prices'][symbol]
        self._save_state()

    # ── 综合检查（日常运行入口）──────────────────────────────

    def daily_check(self, current_prices: dict,
                    positions: dict,
                    current_value: float) -> dict:
        """
        日常风控检查入口

        参数:
            current_prices: {symbol: price}  当前价格
            positions:      {symbol: {'direction': '多'/'空', 'size': 仓位比例}}
            current_value:  当前组合净值

        返回:
            {
              'status':   'ok' / 'cooling' / 'force_close' / 'stop_loss',
              'actions':  [{'symbol': ..., 'action': ...}],
              'summary':  文字摘要,
            }
        """
        print(f"\n{'='*50}")
        print(f"风控日检 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*50}")

        actions = []

        # 0. 冷静期检查
        if self.in_cooling_period():
            msg = f"冷静期中（至 {self.state['cooling_until']}），禁止开仓"
            print(f"  [冷静期] {msg}")
            return {'status': 'cooling', 'actions': [], 'summary': msg}

        # 1. 组合级别：最大回撤
        portfolio_check = self.check_portfolio(current_value)
        drawdown = portfolio_check['drawdown']
        print(f"  组合回撤: {drawdown:.2%}  ({portfolio_check['reason']})")

        if portfolio_check['action'] == 'force_close_all':
            for sym in list(positions.keys()):
                actions.append({'symbol': sym, 'action': 'force_close',
                                 'reason': portfolio_check['reason']})
            return {
                'status':  'force_close',
                'actions': actions,
                'summary': portfolio_check['reason'],
            }

        # 2. 单笔止损检查
        stop_loss_triggered = []
        for sym, pos in positions.items():
            if sym not in current_prices:
                continue
            entry = self.state['entry_prices'].get(sym, 0)
            if entry == 0:
                continue

            check = self.check_position(
                sym, pos.get('direction', '多'),
                entry, current_prices[sym]
            )
            print(f"  {sym}: {check['reason']}")

            if check['action'] == 'stop_loss':
                stop_loss_triggered.append(sym)
                actions.append({'symbol': sym, 'action': 'stop_loss',
                                 'reason': check['reason']})

        if stop_loss_triggered:
            return {
                'status':  'stop_loss',
                'actions': actions,
                'summary': f"止损触发: {', '.join(stop_loss_triggered)}",
            }

        # 3. 全部正常
        summary = (f"回撤{drawdown:.2%}，"
                   f"持仓{len(positions)}个品种，风控正常")
        print(f"  {summary}")
        return {'status': 'ok', 'actions': [], 'summary': summary}


# ============================================================
# 事中动态监测（观察口径：只监测、告警、给建议，不改仓位状态机）
# 依据尽调笔记观点23（波动率/相关性 Regime Adaptive）、
# 观点24（系统性风险上升必须降低整体暴露）与 Step4 事中监控阈值
# ============================================================

def _to_float(value):
    """标量安全转 float：转换失败或 NaN 返回 None。"""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(num) else num


def _monitor_gap(product: str, dimension: str) -> dict:
    return {
        'event_type': 'MONITOR_GAP',
        'level':      'info',
        'symbol':     'ALL',
        'detail':     f'{dimension}维度未监测: 缺少产物 {product} 或必需列',
    }


def build_monitor_alerts(garch_frame, dcc_frame, crisis_frame) -> list:
    """纯函数：根据 garch/dcc/crisis 三个产物 DataFrame 生成事中监测告警。

    参数:
        garch_frame:  garch_results.csv       需要列 [资产, 年化波动率%]
        dcc_frame:    dcc_latest.csv          需要列 [平均相关系数]（取最末行）
        crisis_frame: crisis_score_latest.csv 需要列 [Crisis Score]（取最末行）

    返回:
        [{'event_type', 'level', 'symbol', 'detail'}, ...]
        全部正常时返回 []；某维度输入 None/空/缺列时降级为一条
        MONITOR_GAP(info) 记录，不抛异常。
    """
    alerts = []

    # ── 波动率维度：任一资产年化波动率% > 30 → 高波动 ──
    if (garch_frame is None or garch_frame.empty
            or '资产' not in garch_frame.columns
            or '年化波动率%' not in garch_frame.columns):
        alerts.append(_monitor_gap(GARCH_FILE, '波动率'))
    else:
        hot = []
        for asset, raw_vol in zip(garch_frame['资产'], garch_frame['年化波动率%'], strict=True):
            vol = _to_float(raw_vol)
            if vol is not None and vol > VOL_ANNUAL_PCT_LIMIT:
                hot.append((str(asset), vol))
        if hot:
            asset_list = ','.join(asset for asset, _ in hot)
            vol_items  = '; '.join(f'{asset}={vol:.2f}%' for asset, vol in hot)
            alerts.append({
                'event_type': 'VOL_ALERT',
                'level':      'warning',
                'symbol':     asset_list,
                'detail':     (f'年化波动率>{VOL_ANNUAL_PCT_LIMIT:.0f}%: {vol_items}；'
                               f'高波动：降仓防御/尾部对冲'),
            })

    # ── 相关性维度：DCC 平均相关 > 0.70 黄色 / > 0.85 红色 ──
    if (dcc_frame is None or dcc_frame.empty
            or '平均相关系数' not in dcc_frame.columns):
        alerts.append(_monitor_gap(DCC_FILE, '相关性'))
    else:
        avg_corr = _to_float(dcc_frame.iloc[-1]['平均相关系数'])
        if avg_corr is None:
            alerts.append(_monitor_gap(DCC_FILE, '相关性'))
        elif avg_corr > CORR_CRITICAL_LIMIT:
            alerts.append({
                'event_type': 'CORR_ALERT',
                'level':      'critical',
                'symbol':     'ALL',
                'detail':     (f'DCC平均相关{avg_corr:.4f}>{CORR_CRITICAL_LIMIT:.2f}红色预警：'
                               f'分散化失效，建议降仓或对冲'),
            })
        elif avg_corr > CORR_WARNING_LIMIT:
            alerts.append({
                'event_type': 'CORR_ALERT',
                'level':      'warning',
                'symbol':     'ALL',
                'detail':     (f'DCC平均相关{avg_corr:.4f}>{CORR_WARNING_LIMIT:.2f}黄色预警：'
                               f'警惕相关性跃升'),
            })

    # ── 系统性风险维度：Crisis Score ≥1 警惕 / ≥2 高风险 / ≥3 危机 ──
    if (crisis_frame is None or crisis_frame.empty
            or 'Crisis Score' not in crisis_frame.columns):
        alerts.append(_monitor_gap(CRISIS_FILE, '系统性风险'))
    else:
        score = _to_float(crisis_frame.iloc[-1]['Crisis Score'])
        if score is None:
            alerts.append(_monitor_gap(CRISIS_FILE, '系统性风险'))
        elif score >= CRISIS_EMERGENCY_LIMIT:
            alerts.append({
                'event_type': 'CRISIS_ALERT',
                'level':      'critical',
                'symbol':     'ALL',
                'detail':     f'Crisis Score={score:.3f}≥{CRISIS_EMERGENCY_LIMIT:.0f}：'
                              f'危机状态，启动应急预案',
            })
        elif score >= CRISIS_HIGH_LIMIT:
            alerts.append({
                'event_type': 'CRISIS_ALERT',
                'level':      'critical',
                'symbol':     'ALL',
                'detail':     f'Crisis Score={score:.3f}≥{CRISIS_HIGH_LIMIT:.0f}：'
                              f'高风险，降低整体暴露',
            })
        elif score >= CRISIS_WATCH_LIMIT:
            alerts.append({
                'event_type': 'CRISIS_ALERT',
                'level':      'warning',
                'symbol':     'ALL',
                'detail':     f'Crisis Score={score:.3f}≥{CRISIS_WATCH_LIMIT:.0f}：警惕状态',
            })

    return alerts


def _load_output_csv(filename: str, output_dir: Path):
    path = output_dir / filename
    if not path.exists():
        return None
    try:
        return pd.read_csv(path, encoding='utf-8-sig')
    except Exception as e:
        print(f"  [WARN] 读取 {filename} 失败: {e}")
        return None


def run_intraday_monitor(monitor: RiskMonitor, output_dir=None) -> list:
    """事中动态监测接线：读三个产物 → 告警逐条写 risk_log → stdout 摘要。

    无告警时仅打印"监测正常"，不写 NORMAL 日志行（避免日志膨胀）。
    """
    root = Path(output_dir) if output_dir is not None else ROOT
    alerts = build_monitor_alerts(
        _load_output_csv(GARCH_FILE, root),
        _load_output_csv(DCC_FILE, root),
        _load_output_csv(CRISIS_FILE, root),
    )

    print("\n事中动态监测（波动率/相关性/Crisis Score，观察口径）:")
    if not alerts:
        print("  监测正常：三维度均低于阈值")
        return alerts

    for alert in alerts:
        monitor._log_event(
            alert['event_type'], alert['symbol'],
            f"level={alert['level']}; {alert['detail']}",
        )
    n_critical = sum(1 for a in alerts if a['level'] == 'critical')
    n_warning  = sum(1 for a in alerts if a['level'] == 'warning')
    n_info     = sum(1 for a in alerts if a['level'] == 'info')
    print(f"  告警合计 {len(alerts)} 条: critical={n_critical} "
          f"warning={n_warning} info(缺产物)={n_info}")
    return alerts


# ============================================================
# 独立运行：读取 final_signal.csv 做检查
# ============================================================

def main():
    print("=" * 60)
    print("风控监控器（独立运行模式）")
    print("=" * 60)

    monitor = RiskMonitor()

    # 读取当前信号
    signal_path = ROOT / 'final_signal.csv'
    if not signal_path.exists():
        print("[WARN] final_signal.csv 不存在，请先运行 signal_aggregator.py")
        return

    signals = pd.read_csv(signal_path, encoding='utf-8-sig')
    active  = signals[signals['最终信号'] != '空仓']

    print(f"\n当前持仓信号: {len(active)} 个品种")
    for _, row in active.iterrows():
        print(f"  {row['品种']}: {row['最终信号']}  仓位={row['仓位比例']:.1%}")

    # 事中动态监测（观察口径，独立于冷静期状态机）
    run_intraday_monitor(monitor)

    # 冷静期状态
    if monitor.in_cooling_period():
        monitor._save_state()
        monitor._log_event(
            'DAILY_CHECK',
            'ALL',
            f"active_positions={len(active)}; status=cooling; final_signal={signal_path.name}",
        )
        print(f"\n[冷静期] 当前处于冷静期，至 {monitor.state['cooling_until']}")
        print("  建议：等待冷静期结束后再开仓")
        return

    # 读取入场价（如果有）
    entry_prices = monitor.state.get('entry_prices', {})
    if entry_prices:
        print(f"\n已记录入场价: {entry_prices}")
        print("  提示：需要提供当前价格才能做止损检查")
        print("  用法: monitor.daily_check(current_prices, positions, current_value)")
    else:
        print("\n  暂无持仓入场价记录")
        print("  开仓时调用: monitor.record_entry('T', 入场价格)")

    monitor._save_state()
    monitor._log_event(
        'DAILY_CHECK',
        'ALL',
        f"active_positions={len(active)}; status=observed; final_signal={signal_path.name}",
    )

    # 打印历史日志（最近5条）
    if LOG_FILE.exists():
        log = pd.read_csv(LOG_FILE, encoding='utf-8-sig')
        if not log.empty:
            print("\n最近风控事件（最近5条）:")
            print(log.tail(5).to_string(index=False))

    print("\n完成")


if __name__ == '__main__':
    main()
