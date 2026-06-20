import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useSectorPanelState } from "./useSectorPanelState";

describe("useSectorPanelState", () => {
  it("starts with the default sector controls used by the stock analysis page", () => {
    const { result } = renderHook(() => useSectorPanelState());

    expect(result.current.sectorFilterSectorCode).toBeNull();
    expect(result.current.sectorView).toBe("score");
    expect(result.current.sectorSeriesCollapseKeys).toEqual([]);
    expect(result.current.sectorSeriesWindow).toBe(5);
    expect(result.current.sectorSeriesExpanded).toBe(false);
  });

  it("toggles sector filtering and switches to a newly selected sector", () => {
    const { result } = renderHook(() => useSectorPanelState());

    act(() => {
      result.current.toggleSectorFilter("BK001");
    });
    expect(result.current.sectorFilterSectorCode).toBe("BK001");

    act(() => {
      result.current.toggleSectorFilter("BK001");
    });
    expect(result.current.sectorFilterSectorCode).toBeNull();

    act(() => {
      result.current.toggleSectorFilter("BK002");
    });
    expect(result.current.sectorFilterSectorCode).toBe("BK002");
  });

  it("normalizes sector tab, series collapse, and window change keys", () => {
    const { result } = renderHook(() => useSectorPanelState());

    act(() => {
      result.current.handleSectorViewChange("turnover");
    });
    expect(result.current.sectorView).toBe("turnover");

    act(() => {
      result.current.handleSectorSeriesCollapseChange("sector-rank-series-multi");
    });
    expect(result.current.sectorSeriesCollapseKeys).toEqual(["sector-rank-series-multi"]);
    expect(result.current.sectorSeriesExpanded).toBe(true);

    act(() => {
      result.current.handleSectorSeriesWindowChange("20");
    });
    expect(result.current.sectorSeriesWindow).toBe(20);

    act(() => {
      result.current.handleSectorSeriesCollapseChange([]);
      result.current.handleSectorSeriesWindowChange("5");
    });
    expect(result.current.sectorSeriesCollapseKeys).toEqual([]);
    expect(result.current.sectorSeriesExpanded).toBe(false);
    expect(result.current.sectorSeriesWindow).toBe(5);
  });
});
