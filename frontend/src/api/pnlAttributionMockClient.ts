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
import type { PnlAttributionClientMethods } from "./pnlAttributionClient";

type Delay = () => Promise<void>;

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
