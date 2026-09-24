/**
 * ledger-pnl `date_semantics` gate 探针（交易日 vs 自然日 / 月末时点 vs 流量·YTD 口径）。
 *
 * Gap 记录："LedgerPnlCurrencyBasis covers report-date navigation stability only,
 * not trade-vs-natural date or month-end vs YTD basis." 本探针补齐的维度：
 *
 * 1. flow（流量/同期比）与 point（时点/年末比）两种日期基准的标签与数据字段绑定不可混用
 *    （LedgerPnlFinancialIndicatorSummaryPanel.tsx 的 compareHeaderLabel / periodGroupLabel /
 *    periodCompareLabel / periodCompareAvailable / splitRowsByBasis，均为模块私有，经组件渲染断言）：
 *    - flow 段表头必须是「上年同期」并绑定 flow_label / flow_compare_label / flow_compare_available；
 *    - point 段表头必须是「上年末」并绑定 point_label / point_compare_label / point_compare_available；
 *    - 混合 basis 分区（资产质量类）中每个行段挂在自己 basis 的表头下，不得串段；
 *    - 数值单元格严格按 period_id 绑定，不得按数组索引错位取数。
 *
 * 2. 报告日「必须为精确日历月末」的后端硬语义（backend/app/services/ledger_pnl_service.py
 *    `_require_exact_month_end`：monthrange 当月最后一天）在前端的体现：
 *    - 报告日控件是 <select>，只提供后端 dates 清单登记的报告日，不提供自由自然日输入；
 *    - mock dates 清单（前端可选日期的数据源快照）必须全部是精确日历月末，与后端硬语义相容；
 *    - URL 携带非月末自然日时，前端把它原样透传给 summary/data/analysis（由后端月末校验裁决），
 *      不做本地日期推算改写成月末，同时给出「不在可选列表」警示；
 *    - report_month 由 report_date 纯字符串切割（YYYY-MM → YYYYMM，LedgerPnlPage.tsx
 *      reportDateToMonth 的正则切割），不做任何本地日期数学。
 *
 * 3. YTD 流量口径与月末时点口径并存时的日期算术语义（mock 快照契约层，
 *    src/mocks/fixtures/ledgerPnlFinancialIndicatorSummary202603.json）：
 *    - flow_label 是年初至今累计期间（"2026年1月" / "2026年1-N月"），对比月 flow_compare_month
 *      是上年同月（同期比）；
 *    - point_label 是月末时点（"…月末"），对比月 point_compare_month 是上年 12 月（年末比）；
 *    - 面板 report_month 入参只做 trim 规范化透传；空报告月不发起查询、不猜测月份。
 *
 * 先红后绿：开发中临时把「flow 段对比表头 = 上年同期」断言改为期望「上年末」，
 * 实测得到红（expected "上年末", received "上年同期"），证据保存在专家报告中，此处已恢复契约断言。
 */
import { useRef, useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  LedgerMoneyValue,
  LedgerPnlIndicatorSummaryPayload,
  LedgerPnlIndicatorSummaryPeriod,
  LedgerPnlIndicatorSummaryRow,
  ResultMeta,
} from "../api/contracts";
import { AppProviders } from "../app/providers";
import { LedgerPnlFinancialIndicatorSummaryPanel } from "../features/ledger-pnl/components/LedgerPnlFinancialIndicatorSummaryPanel";
import LedgerPnlPage from "../features/ledger-pnl/pages/LedgerPnlPage";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { EM_DASH } from "../utils/format";

/** 镜像后端 `_require_exact_month_end` 的月末谓词（monthrange 当月最后一天），UTC 域避免时区漂移。 */
function isExactCalendarMonthEnd(isoDate: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (!match) return false;
  const [, year, month, day] = match;
  const monthNumber = Number(month);
  // 先拦截非法月份：Date.UTC 对 13 月会静默翻年，导致 2026-13-31 被误判为月末。
  if (monthNumber < 1 || monthNumber > 12) return false;
  const lastDay = new Date(Date.UTC(Number(year), monthNumber, 0)).getUTCDate();
  return Number(day) === lastDay;
}

