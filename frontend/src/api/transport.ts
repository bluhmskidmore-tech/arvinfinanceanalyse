/**
 * Shared HTTP transport for domain API clients.
 *
 * Single home for the JSON request helpers that used to be copied between
 * `client.ts`, `marketDataClient.ts`, and `healthClient.ts`:
 *
 * - `requestJson`      envelope GET (validated `ApiEnvelope` shape, 60s default timeout)
 * - `requestPlainJson` plain JSON GET (no envelope assumption)
 * - `requestActionJson` action POST/GET returning rich `ActionRequestError` on failure
 * - `requestText` / `requestBlob` / `requestActionWithBody` download + write helpers
 *
 * Error-detail and timeout semantics are parameterized so each caller keeps its
 * historical behavior (`client.ts`: status-only errors + 60s timeout;
 * `marketDataClient.ts`: FastAPI detail-aware errors + no timeout).
 */
import type { ApiEnvelope } from "./contracts";
import { readHttpJsonDetail } from "./httpResponseError";

export type FetchLike = typeof fetch;

export const DEFAULT_REQUEST_JSON_TIMEOUT_MS = 60_000;

/**
 * - `status-only`: failed responses throw `Request failed: <path> (<status>)`.
 * - `json-detail`: failed responses surface the FastAPI-style JSON `detail`
 *   text when present, falling back to the status-only message.
 */
export type TransportErrorDetailMode = "status-only" | "json-detail";

export type TransportRequestOptions = {
  /** Milliseconds before aborting. `null` disables the timeout entirely. */
  timeoutMs?: number | null;
  /** Optional caller cancellation signal, including during response reading. */
  signal?: AbortSignal;
  /** How failed (non-2xx) responses are turned into error messages. */
  errorDetail?: TransportErrorDetailMode;
  /**
   * Optional business-critical field descriptors checked against `result`
   * (see `ShapeFieldSpec` / `assertShape`). Omit to keep the historical
   * shell-only envelope check.
   */
  keyFields?: ShapeFieldSpec[];
};

export class ActionRequestError extends Error {
  readonly status: number;
  readonly runId?: string;
  /** Top-level `error_message` from the JSON body when present. */
  readonly errorMessage?: string;
  /** Raw `detail` field from the JSON body (string, object, or array). */
  readonly detail?: unknown;

  constructor(
    message: string,
    opts: {
      status: number;
      runId?: string;
      errorMessage?: string;
      detail?: unknown;
    },
  ) {
    super(message);
    this.name = "ActionRequestError";
    this.status = opts.status;
    this.runId = opts.runId;
    this.errorMessage = opts.errorMessage;
    this.detail = opts.detail;
  }
}

function extractApiRunId(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const body = payload as Record<string, unknown>;
  const top = body.run_id;
  if (typeof top === "string" && top.trim()) {
    return top;
  }
  const detail = body.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const nested = (detail as Record<string, unknown>).run_id;
    if (typeof nested === "string" && nested.trim()) {
      return nested;
    }
  }
  return undefined;
}

function extractTopLevelErrorMessage(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const errMsg = (payload as Record<string, unknown>).error_message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    return errMsg;
  }
  return undefined;
}

function extractApiErrorDetail(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const body = payload as Record<string, unknown>;
  const errMsg = body.error_message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    return errMsg;
  }
  const detail = body.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as Record<string, unknown>;
    const nestedMsg = d.error_message;
    if (typeof nestedMsg === "string" && nestedMsg.trim()) {
      return nestedMsg;
    }
    const nestedDetail = d.detail;
    if (typeof nestedDetail === "string" && nestedDetail.trim()) {
      return nestedDetail;
    }
  }
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (typeof item === "string") {
        return item;
      }
      if (item && typeof item === "object" && "msg" in item) {
        return String((item as { msg: unknown }).msg);
      }
      try {
        return JSON.stringify(item);
      } catch {
        return String(item);
      }
    });
    const joined = parts.filter((p) => p.trim()).join("; ");
    return joined || undefined;
  }
  return undefined;
}

