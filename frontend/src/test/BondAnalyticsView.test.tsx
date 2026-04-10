import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BondAnalyticsView } from "../features/bond-analytics/components/BondAnalyticsView";

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
  beforeEach(() => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;

      if (url.includes("/api/bond-analytics/return-decomposition")) {
        return {
          ok: true,
          json: async () => ({ result: createReturnDecompositionResult() }),
        };
      }

      if (url.includes("/api/bond-analytics/action-attribution")) {
        return {
          ok: true,
          json: async () => ({
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

  it("renders the overview-first shell and downgrades placeholder summaries", async () => {
    render(<BondAnalyticsView />);

    expect(
      await screen.findByTestId("bond-analysis-overview", {}, { timeout: 10000 }),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("bond-analysis-module-grid", {}, { timeout: 10000 }),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("bond-analysis-future-grid", {}, { timeout: 10000 }),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("bond-analysis-no-summary", {}, { timeout: 10000 }),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("bond-analysis-module-action-attribution", {}, { timeout: 10000 }),
    ).toHaveAttribute(
      "data-tier",
      "status",
    );
  });

  it("promotes real action attribution content and keeps drill switching", async () => {
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
            json: async () => ({ result: createReturnDecompositionResult() }),
          };
        }

        if (url.includes("/api/bond-analytics/action-attribution")) {
          return {
            ok: true,
            json: async () => ({
              result: createActionAttributionResult({
                total_actions: 4,
                total_pnl_from_actions: "1500000",
                by_action_type: [
                  {
                    action_type: "ADD_DURATION",
                    action_type_name: "加久期",
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

    render(<BondAnalyticsView />);

    expect(
      await screen.findByTestId("bond-analysis-summary-action-attribution", {}, { timeout: 10000 }),
    ).toBeInTheDocument();

    await user.click(
      within(
        await screen.findByTestId("bond-analysis-module-action-attribution", {}, { timeout: 10000 }),
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
