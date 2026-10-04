import { EM_DASH } from "../../../utils/format";
import type {
  Numeric,
  BondDashboardHeadlinePayload,
  BalanceAnalysisBasisBreakdownPayload,
  AssetStructurePayload,
  PnlAttributionAnalysisSummary,
} from "../../../api/contracts";
import {
  nativeToNumber,
  formatMomChange,
  formatYi,
  formatRatePercent,
  formatBp,
  formatYears,
  formatDv01Wan,
} from "../../bond-dashboard/utils/format";
import type { BondKpiMomKind } from "../../bond-dashboard/utils/format";
import type {
  ModuleHomeKpi,
  ModuleHomeDistributionRow,
  ModuleHomeDistributionPanel,
  ModuleHomeStatus,
  ModuleHomeSourceQueries,
  ModuleHomeDataNote,
  ModuleHomeViewBody,
} from "./moduleHomeModel";
import {
  plain,
  envelopeMeta,
  buildDetailPanel,
} from "./moduleHomePresentation";
import {
  decimalToNumber,
  YUAN_PER_YI,
  formatPortfolioYiFromYuan,
  formatYtmCoverageNote,
  buildRiskIndicatorDetailRows,
  buildPortfolioComparisonRows,
  buildYieldDistributionRows,
  buildSpreadAnalysisRows,
  buildBusinessTypeRows,
  buildBalanceBasisRows,
  buildPnlSummaryRows,
  buildPortfolioComparisonChart,
  buildYieldDistributionChart,
  buildSpreadAnalysisChart,
  buildBusinessTypeChart,
} from "./portfolioHomeModel";
import type { UseQueryResult } from "@tanstack/react-query";
import {
  dependentQueryStatus,
  baseDataNote,
  countDistinctFailedQueries,
  metaEvidenceLine,
  portfolioCoreReadQueries,
  hasError,
  hasLoading,
  hasData,
  queryIsInitialLoading,
  portfolioUsesPublishedBalanceDates,
  metaIsFormalDecisionSource,
  sourceUseStatus,
  emptyRowsWatchStatus,
  dependentCombinedQueryStatus,
  portfolioWaterfallState,
} from "./moduleHomeSourceState";
import type {
  PortfolioReadPathState,
  PortfolioPnlState,
  PortfolioEvidenceState,
} from "./portfolioDecisionModel";
import type { PortfolioEvidenceSource } from "./portfolioReadinessGate";
import type {
  ModuleHomeTone,
  ModuleHomeDetailPanel,
} from "./moduleHomeDetailTypes";
import { buildPortfolioReadinessGate } from "./portfolioReadinessGate";
import {
  buildPortfolioDecision,
  pnlDriverLabel,
} from "./portfolioDecisionModel";
import { bondNumericDisplay } from "../../bond-analytics/adapters/bondAnalyticsAdapter";

function bondDashboardMeta(reportDate: string) {
  return `来源 债券总览 · ${reportDate || EM_DASH}`;
}

function portfolioKpiSparkline(
  current: Numeric | number | null | undefined,
  previous: Numeric | number | null | undefined,
): readonly number[] | undefined {
  const currentRaw =
    typeof current === "number"
      ? current
      : current === null || current === undefined
        ? null
        : nativeToNumber(current);
  const previousRaw =
    typeof previous === "number"
      ? previous
      : previous === null || previous === undefined
        ? null
        : nativeToNumber(previous);
  if (currentRaw === null || previousRaw === null) {
    return undefined;
  }
  return [previousRaw, currentRaw];
}

/**
 * 环比口径与 /bond-dashboard 的 KPI_BAND_NUMERIC_DEFS 逐项一致：
 * 收益率/票息/利差用 bp 差，未实现损益用亿元差，规模/久期/DV01 用相对百分比。
 */
const PORTFOLIO_KPI_MOM_KIND: Record<
  Exclude<keyof BondDashboardHeadlinePayload["kpis"], "bond_count" | "weighted_ytm_coverage_ratio">,
  BondKpiMomKind
> = {
  total_market_value: "percent",
  unrealized_pnl: "amountYi",
  weighted_ytm: "rateBp",
  weighted_duration: "percent",
  weighted_coupon: "rateBp",
  credit_spread_median: "rateBp",
  total_dv01: "percent",
};

function portfolioKpiMomDetail(
  field: keyof BondDashboardHeadlinePayload["kpis"],
  current: Numeric | number | null | undefined,
  previous: Numeric | number | null | undefined,
): string | null {
  if (field === "weighted_ytm_coverage_ratio") {
    return null;
  }
  if (field === "bond_count") {
    const currentCount = typeof current === "number" ? current : null;
    const previousCount = typeof previous === "number" ? previous : null;
    if (currentCount === null || previousCount === null) {
      return null;
    }
    const diff = currentCount - previousCount;
    return `较前日 ${diff >= 0 ? "+" : ""}${diff} 只`;
  }
  if (typeof current !== "object" || current === null || typeof previous !== "object" || previous === null) {
    return null;
  }
  const mom = formatMomChange(PORTFOLIO_KPI_MOM_KIND[field], current, previous);
  return mom ? `环比 ${mom}` : null;
}

