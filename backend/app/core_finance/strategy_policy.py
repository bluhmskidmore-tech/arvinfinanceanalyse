from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

POLICY_VERSION = "sp_v1"


@dataclass(frozen=True)
class StockCandidatePolicyDefinition:
    name: str
    active_market_states: frozenset[str]
    close_strength_min: float
    gap_norm_max: float
    abnormal_turnover_min: float
    abnormal_turnover_max: float
    close_strength_first: bool = False
    #: 异常换手上界的开闭：True 表示闭区间（<= max），False 表示开区间（< max）。
    #: 下界始终为闭区间（>= min）。
    abnormal_turnover_max_inclusive: bool = True


@dataclass(frozen=True)
class EntryFilterPolicy:
    min_history: int
    ema_window: int
    max_ranked: int
    min_daily_amount: float
    close_strength_min: float
    abnormal_turnover_range: tuple[float, float]
    gap_norm_min: float
    max_breakout_extension_norm: float
    crowded_leader_turnover_block: float
    default_fundamental_top_fraction: float
    warm_fundamental_top_fraction: float
    stock_candidate_policies: tuple[StockCandidatePolicyDefinition, ...]


@dataclass(frozen=True)
class RiskExitPolicy:
    ema_window: int
    volume_ma_window: int
    volume_confirmation_ratio: float
    min_history: int


@dataclass(frozen=True)
class MonitoringThresholds:
    factor_screen_primary_coverage_threshold: float
    factor_screen_partial_coverage_threshold: float
    factor_screen_freshness_threshold_days: int
    # v3 流动性治理：候选近 20 日均成交额通过率低于该阈值时，factor_screen
    # 降级为观察名单（服务层 _factor_screen_degradation_reasons 消费）。
    factor_screen_liquidity_pass_threshold: float


@dataclass(frozen=True)
class BacktestVariantPolicy:
    risk_budget_risk_per_trade_grid: tuple[float, ...]
    risk_budget_single_name_cap: float
    risk_budget_fallback_stop_distance_pct: float
    probe_fraction: float
    probe_confirm_days_grid: tuple[int, ...]
    max_entry_premium_grid: tuple[float | None, ...]
    vol_target_grid: tuple[float, ...]
    vol_target_window: int


@dataclass(frozen=True)
class SizingPolicy:
    """正式化的实时建议仓位政策（risk_budget sizing，stock_candidate 先行）。

    与回测引擎 `portfolio_backtest` 的 risk_budget 变体同款公式：
    raw_weight = min(risk_per_trade / stop_distance_pct, single_name_cap)。
    hint 是单票权重上限建议；实盘串联 gate 敞口预算截断由引擎语义约定，
    实时提示不做敞口截断计算。评估依据见 tmp-strategy-reports/risk-budget-promotion.md。
    """

    policy_version: str
    sizing_mode: str
    risk_per_trade: float
    single_name_cap: float
    fallback_stop_distance_pct: float
    stop_basis: str
    applies_to: tuple[str, ...]


@dataclass(frozen=True)
class StrategyPolicy:
    entry_observation_states: frozenset[str]
    mean_reversion_active_states: frozenset[str]
    hybrid_fusion_active_states: frozenset[str]
    factor_screen_active_states: frozenset[str]
    exposure_by_market_state: Mapping[str, tuple[float, ...]]
    macro_multipliers: Mapping[str, float]
    buy_cost_rate: float
    sell_cost_rate: float
    slippage_rate: float
    risk_exit: RiskExitPolicy
    entry_filters: EntryFilterPolicy
    monitoring_thresholds: MonitoringThresholds
    backtest_variants: BacktestVariantPolicy
    sizing: SizingPolicy


