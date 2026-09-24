/**
 * ledger-pnl unit_consistency 契约探针（agent 评测 harness gate 探针）。
 *
 * Gate 语义：页面渲染的金额单位缩放（元/万元/亿元）与治理指标契约一致，换算正确。
 *
 * 契约依据：
 * - docs/metric_dictionary.md §15.2.4：MTR-LPN-001（核心损益）/ MTR-LPN-002（全量损益）/
 *   MTR-LPN-003（净资产）均为 display_unit=亿元、precision=2、
 *   sign_rule="signed amount; preserve source sign"、null_rule="null -> --"
 *   （前端按 frontend/AGENTS.md 以 EM_DASH「—」呈现缺失）。
 * - 后端口径 backend/app/core_finance/decimal_utils.py::fmt_money：
 *   LedgerMoneyValue.yuan = 元原值十进制字符串；
 *   LedgerMoneyValue.yi   = (元 / 1e8) 经 ROUND_HALF_UP 保留 2 位的十进制字符串。
 * - 前端展示层 LedgerPnlPage.tsx::formatMoney（页面私有，本文件经整页渲染锁定其行为）：
 *   优先透传后端 yi 并追加「 亿元」；yi 缺失时 fallback (Number(yuan) / 1e8).toFixed(2)；
 *   yuan/yi 双缺 → EM_DASH。
 * - 候选跨期比较 models 层 candidatePeriodComparisonModel.ts：
 *   后端 *_yi 字段已是亿元十进制字符串（payload 契约 unit="亿元"），前端仅做
 *   4 位定点 + 千分组 + U+2212 负号显示，不得再次缩放。
 */
import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { LedgerMoneyValue, ResultMeta } from "../api/contracts";
import {
  formatCandidateComparisonAmount,
  formatCandidateComparisonRate,
} from "../features/ledger-pnl/models/candidatePeriodComparisonModel";
import {
  buildMockLedgerPnlNoDataAnalysis,
  getMockLedgerPnlFormalFinancialIndicators,
} from "../mocks/ledgerPnlMocks";
import LedgerPnlPage from "../features/ledger-pnl/pages/LedgerPnlPage";
import { EM_DASH } from "../utils/format";

const REPORT_DATE = "2026-03-31";
/** fixedDecimal 的负号是 U+2212 MINUS SIGN，不是 ASCII 连字符。 */
const MINUS = "\u2212";

/** 构造 LedgerMoneyValue；yi 留空可强制页面走 yuan→亿元的前端 fallback 换算。 */
function ledgerMoney(yuan: string, yi = ""): LedgerMoneyValue {
  return { yuan, yi };
}

function buildMeta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "ledger",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_ledger_unit_contract",
    vendor_version: "vv_none",
    rule_version: "rv_ledger_unit_contract",
    cache_version: "cv_ledger_unit_contract",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-01T08:00:00Z",
    tables_used: ["qdb_general_ledger_workbook"],
    requested_report_date: REPORT_DATE,
    resolved_report_date: REPORT_DATE,
    as_of_date: REPORT_DATE,
    date_basis: "ledger_report_date",
    evidence_rows: 1,
  };
}

function renderLedgerPnlPage(client: ApiClient) {
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
          <MemoryRouter initialEntries={[`/ledger-pnl?report_date=${REPORT_DATE}`]}>
            {children}
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

/** 在 summary 卡容器内按标题精确取出该卡渲染的 value 文本。 */
function readSummaryCardValue(cardsRoot: HTMLElement, title: string): string {
  const frames = Array.from(cardsRoot.querySelectorAll(".ledger-pnl-summary-card-frame"));
  const frame = frames.find(
    (el) => el.querySelector(".ledger-pnl-summary-card__title")?.textContent?.trim() === title,
  );
  if (!frame) {
    throw new Error(`未找到标题为「${title}」的 summary 卡`);
  }
  return frame.querySelector(".ledger-pnl-summary-card__value")?.textContent?.trim() ?? "";
}

function buildUnitContractClient(): ApiClient {
  const base = createApiClient({ mode: "mock" });
  return {
    ...base,
    getLedgerPnlDates: vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.dates"),
      result: { dates: [REPORT_DATE] },
    })),
    getLedgerPnlSummary: vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: {
        report_date: REPORT_DATE,
        source_version: "sv_ledger_unit_contract",
        // 正常量级：后端 yi 缺失，前端 fallback 换算 1234567890 元 / 1e8
        // = 12.3456789 → toFixed(2) → "12.35 亿元"（缩放因子 + 四舍五入）。
        ledger_monthly_pnl_core: ledgerMoney("1234567890"),
        // 负值：保留来源符号（sign_rule=preserve source sign）。
        ledger_monthly_pnl_all: ledgerMoney("-987654321"),
        // 缩放阈值边界：恰好 1 亿元，换算结果必须恰为 "1.00 亿元"。
        ledger_total_assets: ledgerMoney("100000000"),
        // 后端预格式化优先：yi 有值时透传后端权威换算，不得用 yuan 重算，
        // 也不得对 yi 再缩放一次。yuan 故意给出与 yi 矛盾的干扰值。
        ledger_total_liabilities: ledgerMoney("999", "3.14"),
        // 真零：显示 "0.00 亿元"，必须与缺失（EM_DASH）不同形。
        ledger_net_assets: ledgerMoney("0"),
        // 缺失占位：yuan/yi 双缺 → EM_DASH（null_rule）。由币种汇总表行承载断言。
        by_currency: [{ currency: "SGD", total_pnl: ledgerMoney("") }],
        by_account: [],
      },
    })),
    getLedgerPnlData: vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.data"),
      result: {
        report_date: REPORT_DATE,
        summary: {
          total_pnl_cnx: ledgerMoney("0"),
          total_pnl_cny: ledgerMoney("0"),
          total_pnl: ledgerMoney("0"),
          count: 0,
        },
        items: [],
      },
    })),
    getLedgerPnlAnalysis: vi.fn(async (reportDate: string, currency?: string) => ({
      result_meta: buildMeta("ledger_pnl.analysis"),
      result: buildMockLedgerPnlNoDataAnalysis(reportDate, currency === "CNY" ? "CNY" : "CNX"),
    })),
    getLedgerPnlMonthlyAnalysisDates: vi.fn(async () => ({
      result_meta: { ...buildMeta("qdb-gl-monthly-analysis.dates"), basis: "analytical" as const },
      result: { report_months: [] },
    })),
    getLedgerPnlMonthlyAnalysisWorkbook: vi.fn(),
    getLedgerPnlFormalFinancialIndicators: vi.fn(async (reportMonth: string) => ({
      result_meta: buildMeta("ledger_pnl.formal_financial_indicator_source_contract"),
      result: getMockLedgerPnlFormalFinancialIndicators(reportMonth),
    })),
  };
}

