import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { ApiClientProvider, createDeferredApiClient, useApiClient } from "../api/clientContext";
import { getApiClientFactoryRecord } from "../api/clientFactoryOptions";
import { SYSTEM_READ_GENERATION_HEADER } from "../api/systemReadGeneration";
import { SystemReadGenerationBoundary } from "../router/SystemReadGenerationBoundary";
import { useSystemReadInteraction } from "../router/systemReadInteractionContext";

function envelope(result: unknown) {
  return { result, result_meta: {} };
}

function jsonResponse(payload: unknown, generation?: string) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      ...(generation ? { [SYSTEM_READ_GENERATION_HEADER]: generation } : {}),
    },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function QueryProbe() {
  const client = useApiClient();
  const interaction = useSystemReadInteraction();
  const riskDates = useQuery({
    queryKey: ["system-read-test", "risk-dates"],
    queryFn: () => client.getRiskTensorDates(),
  });
  const balanceDates = useQuery({
    queryKey: ["system-read-test", "balance-dates"],
    queryFn: () => client.getBalanceAnalysisDates(),
  });

  return (
    <section>
      <output data-testid="interaction-generation">{interaction.generation ?? "disabled"}</output>
      <output data-testid="risk-generation">
        {(riskDates.data?.result as { generation?: string } | undefined)?.generation ?? "loading"}
      </output>
      <output data-testid="balance-generation">
        {(balanceDates.data?.result as { generation?: string } | undefined)?.generation ?? "loading"}
      </output>
      <button type="button" onClick={interaction.refresh}>刷新交互</button>
    </section>
  );
}

function renderBoundary(client: ReturnType<typeof createApiClient>) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter>
      <ApiClientProvider client={client}>
        <QueryClientProvider client={queryClient}>
          <SystemReadGenerationBoundary>
            <QueryProbe />
          </SystemReadGenerationBoundary>
        </QueryClientProvider>
      </ApiClientProvider>
    </MemoryRouter>,
  );
}

function NavigationProbe({ onRead }: { onRead: (path: string) => void }) {
  const location = useLocation();
  const navigate = useNavigate();
  const client = useApiClient();
  useQuery({
    queryKey: ["navigation-read", location.pathname],
    queryFn: () => {
      onRead(location.pathname);
      return client.getRiskTensorDates();
    },
  });
  return <button onClick={() => navigate("/risk-tensor")}>下一页面</button>;
}

function ReturnNavigationProbe() {
  const location = useLocation();
  const navigate = useNavigate();
  return <>
    <QueryProbe />
    <button onClick={() => navigate(location.pathname === "/" ? "/risk-tensor" : "/")}>
      切换页面
    </button>
  </>;
}

function ReportDateProbe() {
  const [searchParams] = useSearchParams();
  const client = useApiClient();
  const interaction = useSystemReadInteraction();
  const reportDate = searchParams.get("report_date") ?? "2026-08-31";
  const [note, setNote] = useState("");
  const [initialAsOfDate] = useState(() => searchParams.get("as_of_date") ?? "");
  const [initialReportDate] = useState(() => searchParams.get("report_date") ?? "latest");
  const query = useQuery({
    queryKey: ["report-date-read", reportDate],
    queryFn: () => client.getRiskTensor(reportDate),
  });
  return (
    <section>
      <input aria-label="页面备注" value={note} onChange={(event) => setNote(event.target.value)} />
      <output data-testid="report-date">{query.data?.result.report_date ?? "loading"}</output>
      <output data-testid="interaction-generation">{interaction.generation ?? "disabled"}</output>
      <output data-testid="initial-as-of-date">{initialAsOfDate}</output>
      <output data-testid="initial-report-date">{initialReportDate}</output>
    </section>
  );
}

function FilterNavigationControls() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <nav>
      <button onClick={() => navigate("?report_date=2026-09-30", { replace: true })}>下一报告日</button>
      <button onClick={() => navigate("?report_date=2026-08-31", { replace: true })}>上一报告日</button>
      <button onClick={() => navigate({ pathname: location.pathname, search: "" })}>清除报告日</button>
      <button onClick={() => navigate({ ...location, hash: "#details" })}>页面锚点</button>
      <button onClick={() => navigate(location)}>相同网址</button>
      <button onClick={() => navigate("?year=2025&as_of_date=2025-12-31")}>新初始参数</button>
      <button onClick={() => navigate("/risk-tensor")}>下一页面</button>
    </nav>
  );
}

