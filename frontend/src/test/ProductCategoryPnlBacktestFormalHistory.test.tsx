import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import type { ProductCategoryPnlPayload } from "../api/contracts";
import { selectProductCategoryOperatingActionBacktestSurface } from "../features/product-category-pnl/pages/productCategoryPnlPageModel";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { buildMockProductCategoryPnlEnvelope } from "../mocks/productCategoryPnl";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({ default: () => <div /> }));

const REPORT_DATE = "2026-08-31";
const PRIOR_DATE = "2026-07-31";

function pnlEnvelope(
  options: Parameters<typeof buildMockProductCategoryPnlEnvelope>[0],
) {
  const envelope = buildMockProductCategoryPnlEnvelope(options);
  const income = options.reportDate === PRIOR_DATE ? -100_000_000 : -90_000_000;
  envelope.result.rows = [
    {
      ...envelope.result.rows[0]!,
      category_name: "回测样本资产",
      business_net_income: String(
        income - (options.scenarioRatePct ? 100_000_000 : 0),
      ),
      cnx_scale: "10000000000",
      weighted_yield: "1.00",
    },
  ];
  return envelope;
}

function clientFixture() {
  const client = createApiClient({ mode: "mock" });
  return {
    ...client,
    getProductCategoryDates: vi.fn(async () =>
      buildMockApiEnvelope("product_category_pnl.dates", {
        report_dates: [REPORT_DATE, PRIOR_DATE],
      }),
    ),
    getProductCategoryPnl: vi.fn(
      async (options: Parameters<typeof client.getProductCategoryPnl>[0]) =>
        pnlEnvelope(options),
    ),
    getProductCategoryHistory: vi.fn(client.getProductCategoryHistory),
  } satisfies typeof client;
}

async function openWorkspace(testId: string) {
  const user = userEvent.setup();
  const workspace = await screen.findByTestId(testId);
  await user.click(workspace.querySelector("summary")!);
}

async function applyScenario() {
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("FTP 场景"), "2.00");
  await user.click(screen.getByTestId("product-category-apply-scenario-button"));
  await screen.findByTestId("product-category-result-meta-scenario");
}

beforeAll(async () => {
  await preloadWorkbenchRouteModules("product-category-pnl");
}, 60_000);

beforeEach(() => {
  window.localStorage.setItem("moss.product-category-pnl.trend-workspace-open", "0");
});

