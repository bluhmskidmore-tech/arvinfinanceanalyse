import {
  AgentRunStreamConnectionError,
  streamAgentRunEvents as defaultStreamAgentRunEvents,
  type AgentRunEventHandler,
  type AgentRunStreamOptions,
} from "../../../api/agentRunStream";
import {
  AGENT_RUN_POLL_MAX_ATTEMPTS,
  AGENT_RUN_POLL_NETWORK_RECOVERABLE_MESSAGE,
  AGENT_RUN_POLL_TIMEOUT_RECOVERABLE_MESSAGE,
  AGENT_RUN_POLL_TRANSIENT_RETRY_LIMIT,
  getAgentRunPollIntervalMs,
  getAgentRunPollTransientRetryDelayMs,
  isAgentRunPayload,
  isTerminalAgentRunStatus,
  normalizeAgentRunPayload,
} from "../lib/agentWorkbenchModel";
import type { AgentRunPayload } from "../lib/agentWorkbenchModel";

export type StreamAgentRunEvents = (
  runId: string,
  onEvent: AgentRunEventHandler,
  options?: AgentRunStreamOptions,
) => Promise<void>;

/** SSE 断开后允许的最大重连次数；预算耗尽才降级 GET 轮询。 */
export const AGENT_RUN_SSE_RECONNECT_LIMIT = 2;

/** SSE 重连退避：第 1 次 1s，第 2 次起 3s（reconnectAttempt 从 1 起）。 */
export function getAgentRunSseReconnectDelayMs(reconnectAttempt: number) {
  return reconnectAttempt <= 1 ? 1000 : 3000;
}

/**
 * 连接期失败（4xx/5xx、不支持 event-stream、fetch 拒绝）说明该环境下 SSE 无法
 * 建立，重试没有意义，直接降级轮询；只有“已建立后断开”（中流错误 / 终态前
 * EOF）才值得有限重连。abort 不属于可重连失败，由调用方按中止语义处理。
 */
function isReconnectableStreamFailure(error: unknown) {
  if (isAbortError(error)) {
    return false;
  }
  return !(error instanceof AgentRunStreamConnectionError);
}

type WaitForAgentRunTerminalOptions = {
  runId: string;
  initialPayload?: AgentRunPayload;
  streamAgentRunEvents?: StreamAgentRunEvents;
  fetchAgentRunStatus: (runId: string) => Promise<AgentRunPayload>;
  canCommit: () => boolean;
  onRunUpdate: (payload: AgentRunPayload) => void;
  signal?: AbortSignal;
};

export async function waitForAgentRunTerminal(
  options: WaitForAgentRunTerminalOptions,
): Promise<AgentRunPayload> {
  const {
    runId,
    initialPayload,
    fetchAgentRunStatus,
    canCommit,
    onRunUpdate,
    signal,
  } = options;
  const streamAgentRunEvents = options.streamAgentRunEvents ?? defaultStreamAgentRunEvents;
  let latestPayload = initialPayload;
  let terminalPayload = isTerminalPayload(initialPayload) ? initialPayload : undefined;
  let lastSnapshot = initialPayload ? JSON.stringify(initialPayload) : undefined;

  const publishSnapshot = (payload: AgentRunPayload) => {
    latestPayload = payload;
    const snapshot = JSON.stringify(payload);
    if (snapshot === lastSnapshot) {
      return;
    }
    lastSnapshot = snapshot;
    if (canCommit()) {
      onRunUpdate(payload);
    }
  };

  if (terminalPayload) {
    return terminalPayload;
  }

  let streamPayloadInvalid = false;
  const streamOnce = () =>
    streamAgentRunEvents(
      runId,
      (value) => {
        if (!isAgentRunPayload(value) || value.run_id !== runId) {
          streamPayloadInvalid = true;
          return true;
        }
        const payload = normalizeAgentRunPayload(value);
        publishSnapshot(payload);
        if (isTerminalPayload(payload)) {
          terminalPayload = payload;
          return true;
        }
        return false;
      },
      { signal },
    );

  // SSE 有限重连：后端在终态前不会正常关流（服务端只在终态后 return），因此
  // “中流失败 / 终态前 EOF”视为断开，按 1s/3s 退避重连（每个 run_update 都是
  // 全量快照，publishSnapshot 以 JSON 去重，重连不丢事件也不重复发布）。
  // 连接期失败与无效载荷保持原行为：立即降级 GET 轮询。
  let reconnectAttempt = 0;
  while (true) {
    let streamThrew = false;
    let streamFailure: unknown;
    try {
      await streamOnce();
    } catch (error) {
      streamThrew = true;
      streamFailure = error;
    }

    if (terminalPayload) {
      return terminalPayload;
    }
    throwIfAborted(signal);
    if (streamPayloadInvalid) {
      break;
    }
    if (streamThrew && !isReconnectableStreamFailure(streamFailure)) {
      break;
    }
    if (reconnectAttempt >= AGENT_RUN_SSE_RECONNECT_LIMIT) {
      break;
    }
    reconnectAttempt += 1;
    await sleepWithAbort(getAgentRunSseReconnectDelayMs(reconnectAttempt), signal);
  }

  const fallbackPayload = await pollAgentRunUntilTerminal({
    runId,
    initialPayload: latestPayload,
    fetchAgentRunStatus,
    onUpdate: publishSnapshot,
    signal,
  });

  if (streamPayloadInvalid && fallbackPayload.run_id !== runId) {
    throw new Error("Agent run status response does not match the requested run.");
  }
  return fallbackPayload;
}

