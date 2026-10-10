import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Numeric } from "../../../api/contracts";
import { BOND_SECTION_READY } from "../sectionStatus";
import { MaturityStructureChart } from "./MaturityStructureChart";
import { YieldDistributionBar } from "./YieldDistributionBar";

let lastChartOption: unknown = null;

vi.mock("../../../components/charts/BaseChart", () => ({
  BaseChart: ({ option }: { option: unknown }) => {
    lastChartOption = option;
    return <div data-testid="bond-dashboard-chart-stub" />;
  },
}));

function numeric(
  raw: number | null,
  unit: Numeric["unit"],
  rawText?: string,
): Numeric {
  return {
    raw,
    ...(rawText === undefined ? {} : { raw_text: rawText }),
    unit,
    display: raw === null ? "—" : String(raw),
    precision: 8,
    sign_aware: false,
  };
}

function readChartOption(): {
  series: Array<{ data: Array<number | null> }>;
  tooltip: { formatter: (params: unknown) => string };
} {
  if (!lastChartOption) {
    throw new Error("chart option not captured");
  }
  return lastChartOption as {
    series: Array<{ data: Array<number | null> }>;
    tooltip: { formatter: (params: unknown) => string };
  };
}

describe("bond dashboard exact numeric chart boundaries", () => {
  it("uses exact yuan text in the yield tooltip while keeping chart data numeric", () => {
    render(
      <YieldDistributionBar
        yieldData={{
          report_date: "2026-04-30",
          items: [
            {
              yield_bucket: "2.0%-2.5%",
              total_market_value: numeric(100_000_000, "yuan", "150000000.00000000"),
              bond_count: 3,
            },
          ],
        } as never}
        tenorData={undefined}
        yieldState={BOND_SECTION_READY}
        tenorState={BOND_SECTION_READY}
      />,
    );

    const option = readChartOption();
    expect(option.series[0]?.data).toEqual([1.5]);
    expect(
      option.tooltip.formatter({
        name: "2.0%-2.5%",
        dataIndex: 0,
        value: 1.5,
      }),
    ).toContain("1.50 亿元");
  });

  it("keeps missing chart values blank in the yield tooltip instead of fabricating a unit", () => {
    render(
      <YieldDistributionBar
        yieldData={{
          report_date: "2026-04-30",
          items: [
            {
              yield_bucket: "missing",
              total_market_value: numeric(null, "yuan"),
              bond_count: 0,
            },
          ],
        } as never}
        tenorData={undefined}
        yieldState={BOND_SECTION_READY}
        tenorState={BOND_SECTION_READY}
      />,
    );

    const option = readChartOption();
    expect(option.series[0]?.data).toEqual([null]);
    const tooltip = option.tooltip.formatter({
      name: "missing",
      dataIndex: 0,
      value: null,
    });
    expect(tooltip).toContain("<br/>—");
    expect(tooltip).not.toContain("— 亿元");
  });

  it("keeps the raw-only yield coordinate on the legacy js path", () => {
    const rawOnlyValue = 150_000_001;
    render(
      <YieldDistributionBar
        yieldData={{
          report_date: "2026-04-30",
          items: [
            {
              yield_bucket: "legacy",
              total_market_value: numeric(rawOnlyValue, "yuan"),
              bond_count: 1,
            },
          ],
        } as never}
        tenorData={undefined}
        yieldState={BOND_SECTION_READY}
        tenorState={BOND_SECTION_READY}
      />,
    );

    const option = readChartOption();
    expect(option.series[0]?.data[0]).toBe(rawOnlyValue / 1e8);
    expect(option.tooltip.formatter({ name: "legacy", dataIndex: 0, value: rawOnlyValue / 1e8 })).toContain(
      "1.50 亿元",
    );
  });

  it("uses exact text for maturity tooltip rows and total while keeping series numeric", () => {
    render(
      <MaturityStructureChart
        state={BOND_SECTION_READY}
        data={{
          report_date: "2026-04-30",
          total_market_value: numeric(200_000_000, "yuan", "250000000.00000000"),
          items: [
            {
              maturity_bucket: "1-3年",
              total_market_value: numeric(100_000_000, "yuan", "150000000.00000000"),
              bond_count: 1,
              percentage: numeric(0.4, "ratio", "0.37500000"),
            },
          ],
        } as never}
      />,
    );

    expect(screen.getByText("合计 2.50 亿元")).toBeInTheDocument();

    const option = readChartOption();
    expect(option.series[0]?.data).toEqual([1.5]);
    expect(option.series[1]?.data).toEqual([37.5]);

    const tooltip = option.tooltip.formatter([
      { seriesName: "规模(亿)", name: "1-3年", dataIndex: 0, value: 1.5 },
      { seriesName: "占比(%)", name: "1-3年", dataIndex: 0, value: 37.5 },
    ]);
    expect(tooltip).toContain("规模(亿)：1.50 亿元");
    expect(tooltip).toContain("占比(%)：37.50%");
    expect(tooltip).toContain("1 只");
  });

  it("keeps the raw-only maturity coordinates on the legacy js path", () => {
    const rawOnlyValue = 150_000_001;
    const rawOnlyRatio = 0.37500001;
    render(
      <MaturityStructureChart
        state={BOND_SECTION_READY}
        data={{
          report_date: "2026-04-30",
          total_market_value: numeric(rawOnlyValue, "yuan"),
          items: [
            {
              maturity_bucket: "legacy",
              total_market_value: numeric(rawOnlyValue, "yuan"),
              bond_count: 2,
              percentage: numeric(rawOnlyRatio, "ratio"),
            },
          ],
        } as never}
      />,
    );

    const option = readChartOption();
    expect(option.series[0]?.data[0]).toBe(rawOnlyValue / 1e8);
    expect(option.series[1]?.data[0]).toBe(rawOnlyRatio * 100);
  });

  it("switches the tenor tooltip percentage to the governed exact display", () => {
    render(
      <YieldDistributionBar
        yieldData={{
          report_date: "2026-04-30",
          items: [],
        } as never}
        tenorData={{
          report_date: "2026-04-30",
          group_by: "tenor_bucket",
          total_market_value: numeric(200_000_000, "yuan"),
          items: [
            {
              category: "1-3年",
              total_market_value: numeric(100_000_000, "yuan", "150000000.00000000"),
              bond_count: 2,
              percentage: numeric(0.4, "ratio", "0.37500000"),
            },
          ],
        } as never}
        yieldState={BOND_SECTION_READY}
        tenorState={BOND_SECTION_READY}
      />,
    );

    fireEvent.click(screen.getByText("期限"));

    const option = readChartOption();
    const tooltip = option.tooltip.formatter({
      name: "1-3年",
      dataIndex: 0,
      value: 1.5,
    });
    expect(tooltip).toContain("1.50 亿元");
    expect(tooltip).toContain("占比：37.50%");
  });
});
