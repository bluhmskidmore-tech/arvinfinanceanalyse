import { act, fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDeferredHomeContent } from "./useDeferredHomeContent";

const deferredModuleLoads = vi.hoisted(() => ({ content: vi.fn(), body: vi.fn() }));
vi.mock("./DeferredTerminalHomeContent", () => {
  deferredModuleLoads.content();
  return { DeferredTerminalHomeContent: () => null };
});
vi.mock("./DeferredTerminalHomeBody", () => {
  deferredModuleLoads.body();
  return { DeferredTerminalHomeBody: () => null };
});

function Harness({ snapshotReady }: { snapshotReady: boolean }) {
  const layoutRef = useRef<HTMLDivElement | null>(null);
  const { deferredContentSentinelRef, shouldLoad, userReachedDeferredContent } =
    useDeferredHomeContent(snapshotReady, layoutRef);
  return (
    <>
      <style>{".deferred-home-test-scroll { overflow-y: auto; }"}</style>
      <div ref={layoutRef} data-testid="scroll-root" className="deferred-home-test-scroll">
        <div ref={deferredContentSentinelRef} data-testid="sentinel" />
        <output data-testid="revealed">{String(shouldLoad)}</output>
        <output data-testid="requested">{String(userReachedDeferredContent)}</output>
      </div>
    </>
  );
}

function stubScheduling() {
  const callbacks: IntersectionObserverCallback[] = [];
  const idleWork = new Map<number, () => void>();
  let nextHandle = 0;
  const observe = vi.fn();
  const disconnect = vi.fn();
  vi.stubGlobal("IntersectionObserver", vi.fn(function Observer(callback: IntersectionObserverCallback) {
    callbacks.push(callback);
    return { observe, disconnect };
  }));
  vi.stubGlobal("requestIdleCallback", vi.fn((callback: () => void) => {
    const handle = ++nextHandle;
    idleWork.set(handle, callback);
    return handle;
  }));
  vi.stubGlobal("cancelIdleCallback", vi.fn((handle: number) => idleWork.delete(handle)));
  const intersect = (visible: boolean, callback = callbacks.at(-1)) => {
    callback?.([
      { isIntersecting: visible, intersectionRatio: visible ? 1 : 0 } as IntersectionObserverEntry,
    ], {} as IntersectionObserver);
  };
  const flushIdle = () => {
    const pending = Array.from(idleWork.values());
    idleWork.clear();
    for (const callback of pending) callback();
  };
  return { observe, disconnect, callbacks, intersect, flushIdle, pendingIdle: () => idleWork.size };
}