function enrichPortfolioKpis(
  kpis: ModuleHomeKpi[],
  bondHeadline: BondDashboardHeadlinePayload | undefined,
  bondKpiDefs: Array<{
    key: string;
    field?: keyof BondDashboardHeadlinePayload["kpis"];
  }>,
): ModuleHomeKpi[] {
  const bondKpis = bondHeadline?.kpis;
  const prevKpis = bondHeadline?.prev_kpis;
  if (!bondKpis || !prevKpis) {
    return kpis;
  }

  return kpis.map((kpi) => {
    const def = bondKpiDefs.find((item) => item.key === kpi.key);
    if (!def?.field) {
      return kpi;
    }
    const field = def.field;
    const sparkline = portfolioKpiSparkline(bondKpis[field], prevKpis[field]);
    const momDetail = portfolioKpiMomDetail(field, bondKpis[field], prevKpis[field]);
    if (!sparkline && !momDetail) {
      return kpi;
    }
    return {
      ...kpi,
      sparkline,
      detail: momDetail ? `${kpi.detail} · ${momDetail}` : kpi.detail,
    };
  });
}

function formatBondHeadlineKpi(
  key: keyof BondDashboardHeadlinePayload["kpis"],
  value: Numeric | number | null | undefined,
) {
  if (value === null || value === undefined) {
    return EM_DASH;
  }
  if (key === "bond_count") {
    const count = typeof value === "number" ? value : nativeToNumber(value);
    if (count === null) {
      return EM_DASH;
    }
    return `${count.toLocaleString("zh-CN", { maximumFractionDigits: 0 })} 只`;
  }
  if (typeof value !== "object" || !("raw" in value)) {
    return EM_DASH;
  }
  if (nativeToNumber(value) === null) {
    return EM_DASH;
  }
  if (key === "total_market_value" || key === "unrealized_pnl") {
    return `${formatYi(value)} 亿元`;
  }
  if (key === "weighted_ytm" || key === "weighted_coupon") {
    return `${formatRatePercent(value)}%`;
  }
  if (key === "credit_spread_median") {
    return value.unit === "bp" ? `${formatBp(value)} bp` : `${formatRatePercent(value)}%`;
  }
  if (key === "weighted_duration") {
    return `${formatYears(value)} 年`;
  }
  if (key === "total_dv01") {
    return `${formatDv01Wan(value)} 万元`;
  }
  return plain(value);
}

function distributionRows(
  items: Array<{ key: string; label: string; marketValue: Numeric; percentage: Numeric | null }>,
  totalMarketValue?: Numeric,
  options: { emptyLabel?: string } = {},
): ModuleHomeDistributionRow[] {
  const totalRaw =
    totalMarketValue !== undefined
      ? (nativeToNumber(totalMarketValue) ?? 0)
      : items.reduce((sum, item) => sum + (nativeToNumber(item.marketValue) ?? 0), 0);

  return items.map((item) => {
    const mvRaw = nativeToNumber(item.marketValue);
    const barPct = totalRaw > 0 && mvRaw !== null ? (mvRaw / totalRaw) * 100 : 0;
    const share = item.percentage ? plain(item.percentage) : EM_DASH;
    return {
      key: item.key,
      label: item.label?.trim() || options.emptyLabel || "未分类",
      marketValue: `${formatYi(item.marketValue)} 亿元`,
      share,
      barPct: Math.min(100, Math.max(0, barPct)),
      tone: mvRaw !== null && mvRaw > 0 ? "ok" : "muted",
    };
  });
}

function zqtzAssetCnyMarketValue(balanceBasis: BalanceAnalysisBasisBreakdownPayload | undefined) {
  if (!balanceBasis) {
    return null;
  }
  const rows = balanceBasis.rows.filter(
    (row) =>
      row.source_family === "zqtz" &&
      row.position_scope === "asset" &&
      row.currency_basis === "CNY",
  );
  if (rows.length === 0) {
    return null;
  }
  return rows.reduce((sum, row) => sum + (decimalToNumber(row.market_value_amount) ?? 0), 0);
}

function ratingTieOutSubtitle(
  assetRating: AssetStructurePayload | undefined,
  balanceBasis: BalanceAnalysisBasisBreakdownPayload | undefined,
) {
  if (!assetRating) {
    return undefined;
  }
  const ratingTotal = nativeToNumber(assetRating.total_market_value);
  const basisTotal = zqtzAssetCnyMarketValue(balanceBasis);
  const tieOut =
    ratingTotal !== null && basisTotal !== null
      ? `正式余额核对差异 ${((ratingTotal - basisTotal) / YUAN_PER_YI).toLocaleString("zh-CN", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })} 亿`
      : "正式余额核对待 basis 分解返回";
  return `ZQTZ 资产端 CNY；${tieOut}；无评级含利率债或未填评级。`;
}

