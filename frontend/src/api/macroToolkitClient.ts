import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { readHttpJsonDetail } from "./httpResponseError";
import type { ApiEnvelope } from "./contracts";

type FetchLike = typeof fetch;

type MacroToolkitClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

const MACRO_TOOLKIT_READ_TIMEOUT_MS = 90_000;

export type MacroToolkitScriptRecord = {
  name: string;
  filename: string;
  group: string;
  default_data_sources: string[];
  optional_dependencies: string[];
  notes: string;
  path: string;
  available: boolean;
};

export type MacroToolkitOutputFile = {
  name: string;
  path: string;
  size_bytes: number;
  modified_at: string;
};

export type MacroToolkitSourceCheck = {
  alias: string;
  row_count: number;
  latest: null | {
    date: string;
    series_id: string;
    vendor_name: string;
    value: number;
  };
};

export type MacroToolkitCapability = {
  key: string;
  legacy_module: string;
  label: string;
  group: string;
  implementation_status: string;
  route_status: string;
  frontend_status: string;
  data_status: string;
  data_hit_count: number;
  data_required_count: number;
  evidence: Array<{
    alias: string;
    row_count: number;
    latest_date: string | null;
    series_id: string | null;
  }>;
  next_step: string;
};

export type MacroToolkitCffexMemberRankStatus = {
  materialized: boolean;
  status: string;
  row_count: number;
  latest_trade_date: string | null;
  contracts: string[];
  source_vendors: string[];
  freshness_status?: string;
  reference_date?: string | null;
  stale_days?: number | null;
};

export type MacroToolkitChoiceStockRefreshPermission = {
  mode: "identity_only" | string;
  allowed?: boolean;
  user_id?: string | null;
  role?: string | null;
  identity_source?: string | null;
  resource?: string;
  actions?: string[];
};

export type MacroToolkitChoiceStockRefreshRun = {
  status: string;
  run_id?: string;
  job_name?: string;
  cache_key?: string;
  trigger_mode?: "idle" | "async" | "terminal" | string;
  report_date?: string;
  error_message?: string | null;
  failure_category?: string | null;
  failure_reason?: string | null;
  history_row_count?: number | null;
  factor_row_count?: number | null;
  source_version?: string;
  vendor_version?: string | null;
  refresh_history?: boolean;
  refresh_factors?: boolean;
  factor_max_stock_count?: number | null;
  permission?: MacroToolkitChoiceStockRefreshPermission;
};

export type MacroToolkitChoiceStockTableStatus = {
  materialized: boolean;
  status: string;
  row_count: number;
  stock_count: number;
  trade_date_count?: number;
  latest_trade_date?: string | null;
  as_of_date?: string | null;
};

export type MacroToolkitChoiceStockRefreshStatus = {
  permission: MacroToolkitChoiceStockRefreshPermission;
  refresh?: MacroToolkitChoiceStockRefreshRun;
  daily_observation?: MacroToolkitChoiceStockTableStatus;
  factor_snapshot?: MacroToolkitChoiceStockTableStatus;
  default_factor_max_stock_count?: number | null;
};

export type MacroToolkitChoiceStockRefreshResponse = ApiEnvelope<{
  refresh: MacroToolkitChoiceStockRefreshRun;
  choice_stock_refresh: MacroToolkitChoiceStockRefreshStatus;
}>;

export type MacroToolkitPayload = {
  default_data_sources: string[];
  toolkit_root: string;
  output_dir: string;
  scripts: MacroToolkitScriptRecord[];
  groups: string[];
  omitted_scripts: Record<string, string>;
  output_files: MacroToolkitOutputFile[];
  source_checks: MacroToolkitSourceCheck[];
  capabilities: MacroToolkitCapability[];
  cffex_member_rank?: MacroToolkitCffexMemberRankStatus;
  choice_stock_refresh?: MacroToolkitChoiceStockRefreshStatus;
  warnings: string[];
};

export type MacroToolkitIndicator = {
  key: string;
  alias: string;
  label: string;
  group: string;
  unit: string;
  row_count: number;
  latest_date: string | null;
  latest_value: number | null;
  previous_value: number | null;
  change: number | null;
  change_pct: number | null;
  source: string | null;
  series_id: string | null;
  quality: "ok" | "missing";
};

