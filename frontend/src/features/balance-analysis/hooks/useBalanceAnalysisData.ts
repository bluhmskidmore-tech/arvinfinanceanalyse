import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/clientContext";
import { apiQueryKeys } from "../../../api/queryKeys";
import type {
  BalanceAnalysisSeverity,
  BalanceAnalysisWorkbookOperationalSection,
  BalanceAnalysisWorkbookTable,
  BalanceBusinessMovementTrendMonth,
  BalancePageCalibration,
  BalanceZqtzConcentrationAnalysis,
  ResultMeta,
} from "../../../api/contracts";
import { buildStateSurfaces } from "../../../pageModel";
import { buildBalanceDetailGridRows, buildBalanceDetailSummaryGridRows } from "../pages/balanceAnalysisGridRows";
import { useBalanceAnalysisFilters } from "./useBalanceAnalysisFilters";

import { EM_DASH } from "../../../utils/format";
const PAGE_SIZE = 2;

const primaryWorkbookTableKeys = [
  "bond_business_types",
  "rating_analysis",
  "maturity_gap",
  "issuance_business_types",
] as const;

const secondaryWorkbookPanelKeys = [
  "industry_distribution",
  "rate_distribution",
  "counterparty_types",
] as const;

const rightRailWorkbookKeys = [
  "event_calendar",
  "risk_alerts",
] as const;

export interface BalanceAnalysisDataParams {
  summaryOffset: number;
  eventTypeFilter: string;
  riskSeverityFilter: "all" | BalanceAnalysisSeverity;
  selectedDecisionKey: string | null;
  selectedEventCalendarKey: string | null;
  selectedRiskAlertKey: string | null;
}