_STOCK_CANDIDATE_POLICIES = (
    StockCandidatePolicyDefinition(
        name="default",
        active_market_states=frozenset({"WARM", "HOT", "OVERHEAT"}),
        close_strength_min=0.95,
        gap_norm_max=0.45,
        abnormal_turnover_min=1.2,
        abnormal_turnover_max=2.0,
        # v7 主档历史口径为开区间上界（< 2.0），显式声明以保持行为不变。
        abnormal_turnover_max_inclusive=False,
    ),
    StockCandidatePolicyDefinition(
        name="exp3b",
        active_market_states=frozenset({"WARM", "HOT"}),
        close_strength_min=0.99,
        gap_norm_max=0.35,
        abnormal_turnover_min=1.2,
        abnormal_turnover_max=2.4,
        close_strength_first=True,
    ),
    StockCandidatePolicyDefinition(
        name="exp3c_shadow",
        active_market_states=frozenset({"WARM", "HOT"}),
        close_strength_min=0.99,
        gap_norm_max=0.35,
        abnormal_turnover_min=1.0,
        abnormal_turnover_max=2.4,
        close_strength_first=True,
    ),
    StockCandidatePolicyDefinition(
        name="v6_compat",
        active_market_states=frozenset({"WARM", "HOT", "OVERHEAT"}),
        close_strength_min=0.95,
        gap_norm_max=0.45,
        abnormal_turnover_min=1.0,
        abnormal_turnover_max=3.5,
    ),
)


POLICY = StrategyPolicy(
    entry_observation_states=frozenset({"WARM", "HOT"}),
    mean_reversion_active_states=frozenset({"WARM"}),
    hybrid_fusion_active_states=frozenset({"WARM", "HOT"}),
    factor_screen_active_states=frozenset({"WARM", "HOT", "OVERHEAT"}),
    exposure_by_market_state=MappingProxyType(
        {
            "NO_DATA": (0.0,),
            "STALE": (0.0,),
            "PENDING_DATA": (0.0,),
            "OFF": (0.0, 0.25),
            "WARM": (0.25, 0.5, 0.75),
            "HOT": (0.75,),
            "OVERHEAT": (1.0,),
        }
    ),
    macro_multipliers=MappingProxyType(
        {
            "supportive": 1.0,
            "neutral": 0.5,
            "restrictive": 0.0,
            "unknown": 0.0,
        }
    ),
    buy_cost_rate=0.0008,
    sell_cost_rate=0.0013,
    slippage_rate=0.0010,
    risk_exit=RiskExitPolicy(
        ema_window=10,
        volume_ma_window=20,
        volume_confirmation_ratio=1.3,
        min_history=21,
    ),
    entry_filters=EntryFilterPolicy(
        min_history=120,
        ema_window=10,
        max_ranked=6,
        min_daily_amount=200_000_000.0,
        close_strength_min=0.95,
        abnormal_turnover_range=(1.2, 2.0),
        gap_norm_min=0.0,
        max_breakout_extension_norm=0.35,
        crowded_leader_turnover_block=2.0,
        default_fundamental_top_fraction=0.5,
        warm_fundamental_top_fraction=1 / 3,
        stock_candidate_policies=_STOCK_CANDIDATE_POLICIES,
    ),
    monitoring_thresholds=MonitoringThresholds(
        factor_screen_primary_coverage_threshold=0.8,
        factor_screen_partial_coverage_threshold=0.5,
        factor_screen_freshness_threshold_days=3,
        factor_screen_liquidity_pass_threshold=0.95,
    ),
    backtest_variants=BacktestVariantPolicy(
        risk_budget_risk_per_trade_grid=(0.005, 0.010),
        risk_budget_single_name_cap=0.25,
        risk_budget_fallback_stop_distance_pct=0.08,
        probe_fraction=0.5,
        probe_confirm_days_grid=(3, 5),
        max_entry_premium_grid=(0.02, 0.03, None),
        vol_target_grid=(0.15, 0.20),
        vol_target_window=20,
    ),
    sizing=SizingPolicy(
        policy_version="sizing_rb_v1_stock_candidate",
        sizing_mode="risk_budget",
        risk_per_trade=0.005,
        single_name_cap=0.25,
        fallback_stop_distance_pct=0.08,
        stop_basis="ema10_stop_ref",
        applies_to=("stock_candidate",),
    ),
)
