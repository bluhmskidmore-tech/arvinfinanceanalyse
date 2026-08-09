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
  focusPolicyFunding?: boolean;
  homeAvailability?: DashboardHomeAvailability;
  homeAvailabilityKind?: "normal" | "serviceUnavailable";
  snapshotRefreshing?: boolean;
  supplementalState?: HomeSupplementalApiState;
  updatedAt?: string;
};

export function DeferredTerminalHomeBody({
  snapshotBoundary,
  firstScreenView,
  focusPolicyFunding = false,
  homeAvailability,
  homeAvailabilityKind = "normal",
  snapshotRefreshing = false,
  supplementalState,
  updatedAt,
}: DeferredTerminalHomeBodyProps) {
  const queryClient = useQueryClient();
  const { view } = useDashboardHomeViewModel(snapshotBoundary, {
    eagerEventFeeds: focusPolicyFunding,
  });

  return (
    <DashboardHomeOptionTwoBody
      view={view}
      firstScreenView={firstScreenView}
      bondNewsActions={{ queryClient }}
      focusPolicyFunding={focusPolicyFunding}
      homeAvailability={homeAvailability}
      homeAvailabilityKind={homeAvailabilityKind}
      onRefresh={snapshotBoundary.refreshSnapshot}
      snapshotRefreshing={snapshotRefreshing}
      supplementalStateLabel={supplementalState?.label}
      updatedAt={updatedAt}
    />
  );
}
