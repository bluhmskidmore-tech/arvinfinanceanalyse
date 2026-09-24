/**
 * 策略验证报告 client：GET /api/strategy-reports/walk-forward。
 *
 * 后端为 `backend/app/services/strategy_report_service.py` 的展示裁剪结果
 * (walk-forward 样本外验证)。契约字段全部 optional：展示面必须容忍报告
 * 字段缺失/半空，绝不因缺字段抛错。404 语义化为 null(报告未生成 → 整面隐藏)。
 */

export type WalkForwardSignConsistency = {
  observed_windows?: number | null;
  positive_windows?: number | null;
  negative_windows?: number | null;
  positive_ratio?: number | null;
};

export type WalkForwardRiskBudgetWindowParam = {
  window_id?: string | null;
  /** 该验证窗由训练集选出的 rpt(risk-per-trade)参数。 */
  selected?: number | null;
  /** 该验证窗事后最优 rpt 参数(oracle，仅诊断用)。 */
  oracle?: number | null;
};

export type WalkForwardRiskBudgetSummary = {
  grid?: (number | null)[] | null;
  policy_param?: number | null;
  selected_verdict?: string | null;
  selected_oos_chain_excess?: number | null;
  window_params?: WalkForwardRiskBudgetWindowParam[] | null;
  switch_rate?: number | null;
  switch_count?: number | null;
  mode_value?: number | null;
  mode_share?: number | null;
  observed_windows?: number | null;
  distinct_values?: number | null;
};

export type WalkForwardStrategyRow = {
  strategy?: string | null;
  /** oos_supported | oos_weakened | oos_inconclusive | insufficient_windows */
  verdict?: string | null;
  verdict_reason?: string | null;
  oos_window_count?: number | null;
  /** 样本内为全训练期单值口径(报告无逐窗样本内序列)。 */
  in_sample_excess?: number | null;
  oos_excess_median?: number | null;
  oos_excess_mean?: number | null;
  oos_chain_excess?: number | null;
  excess_sign_consistency?: WalkForwardSignConsistency | null;
  decay_cumulative_status?: string | null;
  decay_cumulative_ratio?: number | null;
  risk_budget?: WalkForwardRiskBudgetSummary | null;
};

export type WalkForwardScheduleSummary = {
  label?: string | null;
  train_months?: number | null;
  valid_months?: number | null;
  step_months?: number | null;
  objective?: string | null;
  min_windows_for_verdict?: number | null;
  window_count?: number | null;
  strategies?: WalkForwardStrategyRow[] | null;
};

export type WalkForwardReportPayload = {
  generated_at?: string | null;
  engine_version?: string | null;
  mode?: string | null;
  issue_count?: number | null;
  schedules?: WalkForwardScheduleSummary[] | null;
};

export type WalkForwardReportEnvelope = {
  result_meta?: Record<string, unknown> | null;
  result?: WalkForwardReportPayload | null;
};

export const WALK_FORWARD_REPORT_PATH = "/api/strategy-reports/walk-forward";

export type FetchWalkForwardReportOptions = {
  fetchImpl?: typeof fetch;
  baseUrl?: string;
  signal?: AbortSignal;
};

/**
 * 拉取 walk-forward 展示摘要。
 *
 * - 404(报告未生成/被移除)→ 返回 null，调用方应整面隐藏；
 * - 其他非 2xx → 抛错，由调用方决定是否降级为隐藏。
 */
export async function fetchWalkForwardReport(
  options?: FetchWalkForwardReportOptions,
): Promise<WalkForwardReportPayload | null> {
  const fetchImpl =
    options?.fetchImpl ?? ((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init));
  const baseUrl = options?.baseUrl ?? "";
  const response = await fetchImpl(`${baseUrl}${WALK_FORWARD_REPORT_PATH}`, {
    headers: { Accept: "application/json" },
    signal: options?.signal,
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`walk-forward report request failed (${response.status})`);
  }
  const envelope = (await response.json()) as WalkForwardReportEnvelope | null;
  return envelope?.result ?? null;
}
