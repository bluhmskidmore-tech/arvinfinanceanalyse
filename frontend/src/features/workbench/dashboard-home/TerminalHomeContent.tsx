import { lazy, Suspense } from "react";
import { NextUIProvider } from "@nextui-org/react";

import type { DashboardHomeBodyView } from "./dashboardHomeBodyView";
import { ResearchCalendarSection } from "./sections/ResearchCalendarSection";
import styles from "./dashboardHome.module.css";

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
      <ResearchCalendarSection
        macroBriefing={view.macroBriefing}
        focusPolicyFunding={focusPolicyFunding}
      />

      <Suspense fallback={<div aria-hidden="true" className={styles.dhTerminalDeferredPlaceholder} />}>
        <TerminalHomeWorkGrid
          view={view}
          homeAvailabilityKind={homeAvailabilityKind}
        />
      </Suspense>

      <Suspense fallback={<div aria-hidden="true" className={styles.dhTerminalDeferredPlaceholder} />}>
        <TerminalHomeDeferredSections view={view} />
      </Suspense>
    </NextUIProvider>
  );
}
