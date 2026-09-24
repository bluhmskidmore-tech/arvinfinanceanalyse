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
class ThemeProxyDefinition:
    """theme_breakout 的题材代理篮子（proxy）定义。

    生产库当前没有题材 ETF/指数日线（fact_choice_macro_daily 仅 CSI300/CSI500
    收盘序列，choice_stock_daily_observation 仅覆盖股票代码），因此题材 proxy
    以申万一级(2021)行业成员股票篮子表达，与历史 semiconductor_proxy 同机制；
    ``proxy_code`` 记录篮子对应的申万一级行业代码（多行业以 ``+`` 连接），
    ``stock_name_keywords`` 为空表示整行业篮子，非空表示行业内名称关键词子集。
    """

    key: str
    #: 题材中文名，进入信号 theme_name 与历史行展示。
    name: str
    #: 篮子标的代码：申万一级行业代码，多行业用 "+" 连接。
    proxy_code: str
    parent_sector_codes: tuple[str, ...]
    parent_sector_names: tuple[str, ...]
    stock_name_keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class SizingPolicy:
    """正式化的实时建议仓位政策（等权为主参考，risk_budget 降为实验参考）。

    walk-forward 样本外验证（docs/strategy-reports/walk-forward-first-run.md）不支持
    固定 rpt=0.5% 的 risk_budget 优势，等权是更稳健的默认参考，因此 hint 的主参考
    口径由 ``primary_basis`` 声明（单一来源）：

    - 等权（主参考）：equal_weight = 当日门控敞口 / 候选数，与回测引擎
      `portfolio_backtest` 的 equal_weight 变体同语义（敞口直接进入权重）；
    - risk_budget（实验参考）：raw_weight = min(risk_per_trade / stop_distance_pct,
      single_name_cap)，仍为截断前单票权重上限，实盘串联 gate 敞口预算截断由
      引擎语义约定，实时提示不做敞口截断计算。
      历史评估见 docs/strategy-reports/risk-budget-promotion.md。
    """

    policy_version: str
    sizing_mode: str
    risk_per_trade: float
    single_name_cap: float
    fallback_stop_distance_pct: float
    stop_basis: str
    applies_to: tuple[str, ...]
    oos_validation_status: str = "not_supported_by_walk_forward"
    #: hint 主参考口径声明，前端主展示依此切换；risk_budget 输出保留为实验参考。
    primary_basis: str = "equal_weight"


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
    theme_proxies: tuple[ThemeProxyDefinition, ...]


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


# theme_breakout 多题材 proxy 池。成员数为 2026-08-12 审计日生产库口径
# （choice_stock_universe × choice_stock_sector_membership × choice_stock_daily_observation
# 内连接，快照/交易日 2026-08-11）。历史 Critical 问题：池内仅 semiconductor_proxy
# 一项，"题材突破"实际退化为单一半导体行业动量（docs/strategy-reports/
# theme-breakout-decay-review.md §8）。低空经济类题材因名称关键词仅命中 1 只、
# 且概念表非时点数据而未纳入。
_THEME_PROXY_POOL: tuple[ThemeProxyDefinition, ...] = (
    # 33 只。首项保持与 v5 semiconductor_proxy 完全同义（含旧代码 801080 与
    # 英文行业别名），保证 theme_key 历史连续。
    ThemeProxyDefinition(
        key="semiconductor_proxy",
        name="半导体",
        proxy_code="S270000",
        parent_sector_codes=("S270000", "801080"),
        parent_sector_names=("electronic", "electronics", "dianzi", "电子"),
        stock_name_keywords=(
            "semiconductor",
            "chip",
            "micro",
            "wafer",
            "ic",
            "半导体",
            "芯",
            "晶圆",
            "集成",
            "微电子",
        ),
    ),
    # 456 只（计算机 334 + 通信 122），覆盖服务器/软件/IDC/光模块算力链。
    ThemeProxyDefinition(
        key="ai_computing_proxy",
        name="算力AI",
        proxy_code="S710000+S730000",
        parent_sector_codes=("S710000", "S730000"),
        parent_sector_names=("computer", "telecom", "计算机", "通信"),
    ),
    # 63 只：机械设备行业内机器人/数控/激光/自动化名称子集。
    ThemeProxyDefinition(
        key="robotics_proxy",
        name="机器人与智能装备",
        proxy_code="S640000",
        parent_sector_codes=("S640000",),
        parent_sector_names=("machinery", "机械设备"),
        stock_name_keywords=(
            "robot",
            "automation",
            "机器人",
            "智能",
            "数控",
            "激光",
            "自动化",
            "减速",
            "伺服",
            "机床",
            "精工",
        ),
    ),
    # 138 只，整行业篮子。
    ThemeProxyDefinition(
        key="defense_proxy",
        name="国防军工",
        proxy_code="S650000",
        parent_sector_codes=("S650000",),
        parent_sector_names=("defense", "国防军工"),
    ),
    # 377 只（电池/光伏/风电/储能/电网设备），整行业篮子。
    ThemeProxyDefinition(
        key="new_energy_proxy",
        name="新能源",
        proxy_code="S630000",
        parent_sector_codes=("S630000",),
        parent_sector_names=("power equipment", "电力设备"),
    ),
    # 478 只，整行业篮子。
    ThemeProxyDefinition(
        key="pharma_proxy",
        name="医药",
        proxy_code="S370000",
        parent_sector_codes=("S370000",),
        parent_sector_names=("pharmaceutical", "医药生物"),
    ),
    # 35 只：非银金融行业内证券名称子集。
    ThemeProxyDefinition(
        key="broker_proxy",
        name="券商",
        proxy_code="S490000",
        parent_sector_codes=("S490000",),
        parent_sector_names=("non-bank financial", "非银金融"),
        stock_name_keywords=("securities", "证券"),
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
        # v2：主参考切换为等权（walk-forward 样本外不支持固定 rpt=0.5% 优势），
        # risk_budget 字段保留为实验参考。
        policy_version="sizing_eqw_v2_stock_candidate",
        sizing_mode="risk_budget",
        risk_per_trade=0.005,
        single_name_cap=0.25,
        fallback_stop_distance_pct=0.08,
        stop_basis="ema10_stop_ref",
        applies_to=("stock_candidate",),
        primary_basis="equal_weight",
    ),
    theme_proxies=_THEME_PROXY_POOL,
)