describe("formal monthly operating backtest", () => {
  it.each(["2.00", "0", 0])(
    "excludes the %s percent scenario when replaying formal history",
    (scenarioRate) => {
      const prior = pnlEnvelope({ reportDate: PRIOR_DATE, view: "monthly" }).result;
      const current = pnlEnvelope({ reportDate: REPORT_DATE, view: "monthly" }).result;
      const scenario: ProductCategoryPnlPayload = {
        ...pnlEnvelope({
          reportDate: PRIOR_DATE,
          view: "monthly",
          scenarioRatePct: String(scenarioRate),
        }).result,
        scenario_rate_pct: scenarioRate,
      };
      const formal = selectProductCategoryOperatingActionBacktestSurface({
        payloads: [prior, current],
      });

      expect(formal.summary.evaluatedMonthCount).toBe(1);
      expect(formal.examples[0]?.netIncomeDelta).toBeCloseTo(0.1, 12);
      expect(
        selectProductCategoryOperatingActionBacktestSurface({
          payloads: [prior, scenario, current],
        }),
      ).toEqual(formal);
      expect(
        selectProductCategoryOperatingActionBacktestSurface({
          payloads: [scenario, current],
        }).summary.evaluatedMonthCount,
      ).toBe(0);
    },
  );

  it("reuses management-monitor formal history when the backtest opens under an applied FTP scenario", async () => {
    const client = clientFixture();
    renderWorkbenchApp(["/product-category-pnl"], { client });
    await screen.findByTestId("product-category-table");
    // The visible management monitor shares this formal monthly query. Opening
    // a backtest must reuse it rather than treating the endpoint as exclusive.
    await waitFor(() => {
      expect(client.getProductCategoryHistory).toHaveBeenCalledTimes(1);
    });
    await applyScenario();
    expect(client.getProductCategoryHistory).toHaveBeenCalledTimes(1);

    await openWorkspace("product-category-backtest-workspace");

    await waitFor(() => {
      expect(client.getProductCategoryHistory).toHaveBeenCalledWith({
        reportDates: [PRIOR_DATE],
        view: "monthly",
      });
      expect(
        screen.getByTestId("product-category-operating-action-backtest"),
      ).toHaveTextContent("净营收 +0.10 亿元");
    });
    expect(client.getProductCategoryHistory).toHaveBeenCalledTimes(1);
    expect(
      screen.getByTestId("product-category-operating-action-backtest"),
    ).not.toHaveTextContent("净营收 +1.10 亿元");
  });

  it("reuses formal trend history through scenario changes without duplicate reads", async () => {
    const client = clientFixture();
    renderWorkbenchApp(["/product-category-pnl"], { client });
    await screen.findByTestId("product-category-table");
    await openWorkspace("product-category-trend-workspace");
    await waitFor(() => {
      expect(client.getProductCategoryHistory).toHaveBeenCalledTimes(1);
    });
    await openWorkspace("product-category-backtest-workspace");
    await waitFor(() => {
      expect(
        screen.getByTestId("product-category-operating-action-backtest"),
      ).toHaveTextContent("净营收 +0.10 亿元");
    });
    await applyScenario();
    await waitFor(() => {
      expect(client.getProductCategoryHistory).toHaveBeenCalledWith({
        reportDates: [PRIOR_DATE],
        view: "monthly",
        scenarioRatePct: "2.00",
      });
    });
    await waitFor(() => {
      expect(
        screen.getByTestId("product-category-operating-action-backtest"),
      ).toHaveTextContent("净营收 +0.10 亿元");
    });
    expect(
      client.getProductCategoryHistory.mock.calls.filter(
        ([options]) => !options.scenarioRatePct,
      ),
    ).toHaveLength(1);
  });

  it("shows a retryable formal-history failure without using scenario results", async () => {
    const client = clientFixture();
    const getHistory = client.getProductCategoryHistory;
    let failFormalHistory = true;
    client.getProductCategoryHistory = vi.fn(async (options) => {
      if (!options.scenarioRatePct && failFormalHistory) {
        throw new Error("formal-history-unavailable");
      }
      return getHistory.call(client, options);
    });
    renderWorkbenchApp(["/product-category-pnl"], { client });
    await screen.findByTestId("product-category-table");
    await applyScenario();
    await openWorkspace("product-category-backtest-workspace");

    const error = await screen.findByTestId("product-category-backtest-history-error");
    expect(error).toHaveTextContent("正式月度历史读取失败");
    expect(
      screen.queryByTestId("product-category-operating-action-backtest"),
    ).not.toBeInTheDocument();
    failFormalHistory = false;
    await userEvent.setup().click(within(error).getByRole("button", { name: "重试正式历史" }));
    await waitFor(() => {
      expect(
        screen.getByTestId("product-category-operating-action-backtest"),
      ).toHaveTextContent("净营收 +0.10 亿元");
    });
  });

  it("waits for formal history even when scenario history has already loaded", async () => {
    const client = clientFixture();
    let releaseHistory!: () => void;
    const historyReady = new Promise<void>((resolve) => {
      releaseHistory = resolve;
    });
    client.getProductCategoryPnl.mockImplementation(async (options) => {
      if (options.reportDate === PRIOR_DATE && !options.scenarioRatePct) {
        await historyReady;
      }
      return pnlEnvelope(options);
    });
    renderWorkbenchApp(["/product-category-pnl"], { client });
    await screen.findByTestId("product-category-table");
    await applyScenario();
    await openWorkspace("product-category-trend-workspace");
    await waitFor(() => {
      expect(client.getProductCategoryHistory).toHaveBeenCalledWith({
        reportDates: [PRIOR_DATE],
        view: "monthly",
        scenarioRatePct: "2.00",
      });
    });
    await openWorkspace("product-category-backtest-workspace");

    const panel = screen.getByTestId("product-category-operating-action-backtest");
    await waitFor(() => {
      expect(panel).toHaveTextContent("正在加载历史月度快照。");
    });
    expect(panel).not.toHaveTextContent("净营收 +1.10 亿元");
    releaseHistory();
    await waitFor(() => {
      expect(panel).toHaveTextContent("净营收 +0.10 亿元");
    });
  });

  it("keeps the unsupported YTD backtest state without adding monthly history requests", async () => {
    const client = clientFixture();
    renderWorkbenchApp(["/product-category-pnl"], { client });
    await screen.findByTestId("product-category-table");
    // Monthly management monitoring is already active before switching views.
    await waitFor(() => {
      expect(client.getProductCategoryHistory).toHaveBeenCalledTimes(1);
    });
    await userEvent.setup().click(screen.getByRole("button", { name: "汇总视图" }));
    await applyScenario();
    await openWorkspace("product-category-backtest-workspace");

    await waitFor(() => {
      expect(
        screen.getByTestId("product-category-operating-action-backtest"),
      ).toHaveTextContent("需要至少两个连续月度正式 payload 才能回测行动信号。");
    });
    expect(client.getProductCategoryHistory).toHaveBeenCalledTimes(1);
  });
});
