import { EM_DASH, formatYuanAmountAsYiPlain } from "../../../utils/format";
import type {
  BalanceMovementDrilldownStatus,
  BalanceZqtzConcentrationDimensionKey,
} from "../../../api/contracts";
import type { BusinessMomMove } from "./balanceMovementBusinessModel";

export function formatPct(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return String(value);
  }
  return `${n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

/**
 * 2026-08-13 债务清零：本地元→亿实现并入共享 formatYuanAmountAsYiPlain
 * （输出一致：zh-CN 分组、固定 2 位、缺失 EM_DASH、无效串原样透出）。
 * 全部调用点均为 2 位小数，故收敛为无 digits 参数的委托。
 */
export function formatYiFixed(value: string | number | null | undefined) {
  return formatYuanAmountAsYiPlain(value);
}

export function formatSignedYi(value: string | number | null | undefined, digits = 2) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  const n = Number(value) / 100000000;
  if (!Number.isFinite(n)) {
    return String(value);
  }
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} 亿`;
}

export function formatPlainNumber(value: string | number | null | undefined, digits = 2) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return String(value);
  }
  return n.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatTrendMonthLabel(reportMonth: string) {
  const [year, month] = reportMonth.split("-");
  const monthNumber = Number(month);
  if (!year || !Number.isFinite(monthNumber)) {
    return reportMonth;
  }
  return `${year}年${monthNumber}月`;
}

export function formatYiCell(value: string | number | null | undefined) {
  return formatYiFixed(value);
}

export function formatSignedYiCell(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  const n = Number(value) / 100000000;
  if (!Number.isFinite(n)) {
    return String(value);
  }
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export type BalanceMovementMatrixValueKind = "amount" | "percent";

export function formatMatrixValue(
  value: string | number | null | undefined,
  valueKind: BalanceMovementMatrixValueKind,
  omitUnit = false,
) {
  if (valueKind === "percent") {
    return formatPct(value);
  }
  const formatted = formatYiCell(value);
  if (formatted === EM_DASH) {
    return formatted;
  }
  return omitUnit ? formatted : `${formatted} 亿`;
}

export function formatMatrixCellWithMissing(
  value: string | number | null | undefined,
  valueKind: BalanceMovementMatrixValueKind,
  omitUnit: boolean,
  hasMissingInputs?: boolean,
) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  const formatted = formatMatrixValue(value, valueKind, omitUnit);
  if (hasMissingInputs && formatted !== EM_DASH) {
    return `${formatted}*`;
  }
  return formatted;
}

export function formatSignedPercentPoint(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return String(value);
  }
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}pp`;
}

export function drilldownStatusLabel(status: BalanceMovementDrilldownStatus | undefined) {
  switch (status) {
    case "supported":
      return "已支持";
    case "unsupported_missing_columns":
      return "字段不足";
    case "unsupported_low_coverage":
      return "覆盖率不足";
    case "no_data":
      return "无数据";
    default:
      return "未确认";
  }
}

export function concentrationDimensionLabel(dimension: BalanceZqtzConcentrationDimensionKey) {
  switch (dimension) {
    case "issuer_name":
      return "主体";
    case "rating":
      return "评级";
    case "industry_name":
      return "行业";
    default:
      return dimension;
  }
}

export function formatSignedMatrixValue(
  value: string | number | null | undefined,
  valueKind: BalanceMovementMatrixValueKind,
  omitUnit = false,
) {
  if (valueKind === "percent") {
    return formatSignedPercentPoint(value);
  }
  const formatted = formatSignedYiCell(value);
  if (formatted === EM_DASH) {
    return formatted;
  }
  return omitUnit ? formatted : `${formatted} 亿`;
}

export function matrixDeltaTone(formatted: string): string {
  const t = formatted.trim();
  if (t === "" || t === EM_DASH || t === "-") {
    return "balance-movement-matrix__delta balance-movement-matrix__delta--neutral";
  }
  if (t.startsWith("+") || t.startsWith("＋")) {
    return "balance-movement-matrix__delta balance-movement-matrix__delta--up";
  }
  if (t.startsWith("-") || t.startsWith("−")) {
    return "balance-movement-matrix__delta balance-movement-matrix__delta--down";
  }
  return "balance-movement-matrix__delta balance-movement-matrix__delta--neutral";
}

export function formatSignedYiNumber(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function sourceKindLabel(sourceKind: BusinessMomMove["sourceKind"]) {
  return sourceKind === "zqtz" ? "证券投资辅助" : "总账";
}

export function moveDeltaToneClass(value: number | null) {
  // 缺失≠零：null 不得套用持平色阶，只有有限数值才有方向/持平色。
  if (value === null) {
    return "";
  }
  if (value > 0) {
    return "balance-movement-top-moves-table__delta balance-movement-top-moves-table__delta--up";
  }
  if (value < 0) {
    return "balance-movement-top-moves-table__delta balance-movement-top-moves-table__delta--down";
  }
  return "balance-movement-top-moves-table__delta";
}

export function sourceNotePreview(sourceNote: string | undefined) {
  if (!sourceNote) {
    return "来源已记录";
  }
  return sourceNote.replace(/\s+/g, " ").trim();
}

export function movementDirection(value: string | number | null | undefined) {
  const n = finiteMetric(value);
  if (n === null) return EM_DASH;
  if (n > 0) return "增加";
  if (n < 0) return "减少";
  return "持平";
}

export function formatMetaList(values: string[] | undefined) {
  return values && values.length > 0 ? values.join("、") : EM_DASH;
}

export function finiteMetric(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}
