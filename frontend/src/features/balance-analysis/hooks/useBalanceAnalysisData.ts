import { useQuery } from "@tanstack/react-query";
import { useApiClient } from "../../../api/client";
import type {
  BalanceAnalysisWorkbookOperationalSection,
  BalanceAnalysisWorkbookTable,
  BalanceCurrencyBasis,
  BalancePositionScope,
} from "../../../api/contracts";

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
  selectedReportDate: string;
  positionScope: BalancePositionScope;
  currencyBasis: BalanceCurrencyBasis;
  summaryOffset: number;
}

export function useBalanceAnalysisData({
  selectedReportDate,
  positionScope,
  currencyBasis,
  summaryOffset,
}: BalanceAnalysisDataParams) {
  const client = useApiClient();

  const datesQuery = useQuery({
    queryKey: ["balance-analysis", "dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });

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

  const detailQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "detail",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisDetail({
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
    enabled: Boolean(selectedReportDate),
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
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisSummaryByBasis({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      }),
    retry: false,
  });

  const adbStartDate = selectedReportDate ? `${selectedReportDate.slice(0, 4)}-01-01` : "";

  const adbComparisonQuery = useQuery({
    queryKey: ["balance-analysis", "adb-preview", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getAdbComparison(adbStartDate, selectedReportDate),
    retry: false,
  });

  const advancedAttributionQuery = useQuery({
    queryKey: ["balance-analysis", "advanced-attribution", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisAdvancedAttribution({
        reportDate: selectedReportDate,
      }),
    retry: false,
  });

  // Derived data
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
  const decisionRows = decisionItems?.rows ?? [];
  const workbookTables = workbook?.tables ?? [];
  const workbookOperationalSections = workbook?.operational_sections ?? [];

  const primaryWorkbookTables = primaryWorkbookTableKeys
    .map((tableKey) => workbookTables.find((table) => table.key === tableKey))
    .filter((table): table is BalanceAnalysisWorkbookTable => table !== undefined);

  const secondaryWorkbookPanelTables = secondaryWorkbookPanelKeys
    .map((tableKey) => workbookTables.find((table) => table.key === tableKey))
    .filter((table): table is BalanceAnalysisWorkbookTable => table !== undefined);

  const rightRailWorkbookTables = workbookOperationalSections.filter((table) =>
    rightRailWorkbookKeys.includes(table.section_kind as (typeof rightRailWorkbookKeys)[number]),
  );

  const eventCalendarRows = workbookOperationalSections
    .filter(
      (table): table is Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "event_calendar" }> =>
        table.section_kind === "event_calendar",
    )
    .flatMap((table) => table.rows);

  const riskAlertRows = workbookOperationalSections
    .filter(
      (table): table is Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "risk_alerts" }> =>
        table.section_kind === "risk_alerts",
    )
    .flatMap((table) => table.rows);

  const workbookDecisionRows = workbookOperationalSections
    .filter(
      (table): table is Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "decision_items" }> =>
        table.section_kind === "decision_items",
    )
    .flatMap((table) => table.rows);

  const secondaryWorkbookTables = workbookTables.filter(
    (table) =>
      !primaryWorkbookTableKeys.includes(table.key as (typeof primaryWorkbookTableKeys)[number]) &&
      !secondaryWorkbookPanelKeys.includes(table.key as (typeof secondaryWorkbookPanelKeys)[number]),
  );

  const totalPages = Math.max(
    1,
    Math.ceil((summaryTable?.total_rows ?? 0) / (summaryTable?.limit ?? PAGE_SIZE)),
  );
  const currentPage = Math.floor(summaryOffset / (summaryTable?.limit ?? PAGE_SIZE)) + 1;

  return {
    // Queries (for refetch, loading, error states)
    datesQuery,
    overviewQuery,
    detailQuery,
    workbookQuery,
    currentUserQuery,
    decisionItemsQuery,
    summaryQuery,
    basisBreakdownQuery,
    adbComparisonQuery,
    advancedAttributionQuery,
    // Derived data
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
    eventCalendarRows,
    riskAlertRows,
    workbookDecisionRows,
    secondaryWorkbookTables,
    totalPages,
    currentPage,
    adbHref: selectedReportDate ? `/average-balance?report_date=${selectedReportDate}` : "/average-balance",
    PAGE_SIZE,
  };
}
