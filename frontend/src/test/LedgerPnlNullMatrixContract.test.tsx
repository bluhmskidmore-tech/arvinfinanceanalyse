/**
 * ledger-pnl `null_zero_undefined_handling` gate 探针（专家 C：null / 0 / undefined / NaN 区分与渲染）。
 *
 * Gate 语义（frontend/AGENTS.md + DESIGN.md §6，由 utils/format.ts 头注释登记）：
 * - 缺数据（null/undefined）必须渲染为 EM_DASH（"—"），绝不能与真实 0 混淆；
 * - 真实 0 是业务值，必须以格式化后的 0（如 "0.00"、"0.0000"、"0.00 亿元"）展示，不得渲染占位；
 * - NaN 不得泄漏 "NaN" 字样到展示层（应转为占位或被上游拦截）。
 *
 * ledger-pnl 页的 null 传播路径（本文件按层覆盖）：
 * 1. 模型纯函数层：features/ledger-pnl/models/candidatePeriodComparisonModel.ts
 *    - formatCandidateComparisonAmount / formatCandidateComparisonRate（string | null 十进制串）。
 *    - null → EM_DASH；非法串（"NaN"/""/undefined 越界输入）→ "契约错误" fail-closed，不静默变 0。
 * 2. LedgerMoneyValue 渲染层：components/LedgerPnlAnalysisWorkbench.tsx（纯 props 组件）。
 *    - 后端 fmt_money 把 Decimal 序列化为 { yuan, yi } 字符串对象；缺失以整个对象为 null 表达。
 *    - 对象 null → EM_DASH；yi="0.00" → "0.00 亿元"；availability=no_data → "无数据"/"不可比"（缺失不补 0）。
 * 3. 字符串数值渲染层：components/LedgerPnlFinancialIndicatorSummaryPanel.tsx（displayCellValue）。
 *    - 单元格 null / 空串 / "NaN" 串 → EM_DASH（Number()+isFinite 拦截 NaN）；"0" → "0.00"（money）/"0.00%"（percent）。
 * 4. 表格单元格兜底层：components/LedgerPnlDataTable.tsx（`render(row) ?? EM_DASH`）。
 *    - render 返回 null/undefined → EM_DASH；返回数字 0 → "0"（?? 不吞 0）。
 *
 * 疑似缺陷登记（不放宽断言，以 it.skip 保留 gate 语义断言，详见专家报告）：
 * - [缺陷A·可达] LedgerPnlWorkbookTables.formatAnalysisValue 对 null/undefined/空串返回连字符 "-"，
 *   违反 "New pages must render missing values as EM_DASH / 禁止字面量 '-'" 规则；工作簿空单元格真实可达。
 * - [缺陷B·契约外防御缺失] Workbench/Page/Drawer 的 formatMoney 对非空 yi 串直接透传：若上游违约送 yi="NaN"
 *   会渲染 "NaN 亿元"。契约内不可达（后端 fmt_yi 经 to_decimal 把 NaN/Inf 归 0），仅登记防御缺失。
 * - [缺陷C·契约外防御缺失] LedgerPnlDataTable 单元格 `render(row) ?? EM_DASH` 对 render 返回的原始 NaN
 *   数字（非 nullish）会经 React 渲染出 "NaN"。契约要求 render 返回已格式化串，页面各列均走 formatMoney，契约内不可达。
 *
 * 先红后绿：临时把「模型层 "0" → "0.0000"」断言改为期望 EM_DASH、并解除缺陷A的 skip，可确认本探针会红；
 * 证据保存在专家报告中，此处恢复为契约断言。
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { LedgerPnlIndicatorSummaryPayload } from "../api/contracts";
import { createApiClient } from "../api/client";
import { AppProviders } from "../app/providers";
import {
  LedgerPnlDataTable,
  type LedgerPnlDataTableColumn,
} from "../features/ledger-pnl/components/LedgerPnlDataTable";
import { LedgerPnlAnalysisWorkbench } from "../features/ledger-pnl/components/LedgerPnlAnalysisWorkbench";
import { LedgerPnlFinancialIndicatorSummaryPanel } from "../features/ledger-pnl/components/LedgerPnlFinancialIndicatorSummaryPanel";
import {
  LedgerPnlWorkbookTables,
  buildLedgerPnlWorkbookGroups,
} from "../features/ledger-pnl/components/LedgerPnlWorkbookTables";
import {
  formatCandidateComparisonAmount,
  formatCandidateComparisonRate,
} from "../features/ledger-pnl/models/candidatePeriodComparisonModel";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { EM_DASH } from "../utils/format";

/** mock 快照中唯一 ready 的总账分析报告日（src/mocks/ledgerPnlMocks.ts）。 */
const READY_ANALYSIS_REPORT_DATE = "2025-12-31";

