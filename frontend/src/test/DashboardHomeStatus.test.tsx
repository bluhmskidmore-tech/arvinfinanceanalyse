import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import { getApiClientFactoryRecord, registerApiClientFactory } from "../api/clientFactoryOptions";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({
  default: () => null,
}));

function createRealModeHomeClient(overrides: Partial<ApiClient> = {}): ApiClient {
  const base = createApiClient({ mode: "real" });
  const client = {
    ...base,
    getResearchCalendarEvents: vi.fn(async () => []),
    ...overrides,
  };
  if (!getApiClientFactoryRecord(client)) {
    registerApiClientFactory(
      client,
      {
        mode: "real",
        baseUrl: "",
        fetchImpl: async (input) => {
          const path = new URL(String(input), "http://moss.local").pathname;
          if (path === "/api/system-read-publication") {
            return new Response(JSON.stringify({ enabled: false, generation: null, coverage_dates: {} }), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            });
          }
          throw new Error(`Unexpected factory fetch in dashboard status test: ${path}`);
        },
      },
      () => client,
    );
  }
  return client;
}

describe("DashboardHomeStatus", () => {
  it("surfaces a governed permission failure without claiming the service is unavailable", async () => {
    const client = createRealModeHomeClient({
      getHomeSnapshot: vi.fn(async () => {
        throw new Error("User is not allowed to read executive.");
      }),
    });

    renderWorkbenchApp(["/"], { client });

    const dataStatus = await screen.findByTestId("dashboard-home-data-status");
    await waitFor(() => {
      expect(dataStatus).toHaveAttribute("data-status-kind", "error");
      expect(dataStatus).toHaveTextContent("权限不足");
    });
    const page = screen.getByTestId("dashboard-home-page");
    expect(page).toHaveClass("theme-dh-api");
    expect(page).toHaveAttribute("data-moss-theme", "dark");
    expect(page).toHaveAttribute("data-moss-theme-scope", "dashboard-home");
    expect(page).not.toHaveTextContent("服务不可达");
    expect(screen.getByTestId("dashboard-home-morning-hero")).toBeInTheDocument();
    expect(
      screen
        .getByTestId("dashboard-home-toolbar")
        .querySelector('[data-role="dashboard-home-update-stamp"]'),
    ).toHaveTextContent("更新 —");
    expect(screen.getByPlaceholderText("2026-04-30")).toHaveValue("");
    expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveAttribute(
      "data-state",
      "empty",
    );
    expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("—");
    expect(screen.getAllByText("无可用快照").length).toBeGreaterThan(0);

    fireEvent.scroll(window);

    const availabilityPanel = await screen.findByTestId("dashboard-home-data-availability");
    expect(availabilityPanel).toHaveTextContent("首页快照权限不足");
    expect(
      screen.getByTestId("dashboard-home-data-availability-retry"),
    ).toHaveTextContent("重新读取");
    expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-source-gate")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-position-changes")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-income-trend")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-bottom-grid")).toBeInTheDocument();
    expect(
      screen
        .getByTestId("dashboard-home-bottom-grid")
        .querySelector('small[data-status-kind="error"]'),
    ).toHaveTextContent("不可用");
    expect(screen.getByTestId("dashboard-home-bond-news")).toBeInTheDocument();
    expect(page).not.toHaveTextContent("3,708.10");
    expect(page).not.toHaveTextContent("样例");
  });

  it("describes a generic snapshot failure as a read failure and does not inject preview KPIs", async () => {
    const client = createRealModeHomeClient({
      getHomeSnapshot: vi.fn(async () => {
        throw new Error("snapshot unavailable");
      }),
    });

    renderWorkbenchApp(["/"], { client });

    const hero = await screen.findByTestId("dashboard-home-morning-hero");
    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-data-status")).toHaveTextContent("首页快照读取失败");
      expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveAttribute(
        "data-state",
        "empty",
      );
      expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("—");
      expect(hero).not.toHaveTextContent("3,708.10");
      expect(hero).not.toHaveTextContent("样例");
    });
    expect(screen.getByTestId("dashboard-home-page")).not.toHaveTextContent("服务不可达");
  });

  it("retries an unavailable snapshot from the degraded panel and clears the error state", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>()
      .mockRejectedValueOnce(new Error("snapshot unavailable"))
      .mockImplementation(async (options) => mockSource.getHomeSnapshot(options));
    const client = createRealModeHomeClient({ getHomeSnapshot });

    renderWorkbenchApp(["/"], { client });

    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-data-status")).toHaveAttribute(
        "data-status-kind",
        "error",
      );
    });
    fireEvent.scroll(window);

    const retryButton = await screen.findByTestId("dashboard-home-data-availability-retry");
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(getHomeSnapshot).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId("dashboard-home-data-status")).not.toHaveAttribute(
        "data-status-kind",
        "error",
      );
    });
    await waitFor(() => {
      const availabilityPanel = screen.queryByTestId("dashboard-home-data-availability");
      expect(availabilityPanel?.getAttribute("data-state")).not.toBe("error");
      expect(availabilityPanel?.textContent ?? "").not.toContain("首页快照读取失败");
    });
  });

  it("keeps the degraded panel visible and disables retry while an unresolved retry is pending", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    type HomeSnapshotEnvelope = Awaited<ReturnType<ApiClient["getHomeSnapshot"]>>;
    let resolveRetry!: (value: HomeSnapshotEnvelope) => void;
    const retryRequest = new Promise<HomeSnapshotEnvelope>((resolve) => {
      resolveRetry = resolve;
    });
    const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>()
      .mockRejectedValueOnce(new Error("User is not allowed to read executive."))
      .mockImplementationOnce(() => retryRequest);
    const client = createRealModeHomeClient({ getHomeSnapshot });

    renderWorkbenchApp(["/"], { client });

    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-data-status")).toHaveAttribute(
        "data-status-kind",
        "error",
      );
    });
    fireEvent.scroll(window);

    const retryButton = await screen.findByTestId("dashboard-home-data-availability-retry");
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(getHomeSnapshot).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId("dashboard-home-data-availability")).toBeInTheDocument();
      expect(screen.getByTestId("dashboard-home-data-availability-retry")).toBeDisabled();
      expect(screen.getByTestId("dashboard-home-data-availability-retry")).toHaveTextContent(
        "刷新中",
      );
    });

    resolveRetry(await mockSource.getHomeSnapshot());

    await waitFor(() => {
      const availabilityPanel = screen.queryByTestId("dashboard-home-data-availability");
      expect(availabilityPanel?.getAttribute("data-state")).not.toBe("error");
      expect(availabilityPanel?.textContent ?? "").not.toContain("首页快照权限不足");
    });
  });

  it("states facts once on a healthy snapshot: no templated verdict, lineage in tooltips, quiet data-quality line", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const yuan = (raw: number, display: string, signAware = false) => ({
      raw,
      unit: "yuan" as const,
      display,
      precision: 2,
      sign_aware: signAware,
    });
    const lineage = "来自治理资产快照，在 2026-04-18 的本币资产口径市值合计。";
    const client = createRealModeHomeClient({
      getHomeSnapshot: vi.fn<ApiClient["getHomeSnapshot"]>(async (options) => {
        const envelope = await mockSource.getHomeSnapshot(options);
        return {
          ...envelope,
          result_meta: {
            ...envelope.result_meta,
            basis: "analytical" as const,
            formal_use_allowed: false,
            source_surface: "executive_analytical",
          },
          result: {
            ...envelope.result,
            overview: {
              ...envelope.result.overview,
              metrics: [
                {
                  id: "aum",
                  label: "总资产规模",
                  caliber_label: "本币资产口径",
                  value: yuan(370_538_010_245.46, "3,705.38 亿"),
                  delta: { raw: -0.0386, unit: "pct" as const, display: "-3.86%", precision: 2, sign_aware: true },
                  tone: "positive" as const,
                  detail: lineage,
                  history: [389_608_270_008, 370_538_010_245.46],
                },
                {
                  id: "yield",
                  label: "年度损益（不扣FTP）",
                  caliber_label: "FI + 非标桥接",
                  value: yuan(4_856_069_979.5, "+48.56 亿", true),
                  delta: { raw: 0.144, unit: "pct" as const, display: "+14.40%", precision: 2, sign_aware: true },
                  tone: "positive" as const,
                  detail: "测试真实接口返回值。",
                  history: [3_651_202_655, 4_856_069_979.5],
                },
              ],
            },
            verdict: {
              conclusion: "首屏整体偏多，可基于规模与收益做方向性判断",
              tone: "positive" as const,
              reasons: [
                { label: "总资产规模", value: "3,705.38 亿", detail: lineage, tone: "positive" as const },
                { label: "年度损益（不扣FTP）", value: "+48.56 亿", detail: lineage, tone: "positive" as const },
              ],
              suggestions: [
                { text: "进入对应专题页继续下钻原因链条", link: null },
                { text: "关注信用利差与久期暴露", link: "/bond-analysis" },
              ],
            },
            product_category_ytd: {
              view: "ytd" as const,
              summary_pnl: yuan(1_240_000_000, "+12.40 亿元", true),
              summary_pnl_detail: "测试真实接口返回值。",
              operating_income: yuan(890_000_000, "+8.90 亿元", true),
              operating_income_detail: "测试真实接口返回值。",
              intermediate_business_income: yuan(350_000_000, "+3.50 亿元", true),
              intermediate_business_income_detail: "测试真实接口返回值。",
            },
            product_category_monthly: {
              view: "monthly" as const,
              monthly_income: yuan(120_000_000, "+1.20 亿元", true),
              monthly_income_detail: "测试真实接口返回值。",
            },
          },
        };
      }),
    });

    renderWorkbenchApp(["/"], { client });

    const hero = await screen.findByTestId("dashboard-home-hero");
    await waitFor(() => {
      expect(within(hero).getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("3,705.38");
    });

    // 模板结论不转述方向判断，也不再冒充「趋势判断待复核」；标题是可核对的读数事实。
    const heroText = hero.textContent ?? "";
    expect(heroText).not.toMatch(/趋势判断|偏多|方向性判断/);
    const attention = within(hero).getByText("观察与数据状态 · 不计入治理待办").parentElement;
    if (!attention) throw new Error("Expected attention block");
    expect(attention.querySelector("strong")).toHaveTextContent(
      "总资产规模（本币资产口径） 3,705.38 亿，年度损益（不扣FTP） +48.56 亿",
    );

    // 两条 reason 的标签+数值都已在标题事实句里，依据行不复述，退到第一条有信息量的建议
    // （跳过「进入专题页」类指路模板）；同一格内「3,705.38」只出现一次，溯源句不进正文。
    const reason = attention.querySelector("small");
    if (!reason) throw new Error("Expected attention reason line");
    expect(reason).toHaveTextContent("关注信用利差与久期暴露");
    expect(reason).not.toHaveTextContent(/3,705\.38|\+48\.56|进入对应专题页/);
    expect((reason.textContent ?? "").split("·").length - 1).toBeLessThanOrEqual(1);
    expect((attention.textContent ?? "").split("3,705.38").length - 1).toBe(1);
    expect(heroText).not.toContain("来自治理资产快照");

    // 02 区不再复述结论与依据，只留归因独有内容。
    const narrative = within(hero).getByTestId("dashboard-home-morning-hero");
    expect(narrative).toHaveTextContent("归因要点");
    expect(narrative).not.toHaveTextContent("3,705.38");
    expect(narrative).toHaveTextContent("进入专题页");

    // 数据质量 ok / 估值完成 / 无缺失域：收成一行 muted 事实，徽标词与「缺失域 无」只在 title。
    const status = within(hero).getByLabelText("首页数据状态");
    expect(status.querySelectorAll("dt")).toHaveLength(1);
    expect(status).toHaveTextContent("数据质量");
    expect(status).toHaveTextContent("核心域同报告日");
    expect(status).not.toHaveTextContent(/缺失域|已就绪|估值已完成|2026-04-18/);
    expect(status.querySelector("dd")).toHaveAttribute(
      "title",
      expect.stringContaining("缺失域 无"),
    );
  });

  it("drops the previous date snapshot and surfaces an explicit error when a new report date request fails", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const firstReportDate = "2026-04-30";
    const failedReportDate = "2026-05-31";
    const client = createRealModeHomeClient({
      getHomeSnapshot: vi.fn<ApiClient["getHomeSnapshot"]>(async (options) => {
        if (options?.reportDate === failedReportDate) {
          throw new Error("new report date unavailable");
        }
        const base = await mockSource.getHomeSnapshot(options);
        return {
          ...base,
          result: {
            ...base.result,
            report_date: firstReportDate,
          },
        };
      }),
    });

    renderWorkbenchApp(["/"], { client });

    const reportDateInput = await screen.findByPlaceholderText("2026-04-30");
    await waitFor(() => {
      expect(reportDateInput).toHaveValue(firstReportDate);
    });

    fireEvent.change(reportDateInput, {
      target: { value: failedReportDate },
    });

    await waitFor(() => {
      expect(
        screen.getByTestId("dashboard-home-data-status").getAttribute("data-status-kind"),
      ).not.toBe("loading");
    });

    // 语义对齐（2026-09-28）：useDashboardSnapshotBoundary 已刻意把「保留上一版本」收窄为
    // **同一读取范围**（见该文件 lastReadScopeRef，以及 useDashboardSnapshotBoundary.test.tsx 的
    // "restores cached data after remount only for the same read scope" 参数化矩阵）。
    // 请求报告日变化属于不同读取范围，因此上一版本快照必须被丢弃，并显式暴露为 error；
    // 不得再伪装成 stale 继续展示上一报告日的数据。
    const dataStatus = screen.getByTestId("dashboard-home-data-status");
    expect(dataStatus).toHaveAttribute("data-status-kind", "error");
    expect(dataStatus).toHaveTextContent("首页快照读取失败");
    expect(dataStatus).not.toHaveTextContent("展示上一版本");
    expect(screen.getByTestId("dashboard-home-report-date-context")).toHaveTextContent("读取失败");

    fireEvent.scroll(window);
    const bottomGrid = await screen.findByTestId("dashboard-home-bottom-grid");
    // 关键回归守卫：跨读取范围失败后，任何位置都不得残留 stale 徽标。
    expect(bottomGrid.querySelectorAll('small[data-status-kind="stale"]')).toHaveLength(0);
    expect(
      bottomGrid.querySelectorAll('small[data-status-kind="error"]').length,
    ).toBeGreaterThan(0);
  });
});
