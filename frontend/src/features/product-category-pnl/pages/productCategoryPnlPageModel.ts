import type { DecimalLike, ProductCategoryPnlRow, ResultMeta } from "../../../api/contracts";

/** Display order for category rows; does not re-aggregate backend totals. */
const DISPLAY_ORDER = [
  "interbank_lending_assets",
  "repo_assets",
  "bond_investment",
  "bond_tpl",
  "bond_ac",
  "bond_ac_other",
  "bond_fvoci",
  "bond_valuation_spread",
  "interest_earning_assets",
  "derivatives",
  "intermediate_business_income",
  "asset_total",
  "interbank_deposits",
  "interbank_borrowings",
  "repo_liabilities",
  "interbank_cds",
  "credit_linked_notes",
  "liability_total",
] as const;

const DISPLAY_ORDER_INDEX = new Map<string, number>(
  DISPLAY_ORDER.map((categoryId, index) => [categoryId, index]),
);

/** First-screen selector scope for the main product-category PnL page (truth contract). */
export const PRODUCT_CATEGORY_MAIN_PAGE_VIEWS = ["monthly", "ytd"] as const;

/**
 * Views the governed detail API may advertise via `available_views` (superset of main-page scope).
 * Main page does not add `qtd` / `year_to_report_month_end` controls without contract updates.
 */
export const PRODUCT_CATEGORY_GOVERNED_DETAIL_VIEWS = [
  "monthly",
  "qtd",
  "ytd",
  "year_to_report_month_end",
] as const;

export function mainPageViewsAreGovernedDetailSubset(): boolean {
  return PRODUCT_CATEGORY_MAIN_PAGE_VIEWS.every((view) =>
    (PRODUCT_CATEGORY_GOVERNED_DETAIL_VIEWS as readonly string[]).includes(view),
  );
}

/** True when the API surface includes both views required by the main-page selector. */
export function availableViewsSupportMainPageSelector(availableViews: string[]): boolean {
  return PRODUCT_CATEGORY_MAIN_PAGE_VIEWS.every((view) => availableViews.includes(view));
}

export const PRODUCT_CATEGORY_VALUE_TONE_COLORS = {
  default: "#162033",
  positive: "#12723b",
  negative: "#b42318",
} as const;

const YUAN_PER_YI = 100_000_000;

export function formatProductCategoryValue(
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return String(value);
  }
  return (parsed / YUAN_PER_YI).toFixed(digits);
}

export function formatProductCategoryRowDisplayValue(
  row: Pick<ProductCategoryPnlRow, "side">,
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) {
    return "-";
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

export function formatProductCategoryYieldValue(
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return String(value);
  }
  return parsed.toFixed(digits);
}

export function toneForProductCategoryValue(value: DecimalLike | null | undefined): string {
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

/**
 * Table body rows: same row objects as the chosen payload (baseline vs scenario), filtered and sorted only.
 * When `scenarioRows` is non-nullish, it wins; otherwise baseline rows are shown - no client-side rollups.
 */
export function selectProductCategoryDetailRows(
  baselineRows: ProductCategoryPnlRow[] | null | undefined,
  scenarioRows: ProductCategoryPnlRow[] | null | undefined,
): ProductCategoryPnlRow[] {
  const source = scenarioRows ?? baselineRows ?? [];
  return source
    .filter((row) => row.category_id !== "grand_total")
    .sort((left, right) => {
      const leftIndex = DISPLAY_ORDER_INDEX.get(left.category_id) ?? Number.MAX_SAFE_INTEGER;
      const rightIndex = DISPLAY_ORDER_INDEX.get(right.category_id) ?? Number.MAX_SAFE_INTEGER;
      return leftIndex - rightIndex;
    });
}

export function selectDisplayedProductCategoryGrandTotal<
  T extends Pick<ProductCategoryPnlRow, "business_net_income">,
>(scenarioGrand: T | null | undefined, baselineGrand: T | null | undefined): T | undefined {
  return scenarioGrand ?? baselineGrand ?? undefined;
}

/**
 * Next value for page `selectedDate` when the user has not chosen one yet.
 *
 * - Non-empty `selectedDate` is never overridden (returns `null`).
 * - Missing or empty `report_dates` yields no default (returns `null`).
 * - Otherwise returns the first list element; API list order is authoritative (see backend flow tests).
 */
export function nextDefaultReportDateIfUnset(
  selectedDate: string,
  reportDates: string[] | undefined,
): string | null {
  if (selectedDate) {
    return null;
  }
  if (!reportDates?.length) {
    return null;
  }
  return reportDates[0] ?? "";
}

/** Deep link to ledger PnL for the same `report_date` as the product-category page selection. */
export function buildLedgerPnlHrefForReportDate(reportDate: string): string {
  if (!reportDate) {
    return "/ledger-pnl";
  }
  return `/ledger-pnl?report_date=${encodeURIComponent(reportDate)}`;
}

/** Page-visible copy: standalone `as_of_date` is a known outward contract gap (see truth contract §10). */
export const PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY =
  "as_of_date：无独立外显字段（显式合同缺口；勿用本页 report_date 或 generated_at 代替）。 ";

export type ProductCategoryGovernanceNotice = {
  id: "fallback_mode" | "vendor_status" | "quality_flag";
  text: string;
};

/**
 * Notices for degraded governance signals from a single `result_meta` (typ. formal baseline on first screen).
 * Does not invent dates or categories; only reflects backend-reported fields.
 */
export function collectProductCategoryGovernanceNotices(
  meta: ResultMeta | null | undefined,
): ProductCategoryGovernanceNotice[] {
  if (!meta) {
    return [];
  }
  const out: ProductCategoryGovernanceNotice[] = [];
  if (meta.fallback_mode !== "none") {
    out.push({
      id: "fallback_mode",
      text: `读链路回退中：fallback_mode=${meta.fallback_mode}（仅元数据展示，非前端补算）。`,
    });
  }
  if (meta.vendor_status === "vendor_stale" || meta.vendor_status === "vendor_unavailable") {
    out.push({
      id: "vendor_status",
      text: `供应侧状态需关注：vendor_status=${meta.vendor_status}。`,
    });
  }
  if (meta.quality_flag !== "ok") {
    out.push({
      id: "quality_flag",
      text: `质量标记需关注：quality_flag=${meta.quality_flag}。`,
    });
  }
  return out;
}

/**
 * One-line evidence that formal vs scenario `result_meta` are separate envelopes (trace/basis not assumed equal).
 */
export function formatProductCategoryDualMetaDistinctLine(
  formalMeta: ResultMeta,
  scenarioMeta: ResultMeta,
): string {
  return `正式与情景分开展示：formal basis=${formalMeta.basis} trace_id=${formalMeta.trace_id}；scenario basis=${scenarioMeta.basis} trace_id=${scenarioMeta.trace_id}（两路 result_meta 分卡展示，不混用）。`;
}