function extractRawDetail(payload: unknown): unknown {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  if (!("detail" in (payload as Record<string, unknown>))) {
    return undefined;
  }
  return (payload as Record<string, unknown>).detail;
}

function describePayloadBriefly(value: unknown): string {
  if (value === null) return "null";
  if (Array.isArray(value)) return "an array";
  if (typeof value !== "object") return `a ${typeof value}`;
  return "an object";
}

/**
 * Lightweight runtime check of the shared `ApiEnvelope` shape
 * (`result` + `result_meta`, see `contracts/core.ts`).
 *
 * Deliberately lenient so real backend responses never trip it:
 * `result` may hold any value (including `null`), `result_meta` only has to be
 * a plain object, and `basis` / `as_of_date` are type-checked only when
 * present (`as_of_date` is optional and nullable in the contract).
 * Field-level numeric validation stays with `src/api/numeric.ts` guards.
 *
 * `resultFields` is an optional escape hatch to also check a handful of
 * business-critical fields inside `result` (see `assertShape`). Passing
 * nothing keeps the historical shell-only behavior.
 */
export function assertApiEnvelopeShape(
  payload: unknown,
  url: string,
  resultFields?: ShapeFieldSpec[],
): asserts payload is ApiEnvelope<unknown> {
  const fail = (reason: string): never => {
    throw new Error(`Invalid ApiEnvelope from ${url}: ${reason}`);
  };
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    fail(`response is ${describePayloadBriefly(payload)}, expected { result, result_meta }`);
  }
  const envelope = payload as Record<string, unknown>;
  if (!("result" in envelope)) {
    fail("missing `result`");
  }
  const meta = envelope.result_meta;
  if (meta === undefined) {
    fail("missing `result_meta`");
  }
  if (meta === null || typeof meta !== "object" || Array.isArray(meta)) {
    fail(`\`result_meta\` is ${describePayloadBriefly(meta)}, expected an object`);
  }
  const metaRecord = meta as Record<string, unknown>;
  if (metaRecord.basis !== undefined && typeof metaRecord.basis !== "string") {
    fail("`result_meta.basis` must be a string when present");
  }
  const asOfDate = metaRecord.as_of_date;
  if (asOfDate !== undefined && asOfDate !== null && typeof asOfDate !== "string") {
    fail("`result_meta.as_of_date` must be a string or null when present");
  }
  if (resultFields?.length) {
    assertShape(envelope.result, url, resultFields, "result.");
  }
}

/** Primitive types `assertShape` can check via `typeof`/`Array.isArray`. */
export type ShapeFieldType = "string" | "number" | "boolean" | "object" | "array";

/**
 * Descriptor for one business-critical field checked by `assertShape`.
 * `path` is a dot-separated path relative to the object being checked
 * (e.g. `"summary.total_pnl"`). Nested array elements are not walked —
 * this is a shallow presence + `typeof` check, not a schema validator.
 */
export type ShapeFieldSpec = {
  path: string;
  type: ShapeFieldType;
  /** Field may be absent, `undefined`, or `null` without failing validation. */
  optional?: boolean;
};

function resolveShapePath(value: unknown, path: string): { found: boolean; value: unknown } {
  let current: unknown = value;
  for (const segment of path.split(".")) {
    if (current === null || typeof current !== "object" || Array.isArray(current)) {
      return { found: false, value: undefined };
    }
    const record = current as Record<string, unknown>;
    if (!(segment in record)) {
      return { found: false, value: undefined };
    }
    current = record[segment];
  }
  return { found: true, value: current };
}

function matchesShapeType(value: unknown, type: ShapeFieldType): boolean {
  switch (type) {
    case "string":
      return typeof value === "string";
    case "number":
      return typeof value === "number";
    case "boolean":
      return typeof value === "boolean";
    case "array":
      return Array.isArray(value);
    case "object":
      return value !== null && typeof value === "object" && !Array.isArray(value);
    default:
      return false;
  }
}

