import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiEnvelope, LedgerMoneyValue, LedgerPnlAnalysisPayload, ResultMeta } from "../api/contracts";
import { LedgerPnlAnalysisWorkbench } from "../features/ledger-pnl/components/LedgerPnlAnalysisWorkbench";

function money(yuan: string, yi: string): LedgerMoneyValue {
  return { yuan, yi };
}

function meta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_ledger_pnl_analysis",
    basis: "ledger",
    result_kind: "ledger_pnl.analysis",
    formal_use_allowed: false,
    source_version: "sv_ledger_pnl_analysis_test",
    vendor_version: "vv_none",
    rule_version: "rv_ledger_pnl_analysis_v1",
    cache_version: "cv_ledger_pnl_analysis_v1",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    requested_report_date: "2026-06-30",
    resolved_report_date: "2026-06-30",
    as_of_date: "2026-06-30",
    date_basis: "ledger_report_date",
    generated_at: "2026-07-10T00:00:00Z",
    tables_used: ["qdb_gl_ledger_reconciliation_workbook"],
    filters_applied: {
      report_date: "2026-06-30",
      currency: "CNX",
      currency_basis: "CNX",
    },
    ...overrides,
  };
}

const READY_RESULT: LedgerPnlAnalysisPayload = {
  report_date: "2026-06-30",
  source_version: "sv_ledger_pnl_analysis_test",
  currency_basis: "CNX",
  basis_availability: { CNX: "ready", CNY: "ready" },
  analysis_status: "ready",
  metric_status: "candidate",
  conclusion: {
    direction: "positive",
    other_effect: "support",
    core_pnl: money("352000000", "3.52"),
    other_5_pnl: money("66000000", "0.66"),
    all_pnl: money("418000000", "4.18"),
  },
  pnl_bridge: {
    components: [
      { metric_key: "core_pnl", metric_name: "核心损益", amount: money("352000000", "3.52") },
      { metric_key: "other_5_pnl", metric_name: "其他 5* 损益", amount: money("66000000", "0.66") },
    ],
    total: money("418000000", "4.18"),
    residual: money("0", "0.00"),
  },
  basis_comparison: ([
    ["assets", "总资产"],
    ["liabilities", "总负债"],
    ["net_assets", "净资产"],
    ["core_pnl", "核心损益"],
    ["all_pnl", "全量损益"],
    ["other_5_pnl", "其他 5* 损益"],
  ] as const).map(([metric_key, metric_name]) => ({
    metric_key,
    metric_name,
    cnx: money("100000000", "1.00"),
    cny: money("90000000", "0.90"),
    cnx_minus_cny: money("10000000", "0.10"),
    availability: { CNX: "ready", CNY: "ready" },
    evidence_rows: { CNX: 1, CNY: 1 },
  })),
  contributors: {
    positive_total: money("500000000", "5.00"),
    negative_total: money("-82000000", "-0.82"),
    net_total: money("418000000", "4.18"),
    top_positive: [
      {
        rank: 1,
        account_code: "514100",
        account_name: "利息收入",
        amount: money("500000000", "5.00"),
        count: 18,
      },
    ],
    top_negative: [
      {
        rank: 1,
        account_code: "519900",
        account_name: "其他损益",
        amount: money("-82000000", "-0.82"),
        count: 4,
      },
    ],
  },
  period_comparison: {
    status: "available",
    previous_report_date: "2026-05-31",
    previous_source_version: "sv_ledger_pnl_analysis_previous",
    rows: [
      {
        metric_key: "core_pnl",
        metric_name: "核心损益",
        current: money("352000000", "3.52"),
        previous: money("300000000", "3.00"),
        change: money("52000000", "0.52"),
      },
      {
        metric_key: "other_5_pnl",
        metric_name: "其他 5* 损益",
        current: money("66000000", "0.66"),
        previous: money("50000000", "0.50"),
        change: money("16000000", "0.16"),
      },
      {
        metric_key: "all_pnl",
        metric_name: "全量损益",
        current: money("418000000", "4.18"),
        previous: money("350000000", "3.50"),
        change: money("68000000", "0.68"),
      },
    ],
  },
  calculation_basis: {
    core_pnl_prefixes: ["514", "516", "517"],
    all_pnl_prefixes: ["5"],
    other_5_pnl_formula: "all_pnl - core_pnl",
    other_5_pnl_boundary: "arithmetic residual within 5* accounts; not a formal attribution category",
    basis_difference_formula: "CNX - CNY",
    basis_boundary: "overlapping accounting bases; not FX PnL",
    basis_availability_boundary:
      "basis availability is metric-specific and missing evidence is never zero-filled",
    metric_boundary: "candidate ledger analysis; not formal PnL",
    previous_period_rule: "previous available report date",
  },
};

function envelope(
  result: LedgerPnlAnalysisPayload = READY_RESULT,
  metaOverrides: Partial<ResultMeta> = {},
): ApiEnvelope<LedgerPnlAnalysisPayload> {
  return { result_meta: meta(metaOverrides), result };
}

