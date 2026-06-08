import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useDeferredSectionSeen } from "./useDeferredSectionSeen";

describe("useDeferredSectionSeen", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("stays hidden while deferred sections are disabled", () => {
    vi.useFakeTimers();
    vi.stubGlobal("IntersectionObserver", undefined);

    const { result } = renderHook(() => useDeferredSectionSeen<HTMLDivElement>(false, 20));

    act(() => {
      vi.advanceTimersByTime(40);
    });

    expect(result.current.seen).toBe(false);
  });

  it("reveals after the fallback delay when IntersectionObserver is unavailable", () => {
    vi.useFakeTimers();
    vi.stubGlobal("IntersectionObserver", undefined);

    const { result } = renderHook(() => useDeferredSectionSeen<HTMLDivElement>(true, 20));

    expect(result.current.seen).toBe(false);

    act(() => {
      vi.advanceTimersByTime(20);
    });

    expect(result.current.seen).toBe(true);
  });
});
