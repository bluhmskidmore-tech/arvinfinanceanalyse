import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../lib/echarts", () => ({
  default: ({ option }: { option?: unknown }) => (
    <div data-testid="untraced-reconciliation-echarts-stub">{JSON.stringify(option ?? null)}</div>
  ),
}));

import type { PnlByBusinessUntracedTrendRow } from "../../api/contracts";
import { ibTokens } from "../../theme/designSystem";
import {
  buildUntracedReconciliationTrendOption,
  UntracedReconciliationTrendPanel,
} from "./UntracedReconciliationTrendPanel";

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

  it("only uses neutral IB ink/surface tones for the series styling (no warning/danger/KPI accent colors)", () => {
    const rows = [buildRow({})];
    const option = buildUntracedReconciliationTrendOption(rows);
    const series = option.series as Array<{
      lineStyle?: { color?: string };
      itemStyle?: { color?: string };
      areaStyle?: { color?: string };
    }>;

    const colors = [series[0].lineStyle?.color, series[0].itemStyle?.color, series[0].areaStyle?.color];
    const allowed = new Set<string>([
      ibTokens.color.inkSecondary,
      ibTokens.color.surfaceMuted,
      ibTokens.color.inkMuted,
      ibTokens.color.hairline,
    ]);
    for (const color of colors) {
      expect(allowed.has(color ?? "")).toBe(true);
    }
    expect(colors).not.toContain(ibTokens.color.down);
    expect(colors).not.toContain(ibTokens.color.warn);
    expect(colors).not.toContain(ibTokens.color.accent);
    expect(colors).not.toContain(ibTokens.color.up);
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
