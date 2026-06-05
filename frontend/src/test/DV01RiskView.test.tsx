import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ApiEnvelope, DV01RiskPayload, Numeric, ResultMeta } from "../api/contracts";
import { DV01RiskView } from "../features/bond-analytics/components/DV01RiskView";
import { formatRawAsNumeric } from "../utils/format";

type GetBondAnalyticsDv01Risk = (
  reportDate: string,
  options?: { accountingClass?: string; topN?: number; shockBps?: string },
) => Promise<ApiEnvelope<DV01RiskPayload>>;

const yuan = (raw: number, signAware = false) =>
  formatRawAsNumeric({ raw, unit: "yuan", sign_aware: signAware });
const ratio = (raw: number, precision = 2) =>
  formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false, precision });
const dv01 = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });
const bp = (raw: number) => formatRawAsNumeric({ raw, unit: "bp", sign_aware: true });

function resultMeta(): ResultMeta {
  return {
    trace_id: "tr_dv01",
    basis: "formal",
    result_kind: "bond_analytics.dv01_risk",
    formal_use_allowed: true,
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    cache_version: "cv",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T00:00:00Z",
  };
}

function payload(overrides: Partial<DV01RiskPayload> = {}): DV01RiskPayload {
  return {
    report_date: "2026-03-31",
    accounting_class: "OCI",
    total_face_value: yuan(10_000_000_000),
    total_market_value: yuan(10_500_000_000),
    face_weighted_modified_duration: ratio(3.43),
    total_dv01: dv01(3_546_830),
    position_count: 574,
    shock_scenarios: [
      {
        scenario_name: "rate_up_10bp",
        shock_bp: bp(10),
        estimated_pnl: yuan(-35_468_300, true),
      },
      {
        scenario_name: "rate_down_10bp",
        shock_bp: bp(-10),
        estimated_pnl: yuan(35_468_300, true),
      },
    ],
    tenor_buckets: [
      {
        tenor_bucket: "3-5Y",
        face_value: yuan(6_000_000_000),
        market_value: yuan(6_200_000_000),
        face_weighted_modified_duration: ratio(3.8),
        dv01: dv01(2_100_000),
        dv01_share: ratio(0.5921, 4),
        position_count: 210,
      },
    ],
    top_bonds: [
      {
        instrument_code: "BOND-1",
        instrument_name: "测试债 01",
        issuer_name: "发行人A",
        rating: "AAA",
        tenor_bucket: "3-5Y",
        accounting_class: "OCI",
        face_value: yuan(1_000_000_000),
        market_value: yuan(1_050_000_000),
        modified_duration: ratio(3.7),
        dv01: dv01(390_000),
        dv01_share: ratio(0.10996, 4),
      },
    ],
    top_issuers: [
      {
        issuer_name: "发行人A",
        face_value: yuan(1_500_000_000),
        market_value: yuan(1_560_000_000),
        face_weighted_modified_duration: ratio(3.65),
        dv01: dv01(580_000),
        dv01_share: ratio(0.1635, 4),
        position_count: 3,
      },
    ],
    warnings: [],
    computed_at: "2026-04-12T00:00:00Z",
    ...overrides,
  };
}

