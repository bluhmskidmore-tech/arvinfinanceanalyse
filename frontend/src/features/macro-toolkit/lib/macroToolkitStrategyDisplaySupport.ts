import type {
  MacroToolkitChoiceStockRefreshPermission,
  MacroToolkitChoiceStockRefreshRun,
  MacroToolkitCommodityFuturesRefreshStatus,
  MacroToolkitDualFrequencyCandidate,
  MacroToolkitShadowPortfolio,
  MacroToolkitShadowPortfolioHolding,
  MacroToolkitShadowPortfolioPeriodReturn,
  MacroToolkitShadowPortfolioReport,
  MacroToolkitStrategySummary,
} from "../../../api/macroToolkitClient";
import { formatNumberValue } from "./macroToolkitCrisisSupport";
import { formatBusinessEvidenceLabel } from "./macroToolkitDisplayFormat";
import { statusLabel } from "./macroToolkitPanelShared";

export function hasRealStrategySource(strategy: MacroToolkitStrategySummary) {
  return (
    strategy.result.price_source === "choice_stock_daily_observation" ||
    strategy.result.factor_source === "choice_stock_factor_snapshot"
  );
}

export function hasCompleteRealStrategyChain(strategy: MacroToolkitStrategySummary) {
  if (strategy.status !== "complete" || strategyDataStatus(strategy) !== "complete") {
    return false;
  }
  const hasPriceSource = strategy.result.price_source === "choice_stock_daily_observation";
  const hasFactorSource = strategy.result.factor_source === "choice_stock_factor_snapshot";
  if (strategy.key === "multi_factor_selection") {
    return hasFactorSource;
  }
  if (strategy.key === "low_crowding_regime_multifactor") {
    return hasPriceSource && hasFactorSource;
  }
  return hasPriceSource;
}

export function strategyDataStatus(strategy: MacroToolkitStrategySummary) {
  return typeof strategy.result.data_status === "string" && strategy.result.data_status.trim()
    ? strategy.result.data_status.trim()
    : strategy.status;
}

export function choiceStockTableDetail(
  table: { row_count?: number; latest_trade_date?: string | null; as_of_date?: string | null; freshness_status?: string; fallback_mode?: string | null; fallback_date?: string | null } | null | undefined,
  dateField: "latest_trade_date" | "as_of_date",
) {
  return `行数 ${table?.row_count ?? 0} · ${choiceStockTableSummary(table, dateField)}`;
}

export function choiceStockTableSummary(
  table: { latest_trade_date?: string | null; as_of_date?: string | null; freshness_status?: string; fallback_mode?: string | null; fallback_date?: string | null } | null | undefined,
  dateField: "latest_trade_date" | "as_of_date",
) {
  const dateText = table?.[dateField] ?? "缺失";
  const statusText = statusLabel(table?.freshness_status ?? "unknown");
  const fallbackText = choiceStockFallbackText(table);
  return [dateText, statusText, fallbackText].filter(Boolean).join(" · ");
}

export type CommodityHealthStatus = NonNullable<NonNullable<MacroToolkitCommodityFuturesRefreshStatus>["status"]>;

export function commodityStatusTone(status: CommodityHealthStatus | null | undefined): "neutral" | "positive" | "missing" {
  if (!status) {
    return "neutral";
  }
  return status.status === "ok" ? "positive" : "missing";
}

export function commodityNanhuaStatusTone(status: CommodityHealthStatus | null | undefined): "neutral" | "positive" | "missing" {
  if (!status) {
    return "neutral";
  }
  return status.nanhua_input?.status === "hit" ? "positive" : "missing";
}

export function commodityNanhuaStatusValue(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "待确认";
  }
  if (status.nanhua_input?.status !== "hit") {
    return "缺失";
  }
  const latestValue = formatNumberValue(status.nanhua_input.latest_value, 2);
  return latestValue === "缺失" ? "已命中" : `已命中 ${latestValue}`;
}

export function commodityNanhuaStatusDetail(status: CommodityHealthStatus | null | undefined) {
  const input = status?.nanhua_input;
  if (!input || input.status !== "hit") {
    return "NHCI / NH0100.NHF 未命中";
  }
  const date = input.latest_trade_date ?? "日期缺失";
  const value = formatNumberValue(input.latest_value, 2);
  const source = input.source_version || input.vendor_version || "来源缺失";
  return `${input.product_code} / ${input.series_id} · ${date} · ${value} · ${source}`;
}