export type MacroToolkitSignalCard = {
  key: string;
  title: string;
  stance: string;
  tone: "positive" | "neutral" | "negative" | "missing";
  score: number | null;
  evidence: string[];
};

export type MacroToolkitInputEvidence = {
  inputs?: Array<{
    field: string;
    label: string;
    aliases?: string[];
    warning?: string;
    required?: boolean;
    available?: boolean;
    row_count?: number;
    latest_date?: string | null;
    series_id?: string | null;
    source?: string | null;
    value?: number | null;
  }>;
  missing_inputs?: string[];
  sources?: string[];
  latest_dates?: string[];
};

export type MacroToolkitCapabilityResult = {
  key: string;
  legacy_module: string;
  label: string;
  group: string;
  status: "complete" | "degraded" | "unavailable";
  tone: MacroToolkitSignalCard["tone"];
  score: number | null;
  headline: string;
  primary_metric: {
    label: string;
    value: string | number;
    unit: string;
  } | null;
  input_evidence?: MacroToolkitInputEvidence | null;
  evidence: string[];
  warnings: string[];
  result: Record<string, unknown> & {
    input_evidence?: MacroToolkitInputEvidence | null;
  };
};

export type MacroToolkitStrategySummary = {
  key: string;
  label: string;
  group: string;
  status: "sample_only" | "complete" | "degraded" | "unavailable";
  tone: MacroToolkitSignalCard["tone"];
  primary_metric: {
    label: string;
    value: string | number;
    unit: string;
  } | null;
  evidence: string[];
  warnings: string[];
  result: Record<string, unknown>;
};

export type MacroToolkitAShareRiskPayload = {
  trade_date: string | null;
  status: "complete" | "degraded" | "unavailable";
  risk_score: number | null;
  risk_level: "green" | "yellow" | "orange" | "red" | "unknown";
  risk_name: string;
  summary: string;
  position_rule: string;
  metrics: Record<string, number | null>;
  triggered_rules: string[];
  watch_next: string[];
  warnings: string[];
  tables_used: string[];
};

export type MacroToolkitRuntimeStatusPayload = {
  analysis_scope: "core" | "full" | string;
  deferred_sections: Array<{
    key: string;
    label: string;
    status: "deferred" | "loading" | "complete" | "failed" | string;
  }>;
};

export type MacroToolkitAnalysisPayload = {
  default_data_sources: string[];
  as_of_date: string | null;
  conclusion: {
    stance: string;
    tone: "positive" | "neutral" | "negative" | "missing";
    summary: string;
    recommended_action: string;
  };
  coverage: {
    indicator_count: number;
    hit_count: number;
    hit_rate: number;
    script_count: number;
    output_file_count: number;
  };
  indicators: MacroToolkitIndicator[];
  signal_cards: MacroToolkitSignalCard[];
  a_share_risk?: MacroToolkitAShareRiskPayload;
  capability_results: MacroToolkitCapabilityResult[];
  strategy_summaries: MacroToolkitStrategySummary[];
  output_files: MacroToolkitOutputFile[];
  source_checks: MacroToolkitSourceCheck[];
  capabilities: MacroToolkitCapability[];
  cffex_member_rank?: MacroToolkitPayload["cffex_member_rank"];
  choice_stock_refresh?: MacroToolkitChoiceStockRefreshStatus;
  runtime_status?: MacroToolkitRuntimeStatusPayload;
  warnings: string[];
};

export type MacroToolkitStrategySummariesPayload = {
  strategy_summaries: MacroToolkitStrategySummary[];
  choice_stock_refresh?: MacroToolkitChoiceStockRefreshStatus;
};

export type MacroToolkitRunResponse = {
  status: "completed" | "failed" | "timeout";
  script: MacroToolkitScriptRecord;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  output_files: MacroToolkitOutputFile[];
  message?: string;
};

export type MacroToolkitCffexRefreshResponse = ApiEnvelope<{
  refresh: Record<string, unknown>;
  cffex_member_rank: MacroToolkitCffexMemberRankStatus;
}>;