function renderView(getDv01Risk: GetBondAnalyticsDv01Risk) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  const client = {
    ...createApiClient({ mode: "mock" }),
    getBondAnalyticsDv01Risk: getDv01Risk,
  };
  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <DV01RiskView reportDate="2026-03-31" />
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("DV01RiskView", () => {
  it("defaults to OCI and renders KPI, shock, tenor, bond, and issuer sections", async () => {
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload(),
    }));

    renderView(getDv01Risk);

    await waitFor(() =>
      expect(getDv01Risk).toHaveBeenCalledWith("2026-03-31", {
        accountingClass: "OCI",
        topN: 20,
        shockBps: "1,10,25,50",
      }),
    );

    expect(await screen.findByTestId("dv01-risk-view")).toBeInTheDocument();
    expect(screen.getByTestId("dv01-risk-accounting-class")).toHaveTextContent("OCI");
    expect(screen.getByText("总面值")).toBeInTheDocument();
    expect(screen.getByText("100.00 亿")).toBeInTheDocument();
    expect(screen.getByText("总市值")).toBeInTheDocument();
    expect(screen.getByText("105.00 亿")).toBeInTheDocument();
    expect(screen.getByText("面值加权修正久期")).toBeInTheDocument();
    expect(screen.getByText("3.43 年")).toBeInTheDocument();
    expect(screen.getByText("总 DV01")).toBeInTheDocument();
    expect(screen.getByText("3,546,830")).toBeInTheDocument();
    expect(screen.getAllByText("持仓数").length).toBeGreaterThan(0);
    expect(screen.getByText("574")).toBeInTheDocument();

    const shockTable = screen.getByTestId("dv01-risk-shocks-table");
    expect(within(shockTable).getByText("rate_up_10bp")).toBeInTheDocument();
    expect(within(shockTable).getByText("-0.35 亿")).toBeInTheDocument();
    expect(within(shockTable).getByText("+0.35 亿")).toBeInTheDocument();

    expect(screen.getByText("期限桶 DV01")).toBeInTheDocument();
    const tenorTable = screen.getByTestId("dv01-risk-tenor-table");
    expect(within(tenorTable).getByText("3-5Y")).toBeInTheDocument();
    expect(within(tenorTable).getByText("3.80 年")).toBeInTheDocument();
    expect(within(tenorTable).getByText("59.21%")).toBeInTheDocument();
    expect(screen.getByText("Top 债券")).toBeInTheDocument();
    expect(screen.getByText("测试债 01")).toBeInTheDocument();
    expect(screen.getByText("3.70 年")).toBeInTheDocument();
    expect(screen.getByText("Top 发行人")).toBeInTheDocument();
    expect(within(screen.getByTestId("dv01-risk-top-issuers-table")).getByText("发行人A")).toBeInTheDocument();
    expect(within(screen.getByTestId("dv01-risk-top-issuers-table")).getByText("3.65 年")).toBeInTheDocument();
  });

  it("refetches when accounting class or Top N changes", async () => {
    const user = userEvent.setup();
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload(),
    }));

    renderView(getDv01Risk);
    await waitFor(() => expect(getDv01Risk).toHaveBeenCalledTimes(1));

    await user.click(screen.getByText("全部"));
    await waitFor(() => expect(getDv01Risk).toHaveBeenCalledTimes(2));
    expect(getDv01Risk.mock.calls[1]).toEqual([
      "2026-03-31",
      { accountingClass: "all", topN: 20, shockBps: "1,10,25,50" },
    ]);

    await user.selectOptions(screen.getByTestId("dv01-risk-topn"), "50");
    await waitFor(() => expect(getDv01Risk).toHaveBeenCalledTimes(3));
    expect(getDv01Risk.mock.calls[2]).toEqual([
      "2026-03-31",
      { accountingClass: "all", topN: 50, shockBps: "1,10,25,50" },
    ]);
  });

  it("shows the governed empty state without deriving frontend metrics", async () => {
    const zero = (unit: Numeric["unit"]) =>
      formatRawAsNumeric({ raw: 0, unit, sign_aware: false });
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload({
        total_face_value: zero("yuan"),
        total_market_value: zero("yuan"),
        face_weighted_modified_duration: zero("ratio"),
        total_dv01: zero("dv01"),
        position_count: 0,
        shock_scenarios: [],
        tenor_buckets: [],
        top_bonds: [],
        top_issuers: [],
        warnings: ["no formal bond analytics rows"],
      }),
    }));

    renderView(getDv01Risk);

    expect(await screen.findByText("该报告日/分类暂无债券 DV01 数据")).toBeInTheDocument();
    expect(screen.queryByTestId("dv01-risk-shocks-table")).not.toBeInTheDocument();
  });
});
