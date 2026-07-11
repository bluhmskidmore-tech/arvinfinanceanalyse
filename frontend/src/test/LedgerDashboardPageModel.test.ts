import { describe, expect, it } from "vitest";

import {
  buildLedgerKpiCards,
  formatLedgerYiAmount,
  formatLedgerYuanAmount,
  ledgerImportPresentation,
  ledgerImportStatusIsTerminal,
  ledgerDataState,
} from "../features/ledger-dashboard/pages/ledgerDashboardPageModel";

describe("ledgerDashboardPageModel", () => {
  it("keeps dashboard KPI values as source-blocked native-amount aggregates", () => {
    expect(formatLedgerYiAmount(3289.07)).toBe("3289.07 原币合计/1亿");
    expect(formatLedgerYiAmount(null)).toBe("--");

    const cards = buildLedgerKpiCards({
      as_of_date: "2026-03-17",
      asset_face_amount: 3289.07,
      liability_face_amount: 1231.77,
      net_face_exposure: 2057.31,
      alert_count: 0,
    });

    expect(cards.map((item) => item.value)).toEqual([
      "3289.07 原币合计/1亿",
      "1231.77 原币合计/1亿",
      "2057.31 原币合计/1亿",
      "--",
    ]);
    expect(cards.at(-1)?.detail).toContain("未接入");
    expect(cards.at(-1)?.detail).toContain("不能解释为 0 条预警");
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
});
