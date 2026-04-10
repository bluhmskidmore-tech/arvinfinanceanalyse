import { getJobPollingConfig } from "./config";

export type PollingTaskPayload = {
  status: string;
  run_id?: string;
  detail?: string | null;
  error_message?: string | null;
};

export type RunPollingTaskOptions<TPayload extends PollingTaskPayload> = {
  start: () => Promise<TPayload>;
  getStatus: (runId: string) => Promise<TPayload>;
  intervalMs?: number;
  maxAttempts?: number;
  isTerminal?: (status: string) => boolean;
  onUpdate?: (payload: TPayload) => void;
};

export async function runPollingTask<TPayload extends PollingTaskPayload>(
  options: RunPollingTaskOptions<TPayload>,
): Promise<TPayload> {
  const defaults = getJobPollingConfig();
  const {
    start,
    getStatus,
    intervalMs = defaults.intervalMs,
    maxAttempts = defaults.maxAttempts,
    isTerminal = (status: string) => status === "completed" || status === "failed",
    onUpdate,
  } = options;

  let payload = await start();
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
    onUpdate?.(payload);
    if (isTerminal(payload.status)) {
      return payload;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  const rid = payload.run_id ?? "—";
  throw new Error(`任务轮询超时 (run_id: ${rid}, 最后状态: ${payload.status})`);
}
