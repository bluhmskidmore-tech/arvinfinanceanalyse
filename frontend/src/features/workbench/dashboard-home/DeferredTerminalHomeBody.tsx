import { TerminalHomeContent } from "./TerminalHomeContent";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";
import { useDashboardHomeViewModel } from "./useDashboardHomeViewModel";

type DeferredTerminalHomeBodyProps = {
  snapshotBoundary: DashboardHomeSnapshotBoundary;
};

export function DeferredTerminalHomeBody({ snapshotBoundary }: DeferredTerminalHomeBodyProps) {
  const { view } = useDashboardHomeViewModel(snapshotBoundary);

  return <TerminalHomeContent view={view} showFirstScreen={false} />;
}
