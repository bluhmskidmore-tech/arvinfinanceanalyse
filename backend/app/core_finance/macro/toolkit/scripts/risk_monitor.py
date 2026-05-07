# -*- coding: utf-8 -*-
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

使用方式：
  每日收盘后运行，检查是否需要强制平仓（在 macro_toolkit 根目录下）
  python -X utf8 scripts/risk_monitor.py

  也可在 signal_aggregator.py 之后调用：
  from risk_monitor import RiskMonitor
  monitor = RiskMonitor()
  monitor.check(current_prices, positions)
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
# 配置
# ============================================================

MAX_DRAWDOWN      = 0.03    # 最大回撤硬约束 3%
STOP_LOSS_PCT     = 0.015   # 单笔止损 1.5%
COOLING_DAYS      = 3       # 强制平仓后冷静期（交易日）
STATE_FILE        = ROOT / 'risk_state.csv'
LOG_FILE          = ROOT / 'risk_log.csv'


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
        df.to_csv(STATE_FILE, index=False, encoding='utf-8-sig')

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

        if LOG_FILE.exists():
            df_old = pd.read_csv(LOG_FILE, encoding='utf-8-sig')
            df_out = pd.concat([df_old, df_new], ignore_index=True)
        else:
            df_out = df_new

        df_out.to_csv(LOG_FILE, index=False, encoding='utf-8-sig')
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
                pnl_pct=pnl_pct
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

    def record_exit(self, symbol: str, price: float, reason: str = ''):
        """记录出场"""
        entry = self.state['entry_prices'].get(symbol, 0)
        if entry > 0:
            pnl = (price - entry) / entry
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

    # 冷静期状态
    if monitor.in_cooling_period():
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

    # 打印历史日志（最近5条）
    if LOG_FILE.exists():
        log = pd.read_csv(LOG_FILE, encoding='utf-8-sig')
        if not log.empty:
            print(f"\n最近风控事件（最近5条）:")
            print(log.tail(5).to_string(index=False))

    print("\n完成")


if __name__ == '__main__':
    main()