function buildPeriod(
  overrides: Partial<LedgerPnlIndicatorSummaryPeriod> & { period_id: string },
): LedgerPnlIndicatorSummaryPeriod {
  return {
    flow_label: "2026年1-4月",
    flow_compare_label: "2025年1-4月",
    point_label: "2026年4月末",
    point_compare_label: "2025年末",
    current_month: "202604",
    flow_compare_month: "202504",
    point_compare_month: "202512",
    current_available: true,
    flow_compare_available: true,
    point_compare_available: true,
    ...overrides,
  };
}

function buildRow(
  overrides: Partial<LedgerPnlIndicatorSummaryRow> & {
    row_id: string;
    basis: "flow" | "point";
  },
): LedgerPnlIndicatorSummaryRow {
  return {
    name: `探针行 ${overrides.row_id}`,
    indent: 0,
    value_kind: "money_yi",
    availability: "ledger_computed",
    caliber_note: null,
    unavailable_reason: null,
    account_evidence: null,
    values: [],
    ...overrides,
  };
}

function buildSummaryPayload(
  overrides: Partial<LedgerPnlIndicatorSummaryPayload>,
): LedgerPnlIndicatorSummaryPayload {
  return {
    contract_version: "ledger-indicator-summary-date-semantics-probe",
    title: "经营指标情况表（总账口径）",
    report_month: "202604",
    report_year: 2026,
    currency_basis: "CNX",
    unit: "亿元",
    data_status: "ready",
    periods: [buildPeriod({ period_id: "p1" })],
    sections: [],
    quality_checks: [],
    coverage: { row_total: 0, row_computed: 0, row_unavailable: 0 },
    notes: ["date_semantics 探针夹具"],
    source_files: [],
    ...overrides,
  };
}

async function renderPanelWith(
  payload: LedgerPnlIndicatorSummaryPayload,
  reportMonth = "202604",
) {
  const client = createApiClient({ mode: "mock" });
  vi.spyOn(client, "getLedgerPnlFinancialIndicatorSummary").mockResolvedValue(
    buildMockApiEnvelope("ledger_pnl.financial_indicator_summary", payload),
  );
  render(
    <AppProviders client={client}>
      <LedgerPnlFinancialIndicatorSummaryPanel reportMonth={reportMonth} currency="CNX" />
    </AppProviders>,
  );
  return screen.findByTestId("ledger-pnl-financial-indicator-summary-panel");
}

