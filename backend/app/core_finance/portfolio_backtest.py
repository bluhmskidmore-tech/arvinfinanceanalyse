from __future__ import annotations

import csv
import math
import statistics
from bisect import bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from backend.app.core_finance.adjusted_returns import net_return_after_costs
from backend.app.core_finance.portfolio_paths import (
    calculate_path_horizon_exit,
    path_entry_price,
    path_mark_price,
    position_path_key,
)
from backend.app.core_finance.strategy_policy import POLICY

DEFAULT_INITIAL_CAPITAL = 100.0
DEFAULT_MAX_POSITIONS = 5
PORTFOLIO_ENGINE_VERSION = "pbt_v2_path_mode"
VOL_TARGET_NOT_WIRED_WARNING = (
    "vol_target 仅作为标注写入 metrics，模拟循环不会据此缩放仓位；"
    "实际波动率目标暴露需通过 vol_target_overlay.build_vol_target_index_comparison "
    "计算出的 exposure_by_date 传入才会生效。"
)
HORIZON_REALIZED_ONLY_WARNING = (
    "horizon 模式下持仓按买入成本记账、不做盯市，equity 曲线仅在卖出日反映损益；"
    "max_drawdown / daily_sharpe 等风险指标只覆盖已实现口径，系统性低估(确定性方向)持仓期内的"
    "真实回撤与波动。需要盯市口径请使用 mode='path'。"
)
VARIANT_HORIZONS = {
    "fixed_5d": "5d",
    "fixed_20d": "20d",
}


@dataclass(frozen=True)
class PortfolioBacktestResult:
    variant: str
    horizon: str
    equity_curve: list[dict[str, object]]
    trades: list[dict[str, object]]
    metrics: dict[str, object]
    skip_counts: dict[str, int]


@dataclass(frozen=True)
class _Candidate:
    signal_date: str
    stock_code: str
    stock_name: str
    signal_kind: str
    candidate_rank: int
    market_state: str
    entry_date: str
    exit_date: str | None
    return_net: float | None
    entry_executable: bool
    entry_block_reason: str
    daily_amount: float | None
    entry_price: float | None
    signal_close: float | None
    ema10_signal: float | None
    signal_high: float | None


@dataclass(frozen=True)
class _Lot:
    amount: float
    entry_price: float


class _IndexedPathRows(Sequence[Mapping[str, object]]):
    def __init__(self, rows: Sequence[Mapping[str, object]]) -> None:
        self._rows = tuple(rows)
        self._row_index_by_date: dict[str, int] = {}
        for index, row in enumerate(self._rows):
            date_key = _date_text(row.get("trade_date") or row.get("date"))
            self._row_index_by_date.setdefault(date_key, index)

        mark_dates: list[str] = []
        marks_as_of: list[float | None] = []
        mark: float | None = None
        for row in self._rows:
            date_key = _date_text(row.get("trade_date") or row.get("date"))
            if not date_key:
                break
            candidate = path_mark_price(row)
            if candidate is not None:
                mark = candidate
            mark_dates.append(date_key)
            marks_as_of.append(mark)
        self._mark_dates = tuple(mark_dates)
        self._marks_as_of = tuple(marks_as_of)

    def __getitem__(
        self,
        index: int | slice,
    ) -> Mapping[str, object] | tuple[Mapping[str, object], ...]:
        return self._rows[index]

    def __len__(self) -> int:
        return len(self._rows)

    def row_index(self, trade_date: str) -> int | None:
        return self._row_index_by_date.get(trade_date)

    def mark_for_date(self, trade_date: str) -> float | None:
        index = bisect_right(self._mark_dates, trade_date) - 1
        if index < 0:
            return None
        return self._marks_as_of[index]


@dataclass(frozen=True)
class _Position:
    stock_code: str
    stock_name: str
    signal_kind: str
    candidate_rank: int
    market_state: str
    entry_date: str
    exit_date: str
    amount: float
    return_net: float
    target_weight: float
    sizing: str
    entry_price: float | None = None
    path_rows: Sequence[Mapping[str, object]] = ()
    risk_per_trade: float | None = None
    stop_distance_pct: float | None = None
    risk_budget_planned: float | None = None
    stop_ref_fallback: bool = False
    exit_price: float | None = None
    lots: tuple[_Lot, ...] = ()
    entry_style: str = "full"
    target_amount: float | None = None
    signal_high: float | None = None
    probe_fraction: float | None = None
    confirm_days: int | None = None
    probe_confirmed: bool = False


def run_portfolio_backtests(
    execution_rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]] = (),
    *,
    exposure_rows: Sequence[Mapping[str, object]] = (),
    variants: Sequence[str] = tuple(VARIANT_HORIZONS),
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
    exposure_by_market_state: Mapping[str, object] = POLICY.exposure_by_market_state,
    exposure_by_date: Mapping[str, float] | None = None,
    mode: str = "horizon",
    price_paths: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
    sizing: str = "equal_weight",
    risk_per_trade: float | None = None,
    single_name_cap: float | None = None,
    fallback_stop_distance_pct: float | None = None,
    entry_style: str = "full",
    probe_fraction: float | None = None,
    confirm_days: int | None = None,
    max_entry_premium: float | None = None,
    vol_target: float | None = None,
) -> dict[str, PortfolioBacktestResult]:
    return {
        variant: run_portfolio_backtest(
            execution_rows,
            market_state_rows,
            variant=variant,
            exposure_rows=exposure_rows,
            initial_capital=initial_capital,
            max_positions=max_positions,
            exposure_by_market_state=exposure_by_market_state,
            exposure_by_date=exposure_by_date,
            mode=mode,
            price_paths=price_paths,
            sizing=sizing,
            risk_per_trade=risk_per_trade,
            single_name_cap=single_name_cap,
            fallback_stop_distance_pct=fallback_stop_distance_pct,
            entry_style=entry_style,
            probe_fraction=probe_fraction,
            confirm_days=confirm_days,
            max_entry_premium=max_entry_premium,
            vol_target=vol_target,
        )
        for variant in variants
    }


