import type { RiskTensorPayload } from "../../api/contracts";
import { riskTensorRawOrNull, type RiskTensorDisplayValue } from "./riskTensorDisplay";

export const MAIN_PAYLOAD_NUMERIC_FIELDS = [
  { key: "portfolio_dv01", label: "portfolio_dv01" },
  { key: "krd_1y", label: "krd_1y" },
  { key: "krd_3y", label: "krd_3y" },
  { key: "krd_5y", label: "krd_5y" },
  { key: "krd_7y", label: "krd_7y" },
  { key: "krd_10y", label: "krd_10y" },
  { key: "krd_30y", label: "krd_30y" },
  { key: "cs01", label: "cs01" },
  { key: "portfolio_convexity", label: "portfolio_convexity" },
  { key: "portfolio_modified_duration", label: "portfolio_modified_duration" },
  { key: "issuer_concentration_hhi", label: "issuer_concentration_hhi" },
  { key: "issuer_top5_weight", label: "issuer_top5_weight" },
  { key: "asset_cashflow_30d", label: "asset_cashflow_30d" },
  { key: "asset_cashflow_90d", label: "asset_cashflow_90d" },
  { key: "liability_cashflow_30d", label: "liability_cashflow_30d" },
  { key: "liability_cashflow_90d", label: "liability_cashflow_90d" },
  { key: "liquidity_gap_30d", label: "liquidity_gap_30d" },
  { key: "liquidity_gap_90d", label: "liquidity_gap_90d" },
  { key: "liquidity_gap_30d_ratio", label: "liquidity_gap_30d_ratio" },
  { key: "total_market_value", label: "total_market_value" },
] as const;

export const REQUIRED_DURATION_SCOPE_FIELDS = [
  { key: "rate_risk_market_value", label: "rate_risk_market_value" },
  { key: "rate_risk_dv01", label: "rate_risk_dv01" },
  { key: "rate_risk_modified_duration", label: "rate_risk_modified_duration" },
  { key: "duration_excluded_market_value", label: "duration_excluded_market_value" },
] as const;

export const PROJECTION_QUALITY_FIELDS = [
  {
    title: "未列到期日（现金流排除）",
    marketValueKey: "missing_maturity_market_value",
    countKey: "missing_maturity_count",
    detail: "兼容字段含基金等未列日期资产；产品属性见久期排除拆分，不并入合同到期现金流。",
  },
  {
    title: "浮息债代理",
    marketValueKey: "floating_rate_proxy_market_value",
    countKey: "floating_rate_proxy_count",
    detail: "浮息票息按代理口径冻结展示，未模拟后续 reset。",
  },
  {
    title: "付息频率代理",
    marketValueKey: "payment_frequency_fallback_market_value",
    countKey: "payment_frequency_fallback_count",
    detail: "年付息频率为代理口径，不代表合同字段已确认。",
  },
  {
    title: "起息日缺失代理",
    marketValueKey: "bullet_value_date_fallback_market_value",
    countKey: "bullet_value_date_fallback_count",
    detail: "起息日缺失时按一年利息代理估算，仅用于投影质量披露。",
  },
] as const;

export function riskTensorScalarIssue(value: RiskTensorDisplayValue | null | undefined) {
  if (value === null || value === undefined) {
    return "缺失";
  }
  if (typeof value === "string") {
    const normalized = value.trim();
    if (!normalized || normalized === "undefined") {
      return "缺失";
    }
    return riskTensorRawOrNull(value) === null ? "不可解析" : null;
  }
  if (value.raw === null) {
    return "缺失";
  }
  return Number.isFinite(value.raw) ? null : "不可解析";
}

export function riskTensorPayloadQualityIssues(result: RiskTensorPayload) {
  const mainIssues = MAIN_PAYLOAD_NUMERIC_FIELDS.flatMap((field) => {
    const issue = riskTensorScalarIssue(result[field.key]);
    return issue ? [{ ...field, issue }] : [];
  });
  const durationCoverageIssues = REQUIRED_DURATION_SCOPE_FIELDS.flatMap((field) => {
    const issue = riskTensorScalarIssue(result[field.key]);
    return issue ? [{ ...field, issue }] : [];
  });
  const excludedCountIssue =
    typeof result.duration_excluded_count !== "number" ||
    !Number.isFinite(result.duration_excluded_count) ||
    result.duration_excluded_count < 0 ||
    !Number.isInteger(result.duration_excluded_count)
      ? [{ key: "duration_excluded_count", label: "duration_excluded_count", issue: "缺失或无效" }]
      : [];
  return [...mainIssues, ...durationCoverageIssues, ...excludedCountIssue];
}

export function hasRiskTensorValue(value: RiskTensorDisplayValue | null | undefined) {
  return value !== null && value !== undefined;
}

export function hasDurationScopeDisclosure(result: RiskTensorPayload) {
  return (
    hasRiskTensorValue(result.rate_risk_market_value) ||
    hasRiskTensorValue(result.rate_risk_dv01) ||
    hasRiskTensorValue(result.rate_risk_modified_duration) ||
    hasRiskTensorValue(result.duration_excluded_market_value) ||
    (result.duration_excluded_count !== null && result.duration_excluded_count !== undefined)
  );
}