/**
 * Minimal runtime "does this look right" check: field existence + `typeof`.
 * No external schema library — deliberately not a full validator (no unions,
 * enums, or array-element checks). Intended for a short list of
 * business-critical fields (amounts, dates, status enums) so a backend
 * rename/removal fails loudly at the API boundary instead of surfacing as a
 * page-level `undefined`/`NaN` later.
 *
 * Throws the same `Invalid ApiEnvelope from <url>: ...` shape as
 * `assertApiEnvelopeShape` so callers keep a single contract-error channel.
 */
export function assertShape(
  value: unknown,
  url: string,
  fields: ShapeFieldSpec[],
  pathPrefix = "",
): void {
  for (const field of fields) {
    const { found, value: fieldValue } = resolveShapePath(value, field.path);
    const labeledPath = `${pathPrefix}${field.path}`;
    if (!found || fieldValue === undefined) {
      if (field.optional) continue;
      throw new Error(`Invalid ApiEnvelope from ${url}: missing \`${labeledPath}\``);
    }
    if (fieldValue === null) {
      if (field.optional) continue;
      throw new Error(
        `Invalid ApiEnvelope from ${url}: \`${labeledPath}\` is null, expected ${field.type}`,
      );
    }
    if (!matchesShapeType(fieldValue, field.type)) {
      throw new Error(
        `Invalid ApiEnvelope from ${url}: \`${labeledPath}\` is ${describePayloadBriefly(fieldValue)}, expected ${field.type}`,
      );
    }
  }
}

/** Keep cancellation and the deadline active until the response is consumed. */
export async function fetchWithOptionalTimeout<T>(
  fetchImpl: FetchLike,
  url: string,
  init: RequestInit,
  timeoutMs: number | null,
  path: string,
  consumeResponse: (response: Response) => Promise<T>,
): Promise<T> {
  const callerSignal = init.signal;
  if (callerSignal?.aborted) {
    throw callerSignal.reason;
  }
  if (timeoutMs === null) {
    if (!callerSignal) {
      return consumeResponse(await fetchImpl(url, init));
    }
    let rejectOnAbort!: () => void;
    const aborted = new Promise<never>((_resolve, reject) => {
      rejectOnAbort = () => reject(callerSignal.reason);
      callerSignal.addEventListener("abort", rejectOnAbort, { once: true });
    });
    try {
      return await Promise.race([
        aborted,
        (async () => {
          const response = await fetchImpl(url, init);
          callerSignal.throwIfAborted();
          return consumeResponse(response);
        })(),
      ]);
    } finally {
      callerSignal.removeEventListener("abort", rejectOnAbort);
    }
  }

  const controller = new AbortController();
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  let rejectOnAbort!: () => void;
  const aborted = new Promise<never>((_resolve, reject) => {
    rejectOnAbort = () => reject(controller.signal.reason);
    controller.signal.addEventListener("abort", rejectOnAbort, { once: true });
  });
  const abortForCaller = () => {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }
    controller.abort(callerSignal?.reason);
  };
  if (callerSignal) {
    callerSignal.addEventListener("abort", abortForCaller, { once: true });
    if (callerSignal.aborted) {
      abortForCaller();
    }
  }
  timeoutId = setTimeout(() => {
    controller.abort(new Error(`Request timed out: ${path}`));
  }, timeoutMs);
  try {
    return await Promise.race([
      aborted,
      (async () => {
        const response = await fetchImpl(url, { ...init, signal: controller.signal });
        controller.signal.throwIfAborted();
        return consumeResponse(response);
      })(),
    ]);
  } finally {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }
    callerSignal?.removeEventListener("abort", abortForCaller);
    controller.signal.removeEventListener("abort", rejectOnAbort);
  }
}

async function throwFailedResponse(
  response: Response,
  path: string,
  errorDetail: TransportErrorDetailMode,
): Promise<never> {
  const fallback = `Request failed: ${path} (${response.status})`;
  if (errorDetail === "json-detail") {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? fallback);
  }
  throw new Error(fallback);
}

