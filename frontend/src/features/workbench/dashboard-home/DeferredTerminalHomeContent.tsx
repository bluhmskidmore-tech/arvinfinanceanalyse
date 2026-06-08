import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";

import type { DashboardHomeFirstScreenHydration } from "./dashboardHomeFirstScreenTypes";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";
import { useDashboardHomeSupplementalHydration } from "./useDashboardHomeSupplementalHydration";
import styles from "./dashboardHomeShell.module.css";

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
const BODY_IDLE_TIMEOUT_MS = 1_200;
const BODY_TIMEOUT_FALLBACK_MS = 900;

type DeferredTerminalHomeContentProps = {
  snapshotBoundary: DashboardHomeSnapshotBoundary;
  userReachedDeferredContent: boolean;
  focusPolicyFunding?: boolean;
  onFirstScreenHydrated?: (hydration: DashboardHomeFirstScreenHydration) => void;
};

function firstScreenHydrationSignature(hydration: DashboardHomeFirstScreenHydration): string {
  return JSON.stringify({
    reportDate: hydration.reportDate,
    headerStatus: hydration.headerStatus,
    decisionRail: hydration.decisionRail,
    terminalKpis: hydration.terminalKpis.map((kpi) => ({
      id: kpi.id,
      value: kpi.value,
      unit: kpi.unit,
      delta: kpi.delta,
      deltaTone: kpi.deltaTone,
      state: kpi.state,
    })),
    keyRiskStrip: hydration.keyRiskStrip.map((item) => ({
      id: item.id,
      value: item.value,
      delta: item.delta,
      deltaTone: item.deltaTone,
    })),
  });
}

export function DeferredTerminalHomeContent({
  snapshotBoundary,
  userReachedDeferredContent,
  focusPolicyFunding = false,
  onFirstScreenHydrated,
}: DeferredTerminalHomeContentProps) {
  const [loadFirstScreenHydration, setLoadFirstScreenHydration] = useState(false);
  const firstScreenHydration = useDashboardHomeSupplementalHydration(snapshotBoundary, {
    enabled: loadFirstScreenHydration,
  });
  const hydrationSignature = useMemo(
    () => firstScreenHydrationSignature(firstScreenHydration),
    [firstScreenHydration],
  );
  const emittedHydrationSignatureRef = useRef<string | null>(null);
  const [loadBody, setLoadBody] = useState(false);

  useEffect(() => {
    if (emittedHydrationSignatureRef.current === hydrationSignature) {
      return;
    }
    emittedHydrationSignatureRef.current = hydrationSignature;
    onFirstScreenHydrated?.(firstScreenHydration);
  }, [firstScreenHydration, hydrationSignature, onFirstScreenHydrated]);

  useEffect(() => {
    if (focusPolicyFunding) {
      setLoadBody(true);
      return undefined;
    }

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
    const cancelScheduledWork = () => {
      if (idleHandle != null) {
        idleWindow.cancelIdleCallback?.(idleHandle);
        idleHandle = null;
      }
      if (timeoutHandle != null) {
        window.clearTimeout(timeoutHandle);
        timeoutHandle = null;
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
    scheduleBodyLoad();

    return () => {
      isActive = false;
      removeReachListeners();
      cancelScheduledWork();
    };
  }, [focusPolicyFunding, loadBody, userReachedDeferredContent]);

  useEffect(() => {
    if (loadBody) {
      setLoadFirstScreenHydration(true);
    }
  }, [loadBody]);

  if (!loadBody) {
    return <div aria-hidden="true" className={styles.dhTerminalDeferredPlaceholder} />;
  }

  return (
    <Suspense fallback={<div aria-hidden="true" className={styles.dhTerminalDeferredPlaceholder} />}>
      <DeferredTerminalHomeBody
        snapshotBoundary={snapshotBoundary}
        focusPolicyFunding={focusPolicyFunding}
      />
    </Suspense>
  );
}