function buildDistributionPanel(args: {
  key: string;
  title: string;
  reportDate: string;
  query: UseQueryResult<unknown> | undefined;
  /** 报告日列表 query；上游失败时分布卡归因为「上游失败」而非「暂无数据」。 */
  upstream?: UseQueryResult<unknown>;
  rows: ModuleHomeDistributionRow[];
  readyDetail: string;
  totalMarketValue?: Numeric;
  /** 合计前缀（如「Top10 合计」）；缺省只显示金额。 */
  totalLabel?: string;
  subtitle?: string;
  viewAllPath?: string;
}): ModuleHomeDistributionPanel {
  const status = dependentQueryStatus(args.key, args.title, args.query, args.upstream, args.readyDetail);
  const emptyReadyStatus: ModuleHomeStatus | null =
    status.tone === "ok" && args.rows.length === 0
      ? {
          key: args.key,
          label: args.title,
          value: "明细为空",
          detail: `${args.title}明细为空；正式读链路已返回但无分组行，请复核源表过滤条件。`,
          tone: "watch",
        }
      : null;
  const panelStatus = emptyReadyStatus ?? status;
  return {
    key: args.key,
    title: args.title,
    meta: bondDashboardMeta(args.reportDate),
    stateLabel: panelStatus.value,
    stateDetail: panelStatus.detail,
    rows: panelStatus.tone === "ok" ? args.rows : [],
    tone: panelStatus.tone,
    totalDisplay:
      panelStatus.tone === "ok" && args.totalMarketValue !== undefined
        ? `${args.totalLabel ? `${args.totalLabel} ` : ""}${formatYi(args.totalMarketValue)} 亿`
        : undefined,
    subtitle: panelStatus.tone === "ok" ? args.subtitle : undefined,
    viewAllPath: args.viewAllPath,
  };
}

function portfolioDataNote(queries: ModuleHomeSourceQueries): ModuleHomeDataNote {
  const base = baseDataNote("portfolio", queries, countDistinctFailedQueries(queries));
  const evidenceLines = [
    metaEvidenceLine("债券总览", queries.bondHeadline?.data?.result_meta),
    metaEvidenceLine("资产负债", queries.balanceOverview?.data?.result_meta),
    metaEvidenceLine("损益归因", queries.pnlSummary?.data?.result_meta),
  ].filter((line): line is string => Boolean(line));

  return {
    ...base,
    lines: [...base.lines, ...evidenceLines],
  };
}

function balanceSourceMeta(reportDate: string) {
  return `来源 资产负债分析 · ${reportDate || EM_DASH}`;
}

function portfolioReadPathState(queries: ModuleHomeSourceQueries): PortfolioReadPathState {
  const coreQueries = portfolioCoreReadQueries(queries);
  if (hasError(coreQueries)) {
    return { label: "读取失败", tone: "error" };
  }
  if (hasLoading(coreQueries)) {
    if (hasData(coreQueries)) {
      return { label: "部分接入", tone: "watch" };
    }
    return { label: "读取中", tone: "muted" };
  }
  return { label: "已接入", tone: "ok" };
}

function portfolioPnlState(
  queries: ModuleHomeSourceQueries,
  summary: PnlAttributionAnalysisSummary | undefined,
): PortfolioPnlState {
  if (queries.pnlSummary?.isError) {
    return { label: "读取失败", tone: "error" };
  }
  if (queryIsInitialLoading(queries.pnlSummary)) {
    return { label: "读取中", tone: "muted" };
  }
  if (summary) {
    return { label: "已返回", tone: "ok" };
  }
  return { label: "待读", tone: "watch" };
}

function portfolioEvidenceState(queries: ModuleHomeSourceQueries): PortfolioEvidenceState {
  const meta =
    queries.bondHeadline?.data?.result_meta ??
    queries.bondRisk?.data?.result_meta ??
    queries.bondPortfolioComparison?.data?.result_meta;
  if (!meta) {
    return {
      factValue: "待返回",
      detail: "证据元数据待返回",
      tone: "muted",
    };
  }

  const rows =
    typeof meta.evidence_rows === "number" ? `${meta.evidence_rows} 行` : "行数未披露";
  const table = meta.tables_used?.[0] ?? "来源表未披露";
  const fallback =
    meta.fallback_mode === "none" && !meta.fallback_date
      ? "无回退"
      : `${meta.fallback_mode}${meta.fallback_date ? ` / ${meta.fallback_date}` : ""}`;
  return {
    factValue: rows,
    detail: `${meta.result_kind} / ${rows} / ${table} / ${fallback}`,
    tone: meta.quality_flag === "ok" ? "ok" : "watch",
  };
}

function portfolioDecisionAnchorDate(queries: ModuleHomeSourceQueries) {
  return (
    queries.bondHeadline?.data?.result.report_date ??
    queries.bondDates?.data?.result.report_dates[0] ??
    ""
  );
}