describe("LedgerPnlDateSemanticsContract / flow 与 point 日期基准的标签-字段绑定", () => {
  it("flow 段绑定 flow_* 字段（上年同期），point 段绑定 point_* 字段（上年末），交叉不可混用", async () => {
    // 故意让两个基准的字段值互不相同、可用性不对称：若组件把任一字段绑错基准，断言必红。
    const period = buildPeriod({
      period_id: "p1",
      flow_label: "2026年1-4月",
      flow_compare_label: "2025年1-4月",
      point_label: "2026年4月末",
      point_compare_label: "2025年末",
      flow_compare_available: true,
      point_compare_available: false,
    });
    await renderPanelWith(
      buildSummaryPayload({
        periods: [period],
        sections: [
          {
            section_id: "financial",
            title: "财务指标",
            basis_note: "累计期间流量口径",
            rows: [
              buildRow({
                row_id: "flow-row",
                basis: "flow",
                values: [
                  { period_id: "p1", current: "10", compare: "8", delta: "2", delta_pct: "25" },
                ],
              }),
            ],
          },
          {
            section_id: "business",
            title: "业务指标",
            basis_note: "月末时点口径",
            rows: [
              buildRow({
                row_id: "point-row",
                basis: "point",
                values: [
                  { period_id: "p1", current: "100", compare: null, delta: null, delta_pct: null },
                ],
              }),
            ],
          },
        ],
        coverage: { row_total: 2, row_computed: 2, row_unavailable: 0 },
      }),
    );

    const flowSection = await screen.findByTestId("ledger-indicator-summary-section-financial");
    // flow 段：同期比表头 + YTD 期间标签（flow_label），不得出现年末比表头或时点标签（point_label）。
    expect(within(flowSection).getByText("上年同期")).toBeInTheDocument();
    expect(within(flowSection).queryByText("上年末")).not.toBeInTheDocument();
    expect(within(flowSection).getByText("2026年1-4月")).toBeInTheDocument();
    expect(within(flowSection).queryByText("2026年4月末")).not.toBeInTheDocument();
    // 对比列 title 绑定 flow_compare_label（上年同期期间），且 flow 可用时不得渲染「缺源」标记。
    const flowCompareHead = within(flowSection).getByText("上年同期").closest("th");
    expect(flowCompareHead).not.toBeNull();
    expect(flowCompareHead).toHaveAttribute("title", "2025年1-4月");
    expect(within(flowSection).queryByText("缺源")).not.toBeInTheDocument();

    const pointSection = screen.getByTestId("ledger-indicator-summary-section-business");
    // point 段：年末比表头 + 月末时点标签（point_label），不得出现同期比表头或 YTD 标签（flow_label）。
    expect(within(pointSection).getByText("上年末")).toBeInTheDocument();
    expect(within(pointSection).queryByText("上年同期")).not.toBeInTheDocument();
    expect(within(pointSection).getByText("2026年4月末")).toBeInTheDocument();
    expect(within(pointSection).queryByText("2026年1-4月")).not.toBeInTheDocument();
    // 对比列 title 绑定 point_compare_label（上年末时点）。
    const pointCompareHead = within(pointSection).getByText("上年末").closest("th");
    expect(pointCompareHead).not.toBeNull();
    expect(pointCompareHead).toHaveAttribute("title", "2025年末");
    // point_compare_available=false 只影响 point 段：缺源标记出现在 point 段并引用 point_compare_label。
    const pointMissingMarker = within(pointSection).getByText("缺源");
    expect(pointMissingMarker).toHaveAttribute(
      "title",
      expect.stringContaining("2025年末"),
    );
    expect(pointMissingMarker).toHaveAttribute(
      "title",
      expect.not.stringContaining("2025年1-4月"),
    );
  });

  it("混合 basis 分区内，每个行段挂在自己 basis 的表头下（flow→上年同期 / point→上年末），不得串段", async () => {
    // 模拟资产质量类混合口径：核销累计（flow）→ 余额时点（point）→ 再回到累计（flow）。
    await renderPanelWith(
      buildSummaryPayload({
        sections: [
          {
            section_id: "asset_quality",
            title: "资产质量指标",
            basis_note: "核销为累计期间、余额为月末时点",
            rows: [
              buildRow({
                row_id: "writeoff-flow",
                basis: "flow",
                values: [
                  { period_id: "p1", current: "1", compare: "1", delta: "0", delta_pct: "0" },
                ],
              }),
              buildRow({
                row_id: "balance-point",
                basis: "point",
                values: [
                  { period_id: "p1", current: "2", compare: "2", delta: "0", delta_pct: "0" },
                ],
              }),
              buildRow({
                row_id: "recovery-flow",
                basis: "flow",
                values: [
                  { period_id: "p1", current: "3", compare: "3", delta: "0", delta_pct: "0" },
                ],
              }),
            ],
          },
        ],
        coverage: { row_total: 3, row_computed: 3, row_unavailable: 0 },
      }),
    );

    const section = await screen.findByTestId(
      "ledger-indicator-summary-section-asset_quality",
    );
    // 按文档顺序扫描表格行：数据行归属于其上方最近一次出现的基准表头。
    const headerByRowId = new Map<string, string | null>();
    let currentCompareHeader: string | null = null;
    for (const tr of Array.from(section.querySelectorAll("tr"))) {
      const text = tr.textContent ?? "";
      if (text.includes("上年同期")) currentCompareHeader = "上年同期";
      else if (text.includes("上年末")) currentCompareHeader = "上年末";
      const testId = tr.getAttribute("data-testid");
      if (testId?.startsWith("ledger-indicator-summary-row-")) {
        headerByRowId.set(testId.replace("ledger-indicator-summary-row-", ""), currentCompareHeader);
      }
    }
    expect(headerByRowId.get("writeoff-flow")).toBe("上年同期");
    expect(headerByRowId.get("balance-point")).toBe("上年末");
    expect(headerByRowId.get("recovery-flow")).toBe("上年同期");
  });

  it("数值单元格严格按 period_id 绑定期间，不得按数组索引错位取数", async () => {
    // 两个期间列，行值数组只登记 p2 一个 cell：若实现按索引 zip，p2 的值会错位渲染进 p1 列。
    await renderPanelWith(
      buildSummaryPayload({
        periods: [
          buildPeriod({
            period_id: "p1",
            flow_label: "2026年1-3月",
            flow_compare_label: "2025年1-3月",
            current_month: "202603",
            flow_compare_month: "202503",
          }),
          buildPeriod({ period_id: "p2" }),
        ],
        sections: [
          {
            section_id: "financial",
            title: "财务指标",
            basis_note: "累计期间流量口径",
            rows: [
              buildRow({
                row_id: "period-binding",
                basis: "flow",
                values: [
                  {
                    period_id: "p2",
                    current: "11.11",
                    compare: "22.22",
                    delta: "33.33",
                    delta_pct: "44.44",
                  },
                ],
              }),
            ],
          },
        ],
        coverage: { row_total: 1, row_computed: 1, row_unavailable: 0 },
      }),
    );

    await screen.findByTestId("ledger-indicator-summary-section-financial");
    const row = screen.getByTestId("ledger-indicator-summary-row-period-binding");
    const cells = within(row)
      .getAllByRole("cell")
      .map((cell) => cell.textContent);
    // 列序：p1（本期/对比/增减额/增减幅）→ p2（本期/对比/增减额/增减幅）。
    expect(cells).toEqual([
      EM_DASH,
      EM_DASH,
      EM_DASH,
      EM_DASH,
      "11.11",
      "22.22",
      "+33.33",
      "+44.44%",
    ]);
  });
});

