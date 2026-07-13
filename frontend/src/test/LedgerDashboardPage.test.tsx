import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { RouterProvider } from "react-router-dom";

import { AppProviders } from "../app/providers";
import { createApiClient, type ApiClient } from "../api/client";
import { LedgerRequestError } from "../api/ledgerClient";
import type {
  LedgerApiResponse,
  LedgerDashboardData,
  LedgerDatesData,
  LedgerImportResponse,
  LedgerPositionsData,
  LedgerPositionsOptions,
} from "../api/ledgerClient";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { createWorkbenchMemoryRouter, renderWorkbenchApp } from "./renderWorkbenchApp";

const metadata = {
  source_version: "sv_ledger_test",
  rule_version: "position_key_contract_v1",
  batch_id: 7,
  stale: false,
  fallback: false,
  no_data: false,
};

function envelope<TData>(
  data: TData,
  overrides?: {
    metadata?: Partial<LedgerApiResponse<TData>["metadata"]>;
    trace?: Partial<LedgerApiResponse<TData>["trace"]>;
  },
): LedgerApiResponse<TData> {
  return {
    data,
    metadata: { ...metadata, ...overrides?.metadata },
    trace: {
      request_id: "req_ledger_test",
      requested_as_of_date: "2026-03-17",
      resolved_as_of_date: "2026-03-17",
      batch_id: 7,
      filters: null,
      ...overrides?.trace,
    },
  };
}

function positionsPayload(options: LedgerPositionsOptions): LedgerApiResponse<LedgerPositionsData> {
  const baseItems: LedgerPositionsData["items"] = [
    {
      position_key: "asset-key",
      batch_id: 7,
      row_no: 1,
      as_of_date: "2026-03-17",
      bond_code: "ASSET-001",
      bond_name: "资产债券",
      portfolio: "银行账簿",
      direction: "ASSET",
      business_type: "投资",
      business_type_1: "债券",
      account_category_std: "银行账户",
      cost_center: "总行",
      asset_class_std: "持有至到期类资产",
      channel: "ZQTZSHOW",
      currency: "CNY",
      face_amount: 100000000,
      fair_value: 99500000,
      amortized_cost: 100100000,
      accrued_interest: null,
      interest_receivable_payable: null,
      quantity: null,
      latest_face_value: null,
      interest_method: "fixed",
      coupon_rate: null,
      yield_to_maturity: null,
      interest_start_date: null,
      maturity_date: "2028-03-17",
      counterparty_name_cn: "发行人A",
      legal_customer_name: "发行人A",
      group_customer_name: "集团A",
      trace: { position_key: "asset-key", batch_id: 7, row_no: 1 },
    },
    {
      position_key: "liability-key",
      batch_id: 7,
      row_no: 2,
      as_of_date: "2026-03-17",
      bond_code: "LIAB-001",
      bond_name: "发行负债债券",
      portfolio: "银行账簿",
      direction: "LIABILITY",
      business_type: "发行",
      business_type_1: "债券",
      account_category_std: "发行类债券",
      cost_center: "总行",
      asset_class_std: "发行类债券",
      channel: "ZQTZSHOW",
      currency: "CNY",
      face_amount: 50000000,
      fair_value: 49800000,
      amortized_cost: 50020000,
      accrued_interest: null,
      interest_receivable_payable: null,
      quantity: null,
      latest_face_value: null,
      interest_method: "fixed",
      coupon_rate: null,
      yield_to_maturity: null,
      interest_start_date: null,
      maturity_date: "2029-03-17",
      counterparty_name_cn: "本行发行",
      legal_customer_name: "本行发行",
      group_customer_name: "本行发行",
      trace: { position_key: "liability-key", batch_id: 7, row_no: 2 },
    },
  ];
  const items = options.direction
    ? baseItems.filter((item) => item.direction === options.direction)
    : baseItems;
  return envelope(
    {
      items,
      page: options.page ?? 1,
      page_size: options.pageSize ?? 20,
      total: items.length,
    },
    {
      trace: {
        request_id: "req_positions_test",
        requested_as_of_date: options.asOfDate,
        resolved_as_of_date: "2026-03-17",
        batch_id: 7,
        filters: options,
      },
    },
  );
}