export function commodityLatestDateValue(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "待确认";
  }
  return status.latest_trade_date ?? "暂无数据";
}

export function commodityTableStatusDetail(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "商品期货证据状态待确认";
  }
  const rowText = status.row_count == null ? "行数缺失" : `${status.row_count} 行`;
  return `商品期货证据 · ${commodityTableStatusLabel(status.status)} · ${rowText}`;
}

export function commodityCoverageValue(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "待确认";
  }
  const coverage = status.coverage;
  return `${coverage.available_product_count}/${coverage.target_product_count}`;
}

export function commodityCoverageDetail(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "覆盖品种待确认";
  }
  const available = status.coverage.available_products.length ? status.coverage.available_products.join(" / ") : "无命中";
  const missing = status.coverage.missing_products.length ? ` · 缺失 ${status.coverage.missing_products.join(" / ")}` : "";
  return `${available}${missing}`;
}

export function commoditySourceValue(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "待确认";
  }
  return status.source_vendors.length ? status.source_vendors.join(" / ") : "缺失";
}

export function commoditySourceDetail(status: CommodityHealthStatus | null | undefined) {
  if (!status) {
    return "来源待确认";
  }
  const nanhua = status.nanhua_input;
  const source = nanhua?.source_version || nanhua?.vendor_version || status.source_vendors.join(" / ") || "来源缺失";
  return `商品期货证据 · ${formatBusinessEvidenceLabel(source)}`;
}

export function commodityTableStatusLabel(status: string) {
  if (status === "ok") {
    return "正常";
  }
  if (status === "empty_table") {
    return "暂无数据";
  }
  if (status === "missing_table") {
    return "未接入";
  }
  if (status === "unreadable_database") {
    return "读取失败";
  }
  return status || "未知";
}

export function commodityFuturesPermissionErrorMessage() {
  return "当前账号没有商品期货刷新权限，请先授予 macro_toolkit.commodity_futures:refresh。";
}

export function commodityFuturesPermissionPendingMessage() {
  return "商品期货刷新授权待确认，请先确认 macro_toolkit.commodity_futures:dry_run / refresh。";
}

export function commodityFuturesPermissionBlockMessage(
  permission: MacroToolkitChoiceStockRefreshPermission | null | undefined,
) {
  return permission?.allowed === false ? commodityFuturesPermissionErrorMessage() : commodityFuturesPermissionPendingMessage();
}

export function formatCommodityFuturesRefreshError(error: unknown) {
  const message = error instanceof Error ? error.message : "";
  if (/not allowed/i.test(message) && message.includes("macro_toolkit.commodity_futures")) {
    return commodityFuturesPermissionErrorMessage();
  }
  return message || "刷新商品期货失败";
}

export function commodityFuturesPermissionDetail(permission: MacroToolkitChoiceStockRefreshPermission | null | undefined) {
  if (!permission) {
    return "商品期货刷新授权待确认";
  }
  const actions = permission.actions?.length ? permission.actions.join(" / ") : "dry_run / refresh";
  const user = permission.user_id || "anonymous";
  return `${permission.allowed ? "可刷新" : "未授权"} · ${actions} · ${user}`;
}

export function commodityFuturesPermissionNoticeTitle(permission: MacroToolkitChoiceStockRefreshPermission | null | undefined) {
  return permission?.allowed === false ? "缺少商品期货刷新授权" : "商品期货刷新授权待确认";
}

export function commodityFuturesPermissionNotice(permission: MacroToolkitChoiceStockRefreshPermission | null | undefined) {
  const resource = permission?.resource ?? "macro_toolkit.commodity_futures";
  const actions = permission?.actions?.length ? permission.actions.join(" / ") : "dry_run / refresh";
  const user = permission?.user_id || "anonymous";
  const role = permission?.role || "unknown";
  return `请在 scope store 授予 ${resource} 的 action refresh；dry_run / refresh 都需要这条授权。当前用户 ${user}，角色 ${role}，动作 ${actions}。`;
}

export function choiceStockFallbackText(
  table: { fallback_mode?: string | null; fallback_date?: string | null } | null | undefined,
) {
  if (table?.fallback_mode !== "latest_available" || !table.fallback_date) {
    return "";
  }
  return `fallback ${table.fallback_mode} · 最近可用 ${table.fallback_date}`;
}

