import { TerminalHomeContent } from "./TerminalHomeContent";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";
import { useDashboardHomeViewModel } from "./useDashboardHomeViewModel";

type DeferredTerminalHomeBodyProps = {
  snapshotBoundary: DashboardHomeSnapshotBoundary;
  focusPolicyFunding?: boolean;
};

export function DeferredTerminalHomeBody({
  snapshotBoundary,
  focusPolicyFunding = false,
}: DeferredTerminalHomeBodyProps) {
  const { view } = useDashboardHomeViewModel(snapshotBoundary, {
    eagerEventFeeds: focusPolicyFunding,
  });

  return (
    <TerminalHomeContent
      view={view}
      showFirstScreen={false}
      focusPolicyFunding={focusPolicyFunding}
    />
  );
}
