import { type PnlByBusinessAnalysisDimension } from "../../api/contracts";

export const ANALYSIS_DIMENSION_LABELS: Record<PnlByBusinessAnalysisDimension, string> = {
  monthly: "月份",
  portfolio: "组合",
  accounting: "会计分类",
  currency: "原币种",
  cost_center: "成本中心",
  instrument: "资产明细",
  bond_bucket: "投资资产四类",
  bond_bucket_monthly: "四类月度",
};

export const MAIN_BREAKDOWN_DIMENSION_LABELS = {
  currency: "原币种",
  accounting: "会计分类",
  portfolio: "投资组合",
  cost_center: "成本中心",
  instrument: "资产明细",
} as const;

export type MainBreakdownDimension = keyof typeof MAIN_BREAKDOWN_DIMENSION_LABELS;
