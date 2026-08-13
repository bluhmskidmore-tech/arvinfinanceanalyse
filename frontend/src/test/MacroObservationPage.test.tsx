import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import { ApiClientProvider } from "../api/clientContext";
import MacroObservationPage from "../features/macro-observation/pages/MacroObservationPage";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

beforeAll(async () => {
  await preloadWorkbenchRouteModules("macro-observation");
}, 20_000);

type MacroToolkitAnalysisEnvelope = Awaited<ReturnType<ApiClient["getMacroToolkitAnalysis"]>>;

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: 0,
        refetchOnWindowFocus: false,
      },
    },
  });
}

function renderObservationPage(client: ApiClient, queryClient = createTestQueryClient()) {
  return render(
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        <MacroObservationPage />
      </QueryClientProvider>
    </ApiClientProvider>,
  );
}

async function buildCoreDeferredEnvelope(): Promise<{
  fullEnvelope: MacroToolkitAnalysisEnvelope;
  coreEnvelope: MacroToolkitAnalysisEnvelope;
}> {
  const baseClient = createApiClient({ mode: "mock" });
  const fullEnvelope = await baseClient.getMacroToolkitAnalysis();
  const coreEnvelope: MacroToolkitAnalysisEnvelope = {
    ...fullEnvelope,
    result: {
      ...fullEnvelope.result,
      runtime_status: {
        analysis_scope: "core",
        deferred_sections: [
          { key: "capability_results", label: "功能结果", status: "deferred" },
          { key: "source_checks", label: "功能补齐方案", status: "deferred" },
        ],
      },
      capability_results: [],
    },
  };
  return { fullEnvelope, coreEnvelope };
}

