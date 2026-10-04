import { EM_DASH, fixedOrDash, pctOrDash, signedFixedOrDash } from "../../../pageModel";

/**
 * 股票分析域共享的展示格式化。所有函数只做"数值 → 字符串"，不做单位推断：
 * 调用方必须知道输入是比率（0-1）、百分点还是倍数，并选用对应函数。
 * 缺失/非有限值统一走 `fallback`（默认 `EM_DASH`；抽屉等旧界面传入 "待补"）。
 */

/** 页面沿用的"待补"占位，供旧界面显式传入 fallback。 */
export const PENDING_TEXT = "待补";

function isFinite(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function withFallback(value: number | null | undefined, fallback: string, render: (n: number) => string): string {
  return isFinite(value) ? render(value) : fallback;
}

/** 定点小数：`12.40`。 */
export function formatFixed(value: number | null | undefined, digits = 2, fallback: string = EM_DASH): string {
  return withFallback(value, fallback, (n) => fixedOrDash(n, digits));
}

/** 比率（0-1）→ `14.30%`。 */
export function formatRatioPercent(
  value: number | null | undefined,
  digits = 2,
  fallback: string = EM_DASH,
): string {
  return withFallback(value, fallback, (n) => pctOrDash(n * 100, digits));
}

/** 比率（0-1）→ 带符号 `+12.30%`；零和负数不加 `+`（与 pageModel.signedFixedOrDash 一致）。 */
export function formatRatioSignedPercent(
  value: number | null | undefined,
  digits = 2,
  fallback: string = EM_DASH,
): string {
  return withFallback(value, fallback, (n) => `${signedFixedOrDash(n * 100, digits)}%`);
}

/** 百分点（3.21 即 3.21%）→ 带符号 `+3.21%`。 */
export function formatPointSignedPercent(
  value: number | null | undefined,
  digits = 2,
  fallback: string = EM_DASH,
): string {
  return withFallback(value, fallback, (n) => `${signedFixedOrDash(n, digits)}%`);
}

/** 倍数 → `2.3x`。 */
export function formatMultiple(value: number | null | undefined, digits = 1, fallback: string = EM_DASH): string {
  return withFallback(value, fallback, (n) => `${n.toFixed(digits)}x`);
}

/** Choice 事件接收时间：ISO → `YYYY-MM-DD HH:mm`。 */
export function formatChoiceNewsReceivedAt(iso: string): string {
  const value = iso.trim();
  if (value.length >= 16) return value.slice(0, 16).replace("T", " ");
  return value || EM_DASH;
}

/** Choice 事件数据日标签，含剔除未来行的说明；调用方自行决定是否加"数据日期"前缀。 */
export function choiceNewsDataDateLabel(
  asOfDate: string | null | undefined,
  excludedFutureRows: number | null | undefined,
): string {
  const dateLabel = asOfDate?.replace(/\s+/g, " ").trim() || "待确认";
  const futureRows = isFinite(excludedFutureRows) ? excludedFutureRows : 0;
  return futureRows > 0 ? `${dateLabel}（已剔除未来 ${futureRows} 条）` : dateLabel;
}

/** Choice 事件正文截断；空文本回退 `EM_DASH`。 */
export function truncateChoiceNewsText(text: string | null | undefined, maxLen: number): string {
  const value = text?.replace(/\s+/g, " ").trim() ?? "";
  if (!value) return EM_DASH;
  return value.length <= maxLen ? value : `${value.slice(0, maxLen)}…`;
}

const CHOICE_NEWS_CONTENT_TYPE_LABELS: Record<string, string> = {
  announcement: "公告",
  research: "研报",
  research_report: "研报",
  sectornews: "行业新闻",
  stocknews: "个股新闻",
};

/** 供应商内部代码（vendor/source_table 等）不是业务分类，不能当标签展示。 */
function isTechnicalChoiceNewsCode(value: string | null | undefined): boolean {
  const normalized = value?.trim().toLowerCase().replace(/[\s_-]+/g, "");
  if (!normalized) return false;
  return (
    normalized.includes("externalvendor") ||
    normalized.includes("vendorstatus") ||
    normalized.includes("sourcetable") ||
    normalized.includes("choicestock")
  );
}

/**
 * Choice 事件分类标签：优先按 content_type 映射中文；否则采用可读的 topic_code；
 * 全大写枚举/含下划线的技术码一律回退到 `fallback`。
 */
export function choiceNewsTopicLabel(
  topicCode: string | null | undefined,
  contentType: string | null | undefined,
  fallback = "事件分类待确认",
): string {
  const normalizedContentType = contentType?.trim().toLowerCase();
  if (normalizedContentType && CHOICE_NEWS_CONTENT_TYPE_LABELS[normalizedContentType]) {
    return CHOICE_NEWS_CONTENT_TYPE_LABELS[normalizedContentType];
  }
  const value = topicCode?.trim();
  if (!value) return fallback;
  if (isTechnicalChoiceNewsCode(contentType) || isTechnicalChoiceNewsCode(value)) return fallback;
  if (/^[A-Z0-9_]+$/.test(value) || value.includes("_")) return fallback;
  return value;
}