export type MacroToolkitClientMethods = {
  getMacroToolkitAnalysis: () => Promise<ApiEnvelope<MacroToolkitAnalysisPayload>>;
  getMacroToolkitStrategySummaries: () => Promise<ApiEnvelope<MacroToolkitStrategySummariesPayload>>;
  getMacroToolkitScripts: () => Promise<ApiEnvelope<MacroToolkitPayload>>;
  runMacroToolkitScript: (
    name: string,
    options?: { timeoutSeconds?: number; argv?: string[] },
  ) => Promise<MacroToolkitRunResponse>;
  refreshCffexMemberRank: (options?: {
    tradeDate?: string;
    contracts?: string[];
    sources?: string[];
  }) => Promise<MacroToolkitCffexRefreshResponse>;
  refreshChoiceStock: (options?: {
    asOfDate?: string;
    refreshHistory?: boolean;
    refreshFactors?: boolean;
    factorMaxStockCount?: number | null;
  }) => Promise<MacroToolkitChoiceStockRefreshResponse>;
  getChoiceStockRefreshStatus: (runId: string) => Promise<MacroToolkitChoiceStockRefreshResponse>;
};

const MOCK_CAPABILITY_RESULTS: MacroToolkitCapabilityResult[] = [
  {
    key: "monetary_policy_stance",
    legacy_module: "M7",
    label: "货币政策立场",
    group: "政策与资金面",
    status: "degraded",
    tone: "neutral",
    score: 56,
    headline: "资金面偏平衡，政策立场暂不形成单边信号。",
    primary_metric: { label: "立场得分", value: 56, unit: "" },
    evidence: ["DR007=1.82%", "10Y-1Y=34bp"],
    warnings: [],
    input_evidence: {
      inputs: [
        {
          field: "policy_rate_7d",
          label: "Policy rate 7D",
          aliases: ["M0041653"],
          warning: "POLICY_RATE_7D_MISSING",
          required: true,
          available: true,
          row_count: 1,
          latest_date: "2026-04-10",
          series_id: "M001",
          source: "choice",
          value: 1.75,
        },
        {
          field: "dr007",
          label: "DR007",
          aliases: ["DR007.IB"],
          warning: "DR007_MISSING",
          required: true,
          available: true,
          row_count: 1,
          latest_date: "2026-04-10",
          series_id: "CA.DR007",
          source: "choice",
          value: 1.82,
        },
      ],
      missing_inputs: [],
      sources: ["choice"],
      latest_dates: ["2026-04-10"],
    },
    result: {
      data_status: "degraded",
      key_metrics: {
        policy_rate_curve_id: "CN_RRP",
        policy_rate_tenor: "7D",
        policy_rate_7d: 1.75,
        dr007: 1.82,
      },
      input_evidence: {
        missing_inputs: [],
        sources: ["choice"],
        latest_dates: ["2026-04-10"],
      },
    },
  },
  {
    key: "leading_indicator",
    legacy_module: "M10",
    label: "宏观领先指标",
    group: "增长与通胀",
    status: "degraded",
    tone: "neutral",
    score: 51,
    headline: "领先指标位于中性区间，部分输入待补齐。",
    primary_metric: { label: "LEI", value: 51, unit: "" },
    evidence: ["LEI=51", "trend=flat"],
    warnings: ["PMI_MISSING", "M2_YOY_MISSING"],
    input_evidence: {
      inputs: [
        {
          field: "pmi",
          label: "PMI",
          aliases: ["M0017126"],
          warning: "PMI_MISSING",
          required: true,
          available: false,
          row_count: 0,
          latest_date: null,
          series_id: null,
          source: null,
          value: null,
        },
        {
          field: "m2_yoy",
          label: "M2 YoY",
          aliases: ["M0001385"],
          warning: "M2_YOY_MISSING",
          required: true,
          available: false,
          row_count: 0,
          latest_date: null,
          series_id: null,
          source: null,
          value: null,
        },
        {
          field: "social_financing_yoy",
          label: "Social financing YoY",
          aliases: ["M5525763"],
          warning: "SOCIAL_FINANCING_YOY_MISSING",
          required: true,
          available: true,
          row_count: 1,
          latest_date: "2026-02-01",
          series_id: "EMM00191807",
          source: "choice",
          value: 8.944901,
        },
      ],
      missing_inputs: ["PMI_MISSING", "M2_YOY_MISSING"],
      sources: ["choice", "fred", "moss_derived"],
      latest_dates: ["2026-02-01", "2026-04-10", "2026-04-27", "2026-04-30"],
    },
    result: {
      data_status: "degraded",
      input_evidence: {
        missing_inputs: ["PMI_MISSING", "M2_YOY_MISSING"],
        sources: ["choice", "fred", "moss_derived"],
        latest_dates: ["2026-02-01", "2026-04-10", "2026-04-27", "2026-04-30"],
      },
    },
  },
  {
    key: "economic_cycle",
    legacy_module: "M14",
    label: "经济周期定位",
    group: "增长与通胀",
    status: "degraded",
    tone: "neutral",
    score: 47,
    headline: "周期定位证据不足，需补齐增长与社融输入。",
    primary_metric: { label: "增长得分", value: 47, unit: "" },
    evidence: ["growth=47", "inflation=32"],
    warnings: ["PMI_MISSING", "PPI_YOY_MISSING", "M2_YOY_MISSING"],
    input_evidence: {
      inputs: [
        {
          field: "pmi",
          label: "PMI",
          aliases: ["M0017126"],
          warning: "PMI_MISSING",
          required: true,
          available: false,
          row_count: 0,
          latest_date: null,
          series_id: null,
          source: null,
          value: null,
        },
        {
          field: "cpi_yoy",
          label: "CPI YoY",
          aliases: ["M0000612"],
          warning: "CPI_YOY_MISSING",
          required: true,
          available: true,
          row_count: 507,
          latest_date: "2026-03-01",
          series_id: "EMM00072301",
          source: "choice",
          value: 1,
        },
        {
          field: "ppi_yoy",
          label: "PPI YoY",
          aliases: ["M0001227"],
          warning: "PPI_YOY_MISSING",
          required: true,
          available: false,
          row_count: 0,
          latest_date: null,
          series_id: null,
          source: null,
          value: null,
        },
      ],
      missing_inputs: ["PMI_MISSING", "PPI_YOY_MISSING", "M2_YOY_MISSING"],
      sources: ["choice"],
      latest_dates: ["2026-02-01", "2026-03-01"],
    },
    result: {
      data_status: "degraded",
      input_evidence: {
        missing_inputs: ["PMI_MISSING", "PPI_YOY_MISSING", "M2_YOY_MISSING"],
        sources: ["choice"],
        latest_dates: ["2026-02-01", "2026-03-01"],
      },
    },
  },
  {
    key: "decision_summary",
    legacy_module: "M16",
    label: "宏观决策摘要",
    group: "决策摘要",
    status: "degraded",
    tone: "neutral",
    score: 50,
    headline: "宏观信号分化，维持中性观察。",
    primary_metric: { label: "可用模块", value: 6, unit: "/9" },
    evidence: ["M7 资金面偏平衡", "M10 LEI 处于中性区间"],
    warnings: ["部分模块数据降级或不可用"],
    result: { data_status: "degraded" },
  },
];

