import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OptionTwoSparkline } from "./OptionTwoSparkline";

function pathOf(container: HTMLElement): string {
  const path = container.querySelector("path");
  if (!path) throw new Error("expected sparkline path");
  return path.getAttribute("d") ?? "";
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
    const circle = container.querySelector("circle");
    expect(circle).not.toBeNull();
    expect(Number(circle?.getAttribute("cx"))).toBeCloseTo(50, 1);
  });
});
