import { useRef, useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { LedgerMoneyValue, ResultMeta } from "../api/contracts";
import LedgerPnlPage from "../features/ledger-pnl/pages/LedgerPnlPage";

const REPORT_DATE = "2026-04-30";
const EXTERNAL_REPORT_DATE = "2026-05-31";

function buildMeta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "ledger",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_ledger_currency_basis_test",
    vendor_version: "vv_none",
    rule_version: "rv_ledger_currency_basis_test",
    cache_version: "cv_ledger_currency_basis_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-05-01T00:00:00Z",
    tables_used: ["qdb_general_ledger_workbook"],
  };
}

function money(yuan: string): LedgerMoneyValue {
  return {
    yuan,
    yi: (Number(yuan) / 100_000_000).toFixed(2),
  } as LedgerMoneyValue;
}

function LocationSearchProbe() {
  const location = useLocation();
  const lastSearch = useRef(location.search);
  const searchChangeCount = useRef(0);
  if (lastSearch.current !== location.search) {
    lastSearch.current = location.search;
    searchChangeCount.current += 1;
  }
  expect(searchChangeCount.current).toBeLessThan(10);
  return <output data-testid="location-search">{location.search}</output>;
}

function ExternalNavigationProbe({ to }: { to: string | undefined }) {
  const navigate = useNavigate();
  return to ? (
    <button type="button" data-testid="external-navigation" onClick={() => navigate(to)}>
      external navigation
    </button>
  ) : null;
}

function renderLedgerPnlPage(client: ApiClient, initialEntry: string, externalNavigationEntry?: string) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter initialEntries={[initialEntry]}>
            {children}
            <LocationSearchProbe />
            <ExternalNavigationProbe to={externalNavigationEntry} />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(
    <Wrapper>
      <LedgerPnlPage />
    </Wrapper>,
  );
}

function createLedgerCurrencyBasisClient() {
  const base = createApiClient({ mode: "mock" });
  const getLedgerPnlAnalysis = vi.fn((reportDate: string, currency?: string) =>
    base.getLedgerPnlAnalysis(reportDate, currency),
  );
  const getLedgerPnlSummary = vi.fn(async (_reportDate: string, _currency?: string) => ({
    result_meta: buildMeta("ledger_pnl.summary"),
    result: {
      report_date: REPORT_DATE,
      source_version: "sv_ledger_currency_basis_test",
      ledger_monthly_pnl_core: money("100000000.00"),
      ledger_monthly_pnl_all: money("100000000.00"),
      ledger_total_assets: money("1000000000.00"),
      ledger_total_liabilities: money("400000000.00"),
      ledger_net_assets: money("600000000.00"),
      by_currency: [
        { currency: "CNX", total_pnl: money("100000000.00") },
        { currency: "CNY", total_pnl: money("90000000.00") },
        { currency: "USD", total_pnl: money("10000000.00") },
      ],
      by_account: [],
    },
  }));
  const getLedgerPnlData = vi.fn(async (_reportDate: string, _currency?: string) => ({
    result_meta: buildMeta("ledger_pnl.data"),
    result: {
      report_date: REPORT_DATE,
      summary: {
        total_pnl_cnx: money("100000000.00"),
        total_pnl_cny: money("90000000.00"),
        total_pnl: money("100000000.00"),
        count: 0,
      },
      items: [],
    },
  }));
  const client: ApiClient = {
    ...base,
    getLedgerPnlDates: vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.dates"),
      result: { dates: [REPORT_DATE] },
    })),
    getLedgerPnlSummary,
    getLedgerPnlData,
    getLedgerPnlAnalysis,
  };

  return { client, getLedgerPnlSummary, getLedgerPnlData, getLedgerPnlAnalysis };
}

function currentCurrencyQuery() {
  return new URLSearchParams(screen.getByTestId("location-search").textContent ?? "").get("currency");
}

function currentReportDateQuery() {
  return new URLSearchParams(screen.getByTestId("location-search").textContent ?? "").get("report_date");
}

