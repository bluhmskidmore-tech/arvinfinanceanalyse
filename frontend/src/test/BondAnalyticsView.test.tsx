import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import { BondAnalyticsView } from "../features/bond-analytics/components/BondAnalyticsView";

function renderBondAnalyticsView() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
  const client = createApiClient({ mode: "mock" });
  return render(
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        <BondAnalyticsView />
      </QueryClientProvider>
    </ApiClientProvider>,
  );
}

function createResultMeta(overrides: Record<string, unknown> = {}) {
  return {
    trace_id: "tr_demo",
    basis: "formal",
    result_kind: "bond_analytics.action_attribution",
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

function createReturnDecompositionResult() {
  return {
    report_date: "2026-03-31",
    period_type: "MoM",
    period_start: "2026-03-01",
    period_end: "2026-03-31",
    carry: "0",
    roll_down: "0",
    rate_effect: "0",
    spread_effect: "0",
    trading: "0",
    fx_effect: "0",
    convexity_effect: "0",
    explained_pnl: "0",
    explained_pnl_accounting: "0",
    explained_pnl_economic: "0",
    oci_reserve_impact: "0",
    actual_pnl: "0",
    recon_error: "0",
    recon_error_pct: "0",
    by_asset_class: [],
    by_accounting_class: [],
    bond_details: [],
    bond_count: 0,
    total_market_value: "0",
    warnings: [],
    computed_at: "2026-04-10T00:00:00Z",
  };
}

function createActionAttributionResult(overrides: Record<string, unknown> = {}) {
  return {
    report_date: "2026-03-31",
    period_type: "MoM",
    period_start: "2026-03-01",
    period_end: "2026-03-31",
    total_actions: 0,
    total_pnl_from_actions: "0",
    by_action_type: [],
    action_details: [],
    period_start_duration: "3.10",
    period_end_duration: "3.05",
    duration_change_from_actions: "-0.05",
    period_start_dv01: "120000",
    period_end_dv01: "115000",
    warnings: [],
    computed_at: "2026-04-10T00:00:00Z",
    ...overrides,
  };
}

describe("BondAnalyticsView", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;

      if (url.includes("/api/bond-analytics/return-decomposition")) {
        return {
          ok: true,
          json: async () => ({
            result_meta: createResultMeta({
              result_kind: "bond_analytics.return_decomposition",
            }),
            result: createReturnDecompositionResult(),
          }),
        };
      }

      if (url.includes("/api/bond-analytics/action-attribution")) {
        return {
          ok: true,
          json: async () => ({
            result_meta: createResultMeta({
              quality_flag: "warning",
              fallback_mode: "latest_snapshot",
            }),
            result: createActionAttributionResult({
              warnings: ["DuckDB fact tables not yet populated - returning empty attribution"],
            }),
          }),
        };
      }

      throw new Error(`Unhandled fetch request: ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it(
    "renders a governed cockpit with top-right deferred visibility and non-promoted modules",
    async () => {
    renderBondAnalyticsView();

    expect(
      await screen.findByTestId("bond-analysis-top-cockpit", {}, { timeout: 10000 }),
    ).toBeInTheDocument();

    const topCockpit = await screen.findByTestId("bond-analysis-top-cockpit");
    expect(within(topCockpit).getByTestId("bond-analysis-market-context-strip")).toBeInTheDocument();
    expect(within(topCockpit).getByTestId("bond-analysis-filter-action-strip")).toBeInTheDocument();
    expect(within(topCockpit).getByTestId("bond-analysis-truth-strip")).toBeInTheDocument();
    expect(within(topCockpit).getByTestId("bond-analysis-right-rail")).toBeInTheDocument();
    expect(within(topCockpit).getByTestId("bond-analysis-future-panel")).toBeInTheDocument();
    expect(within(topCockpit).getByText("No refresh run has been captured yet.")).toBeInTheDocument();

    expect(screen.queryByTestId("bond-analysis-headline-action-attribution")).not.toBeInTheDocument();
    expect(screen.queryByTestId("bond-analysis-open-headline-action-attribution")).not.toBeInTheDocument();
    expect(screen.getByTestId("bond-analysis-readiness-matrix")).toBeInTheDocument();
    expect(
      await screen.findByTestId("bond-analysis-detail-section", {}, { timeout: 10000 }),
    ).toHaveAttribute(
      "data-module-key",
      "action-attribution",
    );
    expect(screen.getByTestId("bond-analysis-readiness-return-decomposition")).toHaveAttribute(
      "data-promotion-destination",
      "readiness-only",
    );
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0] instanceof Request ? call[0].url : call[0]).includes(
          "/api/bond-analytics/return-decomposition",
        ),
      ),
    ).toBe(false);
    },
    20_000,
  );

  it("promotes clean action attribution and keeps cockpit drill switching", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;

        if (url.includes("/api/bond-analytics/return-decomposition")) {
          return {
            ok: true,
            json: async () => ({
              result_meta: createResultMeta({
                result_kind: "bond_analytics.return_decomposition",
              }),
              result: createReturnDecompositionResult(),
            }),
          };
        }

        if (url.includes("/api/bond-analytics/action-attribution")) {
          return {
            ok: true,
            json: async () => ({
              result_meta: createResultMeta(),
              result: createActionAttributionResult({
                total_actions: 4,
                total_pnl_from_actions: "1500000",
                by_action_type: [
                  {
                    action_type: "ADD_DURATION",
                    action_type_name: "Add duration",
                    action_count: 4,
                    total_pnl_economic: "1500000",
                    total_pnl_accounting: "1500000",
                    avg_pnl_per_action: "375000",
                  },
                ],
              }),
            }),
          };
        }

        throw new Error(`Unhandled fetch request: ${url}`);
      }),
    );

    renderBondAnalyticsView();

    expect(
      await screen.findByTestId("bond-analysis-headline-action-attribution", {}, { timeout: 10000 }),
    ).toBeInTheDocument();

    await user.click(
      await screen.findByTestId("bond-analysis-open-headline-action-attribution", {}, {
        timeout: 10000,
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("bond-analysis-detail-section")).toHaveAttribute(
        "data-module-key",
        "action-attribution",
      );
    });

    await user.click(
      within(
        await screen.findByTestId("bond-analysis-readiness-action-attribution", {}, {
          timeout: 10000,
        }),
      ).getByTestId("bond-analysis-open-action-attribution"),
    );

    await waitFor(() => {
      expect(screen.getByTestId("bond-analysis-detail-section")).toHaveAttribute(
        "data-module-key",
        "action-attribution",
      );
    });
  });
});