function renderReportDateBoundary(fetchImpl: typeof fetch, initialEntry = "/?report_date=2026-08-31") {
  const client = createApiClient({ mode: "real", fetchImpl });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 60_000 } },
  });
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <ApiClientProvider client={client}>
        <QueryClientProvider client={queryClient}>
          <FilterNavigationControls />
          <SystemReadGenerationBoundary><ReportDateProbe /></SystemReadGenerationBoundary>
        </QueryClientProvider>
      </ApiClientProvider>
    </MemoryRouter>,
  );
}

describe("SystemReadGenerationBoundary", () => {
  it.each(["/", "/dashboard"])("preserves %s and its fixed generation while changing report_date, with separate date caches", async (path) => {
    let publishedGeneration = "full-gen-a";
    let handshakes = 0;
    const nextDate = deferred<Response>();
    const requests: Array<{ date: string | null; generation: string | null }> = [];
    const fetchImpl = vi.fn<typeof fetch>(async (input, init) => {
      const url = new URL(String(input), "http://moss.local");
      if (url.pathname === "/api/system-read-publication") {
        handshakes += 1;
        return jsonResponse({
          enabled: true, generation: publishedGeneration, coverage_dates: {},
        }, publishedGeneration);
      }
      const date = url.searchParams.get("report_date");
      const generation = new Headers(init?.headers).get(SYSTEM_READ_GENERATION_HEADER);
      requests.push({ date, generation });
      if (date === "2026-09-30") return nextDate.promise;
      return jsonResponse(envelope({ report_date: date }), generation ?? undefined);
    });
    renderReportDateBoundary(fetchImpl, `${path}?report_date=2026-08-31`);
    await waitFor(() => expect(screen.getByTestId("report-date")).toHaveTextContent("2026-08-31"));
    const note = screen.getByRole("textbox", { name: "页面备注" });
    fireEvent.change(note, { target: { value: "保留筛选上下文" } });

    // Publication changes while this page remains a fixed interaction.
    publishedGeneration = "full-gen-b";
    fireEvent.click(screen.getByRole("button", { name: "下一报告日" }));
    expect(screen.getByRole("textbox", { name: "页面备注" })).toBe(note);
    expect(note).toHaveValue("保留筛选上下文");
    expect(screen.queryByText("页面加载中")).not.toBeInTheDocument();
    expect(screen.getByTestId("interaction-generation")).toHaveTextContent("full-gen-a");
    expect(screen.getByTestId("report-date")).toHaveTextContent("loading");
    await waitFor(() => expect(requests).toHaveLength(2));
    expect(handshakes).toBe(1);
    expect(requests).toEqual([
      { date: "2026-08-31", generation: "full-gen-a" },
      { date: "2026-09-30", generation: "full-gen-a" },
    ]);

    nextDate.resolve(jsonResponse(envelope({ report_date: "2026-09-30" }), "full-gen-a"));
    await waitFor(() => expect(screen.getByTestId("report-date")).toHaveTextContent("2026-09-30"));
    fireEvent.click(screen.getByRole("button", { name: "上一报告日" }));
    expect(screen.getByTestId("report-date")).toHaveTextContent("2026-08-31");
    expect(screen.getByRole("textbox", { name: "页面备注" })).toBe(note);
    expect(handshakes).toBe(1);
    expect(requests).toHaveLength(2);
  });

  it("preserves the page on hash changes and navigation to the same URL", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async (input) => {
      if (String(input).endsWith("/api/system-read-publication")) {
        return jsonResponse({ enabled: true, generation: "full-gen-a", coverage_dates: {} }, "full-gen-a");
      }
      return jsonResponse(envelope({ report_date: "2026-08-31" }), "full-gen-a");
    });
    renderReportDateBoundary(fetchImpl);
    await waitFor(() => expect(screen.getByTestId("report-date")).toHaveTextContent("2026-08-31"));
    const note = screen.getByRole("textbox", { name: "页面备注" });
    fireEvent.change(note, { target: { value: "保留页面状态" } });

    for (const name of ["页面锚点", "相同网址"]) {
      fireEvent.click(screen.getByRole("button", { name }));
      expect(screen.getByRole("textbox", { name: "页面备注" })).toBe(note);
      expect(note).toHaveValue("保留页面状态");
      expect(screen.queryByText("页面加载中")).not.toBeInTheDocument();
    }
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it.each([
    ["/balance-analysis", "下一报告日", "2026-09-30"],
    ["/balance-analysis", "清除报告日", "latest"],
    ["/bond-analysis", "下一报告日", "2026-09-30"],
    ["/bond-analysis", "清除报告日", "latest"],
  ])("reopens %s after %s so local report-date state is initialized again", async (path, action, expectedDate) => {
    let handshakes = 0;
    const nextHandshake = deferred<Response>();
    const fetchImpl = vi.fn<typeof fetch>(async (input, init) => {
      const url = new URL(String(input), "http://moss.local");
      if (url.pathname === "/api/system-read-publication") {
        handshakes += 1;
        if (handshakes > 1) return nextHandshake.promise;
        return jsonResponse({ enabled: true, generation: "full-gen-a", coverage_dates: {} }, "full-gen-a");
      }
      const generation = new Headers(init?.headers).get(SYSTEM_READ_GENERATION_HEADER);
      return jsonResponse(envelope({
        report_date: url.searchParams.get("report_date"),
      }), generation ?? undefined);
    });
    renderReportDateBoundary(fetchImpl, `${path}?report_date=2026-08-31`);
    await waitFor(() => expect(screen.getByTestId("report-date")).toHaveTextContent("2026-08-31"));
    const previousNote = screen.getByRole("textbox", { name: "页面备注" });
    fireEvent.change(previousNote, { target: { value: "旧页面状态" } });
    fireEvent.click(screen.getByRole("button", { name: action }));

    expect(screen.queryByRole("textbox", { name: "页面备注" })).not.toBeInTheDocument();
    expect(handshakes).toBe(2);
    expect(fetchImpl).toHaveBeenCalledTimes(3);
    nextHandshake.resolve(jsonResponse({
      enabled: true, generation: "full-gen-b", coverage_dates: {},
    }, "full-gen-b"));
    await screen.findByRole("textbox", { name: "页面备注" });
    expect(screen.getByRole("textbox", { name: "页面备注" })).not.toBe(previousNote);
    expect(screen.getByRole("textbox", { name: "页面备注" })).toHaveValue("");
    expect(screen.getByTestId("initial-report-date")).toHaveTextContent(expectedDate);
    expect(screen.getByTestId("interaction-generation")).toHaveTextContent("full-gen-b");
  });

  it("still handshakes and remounts for other search inputs read only during page initialization", async () => {
    let handshakes = 0;
    const nextHandshake = deferred<Response>();
    const fetchImpl = vi.fn<typeof fetch>(async (input, init) => {
      if (String(input).endsWith("/api/system-read-publication")) {
        handshakes += 1;
        if (handshakes > 1) return nextHandshake.promise;
        return jsonResponse({ enabled: true, generation: "full-gen-a", coverage_dates: {} }, "full-gen-a");
      }
      const generation = new Headers(init?.headers).get(SYSTEM_READ_GENERATION_HEADER);
      return jsonResponse(envelope({ report_date: "2026-08-31" }), generation ?? undefined);
    });
    renderReportDateBoundary(fetchImpl, "/?year=2026&as_of_date=2026-08-31");
    await waitFor(() => expect(screen.getByTestId("report-date")).toHaveTextContent("2026-08-31"));
    expect(screen.getByTestId("initial-as-of-date")).toHaveTextContent("2026-08-31");
    fireEvent.click(screen.getByRole("button", { name: "新初始参数" }));

    await waitFor(() => expect(handshakes).toBe(2));
    expect(screen.queryByTestId("report-date")).not.toBeInTheDocument();
    expect(fetchImpl).toHaveBeenCalledTimes(3);
    nextHandshake.resolve(jsonResponse({
      enabled: true, generation: "full-gen-b", coverage_dates: {},
    }, "full-gen-b"));
    await waitFor(() => expect(screen.getByTestId("report-date")).toHaveTextContent("2026-08-31"));
    expect(screen.getByTestId("initial-as-of-date")).toHaveTextContent("2025-12-31");
    expect(screen.getByTestId("interaction-generation")).toHaveTextContent("full-gen-b");
    expect(fetchImpl).toHaveBeenCalledTimes(4);
  });

  it("aborts a superseded navigation handshake and ignores its late publication", async () => {
    let handshakes = 0;
    let abandonedSignal: AbortSignal | null | undefined;
    const abandonedHandshake = deferred<Response>();
    const fetchImpl = vi.fn<typeof fetch>(async (input, init) => {
      if (String(input).endsWith("/api/system-read-publication")) {
        handshakes += 1;
        if (handshakes === 2) {
          abandonedSignal = init?.signal;
          return abandonedHandshake.promise;
        }
        const generation = handshakes === 1 ? "full-gen-a" : "full-gen-c";
        return jsonResponse({ enabled: true, generation, coverage_dates: {} }, generation);
      }
      const generation = new Headers(init?.headers).get(SYSTEM_READ_GENERATION_HEADER);
      return jsonResponse(envelope({ report_date: "2026-08-31" }), generation ?? undefined);
    });
    renderReportDateBoundary(fetchImpl);
    await waitFor(() => expect(screen.getByTestId("report-date")).toHaveTextContent("2026-08-31"));
    fireEvent.click(screen.getByRole("button", { name: "新初始参数" }));
    await waitFor(() => expect(handshakes).toBe(2));
    expect(abandonedSignal?.aborted).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "下一页面" }));
    await waitFor(() => expect(screen.getByTestId("interaction-generation")).toHaveTextContent("full-gen-c"));
    expect(abandonedSignal?.aborted).toBe(true);
    abandonedHandshake.resolve(jsonResponse({
      enabled: true, generation: "full-gen-b", coverage_dates: {},
    }, "full-gen-b"));
    await waitFor(() => expect(screen.getByTestId("report-date")).toHaveTextContent("2026-08-31"));
    expect(screen.getByTestId("interaction-generation")).toHaveTextContent("full-gen-c");
    expect(fetchImpl).toHaveBeenCalledTimes(5);
  });


  it.each(["source client", "parent query client"])(
    "does not share cached reads across a changed %s even with the same generation",
    async (scope) => {
      let reads = 0;
      const fetchImpl = vi.fn<typeof fetch>(async (input) => {
        if (String(input).endsWith("/api/system-read-publication")) {
          return jsonResponse({ enabled: true, generation: "full-gen-a", coverage_dates: {} }, "full-gen-a");
        }
        reads += 1;
        return jsonResponse(envelope({ dates: [], generation: "full-gen-a" }), "full-gen-a");
      });
      const options = { defaultOptions: { queries: { retry: false, staleTime: 60_000 } } };
      const client = createApiClient({ mode: "real", fetchImpl });
      const parent = new QueryClient(options);
      const tree = (apiClient: typeof client, queryClient: QueryClient) => (
        <MemoryRouter><ApiClientProvider client={apiClient}><QueryClientProvider client={queryClient}>
          <SystemReadGenerationBoundary><QueryProbe /></SystemReadGenerationBoundary>
        </QueryClientProvider></ApiClientProvider></MemoryRouter>
      );
      const first = render(tree(client, parent));
      await waitFor(() => expect(screen.getByTestId("risk-generation")).toHaveTextContent("full-gen-a"));
      expect(reads).toBe(2);
      first.unmount();
      render(tree(
        scope === "source client" ? createApiClient({ mode: "real", fetchImpl }) : client,
        scope === "parent query client" ? new QueryClient(options) : parent,
      ));
      await waitFor(() => expect(screen.getByTestId("risk-generation")).toHaveTextContent("full-gen-a"));
      expect(reads).toBe(4);
    },
  );

  it("reuses fresh reads only after confirming the same generation, but refresh forces new reads", async () => {
    let generation = "full-gen-a";
    let handshakes = 0;
    let reads = 0;
    const fetchImpl = vi.fn<typeof fetch>(async (input) => {
      if (String(input).endsWith("/api/system-read-publication")) {
        handshakes += 1;
        return jsonResponse({ enabled: true, generation, coverage_dates: {} }, generation);
      }
      reads += 1;
      return jsonResponse(envelope({ dates: [], generation }), generation);
    });
    const client = createApiClient({ mode: "real", fetchImpl });
    const parent = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 60_000 } } });
    render(<MemoryRouter><ApiClientProvider client={client}><QueryClientProvider client={parent}>
      <SystemReadGenerationBoundary><ReturnNavigationProbe /></SystemReadGenerationBoundary>
    </QueryClientProvider></ApiClientProvider></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId("risk-generation")).toHaveTextContent("full-gen-a"));
    expect(reads).toBe(2);
    fireEvent.click(screen.getByRole("button", { name: "切换页面" }));
    await waitFor(() => expect(handshakes).toBe(2));
    await waitFor(() => expect(screen.getByTestId("risk-generation")).toHaveTextContent("full-gen-a"));
    expect(reads).toBe(2);
    fireEvent.click(screen.getByRole("button", { name: "切换页面" }));
    await waitFor(() => expect(handshakes).toBe(3));
    await waitFor(() => expect(screen.getByTestId("risk-generation")).toHaveTextContent("full-gen-a"));
    expect(reads).toBe(2);

    fireEvent.click(screen.getByRole("button", { name: "刷新交互" }));
    await waitFor(() => expect(handshakes).toBe(4));
    await waitFor(() => expect(reads).toBe(4));
    await waitFor(() => expect(screen.getByTestId("risk-generation")).toHaveTextContent("full-gen-a"));

    generation = "full-gen-b";
    fireEvent.click(screen.getByRole("button", { name: "切换页面" }));
    await waitFor(() => expect(screen.getByTestId("risk-generation")).toHaveTextContent("full-gen-b"));
    expect(reads).toBe(6);
  });

  it("does not start the next route's reads in the previous interaction while its handshake is pending", async () => {
    const nextHandshake = deferred<Response>();
    let handshakes = 0;
    const onRead = vi.fn();
    const fetchImpl = vi.fn<typeof fetch>(async (input) => {
      if (String(input).endsWith("/api/system-read-publication")) {
        handshakes += 1;
        if (handshakes > 1) return nextHandshake.promise;
        return jsonResponse({ enabled: true, generation: "full-gen-a", coverage_dates: {} }, "full-gen-a");
      }
      return jsonResponse(envelope({ dates: [] }), "full-gen-a");
    });
    render(
      <MemoryRouter>
        <ApiClientProvider client={createApiClient({ mode: "real", fetchImpl })}>
          <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
            <SystemReadGenerationBoundary>
              <NavigationProbe onRead={onRead} />
            </SystemReadGenerationBoundary>
          </QueryClientProvider>
        </ApiClientProvider>
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "下一页面" }));
    await waitFor(() => expect(handshakes).toBe(2));
    expect(onRead.mock.calls).toEqual([["/"]]);
    nextHandshake.resolve(jsonResponse({ enabled: true, generation: "full-gen-a", coverage_dates: {} }, "full-gen-a"));
    await waitFor(() => expect(onRead.mock.calls).toEqual([["/"], ["/risk-tensor"]]));
  });

  it("pins concurrent page GETs to one generation and isolates the next interaction cache", async () => {
    let publishedGeneration = "full-gen-a";
    const businessRequests: Array<{ path: string; generation: string | null }> = [];
    const oldResponses = [deferred<Response>(), deferred<Response>()];
    let oldResponseIndex = 0;
    const fetchImpl = vi.fn<typeof fetch>(async (input, init) => {
      const path = new URL(String(input), "http://moss.local").pathname;
      if (path.endsWith("/api/system-read-publication")) {
        return jsonResponse(
          {
            enabled: true,
            generation: publishedGeneration,
            coverage_dates: { risk: ["2026-08-31"], balance: ["2026-08-31"] },
          },
          publishedGeneration,
        );
      }

      const generation = new Headers(init?.headers).get(SYSTEM_READ_GENERATION_HEADER);
      businessRequests.push({ path, generation });
      if (generation === "full-gen-a") {
        const pending = oldResponses[oldResponseIndex];
        oldResponseIndex += 1;
        if (!pending) throw new Error("Unexpected extra old-generation request");
        return pending.promise;
      }
      return jsonResponse(
        envelope({ dates: [], generation: publishedGeneration }),
        publishedGeneration,
      );
    });
    renderBoundary(
      createDeferredApiClient({
        mode: "real",
        baseUrl: "https://moss.test/base/",
        fetchImpl,
      }),
    );

    expect(await screen.findByTestId("interaction-generation")).toHaveTextContent("full-gen-a");
    await waitFor(() => expect(businessRequests).toHaveLength(2));
    expect(businessRequests).toEqual(
      expect.arrayContaining([
        { path: "/base/api/risk/tensor/dates", generation: "full-gen-a" },
        { path: "/base/ui/balance-analysis/dates", generation: "full-gen-a" },
      ]),
    );

    publishedGeneration = "full-gen-b";
    fireEvent.click(screen.getByRole("button", { name: "刷新交互" }));

    expect(await screen.findByTestId("interaction-generation")).toHaveTextContent("full-gen-b");
    await waitFor(() => expect(businessRequests).toHaveLength(4));
    expect(businessRequests.slice(2)).toEqual(
      expect.arrayContaining([
        { path: "/base/api/risk/tensor/dates", generation: "full-gen-b" },
        { path: "/base/ui/balance-analysis/dates", generation: "full-gen-b" },
      ]),
    );
    expect(await screen.findByTestId("risk-generation")).toHaveTextContent("full-gen-b");
    expect(await screen.findByTestId("balance-generation")).toHaveTextContent("full-gen-b");

    for (const pending of oldResponses) {
      pending.resolve(
        jsonResponse(envelope({ dates: [], generation: "full-gen-a" }), "full-gen-a"),
      );
    }
    await waitFor(() => {
      expect(screen.getByTestId("risk-generation")).toHaveTextContent("full-gen-b");
      expect(screen.getByTestId("balance-generation")).toHaveTextContent("full-gen-b");
    });
  });

  it.each([undefined, "full-gen-other"])(
    "fails closed when an enabled GET response returns %s instead of the selected generation",
    async (responseGeneration) => {
      const fetchImpl = vi.fn<typeof fetch>(async (input) => {
        const path = new URL(String(input), "http://moss.local").pathname;
        if (path === "/api/system-read-publication") {
          return jsonResponse(
            { enabled: true, generation: "full-gen-a", coverage_dates: {} },
            "full-gen-a",
          );
        }
        return jsonResponse(envelope({ dates: [] }), responseGeneration);
      });
      const client = createApiClient({ mode: "real", fetchImpl });

      const { createGenerationScopedApiClient } = await import("../api/systemReadGeneration");
      await expect(createGenerationScopedApiClient(client, "full-gen-a").getRiskTensorDates())
        .rejects.toThrow(/generation mismatch/i);
    },
  );

  it("does not mount page queries until the publication handshake completes", async () => {
    const handshake = deferred<Response>();
    const fetchImpl = vi.fn<typeof fetch>(async (input) => {
      const path = new URL(String(input), "http://moss.local").pathname;
      if (path === "/api/system-read-publication") return handshake.promise;
      return jsonResponse(envelope({ dates: [], generation: "full-gen-a" }), "full-gen-a");
    });
    renderBoundary(createApiClient({ mode: "real", fetchImpl }));

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId("interaction-generation")).not.toBeInTheDocument();

    handshake.resolve(
      jsonResponse(
        { enabled: true, generation: "full-gen-a", coverage_dates: {} },
        "full-gen-a",
      ),
    );
    expect(await screen.findByTestId("interaction-generation")).toHaveTextContent("full-gen-a");
    await waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(3));
  });

  it("keeps liveness, refresh status, the exact auth read and write requests live", async () => {
    const requests: Array<{ path: string; method: string; generation: string | null }> = [];
    const fetchImpl = vi.fn<typeof fetch>(async (input, init) => {
      const path = new URL(String(input), "http://moss.local").pathname;
      requests.push({
        path,
        method: init?.method ?? "GET",
        generation: new Headers(init?.headers).get(SYSTEM_READ_GENERATION_HEADER),
      });
      const requestGeneration = new Headers(init?.headers).get(SYSTEM_READ_GENERATION_HEADER);
      return jsonResponse(
        path === "/base/api/risk/tensor/dates" ? envelope({ dates: [] }) : {},
        requestGeneration ?? undefined,
      );
    });
    const { createGenerationScopedApiClient } = await import("../api/systemReadGeneration");
    const client = createGenerationScopedApiClient(
      createApiClient({ mode: "real", baseUrl: "https://moss.test/base", fetchImpl }),
      "full-gen-a",
    );

    await client.getBalanceAnalysisCurrentUser();
    await client.getBalanceAnalysisRefreshStatus("balance-run-new");
    await client.getBondAnalyticsRefreshStatus("bond-run-new");
    await client.refreshBondAnalytics("2026-08-31");
    await client.getRiskTensorDates();
    const factory = getApiClientFactoryRecord(client);
    if (!factory) throw new Error("Scoped client did not retain its factory options");
    await factory.options.fetchImpl("https://moss.test/base/health/live");

    expect(requests).toEqual([
      {
        path: "/base/ui/balance-analysis/current-user",
        method: "GET",
        generation: null,
      },
      {
        path: "/base/ui/balance-analysis/refresh-status",
        method: "GET",
        generation: null,
      },
      {
        path: "/base/api/bond-analytics/refresh-status",
        method: "GET",
        generation: null,
      },
      {
        path: "/base/api/bond-analytics/refresh",
        method: "POST",
        generation: null,
      },
      {
        path: "/base/api/risk/tensor/dates",
        method: "GET",
        generation: "full-gen-a",
      },
      {
        path: "/base/health/live",
        method: "GET",
        generation: null,
      },
    ]);
  });

  it.each(["full-gen-a", "full-gen-b", null])(
    "pins Cube POST requests and validates response generation %s",
    async (responseGeneration) => {
      const request = {
        report_date: "2026-09-15", fact_table: "bond_analytics",
        measures: ["sum(market_value)"],
      };
      const fetchImpl = vi.fn<typeof fetch>(async (_input, init) => {
        expect(init?.method).toBe("POST");
        expect(new Headers(init?.headers).get(SYSTEM_READ_GENERATION_HEADER)).toBe("full-gen-a");
        expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
        expect(JSON.parse(String(init?.body))).toEqual(request);
        return jsonResponse({ rows: [{ market_value: "125.00" }] }, responseGeneration ?? undefined);
      });
      const { createGenerationScopedApiClient } = await import("../api/systemReadGeneration");
      const client = createGenerationScopedApiClient(
        createApiClient({ mode: "real", baseUrl: "https://moss.test/base", fetchImpl }), "full-gen-a",
      );
      if (responseGeneration === "full-gen-a") {
        await expect(client.executeCubeQuery(request)).resolves.toMatchObject({
          rows: [{ market_value: "125.00" }],
        });
      } else {
        await expect(client.executeCubeQuery(request)).rejects.toThrow("generation mismatch");
      }
    },
  );

  it("keeps disabled and mock clients on their existing behavior", async () => {
    const realFetch = vi.fn<typeof fetch>(async (input, init) => {
      const path = new URL(String(input), "http://moss.local").pathname;
      if (path === "/api/system-read-publication") {
        return jsonResponse({ enabled: false, generation: null, coverage_dates: {} });
      }
      expect(new Headers(init?.headers).has(SYSTEM_READ_GENERATION_HEADER)).toBe(false);
      return jsonResponse(envelope({ dates: [], generation: "live" }));
    });
    const first = renderBoundary(createApiClient({ mode: "real", fetchImpl: realFetch }));
    expect(await screen.findByTestId("interaction-generation")).toHaveTextContent("disabled");
    await waitFor(() => expect(realFetch).toHaveBeenCalledTimes(3));
    first.unmount();

    const unusedFetch = vi.fn<typeof fetch>();
    renderBoundary(createDeferredApiClient({ mode: "mock", fetchImpl: unusedFetch }));
    expect(await screen.findByTestId("interaction-generation")).toHaveTextContent("disabled");
    expect(unusedFetch).not.toHaveBeenCalled();
  });
});