export function choiceStockPermissionValue(permission: MacroToolkitChoiceStockRefreshPermission | null | undefined) {
  if (!permission) {
    return "待确认";
  }
  if (permission.allowed === false) {
    return "未授权";
  }
  return permission.allowed === true || permission.mode === "identity_only" ? "已授权" : "待确认";
}

export function choiceStockRefreshValue(
  refresh: MacroToolkitChoiceStockRefreshRun | null | undefined,
  permission: MacroToolkitChoiceStockRefreshPermission | null | undefined,
) {
  if (choiceStockHasRunEvidence(refresh)) {
    return statusLabel(refresh.status);
  }
  return choiceStockPermissionValue(permission);
}

export function choiceStockRefreshDetail(
  refresh: MacroToolkitChoiceStockRefreshRun | null | undefined,
  permission: MacroToolkitChoiceStockRefreshPermission | null | undefined,
) {
  const hasRunEvidence = choiceStockHasRunEvidence(refresh);
  const permissionDetail = choiceStockPermissionDetail(hasRunEvidence ? (refresh.permission ?? permission) : permission);
  if (!hasRunEvidence) {
    return permissionDetail;
  }
  const runId = refresh.run_id ?? "none";
  const reportDate = refresh.report_date ?? "unknown";
  const triggerMode = refresh.trigger_mode ?? "unknown";
  const historyRows = refresh.history_row_count ?? "-";
  const factorRows = refresh.factor_row_count ?? "-";
  const source = refresh.source_version?.trim();
  const vendor = refresh.vendor_version?.trim();
  const rule = refresh.rule_version?.trim();
  const cache = refresh.cache_version?.trim();
  const versionText = [
    source ? `source ${source}` : "",
    vendor ? `vendor ${vendor}` : "",
    rule ? `rule ${rule}` : "",
    cache ? `cache ${cache}` : "",
  ].filter(Boolean).join(" · ");
  const version = versionText ? ` · ${versionText}` : "";
  const failureText = choiceStockRefreshFailureText(refresh);
  const failure = failureText ? ` · failure ${failureText}` : "";
  return `run ${runId} · report ${reportDate} · trigger ${triggerMode} · rows history ${historyRows} / factor ${factorRows}${version}${failure} · ${permissionDetail}`;
}

export function choiceStockHasRunEvidence(refresh: MacroToolkitChoiceStockRefreshRun | null | undefined): refresh is MacroToolkitChoiceStockRefreshRun {
  return Boolean(refresh?.run_id);
}

export function choiceStockRefreshFailureText(refresh: MacroToolkitChoiceStockRefreshRun) {
  return refresh.failure_category?.trim() || "";
}

export function choiceStockPermissionDetail(
  permission: MacroToolkitChoiceStockRefreshPermission | null | undefined,
  defaultResource = "choice_stock.refresh",
) {
  if (!permission) {
    return `resource ${defaultResource}`;
  }
  const resource = permission.resource ?? defaultResource;
  const mode = permission.mode || "unknown";
  const actions = permission.actions?.length ? permission.actions.join(" / ") : "unknown";
  const user = permission.user_id || "anonymous";
  return `resource ${resource} · mode ${mode} · actions ${actions} · user ${user}`;
}

export function formatSignedRatio(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) {
    return "缺失";
  }
  const percent = value * 100;
  return `${percent >= 0 ? "+" : ""}${percent.toFixed(1)}%`;
}

export function formatPlainRatio(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) {
    return "缺失";
  }
  return `${(value * 100).toFixed(1)}%`;
}

export function portfolioConstraintText(portfolio: MacroToolkitShadowPortfolio) {
  const constraints = portfolio.constraints;
  const parts = [
    constraints.pe_max == null ? "" : `PE≤${constraints.pe_max}`,
    constraints.pb_max == null ? "" : `PB≤${constraints.pb_max}`,
    constraints.turnover_cap == null ? "" : `换手≤${Math.round(constraints.turnover_cap * 100)}%`,
  ].filter(Boolean);
  return parts.length ? parts.join(" / ") : "沿用正式规则约束";
}

export function portfolioWeightsText(portfolio: MacroToolkitShadowPortfolio) {
  const labels: Record<string, string> = {
    value: "价值",
    quality: "质量",
    momentum: "动量",
    low_vol: "低波",
    dividend: "红利",
  };
  return Object.entries(portfolio.weights)
    .map(([key, value]) => `${labels[key] ?? key}${Math.round(value * 100)}%`)
    .join(" / ");
}

