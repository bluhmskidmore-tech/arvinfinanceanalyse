import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { BaseChart } from "../components/charts/BaseChart";
import { ibTokens, nocturneTokens } from "../theme/designSystem";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="base-chart-echarts-stub" />,
}));

/** jsdom 把 hex 归一化为 rgb()，按同一规则换算后再比对 token。 */
function hexToRgb(hex: string): string {
  const value = Number.parseInt(hex.slice(1), 16);
  return `rgb(${(value >> 16) & 0xff}, ${(value >> 8) & 0xff}, ${value & 0xff})`;
}

describe("BaseChart", () => {
  it("renders the empty state on the Nocturne panel palette, not the IB light surface", () => {
    render(<BaseChart option={{ series: [] }} height={120} />);

    const empty = screen.getByTestId("base-chart-empty");
    expect(empty).toHaveTextContent("暂无数据");
    // 2026-09-02 走查：40+ 深色页图表共用此空态，此前是 IB 浅色白底 + 2px 圆角。
    expect(empty.style.background).toBe(hexToRgb(nocturneTokens.color.panel2));
    expect(empty.style.color).toBe(hexToRgb(nocturneTokens.color.inkMuted));
    expect(empty.style.borderRadius).toBe(`${nocturneTokens.radius}px`);
    expect(empty.style.background).not.toBe(hexToRgb(ibTokens.color.surface));
    expect(screen.queryByTestId("base-chart-echarts-stub")).not.toBeInTheDocument();
  });

  it("mounts the chart when the option carries series", () => {
    render(<BaseChart option={{ series: [{ type: "bar", data: [1] }] }} height={120} />);

    expect(screen.getByTestId("base-chart-echarts-stub")).toBeInTheDocument();
    expect(screen.queryByTestId("base-chart-empty")).not.toBeInTheDocument();
  });
});
