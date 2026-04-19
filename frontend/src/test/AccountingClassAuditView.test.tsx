import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { Numeric, ResultMeta } from "../api/contracts";
import { AccountingClassAuditView } from "../features/bond-analytics/components/AccountingClassAuditView";
import type { AccountingClassAuditResponse } from "../features/bond-analytics/types";
import { formatRawAsNumeric } from "../utils/format";

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
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

function governed(raw: number | null, unit: Numeric["unit"], signAware = false): Numeric {
  return formatRawAsNumeric({ raw, unit, sign_aware: signAware });
}

function createAccountingAuditResult(
  overrides: Partial<AccountingClassAuditResponse> = {},
): AccountingClassAuditResponse {
  return {
    report_date: "2026-03-31",
    total_positions: 100,
    total_market_value: governed(10_000_000_000, "yuan"),
    distinct_asset_classes: 5,
    divergent_asset_classes: 1,
    divergent_position_count: 3,
    divergent_market_value: governed(300_000_000, "yuan"),
    map_unclassified_asset_classes: 0,
    map_unclassified_position_count: 0,
    map_unclassified_market_value: governed(0, "yuan"),
    rows: [
      {
        asset_class: "政策金债",
        position_count: 10,
        market_value: governed(2_000_000_000, "yuan"),
        market_value_weight: governed(0.2, "ratio"),
        infer_accounting_class: "FVOCI",
        map_accounting_class: "FVTPL",
        infer_rule_id: "r1",
        infer_match: "exact",
        map_rule_id: "r2",
        map_match: "fuzzy",
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
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsAccountingClassAudit: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createAccountingAuditResult(),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <AccountingClassAuditView reportDate="2026-03-31" />
      </ApiClientProvider>,
    );

    await waitFor(() =>
      expect(client.getBondAnalyticsAccountingClassAudit).toHaveBeenCalledWith("2026-03-31"),
    );

    expect(await screen.findByTestId("accounting-class-audit-computed-at")).toHaveTextContent(
      "2026-04-10T00:00:00Z",
    );
    expect(screen.getByTestId("accounting-class-audit-shell-lead")).toBeInTheDocument();
    expect(screen.getByTestId("accounting-class-audit-rules-lead")).toBeInTheDocument();
    expect(screen.getByTestId("accounting-class-audit-detail-lead")).toBeInTheDocument();
    expect(screen.getByText("资产类别数（去重）")).toBeInTheDocument();
    expect(screen.getByText("分歧分类")).toBeInTheDocument();
    expect(screen.getByText("映射为其他（other）")).toBeInTheDocument();
    expect(screen.getByText("覆盖市值")).toBeInTheDocument();
    expect(screen.getByTestId("accounting-audit-total-positions")).toHaveTextContent("100");
    expect(screen.getByText("分歧持仓数")).toBeInTheDocument();
    expect(screen.getByText("精确匹配")).toBeInTheDocument();
    expect(screen.getByText("模糊匹配")).toBeInTheDocument();
    expect(screen.getAllByText(/infer_accounting_class/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/map_accounting_class/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("审计明细")).toBeInTheDocument();
    expect(screen.getByText("政策金债")).toBeInTheDocument();
  });

  it("renders warning alert when warnings exist", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsAccountingClassAudit: vi.fn(async () => ({
        result_meta: createResultMeta(),
        result: createAccountingAuditResult({
          warnings: ["示例：映射规则版本待对齐"],
          rows: [],
        }),
      })),
    };

    render(
      <ApiClientProvider client={client}>
        <AccountingClassAuditView reportDate="2026-03-31" />
      </ApiClientProvider>,
    );

    expect(await screen.findByText("提示")).toBeInTheDocument();
    expect(screen.getByText("示例：映射规则版本待对齐")).toBeInTheDocument();
  });
});