export function costResultText(portfolio: MacroToolkitShadowPortfolio, costBps: number) {
  const result = portfolio.cost_results.find((item) => item.cost_bps === costBps);
  if (!result) {
    return `${costBps}bp 缺失`;
  }
  return `${costBps}bp ${formatSignedRatio(result.total_return)} / 超额 ${formatSignedRatio(result.excess_return)}`;
}

export function portfolioCostResult(portfolio: MacroToolkitShadowPortfolio, costBps: number) {
  return portfolio.cost_results.find((item) => item.cost_bps === costBps);
}

export function shadowPortfolioPeriodRows(
  report: MacroToolkitShadowPortfolioReport,
  portfolio: MacroToolkitShadowPortfolio,
) {
  return report.period_returns.filter((row) => row.portfolio_key === portfolio.key);
}

export function shadowPortfolioPeriodWinLossText(rows: MacroToolkitShadowPortfolioPeriodReturn[]) {
  if (!rows.length) {
    return "周期缺失";
  }
  const wins = rows.filter((row) => row.excess_return > 0).length;
  return `${wins}赢 / ${rows.length - wins}输`;
}

export function shadowPortfolioPeriodRangeText(rows: MacroToolkitShadowPortfolioPeriodReturn[]) {
  if (!rows.length) {
    return "最佳缺失 / 最差缺失";
  }
  const best = rows.reduce((winner, row) => (row.excess_return > winner.excess_return ? row : winner), rows[0]!);
  const worst = rows.reduce((loser, row) => (row.excess_return < loser.excess_return ? row : loser), rows[0]!);
  return `最佳 ${formatSignedRatio(best.excess_return)} / 最差 ${formatSignedRatio(worst.excess_return)}`;
}

export function shadowPortfolioCostGateText(
  reference: MacroToolkitShadowPortfolio,
  candidate: MacroToolkitShadowPortfolio,
) {
  const passingCosts = [20, 50].filter((costBps) => {
    const referenceCost = portfolioCostResult(reference, costBps);
    const candidateCost = portfolioCostResult(candidate, costBps);
    return (
      referenceCost != null &&
      candidateCost != null &&
      candidateCost.total_return > referenceCost.total_return &&
      candidateCost.excess_return > referenceCost.excess_return
    );
  });
  if (passingCosts.length === 2) {
    return "20bp/50bp 均胜出";
  }
  if (passingCosts.length) {
    return `${passingCosts.join("bp / ")}bp 胜出`;
  }
  return "成本后未胜出";
}

export function shadowPortfolioAdmissionText(candidate: MacroToolkitShadowPortfolio) {
  if (!candidate.admission) {
    return "准入口径缺失";
  }
  return `${candidate.admission.label} · ${candidate.admission.summary}`;
}

export function admissionCriterionText(threshold: unknown) {
  if (threshold == null) {
    return "";
  }
  if (Array.isArray(threshold)) {
    return threshold.length ? threshold.join(" / ") : "无";
  }
  if (typeof threshold === "string" || typeof threshold === "number" || typeof threshold === "boolean") {
    return String(threshold);
  }
  return "";
}

export function holdingCodeList(holdings: MacroToolkitShadowPortfolioHolding[]) {
  return holdings.slice(0, 3).map((holding) => holding.stock_code).join(" / ") || "无";
}

export function shadowPortfolioHoldingDiff(
  reference: MacroToolkitShadowPortfolio,
  candidate: MacroToolkitShadowPortfolio,
) {
  const referenceCodes = new Set(reference.latest_holdings.map((holding) => holding.stock_code));
  const candidateCodes = new Set(candidate.latest_holdings.map((holding) => holding.stock_code));
  const overlap = candidate.latest_holdings.filter((holding) => referenceCodes.has(holding.stock_code));
  const candidateOnly = candidate.latest_holdings.filter((holding) => !referenceCodes.has(holding.stock_code));
  const referenceOnly = reference.latest_holdings.filter((holding) => !candidateCodes.has(holding.stock_code));
  return {
    overlapText: `持仓重合 ${overlap.length}/${Math.max(candidate.latest_holdings.length, 1)}`,
    candidateOnlyText: `新增观察 ${holdingCodeList(candidateOnly)}`,
    referenceOnlyText: `正式独有 ${holdingCodeList(referenceOnly)}`,
  };
}

