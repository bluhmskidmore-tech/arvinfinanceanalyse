import { Suspense, lazy } from "react";

import { WorkbenchRouteFallback } from "../../../router/WorkbenchRouteFallback";

const CrossAssetDriversPage = lazy(() => import("./CrossAssetDriversPage"));

function CrossAssetRouteLoadingBoundary() {
  return (
    <div data-testid="cross-asset-route-loading">
      <WorkbenchRouteFallback />
    </div>
  );
}

export default function CrossAssetPage() {
  return (
    <Suspense fallback={<CrossAssetRouteLoadingBoundary />}>
      <CrossAssetDriversPage />
    </Suspense>
  );
}