function finiteNumber(value: unknown): number {
  const parsed = Number(String(value ?? "0").replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

/**
 * 后端把 calibration 放在余额分析信封顶层（`_with_balance_analysis_response_context`），
 * `result` payload 为 `extra=forbid`、不含该字段；`ApiEnvelope` 契约也未声明顶层
 * calibration，因此这里做运行时读取，供下方合并进 overview。
 */
function readEnvelopeCalibration(envelope: unknown): BalancePageCalibration | null | undefined {
  if (!envelope || typeof envelope !== "object" || !("calibration" in envelope)) {
    return undefined;
  }
  return (envelope as { calibration?: BalancePageCalibration | null }).calibration;
}

function normalizeConcentrationDimensionLabel(value: unknown, kind: "top" | "other" | "unknown") {
  const label = String(value ?? "").trim() || EM_DASH;
  if (kind === "other" && label.toLowerCase() === "other") {
    return "其他";
  }
  if (kind === "unknown" && label.toLowerCase() === "unknown") {
    return "未映射";
  }
  return label;
}

export function yuanAmountToWanString(value: unknown): string {
  if (value === null || value === undefined) {
    return EM_DASH;
  }
  const raw = String(value).trim().replace(/,/g, "");
  if (raw === "") {
    return EM_DASH;
  }
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(raw);
  if (!match) {
    return raw;
  }
  const [, sign, wholePart, fractionPart = ""] = match;
  const digits = `${wholePart}${fractionPart}`.replace(/^0+/, "") || "0";
  if (digits === "0") {
    return "0";
  }
  const scale = fractionPart.length + 4;
  const padded = digits.length <= scale ? `${"0".repeat(scale - digits.length + 1)}${digits}` : digits;
  const pointIndex = padded.length - scale;
  const intPart = padded.slice(0, pointIndex) || "0";
  const fracPart = padded.slice(pointIndex).replace(/0+$/, "");
  return `${sign === "-" ? "-" : ""}${intPart}${fracPart ? `.${fracPart}` : ""}`;
}

function buildMovementBondBusinessTypeTable(
  workbookBondTable: BalanceAnalysisWorkbookTable | undefined,
  months: BalanceBusinessMovementTrendMonth[],
  reportDate: string,
): BalanceAnalysisWorkbookTable | undefined {
  const movementMonth = months.find((month) => month.report_date === reportDate) ?? months[0];
  const movementRows = (movementMonth?.rows ?? [])
    .filter(
      (row) =>
        row.side === "asset" &&
        row.source_kind === "zqtz" &&
        row.row_key.startsWith("asset_zqtz_") &&
        finiteNumber(row.current_balance) !== 0,
    )
    .sort((left, right) => {
      const amountDelta = finiteNumber(right.current_balance) - finiteNumber(left.current_balance);
      return amountDelta === 0 ? left.sort_order - right.sort_order : amountDelta;
    });
  if (movementRows.length === 0) {
    return workbookBondTable;
  }
  return {
    key: "bond_business_types",
    title: workbookBondTable?.title ?? "债券业务种类",
    section_kind: "table",
    columns: workbookBondTable?.columns ?? [
      { key: "bond_type", label: "业务种类" },
      { key: "balance_amount", label: "期末余额" },
    ],
    rows: movementRows.map((row) => ({
      bond_type: String(row.row_label ?? EM_DASH),
      balance_amount: yuanAmountToWanString(row.current_balance),
      source_note: row.source_note,
    })),
  };
}

function buildMovementIndustryDistributionTable(
  workbookIndustryTable: BalanceAnalysisWorkbookTable | undefined,
  concentration: BalanceZqtzConcentrationAnalysis | null | undefined,
): BalanceAnalysisWorkbookTable | undefined {
  const industryDimension = concentration?.dimensions.find(
    (dimension) => dimension.dimension === "industry_name" && dimension.status === "supported",
  );
  if (!industryDimension || industryDimension.items.length === 0) {
    return workbookIndustryTable;
  }
  return {
    key: "industry_distribution",
    title: workbookIndustryTable?.title ?? "行业分布",
    section_kind: "table",
    columns: workbookIndustryTable?.columns ?? [
      { key: "industry_name", label: "行业" },
      { key: "balance_amount", label: "期末余额" },
    ],
    rows: industryDimension.items.map((item) => ({
      industry_name: normalizeConcentrationDimensionLabel(item.dimension_value, item.item_kind),
      balance_amount: yuanAmountToWanString(item.current_amount),
      count: item.item_count,
      share: item.share_pct,
    })),
  };
}

export function buildBalanceDistributionEvidence({
  linked,
  reportDate,
  requestedReportDate,
  meta,
  loading,
  failed,
}: {
  linked: boolean;
  reportDate: string | undefined;
  requestedReportDate: string;
  meta: ResultMeta | undefined;
  loading: boolean;
  failed: boolean;
}) {
  const source = linked ? "余额变动" : "工作簿";
  return {
    source,
    reportDate: reportDate || EM_DASH,
    meta,
    stateSurfaces: buildStateSurfaces([
      { when: loading, key: "loading", variant: "loading", title: "余额变动联动加载中", description: `当前展示${source}数据。` },
      { when: failed, key: "error", variant: "error", title: "余额变动联动读取失败", description: `当前展示${source}数据，请复核来源后使用。` },
      { when: !linked && !loading && !failed, key: "missing", variant: "definition-pending", title: "余额变动联动缺失", description: "当前展示工作簿数据，未使用余额变动覆盖。" },
      { when: !meta, key: "meta-missing", variant: "definition-pending", title: "来源质量待确认", description: "当前分布数据未返回质量元信息。" },
      { when: Boolean(reportDate && reportDate !== requestedReportDate), key: "date", variant: "fallback-date", title: "分布报告日不一致", description: `请求 ${requestedReportDate}，当前分布实际报告日 ${reportDate}。` },
      { when: meta?.quality_flag === "stale", key: "stale", variant: "stale", title: "分布数据陈旧", description: `当前仍展示${source}返回值，请复核新鲜度。` },
      { when: meta?.quality_flag === "warning", key: "partial", variant: "definition-pending", title: "分布质量需复核", description: `${source}返回质量预警，覆盖范围可能不完整。` },
      { when: meta?.quality_flag === "error" || meta?.quality_flag === "missing", key: "quality-error", variant: "error", title: "分布质量异常", description: `${source}标记为错误或缺失，请复核后使用。` },
      { when: meta?.fallback_mode === "latest_snapshot", key: "fallback", variant: "fallback-date", title: "分布使用回退快照", description: `实际报告日 ${reportDate || EM_DASH}。` },
    ]),
  };
}

export function useBalanceAnalysisData({
  summaryOffset,
  eventTypeFilter,
  riskSeverityFilter,
  selectedDecisionKey,
  selectedEventCalendarKey,
  selectedRiskAlertKey,
}: BalanceAnalysisDataParams) {
  const client = useApiClient();
  const [deferredAnalysisQueryKey, setDeferredAnalysisQueryKey] = useState("");

  const datesQuery = useQuery({
    queryKey: ["balance-analysis", "dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });
  const publicationStatusQuery = useQuery({
    queryKey: ["balance-analysis", "publication-status", client.mode],
    queryFn: () => client.getBalanceAnalysisPublicationStatus(),
    retry: false,
  });
  const publicationStatus = publicationStatusQuery.data;
  const availableReportDates = Array.from(
    new Set([
      ...(publicationStatus?.enabled ? publicationStatus.report_dates : []),
      ...(datesQuery.data?.result.report_dates ?? []),
    ]),
  );
  const {
    selectedReportDate,
    unavailableRequestedReportDate,
    isSelectedReportDateAvailable,
    positionScope,
    currencyBasis,
    setSelectedReportDate,
    setPositionScope,
    setCurrencyBasis,
  } = useBalanceAnalysisFilters(availableReportDates);
  const activeAnalysisQueryKey = `${selectedReportDate}|${positionScope}|${currencyBasis}`;
  const overviewGeneration =
    publicationStatus?.enabled &&
    publicationStatus.available &&
    publicationStatus.generation &&
    publicationStatus.report_dates.includes(selectedReportDate)
      ? publicationStatus.generation
      : undefined;
  const overviewServingMode = !publicationStatusQuery.isSuccess
    ? "pending"
    : publicationStatus?.enabled
      ? overviewGeneration
        ? "published"
        : "blocked"
      : "legacy";

  useEffect(() => {
    setDeferredAnalysisQueryKey("");
  }, [activeAnalysisQueryKey]);

  const overviewQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "overview",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
      overviewServingMode,
      overviewGeneration,
    ],
    enabled:
      isSelectedReportDateAvailable &&
      (overviewServingMode === "legacy" || overviewServingMode === "published"),
    queryFn: () =>
      client.getBalanceAnalysisOverview({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
        ...(overviewGeneration ? { generation: overviewGeneration } : {}),
      }),
    retry: false,
  });

  const workbookQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "workbook",
      client.mode,
      selectedReportDate,
      "all",
      currencyBasis,
    ],
    enabled: isSelectedReportDateAvailable,
    queryFn: () =>
      client.getBalanceAnalysisWorkbook({
        reportDate: selectedReportDate,
        positionScope: "all",
        currencyBasis,
      }),
    retry: false,
  });

  const currentUserQuery = useQuery({
    queryKey: ["balance-analysis", "current-user", client.mode],
    queryFn: () => client.getBalanceAnalysisCurrentUser(),
    retry: false,
  });

  const decisionItemsQuery = useQuery({
    queryKey: apiQueryKeys.balanceAnalysisDecisionItems(
      client.mode,
      selectedReportDate,
      "all",
      currencyBasis,
    ),
    enabled: isSelectedReportDateAvailable,
    queryFn: () =>
      client.getBalanceAnalysisDecisionItems({
        reportDate: selectedReportDate,
        positionScope: "all",
        currencyBasis,
      }),
    retry: false,
  });

  const firstScreenQueriesSettled =
    isSelectedReportDateAvailable &&
    !overviewQuery.isLoading &&
    !workbookQuery.isLoading &&
    !decisionItemsQuery.isLoading;

  useEffect(() => {
    if (!isSelectedReportDateAvailable || !firstScreenQueriesSettled) {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      setDeferredAnalysisQueryKey(activeAnalysisQueryKey);
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [activeAnalysisQueryKey, firstScreenQueriesSettled, isSelectedReportDateAvailable]);

  const deferredAnalysisQueriesEnabled =
    isSelectedReportDateAvailable && deferredAnalysisQueryKey === activeAnalysisQueryKey;
  const deferredAnalysisQueriesPending =
    isSelectedReportDateAvailable && !deferredAnalysisQueriesEnabled;

  const detailQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "detail",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
    ],
    enabled: deferredAnalysisQueriesEnabled,
    queryFn: () =>
      client.getBalanceAnalysisDetail({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      }),
    retry: false,
  });

  const summaryQueryEnabled =
    isSelectedReportDateAvailable &&
    (overviewQuery.isSuccess ||
      (publicationStatusQuery.isSuccess &&
        Boolean(publicationStatus?.enabled) &&
        !overviewGeneration));

  const summaryQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "summary-table",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
      summaryOffset,
    ],
    enabled: summaryQueryEnabled,
    queryFn: () =>
      client.getBalanceAnalysisSummary({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
        limit: PAGE_SIZE,
        offset: summaryOffset,
      }),
    retry: false,
  });

  const basisBreakdownQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "summary-by-basis",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
    ],
    enabled: deferredAnalysisQueriesEnabled,
    queryFn: () =>
      client.getBalanceAnalysisSummaryByBasis({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      }),
    retry: false,
  });

  const movementDatesQuery = useQuery({
    queryKey: ["balance-analysis", "movement-dates", client.mode, "CNX"],
    enabled: isSelectedReportDateAvailable,
    queryFn: () => client.getBalanceMovementDates("CNX"),
    retry: false,
  });

  const movementReportDates = movementDatesQuery.data?.result.report_dates ?? [];
  const movementDateAvailable = Boolean(
    selectedReportDate && movementReportDates.includes(selectedReportDate),
  );

  const movementLinkQuery = useQuery({
    queryKey: ["balance-analysis", "movement-link", client.mode, selectedReportDate, "CNX"],
    enabled: deferredAnalysisQueriesEnabled && movementDateAvailable,
    queryFn: () =>
      client.getBalanceMovementAnalysis({
        reportDate: selectedReportDate,
        currencyBasis: "CNX",
      }),
    retry: false,
  });

  const adbStartDate = selectedReportDate ? `${selectedReportDate.slice(0, 4)}-01-01` : "";

  const adbComparisonQuery = useQuery({
    queryKey: ["balance-analysis", "adb-preview", client.mode, selectedReportDate],
    enabled: deferredAnalysisQueriesEnabled,
    queryFn: () => client.getAdbComparison(adbStartDate, selectedReportDate),
    retry: false,
  });

  const advancedAttributionQuery = useQuery({
    queryKey: ["balance-analysis", "advanced-attribution", client.mode, selectedReportDate],
    enabled: deferredAnalysisQueriesEnabled,
    queryFn: () =>
      client.getBalanceAnalysisAdvancedAttribution({
        reportDate: selectedReportDate,
      }),
    retry: false,
  });

  const overviewEnvelope =
    overviewQuery.isSuccess &&
    (overviewServingMode === "legacy" || overviewServingMode === "published")
      ? overviewQuery.data
      : undefined;
  // 把信封顶层 calibration 合并进 overview，页面继续消费 overview?.calibration 即可生效。
  const overview = useMemo(() => {
    const result = overviewEnvelope?.result;
    if (!result || result.currency_basis !== "CNY") {
      return undefined;
    }
    const calibration = result.calibration ?? readEnvelopeCalibration(overviewEnvelope);
    return calibration === undefined ? result : { ...result, calibration };
  }, [overviewEnvelope]);
  const overviewMeta = overviewEnvelope?.result_meta;
  const detailMeta = detailQuery.data?.result_meta;
  const decisionItemsMeta = decisionItemsQuery.data?.result_meta;
  const workbookMeta = workbookQuery.data?.result_meta;
  const summaryMeta = summaryQuery.data?.result_meta;
  const movementMeta = movementLinkQuery.data?.result_meta;
  const currentUser = currentUserQuery.data;
  const decisionItems = decisionItemsQuery.data?.result;
  const workbookResult = workbookQuery.data?.result;
  const workbook = workbookResult?.currency_basis === "CNY" ? workbookResult : undefined;
  const summaryResult = summaryQuery.data?.result;
  const summaryTable = summaryResult?.currency_basis === "CNY" ? summaryResult : undefined;
  const detailResult = detailQuery.data?.result;
  const detail = detailResult?.currency_basis === "CNY" ? detailResult : undefined;
  const detailSummaryRows = detail?.summary ?? [];
  const detailSummaryGridRows = buildBalanceDetailSummaryGridRows(detailSummaryRows);
  const detailGridRows = buildBalanceDetailGridRows(detail?.details ?? []);
  const decisionRows = decisionItems?.rows ?? [];
  const workbookTables = workbook?.tables ?? [];
  const workbookOperationalSections = workbook?.operational_sections ?? [];

  const movementBondBusinessTypeTable = buildMovementBondBusinessTypeTable(
    workbookTables.find((table) => table.key === "bond_business_types"),
    movementLinkQuery.data?.result.business_trend_months ?? [],
    selectedReportDate,
  );
  const isBondBusinessLinkedToMovement =
    movementBondBusinessTypeTable !== undefined &&
    movementBondBusinessTypeTable !== workbookTables.find((table) => table.key === "bond_business_types");
  const movementIndustryTable = buildMovementIndustryDistributionTable(
    workbookTables.find((table) => table.key === "industry_distribution"),
    movementLinkQuery.data?.result.zqtz_concentration_analysis,
  );
  const isIndustryLinkedToMovement =
    movementIndustryTable !== undefined &&
    movementLinkQuery.data?.result.zqtz_concentration_analysis?.dimensions.some(
      (dimension) =>
        dimension.dimension === "industry_name" &&
        dimension.status === "supported" &&
        dimension.items.length > 0,
    );

  const movementMonth = movementLinkQuery.data?.result.business_trend_months?.find(
    (month) => month.report_date === selectedReportDate,
  ) ?? movementLinkQuery.data?.result.business_trend_months?.[0];
  const distributionEvidence = {
    bond_business_types: buildBalanceDistributionEvidence({
      linked: isBondBusinessLinkedToMovement,
      reportDate: isBondBusinessLinkedToMovement ? movementMonth?.report_date : workbook?.report_date,
      requestedReportDate: selectedReportDate,
      meta: isBondBusinessLinkedToMovement ? movementMeta : workbookMeta,
      loading: deferredAnalysisQueriesPending || movementDatesQuery.isLoading || (movementDateAvailable && movementLinkQuery.isLoading),
      failed: movementDatesQuery.isError || movementLinkQuery.isError,
    }),
    industry_distribution: buildBalanceDistributionEvidence({
      linked: Boolean(isIndustryLinkedToMovement),
      reportDate: isIndustryLinkedToMovement
        ? movementLinkQuery.data?.result.zqtz_concentration_analysis?.meta.report_date
        : workbook?.report_date,
      requestedReportDate: selectedReportDate,
      meta: isIndustryLinkedToMovement ? movementMeta : workbookMeta,
      loading: deferredAnalysisQueriesPending || movementDatesQuery.isLoading || (movementDateAvailable && movementLinkQuery.isLoading),
      failed: movementDatesQuery.isError || movementLinkQuery.isError,
    }),
  };

  const primaryWorkbookTables = primaryWorkbookTableKeys
    .map((tableKey) =>
      tableKey === "bond_business_types"
        ? movementBondBusinessTypeTable
        : workbookTables.find((table) => table.key === tableKey),
    )
    .filter((table): table is BalanceAnalysisWorkbookTable => table !== undefined);

  const secondaryWorkbookPanelTables = secondaryWorkbookPanelKeys
    .map((tableKey) =>
      tableKey === "industry_distribution"
        ? movementIndustryTable
        : workbookTables.find((table) => table.key === tableKey),
    )
    .filter((table): table is BalanceAnalysisWorkbookTable => table !== undefined);

  const rightRailWorkbookTables = workbookOperationalSections.filter((table) =>
    rightRailWorkbookKeys.includes(table.section_kind as (typeof rightRailWorkbookKeys)[number]),
  );

  const eventTypeOptions = Array.from(
    new Set(
      rightRailWorkbookTables
        .filter(
          (
            table,
          ): table is Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "event_calendar" }> =>
            table.section_kind === "event_calendar",
        )
        .flatMap((table) => table.rows.map((row) => row.event_type)),
    ),
  );

  const filteredRightRailWorkbookTables = rightRailWorkbookTables.map((table) => {
    if (table.section_kind === "event_calendar") {
      return {
        ...table,
        rows:
          eventTypeFilter === "all"
            ? table.rows
            : table.rows.filter((row) => row.event_type === eventTypeFilter),
      };
    }
    if (table.section_kind === "risk_alerts") {
      return {
        ...table,
        rows:
          riskSeverityFilter === "all"
            ? table.rows
            : table.rows.filter((row) => row.severity === riskSeverityFilter),
      };
    }
    return table;
  });

  const eventCalendarRows = workbookOperationalSections
    .filter(
      (
        table,
      ): table is Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "event_calendar" }> =>
        table.section_kind === "event_calendar",
    )
    .flatMap((table) => table.rows);
  const riskAlertRows = workbookOperationalSections
    .filter(
      (
        table,
      ): table is Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "risk_alerts" }> =>
        table.section_kind === "risk_alerts",
    )
    .flatMap((table) => table.rows);
  const workbookDecisionRows = workbookOperationalSections
    .filter(
      (
        table,
      ): table is Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "decision_items" }> =>
        table.section_kind === "decision_items",
    )
    .flatMap((table) => table.rows);

  const selectedDecision = decisionRows.find((row) => row.decision_key === selectedDecisionKey);
  const selectedEventCalendar = rightRailWorkbookTables
    .filter(
      (
        table,
      ): table is Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "event_calendar" }> =>
        table.section_kind === "event_calendar",
    )
    .flatMap((table) => table.rows)
    .find((row) => `${row.event_date}:${row.title}` === selectedEventCalendarKey);
  const selectedRiskAlert = rightRailWorkbookTables
    .filter(
      (
        table,
      ): table is Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "risk_alerts" }> =>
        table.section_kind === "risk_alerts",
    )
    .flatMap((table) => table.rows)
    .find((row) => `${row.severity}:${row.title}` === selectedRiskAlertKey);

  const totalPages = Math.max(
    1,
    Math.ceil((summaryTable?.total_rows ?? 0) / (summaryTable?.limit ?? PAGE_SIZE)),
  );
  const currentPage = Math.floor(summaryOffset / (summaryTable?.limit ?? PAGE_SIZE)) + 1;

  return {
    datesQuery,
    publicationStatusQuery,
    publicationStatus,
    availableReportDates,
    overviewGeneration,
    overviewServingMode,
    selectedReportDate,
    unavailableRequestedReportDate,
    isSelectedReportDateAvailable,
    positionScope,
    currencyBasis,
    setSelectedReportDate,
    setPositionScope,
    setCurrencyBasis,
    overviewQuery,
    detailQuery,
    workbookQuery,
    currentUserQuery,
    decisionItemsQuery,
    summaryQuery,
    basisBreakdownQuery,
    adbComparisonQuery,
    advancedAttributionQuery,
    movementDatesQuery,
    movementLinkQuery,
    overview,
    overviewMeta,
    detailMeta,
    decisionItemsMeta,
    workbookMeta,
    summaryMeta,
    movementMeta,
    distributionEvidence,
    currentUser,
    decisionRows,
    workbook,
    summaryTable,
    detailSummaryRows,
    workbookTables,
    workbookOperationalSections,
    primaryWorkbookTables,
    secondaryWorkbookPanelTables,
    rightRailWorkbookTables,
    filteredRightRailWorkbookTables,
    eventTypeOptions,
    eventCalendarRows,
    riskAlertRows,
    workbookDecisionRows,
    detailSummaryGridRows,
    detailGridRows,
    selectedDecision,
    selectedEventCalendar,
    selectedRiskAlert,
    movementBondBusinessTypeTable,
    movementIndustryTable,
    isBondBusinessLinkedToMovement,
    isIndustryLinkedToMovement,
    movementReportDates,
    movementDateAvailable,
    deferredAnalysisQueriesEnabled,
    deferredAnalysisQueriesPending,
    firstScreenQueriesSettled,
    totalPages,
    currentPage,
    adbHref: selectedReportDate ? `/average-balance?report_date=${selectedReportDate}` : "/average-balance",
    PAGE_SIZE,
  };
}