export function periodChipText(row: MacroToolkitShadowPortfolioPeriodReturn) {
  return `${row.start_date.slice(5)}→${row.end_date.slice(5)} ${formatSignedRatio(row.excess_return)}`;
}

export function shadowPortfolioFactorWindowText(report: MacroToolkitShadowPortfolioReport) {
  const firstDate = report.factor_dates[0];
  const lastDate = report.factor_dates.at(-1) ?? report.as_of_date;
  if (!firstDate || !lastDate) {
    return `${report.completed_periods}周期`;
  }
  return `${firstDate} → ${lastDate} / ${report.completed_periods}周期`;
}

export function shadowPortfolioCostModelText(report: MacroToolkitShadowPortfolioReport) {
  const costs = report.cost_model.cost_bps.length ? `${report.cost_model.cost_bps.join("/")}bp` : "成本缺失";
  const initialBuild = report.cost_model.initial_build_included ? "含初始建仓" : "不含初始建仓";
  const finalLiquidation = report.cost_model.final_liquidation_included ? "含期末清仓" : "不含期末清仓";
  return `${costs} · ${initialBuild} · ${finalLiquidation}`;
}

export function shadowPortfolioReviewAction(candidate: MacroToolkitShadowPortfolio) {
  if (candidate.admission?.status === "passed") {
    return "进入正式候选评审，不自动替换正式规则";
  }
  if (candidate.admission?.status === "needs_review") {
    return "补齐历史与告警复核后再评审";
  }
  if (candidate.admission?.status === "failed") {
    return "保持影子观察，暂不进入正式候选";
  }
  return "等待准入口径补齐";
}

export function shadowPortfolioWarningText(warning: string) {
  if (warning === "DUCKDB_BUSY") {
    return "本地股票历史库正在刷新或被落库任务占用，稍后刷新页面即可重试。";
  }
  if (warning.startsWith("DUCKDB_OPEN_FAILED")) {
    return "DuckDB 读连接打开失败，暂时不能生成影子组合回测。";
  }
  if (warning === "DUCKDB_NOT_FOUND") {
    return "本地股票历史库不存在，暂时不能生成影子组合回测。";
  }
  if (warning.startsWith("MISSING_TABLES")) {
    return "本地股票历史表或因子快照表缺失，暂时不能生成影子组合回测。";
  }
  if (warning === "FACTOR_HISTORY_TOO_SHORT" || warning === "SHORT_HISTORY") {
    return "因子快照历史偏短，当前结果只能作为只读观察。";
  }
  if (warning === "READ_ONLY_SHADOW_NOT_PRODUCTION") {
    return "只读影子评估，不能作为正式投研信号。";
  }
  return warning;
}

export function shadowPortfolioUnavailableDescription(warnings: readonly string[]) {
  const visibleWarnings = Array.from(new Set(warnings.map(shadowPortfolioWarningText).filter(Boolean)));
  return visibleWarnings.join(" / ") || "本地股票历史或因子快照不足。";
}

export function shadowPortfolioObservationText(report: MacroToolkitShadowPortfolioReport | null) {
  if (!report) {
    return {
      label: "影子组合待确认",
      value: "未返回",
      detail: "完整分析可继续确认只读组合证据。",
      tone: "missing" as const,
    };
  }
  if (report.status !== "complete") {
    return {
      label: "影子组合只读",
      value: "待确认",
      detail: shadowPortfolioUnavailableDescription(report.warnings),
      tone: "missing" as const,
    };
  }
  const candidate = report.portfolios.find((portfolio) => portfolio.role === "shadow_candidate");
  const action = candidate ? shadowPortfolioReviewAction(candidate) : "保持观察，不替换正式规则";
  return {
    label: "影子组合只读",
    value: report.as_of_date ?? "日期缺失",
    detail: `${report.completed_periods} 个周期 · ${action}`,
    tone: "neutral" as const,
  };
}

