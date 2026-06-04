import { useEffect } from "react";

import { TerminalHomeContent } from "./TerminalHomeContent";
import { useDashboardHomeViewModel } from "./useDashboardHomeViewModel";
import type { DashboardHomeFirstScreenHydration } from "./dashboardHomeFirstScreenTypes";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";

type DeferredTerminalHomeContentProps = {
  snapshotBoundary: DashboardHomeSnapshotBoundary;
  onFirstScreenHydrated?: (hydration: DashboardHomeFirstScreenHydration) => void;
};

export function DeferredTerminalHomeContent({
  snapshotBoundary,
  onFirstScreenHydrated,
}: DeferredTerminalHomeContentProps) {
  const { view } = useDashboardHomeViewModel(snapshotBoundary);

  useEffect(() => {
    onFirstScreenHydrated?.({
      reportDate: view.reportDate,
      headerStatus: view.headerStatus,
      decisionRail: view.decisionRail,
      terminalKpis: view.terminalKpis,
      keyRiskStrip: view.keyRiskStrip,
    });
  }, [
    onFirstScreenHydrated,
    view.decisionRail,
    view.headerStatus,
    view.keyRiskStrip,
    view.reportDate,
    view.terminalKpis,
  ]);

  return <TerminalHomeContent view={view} showFirstScreen={false} />;
}
