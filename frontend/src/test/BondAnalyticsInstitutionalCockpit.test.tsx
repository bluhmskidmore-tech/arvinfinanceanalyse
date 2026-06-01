import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import { BondAnalyticsInstitutionalCockpit } from "../features/bond-analytics/components/BondAnalyticsInstitutionalCockpit";

const COCKPIT_CSS = readFileSync(
  resolve(
    process.cwd(),
    "src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.module.css",
  ),
  "utf8",
);

function cssRuleBody(selector: string): string {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = new RegExp(`${escapedSelector}\\s*\\{([\\s\\S]*?)\\}`).exec(
    COCKPIT_CSS,
  );
  return match?.[1] ?? "";
}

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_cockpit",
    basis: "formal",
    result_kind: "bond_dashboard.dates",
    formal_use_allowed: true,
    source_version: "sv_cockpit",
    vendor_version: "vv_cockpit",
    rule_version: "rv_cockpit",
    cache_version: "cv_cockpit",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-19T00:00:00Z",
    ...overrides,
  };
}

describe("BondAnalyticsInstitutionalCockpit", () => {
  function renderCockpit(
    client: ReturnType<typeof createApiClient>,
    props: Partial<React.ComponentProps<typeof BondAnalyticsInstitutionalCockpit>> = {},
  ) {
    render(
      <QueryClientProvider
        client={
          new QueryClient({
            defaultOptions: {
              queries: { retry: false, refetchOnWindowFocus: false },
            },
          })
        }
      >
        <ApiClientProvider client={client}>
          <BondAnalyticsInstitutionalCockpit
            reportDate="2026-03-31"
            topAnomalies={[]}
            actionAttribution={null}
            {...props}
          />
        </ApiClientProvider>
      </QueryClientProvider>,
    );
  }

  it("falls back to the latest bond-dashboard report date when the page report date is unsupported", async () => {
    const base = createApiClient({ mode: "mock" });
    const getBondDashboardDates = vi.fn(async () => ({
      result_meta: createResultMeta({
        result_kind: "bond_dashboard.dates",
      }),
      result: {
        report_dates: ["2026-02-28"],
      },
    }));
    const getBondDashboardHeadlineKpis = vi.fn(async (reportDate: string) => {
      if (reportDate !== "2026-02-28") {
        throw new Error(`unsupported dashboard date ${reportDate}`);
      }
      return base.getBondDashboardHeadlineKpis(reportDate);
    });
    const getBondDashboardSpreadAnalysis = vi.fn(async (reportDate: string) => {
      if (reportDate !== "2026-02-28") {
        throw new Error(`unsupported spread date ${reportDate}`);
      }
      return base.getBondDashboardSpreadAnalysis(reportDate);
    });
    const getBondDashboardMaturityStructure = vi.fn(async (reportDate: string) => {
      if (reportDate !== "2026-02-28") {
        throw new Error(`unsupported maturity date ${reportDate}`);
      }
      return base.getBondDashboardMaturityStructure(reportDate);
    });
    const getBondAnalyticsTopHoldings = vi.fn(async (reportDate: string, limit?: number) => {
      if (reportDate !== "2026-02-28") {
        throw new Error(`unsupported holdings date ${reportDate}`);
      }
      return base.getBondAnalyticsTopHoldings(reportDate, limit);
    });
    const getBondAnalyticsPortfolioHeadlines = vi.fn(async (reportDate: string) => {
      if (reportDate !== "2026-02-28") {
        throw new Error(`unsupported portfolio-headlines date ${reportDate}`);
      }
      return base.getBondAnalyticsPortfolioHeadlines(reportDate);
    });

    const client = {
      ...base,
      getBondDashboardDates,
      getBondDashboardHeadlineKpis,
      getBondDashboardSpreadAnalysis,
      getBondDashboardMaturityStructure,
      getBondAnalyticsTopHoldings,
      getBondAnalyticsPortfolioHeadlines,
    };

    renderCockpit(client);

    expect(await screen.findByTestId("bond-analysis-phase3-cockpit")).toBeInTheDocument();

    await waitFor(() => {
      expect(getBondDashboardDates).toHaveBeenCalledTimes(1);
      expect(getBondDashboardHeadlineKpis).toHaveBeenCalledWith("2026-02-28");
      expect(getBondDashboardSpreadAnalysis).toHaveBeenCalledWith("2026-02-28");
      expect(getBondDashboardMaturityStructure).toHaveBeenCalledWith("2026-02-28");
      expect(getBondAnalyticsTopHoldings).toHaveBeenCalledWith("2026-02-28", 10);
      expect(getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledWith("2026-02-28");
    });

    expect(screen.queryByText("部分驾驶舱指标未就绪")).not.toBeInTheDocument();
    expect(screen.getAllByText("快照回退 2026-02-28").length).toBeGreaterThan(0);
  });

  it("shows controlled module fallback copy when portfolio headlines fail", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsPortfolioHeadlines: vi.fn(async () => {
        throw new Error("backend 503 for portfolio headlines");
      }),
    };

    renderCockpit(client);

    expect(await screen.findByTestId("bond-analysis-phase3-cockpit")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText("backend 503 for portfolio headlines")).not.toBeInTheDocument();
      expect(screen.queryByText("请求失败")).not.toBeInTheDocument();
      expect(screen.queryByText("不可用")).not.toBeInTheDocument();
      expect(
        screen.getByText("组合信用摘要暂未返回，资产结构稍后补齐。"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("组合信用摘要暂未返回，债券只数、集中度和 DV01 稍后补齐。"),
      ).toBeInTheDocument();
    });
  });

  it("shows controlled module fallback copy when top holdings fail", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsTopHoldings: vi.fn(async () => {
        throw new Error("backend 503 for top holdings");
      }),
    };

    renderCockpit(client);

    expect(await screen.findByTestId("bond-analysis-phase3-cockpit")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText("backend 503 for top holdings")).not.toBeInTheDocument();
      expect(screen.queryByText("请求失败")).not.toBeInTheDocument();
      expect(screen.queryByText("不可用")).not.toBeInTheDocument();
      expect(
        screen.getByText("前十大持仓暂未返回，首页先保留组合规模与浮盈快照。"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("持仓明细暂未返回，评级分布稍后补齐。"),
      ).toBeInTheDocument();
    });
  });

  it("opens portfolio headlines and top holdings drills from homepage cards", async () => {
    const user = userEvent.setup();
    const onOpenModuleDetail = vi.fn();

    renderCockpit(createApiClient({ mode: "mock" }), { onOpenModuleDetail });

    await user.click(
      await screen.findByTestId("bond-analysis-home-open-portfolio-headlines"),
    );
    expect(onOpenModuleDetail).toHaveBeenCalledWith("portfolio-headlines");

    await user.click(
      await screen.findByTestId("bond-analysis-home-open-top-holdings"),
    );
    expect(onOpenModuleDetail).toHaveBeenCalledWith("top-holdings");
  });

  it("renders the reference-style portfolio dashboard hierarchy on the first screen", async () => {
    renderCockpit(createApiClient({ mode: "mock" }));

    const dashboard = await screen.findByTestId("bond-analysis-reference-dashboard");

    expect(within(dashboard).getAllByText("组合总览").length).toBeGreaterThan(0);
    expect(within(dashboard).getAllByTestId("bond-analysis-kpi-ribbon")).toHaveLength(1);
    expect(within(dashboard).getByTestId("bond-analysis-kpi-ribbon")).toHaveTextContent("债券总市值");

    const distributionGrid = screen.getByTestId("bond-analysis-distribution-grid");
    expect(distributionGrid).toHaveTextContent("资产分布");
    expect(distributionGrid).toHaveTextContent("到期结构");
    expect(distributionGrid).toHaveTextContent("地区分布");

    expect(screen.getByTestId("bond-analysis-holdings-table")).toHaveTextContent("持仓明细");
    expect(screen.getByTestId("bond-analysis-risk-guardrails")).toHaveTextContent("风险指标");
  });

  it("keeps the reference topbar and current conclusion visible in the desktop first screen grid", () => {
    const dashboardRule = cssRuleBody(".referenceDashboard");
    const topbarRule = cssRuleBody(".referenceTopbar");
    const signalRule = cssRuleBody(".referenceSignalStrip");

    expect(dashboardRule).toContain('"topbar topbar"');
    expect(dashboardRule).toContain('"signal signal"');
    expect(topbarRule).not.toMatch(/display:\s*none/);
    expect(signalRule).not.toMatch(/display:\s*none/);
  });
});
