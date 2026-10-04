import type { LedgerMoneyValue, LedgerPnlAnalysisPeriodRow } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

export type LedgerSectionState = { label: string; tone: "loading" | "error" | "empty" } | null;

export function ledgerSectionState(
  query: { isLoading: boolean; isError: boolean },
  options?: { isEmpty?: boolean; emptyLabel?: string },
): LedgerSectionState {
  if (query.isLoading) {
    return { label: "读取中", tone: "loading" };
  }
  if (query.isError) {
    return { label: "读取失败", tone: "error" };
  }
  if (options?.isEmpty) {
    return { label: options.emptyLabel ?? "暂无数据", tone: "empty" };
  }
  return null;
}

export function formatMoney(value: LedgerMoneyValue | null | undefined) {
  const yi = String(value?.yi ?? "").trim();
  // 后端契约保证 yi 必填合法；yi 缺失或非有限数值串（如 "NaN"）一律按缺失处理，
  // 不再用 yuan/1e8 在前端自算兜底（该路径与全页 ROUND_HALF_UP 口径不一致）。
  if (yi && Number.isFinite(Number(yi))) {
    return `${yi} 亿元`;
  }
  return EM_DASH;
}

/**
 * 读取后端已格式化金额的正负号用于展示 tone（绿涨红跌），不做任何前端金额计算。
 * yi 缺失或非有限数值串时按中性处理。
 */
export function moneyTone(value: LedgerMoneyValue | null | undefined): "positive" | "negative" | "neutral" {
  const yi = String(value?.yi ?? "").trim();
  if (!yi || !Number.isFinite(Number(yi))) {
    return "neutral";
  }
  const parsed = Number(yi);
  if (parsed > 0) return "positive";
  if (parsed < 0) return "negative";
  return "neutral";
}

/** 在候选跨期对比行中按 metric_key 取行；rows 为空（如 no_previous_period）时返回 undefined。 */
export function findPeriodComparisonRow(
  rows: LedgerPnlAnalysisPeriodRow[] | undefined,
  metricKey: LedgerPnlAnalysisPeriodRow["metric_key"],
): LedgerPnlAnalysisPeriodRow | undefined {
  return rows?.find((row) => row.metric_key === metricKey);
}
export function ledgerMoneyYuan(value: LedgerMoneyValue | null | undefined) {
  const rawYuan = String(value?.yuan ?? "").trim();
  if (!rawYuan) {
    return null;
  }
  const yuan = Number(rawYuan);
  return Number.isFinite(yuan) ? yuan : null;
}

function ledgerMoneyAbsYuan(value: LedgerMoneyValue | null | undefined) {
  const yuan = ledgerMoneyYuan(value);
  return yuan === null ? -1 : Math.abs(yuan);
}

/** 默认排序：金额绝对值降序，让影响最大的科目排在首页。 */
export function sortLedgerRowsByAbsYuan<T>(
  rows: T[],
  selectMoney: (row: T) => LedgerMoneyValue | null | undefined,
) {
  return rows
    .map((row, index) => ({
      row,
      index,
      absYuan: ledgerMoneyAbsYuan(selectMoney(row)),
    }))
    .sort((left, right) => right.absYuan - left.absYuan || left.index - right.index)
    .map((item) => item.row);
}
export function reportDateToMonth(reportDate: string) {
  const match = /^(\d{4})-(\d{2})/.exec(reportDate.trim());
  return match ? `${match[1]}${match[2]}` : "";
}
