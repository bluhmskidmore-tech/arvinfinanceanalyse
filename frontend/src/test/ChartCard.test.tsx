import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import type { EChartsOption } from "../lib/echarts";
import { ChartCard } from "../components/charts/ChartCard";
import { applyChartCardChrome, detectChartCardWarnings } from "../components/charts/chartCardChrome";
import { chartCardLegendReservedBottom, CHART_CARD_HEIGHTS } from "../components/charts/chartCardScale";
import { ibTokens, nocturneTokens } from "../theme/designSystem";

const captured: { option: EChartsOption | null; height: number | null } = { option: null, height: null };

vi.mock("../lib/echarts", () => ({
  default: ({ option, style }: { option: EChartsOption; style?: { height?: number } }) => {
    captured.option = option;
    captured.height = style?.height ?? null;
    return <div data-testid="chart-card-echarts-stub" />;
  },
}));

/** 测试夹具允许用宽松对象构造 option（渐变对象等不逐字段满足 ECharts 类型）。 */
const asOption = (value: unknown) => value as EChartsOption;

const barOption: EChartsOption = {
  xAxis: { type: "category", data: ["1Y", "3Y", "5Y"] },
  yAxis: { type: "value" },
  legend: { right: 0, top: 0, type: "scroll" },
  // 调用方带来的浅色 tooltip 底必须被铬件覆盖掉。
  tooltip: { trigger: "axis", backgroundColor: ibTokens.color.surface },
  series: [{ name: "期限", type: "bar", data: [1, 2, 3] }],
};

const accent = nocturneTokens.color.blue;
const green = nocturneTokens.color.green;

