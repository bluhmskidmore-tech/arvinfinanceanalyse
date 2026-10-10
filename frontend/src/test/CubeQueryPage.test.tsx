import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { CubeDimensionsPayload, CubeQueryResult, ResultMeta } from "../api/contracts";
import { ActionRequestError } from "../api/transport";
import CubeQueryPage from "../features/cube-query/pages/CubeQueryPage";

const resultMeta: ResultMeta = {
  trace_id: "tr_cube_test",
  basis: "formal",
  result_kind: "cube.query",
  formal_use_allowed: true,
  source_version: "sv_test",
  vendor_version: "vv_test",
  rule_version: "rv_test",
  cache_version: "cv_test",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  generated_at: "2026-04-13T00:00:00Z",
};

/** 与共享 mock 工厂 bond_analytics 元数据同值；测试内固化避免依赖 mock 组合链路。 */
function dimensionsPayload(): CubeDimensionsPayload {
  return {
    fact_table: "bond_analytics",
    dimensions: [
      "asset_class_std",
      "accounting_class",
      "tenor_bucket",
      "rating",
      "bond_type",
      "issuer_name",
      "industry_name",
      "portfolio_name",
      "cost_center",
    ],
    measures: ["sum", "avg", "count", "min", "max"],
    measure_fields: ["market_value", "duration"],
  };
}

function stubDimensions(client: ReturnType<typeof createApiClient>) {
  return vi.spyOn(client, "getCubeDimensions").mockResolvedValue(dimensionsPayload());
}

function renderCubePage(client: ReturnType<typeof createApiClient>) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <CubeQueryPage />
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

function sampleResult(overrides: Partial<CubeQueryResult> = {}): CubeQueryResult {
  return {
    report_date: "2025-12-31",
    fact_table: "bond_analytics",
    measures: ["sum(market_value)"],
    dimensions: ["rating"],
    rows: [{ rating: "AAA", market_value: 1234.5678 }],
    total_rows: 1,
    drill_paths: [],
    result_meta: resultMeta,
    ...overrides,
  };
}

