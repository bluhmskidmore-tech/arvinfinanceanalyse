import { describe, expect, it } from "vitest";

import type { BalanceMovementRow } from "../../../api/contracts";

import {
  chainStatusLabel,
  counterpartyAmountText,
  reconciliationConcernLabel,
  reconciliationStatusLabels,
  reconciliationStatusTones,
  reconciliationTieoutSummary,
  countReconciliationStatuses,
} from "./balanceMovementReconciliationModel";

function row(overrides: Partial<BalanceMovementRow>): BalanceMovementRow {
  return {
    report_date: "2026-02-28",
    report_month: "2026-02",
    currency_basis: "CNX",
    sort_order: 1,
    basis_bucket: "AC",
    previous_balance: "100",
    current_balance: "110",
    previous_balance_pct: null,
    current_balance_pct: null,
    balance_change: "10",
    change_pct: null,
    contribution_pct: null,
    zqtz_amount: "110",
    gl_amount: "110",
    reconciliation_diff: "0",
    reconciliation_status: "matched",
    source_version: "sv",
    rule_version: "rv",
    chain_status: "continuous",
    position_source_basis: "CNY",
    ...overrides,
  };
}

const mismatchRow = row({
  basis_bucket: "AC",
  reconciliation_status: "mismatch",
  reconciliation_diff: "-500000000",
});
const glOnlyRow = row({
  basis_bucket: "OCI",
  sort_order: 2,
  reconciliation_status: "gl_only",
  zqtz_amount: "0",
  reconciliation_diff: "-200000000",
  position_source_basis: "unavailable",
});
const chainBrokenRow = row({
  basis_bucket: "TPL",
  sort_order: 3,
  reconciliation_status: "chain_broken",
  chain_status: "broken",
});

const signedYi = (value: number) => `${value > 0 ? "+" : ""}${value.toFixed(2)}`;

describe("balanceMovementReconciliationModel", () => {
  it("gives gl_only, mismatch and chain_broken distinct labels and tones", () => {
    expect(reconciliationStatusLabels.gl_only).not.toBe(reconciliationStatusLabels.mismatch);
    expect(reconciliationStatusLabels.chain_broken).not.toBe(reconciliationStatusLabels.mismatch);
    expect(
      new Set([
        reconciliationStatusTones.gl_only,
        reconciliationStatusTones.mismatch,
        reconciliationStatusTones.chain_broken,
      ]).size,
    ).toBe(3);
    // 每个取值都必须有中文标签，英文码不得泄漏到页面。
    for (const label of Object.values(reconciliationStatusLabels)) {
      expect(label).not.toMatch(/^[a-z_]+$/);
    }
  });

  it("names the specific failure instead of a generic 需关注", () => {
    const counts = countReconciliationStatuses([mismatchRow, glOnlyRow, chainBrokenRow]);
    expect(reconciliationConcernLabel(counts)).toBe("分桶对不平");
    expect(
      reconciliationConcernLabel(countReconciliationStatuses([glOnlyRow, chainBrokenRow])),
    ).toBe("跨月勾稽断裂");
    expect(reconciliationConcernLabel(countReconciliationStatuses([glOnlyRow]))).toBe(
      "缺对账对手方",
    );
  });

  it("prints 不适用 rather than a fabricated amount when there is no counterparty", () => {
    expect(counterpartyAmountText(mismatchRow, "-5.00")).toBe("-5.00");
    // 印 0 会被读成"辅助账为零"，印 -2.00 会被读成真实缺口。
    expect(counterpartyAmountText(glOnlyRow, "0.00")).toBe("不适用");
    expect(counterpartyAmountText(glOnlyRow, "-2.00")).toBe("不适用");
  });

  it("keeps an unrecorded chain status distinct from a judged one", () => {
    expect(chainStatusLabel(null)).toBe("未记录");
    expect(chainStatusLabel("no_prior_month")).toBe("无上月基准");
    expect(chainStatusLabel(null)).not.toBe(chainStatusLabel("no_prior_month"));
    // 真实链路可能整体省略该字段：undefined 同样按未记录处理，
    // 不得把字面量 "undefined" 透出到勾稽汇总。
    expect(chainStatusLabel(undefined)).toBe("未记录");
    const summary = reconciliationTieoutSummary(
      [row({ chain_status: undefined as unknown as BalanceMovementRow["chain_status"] })],
      signedYi,
    );
    expect(summary).toContain("跨月勾稽 未记录 1");
    expect(summary).not.toContain("undefined");
  });

  it("excludes rows without a counterparty from the comparable difference total", () => {
    const summary = reconciliationTieoutSummary(
      [mismatchRow, glOnlyRow, chainBrokenRow],
      signedYi,
    );

    expect(summary).toContain("0 / 3 一致");
    expect(summary).toContain("对不平 1 · 无头寸对手方 1 · 跨月断裂 1");
    // -5 亿（mismatch）+ 0（chain_broken），gl_only 的 -2 亿不参与合计。
    expect(summary).toContain("可比差异 -5.00 亿");
    expect(summary).toContain("跨月勾稽 衔接 2 · 断裂 1");
  });

  it("marks the comparable difference as 不适用 when no row has a counterparty", () => {
    const summary = reconciliationTieoutSummary([glOnlyRow], signedYi);

    expect(summary).toContain("可比差异 不适用");
    expect(summary).not.toContain("0.00 亿");
  });
});
