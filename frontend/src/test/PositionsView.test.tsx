import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type {
  ApiEnvelope,
  BondPositionItem,
  InterbankPositionItem,
  PageResponse,
  ResultMeta,
  SubTypesResponse,
} from "../api/contracts";
import PositionsView from "../features/positions/components/PositionsView";
import { EM_DASH } from "../utils/format";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="positions-echarts-stub" />,
}));

function meta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_test",
    vendor_version: "vv_none",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-01-02T00:00:00Z",
  };
}

function envelope<T>(
  resultKind: string,
  result: T,
  metaOverrides: Partial<ResultMeta> = {},
): ApiEnvelope<T> {
  return {
    result_meta: { ...meta(resultKind), ...metaOverrides },
    result,
  };
}

function bondPage(items: BondPositionItem[]): PageResponse<BondPositionItem> {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 20,
  };
}

function interbankPage(items: InterbankPositionItem[]): PageResponse<InterbankPositionItem> {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 20,
  };
}

function statusBond(code = "STATUS-BOND"): BondPositionItem {
  return {
    bond_code: code,
    credit_name: "状态测试主体",
    sub_type: "信用债",
    asset_class: "HTM",
    market_value: "100000000.00000000",
    face_value: "100000000.00000000",
    valuation_net_price: "100.00000000",
    yield_rate: "0.03000000",
  };
}

function statusInterbank(dealId = "STATUS-INTERBANK"): InterbankPositionItem {
  return {
    deal_id: dealId,
    counterparty: "状态测试对手方",
    product_type: "拆借",
    direction: "Asset",
    amount: "100000000.00000000",
    interest_rate: "0.02500000",
    maturity_date: "2026-05-30",
  };
}

