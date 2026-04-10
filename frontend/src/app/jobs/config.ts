function parsePositiveInt(value: string | undefined, fallback: number) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return Math.floor(parsed);
}

export function getJobPollingConfig() {
  return {
    intervalMs: parsePositiveInt(
      import.meta.env.VITE_JOB_POLL_INTERVAL_MS,
      250,
    ),
    maxAttempts: parsePositiveInt(
      import.meta.env.VITE_JOB_POLL_MAX_ATTEMPTS,
      40,
    ),
  };
}