function buildClient(
  overrides?: Partial<{
    dates: LedgerApiResponse<LedgerDatesData>;
    datesError: Error;
    dashboard: (asOfDate: string) => LedgerApiResponse<LedgerDashboardData>;
    positions: (options: LedgerPositionsOptions) => Promise<LedgerApiResponse<LedgerPositionsData>>;
    importLedger: (file: File) => Promise<LedgerImportResponse>;
    importStatus: (runId: string, signal?: AbortSignal) => Promise<LedgerImportResponse>;
  }>,
): ApiClient {
  const base = createApiClient({ mode: "real" });
  return {
    ...base,
    getLedgerDates: vi.fn(async () => {
      if (overrides?.datesError) {
        throw overrides.datesError;
      }
      return overrides?.dates ?? envelope<LedgerDatesData>({ items: ["2026-03-17"] });
    }),
    getLedgerDashboard: vi.fn(async (asOfDate: string) =>
      overrides?.dashboard
        ? overrides.dashboard(asOfDate)
        : envelope<LedgerDashboardData>({
            as_of_date: "2026-03-17",
            classification_status: "ready",
            classification_rule_version: "rv_ledger_classification_v2",
            currency_breakdown: [
              { currency: "CNY", asset_face_amount: 3289.07, liability_face_amount: 1231.77, net_face_exposure: 2057.31, classification_total_row_count: 2, unclassified_row_count: 0, unclassified_face_amount: 0, classification_coverage_pct: 100 },
              { currency: "USD", asset_face_amount: 2, liability_face_amount: null, net_face_exposure: 2, classification_total_row_count: 1, unclassified_row_count: 0, unclassified_face_amount: 0, classification_coverage_pct: 100 },
            ],
          }),
    ),
    getLedgerPositions: vi.fn(async (options: LedgerPositionsOptions) =>
      overrides?.positions ? overrides.positions(options) : positionsPayload(options),
    ),
    importLedger: vi.fn(async (file: File): Promise<LedgerImportResponse> =>
      overrides?.importLedger
        ? overrides.importLedger(file)
        : {
            data: {
              run_id: "ledger_import:test",
              status: "queued",
              file_name: file.name,
            },
            trace: { request_id: "req_import_test", run_id: "ledger_import:test" },
          },
    ),
    getLedgerImportStatus: vi.fn(async (runId: string, signal?: AbortSignal): Promise<LedgerImportResponse> =>
      overrides?.importStatus
        ? overrides.importStatus(runId, signal)
        : {
            data: {
              run_id: runId,
              status: "succeeded",
              file_name: "ledger.xlsx",
              batch_id: 9,
              finished_at: "2026-07-11T04:00:00Z",
            },
            trace: { request_id: "req_status_test", run_id: runId },
          },
    ),
  };
}

