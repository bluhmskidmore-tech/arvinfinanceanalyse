import { EM_DASH } from "../../../utils/format";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitIndicator,
  MacroToolkitAShareRiskPayload,
  MacroToolkitHasonStrategy,
  MacroToolkitShadowPortfolioReport,
  MacroToolkitStrategySummariesPayload,
} from "../../../api/macroToolkitClient";
import type {
  ModuleHomeDetailRow,
  ModuleHomeTone,
} from "./moduleHomeDetailTypes";
import { formatMacroSignalEvidence } from "./marketEvidenceVisual";
import { macroToolkitModuleTone } from "./marketDeskIntelModel";
import { formatRatioPct } from "../../pnl/pnlByBusinessPageModel";

function formatMacroToolkitPrimaryMetric(
  metric: { label: string; value: string | number; unit: string } | null,
): string {
  if (!metric) {
    return EM_DASH;
  }
  const unit = metric.unit ? ` ${metric.unit}` : "";
  return `${metric.value}${unit}`;
}

function pickMacroSignalChangeDetail(evidence: string[]): string | undefined {
  return evidence.find((line) => {
    const trimmed = line.trim();
    if (/^(?:score|regime|percentile)=/i.test(trimmed)) {
      return false;
    }
    return /bp|日变动|[+-]\d/.test(trimmed);
  });
}

export const MARKET_HOME_MACRO_SIGNAL_ORDER = [
  "crisis_score_cn",
  "liquidity",
  "credit",
  "risk_appetite",
  "a_share_stampede_risk",
] as const;

function marketHomeMacroSignalSortIndex(key: string): number {
  const index = MARKET_HOME_MACRO_SIGNAL_ORDER.indexOf(key as (typeof MARKET_HOME_MACRO_SIGNAL_ORDER)[number]);
  return index === -1 ? MARKET_HOME_MACRO_SIGNAL_ORDER.length : index;
}

export function buildMacroToolkitSignalRows(analysis: MacroToolkitAnalysisPayload): ModuleHomeDetailRow[] {
  return analysis.signal_cards
    .map((card) => {
      const evidenceLines = card.evidence
        .map((line) => line.trim())
        .filter((line) => line.length > 0 && !/^(?:score|regime|percentile)=/i.test(line));
      const detail = evidenceLines.slice(0, 2).join(" · ") || pickMacroSignalChangeDetail(card.evidence);
      const stance =
        card.key === "a_share_stampede_risk" ? formatAShareRiskStance(card.stance) : card.stance;

      return {
        key: card.key,
        label: card.title,
        value: card.score !== null ? `${stance} · ${card.score}` : stance,
        detail,
        tradeDate: analysis.as_of_date ?? EM_DASH,
        source: formatMacroSignalEvidence(card.evidence) || "macro-toolkit",
        tone: macroToolkitModuleTone(card.tone),
      };
    })
    .sort((left, right) => marketHomeMacroSignalSortIndex(left.key) - marketHomeMacroSignalSortIndex(right.key));
}

export function buildMacroToolkitCapabilityRows(analysis: MacroToolkitAnalysisPayload): ModuleHomeDetailRow[] {
  return analysis.capability_results.map((capability) => ({
    key: capability.key,
    label: capability.label,
    value: capability.headline || formatMacroToolkitPrimaryMetric(capability.primary_metric),
    tradeDate: analysis.as_of_date ?? EM_DASH,
    source: [capability.group, capability.evidence.join(" · ")].filter(Boolean).join(" · "),
    tone: macroToolkitModuleTone(capability.status),
  }));
}

export function buildMacroToolkitIndicatorRows(indicators: MacroToolkitIndicator[]): ModuleHomeDetailRow[] {
  return indicators.map((indicator) => {
    const changeText =
      indicator.change_pct !== null && indicator.change_pct !== undefined
        ? ` · ${indicator.change_pct >= 0 ? "+" : ""}${indicator.change_pct.toFixed(2)}%`
        : "";
    const value =
      indicator.latest_value !== null
        ? `${indicator.latest_value}${indicator.unit ? indicator.unit : ""}${changeText}`
        : EM_DASH;
    return {
      key: indicator.key,
      label: indicator.label,
      value,
      tradeDate: indicator.latest_date ?? EM_DASH,
      source: [indicator.group, indicator.series_id ?? indicator.source].filter(Boolean).join(" · "),
      tone: indicator.quality === "ok" ? "ok" : "watch",
    };
  });
}

