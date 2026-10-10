import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../../api/client";
import type {
  ApiBasis,
  PnlDatesPayload,
  PnlOverviewPayload,
  PnlV1DataPayload,
  PnlV1DetailRow,
  ResultMeta,
} from "../../api/contracts";
import { EM_DASH } from "../../utils/format";
import FormalPnlV1Page from "./FormalPnlV1Page";

function renderFormalPnlV1Page(client: ApiClient) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(
    <Wrapper>
      <FormalPnlV1Page />
    </Wrapper>,
  );
}

function buildMeta(resultKind: string, traceId: string, basis: ApiBasis = "formal"): ResultMeta {
  return {
    trace_id: traceId,
    basis,
    result_kind: resultKind,
    formal_use_allowed: basis === "formal",
    source_version: "sv_pnl_test",
    vendor_version: "vv_none",
    rule_version: "rv_pnl_test",
    cache_version: "cv_pnl_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T08:00:00Z",
  };
}

function sampleFormalFiRow(overrides: Partial<PnlV1DetailRow> = {}): PnlV1DetailRow {
  return {
    report_date: "2025-12-31",
    source: "FI",
    asset_code: "240001.IB",
    bond_name: "240001.IB",
    portfolio: "FI Desk A",
    asset_type: "A",
    asset_class: "bond-trading",
    market_value: "1234500",
    interest_income: "1200.50",
    fair_value_change: "30.25",
    capital_gain: "10.00",
    total_pnl: "1240.75",
    source_version: "sv_pnl_row",
    trace_id: "tr_pnl_fi_row",
    ...overrides,
  };
}

function closedOverviewPayload(reportDate = "2025-12-31"): PnlOverviewPayload {
  return {
    report_date: reportDate,
    formal_fi_row_count: 7,
    nonstd_bridge_row_count: 2,
    interest_income_514: "100000.00",
    fair_value_change_516: "200000.00",
    capital_gain_517: "300000.00",
    manual_adjustment: "400000.00",
    total_pnl: "1000000.00",
  };
}

function stubDatesAndData(client: ApiClient, rows: PnlV1DetailRow[], overview: PnlOverviewPayload) {
  const datesPayload: PnlDatesPayload = {
    report_dates: [overview.report_date],
    formal_fi_report_dates: [overview.report_date],
    nonstd_bridge_report_dates: [overview.report_date],
  };
  const dataPayload: PnlV1DataPayload = {
    report_date: overview.report_date,
    source_tables: ["data_input/pnl"],
    rows,
  };

  return {
    ...client,
    getFormalPnlDates: vi.fn(async () => ({
      result_meta: buildMeta("pnl.dates", "tr_pnl_dates_wan"),
      result: datesPayload,
    })),
    getPnlV1Data: vi.fn(async () => ({
      result_meta: buildMeta("pnl.v1_data", "tr_pnl_data_wan"),
      result: dataPayload,
    })),
    getFormalPnlOverview: vi.fn(async () => ({
      result_meta: buildMeta("pnl.overview", "tr_pnl_overview_wan"),
      result: overview,
    })),
  };
}

function kpiValue(testId: string): string {
  const card = screen.getByTestId(testId);
  const value = card.querySelector(".kpi-card__value");
  if (!value?.textContent) {
    throw new Error(`missing kpi value for ${testId}`);
  }
  return value.textContent;
}

function parseWanDisplay(display: string): number {
  return Number(display.replace(/,/g, ""));
}

describe("FormalPnlV1Page wan display and manual adjustment", () => {
  it("converts detail-table yuan amounts to wan and labels columns in 万元", async () => {
    const base = createApiClient({ mode: "mock" });
    renderFormalPnlV1Page(
      stubDatesAndData(base, [sampleFormalFiRow()], closedOverviewPayload()),
    );

    const fiTable = await screen.findByTestId("pnl-formal-fi-table");
    await waitFor(() => {
      expect(fiTable).toHaveTextContent("市值（万元）");
      expect(fiTable).toHaveTextContent("514利息收入（万元）");
      expect(fiTable).toHaveTextContent("516公允价值（万元）");
      expect(fiTable).toHaveTextContent("517投资收益（万元）");
      expect(fiTable).toHaveTextContent("合计损益（万元）");
      expect(fiTable).toHaveTextContent("123.45");
      expect(fiTable).toHaveTextContent("0.12");
      expect(fiTable).not.toHaveTextContent("1,234,500");
    });
  });

  it("renders missing detail amounts as EM_DASH instead of 0", async () => {
    const base = createApiClient({ mode: "mock" });
    renderFormalPnlV1Page(
      stubDatesAndData(
        base,
        [
          sampleFormalFiRow({
            market_value: null as unknown as string,
            interest_income: "",
            fair_value_change: "0",
            capital_gain: "10000",
            total_pnl: "",
          }),
        ],
        closedOverviewPayload(),
      ),
    );

    const fiTable = await screen.findByTestId("pnl-formal-fi-table");
    await waitFor(() => {
      expect(fiTable).toHaveTextContent(EM_DASH);
      expect(fiTable).toHaveTextContent("0.00");
      expect(fiTable).toHaveTextContent("1.00");
    });
    const dashes = Array.from(fiTable.querySelectorAll(".ag-cell")).filter(
      (cell) => cell.textContent === EM_DASH,
    );
    expect(dashes.length).toBeGreaterThanOrEqual(3);
  });

  it("shows the manual-adjustment KPI and keeps 514+516+517+调整 closed with total", async () => {
    const base = createApiClient({ mode: "mock" });
    renderFormalPnlV1Page(
      stubDatesAndData(base, [sampleFormalFiRow()], closedOverviewPayload()),
    );

    await screen.findByTestId("pnl-kpi-manual-adjustment");
    expect(screen.getByTestId("pnl-kpi-manual-adjustment")).toHaveTextContent("手工调整");
    expect(kpiValue("pnl-kpi-interest-income")).toBe("10.00");
    expect(kpiValue("pnl-kpi-fair-value")).toBe("20.00");
    expect(kpiValue("pnl-kpi-capital-gain")).toBe("30.00");
    expect(kpiValue("pnl-kpi-manual-adjustment")).toBe("40.00");
    expect(kpiValue("pnl-kpi-total-pnl")).toBe("100.00");

    const closedSum =
      parseWanDisplay(kpiValue("pnl-kpi-interest-income")) +
      parseWanDisplay(kpiValue("pnl-kpi-fair-value")) +
      parseWanDisplay(kpiValue("pnl-kpi-capital-gain")) +
      parseWanDisplay(kpiValue("pnl-kpi-manual-adjustment"));
    expect(closedSum).toBe(parseWanDisplay(kpiValue("pnl-kpi-total-pnl")));
    expect(screen.getByTestId("pnl-kpi-total-pnl")).toHaveTextContent("万元");
  });

  it("renders missing manual_adjustment as EM_DASH rather than 0", async () => {
    const base = createApiClient({ mode: "mock" });
    renderFormalPnlV1Page(
      stubDatesAndData(base, [sampleFormalFiRow()], {
        ...closedOverviewPayload(),
        manual_adjustment: "",
      }),
    );

    await screen.findByTestId("pnl-kpi-manual-adjustment");
    expect(kpiValue("pnl-kpi-manual-adjustment")).toBe(EM_DASH);
    expect(screen.getByTestId("pnl-kpi-manual-adjustment")).not.toHaveTextContent("0.00");
  });
});
