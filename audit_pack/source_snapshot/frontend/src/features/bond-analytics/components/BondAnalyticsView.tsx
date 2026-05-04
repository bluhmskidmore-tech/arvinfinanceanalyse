import { Suspense, lazy } from "react";

const BondAnalyticsViewContent = lazy(() => import("./BondAnalyticsViewContent"));

export function BondAnalyticsView() {
  return (
    <Suspense
      fallback={null}
    >
      <BondAnalyticsViewContent />
    </Suspense>
  );
}

export default BondAnalyticsView;
