import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  __esModule: true,
  default: () => <div data-testid="bond-analytics-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient } from "../api/client";
import { createDeferredApiClient } from "../api/clientContext";
import type { BondTopHoldingItem, DV01RiskPayload, Numeric, ResultMeta } from "../api/contracts";
import { BondAnalyticsInstitutionalCockpit } from "../features/bond-analytics/components/BondAnalyticsInstitutionalCockpit";
import { formatRawAsNumeric } from "../utils/format";

const COCKPIT_CSS = readFileSync(
  resolve(
    process.cwd(),
    "src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.module.css",
  ),
  "utf8",
).replace(/\r\n/g, "\n");

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

const yuan = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
const ratio = (raw: number) =>
  formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false, precision: 2 });
const dv01 = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });
const bp = (raw: number) => formatRawAsNumeric({ raw, unit: "bp", sign_aware: true });
const pct = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });

function createDv01RiskPayload(
  accountingClass: string,
  durationRaw: number,
  dv01Raw: number,
): DV01RiskPayload {
  const zero = (unit: Numeric["unit"]) =>
    formatRawAsNumeric({ raw: 0, unit, sign_aware: false });
  return {
    report_date: "2026-03-31",
    accounting_class: accountingClass,
    total_face_value: yuan(1_000_000_000),
    total_market_value: yuan(1_020_000_000),
    face_weighted_modified_duration: ratio(durationRaw),
    total_dv01: dv01(dv01Raw),
    position_count: 12,
    shock_scenarios: [
      {
        scenario_name: "rate_up_1bp",
        shock_bp: bp(1),
        estimated_pnl: formatRawAsNumeric({ raw: -dv01Raw, unit: "yuan", sign_aware: true }),
      },
    ],
    tenor_buckets: [],
    top_bonds: [],
    top_issuers: [],
    warnings: [],
    computed_at: "2026-04-19T00:00:00Z",
    ...(dv01Raw === 0
      ? {
          total_face_value: zero("yuan"),
          total_market_value: zero("yuan"),
          face_weighted_modified_duration: zero("ratio"),
          total_dv01: zero("dv01"),
          position_count: 0,
          shock_scenarios: [],
        }
      : {}),
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
          <MemoryRouter>
            <BondAnalyticsInstitutionalCockpit
              reportDate="2026-03-31"
              topAnomalies={[]}
              actionAttribution={null}
              {...props}
            />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );
  }

  it("renders headline credit spread by Numeric.unit without raw-value thresholds", async () => {
    const base = createApiClient({ mode: "mock" });
    const getBondDashboardHeadlineKpis = vi.fn(async (reportDate: string) => {
      const response = await base.getBondDashboardHeadlineKpis(reportDate);
      return {
        ...response,
        result: {
          ...response.result,
          kpis: {
            ...response.result.kpis,
            credit_spread_median: formatRawAsNumeric({ raw: 0.42, unit: "bp", sign_aware: false }),
          },
        },
      };
    });
    const client = {
      ...base,
      getBondDashboardHeadlineKpis,
    };

    renderCockpit(client);

    const dashboard = await screen.findByTestId("bond-analysis-reference-dashboard");
    await waitFor(() => {
      expect(within(dashboard).getAllByText("0.4 bp").length).toBeGreaterThan(0);
    });
    expect(within(dashboard).queryByText("4200.0 bp")).not.toBeInTheDocument();
  });

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
      getBondDashboardMaturityStructure,
      getBondAnalyticsTopHoldings,
      getBondAnalyticsPortfolioHeadlines,
    };

    renderCockpit(client);

    expect(await screen.findByTestId("bond-analysis-phase3-cockpit")).toBeInTheDocument();

    await waitFor(() => {
      expect(getBondDashboardDates).toHaveBeenCalledTimes(1);
      expect(getBondDashboardHeadlineKpis).toHaveBeenCalledWith("2026-02-28");
      expect(getBondDashboardMaturityStructure).toHaveBeenCalledWith("2026-02-28");
      expect(getBondAnalyticsTopHoldings).toHaveBeenCalledWith("2026-02-28", 10);
      expect(getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledWith("2026-02-28");
    });

    expect(screen.queryByText("部分驾驶舱指标未就绪")).not.toBeInTheDocument();
    expect(screen.getAllByText("快照回退 2026-02-28").length).toBeGreaterThan(0);
  });

  it("fires business queries for reportDate without waiting for the dashboard-dates gate to resolve", async () => {
    const base = createApiClient({ mode: "mock" });
    let resolveDates: (value: Awaited<ReturnType<typeof base.getBondDashboardDates>>) => void = () => {};
    const datesPromise = new Promise<Awaited<ReturnType<typeof base.getBondDashboardDates>>>((resolve) => {
      resolveDates = resolve;
    });
    const getBondDashboardDates = vi.fn(() => datesPromise);
    const getBondDashboardHeadlineKpis = vi.fn((reportDate: string) =>
      base.getBondDashboardHeadlineKpis(reportDate),
    );
    const client = {
      ...base,
      getBondDashboardDates,
      getBondDashboardHeadlineKpis,
    };

    renderCockpit(client);

    await waitFor(() => {
      expect(getBondDashboardHeadlineKpis).toHaveBeenCalledWith("2026-03-31");
    });
    expect(getBondDashboardDates).toHaveBeenCalledTimes(1);

    resolveDates({
      result_meta: createResultMeta({ result_kind: "bond_dashboard.dates" }),
      result: { report_dates: ["2026-03-31"] },
    });

    await screen.findByTestId("bond-analysis-phase3-cockpit");
  });

  it("does not present a current business conclusion when dashboard date falls back", async () => {
    const base = createApiClient({ mode: "mock" });
    const client = {
      ...base,
      getBondDashboardDates: vi.fn(async () => ({
        result_meta: createResultMeta({
          result_kind: "bond_dashboard.dates",
        }),
        result: {
          report_dates: ["2026-03-31"],
        },
      })),
    };

    renderCockpit(client, { reportDate: "2026-04-30" });

    const conclusion = await screen.findByTestId("bond-analysis-cockpit-conclusion");

    await waitFor(() => {
      expect(conclusion).toHaveTextContent("2026-04-30");
      expect(conclusion).toHaveTextContent("2026-03-31");
      expect(conclusion).not.toHaveTextContent("当前结论");
      expect(conclusion).not.toHaveTextContent("久期敞口仍是首页第一观察位");
      expect(conclusion).not.toHaveTextContent("信用敞口偏重");
    });

    const dailyJudgment = screen.getByTestId("bond-analysis-daily-judgment");
    expect(dailyJudgment).toHaveTextContent("核心读面");
    expect(dailyJudgment).toHaveTextContent("数据边界");
    expect(dailyJudgment).toHaveTextContent("报告日状态");
    expect(dailyJudgment).toHaveTextContent("下钻入口");
    expect(dailyJudgment).toHaveTextContent("待读面");
    expect(dailyJudgment).toHaveTextContent("回退快照不形成当前结论");
    expect(dailyJudgment).not.toHaveTextContent("今日先把久期");
    expect(dailyJudgment).not.toHaveTextContent("信用仓位先按利差");
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

  it("renders null top holding evidence fields as explicit gaps", async () => {
    const base = createApiClient({ mode: "mock" });
    const nullNumeric = (unit: Numeric["unit"]) =>
      formatRawAsNumeric({ raw: null, unit, sign_aware: false });
    const holdingWithGaps: BondTopHoldingItem = {
      instrument_code: "NULL-001",
      instrument_name: "Null Evidence Bond",
      issuer_name: "Null Issuer",
      rating: "",
      asset_class: "rate",
      market_value: nullNumeric("yuan"),
      face_value: yuan(1_000_000),
      ytm: nullNumeric("pct"),
      modified_duration: nullNumeric("ratio"),
      weight: nullNumeric("ratio"),
    };
    const client = {
      ...base,
      getBondAnalyticsTopHoldings: vi.fn(async (reportDate: string, limit?: number) => {
        const response = await base.getBondAnalyticsTopHoldings(reportDate, limit);
        return {
          ...response,
          result: {
            ...response.result,
            items: [holdingWithGaps],
          },
        };
      }),
    };

    renderCockpit(client);

    const holdings = await screen.findByTestId("bond-analysis-holdings-table");
    const evidenceStrip = await screen.findByTestId("bond-analysis-holdings-evidence-strip");

    await waitFor(() => {
      expect(evidenceStrip).toHaveTextContent("评级缺口");
      expect(evidenceStrip).toHaveTextContent("1 条");
      expect(evidenceStrip).toHaveTextContent("数值缺口");
      expect(evidenceStrip).toHaveTextContent("4 项");
    });

    const rawGrid = within(holdings).getByTestId("bond-analysis-holdings-raw-grid");
    expect(within(rawGrid).getByTestId("bond-analysis-holdings-scroll-cue")).toBeInTheDocument();
    const row = within(rawGrid).getByText("NULL-001").parentElement?.parentElement;
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getAllByText("—")).toHaveLength(5);
    expect(row).not.toHaveTextContent("NaN");
    expect(row).not.toHaveTextContent("0.00%");
    expect(row).not.toHaveTextContent("0.00 亿");
    expect(within(holdings).queryByText("-", { exact: true })).not.toBeInTheDocument();
  });

  it("renders deferred trading-desk and yield-curve sections through the cockpit", async () => {
    renderCockpit(createDeferredApiClient({ mode: "mock" }));

    const evidenceStrip = await screen.findByTestId("bond-analysis-holdings-evidence-strip");
    const grid = await screen.findByTestId("bond-analysis-holdings-raw-grid");
    const yieldCurvePanel = await screen.findByTestId("bond-analysis-yield-curve-panel");

    await waitFor(() => {
      expect(evidenceStrip).toHaveTextContent("1 \u6761");
    });
    expect(
      within(yieldCurvePanel).getByTestId("bond-analysis-yield-curve-empty"),
    ).toBeInTheDocument();
    expect(yieldCurvePanel).not.toHaveTextContent(/\u52a0\u8f7d\u5931\u8d25|\u4e0d\u53ef\u7528/);

    const link = await within(grid).findByTestId("bond-trading-desk-link-230210.IB");
    expect(link).toHaveAttribute(
      "href",
      expect.stringContaining("/bond-trading-desk?bond_code=230210.IB"),
    );
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

  it("renders the decision rail inside the hero aside when decision rail props are supplied", async () => {
    const onOpenModuleDetail = vi.fn();

    renderCockpit(createApiClient({ mode: "mock" }), {
      onOpenModuleDetail,
      decisionRail: {
        activeModuleContext: {
          key: "action-attribution",
          label: "动作归因",
          description: "读取治理后的动作归因结果。",
          statusLabel: "eligible",
          statusReason: "动作归因已返回。",
        },
        activeReadinessItem: {
          key: "action-attribution",
          label: "动作归因",
          description: "说明",
          detailHint: "提示",
          statusLabel: "eligible",
          statusReason: "动作归因已返回。",
          promotionDestination: "headline",
          warnings: [],
        },
        watchlistItems: [
          {
            key: "return-decomposition",
            label: "收益拆解",
            description: "说明",
            detailHint: "提示",
            statusLabel: "placeholder-blocked",
            statusReason: "待返回",
            promotionDestination: "readiness-only",
            warnings: [],
          },
        ],
      },
    });

    const aside = await screen.findByTestId("bond-analysis-hero-aside");
    expect(within(aside).getByTestId("bond-analysis-decision-rail")).toBeInTheDocument();
    expect(within(aside).getByTestId("bond-analysis-decision-trust")).toHaveTextContent(
      "读取治理后的动作归因结果。",
    );
  });

  it("renders the reference-style bond analysis workstation hierarchy on the first screen", async () => {
    renderCockpit(createApiClient({ mode: "mock" }));

    const dashboard = await screen.findByTestId("bond-analysis-reference-dashboard");
    const marketTicker = within(dashboard).getByTestId("bond-analysis-market-ticker");
    const topbar = within(dashboard).getByTestId("bond-analysis-reference-topbar");
    const dailyJudgment = within(topbar).getByTestId("bond-analysis-daily-judgment");
    const heroConclusion = within(topbar).getByTestId("bond-analysis-cockpit-conclusion");
    expect(
      topbar.compareDocumentPosition(marketTicker) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    expect(within(topbar).getByText("固定收益交易台")).toBeInTheDocument();
    await waitFor(() => {
      expect(heroConclusion).toHaveTextContent("久期、信用利差与信用占比读面已返回");
      expect(topbar).toHaveTextContent("报告日");
      expect(topbar).toHaveTextContent("首屏 KPI");
      expect(topbar).not.toHaveTextContent("数据更新时间");
    });
    expect(within(dashboard).getByTestId("bond-analysis-market-ticker")).toHaveTextContent("10年国债");
    expect(within(dashboard).getByTestId("bond-analysis-market-ticker")).toHaveTextContent("DR007");
    await waitFor(() => {
      expect(dailyJudgment).toHaveTextContent("固定收益读面");
      expect(dailyJudgment).toHaveTextContent("证据展开");
      expect(dailyJudgment).toHaveTextContent("首屏读面拆解");
      expect(dailyJudgment).not.toHaveTextContent("久期、信用利差与信用占比读面已返回。");
      expect(dailyJudgment).toHaveTextContent("久期 3.45 年");
      expect(dailyJudgment).toHaveTextContent("信用利差 85.0 bp");
      expect(dailyJudgment).toHaveTextContent("信用占比 42.0%");
      expect(dailyJudgment).toHaveTextContent("数据边界");
      expect(dailyJudgment).toHaveTextContent("正式曲线待返回");
      expect(dailyJudgment).toHaveTextContent("报告日状态");
      expect(dailyJudgment).toHaveTextContent("报告日匹配");
      expect(dailyJudgment).toHaveTextContent("下钻入口");
      expect(dailyJudgment).toHaveTextContent("正式下钻待返回");
    });
    expect(dailyJudgment).not.toHaveTextContent("核心读面 · 核心读面");
    expect(dashboard.textContent?.match(/久期、信用利差与信用占比读面已返回。/g) ?? []).toHaveLength(1);
    expect(dailyJudgment).not.toHaveTextContent("今日先把久期放在交易台第一盯盘位");
    expect(dailyJudgment).not.toHaveTextContent("信用仓位先按利差与集中度开盘复核");
    expect(dailyJudgment).not.toHaveTextContent("看期限/KRD");
    expect(dailyJudgment).not.toHaveTextContent("复核 DV01");

    expect(within(dashboard).getAllByTestId("bond-analysis-kpi-ribbon")).toHaveLength(1);
    const kpiRibbon = within(dashboard).getByTestId("bond-analysis-kpi-ribbon");
    expect(kpiRibbon).toHaveTextContent("久期");
    expect(kpiRibbon).toHaveTextContent("组合到期收益率");
    expect(kpiRibbon).toHaveTextContent("信用利差");
    await waitFor(() => {
      expect(kpiRibbon).toHaveTextContent("85.0 bp");
    });
    expect(within(kpiRibbon).getByText("久期").closest('[data-priority="primary"]')).not.toBeNull();
    expect(kpiRibbon).toHaveTextContent("DV01");
    expect(kpiRibbon).toHaveTextContent("Carry+Roll");
    expect(within(kpiRibbon).getByText("Carry+Roll").closest('[data-state="gap"]')).not.toBeNull();
    expect(within(kpiRibbon).getByText("Carry+Roll").closest('[data-priority="gap"]')).not.toBeNull();
    expect(kpiRibbon).toHaveTextContent("缺口");
    expect(kpiRibbon).toHaveTextContent("接口未返回");
    expect(kpiRibbon).toHaveTextContent("待读面");
    expect(within(dashboard).getByTestId("bond-analysis-yield-curve-panel")).toHaveTextContent("曲线 / KRD 观察");
    expect(within(dashboard).getByTestId("bond-analysis-evidence-boundary-panel")).toHaveTextContent("证据边界");
    expect(within(dashboard).getByTestId("bond-analysis-judgment-matrix")).toHaveTextContent("利率证据");
    expect(within(dashboard).getByTestId("bond-analysis-judgment-matrix")).toHaveTextContent("曲线证据");
    expect(within(dashboard).getByTestId("bond-analysis-judgment-matrix")).toHaveTextContent("信用证据");
    expect(within(dashboard).getByTestId("bond-analysis-judgment-matrix")).toHaveTextContent("资金证据");
    expect(within(dashboard).getByTestId("bond-analysis-judgment-matrix")).toHaveTextContent("只展示后端返回事实");
    expect(within(dashboard).getByTestId("bond-analysis-return-attribution-panel")).toHaveTextContent("收益归因");
    expect(within(dashboard).getByTestId("bond-analysis-return-attribution-panel")).toHaveTextContent("DV01 变动证据");
    expect(within(dashboard).getByTestId("bond-analysis-return-attribution-panel")).toHaveTextContent("不在前端补算归因");
    expect(within(dashboard).getByTestId("bond-analysis-currency-basis-banner")).toHaveTextContent(
      "金额指标按人民币/CNY口径展示，外币债券市值、摊余成本、应计利息等已折算为人民币。",
    );

    const distributionGrid = screen.getByTestId("bond-analysis-distribution-grid");
    expect(distributionGrid).toHaveTextContent("结构证据");
    expect(distributionGrid).toHaveTextContent("风险切片");
    expect(distributionGrid).toHaveTextContent("集中度证据");
    expect(distributionGrid).toHaveTextContent("只列后端返回风险字段");

    expect(screen.getByTestId("bond-analysis-holdings-table")).toHaveTextContent("持仓证据明细");
    expect(screen.getByTestId("bond-analysis-holdings-evidence-strip")).toHaveTextContent("返回持仓");
    expect(screen.getByTestId("bond-analysis-holdings-evidence-strip")).toHaveTextContent("评级缺口");
    expect(screen.getByTestId("bond-analysis-holdings-evidence-strip")).toHaveTextContent("数值缺口");
    expect(screen.getByTestId("bond-analysis-risk-slice-stack")).toHaveTextContent("风险切片");
    expect(screen.getByTestId("bond-analysis-risk-guardrails")).toHaveTextContent("风险读面");
    expect(screen.getByTestId("bond-analysis-return-trend-boundary")).toHaveTextContent("不绘制趋势占位");
  });

  it("keeps the desktop cockpit and matrix on factual readout copy only", async () => {
    renderCockpit(createApiClient({ mode: "mock" }));

    const dashboard = await screen.findByTestId("bond-analysis-reference-dashboard");
    const topbar = within(dashboard).getByTestId("bond-analysis-reference-topbar");
    const dailyJudgment = within(topbar).getByTestId("bond-analysis-daily-judgment");
    const heroConclusion = within(topbar).getByTestId("bond-analysis-cockpit-conclusion");
    const matrix = within(dashboard).getByTestId("bond-analysis-judgment-matrix");

    await waitFor(() => {
      expect(heroConclusion).toHaveTextContent("久期、信用利差与信用占比读面已返回");
      expect(dailyJudgment).toHaveTextContent("首屏读面拆解");
      expect(matrix).toHaveTextContent("正式曲线待返回");
    });

    expect(dailyJudgment).toHaveTextContent("证据展开");
    expect(dailyJudgment).toHaveTextContent("久期");
    expect(dailyJudgment).toHaveTextContent("信用利差");
    expect(dailyJudgment).toHaveTextContent("信用占比");
    expect(matrix).toHaveTextContent("已返回");
    expect(matrix).toHaveTextContent("DV01已返回");
    expect(matrix).toHaveTextContent("返回字段：组合 DV01");
    expect(matrix).toHaveTextContent("缺失项：正式曲线 / 正式 KRD");
    expect(matrix).toHaveTextContent("只展示返回事实");
    expect(matrix).not.toHaveTextContent("久期偏高");
    expect(matrix).not.toHaveTextContent("久期中性");
    expect(matrix).not.toHaveTextContent("信用占比偏重");
    expect(matrix).not.toHaveTextContent("关注 DV01");
    expect(dailyJudgment).not.toHaveTextContent("今日先把久期放在交易台第一盯盘位");
    expect(dailyJudgment).not.toHaveTextContent("信用仓位先按利差与集中度开盘复核");
    expect(dailyJudgment).not.toHaveTextContent("主风险");
    expect(dailyJudgment).not.toHaveTextContent("优先复核");
  });

  it("keeps the cockpit conclusion partial when only some core readouts return", async () => {
    const base = createApiClient({ mode: "mock" });
    const nullNumeric = (unit: Numeric["unit"]) =>
      formatRawAsNumeric({ raw: null, unit, sign_aware: false });
    const client = {
      ...base,
      getBondDashboardHeadlineKpis: vi.fn(async (reportDate: string) => {
        const response = await base.getBondDashboardHeadlineKpis(reportDate);
        return {
          ...response,
          result: {
            ...response.result,
            kpis: {
              ...response.result.kpis,
              weighted_duration: ratio(3.45),
              credit_spread_median: nullNumeric("bp"),
            },
          },
        };
      }),
      getBondDashboardRiskIndicators: vi.fn(async (reportDate: string) => {
        const response = await base.getBondDashboardRiskIndicators(reportDate);
        return {
          ...response,
          result: {
            ...response.result,
            credit_ratio: nullNumeric("ratio"),
          },
        };
      }),
      getBondAnalyticsPortfolioHeadlines: vi.fn(async (reportDate: string) => {
        const response = await base.getBondAnalyticsPortfolioHeadlines(reportDate);
        return {
          ...response,
          result: {
            ...response.result,
            credit_weight: nullNumeric("ratio"),
          },
        };
      }),
      getBondDashboardMaturityStructure: vi.fn(async (reportDate: string) => {
        const response = await base.getBondDashboardMaturityStructure(reportDate);
        return {
          ...response,
          result: {
            ...response.result,
            items: [
              {
                ...response.result.items[0],
                maturity_bucket: "空值期限桶",
                total_market_value: nullNumeric("yuan"),
              },
              ...response.result.items,
            ],
          },
        };
      }),
    };

    renderCockpit(client);

    const dashboard = await screen.findByTestId("bond-analysis-reference-dashboard");
    const topbar = within(dashboard).getByTestId("bond-analysis-reference-topbar");
    const dailyJudgment = within(topbar).getByTestId("bond-analysis-daily-judgment");
    const heroConclusion = within(topbar).getByTestId("bond-analysis-cockpit-conclusion");

    await waitFor(() => {
      expect(heroConclusion).toHaveTextContent("部分核心债券读面已返回");
      expect(heroConclusion).toHaveTextContent("待返回 信用利差 / 信用占比");
      expect(dailyJudgment).toHaveTextContent("固定收益读面");
      expect(dailyJudgment).toHaveTextContent("首屏读面拆解");
      expect(dailyJudgment).toHaveTextContent("久期 3.45 年");
      expect(dailyJudgment).toHaveTextContent("只展示后端返回事实");
    });
    expect(dailyJudgment).not.toHaveTextContent("久期、信用利差与信用占比读面已返回");
    expect(screen.getByTestId("bond-analysis-reference-dashboard")).not.toHaveTextContent("NaN 年");
    await waitFor(() => {
      expect(screen.getByTestId("bond-analysis-kpi-ribbon")).toHaveTextContent("最重期限桶 1-3年");
    });
    expect(screen.getByTestId("bond-analysis-kpi-ribbon")).not.toHaveTextContent("最重期限桶 空值期限桶");
  });

  it("keeps formal curve pending when curve objects return only null points", async () => {
    const base = createApiClient({ mode: "mock" });
    const nullNumeric = (unit: Numeric["unit"], display = "—") =>
      ({ raw: null, display, unit, sign_aware: false }) as Numeric;
    const getBondAnalyticsYieldCurveTermStructure = vi.fn(async (reportDate: string) => ({
      result_meta: createResultMeta({
        result_kind: "bond_analytics.yield_curve_term_structure",
      }),
      result: {
        report_date: reportDate,
        curves: [
          {
            curve_type: "treasury",
            trade_date_requested: reportDate,
            trade_date_resolved: reportDate,
            source_version: "curve_sv_null",
            rule_version: "curve_rv_1",
            vendor_name: "choice",
            vendor_version: "choice_v1",
            points: [
              {
                tenor: "1Y",
                yield_pct: nullNumeric("pct"),
                delta_bp_prev: nullNumeric("bp"),
              },
              {
                tenor: "10Y",
                yield_pct: nullNumeric("pct"),
                delta_bp_prev: nullNumeric("bp"),
              },
            ],
          },
        ],
        warnings: [],
        computed_at: "2026-04-19T00:00:00Z",
      },
    }));
    const client = {
      ...base,
      getBondAnalyticsYieldCurveTermStructure,
    };

    renderCockpit(client);

    const panel = await screen.findByTestId("bond-analysis-yield-curve-panel");
    const matrix = await screen.findByTestId("bond-analysis-judgment-matrix");

    await waitFor(() => {
      expect(getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalled();
      expect(within(panel).getByTestId("bond-analysis-yield-curve-empty")).toHaveTextContent(
        "正式曲线 / KRD 读面待返回",
      );
    });
    expect(panel).toHaveTextContent("正式曲线 / KRD 读面待返回");
    expect(matrix).toHaveTextContent("正式曲线待返回");
    expect(matrix).toHaveTextContent("缺失项：正式曲线 / 正式 KRD");
    expect(matrix).not.toHaveTextContent("正式曲线可读");
  });

  it("keeps DV01 pending when all DV01 readout sources are null", async () => {
    const base = createApiClient({ mode: "mock" });
    const nullDv01 = formatRawAsNumeric({ raw: null, unit: "dv01", sign_aware: false });
    const client = {
      ...base,
      getBondDashboardHeadlineKpis: vi.fn(async (reportDate: string) => {
        const response = await base.getBondDashboardHeadlineKpis(reportDate);
        return {
          ...response,
          result: {
            ...response.result,
            kpis: {
              ...response.result.kpis,
              total_dv01: nullDv01,
            },
            prev_kpis: {
              ...(response.result.prev_kpis ?? response.result.kpis),
              total_dv01: nullDv01,
            },
          },
        };
      }),
      getBondDashboardRiskIndicators: vi.fn(async (reportDate: string) => {
        const response = await base.getBondDashboardRiskIndicators(reportDate);
        return {
          ...response,
          result: {
            ...response.result,
            total_dv01: nullDv01,
          },
        };
      }),
      getBondAnalyticsPortfolioHeadlines: vi.fn(async (reportDate: string) => {
        const response = await base.getBondAnalyticsPortfolioHeadlines(reportDate);
        return {
          ...response,
          result: {
            ...response.result,
            total_dv01: nullDv01,
          },
        };
      }),
    };

    renderCockpit(client);

    const matrix = await screen.findByTestId("bond-analysis-judgment-matrix");
    const kpiRibbon = await screen.findByTestId("bond-analysis-kpi-ribbon");
    const attribution = await screen.findByTestId("bond-analysis-return-attribution-panel");

    await waitFor(() => {
      expect(matrix).toHaveTextContent("DV01待返回");
      expect(matrix).toHaveTextContent("缺失项：DV01");
    });
    expect(kpiRibbon).toHaveTextContent("DV01");
    expect(kpiRibbon).toHaveTextContent("待读面");
    expect(kpiRibbon).not.toHaveTextContent("DV01已返回");
    expect(matrix).not.toHaveTextContent("DV01已返回");
    expect(attribution).toHaveTextContent("DV01 —");
    expect(attribution).toHaveTextContent("DV01变动");
    expect(attribution).toHaveTextContent("—");
  });

  it("does not re-scale credit spread when the headline readout is already in bp", async () => {
    const base = createApiClient({ mode: "mock" });
    const client = {
      ...base,
      getBondDashboardHeadlineKpis: vi.fn(async (reportDate: string) => {
        const response = await base.getBondDashboardHeadlineKpis(reportDate);
        return {
          ...response,
          result: {
            ...response.result,
            kpis: {
              ...response.result.kpis,
              credit_spread_median: bp(85),
            },
          },
        };
      }),
    };

    renderCockpit(client);

    const kpiRibbon = await screen.findByTestId("bond-analysis-kpi-ribbon");

    await waitFor(() => {
      expect(kpiRibbon).toHaveTextContent("85.0 bp");
    });
    expect(kpiRibbon).not.toHaveTextContent("850000.0 bp");
  });

  it("keeps the market ticker in a pending readout state when macro latest is empty", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getChoiceMacroLatest: vi.fn(async () => ({
        result_meta: createResultMeta({ result_kind: "choice_macro.latest" }),
        result: {
          read_target: "duckdb" as const,
          series: [],
        },
      })),
    };

    renderCockpit(client);

    const marketTicker = await screen.findByTestId("bond-analysis-market-ticker");

    await waitFor(() => {
      expect(marketTicker).toHaveTextContent("待读取");
    });
    expect(marketTicker).not.toHaveTextContent("0.00");
  });

  it("puts accounting-class duration and DV01 directly on the bond-analysis homepage", async () => {
    const dv01ByClass = {
      AC: createDv01RiskPayload("AC", 2.1, 123_000),
      OCI: createDv01RiskPayload("OCI", 3.43, 3_546_830),
      TPL: createDv01RiskPayload("TPL", 0.65, 42_000),
      all: createDv01RiskPayload("all", 2.88, 3_711_830),
    };
    const getBondAnalyticsDv01Risk = vi.fn(async (_reportDate: string, options?: { accountingClass?: string }) => ({
      result_meta: createResultMeta({ result_kind: "bond_analytics.dv01_risk" }),
      result: dv01ByClass[(options?.accountingClass ?? "OCI") as keyof typeof dv01ByClass],
    }));
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsDv01Risk,
    };

    renderCockpit(client);

    const summary = await screen.findByTestId("bond-analysis-accounting-dv01-summary");

    await waitFor(() => {
      expect(getBondAnalyticsDv01Risk).toHaveBeenCalledWith(expect.any(String), {
        accountingClass: "AC",
        topN: 1,
        shockBps: "1",
      });
      expect(getBondAnalyticsDv01Risk).toHaveBeenCalledWith(expect.any(String), {
        accountingClass: "OCI",
        topN: 1,
        shockBps: "1",
      });
      expect(getBondAnalyticsDv01Risk).toHaveBeenCalledWith(expect.any(String), {
        accountingClass: "TPL",
        topN: 1,
        shockBps: "1",
      });
      expect(getBondAnalyticsDv01Risk).toHaveBeenCalledWith(expect.any(String), {
        accountingClass: "all",
        topN: 1,
        shockBps: "1",
      });
      expect(summary).toHaveTextContent("2.10 年");
    });
    expect(summary).toHaveTextContent("会计分类 DV01");
    expect(summary).toHaveTextContent("AC");
    expect(summary).toHaveTextContent("2.10 年");
    expect(summary).toHaveTextContent("12 万");
    expect(summary).toHaveTextContent("OCI");
    expect(summary).toHaveTextContent("3.43 年");
    expect(summary).toHaveTextContent("355 万");
    expect(summary).toHaveTextContent("TPL");
    expect(summary).toHaveTextContent("全部");
    expect(summary).toHaveTextContent("371 万");
    expect(summary).not.toHaveTextContent("3,711,830");
  });

  it("does not promote missing accounting-class DV01 as the lead DV01 row", async () => {
    const nullDv01 = formatRawAsNumeric({ raw: null, unit: "dv01", sign_aware: false });
    const dv01ByClass = {
      AC: {
        ...createDv01RiskPayload("AC", 2.1, 123_000),
        total_dv01: nullDv01,
      },
      OCI: {
        ...createDv01RiskPayload("OCI", 3.43, 3_546_830),
        total_dv01: nullDv01,
      },
      TPL: {
        ...createDv01RiskPayload("TPL", 0.65, 42_000),
        total_dv01: nullDv01,
      },
      all: {
        ...createDv01RiskPayload("all", 2.88, 3_711_830),
        total_dv01: nullDv01,
      },
    };
    const getBondAnalyticsDv01Risk = vi.fn(async (_reportDate: string, options?: { accountingClass?: string }) => ({
      result_meta: createResultMeta({ result_kind: "bond_analytics.dv01_risk" }),
      result: dv01ByClass[(options?.accountingClass ?? "OCI") as keyof typeof dv01ByClass],
    }));
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsDv01Risk,
    };

    renderCockpit(client);

    const mobileReadout = await screen.findByTestId("bond-analysis-accounting-dv01-mobile-readout");

    await waitFor(() => {
      expect(getBondAnalyticsDv01Risk).toHaveBeenCalledTimes(4);
    });

    expect(mobileReadout).not.toHaveTextContent(/\bAC\b/);
    expect(mobileReadout).not.toHaveTextContent(/\bOCI\b/);
    expect(mobileReadout).not.toHaveTextContent(/\bTPL\b/);
    expect(mobileReadout).not.toHaveTextContent("2.10");
    expect(mobileReadout).not.toHaveTextContent("3.43");
  });

  it("renders formal yield-curve tenors on the desktop first-screen curve panel", async () => {
    const base = createApiClient({ mode: "mock" });
    const getBondAnalyticsYieldCurveTermStructure = vi.fn(async (reportDate: string) => ({
      result_meta: createResultMeta({
        result_kind: "bond_analytics.yield_curve_term_structure",
      }),
      result: {
        report_date: reportDate,
        curves: [
          {
            curve_type: "treasury",
            trade_date_requested: reportDate,
            trade_date_resolved: reportDate,
            source_version: "curve_sv_20260331",
            rule_version: "curve_rv_1",
            vendor_name: "choice",
            vendor_version: "choice_v1",
            points: [
              {
                tenor: "1Y",
                yield_pct: pct(0.0168),
                delta_bp_prev: bp(-1.2),
              },
              {
                tenor: "10Y",
                yield_pct: pct(0.0231),
                delta_bp_prev: bp(2.4),
              },
            ],
          },
        ],
        warnings: [],
        computed_at: "2026-04-19T00:00:00Z",
      },
    }));
    const client = {
      ...base,
      getBondAnalyticsYieldCurveTermStructure,
    };

    renderCockpit(client);

    const panel = await screen.findByTestId("bond-analysis-yield-curve-panel");

    await waitFor(() => {
      expect(getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalledWith("2026-03-31", {
        curveTypes: "treasury,cdb",
      });
      expect(within(panel).getByTestId("bond-analysis-yield-curve-readout")).toBeInTheDocument();
    });
    expect(within(panel).getByTestId("bond-analysis-yield-curve-readout")).toBeInTheDocument();
    expect(panel).toHaveTextContent("国债");
    expect(panel).toHaveTextContent("1Y");
    expect(panel).toHaveTextContent("10Y");
    expect(panel).toHaveTextContent("1.68%");
    expect(panel).toHaveTextContent("+2.4 bp");
    expect(panel).toHaveTextContent("最大日变动");
    expect(panel).toHaveTextContent("10Y +2.4 bp");
    expect(within(panel).getByTestId("bond-analysis-curve-tenor-matrix")).toHaveTextContent(
      "收益率",
    );
    expect(within(panel).getByTestId("bond-analysis-curve-tenor-matrix")).toHaveTextContent(
      "日变动",
    );
    expect(panel).toHaveTextContent("全部返回点扫描");
    expect(panel).toHaveTextContent("正式 KRD");
    expect(panel).toHaveTextContent("待返回");
    expect(panel).toHaveTextContent("期限桶校验 / 暴露观察");
    expect(screen.getByTestId("bond-analysis-judgment-matrix")).toHaveTextContent("正式曲线可读");
  });

  it("picks the largest curve move from all returned points, not only the displayed tenor strip", async () => {
    const base = createApiClient({ mode: "mock" });
    const getBondAnalyticsYieldCurveTermStructure = vi.fn(async (reportDate: string) => ({
      result_meta: createResultMeta({
        result_kind: "bond_analytics.yield_curve_term_structure",
      }),
      result: {
        report_date: reportDate,
        curves: [
          {
            curve_type: "treasury",
            trade_date_requested: reportDate,
            trade_date_resolved: reportDate,
            source_version: "curve_sv_20260331",
            rule_version: "curve_rv_1",
            vendor_name: "choice",
            vendor_version: "choice_v1",
            points: [
              { tenor: "1Y", yield_pct: pct(0.0168), delta_bp_prev: bp(0.4) },
              { tenor: "2Y", yield_pct: pct(0.0174), delta_bp_prev: bp(0.6) },
              { tenor: "3Y", yield_pct: pct(0.0181), delta_bp_prev: bp(0.8) },
              { tenor: "4Y", yield_pct: pct(0.0188), delta_bp_prev: bp(1.0) },
              { tenor: "5Y", yield_pct: pct(0.0193), delta_bp_prev: bp(1.2) },
              { tenor: "6Y", yield_pct: pct(0.0199), delta_bp_prev: bp(1.4) },
              { tenor: "7Y", yield_pct: pct(0.0205), delta_bp_prev: bp(1.6) },
              { tenor: "8Y", yield_pct: pct(0.0211), delta_bp_prev: bp(1.8) },
              { tenor: "30Y", yield_pct: pct(0.0275), delta_bp_prev: bp(-9.6) },
            ],
          },
        ],
        warnings: [],
        computed_at: "2026-04-19T00:00:00Z",
      },
    }));
    const client = {
      ...base,
      getBondAnalyticsYieldCurveTermStructure,
    };

    renderCockpit(client);

    const panel = await screen.findByTestId("bond-analysis-yield-curve-panel");

    await waitFor(() => {
      expect(panel).toHaveTextContent("30Y -9.6 bp");
    });
    expect(panel).toHaveTextContent("最大日变动");
    expect(panel).toHaveTextContent("正式 KRD");
    expect(panel).toHaveTextContent("待返回");
  });

  it("renders returned treasury and CDB curves in one desktop comparison matrix", async () => {
    const base = createApiClient({ mode: "mock" });
    const getBondAnalyticsYieldCurveTermStructure = vi.fn(async (reportDate: string) => ({
      result_meta: createResultMeta({
        result_kind: "bond_analytics.yield_curve_term_structure",
      }),
      result: {
        report_date: reportDate,
        curves: [
          {
            curve_type: "treasury",
            trade_date_requested: reportDate,
            trade_date_resolved: reportDate,
            source_version: "curve_sv_treasury",
            rule_version: "curve_rv_1",
            vendor_name: "choice",
            vendor_version: "choice_v1",
            points: [
              { tenor: "1Y", yield_pct: pct(0.0168), delta_bp_prev: bp(-1.2) },
              { tenor: "10Y", yield_pct: pct(0.0231), delta_bp_prev: bp(2.4) },
            ],
          },
          {
            curve_type: "cdb",
            trade_date_requested: reportDate,
            trade_date_resolved: reportDate,
            source_version: "curve_sv_cdb",
            rule_version: "curve_rv_1",
            vendor_name: "choice",
            vendor_version: "choice_v1",
            points: [
              { tenor: "1Y", yield_pct: pct(0.0181), delta_bp_prev: bp(-0.8) },
              { tenor: "10Y", yield_pct: pct(0.0262), delta_bp_prev: bp(3.1) },
            ],
          },
        ],
        warnings: [],
        computed_at: "2026-04-19T00:00:00Z",
      },
    }));
    const client = {
      ...base,
      getBondAnalyticsYieldCurveTermStructure,
    };

    renderCockpit(client);

    const panel = await screen.findByTestId("bond-analysis-yield-curve-panel");
    const matrices = await within(panel).findAllByTestId("bond-analysis-curve-tenor-matrix");
    const matrix = matrices[0];

    expect(matrices).toHaveLength(1);
    expect(matrix).toHaveTextContent("国债 收益率");
    expect(matrix).toHaveTextContent("国债 日变动");
    expect(matrix).toHaveTextContent("国开 收益率");
    expect(matrix).toHaveTextContent("国开 日变动");
    expect(matrix).toHaveTextContent("2.62%");
    expect(matrix).toHaveTextContent("+3.1 bp");
    expect(panel).toHaveTextContent("返回曲线：2 条");
    expect(panel).toHaveTextContent("最大日变动");
  });

  it("keeps the homepage curve panel explicit when formal curve points are absent", async () => {
    renderCockpit(createApiClient({ mode: "mock" }));

    const panel = await screen.findByTestId("bond-analysis-yield-curve-panel");
    const empty = within(panel).getByTestId("bond-analysis-yield-curve-empty");

    expect(empty).toHaveTextContent(
      "正式曲线 / KRD 读面待返回",
    );
    expect(empty).toHaveTextContent("正式曲线期限点");
    expect(empty).toHaveTextContent("正式 KRD");
    expect(empty).toHaveTextContent("前端处理");
    expect(empty).toHaveTextContent("不补造");
    expect(panel).toHaveTextContent("期限桶占位 / 不冒充 KRD");
    expect(panel).toHaveTextContent("不把 maturity bucket 说成 KRD");
    expect(screen.getByTestId("bond-analysis-judgment-matrix")).toHaveTextContent("正式曲线待返回");
  });

  it("keeps the reference hero and current conclusion ahead of the market ticker in the desktop first screen grid", () => {
    const dashboardRule = cssRuleBody(".referenceDashboard");
    const heroRule = cssRuleBody(".heroSection");
    const heroMainRule = cssRuleBody(".heroMain");
    const heroHeadlineRule = cssRuleBody(".heroHeadline");
    const heroDetailRule = cssRuleBody(".heroDetail");
    const heroMetricsRule = cssRuleBody(".heroMetrics");
    const heroMetricValueRule = cssRuleBody(".heroMetricValue");
    const heroGovernanceRule = cssRuleBody(".heroGovernance");
    const heroVerdictRowRule = cssRuleBody(".heroVerdictRow");
    const heroVerdictStrongRule = cssRuleBody(".heroVerdictField strong");
    const heroVerdictSmallRule = cssRuleBody(".heroVerdictField small");
    const heroTitleRule = cssRuleBody(".heroTitle");
    const marketRule = cssRuleBody(".referenceMarketTicker");
    const kpiRailRule = cssRuleBody(".holdingsKpiRail");
    const kpiGridRule = cssRuleBody(".holdingsKpiGrid");
    const kpiTileRule = cssRuleBody(".referenceKpiTile");
    const kpiPrimaryTileRule = cssRuleBody('.referenceKpiTile[data-priority="primary"]');
    const kpiPrimaryValueRule = cssRuleBody('.referenceKpiTile[data-priority="primary"] .referenceKpiValue');
    const kpiGapTileRule = cssRuleBody('.referenceKpiTile[data-state="gap"]');
    const kpiValueRule = cssRuleBody(".referenceKpiValue");
    const responsiveBlock = /@media \(max-width: 1180px\)\s*\{[\s\S]*?\.referenceDashboard\s*\{([\s\S]*?)\n  \}/.exec(
      COCKPIT_CSS,
    )?.[1] ?? "";

    expect(dashboardRule).toContain('"hero hero"');
    expect(dashboardRule).toContain('"market market"');
    expect(dashboardRule.indexOf('"market market"')).toBeGreaterThan(dashboardRule.indexOf('"hero hero"'));
    expect(responsiveBlock).toContain('"hero"');
    expect(responsiveBlock).toContain('"market"');
    expect(responsiveBlock.indexOf('"market"')).toBeGreaterThan(responsiveBlock.indexOf('"hero"'));
    expect(heroRule).not.toContain("border-left:");
    expect(heroRule).toContain("background: var(--moss-color-card-bg)");
    expect(heroRule).toContain("padding: 14px 18px");
    expect(heroRule).toContain('grid-template-areas:');
    expect(heroRule).toContain('"identity identity"');
    expect(heroRule).toContain('"main governance"');
    expect(heroRule).not.toContain("linear-gradient");
    expect(heroRule).not.toMatch(/box-shadow:/);
    const heroAsideRule = cssRuleBody(".heroAside");
    expect(heroAsideRule).toContain("grid-area: governance");
    expect(heroGovernanceRule).toContain("border: 1px solid var(--moss-color-neutral-200)");
    expect(heroMainRule).toContain("grid-template-columns: minmax(360px, 1fr) minmax(520px, 0.62fr)");
    expect(heroHeadlineRule).toContain("font-size: 26px");
    expect(heroHeadlineRule).toContain("-webkit-line-clamp: 2");
    expect(heroDetailRule).toContain("font-size: 12px");
    expect(heroMetricsRule).toContain("grid-template-columns: repeat(4, minmax(84px, 1fr))");
    expect(heroMetricsRule).toContain("border-left: 1px solid var(--moss-color-neutral-100)");
    expect(heroMetricValueRule).toContain("font-size: 25px");
    expect(heroMetricValueRule).toContain("white-space: nowrap");
    expect(heroGovernanceRule).not.toContain("border-left:");
    expect(heroVerdictRowRule).toContain("border-top: 1px solid var(--moss-color-neutral-100)");
    expect(heroVerdictStrongRule).toContain("white-space: normal");
    expect(heroVerdictStrongRule).toContain("overflow-wrap: anywhere");
    expect(heroVerdictStrongRule).toContain("-webkit-line-clamp: 2");
    expect(heroVerdictSmallRule).toContain("overflow-wrap: anywhere");
    expect(heroTitleRule).toContain("font-size: 15px");
    expect(heroRule).not.toMatch(/display:\s*none/);
    expect(marketRule).not.toMatch(/box-shadow:/);
    expect(kpiRailRule).toContain("border-radius: 6px");
    expect(kpiRailRule).not.toContain("background: var(--moss-color-primary-900)");
    expect(kpiGridRule).toContain("grid-template-columns: repeat(7, minmax(108px, 1fr))");
    expect(kpiGridRule).toContain("background: var(--moss-color-neutral-200)");
    expect(kpiTileRule).toContain("min-height: 52px");
    expect(kpiTileRule).toContain("padding: 8px 8px");
    expect(kpiTileRule).toContain("background: var(--moss-color-neutral-50)");
    expect(kpiPrimaryTileRule).toContain("background: var(--moss-color-card-bg)");
    expect(kpiPrimaryTileRule).toContain("box-shadow: inset 0 2px 0 var(--moss-color-primary-100)");
    expect(kpiPrimaryValueRule).toContain("font-size: 16px");
    expect(kpiGapTileRule).toContain("border-left: 2px solid var(--moss-color-neutral-200)");
    expect(kpiGapTileRule).toContain("background: var(--moss-color-card-bg)");
    expect(kpiValueRule).toContain("font-size: 15px");
  });

  it("keeps the desktop work area as a restrained evidence desk, not decorative hero cards", () => {
    const accountingDv01HeaderFirstCellRule = cssRuleBody(".accountingDv01Header span:first-child");
    const accountingDv01LabelRule = cssRuleBody(".accountingDv01Row strong");
    const accountingDv01NumberRule = cssRuleBody(".accountingDv01Number");
    const analysisRule = cssRuleBody(".referenceAnalysisGrid");
    const panelRule = cssRuleBody(".referencePanelCard");
    const analysisPanelRule = cssRuleBody(".referenceAnalysisGrid .referencePanelCard");
    const curveBannerRule = cssRuleBody(".referenceCurveBanner");
    const curveBannerTextStrongRule = cssRuleBody(".referenceCurveBannerText strong");
    const curveBannerStatsRule = cssRuleBody(".referenceCurveBannerStats");
    const curveBannerStatsDivRule = cssRuleBody(".referenceCurveBannerStats div");
    const curveBannerStatsStrongRule = cssRuleBody(".referenceCurveBannerStats strong");
    const curveCardRule = cssRuleBody(".referenceCurveCard");
    const evidenceNoticeRule = cssRuleBody(".referenceEvidenceNotice");
    const judgmentMatrixRule = cssRuleBody(".referenceJudgmentMatrix");
    const judgmentCardRule = cssRuleBody(".referenceJudgmentCard");
    const judgmentCardSmallRule = cssRuleBody(".referenceJudgmentCard small");
    const strategyGridRule = cssRuleBody(".strategyTagGrid");
    const attributionLeadRule = cssRuleBody(".attributionLead");
    const attributionLeadSmallRule = cssRuleBody(".attributionLead small");
    const attributionLeadStrongRule = cssRuleBody(".attributionLead strong");
    const attributionBoundaryNoteRule = cssRuleBody(".attributionBoundaryNote");
    const attributionGridRule = cssRuleBody(".attributionEvidenceGrid");
    const attributionGridCellRule = cssRuleBody(".attributionEvidenceGrid div");
    const attributionLedgerRowRule = cssRuleBody(".attributionLedger div");

    const sideStackRule = cssRuleBody(".referenceAnalysisSideStack");
    const attributionCardRule = cssRuleBody(".referenceAttributionCard");
    const attributionPanelRule = cssRuleBody(".referenceAttributionPanel");
    const attributionButtonRule = cssRuleBody(".referenceAttributionPanel :global(.ant-btn)");

    expect(analysisRule).toContain("grid-template-columns: minmax(0, 1fr) 372px");
    expect(analysisRule).toContain('"curve evidence"');
    expect(analysisRule).toContain('"attribution attribution"');
    expect(analysisRule).toContain("gap: 8px");
    expect(analysisRule).toContain("align-items: start");
    expect(curveCardRule).toContain("grid-area: curve");
    expect(curveCardRule).toContain("align-self: start");
    expect(sideStackRule).toContain("grid-area: evidence");
    expect(sideStackRule).toContain("display: grid");
    expect(sideStackRule).toContain("gap: 8px");
    expect(attributionCardRule).toContain("grid-area: attribution");
    expect(attributionPanelRule).toContain("grid-template-columns: minmax(210px, 0.75fr) minmax(180px, 0.62fr) minmax(280px, 1fr) minmax(180px, 0.65fr)");
    expect(panelRule).toContain("border: 1px solid var(--moss-color-neutral-200)");
    expect(panelRule).toContain("border-radius: 6px");
    expect(panelRule).toContain("box-shadow: 0 2px 6px rgba(22, 35, 46, 0.035)");
    expect(analysisPanelRule).toContain("box-shadow: 0 2px 6px rgba(22, 35, 46, 0.035)");
    expect(curveBannerRule).toContain("border-left: 4px solid var(--moss-color-primary-700)");
    expect(curveBannerRule).toContain("background: var(--moss-color-neutral-50)");
    expect(curveBannerRule).toContain("padding: 8px 12px");
    expect(curveBannerRule).toContain("gap: 8px");
    expect(curveBannerTextStrongRule).toContain("font-size: 15px");
    expect(curveBannerStatsRule).toContain("grid-template-columns: repeat(2, minmax(74px, 1fr))");
    expect(curveBannerStatsRule).toContain("gap: 1px");
    expect(curveBannerStatsDivRule).toContain("padding: 4px 8px");
    expect(curveBannerStatsStrongRule).toContain("font-size: 14px");
    expect(curveBannerRule).not.toContain("linear-gradient");
    expect(curveBannerRule).not.toMatch(/box-shadow:/);
    expect(evidenceNoticeRule).toContain("border-left: 3px solid var(--moss-color-primary-600)");
    expect(judgmentMatrixRule).toContain("grid-template-columns: repeat(2, minmax(0, 1fr))");
    expect(judgmentCardRule).toContain("border: 1px solid var(--moss-color-neutral-200)");
    expect(judgmentCardRule).toContain("border-radius: 6px");
    expect(judgmentCardRule).toContain("box-shadow: 0 2px 6px rgba(22, 35, 46, 0.035)");
    expect(judgmentCardRule).toContain("min-height: 72px");
    expect(judgmentCardSmallRule).toContain("white-space: normal");
    expect(judgmentCardSmallRule).toContain("overflow-wrap: anywhere");
    expect(strategyGridRule).toContain("display: grid");
    expect(strategyGridRule).toContain("grid-template-columns: repeat(2, minmax(0, 1fr))");
    expect(strategyGridRule).toContain("border: 1px solid var(--moss-color-neutral-100)");
    expect(attributionLeadRule).toContain("grid-template-columns: minmax(0, 1fr) auto");
    expect(attributionLeadRule).toContain("padding: 4px 8px");
    expect(attributionLeadSmallRule).toContain("overflow-wrap: anywhere");
    expect(attributionLeadSmallRule).not.toContain("white-space: nowrap");
    expect(attributionLeadStrongRule).toContain("font-size: 17px");
    expect(attributionLedgerRowRule).toContain("padding: 4px 8px");
    expect(attributionGridCellRule).toContain("padding: 4px 8px");
    expect(attributionBoundaryNoteRule).toContain("grid-column: 1 / 4");
    expect(attributionBoundaryNoteRule).toContain("overflow-wrap: anywhere");
    expect(attributionBoundaryNoteRule).not.toContain("white-space: nowrap");
    expect(attributionButtonRule).toContain("grid-column: 4 / 5");
    expect(attributionGridRule).toContain("grid-template-columns: repeat(2, minmax(0, 1fr))");
    expect(cssRuleBody(".accountingDv01Header")).toContain("padding: 8px 12px");
    expect(accountingDv01HeaderFirstCellRule).toContain("position: sticky");
    expect(COCKPIT_CSS).toContain(".accountingDv01Row {\n  padding: 8px 12px");
    expect(accountingDv01LabelRule).toContain("position: sticky");
    expect(accountingDv01NumberRule).toContain("text-align: right");
  });

  it("locks the curve readout as a dense tenor matrix instead of a decorative chart card", () => {
    const readoutBlockRule = cssRuleBody(".curveReadoutBlock");
    const readoutHeaderRule = cssRuleBody(".curveReadoutHeader");
    const matrixRule = cssRuleBody(".curveTenorMatrix");
    const rowRule = cssRuleBody(".curveMatrixRow");
    const pointCountRule = cssRuleBody(".curvePointCount");
    const valueRule = cssRuleBody(".curveMatrixValue");
    const evidenceTagRule = cssRuleBody(".curveEvidenceTag");
    const curveLayoutRule = cssRuleBody(".referenceCurveLayout");
    const pendingPanelRule = cssRuleBody(".curvePendingPanel");
    const pendingLedgerRule = cssRuleBody(".curvePendingLedger");
    const pendingRowRule = cssRuleBody(".curvePendingRow");

    expect(readoutBlockRule).toContain("border-radius: 6px");
    expect(readoutBlockRule).toContain("background: var(--moss-color-card-bg)");
    expect(readoutBlockRule).toContain("gap: 4px");
    expect(readoutBlockRule).toContain("padding: 8px 8px");
    expect(readoutHeaderRule).toContain("gap: 4px");
    expect(readoutBlockRule).not.toContain("linear-gradient");
    expect(readoutBlockRule).not.toMatch(/box-shadow:/);
    expect(matrixRule).toContain("border: 1px solid var(--moss-color-neutral-200)");
    expect(matrixRule).toContain("border-radius: 4px");
    expect(rowRule).toContain("grid-template-columns: 88px repeat(8, minmax(0, 1fr))");
    expect(rowRule).toContain("min-height: 24px");
    expect(pointCountRule).toContain("display: flex");
    expect(pointCountRule).toContain("line-height: 1.1");
    expect(valueRule).toContain("font-family: var(--moss-font-mono)");
    expect(valueRule).toContain("text-align: right");
    expect(evidenceTagRule).toContain("border-left: 3px solid var(--moss-color-primary-600)");
    expect(curveLayoutRule).toContain("grid-template-columns: minmax(0, 1fr)");
    expect(pendingPanelRule).toContain("min-height: 96px");
    expect(pendingPanelRule).toContain("border: 1px dashed var(--moss-color-neutral-200)");
    expect(pendingPanelRule).toContain("border-radius: 6px");
    expect(pendingPanelRule).not.toContain("linear-gradient");
    expect(pendingLedgerRule).toContain("grid-template-columns: repeat(4, minmax(0, 1fr))");
    expect(pendingRowRule).toContain("padding: 6px 8px");
    expect(COCKPIT_CSS).not.toContain(".curveSpotlight");
    expect(COCKPIT_CSS).not.toContain(".curveLineRail");
  });

  it("presents the lower desktop area as evidence details instead of loose dashboard cards", async () => {
    renderCockpit(createApiClient({ mode: "mock" }));

    const dashboard = await screen.findByTestId("bond-analysis-reference-dashboard");
    const distributionGrid = within(dashboard).getByTestId("bond-analysis-distribution-grid");
    const holdings = within(dashboard).getByTestId("bond-analysis-holdings-table");
    const evidenceStrip = within(dashboard).getByTestId("bond-analysis-holdings-evidence-strip");
    const sideStack = within(dashboard).getByTestId("bond-analysis-risk-slice-stack");
    const summary = within(dashboard).getByTestId("bond-analysis-summary-card");

    expect(distributionGrid).toHaveTextContent("结构证据");
    expect(distributionGrid).toHaveTextContent("风险切片");
    expect(distributionGrid).toHaveTextContent("集中度证据");
    expect(distributionGrid).toHaveTextContent("缺失保持占位");
    expect(distributionGrid).toHaveTextContent("不生成阈值判断");

    expect(holdings).toHaveTextContent("持仓证据明细");
    expect(holdings).toHaveTextContent("前十大返回持仓");
    expect(evidenceStrip).toHaveTextContent("返回持仓");
    expect(evidenceStrip).toHaveTextContent("评级缺口");
    expect(evidenceStrip).toHaveTextContent("数值缺口");
    expect(evidenceStrip).toHaveTextContent("不补造评级");

    expect(sideStack).toHaveTextContent("风险切片");
    expect(sideStack).toHaveTextContent("评级 / 期限 / 流动性");
    expect(sideStack).toHaveTextContent("接口缺口直接显示");

    expect(summary).toHaveTextContent("收益证据");
    expect(within(dashboard).getByTestId("bond-analysis-return-trend-boundary")).toHaveTextContent(
      "收益时序未返回：不绘制趋势占位",
    );
    expect(summary).not.toHaveTextContent("健康");
    expect(summary).not.toHaveTextContent("稳定");
    expect(dashboard).not.toHaveTextContent("风险可控");
  });

  it("locks lower evidence area desktop styling around table and slice boundaries", () => {
    const distributionGridRule = cssRuleBody(".referenceDistributionGrid");
    const structureLeadRule = cssRuleBody(".referenceStructureLeadCard");
    const distributionSupportRule = cssRuleBody(".referenceDistributionSupportCard");
    const donutPanelRule = cssRuleBody(".referenceDonutPanel");
    const donutRule = cssRuleBody(".referenceDonut");
    const footerGridRule = cssRuleBody(".referenceFooterGrid");
    const footerCardRule = cssRuleBody(".referenceFooterGrid :global(.ant-card)");
    const footerPrimaryCardRule = cssRuleBody(".referenceFooterPrimaryCard");
    const footerSupportStackRule = cssRuleBody(".footerSupportStack");
    const footerEvidenceBlockRule = cssRuleBody(".footerEvidenceBlock");
    const footerActionBarRule = cssRuleBody(".footerActionBar");
    const footerMetricStrongRule = cssRuleBody(".footerMetricPanel strong");
    const holdingsStripRule = cssRuleBody(".holdingsEvidenceStrip");
    const holdingsTableRule = cssRuleBody(".holdingsTable");
    const holdingsScrollCueRule = cssRuleBody(".holdingsScrollCue");
    const holdingsScrollCueSpanRule = cssRuleBody(".holdingsScrollCue span");
    const holdingsTableRowsRule = cssRuleBody(".holdingsTableRows");
    const holdingsTableHeaderRule = cssRuleBody(".holdingsTableHeader");
    const holdingsTableHeaderFirstCellRule = cssRuleBody(".holdingsTableHeader span:first-child");
    const holdingNameCellRule = cssRuleBody(".holdingNameCell");
    const tableEmptyRule = cssRuleBody(".tableEmpty");
    const emptyEvidencePanelRule = cssRuleBody(".emptyEvidencePanel");
    const moduleNoteRule = cssRuleBody(".moduleNote");
    const pendingReadModelPanelRule = cssRuleBody(".pendingReadModelPanel");
    const riskEvidenceListRule = cssRuleBody(".riskEvidenceList");
    const riskEvidenceRowRule = cssRuleBody(".riskEvidenceRow");
    const sideHeaderRule = cssRuleBody(".sideStackHeader");
    const sideStackRule = cssRuleBody(".referenceSideStack");
    const sideStackCardRule = cssRuleBody(".referenceSideStack :global(.ant-card)");
    const numericCellRule = cssRuleBody(".holdingNumericCell");
    const footerEvidenceNoteRule = cssRuleBody(".footerEvidenceNote");

    expect(distributionGridRule).toContain("grid-template-columns: minmax(440px, 1.4fr) minmax(300px, 0.88fr) minmax(300px, 0.88fr)");
    expect(structureLeadRule).toContain("min-width: 0");
    expect(distributionSupportRule).toContain("min-width: 0");
    expect(donutPanelRule).toContain("grid-template-columns: minmax(0, 1fr) 150px");
    expect(donutPanelRule).toContain("min-height: 132px");
    expect(donutRule).toContain("width: 116px");
    expect(footerGridRule).toContain("grid-template-columns: minmax(0, 1.36fr) minmax(320px, 0.84fr)");
    expect(footerGridRule).toContain("gap: 1px");
    expect(footerGridRule).toContain("align-items: start");
    expect(footerGridRule).toContain("border: 1px solid var(--moss-color-neutral-200)");
    expect(footerCardRule).toContain("box-shadow: none !important");
    expect(footerPrimaryCardRule).toContain("min-width: 0");
    expect(footerSupportStackRule).toContain("gap: 1px");
    expect(footerSupportStackRule).toContain("background: var(--moss-color-neutral-200)");
    expect(footerEvidenceBlockRule).toContain("gap: 6px");
    expect(footerEvidenceBlockRule).not.toContain("border:");
    expect(footerActionBarRule).toContain("grid-template-columns: minmax(0, 1fr) auto");
    expect(COCKPIT_CSS).toContain(".referenceFooterGrid :global(.ant-card-head)");
    expect(COCKPIT_CSS).toContain("min-height: 32px");
    expect(footerMetricStrongRule).toContain("font-size: 16px");
    expect(holdingsStripRule).toContain("grid-template-columns: repeat(3, minmax(0, 1fr))");
    expect(holdingsStripRule).toContain("border-bottom: 1px solid var(--moss-color-neutral-200)");
    expect(holdingsTableRule).toContain("overflow-x: auto");
    expect(holdingsTableRule).toContain("scrollbar-gutter: stable");
    expect(holdingsTableRule).toContain("box-shadow: inset -18px 0 18px -22px rgba(31, 41, 55, 0.48)");
    expect(holdingsScrollCueRule).toContain("position: sticky");
    expect(holdingsScrollCueRule).toContain("right: 8px");
    expect(holdingsScrollCueRule).toContain("pointer-events: none");
    expect(holdingsScrollCueSpanRule).toContain("transform: rotate(45deg)");
    expect(holdingsTableRowsRule).toContain("min-height: 88px");
    expect(holdingsTableHeaderRule).toContain("padding: 8px 12px");
    expect(holdingsTableHeaderFirstCellRule).toContain("position: sticky");
    expect(holdingsTableHeaderFirstCellRule).toContain("left: 0");
    expect(COCKPIT_CSS).toContain(".holdingsTableRow {\n  padding: 8px 12px");
    expect(holdingNameCellRule).toContain("position: sticky");
    expect(holdingNameCellRule).toContain("border-right: 1px solid var(--moss-color-neutral-100)");
    expect(tableEmptyRule).toContain("min-height: 64px");
    expect(tableEmptyRule).toContain("border: 1px dashed var(--moss-color-neutral-200)");
    expect(tableEmptyRule).toContain("background: var(--moss-color-neutral-50)");
    expect(emptyEvidencePanelRule).toContain("min-height: 56px");
    expect(emptyEvidencePanelRule).toContain("border: 1px dashed var(--moss-color-neutral-200)");
    expect(moduleNoteRule).toContain("min-height: 32px");
    expect(moduleNoteRule).toContain("border: 1px dashed var(--moss-color-neutral-200)");
    expect(pendingReadModelPanelRule).toContain("border: 1px dashed var(--moss-color-neutral-200)");
    expect(riskEvidenceListRule).toContain("border: 1px solid var(--moss-color-neutral-100)");
    expect(riskEvidenceRowRule).toContain("grid-template-columns: minmax(0, 1fr) auto");
    expect(sideStackRule).toContain("gap: 1px");
    expect(sideStackRule).toContain("border: 1px solid var(--moss-color-neutral-200)");
    expect(sideStackCardRule).toContain("box-shadow: none !important");
    expect(sideHeaderRule).toContain("border-left: 4px solid var(--moss-color-primary-700)");
    expect(numericCellRule).toContain("text-align: right");
    expect(footerEvidenceNoteRule).toContain("border: 1px dashed var(--moss-color-neutral-200)");
    expect(footerEvidenceNoteRule).toContain("background: var(--moss-color-neutral-50)");
    expect(COCKPIT_CSS).not.toContain(".footerSparkline");
  });

  it("renders the footer evidence grid as a primary summary card with a support stack", async () => {
    renderCockpit(createApiClient({ mode: "mock" }));

    const dashboard = await screen.findByTestId("bond-analysis-reference-dashboard");
    const footerGrid = within(dashboard).getByTestId("bond-analysis-footer-evidence-grid");
    const summaryCard = within(footerGrid).getByTestId("bond-analysis-summary-card");
    const supportStack = within(footerGrid).getByTestId("bond-analysis-footer-support-stack");
    const primaryEvidence = within(summaryCard).getByTestId("bond-analysis-footer-primary-evidence");
    const trendBoundary = within(summaryCard).getByTestId("bond-analysis-return-trend-boundary");
    const actionAttributionCard = within(supportStack).getByTestId("bond-analysis-today-focus");
    const riskGuardrails = within(supportStack).getByTestId("bond-analysis-risk-guardrails");

    expect(summaryCard).toBeInTheDocument();
    expect(supportStack).toBeInTheDocument();
    expect(summaryCard).toContainElement(primaryEvidence);
    expect(primaryEvidence).toContainElement(trendBoundary);
    expect(trendBoundary).toHaveTextContent("不绘制趋势占位");
    expect(summaryCard).toHaveTextContent("收益时序");
    expect(summaryCard).toHaveTextContent("不补造趋势");
    expect(actionAttributionCard).toHaveTextContent("动作归因");
    expect(actionAttributionCard).toHaveTextContent("市值变动与 DV01 变动用于核对动作归因字段返回范围。");
    expect(riskGuardrails).toHaveTextContent("只列已返回风险字段；缺失保持证据缺口，不延伸为审批或阈值结论。");
    expect(riskGuardrails).toHaveTextContent("信用利差字段以下钻返回为准；缺失继续保留证据缺口。");
    expect(riskGuardrails).not.toHaveTextContent("风险可控");
    expect(riskGuardrails).not.toHaveTextContent("健康");
    expect(riskGuardrails).not.toHaveTextContent("稳定");
  });

  it("locks the footer evidence CSS structure without sparkline placeholders", () => {
    const footerGridRule = cssRuleBody(".referenceFooterGrid");
    const footerSupportStackRule = cssRuleBody(".footerSupportStack");
    const footerEvidenceBlockRule = cssRuleBody(".footerEvidenceBlock");
    const footerReturnLedgerRule = cssRuleBody(".footerReturnLedger");
    const footerReturnLedgerSecondRule = cssRuleBody(".footerReturnLedger div:nth-child(2n)");
    const footerReturnLedgerLowerRule = cssRuleBody(".footerReturnLedger div:nth-child(n + 3)");
    const footerActionBarRule = cssRuleBody(".footerActionBar");
    const footerRiskRowRule = cssRuleBody(".footerRiskRow");

    expect(footerGridRule).toContain("display: grid");
    expect(footerGridRule).toContain("grid-template-columns: minmax(0, 1.36fr) minmax(320px, 0.84fr)");
    expect(footerGridRule).toContain("align-items: start");
    expect(footerSupportStackRule).toContain("display: grid");
    expect(footerSupportStackRule).toContain("gap: 1px");
    expect(footerSupportStackRule).toContain("min-width: 0");
    expect(footerEvidenceBlockRule).toContain("display: grid");
    expect(footerEvidenceBlockRule).toContain("gap: 6px");
    expect(footerEvidenceBlockRule).toContain("min-width: 0");
    expect(footerEvidenceBlockRule).not.toContain("border:");
    expect(footerReturnLedgerRule).toContain("grid-template-columns: repeat(2, minmax(0, 1fr))");
    expect(footerReturnLedgerRule).toContain("background: var(--moss-color-neutral-50)");
    expect(footerReturnLedgerSecondRule).toContain("border-left: 1px solid var(--moss-color-neutral-100)");
    expect(footerReturnLedgerLowerRule).toContain("border-top: 1px solid var(--moss-color-neutral-100)");
    expect(footerActionBarRule).toContain("display: grid");
    expect(footerActionBarRule).toContain("grid-template-columns: minmax(0, 1fr) auto");
    expect(footerActionBarRule).toContain("align-items: center");
    expect(footerRiskRowRule).toContain("display: flex");
    expect(COCKPIT_CSS).not.toContain(".footerRiskList div");
    expect(COCKPIT_CSS).not.toContain(".footerSparkline");
  });

  it("keeps cockpit cards in a compact institutional panel style", () => {
    const source = readFileSync(
      resolve(
        process.cwd(),
        "src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.tsx",
      ),
      "utf8",
    );

    expect(source).toContain("const deskPanelShadow = \"0 2px 6px rgba(22, 35, 46, 0.035)\"");
    expect(source).toContain("border: `1px solid ${dt.color.neutral[200]}`");
    expect(source).toContain("borderRadius: dt.radius.sm");
    expect(source).not.toContain("borderRadius: dt.radius.lg");
    expect(source).not.toContain("const restrainedShadow =");
  });
});
