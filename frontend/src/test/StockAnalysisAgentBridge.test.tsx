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
    expect(ctx.current_filters.report_date).toBeUndefined();
    expect(ctx.current_filters.sector_filter).toBeNull();
    expect(ctx.current_filters.sector_filter_label).toBeNull();
    expect(ctx.current_filters.sector_view).toBe("pctchange");
    expect(ctx.current_filters.current_view).toBe("decision");
    expect(ctx.selected_rows).toEqual([]);
  });

  it("includes optional fields when present", () => {
    const ctx = buildStockAnalysisAgentPageContext({
      asOfDate: "2026-04-30",
      sectorFilterSectorCode: "801001",
      sectorFilterLabel: "AI",
      sectorView: "score",
      detailSelection: {
        code: "000001.SZ",
        name: "Alpha Co",
        reviewRank: 1,
        sectorCode: "801001",
        sectorName: "AI",
        source: "review_queue",
      },
    });

    expect(ctx.current_filters.as_of_date).toBe("2026-04-30");
    expect(ctx.current_filters.sector_filter).toBe("801001");
    expect(ctx.current_filters.sector_filter_label).toBe("AI");
    expect(ctx.current_filters.current_view).toBe("stock_detail");
    expect(ctx.selected_rows).toEqual([
      {
        stock_code: "000001.SZ",
        stock_name: "Alpha Co",
        review_rank: 1,
        sector_code: "801001",
        sector_name: "AI",
        source: "review_queue",
      },
    ]);
  });

  it("keeps requested date separate from the resolved data date", () => {
    const ctx = buildStockAnalysisAgentPageContext({
      asOfDate: "2026-04-29",
      requestedAsOfDate: "2026-05-08",
      sectorFilterSectorCode: null,
      sectorView: "score",
      detailSelection: null,
    });

    expect(ctx.current_filters.as_of_date).toBe("2026-04-29");
    expect(ctx.current_filters.requested_as_of_date).toBe("2026-05-08");
  });

  it("mirrors the resolved data date into report_date so the backend date resolver honors it", () => {
    // 后端 _requested_report_date 只识别 report_date/date 键（读 page_context.current_filters）；
    // 只写 as_of_date 会被静默忽略，页面日期不生效。
    const ctx = buildStockAnalysisAgentPageContext({
      asOfDate: "2026-04-30",
      sectorFilterSectorCode: null,
      sectorView: "score",
      detailSelection: null,
    });

    expect(ctx.current_filters.report_date).toBe("2026-04-30");
    expect(ctx.current_filters.as_of_date).toBe("2026-04-30");
  });

  it("does not emit report_date when no data date is resolved", () => {
    const ctx = buildStockAnalysisAgentPageContext({
      asOfDate: null,
      requestedAsOfDate: "2026-05-08",
      sectorFilterSectorCode: null,
      sectorView: "score",
      detailSelection: null,
    });

    expect(ctx.current_filters.report_date).toBeUndefined();
  });

  it("does not promote a requested date into as_of_date when no data date is resolved", () => {
    const ctx = buildStockAnalysisAgentPageContext({
      asOfDate: null,
      requestedAsOfDate: "2026-05-08",
      sectorFilterSectorCode: null,
      sectorView: "score",
      detailSelection: null,
    });

    expect(ctx.current_filters.as_of_date).toBeUndefined();
    expect(ctx.current_filters.requested_as_of_date).toBe("2026-05-08");
    expect(ctx.current_filters.requested_as_of_date).not.toBe(ctx.current_filters.as_of_date);
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

  it("preserves multi-strategy detail ranks for agent review", () => {
    const ctx = buildStockAnalysisAgentPageContext({
      asOfDate: "2026-04-30",
      sectorFilterSectorCode: null,
      sectorView: "score",
      detailSelection: {
        code: "000003.SZ",
        name: "Gamma Co",
        sectorName: "Robotics",
        source: "consensus",
        livermoreRank: 2,
        meanReversionRank: 5,
        factorScreenRank: null,
      },
    });

    expect(ctx.selected_rows).toEqual([
      {
        stock_code: "000003.SZ",
        stock_name: "Gamma Co",
        sector_name: "Robotics",
        source: "consensus",
        livermore_rank: 2,
        mean_reversion_rank: 5,
      },
    ]);
  });

  it("marks filtered review queue context without a selected stock", () => {
    const ctx = buildStockAnalysisAgentPageContext({
      asOfDate: "2026-04-30",
      sectorFilterSectorCode: "801002",
      sectorFilterLabel: "新能源车",
      sectorView: "turnover",
      detailSelection: null,
    });

    expect(ctx.current_filters.sector_filter).toBe("801002");
    expect(ctx.current_filters.sector_filter_label).toBe("新能源车");
    expect(ctx.current_filters.current_view).toBe("review_queue_filtered");
    expect(ctx.selected_rows).toEqual([]);
  });
});