const MOCK_STRATEGY_SUMMARIES: MacroToolkitStrategySummary[] = [
  {
    key: "moving_average",
    label: "移动均线策略",
    group: "A股策略",
    status: "sample_only",
    tone: "neutral",
    primary_metric: { label: "样例累计净值", value: 1.0832, unit: "" },
    evidence: ["短均线上穿长均线时建仓。", "合成价格样本 180 个观察点。"],
    warnings: ["SYNTHETIC_SAMPLE_ONLY"],
    result: { data_status: "sample_only" },
  },
  {
    key: "mean_reversion_momentum",
    label: "均值回归 + 动量",
    group: "A股策略",
    status: "sample_only",
    tone: "neutral",
    primary_metric: { label: "样例累计净值", value: 1.0148, unit: "" },
    evidence: ["价格偏离需同时满足趋势过滤。", "合成价格样本 180 个观察点。"],
    warnings: ["SYNTHETIC_SAMPLE_ONLY"],
    result: { data_status: "sample_only" },
  },
  {
    key: "multi_factor_selection",
    label: "多因子选股",
    group: "A股策略",
    status: "sample_only",
    tone: "neutral",
    primary_metric: { label: "样例入选数量", value: 1, unit: "" },
    evidence: ["价值、质量、动量、低波和股息因子加权排序。", "样例池 4 只。"],
    warnings: ["SYNTHETIC_SAMPLE_ONLY"],
    result: { data_status: "sample_only", selected_symbols: ["AAA"] },
  },
  {
    key: "low_crowding_regime_multifactor",
    label: "低拥挤度择时多因子",
    group: "A股策略",
    status: "sample_only",
    tone: "neutral",
    primary_metric: { label: "样例目标仓位", value: 0.7, unit: "" },
    evidence: ["样例市场状态 weak_up。", "样例低拥挤多因子入选 1 只。"],
    warnings: ["SYNTHETIC_SAMPLE_ONLY"],
    result: {
      data_status: "sample_only",
      regime: "weak_up",
      target_position: 0.7,
      selected_symbols: ["AAA"],
    },
  },
];

