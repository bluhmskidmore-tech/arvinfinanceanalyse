import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../lib/echarts", () => ({
  default: ({ option }: { option?: unknown }) => (
    <div data-testid="untraced-reconciliation-echarts-stub">{JSON.stringify(option ?? null)}</div>
  ),
}));

import type { PnlByBusinessUntracedTrendRow } from "../../api/contracts";
import { nocturneTokens } from "../../theme/designSystem";
import { UntracedReconciliationTrendPanel } from "./UntracedReconciliationTrendPanel";
import { buildUntracedReconciliationTrendOption } from "./untracedReconciliationTrendOption";

function buildRow(partial: Partial<PnlByBusinessUntracedTrendRow>): PnlByBusinessUntracedTrendRow {
  return {
    report_date: partial.report_date ?? "2026-01-31",
    untraced_row_count: partial.untraced_row_count ?? 0,
    total_row_count: partial.total_row_count ?? 2,
    untraced_share_pct: "untraced_share_pct" in partial ? (partial.untraced_share_pct as string | null) : "0.00",
  };
}

describe("buildUntracedReconciliationTrendOption", () => {
  it("maps report_date to the x-axis and untraced_share_pct to the line series", () => {
    const rows = [
      buildRow({ report_date: "2025-12-31", untraced_share_pct: "0.00" }),
      buildRow({ report_date: "2026-01-31", untraced_share_pct: "12.50" }),
      buildRow({ report_date: "2026-02-28", untraced_share_pct: "5.00" }),
    ];

    const option = buildUntracedReconciliationTrendOption(rows);

    expect(option.xAxis).toMatchObject({ data: ["2025-12-31", "2026-01-31", "2026-02-28"] });
    const series = option.series as Array<{ type: string; data: unknown[] }>;
    expect(series).toHaveLength(1);
    expect(series[0].type).toBe("line");
    expect(series[0].data).toEqual([0, 12.5, 5]);
  });

  it("maps a null untraced_share_pct to a null data point (a rendered gap), not zero", () => {
    const rows = [
      buildRow({ report_date: "2025-12-31", untraced_share_pct: "0.00" }),
      buildRow({ report_date: "2026-01-31", untraced_share_pct: null }),
      buildRow({ report_date: "2026-02-28", untraced_share_pct: "5.00" }),
    ];

    const option = buildUntracedReconciliationTrendOption(rows);
    const series = option.series as Array<{ data: unknown[]; connectNulls?: boolean }>;

    expect(series[0].data).toEqual([0, null, 5]);
    expect(series[0].data[1]).not.toBe(0);
    expect(series[0].connectNulls).toBe(false);
  });

  it("only uses neutral Nocturne ink tones for the series styling (no warning/danger/KPI accent colors)", () => {
    const rows = [buildRow({})];
    const option = buildUntracedReconciliationTrendOption(rows);
    const series = option.series as Array<{
      lineStyle?: { color?: string };
      itemStyle?: { color?: string };
      areaStyle?: { color?: string };
    }>;

    // 深色页 canvas 取色走 nocturneTokens；本图为血缘完整性观察，仍限定中性墨阶，
    // 禁止 warning/danger/accent（会被误读为业务预警）。
    const colors = [series[0].lineStyle?.color, series[0].itemStyle?.color, series[0].areaStyle?.color];
    const allowed = new Set<string>([
      nocturneTokens.color.inkSoft,
      nocturneTokens.color.inkMuted,
      nocturneTokens.color.lineSoft,
      nocturneTokens.color.panel2,
      nocturneTokens.color.panel3,
    ]);
    for (const color of colors) {
      expect(allowed.has(color ?? "")).toBe(true);
    }
    expect(colors).not.toContain(nocturneTokens.color.red);
    expect(colors).not.toContain(nocturneTokens.color.amber);
    expect(colors).not.toContain(nocturneTokens.color.blue);
    expect(colors).not.toContain(nocturneTokens.color.green);
  });

  it("reuses the normalized series values in the tooltip: missing/invalid strings read 无数据, never NaN%", () => {
    const rows = [
      buildRow({ report_date: "2025-12-31", untraced_share_pct: "12.5" }),
      buildRow({ report_date: "2026-01-31", untraced_share_pct: null }),
      buildRow({ report_date: "2026-02-28", untraced_share_pct: "not-a-number" }),
      buildRow({ report_date: "2026-03-31", untraced_share_pct: "" }),
    ];
    const option = buildUntracedReconciliationTrendOption(rows);
    const formatter = (option.tooltip as { formatter: (params: unknown) => string }).formatter;

    // 合法数值：按两位小数展示。
    expect(formatter([{ dataIndex: 0 }])).toContain("未追溯占比：12.50%");
    // null：显示无数据（与折线断点一致）。
    expect(formatter([{ dataIndex: 1 }])).toContain("未追溯占比：无数据");
    // 非法字符串：原实现 Number("not-a-number").toFixed(2) 直出 "NaN%"；
    // 现复用折线已归一的 values[dataIndex]，与断点口径一致。
    const invalidTooltip = formatter([{ dataIndex: 2 }]);
    expect(invalidTooltip).toContain("未追溯占比：无数据");
    expect(invalidTooltip).not.toContain("NaN");
    // 空串：原实现 Number("") 变 0 直出 "0.00%"（无中生有）；现同样显示无数据。
    expect(formatter([{ dataIndex: 3 }])).toContain("未追溯占比：无数据");
    // 行数证据仍原样透出。
    expect(formatter([{ dataIndex: 1 }])).toContain("未追溯行数 / 总行数：0 / 2");
    expect(formatter([])).toBe("");
  });

  it("maps invalid share strings to null data points in the series (no fabricated zeros)", () => {
    const rows = [
      buildRow({ report_date: "2026-02-28", untraced_share_pct: "not-a-number" }),
      buildRow({ report_date: "2026-03-31", untraced_share_pct: "" }),
    ];
    const option = buildUntracedReconciliationTrendOption(rows);
    const series = option.series as Array<{ data: unknown[] }>;
    expect(series[0].data).toEqual([null, null]);
  });
});

describe("UntracedReconciliationTrendPanel", () => {
  it("renders the chart when rows are present", () => {
    const rows = [
      buildRow({ report_date: "2025-12-31", untraced_share_pct: "0.00" }),
      buildRow({ report_date: "2026-01-31", untraced_share_pct: "0.00" }),
    ];
    const { getByTestId } = render(<UntracedReconciliationTrendPanel rows={rows} />);

    expect(getByTestId("untraced-reconciliation-trend-panel")).not.toBeNull();
    const stub = getByTestId("untraced-reconciliation-echarts-stub");
    expect(stub.textContent).toContain('"type":"line"');
    expect(stub.textContent).toContain("2026-01-31");
  });

  it("shows the empty-state message when rows is empty", () => {
    const { getByTestId, queryByTestId } = render(<UntracedReconciliationTrendPanel rows={[]} />);

    expect(getByTestId("untraced-reconciliation-trend-empty")).toHaveTextContent(
      "暂无可用的历史对账诊断数据",
    );
    expect(queryByTestId("untraced-reconciliation-trend-panel")).toBeNull();
  });
});
