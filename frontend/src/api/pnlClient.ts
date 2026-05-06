/**
 * P&L and Attribution domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { readHttpJsonDetail } from "./httpResponseError";
import type {
  ApiEnvelope,
  AdvancedAttributionSummary,
  CampisiAttributionPayload,
  CampisiEnhancedPayload,
  CampisiFourEffectsPayload,
  CampisiMaturityBucketsPayload,
  CarryRollDownPayload,
  FormalPnlRefreshPayload,
  KRDAttributionPayload,
  LedgerPnlDataPayload,
  LedgerPnlDatesPayload,
  LedgerPnlSummaryPayload,
  PnlAttributionAnalysisSummary,
  PnlAttributionPayload,
  PnlBasis,
  PnlByBusinessAnalysisDimension,
  PnlByBusinessAnalysisPayload,
  PnlByBusinessMonthlyPayload,
  PnlByBusinessPayload,
  PnlByBusinessYtdPayload,
  PnlBridgePayload,
  PnlCompositionPayload,
  PnlDataPayload,
  PnlDatesPayload,
  PnlOverviewPayload,
  PnlV1DataPayload,
  PnlYearlyBusinessSummaryPayload,
  ProductCategoryDatesPayload,
  ProductCategoryAttributionPayload,
  ProductCategoryManualAdjustmentExportPayload,
  ProductCategoryManualAdjustmentListPayload,
  ProductCategoryManualAdjustmentPayload,
  ProductCategoryManualAdjustmentQuery,
  ProductCategoryManualAdjustmentRequest,
  ProductCategoryPnlPayload,
  ProductCategoryRefreshPayload,
  QdbGlMonthlyAnalysisDatesPayload,
  QdbGlMonthlyAnalysisManualAdjustmentExportPayload,
  QdbGlMonthlyAnalysisManualAdjustmentListPayload,
  QdbGlMonthlyAnalysisManualAdjustmentPayload,
  QdbGlMonthlyAnalysisManualAdjustmentRequest,
  QdbGlMonthlyAnalysisScenarioPayload,
  QdbGlMonthlyAnalysisWorkbookExportPayload,
  QdbGlMonthlyAnalysisWorkbookPayload,
  SpreadAttributionPayload,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "./contracts";

type FetchLike = typeof fetch;

type PnlClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

export type PnlClientMethods = {
  getFormalPnlDates: (basis?: PnlBasis) => Promise<ApiEnvelope<PnlDatesPayload>>;
  getFormalPnlData: (date: string, basis?: PnlBasis) => Promise<ApiEnvelope<PnlDataPayload>>;
  getFormalPnlOverview: (
    reportDate: string,
    basis?: PnlBasis,
  ) => Promise<ApiEnvelope<PnlOverviewPayload>>;
  getPnlV1Data: (date: string) => Promise<ApiEnvelope<PnlV1DataPayload>>;
  getLedgerPnlDates: () => Promise<ApiEnvelope<LedgerPnlDatesPayload>>;
  getLedgerPnlData: (
    reportDate: string,
    currency?: string,
  ) => Promise<ApiEnvelope<LedgerPnlDataPayload>>;
  getLedgerPnlSummary: (
    reportDate: string,
    currency?: string,
  ) => Promise<ApiEnvelope<LedgerPnlSummaryPayload>>;
  getPnlByBusiness: (reportDate: string) => Promise<ApiEnvelope<PnlByBusinessPayload>>;
  getPnlByBusinessYtd: (year: number, asOfDate?: string) => Promise<ApiEnvelope<PnlByBusinessYtdPayload>>;
  getPnlByBusinessMonthly: (year: number, asOfDate?: string) => Promise<ApiEnvelope<PnlByBusinessMonthlyPayload>>;
  getPnlByBusinessAnalysis: (options: {
    year: number;
    asOfDate?: string;
    businessKey?: string;
    dimension: PnlByBusinessAnalysisDimension;
  }) => Promise<ApiEnvelope<PnlByBusinessAnalysisPayload>>;
  getPnlYearlyBusinessSummary: (year: number) => Promise<ApiEnvelope<PnlYearlyBusinessSummaryPayload>>;
  getPnlBridge: (reportDate: string) => Promise<ApiEnvelope<PnlBridgePayload>>;
  refreshFormalPnl: (reportDate?: string) => Promise<FormalPnlRefreshPayload>;
  getFormalPnlImportStatus: (runId?: string) => Promise<FormalPnlRefreshPayload>;
  getPnlAttribution: (reportDate?: string) => Promise<ApiEnvelope<PnlAttributionPayload>>;
  getVolumeRateAttribution: (options?: {
    reportDate?: string;
    compareType?: "mom" | "yoy";
  }) => Promise<ApiEnvelope<VolumeRateAttributionPayload>>;
  getTplMarketCorrelation: (options?: {
    months?: number;
  }) => Promise<ApiEnvelope<TPLMarketCorrelationPayload>>;
  getPnlCompositionBreakdown: (options?: {
    reportDate?: string;
    includeTrend?: boolean;
    trendMonths?: number;
  }) => Promise<ApiEnvelope<PnlCompositionPayload>>;
  getPnlAttributionAnalysisSummary: (
    reportDate?: string,
  ) => Promise<ApiEnvelope<PnlAttributionAnalysisSummary>>;
  getPnlCarryRollDown: (reportDate?: string) => Promise<ApiEnvelope<CarryRollDownPayload>>;
  getPnlSpreadAttribution: (options?: {
    reportDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<SpreadAttributionPayload>>;
  getPnlKrdAttribution: (options?: {
    reportDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<KRDAttributionPayload>>;
  getPnlAdvancedAttributionSummary: (
    reportDate?: string,
  ) => Promise<ApiEnvelope<AdvancedAttributionSummary>>;
  getPnlCampisiAttribution: (options?: {
    startDate?: string;
    endDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<CampisiAttributionPayload>>;
  getPnlCampisiFourEffects: (options?: {
    startDate?: string;
    endDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<CampisiFourEffectsPayload>>;
  getPnlCampisiEnhanced: (options?: {
    startDate?: string;
    endDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<CampisiEnhancedPayload>>;
  getPnlCampisiMaturityBuckets: (options?: {
    startDate?: string;
    endDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<CampisiMaturityBucketsPayload>>;
  getProductCategoryDates: () => Promise<ApiEnvelope<ProductCategoryDatesPayload>>;
  refreshProductCategoryPnl: () => Promise<ProductCategoryRefreshPayload>;
  getProductCategoryRefreshStatus: (runId: string) => Promise<ProductCategoryRefreshPayload>;
  createProductCategoryManualAdjustment: (
    payload: ProductCategoryManualAdjustmentRequest,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  getProductCategoryManualAdjustments: (
    reportDate: string,
    options?: ProductCategoryManualAdjustmentQuery,
  ) => Promise<ProductCategoryManualAdjustmentListPayload>;
  exportProductCategoryManualAdjustmentsCsv: (
    reportDate: string,
    options?: ProductCategoryManualAdjustmentQuery,
  ) => Promise<ProductCategoryManualAdjustmentExportPayload>;
  updateProductCategoryManualAdjustment: (
    adjustmentId: string,
    payload: ProductCategoryManualAdjustmentRequest,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  revokeProductCategoryManualAdjustment: (
    adjustmentId: string,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  restoreProductCategoryManualAdjustment: (
    adjustmentId: string,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  getProductCategoryPnl: (options: {
    reportDate: string;
    view: string;
    scenarioRatePct?: string;
  }) => Promise<ApiEnvelope<ProductCategoryPnlPayload>>;
  getProductCategoryAttribution: (options: {
    reportDate: string;
    compare?: "mom" | "yoy";
  }) => Promise<ApiEnvelope<ProductCategoryAttributionPayload>>;
  getQdbGlMonthlyAnalysisDates: () => Promise<ApiEnvelope<QdbGlMonthlyAnalysisDatesPayload>>;
  getQdbGlMonthlyAnalysisWorkbook: (options: {
    reportMonth: string;
  }) => Promise<ApiEnvelope<QdbGlMonthlyAnalysisWorkbookPayload>>;
  exportQdbGlMonthlyAnalysisWorkbookXlsx: (options: {
    reportMonth: string;
  }) => Promise<QdbGlMonthlyAnalysisWorkbookExportPayload>;
  refreshQdbGlMonthlyAnalysis: (options: {
    reportMonth: string;
  }) => Promise<{ status: string; run_id: string; job_name: string; trigger_mode: string; cache_key?: string; report_month?: string }>;
  getQdbGlMonthlyAnalysisRefreshStatus: (runId: string) => Promise<{ status: string; run_id: string; job_name: string; trigger_mode: string; cache_key?: string }>;
  getQdbGlMonthlyAnalysisScenario: (options: {
    reportMonth: string;
    scenarioName: string;
    deviationWarn?: number;
    deviationAlert?: number;
    deviationCritical?: number;
  }) => Promise<ApiEnvelope<QdbGlMonthlyAnalysisScenarioPayload>>;
  createQdbGlMonthlyAnalysisManualAdjustment: (
    payload: QdbGlMonthlyAnalysisManualAdjustmentRequest,
  ) => Promise<QdbGlMonthlyAnalysisManualAdjustmentPayload>;
  updateQdbGlMonthlyAnalysisManualAdjustment: (
    adjustmentId: string,
    payload: QdbGlMonthlyAnalysisManualAdjustmentRequest,
  ) => Promise<QdbGlMonthlyAnalysisManualAdjustmentPayload>;
  revokeQdbGlMonthlyAnalysisManualAdjustment: (
    adjustmentId: string,
  ) => Promise<QdbGlMonthlyAnalysisManualAdjustmentPayload>;
  restoreQdbGlMonthlyAnalysisManualAdjustment: (
    adjustmentId: string,
  ) => Promise<QdbGlMonthlyAnalysisManualAdjustmentPayload>;
  getQdbGlMonthlyAnalysisManualAdjustments: (
    reportMonth: string,
  ) => Promise<QdbGlMonthlyAnalysisManualAdjustmentListPayload>;
  exportQdbGlMonthlyAnalysisManualAdjustmentsCsv: (
    reportMonth: string,
  ) => Promise<QdbGlMonthlyAnalysisManualAdjustmentExportPayload>;
};

type PnlBusinessClientMethods = Pick<
  PnlClientMethods,
  | "getPnlV1Data"
  | "getPnlByBusiness"
  | "getPnlByBusinessYtd"
  | "getPnlByBusinessMonthly"
  | "getPnlByBusinessAnalysis"
  | "getPnlYearlyBusinessSummary"
>;

const delay = async () => new Promise((resolve) => setTimeout(resolve, 40));

export function createMockPnlBusinessClient(): PnlBusinessClientMethods {
  return {
    async getPnlV1Data(date: string) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.v1_data",
        {
          report_date: date,
          source_tables: ["data_input/pnl", "data_input/pnl_514", "data_input/pnl_516", "data_input/pnl_517"],
          rows: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPnlByBusiness(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.by_business",
        {
          report_date: reportDate,
          source_tables: ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"],
          summary: {
            business_count: 0,
            total_pnl: "0.00",
            total_scale_amount: "0.00",
            traced_pnl_row_count: 0,
            untraced_pnl_row_count: 0,
          },
          rows: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPnlByBusinessYtd(year: number, _asOfDate?: string) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.by_business_ytd",
        {
          year,
          period_type: "yearly",
          period_label: `${year}年累计`,
          period_start_date: `${year}-01-01`,
          period_end_date: _asOfDate ?? `${year}-12-31`,
          total_pnl: "0.00",
          source_tables: ["data_input/pnl", "fact_formal_zqtz_balance_daily", "ZQTZ_ASSET_BOND_ROWS"],
          items: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPnlByBusinessMonthly(year: number, _asOfDate?: string) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.by_business_monthly",
        {
          year,
          as_of_date: _asOfDate ?? `${year}-12-31`,
          source_tables: [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
            "ZQTZ_ASSET_BOND_ROWS",
          ],
          months: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPnlByBusinessAnalysis(options) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.by_business_analysis",
        {
          year: options.year,
          as_of_date: options.asOfDate ?? `${options.year}-12-31`,
          business_key: options.businessKey ?? null,
          dimension: options.dimension,
          period_start_date: `${options.year}-01-01`,
          period_end_date: options.asOfDate ?? `${options.year}-12-31`,
          source_tables: [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
            "ZQTZ_ASSET_BOND_ROWS",
          ],
          rows: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPnlYearlyBusinessSummary(year: number) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.yearly_summary",
        {
          year,
          source_tables: ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"],
          rows: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
  };
}

export function createRealPnlBusinessClient({
  fetchImpl,
  baseUrl,
}: PnlClientFactoryOptions): PnlBusinessClientMethods {
  return {
    getPnlV1Data: (date: string) =>
      requestJson<PnlV1DataPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/v1-data?date=${encodeURIComponent(date)}`,
      ),
    getPnlByBusiness: (reportDate: string) =>
      requestJson<PnlByBusinessPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getPnlByBusinessYtd: (year: number, asOfDate?: string) => {
      const query = new URLSearchParams({ year: String(year) });
      if (asOfDate) {
        query.set("as_of_date", asOfDate);
      }
      return requestJson<PnlByBusinessYtdPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business-ytd?${query.toString()}`,
      );
    },
    getPnlByBusinessMonthly: (year: number, asOfDate?: string) => {
      const query = new URLSearchParams({ year: String(year) });
      if (asOfDate) {
        query.set("as_of_date", asOfDate);
      }
      return requestJson<PnlByBusinessMonthlyPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business-monthly?${query.toString()}`,
      );
    },
    getPnlByBusinessAnalysis: (options) => {
      const query = new URLSearchParams({
        year: String(options.year),
        dimension: options.dimension,
      });
      if (options.asOfDate) {
        query.set("as_of_date", options.asOfDate);
      }
      if (options.businessKey) {
        query.set("business_key", options.businessKey);
      }
      return requestJson<PnlByBusinessAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business-analysis?${query.toString()}`,
      );
    },
    getPnlYearlyBusinessSummary: (year: number) =>
      requestJson<PnlYearlyBusinessSummaryPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/yearly-summary?year=${encodeURIComponent(String(year))}`,
      ),
  };
}

async function requestJson<TData>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<TData>> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<TData>;
}