describe("MacroObservationPage", () => {
  it("renders the read-only observation skeleton without operations controls", async () => {
    renderWorkbenchApp(["/macro-observation"]);

    const page = await screen.findByTestId("macro-observation-page");
    expect(page).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1, name: "宏观观察" })).toBeInTheDocument();
    expect(await screen.findByTestId("macro-observation-readonly-boundary")).toHaveTextContent(
      "只读宏观观察 · 本页只展示宏观分析证据；刷新、脚本执行和运营注册表保留在宏观工具页。",
    );
    const kpiBand = await screen.findByTestId("macro-observation-kpi-band");
    expect(kpiBand.querySelectorAll(".macro-observation-view__kpi-cell")).toHaveLength(6);
    expect(screen.getByRole("link", { name: "前往宏观工具页" })).toHaveAttribute(
      "href",
      "/macro-toolkit",
    );
    expect(screen.queryByRole("button", { name: /刷新结果/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /刷新注册表/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /运行选中脚本/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "脚本注册表" })).not.toBeInTheDocument();
  });

  it("promotes the decision summary with an explicit mock-basis flag", async () => {
    renderWorkbenchApp(["/macro-observation"]);

    const decisionSummary = await screen.findByTestId("macro-observation-decision-summary");
    // 决策摘要块在 loading 骨架期即渲染（空态文案），等待后端 mock 数据落地。
    await waitFor(() => expect(decisionSummary).toHaveTextContent("宏观决策摘要"));
    expect(decisionSummary).toHaveTextContent(/可用模块 \d+\/\d+/);
    const mockFlag = within(decisionSummary).getByTestId("macro-observation-decision-mock-flag");
    expect(mockFlag).toHaveTextContent("模拟口径");
  });

  it("ignores cached script registry payloads and never requests scripts", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const scriptEnvelope = await baseClient.getMacroToolkitScripts();
    const getMacroToolkitScripts = vi.fn(baseClient.getMacroToolkitScripts);
    const client = { ...baseClient, getMacroToolkitScripts } as ApiClient;
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(["macro-toolkit", "scripts"], scriptEnvelope);

    renderObservationPage(client, queryClient);

    await screen.findByTestId("macro-observation-decision-summary");
    expect(getMacroToolkitScripts).not.toHaveBeenCalled();
    expect(
      screen.queryByText(scriptEnvelope.result.scripts[0]?.name ?? ""),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "脚本注册表" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /运行选中脚本/ })).not.toBeInTheDocument();
  });

  it("keeps the loading skeleton read-only with the boundary anchor", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: () => new Promise<MacroToolkitAnalysisEnvelope>(() => {}),
      getMacroToolkitStrategySummaries: () => new Promise<never>(() => {}),
    } as ApiClient;

    renderObservationPage(client);

    expect(await screen.findByTestId("macro-observation-readonly-boundary")).toBeInTheDocument();
    expect(await screen.findByTestId("macro-observation-loading-note")).toHaveTextContent(
      "页面口径边界已就绪；观察结论和证据对照会在后端返回后自动补上。",
    );
    expect(screen.getByTestId("macro-observation-kpi-band")).toBeInTheDocument();
    expect(screen.getAllByText("观察证据加载中").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /刷新结果/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /运行选中脚本/ })).not.toBeInTheDocument();
  });

  it("keeps read failures readable without backend paths", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getMacroToolkitAnalysis: async () => {
        throw new Error("Request failed: /ui/macro/toolkit/analysis?detail=core (502)");
      },
      getMacroToolkitStrategySummaries: async () => {
        throw new Error("Request failed: /ui/macro/toolkit/analysis/strategy-summaries (502)");
      },
    } as ApiClient;

    renderObservationPage(client);

    const errorState = await screen.findByTestId("macro-observation-error-state");
    expect(errorState).toHaveTextContent("宏观观察暂不可用");
    expect(errorState).toHaveTextContent(
      "核心分析暂时没有返回；请稍后重试或打开宏观工具页查看诊断。",
    );
    expect(errorState).toHaveTextContent("读取核心分析失败");
    expect(errorState).toHaveTextContent("读取策略摘要失败");
    expect(errorState).not.toHaveTextContent("Request failed");
    expect(errorState).not.toHaveTextContent("/ui/macro/toolkit");
    expect(screen.getByTestId("macro-observation-readonly-boundary")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重试读取" })).toBeInTheDocument();
    expect(screen.queryByTestId("macro-observation-kpi-band")).not.toBeInTheDocument();
  });

  it("summarizes core deferred runtime and loads the full analysis on demand", async () => {
    const user = userEvent.setup();
    const { fullEnvelope, coreEnvelope } = await buildCoreDeferredEnvelope();
    const baseClient = createApiClient({ mode: "mock" });
    const getMacroToolkitAnalysis = vi.fn(
      (options?: Parameters<ApiClient["getMacroToolkitAnalysis"]>[0]) =>
        Promise.resolve(options?.detail === "full" ? fullEnvelope : coreEnvelope),
    );
    const client = { ...baseClient, getMacroToolkitAnalysis } as ApiClient;

    renderObservationPage(client);

    expect((await screen.findAllByText("2 项证据延后确认")).length).toBeGreaterThan(0);
    const fullAnalysisButton = await screen.findByRole("button", { name: "查看完整分析" });
    await user.click(fullAnalysisButton);

    await waitFor(() =>
      expect(getMacroToolkitAnalysis).toHaveBeenCalledWith(
        expect.objectContaining({ detail: "full" }),
      ),
    );
  });

  it("assembles the six numbered sections with standard leads", async () => {
    const client = createApiClient({ mode: "mock" });

    renderObservationPage(client);

    await screen.findByTestId("macro-observation-kpi-band");
    for (const title of [
      "当日观察结论",
      "信号与风险对照",
      "模型与策略证据",
      "危机分证据",
      "数据健康与修复项",
      "证据与口径",
    ]) {
      expect(screen.getByRole("heading", { level: 2, name: title })).toBeInTheDocument();
    }
    expect(document.querySelectorAll(".macro-observation-view__section")).toHaveLength(6);
    expect(screen.getByTestId("macro-observation-crisis-chart")).toBeInTheDocument();
  });
});