describe("LedgerPnlAnalysisWorkbench", () => {
  it("renders the candidate ready conclusion, backend bridge, comparison, and contributors from DTO yi values", () => {
    render(
      <LedgerPnlAnalysisWorkbench
        envelope={envelope()}
        isLoading={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    );

    const workbench = screen.getByTestId("ledger-pnl-analysis-workbench");
    expect(workbench).toHaveAttribute("data-state", "ready");
    expect(workbench).toHaveTextContent("候选总账读模型");
    expect(workbench).toHaveTextContent("候选分析");
    expect(workbench).toHaveTextContent("全量损益为正");
    expect(workbench).toHaveTextContent("其他 5* 损益形成支持");
    const bridge = screen.getByTestId("ledger-pnl-analysis-bridge");
    expect(within(bridge).getByText("3.52 亿元")).toBeVisible();
    expect(bridge).toHaveTextContent("核心损益");
    expect(bridge).toHaveTextContent("其他 5* 损益");
    expect(bridge).toHaveTextContent("闭环残差");
    expect(bridge).toHaveTextContent("0.00 亿元");

    expect(screen.getByTestId("ledger-pnl-analysis-period")).toHaveTextContent("2026-05-31");
    expect(screen.getByTestId("ledger-pnl-analysis-period")).toHaveTextContent("全量变化 0.68 亿元");
    expect(screen.getByTestId("ledger-pnl-analysis-period")).toHaveTextContent("其他 5* 变化 0.16 亿元");
    expect(screen.getByTestId("ledger-pnl-analysis-basis")).toHaveTextContent("CNX - CNY");
    expect(screen.getByTestId("ledger-pnl-analysis-basis")).toHaveTextContent("不可相加，也不是 FX PnL");
    expect(screen.getByTestId("ledger-pnl-analysis-contributors")).toHaveTextContent("514100 利息收入");
    expect(screen.getByTestId("ledger-pnl-analysis-contributors")).toHaveTextContent("519900 其他损益");
    expect(screen.getByTestId("ledger-pnl-analysis-contributors")).toHaveTextContent("18 行");
    expect(workbench).toHaveTextContent("候选非正式");
  });

  it("opens account drill-through from the full contributor row with the exact selection", () => {
    const onSelectContributor = vi.fn();
    render(
      <LedgerPnlAnalysisWorkbench
        envelope={envelope()}
        isLoading={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
        onSelectContributor={onSelectContributor}
      />,
    );

    const positive = screen.getByRole("button", {
      name: "查看科目穿透 514100 利息收入",
    });
    expect(positive).toHaveAttribute("aria-haspopup", "dialog");
    fireEvent.click(positive);
    expect(onSelectContributor).toHaveBeenLastCalledWith({
      account_code: "514100",
      account_name: "利息收入",
      tone: "positive",
    });

    const negative = screen.getByRole("button", {
      name: "查看科目穿透 519900 其他损益",
    });
    expect(negative).toHaveAttribute("aria-haspopup", "dialog");
    fireEvent.click(negative);
    expect(onSelectContributor).toHaveBeenLastCalledWith({
      account_code: "519900",
      account_name: "其他损益",
      tone: "negative",
    });
  });

  it("uses the DTO yi display field without recomputing from yuan", () => {
    render(
      <LedgerPnlAnalysisWorkbench
        envelope={envelope({
          ...READY_RESULT,
          pnl_bridge: {
            ...READY_RESULT.pnl_bridge,
            components: [
              { metric_key: "core_pnl", metric_name: "核心损益", amount: money("1", "9.91") },
              ...READY_RESULT.pnl_bridge.components.slice(1),
            ],
          },
        })}
        isLoading={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    );

    expect(within(screen.getByTestId("ledger-pnl-analysis-bridge")).getByText("9.91 亿元")).toBeVisible();
  });

  it("renders no_data without presenting zero as an analytical conclusion", () => {
    render(
      <LedgerPnlAnalysisWorkbench
        envelope={envelope({
          ...READY_RESULT,
          analysis_status: "no_data",
          basis_availability: { CNX: "no_data", CNY: "no_data" },
          conclusion: {
            direction: "unavailable",
            other_effect: "unavailable",
            core_pnl: null,
            other_5_pnl: null,
            all_pnl: null,
          },
          pnl_bridge: {
            components: READY_RESULT.pnl_bridge.components.map((component) => ({
              ...component,
              amount: null,
            })),
            total: null,
            residual: null,
          },
          basis_comparison: [],
          contributors: {
            positive_total: null,
            negative_total: null,
            net_total: null,
            top_positive: [],
            top_negative: [],
          },
          period_comparison: {
            status: "current_basis_no_data",
            previous_report_date: null,
            previous_source_version: null,
            rows: [],
          },
        })}
        isLoading={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByTestId("ledger-pnl-analysis-workbench")).toHaveAttribute("data-state", "no_data");
    expect(screen.getByText("当前报告日与账务口径暂无损益分析数据")).toBeVisible();
    expect(screen.queryByTestId("ledger-pnl-analysis-bridge")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ledger-pnl-analysis-basis")).not.toBeInTheDocument();
  });

  it("keeps balance metrics visible when selected-basis PnL is unavailable", () => {
    const partialRows = READY_RESULT.basis_comparison.map((row) => {
      if (row.metric_key === "assets") {
        return {
          ...row,
          cny: null,
          cnx_minus_cny: null,
          availability: { CNX: "ready", CNY: "no_data" } as const,
          evidence_rows: { CNX: 12, CNY: 0 },
        };
      }
      return {
        ...row,
        cnx: null,
        cny: null,
        cnx_minus_cny: null,
        availability: { CNX: "no_data", CNY: "no_data" } as const,
        evidence_rows: { CNX: 0, CNY: 0 },
      };
    });

    render(
      <LedgerPnlAnalysisWorkbench
        envelope={envelope({
          ...READY_RESULT,
          analysis_status: "no_data",
          basis_availability: { CNX: "no_data", CNY: "no_data" },
          conclusion: {
            direction: "unavailable",
            other_effect: "unavailable",
            core_pnl: null,
            other_5_pnl: null,
            all_pnl: null,
          },
          pnl_bridge: {
            components: READY_RESULT.pnl_bridge.components.map((component) => ({
              ...component,
              amount: null,
            })),
            total: null,
            residual: null,
          },
          basis_comparison: partialRows,
          contributors: {
            positive_total: null,
            negative_total: null,
            net_total: null,
            top_positive: [],
            top_negative: [],
          },
          period_comparison: {
            status: "current_basis_no_data",
            previous_report_date: null,
            previous_source_version: null,
            rows: [],
          },
        })}
        isLoading={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText("当前报告日与账务口径暂无损益分析数据")).toBeVisible();
    const basis = screen.getByTestId("ledger-pnl-analysis-basis");
    const assetsRow = within(basis).getByText("总资产").closest("tr");
    expect(assetsRow).toHaveTextContent("1.00 亿元");
    expect(assetsRow).toHaveTextContent("无数据");
    expect(assetsRow).toHaveTextContent("不可比");
    expect(screen.queryByTestId("ledger-pnl-analysis-bridge")).not.toBeInTheDocument();
  });

  it("does not present a basis difference when either overlapping basis has no data", () => {
    render(
      <LedgerPnlAnalysisWorkbench
        envelope={envelope({
          ...READY_RESULT,
          basis_availability: { CNX: "ready", CNY: "no_data" },
          basis_comparison: READY_RESULT.basis_comparison.map((row) => ({
            ...row,
            cny: null,
            cnx_minus_cny: null,
            availability: { CNX: "ready", CNY: "no_data" },
            evidence_rows: { CNX: row.evidence_rows.CNX, CNY: 0 },
          })),
        })}
        isLoading={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    );

    const basis = screen.getByTestId("ledger-pnl-analysis-basis");
    expect(basis).toHaveTextContent("对比口径数据不完整");
    expect(basis).toHaveTextContent("无数据");
    expect(basis).toHaveTextContent("不可比");
    expect(basis).not.toHaveTextContent("0.10 亿元");
  });

  it("shows per-metric missing evidence as unavailable instead of zero", () => {
    render(
      <LedgerPnlAnalysisWorkbench
        envelope={envelope({
          ...READY_RESULT,
          basis_comparison: READY_RESULT.basis_comparison.map((row) =>
            row.metric_key === "assets"
              ? {
                  ...row,
                  cny: null,
                  cnx_minus_cny: null,
                  availability: { CNX: "ready", CNY: "no_data" },
                  evidence_rows: { CNX: 1, CNY: 0 },
                }
              : row,
          ),
        })}
        isLoading={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    );

    const basis = screen.getByTestId("ledger-pnl-analysis-basis");
    const assetsRow = within(basis).getByText("总资产").closest("tr");
    expect(assetsRow).not.toBeNull();
    expect(assetsRow).toHaveTextContent("无数据");
    expect(assetsRow).toHaveTextContent("不可比");
    expect(assetsRow).not.toHaveTextContent("0.00 亿元");
  });

  it("distinguishes 403 failures and keeps a working retry action", () => {
    const onRetry = vi.fn();
    render(
      <LedgerPnlAnalysisWorkbench
        envelope={undefined}
        isLoading={false}
        isError
        error={new Error("Request failed (403): forbidden")}
        onRetry={onRetry}
      />,
    );

    expect(screen.getByText("无权限读取总账损益分析")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "重试分析" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("surfaces fallback and stale metadata ahead of candidate analysis", () => {
    render(
      <LedgerPnlAnalysisWorkbench
        envelope={envelope(READY_RESULT, {
          quality_flag: "stale",
          vendor_status: "vendor_stale",
          fallback_mode: "latest_snapshot",
          requested_report_date: "2026-06-30",
          resolved_report_date: "2026-05-31",
          fallback_date: "2026-05-31",
          as_of_date: "2026-05-31",
        })}
        isLoading={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    );

    const status = screen.getByTestId("ledger-pnl-analysis-source-status");
    expect(status).toHaveTextContent("已回退至最近可用报告日");
    expect(status).toHaveTextContent("请求日 2026-06-30");
    expect(status).toHaveTextContent("解析日 2026-05-31");
    expect(status).toHaveTextContent("数据可能已过期");
  });
});
