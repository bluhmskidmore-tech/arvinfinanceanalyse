import { act, render, renderHook } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useLazyMount } from "./useLazyMount";

type MockObserver = {
  observe: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
  trigger: (isIntersecting: boolean) => void;
};

function stubIntersectionObserver(): MockObserver {
  const callbacks: IntersectionObserverCallback[] = [];
  const observe = vi.fn();
  const disconnect = vi.fn();
  const instance: MockObserver = {
    observe,
    disconnect,
    trigger: (isIntersecting: boolean) => {
      for (const callback of callbacks) {
        callback(
          [{ isIntersecting } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      }
    },
  };
  const MockObserver = vi.fn(function MockIntersectionObserver(callback: IntersectionObserverCallback) {
    callbacks.push(callback);
    return instance;
  });
  vi.stubGlobal("IntersectionObserver", MockObserver);
  return instance;
}

describe("useLazyMount", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("starts with shouldMount false", () => {
    vi.useFakeTimers();
    vi.stubGlobal("IntersectionObserver", undefined);

    const { result } = renderHook(() => useLazyMount());

    expect(result.current.shouldMount).toBe(false);
  });

  it("mounts after fallbackDelayMs when IntersectionObserver is unavailable", () => {
    vi.useFakeTimers();
    vi.stubGlobal("IntersectionObserver", undefined);

    const { result } = renderHook(() => useLazyMount({ fallbackDelayMs: 60 }));

    expect(result.current.shouldMount).toBe(false);

    act(() => {
      vi.advanceTimersByTime(60);
    });

    expect(result.current.shouldMount).toBe(true);
  });

  it("mounts when the observer reports the element is intersecting", () => {
    vi.useFakeTimers();
    const observer = stubIntersectionObserver();

    const state = { shouldMount: false };
    function Probe() {
      const lazy = useLazyMount({ fallbackDelayMs: 60 });
      state.shouldMount = lazy.shouldMount;
      return createElement("div", { ref: lazy.ref });
    }

    render(createElement(Probe));

    expect(state.shouldMount).toBe(false);
    expect(observer.observe).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(60);
    });

    expect(state.shouldMount).toBe(false);
    expect(observer.disconnect).not.toHaveBeenCalled();

    act(() => {
      observer.trigger(true);
    });

    expect(state.shouldMount).toBe(true);
    expect(observer.disconnect).toHaveBeenCalledTimes(1);
  });
});
