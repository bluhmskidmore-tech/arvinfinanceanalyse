import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type {
  BalanceAnalysisSeverity,
  BalanceAnalysisWorkbookOperationalSection,
  BalanceAnalysisWorkbookTable,
  BalanceBusinessMovementTrendMonth,
  BalanceZqtzConcentrationAnalysis,
} from "../../../api/contracts";
import { buildBalanceDetailGridRows, buildBalanceDetailSummaryGridRows } from "../pages/balanceAnalysisGridRows";
import { useBalanceAnalysisFilters } from "./useBalanceAnalysisFilters";

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

function normalizeConcentrationDimensionLabel(value: unknown, kind: "top" | "other" | "unknown") {
  const label = String(value ?? "").trim() || "—";
  if (kind === "other" && label.toLowerCase() === "other") {
    return "其他";
  }
  if (kind === "unknown" && label.toLowerCase() === "unknown") {
    return "未映射";
  }
  return label;
}

function yuanAmountToWanString(value: unknown) {
  const raw = String(value ?? "0").trim().replace(/,/g, "");
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
      bond_type: String(row.row_label ?? "—"),
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
  const {
    selectedReportDate,
    positionScope,
    currencyBasis,
    setSelectedReportDate,
    setPositionScope,
    setCurrencyBasis,
  } = useBalanceAnalysisFilters(datesQuery.data?.result.report_dates ?? []);
  const activeAnalysisQueryKey = `${selectedReportDate}|${positionScope}|${currencyBasis}`;

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
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisOverview({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      }),
    retry: false,
  });

  const workbookQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "workbook",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisWorkbook({
        reportDate: selectedReportDate,
        positionScope,
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
    queryKey: [
      "balance-analysis",
      "decision-items",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisDecisionItems({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      }),
    retry: false,
  });

  const firstScreenQueriesSettled =
    Boolean(selectedReportDate) &&
    !overviewQuery.isLoading &&
    !workbookQuery.isLoading &&
    !decisionItemsQuery.isLoading;

  useEffect(() => {
    if (!selectedReportDate || !firstScreenQueriesSettled) {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      setDeferredAnalysisQueryKey(activeAnalysisQueryKey);
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [activeAnalysisQueryKey, firstScreenQueriesSettled, selectedReportDate]);

  const deferredAnalysisQueriesEnabled =
    Boolean(selectedReportDate) && deferredAnalysisQueryKey === activeAnalysisQueryKey;
  const deferredAnalysisQueriesPending =
    Boolean(selectedReportDate) && !deferredAnalysisQueriesEnabled;

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

  const summaryQueryEnabled = Boolean(selectedReportDate) && overviewQuery.isSuccess;

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
    enabled: Boolean(selectedReportDate),
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

  const overview = overviewQuery.data?.result;
  const overviewMeta = overviewQuery.data?.result_meta;
  const detailMeta = detailQuery.data?.result_meta;
  const decisionItemsMeta = decisionItemsQuery.data?.result_meta;
  const workbookMeta = workbookQuery.data?.result_meta;
  const summaryMeta = summaryQuery.data?.result_meta;
  const currentUser = currentUserQuery.data;
  const decisionItems = decisionItemsQuery.data?.result;
  const workbook = workbookQuery.data?.result;
  const summaryTable = summaryQuery.data?.result;
  const detailSummaryGridRows = buildBalanceDetailSummaryGridRows(detailQuery.data?.result.summary ?? []);
  const detailGridRows = buildBalanceDetailGridRows(detailQuery.data?.result.details ?? []);
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
    (movementLinkQuery.data?.result.business_trend_months ?? []).some(
      (month) =>
        month.report_date === selectedReportDate &&
        month.rows.some(
          (row) =>
            row.side === "asset" &&
            row.source_kind === "zqtz" &&
            row.row_key.startsWith("asset_zqtz_") &&
            finiteNumber(row.current_balance) !== 0,
        ),
    );
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
    selectedReportDate,
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
    currentUser,
    decisionRows,
    workbook,
    summaryTable,
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
