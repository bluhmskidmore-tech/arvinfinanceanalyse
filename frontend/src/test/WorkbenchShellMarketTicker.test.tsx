import { act, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ApiClientProvider, createDeferredApiClient, type ApiClient } from "../api/clientContext";
import type { ChoiceMacroLatestPoint } from "../api/contracts";
import { WorkbenchShellMarketTicker } from "../layouts/WorkbenchShellMarketTicker";

const realPoint: ChoiceMacroLatestPoint = {
  series_id: "E1000180",
  series_name: "中债国债到期收益率:10年",
  trade_date: "2026-01-10",
  value_numeric: 1.88,
  unit: "%",
  source_version: "sv_ticker_test",
  vendor_version: "vv_ticker_test",
  latest_change: -0.02,
};

const queryClients: QueryClient[] = [];

function renderTicker(client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  queryClients.push(queryClient);
  render(
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        <WorkbenchShellMarketTicker />
      </QueryClientProvider>
    </ApiClientProvider>,
  );
  return queryClient;
}

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function expectNoTickerValues() {
  const ticker = screen.getByTestId("workbench-market-ticker");
  expect(ticker.querySelector("strong")).toBeNull();
  expect(within(ticker).queryByText("演示")).not.toBeInTheDocument();
}

afterEach(() => {
  queryClients.splice(0).forEach((client) => client.clear());
  vi.unstubAllEnvs();
});

describe.each([
  { label: "development real", production: false },
  { label: "production real", production: true },
])("WorkbenchShellMarketTicker in $label mode", ({ production }) => {
  beforeEach(() => {
    vi.stubEnv("PROD", production);
    vi.stubEnv("VITE_DATA_SOURCE", "real");
  });

  it("shows loading without sample ticker values before the real request completes", async () => {
    let finishRequest!: (response: Response) => void;
    const fetchImpl = vi.fn<typeof fetch>(() => new Promise<Response>((resolve) => {
      finishRequest = resolve;
    }));
    renderTicker(createDeferredApiClient({ fetchImpl }));

    expectNoTickerValues();
    expect(screen.getByRole("status")).toHaveTextContent("行情加载中");
    expect(screen.getByTestId("workbench-market-ticker")).toHaveAttribute("data-market-ticker-state", "loading");
    await waitFor(() => expect(fetchImpl).toHaveBeenCalledOnce());
    expect(fetchImpl.mock.calls[0][0]).toBe("/ui/macro/choice-series/latest");

    await act(async () => finishRequest(jsonResponse({ result: { series: [] } })));
    expect(await screen.findByText("暂无可用行情")).toBeInTheDocument();
    expectNoTickerValues();
  });

  it("discloses a failed real request without sample ticker values", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockRejectedValue(new Error("ticker unavailable"));
    const queryClient = renderTicker(createDeferredApiClient({ fetchImpl }));

    await waitFor(() => expect(queryClient.getQueryState(["workbench-shell", "choice-macro-latest", "real"])?.status).toBe("error"));
    await waitFor(expectNoTickerValues);
    expect(await screen.findByText("行情加载失败")).toBeInTheDocument();
    expect(screen.getByTestId("workbench-market-ticker")).toHaveAttribute("data-market-ticker-state", "unavailable");
  });

  it.each([
    { label: "missing result", body: {} },
    { label: "empty series", body: { result: { series: [] } } },
    {
      label: "unmatched series",
      body: { result: { series: [{ ...realPoint, series_id: "OTHER", series_name: "其他序列" }] } },
    },
    {
      label: "matched null value",
      body: { result: { series: [{ ...realPoint, value_numeric: null }] } },
    },
  ])("shows no-data without sample ticker values for $label", async ({ body }) => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(body));
    const queryClient = renderTicker(createDeferredApiClient({ fetchImpl }));

    await waitFor(() => expect(queryClient.getQueryState(["workbench-shell", "choice-macro-latest", "real"])?.status).toBe("success"));
    await waitFor(expectNoTickerValues);
    expect(await screen.findByText("暂无可用行情")).toBeInTheDocument();
    expect(screen.getByTestId("workbench-market-ticker")).toHaveAttribute("data-market-ticker-state", "empty");
  });

  it("renders only the available real sequence without filling missing concepts with samples", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({ result: { series: [realPoint] } }),
    );
    renderTicker(createDeferredApiClient({ fetchImpl }));

    const ticker = screen.getByTestId("workbench-market-ticker");
    expect(await within(ticker).findByText("1.88%")).toBeInTheDocument();
    expect(ticker).toHaveAttribute("data-market-ticker-state", "ready");
    expect(ticker.querySelectorAll("strong")).toHaveLength(1);
    expect(ticker).toHaveTextContent("10年国债");
    expect(ticker).toHaveTextContent("-2bp");
    expect(within(ticker).getByText("1.88%")).toHaveAttribute("title", "数据日期 2026-01-10");
    expect(ticker).not.toHaveTextContent("DR007");
    expect(ticker).not.toHaveTextContent("美元/人民币");
    expect(within(ticker).queryByText("演示")).not.toBeInTheDocument();
  });

  it("keeps a valid zero reading when an earlier matching reading is unavailable", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({ result: { series: [
        { ...realPoint, value_numeric: null },
        { ...realPoint, value_numeric: 0, latest_change: 0 },
      ] } }),
    );
    renderTicker(createDeferredApiClient({ fetchImpl }));

    const ticker = screen.getByTestId("workbench-market-ticker");
    expect(await within(ticker).findByText("0%")).toBeInTheDocument();
    expect(ticker.querySelectorAll("strong")).toHaveLength(1);
    expect(ticker).toHaveTextContent("持平");
  });

  it("discloses a failed refresh while retaining the last successful real values", async () => {
    const fetchImpl = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ result: { series: [realPoint] } }))
      .mockRejectedValueOnce(new Error("ticker refresh unavailable"));
    const queryClient = renderTicker(createDeferredApiClient({ fetchImpl }));
    expect(await screen.findByText("1.88%")).toBeInTheDocument();

    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: ["workbench-shell", "choice-macro-latest", "real"] });
    });

    expect(await screen.findByText("行情更新失败，显示上次结果")).toBeInTheDocument();
    expect(screen.getByTestId("workbench-market-ticker")).toHaveAttribute("data-market-ticker-state", "stale");
    expect(screen.getByText("1.88%")).toBeInTheDocument();
    expect(screen.getByTestId("workbench-market-ticker").querySelectorAll("strong")).toHaveLength(1);
    expect(screen.queryByText("演示")).not.toBeInTheDocument();
  });
});

it("uses the existing explicit mock client for demo values", async () => {
  vi.stubEnv("PROD", false);
  vi.stubEnv("VITE_DATA_SOURCE", "mock");
  renderTicker(createDeferredApiClient());

  const ticker = screen.getByTestId("workbench-market-ticker");
  expect(await within(ticker).findByText("2.31%")).toBeInTheDocument();
  expect(within(ticker).getByText("演示")).toBeInTheDocument();
  expect(ticker).toHaveTextContent("DR007");
  expect(ticker).toHaveTextContent("7.14");
  expect(ticker).not.toHaveTextContent("1.94%");
});