describe("ChartCard", () => {
  beforeEach(() => {
    captured.option = null;
    captured.height = null;
  });

  it("renders a figure with title, unit · asOf meta and a Nocturne-chromed chart", () => {
    render(
      <ChartCard
        testId="cc"
        title="期限结构"
        question="到期集中在哪个窗口"
        unit="亿元"
        asOf="2026-07-31"
        height={CHART_CARD_HEIGHTS.hero}
        option={barOption}
        footnote="来源 债券总览"
      />,
    );

    const figure = screen.getByTestId("cc");
    expect(figure.tagName).toBe("FIGURE");
    expect(figure).toHaveAttribute("data-state", "ready");
    expect(figure).toHaveAttribute("aria-label", "期限结构");
    expect(figure).toHaveTextContent("期限结构");
    expect(figure).toHaveTextContent("到期集中在哪个窗口");
    expect(figure).toHaveTextContent("亿元 · 2026-07-31");
    expect(figure).toHaveTextContent("来源 债券总览");
    expect(screen.getByTestId("chart-card-echarts-stub")).toBeInTheDocument();
    expect(captured.height).toBe(280);

    // 铬件统一覆盖：图例左下 plain，tooltip 深色底，全局文字色 inkSoft；series 原样保留。
    const option = captured.option as Record<string, unknown>;
    expect(option.legend).toMatchObject({ show: true, type: "plain", left: 0, bottom: 0, itemWidth: 12, itemHeight: 8 });
    expect(option.tooltip).toMatchObject({ backgroundColor: nocturneTokens.color.panel2, borderColor: nocturneTokens.color.line, trigger: "axis" });
    expect((option.textStyle as { color: string }).color).toBe(nocturneTokens.color.inkSoft);
    expect(option.series).toEqual(barOption.series);
    expect(option.xAxis).toEqual(barOption.xAxis);
  });

  it("collapses to the shrinking empty state when option is null or has no series", () => {
    const { rerender } = render(<ChartCard testId="cc" title="券种分布" option={null} asOf={null} />);
    expect(screen.getByTestId("cc")).toHaveAttribute("data-state", "empty");
    expect(screen.getByTestId("cc-state")).toHaveAttribute("data-status", "empty");
    expect(screen.getByTestId("cc")).toHaveTextContent("暂无数据");
    expect(screen.queryByTestId("chart-card-echarts-stub")).not.toBeInTheDocument();
    // 应有日期但缺失（asOf=null）渲染 EM_DASH，不留空；不传 asOf 则不占位。
    expect(screen.getByTestId("cc")).toHaveTextContent("—");

    rerender(<ChartCard testId="cc" title="券种分布" option={{ series: [] }} emptyMessage="结构数据待返回" />);
    expect(screen.getByTestId("cc")).toHaveTextContent("结构数据待返回");
  });

  it("shows an anti-reflow loading backdrop at the chart height", () => {
    render(<ChartCard testId="cc" title="收益趋势" option={barOption} state="loading" height={160} />);
    const surface = screen.getByTestId("cc-state");
    expect(surface).toHaveAttribute("data-status", "loading");
    expect(surface.getAttribute("style")).toContain("--ss-min-height: 160px");
    expect(screen.queryByTestId("chart-card-echarts-stub")).not.toBeInTheDocument();
  });

  it("renders error copy with a single retry only when onRetry is provided", () => {
    const onRetry = vi.fn();
    const { rerender } = render(
      <ChartCard testId="cc" title="集中度" option={barOption} state="error" errorMessage="当前角色无权读取" />,
    );
    expect(screen.getByTestId("cc")).toHaveAttribute("data-state", "error");
    expect(screen.getByTestId("cc")).toHaveTextContent("当前角色无权读取");
    expect(screen.queryByRole("button", { name: "重试" })).not.toBeInTheDocument();

    rerender(<ChartCard testId="cc" title="集中度" option={barOption} state="error" onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("keeps drawing for stale / partial and flags the date with an amber dot", () => {
    render(<ChartCard testId="cc" title="NIM 压力" option={barOption} state="stale" asOf="2026-06-30" unit="%" />);
    const figure = screen.getByTestId("cc");
    expect(figure).toHaveAttribute("data-state", "stale");
    expect(screen.getByTestId("chart-card-echarts-stub")).toBeInTheDocument();
    const meta = figure.querySelector('[title^="数据陈旧"]');
    expect(meta).not.toBeNull();
    expect(meta!.querySelector("i")).not.toBeNull();
  });

  it("falls back to 220 for an illegal height and warns in dev", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(<ChartCard title="x" option={barOption} height={300 as unknown as 220} />);
    expect(captured.height).toBe(220);
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("非法高度"));
    warn.mockRestore();
  });

  it("omits the caption when a flat chart inherits its outer section title", () => {
    render(<ChartCard flat ariaLabel="收益归因" option={barOption} />);
    const figure = screen.getByRole("figure", { name: "收益归因" });
    expect(figure.querySelector("figcaption")).toBeNull();
  });

  it("keeps the metadata row for a titleless flat chart when unit is present", () => {
    render(<ChartCard flat ariaLabel="收益归因" unit="亿元" option={barOption} />);
    const figure = screen.getByRole("figure", { name: "收益归因" });
    expect(figure.querySelector("figcaption")).not.toBeNull();
    expect(figure).toHaveTextContent("亿元");
  });

  it("passes the chromed option and tier height to an interactive chart renderer", () => {
    const renderer = vi.fn(({ option, height }: { option: EChartsOption; height: number }) => (
      <div data-testid="interactive-chart" data-height={height}>
        {String((option.legend as { left?: number }).left)}
      </div>
    ));
    render(<ChartCard title="KRD分档" height={280} option={barOption} chartRenderer={renderer} />);
    expect(screen.getByTestId("interactive-chart")).toHaveAttribute("data-height", "280");
    expect(screen.getByTestId("interactive-chart")).toHaveTextContent("0");
    expect(renderer).toHaveBeenCalledTimes(1);
  });

  it("warns once about forbidden chart grammar (two pies, rounded bars)", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    render(
      <ChartCard
        title="结构"
        option={{
          series: [
            { type: "pie", data: [] },
            { type: "pie", data: [] },
            { type: "bar", name: "柱", data: [1], itemStyle: { borderRadius: [6, 6, 0, 0] } },
          ],
        }}
      />,
    );
    expect(warn).toHaveBeenCalledTimes(1);
    const message = String(warn.mock.calls[0]?.[0]);
    expect(message).toContain("2 个环形/饼图");
    expect(message).toContain("柱圆角超过 2px");
    warn.mockRestore();
  });
});

describe("chartCardChrome helpers", () => {
  it("reserves legend rows at the bottom and honours legend=none", () => {
    expect(chartCardLegendReservedBottom(0)).toBe(0);
    expect(chartCardLegendReservedBottom(1)).toBe(24);
    expect(chartCardLegendReservedBottom(9)).toBe(chartCardLegendReservedBottom(4));
    const none = applyChartCardChrome(barOption, { legend: "none" }) as Record<string, unknown>;
    expect(none.legend).toEqual({ show: false });
    expect((none.grid as { bottom: number }).bottom).toBe(4);
    const two = applyChartCardChrome(barOption, { legendRows: 2 }) as Record<string, unknown>;
    expect((two.grid as { bottom: number }).bottom).toBe(chartCardLegendReservedBottom(2) + 4);
  });

  it("flags only real grammar violations", () => {
    expect(detectChartCardWarnings(barOption)).toEqual([]);
    // 单色透明度渐变（同一色相、只变 alpha 位）允许。
    expect(
      detectChartCardWarnings(
        asOption({
          series: [{ type: "line", name: "a", areaStyle: { color: { colorStops: [{ color: `${accent}22` }, { color: `${accent}00` }] } } }],
        }),
      ),
    ).toEqual([]);
    // 双色相渐变（AI 紫→绿）是禁止项。
    expect(
      detectChartCardWarnings(
        asOption({
          series: [{ type: "line", name: "a", areaStyle: { color: { colorStops: [{ color: accent }, { color: green }] } } }],
        }),
      ),
    ).toHaveLength(1);
  });
});