function portfolioEvidenceSources(queries: ModuleHomeSourceQueries): PortfolioEvidenceSource[] {
  return [
    {
      label: "债券总览",
      hasData: Boolean(queries.bondHeadline?.data),
      isError: queries.bondHeadline?.isError,
      isLoading: queryIsInitialLoading(queries.bondHeadline),
      meta: queries.bondHeadline?.data?.result_meta,
      reportDate: queries.bondHeadline?.data?.result.report_date ?? "",
    },
    {
      label: "风险指标",
      hasData: Boolean(queries.bondRisk?.data),
      isError: queries.bondRisk?.isError,
      isLoading: queryIsInitialLoading(queries.bondRisk),
      meta: queries.bondRisk?.data?.result_meta,
      reportDate: queries.bondRisk?.data?.result.report_date ?? "",
    },
    {
      label: "资产负债",
      hasData: Boolean(queries.balanceOverview?.data),
      isError: queries.balanceOverview?.isError,
      isLoading: queryIsInitialLoading(queries.balanceOverview),
      meta: queries.balanceOverview?.data?.result_meta,
      reportDate: queries.balanceOverview?.data?.result.report_date ?? "",
    },
    {
      label: "损益归因",
      hasData: Boolean(queries.pnlSummary?.data),
      isError: queries.pnlSummary?.isError,
      isLoading: queryIsInitialLoading(queries.pnlSummary),
      meta: queries.pnlSummary?.data?.result_meta,
      reportDate: queries.pnlSummary?.data?.result.report_date ?? "",
    },
  ];
}

function portfolioRiskDatesEvidence(queries: ModuleHomeSourceQueries) {
  return {
    hasData: Boolean(queries.riskDates?.data),
    isError: queries.riskDates?.isError,
    isLoading: queryIsInitialLoading(queries.riskDates),
    dates: queries.riskDates?.data?.result.report_dates ?? [],
    meta: queries.riskDates?.data?.result_meta,
  };
}