def run_portfolio_backtest(
    execution_rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]] = (),
    *,
    variant: str = "fixed_5d",
    exposure_rows: Sequence[Mapping[str, object]] = (),
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
    exposure_by_market_state: Mapping[str, object] = POLICY.exposure_by_market_state,
    exposure_by_date: Mapping[str, float] | None = None,
    mode: str = "horizon",
    price_paths: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
    sizing: str = "equal_weight",
    risk_per_trade: float | None = None,
    single_name_cap: float | None = None,
    fallback_stop_distance_pct: float | None = None,
    entry_style: str = "full",
    probe_fraction: float | None = None,
    confirm_days: int | None = None,
    max_entry_premium: float | None = None,
    vol_target: float | None = None,
) -> PortfolioBacktestResult:
    if max_positions <= 0:
        raise ValueError("max_positions must be positive")
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")
    horizon = VARIANT_HORIZONS.get(variant)
    if horizon is None:
        raise ValueError(f"Unsupported portfolio backtest variant: {variant}")
    if mode not in {"horizon", "path"}:
        raise ValueError("mode must be 'horizon' or 'path'")
    if sizing not in {"equal_weight", "risk_budget"}:
        raise ValueError("sizing must be 'equal_weight' or 'risk_budget'")
    if entry_style not in {"full", "probe_pyramid"}:
        raise ValueError("entry_style must be 'full' or 'probe_pyramid'")
    if entry_style == "probe_pyramid" and mode != "path":
        raise ValueError("probe_pyramid requires path mode")
    if max_entry_premium is not None and max_entry_premium < 0:
        raise ValueError("max_entry_premium must be non-negative")
    if vol_target is not None and vol_target <= 0:
        raise ValueError("vol_target must be positive")
    risk_per_trade_value = (
        risk_per_trade
        if risk_per_trade is not None
        else POLICY.backtest_variants.risk_budget_risk_per_trade_grid[0]
    )
    single_name_cap_value = (
        single_name_cap
        if single_name_cap is not None
        else POLICY.backtest_variants.risk_budget_single_name_cap
    )
    fallback_stop_distance_pct_value = (
        fallback_stop_distance_pct
        if fallback_stop_distance_pct is not None
        else POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct
    )
    probe_fraction_value = (
        probe_fraction if probe_fraction is not None else POLICY.backtest_variants.probe_fraction
    )
    confirm_days_value = (
        confirm_days if confirm_days is not None else POLICY.backtest_variants.probe_confirm_days_grid[0]
    )
    if sizing == "risk_budget":
        if risk_per_trade_value <= 0:
            raise ValueError("risk_per_trade must be positive")
        if single_name_cap_value <= 0:
            raise ValueError("single_name_cap must be positive")
        if fallback_stop_distance_pct_value <= 0:
            raise ValueError("fallback_stop_distance_pct must be positive")
    if entry_style == "probe_pyramid":
        if probe_fraction_value <= 0 or probe_fraction_value >= 1:
            raise ValueError("probe_fraction must be between 0 and 1")
        if confirm_days_value <= 0:
            raise ValueError("confirm_days must be positive")

    market_state_by_date = _market_state_by_date(market_state_rows)
    daily_exposure_by_date = _exposure_by_date(exposure_rows)
    if exposure_by_date:
        for key, value in exposure_by_date.items():
            exposure = _safe_float(value)
            if exposure is not None:
                daily_exposure_by_date[_date_text(key)] = min(max(exposure, 0.0), 1.0)
    exposure_basis = "per_date_actual" if daily_exposure_by_date else "state_max_fallback"
    candidates = [
        candidate
        for row in execution_rows
        if (candidate := _candidate_from_row(row, horizon=horizon)) is not None
    ]
    candidates_by_entry_date: dict[str, list[_Candidate]] = {}
    for candidate in candidates:
        candidates_by_entry_date.setdefault(candidate.entry_date, []).append(candidate)
        market_state_by_date.setdefault(candidate.entry_date, candidate.market_state)
    for rows in candidates_by_entry_date.values():
        rows.sort(key=lambda item: (item.candidate_rank, item.stock_code))

    path_rows_by_key = _price_paths_by_key(price_paths or {})
    path_exit_by_key: dict[str, dict[str, object]] = {}
    if mode == "path":
        for candidate in candidates:
            key = position_path_key(candidate.stock_code, candidate.entry_date)
            path_exit = _path_exit(path_rows_by_key.get(key, ()), horizon=horizon, entry_price=candidate.entry_price)
            if path_exit is not None:
                path_exit_by_key[key] = path_exit
    trade_dates = _portfolio_trade_dates(
        candidates,
        market_state_by_date,
        path_rows_by_key if mode == "path" else None,
        path_exit_by_key if mode == "path" else None,
    )
    cash = float(initial_capital)
    positions: list[_Position] = []
    trades: list[dict[str, object]] = []
    equity_curve: list[dict[str, object]] = []
    exposure_actual_days = 0
    exposure_fallback_days = 0
    skip_counts = {
        "entry_blocked": 0,
        "missing_exit_or_return": 0,
        "no_exposure": 0,
        "no_slot": 0,
        "insufficient_cash": 0,
        "duplicate_stock": 0,
        "exposure_cap_skip": 0,
        "entry_premium_blocked": 0,
    }
    stop_ref_fallback_count = 0
    exposure_cap_clipped_count = 0
    risk_budget_hit_count = 0
    risk_budget_trade_count = 0
    probe_entry_count = 0
    probe_confirmed_count = 0
    probe_failed_exit_count = 0
    holding_days_marked_at_cost = 0
    mtm_position_days = 0
    mtm_cost_fallback_position_days = 0
    mtm_cost_fallback_exit_trades = 0

    for trade_index, trade_date in enumerate(trade_dates):
        # 敞口由 T 日收盘决定、T+1 日生效（与 gate_timing_csi300 基准和
        # vol_target_overlay 同一口径，2026-07-19 审计 宏观 H-1）：建仓规模只能
        # 使用上一交易日已知的敞口决策，否则策略侧存在前视偏差且与已加一天
        # 滞后的基准不可比（2026-08 审计 MAC-01）。序列首日无 T-1 决策，退回当日。
        prior_trade_date = trade_dates[trade_index - 1] if trade_index > 0 else None
        trade_date_has_actual_exposure = trade_date in daily_exposure_by_date
        if trade_date_has_actual_exposure:
            exposure_actual_days += 1
        else:
            exposure_fallback_days += 1
        realized_pnl = 0.0
        if mode == "path" and entry_style == "probe_pyramid":
            updated_positions: list[_Position] = []
            for position in positions:
                probe_event = _probe_event_for_open(position, trade_date)
                if probe_event and probe_event["event"] == "fail":
                    exit_price = _safe_float(probe_event.get("price"))
                    if _position_exit_uses_cost_fallback(position, mode=mode, exit_price=exit_price):
                        mtm_cost_fallback_exit_trades += 1
                    proceeds = _position_exit_proceeds(position, mode=mode, exit_price=exit_price)
                    cash += proceeds
                    realized_pnl += proceeds - position.amount
                    probe_failed_exit_count += 1
                    risk_budget_loss, risk_budget_planned, risk_budget_hit = _risk_budget_sale_stats(
                        position,
                        return_net=_sell_return_net(position, proceeds),
                    )
                    if risk_budget_hit is not None:
                        risk_budget_trade_count += 1
                        if risk_budget_hit:
                            risk_budget_hit_count += 1
                    trades.append(
                        _sell_trade_row(
                            position,
                            trade_date=trade_date,
                            proceeds=proceeds,
                            exit_stage="probe_failed_exit",
                        )
                    )
                    continue
                if probe_event and probe_event["event"] == "confirm" and not position.probe_confirmed:
                    add_price = _safe_float(probe_event.get("price"))
                    add_amount = max((position.target_amount or position.amount) - position.amount, 0.0)
                    if add_price is not None and add_price > 0 and add_amount > 0 and cash + 1e-9 >= add_amount:
                        cash -= add_amount
                        probe_confirmed_count += 1
                        updated_position = _add_position_lot(position, amount=add_amount, entry_price=add_price)
                        trades.append(
                            {
                                "date": trade_date,
                                "action": "buy",
                                "entry_stage": "pyramid_add",
                                "stock_code": position.stock_code,
                                "stock_name": position.stock_name,
                                "signal_kind": position.signal_kind,
                                "candidate_rank": position.candidate_rank,
                                "market_state": position.market_state,
                                "amount": round(add_amount, 6),
                                "target_weight": round(updated_position.target_weight, 6),
                                "exit_date": position.exit_date,
                                "expected_return_net": None,
                                "daily_amount": None,
                                "sizing": position.sizing,
                                "risk_per_trade": position.risk_per_trade,
                                "risk_budget_planned": _round_optional(position.risk_budget_planned),
                                "stop_distance_pct": _round_optional(position.stop_distance_pct),
                                "exposure_cap_clipped": None,
                                "stop_ref_fallback": position.stop_ref_fallback
                                if position.sizing == "risk_budget"
                                else None,
                            }
                        )
                        updated_positions.append(updated_position)
                        continue
                updated_positions.append(position)
            positions = updated_positions
        if mode != "path":
            remaining_positions: list[_Position] = []
            for position in positions:
                if position.exit_date <= trade_date:
                    proceeds = _position_exit_proceeds(position, mode=mode)
                    cash += proceeds
                    realized_pnl += proceeds - position.amount
                    risk_budget_loss, risk_budget_planned, risk_budget_hit = _risk_budget_sale_stats(
                        position,
                        return_net=_sell_return_net(position, proceeds),
                    )
                    if risk_budget_hit is not None:
                        risk_budget_trade_count += 1
                        if risk_budget_hit:
                            risk_budget_hit_count += 1
                    trades.append(_sell_trade_row(position, trade_date=trade_date, proceeds=proceeds))
                else:
                    remaining_positions.append(position)
            positions = remaining_positions

        day_start_equity = cash + _invested_value(positions, trade_date, mode=mode)
        day_buy_notional = 0.0
        for candidate in candidates_by_entry_date.get(trade_date, []):
            if not candidate.entry_executable:
                skip_counts["entry_blocked"] += 1
                continue
            exit_date = candidate.exit_date
            return_net = candidate.return_net
            path_rows: Sequence[Mapping[str, object]] = ()
            entry_price = candidate.entry_price
            if mode == "path":
                path_key = position_path_key(candidate.stock_code, candidate.entry_date)
                path_rows = path_rows_by_key.get(path_key, ())
                path_exit = path_exit_by_key.get(path_key)
                if path_exit is not None:
                    exit_date = str(path_exit["exit_date"])
                    return_net = float(path_exit["return_net"])
                    entry_price = float(path_exit["entry_price"])
                    exit_price = float(path_exit["exit_price"])
                else:
                    exit_price = None
            else:
                exit_price = None
            if exit_date is None or return_net is None:
                skip_counts["missing_exit_or_return"] += 1
                continue
            if entry_style == "probe_pyramid" and candidate.signal_high is None:
                skip_counts["missing_exit_or_return"] += 1
                continue
            entry_premium = _entry_premium(entry_price=entry_price, signal_close=candidate.signal_close)
            if (
                max_entry_premium is not None
                and entry_premium is not None
                and entry_premium > max_entry_premium
            ):
                skip_counts["entry_premium_blocked"] += 1
                continue
            if any(position.stock_code == candidate.stock_code for position in positions):
                skip_counts["duplicate_stock"] += 1
                continue
            if len(positions) >= max_positions:
                skip_counts["no_slot"] += 1
                continue

            # 持仓记录的市场状态保持当日语义；仅敞口决策取 T-1（见循环头注释）。
            state = candidate.market_state or market_state_by_date.get(trade_date, "OFF")
            if prior_trade_date is not None:
                exposure_decision_date = prior_trade_date
                exposure_state = market_state_by_date.get(prior_trade_date, "OFF")
            else:
                exposure_decision_date = trade_date
                exposure_state = state
            exposure = _exposure_for_date(
                exposure_decision_date,
                state=exposure_state,
                exposure_by_date=daily_exposure_by_date,
                exposure_by_market_state=exposure_by_market_state,
            )
            if exposure <= 0:
                skip_counts["no_exposure"] += 1
                continue
            stop_distance_pct: float | None = None
            stop_ref_fallback = False
            exposure_cap_clipped = False
            if sizing == "risk_budget":
                stop_distance_pct, stop_ref_fallback = _risk_budget_stop_distance(
                    candidate,
                    fallback_stop_distance_pct=fallback_stop_distance_pct_value,
                )
                raw_target_weight = min(risk_per_trade_value / stop_distance_pct, single_name_cap_value)
                raw_target_amount = day_start_equity * raw_target_weight
                remaining_exposure_budget = max(day_start_equity * exposure - day_buy_notional, 0.0)
                if remaining_exposure_budget <= 1e-9:
                    skip_counts["exposure_cap_skip"] += 1
                    continue
                target_amount = min(raw_target_amount, remaining_exposure_budget)
                if target_amount + 1e-9 < raw_target_amount:
                    exposure_cap_clipped = True
                    exposure_cap_clipped_count += 1
            else:
                target_amount = day_start_equity * exposure / max_positions
            if target_amount <= 0:
                skip_counts["no_exposure"] += 1
                continue
            full_target_amount = target_amount
            entry_stage = "full"
            if entry_style == "probe_pyramid":
                target_amount = full_target_amount * probe_fraction_value
                entry_stage = "probe"
            if cash + 1e-9 < target_amount:
                skip_counts["insufficient_cash"] += 1
                continue

            cash -= target_amount
            day_buy_notional += target_amount
            target_weight = target_amount / day_start_equity if day_start_equity > 0 else 0.0
            risk_budget_planned = (
                target_weight * stop_distance_pct
                if sizing == "risk_budget" and stop_distance_pct is not None
                else None
            )
            if stop_ref_fallback:
                stop_ref_fallback_count += 1
            positions.append(
                _Position(
                    stock_code=candidate.stock_code,
                    stock_name=candidate.stock_name,
                    signal_kind=candidate.signal_kind,
                    candidate_rank=candidate.candidate_rank,
                    market_state=state,
                    entry_date=trade_date,
                    exit_date=exit_date,
                    amount=target_amount,
                    return_net=return_net,
                    target_weight=target_weight,
                    sizing=sizing,
                    entry_price=entry_price,
                    path_rows=path_rows,
                    risk_per_trade=risk_per_trade_value if sizing == "risk_budget" else None,
                    stop_distance_pct=stop_distance_pct,
                    risk_budget_planned=risk_budget_planned,
                    stop_ref_fallback=stop_ref_fallback,
                    exit_price=exit_price,
                    lots=(_Lot(amount=target_amount, entry_price=entry_price),)
                    if mode == "path" and entry_price is not None
                    else (),
                    entry_style=entry_style,
                    target_amount=full_target_amount,
                    signal_high=candidate.signal_high,
                    probe_fraction=probe_fraction_value if entry_style == "probe_pyramid" else None,
                    confirm_days=confirm_days_value if entry_style == "probe_pyramid" else None,
                )
            )
            if entry_style == "probe_pyramid":
                probe_entry_count += 1
            trades.append(
                {
                    "date": trade_date,
                    "action": "buy",
                    "entry_stage": entry_stage,
                    "stock_code": candidate.stock_code,
                    "stock_name": candidate.stock_name,
                    "signal_kind": candidate.signal_kind,
                    "candidate_rank": candidate.candidate_rank,
                    "market_state": state,
                    "amount": round(target_amount, 6),
                    "target_weight": round(target_weight, 6),
                    "exit_date": exit_date,
                    "expected_return_net": round(return_net, 6),
                    "daily_amount": candidate.daily_amount,
                    "entry_premium": _round_optional(entry_premium),
                    "max_entry_premium": max_entry_premium,
                    "sizing": sizing,
                    "risk_per_trade": risk_per_trade_value if sizing == "risk_budget" else None,
                    "risk_budget_planned": _round_optional(risk_budget_planned),
                    "stop_distance_pct": round(stop_distance_pct, 6)
                    if stop_distance_pct is not None
                    else None,
                    "exposure_cap_clipped": exposure_cap_clipped if sizing == "risk_budget" else None,
                    "stop_ref_fallback": stop_ref_fallback if sizing == "risk_budget" else None,
                }
            )

        # Runs for every mode so a same-day exit_date == entry_date position
        # bought above is not left open until the next trade_date.
        remaining_positions = []
        for position in positions:
            if position.exit_date <= trade_date:
                if _position_exit_uses_cost_fallback(position, mode=mode):
                    mtm_cost_fallback_exit_trades += 1
                proceeds = _position_exit_proceeds(position, mode=mode)
                cash += proceeds
                realized_pnl += proceeds - position.amount
                risk_budget_loss, risk_budget_planned, risk_budget_hit = _risk_budget_sale_stats(
                    position,
                    return_net=_sell_return_net(position, proceeds),
                )
                if risk_budget_hit is not None:
                    risk_budget_trade_count += 1
                    if risk_budget_hit:
                        risk_budget_hit_count += 1
                trades.append(_sell_trade_row(position, trade_date=trade_date, proceeds=proceeds))
            else:
                remaining_positions.append(position)
        positions = remaining_positions

        if mode == "path":
            mtm_position_days += len(positions)
            mtm_cost_fallback_position_days += sum(
                1
                for position in positions
                if _position_uses_cost_mark(position, trade_date, mode=mode)
            )
        else:
            holding_days_marked_at_cost += len(positions)
        invested = _invested_value(positions, trade_date, mode=mode)
        equity = cash + invested
        max_single_name_weight = (
            max((_position_value(position, trade_date, mode=mode) / equity for position in positions), default=0.0)
            if equity > 0
            else 0.0
        )
        date_state = market_state_by_date.get(trade_date, "OFF")
        date_exposure_basis = "per_date_actual" if trade_date_has_actual_exposure else "state_max_fallback"
        equity_curve.append(
            {
                "date": trade_date,
                "net_value": round(equity, 6),
                "cash": round(cash, 6),
                "invested": round(invested, 6),
                "open_positions": len(positions),
                "slot_utilization": round(len(positions) / max_positions, 6),
                "market_state": date_state,
                "exposure": round(
                    _exposure_for_date(
                        trade_date,
                        state=date_state,
                        exposure_by_date=daily_exposure_by_date,
                        exposure_by_market_state=exposure_by_market_state,
                    ),
                    6,
                ),
                "exposure_basis": date_exposure_basis,
                "max_single_name_weight": round(max_single_name_weight, 6),
                "buy_notional": round(day_buy_notional, 6),
                "realized_pnl": round(realized_pnl, 6),
            }
        )

    metrics = summarize_equity_curve(
        equity_curve,
        initial_capital=initial_capital,
        max_positions=max_positions,
        trades=trades,
    )
    exposure_days = exposure_actual_days + exposure_fallback_days
    mtm_cost_fallback_ratio = (
        round(mtm_cost_fallback_position_days / mtm_position_days, 6) if mtm_position_days else 0.0
    )
    metrics.update(
        {
            "portfolio_engine_version": PORTFOLIO_ENGINE_VERSION,
            "mode": mode,
            "risk_metrics_basis": "mark_to_market" if mode == "path" else "realized_only",
            "risk_metrics_warning": _risk_metrics_warning(
                mode,
                mtm_cost_fallback_position_days=mtm_cost_fallback_position_days,
                mtm_position_days=mtm_position_days,
                mtm_cost_fallback_exit_trades=mtm_cost_fallback_exit_trades,
            ),
            "holding_days_marked_at_cost": holding_days_marked_at_cost if mode != "path" else None,
            "mtm_position_days": mtm_position_days if mode == "path" else None,
            "mtm_cost_fallback_position_days": (
                mtm_cost_fallback_position_days if mode == "path" else None
            ),
            "mtm_cost_fallback_ratio": mtm_cost_fallback_ratio if mode == "path" else None,
            "mtm_cost_fallback_exit_trades": mtm_cost_fallback_exit_trades if mode == "path" else None,
            "sizing": sizing,
            "entry_style": entry_style,
            "max_entry_premium": max_entry_premium,
            "vol_target": vol_target,
            "vol_target_warning": VOL_TARGET_NOT_WIRED_WARNING if vol_target is not None else None,
            "entry_premium_blocked": skip_counts["entry_premium_blocked"],
            "probe_fraction": probe_fraction_value if entry_style == "probe_pyramid" else None,
            "confirm_days": confirm_days_value if entry_style == "probe_pyramid" else None,
            "probe_entries": probe_entry_count,
            "probe_confirmed": probe_confirmed_count,
            "probe_failed_exit": probe_failed_exit_count,
            "probe_confirm_rate": round(probe_confirmed_count / probe_entry_count, 6)
            if probe_entry_count
            else None,
            "risk_per_trade": risk_per_trade_value if sizing == "risk_budget" else None,
            "single_name_cap": single_name_cap_value if sizing == "risk_budget" else None,
            "stop_ref_fallback": stop_ref_fallback_count,
            "exposure_cap_clipped": exposure_cap_clipped_count,
            "risk_budget_hit_rate": round(risk_budget_hit_count / risk_budget_trade_count, 6)
            if risk_budget_trade_count
            else None,
            "risk_budget_hit_count": risk_budget_hit_count,
            "risk_budget_trade_count": risk_budget_trade_count,
            "exposure_basis": exposure_basis,
            "exposure_actual_days": exposure_actual_days,
            "exposure_fallback_days": exposure_fallback_days,
            "exposure_fallback_day_ratio": round(exposure_fallback_days / exposure_days, 6)
            if exposure_days
            else 0.0,
        }
    )
    metrics.update(_probe_pyramid_trade_metrics(trades, enabled=entry_style == "probe_pyramid"))
    return PortfolioBacktestResult(
        variant=variant,
        horizon=horizon,
        equity_curve=equity_curve,
        trades=trades,
        metrics=metrics,
        skip_counts=skip_counts,
    )