describe("LedgerPnlDateSemanticsContract / 报告日精确月末语义（镜像后端 _require_exact_month_end）", () => {
  it("月末谓词自检：平年/闰年二月与月中日期判定正确", () => {
    expect(isExactCalendarMonthEnd("2026-02-28")).toBe(true);
    expect(isExactCalendarMonthEnd("2024-02-29")).toBe(true);
    expect(isExactCalendarMonthEnd("2024-02-28")).toBe(false);
    expect(isExactCalendarMonthEnd("2026-04-30")).toBe(true);
    expect(isExactCalendarMonthEnd("2026-04-15")).toBe(false);
    expect(isExactCalendarMonthEnd("2026-13-31")).toBe(false);
  });

  it("mock 报告日清单（前端可选日期数据源）全部是精确日历月末，与后端硬语义相容", async () => {
    const client = createApiClient({ mode: "mock" });
    const envelope = await client.getLedgerPnlDates();
    const dates = envelope.result.dates;
    expect(dates.length).toBeGreaterThan(0);
    for (const reportDate of dates) {
      expect(
        isExactCalendarMonthEnd(reportDate),
        `${reportDate} 必须是精确日历月末（后端 _require_exact_month_end 会拒绝非月末报告日）`,
      ).toBe(true);
    }
  });
});

const PAGE_REPORT_DATES = ["2026-03-31", "2026-02-28", "2025-12-31"];
const NON_MONTH_END_DATE = "2026-04-15";

function buildPageMeta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "ledger",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_ledger_date_semantics_test",
    vendor_version: "vv_none",
    rule_version: "rv_ledger_date_semantics_test",
    cache_version: "cv_ledger_date_semantics_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-05-01T00:00:00Z",
    tables_used: ["qdb_general_ledger_workbook"],
  };
}

