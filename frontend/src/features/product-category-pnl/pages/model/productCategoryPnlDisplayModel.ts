import { TONE_DH_CSS_VAR } from "../../../../utils/tone";
import type {
  DecimalLike,
  ProductCategoryPnlRow,
} from "../../../../api/contracts";
import { EM_DASH } from "../../../../utils/format";
import { decimalNumberInternal as decimalNumber } from "./productCategoryPnlModelInternals";

/*
 * 盈亏着色走主题感知 tone 入口（frontend/AGENTS.md：深色路由禁止浅色
 * semantic.profit/loss 直灌）。消费方（本页 + operations-analysis 贡献表）
 * 均为 DOM 内联样式且页根已声明 Nocturne scope，--dh-api-* 在 scope 内
 * 解析为 --nct-* 色板；default 取强墨阶（原 neutral-900 语义）。
 */
export const PRODUCT_CATEGORY_VALUE_TONE_COLORS = {
  default: "var(--dh-api-ink)",
  positive: TONE_DH_CSS_VAR.positive,
  negative: TONE_DH_CSS_VAR.negative,
} as const;

const YUAN_PER_YI = 100_000_000;
const PRODUCT_CATEGORY_CLOSURE_ERROR_ALERT_THRESHOLD_YUAN = 500_000;
const PRODUCT_CATEGORY_CLOSURE_ERROR_WARNING_TEXT =
  "对账残差非零，父级自报变动与子项之和存在缺口";

export function formatProductCategoryValue(
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) {
    return EM_DASH;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return String(value);
  }
  return (parsed / YUAN_PER_YI).toFixed(digits);
}

export function formatProductCategoryAttributionEffect(
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  return formatProductCategoryValue(value, digits);
}

export type ProductCategoryClosureErrorSignal = {
  hasMaterialGap: boolean;
  warningText: string | null;
};

export function selectProductCategoryClosureErrorSignal(
  value: DecimalLike | null | undefined,
): ProductCategoryClosureErrorSignal {
  const raw = decimalNumber(value);
  if (raw === null) {
    return {
      hasMaterialGap: false,
      warningText: null,
    };
  }
  const hasMaterialGap =
    Math.abs(raw) >= PRODUCT_CATEGORY_CLOSURE_ERROR_ALERT_THRESHOLD_YUAN;
  return {
    hasMaterialGap,
    warningText: hasMaterialGap
      ? PRODUCT_CATEGORY_CLOSURE_ERROR_WARNING_TEXT
      : null,
  };
}

/** Liability direction display for scale, cash and FTP; net income stays signed. */
export function formatProductCategoryRowDisplayValue(
  row: Pick<ProductCategoryPnlRow, "side">,
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) {
    return EM_DASH;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return String(value);
  }
  if (row.side === "liability") {
    return (Math.abs(parsed) / YUAN_PER_YI).toFixed(digits);
  }
  return (parsed / YUAN_PER_YI).toFixed(digits);
}

/** Foreign liability direction display for scale, cash and FTP only. */
export function formatProductCategoryForeignDisplayValue(
  row: Pick<ProductCategoryPnlRow, "side">,
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) {
    return EM_DASH;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return String(value);
  }
  const displayValue = row.side === "liability" ? -parsed : parsed;
  return (displayValue / YUAN_PER_YI).toFixed(digits);
}

export function formatProductCategoryYieldValue(
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) {
    return EM_DASH;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return String(value);
  }
  return parsed.toFixed(digits);
}

export function formatProductCategoryChartNumberTwoDecimals(
  value: unknown,
): string {
  if (value === null || value === undefined) {
    return EM_DASH;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(2) : EM_DASH;
}

export function toneForProductCategoryValue(
  value: DecimalLike | null | undefined,
): string {
  if (value === null || value === undefined) {
    return PRODUCT_CATEGORY_VALUE_TONE_COLORS.default;
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return PRODUCT_CATEGORY_VALUE_TONE_COLORS.default;
  }
  if (parsed > 0) {
    return PRODUCT_CATEGORY_VALUE_TONE_COLORS.positive;
  }
  if (parsed < 0) {
    return PRODUCT_CATEGORY_VALUE_TONE_COLORS.negative;
  }
  return PRODUCT_CATEGORY_VALUE_TONE_COLORS.default;
}

export function toneForProductCategoryForeignDisplayValue(
  row: Pick<ProductCategoryPnlRow, "side">,
  value: DecimalLike | null | undefined,
): string {
  const displayValue = productCategoryForeignDisplayNumber(row, value);
  if (displayValue === null) {
    return PRODUCT_CATEGORY_VALUE_TONE_COLORS.default;
  }
  return toneForProductCategoryValue(displayValue);
}

function productCategoryForeignDisplayNumber(
  row: Pick<ProductCategoryPnlRow, "side">,
  value: DecimalLike | null | undefined,
): number | null {
  const parsed = decimalNumber(value);
  if (parsed === null) {
    return null;
  }
  return row.side === "liability" ? -parsed : parsed;
}
