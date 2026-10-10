import { StrictMode, type PropsWithChildren } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { runPollingTask } from "./polling";
import { usePollingTaskSignal } from "./usePollingTaskSignal";

describe("page polling lifetime", () => {
  it("keeps the remounted StrictMode signal active and cancels only the local pending wait", async () => {
    const wrapper = ({ children }: PropsWithChildren) => <StrictMode>{children}</StrictMode>;
    const { result, unmount } = renderHook(usePollingTaskSignal, { wrapper });
    const signal = result.current();
    expect(signal?.aborted).toBe(false);
    const getStatus = vi.fn(() => new Promise<never>(() => undefined));
    const work = runPollingTask({
      start: async () => ({ status: "queued", run_id: "existing-run" }),
      getStatus,
      signal,
    }).catch((error: unknown) => error);
    await waitFor(() => expect(getStatus).toHaveBeenCalledOnce());
    unmount();
    expect(signal?.aborted).toBe(true);
    expect(await work).toEqual(new Error("任务轮询已取消"));
    expect(getStatus).toHaveBeenCalledWith("existing-run", signal);
  });
});
