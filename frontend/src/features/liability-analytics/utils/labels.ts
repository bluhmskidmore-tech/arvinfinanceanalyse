import type { Numeric } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

/**
 * 对手方类型展示词表（DESIGN.md §7 一页一语域）：
 * 后端 classify_counterparty / classify_monthly_counterparty 的英文枚举仅做显示层
 * 中文化，原值继续作为数据键参与逻辑（如 by_type 的 "Bank" 判定），未登记枚举原样透出。
 */
const COUNTERPARTY_TYPE_LABELS: Record<string, string> = {
  Bank: "银行",
  "Non-Bank FI": "非银金融",
  NonBank: "非银金融",
  Corporate: "企业",
  "Corporate/Other": "企业/其他",
  Other: "其他",
};

export function counterpartyTypeLabel(type: string | null | undefined): string {
  const normalized = (type ?? "").trim();
  if (!normalized) {
    return "";
  }
  return COUNTERPARTY_TYPE_LABELS[normalized] ?? normalized;
}

/**
 * 期限桶展示词表：后端 V1_MONTHLY_BUCKET_ORDER（0-3M…Matured）仅做显示层中文化；
 * 页内 1 年内到期等逻辑仍使用原始桶名，未登记桶名原样透出。
 */
const TERM_BUCKET_LABELS: Record<string, string> = {
  "0-3M": "0-3月",
  "3-6M": "3-6月",
  "6-12M": "6-12月",
  "1-3Y": "1-3年",
  "3-5Y": "3-5年",
  "5-10Y": "5-10年",
  "10Y+": "10年以上",
  Matured: "已到期",
};

export function termBucketLabel(bucket: string | null | undefined): string {
  const normalized = (bucket ?? "").trim();
  if (!normalized) {
    return "";
  }
  return TERM_BUCKET_LABELS[normalized] ?? normalized;
}

/**
 * 水平值（如加权负债成本）不是变动量，剥掉后端 sign_aware 带来的前导「+」；
 * 负值保留负号，数值与精度不重排（仍以后端 display 为准）。
 */
export function unsignedNumericDisplay(value: Numeric | null | undefined): string {
  const display = value?.display;
  if (!display) {
    return EM_DASH;
  }
  return display.startsWith("+") ? display.slice(1) : display;
}
