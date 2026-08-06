/** Liability / ADB domain contracts moved out of the shared API contract barrel. */
import type { Numeric } from "./contracts";

export type LiabilityBucketAmountItem = {
  bucket: string;
  amount?: Numeric | null;
  amount_yi?: Numeric | null;
};

export type LiabilityNameAmountItem = {
  name: string;
  amount?: Numeric | null;
  amount_yi?: Numeric | null;
};

export type LiabilityRiskBucketsPayload = {
  report_date: string;
  liabilities_structure: LiabilityNameAmountItem[];
  liabilities_term_buckets: LiabilityBucketAmountItem[];
  interbank_liabilities_structure?: LiabilityNameAmountItem[];
  interbank_liabilities_term_buckets?: LiabilityBucketAmountItem[];
  issued_liabilities_structure?: LiabilityNameAmountItem[];
  issued_liabilities_term_buckets?: LiabilityBucketAmountItem[];
};

export type LiabilityNimStress = {
  nim_stressed: Numeric | null;
  delta_bp: Numeric | null;
};

export type LiabilityYieldKpi = {
  asset_yield: Numeric | null;
  liability_cost: Numeric | null;
  market_liability_cost: Numeric | null;
  nim: Numeric | null;
  nim_stress?: LiabilityNimStress | null;
};

export type LiabilityYieldHistoryPoint = {
  date: string;
  asset_yield: number | null;
  liability_cost: number | null;
  market_liability_cost: number | null;
  nim: number | null;
};

export type LiabilityYieldScatterPoint = {
  x: number;
  y: number;
  z: number;
  name: string;
};

export type LiabilityYieldMetricsPayload = {
  report_date: string;
  kpi: LiabilityYieldKpi;
  history?: LiabilityYieldHistoryPoint[];
  scatter?: LiabilityYieldScatterPoint[];
};

export type LiabilityCounterpartyItem = {
  name: string;
  value?: Numeric | null;
  type: string;
  weighted_cost?: Numeric | null;
};

export type LiabilityCounterpartyTypeSlice = {
  name: string;
  value?: Numeric | null;
};

export type LiabilityCounterpartyPayload = {
  report_date: string;
  total_value: Numeric;
  top10_share: Numeric | null;
  hhi: Numeric | null;
  population_count: number;
  is_truncated: boolean;
  top_10: LiabilityCounterpartyItem[];
  by_type: LiabilityCounterpartyTypeSlice[];
};

export type LiabilityKnowledgeNote = {
  id: string;
  title: string;
  summary: string;
  why_it_matters: string;
  key_questions: string[];
  source_path: string;
};

export type LiabilityKnowledgeBriefPayload = {
  page_id: string;
  available: boolean;
  vault_path: string | null;
  status_note: string | null;
  notes: LiabilityKnowledgeNote[];
};

export type LiabilityMonthlyBreakdownRow = {
  category?: string | null;
  bucket?: string | null;
  type?: string | null;
  name?: string | null;
  avg_balance?: Numeric | null;
  avg_value?: Numeric | null;
  proportion?: Numeric | null;
  amount?: Numeric | null;
  pct?: Numeric | null;
  weighted_cost?: Numeric | null;
};

export type LiabilitiesMonthlyItem = {
  month: string;
  month_label: string;
  avg_total_liabilities: Numeric | null;
  avg_interbank_liabilities: Numeric | null;
  avg_issued_liabilities: Numeric | null;
  avg_liability_cost: Numeric | null;
  mom_change: Numeric | null;
  mom_change_pct: Numeric | null;
  top10_share: Numeric | null;
  hhi: Numeric | null;
  population_count: number;
  is_truncated: boolean;
  counterparty_top10?: LiabilityMonthlyBreakdownRow[];
  by_institution_type?: LiabilityMonthlyBreakdownRow[];
  structure_overview?: LiabilityMonthlyBreakdownRow[];
  term_buckets?: LiabilityMonthlyBreakdownRow[];
  interbank_by_type?: LiabilityMonthlyBreakdownRow[];
  interbank_term_buckets?: LiabilityMonthlyBreakdownRow[];
  issued_by_type?: LiabilityMonthlyBreakdownRow[];
  issued_term_buckets?: LiabilityMonthlyBreakdownRow[];
  counterparty_details?: LiabilityMonthlyBreakdownRow[];
  num_days: number;
};

export type LiabilitiesMonthlyPayload = {
  year: number;
  months: LiabilitiesMonthlyItem[];
  ytd_avg_total_liabilities: Numeric | null;
  ytd_avg_liability_cost: Numeric | null;
};
