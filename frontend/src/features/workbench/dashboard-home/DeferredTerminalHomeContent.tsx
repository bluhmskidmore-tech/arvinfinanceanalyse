import { lazy, Suspense, useEffect, useMemo, useRef } from "react";

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
  onViewLatestReport?: () => void;
  onFirstScreenHydrated?: (hydration: DashboardHomeFirstScreenHydration) => void;
};

function firstScreenHydrationSignature(hydration: DashboardHomeFirstScreenHydration): string {
  return JSON.stringify({
    reportDate: hydration.reportDate,
    keyRiskStrip: hydration.keyRiskStrip,
  });
}

export function DeferredTerminalHomeContent({
  snapshotBoundary,
  firstScreenView,
  userReachedDeferredContent,
  homeAvailability,
  homeAvailabilityKind = "normal",
  snapshotRefreshing = false,
  onViewLatestReport,
  onFirstScreenHydrated,
}: DeferredTerminalHomeContentProps) {
  const { firstScreenHydration, supplementalState, updatedAt } =
    useDashboardHomeSupplementalHydration(snapshotBoundary, {
      enabled: userReachedDeferredContent,
    });
  const hydrationSignature = useMemo(
    () => firstScreenHydrationSignature(firstScreenHydration),
    [firstScreenHydration],
  );
  const emittedHydrationSignatureRef = useRef<string | null>(null);

  useEffect(() => {
    if (emittedHydrationSignatureRef.current === hydrationSignature) {
      return;
    }
    emittedHydrationSignatureRef.current = hydrationSignature;
    onFirstScreenHydrated?.(firstScreenHydration);
  }, [firstScreenHydration, hydrationSignature, onFirstScreenHydrated]);

  if (!userReachedDeferredContent) {
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
        onViewLatestReport={onViewLatestReport}
        supplementalState={supplementalState}
        updatedAt={updatedAt}
      />
    </Suspense>
  );
}