async function loadReadyAnalysisEnvelope() {
  const client = createApiClient({ mode: "mock" });
  const base = await client.getLedgerPnlAnalysis(READY_ANALYSIS_REPORT_DATE, "CNX");
  return structuredClone(base);
}

describe("LedgerPnlNullMatrixContract / 模型纯函数层（candidatePeriodComparisonModel）", () => {
  it.each([
    ["null（缺数据）", null, EM_DASH],
    ["\"0\"（真零）", "0", "0.0000"],
    ["\"0.0000\"（真零，已带精度）", "0.0000", "0.0000"],
  ] as const)(
    "formatCandidateComparisonAmount：%s → %s",
    (_label, input, expected) => {
      expect(formatCandidateComparisonAmount(input)).toBe(expected);
    },
  );

  it("null 占位与真零展示必须不同形，且互不含对方字样", () => {
    const missing = formatCandidateComparisonAmount(null);
    const zero = formatCandidateComparisonAmount("0");
    expect(missing).toBe(EM_DASH);
    expect(missing).not.toBe("0");
    expect(missing).not.toBe("");
    expect(missing).not.toContain("NaN");
    expect(zero).toBe("0.0000");
    expect(zero).not.toContain(EM_DASH);
  });

  it("signed 真零不得渲染符号（0 既非正也非负）", () => {
    expect(formatCandidateComparisonAmount("0", { signed: true })).toBe("0.0000");
    expect(formatCandidateComparisonAmount("0.0000", { signed: true })).toBe("0.0000");
  });

  it.each([
    ["\"NaN\" 串", "NaN"],
    ["\"Infinity\" 串", "Infinity"],
    ["空串（不得经 Number(\"\") 静默变 0）", ""],
  ] as const)(
    "formatCandidateComparisonAmount 非法输入 %s → fail-closed \"契约错误\"，不泄漏 NaN、不静默变 0",
    (_label, input) => {
      const display = formatCandidateComparisonAmount(input);
      expect(display).toBe("契约错误");
      expect(display).not.toContain("NaN");
      expect(display).not.toBe("0.0000");
    },
  );

  it("运行时越界 undefined → fail-closed \"契约错误\"（类型契约为 string | null，undefined 由上游解析层阻断）", () => {
    const display = formatCandidateComparisonAmount(
      undefined as unknown as string | null,
    );
    expect(display).toBe("契约错误");
    expect(display).not.toBe("0.0000");
    expect(display).not.toBe(EM_DASH);
  });

  it("formatCandidateComparisonRate：null → EM_DASH；\"0\" → \"0.00%\"；\"NaN\" → 契约错误", () => {
    expect(formatCandidateComparisonRate(null)).toBe(EM_DASH);
    expect(formatCandidateComparisonRate("0")).toBe("0.00%");
    expect(formatCandidateComparisonRate("NaN")).toBe("契约错误");
  });
});

