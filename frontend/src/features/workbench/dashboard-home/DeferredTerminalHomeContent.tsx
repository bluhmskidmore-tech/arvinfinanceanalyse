import { lazy, Suspense, useEffect, useState } from "react";

import type { DashboardHomeFirstScreenHydration } from "./dashboardHomeFirstScreenTypes";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";
import { useDashboardHomeSupplementalHydration } from "./useDashboardHomeSupplementalHydration";
import styles from "./dashboardHome.module.css";

const DeferredTerminalHomeBody = lazy(() =>
  import("./DeferredTerminalHomeBody").then((module) => ({
    default: module.DeferredTerminalHomeBody,
  })),
);

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  cancelIdleCallback?: (handle: number) => void;
};

const BODY_REVEAL_KEYS = new Set(["ArrowDown", "PageDown", "End", " ", "Space"]);
const BODY_IDLE_MIN_DELAY_MS = 2_000;
const BODY_IDLE_TIMEOUT_MS = 1_200;
const BODY_TIMEOUT_FALLBACK_MS = 900;

type DeferredTerminalHomeContentProps = {
  snapshotBoundary: DashboardHomeSnapshotBoundary;
  userReachedDeferredContent: boolean;
  onFirstScreenHydrated?: (hydration: DashboardHomeFirstScreenHydration) => void;
};

export function DeferredTerminalHomeContent({
  snapshotBoundary,
  userReachedDeferredContent,
  onFirstScreenHydrated,
}: DeferredTerminalHomeContentProps) {
  const firstScreenHydration = useDashboardHomeSupplementalHydration(snapshotBoundary);
  const [loadBody, setLoadBody] = useState(false);

  useEffect(() => {
    onFirstScreenHydrated?.(firstScreenHydration);
  }, [firstScreenHydration, onFirstScreenHydrated]);

  useEffect(() => {
    if (userReachedDeferredContent) {
      setLoadBody(true);
      return undefined;
    }
    if (loadBody) {
      return undefined;
    }

    let isActive = true;
    const idleWindow = window as IdleWindow;
    let idleHandle: number | null = null;
    let timeoutHandle: number | null = null;
    let delayHandle: number | null = null;
    const cancelScheduledWork = () => {
      if (idleHandle != null) {
        idleWindow.cancelIdleCallback?.(idleHandle);
        idleHandle = null;
      }
      if (timeoutHandle != null) {
        window.clearTimeout(timeoutHandle);
        timeoutHandle = null;
      }
      if (delayHandle != null) {
        window.clearTimeout(delayHandle);
        delayHandle = null;
      }
    };
    const markReady = () => {
      if (isActive) {
        cancelScheduledWork();
        setLoadBody(true);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (BODY_REVEAL_KEYS.has(event.key)) {
        markReady();
      }
    };
    const removeReachListeners = () => {
      window.removeEventListener("scroll", markReady);
      window.removeEventListener("wheel", markReady);
      window.removeEventListener("touchmove", markReady);
      window.removeEventListener("keydown", handleKeyDown);
    };
    window.addEventListener("scroll", markReady, { passive: true });
    window.addEventListener("wheel", markReady, { passive: true });
    window.addEventListener("touchmove", markReady, { passive: true });
    window.addEventListener("keydown", handleKeyDown);

    const scheduleBodyLoad = () => {
      if (!isActive) {
        return;
      }
      if (idleWindow.requestIdleCallback) {
        idleHandle = idleWindow.requestIdleCallback(markReady, {
          timeout: BODY_IDLE_TIMEOUT_MS,
        });
        return;
      }
      timeoutHandle = window.setTimeout(markReady, BODY_TIMEOUT_FALLBACK_MS);
    };
    delayHandle = window.setTimeout(scheduleBodyLoad, BODY_IDLE_MIN_DELAY_MS);

    return () => {
      isActive = false;
      removeReachListeners();
      cancelScheduledWork();
    };
  }, [loadBody, userReachedDeferredContent]);

  if (!loadBody) {
    return <div aria-hidden="true" className={styles.dhTerminalDeferredPlaceholder} />;
  }

  return (
    <Suspense fallback={<div aria-hidden="true" className={styles.dhTerminalDeferredPlaceholder} />}>
      <DeferredTerminalHomeBody snapshotBoundary={snapshotBoundary} />
    </Suspense>
  );
}
