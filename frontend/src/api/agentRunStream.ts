export type AgentRunStreamOptions = {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  signal?: AbortSignal;
};

export type AgentRunEventHandler = (payload: unknown) => boolean | void;

/**
 * Connection-phase SSE failure: the stream never delivered a usable
 * event-stream response (fetch rejected, non-2xx status, wrong content type,
 * or a missing body). Callers should degrade to GET polling immediately
 * instead of reconnecting — retrying an unsupported or client-rejected
 * transport cannot succeed. Mid-stream failures (reader errors after the
 * stream was established) keep their original error type and remain
 * reconnectable.
 */
export class AgentRunStreamConnectionError extends Error {
  readonly status?: number;

  constructor(message: string, options: { status?: number } = {}) {
    super(message);
    this.name = "AgentRunStreamConnectionError";
    this.status = options.status;
  }
}

const defaultFetch = (...args: Parameters<typeof fetch>) => fetch(...args);

function isAbortError(error: unknown) {
  return error instanceof Error && error.name === "AbortError";
}

function normalizeBaseUrl(value: string | undefined) {
  return value?.trim().replace(/\/+$/, "") ?? "";
}

function getDefaultBaseUrl() {
  const value = import.meta.env.VITE_API_BASE_URL;
  return normalizeBaseUrl(typeof value === "string" ? value : undefined);
}

function dispatchEventBlock(block: string, onEvent: AgentRunEventHandler) {
  let eventType = "";
  const dataLines: string[] = [];

  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) {
      continue;
    }
    const separatorIndex = line.indexOf(":");
    const field = separatorIndex < 0 ? line : line.slice(0, separatorIndex);
    let value = separatorIndex < 0 ? "" : line.slice(separatorIndex + 1);
    if (value.startsWith(" ")) {
      value = value.slice(1);
    }
    if (field === "event") {
      eventType = value;
    } else if (field === "data") {
      dataLines.push(value);
    }
  }

  if (eventType !== "run_update" || dataLines.length === 0) {
    return false;
  }

  let payload: unknown;
  try {
    payload = JSON.parse(dataLines.join("\n"));
  } catch {
    throw new Error("Agent run SSE data is not valid JSON.");
  }
  return onEvent(payload) === true;
}

export async function streamAgentRunEvents(
  runId: string,
  onEvent: AgentRunEventHandler,
  options: AgentRunStreamOptions = {},
): Promise<void> {
  const fetchImpl = options.fetchImpl ?? defaultFetch;
  const baseUrl =
    options.baseUrl === undefined ? getDefaultBaseUrl() : normalizeBaseUrl(options.baseUrl);
  const path = `/api/agent/runs/${encodeURIComponent(runId)}/events`;
  let response: Response | undefined;
  try {
    response = await fetchImpl(`${baseUrl}${path}`, {
      method: "GET",
      headers: { Accept: "text/event-stream" },
      signal: options.signal,
    });
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }
    throw new AgentRunStreamConnectionError(
      `Agent run SSE connection failed: ${path} (${error instanceof Error ? error.message : "unknown error"})`,
    );
  }

  if (!response) {
    throw new AgentRunStreamConnectionError(`Agent run SSE response is unavailable: ${path}`);
  }
  if (!response.ok) {
    throw new AgentRunStreamConnectionError(`Agent run SSE request failed: ${path} (${response.status})`, {
      status: response.status,
    });
  }
  if (!response.headers.get("Content-Type")?.toLowerCase().includes("text/event-stream")) {
    throw new AgentRunStreamConnectionError("Agent run SSE response has an invalid content type.");
  }
  if (!response.body) {
    throw new AgentRunStreamConnectionError("Agent run SSE response body is unavailable.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let reachedEof = false;

  const dispatchAvailableBlocks = (flushRemainder = false) => {
    while (true) {
      const delimiter = /\r?\n\r?\n/.exec(buffer);
      if (!delimiter) {
        break;
      }
      const block = buffer.slice(0, delimiter.index);
      buffer = buffer.slice(delimiter.index + delimiter[0].length);
      if (dispatchEventBlock(block, onEvent)) {
        return true;
      }
    }
    if (flushRemainder && buffer.trim()) {
      const block = buffer;
      buffer = "";
      return dispatchEventBlock(block, onEvent);
    }
    return false;
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        reachedEof = true;
        buffer += decoder.decode();
        dispatchAvailableBlocks(true);
        return;
      }
      buffer += decoder.decode(value, { stream: true });
      if (dispatchAvailableBlocks()) {
        return;
      }
    }
  } finally {
    if (!reachedEof) {
      try {
        await reader.cancel();
      } catch {
        // The stream may already be aborted or disconnected.
      }
    }
    reader.releaseLock();
  }
}