describe("LedgerPnlPage currency basis", () => {
  it.each([
    ["missing currency", `/ledger-pnl?report_date=${REPORT_DATE}`],
    ["legacy ALL", `/ledger-pnl?report_date=${REPORT_DATE}&currency=ALL`],
    ["unsupported currency", `/ledger-pnl?report_date=${REPORT_DATE}&currency=USD`],
  ])("normalizes %s to CNX for every ledger read and the URL", async (_caseName, initialEntry) => {
    const { client, getLedgerPnlSummary, getLedgerPnlData, getLedgerPnlAnalysis } =
      createLedgerCurrencyBasisClient();

    renderLedgerPnlPage(client, initialEntry);

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith(REPORT_DATE, "CNX");
      expect(getLedgerPnlData).toHaveBeenCalledWith(REPORT_DATE, "CNX");
      expect(getLedgerPnlAnalysis).toHaveBeenCalledWith(REPORT_DATE, "CNX");
      expect(currentCurrencyQuery()).toBe("CNX");
    });
  });

  it("offers only the two overlapping accounting bases with explicit labels", async () => {
    const { client } = createLedgerCurrencyBasisClient();

    renderLedgerPnlPage(client, `/ledger-pnl?report_date=${REPORT_DATE}`);

    const control = await screen.findByRole("combobox", { name: "总账损益账务口径" });
    expect(within(control).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "CNX（综本）",
      "CNY（人民币账）",
    ]);
    expect(within(control).queryByRole("option", { name: "ALL" })).not.toBeInTheDocument();
    expect(within(control).queryByRole("option", { name: "USD" })).not.toBeInTheDocument();
    expect(screen.getByText(/重叠账务口径/)).toHaveTextContent("不可相加");
  });

  it("passes CNY explicitly to both reads after the user changes basis", async () => {
    const user = userEvent.setup();
    const { client, getLedgerPnlSummary, getLedgerPnlData, getLedgerPnlAnalysis } =
      createLedgerCurrencyBasisClient();

    renderLedgerPnlPage(client, `/ledger-pnl?report_date=${REPORT_DATE}`);

    const control = await screen.findByRole("combobox", { name: "总账损益账务口径" });
    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith(REPORT_DATE, "CNX");
      expect(getLedgerPnlData).toHaveBeenCalledWith(REPORT_DATE, "CNX");
      expect(getLedgerPnlAnalysis).toHaveBeenCalledWith(REPORT_DATE, "CNX");
    });
    getLedgerPnlSummary.mockClear();
    getLedgerPnlData.mockClear();
    getLedgerPnlAnalysis.mockClear();

    await user.selectOptions(control, "CNY");

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith(REPORT_DATE, "CNY");
      expect(getLedgerPnlData).toHaveBeenCalledWith(REPORT_DATE, "CNY");
      expect(getLedgerPnlAnalysis).toHaveBeenCalledWith(REPORT_DATE, "CNY");
      expect(currentCurrencyQuery()).toBe("CNY");
    });
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(control).toHaveValue("CNY");
    expect(currentCurrencyQuery()).toBe("CNY");
    expect(getLedgerPnlSummary.mock.calls.map((call) => call[1])).not.toContain("CNX");
    expect(getLedgerPnlData.mock.calls.map((call) => call[1])).not.toContain("CNX");
    expect(getLedgerPnlAnalysis.mock.calls.map((call) => call[1])).not.toContain("CNX");
  });

  it("stabilizes an external report date navigation without reverting to the previous date", async () => {
    const user = userEvent.setup();
    const { client, getLedgerPnlSummary, getLedgerPnlData, getLedgerPnlAnalysis } =
      createLedgerCurrencyBasisClient();

    renderLedgerPnlPage(
      client,
      `/ledger-pnl?report_date=${REPORT_DATE}&currency=CNY&view=detail`,
      `/ledger-pnl?report_date=${EXTERNAL_REPORT_DATE}&currency=CNY&view=detail`,
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith(REPORT_DATE, "CNY");
      expect(getLedgerPnlData).toHaveBeenCalledWith(REPORT_DATE, "CNY");
      expect(getLedgerPnlAnalysis).toHaveBeenCalledWith(REPORT_DATE, "CNY");
    });
    getLedgerPnlSummary.mockClear();
    getLedgerPnlData.mockClear();
    getLedgerPnlAnalysis.mockClear();

    await user.click(screen.getByTestId("external-navigation"));

    await waitFor(() => {
      expect(screen.getByTestId("ledger-pnl-report-date-control")).toHaveValue(EXTERNAL_REPORT_DATE);
      expect(currentReportDateQuery()).toBe(EXTERNAL_REPORT_DATE);
      expect(currentCurrencyQuery()).toBe("CNY");
      expect(screen.getByText("当前报告日不在可选列表中，仍按查询日期读取总账数据")).toBeInTheDocument();
      expect(getLedgerPnlSummary).toHaveBeenCalledWith(EXTERNAL_REPORT_DATE, "CNY");
      expect(getLedgerPnlData).toHaveBeenCalledWith(EXTERNAL_REPORT_DATE, "CNY");
      expect(getLedgerPnlAnalysis).toHaveBeenCalledWith(EXTERNAL_REPORT_DATE, "CNY");
    });
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(screen.getByTestId("ledger-pnl-report-date-control")).toHaveValue(EXTERNAL_REPORT_DATE);
    expect(currentReportDateQuery()).toBe(EXTERNAL_REPORT_DATE);
    expect(new URLSearchParams(screen.getByTestId("location-search").textContent ?? "").get("view")).toBe(
      "detail",
    );
    expect(getLedgerPnlSummary.mock.calls.every((call) => call[0] === EXTERNAL_REPORT_DATE && call[1] === "CNY"))
      .toBe(true);
    expect(getLedgerPnlData.mock.calls.every((call) => call[0] === EXTERNAL_REPORT_DATE && call[1] === "CNY"))
      .toBe(true);
    expect(getLedgerPnlAnalysis.mock.calls.every((call) => call[0] === EXTERNAL_REPORT_DATE && call[1] === "CNY"))
      .toBe(true);
  });
});
