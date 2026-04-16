import { afterEach, describe, expect, it, vi } from "vitest";

import { getJobPollingConfig } from "../app/jobs/config";

describe("getJobPollingConfig", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("uses defaults when env is missing", () => {
    expect(getJobPollingConfig()).toEqual({
      intervalMs: 250,
      maxAttempts: 40,
    });
  });

  it("uses env overrides when provided", () => {
    vi.stubEnv("VITE_JOB_POLL_INTERVAL_MS", "1000");
    vi.stubEnv("VITE_JOB_POLL_MAX_ATTEMPTS", "99");

    expect(getJobPollingConfig()).toEqual({
      intervalMs: 1000,
      maxAttempts: 99,
    });
  });
});
