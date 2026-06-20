import { useState } from "react";

import type { StockSectorViewKind } from "../lib/stockAnalysisPageModel";

export type SectorSeriesWindow = 5 | 20;

export function useSectorPanelState() {
  const [sectorFilterSectorCode, setSectorFilterSectorCode] = useState<string | null>(null);
  const [sectorView, setSectorView] = useState<StockSectorViewKind>("score");
  const [sectorSeriesCollapseKeys, setSectorSeriesCollapseKeys] = useState<string[]>([]);
  const [sectorSeriesWindow, setSectorSeriesWindow] = useState<SectorSeriesWindow>(5);

  const toggleSectorFilter = (code: string | null) => {
    setSectorFilterSectorCode((prev) => (prev === code ? null : code));
  };

  const handleSectorViewChange = (key: string) => {
    setSectorView(key as StockSectorViewKind);
  };

  const handleSectorSeriesCollapseChange = (keys: string | string[]) => {
    setSectorSeriesCollapseKeys(Array.isArray(keys) ? keys : [keys]);
  };

  const handleSectorSeriesWindowChange = (key: string) => {
    setSectorSeriesWindow(key === "20" ? 20 : 5);
  };

  return {
    sectorFilterSectorCode,
    sectorView,
    sectorSeriesCollapseKeys,
    sectorSeriesWindow,
    sectorSeriesExpanded: sectorSeriesCollapseKeys.includes("sector-rank-series-multi"),
    toggleSectorFilter,
    handleSectorViewChange,
    handleSectorSeriesCollapseChange,
    handleSectorSeriesWindowChange,
  };
}
