import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../../../api/client";
import { buildMockApiEnvelope } from "../../../mocks/mockApiEnvelope";
import { EM_DASH } from "../../../utils/format";
import { MarketDataTushareSupplementSection } from "./MarketDataTushareSupplementSection";

function renderSection(client: ApiClient) {
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
      <MarketDataTushareSupplementSection />
    </Wrapper>,
  );
}

describe("MarketDataTushareSupplementSection", () => {
  it("renders money supply and eco calendar rows from getTushareSupplement", async () => {
    const base = createApiClient({ mode: "mock" });
    const getTushareSupplement = vi.fn(async () => base.getTushareSupplement());

    renderSection({
      ...base,
      getTushareSupplement,
    });

    expect(await screen.findByTestId("market-data-tushare-money-supply-table")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-tushare-eco-cal-list")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-tushare-supplement-meta")).toBeInTheDocument();
    expect(screen.getByText("Mock 中国CPI同比")).toBeInTheDocument();
    await waitFor(() => {
      expect(getTushareSupplement).toHaveBeenCalled();
    });
  });

  it("adds analytical summaries and trend context from existing supplement rows", async () => {
    const base = createApiClient({ mode: "mock" });
    const getTushareSupplement = vi.fn(async () =>
      buildMockApiEnvelope(
        "market_data.tushare_supplement",
        {
          money_supply_rows: [
            {
              month: "2026-04-01",
              m0: 147477.38,
              m0_yoy: 12.2,
              m0_mom: 0.27,
              m1: 1145833.73,
              m1_yoy: 5.0,
              m1_mom: -3.97,
              m2: 3530425.21,
              m2_yoy: 8.6,
              m2_mom: -0.23,
            },
            {
              month: "2026-03-01",
              m0: 146000,
              m0_yoy: 12.5,
              m0_mom: 0.12,
              m1: 1160000,
              m1_yoy: 5.1,
              m1_mom: 2.93,
              m2: 3510000,
              m2_yoy: 8.5,
              m2_mom: 1.33,
            },
            {
              month: "2026-02-01",
              m0: 145000,
              m0_yoy: 14.1,
              m0_mom: 0.2,
              m1: 1150000,
              m1_yoy: 5.9,
              m1_mom: -1.73,
              m2: 3490000,
              m2_yoy: 9.0,
              m2_mom: 0.59,
            },
          ],
          eco_cal_rows: [
            {
              event_id: "eco-1",
              event_date: "20260613",
              event_time: "09:30",
              currency: "CNY",
              country: "China",
              event: "中国CPI同比",
              value: "1.2",
              pre_value: "1.0",
              fore_value: "1.1",
            },
            {
              event_id: "eco-2",
              event_date: "20260613",
              event_time: "15:00",
              currency: "EUR",
              country: "Spain",
              event: "西班牙CPI年率",
              value: null,
              pre_value: "3.2",
              fore_value: "3.1",
            },
            {
              event_id: "eco-3",
              event_date: "20260614",
              event_time: "14:00",
              currency: "GBP",
              country: "United Kingdom",
              event: "英国制造业产出年率",
              value: "1.0",
              pre_value: "1.2",
              fore_value: "0.4",
            },
          ],
          warnings: [],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_tushare_supplement_summary",
          vendor_version: "vv_tushare_supplement_v1",
          rule_version: "rv_market_data_tushare_supplement_v1",
          cache_version: "cv_market_data_tushare_supplement_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          as_of_date: "2026-06-15",
        },
      ),
    );

    renderSection({
      ...base,
      getTushareSupplement,
    });

    const moneySummary = await screen.findByTestId("market-data-tushare-money-summary");
    expect(moneySummary).toHaveTextContent("2026-04");
    expect(moneySummary).toHaveTextContent("M2-M1 剪刀差");
    expect(moneySummary).toHaveTextContent("3.60%");
    expect(moneySummary).toHaveTextContent("近3月 M2 同比");
    expect(moneySummary).toHaveTextContent("下行");
    expect(screen.getByTestId("market-data-tushare-money-trend")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-tushare-money-trend")).toHaveTextContent("M1同比");
    expect(screen.getByTestId("market-data-tushare-money-trend")).toHaveTextContent("剪刀差");

    const ecoSummary = screen.getByTestId("market-data-tushare-eco-summary");
    expect(ecoSummary).toHaveTextContent("事件 3");
    expect(ecoSummary).toHaveTextContent("已公布 2");
    expect(ecoSummary).toHaveTextContent("待公布 1");
    expect(screen.getByTestId("market-data-tushare-eco-currency-filter")).toHaveTextContent("CNY 1");
    expect(screen.getByTestId("market-data-tushare-eco-currency-filter")).toHaveTextContent("EUR 1");
    expect(screen.getByTestId("market-data-tushare-eco-currency-filter")).toHaveTextContent("GBP 1");
  });

  it("filters eco calendar events by currency chip", async () => {
    const base = createApiClient({ mode: "mock" });
    const getTushareSupplement = vi.fn(async () =>
      buildMockApiEnvelope(
        "market_data.tushare_supplement",
        {
          money_supply_rows: [],
          eco_cal_rows: [
            {
              event_id: "eco-1",
              event_date: "20260613",
              event_time: "09:30",
              currency: "CNY",
              country: "China",
              event: "中国CPI同比",
              value: "1.2",
              pre_value: "1.0",
              fore_value: "1.1",
            },
            {
              event_id: "eco-2",
              event_date: "20260613",
              event_time: "15:00",
              currency: "EUR",
              country: "Spain",
              event: "西班牙CPI年率",
              value: null,
              pre_value: "3.2",
              fore_value: "3.1",
            },
          ],
          warnings: [],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_tushare_supplement_filter",
          vendor_version: "vv_tushare_supplement_v1",
          rule_version: "rv_market_data_tushare_supplement_v1",
          cache_version: "cv_market_data_tushare_supplement_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          as_of_date: "2026-06-15",
        },
      ),
    );

    renderSection({
      ...base,
      getTushareSupplement,
    });

    expect(await screen.findByText("中国CPI同比")).toBeInTheDocument();
    expect(screen.getByText("西班牙CPI年率")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "EUR 1" }));

    expect(screen.queryByText("中国CPI同比")).not.toBeInTheDocument();
    expect(screen.getByText("西班牙CPI年率")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-tushare-eco-summary")).toHaveTextContent("事件 1");
  });

  it("marks money trend and spread gaps instead of implying a formal reading", async () => {
    const base = createApiClient({ mode: "mock" });
    const getTushareSupplement = vi.fn(async () =>
      buildMockApiEnvelope(
        "market_data.tushare_supplement",
        {
          money_supply_rows: [
            {
              month: "2026-04-01",
              m0: 147477.38,
              m0_yoy: 12.2,
              m0_mom: 0.27,
              m1: 1145833.73,
              m1_yoy: null,
              m1_mom: -3.97,
              m2: 3530425.21,
              m2_yoy: 8.6,
              m2_mom: -0.23,
            },
          ],
          eco_cal_rows: [],
          warnings: [],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_tushare_supplement_sparse",
          vendor_version: "vv_tushare_supplement_v1",
          rule_version: "rv_market_data_tushare_supplement_v1",
          cache_version: "cv_market_data_tushare_supplement_v1",
          quality_flag: "warning",
          vendor_status: "ok",
          fallback_mode: "none",
          as_of_date: "2026-06-15",
        },
      ),
    );

    renderSection({
      ...base,
      getTushareSupplement,
    });

    const moneySummary = await screen.findByTestId("market-data-tushare-money-summary");
    const spreadCard = within(moneySummary).getByText("M2-M1 剪刀差").closest("div");
    const directionCard = within(moneySummary).getByText("近3月 M2 同比").closest("div");

    expect(spreadCard).toHaveTextContent(EM_DASH);
    expect(directionCard).toHaveTextContent("缺口");
    expect(directionCard).not.toHaveTextContent("震荡");
    expect(moneySummary).toHaveTextContent("仅作分析读面");
  });

  it("shows forbidden guidance when API returns 403", async () => {
    const base = createApiClient({ mode: "mock" });
    const getTushareSupplement = vi.fn(async () => {
      throw new Error("Request failed: /ui/market-data/tushare-supplement (403)");
    });

    renderSection({
      ...base,
      getTushareSupplement,
    });

    const error = await screen.findByTestId("market-data-tushare-supplement-error");
    expect(error).toHaveTextContent("无读取权限（403）");
    expect(error).toHaveTextContent("market_data.tushare_supplement");
  });

  it("shows empty-state hints when payload has no rows", async () => {
    const base = createApiClient({ mode: "mock" });
    const getTushareSupplement = vi.fn(async () =>
      buildMockApiEnvelope(
        "market_data.tushare_supplement",
        { money_supply_rows: [], eco_cal_rows: [], warnings: ["Money supply table is not materialized."] },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_tushare_supplement_empty",
          vendor_version: "vv_tushare_supplement_v1",
          rule_version: "rv_market_data_tushare_supplement_v1",
          cache_version: "cv_market_data_tushare_supplement_v1",
          quality_flag: "warning",
          vendor_status: "vendor_unavailable",
          fallback_mode: "none",
          as_of_date: "2026-06-15",
        },
      ),
    );

    renderSection({
      ...base,
      getTushareSupplement,
    });

    expect(await screen.findByTestId("market-data-tushare-money-supply-empty")).toHaveTextContent(
      "refresh_tushare_supplement",
    );
    expect(screen.getByTestId("market-data-tushare-eco-cal-empty")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-tushare-supplement-warnings")).toHaveTextContent(
      "Money supply table is not materialized.",
    );
  });

  it("shows freshness hint with runbook when supplement meta is stale", async () => {
    const base = createApiClient({ mode: "mock" });
    const getTushareSupplement = vi.fn(async () =>
      buildMockApiEnvelope(
        "market_data.tushare_supplement",
        {
          money_supply_rows: [
            {
              month: "2026-04-01",
              m0: 147477.38,
              m0_yoy: 12.2,
              m0_mom: 0.27,
              m1: 1145833.73,
              m1_yoy: 5.0,
              m1_mom: -3.97,
              m2: 3530425.21,
              m2_yoy: 8.6,
              m2_mom: -0.23,
            },
          ],
          eco_cal_rows: [],
          warnings: [],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_tushare_supplement_stale",
          vendor_version: "vv_tushare_supplement_v1",
          rule_version: "rv_market_data_tushare_supplement_v1",
          cache_version: "cv_market_data_tushare_supplement_v1",
          quality_flag: "stale",
          vendor_status: "vendor_stale",
          fallback_mode: "none",
          as_of_date: "2026-05-01",
          generated_at: "2026-05-02T08:00:00Z",
        },
      ),
    );

    renderSection({
      ...base,
      getTushareSupplement,
    });

    const freshness = await screen.findByTestId("market-data-tushare-supplement-freshness");
    expect(freshness).toHaveAttribute("data-tone", "warn");
    expect(freshness).toHaveTextContent("2026-05-01");
    expect(freshness).toHaveTextContent("tushare_supplement_refresh_runbook");
  });
});
