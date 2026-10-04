import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OptionTwoSparkline } from "./OptionTwoSparkline";

function pathOf(container: HTMLElement): string {
  const path = container.querySelector('[data-spark-line="true"]');
  if (!path) throw new Error("expected sparkline path");
  return path.getAttribute("d") ?? "";
}

function dotX(dot: Element | null): number {
  const match = /^M([\d.]+) /.exec(dot?.getAttribute("d") ?? "");
  if (!match) throw new Error("expected a dot path with a leading move-to");
  return Number(match[1]);
}

describe("OptionTwoSparkline", () => {
  it("renders nothing with fewer than two finite points", () => {
    expect(render(<OptionTwoSparkline values={[]} />).container.firstChild).toBeNull();
    expect(render(<OptionTwoSparkline values={[1]} />).container.firstChild).toBeNull();
    expect(
      render(<OptionTwoSparkline values={[null, 2]} />).container.firstChild,
    ).toBeNull();
    expect(
      render(<OptionTwoSparkline values={[Number.NaN, 2]} />).container.firstChild,
    ).toBeNull();
  });

  it("breaks the path at null gaps instead of interpolating", () => {
    const { container } = render(<OptionTwoSparkline values={[1, null, 3]} />);
    const d = pathOf(container);
    expect(d.match(/M/g)).toHaveLength(2);
    expect(d.match(/L/g)).toBeNull();
  });

  it("draws an honest midline for an all-equal series", () => {
    const { container } = render(<OptionTwoSparkline values={[2, 2, 2]} />);
    const d = pathOf(container);
    const yValues = [...d.matchAll(/[ML][\d.]+ ([\d.]+)/g)].map((m) => Number(m[1]));
    expect(yValues).toHaveLength(3);
    for (const y of yValues) {
      expect(y).toBeCloseTo(10, 5);
    }
  });

  it("positions points by provided x scale instead of even spacing", () => {
    const { container } = render(
      <OptionTwoSparkline values={[1, 2, 3, 4]} xValues={[1, 3, 5, 10]} />,
    );
    const d = pathOf(container);
    const xValues = [...d.matchAll(/[ML]([\d.]+) /g)].map((m) => Number(m[1]));
    expect(xValues[0]).toBeCloseTo(0, 5);
    expect(xValues[1]).toBeCloseTo((2 / 9) * 100, 1);
    expect(xValues[2]).toBeCloseTo((4 / 9) * 100, 1);
    expect(xValues[3]).toBeCloseTo(100, 5);
  });

  it("marks the last valid point with the end dot", () => {
    const { container } = render(
      <OptionTwoSparkline values={[1, 2, null]} endDot />,
    );
    const endDot = container.querySelector('[data-end-dot="true"]');
    expect(endDot).not.toBeNull();
    expect(dotX(endDot)).toBeCloseTo(50, 1);
  });

  it("renders a dot per valid point when pointDots is enabled", () => {
    const { container } = render(
      <OptionTwoSparkline values={[1, null, 3, 4]} pointDots />,
    );
    const dots = container.querySelectorAll('[data-point-dot="true"]');
    expect(dots).toHaveLength(3);
  });

  it("keeps the end dot distinct from point dots", () => {
    const { container } = render(
      <OptionTwoSparkline values={[1, 2, 3]} pointDots endDot />,
    );
    expect(container.querySelectorAll('[data-point-dot="true"]')).toHaveLength(3);
    expect(container.querySelectorAll('[data-end-dot="true"]')).toHaveLength(1);
  });

  it("draws dots with non-scaling round caps so they stay circular when stretched", () => {
    const { container } = render(
      <OptionTwoSparkline values={[1, 2, 3]} pointDots endDot />,
    );

    // preserveAspectRatio="none" 会把用户坐标里的半径压成椭圆，点必须靠
    // 非缩放描边的圆端点成形，不能回退到 <circle r="...">。
    expect(container.querySelectorAll("circle")).toHaveLength(0);
    for (const dot of container.querySelectorAll(
      '[data-point-dot="true"], [data-end-dot="true"]',
    )) {
      expect(dot.getAttribute("stroke-linecap")).toBe("round");
      expect(dot.getAttribute("vector-effect")).toBe("non-scaling-stroke");
      const d = dot.getAttribute("d") ?? "";
      const [, moveX, moveY, lineX, lineY] =
        /^M([\d.]+) ([\d.]+)L([\d.]+) ([\d.]+)$/.exec(d) ?? [];
      expect(moveX).toBe(lineX);
      expect(moveY).toBe(lineY);
    }
  });
});