const MOCK_CHOICE_STOCK_REFRESH: MacroToolkitChoiceStockRefreshStatus = {
  permission: {
    mode: "identity_only",
    allowed: true,
    resource: "choice_stock.refresh",
    actions: ["history", "factor_snapshot"],
  },
  refresh: {
    status: "idle",
    trigger_mode: "idle",
    permission: { mode: "identity_only", allowed: true },
  },
  daily_observation: {
    materialized: true,
    status: "ok",
    row_count: 64300,
    stock_count: 1000,
    trade_date_count: 260,
    latest_trade_date: "2026-04-30",
  },
  factor_snapshot: {
    materialized: true,
    status: "ok",
    row_count: 643,
    stock_count: 1000,
    as_of_date: "2026-04-30",
  },
  default_factor_max_stock_count: null,
};

const MOCK_A_SHARE_RISK: MacroToolkitAShareRiskPayload = {
  trade_date: "2026-04-30",
  status: "degraded",
  risk_score: 64,
  risk_level: "orange",
  risk_name: "橙色风险",
  summary: "市场踩踏风险升温：上涨家数低于700或上涨比例低于18% / 跌停家数超过50。",
  position_rule: "总仓位上限30%，高位主题只减不加，午后不做冲高追买。",
  metrics: {
    core_stock_count: 1000,
    up_count: 186,
    up_ratio: 0.186,
    drop_3_count: 338,
    drop_5_count: 96,
    limit_down_count: 56,
    near_down_count: 118,
    turnover_ratio_ma20: 1.42,
    index_drawdown_from_high: 0.018,
  },
  triggered_rules: ["上涨家数低于700或上涨比例低于18%", "跌停家数超过50", "指数从日内高点回落超过1.5%且收在低位"],
  watch_next: ["跌停家数是否收敛到30只以内", "上涨家数是否恢复到1500只以上", "午后是否再次放量下杀"],
  warnings: ["主题拥挤 V1 仅按可用行业证据降级计算。"],
  tables_used: ["choice_stock_daily_observation", "choice_stock_limit_quality", "choice_stock_factor_snapshot"],
};