export type PollAgentRunUntilTerminalOptions = {
  runId: string;
  initialPayload?: AgentRunPayload;
  fetchAgentRunStatus: (runId: string) => Promise<AgentRunPayload>;
  onUpdate?: (payload: AgentRunPayload) => void;
  signal?: AbortSignal;
};

/**
 * Agent 专用状态轮询：支持 AbortSignal 中止，并对瞬时错误（网络抖动等）做有限次
 * 指数退避重试，重试预算耗尽或轮询超时都会抛出“可恢复”文案的错误，而不是把
 * 仍在后台运行的任务判死。
 */
export async function pollAgentRunUntilTerminal({
  runId,
  initialPayload,
  fetchAgentRunStatus,
  onUpdate,
  signal,
}: PollAgentRunUntilTerminalOptions): Promise<AgentRunPayload> {
  let payload = initialPayload;
  if (payload) {
    onUpdate?.(payload);
    if (isTerminalAgentRunStatus(payload.status)) {
      return payload;
    }
  }

  let consecutiveErrorCount = 0;
  for (let attempt = 0; attempt < AGENT_RUN_POLL_MAX_ATTEMPTS; attempt += 1) {
    throwIfAborted(signal);
    try {
      payload = await fetchAgentRunStatus(runId);
      consecutiveErrorCount = 0;
    } catch (error) {
      throwIfAborted(signal);
      if (isAbortError(error)) {
        throw error;
      }
      consecutiveErrorCount += 1;
      if (consecutiveErrorCount > AGENT_RUN_POLL_TRANSIENT_RETRY_LIMIT) {
        throw new Error(AGENT_RUN_POLL_NETWORK_RECOVERABLE_MESSAGE);
      }
      await sleepWithAbort(getAgentRunPollTransientRetryDelayMs(consecutiveErrorCount), signal);
      continue;
    }
    onUpdate?.(payload);
    if (isTerminalAgentRunStatus(payload.status)) {
      return payload;
    }
    await sleepWithAbort(getAgentRunPollIntervalMs(payload, attempt), signal);
  }
  throw new Error(AGENT_RUN_POLL_TIMEOUT_RECOVERABLE_MESSAGE);
}

export function isAbortError(error: unknown) {
  return error instanceof Error && error.name === "AbortError";
}

function isTerminalPayload(payload: AgentRunPayload | undefined): payload is AgentRunPayload {
  return payload !== undefined && isTerminalAgentRunStatus(payload.status);
}

function createAbortError() {
  const error = new Error("Agent run wait was aborted.");
  error.name = "AbortError";
  return error;
}

function throwIfAborted(signal: AbortSignal | undefined) {
  if (signal?.aborted) {
    throw createAbortError();
  }
}

function sleepWithAbort(delayMs: number, signal: AbortSignal | undefined) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(createAbortError());
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(createAbortError());
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, Math.max(0, delayMs));
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}
