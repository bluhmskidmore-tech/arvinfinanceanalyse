import { getJobPollingConfig } from "./config";

export type PollingTaskPayload = {
  status: string;
  run_id: string;
  detail?: string | null;
};

export type RunPollingTaskOptions<TPayload extends PollingTaskPayload> = {
  start: () => Promise<TPayload>;
  getStatus: (runId: string) => Promise<TPayload>;
  intervalMs?: number;
  maxAttempts?: number;
  isTerminal?: (status: string) => boolean;
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
  } = options;

  let payload = await start();
  if (isTerminal(payload.status)) {
    return payload;
  }

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    payload = await getStatus(payload.run_id);
    if (isTerminal(payload.status)) {
      return payload;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error("任务轮询超时");
}