def summarize_equity_curve(
    equity_curve: Sequence[Mapping[str, object]],
    *,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
    trades: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    if not equity_curve:
        return {
            "sample_days": 0,
            "cumulative_return": None,
            "cagr": None,
            "max_drawdown": None,
            "daily_sharpe": None,
            "annual_turnover": None,
            "avg_slot_utilization": None,
            "empty_day_ratio": None,
            "max_single_name_weight": None,
        }

    values = [float(row["net_value"]) for row in equity_curve]
    sample_days = max(len(values) - 1, 0)
    # equity 曲线是信号驱动的稀疏日期序列，"记录条数 = 交易日"不成立；年化必须
    # 按真实日历跨度折算（365/span），与 candidate_history_proxy_backtest 的
    # PROXY_ANNUALIZATION_DAYS_PER_YEAR/span_days 同一口径（2026-08 审计 MAC-02）。
    annualization = _annualization_factor([str(row.get("date") or "") for row in equity_curve])
    terminal_value = values[-1]
    cumulative_return = terminal_value / initial_capital - 1.0 if initial_capital > 0 else None
    cagr = (
        (terminal_value / initial_capital) ** annualization - 1.0
        if annualization is not None and terminal_value > 0 and initial_capital > 0
        else None
    )
    daily_returns = [
        values[index] / values[index - 1] - 1.0
        for index in range(1, len(values))
        if values[index - 1] > 0
    ]
    daily_sharpe = _sharpe(
        daily_returns,
        periods_per_year=(sample_days * annualization if annualization is not None else None),
    )
    buy_turnover = sum(
        float(row.get("amount") or 0.0) / initial_capital
        for row in trades
        if row.get("action") == "buy"
    )
    annual_turnover = buy_turnover * annualization if annualization is not None else None
    open_counts = [int(row.get("open_positions") or 0) for row in equity_curve]
    slot_values = [
        float(row.get("slot_utilization"))
        if row.get("slot_utilization") is not None
        else count / max_positions
        for row, count in zip(equity_curve, open_counts, strict=False)
    ]
    return {
        "sample_days": sample_days,
        "terminal_value": round(terminal_value, 6),
        "cumulative_return": _round_optional(cumulative_return),
        "cagr": _round_optional(cagr),
        "max_drawdown": _round_optional(_max_drawdown(values)),
        "daily_sharpe": _round_optional(daily_sharpe),
        "annual_turnover": _round_optional(annual_turnover),
        "avg_slot_utilization": _round_optional(statistics.fmean(slot_values) if slot_values else None),
        "empty_day_ratio": _round_optional(open_counts.count(0) / len(open_counts) if open_counts else None),
        "max_single_name_weight": _round_optional(
            max(float(row.get("max_single_name_weight") or 0.0) for row in equity_curve)
        ),
    }


def build_benchmark_comparison(
    strategy_curve: Sequence[Mapping[str, object]],
    benchmark_rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]] = (),
    *,
    exposure_rows: Sequence[Mapping[str, object]] = (),
    exposure_by_market_state: Mapping[str, object] = POLICY.exposure_by_market_state,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> dict[str, object]:
    if not strategy_curve:
        return {"status": "empty", "curves": [], "metrics": {}}

    benchmark_returns = _benchmark_returns_by_date(benchmark_rows)
    if not benchmark_returns:
        return {"status": "benchmark_unavailable", "curves": [], "metrics": {}}

    state_by_date = _market_state_by_date(market_state_rows)
    exposure_by_date = _exposure_by_date(exposure_rows)
    start_date = str(strategy_curve[0]["date"])[:10]

    # Compound over the benchmark's own full trading-day calendar (not just
    # the strategy curve's anchor dates) so a sparse strategy curve cannot
    # skip intermediate benchmark trading days. Anchor lookups below then
    # take the last compounded value on or before each strategy curve date.
    buy_hold_by_date: dict[str, float] = {}
    gate_timing_by_date: dict[str, float] = {}
    buy_hold = float(initial_capital)
    gate_timing = float(initial_capital)
    # 敞口由 T 日收盘决定、T+1 日生效（与 equity_strategies 口径一致），
    # 避免"当日收盘决定的敞口吃当日收益"美化 gate 择时基准
    # （2026-07-19 审计 宏观 H-1）。首个复利日使用 start_date 收盘的决策。
    prev_exposure = _exposure_for_date(
        start_date,
        state=state_by_date.get(start_date, "OFF"),
        exposure_by_date=exposure_by_date,
        exposure_by_market_state=exposure_by_market_state,
    )
    for date_key in sorted(benchmark_returns):
        if date_key <= start_date:
            continue
        daily_return = benchmark_returns[date_key]
        buy_hold *= 1.0 + daily_return
        gate_timing *= 1.0 + daily_return * prev_exposure
        prev_exposure = _exposure_for_date(
            date_key,
            state=state_by_date.get(date_key, "OFF"),
            exposure_by_date=exposure_by_date,
            exposure_by_market_state=exposure_by_market_state,
        )
        buy_hold_by_date[date_key] = buy_hold
        gate_timing_by_date[date_key] = gate_timing
    sorted_benchmark_dates = sorted(buy_hold_by_date)

    def _value_as_of(series: Mapping[str, float], date_key: str) -> float:
        index = bisect_right(sorted_benchmark_dates, date_key) - 1
        if index < 0:
            return float(initial_capital)
        return series[sorted_benchmark_dates[index]]

    curves: list[dict[str, object]] = []
    for row in strategy_curve:
        date_key = str(row["date"])[:10]
        strategy_value = float(row["net_value"])
        buy_hold_value = _value_as_of(buy_hold_by_date, date_key)
        gate_timing_value = _value_as_of(gate_timing_by_date, date_key)
        curves.append(
            {
                "date": date_key,
                "strategy": round(strategy_value, 6),
                "csi300_buy_hold": round(buy_hold_value, 6),
                "gate_timing_csi300": round(gate_timing_value, 6),
                "stock_selection_increment": round(strategy_value - gate_timing_value, 6),
            }
        )

    strategy_values = [float(row["strategy"]) for row in curves]
    buy_hold_values = [float(row["csi300_buy_hold"]) for row in curves]
    gate_values = [float(row["gate_timing_csi300"]) for row in curves]
    curve_dates = [str(row["date"]) for row in curves]
    strategy_return = strategy_values[-1] / initial_capital - 1.0
    gate_return = gate_values[-1] / initial_capital - 1.0
    return {
        "status": "ready",
        "curves": curves,
        "metrics": {
            "strategy": _metrics_from_values(strategy_values, initial_capital=initial_capital, dates=curve_dates),
            "csi300_buy_hold": _metrics_from_values(buy_hold_values, initial_capital=initial_capital, dates=curve_dates),
            "gate_timing_csi300": _metrics_from_values(gate_values, initial_capital=initial_capital, dates=curve_dates),
            "stock_selection_increment": {
                "cumulative_return": round(strategy_return - gate_return, 6),
                "terminal_value_spread": round(strategy_values[-1] - gate_values[-1], 6),
            },
        },
    }


