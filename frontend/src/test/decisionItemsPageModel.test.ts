import { describe, expect, it } from "vitest";

import type { BalanceAnalysisDecisionItemStatusRow, ResultMeta } from "../api/contracts";
import { buildDecisionItemsPageViewModel } from "../features/decision-items/lib/decisionItemsPageModel";

function makeResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_decision_items_test",
    basis: "analytical",
    result_kind: "balance.decision_items",
    formal_use_allowed: true,
    source_version: "sv_test",
    vendor_version: "vv_test",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-24T09:00:00Z",
    ...overrides,
  };
}

function makeRow(
  overrides: Partial<BalanceAnalysisDecisionItemStatusRow> = {},
): BalanceAnalysisDecisionItemStatusRow {
  return {
    decision_key: "rule_a",
    title: "Alpha",
    action_label: "Review",
    severity: "low",
    reason: "Because",
    source_section: "sec",
    rule_id: "r1",
    rule_version: "1",
    latest_status: {
      decision_key: "rule_a",
      status: "pending",
      updated_at: null,
      updated_by: null,
    },
    ...overrides,
  };
}

describe("buildDecisionItemsPageViewModel", () => {
  it("sorts pending before non-pending, then high severity before lower", () => {
    const vm = buildDecisionItemsPageViewModel({
      payload: {
        report_date: "2026-04-24",
        position_scope: "all",
        currency_basis: "native",
        rows: [
          makeRow({
            decision_key: "k2",
            title: "Later title",
            severity: "high",
            latest_status: {
              decision_key: "k2",
              status: "confirmed",
              updated_at: null,
              updated_by: null,
            },
          }),
          makeRow({
            decision_key: "k1",
            title: "Earlier title",
            severity: "low",
            latest_status: {
              decision_key: "k1",
              status: "pending",
              updated_at: null,
              updated_by: null,
            },
          }),
        ],
      },
      result_meta: makeResultMeta(),
    });
    expect(vm.rows.map((r) => r.decision_key)).toEqual(["k1", "k2"]);
  });

  it("among pending rows, orders high severity before medium before low; tie-breaks title then decision_key", () => {
    const vm = buildDecisionItemsPageViewModel({
      payload: {
        rows: [
          makeRow({ decision_key: "z", title: "B", severity: "low" }),
          makeRow({ decision_key: "a", title: "B", severity: "medium" }),
          makeRow({ decision_key: "m", title: "A", severity: "high" }),
        ],
      },
    });
    expect(vm.rows.map((r) => r.decision_key)).toEqual(["m", "a", "z"]);
  });

  it("aggregates statusCounts and severityCounts", () => {
    const vm = buildDecisionItemsPageViewModel({
      payload: {
        rows: [
          makeRow({ decision_key: "1", severity: "high", latest_status: { decision_key: "1", status: "pending", updated_at: null, updated_by: null } }),
          makeRow({ decision_key: "2", severity: "medium", latest_status: { decision_key: "2", status: "confirmed", updated_at: null, updated_by: null } }),
          makeRow({ decision_key: "3", severity: "low", latest_status: { decision_key: "3", status: "dismissed", updated_at: null, updated_by: null } }),
        ],
      },
    });
    expect(vm.statusCounts).toEqual({ pending: 1, confirmed: 1, dismissed: 1 });
    expect(vm.severityCounts).toEqual({ high: 1, medium: 1, low: 1 });
  });

  it("emits contractWarnings for missing fields and does not throw", () => {
    const broken = {
      ...makeRow(),
      title: "",
      severity: "oops" as BalanceAnalysisDecisionItemStatusRow["severity"],
      latest_status: {
        decision_key: "rule_a",
        status: "maybe" as BalanceAnalysisDecisionItemStatusRow["latest_status"]["status"],
        updated_at: null,
        updated_by: null,
      },
    } as BalanceAnalysisDecisionItemStatusRow;

    expect(() =>
      buildDecisionItemsPageViewModel({
        payload: { rows: [broken] },
      }),
    ).not.toThrow();

    const vm = buildDecisionItemsPageViewModel({
      payload: { rows: [broken] },
    });
    expect(vm.contractWarnings.some((w) => w.includes("title"))).toBe(true);
    expect(vm.contractWarnings.some((w) => w.includes("severity"))).toBe(true);
    expect(vm.contractWarnings.some((w) => w.includes("latest_status.status"))).toBe(true);
  });

  it("empty rows yields empty-state-friendly model", () => {
    const vm = buildDecisionItemsPageViewModel({
      payload: { report_date: "2026-04-24", rows: [] },
    });
    expect(vm.rows).toEqual([]);
    expect(vm.summary).toContain("No decision items");
    expect(vm.statusCounts).toEqual({ pending: 0, confirmed: 0, dismissed: 0 });
    expect(vm.severityCounts).toEqual({ low: 0, medium: 0, high: 0 });
    expect(vm.pendingRows).toEqual([]);
    expect(vm.attentionRows).toEqual([]);
  });

  it("includes result_meta-derived warnings in contractWarnings", () => {
    const vm = buildDecisionItemsPageViewModel({
      payload: { rows: [] },
      result_meta: makeResultMeta({ formal_use_allowed: false, fallback_mode: "latest_snapshot" }),
    });
    expect(vm.contractWarnings.some((w) => w.includes("formal_use_allowed"))).toBe(true);
    expect(vm.contractWarnings.some((w) => w.includes("fallback_mode"))).toBe(true);
  });
});