describe("useDeferredHomeContent", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("observes immediately but leaves initial proximity outside the 400ms first-screen budget", () => {
    const scheduled = stubScheduling();
    render(<Harness snapshotReady />);
    expect(scheduled.observe).toHaveBeenCalledWith(screen.getByTestId("sentinel"));
    act(() => scheduled.intersect(true));
    act(() => vi.advanceTimersByTime(400));
    expect(screen.getByTestId("revealed")).toHaveTextContent("false");
    expect(scheduled.pendingIdle()).toBe(0);

    act(() => vi.runOnlyPendingTimers());
    expect(scheduled.pendingIdle()).toBe(1);
    expect(screen.getByTestId("revealed")).toHaveTextContent("false");
    act(() => scheduled.flushIdle());
    expect(screen.getByTestId("revealed")).toHaveTextContent("true");
  });

  it("reveals on explicit traversal near the boundary without waiting for passive work", () => {
    const scheduled = stubScheduling();
    render(<Harness snapshotReady />);
    act(() => scheduled.intersect(true));
    expect(screen.getByTestId("revealed")).toHaveTextContent("false");
    fireEvent.scroll(screen.getByTestId("scroll-root"));
    expect(screen.getByTestId("revealed")).toHaveTextContent("true");
    expect(scheduled.pendingIdle()).toBe(0);
  });

  it("keeps light input deferred until the reader actually approaches the boundary", () => {
    const scheduled = stubScheduling();
    render(<Harness snapshotReady />);
    fireEvent.wheel(screen.getByTestId("scroll-root"));
    fireEvent.keyDown(window, { key: "PageDown" });
    act(() => scheduled.intersect(false));
    expect(screen.getByTestId("requested")).toHaveTextContent("false");
    act(() => scheduled.intersect(true));
    expect(screen.getByTestId("revealed")).toHaveTextContent("true");
  });

  it("keeps a distant body unloaded after passive idle and reveals immediately on later traversal", async () => {
    const scheduled = stubScheduling();
    render(<Harness snapshotReady />);
    act(() => scheduled.intersect(false));
    act(() => vi.runOnlyPendingTimers());
    act(() => scheduled.flushIdle());
    expect(screen.getByTestId("requested")).toHaveTextContent("false");
    expect(screen.getByTestId("revealed")).toHaveTextContent("false");
    vi.useRealTimers();
    await vi.dynamicImportSettled();
    expect(deferredModuleLoads.content).not.toHaveBeenCalled();
    expect(deferredModuleLoads.body).not.toHaveBeenCalled();

    fireEvent.scroll(screen.getByTestId("scroll-root"));
    act(() => scheduled.intersect(true));
    expect(screen.getByTestId("revealed")).toHaveTextContent("true");
    expect(scheduled.pendingIdle()).toBe(0);
  });

  it("retains explicit demand while the snapshot is pending and reveals as soon as it is ready", () => {
    const scheduled = stubScheduling();
    const { rerender } = render(<Harness snapshotReady={false} />);
    fireEvent.scroll(screen.getByTestId("scroll-root"));
    act(() => scheduled.intersect(true));
    expect(screen.getByTestId("requested")).toHaveTextContent("true");
    expect(screen.getByTestId("revealed")).toHaveTextContent("false");
    expect(scheduled.pendingIdle()).toBe(0);

    rerender(<Harness snapshotReady />);
    expect(screen.getByTestId("revealed")).toHaveTextContent("true");
    expect(scheduled.pendingIdle()).toBe(0);
    // Revealed content stays mounted; the snapshot boundary owns dated reads.
    rerender(<Harness snapshotReady={false} />);
    expect(screen.getByTestId("revealed")).toHaveTextContent("true");
  });

  it("cancels passive work and ignores disconnected observers when the snapshot becomes unavailable", () => {
    const scheduled = stubScheduling();
    const { rerender } = render(<Harness snapshotReady />);
    const previousObserver = scheduled.callbacks.at(-1);
    act(() => vi.runOnlyPendingTimers());
    expect(scheduled.pendingIdle()).toBe(1);
    rerender(<Harness snapshotReady={false} />);
    expect(scheduled.pendingIdle()).toBe(0);
    act(() => scheduled.intersect(true, previousObserver));
    rerender(<Harness snapshotReady />);
    act(() => vi.runOnlyPendingTimers());
    act(() => scheduled.flushIdle());
    expect(screen.getByTestId("revealed")).toHaveTextContent("false");
  });

  it("uses one post-snapshot idle fallback when observers are unavailable", () => {
    const scheduled = stubScheduling();
    vi.stubGlobal("IntersectionObserver", undefined);
    const { rerender } = render(<Harness snapshotReady={false} />);
    act(() => vi.runOnlyPendingTimers());
    expect(scheduled.pendingIdle()).toBe(0);
    rerender(<Harness snapshotReady />);
    act(() => vi.runOnlyPendingTimers());
    expect(scheduled.pendingIdle()).toBe(1);
    expect(screen.getByTestId("revealed")).toHaveTextContent("false");
    act(() => scheduled.flushIdle());
    expect(screen.getByTestId("revealed")).toHaveTextContent("true");
  });
});
