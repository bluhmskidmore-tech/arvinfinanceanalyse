import { describe, expect, it } from "vitest";

import { createMockBalanceMovementClient } from "./balanceMovementMockClient";

describe("createMockBalanceMovementClient", () => {
  it("uses the governed J4 structured-finance broker label", async () => {
    const response = await createMockBalanceMovementClient().getBalanceMovementAnalysis({
      reportDate: "2026-06-30",
      currencyBasis: "CNY",
    });
    const currentMonth = response.result.business_trend_months.find(
      (month) => month.report_date === "2026-06-30",
    );
    const j4Row = currentMonth?.rows.find(
      (row) => row.row_key === "asset_zqtz_detail_structured_finance_broker",
    );

    expect(j4Row?.row_label).toBe("结构化融资（券商）");
  });
});