const MOCK_ANALYSIS: MacroToolkitAnalysisPayload = {
  default_data_sources: ["choice", "tushare"],
  as_of_date: "2026-04-30",
  conclusion: {
    stance: "中性观察",
    tone: "neutral",
    summary: "风险资产和资金利率证据接近，当前适合观察数据延续性，而不是给出单边结论。",
    recommended_action: "优先运行 signal_aggregator / risk_monitor 形成交易层信号。",
  },
  coverage: {
    indicator_count: 8,
    hit_count: 7,
    hit_rate: 0.875,
    script_count: 24,
    output_file_count: 0,
  },
  indicators: [
    {
      key: "hs300",
      alias: "sh000300",
      label: "沪深300",
      group: "风险资产",
      unit: "点",
      row_count: 120,
      latest_date: "2026-04-30",
      latest_value: 4807.3069,
      previous_value: 4778.1201,
      change: 29.1868,
      change_pct: 0.6108,
      source: "tushare",
      series_id: "CA.CSI300",
      quality: "ok",
    },
    {
      key: "dr007",
      alias: "DR007.IB",
      label: "DR007",
      group: "流动性",
      unit: "%",
      row_count: 248,
      latest_date: "2026-04-30",
      latest_value: 1.82,
      previous_value: 1.89,
      change: -0.07,
      change_pct: -3.7037,
      source: "choice",
      series_id: "CA.DR007",
      quality: "ok",
    },
    {
      key: "aa_5y",
      alias: "S0059760",
      label: "5Y AA 信用债",
      group: "信用",
      unit: "%",
      row_count: 6,
      latest_date: "2026-04-30",
      latest_value: 2.91,
      previous_value: null,
      change: null,
      change_pct: null,
      source: "choice",
      series_id: "legacy.yield.choice.aa_credit.5Y",
      quality: "ok",
    },
  ],
  signal_cards: [
    {
      key: "a_share_stampede_risk",
      title: "市场踩踏风险",
      stance: "橙色风险",
      tone: "negative",
      score: 64,
      evidence: ["上涨家数低于700或上涨比例低于18%", "跌停家数超过50"],
    },
    {
      key: "liquidity",
      title: "流动性",
      stance: "偏松",
      tone: "positive",
      score: 78,
      evidence: ["DR007 1.82%"],
    },
    {
      key: "risk_appetite",
      title: "风险偏好",
      stance: "改善",
      tone: "positive",
      score: 72,
      evidence: ["沪深300 +0.61%"],
    },
    {
      key: "credit",
      title: "信用利差",
      stance: "中性",
      tone: "neutral",
      score: 55,
      evidence: ["AA-国债 5Y 57.0bp"],
    },
    {
      key: "outputs",
      title: "脚本产物",
      stance: "待生成",
      tone: "neutral",
      score: 45,
      evidence: ["尚未发现输出文件"],
    },
  ],
  a_share_risk: MOCK_A_SHARE_RISK,
  capability_results: MOCK_CAPABILITY_RESULTS,
  strategy_summaries: MOCK_STRATEGY_SUMMARIES,
  output_files: [],
  source_checks: [],
  capabilities: [],
  cffex_member_rank: {
    materialized: true,
    status: "ok",
    row_count: 80,
    latest_trade_date: "2026-04-30",
    contracts: ["T.CFE", "TF.CFE", "TL.CFE", "TS.CFE"],
    source_vendors: ["choice", "tushare"],
    freshness_status: "current",
    reference_date: "2026-04-30",
    stale_days: 0,
  },
  choice_stock_refresh: MOCK_CHOICE_STOCK_REFRESH,
  runtime_status: {
    analysis_scope: "full",
    deferred_sections: [],
  },
  warnings: [],
};

const MOCK_SCRIPTS: MacroToolkitScriptRecord[] = [
  {
    name: "equity_strategies",
    filename: "equity_strategies.py",
    group: "allocation",
    default_data_sources: ["choice", "tushare"],
    optional_dependencies: ["numpy", "pandas"],
    notes: "",
    path: "scripts/equity_strategies.py",
    available: true,
  },
  {
    name: "signal_aggregator",
    filename: "signal_aggregator.py",
    group: "macro_signal",
    default_data_sources: ["choice", "tushare"],
    optional_dependencies: ["pandas"],
    notes: "",
    path: "scripts/signal_aggregator.py",
    available: true,
  },
  {
    name: "merrill_clock_cn",
    filename: "merrill_clock_cn.py",
    group: "macro_signal",
    default_data_sources: ["choice", "tushare"],
    optional_dependencies: ["pandas"],
    notes: "",
    path: "scripts/merrill_clock_cn.py",
    available: true,
  },
  {
    name: "debug_wind",
    filename: "debug_wind.py",
    group: "diagnostic",
    default_data_sources: ["choice", "tushare"],
    optional_dependencies: [],
    notes: "",
    path: "scripts/debug_wind.py",
    available: true,
  },
];

const MOCK_CAPABILITIES: MacroToolkitCapability[] = [
  {
    key: "monetary_policy_stance",
    legacy_module: "M7",
    label: "货币政策立场",
    group: "政策与资金面",
    implementation_status: "library_ready",
    route_status: "not_wired",
    frontend_status: "planned",
    data_status: "ready",
    data_hit_count: 3,
    data_required_count: 3,
    evidence: [
      { alias: "DR007.IB", row_count: 248, latest_date: "2026-04-30", series_id: "CA.DR007" },
    ],
    next_step: "封装 /api/macro/monetary-policy-stance，并在本页接入政策立场卡。",
  },
  {
    key: "yield_curve_shape",
    legacy_module: "M8",
    label: "收益率曲线形态",
    group: "曲线",
    implementation_status: "partial",
    route_status: "partial",
    frontend_status: "partial",
    data_status: "partial",
    data_hit_count: 2,
    data_required_count: 3,
    evidence: [
      { alias: "S0059749", row_count: 122, latest_date: "2026-04-29", series_id: "E1000180" },
    ],
    next_step: "复用正式曲线表，把曲线形态纯函数输出接到宏观工具箱。",
  },
];

