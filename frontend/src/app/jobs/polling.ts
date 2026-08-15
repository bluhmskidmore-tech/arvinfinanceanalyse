import { getJobPollingConfig } from "./config";

export type PollingTaskPayload = {
  status: string;
  run_id?: string;
  detail?: string | null;
  error_message?: string | null;
  report_date?: string;
  source_version?: string;
};

export type RunPollingTaskOptions<TPayload extends PollingTaskPayload> = {
  start: () => Promise<TPayload>;
  getStatus: (runId: string) => Promise<TPayload>;
  intervalMs?: number;
  getIntervalMs?: (payload: TPayload, attempt: number) => number;
  maxAttempts?: number;
  isTerminal?: (status: string) => boolean;
  onUpdate?: (payload: TPayload) => void;
  /**
   * 可选取消信号（AbortSignal 风格）。调用方在组件卸载/effect cleanup 时
   * abort，轮询会立刻停止（含等待间隔中），并以取消错误 reject；
   * 不传 signal 时行为与原来完全一致。
   */
  signal?: AbortSignal;
};

function pollingAbortError(signal: AbortSignal): Error {
  const reason: unknown = signal.reason;
  // abort() 不带参数时 reason 是默认 DOMException(AbortError)，统一归一成
  // 可读的取消错误；只透传调用方显式提供的自定义 Error reason。
  if (reason instanceof Error && reason.name !== "AbortError") {
    return reason;
  }
  return new Error("任务轮询已取消");
}

function throwIfAborted(signal: AbortSignal | undefined): void {
  if (signal?.aborted) {
    throw pollingAbortError(signal);
  }
}

function sleepUnlessAborted(ms: number, signal: AbortSignal | undefined): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(pollingAbortError(signal));
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(pollingAbortError(signal!));
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export async function runPollingTask<TPayload extends PollingTaskPayload>(
  options: RunPollingTaskOptions<TPayload>,
): Promise<TPayload> {
  const defaults = getJobPollingConfig();
  const {
    start,
    getStatus,
    intervalMs = defaults.intervalMs,
    getIntervalMs,
    maxAttempts = defaults.maxAttempts,
    isTerminal = (status: string) => status === "completed" || status === "failed",
    onUpdate,
    signal,
  } = options;

  throwIfAborted(signal);
  let payload = await start();
  throwIfAborted(signal);
  onUpdate?.(payload);
  if (isTerminal(payload.status)) {
    return payload;
  }

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const runId = payload.run_id;
    if (!runId) {
      throw new Error(`任务轮询缺少 run_id（最后状态：${payload.status}）`);
    }
    payload = await getStatus(runId);
    throwIfAborted(signal);
    onUpdate?.(payload);
    if (isTerminal(payload.status)) {
      return payload;
    }
    const nextIntervalMs = getIntervalMs?.(payload, attempt) ?? intervalMs;
    await sleepUnlessAborted(Math.max(0, nextIntervalMs), signal);
  }

  const rid = payload.run_id ?? "—";
  throw new Error(`任务轮询超时 (run_id: ${rid}, 最后状态: ${payload.status})`);
}