def liquidity_floor_summary(
    rows: Sequence[Mapping[str, object]],
    *,
    min_daily_amount: float = POLICY.entry_filters.min_daily_amount,
) -> dict[str, int | float]:
    known_pass = 0
    known_fail = 0
    missing = 0
    for row in rows:
        amount = _safe_float(row.get("daily_amount"))
        if amount is None:
            missing += 1
        elif amount >= min_daily_amount:
            known_pass += 1
        else:
            known_fail += 1
    return {
        "min_daily_amount": min_daily_amount,
        "total_rows": len(rows),
        "known_pass_rows": known_pass,
        "known_fail_rows": known_fail,
        "missing_amount_rows": missing,
    }


def filter_rows_by_liquidity_floor(
    rows: Sequence[Mapping[str, object]],
    *,
    min_daily_amount: float = POLICY.entry_filters.min_daily_amount,
) -> list[Mapping[str, object]]:
    return [
        row
        for row in rows
        if (amount := _safe_float(row.get("daily_amount"))) is None or amount >= min_daily_amount
    ]


def write_equity_curve_csv(path: str | Path, rows: Sequence[Mapping[str, object]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "date",
        "net_value",
        "cash",
        "invested",
        "open_positions",
        "slot_utilization",
        "market_state",
        "exposure",
        "exposure_basis",
        "max_single_name_weight",
        "buy_notional",
        "realized_pnl",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def _candidate_from_row(row: Mapping[str, object], *, horizon: str) -> _Candidate | None:
    signal_date = _date_text(row.get("signal_date") or row.get("snapshot_as_of_date"))
    entry_date = _date_text(row.get("entry_date")) or signal_date
    if not signal_date or not entry_date:
        return None
    stock_code = _text(row.get("stock_code"))
    if not stock_code:
        return None
    return _Candidate(
        signal_date=signal_date,
        stock_code=stock_code,
        stock_name=_text(row.get("stock_name")),
        signal_kind=_text(row.get("signal_kind")) or "stock_candidate",
        candidate_rank=_safe_int(row.get("candidate_rank") or row.get("rank"), default=999999),
        market_state=_text(row.get("market_state")) or "OFF",
        entry_date=entry_date,
        exit_date=_date_text(row.get(f"exit_date_{horizon}")),
        return_net=_first_float(
            row.get(f"return_{horizon}_net_adj"),
            row.get(f"return_{horizon}_adj"),
            row.get(f"return_{horizon}_net"),
            row.get(f"return_{horizon}"),
        ),
        entry_executable=_safe_bool(row.get("entry_executable"), default=True),
        entry_block_reason=_text(row.get("entry_block_reason")),
        daily_amount=_safe_float(row.get("daily_amount")),
        entry_price=_safe_float(row.get("entry_price")),
        signal_close=_safe_float(row.get("signal_close")),
        ema10_signal=_first_float(row.get("ema10_signal"), row.get("ema10")),
        signal_high=_first_float(row.get("signal_high"), row.get("signal_day_high")),
    )


def _portfolio_trade_dates(
    candidates: Sequence[_Candidate],
    market_state_by_date: Mapping[str, str],
    price_paths: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
    path_exit_by_key: Mapping[str, Mapping[str, object]] | None = None,
) -> list[str]:
    dates: set[str] = set()
    timeline_dates: list[str] = []
    for candidate in candidates:
        dates.add(candidate.entry_date)
        timeline_dates.append(candidate.entry_date)
        path_key = position_path_key(candidate.stock_code, candidate.entry_date)
        effective_exit_date = _date_text(
            (path_exit_by_key or {}).get(path_key, {}).get("exit_date")
            if path_exit_by_key
            else None
        ) or candidate.exit_date
        if effective_exit_date:
            dates.add(effective_exit_date)
            timeline_dates.append(effective_exit_date)
    if timeline_dates:
        start = min(timeline_dates)
        end = max(timeline_dates)
        dates.update(date_key for date_key in market_state_by_date if start <= date_key <= end)
    else:
        dates.update(market_state_by_date)
    if price_paths:
        for key, rows in price_paths.items():
            entry_bound = _path_key_entry_date(key)
            exit_bound = _date_text((path_exit_by_key or {}).get(str(key), {}).get("exit_date"))
            for row in rows:
                date_key = _date_text(row.get("trade_date") or row.get("date"))
                if not date_key:
                    continue
                lower_bound = entry_bound or (min(timeline_dates) if timeline_dates else "")
                upper_bound = exit_bound or (max(timeline_dates) if timeline_dates else "")
                if (not lower_bound or lower_bound <= date_key) and (not upper_bound or date_key <= upper_bound):
                    dates.add(date_key)
    return sorted(date for date in dates if date)


def _path_key_entry_date(key: object) -> str:
    parts = str(key).split("|", 1)
    return parts[1][:10] if len(parts) == 2 else ""


def _market_state_by_date(rows: Sequence[Mapping[str, object]]) -> dict[str, str]:
    by_date: dict[str, str] = {}
    for row in rows:
        date_key = _date_text(row.get("trade_date") or row.get("date") or row.get("snapshot_as_of_date"))
        state = _text(row.get("market_state") or row.get("state"))
        if date_key and state:
            by_date[date_key] = state
    return by_date


def _exposure_by_date(rows: Sequence[Mapping[str, object]]) -> dict[str, float]:
    by_date: dict[str, float] = {}
    for row in rows:
        date_key = _date_text(row.get("trade_date") or row.get("date") or row.get("snapshot_as_of_date"))
        exposure = _first_float(row.get("exposure"), row.get("market_gate_exposure"), row.get("value"))
        if date_key and exposure is not None:
            by_date[date_key] = min(max(exposure, 0.0), 1.0)
    return by_date


def _benchmark_returns_by_date(rows: Sequence[Mapping[str, object]]) -> dict[str, float]:
    direct_returns: dict[str, float] = {}
    value_rows: list[tuple[str, float]] = []
    for row in rows:
        date_key = _date_text(row.get("trade_date") or row.get("date"))
        if not date_key:
            continue
        daily_return = _first_float(row.get("return"), row.get("daily_return"))
        if daily_return is not None:
            direct_returns[date_key] = daily_return
            continue
        value = _first_float(row.get("value"), row.get("close"), row.get("value_numeric"))
        if value is not None and value > 0:
            value_rows.append((date_key, value))
    if direct_returns:
        return direct_returns
    returns: dict[str, float] = {}
    previous_value: float | None = None
    for date_key, value in sorted(value_rows):
        if previous_value is not None and previous_value > 0:
            returns[date_key] = value / previous_value - 1.0
        previous_value = value
    return returns


def _annualization_factor(dates: Sequence[str]) -> float | None:
    """日历跨度年化因子 365/span_days。

    信号驱动的稀疏日期序列不能按"记录条数=交易日"年化（2026-08 审计
    MAC-02）；与 candidate_history_proxy_backtest 的
    ``PROXY_ANNUALIZATION_DAYS_PER_YEAR / span_days`` 口径一致。
    跨度不足（少于 2 个可解析日期或同日）时返回 ``None``。
    """
    parsed: list[date] = []
    for value in dates:
        text = str(value or "")[:10]
        if not text:
            continue
        try:
            parsed.append(date.fromisoformat(text))
        except ValueError:
            continue
    if len(parsed) < 2:
        return None
    span_days = (max(parsed) - min(parsed)).days
    if span_days <= 0:
        return None
    return 365.0 / span_days


def _metrics_from_values(
    values: Sequence[float],
    *,
    initial_capital: float,
    dates: Sequence[str] = (),
) -> dict[str, object]:
    if not values:
        return {
            "sample_days": 0,
            "cumulative_return": None,
            "cagr": None,
            "max_drawdown": None,
            "daily_sharpe": None,
        }
    sample_days = max(len(values) - 1, 0)
    annualization = _annualization_factor(dates)
    terminal_value = values[-1]
    cagr = (
        (terminal_value / initial_capital) ** annualization - 1.0
        if annualization is not None and terminal_value > 0 and initial_capital > 0
        else None
    )
    returns = [
        values[index] / values[index - 1] - 1.0
        for index in range(1, len(values))
        if values[index - 1] > 0
    ]
    return {
        "sample_days": sample_days,
        "terminal_value": round(terminal_value, 6),
        "cumulative_return": _round_optional(terminal_value / initial_capital - 1.0),
        "cagr": _round_optional(cagr),
        "max_drawdown": _round_optional(_max_drawdown(values)),
        "daily_sharpe": _round_optional(
            _sharpe(
                returns,
                periods_per_year=(sample_days * annualization if annualization is not None else None),
            )
        ),
    }


def _exposure_for_state(state: str | None, exposure_by_market_state: Mapping[str, object]) -> float:
    raw = exposure_by_market_state.get(str(state or "OFF"), 0.0)
    if isinstance(raw, (tuple, list)):
        values = [_safe_float(value) for value in raw]
        exposure = max((value for value in values if value is not None), default=0.0)
    else:
        exposure = _safe_float(raw) or 0.0
    return min(max(exposure, 0.0), 1.0)


def _exposure_for_date(
    date_key: str,
    *,
    state: str | None,
    exposure_by_date: Mapping[str, float],
    exposure_by_market_state: Mapping[str, object],
) -> float:
    if date_key in exposure_by_date:
        return exposure_by_date[date_key]
    return _exposure_for_state(state, exposure_by_market_state)


def _risk_budget_stop_distance(
    candidate: _Candidate,
    *,
    fallback_stop_distance_pct: float,
) -> tuple[float, bool]:
    entry_price = candidate.entry_price
    ema10 = candidate.ema10_signal
    if entry_price is None or entry_price <= 0 or ema10 is None:
        return fallback_stop_distance_pct, True
    stop_distance_pct = (entry_price - ema10) / entry_price
    if stop_distance_pct <= 0 or not math.isfinite(stop_distance_pct):
        return fallback_stop_distance_pct, True
    return stop_distance_pct, False


def _entry_premium(*, entry_price: float | None, signal_close: float | None) -> float | None:
    if entry_price is None or signal_close is None or signal_close <= 0:
        return None
    return entry_price / signal_close - 1.0


def _risk_budget_sale_stats(
    position: _Position,
    *,
    return_net: float | None = None,
) -> tuple[float | None, float | None, bool | None]:
    if position.sizing != "risk_budget" or position.stop_distance_pct is None:
        return None, None, None
    effective_return_net = position.return_net if return_net is None else return_net
    risk_budget_loss = max(-effective_return_net, 0.0) * position.target_weight
    risk_budget_planned = position.risk_budget_planned
    if risk_budget_planned is None:
        risk_budget_planned = position.target_weight * position.stop_distance_pct
    return risk_budget_loss, risk_budget_planned, risk_budget_loss <= risk_budget_planned + 1e-12


def _position_exit_proceeds(
    position: _Position,
    *,
    mode: str,
    exit_price: float | None = None,
) -> float:
    if mode == "path" and position.lots:
        price = exit_price if exit_price is not None else position.exit_price
        if price is not None and price > 0:
            return sum(_lot_exit_proceeds(lot, exit_price=price) for lot in position.lots)
    return position.amount * (1.0 + position.return_net)


def _lot_exit_proceeds(lot: _Lot, *, exit_price: float) -> float:
    if lot.entry_price <= 0:
        return lot.amount
    gross_return = exit_price / lot.entry_price - 1.0
    return lot.amount * (
        1.0
        + net_return_after_costs(
            gross_return,
            buy_cost_rate=POLICY.buy_cost_rate,
            sell_cost_rate=POLICY.sell_cost_rate,
            slippage_rate=POLICY.slippage_rate,
        )
    )


def _sell_return_net(position: _Position, proceeds: float) -> float:
    return proceeds / position.amount - 1.0 if position.amount > 0 else position.return_net


def _sell_trade_row(
    position: _Position,
    *,
    trade_date: str,
    proceeds: float,
    exit_stage: str = "scheduled_exit",
) -> dict[str, object]:
    return_net = _sell_return_net(position, proceeds)
    risk_budget_loss, risk_budget_planned, risk_budget_hit = _risk_budget_sale_stats(
        position,
        return_net=return_net,
    )
    return {
        "date": trade_date,
        "action": "sell",
        "exit_stage": exit_stage,
        "stock_code": position.stock_code,
        "stock_name": position.stock_name,
        "signal_kind": position.signal_kind,
        "candidate_rank": position.candidate_rank,
        "market_state": position.market_state,
        "amount": round(proceeds, 6),
        "target_weight": round(position.target_weight, 6),
        "return_net": round(return_net, 6),
        "sizing": position.sizing,
        "risk_per_trade": position.risk_per_trade,
        "risk_budget_loss": _round_optional(risk_budget_loss),
        "risk_budget_planned": _round_optional(risk_budget_planned),
        "risk_budget_hit": risk_budget_hit,
        "entry_style": position.entry_style,
        "probe_confirmed": position.probe_confirmed,
    }


def _probe_pyramid_trade_metrics(
    trades: Sequence[Mapping[str, object]],
    *,
    enabled: bool,
) -> dict[str, object]:
    if not enabled:
        return {
            "probe_failed_avg_return": None,
            "probe_failed_avg_loss": None,
            "probe_confirmed_avg_return": None,
            "probe_confirmed_median_return": None,
            "probe_confirmed_win_rate": None,
        }
    failed_returns = [
        float(row["return_net"])
        for row in trades
        if row.get("action") == "sell"
        and row.get("exit_stage") == "probe_failed_exit"
        and row.get("return_net") is not None
    ]
    confirmed_returns = [
        float(row["return_net"])
        for row in trades
        if row.get("action") == "sell"
        and row.get("entry_style") == "probe_pyramid"
        and bool(row.get("probe_confirmed"))
        and row.get("return_net") is not None
    ]
    return {
        "probe_failed_avg_return": _round_optional(statistics.fmean(failed_returns) if failed_returns else None),
        "probe_failed_avg_loss": _round_optional(
            statistics.fmean(max(-value, 0.0) for value in failed_returns) if failed_returns else None
        ),
        "probe_confirmed_avg_return": _round_optional(
            statistics.fmean(confirmed_returns) if confirmed_returns else None
        ),
        "probe_confirmed_median_return": _round_optional(
            statistics.median(confirmed_returns) if confirmed_returns else None
        ),
        "probe_confirmed_win_rate": _round_optional(
            sum(1 for value in confirmed_returns if value > 0) / len(confirmed_returns)
            if confirmed_returns
            else None
        ),
    }


def _add_position_lot(position: _Position, *, amount: float, entry_price: float) -> _Position:
    lots = position.lots + (_Lot(amount=amount, entry_price=entry_price),)
    total_amount = position.amount + amount
    target_weight = position.target_weight
    if position.probe_fraction is not None and position.probe_fraction > 0:
        target_weight = position.target_weight / position.probe_fraction
    risk_budget_planned = (
        target_weight * position.stop_distance_pct
        if position.sizing == "risk_budget" and position.stop_distance_pct is not None
        else position.risk_budget_planned
    )
    return_net = position.return_net
    if position.exit_price is not None and position.exit_price > 0 and total_amount > 0:
        return_net = sum(_lot_exit_proceeds(lot, exit_price=position.exit_price) for lot in lots) / total_amount - 1.0
    return replace(
        position,
        amount=total_amount,
        entry_price=_weighted_lot_entry_price(lots, fallback=position.entry_price),
        lots=lots,
        target_weight=target_weight,
        risk_budget_planned=risk_budget_planned,
        return_net=return_net,
        probe_confirmed=True,
    )


def _weighted_lot_entry_price(
    lots: Sequence[_Lot],
    *,
    fallback: float | None,
) -> float | None:
    total_amount = sum(lot.amount for lot in lots)
    total_shares = sum(lot.amount / lot.entry_price for lot in lots if lot.entry_price > 0)
    if total_amount > 0 and total_shares > 0:
        return total_amount / total_shares
    return fallback


def _probe_event_for_open(position: _Position, trade_date: str) -> dict[str, object] | None:
    if position.entry_style != "probe_pyramid" or position.probe_confirmed:
        return None
    if position.signal_high is None or position.confirm_days is None:
        return None
    rows = position.path_rows
    entry_index = _path_row_index(rows, position.entry_date)
    open_index = _path_row_index(rows, trade_date)
    if entry_index is None or open_index is None:
        return None

    confirm_end = min(entry_index + position.confirm_days, len(rows))
    for index in range(entry_index, confirm_end):
        close_price = path_mark_price(rows[index])
        if close_price is None or close_price <= position.signal_high:
            continue
        add_index = index + 1
        if add_index == open_index:
            add_price = _path_open_price(rows[open_index])
            return {"event": "confirm", "price": add_price} if add_price is not None else None
        return None

    fail_index = entry_index + position.confirm_days
    if fail_index == open_index:
        fail_price = _path_open_price(rows[open_index])
        return {"event": "fail", "price": fail_price} if fail_price is not None else None
    return None


def _path_row_index(rows: Sequence[Mapping[str, object]], trade_date: str) -> int | None:
    if isinstance(rows, _IndexedPathRows):
        return rows.row_index(trade_date)
    for index, row in enumerate(rows):
        if _date_text(row.get("trade_date") or row.get("date")) == trade_date:
            return index
    return None


def _path_open_price(row: Mapping[str, object]) -> float | None:
    return path_entry_price(row, fallback=None)


def _price_paths_by_key(
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, _IndexedPathRows]:
    return {
        str(key): _IndexedPathRows(
            sorted(rows, key=lambda row: _date_text(row.get("trade_date") or row.get("date")))
        )
        for key, rows in price_paths.items()
    }


def _path_exit(
    rows: Sequence[Mapping[str, object]],
    *,
    horizon: str,
    entry_price: float | None,
) -> dict[str, object] | None:
    horizon_days = _horizon_days(horizon)
    if horizon_days is None:
        return None
    return calculate_path_horizon_exit(
        rows,
        horizon_days=horizon_days,
        entry_price=entry_price,
        buy_cost_rate=POLICY.buy_cost_rate,
        sell_cost_rate=POLICY.sell_cost_rate,
        slippage_rate=POLICY.slippage_rate,
    )


def _invested_value(positions: Sequence[_Position], trade_date: str, *, mode: str) -> float:
    return sum(_position_value(position, trade_date, mode=mode) for position in positions)


def _position_value(position: _Position, trade_date: str, *, mode: str) -> float:
    if mode != "path":
        return position.amount
    mark = _path_mark_for_date(position.path_rows, trade_date)
    if mark is None or mark <= 0:
        return position.amount
    if position.lots:
        return sum(
            lot.amount * mark / lot.entry_price if lot.entry_price > 0 else lot.amount
            for lot in position.lots
        )
    entry = position.entry_price
    if entry is None or entry <= 0:
        return position.amount
    return position.amount * mark / entry


def _position_uses_cost_mark(position: _Position, trade_date: str, *, mode: str) -> bool:
    if mode != "path":
        return False
    mark = _path_mark_for_date(position.path_rows, trade_date)
    return mark is None or mark <= 0


def _position_exit_uses_cost_fallback(
    position: _Position,
    *,
    mode: str,
    exit_price: float | None = None,
) -> bool:
    if mode != "path":
        return False
    if not position.lots:
        return True
    price = exit_price if exit_price is not None else position.exit_price
    return price is None or price <= 0


def _risk_metrics_warning(
    mode: str,
    *,
    mtm_cost_fallback_position_days: int,
    mtm_position_days: int,
    mtm_cost_fallback_exit_trades: int,
) -> str | None:
    if mode != "path":
        return HORIZON_REALIZED_ONLY_WARNING
    if mtm_cost_fallback_position_days <= 0 and mtm_cost_fallback_exit_trades <= 0:
        return None
    return (
        "path 模式标记为 mark_to_market，但存在缺少可用盯市价格的成本计价回退："
        f"{mtm_cost_fallback_position_days}/{mtm_position_days} 个持仓-日按成本计价，"
        f"{mtm_cost_fallback_exit_trades} 笔 path 退出按成本/既有收益口径结算；"
        "相关风险指标为降级盯市口径。"
    )


def _path_mark_for_date(rows: Sequence[Mapping[str, object]], trade_date: str) -> float | None:
    if isinstance(rows, _IndexedPathRows):
        return rows.mark_for_date(trade_date)
    mark: float | None = None
    for row in rows:
        date_key = _date_text(row.get("trade_date") or row.get("date"))
        if not date_key or date_key > trade_date:
            break
        candidate = path_mark_price(row)
        if candidate is not None:
            mark = candidate
    return mark


def _horizon_days(horizon: str) -> int | None:
    if not horizon.endswith("d"):
        return None
    return _safe_int(horizon[:-1], default=0) or None


def _max_drawdown(values: Sequence[float]) -> float | None:
    if not values:
        return None
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, 1.0 - value / peak)
    return max_drawdown


def _sharpe(returns: Sequence[float], *, periods_per_year: float | None = None) -> float | None:
    """按估计步频年化的 Sharpe。

    ``periods_per_year`` = 步数 × (365/日历跨度)，即每年经历的曲线步数估计；
    稀疏序列下固定 sqrt(252) 会系统性放大结果（2026-08 审计 MAC-02）。
    无法估计年化基准时返回 ``None`` 而不是给出不可比的数字。
    """
    if len(returns) < 2 or periods_per_year is None or periods_per_year <= 0:
        return None
    stdev = statistics.stdev(returns)
    if stdev <= 0:
        return None
    return statistics.fmean(returns) / stdev * math.sqrt(periods_per_year)


def _first_float(*values: object) -> float | None:
    for value in values:
        coerced = _safe_float(value)
        if coerced is not None:
            return coerced
    return None


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _safe_int(value: object, *, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return default


def _round_optional(value: float | None) -> float | None:
    return round(value, 6) if value is not None and math.isfinite(value) else None


def _date_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text[:10]


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
