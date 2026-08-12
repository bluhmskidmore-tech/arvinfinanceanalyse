/**
 * Date-semantics contract probe for PAGE-BALANCE-001 (/balance-analysis).
 *
 * Pins two page-level date rules that historically drifted:
 * 1. The read model must never present a requested report date as backend-confirmed:
 *    requested != resolved must surface as "mismatch", a missing overview date as
 *    "pending", and only an exact echo as "matched".
 * 2. The ADB analytical preview must keep its averaging window auditable: the
 *    year-start-to-report-date (YTD) basis copy plus the exact window bounds and
 *    day count from the payload, with a null NIM shown as an em dash rather than
 *    a fabricated percentage.
 *
 * The window *derivation* (report date -> `${year}-01-01` start) is asserted by
 * BalanceAnalysisPage.test.tsx via the getAdbComparison call args; this probe
 * covers the read-model status contract and the rendered window surface.
 */
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type {
  AdbComparisonResponse,
  BalanceAnalysisOverviewPayload,
} from "../api/contracts";
import AdbAnalyticalPreview from "../features/balance-analysis/components/AdbAnalyticalPreview";
import { buildBalanceAnalysisPageReadModel } from "../features/balance-analysis/pages/balanceAnalysisPageModel";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="adb-date-contract-echarts-stub" />,
}));

function buildOverview(reportDate: string): BalanceAnalysisOverviewPayload {
  return {
    report_date: reportDate,
    position_scope: "asset",
    currency_basis: "CNY",
    detail_row_count: 12,
    summary_row_count: 4,
    total_market_value_amount: "1200000000",
    total_amortized_cost_amount: "1100000000",
    total_accrued_interest_amount: "30000000",
    asset_total_market_value_amount: "1200000000",
    liability_total_market_value_amount: "0",
    asset_total_amortized_cost_amount: "1100000000",
    liability_total_amortized_cost_amount: "0",
    asset_total_accrued_interest_amount: "30000000",
    liability_total_accrued_interest_amount: "0",
  };
}

function buildReadModel({
  requestedReportDate,
  overview,
}: {
  requestedReportDate: string;
  overview: BalanceAnalysisOverviewPayload | null;
}) {
  return buildBalanceAnalysisPageReadModel({
    clientMode: "real",
    requestedReportDate,
    selectedPositionScope: "asset",
    selectedCurrencyBasis: "CNY",
    overview,
    summary: null,
    decisionItems: null,
    metaSections: [],
  });
}

describe("BalanceAnalysisDateSemanticsContract", () => {
  describe("requested vs resolved report date", () => {
    it("flags a requested-vs-resolved report-date mismatch instead of silently matching", () => {
      const readModel = buildReadModel({
        requestedReportDate: "2025-11-30",
        overview: buildOverview("2025-12-31"),
      });

      expect(readModel.dateStatus).toBe("mismatch");
      expect(readModel.requestedReportDate).toBe("2025-11-30");
      expect(readModel.resolvedReportDate).toBe("2025-12-31");

      const dateBadge = readModel.statusBadges.find((badge) => badge.key === "date");
      expect(dateBadge?.label).toContain("2025-11-30");
      expect(dateBadge?.label).toContain("2025-12-31");
      expect(dateBadge?.tone).toBe("warning");

      const mismatchSurface = readModel.stateSurfaces.find(
        (surface) => surface.key === "date-mismatch",
      );
      expect(mismatchSurface).toBeDefined();
      expect(mismatchSurface?.variant).toBe("fallback-date");
      expect(
        readModel.stateSurfaces.find((surface) => surface.key === "date-matched"),
      ).toBeUndefined();
    });

    it("treats a missing overview report date as pending, never as backend-confirmed", () => {
      const readModel = buildReadModel({
        requestedReportDate: "2025-12-31",
        overview: null,
      });

      expect(readModel.dateStatus).toBe("pending");
      expect(
        readModel.stateSurfaces.find((surface) => surface.key === "date-pending"),
      ).toBeDefined();
      expect(
        readModel.stateSurfaces.find((surface) => surface.key === "date-matched"),
      ).toBeUndefined();
    });

    it("confirms matched only when the backend echoes the exact requested date", () => {
      const readModel = buildReadModel({
        requestedReportDate: "2025-12-31",
        overview: buildOverview("2025-12-31"),
      });

      expect(readModel.dateStatus).toBe("matched");
      expect(
        readModel.stateSurfaces.find((surface) => surface.key === "date-matched"),
      ).toBeDefined();
      expect(
        readModel.stateSurfaces.find((surface) => surface.key === "date-mismatch"),
      ).toBeUndefined();
    });
  });

  describe("ADB preview averaging-window surface", () => {
    it("renders the YTD basis copy plus exact window bounds and day count for a mid-year report date", () => {
      const comparison: AdbComparisonResponse = {
        report_date: "2025-06-30",
        start_date: "2025-01-01",
        end_date: "2025-06-30",
        calendar_days_inclusive: 181,
        adb_denominator_basis: "formal_calendar",
        num_days: 181,
        simulated: false,
        total_spot_assets: 300_000_000,
        total_avg_assets: 250_000_000,
        total_spot_liabilities: 120_000_000,
        total_avg_liabilities: 100_000_000,
        total_avg_interbank_assets: 0,
        total_avg_interbank_liabilities: 0,
        asset_yield: null,
        liability_cost: null,
        net_interest_margin: null,
        assets_breakdown: [],
        liabilities_breakdown: [],
      };

      render(
        <MemoryRouter>
          <AdbAnalyticalPreview comparison={comparison} href="/average-balance" />
        </MemoryRouter>,
      );

      const preview = screen.getByTestId("balance-analysis-adb-preview");
      expect(preview).toHaveTextContent("年初至报告日");
      expect(preview).toHaveTextContent("区间起点 2025-01-01");
      expect(preview).toHaveTextContent("区间终点 2025-06-30");
      expect(preview).toHaveTextContent("181 天");
      expect(preview).not.toHaveTextContent("NaN");

      const nimCard = within(preview).getByText("NIM").parentElement;
      expect(nimCard?.textContent).toContain("—");
      expect(nimCard?.textContent).not.toContain("%");
    });
  });
});
