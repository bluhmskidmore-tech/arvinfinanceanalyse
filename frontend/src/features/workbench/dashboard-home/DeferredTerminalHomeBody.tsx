import { useQueryClient } from "@tanstack/react-query";

import { useDeferredSectionSeen } from "../../../hooks/useDeferredSectionSeen";

import { DashboardHomeOptionTwoBody } from "./DashboardHomeOptionTwoLayout";
import type { DashboardHomeAvailability } from "./dashboardHomeAvailability";
import type {
  DashboardHomeFirstScreenView,
  HomeSupplementalApiState,
} from "./dashboardHomeFirstScreenTypes";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";
import { useDashboardHomeViewModel } from "./useDashboardHomeViewModel";

type DeferredTerminalHomeBodyProps = {
  snapshotBoundary: DashboardHomeSnapshotBoundary;
  firstScreenView: DashboardHomeFirstScreenView;
  homeAvailability?: DashboardHomeAvailability;
  homeAvailabilityKind?: "normal" | "serviceUnavailable";
  snapshotRefreshing?: boolean;
  onViewLatestReport?: () => void;
  supplementalState?: HomeSupplementalApiState;
  updatedAt?: string;
};

export function DeferredTerminalHomeBody({
  snapshotBoundary,
  firstScreenView,
  homeAvailability,
  homeAvailabilityKind = "normal",
  snapshotRefreshing = false,
  onViewLatestReport,
  supplementalState,
  updatedAt,
}: DeferredTerminalHomeBodyProps) {
  const queryClient = useQueryClient();
  const canLoad = Boolean(snapshotBoundary.supplementalReportDate);
  const holdings = useDeferredSectionSeen<HTMLElement>(canLoad);
  const risk = useDeferredSectionSeen<HTMLElement>(canLoad);
  const market = useDeferredSectionSeen<HTMLElement>(canLoad);
  const support = useDeferredSectionSeen<HTMLElement>(canLoad);
  const evidence = useDeferredSectionSeen<HTMLElement>(canLoad);
  const { view, newsLoading } = useDashboardHomeViewModel(snapshotBoundary, {
    sections: {
      holdings: holdings.seen,
      risk: risk.seen,
      market: market.seen,
      support: support.seen,
      evidence: evidence.seen,
    },
  });

  return (
    <DashboardHomeOptionTwoBody
      view={view}
      newsLoading={newsLoading}
      sectionRefs={{
        holdings: holdings.ref,
        risk: risk.ref,
        market: market.ref,
        support: support.ref,
        evidence: evidence.ref,
      }}
      firstScreenView={firstScreenView}
      bondNewsActions={{ queryClient }}
      homeAvailability={homeAvailability}
      homeAvailabilityKind={homeAvailabilityKind}
      onRefresh={snapshotBoundary.refreshSnapshot}
      onViewLatestReport={onViewLatestReport}
      snapshotRefreshing={snapshotRefreshing}
      supplementalStateLabel={supplementalState?.label}
      supplementalStateKind={supplementalState?.kind}
      updatedAt={updatedAt}
    />
  );
}
