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

  it("emits progress updates for start and each polled status", async () => {
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
    const onUpdate = vi.fn();

    await runPollingTask({
      start,
      getStatus,
      onUpdate,
      intervalMs: 0,
      maxAttempts: 3,
    });

    expect(onUpdate).toHaveBeenNthCalledWith(1, {
      status: "queued",
      run_id: "job:queued",
    });
    expect(onUpdate).toHaveBeenNthCalledWith(2, {
      status: "running",
      run_id: "job:queued",
    });
    expect(onUpdate).toHaveBeenNthCalledWith(3, {
      status: "completed",
      run_id: "job:queued",
    });
  });

  it("uses a dynamic interval when provided", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
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

    try {
      const payload = await runPollingTask({
        start,
        getStatus,
        intervalMs: 999,
        getIntervalMs: () => 0,
        maxAttempts: 3,
      });

      expect(payload.status).toBe("completed");
      expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 0);
      expect(setTimeoutSpy).not.toHaveBeenCalledWith(expect.any(Function), 999);
    } finally {
      setTimeoutSpy.mockRestore();
    }
  });

  it("rejects without calling start when the signal is already aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    const start = vi.fn(async () => ({
      status: "queued",
      run_id: "job:aborted",
    }));
    const getStatus = vi.fn();

    await expect(
      runPollingTask({
        start,
        getStatus,
        signal: controller.signal,
      }),
    ).rejects.toThrow("任务轮询已取消");
    expect(start).not.toHaveBeenCalled();
    expect(getStatus).not.toHaveBeenCalled();
  });

  it("stops polling immediately when the signal aborts during the wait interval", async () => {
    const controller = new AbortController();
    const start = vi.fn(async () => ({
      status: "queued",
      run_id: "job:cancel",
    }));
    const getStatus = vi.fn(async () => ({
      status: "running",
      run_id: "job:cancel",
    }));

    const pollingPromise = runPollingTask({
      start,
      getStatus,
      intervalMs: 60_000,
      maxAttempts: 5,
      signal: controller.signal,
    });
    const guardedPromise = pollingPromise.catch((error: unknown) => error);

    await vi.waitFor(() => expect(getStatus).toHaveBeenCalledTimes(1));
    controller.abort();

    // 中断发生在 60s 等待间隔内：必须立即 reject，而不是等计时器走完。
    const settled = await guardedPromise;
    expect(settled).toBeInstanceOf(Error);
    expect((settled as Error).message).toBe("任务轮询已取消");
    expect(getStatus).toHaveBeenCalledTimes(1);
  });

  it("propagates a custom abort reason error", async () => {
    const controller = new AbortController();
    controller.abort(new Error("页面已卸载"));
    const start = vi.fn();
    const getStatus = vi.fn();

    await expect(
      runPollingTask({
        start,
        getStatus,
        signal: controller.signal,
      }),
    ).rejects.toThrow("页面已卸载");
    expect(start).not.toHaveBeenCalled();
  });

  it("throws a timeout error that includes the last run id and status", async () => {
    const start = vi.fn(async () => ({
      status: "queued",
      run_id: "job:stuck",
    }));
    const getStatus = vi.fn(async () => ({
      status: "running",
      run_id: "job:stuck",
    }));

    await expect(
      runPollingTask({
        start,
        getStatus,
        intervalMs: 0,
        maxAttempts: 2,
      }),
    ).rejects.toThrow(/任务轮询超时 \(run_id: job:stuck, 最后状态: running\)/);
    expect(getStatus).toHaveBeenCalled();
  });
});