export function portfolioView(
  queries: ModuleHomeSourceQueries,
): ModuleHomeViewBody {
  const balance = queries.balanceOverview?.data?.result;
  const bond = queries.bondHeadline?.data?.result;
  const risk = queries.bondRisk?.data?.result;
  const balanceDate = balance?.report_date ?? queries.balanceBasis?.data?.result.report_date
    ?? (portfolioUsesPublishedBalanceDates(queries) ? queries.balancePublicationStatus?.data?.report_dates[0] : undefined)
    ?? queries.balanceDates?.data?.result.report_dates[0] ?? EM_DASH;
  const balanceDateQuery = portfolioUsesPublishedBalanceDates(queries)
    ? queries.balancePublicationStatus : queries.balanceDates;
  const bondDate = queries.bondDates?.data?.result.report_dates[0] ?? bond?.report_date ?? EM_DASH;
  const bondKpis = bond?.kpis;
  const assetType = queries.bondAssetType?.data?.result;
  const assetRating = queries.bondAssetRating?.data?.result;
  const maturity = queries.bondMaturity?.data?.result;
  const industry = queries.bondIndustry?.data?.result;
  const yieldDist = queries.bondYield?.data?.result;
  const portfolioComparison = queries.bondPortfolioComparison?.data?.result;
  const spread = queries.bondSpread?.data?.result;
  const businessType = queries.bondBusinessType?.data?.result;
  const balanceBasis = queries.balanceBasis?.data?.result;
  const pnlSummary = queries.pnlSummary?.data?.result;
  const bondMeta = queries.bondHeadline?.data?.result_meta;
  const riskMeta = queries.bondRisk?.data?.result_meta;
  const formalBond = metaIsFormalDecisionSource(bondMeta) ? bond : undefined;
  const formalRisk = metaIsFormalDecisionSource(riskMeta) ? risk : undefined;
  const formalBondKpis = formalBond?.kpis;
  const visibleBondKpis = bondKpis;
  const visibleRisk = risk;

  const creditRatio = risk ? nativeToNumber(risk.credit_ratio) : null;
  const creditTone =
    creditRatio === null
      ? "待确认信用结构"
      : creditRatio >= 0.5
        ? "信用仓位偏高"
        : creditRatio >= 0.3
          ? "信用仓位适中"
          : "利率债占比更高";

  const bondKpiDefs: Array<{
    key: string;
    label: string;
    field?: keyof NonNullable<typeof bondKpis>;
    detail: string;
    customValue?: string;
    tone?: ModuleHomeTone;
  }> = [
    {
      key: "bond-market",
      label: "债券组合市值",
      field: "total_market_value",
      detail: "债券总览口径，按亿元展示。",
    },
    {
      key: "asset-market",
      label: "资产侧市值",
      customValue: formatPortfolioYiFromYuan(balance?.asset_total_market_value_amount),
      detail: `资产负债口径，${envelopeMeta(queries.balanceOverview)}`,
      tone: balance ? "ok" : "watch",
    },
    {
      key: "liability-market",
      label: "负债侧市值",
      customValue: formatPortfolioYiFromYuan(balance?.liability_total_market_value_amount),
      detail: `资产负债口径，${envelopeMeta(queries.balanceOverview)}`,
      tone: balance ? "ok" : "watch",
    },
    {
      key: "bond-duration",
      label: "加权久期",
      field: "weighted_duration",
      detail: "债券总览久期读数。",
    },
    {
      key: "bond-ytm",
      label: "加权 YTM",
      field: "weighted_ytm",
      detail: "债券总览收益率读数。",
    },
    {
      key: "bond-credit-spread",
      label: "信用利差中位数",
      field: "credit_spread_median",
      detail: "债券总览信用利差读数。",
    },
    {
      key: "bond-dv01",
      label: "DV01 合计",
      field: "total_dv01",
      detail: "债券总览口径，按万元展示。",
    },
    {
      key: "bond-credit-ratio",
      label: "信用占比",
      customValue: visibleRisk ? `${formatRatePercent(visibleRisk.credit_ratio)}%` : EM_DASH,
      detail: formalRisk
        ? "风险指标口径。"
        : visibleRisk
          ? "风险指标为分析/复核口径，仅展示读数，不纳入风险 ticker 或闭合判断。"
          : "风险指标未返回，未纳入 KPI。",
      tone: formalRisk ? "ok" : "watch",
    },
    {
      key: "bond-pnl",
      label: "未实现损益",
      field: "unrealized_pnl",
      detail: "债券总览损益读数，按亿元展示。",
    },
    {
      key: "bond-count",
      label: "持仓只数",
      field: "bond_count",
      detail: "债券总览逐券行数。",
    },
  ];

  const kpis: ModuleHomeKpi[] = enrichPortfolioKpis(
    bondKpiDefs.map((def) => {
      if (def.customValue !== undefined) {
        return {
          key: def.key,
          label: def.label,
          value: def.customValue,
          detail: def.detail,
          tone: def.tone ?? (def.customValue === EM_DASH ? "watch" : "ok"),
        };
      }
      const raw = visibleBondKpis?.[def.field!];
      return {
        key: def.key,
        label: def.label,
        value: visibleBondKpis ? formatBondHeadlineKpi(def.field!, raw) : EM_DASH,
        coverageNote: def.key === "bond-ytm"
          ? formatYtmCoverageNote(visibleBondKpis?.weighted_ytm_coverage_ratio)
          : undefined,
        detail: formalBondKpis
          ? def.detail
          : visibleBondKpis
            ? `${def.detail} 分析/复核口径，仅展示读数，不形成调仓建议。`
            : "债券总览未返回，未纳入 KPI。",
        tone: formalBondKpis ? "ok" : "watch",
      };
    }),
    bond,
    bondKpiDefs,
  );

  const distributionPanels: ModuleHomeDistributionPanel[] = [
    buildDistributionPanel({
      key: "asset-type",
      title: "券种分布",
      reportDate: assetType?.report_date ?? bondDate,
      query: queries.bondAssetType,
      upstream: queries.bondDates,
      readyDetail: "asset-structure / bond_type 已返回。",
      viewAllPath: "/bond-dashboard",
      rows: distributionRows(
        (assetType?.items ?? []).map((item) => ({
          key: item.category,
          label: item.category,
          marketValue: item.total_market_value,
          percentage: item.percentage,
        })),
        assetType?.total_market_value,
      ),
      totalMarketValue: assetType?.total_market_value,
    }),
    buildDistributionPanel({
      key: "rating",
      title: "评级分布",
      reportDate: assetRating?.report_date ?? bondDate,
      query: queries.bondAssetRating,
      upstream: queries.bondDates,
      readyDetail: "asset-structure / rating 已返回。",
      viewAllPath: "/bond-dashboard",
      rows: distributionRows(
        (assetRating?.items ?? []).map((item) => ({
          key: item.category,
          label: item.category,
          marketValue: item.total_market_value,
          percentage: item.percentage,
        })),
        assetRating?.total_market_value,
        { emptyLabel: "未填评级 / 不适用评级" },
      ),
      totalMarketValue: assetRating?.total_market_value,
      subtitle: ratingTieOutSubtitle(assetRating, balanceBasis),
    }),
    buildDistributionPanel({
      key: "maturity",
      title: "期限分布",
      reportDate: maturity?.report_date ?? bondDate,
      query: queries.bondMaturity,
      upstream: queries.bondDates,
      readyDetail: "maturity-structure 已返回。",
      viewAllPath: "/bond-dashboard",
      rows: distributionRows(
        (maturity?.items ?? []).map((item) => ({
          key: item.maturity_bucket,
          label: item.maturity_bucket,
          marketValue: item.total_market_value,
          percentage: item.percentage,
        })),
        maturity?.total_market_value,
      ),
      totalMarketValue: maturity?.total_market_value,
    }),
    buildDistributionPanel({
      key: "industry",
      // 后端 industry-distribution 只返回前 10 大行业，percentage 是 Top10 内占比，
      // 合计也是 Top10 之和，与相邻券种/评级/期限卡的全组合总市值不是同一分母。
      title: "行业分布（Top10）",
      reportDate: industry?.report_date ?? bondDate,
      query: queries.bondIndustry,
      upstream: queries.bondDates,
      readyDetail: "industry-distribution 已返回；占比为 Top10 内占比，合计为 Top10 之和。",
      subtitle: "占比为 Top10 内占比；合计为 Top10 之和，非全组合总市值。",
      totalLabel: "Top10 合计",
      viewAllPath: "/bond-dashboard",
      rows: distributionRows(
        (industry?.items ?? []).map((item) => ({
          key: item.industry_name,
          label: item.industry_name,
          marketValue: item.total_market_value,
          percentage: item.percentage,
        })),
        industry?.total_market_value,
      ),
      totalMarketValue: industry?.total_market_value,
    }),
    buildDistributionPanel({
      key: "yield",
      title: "收益率分布",
      reportDate: yieldDist?.report_date ?? bondDate,
      query: queries.bondYield,
      upstream: queries.bondDates,
      readyDetail: "yield-distribution 已返回。",
      viewAllPath: "/bond-dashboard",
      subtitle: yieldDist
        ? `组合加权 YTM ${formatBondHeadlineKpi("weighted_ytm", yieldDist.weighted_ytm)}`
        : undefined,
      rows: distributionRows(
        (yieldDist?.items ?? []).map((item) => ({
          key: item.yield_bucket,
          label: item.yield_bucket,
          marketValue: item.total_market_value,
          percentage: null,
        })),
      ),
    }),
  ];

  const riskRows = risk ? buildRiskIndicatorDetailRows(risk) : [];
  const riskStatus = sourceUseStatus(
    dependentQueryStatus(
      "risk-indicators-detail",
      "风险指标",
      queries.bondRisk,
      queries.bondDates,
      riskRows.length > 0 ? `risk-indicators 已返回 ${riskRows.length} 项。` : "风险指标为空。",
    ),
    riskMeta,
    "risk-indicators 为分析口径或未允许正式使用，仅保留为明细复核，不参与风险 ticker 或闭合判断。",
  );

  const portfolioRows = portfolioComparison ? buildPortfolioComparisonRows(portfolioComparison) : [];
  const readPath = portfolioReadPathState(queries);
  const pnlState = portfolioPnlState(queries, pnlSummary);
  const evidenceState = portfolioEvidenceState(queries);
  const readiness = buildPortfolioReadinessGate({
    decisionAnchorDate: portfolioDecisionAnchorDate(queries),
    readPathTone: readPath.tone,
    hasCoreReads: Boolean(bondKpis || risk),
    evidenceSources: portfolioEvidenceSources(queries),
    riskDatesEvidence: portfolioRiskDatesEvidence(queries),
  });
  const decision = buildPortfolioDecision({
    bondKpis: formalBondKpis,
    risk: formalRisk,
    pnlSummary,
    bondDate,
    portfolioRows,
    readPath,
    pnlState,
    evidenceState,
    readiness,
  });
  const portfolioStatus = emptyRowsWatchStatus(
    dependentQueryStatus(
      "portfolio-comparison",
      "子组合对比",
      queries.bondPortfolioComparison,
      queries.bondDates,
      portfolioRows.length > 0
        ? `portfolio-comparison 已返回 ${portfolioRows.length} 个子组合。`
        : "子组合对比为空。",
    ),
    portfolioRows,
    "子组合对比为空；正式读链路已返回但无子组合明细，请复核组合分层读链路。",
  );

  const yieldRows = yieldDist ? buildYieldDistributionRows(yieldDist) : [];
  const yieldStatus = emptyRowsWatchStatus(
    dependentQueryStatus(
      "yield-distribution",
      "收益率分布",
      queries.bondYield,
      queries.bondDates,
      yieldRows.length > 0 ? `yield-distribution 已返回 ${yieldRows.length} 项。` : "收益率分布为空。",
    ),
    yieldRows,
    "收益率分布为空；正式读链路已返回但无收益率桶明细，请复核源表过滤条件。",
  );

  const spreadRows = spread ? buildSpreadAnalysisRows(spread) : [];
  const spreadStatus = emptyRowsWatchStatus(
    dependentQueryStatus(
      "spread-analysis",
      "利差结构",
      queries.bondSpread,
      queries.bondDates,
      spreadRows.length > 0 ? `spread-analysis 已返回 ${spreadRows.length} 项。` : "利差结构为空。",
    ),
    spreadRows,
    "利差结构为空；正式读链路已返回但无券种利差明细，请复核源表过滤条件。",
  );

  const businessTypeRows = businessType
    ? buildBusinessTypeRows(businessType, queries.bondBusinessType?.data?.result_meta?.quality_flag)
    : [];
  const businessTypeStatus = emptyRowsWatchStatus(
    dependentQueryStatus(
      "business-type-metrics",
      "业务类型指标",
      queries.bondBusinessType,
      queries.bondDates,
      businessTypeRows.length > 0
        ? `business-type-metrics 已返回 ${businessTypeRows.length} 项。`
        : "业务类型指标为空。",
    ),
    businessTypeRows,
    "业务类型指标为空；正式读链路已返回但无业务类型明细，请复核源表过滤条件。",
  );

  const basisRows = balanceBasis ? buildBalanceBasisRows(balanceBasis) : [];
  const basisStatus = dependentQueryStatus(
    "balance-basis",
    "Basis 分解",
    queries.balanceBasis,
    balanceDateQuery,
    basisRows.length > 0 ? `summary-by-basis 已返回 ${basisRows.length} 行。` : "Basis 分解为空。",
  );

  const pnlRows = pnlSummary ? buildPnlSummaryRows(pnlSummary) : [];
  const pnlStatus = dependentQueryStatus(
    "pnl-attribution-summary",
    "损益归因摘要",
    queries.pnlSummary,
    queries.bondDates,
    pnlRows.length > 0 ? "pnl-attribution summary 已返回。" : "损益归因摘要为空。",
  );

  const detailPanels: ModuleHomeDetailPanel[] = [
    buildDetailPanel({
      key: "risk-indicators-detail",
      title: "风险指标",
      meta: bondDashboardMeta(risk?.report_date ?? bondDate),
      status: riskStatus,
      rows: riskRows,
      showRowsWhenWarning: Boolean(risk),
    }),
    buildDetailPanel({
      key: "portfolio-comparison",
      title: "子组合对比",
      meta: bondDashboardMeta(portfolioComparison?.report_date ?? bondDate),
      status: portfolioStatus,
      rows: portfolioRows,
      chart: portfolioComparison ? buildPortfolioComparisonChart(portfolioComparison) : undefined,
    }),
    buildDetailPanel({
      key: "yield-distribution",
      title: "收益率分布",
      meta: bondDashboardMeta(yieldDist?.report_date ?? bondDate),
      status: yieldStatus,
      rows: yieldRows,
      chart: yieldDist ? buildYieldDistributionChart(yieldDist) : undefined,
    }),
    buildDetailPanel({
      key: "spread-analysis",
      title: "券种收益率中位数",
      meta: bondDashboardMeta(spread?.report_date ?? bondDate),
      status: spreadStatus,
      rows: spreadRows,
      chart: spread ? buildSpreadAnalysisChart(spread) : undefined,
    }),
    buildDetailPanel({
      key: "business-type-metrics",
      title: "业务类型加权指标",
      meta: bondDashboardMeta(businessType?.report_date ?? bondDate),
      status: businessTypeStatus,
      rows: businessTypeRows,
      chart: businessType ? buildBusinessTypeChart(businessType) : undefined,
    }),
    buildDetailPanel({
      key: "balance-basis",
      title: "资产负债 Basis 分解",
      meta: balanceSourceMeta(balanceBasis?.report_date ?? balanceDate),
      status: basisStatus,
      rows: basisRows,
    }),
    buildDetailPanel({
      key: "pnl-attribution-summary",
      title: "损益归因摘要",
      meta: `来源 收益归因 · ${pnlSummary?.report_date ?? bondDate}`,
      status: pnlStatus,
      rows: pnlRows,
    }),
  ];

  const hasCoreReadError = hasError(portfolioCoreReadQueries(queries));

  return {
    stateLabel: readPath.label,
    stateDetail: hasCoreReadError
      ? "部分组合读链路失败，不使用前端补数。"
      : `资产负债 ${balanceDate}，债券总览 ${bondDate}，子组合 ${portfolioRows.length} 个，归因摘要 ${pnlSummary ? "已返回" : "待读"}。`,
    kpis,
    statuses: [
      dependentQueryStatus("balance", "资产负债", queries.balanceOverview, balanceDateQuery, "正式 overview 已返回。"),
      sourceUseStatus(
        dependentQueryStatus("bond", "债券总览", queries.bondHeadline, queries.bondDates, "headline kpis 已返回。"),
        bondMeta,
        "bond.home_summary 为分析口径或未允许正式使用，不参与首屏决策 KPI。",
      ),
      sourceUseStatus(
        dependentQueryStatus("bond-risk", "风险指标", queries.bondRisk, queries.bondDates, "risk-indicators 已返回。"),
        riskMeta,
        "bond.risk_indicators 为分析口径或未允许正式使用，不参与风险 ticker 或闭合判断。",
      ),
      dependentQueryStatus(
        "bond-structure",
        "持仓结构",
        queries.bondAssetType,
        queries.bondDates,
        "券种/评级/期限/行业分布已挂接。",
      ),
      dependentCombinedQueryStatus(
        "bond-depth",
        "深度读链路",
        [
          queries.bondYield,
          queries.bondPortfolioComparison,
          queries.bondSpread,
          queries.bondBusinessType,
        ],
        queries.bondDates,
        "深度读链路至少一个子读面已返回；收益率/子组合/利差/业务类型分别在明细面板披露。",
      ),
      dependentQueryStatus(
        "balance-basis",
        "Basis 分解",
        queries.balanceBasis,
        balanceDateQuery,
        "summary-by-basis 已返回。",
      ),
      dependentQueryStatus("pnl-summary", "损益归因", queries.pnlSummary, queries.bondDates, "summary 已返回。"),
      {
        key: "positions",
        label: "持仓明细",
        value: "下钻页",
        detail: "逐券明细仍在 /positions 展开。",
        tone: "muted",
      },
    ],
    decision,
    briefings: [
      {
        title: "规模与错配",
        conclusion:
          formalBondKpis && balance
            ? `债券组合 ${formatBondHeadlineKpi("total_market_value", formalBondKpis.total_market_value)}，资产侧 ${formatPortfolioYiFromYuan(
                balance.asset_total_market_value_amount,
              )}，负债侧 ${formatPortfolioYiFromYuan(balance.liability_total_market_value_amount)}。`
            : bondKpis && balance
              ? `债券组合 ${formatBondHeadlineKpi("total_market_value", bondKpis.total_market_value)}，资产侧 ${formatPortfolioYiFromYuan(
                  balance.asset_total_market_value_amount,
                )}，负债侧 ${formatPortfolioYiFromYuan(balance.liability_total_market_value_amount)}。`
            : balance
              ? `资产侧 ${formatPortfolioYiFromYuan(balance.asset_total_market_value_amount)}，负债侧 ${formatPortfolioYiFromYuan(
                  balance.liability_total_market_value_amount,
                )}。`
              : "资产负债 overview 暂无可用数据。",
        evidence: basisRows.length
          ? `已挂接 basis 分解 ${basisRows.length} 行；不做净额补算。`
          : "使用 balance-analysis overview 字段展示，不做净额补算。",
        tone: balance || bondKpis ? "ok" : "watch",
      },
      {
        title: "风险敏感度",
        conclusion:
          formalBondKpis && formalRisk
            ? `久期 ${formatBondHeadlineKpi("weighted_duration", formalBondKpis.weighted_duration)}，DV01 ${formatBondHeadlineKpi(
                "total_dv01",
                formalBondKpis.total_dv01,
              )}，${creditTone}（信用占比 ${formatRatePercent(formalRisk.credit_ratio)}%）。`
            : bondKpis && risk
              ? `久期 ${formatBondHeadlineKpi("weighted_duration", bondKpis.weighted_duration)}，DV01 ${formatBondHeadlineKpi(
                  "total_dv01",
                  bondKpis.total_dv01,
                )}，${creditTone}（信用占比 ${formatRatePercent(risk.credit_ratio)}%，仅分析/复核）。`
            : formalRisk
              ? `久期 ${formatYears(formalRisk.weighted_duration)} 年，DV01 ${formatDv01Wan(formalRisk.total_dv01)} 万元，${creditTone}。`
              : risk
                ? `久期 ${formatYears(risk.weighted_duration)} 年，DV01 ${formatDv01Wan(
                    risk.total_dv01,
                  )} 万元，${creditTone}（仅分析/复核）。`
                : "风险读数暂未返回。",
        evidence: "直接展示 headline / risk-indicators 字段，不以前端估算监管 DV01。",
        tone: formalBondKpis || formalRisk ? "ok" : "watch",
      },
      {
        title: "收益解释",
        conclusion: pnlSummary
          ? `主驱动 ${pnlDriverLabel(pnlSummary.primary_driver)}（${bondNumericDisplay(
              pnlSummary.primary_driver_pct,
            )}）；${pnlSummary.key_findings[0] ?? "详见归因摘要。"}`
          : bondKpis
            ? `未实现损益 ${formatBondHeadlineKpi("unrealized_pnl", bondKpis.unrealized_pnl)}，加权 YTM ${formatBondHeadlineKpi(
                "weighted_ytm",
                bondKpis.weighted_ytm,
              )}。`
            : "收益解释需要进入损益归因下钻页。",
        evidence: pnlSummary
          ? "使用 pnl-attribution summary；完整瀑布图在 /pnl-attribution。"
          : "首页只做摘要，不替代正式归因页面。",
        tone: pnlSummary || bondKpis ? "ok" : "muted",
      },
    ],
    distributionPanels,
    detailPanels,
    pnlWaterfall: queries.pnlVolumeRate?.data?.result,
    pnlWaterfallState: portfolioWaterfallState(queries.pnlVolumeRate, bondDate),
    dataNote: portfolioDataNote(queries),
  };
}
