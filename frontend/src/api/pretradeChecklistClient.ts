/**
 * 盘前操作清单 client：GET /api/pretrade-checklist。
 *
 * 后端为 `backend/app/services/pretrade_checklist_service.py` 的观察面组装
 * (最近信号日候选 + 每票可买性检查 + 仓位建议透传 + 门控敞口现状)。
 * 契约字段全部 optional：展示面必须容忍字段缺失/半空，绝不因缺字段抛错。
 * 404、非 2xx 与网络失败一律语义化为 null(清单不可用 → 整面隐藏)。
 */

export type PretradeChecklistLimitCheck = {
  /** limit_up | limit_down | none | unknown(数值价与布尔位皆缺，fail-open)。 */
  status?: string | null;
  /** stk_limit | observation_cast | observation_flag | missing(三态来源)。 */
  price_source?: string | null;
  up_limit?: number | null;
  down_limit?: number | null;
};

export type PretradeChecklistPositionHint = {
  stock_code?: string | null;
  /** 等权主口径：当日门控敞口 / 候选数；门控缺省时为 null。 */
  equal_weight?: number | null;
  /** risk_budget 单票权重上限建议(实验参考，engine 串联语义下仍受敞口截断)。 */
  raw_weight?: number | null;
  stop_distance_pct?: number | null;
  /** ema10_stop_ref | fallback。 */
  stop_basis?: string | null;
  capped?: boolean | null;
};

export type PretradeChecklistItem = {
  candidate_rank?: number | null;
  stock_code?: string | null;
  stock_name?: string | null;
  sector_name?: string | null;
  selection_close?: number | null;
  close_value?: number | null;
  trade_status?: string | null;
  is_suspended?: boolean | null;
  limit_check?: PretradeChecklistLimitCheck | null;
  /** 人民币元口径成交额；vendor 无法定标时为 null(missing_amount)。 */
  amount_rmb?: number | null;
  adj_factor_missing?: boolean | null;
  /** buyable | blocked_suspended | blocked_limit | review | data_missing。 */
  buyable_status?: string | null;
  block_reasons?: (string | null)[] | null;
  data_flags?: (string | null)[] | null;
  position_hint?: PretradeChecklistPositionHint | null;
};

export type PretradeChecklistGate = {
  /** available | missing | degraded。 */
  status?: string | null;
  state?: string | null;
  exposure?: number | null;
  source?: string | null;
  note?: string | null;
};

export type PretradeChecklistStaleness = {
  status?: string | null;
  today?: string | null;
  calendar_gap_days?: number | null;
  stale_calendar_days?: number | null;
};

export type PretradeChecklistSummary = {
  buyable_count?: number | null;
  blocked_count?: number | null;
  review_count?: number | null;
  data_missing_count?: number | null;
};

export type PretradeChecklistPositionHintBlock = {
  policy_version?: string | null;
  sizing_mode?: string | null;
  /** equal_weight(等权主口径) 等；risk_budget 建议降级为实验参考。 */
  primary_basis?: string | null;
  coverage_degraded?: boolean | null;
  coverage_warning?: string | null;
  gate_exposure_note?: string | null;
  items?: PretradeChecklistPositionHint[] | null;
};

export type PretradeChecklistPayload = {
  as_of_date?: string | null;
  signal_kind?: string | null;
  /** ok | stale | empty。 */
  checklist_status?: string | null;
  candidate_count?: number | null;
  top_n?: number | null;
  staleness?: PretradeChecklistStaleness | null;
  gate?: PretradeChecklistGate | null;
  position_size_hint?: PretradeChecklistPositionHintBlock | null;
  items?: PretradeChecklistItem[] | null;
  summary?: PretradeChecklistSummary | null;
  disclaimer?: string | null;
};

export type PretradeChecklistEnvelope = {
  result_meta?: Record<string, unknown> | null;
  result?: PretradeChecklistPayload | null;
};

export const PRETRADE_CHECKLIST_PATH = "/api/pretrade-checklist";

export type FetchPretradeChecklistOptions = {
  fetchImpl?: typeof fetch;
  baseUrl?: string;
  signal?: AbortSignal;
};

/**
 * 拉取盘前操作清单。404、非 2xx、网络/解析失败一律返回 null，
 * 调用方整面隐藏，不在页面上留下空壳或报错态。
 */
export async function fetchPretradeChecklist(
  options?: FetchPretradeChecklistOptions,
): Promise<PretradeChecklistPayload | null> {
  const fetchImpl =
    options?.fetchImpl ?? ((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init));
  const baseUrl = options?.baseUrl ?? "";
  try {
    const response = await fetchImpl(`${baseUrl}${PRETRADE_CHECKLIST_PATH}`, {
      headers: { Accept: "application/json" },
      signal: options?.signal,
    });
    if (!response.ok) return null;
    const envelope = (await response.json()) as PretradeChecklistEnvelope | null;
    return envelope?.result ?? null;
  } catch {
    return null;
  }
}