function pageMoney(yuan: string): LedgerMoneyValue {
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

function renderLedgerPnlPage(client: ApiClient, initialEntry: string) {
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

function createDateSemanticsPageClient() {
  const base = createApiClient({ mode: "mock" });
  const getLedgerPnlSummary = vi.fn(async (reportDate: string, _currency?: string) => ({
    result_meta: buildPageMeta("ledger_pnl.summary"),
    result: {
      report_date: reportDate,
      source_version: "sv_ledger_date_semantics_test",
      ledger_monthly_pnl_core: pageMoney("100000000.00"),
      ledger_monthly_pnl_all: pageMoney("100000000.00"),
      ledger_total_assets: pageMoney("1000000000.00"),
      ledger_total_liabilities: pageMoney("400000000.00"),
      ledger_net_assets: pageMoney("600000000.00"),
      by_currency: [{ currency: "CNX", total_pnl: pageMoney("100000000.00") }],
      by_account: [],
    },
  }));
  const getLedgerPnlData = vi.fn(async (reportDate: string, _currency?: string) => ({
    result_meta: buildPageMeta("ledger_pnl.data"),
    result: {
      report_date: reportDate,
      summary: {
        total_pnl_cnx: pageMoney("100000000.00"),
        total_pnl_cny: pageMoney("90000000.00"),
        total_pnl: pageMoney("100000000.00"),
        count: 0,
      },
      items: [],
    },
  }));
  const getLedgerPnlAnalysis = vi.fn((reportDate: string, currency?: string) =>
    base.getLedgerPnlAnalysis(reportDate, currency),
  );
  const getLedgerPnlFinancialIndicatorSummary = vi.fn(
    (reportMonth: string, currency?: string) =>
      base.getLedgerPnlFinancialIndicatorSummary(reportMonth, currency),
  );
  const client: ApiClient = {
    ...base,
    getLedgerPnlDates: vi.fn(async () => ({
      result_meta: buildPageMeta("ledger_pnl.dates"),
      result: { dates: PAGE_REPORT_DATES },
    })),
    getLedgerPnlSummary,
    getLedgerPnlData,
    getLedgerPnlAnalysis,
    getLedgerPnlFinancialIndicatorSummary,
  };
  return {
    client,
    getLedgerPnlSummary,
    getLedgerPnlData,
    getLedgerPnlAnalysis,
    getLedgerPnlFinancialIndicatorSummary,
  };
}

describe("LedgerPnlDateSemanticsContract / 非月末自然日透传与 report_month 纯切割（整页）", () => {
  it("URL 非月末日期原样透传给总账三读，不本地改写成月末；report_month 为 YYYY-MM 纯切割", async () => {
    const {
      client,
      getLedgerPnlSummary,
      getLedgerPnlData,
      getLedgerPnlAnalysis,
      getLedgerPnlFinancialIndicatorSummary,
    } = createDateSemanticsPageClient();

    renderLedgerPnlPage(client, `/ledger-pnl?report_date=${NON_MONTH_END_DATE}&currency=CNX`);

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith(NON_MONTH_END_DATE, "CNX");
      expect(getLedgerPnlData).toHaveBeenCalledWith(NON_MONTH_END_DATE, "CNX");
      expect(getLedgerPnlAnalysis).toHaveBeenCalledWith(NON_MONTH_END_DATE, "CNX");
    });
    // 经营指标区块经视口门控唤醒后才发查询，等待其收到纯切割的 report_month。
    await waitFor(
      () => {
        expect(getLedgerPnlFinancialIndicatorSummary).toHaveBeenCalledWith("202604", "CNX");
      },
      { timeout: 5000 },
    );

    // 三读的每一次调用都必须是原样日期：前端不得做「就近月末」等本地日期推算。
    const allReportDateCalls = [
      ...getLedgerPnlSummary.mock.calls,
      ...getLedgerPnlData.mock.calls,
      ...getLedgerPnlAnalysis.mock.calls,
    ].map((call) => call[0]);
    expect(allReportDateCalls.length).toBeGreaterThan(0);
    for (const requestedDate of allReportDateCalls) {
      expect(requestedDate).toBe(NON_MONTH_END_DATE);
    }
    // report_month 只允许 YYYYMM 纯切割结果，不得出现任何月末推算月份以外的值。
    for (const call of getLedgerPnlFinancialIndicatorSummary.mock.calls) {
      expect(call[0]).toBe("202604");
    }
    // URL 也保持原样日期，未被归一为月末。
    expect(
      new URLSearchParams(screen.getByTestId("location-search").textContent ?? "").get(
        "report_date",
      ),
    ).toBe(NON_MONTH_END_DATE);

    // 报告日控件是受限 <select>：只提供「URL 当前日期（带警示）+ 后端清单」，无自由自然日输入。
    const control = screen.getByTestId("ledger-pnl-report-date-control");
    expect(control.tagName).toBe("SELECT");
    expect(
      within(control)
        .getAllByRole("option")
        .map((option) => (option as HTMLOptionElement).value),
    ).toEqual([NON_MONTH_END_DATE, ...PAGE_REPORT_DATES]);
    expect(
      screen.getByText("当前报告日不在可选列表中，仍按查询日期读取总账数据"),
    ).toBeInTheDocument();
  });
});

