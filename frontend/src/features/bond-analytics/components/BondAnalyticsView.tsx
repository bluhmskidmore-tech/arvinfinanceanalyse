import { Suspense, lazy } from "react";

import styles from "./BondAnalyticsViewContent.module.css";

const BondAnalyticsViewContent = lazy(() => import("./BondAnalyticsViewContent"));

export function BondAnalyticsView() {
  return (
    <Suspense
      fallback={
        <div
          className={`${styles.bondWorkbenchPage} ${styles.pageSkeleton}`}
          data-testid="bond-analysis-page-skeleton"
          data-moss-theme-scope="bond-analysis"
          aria-hidden="true"
        />
      }
    >
      <BondAnalyticsViewContent />
    </Suspense>
  );
}

export default BondAnalyticsView;
