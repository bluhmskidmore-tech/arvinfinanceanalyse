/**
 * Fixtures for workbench dashboard API samples (tests + demo transport).
 */
import type {
  BondBusinessTypeMetricItem,
  CoreMetricsResult,
  DailyChangesResult,
  Numeric,
} from "../api/contracts";
import { formatRawAsNumeric } from "../utils/format";

export const SAMPLE_DASHBOARD_REPORT_DATE = "2026-03-31";

/** 稳定的「核心指标」result 本体，供信封包裹。 */
export function sampleCoreMetricsResult(overrides?: Partial<CoreMetricsResult>): CoreMetricsResult {
  const zy = (raw: number, signAware: boolean): Numeric =>
    formatRawAsNumeric({ raw, unit: "yi", sign_aware: signAware });

  const top3 = (): Array<{ name: string; amount: string; rate: string }> => [
    { name: "样例 A", amount: "100 亿", rate: "2.50%" },
    { name: "样例 B", amount: "80 亿", rate: "2.62%" },
    { name: "样例 C", amount: "60 亿", rate: "3.05%" },
  ];

  const card = (
    total: number,
    rate: number,
    chAmt: number,
    chPct: number,
  ) => ({
    total_amount: zy(total, false),
    weighted_avg_rate: formatRawAsNumeric({
      raw: rate,
      unit: "pct",
      sign_aware: false,
    }),
    change_amount: zy(chAmt, true),
    change_pct: formatRawAsNumeric({ raw: chPct, unit: "pct", sign_aware: true }),
    top_3_details: top3(),
  });

  const base: CoreMetricsResult = {
    report_date: SAMPLE_DASHBOARD_REPORT_DATE,
    bond_investments: card(8234.56, 0.035, 12.3, 0.0015),
    interbank_assets: card(1456.78, 0.028, -5.2, -0.0036),
    interbank_liabilities: card(2100, 0.031, 8, 0.0039),
  };
  return { ...base, ...overrides };
}

export function sampleDailyChangesResult(overrides?: Partial<DailyChangesResult>): DailyChangesResult {
  const zyi = (raw: number): Numeric =>
    formatRawAsNumeric({ raw, unit: "yi", sign_aware: true });
  const base: DailyChangesResult = {
    report_date: SAMPLE_DASHBOARD_REPORT_DATE,
    periods: [
      {
        period: "day",
        bond_investments_change: zyi(12.3),
        interbank_assets_change: zyi(-5.2),
        interbank_liabilities_change: zyi(8),
        net_change: zyi(15.1),
      },
      {
        period: "week",
        bond_investments_change: zyi(45),
        interbank_assets_change: zyi(-12),
        interbank_liabilities_change: zyi(20),
        net_change: zyi(53),
      },
      {
        period: "month",
        bond_investments_change: zyi(120),
        interbank_assets_change: zyi(-30),
        interbank_liabilities_change: zyi(50),
        net_change: zyi(140),
      },
    ],
  };
  return { ...base, ...overrides };
}

export const sampleBondBusinessTypeMetricRows: BondBusinessTypeMetricItem[] = [
  {
    name: "政策性金融债",
    market_value: "98500000000.00",
    weighted_avg_ytm_pct: "2.72",
    weighted_avg_duration: "3.82",
    duration_source: "formal",
  },
  {
    name: "地方政府债",
    market_value: "82000000000.00",
    weighted_avg_ytm_pct: "2.65",
    weighted_avg_duration: "4.18",
    duration_source: "formal",
  },
  {
    name: "同业存单",
    market_value: "71000000000.00",
    weighted_avg_ytm_pct: "2.68",
    weighted_avg_duration: "0.74",
    duration_source: "formal",
  },
  {
    name: "信用债-企业",
    market_value: "49209000000.00",
    weighted_avg_ytm_pct: "3.41",
    weighted_avg_duration: "2.95",
    duration_source: "formal",
  },
  {
    name: "其他",
    market_value: "28000000000.00",
    weighted_avg_ytm_pct: "2.89",
    weighted_avg_duration: "2.36",
    duration_source: "formal",
  },
];