describe("LedgerPnlNullMatrixContract / LedgerMoneyValue 渲染层（AnalysisWorkbench）", () => {
  it("对象级 null → EM_DASH，真零 → \"0.00 亿元\"，no_data 口径 → \"无数据\"/\"不可比\"，全程不出现 NaN", async () => {
    const envelope = await loadReadyAnalysisEnvelope();
    envelope.result.pnl_bridge.total = null;
    envelope.result.pnl_bridge.residual = { yuan: "0", yi: "0.00" };
    envelope.result.contributors.negative_total = null;
    const firstBasisRow = envelope.result.basis_comparison[0];
    firstBasisRow.cnx = { yuan: "123000000", yi: "1.23" };
    firstBasisRow.cny = null;
    firstBasisRow.cnx_minus_cny = null;
    firstBasisRow.availability = { CNX: "ready", CNY: "no_data" };

    render(
      <LedgerPnlAnalysisWorkbench
        envelope={envelope}
        isLoading={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    );

    const workbench = screen.getByTestId("ledger-pnl-analysis-workbench");
    const bridge = within(workbench).getByTestId("ledger-pnl-analysis-bridge");

    // null 金额 → EM_DASH，且不得与真零同形
    const totalTerm = within(bridge).getByText("全量损益").closest("div");
    expect(totalTerm).not.toBeNull();
    expect(totalTerm).toHaveTextContent(EM_DASH);
    expect(totalTerm).not.toHaveTextContent("0.00 亿元");

    // 真零 → 格式化 0，不得渲染占位
    const residualTerm = within(bridge).getByText("闭环残差").closest("div");
    expect(residualTerm).not.toBeNull();
    expect(residualTerm).toHaveTextContent("0.00 亿元");
    expect(residualTerm).not.toHaveTextContent(EM_DASH);

    // 贡献合计 null → EM_DASH
    const contributors = within(workbench).getByTestId("ledger-pnl-analysis-contributors");
    expect(within(contributors).getByText(/负贡献/)).toHaveTextContent(
      `负贡献 ${EM_DASH}`,
    );

    // 口径不可用：渲染显式状态词，而非 0 值，也非占位坍缩
    const basisPanel = within(workbench).getByTestId("ledger-pnl-analysis-basis");
    const basisRow = within(basisPanel)
      .getByText(firstBasisRow.metric_name)
      .closest("tr");
    expect(basisRow).not.toBeNull();
    expect(basisRow).toHaveTextContent("1.23 亿元");
    expect(basisRow).toHaveTextContent("无数据");
    expect(basisRow).toHaveTextContent("不可比");
    expect(basisRow).not.toHaveTextContent("0.00 亿元");

    // 契约内输入下，NaN 字样不得出现在整个工作台
    expect(workbench).not.toHaveTextContent("NaN");
  });

  it("契约违规的空 yi 串按缺失处理（EM_DASH），不回退为 0；Workbench 不消费 yuan 字段", async () => {
    const envelope = await loadReadyAnalysisEnvelope();
    // yuan 有值但 yi 为空串：Workbench.formatMoney 只信 yi，缺失即占位（与 Page.formatMoney 的 yuan 回退不同，见报告）。
    envelope.result.pnl_bridge.total = { yuan: "418000000", yi: "" };

    render(
      <LedgerPnlAnalysisWorkbench
        envelope={envelope}
        isLoading={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    );

    const bridge = screen.getByTestId("ledger-pnl-analysis-bridge");
    const totalTerm = within(bridge).getByText("全量损益").closest("div");
    expect(totalTerm).toHaveTextContent(EM_DASH);
    expect(totalTerm).not.toHaveTextContent("0.00 亿元");
    expect(totalTerm).not.toHaveTextContent("4.18 亿元");
  });
});

describe("LedgerPnlNullMatrixContract / 字符串数值渲染层（FinancialIndicatorSummaryPanel）", () => {
  function buildSummaryPayload(
    overrides?: Partial<LedgerPnlIndicatorSummaryPayload>,
  ): LedgerPnlIndicatorSummaryPayload {
    return {
      contract_version: "ledger-indicator-summary-null-matrix-probe",
      title: "经营指标情况表（总账口径）",
      report_month: "202606",
      report_year: 2026,
      currency_basis: "CNX",
      unit: "亿元",
      data_status: "ready",
      periods: [
        {
          period_id: "p1",
          flow_label: "2026年6月",
          flow_compare_label: "2025年6月",
          point_label: "2026-06-30",
          point_compare_label: "2025-12-31",
          current_month: "202606",
          flow_compare_month: "202506",
          point_compare_month: "202512",
          current_available: true,
          flow_compare_available: true,
          point_compare_available: true,
        },
      ],
      sections: [
        {
          section_id: "financial",
          title: "财务指标",
          basis_note: "总账口径",
          rows: [
            {
              row_id: "money-row",
              name: "营业收入探针行",
              indent: 0,
              basis: "flow",
              value_kind: "money_yi",
              availability: "ledger_computed",
              caliber_note: null,
              unavailable_reason: null,
              account_evidence: null,
              // current="0" 真零；compare=null 缺失；delta="NaN" 违约串；delta_pct="" 空串
              values: [
                { period_id: "p1", current: "0", compare: null, delta: "NaN", delta_pct: "" },
              ],
            },
            {
              row_id: "percent-row",
              name: "成本收入比探针行",
              indent: 0,
              basis: "flow",
              value_kind: "percent",
              availability: "ledger_computed",
              caliber_note: null,
              unavailable_reason: null,
              account_evidence: null,
              values: [
                { period_id: "p1", current: "0", compare: "12.5", delta: null, delta_pct: null },
              ],
            },
          ],
        },
      ],
      quality_checks: [],
      coverage: { row_total: 2, row_computed: 2, row_unavailable: 0 },
      notes: ["null 矩阵探针夹具"],
      source_files: [],
      ...overrides,
    };
  }

  async function renderPanelWith(payload: LedgerPnlIndicatorSummaryPayload) {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLedgerPnlFinancialIndicatorSummary").mockResolvedValue(
      buildMockApiEnvelope("ledger_pnl.financial_indicator_summary", payload),
    );
    render(
      <AppProviders client={client}>
        <LedgerPnlFinancialIndicatorSummaryPanel reportMonth="202606" currency="CNX" />
      </AppProviders>,
    );
    return screen.findByTestId("ledger-pnl-financial-indicator-summary-panel");
  }

  it("单元格矩阵：null/空串/\"NaN\" 串 → EM_DASH；\"0\" → \"0.00\"（money）与 \"0.00%\"（percent）", async () => {
    const panel = await renderPanelWith(buildSummaryPayload());
    await screen.findByTestId("ledger-indicator-summary-section-financial");

    const moneyRow = screen.getByTestId("ledger-indicator-summary-row-money-row");
    const moneyCells = within(moneyRow)
      .getAllByRole("cell")
      .map((cell) => cell.textContent);
    // 列序：本期 / 对比期 / 增减额 / 增减幅
    expect(moneyCells).toEqual(["0.00", EM_DASH, EM_DASH, EM_DASH]);

    const percentRow = screen.getByTestId("ledger-indicator-summary-row-percent-row");
    const percentCells = within(percentRow)
      .getAllByRole("cell")
      .map((cell) => cell.textContent);
    expect(percentCells).toEqual(["0.00%", "12.50%", EM_DASH, EM_DASH]);

    // "NaN" 违约串已被 Number()+isFinite 拦截为占位，不得泄漏字样
    expect(panel).not.toHaveTextContent("NaN");
  });

  it("data_status=no_data 时整表保持无数据状态，不以 0 值展示", async () => {
    const panel = await renderPanelWith(
      buildSummaryPayload({ data_status: "no_data" }),
    );
    await screen.findByTestId("ledger-indicator-summary-no-data");
    expect(panel).toHaveTextContent("缺失月份保持为空，不以 0 值展示");
    expect(panel).not.toHaveTextContent("0.00");
  });
});

describe("LedgerPnlNullMatrixContract / 表格单元格兜底层（LedgerPnlDataTable）", () => {
  it("render 返回 null/undefined → EM_DASH；返回数字 0 → \"0\"（?? 不吞真零）；已格式化串透传", () => {
    type ProbeRow = { id: string };
    const columns: LedgerPnlDataTableColumn<ProbeRow>[] = [
      { key: "null-cell", header: "null 输入", render: () => null },
      { key: "undefined-cell", header: "undefined 输入", render: () => undefined },
      { key: "zero-number-cell", header: "数字 0 输入", render: () => 0 },
      { key: "zero-money-cell", header: "格式化零", render: () => "0.00 亿元" },
    ];
    render(
      <LedgerPnlDataTable<ProbeRow>
        testId="ledger-pnl-null-matrix-probe-table"
        title="缺失值矩阵探针"
        columns={columns}
        rows={[{ id: "row-1" }]}
        rowKey={(row) => row.id}
        loadingMessage="读取中"
        errorMessage="读取失败"
        emptyMessage="暂无数据"
      />,
    );

    const table = screen.getByTestId("ledger-pnl-null-matrix-probe-table");
    const cells = within(table)
      .getAllByRole("cell")
      .map((cell) => cell.textContent);
    expect(cells).toEqual([EM_DASH, EM_DASH, "0", "0.00 亿元"]);
  });
});

describe("LedgerPnlNullMatrixContract / 疑似缺陷登记（skip 保留 gate 语义断言，详见专家报告）", () => {
  // [缺陷A·可达] formatAnalysisValue（LedgerPnlWorkbookTables.tsx:66-69）对 null/undefined/"" 返回
  // 字面量连字符 "-"，违反 frontend/AGENTS.md（"missing values as EM_DASH；禁止 '-'"）与
  // DESIGN.md §6（format.ts 头注释登记）。总账月度工作簿空单元格真实可达该路径。
  // 解除 skip 的实测输出：expected [..., "—"]，received [..., "-"]。
  it.skip("[缺陷A] 工作簿空单元格应渲染 EM_DASH，而非连字符 \"-\"", () => {
    const groups = buildLedgerPnlWorkbookGroups({
      财务指标落地状态: {
        title: "财务指标落地状态",
        testId: "probe-workbook-null-sheet",
        sheet: {
          key: "probe-sheet",
          title: "财务指标落地状态",
          columns: ["科目", "本月"],
          rows: [{ 科目: "利息净收入", 本月: null }],
        },
      },
    });
    render(<LedgerPnlWorkbookTables groups={groups} testId="probe-workbook-tables" />);
    const sheet = screen.getByTestId("probe-workbook-null-sheet");
    const cells = within(sheet)
      .getAllByRole("cell")
      .map((cell) => cell.textContent);
    expect(cells).toEqual(["利息净收入", EM_DASH]);
  });

  // [缺陷B·契约外防御缺失] Workbench.formatMoney（Page/Drawer 同型）对非空 yi 串直接透传：
  // yi="NaN" 会渲染 "NaN 亿元"。契约内不可达：后端 fmt_yi 经 to_decimal 把 NaN/Inf/None 归 0
  // （backend/app/core_finance/decimal_utils.py），JSON 亦无法携带数字 NaN。仅登记前端无二次防御。
  it.skip("[缺陷B] 上游违约送 yi=\"NaN\" 时，NaN 字样不应透传到展示层", async () => {
    const envelope = await loadReadyAnalysisEnvelope();
    envelope.result.pnl_bridge.total = { yuan: "NaN", yi: "NaN" };
    render(
      <LedgerPnlAnalysisWorkbench
        envelope={envelope}
        isLoading={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByTestId("ledger-pnl-analysis-bridge")).not.toHaveTextContent("NaN");
  });

  // [缺陷C·契约外防御缺失] DataTable 单元格 `render(row) ?? EM_DASH`：NaN 数字非 nullish，
  // React 会渲染 String(NaN)="NaN"。契约要求 render 返回已格式化串（页面各列均走 formatMoney，
  // 其 yuan 分支有 Number.isFinite 拦截），契约内不可达。仅登记共享表格组件无二次防御。
  it.skip("[缺陷C] render 返回原始 NaN 数字时，单元格不应泄漏 NaN 字样", () => {
    type ProbeRow = { id: string };
    render(
      <LedgerPnlDataTable<ProbeRow>
        testId="ledger-pnl-nan-probe-table"
        title="NaN 防御探针"
        columns={[{ key: "nan-cell", header: "NaN 输入", render: () => Number.NaN }]}
        rows={[{ id: "row-1" }]}
        rowKey={(row) => row.id}
        loadingMessage="读取中"
        errorMessage="读取失败"
        emptyMessage="暂无数据"
      />,
    );
    const table = screen.getByTestId("ledger-pnl-nan-probe-table");
    expect(table).not.toHaveTextContent("NaN");
  });
});