const MOCK_PAYLOAD: MacroToolkitPayload = {
  default_data_sources: ["choice", "tushare"],
  toolkit_root: "backend/app/core_finance/macro/toolkit",
  output_dir: "data/macro_toolkit/output",
  scripts: MOCK_SCRIPTS,
  groups: ["diagnostic", "macro_signal"],
  omitted_scripts: {
    "credit_bond_portfolio.py": "Source file has a syntax error in the provided toolkit copy.",
  },
  output_files: [],
  source_checks: [
    {
      alias: "sh000300",
      row_count: 120,
      latest: {
        date: "2026-04-30",
        series_id: "CA.CSI300",
        vendor_name: "tushare",
        value: 4807.3069,
      },
    },
    {
      alias: "M0067855",
      row_count: 851,
      latest: {
        date: "2026-04-30",
        series_id: "EMM00058124",
        vendor_name: "choice",
        value: 6.8628,
      },
    },
  ],
  capabilities: MOCK_CAPABILITIES,
  cffex_member_rank: {
    materialized: true,
    status: "ok",
    row_count: 80,
    latest_trade_date: "2026-04-30",
    contracts: ["T.CFE", "TF.CFE", "TL.CFE", "TS.CFE"],
    source_vendors: ["choice", "tushare"],
    freshness_status: "current",
    reference_date: "2026-04-30",
    stale_days: 0,
  },
  choice_stock_refresh: MOCK_CHOICE_STOCK_REFRESH,
  warnings: [],
};

export function createMockMacroToolkitClient(): MacroToolkitClientMethods {
  return {
    async getMacroToolkitAnalysis() {
      return buildMockApiEnvelope("macro_toolkit.analysis", MOCK_ANALYSIS, {
        basis: "analytical",
        formal_use_allowed: false,
        source_version: "macro_toolkit_mock",
        vendor_version: "choice+tushare",
        rule_version: "rv_macro_toolkit_ui_v1",
        cache_version: "none",
      });
    },
    async getMacroToolkitStrategySummaries() {
      return buildMockApiEnvelope(
        "macro_toolkit.analysis.strategy_summaries",
        {
          strategy_summaries: MOCK_STRATEGY_SUMMARIES,
          choice_stock_refresh: MOCK_CHOICE_STOCK_REFRESH,
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "macro_toolkit_mock",
          vendor_version: "choice+tushare",
          rule_version: "rv_macro_toolkit_ui_v1",
          cache_version: "none",
        },
      );
    },
    async getMacroToolkitScripts() {
      return buildMockApiEnvelope("macro_toolkit.scripts", MOCK_PAYLOAD, {
        basis: "analytical",
        formal_use_allowed: false,
        source_version: "macro_toolkit_mock",
        vendor_version: "choice+tushare",
        rule_version: "rv_macro_toolkit_ui_v1",
        cache_version: "none",
      });
    },
    async runMacroToolkitScript(name) {
      const script = MOCK_SCRIPTS.find((item) => item.name === name) ?? MOCK_SCRIPTS[0]!;
      return {
        status: "completed",
        script,
        exit_code: 0,
        stdout: `mock run completed: ${script.name}`,
        stderr: "",
        output_files: [],
      };
    },
    async refreshCffexMemberRank() {
      return buildMockApiEnvelope(
        "macro_toolkit.cffex_member_rank_refresh",
        {
          refresh: { row_count: 80 },
          cffex_member_rank: MOCK_PAYLOAD.cffex_member_rank!,
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "macro_toolkit_mock",
          vendor_version: "choice+tushare",
          rule_version: "rv_macro_toolkit_ui_v1",
          cache_version: "none",
        },
      );
    },
    async refreshChoiceStock() {
      return buildMockApiEnvelope(
        "macro_toolkit.choice_stock_refresh",
        {
          refresh: {
            status: "queued",
            run_id: "choice_stock_refresh:mock",
            trigger_mode: "async",
            permission: MOCK_CHOICE_STOCK_REFRESH.permission,
          },
          choice_stock_refresh: MOCK_CHOICE_STOCK_REFRESH,
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "macro_toolkit_mock",
          vendor_version: "choice+tushare",
          rule_version: "rv_macro_toolkit_ui_v1",
          cache_version: "none",
        },
      );
    },
    async getChoiceStockRefreshStatus() {
      return buildMockApiEnvelope(
        "macro_toolkit.choice_stock_refresh_status",
        {
          refresh: {
            status: "completed",
            run_id: "choice_stock_refresh:mock",
            trigger_mode: "terminal",
            history_row_count: MOCK_CHOICE_STOCK_REFRESH.daily_observation?.row_count ?? null,
            factor_row_count: MOCK_CHOICE_STOCK_REFRESH.factor_snapshot?.row_count ?? null,
            permission: MOCK_CHOICE_STOCK_REFRESH.permission,
          },
          choice_stock_refresh: MOCK_CHOICE_STOCK_REFRESH,
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "macro_toolkit_mock",
          vendor_version: "choice+tushare",
          rule_version: "rv_macro_toolkit_ui_v1",
          cache_version: "none",
        },
      );
    },
  };
}