function renderPositionsWithClient(
  client: ReturnType<typeof createApiClient>,
  initialEntry = "/positions",
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <MemoryRouter initialEntries={[initialEntry]}>
          <PositionsView />
        </MemoryRouter>
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("PositionsView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders shell, report date control, and bond tab", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <PositionsView />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("positions-page")).toBeInTheDocument();
    expect(await screen.findByTestId("positions-page-title")).toHaveTextContent("持仓透视");
    expect(await screen.findByTestId("positions-decision-hero")).toHaveTextContent(
      "数据来源：ZQTZ + TYWL",
    );
    expect(screen.getByTestId("positions-data-status")).toHaveTextContent("当前：债券持仓");
    expect(screen.getByTestId("positions-kpi-band")).toHaveTextContent("日均合计");
    expect(screen.getByTestId("positions-filter-tray")).toBeInTheDocument();
    expect(screen.getByText("持仓工作区")).toBeInTheDocument();
    expect(
      await screen.findByRole("combobox", { name: "positions-report-date" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("持仓区间起始日期")).toBeInTheDocument();
    expect(screen.getByLabelText("持仓区间结束日期")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "债券持仓" })).toBeInTheDocument();
  });

  it("surfaces candidate list metric boundaries for GAP-POS-LIST", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <PositionsView />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const boundary = await screen.findByTestId("positions-list-candidate-boundary");
    expect(boundary).toHaveTextContent("GAP-POS-LIST");
    expect(boundary).toHaveTextContent("MTR-POS-001");
    expect(boundary).toHaveTextContent("MTR-POS-002");
    expect(boundary).toHaveTextContent("pending_confirmation=true");
    expect(boundary).toHaveTextContent("bound_sample_id=none");
  });

  it("renders duplicate bond codes without duplicate React row-key warnings", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const client = createApiClient({ mode: "mock" });
    client.getPositionsBondSubTypes = vi.fn(async (): Promise<ApiEnvelope<SubTypesResponse>> =>
      envelope("positions.bonds.sub_types", { sub_types: ["Gov"] }),
    );
    client.getPositionsBondsList = vi.fn(
      async (options): Promise<ApiEnvelope<PageResponse<BondPositionItem>>> =>
        envelope("positions.bonds.list", {
          items: [
            {
              bond_code: "DUP001",
              credit_name: "Issuer A",
              sub_type: "Gov",
              asset_class: "HTM",
              market_value: "100000000.00000000",
              face_value: "100000000.00000000",
              valuation_net_price: "100.00000000",
              yield_rate: "0.03000000",
            },
            {
              bond_code: "DUP001",
              credit_name: "Issuer A",
              sub_type: "Gov",
              asset_class: "AFS",
              market_value: "200000000.00000000",
              face_value: "200000000.00000000",
              valuation_net_price: "100.00000000",
              yield_rate: "0.03100000",
            },
          ],
          total: 2,
          page: options.page,
          page_size: options.pageSize,
        }),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <PositionsView />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await screen.findByTestId("positions-page");
    await waitFor(() =>
      expect(client.getPositionsBondsList).toHaveBeenCalledWith(
        expect.objectContaining({ subType: null }),
      ),
    );
    const subTypeSelect = await screen.findByTestId("positions-bond-subtype-select");
    fireEvent.mouseDown(subTypeSelect.querySelector(".ant-select-selector") ?? subTypeSelect);
    fireEvent.click(await screen.findByTitle("Gov"));

    await waitFor(() => expect(screen.getAllByText("DUP001")).toHaveLength(2));
    const duplicateKeyWarnings = errorSpy.mock.calls.filter(([message]) =>
      String(message).includes("Encountered two children with the same key"),
    );
    expect(duplicateKeyWarnings).toHaveLength(0);
  });

  it("links bond rows to the bond trading desk", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondSubTypes = vi.fn(async (): Promise<ApiEnvelope<SubTypesResponse>> =>
      envelope("positions.bonds.sub_types", { sub_types: ["Gov"] }),
    );
    client.getPositionsBondsList = vi.fn(
      async (): Promise<ApiEnvelope<PageResponse<BondPositionItem>>> =>
        envelope("positions.bonds.list", {
          items: [
            {
              bond_code: "POS001.IB",
              credit_name: "持仓样例",
              sub_type: "Gov",
              asset_class: "HTM",
              market_value: "100000000.00000000",
              face_value: "100000000.00000000",
              valuation_net_price: "100.00000000",
              yield_rate: "0.03000000",
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
        }),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter initialEntries={["/positions?report_date=2026-04-30"]}>
            <PositionsView />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const link = await screen.findByTestId("positions-bond-trading-desk-link-POS001.IB");
    expect(link).toHaveAttribute(
      "href",
      "/bond-trading-desk?bond_code=POS001.IB&report_date=2026-04-30",
    );
  });

  it("renders the EM_DASH primitive for missing bond list fields", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondsList = vi.fn(async () =>
      envelope(
        "positions.bonds.list",
        bondPage([
          {
            bond_code: "MISSING-001",
            credit_name: null,
            sub_type: null,
            asset_class: null,
            market_value: "100000000.00000000",
            face_value: "100000000.00000000",
            valuation_net_price: null,
            yield_rate: "0.03000000",
          },
        ]),
      ),
    );

    renderPositionsWithClient(client);

    const codeCell = await screen.findByText("MISSING-001");
    const row = codeCell.closest("tr");
    expect(row).not.toBeNull();
    const dashCells = Array.from(row!.querySelectorAll("td")).filter(
      (td) => td.textContent === EM_DASH,
    );
    // credit_name / sub_type / valuation_net_price 三个缺失字段均走 EM_DASH 基元。
    expect(dashCells.length).toBeGreaterThanOrEqual(3);
  });

  it("uses the active list envelope metadata and shows fallback dates after tab switch", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondsList = vi.fn(async () =>
      envelope("positions.bonds.list", bondPage([statusBond()])),
    );
    client.getPositionsInterbankList = vi.fn(async () =>
      envelope(
        "positions.interbank.list",
        interbankPage([
          {
            deal_id: "STATUS-INTERBANK",
            counterparty: "状态测试对手方",
            product_type: "拆借",
            direction: "Asset",
            amount: "100000000.00000000",
            interest_rate: "0.02500000",
            maturity_date: "2026-05-30",
          },
        ]),
        {
          fallback_mode: "latest_snapshot",
          requested_report_date: "2026-04-30",
          resolved_report_date: "2026-04-29",
          fallback_date: "2026-04-28",
        },
      ),
    );

    renderPositionsWithClient(client);

    expect(await screen.findByText("STATUS-BOND")).toBeInTheDocument();
    expect(screen.queryByTestId("positions-data-state-alert")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "同业持仓" }));

    const alert = await screen.findByTestId("positions-data-state-alert");
    expect(alert).toHaveTextContent("已回退到最近可用快照");
    expect(alert).toHaveTextContent("请求日期 2026-04-30");
    expect(alert).toHaveTextContent("解析日期 2026-04-29");
    expect(alert).toHaveTextContent("回退日期 2026-04-28");
  });

  it.each([
    ["quality stale", { quality_flag: "stale" as const }],
    ["vendor stale", { vendor_status: "vendor_stale" as const }],
  ])("shows a first-screen stale alert for %s", async (_label, metaOverrides) => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondsList = vi.fn(async () =>
      envelope("positions.bonds.list", bondPage([statusBond()]), {
        ...metaOverrides,
        as_of_date: "2026-04-27",
      }),
    );

    renderPositionsWithClient(client);

    const alert = await screen.findByTestId("positions-data-state-alert");
    expect(alert).toHaveTextContent("数据可能偏旧");
    expect(alert).toHaveTextContent("有效日期 2026-04-27");
  });

  it.each([
    ["quality stale", { quality_flag: "stale" as const }],
    ["vendor stale", { vendor_status: "vendor_stale" as const }],
  ])("combines fallback and %s in one first-screen alert", async (_label, metaOverrides) => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondsList = vi.fn(async () =>
      envelope("positions.bonds.list", bondPage([statusBond()]), {
        ...metaOverrides,
        fallback_mode: "latest_snapshot",
        requested_report_date: "2026-04-30",
        resolved_report_date: "2026-04-29",
        as_of_date: "2026-04-28",
      }),
    );

    renderPositionsWithClient(client);

    const alert = await screen.findByTestId("positions-data-state-alert");
    expect(screen.getAllByTestId("positions-data-state-alert")).toHaveLength(1);
    expect(alert).toHaveTextContent("已回退至最近可用快照，且该快照可能偏旧");
    expect(alert).toHaveTextContent("请求日期 2026-04-30");
    expect(alert).toHaveTextContent("有效日期 2026-04-28");
  });

  it.each([
    ["quality error", { quality_flag: "error" as const }],
    ["vendor unavailable", { vendor_status: "vendor_unavailable" as const }],
  ])("shows a first-screen unavailable alert for %s", async (_label, metaOverrides) => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondsList = vi.fn(async () =>
      envelope("positions.bonds.list", bondPage([statusBond()]), metaOverrides),
    );

    renderPositionsWithClient(client);

    expect(await screen.findByTestId("positions-data-state-alert")).toHaveTextContent(
      "债券持仓数据当前不可用",
    );
  });

  it("shows a first-screen no-data alert for an empty active list", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondsList = vi.fn(async () =>
      envelope("positions.bonds.list", bondPage([])),
    );

    renderPositionsWithClient(client);

    expect(await screen.findByTestId("positions-data-state-alert")).toHaveTextContent(
      "当前报告日暂无债券持仓数据",
    );
    expect(await screen.findByTestId("positions-bonds-list-empty")).toHaveTextContent("暂无数据");
  });

  it("keeps the bonds table loading while report dates are unresolved", async () => {
    const client = createApiClient({ mode: "mock" });
    const dates = deferred<ApiEnvelope<{ report_dates: string[] }>>();
    client.getBalanceAnalysisDates = vi.fn(() => dates.promise);
    client.getPositionsBondsList = vi.fn();

    renderPositionsWithClient(client);

    expect(await screen.findByTestId("positions-bonds-list-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("positions-bonds-list-empty")).not.toBeInTheDocument();
    expect(client.getPositionsBondsList).not.toHaveBeenCalled();
  });

  it("shows a first-screen no-data alert when no report dates are available", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: [] }),
    );
    client.getPositionsBondsList = vi.fn();

    renderPositionsWithClient(client);

    expect(await screen.findByTestId("positions-data-state-alert")).toHaveTextContent(
      "暂无可用报告日",
    );
    expect(screen.getAllByText(/暂无可用报告日/)).toHaveLength(1);
    expect(client.getPositionsBondsList).not.toHaveBeenCalled();
  });

  it("shows a first-screen error alert when the active list query fails", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondsList = vi.fn(async () => {
      throw new Error("positions list failed");
    });

    renderPositionsWithClient(client);

    expect(await screen.findByTestId("positions-data-state-alert")).toHaveTextContent(
      "债券持仓加载失败",
    );
    expect(screen.queryByTestId("positions-bonds-list-empty")).not.toBeInTheDocument();
    expect(screen.getByTestId("positions-bonds-list-error")).toHaveTextContent(
      "债券持仓暂不可用",
    );
  });

  it("shows a first-screen error alert for an incomplete active list envelope", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondsList = vi.fn(async () => {
      return {
        result_meta: meta("positions.bonds.list"),
        result: {},
      } as unknown as ApiEnvelope<PageResponse<BondPositionItem>>;
    });

    renderPositionsWithClient(client);

    expect(await screen.findByTestId("positions-data-state-alert")).toHaveTextContent(
      "债券持仓响应不完整",
    );
    expect(screen.queryByTestId("positions-bonds-list-empty")).not.toBeInTheDocument();
    expect(screen.getByTestId("positions-bonds-list-error")).toHaveTextContent(
      "债券持仓暂不可用",
    );
  });

  it.each([
    [
      "items is not an array",
      {
        result_meta: meta("positions.bonds.list"),
        result: { items: "invalid", total: 1, page: 1, page_size: 20 },
      },
    ],
    [
      "total is negative",
      {
        result_meta: meta("positions.bonds.list"),
        result: { items: [], total: -1, page: 1, page_size: 20 },
      },
    ],
    [
      "total is not finite",
      {
        result_meta: meta("positions.bonds.list"),
        result: { items: [], total: Number.NaN, page: 1, page_size: 20 },
      },
    ],
    [
      "total is not an integer",
      {
        result_meta: meta("positions.bonds.list"),
        result: { items: [], total: 1.5, page: 1, page_size: 20 },
      },
    ],
    [
      "meta status is invalid",
      {
        result_meta: { ...meta("positions.bonds.list"), vendor_status: "unknown" },
        result: bondPage([statusBond()]),
      },
    ],
  ])("fails closed before consuming a list when %s", async (_label, invalidEnvelope) => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondsList = vi.fn(async () => {
      return invalidEnvelope as unknown as ApiEnvelope<PageResponse<BondPositionItem>>;
    });

    renderPositionsWithClient(client);

    expect(await screen.findByTestId("positions-data-state-alert")).toHaveTextContent(
      "债券持仓响应不完整",
    );
    expect(screen.getByTestId("positions-bonds-list-error")).toHaveTextContent(
      "债券持仓暂不可用",
    );
    expect(screen.queryByTestId("positions-bonds-list-empty")).not.toBeInTheDocument();
  });

  it("does not treat a positive total with no current rows as globally empty", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondsList = vi.fn(async () =>
      envelope("positions.bonds.list", {
        items: [],
        total: 5,
        page: 1,
        page_size: 20,
      }),
    );

    renderPositionsWithClient(client);

    expect(await screen.findByTestId("positions-bonds-list-blocked")).toBeInTheDocument();
    expect(screen.queryByTestId("positions-bonds-list-empty")).not.toBeInTheDocument();
    expect(screen.queryByText("当前报告日暂无债券持仓数据")).not.toBeInTheDocument();
  });

  it("returns to page one when a later page is empty but total remains positive", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    const bondsListMock = vi.fn(
      async (
        options: Parameters<typeof client.getPositionsBondsList>[0],
      ): Promise<ApiEnvelope<PageResponse<BondPositionItem>>> =>
        envelope("positions.bonds.list", {
          items: options.page === 1 ? [statusBond("RESET-PAGE-1")] : [],
          total: 40,
          page: options.page,
          page_size: options.pageSize,
        }),
    );
    client.getPositionsBondsList = bondsListMock;

    renderPositionsWithClient(client);
    expect(await screen.findByText("RESET-PAGE-1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));

    /*
     * 第 2 页空但 total>0 时回退第一页。staleTime 生效后第 1 页直接吃
     * 5 分钟内的查询缓存，不再发第三次请求（请求序列 [1,2]），行为契约
     * 以「回到第一页且明细可见」为准。
     */
    await waitFor(() =>
      expect(bondsListMock.mock.calls.map(([options]) => options.page)).toEqual([1, 2]),
    );
    expect(await screen.findByText("RESET-PAGE-1")).toBeInTheDocument();
    expect(screen.getByText(/第 1\/2 页/)).toBeInTheDocument();
    expect(screen.queryByTestId("positions-bonds-list-empty")).not.toBeInTheDocument();
  });

  it("requests page one first when switching tabs from a later page", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondsList = vi.fn(async (options) =>
      envelope("positions.bonds.list", {
        items: [statusBond(`TAB-PAGE-${options.page}`)],
        total: 40,
        page: options.page,
        page_size: options.pageSize,
      }),
    );
    const interbankListMock = vi.fn(
      async (
        options: Parameters<typeof client.getPositionsInterbankList>[0],
      ): Promise<ApiEnvelope<PageResponse<InterbankPositionItem>>> =>
        envelope("positions.interbank.list", {
          items: [statusInterbank(`TAB-INTERBANK-${options.page}`)],
          total: 1,
          page: options.page,
          page_size: options.pageSize,
        }),
    );
    client.getPositionsInterbankList = interbankListMock;

    renderPositionsWithClient(client);
    expect(await screen.findByText("TAB-PAGE-1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(await screen.findByText("TAB-PAGE-2")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "同业持仓" }));

    await waitFor(() => expect(interbankListMock).toHaveBeenCalled());
    expect(interbankListMock.mock.calls[0][0].page).toBe(1);
  });

  it("requests page one first when changing the active bond filter", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondSubTypes = vi.fn(async () =>
      envelope("positions.bonds.sub_types", { sub_types: ["Gov"] }),
    );
    const bondsListMock = vi.fn(
      async (
        options: Parameters<typeof client.getPositionsBondsList>[0],
      ): Promise<ApiEnvelope<PageResponse<BondPositionItem>>> =>
        envelope("positions.bonds.list", {
          items: [statusBond(`FILTER-${options.subType ?? "ALL"}-${options.page}`)],
          total: 40,
          page: options.page,
          page_size: options.pageSize,
        }),
    );
    client.getPositionsBondsList = bondsListMock;

    renderPositionsWithClient(client);
    expect(await screen.findByText("FILTER-ALL-1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(await screen.findByText("FILTER-ALL-2")).toBeInTheDocument();

    const subTypeSelect = await screen.findByTestId("positions-bond-subtype-select");
    fireEvent.mouseDown(subTypeSelect.querySelector(".ant-select-selector") ?? subTypeSelect);
    fireEvent.click(await screen.findByTitle("Gov"));

    await waitFor(() =>
      expect(
        bondsListMock.mock.calls.some(([options]) => options.subType === "Gov"),
      ).toBe(true),
    );
    const filteredCalls = bondsListMock.mock.calls.filter(
      ([options]) => options.subType === "Gov",
    );
    expect(filteredCalls[0][0].page).toBe(1);
  });

  it("keeps the interbank table loading while its active list query is pending", async () => {
    const client = createApiClient({ mode: "mock" });
    const interbankList = deferred<ApiEnvelope<PageResponse<InterbankPositionItem>>>();
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondsList = vi.fn(async () =>
      envelope("positions.bonds.list", bondPage([statusBond()])),
    );
    client.getPositionsInterbankList = vi.fn(() => interbankList.promise);

    renderPositionsWithClient(client);
    expect(await screen.findByText("STATUS-BOND")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "同业持仓" }));

    expect(await screen.findByTestId("positions-interbank-list-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("positions-interbank-list-empty")).not.toBeInTheDocument();
  });

  it.each(["query error", "malformed envelope"])(
    "does not show the interbank empty state for %s",
    async (failureMode) => {
      const client = createApiClient({ mode: "mock" });
      client.getBalanceAnalysisDates = vi.fn(async () =>
        envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
      );
      client.getPositionsBondsList = vi.fn(async () =>
        envelope("positions.bonds.list", bondPage([statusBond()])),
      );
      client.getPositionsInterbankList =
        failureMode === "query error"
          ? vi.fn(async () => {
              throw new Error("interbank list failed");
            })
          : vi.fn(async () => {
              return {
                result_meta: meta("positions.interbank.list"),
                result: {},
              } as unknown as ApiEnvelope<PageResponse<InterbankPositionItem>>;
            });

      renderPositionsWithClient(client);
      expect(await screen.findByText("STATUS-BOND")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("tab", { name: "同业持仓" }));

      const alert = await screen.findByTestId("positions-data-state-alert");
      expect(alert).toHaveTextContent(
        failureMode === "query error" ? "同业持仓加载失败" : "同业持仓响应不完整",
      );
      expect(screen.queryByTestId("positions-interbank-list-empty")).not.toBeInTheDocument();
      expect(screen.getByTestId("positions-interbank-list-error")).toHaveTextContent(
        "同业持仓暂不可用",
      );
    },
  );

  it("shows the interbank empty state only after a successful empty response", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondsList = vi.fn(async () =>
      envelope("positions.bonds.list", bondPage([statusBond()])),
    );
    client.getPositionsInterbankList = vi.fn(async () =>
      envelope("positions.interbank.list", interbankPage([])),
    );

    renderPositionsWithClient(client);
    expect(await screen.findByText("STATUS-BOND")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "同业持仓" }));

    expect(await screen.findByTestId("positions-interbank-list-empty")).toHaveTextContent(
      "暂无数据",
    );
    expect(screen.queryByTestId("positions-interbank-list-error")).not.toBeInTheDocument();
  });
});
