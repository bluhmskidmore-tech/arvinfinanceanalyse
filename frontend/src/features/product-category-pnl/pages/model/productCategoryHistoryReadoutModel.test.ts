import { describe, expect, it } from "vitest";
import { buildProductCategoryComparisonReadout } from "./productCategoryHistoryReadoutModel";

describe("product category history readout", () => {
  it("counts a returned missing period as failed while leaving unrequested periods pending", () => {
    const readout = buildProductCategoryComparisonReadout({
      selectedDate: "2026-01-31",
      selectedYearMonth: { year: 2026, month: 1 },
      comparisonSnapshots: [],
      historyPoints: [
        { reportDate: "2025-01-31" },
        { reportDate: "2025-02-28" },
        { reportDate: "2025-03-31" },
        { reportDate: "2025-04-30" },
        { reportDate: "2025-05-31" },
      ],
      historyPayloadByReportDate: new Map([["2025-01-31", {}]]),
      trendHistoryBatches: [["2025-01-31", "2025-02-28"], ["2025-04-30"]],
      trendHistoryQueries: [
        {
          isError: false,
          isFetching: false,
          data: { result: { items: [{ report_date: "2025-02-28", status: "not_found" }] } },
        },
        { isError: false, isFetching: false },
      ],
      interestSpreadHistoryBatches: [["2025-03-31"], ["2025-05-31"]],
      interestSpreadHistoryQueries: [{ isError: false, isFetching: true }],
      baseline: { isError: false, isFetching: false, data: {} },
    });

    expect(readout.loadState).toBe("partial");
    expect(readout.loadLabel).toBe("对比期载入 2/6；载入中 1；失败 1");
    expect(readout.priorPeriodLabel).toBe("2025年全年");
    expect(readout.currentPeriodLabel).toBe("2026年截至1月");
  });

  it("keeps a resolved period loaded when its batch refresh fails", () => {
    const readout = buildProductCategoryComparisonReadout({
      selectedDate: "2026-01-31",
      selectedYearMonth: { year: 2026, month: 1 },
      comparisonSnapshots: [],
      historyPoints: [{ reportDate: "2025-01-31" }],
      historyPayloadByReportDate: new Map([["2025-01-31", {}]]),
      trendHistoryBatches: [["2025-01-31"]],
      trendHistoryQueries: [{ isError: true, isFetching: false }],
      interestSpreadHistoryBatches: [],
      interestSpreadHistoryQueries: [],
      baseline: { isError: false, isFetching: false, data: {} },
    });

    expect(readout.loadState).toBe("complete");
    expect(readout.loadLabel).toBe("对比期载入 2/2");
  });
});
