import { describe, expect, it, vi } from "vitest";

import { runPollingTask } from "../app/jobs/polling";

describe("runPollingTask", () => {
  it("returns immediately when the trigger is already terminal", async () => {
    const start = vi.fn(async () => ({
      status: "completed",
      run_id: "job:done",
    }));
    const getStatus = vi.fn();

    const payload = await runPollingTask({
      start,
      getStatus,
    });

    expect(payload.status).toBe("completed");
    expect(getStatus).not.toHaveBeenCalled();
  });

  it("polls until terminal status", async () => {
    const start = vi.fn(async () => ({
      status: "queued",
      run_id: "job:queued",
    }));
    const getStatus = vi
      .fn()
      .mockResolvedValueOnce({
        status: "running",
        run_id: "job:queued",
      })
      .mockResolvedValueOnce({
        status: "completed",
        run_id: "job:queued",
      });

    const payload = await runPollingTask({
      start,
      getStatus,
      intervalMs: 0,
      maxAttempts: 3,
    });

    expect(payload.status).toBe("completed");
    expect(getStatus).toHaveBeenCalledTimes(2);
  });
});
