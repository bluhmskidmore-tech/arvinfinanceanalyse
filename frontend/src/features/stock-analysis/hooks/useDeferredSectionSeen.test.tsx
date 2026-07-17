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

  it("observes a node that is attached after the hook is enabled", () => {
    const observeNode = vi.fn();
    let notifyIntersecting: (() => void) | null = null;

    vi.stubGlobal(
      "IntersectionObserver",
      class TestIntersectionObserver {
        constructor(callback: (entries: Array<{ isIntersecting: boolean }>) => void) {
          notifyIntersecting = () => callback([{ isIntersecting: true }]);
        }

        observe = observeNode;
        disconnect = vi.fn();
      },
    );

    const { result } = renderHook(() => useDeferredSectionSeen<HTMLDivElement>(true));
    const node = document.createElement("div");

    act(() => {
      result.current.ref(node);
    });

    expect(observeNode).toHaveBeenCalledWith(node);
    act(() => {
      notifyIntersecting?.();
    });
    expect(result.current.seen).toBe(true);
  });
});
