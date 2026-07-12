import { describe, expect, it } from "vitest";

import {
  buildLedgerKpiCards,
  selectLedgerCurrency,
  formatLedgerYiAmount,
  formatLedgerYuanAmount,
  ledgerImportPresentation,
  ledgerImportStatusIsTerminal,
  ledgerDataState,
} from "../features/ledger-dashboard/pages/ledgerDashboardPageModel";

describe("ledgerDashboardPageModel", () => {
  it("keeps dashboard KPI values inside one currency bucket", () => {
    expect(formatLedgerYiAmount(3289.07, "CNY")).toBe("3289.07 CNY/1亿");
    expect(formatLedgerYiAmount(null, "CNY")).toBe("--");
    const cards = buildLedgerKpiCards({
      as_of_date: "2026-03-17",
      currency_breakdown: [
        { currency: "CNY", asset_face_amount: 3289.07, liability_face_amount: 1231.77, net_face_exposure: 2057.31 },
      ],
    }, "CNY");
    expect(cards.map((item) => item.value)).toEqual([
      "3289.07 CNY/1亿", "1231.77 CNY/1亿", "2057.31 CNY/1亿",
    ]);
    expect(cards).toHaveLength(3);
  });
  it("keeps position amounts as native-currency values for detail rows", () => {
    expect(formatLedgerYuanAmount(100000000)).toBe("100,000,000.00");
    expect(formatLedgerYuanAmount(null)).toBe("--");
  });

  it("prioritizes explicit loading, no-data, and fallback states", () => {
    expect(ledgerDataState(undefined, new Error("boom"))).toBe("loading_failure");
    expect(
      ledgerDataState(
        {
          source_version: null,
          rule_version: null,
          batch_id: null,
          stale: false,
          fallback: false,
          no_data: true,
        },
        null,
      ),
    ).toBe("no_data");
    expect(
      ledgerDataState(
        {
          source_version: "sv",
          rule_version: "rv",
          batch_id: 1,
          stale: true,
          fallback: true,
          no_data: false,
        },
        null,
      ),
    ).toBe("fallback");
  });

  it.each([
    ["queued", "已进入导入队列", "pending", false],
    ["running", "正在校验并导入", "pending", false],
    ["succeeded", "导入完成", "success", true],
    ["duplicate", "文件内容已存在，未新增批次", "duplicate", true],
    ["failed", "导入失败", "failure", true],
  ] as const)("maps %s without collapsing duplicate into failure", (status, label, tone, terminal) => {
    expect(ledgerImportPresentation(status)).toEqual({ label, tone });
    expect(ledgerImportStatusIsTerminal(status)).toBe(terminal);
  });
  it("selects CNY by default and builds only the selected currency cards", () => {
    const data = {
      as_of_date: "2026-03-17",
      currency_breakdown: [
        { currency: "USD", asset_face_amount: 2, liability_face_amount: null, net_face_exposure: 2 },
        { currency: "CNY", asset_face_amount: 1, liability_face_amount: 0.5, net_face_exposure: 0.5 },
      ],
    };
    expect(selectLedgerCurrency(data.currency_breakdown, null)).toBe("CNY");
    expect(buildLedgerKpiCards(data, "USD").map((card) => [card.key, card.value])).toEqual([
      ["asset", "2.00 USD/1亿"],
      ["liability", "--"],
      ["net", "2.00 USD/1亿"],
    ]);
  });
});
