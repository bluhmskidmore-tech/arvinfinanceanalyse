import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import type {
  LedgerApiResponse,
  LedgerDashboardData,
  LedgerDatesData,
  LedgerPositionsData,
  LedgerPositionsOptions,
} from "../api/ledgerClient";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

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
            asset_face_amount: 3289.07,
            liability_face_amount: 1231.77,
            net_face_exposure: 2057.31,
            alert_count: 0,
          }),
    ),
    getLedgerPositions: vi.fn(async (options: LedgerPositionsOptions) =>
      overrides?.positions ? overrides.positions(options) : positionsPayload(options),
    ),
  };
}

describe("LedgerDashboardPage", () => {
  it("renders ledger KPI units, trace metadata, and raw-yuan position rows", async () => {
    const client = buildClient();
    renderWorkbenchApp(["/bank-ledger-dashboard"], { client });

    expect(await screen.findByTestId("ledger-dashboard-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("ledger-dashboard-as-of-date")).toHaveValue("2026-03-17");
    });

    await waitFor(() => {
      expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("3289.07 亿元");
      expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("1231.77 亿元");
      expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("2057.31 亿元");
    });
    expect(screen.getByTestId("ledger-dashboard-evidence")).toHaveTextContent("sv_ledger_test");
    expect(screen.getByTestId("ledger-dashboard-evidence")).toHaveTextContent("requested_as_of_date");
    expect(await screen.findByText("asset-key")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-dashboard-positions-table")).toHaveTextContent("100,000,000.00");
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
        direction: "ASSET",
        page: 1,
        pageSize: 20,
      });
    });
    expect(screen.getByTestId("ledger-dashboard-positions-panel")).toHaveTextContent("资产 · 1 条");
    expect(screen.queryByText("liability-key")).not.toBeInTheDocument();
  });

  it("surfaces fallback dates instead of silently treating them as current data", async () => {
    const client = buildClient({
      dashboard: (asOfDate) =>
        envelope<LedgerDashboardData>(
          {
            as_of_date: "2026-03-17",
            asset_face_amount: 3289.07,
            liability_face_amount: 1231.77,
            net_face_exposure: 2057.31,
            alert_count: 0,
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
      expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("3289.07 亿元");
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
      expect(screen.getByTestId("ledger-dashboard-kpis")).toHaveTextContent("3289.07 亿元");
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
    expect(client.getLedgerDashboard).not.toHaveBeenCalled();
  });
});
