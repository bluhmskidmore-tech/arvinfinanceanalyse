import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { CubeDimensionsPayload, CubeQueryResult, ResultMeta } from "../api/contracts";
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
      headerCells.map((th) => [th.textContent ?? "", (th as HTMLElement).style.textAlign]),
    );
    // 列级对齐判据：任意一行是数值（含字符串化 Decimal）即右对齐；维度列左对齐。
    expect(headerAligns.get("market_value")).toBe("right");
    expect(headerAligns.get("duration")).toBe("right");
    expect(headerAligns.get("rating")).not.toBe("right");

    // 数值单元格必须带等宽 tabular 栈（designSystem tabularNumsStyle）。
    const numericCell = screen.getByText("1,234.57").closest("td");
    expect(numericCell).not.toBeNull();
    expect(numericCell!.style.fontFamily).toContain("ui-monospace");
    const dimensionCell = screen.getByText("AA+").closest("td");
    expect(dimensionCell).not.toBeNull();
    expect(dimensionCell!.style.fontFamily).toBe("");

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
