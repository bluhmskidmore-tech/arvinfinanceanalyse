/**
 * Mock payloads for the Campisi attribution domain.
 * Extracted from client.ts to reduce monolith size.
 */
import type {
  CampisiFourEffectsPayload,
  CampisiEnhancedPayload,
  CampisiMaturityBucketsPayload,
} from "../api/contracts";

export const mockCampisiFourEffects: CampisiFourEffectsPayload = {
  report_date: "2026-03-31",
  period_start: "2026-03-01",
  period_end: "2026-03-31",
  num_days: 30,
  totals: {
    income_return: 820000,
    treasury_effect: -210000,
    spread_effect: 160000,
    selection_effect: 95000,
    total_return: 865000,
    market_value_start: 128000000,
  },
  by_asset_class: [
    {
      asset_class: "政策性金融债",
      market_value_start: 78000000,
      income_return: 520000,
      treasury_effect: -180000,
      spread_effect: 120000,
      selection_effect: 50000,
      total_return: 510000,
      weight_pct: 60.94,
    },
  ],
  by_bond: [
    {
      bond_code: "240001.IB",
      asset_class: "政策性金融债",
      maturity_bucket: "1-3Y",
      market_value_start: 32000000,
      income_return: 210000,
      treasury_effect: -70000,
      spread_effect: 42000,
      selection_effect: 20000,
      total_return: 202000,
      mod_duration: 2.7,
    },
  ],
};

export const mockCampisiEnhanced: CampisiEnhancedPayload = {
  report_date: "2026-03-31",
  period_start: "2026-03-01",
  period_end: "2026-03-31",
  num_days: 30,
  totals: {
    income_return: 820000,
    treasury_effect: -210000,
    spread_effect: 160000,
    convexity_effect: 18000,
    cross_effect: 6000,
    reinvestment_effect: 0,
    selection_effect: 81000,
    total_return: 875000,
    market_value_start: 128000000,
  },
  by_asset_class: [
    {
      asset_class: "政策性金融债",
      market_value_start: 78000000,
      income_return: 520000,
      treasury_effect: -180000,
      spread_effect: 120000,
      convexity_effect: 12000,
      cross_effect: 3000,
      reinvestment_effect: 0,
      selection_effect: 45000,
      total_return: 520000,
      weight_pct: 60.94,
    },
  ],
  by_bond: [
    {
      bond_code: "240001.IB",
      asset_class: "政策性金融债",
      maturity_bucket: "1-3Y",
      market_value_start: 32000000,
      income_return: 210000,
      treasury_effect: -70000,
      spread_effect: 42000,
      convexity_effect: 5000,
      cross_effect: 1000,
      reinvestment_effect: 0,
      selection_effect: 17000,
      total_return: 205000,
      mod_duration: 2.7,
    },
  ],
};

export const mockCampisiMaturityBuckets: CampisiMaturityBucketsPayload = {
  period_start: "2026-03-01",
  period_end: "2026-03-31",
  buckets: {
    "0-1Y": {
      market_value_start: 18000000,
      income_return: 90000,
      treasury_effect: -20000,
      spread_effect: 15000,
      selection_effect: 6000,
      total_return: 91000,
    },
    "1-3Y": {
      market_value_start: 52000000,
      income_return: 330000,
      treasury_effect: -82000,
      spread_effect: 61000,
      selection_effect: 26000,
      total_return: 335000,
    },
  },
};
