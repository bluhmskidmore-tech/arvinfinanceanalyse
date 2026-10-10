import { cleanup, render, screen } from "@testing-library/react";
import type { UseQueryResult } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiEnvelope } from "../api/contracts";
import { buildModuleHomeView, type ModuleHomeDetailPanel } from "../features/workbench/module-home/moduleHomeModel";
import { buildPortfolioComparisonRows, buildYieldDistributionRows } from "../features/workbench/module-home/portfolioHomeModel";
import { PortfolioStructureTabPanel } from "../features/workbench/module-home/PortfolioStructureTabPanel";
import { portfolioCrossPageBondHomeSummary, portfolioCrossPageEnvelope, portfolioCrossPageNumeric } from "./portfolioCrossPageGoldenSample";

vi.mock("../features/workbench/module-home/PortfolioStructureChart", () => ({
  PortfolioStructureChart: () => null,
}));
afterEach(cleanup);

function query<T>(result: T): UseQueryResult<ApiEnvelope<T>> {
  return {
    data: portfolioCrossPageEnvelope("portfolio.ytm.test", result),
    isError: false,
    isLoading: false,
    isFetching: false,
    status: "success",
    fetchStatus: "idle",
  } as UseQueryResult<ApiEnvelope<T>>;
}

function panel(key: string, rows: ModuleHomeDetailPanel["rows"]): ModuleHomeDetailPanel {
  return { key, title: key, meta: "2026-08-31", stateLabel: "关注", stateDetail: "", tone: "watch", rows };
}

describe("Portfolio YTM missing inputs", () => {
  it("keeps missing headline YTM empty and discloses the backend coverage", () => {
    const data = portfolioCrossPageBondHomeSummary();
    data.headline.kpis.weighted_ytm = { ...data.headline.kpis.weighted_ytm, raw: null };
    data.headline.kpis.weighted_ytm_coverage_ratio = portfolioCrossPageNumeric(0, "ratio");
    const view = buildModuleHomeView("portfolio", { mode: "real" }, { bondHeadline: query(data.headline) });
    const ytm = view.kpis.find((item) => item.key === "bond-ytm");
    expect(ytm?.value).toBe("—");
    expect(ytm).toHaveProperty("coverageNote", "YTM 有效样本覆盖 0.00%（按加权市值）");
  });

  it("shows partial coverage in the yield summary instead of hiding it in a tooltip", () => {
    const data = portfolioCrossPageBondHomeSummary().yield_distribution;
    data.weighted_ytm = { ...data.weighted_ytm, raw: null };
    data.weighted_ytm_coverage_ratio = portfolioCrossPageNumeric(0, "ratio");
    const rows = buildYieldDistributionRows(data);
    expect(rows[0].value).toBe("—");
    render(<PortfolioStructureTabPanel panel={panel("yield-distribution", rows)} />);
    expect(screen.getByText("YTM 有效样本覆盖 0.00%（按加权市值）")).toBeVisible();
  });

  it("shows per-portfolio coverage and preserves zero or negative YTM", () => {
    const data = portfolioCrossPageBondHomeSummary().portfolio_comparison;
    data.items = data.items.slice(0, 2);
    data.items[0].weighted_ytm = portfolioCrossPageNumeric(0, "pct", true);
    data.items[1].weighted_ytm = portfolioCrossPageNumeric(-0.01, "pct", true);
    data.items[0].weighted_ytm_coverage_ratio = portfolioCrossPageNumeric(0.5, "ratio");
    data.items[1].weighted_ytm_coverage_ratio = portfolioCrossPageNumeric(1, "ratio");
    const rows = buildPortfolioComparisonRows(data);
    expect(rows[0].ytmDisplay).toBe("0.00%");
    expect(rows[1].ytmDisplay).toBe("-1.00%");
    render(<PortfolioStructureTabPanel panel={panel("portfolio-comparison", rows)} />);
    expect(screen.getByText("YTM 有效样本覆盖 50.00%（按加权市值）")).toBeVisible();
    expect(screen.queryByText(/100.00%/)).not.toBeInTheDocument();
  });

  it("discloses zero coverage when every YTM is missing and no yield buckets exist", () => {
    const data = portfolioCrossPageBondHomeSummary().yield_distribution;
    data.items = [];
    data.weighted_ytm = { ...data.weighted_ytm, raw: null };
    data.weighted_ytm_coverage_ratio = portfolioCrossPageNumeric(0, "ratio");
    const rows = buildYieldDistributionRows(data);
    expect(rows).toHaveLength(1);
    expect(rows[0].value).toBe("—");
    render(<PortfolioStructureTabPanel panel={panel("yield-distribution", rows)} />);
    expect(screen.getByText("YTM 有效样本覆盖 0.00%（按加权市值）")).toBeVisible();
  });

  it("retains the empty state when no holdings are eligible for weighting", () => {
    const data = portfolioCrossPageBondHomeSummary().yield_distribution;
    data.items = [];
    data.weighted_ytm = { ...data.weighted_ytm, raw: null };
    data.weighted_ytm_coverage_ratio = null;
    expect(buildYieldDistributionRows(data)).toEqual([]);
  });
});
