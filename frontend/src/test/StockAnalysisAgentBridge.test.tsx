import { describe, expect, it } from "vitest";

import {
  buildStockAnalysisAgentPageContext,
  STOCK_ANALYSIS_AGENT_CONTEXT_NOTE,
} from "../features/stock-analysis/lib/buildStockAnalysisAgentPageContext";

describe("buildStockAnalysisAgentPageContext", () => {
  it("builds page_context with defaults and strips empty as_of_date", () => {
    const ctx = buildStockAnalysisAgentPageContext({
      asOfDate: null,
      sectorFilterSectorCode: null,
      sectorView: "pctchange",
      detailSelection: null,
    });

    expect(ctx.page_id).toBe("stock-analysis");
    expect(ctx.context_note).toBe(STOCK_ANALYSIS_AGENT_CONTEXT_NOTE);
    expect(ctx.current_filters.as_of_date).toBeUndefined();
    expect(ctx.current_filters.sector_filter).toBeNull();
    expect(ctx.current_filters.sector_view).toBe("pctchange");
    expect(ctx.selected_rows).toEqual([]);
  });

  it("includes optional fields when present", () => {
    const ctx = buildStockAnalysisAgentPageContext({
      asOfDate: "2026-04-30",
      sectorFilterSectorCode: "801001",
      sectorView: "score",
      detailSelection: { code: "000001.SZ", name: "Alpha Co" },
    });

    expect(ctx.current_filters.as_of_date).toBe("2026-04-30");
    expect(ctx.current_filters.sector_filter).toBe("801001");
    expect(ctx.selected_rows).toEqual([{ stock_code: "000001.SZ", stock_name: "Alpha Co" }]);
  });

  it("omits stock_name when absent", () => {
    const ctx = buildStockAnalysisAgentPageContext({
      asOfDate: "2026-04-30",
      sectorFilterSectorCode: null,
      sectorView: "amplitude",
      detailSelection: { code: "000002.SZ" },
    });

    expect(ctx.selected_rows).toEqual([{ stock_code: "000002.SZ" }]);
  });
});
