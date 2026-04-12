import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccountingClassAuditView } from "../features/bond-analytics/components/AccountingClassAuditView";

function createResultMeta(overrides: Record<string, unknown> = {}) {
  return {
    trace_id: "tr_demo",
    basis: "formal",
    result_kind: "bond_analytics.accounting_class_audit",
    formal_use_allowed: true,
    source_version: "sv_demo",
    vendor_version: "vv_demo",
    rule_version: "rv_demo",
    cache_version: "cv_demo",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

function createAccountingAuditResult(overrides: Record<string, unknown> = {}) {
  return {
    report_date: "2026-03-31",
    total_positions: 100,
    total_market_value: "10000000000",
    distinct_asset_classes: 5,
    divergent_asset_classes: 1,
    divergent_position_count: 3,
    divergent_market_value: "300000000",
    map_unclassified_asset_classes: 0,
    map_unclassified_position_count: 0,
    map_unclassified_market_value: "0",
    rows: [
      {
        asset_class: "政金债",
        position_count: 10,
        market_value: "2000000000",
        market_value_weight: "0.2",
        infer_accounting_class: "FVOCI",
        map_accounting_class: "FVTPL",
        infer_rule_id: "r1",
        infer_match: null,
        map_rule_id: "r2",
        map_match: null,
        is_divergent: true,
        is_map_unclassified: false,
      },
    ],
    warnings: [],
    computed_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

describe("AccountingClassAuditView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads accounting class audit with KPI cards, explanatory text, and audit table", async () => {
    let resolvePayload!: (v: { result_meta: ReturnType<typeof createResultMeta>; result: ReturnType<typeof createAccountingAuditResult> }) => void;
    const payloadPromise = new Promise<{
      result_meta: ReturnType<typeof createResultMeta>;
      result: ReturnType<typeof createAccountingAuditResult>;
    }>((resolve) => {
      resolvePayload = resolve;
    });

    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => payloadPromise,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountingClassAuditView reportDate="2026-03-31" />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByText("资产类别数（去重）")).not.toBeInTheDocument();

    resolvePayload({
      result_meta: createResultMeta(),
      result: createAccountingAuditResult(),
    });

    expect(await screen.findByText("资产类别数（去重）")).toBeInTheDocument();
    expect(screen.getByText("分歧分类")).toBeInTheDocument();
    expect(screen.getByText("映射为其他（other）")).toBeInTheDocument();
    expect(screen.getByText("覆盖市值")).toBeInTheDocument();

    expect(screen.getByText(/本审计对比两条会计分类路径/)).toBeInTheDocument();
    expect(screen.getByText(/infer_accounting_class/)).toBeInTheDocument();
    expect(screen.getByText(/map_accounting_class/)).toBeInTheDocument();

    expect(screen.getByText("审计明细")).toBeInTheDocument();
    expect(screen.getByText("政金债")).toBeInTheDocument();
  });

  it("renders warning alert when warnings exist", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          result_meta: createResultMeta(),
          result: createAccountingAuditResult({
            warnings: ["示例：映射规则版本待对齐"],
            rows: [],
          }),
        }),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountingClassAuditView reportDate="2026-03-31" />);

    expect(await screen.findByText("提示")).toBeInTheDocument();
    expect(screen.getByText("示例：映射规则版本待对齐")).toBeInTheDocument();
  });
});
