import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import type { ResultMeta } from "../api/contracts";
import { ApiClientProvider, createApiClient } from "../api/client";
import PnlAttributionPage from "../features/pnl-attribution/pages/PnlAttributionPage";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="pnl-attribution-echarts-stub" />,
}));

function buildResultMeta(resultKind: string, traceId = "tr_pnl_attribution_test"): ResultMeta {
  return {
    trace_id: traceId,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_test",
    vendor_version: "vv_none",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    as_of_date: "2026-02-28",
    generated_at: "2026-04-09T10:30:00Z",
    tables_used: [],
    filters_applied: {},
    evidence_rows: 1,
    next_drill: [],
  };
}

describe("PnlAttributionPage", () => {
  it("mounts and exposes the detailed Campisi drill-down panels", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("pnl-attribution-page-title")).toBeInTheDocument();
    expect(screen.getByTestId("pnl-attribution-workbench-lead")).toBeInTheDocument();
    expect(screen.getByTestId("pnl-attribution-current-view-lead")).toBeInTheDocument();

    const currentViewMeta = await screen.findByTestId("pnl-attribution-current-view-meta");
    expect(currentViewMeta).toHaveTextContent("2026-03");
    expect(currentViewMeta).toHaveTextContent("2026-04-09");
    expect(currentViewMeta).toHaveTextContent("2026-04-09T10:30:00Z");
    const bridgePanel = screen.getByTestId("volume-rate-bridge-panel");
    expect(bridgePanel).toHaveTextContent("损益变动桥");
    expect(bridgePanel).toHaveTextContent("交叉效应");
    expect(bridgePanel).toHaveTextContent("未解释差额");

    await user.click(screen.getByRole("button", { name: /TPL/i }));
    expect(screen.getByRole("button", { name: /TPL/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Campisi/i }));

    expect(await screen.findByTestId("campisi-formal-closure-warning")).toHaveTextContent("PnL");

    const advancedMeta = screen.getByTestId("pnl-attribution-advanced-view-meta");
    expect(advancedMeta).toHaveTextContent("Carry / Roll-down");
    expect(advancedMeta).toHaveTextContent("Campisi");
  });

  it("defaults to the latest common report date and reuses product category endpoints", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });
    const getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.dates"),
      result: {
        report_dates: ["2026-03-31", "2026-02-28"],
        formal_fi_report_dates: ["2026-03-31", "2026-02-28"],
        nonstd_bridge_report_dates: [],
      },
    }));
    const getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildResultMeta("product_category_pnl.dates"),
      result: {
        report_dates: ["2026-02-28", "2026-01-31"],
      },
    }));
    const getVolumeRateAttribution = vi.fn(client.getVolumeRateAttribution.bind(client));
    const getProductCategoryPnl = vi.fn(client.getProductCategoryPnl.bind(client));
    const getProductCategoryAttribution = vi.fn(client.getProductCategoryAttribution.bind(client));
    client.getFormalPnlDates = getFormalPnlDates;
    client.getProductCategoryDates = getProductCategoryDates;
    client.getVolumeRateAttribution = getVolumeRateAttribution;
    client.getProductCategoryPnl = getProductCategoryPnl;
    client.getProductCategoryAttribution = getProductCategoryAttribution;

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() =>
      expect(getVolumeRateAttribution).toHaveBeenCalledWith({
        reportDate: "2026-02-28",
        compareType: "mom",
      }),
    );

    await user.click(screen.getByTestId("pnl-attribution-tab-product-category"));

    await waitFor(() =>
      expect(getProductCategoryAttribution).toHaveBeenCalledWith({
        reportDate: "2026-02-28",
        compare: "mom",
      }),
    );
    expect(getProductCategoryPnl).toHaveBeenCalledWith({
      reportDate: "2026-02-28",
      view: "monthly",
    });
    expect(getProductCategoryPnl).toHaveBeenCalledWith({
      reportDate: "2026-02-28",
      view: "ytd",
    });
    expect(await screen.findByTestId("pnl-attribution-product-category-tab")).toBeInTheDocument();
  });

  it("surfaces a missing common report date instead of silently falling back", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });
    const getVolumeRateAttribution = vi.fn(client.getVolumeRateAttribution.bind(client));
    client.getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildResultMeta("pnl.dates"),
      result: {
        report_dates: ["2026-03-31"],
        formal_fi_report_dates: ["2026-03-31"],
        nonstd_bridge_report_dates: [],
      },
    }));
    client.getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildResultMeta("product_category_pnl.dates"),
      result: {
        report_dates: [],
      },
    }));
    client.getVolumeRateAttribution = getVolumeRateAttribution;

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("pnl-attribution-common-date-missing")).toBeInTheDocument();
    expect(getVolumeRateAttribution).not.toHaveBeenCalled();
  });
});
