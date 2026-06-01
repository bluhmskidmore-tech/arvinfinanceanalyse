import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import {
  mockAdvancedAttributionSummary,
  mockCampisiAttribution,
  mockCarryRollDown,
  mockKrdAttribution,
  mockPnlAttributionAnalysisSummary,
  mockPnlComposition,
  mockSpreadAttribution,
  mockTplMarketCorrelation,
  mockVolumeRateAttribution,
} from "../mocks/pnlAttributionWorkbench";
import {
  mockCampisiEnhanced,
  mockCampisiFourEffects,
  mockCampisiMaturityBuckets,
} from "../mocks/campisiMocks";
import { pnlAttributionPayload } from "../mocks/workbench";
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
type Delay = () => Promise<void>;

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
  getPnlCampisiFourEffects: (options?: CampisiOptions) => Promise<ApiEnvelope<CampisiFourEffectsPayload>>;
  getPnlCampisiEnhanced: (options?: CampisiOptions) => Promise<ApiEnvelope<CampisiEnhancedPayload>>;
  getPnlCampisiMaturityBuckets: (options?: CampisiOptions) => Promise<ApiEnvelope<CampisiMaturityBucketsPayload>>;
};

export type PnlAttributionClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
};

function buildCampisiQuery(options?: CampisiOptions) {
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
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function createDemoPnlAttributionClient(delay: Delay): PnlAttributionClientMethods {
  return {
    async getPnlAttribution(_reportDate?: string) {
      await delay();
      return buildMockApiEnvelope("executive.pnl-attribution", pnlAttributionPayload);
    },
    async getVolumeRateAttribution(options) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.volume_rate", {
        ...mockVolumeRateAttribution,
        compare_type: options?.compareType ?? mockVolumeRateAttribution.compare_type,
      });
    },
    async getTplMarketCorrelation(_options) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.tpl_market", mockTplMarketCorrelation);
    },
    async getPnlCompositionBreakdown(_options) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.composition", mockPnlComposition);
    },
    async getPnlAttributionAnalysisSummary(_reportDate) {
      await delay();
      return buildMockApiEnvelope(
        "pnl_attribution.summary",
        mockPnlAttributionAnalysisSummary,
      );
    },
    async getPnlCarryRollDown(_reportDate) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.carry_rolldown", mockCarryRollDown);
    },
    async getPnlSpreadAttribution(_options) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.spread", mockSpreadAttribution);
    },
    async getPnlKrdAttribution(_options) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.krd", mockKrdAttribution);
    },
    async getPnlAdvancedAttributionSummary(_reportDate) {
      await delay();
      return buildMockApiEnvelope(
        "pnl_attribution.advanced_summary",
        mockAdvancedAttributionSummary,
      );
    },
    async getPnlCampisiAttribution(_options) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.campisi", mockCampisiAttribution);
    },
    async getPnlCampisiFourEffects(_options) {
      await delay();
      return buildMockApiEnvelope("campisi.four_effects", mockCampisiFourEffects, {
        basis: "formal",
        formal_use_allowed: true,
      });
    },
    async getPnlCampisiEnhanced(_options) {
      await delay();
      return buildMockApiEnvelope("campisi.enhanced", mockCampisiEnhanced, {
        basis: "formal",
        formal_use_allowed: true,
      });
    },
    async getPnlCampisiMaturityBuckets(_options) {
      await delay();
      return buildMockApiEnvelope("campisi.maturity_buckets", mockCampisiMaturityBuckets, {
        basis: "formal",
        formal_use_allowed: true,
      });
    },
  };
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
