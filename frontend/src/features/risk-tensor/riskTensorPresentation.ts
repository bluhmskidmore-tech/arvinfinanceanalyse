import type { ResultMeta } from "../../api/contracts";
import { EM_DASH } from "../../utils/format";
import { describeCashflowWarning } from "../cashflow-projection/pages/cashflowProjectionPageModel";

/** Translate known warnings only; keep unfamiliar warnings verbatim for review. */
export function describeRiskTensorWarning(warning: string): string {
  const cashflow = describeCashflowWarning(warning);
  if (cashflow.original !== null) return cashflow.summary;

  const tenor = /^Non-standard tenor buckets remapped to nearest KRD bucket: (.+)$/.exec(warning);
  if (tenor) return `非标准期限 ${tenor[1]} 已归入最近的风险期限档。`;

  const classifiedExclusion = /^(\d+) rows carry market_value=\S+ and are excluded from portfolio duration denominator: \d+ without maturity_date \(market_value=\S+\); within that scope (\d+) fund_no_maturity \(market_value=\S+, underlying rate risk not modelled\) and (\d+) unknown_maturity \(market_value=\S+\); (\d+) matured on or before report_date with outstanding market_value \(market_value=\S+\); (\d+) future-dated with non-positive modified_duration \(market_value=\S+\)\./.exec(warning);
  if (classifiedExclusion) {
    return `${classifiedExclusion[1]} 条持仓未计入组合久期：${classifiedExclusion[2]} 条基金未列固定到期日（底层利率风险未穿透）、${classifiedExclusion[3]} 条期限待核实、${classifiedExclusion[4]} 条已到期仍有余额、${classifiedExclusion[5]} 条未来到期但久期非正；DV01 沿既有口径汇总。`;
  }

  const excluded = /^(\d+) rows carry market_value=\S+ and are excluded from portfolio duration denominator: (\d+) without maturity_date \(market_value=\S+\); (\d+) matured on or before report_date with outstanding market_value \(market_value=\S+\); (\d+) future-dated with non-positive modified_duration \(market_value=\S+\)\. DV01 totals remain sourced from row dv01; duration metrics ignore these rows until inputs are remediated\.$/.exec(warning);
  if (excluded) {
    return `${excluded[1]} 条持仓未计入组合久期：${excluded[2]} 条未列到期日（旧版未拆分基金与待核实期限）、${excluded[3]} 条已到期仍有余额、${excluded[4]} 条未来到期但久期非正；DV01 沿既有口径汇总。`;
  }

  const excludedShort = /^(\d+) rows carry market_value=(\S+) and are excluded from portfolio duration denominator\.$/.exec(warning);
  if (excludedShort) {
    return `${excludedShort[1]} 条记录市值 ${excludedShort[2]} 已从组合久期分母剔除。`;
  }

  const missingMaturity = /^Excluded (\d+) (liability )?rows without maturity_date from liquidity gap calculation\.$/.exec(warning);
  if (missingMaturity) return `${missingMaturity[1]} 条${missingMaturity[2] ? "负债" : "资产"}未列到期日，未计入合同流动性缺口；该提示未拆分产品属性。`;

  const assumptions = /^(\d+) of (\d+) bond analytics rows use assumption-based duration inputs; existing numeric aggregation is unchanged\.$/.exec(warning);
  if (assumptions) return `${assumptions[2]} 条持仓中有 ${assumptions[1]} 条久期采用假设输入，仍计入当前汇总，需复核。`;

  if (warning === "Embedded optionality is excluded from liquidity gaps; put/call/prepayment cash flows are not modeled.") {
    return "流动性缺口尚未考虑回售、赎回及提前还款现金流。";
  }
  if (warning === "Scenario stress is a review-only overlay on the materialized formal Risk Tensor; it is not a formal PnL, limit decision, or trading instruction.") {
    return "压力测试仅用于情景复核，不代表实际损益、限额判定或交易指令。";
  }
  if (warning === "Issuer concentration above desk threshold") return "发行人集中度超过业务阈值。";
  return warning;
}

export function qualityFlagLabel(flag: string | undefined) {
  if (flag === "ok") {
    return "正常";
  }
  if (flag === "warning") {
    return "预警";
  }
  if (flag === "error") {
    return "错误";
  }
  if (flag === "stale") {
    return "陈旧";
  }
  if (flag === "missing") {
    return "缺失";
  }
  return flag || EM_DASH;
}

export function qualityTone(flag: string | undefined) {
  if (flag === "error" || flag === "stale") {
    return "danger";
  }
  if (flag === "warning") {
    return "warning";
  }
  if (flag === "ok") {
    return "ok";
  }
  return "neutral";
}

export function fallbackModeLabel(mode: ResultMeta["fallback_mode"] | string | undefined) {
  if (mode === "none") {
    return "未降级";
  }
  if (mode === "latest" || mode === "latest_snapshot") {
    return "latest snapshot fallback";
  }
  if (mode === "mock") {
    return "mock fallback";
  }
  if (mode === "degraded") {
    return "降级";
  }
  return mode || EM_DASH;
}

/**
 * 后端 generated_at 为带微秒/时区的 ISO 串，展示层收敛为 YYYY-MM-DD HH:mm:ss
 * （纯字符串归一，不做时区换算，保持后端时钟读数）；原值由调用方收进 title。
 */
export function formatTimestampDisplay(value: string | undefined) {
  if (!value) {
    return EM_DASH;
  }
  const match = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})/.exec(value);
  if (!match) {
    return value;
  }
  return `${match[1]} ${match[2]}`;
}

export function compactVersion(value: string | undefined) {
  if (!value) {
    return EM_DASH;
  }
  if (value.length <= 42) {
    return value;
  }
  return `${value.slice(0, 22)}...${value.slice(-12)}`;
}

export function metaValueLabel(value: unknown) {
  if (value === null) {
    return "null";
  }
  if (value === undefined) {
    return "未提供";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function filtersAppliedLabel(filters: ResultMeta["filters_applied"] | undefined) {
  const entries = Object.entries(filters ?? {});
  return entries.map(([key, value]) => `${key}=${metaValueLabel(value)}`).join("；");
}

export function errorStatusCode(error: unknown) {
  const message = error instanceof Error ? error.message : String(error ?? "");
  const match = message.match(/\((\d{3})\)/);
  return match ? match[1] : "";
}

export function errorEvidenceMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error ?? "");
}

export function riskTensorErrorMessage(statusCode: string) {
  if (statusCode === "404") {
    return "当前报告日无风险张量数据";
  }
  if (statusCode === "503") {
    return "风险张量治理前置缺失";
  }
  return "风险张量主读面加载失败";
}