export function strategyObservationDetail(
  strategySummaries: MacroToolkitStrategySummary[],
  fullRealStrategyCount: number,
  partialRealStrategyCount: number,
  degradedStrategyCount: number,
  sampleStrategyCount: number,
) {
  if (!strategySummaries.length) {
    return "暂无策略摘要，完整分析后再确认。";
  }
  return [
    `真实链路 ${fullRealStrategyCount}`,
    partialRealStrategyCount ? `部分链路 ${partialRealStrategyCount}` : "",
    degradedStrategyCount ? `降级 ${degradedStrategyCount}` : "",
    sampleStrategyCount ? `样例 ${sampleStrategyCount}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

export function strategyObservationNote(strategy: MacroToolkitStrategySummary | null, strategySupplyState: string) {
  if (!strategy) {
    return `策略供数 ${statusLabel(strategySupplyState)}`;
  }
  const dataStatus = strategyDataStatus(strategy);
  if (hasCompleteRealStrategyChain(strategy)) {
    return `${statusLabel(dataStatus)} · 已接入真实行情或因子快照，仍仅作观察。`;
  }
  if (hasRealStrategySource(strategy)) {
    return `${statusLabel(dataStatus)} · 部分真实供数，缺口需在完整分析中复核。`;
  }
  return `${statusLabel(dataStatus)} · 当前仅展示策略可用性，不作为正式投资信号。`;
}

export function dualFrequencyStatus(candidate: MacroToolkitDualFrequencyCandidate) {
  return candidate.data_status?.status ?? candidate.status ?? "unknown";
}

export function dualFrequencyStatusText(status: string) {
  const labels: Record<string, string> = {
    warning: "存在缺口",
    not_evaluated: "未评估",
    attack: "进攻",
    defense: "防守",
    cooldown: "冷却",
    ramp: "恢复",
  };
  return labels[status] ?? statusLabel(status);
}

export function dualFrequencyRatio(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "—";
}

export function dualFrequencyMultiplier(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? `×${value.toFixed(2)}` : "—";
}

export function dualFrequencyCount(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value)
    : "—";
}

export function dualFrequencyHistory(candidate: MacroToolkitDualFrequencyCandidate) {
  return candidate.provenance?.history ?? candidate.data_status?.history ?? null;
}

export function dualFrequencyUniqueTexts(values: Array<string | null | undefined>) {
  return [...new Set(values.filter((value): value is string => Boolean(value)))];
}

export function dualFrequencySourceText(candidate: MacroToolkitDualFrequencyCandidate) {
  const history = dualFrequencyHistory(candidate);
  return dualFrequencyUniqueTexts(history?.tables_used ?? []).join(" / ") || "来源未返回";
}

export function dualFrequencyVersionText(candidate: MacroToolkitDualFrequencyCandidate) {
  const history = dualFrequencyHistory(candidate);
  const sources = Object.values(history?.sources ?? {});
  const sourceVersions = dualFrequencyUniqueTexts(sources.flatMap((source) => source.source_versions ?? []));
  const vendorVersions = dualFrequencyUniqueTexts(sources.flatMap((source) => source.vendor_versions ?? []));
  const ruleVersions = dualFrequencyUniqueTexts(sources.flatMap((source) => source.rule_versions ?? []));
  const summarize = (label: string, values: string[]) => {
    if (!values.length) return "";
    return `${label} ${values[0]}${values.length > 1 ? ` 等${values.length}项` : ""}`;
  };
  const parts = [
    candidate.formula_version ? `公式 ${candidate.formula_version}` : "",
    candidate.rule_version ? `规则 ${candidate.rule_version}` : "",
    summarize("源版本", sourceVersions),
    summarize("供应商版本", vendorVersions),
    summarize("数据规则", ruleVersions),
  ].filter(Boolean);
  return parts.join(" · ") || "版本未返回";
}

export function dualFrequencyAlignmentText(alignment: string | undefined) {
  const labels: Record<string, string> = {
    exact: "同日对齐",
    prior_observation: "前一交易日",
    no_observation: "无可用观察",
  };
  return alignment ? labels[alignment] ?? alignment : "对齐状态未返回";
}

export function strategyTraceList(value: unknown, maxItems = 3) {
  if (!Array.isArray(value)) {
    return "";
  }
  const items = value
    .map((item) => String(item ?? "").trim())
    .filter(Boolean);
  return (Number.isFinite(maxItems) ? items.slice(0, maxItems) : items).join(" / ");
}

export function strategyScalarText(value: unknown) {
  if (typeof value !== "string" && typeof value !== "number") {
    return "";
  }
  return String(value).trim();
}
