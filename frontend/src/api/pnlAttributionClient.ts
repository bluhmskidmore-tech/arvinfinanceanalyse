import type {
  AdvancedAttributionSummary,
  ApiEnvelope,
  CampisiAttributionPayload,
  CampisiEnhancedPayload,
  CampisiFourEffectsPayload,
  CampisiMaturityBucketsPayload,
  CarryRollDownPayload,
  KRDAttributionPayload,
  PnlAttributionAnalysisSummary,
  PnlAttributionPayload,
  PnlCompositionPayload,
  SpreadAttributionPayload,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "./contracts";

type FetchLike = typeof fetch;

type RequestJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
) => Promise<ApiEnvelope<T>>;

type AttributionOptions = {
  reportDate?: string;
  lookbackDays?: number;
};

type CampisiOptions = {
  startDate?: string;
  endDate?: string;
  lookbackDays?: number;
};

export type PnlAttributionClientMethods = {
  getPnlAttribution: (reportDate?: string) => Promise<ApiEnvelope<PnlAttributionPayload>>;
  getVolumeRateAttribution: (options?: {
    reportDate?: string;
    compareType?: "mom" | "yoy";
  }) => Promise<ApiEnvelope<VolumeRateAttributionPayload>>;
  getTplMarketCorrelation: (options?: {
    months?: number;
    reportDate?: string;
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
  getPnlSpreadAttribution: (options?: AttributionOptions) => Promise<ApiEnvelope<SpreadAttributionPayload>>;
  getPnlKrdAttribution: (options?: AttributionOptions) => Promise<ApiEnvelope<KRDAttributionPayload>>;
  getPnlAdvancedAttributionSummary: (
    reportDate?: string,
  ) => Promise<ApiEnvelope<AdvancedAttributionSummary>>;
  getPnlCampisiAttribution: (options?: CampisiOptions) => Promise<ApiEnvelope<CampisiAttributionPayload>>;
  getPnlCampisiFourEffects: (
    options?: CampisiOptions & { detail?: "full" | "summary" },
  ) => Promise<ApiEnvelope<CampisiFourEffectsPayload>>;
  getPnlCampisiEnhanced: (options?: CampisiOptions) => Promise<ApiEnvelope<CampisiEnhancedPayload>>;
  getPnlCampisiMaturityBuckets: (options?: CampisiOptions) => Promise<ApiEnvelope<CampisiMaturityBucketsPayload>>;
};

export type PnlAttributionClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
};

function buildCampisiQuery(options?: CampisiOptions & { detail?: "full" | "summary" }) {
  const params = new URLSearchParams();
  if (options?.startDate?.trim()) {
    params.set("start_date", options.startDate.trim());
  }
  if (options?.endDate?.trim()) {
    params.set("end_date", options.endDate.trim());
  }
  if (Number.isFinite(options?.lookbackDays)) {
    params.set("lookback_days", String(options?.lookbackDays));
  }
  if (options?.detail) {
    params.set("detail", options.detail);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function createRealPnlAttributionClient({
  fetchImpl,
  baseUrl,
  requestJson,
}: PnlAttributionClientFactoryOptions): PnlAttributionClientMethods {
  return {
    getPnlAttribution: (reportDate?: string) =>
      requestJson<PnlAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/attribution${reportDate?.trim() ? `?report_date=${encodeURIComponent(reportDate.trim())}` : ""}`,
      ),
    getVolumeRateAttribution: (options) => {
      const params = new URLSearchParams();
      if (options?.reportDate?.trim()) {
        params.set("report_date", options.reportDate.trim());
      }
      if (options?.compareType) {
        params.set("compare_type", options.compareType);
      }
      const q = params.toString();
      return requestJson<VolumeRateAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/volume-rate${q ? `?${q}` : ""}`,
      );
    },
    getTplMarketCorrelation: (options) => {
      const params = new URLSearchParams();
      if (options?.months !== undefined) {
        params.set("months", String(options.months));
      }
      if (options?.reportDate?.trim()) {
        params.set("report_date", options.reportDate.trim());
      }
      const q = params.toString();
      return requestJson<TPLMarketCorrelationPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/tpl-market${q ? `?${q}` : ""}`,
      );
    },
    getPnlCompositionBreakdown: (options) => {
      const params = new URLSearchParams();
      if (options?.reportDate?.trim()) {
        params.set("report_date", options.reportDate.trim());
      }
      if (options?.includeTrend === false) {
        params.set("include_trend", "false");
      }
      if (options?.trendMonths !== undefined) {
        params.set("trend_months", String(options.trendMonths));
      }
      const q = params.toString();
      return requestJson<PnlCompositionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/composition${q ? `?${q}` : ""}`,
      );
    },
    getPnlAttributionAnalysisSummary: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<PnlAttributionAnalysisSummary>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/summary${q ? `?${q}` : ""}`,
      );
    },
    getPnlCarryRollDown: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<CarryRollDownPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/carry-rolldown${q ? `?${q}` : ""}`,
      );
    },
    getPnlSpreadAttribution: (options) => {
      const params = new URLSearchParams();
      if (options?.reportDate?.trim()) {
        params.set("report_date", options.reportDate.trim());
      }
      if (options?.lookbackDays !== undefined) {
        params.set("lookback_days", String(options.lookbackDays));
      }
      const q = params.toString();
      return requestJson<SpreadAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/spread${q ? `?${q}` : ""}`,
      );
    },
    getPnlKrdAttribution: (options) => {
      const params = new URLSearchParams();
      if (options?.reportDate?.trim()) {
        params.set("report_date", options.reportDate.trim());
      }
      if (options?.lookbackDays !== undefined) {
        params.set("lookback_days", String(options.lookbackDays));
      }
      const q = params.toString();
      return requestJson<KRDAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/krd${q ? `?${q}` : ""}`,
      );
    },
    getPnlAdvancedAttributionSummary: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<AdvancedAttributionSummary>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/summary${q ? `?${q}` : ""}`,
      );
    },
    getPnlCampisiAttribution: (options) => {
      const q = buildCampisiQuery(options);
      return requestJson<CampisiAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/campisi${q}`,
      );
    },
    getPnlCampisiFourEffects: (options) =>
      requestJson<CampisiFourEffectsPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/campisi/four-effects${buildCampisiQuery(options)}`,
      ),
    getPnlCampisiEnhanced: (options) =>
      requestJson<CampisiEnhancedPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/campisi/enhanced${buildCampisiQuery(options)}`,
      ),
    getPnlCampisiMaturityBuckets: (options) =>
      requestJson<CampisiMaturityBucketsPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/campisi/maturity-buckets${buildCampisiQuery(options)}`,
      ),
  };
}
