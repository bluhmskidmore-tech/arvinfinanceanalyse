import { useState } from "react";

import type { SectorSortKey } from "../lib/stockAnalysisChartModel";

export type SectorSortState = {
  key: SectorSortKey;
  order: "ascend" | "descend";
};

export function useSectorSortState() {
  const [sectorSort, setSectorSort] = useState<SectorSortState>({
    key: "rank",
    order: "ascend",
  });

  const toggleSort = (key: SectorSortKey) => {
    setSectorSort((prev) =>
      prev.key === key
        ? { key, order: prev.order === "ascend" ? "descend" : "ascend" }
        : { key, order: "ascend" },
    );
  };

  function renderSortSuffix(key: SectorSortKey) {
    if (sectorSort.key !== key) return "";
    return sectorSort.order === "ascend" ? " ▲" : " ▼";
  }

  return {
    sectorSort,
    toggleSort,
    renderSortSuffix,
  };
}