/**
 * GET a governed `ApiEnvelope` response. Defaults preserve the historical
 * `client.ts` semantics (60s timeout, status-only error messages).
 */
export async function requestJson<T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  options?: TransportRequestOptions,
): Promise<ApiEnvelope<T>> {
  const timeoutMs = options?.timeoutMs === undefined ? DEFAULT_REQUEST_JSON_TIMEOUT_MS : options.timeoutMs;
  return fetchWithOptionalTimeout(
    fetchImpl,
    `${baseUrl}${path}`,
    { headers: { Accept: "application/json" }, signal: options?.signal },
    timeoutMs,
    path,
    async (response) => {
      if (!response.ok) {
        await throwFailedResponse(response, path, options?.errorDetail ?? "status-only");
      }
      const payload: unknown = await response.json();
      assertApiEnvelopeShape(payload, `${baseUrl}${path}`, options?.keyFields);
      return payload as ApiEnvelope<T>;
    },
  );
}

/** GET a plain (non-envelope) JSON response, e.g. health probes or ledgers. */
export async function requestPlainJson<T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  options?: TransportRequestOptions,
): Promise<T> {
  const timeoutMs = options?.timeoutMs === undefined ? DEFAULT_REQUEST_JSON_TIMEOUT_MS : options.timeoutMs;
  return fetchWithOptionalTimeout(
    fetchImpl,
    `${baseUrl}${path}`,
    { headers: { Accept: "application/json" }, signal: options?.signal },
    timeoutMs,
    path,
    async (response) => {
      if (!response.ok) {
        await throwFailedResponse(response, path, options?.errorDetail ?? "status-only");
      }
      return (await response.json()) as T;
    },
  );
}

/**
 * Action-style request (usually POST). Failed responses raise
 * `ActionRequestError` carrying status, run id, and backend detail.
 * No timeout, matching the historical behavior of both former copies.
 */
export async function requestActionJson<T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    const detailText =
      extractApiErrorDetail(body) ?? `Request failed: ${path} (${response.status})`;
    const runId = extractApiRunId(body);
    const rawDetail = extractRawDetail(body);
    const topErrorMessage = extractTopLevelErrorMessage(body);
    const nestedDetail =
      rawDetail && typeof rawDetail === "object" && !Array.isArray(rawDetail)
        ? (rawDetail as Record<string, unknown>).error_message
        : undefined;
    const errorMessageField =
      topErrorMessage ??
      (typeof nestedDetail === "string" && nestedDetail.trim() ? nestedDetail : undefined);
    throw new ActionRequestError(detailText, {
      status: response.status,
      runId,
      errorMessage: errorMessageField,
      detail: rawDetail,
    });
  }

  return (await response.json()) as T;
}

export async function requestText(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  fallbackFilename = "download.csv",
): Promise<{ content: string; filename: string }> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept: "text/csv, text/plain;q=0.9, */*;q=0.8",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  const contentDisposition = response.headers.get("Content-Disposition") ?? "";
  return {
    content: await response.text(),
    filename: parseDownloadFilename(contentDisposition, fallbackFilename),
  };
}

function parseDownloadFilename(contentDisposition: string, fallbackFilename: string) {
  const utf8Match = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(contentDisposition);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const filenameMatch = /filename=\"?([^\";]+)\"?/i.exec(contentDisposition);
  return filenameMatch?.[1] ?? fallbackFilename;
}

export async function requestBlob(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  fallbackFilename = "download.bin",
): Promise<{ content: Blob; filename: string }> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/octet-stream;q=0.9, */*;q=0.8",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  const contentDisposition = response.headers.get("Content-Disposition") ?? "";
  return {
    content: await response.blob(),
    filename: parseDownloadFilename(contentDisposition, fallbackFilename),
  };
}

export async function requestActionWithBody<TResponse, TBody>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  body: TBody,
): Promise<TResponse> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as TResponse;
}
