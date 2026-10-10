import { lazy } from "react";

function loadCrossAssetECharts() {
  return import("../../../lib/echarts");
}

export const LazyCrossAssetECharts = lazy(loadCrossAssetECharts);

export function preloadCrossAssetECharts() {
  void loadCrossAssetECharts().catch(() => undefined);
}
