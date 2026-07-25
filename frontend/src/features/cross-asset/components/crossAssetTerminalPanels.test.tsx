import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ibTokens } from "../../../theme/designSystem";
import type { CorrelationMatrix, WaterfallBar } from "../lib/crossAssetAnalytics";

import { CorrelationHeatmapPanel } from "./CorrelationAndRegimePanels";
import { DriverWaterfallPanel } from "./DriverWaterfallPanel";

const MATRIX: CorrelationMatrix = {
  keys: ["csi300", "cn_gov_10y"],
  labels: ["沪深300", "10Y国债"],
  cells: [
    [
      { rowKey: "csi300", colKey: "csi300", value: 1 },
      { rowKey: "csi300", colKey: "cn_gov_10y", value: 0.8 },
    ],
    [
      { rowKey: "cn_gov_10y", colKey: "csi300", value: 0.8 },
      { rowKey: "cn_gov_10y", colKey: "cn_gov_10y", value: 1 },
    ],
  ],
};

const BARS: WaterfallBar[] = [
  { key: "liquidity", label: "流动性", value: 0.2, cumulative: 0.2, kind: "factor", color: ibTokens.color.down },
  { key: "rate", label: "海外利率", value: -0.1, cumulative: 0.1, kind: "factor", color: ibTokens.color.up },
  { key: "composite", label: "综合", value: 0.1, cumulative: 0.1, kind: "total", color: ibTokens.color.down },
];

describe("CorrelationHeatmapPanel terminal theme", () => {
  it("uses the terminal heatmap ramp while the default stays on correlationColor", () => {
    const { container: light } = render(<CorrelationHeatmapPanel matrix={MATRIX} />);
    const lightCell = light.querySelector<HTMLElement>('[title="沪深300 × 10Y国债: 0.80"]')!;
    expect(lightCell.style.background).toContain("34, 139, 34");

    const { container: dark } = render(<CorrelationHeatmapPanel matrix={MATRIX} theme="terminal" />);
    const darkCell = dark.querySelector<HTMLElement>('[title="沪深300 × 10Y国债: 0.80"]')!;
    expect(darkCell.style.background).toContain("102, 185, 139");
  });
});

describe("DriverWaterfallPanel terminal theme", () => {
  it("replaces bar colors with the terminal up/down hues, keeping business signs", () => {
    const { container: light } = render(<DriverWaterfallPanel bars={BARS} env={{}} />);
    const lightBars = light.querySelectorAll<HTMLElement>(".ca-waterfall__bar");
    expect(lightBars[0]!.style.background).toBe("rgb(180, 35, 24)");

    const { container: dark } = render(<DriverWaterfallPanel bars={BARS} env={{}} theme="terminal" />);
    const darkBars = dark.querySelectorAll<HTMLElement>(".ca-waterfall__bar");
    expect(darkBars[0]!.style.background).toBe("rgb(212, 122, 114)");
    expect(darkBars[1]!.style.background).toBe("rgb(102, 185, 139)");
    expect(darkBars[2]!.style.background).toBe("rgb(212, 122, 114)");
  });
});
