import type {
  MarketFundingObservation,
  MarketObservationEvidence,
  MarketRatesObservation,
} from "../api/contracts/marketMacro";

// Explicit mock observations, not calculations or a fallback for real API data.
const dr007: MarketObservationEvidence = {
  key: "dr007", label: "DR007", series_id: "CA.DR007", value: 1.52, unit: "%",
  observation_date: "2026-09-02", source: "mock", quality_flag: "ok", fallback_mode: "none",
  is_proxy: false, previous_value: 1.54, previous_date: "2026-08-29", change_bp: -2,
  status: "ok", reason: null,
  recent_points: [{ trade_date: "2026-08-29", value_numeric: 1.54 }, { trade_date: "2026-09-02", value_numeric: 1.52 }],
};
const shibor: MarketObservationEvidence = {
  key: "shibor_3m", label: "SHIBOR 3M", series_id: "NCD.SHIBOR.3M", value: 1.56, unit: "%",
  observation_date: "2026-09-02", source: "mock", quality_flag: "ok", fallback_mode: "none",
  is_proxy: true, previous_value: 1.55, previous_date: "2026-08-29", change_bp: 1,
  status: "ok", reason: "期限报价参考，不是同业存单收益率。",
  recent_points: [{ trade_date: "2026-08-29", value_numeric: 1.55 }, { trade_date: "2026-09-02", value_numeric: 1.56 }],
};
const gov2: MarketObservationEvidence = {
  key: "gov_2y", label: "2年国债", series_id: "EMM00588704", value: 1.67, unit: "%", tenor_years: 2,
  observation_date: "2026-09-02", source: "mock", quality_flag: "ok", fallback_mode: "none", is_proxy: false,
  previous_value: 1.65, previous_date: "2026-08-29", change_bp: 2, status: "ok", reason: null,
  recent_points: [{ trade_date: "2026-08-29", value_numeric: 1.65 }, { trade_date: "2026-09-02", value_numeric: 1.67 }],
};
const gov5: MarketObservationEvidence = {
  key: "gov_5y", label: "5年国债", series_id: "EMM00166462", value: 1.96, unit: "%", tenor_years: 5,
  observation_date: "2026-09-02", source: "mock", quality_flag: "ok", fallback_mode: "none", is_proxy: false,
  previous_value: 1.94, previous_date: "2026-08-29", change_bp: 2, status: "ok", reason: null,
  recent_points: [{ trade_date: "2026-08-29", value_numeric: 1.94 }, { trade_date: "2026-09-02", value_numeric: 1.96 }],
};
const gov10: MarketObservationEvidence = {
  key: "gov_10y", label: "10年国债", series_id: "E1000180", value: 2.14, unit: "%", tenor_years: 10,
  observation_date: "2026-09-02", source: "mock", quality_flag: "ok", fallback_mode: "none", is_proxy: false,
  previous_value: 2.13, previous_date: "2026-08-29", change_bp: 1, status: "ok", reason: null,
  recent_points: [{ trade_date: "2026-08-29", value_numeric: 2.13 }, { trade_date: "2026-09-02", value_numeric: 2.14 }],
};

export const MOCK_FUNDING_OBSERVATION: MarketFundingObservation = {
  status: "ok", judgment_allowed: true, observation_date: "2026-09-02", comparison_date: "2026-08-29",
  summary: "DR007较8月29日回落2 bp，仍高于有效政策基准12 bp。",
  interpretation: "所示回购资金价格回落；本行融资成本是否同步变化，仍需实际融资数据核验。",
  limitations: ["合成演示数据。", "SHIBOR 3M仅作期限报价参考。"], reason: null,
  rule_version: "rv_market_funding_observation_mock_v1", evidence: [dr007, shibor], rows: [dr007, shibor],
  verification_route: "/market-data", window_label: "近20期",
  policy_reference: {
    value: 1.4, unit: "%", effective_from: "2026-09-01", effective_to: null,
    validity_status: "verified", source: "mock", reason: null,
  },
  policy_deviation_bp: 12,
};

export const MOCK_RATES_OBSERVATION: MarketRatesObservation = {
  status: "ok", judgment_allowed: true, observation_date: "2026-09-02", comparison_date: "2026-08-29",
  summary: "2年、5年收益率各上行2 bp，10年上行1 bp；10年与2年期限利差收窄1 bp。",
  interpretation: "短中端上行幅度大于长端；组合影响需在明确冲击假设下查看。",
  limitations: ["合成演示数据。", "比较日为共同观测日，不宣称前一交易日。"], reason: null,
  rule_version: "rv_market_rates_observation_mock_v1", evidence: [gov2, gov5, gov10], rows: [gov2, gov5, gov10],
  verification_route: "/market-data", window_label: "近20期", curve_family: "国债", full_curve_comparison_allowed: true,
  spreads: [
    { key: "term_10y_2y", label: "10年减2年", value_bp: 47, previous_value_bp: 48, change_bp: -1,
      observation_date: "2026-09-02", comparison_date: "2026-08-29", status: "ok", reason: null, input_keys: ["gov_10y", "gov_2y"] },
    { key: "term_10y_5y", label: "10年减5年", value_bp: 18, previous_value_bp: 19, change_bp: -1,
      observation_date: "2026-09-02", comparison_date: "2026-08-29", status: "ok", reason: null, input_keys: ["gov_10y", "gov_5y"] },
  ],
};
