import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";

import type {
  DashboardHomeFirstScreenHydration,
  DashboardHomeFirstScreenView,
} from "./dashboardHomeFirstScreenTypes";
import { DeferredEvidenceIndexPreview } from "./DeferredEvidenceIndexPreview";
import type { DashboardHomeAvailability } from "./dashboardHomeAvailability";
import styles from "./dashboardHomeShell.module.css";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";
import { useDashboardHomeSupplementalHydration } from "./useDashboardHomeSupplementalHydration";

const DeferredTerminalHomeBody = lazy(() =>
  import("./DeferredTerminalHomeBody").then((module) => ({
    default: module.DeferredTerminalHomeBody,
  })),
);

type DeferredTerminalHomeContentProps = {
  snapshotBoundary: DashboardHomeSnapshotBoundary;
  firstScreenView: DashboardHomeFirstScreenView;
  userReachedDeferredContent: boolean;
  homeAvailability?: DashboardHomeAvailability;
  homeAvailabilityKind?: "normal" | "serviceUnavailable";
  snapshotRefreshing?: boolean;
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
    supplementalState: hydration.supplementalState,
  });
}

export function DeferredTerminalHomeContent({
  snapshotBoundary,
  firstScreenView,
  userReachedDeferredContent,
  homeAvailability,
  homeAvailabilityKind = "normal",
  snapshotRefreshing = false,
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
    if (userReachedDeferredContent) {
      setLoadBody(true);
    }
  }, [userReachedDeferredContent]);

  useEffect(() => {
    if (loadBody) {
      setLoadFirstScreenHydration(true);
    }
  }, [loadBody]);

  if (!loadBody) {
    return <DeferredEvidenceIndexPreview />;
  }

  return (
    <Suspense fallback={<div aria-hidden="true" className={styles.dhTerminalDeferredPlaceholder} />}>
      <DeferredTerminalHomeBody
        snapshotBoundary={snapshotBoundary}
        firstScreenView={firstScreenView}
        homeAvailability={homeAvailability}
        homeAvailabilityKind={homeAvailabilityKind}
        snapshotRefreshing={snapshotRefreshing}
        supplementalState={firstScreenHydration.supplementalState}
        updatedAt={firstScreenHydration.headerStatus.dataUpdatedAt}
      />
    </Suspense>
  );
}
