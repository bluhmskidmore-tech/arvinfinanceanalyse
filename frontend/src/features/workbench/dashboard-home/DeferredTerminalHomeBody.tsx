import { useQueryClient } from "@tanstack/react-query";

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
  supplementalState?: HomeSupplementalApiState;
  updatedAt?: string;
};

export function DeferredTerminalHomeBody({
  snapshotBoundary,
  firstScreenView,
  homeAvailability,
  homeAvailabilityKind = "normal",
  snapshotRefreshing = false,
  supplementalState,
  updatedAt,
}: DeferredTerminalHomeBodyProps) {
  const queryClient = useQueryClient();
  const { view } = useDashboardHomeViewModel(snapshotBoundary);

  return (
    <DashboardHomeOptionTwoBody
      view={view}
      firstScreenView={firstScreenView}
      bondNewsActions={{ queryClient }}
      homeAvailability={homeAvailability}
      homeAvailabilityKind={homeAvailabilityKind}
      onRefresh={snapshotBoundary.refreshSnapshot}
      snapshotRefreshing={snapshotRefreshing}
      supplementalStateLabel={supplementalState?.label}
      updatedAt={updatedAt}
    />
  );
}
