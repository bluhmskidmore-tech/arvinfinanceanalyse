import type { AgentRunDeltaEvent } from "./contracts";
import {
  AgentRunStreamConnectionError,
  type AgentRunStreamOptions,
} from "./agentRunStream";

type AgentLabRunStreamHandlers = {
  onRunUpdate: (payload: unknown) => boolean | void;
  onRunDelta: (payload: AgentRunDeltaEvent) => void;
};

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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isAgentRunDeltaEvent(value: unknown, runId: string): value is AgentRunDeltaEvent {
  return (
    isRecord(value) &&
    value.run_id === runId &&
    typeof value.seq === "number" &&
    Number.isInteger(value.seq) &&
    value.seq > 0 &&
    value.channel === "answer" &&
    typeof value.text === "string" &&
    value.text.length > 0 &&
    typeof value.created_at === "string" &&
    value.created_at.length > 0
  );
}

function parseEventBlock(block: string) {
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

  return {
    eventType,
    data: dataLines.length > 0 ? dataLines.join("\n") : null,
  };
}

export async function streamAgentLabRunEvents(
  runId: string,
  handlers: AgentLabRunStreamHandlers,
  options: AgentRunStreamOptions & { afterSeq?: number } = {},
): Promise<void> {
  const fetchImpl = options.fetchImpl ?? defaultFetch;
  const baseUrl =
    options.baseUrl === undefined ? getDefaultBaseUrl() : normalizeBaseUrl(options.baseUrl);
  const query = new URLSearchParams({
    include_deltas: "true",
    after_seq: String(Math.max(0, options.afterSeq ?? 0)),
  });
  const path = `/api/agent/runs/${encodeURIComponent(runId)}/events?${query.toString()}`;
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
      `Agent lab SSE connection failed: ${path} (${error instanceof Error ? error.message : "unknown error"})`,
    );
  }

  if (!response) {
    throw new AgentRunStreamConnectionError(`Agent lab SSE response is unavailable: ${path}`);
  }
  if (!response.ok) {
    throw new AgentRunStreamConnectionError(`Agent lab SSE request failed: ${path} (${response.status})`, {
      status: response.status,
    });
  }
  if (!response.headers.get("Content-Type")?.toLowerCase().includes("text/event-stream")) {
    throw new AgentRunStreamConnectionError("Agent lab SSE response has an invalid content type.");
  }
  if (!response.body) {
    throw new AgentRunStreamConnectionError("Agent lab SSE response body is unavailable.");
  }

  let lastAcceptedDeltaSeq = Math.max(0, options.afterSeq ?? 0);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let reachedEof = false;

  const dispatchBlock = (block: string) => {
    const { eventType, data } = parseEventBlock(block);
    if (!eventType || !data) {
      return false;
    }

    let payload: unknown;
    try {
      payload = JSON.parse(data);
    } catch {
      if (eventType === "run_update" || eventType === "run_delta") {
        throw new Error(`Agent lab SSE ${eventType} data is not valid JSON.`);
      }
      return false;
    }

    if (eventType === "run_update") {
      return handlers.onRunUpdate(payload) === true;
    }

    if (eventType === "run_delta") {
      if (!isAgentRunDeltaEvent(payload, runId)) {
        throw new Error("Agent lab SSE run_delta payload is invalid.");
      }
      if (payload.seq <= lastAcceptedDeltaSeq) {
        return false;
      }
      if (payload.seq !== lastAcceptedDeltaSeq + 1) {
        throw new Error("Agent lab SSE run_delta sequence is out of order.");
      }
      lastAcceptedDeltaSeq = payload.seq;
      handlers.onRunDelta(payload);
      return false;
    }

    return false;
  };

  const dispatchAvailableBlocks = (flushRemainder = false) => {
    while (true) {
      const delimiter = /\r?\n\r?\n/.exec(buffer);
      if (!delimiter) {
        break;
      }
      const block = buffer.slice(0, delimiter.index);
      buffer = buffer.slice(delimiter.index + delimiter[0].length);
      if (dispatchBlock(block)) {
        return true;
      }
    }
    if (flushRemainder && buffer.trim()) {
      const block = buffer;
      buffer = "";
      return dispatchBlock(block);
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