export function createRealMacroToolkitClient({
  fetchImpl,
  baseUrl,
}: MacroToolkitClientFactoryOptions): MacroToolkitClientMethods {
  return {
    getMacroToolkitAnalysis: () =>
      requestJson<MacroToolkitAnalysisPayload>(fetchImpl, baseUrl, "/ui/macro/toolkit/analysis?detail=core"),
    getMacroToolkitStrategySummaries: () =>
      requestJson<MacroToolkitStrategySummariesPayload>(
        fetchImpl,
        baseUrl,
        "/ui/macro/toolkit/analysis/strategy-summaries",
      ),
    getMacroToolkitScripts: () =>
      requestJson<MacroToolkitPayload>(fetchImpl, baseUrl, "/ui/macro/toolkit/scripts"),
    runMacroToolkitScript: (name, options) =>
      requestActionJson<MacroToolkitRunResponse>(
        fetchImpl,
        baseUrl,
        `/ui/macro/toolkit/scripts/${encodeURIComponent(name)}/run`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            argv: options?.argv ?? [],
            timeout_seconds: options?.timeoutSeconds ?? 120,
          }),
        },
      ),
    refreshCffexMemberRank: (options) =>
      requestActionJson<MacroToolkitCffexRefreshResponse>(
        fetchImpl,
        baseUrl,
        "/ui/macro/toolkit/cffex-member-rank/refresh",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            trade_date: options?.tradeDate ?? null,
            contracts: options?.contracts ?? ["TS.CFE", "TF.CFE", "T.CFE", "TL.CFE"],
            sources: options?.sources ?? ["choice", "tushare"],
          }),
        },
      ),
    refreshChoiceStock: (options) =>
      requestActionJson<MacroToolkitChoiceStockRefreshResponse>(
        fetchImpl,
        baseUrl,
        "/ui/macro/toolkit/choice-stock/refresh",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            as_of_date: options?.asOfDate ?? null,
            refresh_history: options?.refreshHistory ?? true,
            refresh_factors: options?.refreshFactors ?? true,
            factor_max_stock_count: options?.factorMaxStockCount ?? null,
          }),
        },
      ),
    getChoiceStockRefreshStatus: (runId) =>
      requestJson<MacroToolkitChoiceStockRefreshResponse["result"]>(
        fetchImpl,
        baseUrl,
        `/ui/macro/toolkit/choice-stock/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
  };
}

async function requestJson<TData>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<TData>> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), MACRO_TOOLKIT_READ_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetchImpl(`${baseUrl}${path}`, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
  } catch (error) {
    const errorName =
      typeof error === "object" && error !== null && "name" in error
        ? (error as { name?: unknown }).name
        : undefined;
    if (errorName === "AbortError") {
      throw new Error(`Macro toolkit request timed out: ${path}`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<TData>;
}

async function requestActionJson<TResponse>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<TResponse> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as TResponse;
}