describe("CubeQueryPage", () => {
  it("shows the new page result and metadata after pagination changes the request", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    stubDimensions(client);
    const exec = vi.spyOn(client, "executeCubeQuery")
      .mockResolvedValueOnce(sampleResult({ total_rows: 150 }))
      .mockResolvedValueOnce(sampleResult({ rows: [{ market_value: 7788 }], total_rows: 150,
        result_meta: { ...resultMeta, trace_id: "tr_page_two" } }));
    renderCubePage(client);
    await screen.findByText("asset_class_std");
    await user.click(screen.getByTestId("cube-execute"));
    await screen.findByText("1,234.57");
    await user.click(screen.getByTitle("2"));
    await waitFor(() => expect(exec).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 50, limit: 50 })));
    expect(await screen.findByText("7,788.00")).toBeInTheDocument();
    expect(screen.queryByText("1,234.57")).not.toBeInTheDocument();
    expect(screen.getByTestId("cube-result-meta")).toHaveTextContent("tr_page_two");
  });

  it("does not revive an obsolete response after changing away and back to the same fact table", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getCubeDimensions").mockImplementation(async (fact) => ({ ...dimensionsPayload(), fact_table: fact }));
    let resolveOld!: (value: CubeQueryResult) => void;
    const oldResponse = new Promise<CubeQueryResult>((resolve) => { resolveOld = resolve; });
    const exec = vi.spyOn(client, "executeCubeQuery").mockReturnValueOnce(oldResponse)
      .mockResolvedValueOnce(sampleResult({ rows: [{ market_value: 9988 }], result_meta: { ...resultMeta, trace_id: "tr_returned_config" } }));
    renderCubePage(client);
    await screen.findByText("asset_class_std");
    await user.click(screen.getByTestId("cube-execute"));
    await waitFor(() => expect(exec).toHaveBeenCalledTimes(1));
    for (const label of ["资产负债", "债券分析"]) {
      fireEvent.mouseDown(screen.getByTestId("cube-fact-select").querySelector(".ant-select-selector")!);
      await user.click(await screen.findByTitle(label));
    }
    await act(async () => { resolveOld(sampleResult()); await oldResponse; });
    expect(screen.queryByText("1,234.57")).not.toBeInTheDocument();
    expect(screen.queryByTestId("cube-result-meta")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("cube-execute"));
    expect(await screen.findByText("9,988.00")).toBeInTheDocument();
    expect(screen.getByTestId("cube-result-meta")).toHaveTextContent("tr_returned_config");
  });

  it("clears a completed result when its report date changes", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    stubDimensions(client);
    vi.spyOn(client, "executeCubeQuery").mockResolvedValue(sampleResult());
    renderCubePage(client);
    await screen.findByText("asset_class_std");
    await user.click(screen.getByTestId("cube-execute"));
    await screen.findByText("1,234.57");
    const date = screen.getByLabelText("cube-report-date");
    fireEvent.change(date, { target: { value: "2026-01-31" } });
    fireEvent.keyDown(date, { key: "Enter", code: "Enter" });
    await waitFor(() => expect(date).toHaveValue("2026-01-31"));
    await waitFor(() => expect(screen.queryByTestId("cube-result-meta")).not.toBeInTheDocument());
    expect(screen.queryByText("1,234.57")).not.toBeInTheDocument();
  });

  it("keeps a drill response current when the drill also changes the filter configuration", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    stubDimensions(client);
    const exec = vi.spyOn(client, "executeCubeQuery")
      .mockResolvedValueOnce(sampleResult({ drill_paths: [{ dimension: "rating", label: "评级", available_values: ["AA+"], current_filter: [] }] }))
      .mockResolvedValueOnce(sampleResult({ rows: [{ rating: "AA+", market_value: 333 }] }));
    renderCubePage(client);
    await screen.findByText("asset_class_std");
    await user.click(screen.getByTestId("cube-execute"));
    await screen.findByText("1,234.57");
    await user.click(screen.getByText("评级 (rating)"));
    await user.click(await screen.findByText("AA+"));
    await waitFor(() => expect(exec).toHaveBeenLastCalledWith(expect.objectContaining({ filters: { rating: ["AA+"] }, offset: 0 })));
    expect(await screen.findByText("333.00")).toBeInTheDocument();
    expect(screen.getByTestId("cube-result-meta")).toBeInTheDocument();
  });

  it("does not show a late response when the selected dimensions have changed", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    stubDimensions(client);
    let resolveOld!: (value: CubeQueryResult) => void;
    const oldResponse = new Promise<CubeQueryResult>((resolve) => { resolveOld = resolve; });
    const exec = vi.spyOn(client, "executeCubeQuery").mockReturnValue(oldResponse);
    renderCubePage(client);
    await screen.findByText("asset_class_std");
    await user.click(screen.getByTestId("cube-execute"));
    await waitFor(() => expect(exec).toHaveBeenCalledTimes(1));
    await user.click(screen.getByText("rating"));
    await act(async () => { resolveOld(sampleResult()); await oldResponse; });
    await waitFor(() => expect(screen.getByTestId("cube-execute")).not.toHaveClass("ant-btn-loading"));
    expect(screen.queryByText("1,234.57")).not.toBeInTheDocument();
    expect(screen.queryByTestId("cube-result-meta")).not.toBeInTheDocument();
  });

  it("discards an old response after changing fact tables and allows the new query immediately", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getCubeDimensions").mockImplementation(async (fact) => ({ ...dimensionsPayload(), fact_table: fact }));
    let resolveOld!: (value: CubeQueryResult) => void;
    const oldResponse = new Promise<CubeQueryResult>((resolve) => { resolveOld = resolve; });
    const exec = vi.spyOn(client, "executeCubeQuery").mockReturnValueOnce(oldResponse).mockResolvedValueOnce(sampleResult({
      fact_table: "balance", rows: [{ market_value: 222 }],
      result_meta: { ...resultMeta, trace_id: "tr_current_balance" },
    }));
    renderCubePage(client);
    await screen.findByText("asset_class_std");
    await user.click(screen.getByTestId("cube-execute"));
    await waitFor(() => expect(exec).toHaveBeenCalledTimes(1));
    fireEvent.mouseDown(screen.getByTestId("cube-fact-select").querySelector(".ant-select-selector")!);
    await user.click(await screen.findByTitle("资产负债"));
    await screen.findByTestId("cube-analytical-only");
    await user.click(screen.getByTestId("cube-execute"));
    await waitFor(() => expect(exec).toHaveBeenCalledTimes(2));
    await screen.findByText("222.00");
    await act(async () => { resolveOld(sampleResult()); await oldResponse; });
    expect(screen.queryByText("1,234.57")).not.toBeInTheDocument();
    expect(screen.getByText("222.00")).toBeInTheDocument();
    expect(screen.getByTestId("cube-result-meta")).toHaveTextContent("tr_current_balance");
  });

  it("invalidates a pending response when dimensions change and the old response later fails", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    stubDimensions(client);
    let rejectOld!: (reason: Error) => void;
    const oldResponse = new Promise<CubeQueryResult>((_, reject) => { rejectOld = reject; });
    const exec = vi.spyOn(client, "executeCubeQuery").mockReturnValue(oldResponse);
    renderCubePage(client);
    await screen.findByText("asset_class_std");
    await user.click(screen.getByTestId("cube-execute"));
    await waitFor(() => expect(exec).toHaveBeenCalledTimes(1));
    await user.click(screen.getByText("rating"));
    await act(async () => { rejectOld(new Error("obsolete request failed")); await oldResponse.catch(() => undefined); });
    await waitFor(() => expect(screen.getByTestId("cube-execute")).not.toHaveClass("ant-btn-loading"));
    expect(screen.queryByTestId("cube-query-error")).not.toBeInTheDocument();
    expect(screen.queryByTestId("cube-result-meta")).not.toBeInTheDocument();
  });

  it("submits balance with an explicit CNY filter and analytical-only disclosure", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getCubeDimensions").mockImplementation(async (fact) => fact === "balance" ? {
      fact_table: fact, dimensions: ["currency_basis", "rating"], measures: ["sum"],
      measure_fields: ["market_value"], required_filters: { currency_basis: ["CNY"] }, analytical_only: true,
    } : dimensionsPayload());
    const execSpy = vi.spyOn(client, "executeCubeQuery").mockResolvedValue(sampleResult({
      fact_table: "balance", rows: [{ market_value: "100.00000000" }], dimensions: [],
      result_meta: { ...resultMeta, basis: "analytical", formal_use_allowed: false, filters_applied: { currency_basis: ["CNY"] } },
    }));
    renderCubePage(client);
    await screen.findByText("asset_class_std");
    fireEvent.mouseDown(screen.getByTestId("cube-fact-select").querySelector(".ant-select-selector")!);
    await user.click(await screen.findByTitle("资产负债"));
    expect(await screen.findByTestId("cube-analytical-only")).toHaveTextContent("不能正式使用");
    await screen.findByText("折人民币（CNY）");
    await user.click(screen.getByTestId("cube-execute"));
    await waitFor(() => expect(execSpy).toHaveBeenCalledWith(expect.objectContaining({
      fact_table: "balance", basis: "analytical", filters: { currency_basis: ["CNY"] },
    })));
    expect(await screen.findByText("100.00")).toBeInTheDocument();
    expect(screen.getByTestId("cube-result-meta")).toHaveTextContent('实际筛选={"currency_basis":["CNY"]}');
  });

  it("requires one category and submits a single selected period without parent-child aggregation", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getCubeDimensions").mockImplementation(async (fact) => fact === "product_category" ? {
      fact_table: fact, dimensions: ["category_id", "view", "side"], measures: ["sum"],
      measure_fields: ["business_net_income"],
      required_filters: { view: ["monthly", "qtd"], category_id: ["bond_investment", "bond_ac"] }, analytical_only: true,
    } : dimensionsPayload());
    const execSpy = vi.spyOn(client, "executeCubeQuery").mockResolvedValue(sampleResult({ rows: [{ business_net_income: "10.00000000" }] }));
    renderCubePage(client);
    await screen.findByText("asset_class_std");
    fireEvent.mouseDown(screen.getByTestId("cube-fact-select").querySelector(".ant-select-selector")!);
    await user.click(await screen.findByTitle("产品类别"));
    await screen.findByRole("combobox", { name: "cube-product-category" });
    await user.click(screen.getByTestId("cube-execute"));
    expect(await screen.findByTestId("cube-config-validation-error")).toHaveTextContent("请选择一个产品类别");
    expect(execSpy).not.toHaveBeenCalled();
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "cube-product-category" }));
    await user.click(await screen.findByTitle("bond_investment"));
    await user.click(screen.getByTestId("cube-execute"));
    await waitFor(() => expect(execSpy).toHaveBeenCalledWith(expect.objectContaining({
      fact_table: "product_category", basis: "analytical", measures: ["sum(business_net_income)"],
      filters: { view: ["monthly"], category_id: ["bond_investment"] },
    })));
  });

  it("clears the previous result when a subsequent query fails", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    stubDimensions(client);
    vi.spyOn(client, "executeCubeQuery").mockResolvedValueOnce(sampleResult()).mockRejectedValueOnce(new Error("storage unavailable"));
    renderCubePage(client);
    await screen.findByText("asset_class_std");
    await user.click(screen.getByTestId("cube-execute"));
    await screen.findByText("1,234.57");
    await user.click(screen.getByTestId("cube-execute"));
    await screen.findByTestId("cube-query-error");
    expect(screen.queryByText("1,234.57")).not.toBeInTheDocument();
    expect(screen.queryByTestId("cube-result-meta")).not.toBeInTheDocument();
  });

  it("shows fact table selector on mount and loads dimensions for bond_analytics", async () => {
    const client = createApiClient({ mode: "mock" });
    const dimSpy = stubDimensions(client);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CubeQueryPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("cube-fact-select")).toBeInTheDocument();
    await waitFor(() => {
      expect(dimSpy).toHaveBeenCalledWith("bond_analytics");
    });
    expect(await screen.findByText("asset_class_std")).toBeInTheDocument();
  });

  it("calls executeCubeQuery and shows results table after run", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    stubDimensions(client);
    const execSpy = vi.spyOn(client, "executeCubeQuery");
    const sample: CubeQueryResult = {
      report_date: "2025-12-31",
      fact_table: "bond_analytics",
      measures: ["sum(market_value)"],
      dimensions: ["rating"],
      rows: [{ rating: "AAA", market_value: 1234.5678 }],
      total_rows: 1,
      drill_paths: [],
      result_meta: resultMeta,
    };
    execSpy.mockResolvedValue(sample);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CubeQueryPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await screen.findByText("asset_class_std");
    const rating = screen.getByText("rating");
    const group = rating.closest(".ant-checkbox-group");
    expect(group).toBeTruthy();
    await user.click(within(group as HTMLElement).getByText("rating"));

    await user.click(screen.getByTestId("cube-execute"));

    await waitFor(() => {
      expect(execSpy).toHaveBeenCalled();
    });

    const firstCall = execSpy.mock.calls[0]![0];
    expect(firstCall.fact_table).toBe("bond_analytics");
    expect(firstCall.basis).toBe("formal");
    expect(firstCall.measures).toContain("sum(market_value)");

    expect(await screen.findByTestId("cube-results-table")).toBeInTheDocument();
    expect(await screen.findByText("1,234.57")).toBeInTheDocument();
    const meta = await screen.findByTestId("cube-result-meta");
    expect(meta).toHaveTextContent("tr_cube_test");
    expect(meta).toHaveTextContent("sv_test");
    expect(meta).toHaveTextContent("正常");
    const metaLines = [...meta.querySelectorAll(".ant-typography")].map((el) => el.textContent ?? "");
    expect(metaLines.length).toBeGreaterThanOrEqual(1);
    for (const line of metaLines) {
      expect((line.match(/·/g) ?? []).length).toBeLessThanOrEqual(1);
    }
  });

  it("passes whitelisted filter dimensions and typed values through to the request", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    stubDimensions(client);
    const execSpy = vi.spyOn(client, "executeCubeQuery").mockResolvedValue(sampleResult());

    renderCubePage(client);
    await screen.findByText("asset_class_std");

    await user.click(screen.getByRole("button", { name: "添加条件" }));
    const dimensionSelect = await screen.findByTestId("cube-filter-dimension");
    fireEvent.mouseDown(dimensionSelect.querySelector(".ant-select-selector")!);
    await user.click(await screen.findByTitle("rating"));

    const valuesSelect = screen.getByTestId("cube-filter-values");
    await user.type(valuesSelect.querySelector("input")!, "AAA{enter}");

    await user.click(screen.getByTestId("cube-execute"));

    await waitFor(() => {
      expect(execSpy).toHaveBeenCalled();
    });
    const request = execSpy.mock.calls[0]![0];
    expect(request.filters).toEqual({ rating: ["AAA"] });
    expect(request.measures).toEqual(["sum(market_value)"]);
    expect(request.basis).toBe("formal");
    expect(request.limit).toBe(50);
    expect(request.offset).toBe(0);
    expect(screen.queryByTestId("cube-config-validation-error")).not.toBeInTheDocument();
  });

  it("rejects filter values without a selected dimension via an in-page error surface", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    stubDimensions(client);
    const execSpy = vi.spyOn(client, "executeCubeQuery");

    renderCubePage(client);
    await screen.findByText("asset_class_std");

    await user.click(screen.getByRole("button", { name: "添加条件" }));
    const valuesSelect = await screen.findByTestId("cube-filter-values");
    await user.type(valuesSelect.querySelector("input")!, "AAA{enter}");

    await user.click(screen.getByTestId("cube-execute"));

    const surface = await screen.findByTestId("cube-config-validation-error");
    expect(surface).toHaveTextContent("查询配置未通过校验，已阻止提交");
    expect(surface).toHaveTextContent("第 1 个筛选条件已填写取值但未选择维度");
    expect(execSpy).not.toHaveBeenCalled();
  });

  it("renders an in-page error surface when the query fails and recovers on retry", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    stubDimensions(client);
    const execSpy = vi
      .spyOn(client, "executeCubeQuery")
      .mockRejectedValueOnce(new Error("cube backend unavailable"))
      .mockResolvedValueOnce(sampleResult());

    renderCubePage(client);
    await screen.findByText("asset_class_std");

    await user.click(screen.getByTestId("cube-execute"));

    const errorSurface = await screen.findByTestId("cube-query-error");
    expect(errorSurface).toHaveTextContent("查询执行失败");
    expect(errorSurface).toHaveTextContent("cube backend unavailable");

    await user.click(within(errorSurface).getByRole("button", { name: /重\s*试/ }));

    expect(await screen.findByText("1,234.57")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByTestId("cube-query-error")).not.toBeInTheDocument();
    });
    expect(execSpy).toHaveBeenCalledTimes(2);
  });

  it("names the RBAC boundary when the dimension catalog returns 403 instead of asking to retry", async () => {
    // 2026-09-02 走查：默认 viewer 身份下 /api/cube/dimensions/* 一律 403，页面曾把它说成「稍后重试」。
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getCubeDimensions").mockRejectedValue(
      new ActionRequestError("Request failed: /api/cube/dimensions/bond_analytics (403)", { status: 403 }),
    );

    renderCubePage(client);

    const errorSurface = await screen.findByTestId("cube-dimensions-error");
    expect(errorSurface).toHaveTextContent("当前角色无权访问自助查询");
    expect(errorSurface).toHaveTextContent("403");
    expect(errorSurface).not.toHaveTextContent("稍后重试");
  });

  it("keeps the generic retry copy for non-permission dimension failures", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getCubeDimensions").mockRejectedValue(
      new ActionRequestError("Request failed: /api/cube/dimensions/bond_analytics (503)", { status: 503 }),
    );

    renderCubePage(client);

    const errorSurface = await screen.findByTestId("cube-dimensions-error");
    expect(errorSurface).toHaveTextContent("维度加载失败");
    expect(errorSurface).toHaveTextContent("稍后重试");
  });

  it("fixes numeric typography: two decimals, column-level alignment and tabular-nums cells", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    stubDimensions(client);
    vi.spyOn(client, "executeCubeQuery").mockResolvedValue(
      sampleResult({
        measures: ["sum(market_value)", "avg(duration)"],
        dimensions: ["rating"],
        rows: [
          // 首行 market_value 为 null、duration 为字符串化 Decimal：
          // 旧实现按首行 typeof 判对齐会把两列都判成左对齐。
          { rating: "AAA", market_value: null, duration: "2.5" },
          { rating: "AA+", market_value: 1234.5678, duration: "3.25" },
        ],
        total_rows: 2,
      }),
    );

    renderCubePage(client);
    await screen.findByText("asset_class_std");
    await user.click(screen.getByTestId("cube-execute"));

    // 固定两位小数：同列不再出现 2 位与 4 位混排；字符串 Decimal 也归一。
    expect(await screen.findByText("1,234.57")).toBeInTheDocument();
    expect(screen.getByText("2.50")).toBeInTheDocument();
    expect(screen.getByText("3.25")).toBeInTheDocument();

    const table = screen.getByTestId("cube-results-table");
    const headerCells = [...table.querySelectorAll("thead th")];
    const headerAligns = new Map(
      headerCells.map((th) => [th.textContent ?? "", th.getAttribute("data-align")]),
    );
    // 列级对齐判据：任意一行是数值（含字符串化 Decimal）即右对齐；维度列左对齐。
    // 迁移到 DataTable 原语后，对齐 + 等宽 tabular 由 `data-align="numeric"`
    // 这一个 CSS 钩子统一承担（DataTable.module.css 已在原语自身的测试里锁死
    // font-family/tabular-nums 的声明），页面测试改为断言这个契约属性，
    // 不再断言 antd 生成的内联 style（迁移前 align="right" 由 antd 写成
    // style.textAlign，onCell 回调写成 style.fontFamily，二者已随 antd 依赖
    // 一起移除）。
    expect(headerAligns.get("market_value")).toBe("numeric");
    expect(headerAligns.get("duration")).toBe("numeric");
    expect(headerAligns.get("rating")).not.toBe("numeric");

    const numericCell = screen.getByText("1,234.57").closest("td");
    expect(numericCell).not.toBeNull();
    expect(numericCell!.getAttribute("data-align")).toBe("numeric");
    const dimensionCell = screen.getByText("AA+").closest("td");
    expect(dimensionCell).not.toBeNull();
    expect(dimensionCell!.getAttribute("data-align")).not.toBe("numeric");

    // null 缺值仍走 EM_DASH 占位（列内两处：market_value 首行）。
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });

  it("bounds pagination parameters: page-size options stop at 200 and offsets follow the page", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    stubDimensions(client);
    const execSpy = vi
      .spyOn(client, "executeCubeQuery")
      .mockResolvedValue(sampleResult({ total_rows: 1000 }));

    renderCubePage(client);
    await screen.findByText("asset_class_std");

    await user.click(screen.getByTestId("cube-execute"));
    expect(await screen.findByText("1,234.57")).toBeInTheDocument();

    // 翻到第 2 页：offset 跟随 page 推进且 limit 不变。
    await user.click(screen.getByTitle("2"));
    await waitFor(() => {
      const request = execSpy.mock.calls.at(-1)![0];
      expect(request.limit).toBe(50);
      expect(request.offset).toBe(50);
    });

    // 每页行数选项存在硬上限 200，不提供更大档位。
    const sizeChanger = document.querySelector(".ant-pagination-options-size-changer");
    expect(sizeChanger).not.toBeNull();
    fireEvent.mouseDown(sizeChanger!.querySelector(".ant-select-selector")!);
    await waitFor(() => {
      expect(document.querySelectorAll(".ant-select-item-option").length).toBeGreaterThan(0);
    });
    const sizeOptions = [...document.querySelectorAll(".ant-select-item-option")];
    const sizes = sizeOptions
      .map((el) => Number.parseInt(el.textContent ?? "", 10))
      .filter((n) => Number.isFinite(n));
    expect(Math.max(...sizes)).toBe(200);

    const maxOption = sizeOptions.find(
      (el) => Number.parseInt(el.textContent ?? "", 10) === 200,
    );
    expect(maxOption).toBeTruthy();
    await user.click(maxOption!);
    await waitFor(() => {
      const request = execSpy.mock.calls.at(-1)![0];
      expect(request.limit).toBe(200);
      expect(request.offset).toBeLessThanOrEqual(800);
      // offset 缺省视为 -1，保证与 200 对齐的断言在 undefined 时同样失败。
      expect((request.offset ?? -1) % 200).toBe(0);
    });
  });
});
