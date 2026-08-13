/**
 * 数据健康总览 client：GET /api/data-health。
 *
 * 后端为 `backend/app/services/data_health_service.py` 的系统级体温计
 * (供数新鲜度/复权因子缺口/公式版本存量/概念区间陈旧度/涨跌停回填/
 * tradestatus 词表观察点/调度任务状态)。
 * 契约字段全部 optional：展示面必须容忍字段缺失/半空，绝不因缺字段抛错。
 * 404、非 2xx 与网络失败一律语义化为 null(健康面不可用 → 整面隐藏)。
 */

export type DataHealthSection = {
  key?: string | null;
  label?: string | null;
  /** ok | warn | stale | missing | error(单项检查失败，detail 带原因)。 */
  status?: string | null;
  /** 简短指标文本，如 "2026-08-11 · 落后 2 天"、"5,022 行缺复权"。 */
  metric?: string | null;
  /** 口径与阈值说明，前端作 tooltip 展示。 */
  detail?: string | null;
  as_of?: string | null;
};

export type DataHealthPayload = {
  /** 评估日(后端 today，自然日)。 */
  as_of_date?: string | null;
  /** 最差 section 决定：ok | warn | stale | missing | error。 */
  overall_status?: string | null;
  /** 新鲜度阈值说明(自然日近似交易日)。 */
  threshold_note?: string | null;
  sections?: (DataHealthSection | null)[] | null;
};

export type DataHealthEnvelope = {
  result_meta?: Record<string, unknown> | null;
  result?: DataHealthPayload | null;
};

export const DATA_HEALTH_PATH = "/api/data-health";

export type FetchDataHealthOptions = {
  fetchImpl?: typeof fetch;
  baseUrl?: string;
  signal?: AbortSignal;
};

/**
 * 拉取数据健康总览。404、非 2xx、网络/解析失败一律返回 null，
 * 调用方整面隐藏，不在页面上留下空壳或报错态。
 */
export async function fetchDataHealth(
  options?: FetchDataHealthOptions,
): Promise<DataHealthPayload | null> {
  const fetchImpl =
    options?.fetchImpl ?? ((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init));
  const baseUrl = options?.baseUrl ?? "";
  try {
    const response = await fetchImpl(`${baseUrl}${DATA_HEALTH_PATH}`, {
      headers: { Accept: "application/json" },
      signal: options?.signal,
    });
    if (!response.ok) return null;
    const envelope = (await response.json()) as DataHealthEnvelope | null;
    return envelope?.result ?? null;
  } catch {
    return null;
  }
}
