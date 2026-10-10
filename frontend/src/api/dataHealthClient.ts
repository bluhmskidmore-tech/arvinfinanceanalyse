/**
 * 数据健康总览 client：GET /api/data-health。
 *
 * 后端为 `backend/app/services/data_health_service.py` 的系统级体温计
 * (供数新鲜度/复权因子缺口/公式版本存量/概念区间陈旧度/涨跌停回填/
 * tradestatus 词表观察点/调度任务状态)。
 * 契约字段全部 optional：展示面必须容忍字段缺失/半空，绝不因缺字段抛错。
 * 结果三分：ok(有数据) / missing(404 能力不存在或后端明确空 → 整面收缩隐藏)
 * / error(其余非 2xx、网络或解析失败 → 组件呈现错误态+重试，不静默吞掉)。
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

/**
 * 五态取数结果：区分「能力不存在/明确空(missing → 整面收缩)」与
 * 「请求失败(error → 错误态+重试)」，不再把失败静默吞成 null。
 */
export type DataHealthFetchResult =
  | { kind: "ok"; payload: DataHealthPayload }
  | { kind: "missing" }
  | { kind: "error"; reason: string };

export type FetchDataHealthOptions = {
  fetchImpl?: typeof fetch;
  baseUrl?: string;
  signal?: AbortSignal;
};

/**
 * 拉取数据健康总览。
 * - 2xx 且 result 非空 → ok
 * - 404(能力不存在) / 2xx 但 result 为空 → missing(调用方整面收缩隐藏)
 * - 其余非 2xx、网络失败、解析失败 → error(调用方呈现一行错误+重试)
 */
export async function fetchDataHealth(
  options?: FetchDataHealthOptions,
): Promise<DataHealthFetchResult> {
  const fetchImpl =
    options?.fetchImpl ?? ((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init));
  const baseUrl = options?.baseUrl ?? "";
  try {
    const response = await fetchImpl(`${baseUrl}${DATA_HEALTH_PATH}`, {
      headers: { Accept: "application/json" },
      signal: options?.signal,
    });
    if (response.status === 404) return { kind: "missing" };
    if (!response.ok) return { kind: "error", reason: `HTTP ${response.status}` };
    const envelope = (await response.json()) as DataHealthEnvelope | null;
    const payload = envelope?.result ?? null;
    return payload ? { kind: "ok", payload } : { kind: "missing" };
  } catch (error) {
    return { kind: "error", reason: error instanceof Error ? error.message : String(error) };
  }
}
