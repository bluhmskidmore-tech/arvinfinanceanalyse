import type { RiskTensorPayload } from "../../api/contracts";
import { numericRaw } from "../../pageModel";
import { EM_DASH } from "../../utils/format";
import { bondNumericDisplay, bondNumericRawOrNull } from "../bond-analytics/adapters/bondAnalyticsAdapter";
import { toneFromSignedDisplayString } from "../workbench/components/kpiFormat";
import { riskTensorExactScaledAmountDisplayOrNull } from "./riskTensorPageModel";

export type RiskTensorDisplayValue = Parameters<typeof bondNumericDisplay>[0];

export const YUAN_PER_WAN = 10_000;

export const YUAN_PER_YI = 100_000_000;

export const WAN_YUAN_UNIT = "\u4e07\u5143";

export const YI_YUAN_UNIT = "\u4ebf\u5143";

export function displayStr(value: Parameters<typeof bondNumericDisplay>[0]) {
  return bondNumericDisplay(value);
}

export function riskTensorRawOrNull(value: RiskTensorDisplayValue): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "string") {
    const normalized = value.trim().replace(/,/g, "");
    if (!normalized) {
      return null;
    }
    const raw = Number(normalized);
    return Number.isFinite(raw) ? raw : null;
  }
  return numericRaw(value);
}

export function amountUnit(value: RiskTensorDisplayValue, unit: string) {
  return riskTensorDecisionAmountAvailable(value) ? unit : undefined;
}

export function riskTensorDecisionAmountAvailable(value: RiskTensorDisplayValue) {
  return riskTensorExactScaledAmountDisplayOrNull(value, 1) !== null || riskTensorRawOrNull(value) !== null;
}

export function shouldPrefixPositiveAmount(value: RiskTensorDisplayValue) {
  if (typeof value === "string") {
    return value.trim().startsWith("+");
  }
  return Boolean(value?.sign_aware);
}

export function formatYuanAmount(value: RiskTensorDisplayValue, divisor: number) {
  const exactDisplay = riskTensorExactScaledAmountDisplayOrNull(
    value,
    divisor,
    shouldPrefixPositiveAmount(value),
  );
  if (exactDisplay !== null) {
    return exactDisplay;
  }

  const raw = riskTensorRawOrNull(value);
  if (raw === null) {
    return displayStr(value);
  }
  const scaled = raw / divisor;
  const formatted = Math.abs(scaled).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  if (scaled < 0) {
    return `-${formatted}`;
  }
  return `${shouldPrefixPositiveAmount(value) && scaled > 0 ? "+" : ""}${formatted}`;
}

export function yuanAsWanDisplay(value: RiskTensorDisplayValue) {
  return formatYuanAmount(value, YUAN_PER_WAN);
}

export function yuanAsYiDisplay(value: RiskTensorDisplayValue) {
  return formatYuanAmount(value, YUAN_PER_YI);
}

export function yuanAsWanWithUnit(value: RiskTensorDisplayValue) {
  const display = yuanAsWanDisplay(value);
  return riskTensorRawOrNull(value) === null ? display : `${display} ${WAN_YUAN_UNIT}`;
}

export function yuanAsYiWithUnit(value: RiskTensorDisplayValue) {
  const display = yuanAsYiDisplay(value);
  return riskTensorRawOrNull(value) === null ? display : `${display} ${YI_YUAN_UNIT}`;
}

export function yuanAsWanMagnitudeOrNull(value: RiskTensorDisplayValue) {
  const raw = riskTensorRawOrNull(value);
  return raw === null ? null : raw / YUAN_PER_WAN;
}

export function chartMagnitudeOrNull(value: RiskTensorDisplayValue) {
  const raw = riskTensorRawOrNull(value);
  return raw === null ? null : raw;
}

export function ratioPercentDisplay(value: Parameters<typeof bondNumericRawOrNull>[0]) {
  const display = displayStr(value);
  if (display.includes("%")) {
    return display;
  }
  const raw = bondNumericRawOrNull(value);
  if (raw === null) {
    return display;
  }
  if (value !== null && typeof value === "object" && value.unit === "ratio") {
    return `${(raw * 100).toFixed(1)}%`;
  }
  const abs = Math.abs(raw);
  if (abs <= 1) {
    return `${(raw * 100).toFixed(1)}%`;
  }
  if (abs <= 100) {
    return `${raw.toFixed(1)}%`;
  }
  return display;
}

export function ratioTone(value: Parameters<typeof bondNumericRawOrNull>[0]) {
  return toneFromSignedDisplayString(ratioPercentDisplay(value));
}

export function countDisplay(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return value.toLocaleString("zh-CN");
}

export function projectionQualityStatusLabel(status: RiskTensorPayload["projection_quality_status"]) {
  if (status === "available") {
    return "可用";
  }
  if (status === "unavailable_legacy") {
    return "历史版本未提供投影质量字段/待重算";
  }
  return "不可用/待重算";
}

export function projectionQualityAmountDisplay(value: RiskTensorDisplayValue | null | undefined) {
  return riskTensorRawOrNull(value) === null ? "不可用/待重算" : yuanAsYiDisplay(value);
}

export function projectionQualityAmountUnit(value: RiskTensorDisplayValue | null | undefined) {
  return riskTensorRawOrNull(value) === null ? undefined : YI_YUAN_UNIT;
}

export function projectionQualityCountDisplay(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value) || value < 0 || !Number.isInteger(value)) {
    return "笔数不可用";
  }
  return `${value.toLocaleString("zh-CN")} 笔`;
}

export function excludedLiabilityCountDisplay(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value) || value < 0 || !Number.isInteger(value)) {
    return "条数不可用";
  }
  return `${value.toLocaleString("zh-CN")} 条`;
}

export function regulatoryDv01Display(value: RiskTensorPayload["regulatory_dv01"]) {
  if (value === null || value === undefined) {
    return "待接入";
  }
  return yuanAsWanDisplay(value);
}

export function regulatoryDv01DisplayWithUnit(value: RiskTensorPayload["regulatory_dv01"]) {
  if (value === null || value === undefined) {
    return regulatoryDv01Display(value);
  }
  return `${regulatoryDv01Display(value)} ${WAN_YUAN_UNIT}`;
}

export function regulatoryDv01Tone(value: RiskTensorPayload["regulatory_dv01"]) {
  if (value === null || value === undefined) {
    return "warning";
  }
  return toneFromSignedDisplayString(regulatoryDv01Display(value));
}
