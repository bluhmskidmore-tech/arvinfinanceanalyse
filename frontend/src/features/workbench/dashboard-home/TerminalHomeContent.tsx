import { lazy, Suspense } from "react";
import { NextUIProvider } from "@nextui-org/react";

import type { DashboardHomeBodyView } from "./dashboardHomeBodyView";
import { DeferredSkeleton } from "./DeferredSkeleton";

type TerminalHomeContentProps = {
  view: DashboardHomeBodyView;
  showFirstScreen?: boolean;
  focusPolicyFunding?: boolean;
  homeAvailabilityKind?: "normal" | "serviceUnavailable";
};

const TerminalHomeWorkGrid = lazy(() =>
  import("./TerminalHomeWorkGrid").then((module) => ({
    default: module.TerminalHomeWorkGrid,
  })),
);

const TerminalHomeDeferredSections = lazy(() =>
  import("./TerminalHomeDeferredSections").then((module) => ({
    default: module.TerminalHomeDeferredSections,
  })),
);

export function TerminalHomeContent({
  view,
  showFirstScreen = true,
  focusPolicyFunding = false,
  homeAvailabilityKind = "normal",
}: TerminalHomeContentProps) {
  void showFirstScreen;

  return (
    <NextUIProvider>
      <Suspense fallback={<DeferredSkeleton variant="work-grid" />}>
        <TerminalHomeDeferredSections
          view={view}
          focusPolicyFunding={focusPolicyFunding}
        />
        <TerminalHomeWorkGrid
          view={view}
          homeAvailabilityKind={homeAvailabilityKind}
        />
      </Suspense>
    </NextUIProvider>
  );
}