describe("LedgerDashboardPage", () => {
  beforeAll(async () => {
    await preloadWorkbenchRouteModules("bank-ledger-dashboard");
  }, 20_000);

  beforeEach(() => {
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders imported currency-bucket KPIs without an alert card", async () => {
    const client = buildClient();
    renderWorkbenchApp(["/bank-ledger-dashboard"], { client });

    expect(await screen.findByTestId("ledger-dashboard-page")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-dashboard-governance-boundary")).toHaveTextContent("imported position_snapshot");
    expect(screen.getByTestId("ledger-dashboard-governance-boundary")).toHaveTextContent("Historical backfill completed");
    expect(screen.getByTestId("ledger-dashboard-governance-boundary")).toHaveTextContent("golden sample captured-awaiting-approval");
    expect(screen.getByTestId("ledger-dashboard-governance-boundary")).not.toHaveTextContent("golden/backfill work remains pending");
    await waitFor(() => expect(screen.getByLabelText("ledger-dashboard-currency")).toHaveValue("CNY"));
    expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("3289.07 CNY/1亿");
    expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("1231.77 CNY/1亿");
    expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("2057.31 CNY/1亿");
    expect(screen.queryByTestId("ledger-dashboard-kpi-alerts")).not.toBeInTheDocument();
    expect(screen.getAllByTestId(/ledger-dashboard-kpi-/)).toHaveLength(3);
    expect(await screen.findByText("asset-key")).toBeInTheDocument();
  });
  it("shows classification quality and drills into materialized UNCLASSIFIED rows", async () => {
    const user = userEvent.setup();
    const client = buildClient();
    renderWorkbenchApp(["/bank-ledger-dashboard?as_of_date=2026-03-17"], { client });

    const panel = await screen.findByTestId("ledger-dashboard-classification-quality");
    await waitFor(() => expect(panel).toHaveTextContent("覆盖率 100.00%"));
    expect(panel).toHaveTextContent("未分类 0 行");
    await user.click(within(panel).getByRole("button", { name: "查看未分类明细" }));

    await waitFor(() => expect(client.getLedgerPositions).toHaveBeenLastCalledWith(
      expect.objectContaining({ direction: "UNCLASSIFIED", asOfDate: "2026-03-17" }),
    ));
    expect(screen.getByRole("button", { name: "未分类" })).toHaveClass("is-active");
  });
  it("fails closed and explains legacy classification batches", async () => {
    const client = buildClient({
      dashboard: (asOfDate) => envelope<LedgerDashboardData>({
        as_of_date: asOfDate,
        classification_status: "legacy_unassessed",
        classification_rule_version: "rv_ledger_classification_v2",
        currency_breakdown: [{
          currency: "CNY",
          asset_face_amount: null,
          liability_face_amount: null,
          net_face_exposure: null,
          classification_total_row_count: 2,
          unclassified_row_count: null,
          unclassified_face_amount: null,
          classification_coverage_pct: null,
        }],
      }),
    });
    renderWorkbenchApp(["/bank-ledger-dashboard?as_of_date=2026-03-17&direction=UNCLASSIFIED"], { client });

    const panel = await screen.findByTestId("ledger-dashboard-classification-quality");
    await waitFor(() => expect(panel).toHaveTextContent("旧规则批次不可评估"));
    expect(within(panel).queryByRole("button", { name: "查看未分类明细" })).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "全部" })).toHaveClass("is-active"));
    expect(
      vi.mocked(client.getLedgerPositions).mock.calls.some(
        ([options]) => options.direction === "UNCLASSIFIED",
      ),
    ).toBe(false);
    expect(screen.getAllByText("--").length).toBeGreaterThanOrEqual(3);
  });
  it("drills from the asset KPI into ASSET positions without changing date口径", async () => {
    const user = userEvent.setup();
    const client = buildClient();
    renderWorkbenchApp(["/bank-ledger-dashboard?as_of_date=2026-03-17"], { client });

    await screen.findByText("asset-key");
    await user.click(
      within(screen.getByTestId("ledger-dashboard-kpi-asset")).getByRole("button", { name: "明细" }),
    );

    await waitFor(() => {
      expect(client.getLedgerPositions).toHaveBeenLastCalledWith({
        asOfDate: "2026-03-17",
        currency: "CNY",
        direction: "ASSET",
        page: 1,
        pageSize: 20,
      });
    });
    expect(screen.getByTestId("ledger-dashboard-positions-panel")).toHaveTextContent("资产 · 1 条");
    expect(screen.queryByText("liability-key")).not.toBeInTheDocument();
  });

  it("hydrates currency when the same route URL changes after mount", async () => {
    const client = buildClient();
    const router = createWorkbenchMemoryRouter([
      "/bank-ledger-dashboard?as_of_date=2026-03-17&currency=CNY",
    ]);
    render(
      <AppProviders client={client}>
        <RouterProvider router={router} />
      </AppProviders>,
    );

    await waitFor(() => expect(screen.getByLabelText("ledger-dashboard-currency")).toHaveValue("CNY"));
    const observedSearches: string[] = [];
    const unsubscribe = router.subscribe((state) => observedSearches.push(state.location.search));
    await router.navigate("/bank-ledger-dashboard?as_of_date=2026-03-17&currency=USD");

    await waitFor(() => expect(screen.getByLabelText("ledger-dashboard-currency")).toHaveValue("USD"));
    expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("2.00 USD/1亿");
    await waitFor(() => expect(client.getLedgerPositions).toHaveBeenLastCalledWith(expect.objectContaining({ currency: "USD" })));
    await waitFor(() => expect(router.state.location.search).toContain("currency=USD"));
    unsubscribe();
    expect(observedSearches.filter((search) => search.includes("currency=CNY"))).toEqual([]);
  });
  it("writes UNCLASSIFIED to the URL and restores it through back and forward history", async () => {
    const user = userEvent.setup();
    const client = buildClient();
    const router = createWorkbenchMemoryRouter([
      "/bank-ledger-dashboard?as_of_date=2026-03-17&currency=CNY",
    ]);
    render(
      <AppProviders client={client}>
        <RouterProvider router={router} />
      </AppProviders>,
    );

    const quality = await screen.findByTestId("ledger-dashboard-classification-quality");
    await waitFor(() => expect(quality).toHaveTextContent("覆盖率 100.00%"));
    await user.click(within(quality).getByRole("button", { name: "查看未分类明细" }));
    await waitFor(() => expect(router.state.location.search).toContain("direction=UNCLASSIFIED"));
    expect(screen.getByRole("button", { name: "未分类" })).toHaveClass("is-active");

    await router.navigate(-1);
    await waitFor(() => expect(router.state.location.search).not.toContain("direction="));
    await waitFor(() => expect(screen.getByRole("button", { name: "全部" })).toHaveClass("is-active"));

    await router.navigate(1);
    await waitFor(() => expect(router.state.location.search).toContain("direction=UNCLASSIFIED"));
    await waitFor(() => expect(screen.getByRole("button", { name: "未分类" })).toHaveClass("is-active"));
    expect(client.getLedgerPositions).toHaveBeenLastCalledWith(
      expect.objectContaining({ direction: "UNCLASSIFIED", currency: "CNY" }),
    );
  });
  it("switches currency and keeps positions and drill requests in the same bucket", async () => {
    const user = userEvent.setup();
    const client = buildClient();
    renderWorkbenchApp(["/bank-ledger-dashboard?as_of_date=2026-03-17"], { client });

    const currency = await screen.findByLabelText("ledger-dashboard-currency");
    await waitFor(() => expect(currency).toHaveValue("CNY"));
    await user.selectOptions(currency, "USD");
    await waitFor(() => expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("2.00 USD/1亿"));
    await waitFor(() => expect(client.getLedgerPositions).toHaveBeenLastCalledWith(expect.objectContaining({ currency: "USD" })));
    await user.click(within(screen.getByTestId("ledger-dashboard-kpi-asset")).getByRole("button"));
    await waitFor(() => expect(client.getLedgerPositions).toHaveBeenLastCalledWith(expect.objectContaining({ currency: "USD", direction: "ASSET" })));
  });
  it("surfaces fallback dates instead of silently treating them as current data", async () => {
    const client = buildClient({
      dashboard: (asOfDate) =>
        envelope<LedgerDashboardData>(
          {
            as_of_date: "2026-03-17",
            classification_status: "ready",
            classification_rule_version: "rv_ledger_classification_v2",
            currency_breakdown: [
              { currency: "CNY", asset_face_amount: 3289.07, liability_face_amount: 1231.77, net_face_exposure: 2057.31, classification_total_row_count: 2, unclassified_row_count: 0, unclassified_face_amount: 0, classification_coverage_pct: 100 },
              { currency: "USD", asset_face_amount: 2, liability_face_amount: null, net_face_exposure: 2, classification_total_row_count: 1, unclassified_row_count: 0, unclassified_face_amount: 0, classification_coverage_pct: 100 },
            ],
          },
          {
            metadata: { stale: true, fallback: true },
            trace: {
              request_id: "req_fallback_test",
              requested_as_of_date: asOfDate,
              resolved_as_of_date: "2026-03-17",
              batch_id: 7,
            },
          },
        ),
    });

    renderWorkbenchApp(["/bank-ledger-dashboard?as_of_date=2026-03-18"], { client });

    await waitFor(() => {
      expect(screen.getByLabelText("ledger-dashboard-as-of-date")).toHaveValue("2026-03-18");
    });
    expect(await screen.findByTestId("ledger-dashboard-status")).toHaveTextContent("已回退到 2026-03-17");
    expect(screen.getByTestId("ledger-dashboard-status")).toHaveTextContent("请求日期 2026-03-18");
    expect(client.getLedgerDashboard).toHaveBeenCalledWith("2026-03-18");
  });

  it("keeps an explicit as_of_date dashboard usable when dates lookup fails", async () => {
    const client = buildClient({
      datesError: new Error("dates unavailable"),
    });

    renderWorkbenchApp(["/bank-ledger-dashboard?as_of_date=2026-03-17"], { client });

    await waitFor(() => {
      expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("3289.07 CNY/1亿");
    });
    expect(screen.queryByText("加载失败")).not.toBeInTheDocument();
    expect(client.getLedgerDashboard).toHaveBeenCalledWith("2026-03-17");
  });

  it("surfaces positions loading failure independently from dashboard KPIs", async () => {
    const client = buildClient({
      positions: async () => {
        throw new Error("positions unavailable");
      },
    });

    renderWorkbenchApp(["/bank-ledger-dashboard?as_of_date=2026-03-17"], { client });

    await waitFor(() => {
      expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("3289.07 CNY/1亿");
    });
    expect(await screen.findByTestId("ledger-dashboard-positions-status")).toHaveTextContent("明细加载失败");
  });

  it("surfaces positions fallback lineage from the positions endpoint", async () => {
    const client = buildClient({
      positions: async (options) => ({
        ...positionsPayload(options),
        metadata: {
          ...metadata,
          stale: true,
          fallback: true,
        },
        trace: {
          request_id: "req_positions_fallback",
          requested_as_of_date: options.asOfDate,
          resolved_as_of_date: "2026-03-17",
          batch_id: 7,
          filters: options,
        },
      }),
    });

    renderWorkbenchApp(["/bank-ledger-dashboard?as_of_date=2026-03-18"], { client });

    expect(await screen.findByTestId("ledger-dashboard-positions-status")).toHaveTextContent(
      "明细已回退到 2026-03-17",
    );
    expect(screen.getByTestId("ledger-dashboard-evidence")).toHaveTextContent("req_positions_fallback");
    expect(screen.getByTestId("ledger-dashboard-evidence")).toHaveTextContent("positions trace");
  });

  it("surfaces positions no-data state from the positions endpoint", async () => {
    const client = buildClient({
      positions: async (options) => ({
        ...positionsPayload(options),
        data: {
          items: [],
          page: 1,
          page_size: 20,
          total: 0,
        },
        metadata: {
          ...metadata,
          no_data: true,
        },
      }),
    });

    renderWorkbenchApp(["/bank-ledger-dashboard?as_of_date=2026-03-17"], { client });

    expect(await screen.findByTestId("ledger-dashboard-positions-status")).toHaveTextContent("明细暂无数据");
    expect(screen.getByText("暂无匹配明细")).toBeInTheDocument();
  });

  it("surfaces positions stale state from the positions endpoint", async () => {
    const client = buildClient({
      positions: async (options) => ({
        ...positionsPayload(options),
        metadata: {
          ...metadata,
          stale: true,
        },
        trace: {
          request_id: "req_positions_stale",
          requested_as_of_date: options.asOfDate,
          resolved_as_of_date: "2026-03-17",
          batch_id: 7,
          filters: options,
        },
      }),
    });

    renderWorkbenchApp(["/bank-ledger-dashboard?as_of_date=2026-03-17"], { client });

    expect(await screen.findByTestId("ledger-dashboard-positions-status")).toHaveTextContent(
      "明细数据截至 2026-03-17",
    );
    expect(screen.getByTestId("ledger-dashboard-evidence")).toHaveTextContent("req_positions_stale");
  });

  it("shows no-data state without fabricating dashboard KPIs", async () => {
    const client = buildClient({
      dates: envelope<LedgerDatesData>(
        { items: [] },
        {
          metadata: {
            source_version: null,
            rule_version: null,
            batch_id: null,
            no_data: true,
          },
          trace: { request_id: "req_no_data", batch_id: null },
        },
      ),
    });

    renderWorkbenchApp(["/bank-ledger-dashboard"], { client });

    expect(await screen.findByTestId("ledger-dashboard-status")).toHaveTextContent("暂无数据");
    expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("--");
    const quality = screen.getByTestId("ledger-dashboard-classification-quality");
    expect(quality).toHaveTextContent("暂无可评估分类质量");
    expect(within(quality).queryByRole("button", { name: "查看未分类明细" })).not.toBeInTheDocument();
    expect(client.getLedgerDashboard).not.toHaveBeenCalled();
  });

  it("drops cached UNCLASSIFIED detail when refreshed classification is not ready", async () => {
    const user = userEvent.setup();
    let dashboardReads = 0;
    const client = buildClient({
      dashboard: () => {
        dashboardReads += 1;
        if (dashboardReads === 1) {
          return envelope<LedgerDashboardData>({
            as_of_date: "2026-03-17",
            classification_status: "ready",
            classification_rule_version: "rv_ledger_classification_v2",
            currency_breakdown: [{
              currency: "CNY",
              asset_face_amount: 1,
              liability_face_amount: null,
              net_face_exposure: 1,
              classification_total_row_count: 1,
              unclassified_row_count: 1,
              unclassified_face_amount: 1,
              classification_coverage_pct: 0,
            }],
          });
        }
        return envelope<LedgerDashboardData>({
          as_of_date: "2026-03-17",
          classification_status: "legacy_unassessed",
          classification_rule_version: "rv_ledger_classification_v2",
          currency_breakdown: [{
            currency: "CNY",
            asset_face_amount: null,
            liability_face_amount: null,
            net_face_exposure: null,
            classification_total_row_count: 1,
            unclassified_row_count: null,
            unclassified_face_amount: null,
            classification_coverage_pct: null,
          }],
        });
      },
      positions: async (options) => {
        const response = positionsPayload({ ...options, direction: undefined });
        if (options.direction !== "UNCLASSIFIED") {
          return { ...response, data: { ...response.data, items: [], total: 0 } };
        }
        const cached = {
          ...response.data.items[0],
          position_key: "cached-u-key",
          direction: "UNCLASSIFIED" as const,
          trace: { position_key: "cached-u-key", batch_id: 7, row_no: 1 },
        };
        return { ...response, data: { ...response.data, items: [cached], total: 1 } };
      },
      importLedger: async (file) => ({
        data: { run_id: "ledger_import:invalidate-u", status: "queued", file_name: file.name },
        trace: { request_id: "req_invalidate_u", run_id: "ledger_import:invalidate-u" },
      }),
      importStatus: async (runId) => ({
        data: { run_id: runId, status: "succeeded", file_name: "ledger.csv", batch_id: 8 },
        trace: { request_id: "req_invalid_materialization", run_id: runId },
      }),
    });
    renderWorkbenchApp([
      "/bank-ledger-dashboard?as_of_date=2026-03-17&currency=CNY&direction=UNCLASSIFIED",
    ], { client });

    expect(await screen.findByText("cached-u-key")).toBeInTheDocument();
    const file = new File(["ledger"], "ledger.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("台账文件"), file);
    await user.click(screen.getByRole("button", { name: "开始导入" }));

    const quality = await screen.findByTestId("ledger-dashboard-classification-quality");
    await waitFor(() => expect(quality).toHaveTextContent("旧规则批次不可评估"));
    expect(within(quality).queryByRole("button", { name: "查看未分类明细" })).not.toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("cached-u-key")).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole("button", { name: "全部" })).toHaveClass("is-active"));
    expect(
      vi.mocked(client.getLedgerPositions).mock.calls.filter(
        ([options]) => options.direction === "UNCLASSIFIED",
      ),
    ).toHaveLength(2);
  });
  it("uploads a ledger file and polls running through succeeded", async () => {
    const user = userEvent.setup();
    const statusResponses: LedgerImportResponse[] = [
      {
        data: {
          run_id: "ledger_import:progress",
          status: "running",
          file_name: "ledger.xlsx",
          started_at: "2026-07-11T04:00:01Z",
        },
        trace: { request_id: "req_running", run_id: "ledger_import:progress" },
      },
      {
        data: {
          run_id: "ledger_import:progress",
          status: "succeeded",
          file_name: "ledger.xlsx",
          batch_id: 12,
          finished_at: "2026-07-11T04:00:02Z",
        },
        trace: { request_id: "req_succeeded", run_id: "ledger_import:progress" },
      },
    ];
    let dashboardReads = 0;
    let positionReads = 0;
    const client = buildClient({
      dashboard: () => {
        dashboardReads += 1;
        if (dashboardReads === 1) {
          return envelope<LedgerDashboardData>({
            as_of_date: "2026-03-17",
            classification_status: "ready",
            classification_rule_version: "rv_ledger_classification_v2",
            currency_breakdown: [
              { currency: "CNY", asset_face_amount: 3289.07, liability_face_amount: 1231.77, net_face_exposure: 2057.31, classification_total_row_count: 2, unclassified_row_count: 0, unclassified_face_amount: 0, classification_coverage_pct: 100 },
            ],
          });
        }
        return envelope<LedgerDashboardData>(
          {
            as_of_date: "2026-03-17",
            classification_status: "ready",
            classification_rule_version: "rv_ledger_classification_v2",
            currency_breakdown: [
              { currency: "CNY", asset_face_amount: 4000, liability_face_amount: 1000, net_face_exposure: 3000, classification_total_row_count: 2, unclassified_row_count: 0, unclassified_face_amount: 0, classification_coverage_pct: 100 },
            ],
          },
          { metadata: { batch_id: 12 }, trace: { batch_id: 12 } },
        );
      },
      positions: async (options) => {
        positionReads += 1;
        const response = positionsPayload(options);
        if (positionReads === 1) return response;
        const imported = {
          ...response.data.items[0],
          position_key: "imported-batch-12-row",
          batch_id: 12,
          bond_code: "IMPORTED-012",
          face_amount: 250000000,
          trace: { position_key: "imported-batch-12-row", batch_id: 12, row_no: 1 },
        };
        return {
          ...response,
          data: { ...response.data, items: [imported], total: 1 },
          metadata: { ...response.metadata, batch_id: 12 },
          trace: { ...response.trace, batch_id: 12 },
        };
      },
      importLedger: async (file) => ({
        data: { run_id: "ledger_import:progress", status: "queued", file_name: file.name },
        trace: { request_id: "req_queued", run_id: "ledger_import:progress" },
      }),
      importStatus: async () => statusResponses.shift() ?? statusResponses[0],
    });
    vi.mocked(client.getLedgerDates)
      .mockResolvedValueOnce(envelope<LedgerDatesData>({ items: ["2026-03-17"] }))
      .mockResolvedValueOnce(
        envelope<LedgerDatesData>(
          { items: ["2026-03-18", "2026-03-17"] },
          { metadata: { batch_id: 12 }, trace: { batch_id: 12 } },
        ),
      );
    renderWorkbenchApp(["/bank-ledger-dashboard"], { client });
    const file = new File(["ledger"], "ledger.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    await user.upload(await screen.findByLabelText("台账文件"), file);
    await user.click(screen.getByRole("button", { name: "开始导入" }));

    expect(await screen.findByRole("status")).toHaveTextContent("正在校验并导入");
    expect(screen.getByRole("button", { name: "正在导入" })).toBeDisabled();
    expect(await screen.findByText("导入完成", {}, { timeout: 3_000 })).toBeInTheDocument();
    expect(screen.getByTestId("ledger-import-status")).toHaveTextContent("batch_id 12");
    expect(client.getLedgerDates).toHaveBeenCalledTimes(2);
    expect(client.getLedgerDashboard).toHaveBeenCalledTimes(2);
    expect(client.getLedgerPositions).toHaveBeenCalledTimes(2);
    expect(await screen.findByText("imported-batch-12-row")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("4000.00 CNY/1亿");
    expect(screen.getByTestId("ledger-dashboard-evidence")).toHaveTextContent("12");
    expect(screen.getByLabelText("ledger-dashboard-as-of-date")).toContainHTML("2026-03-18");
  });

  it("renders duplicate as a successful terminal outcome", async () => {
    const user = userEvent.setup();
    const client = buildClient({
      importStatus: async (runId) => ({
        data: {
          run_id: runId,
          status: "duplicate",
          file_name: "ledger.csv",
          duplicate_of_batch_id: 7,
          finished_at: "2026-07-11T04:00:02Z",
        },
        trace: { request_id: "req_duplicate", run_id: runId },
      }),
    });
    renderWorkbenchApp(["/bank-ledger-dashboard"], { client });

    await user.upload(
      await screen.findByLabelText("台账文件"),
      new File(["ledger"], "ledger.csv", { type: "text/csv" }),
    );
    await user.click(screen.getByRole("button", { name: "开始导入" }));

    expect(await screen.findByText("文件内容已存在，未新增批次")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-import-status")).toHaveTextContent("duplicate_of_batch_id 7");
    expect(screen.queryByText("导入失败")).not.toBeInTheDocument();
  });

  it("restores a pending run from session storage without re-uploading", async () => {
    window.sessionStorage.setItem(
      "moss.ledgerImport.pendingRun.v1",
      JSON.stringify({ run_id: "ledger_import:restored", mode: "real", file_name: "restored.xlsx" }),
    );
    const client = buildClient();

    renderWorkbenchApp(["/bank-ledger-dashboard"], { client });

    expect(await screen.findByText("导入完成")).toBeInTheDocument();
    expect(client.getLedgerImportStatus).toHaveBeenCalledWith(
      "ledger_import:restored",
      expect.any(AbortSignal),
    );
    expect(client.importLedger).not.toHaveBeenCalled();
    expect(window.sessionStorage.getItem("moss.ledgerImport.pendingRun.v1")).toBeNull();
  });

  it("keeps polling errors separate from a confirmed import failure", async () => {
    window.sessionStorage.setItem(
      "moss.ledgerImport.pendingRun.v1",
      JSON.stringify({ run_id: "ledger_import:unknown", mode: "real", file_name: "unknown.xlsx" }),
    );
    const client = buildClient({
      importStatus: async () => {
        throw new Error("network unavailable");
      },
    });

    renderWorkbenchApp(["/bank-ledger-dashboard"], { client });

    expect(await screen.findByRole("alert")).toHaveTextContent("当前无法确认导入状态");
    expect(screen.queryByText("导入失败")).not.toBeInTheDocument();
    expect(window.sessionStorage.getItem("moss.ledgerImport.pendingRun.v1")).toContain(
      "ledger_import:unknown",
    );
  });

  it("shows a confirmed failure with safe facts and permits resubmission", async () => {
    const user = userEvent.setup();
    const client = buildClient({
      importStatus: async (runId) => ({
        data: {
          run_id: runId,
          status: "failed",
          file_name: "invalid.xlsx",
          error_category: "invalid_file",
          error_message: "Ledger file validation failed.",
          finished_at: "2026-07-11T04:00:02Z",
        },
        trace: { request_id: "req_failed", run_id: runId },
      }),
    });
    renderWorkbenchApp(["/bank-ledger-dashboard"], { client });
    await user.upload(
      await screen.findByLabelText("台账文件"),
      new File(["invalid"], "invalid.xlsx", {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      }),
    );

    await user.click(screen.getByRole("button", { name: "开始导入" }));

    expect(await screen.findByText("导入失败")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-import-status")).toHaveTextContent("invalid_file");
    expect(screen.getByTestId("ledger-import-status")).toHaveTextContent(
      "Ledger file validation failed.",
    );
    expect(screen.getByLabelText("台账文件")).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "开始导入" }));
    expect(client.importLedger).toHaveBeenCalledTimes(2);
  });

  it("keeps a forbidden status run recoverable and retries on demand", async () => {
    const user = userEvent.setup();
    window.sessionStorage.setItem(
      "moss.ledgerImport.pendingRun.v1",
      JSON.stringify({ run_id: "ledger_import:forbidden", mode: "real", file_name: "forbidden.xlsx" }),
    );
    let attempts = 0;
    const client = buildClient({
      importStatus: async (runId) => {
        attempts += 1;
        if (attempts === 1) {
          throw new LedgerRequestError(
            "Ledger read access denied.",
            "LEDGER_READ_FORBIDDEN",
            403,
            false,
          );
        }
        return {
          data: {
            run_id: runId,
            status: "succeeded",
            file_name: "forbidden.xlsx",
            batch_id: 11,
          },
          trace: { request_id: "req_recovered", run_id: runId },
        };
      },
    });
    renderWorkbenchApp(["/bank-ledger-dashboard"], { client });

    expect(await screen.findByRole("alert")).toHaveTextContent("无权查询导入状态");
    expect(window.sessionStorage.getItem("moss.ledgerImport.pendingRun.v1")).toContain(
      "ledger_import:forbidden",
    );
    await user.click(screen.getByRole("button", { name: "继续查询" }));

    expect(await screen.findByText("导入完成")).toBeInTheDocument();
    expect(client.getLedgerImportStatus).toHaveBeenCalledTimes(2);
  });

  it("clears a stale restored run when the backend returns not found", async () => {
    window.sessionStorage.setItem(
      "moss.ledgerImport.pendingRun.v1",
      JSON.stringify({ run_id: "ledger_import:stale", mode: "real", file_name: "stale.xlsx" }),
    );
    const client = buildClient({
      importStatus: async () => {
        throw new LedgerRequestError(
          "Ledger import run was not found.",
          "LEDGER_IMPORT_RUN_NOT_FOUND",
          404,
          false,
        );
      },
    });

    renderWorkbenchApp(["/bank-ledger-dashboard"], { client });

    expect(await screen.findByRole("alert")).toHaveTextContent("导入任务记录不存在");
    expect(screen.getByLabelText("台账文件")).toBeEnabled();
    expect(screen.getByRole("button", { name: "开始导入" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "继续查询" })).not.toBeInTheDocument();
    expect(window.sessionStorage.getItem("moss.ledgerImport.pendingRun.v1")).toBeNull();
  });

  it("aborts an in-flight status request when the page unmounts", async () => {
    window.sessionStorage.setItem(
      "moss.ledgerImport.pendingRun.v1",
      JSON.stringify({ run_id: "ledger_import:inflight", mode: "real", file_name: "inflight.xlsx" }),
    );
    let observedSignal: AbortSignal | undefined;
    let requestRejected = false;
    const client = buildClient({
      importStatus: async (_runId, signal) => {
        observedSignal = signal;
        return new Promise<LedgerImportResponse>((_resolve, reject) => {
          signal?.addEventListener("abort", () => {
            requestRejected = true;
            reject(new DOMException("Aborted", "AbortError"));
          });
        });
      },
    });

    const view = renderWorkbenchApp(["/bank-ledger-dashboard"], { client });
    await waitFor(() => expect(observedSignal).toBeDefined());

    view.unmount();

    expect(observedSignal?.aborted).toBe(true);
    await waitFor(() => expect(requestRejected).toBe(true));
  });

  it("times out and aborts a status request that never settles", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    window.sessionStorage.setItem(
      "moss.ledgerImport.pendingRun.v1",
      JSON.stringify({ run_id: "ledger_import:timeout", mode: "real", file_name: "timeout.xlsx" }),
    );
    let observedSignal: AbortSignal | undefined;
    const client = buildClient({
      importStatus: async (_runId, signal) => {
        observedSignal = signal;
        return new Promise<LedgerImportResponse>((_resolve, reject) => {
          signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        });
      },
    });

    renderWorkbenchApp(["/bank-ledger-dashboard"], { client });
    await waitFor(() => expect(observedSignal).toBeDefined());
    await vi.advanceTimersByTimeAsync(10_001);

    expect(await screen.findByRole("alert")).toHaveTextContent("导入状态请求超时");
    expect(observedSignal?.aborted).toBe(true);
    expect(window.sessionStorage.getItem("moss.ledgerImport.pendingRun.v1")).toContain(
      "ledger_import:timeout",
    );
  });
});
