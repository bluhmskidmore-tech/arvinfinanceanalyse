import { useCallback, useEffect, useRef, useState } from "react";

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  cancelIdleCallback?: (handle: number) => void;
};

const REVEAL_KEYS = new Set(["ArrowDown", "PageDown", "End", " ", "Space"]);
const FIRST_SCREEN_IDLE_DELAY_MS = 600;
const DEFERRED_IDLE_TIMEOUT_MS = 1_200;

function resolveHomeScrollRoot(node: HTMLElement | null): HTMLElement | null {
  return node && /^(auto|scroll|overlay)$/.test(window.getComputedStyle(node).overflowY)
    ? node
    : null;
}

// One owner for boundary demand and first-screen idle work. The lazy content
// tree loads modules when requested; dated reads remain owned by its hooks.
export function useDeferredHomeContent(
  snapshotReady: boolean,
  layoutScrollRootRef: { current: HTMLElement | null },
) {
  const deferredContentSentinelRef = useRef<HTMLDivElement | null>(null);
  const [revealState, setRevealState] = useState<"waiting" | "requested" | "revealed">("waiting");
  const nearBoundaryRef = useRef(false);
  const userTraversedRef = useRef(false);
  const firstScreenIdleReadyRef = useRef(false);

  const requestReveal = useCallback(() => {
    setRevealState((current) => current === "revealed" || snapshotReady ? "revealed" : "requested");
  }, [snapshotReady]);

  useEffect(() => {
    if (revealState !== "waiting") return undefined;
    const scrollRoot = resolveHomeScrollRoot(layoutScrollRootRef.current);
    const scrollTarget: Window | HTMLElement = scrollRoot ?? window;
    const hasObserver = typeof window.IntersectionObserver !== "undefined";
    const handleTraversal = () => {
      userTraversedRef.current = true;
      // With an observer, light or unrelated input is not a demand for the body.
      if (!hasObserver || nearBoundaryRef.current) requestReveal();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (REVEAL_KEYS.has(event.key)) handleTraversal();
    };
    for (const eventName of ["scroll", "wheel", "touchmove"]) {
      scrollTarget.addEventListener(eventName, handleTraversal, { passive: true });
    }
    window.addEventListener("keydown", handleKeyDown);

    const sentinel = deferredContentSentinelRef.current;
    let active = true;
    const observer = hasObserver && sentinel ? new window.IntersectionObserver((entries) => {
      if (!active) return;
      nearBoundaryRef.current = entries.some((entry) => entry.isIntersecting || entry.intersectionRatio > 0);
      // Initial proximity only warms after first-screen idle. Explicit traversal
      // reaches the same boundary immediately, even before the passive timer.
      if (nearBoundaryRef.current && (userTraversedRef.current || firstScreenIdleReadyRef.current)) {
        requestReveal();
      }
    }, { root: scrollRoot, rootMargin: "0px 0px 200px 0px" }) : null;
    if (sentinel) observer?.observe(sentinel);

    return () => {
      active = false;
      observer?.disconnect();
      for (const eventName of ["scroll", "wheel", "touchmove"]) {
        scrollTarget.removeEventListener(eventName, handleTraversal);
      }
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [layoutScrollRootRef, requestReveal, revealState]);

  useEffect(() => {
    if (snapshotReady && revealState === "requested") setRevealState("revealed");
  }, [revealState, snapshotReady]);

  useEffect(() => {
    if (!snapshotReady || revealState !== "waiting" || firstScreenIdleReadyRef.current) return undefined;
    let active = true;
    const idleWindow = window as IdleWindow;
    let idleHandle: number | undefined;
    const finishIdle = () => {
      if (!active) return;
      firstScreenIdleReadyRef.current = true;
      if (nearBoundaryRef.current || typeof window.IntersectionObserver === "undefined") requestReveal();
    };
    // One passive window protects first paint; there is no extra delay after
    // reader demand, body mounting or a usable cached snapshot.
    const delayHandle = window.setTimeout(() => {
      if (idleWindow.requestIdleCallback) {
        idleHandle = idleWindow.requestIdleCallback(finishIdle, { timeout: DEFERRED_IDLE_TIMEOUT_MS });
      } else {
        finishIdle();
      }
    }, FIRST_SCREEN_IDLE_DELAY_MS);
    return () => {
      active = false;
      window.clearTimeout(delayHandle);
      if (idleHandle != null) idleWindow.cancelIdleCallback?.(idleHandle);
    };
  }, [requestReveal, revealState, snapshotReady]);

  return {
    deferredContentSentinelRef,
    shouldLoad: revealState === "revealed",
    userReachedDeferredContent: revealState !== "waiting",
  };
}