const A_SHARE_RISK_METRIC_ROWS: Array<{
  key: string;
  label: string;
  format?: "percent" | "ratio";
}> = [
  { key: "up_count", label: "上涨家数" },
  { key: "up_ratio", label: "上涨比例", format: "percent" },
  { key: "drop_3_count", label: "跌超3%家数" },
  { key: "drop_5_count", label: "跌超5%家数" },
  { key: "limit_down_count", label: "跌停家数" },
  { key: "near_down_count", label: "近跌停" },
  { key: "turnover_ratio_ma20", label: "成交额/20日", format: "ratio" },
  { key: "index_drawdown_from_high", label: "回落幅度", format: "percent" },
];

function formatMacroRiskMetric(value: number | null | undefined, format?: "percent" | "ratio"): string {
  if (value == null) {
    return "缺失";
  }
  if (format === "percent") {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (format === "ratio") {
    return `${value.toFixed(2)}x`;
  }
  return String(value);
}

export function aShareRiskModuleTone(risk: MacroToolkitAShareRiskPayload): ModuleHomeTone {
  if (risk.risk_level === "green") {
    return "ok";
  }
  if (risk.risk_level === "yellow") {
    return "watch";
  }
  if (risk.risk_level === "unknown") {
    return "muted";
  }
  return "error";
}

/**
 * A股踩踏风险档位名展示映射（C12）：后端 `_RISK_NAMES`（backend/app/core_finance/
 * macro/a_share_stampede_risk.py，green/yellow/orange/red/unknown 五档）透传的
 * 「绿色风险」直读像“一种叫绿色的风险”，改写为“风险高低＋档位”；未登记档位
 * （含「数据不足」）原样透出。
 */
const A_SHARE_RISK_STANCE_LABELS: Record<string, string> = {
  绿色风险: "风险低（绿档）",
  黄色风险: "风险中（黄档）",
  橙色风险: "风险较高（橙档）",
  红色风险: "风险高（红档）",
};

export function formatAShareRiskStance(stance: string): string {
  return A_SHARE_RISK_STANCE_LABELS[stance.trim()] ?? stance;
}

export function buildMacroToolkitAShareRiskRows(risk: MacroToolkitAShareRiskPayload): ModuleHomeDetailRow[] {
  const tone = aShareRiskModuleTone(risk);
  const rows: ModuleHomeDetailRow[] = [
    {
      key: "a-share-score",
      label: "风险评分",
      value: risk.risk_score !== null ? String(risk.risk_score) : "缺失",
      tradeDate: risk.trade_date ?? EM_DASH,
      source: formatAShareRiskStance(risk.risk_name),
      tone,
    },
    {
      key: "a-share-summary",
      label: "风险摘要",
      value: risk.summary,
      tradeDate: risk.trade_date ?? EM_DASH,
      source: risk.status,
      tone,
    },
    {
      key: "a-share-position",
      label: "仓位规则",
      value: risk.position_rule,
      tradeDate: EM_DASH,
      source: "position_rule",
      tone: "muted",
    },
  ];

  for (const metric of A_SHARE_RISK_METRIC_ROWS) {
    rows.push({
      key: `a-share-${metric.key}`,
      label: metric.label,
      value: formatMacroRiskMetric(risk.metrics[metric.key], metric.format),
      tradeDate: risk.trade_date ?? EM_DASH,
      source: "metrics",
      tone: "ok",
    });
  }

  for (const [index, rule] of risk.triggered_rules.entries()) {
    rows.push({
      key: `a-share-trigger-${index}`,
      label: "触发规则",
      value: rule,
      tradeDate: risk.trade_date ?? EM_DASH,
      source: "triggered_rules",
      tone: "watch",
    });
  }

  for (const [index, item] of risk.watch_next.entries()) {
    rows.push({
      key: `a-share-watch-${index}`,
      label: "观察条件",
      value: item,
      tradeDate: EM_DASH,
      source: "watch_next",
      tone: "muted",
    });
  }

  return rows;
}

export function buildMacroToolkitHasonRows(strategy: MacroToolkitHasonStrategy): ModuleHomeDetailRow[] {
  const rows: ModuleHomeDetailRow[] = [
    {
      key: "hason-framework",
      label: "策略框架",
      value: strategy.framework_name,
      tradeDate: EM_DASH,
      source: strategy.boundary,
      tone: macroToolkitModuleTone(strategy.status),
    },
    {
      key: "hason-readiness",
      label: "模块就绪",
      value: `${strategy.readiness.ready_modules}/${strategy.readiness.total_modules} · ${(strategy.readiness.ratio * 100).toFixed(0)}%`,
      tradeDate: EM_DASH,
      source: `${strategy.readiness.partial_modules} 部分 / ${strategy.readiness.missing_modules} 缺失`,
      tone: strategy.readiness.ratio >= 0.7 ? "ok" : "watch",
    },
    {
      key: "hason-runtime",
      label: "运行时产物",
      value: strategy.runtime_output_status,
      tradeDate: EM_DASH,
      source: strategy.runtime_output_gaps.join(" / ") || strategy.required_runtime_outputs.join(" / ") || EM_DASH,
      tone: strategy.runtime_output_status === "current" ? "ok" : "watch",
    },
  ];

  for (const module of strategy.modules) {
    rows.push({
      key: `hason-${module.key}`,
      label: module.label,
      value: module.status,
      tradeDate: EM_DASH,
      source: module.available_scripts.join(" / ") || "无可用脚本",
      tone: module.missing_scripts.length > 0 ? "watch" : "ok",
    });
  }

  return rows;
}

export function buildMacroToolkitShadowRows(report: MacroToolkitShadowPortfolioReport): ModuleHomeDetailRow[] {
  const rows: ModuleHomeDetailRow[] = [
    {
      key: "shadow-status",
      label: "报告状态",
      value: report.status,
      tradeDate: report.as_of_date ?? EM_DASH,
      source: report.basis,
      tone: report.status === "complete" ? "ok" : "watch",
    },
    {
      key: "shadow-periods",
      label: "完成周期",
      value: `${report.completed_periods} 期`,
      tradeDate: report.as_of_date ?? EM_DASH,
      source: report.rule_version,
      tone: report.completed_periods >= 12 ? "ok" : "watch",
    },
  ];

  if (report.benchmark) {
    rows.push({
      key: "shadow-benchmark",
      label: report.benchmark.label,
      value: `累计 ${formatRatioPct(report.benchmark.total_return)} · 回撤 ${formatRatioPct(report.benchmark.max_drawdown)}`,
      tradeDate: report.as_of_date ?? EM_DASH,
      source: report.benchmark.key,
      tone: "muted",
    });
  }

  for (const portfolio of report.portfolios) {
    const admission = portfolio.admission?.label ? ` · ${portfolio.admission.label}` : "";
    rows.push({
      key: `shadow-${portfolio.key}`,
      label: portfolio.label,
      value: `累计 ${formatRatioPct(portfolio.total_return)} · 超额 ${formatRatioPct(portfolio.excess_return)}${admission}`,
      tradeDate: report.as_of_date ?? EM_DASH,
      source: portfolio.role,
      tone: portfolio.total_return != null && portfolio.total_return >= 0 ? "ok" : "watch",
    });
  }

  return rows;
}

export function buildMacroToolkitRuntimeRows(analysis: MacroToolkitAnalysisPayload): ModuleHomeDetailRow[] {
  const rows: ModuleHomeDetailRow[] = [];

  if (analysis.cffex_member_rank) {
    const rank = analysis.cffex_member_rank;
    rows.push({
      key: "cffex-member-rank",
      label: "中金所会员排名",
      value: `${rank.status} · ${rank.row_count} 行`,
      tradeDate: rank.latest_trade_date ?? EM_DASH,
      source: `${rank.freshness_status} · ${rank.source_vendors?.join("/") ?? EM_DASH}`,
      tone: rank.freshness_status === "current" ? "ok" : "watch",
    });
  }

  const refresh = analysis.choice_stock_refresh;
  if (refresh?.daily_observation) {
    const daily = refresh.daily_observation;
    rows.push({
      key: "choice-daily-observation",
      label: "股票日频观测",
      value: `${daily.status} · ${daily.stock_count ?? EM_DASH} 只`,
      tradeDate: daily.latest_trade_date ?? EM_DASH,
      source: daily.freshness_status ?? EM_DASH,
      tone: daily.freshness_status === "current" ? "ok" : "watch",
    });
  }
  if (refresh?.factor_snapshot) {
    const factor = refresh.factor_snapshot;
    rows.push({
      key: "choice-factor-snapshot",
      label: "股票因子快照",
      value: `${factor.status} · ${factor.stock_count ?? EM_DASH} 只`,
      tradeDate: factor.as_of_date ?? EM_DASH,
      source: factor.freshness_status ?? EM_DASH,
      tone: factor.freshness_status === "current" ? "ok" : "watch",
    });
  }

  for (const check of analysis.source_checks) {
    rows.push({
      key: `source-${check.alias}`,
      label: check.alias,
      value: check.latest
        ? `${check.latest.value} · ${check.latest.series_id}`
        : "未命中",
      tradeDate: check.latest?.date ?? EM_DASH,
      source: check.latest?.vendor_name ?? EM_DASH,
      tone: check.latest ? "ok" : "watch",
    });
  }

  for (const [index, warning] of analysis.warnings.entries()) {
    rows.push({
      key: `macro-warning-${index}`,
      label: "数据提示",
      value: warning,
      tradeDate: EM_DASH,
      source: "warnings",
      tone: "watch",
    });
  }

  return rows;
}

export function buildMacroToolkitOverviewRows(analysis: MacroToolkitAnalysisPayload): ModuleHomeDetailRow[] {
  return [
    {
      key: "macro-summary",
      label: "结论摘要",
      value: analysis.conclusion.summary,
      tradeDate: analysis.as_of_date ?? EM_DASH,
      source: "conclusion",
      tone: macroToolkitModuleTone(analysis.conclusion.tone),
    },
    {
      key: "macro-stance",
      label: "工具立场",
      value: analysis.conclusion.stance,
      tradeDate: analysis.as_of_date ?? EM_DASH,
      source: "conclusion",
      tone: macroToolkitModuleTone(analysis.conclusion.tone),
    },
    {
      key: "macro-hit-rate",
      label: "指标命中率",
      value: `${analysis.coverage.hit_count}/${analysis.coverage.indicator_count} · ${(analysis.coverage.hit_rate * 100).toFixed(1)}%`,
      tradeDate: analysis.as_of_date ?? EM_DASH,
      source: "coverage",
      tone: analysis.coverage.hit_rate >= 0.7 ? "ok" : "watch",
    },
    {
      key: "macro-scripts",
      label: "注册脚本",
      value: `${analysis.coverage.script_count} 个 · 产物 ${analysis.coverage.output_file_count} 个`,
      tradeDate: analysis.as_of_date ?? EM_DASH,
      source: "toolkit",
      tone: analysis.coverage.script_count > 0 ? "ok" : "muted",
    },
    {
      key: "macro-action",
      label: "建议动作",
      value: analysis.conclusion.recommended_action,
      tradeDate: EM_DASH,
      source: "conclusion",
      tone: "muted",
    },
  ];
}

export function mergeMacroToolkitAnalysis(
  analysis: MacroToolkitAnalysisPayload | undefined,
  strategyPayload: MacroToolkitStrategySummariesPayload | undefined,
): MacroToolkitAnalysisPayload | undefined {
  if (!analysis) {
    return undefined;
  }
  if (!strategyPayload) {
    return analysis;
  }
  return {
    ...analysis,
    strategy_summaries: analysis.strategy_summaries.length
      ? analysis.strategy_summaries
      : strategyPayload.strategy_summaries,
    shadow_portfolio_report:
      analysis.shadow_portfolio_report ?? strategyPayload.shadow_portfolio_report,
  };
}

export function buildMacroToolkitStrategyRows(analysis: MacroToolkitAnalysisPayload): ModuleHomeDetailRow[] {
  return analysis.strategy_summaries.map((strategy) => ({
    key: strategy.key,
    label: strategy.label,
    value: formatMacroToolkitPrimaryMetric(strategy.primary_metric) || strategy.status,
    tradeDate: analysis.as_of_date ?? EM_DASH,
    source: [strategy.group, strategy.evidence.join(" · ")].filter(Boolean).join(" · "),
    tone: macroToolkitModuleTone(strategy.status),
  }));
}
