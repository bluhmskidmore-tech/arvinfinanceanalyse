/**
 * 把后端 ExecutiveMetric 的 label / detail 中暴露出来的"工程语言"
 *（数据库表名、ASCII 后缀、英文短语）净化为业务用户能读的中文文案。
 *
 * 设计原则：
 * - 净化是 UI 层一次性"翻译"，不会改变 metric 的语义；
 * - 后端 (executive_service) 出现工程化字符串时，前端做最后一次过滤兜底；
 * - 等后端把 label/detail 改成业务文案后，本层退化为 no-op，移除安全；
 * - 任何新出现的内部表名 / 字段名只需追加到 `TABLE_NAME_PATTERN` / `PHRASE_REPLACEMENTS`。
 */

const TABLE_NAME_PATTERN = /\b(?:fact|dim|mart|stg|tmp)_[a-z0-9_]+\b/gi;

const FIELD_NAME_PATTERN = /\b(?:total_pnl|portfolio_dv01|aum_raw|ytd_raw|nim_raw|dv01_raw)\b/gi;

const PHRASE_REPLACEMENTS: Array<readonly [RegExp, string]> = [
  [/governed\s+formal\s+balance\s+overview/gi, "治理资产快照"],
  [/受治理负债分析收益指标/g, "治理负债收益面"],
  [/bond\s+analytics\s+风险快照/gi, "债券风险快照"],
  [/NIM\s*读面/gi, "净息差"],
  [/年内\s+净利息收入\s*合计/g, "年内净利息收入"],
  [/年内\s*合计/g, "年内累计"],
  [/CNY\s+资产口径/g, "本币资产口径"],
  [/组合\s+DV01/gi, "组合 DV01"],
];

const LABEL_TECH_SUFFIX = /\s*[（(]\s*[a-z][a-z0-9_]*\s*[)）]\s*$/i;

const COMMA_AFTER_REMOVED_TABLE = /(?:来自|来源)?\s*治理数据集[，,\s]+/g;

/**
 * 去掉 metric label 末尾的 ASCII / 拼音技术后缀，例如：
 *   "债券资产规模（zqtz）" -> "债券资产规模"
 *   "组合DV01"           -> "组合 DV01"  (保留，非工程后缀)
 */
export function sanitizeMetricLabel(raw: string): string {
  if (!raw) return raw;
  const trimmed = raw.trim();
  return trimmed.replace(LABEL_TECH_SUFFIX, "").trim();
}

/**
 * 把 detail 中的表名 / 内部短语替换为业务化措辞。
 *   "来自 fact_formal_zqtz_balance_daily，在 2026-02-28 的 CNY 资产口径市值合计。"
 *   -> "在 2026-02-28 的本币资产口径市值合计。"
 */
export function sanitizeMetricDetail(raw: string): string {
  if (!raw) return raw;

  let next = raw;

  next = next.replace(TABLE_NAME_PATTERN, "治理数据集");
  next = next.replace(COMMA_AFTER_REMOVED_TABLE, "");
  next = next.replace(FIELD_NAME_PATTERN, "");

  for (const [pattern, replacement] of PHRASE_REPLACEMENTS) {
    next = next.replace(pattern, replacement);
  }

  next = next
    .replace(/\s{2,}/g, " ")
    .replace(/([\u4e00-\u9fff，。、；：])\s+(?=[\u4e00-\u9fff，。、；：])/g, "$1")
    .replace(/^[，,。.\s]+/, "")
    .trim();

  return next;
}

export function sanitizeMetricCopy<T extends { label: string; detail: string }>(
  metric: T,
): T {
  return {
    ...metric,
    label: sanitizeMetricLabel(metric.label),
    detail: sanitizeMetricDetail(metric.detail),
  };
}
