import type {
  AccountingClassAuditItem as ApiAccountingClassAuditItem,
  AccountingClassAuditPayload as ApiAccountingClassAuditPayload,
  ActionAttributionPayload as ApiActionAttributionPayload,
  ActionDetail as ApiActionDetail,
  ActionTypeSummary as ApiActionTypeSummary,
  AssetClassRiskSummary as ApiAssetClassRiskSummary,
  AssetClassBreakdown as ApiAssetClassBreakdown,
  BenchmarkExcessPayload as ApiBenchmarkExcessPayload,
  BondLevelDecomposition as ApiBondLevelDecomposition,
  ConcentrationItem as ApiConcentrationItem,
  ConcentrationMetrics as ApiConcentrationMetrics,
  CreditSpreadAnalysisPayload as ApiCreditSpreadAnalysisPayload,
  CreditSpreadBondDetailRow as ApiCreditSpreadBondDetailRow,
  CreditSpreadDetailBondRow as ApiCreditSpreadDetailBondRow,
  CreditSpreadMigrationPayload as ApiCreditSpreadMigrationPayload,
  CreditSpreadTermStructurePoint as ApiCreditSpreadTermStructurePoint,
  ExcessSourceBreakdown as ApiExcessSourceBreakdown,
  KRDBucket as ApiKRDBucket,
  KRDCurveRiskPayload as ApiKRDCurveRiskPayload,
  KRDScenarioResult as ApiKRDScenarioResult,
  MigrationScenarioResult as ApiMigrationScenarioResult,
  ReturnDecompositionPayload as ApiReturnDecompositionPayload,
  SpreadHistoricalContextPayload as ApiSpreadHistoricalContextPayload,
  SpreadScenarioResult as ApiSpreadScenarioResult,
} from "../../api/contracts";

export type PeriodType = "MoM" | "YTD" | "TTM";

export type AssetClassBreakdown = ApiAssetClassBreakdown;
export type BondLevelDecomposition = ApiBondLevelDecomposition;
export type ReturnDecompositionResponse = ApiReturnDecompositionPayload;

// ExcessSourceBreakdown
export type ExcessSourceBreakdown = ApiExcessSourceBreakdown;
export type BenchmarkExcessResponse = ApiBenchmarkExcessPayload;

// KRD types
export type KRDBucket = ApiKRDBucket;
export type ScenarioResult = ApiKRDScenarioResult;
export type AssetClassRiskSummary = ApiAssetClassRiskSummary;
export type KRDCurveRiskResponse = ApiKRDCurveRiskPayload;

// Credit spread types
export type SpreadScenarioResult = ApiSpreadScenarioResult;
export type MigrationScenarioResult = ApiMigrationScenarioResult;
export type ConcentrationItem = ApiConcentrationItem;
export type ConcentrationMetrics = ApiConcentrationMetrics;
/** Optional per-bond rows for rating×tenor heatmap; server may omit. */
export type CreditSpreadBondDetailRow = ApiCreditSpreadBondDetailRow;
export type CreditSpreadMigrationResponse = ApiCreditSpreadMigrationPayload;
export type CreditSpreadTermStructurePoint = ApiCreditSpreadTermStructurePoint;
export type CreditSpreadDetailBondRow = ApiCreditSpreadDetailBondRow;
export type SpreadHistoricalContext = ApiSpreadHistoricalContextPayload;
export type CreditSpreadAnalysisResponse = ApiCreditSpreadAnalysisPayload;

// Action attribution types
export type ActionTypeSummary = ApiActionTypeSummary;
export type ActionDetail = ApiActionDetail;
export type ActionAttributionResponse = ApiActionAttributionPayload;

// Accounting audit types
export type AccountingClassAuditItem = ApiAccountingClassAuditItem;
export type AccountingClassAuditResponse = ApiAccountingClassAuditPayload;

export const ACTION_TYPE_NAMES: Record<string, string> = {
  ADD_DURATION: "加久期",
  REDUCE_DURATION: "减久期",
  SWITCH: "换券",
  CREDIT_DOWN: "信用下沉",
  CREDIT_UP: "信用上收",
  TIMING_BUY: "择时买入",
  TIMING_SELL: "择时卖出",
  HEDGE: "对冲操作",
};