describe("LedgerPnlDateSemanticsContract / YTD 流量与月末时点并存的日期算术语义（mock 快照契约）", () => {
  it("flow 对比月=上年同月（同期比），point 对比月=上年12月（年末比），标签区分累计期间与月末时点", async () => {
    const client = createApiClient({ mode: "mock" });
    const envelope = await client.getLedgerPnlFinancialIndicatorSummary("202603", "CNX");
    const payload = envelope.result;
    expect(payload.data_status).toBe("ready");
    expect(payload.periods.length).toBeGreaterThan(0);

    for (const period of payload.periods) {
      const year = Number(period.current_month.slice(0, 4));
      const month = Number(period.current_month.slice(4, 6));
      // flow（流量/YTD）：对比月是上年同月。
      expect(period.flow_compare_month).toBe(
        `${year - 1}${String(month).padStart(2, "0")}`,
      );
      // point（时点）：对比月固定为上年 12 月（上年末）。
      expect(period.point_compare_month).toBe(`${year - 1}12`);
      // 标签语义：point 是「…月末」时点文案；flow 是年初至今累计期间文案，不得带「末」。
      expect(period.point_label.endsWith("月末")).toBe(true);
      expect(period.flow_label.endsWith("末")).toBe(false);
      const expectedFlowLabel = month === 1 ? `${year}年1月` : `${year}年1-${month}月`;
      expect(period.flow_label).toBe(expectedFlowLabel);
      expect(period.flow_compare_label).toBe(
        month === 1 ? `${year - 1}年1月` : `${year - 1}年1-${month}月`,
      );
      expect(period.point_compare_label).toBe(`${year - 1}年末`);
    }
    // 报告月与末位期间对齐：YTD 序列推进到请求的报告月为止。
    expect(payload.report_month).toBe("202603");
    expect(payload.periods[payload.periods.length - 1].current_month).toBe("202603");
  });

  it("面板 report_month 入参只做 trim 透传；空报告月不发查询、不本地猜测月份", async () => {
    const client = createApiClient({ mode: "mock" });
    const spy = vi.spyOn(client, "getLedgerPnlFinancialIndicatorSummary");

    const { unmount } = render(
      <AppProviders client={client}>
        <LedgerPnlFinancialIndicatorSummaryPanel reportMonth=" 202603 " currency="CNX" />
      </AppProviders>,
    );
    await screen.findByTestId("ledger-indicator-summary-section-financial");
    expect(spy).toHaveBeenCalledWith("202603", "CNX");
    expect(spy.mock.calls.every((call) => call[0] === "202603")).toBe(true);
    unmount();
    spy.mockClear();

    render(
      <AppProviders client={client}>
        <LedgerPnlFinancialIndicatorSummaryPanel reportMonth="" currency="CNX" />
      </AppProviders>,
    );
    expect(await screen.findByText("未选择报告月")).toBeInTheDocument();
    expect(
      screen.getByText("选择报告日后按其所在月份读取经营指标情况表。"),
    ).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });
});