describe("ledger-pnl 单位一致性：summary 卡（MTR-LPN-001/002/003，display_unit=亿元）", () => {
  it("元→亿元缩放因子、符号、真零、阈值边界、yi 透传与缺失占位全部与契约一致", async () => {
    renderLedgerPnlPage(buildUnitContractClient());

    // 等 summary 数据落地（正常量级值出现即代表 formatMoney 已执行）。
    await screen.findByText("12.35 亿元");
    const cards = screen.getByTestId("ledger-pnl-summary-cards");

    // MTR-LPN-001 核心损益：1_234_567_890 元 / 1e8 = 12.3456789 → 12.35 亿元。
    // 若缩放因子被误改为 1e4（万元）或标签被改成「万元」，此断言必红。
    expect(readSummaryCardValue(cards, "核心损益")).toBe("12.35 亿元");

    // MTR-LPN-002 全量损益：负值保留来源符号：-987_654_321 元 → -9.88 亿元。
    expect(readSummaryCardValue(cards, "全量损益")).toBe("-9.88 亿元");

    // MTR-LPN-003 净资产：真零渲染 0.00 亿元，与缺失（—）必须不同形。
    expect(readSummaryCardValue(cards, "净资产")).toBe("0.00 亿元");

    // 缩放阈值边界：恰好 1 亿元 → 1.00 亿元。
    expect(readSummaryCardValue(cards, "总资产")).toBe("1.00 亿元");

    // 后端预格式化 yi 优先：显示后端权威换算值 3.14，而非用干扰 yuan=999 重算，
    // 也不得把 yi 再除一次 1e8。
    expect(readSummaryCardValue(cards, "总负债")).toBe("3.14 亿元");

    // 缺失占位：yuan/yi 双缺 → EM_DASH（币种汇总表 SGD 行）。
    const currencyTable = screen.getByTestId("ledger-pnl-currency-summary-table");
    const missingRow = within(currencyTable).getByText("SGD").closest("tr");
    expect(missingRow).not.toBeNull();
    const missingCells = missingRow!.querySelectorAll("td");
    expect(missingCells[1]?.textContent).toBe(EM_DASH);
  });
});

describe("ledger-pnl 单位一致性：候选跨期比较 models 层（后端亿元字符串保真显示）", () => {
  it("正常量级：亿元十进制字符串按 4 位定点 + 千分组保真显示，不再缩放", () => {
    expect(formatCandidateComparisonAmount("1.2345")).toBe("1.2345");
    expect(formatCandidateComparisonAmount("1234.5")).toBe("1,234.5000");
  });

  it("负值与符号：U+2212 负号；signed 选项只给非零正值加 +", () => {
    expect(formatCandidateComparisonAmount("-0.5")).toBe(`${MINUS}0.5000`);
    expect(formatCandidateComparisonAmount("-0.5", { signed: true })).toBe(`${MINUS}0.5000`);
    expect(formatCandidateComparisonAmount("2", { signed: true })).toBe("+2.0000");
  });

  it("真零：0.0000，与缺失（EM_DASH）不同形；signed 下真零不带 +", () => {
    expect(formatCandidateComparisonAmount("0")).toBe("0.0000");
    expect(formatCandidateComparisonAmount("0", { signed: true })).toBe("0.0000");
    expect(formatCandidateComparisonAmount(null)).toBe(EM_DASH);
  });

  it("显示精度舍入边界：half-up 恰好进位/不进位", () => {
    expect(formatCandidateComparisonAmount("0.00005")).toBe("0.0001");
    expect(formatCandidateComparisonAmount("0.00004")).toBe("0.0000");
  });

  it("契约守门：非十进制字符串（科学计数法/带千分组输入）显示「契约错误」而非猜测缩放", () => {
    expect(formatCandidateComparisonAmount("1e8")).toBe("契约错误");
    expect(formatCandidateComparisonAmount("12,345.6")).toBe("契约错误");
  });

  it("环比率：小数比率 ×100 转百分比显示，保留符号与真零语义", () => {
    expect(formatCandidateComparisonRate("0.0255")).toBe("+2.55%");
    expect(formatCandidateComparisonRate("-0.1")).toBe(`${MINUS}10.00%`);
    expect(formatCandidateComparisonRate("0")).toBe("0.00%");
    expect(formatCandidateComparisonRate(null)).toBe(EM_DASH);
  });
});
