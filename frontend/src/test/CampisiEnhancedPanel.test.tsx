import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { CampisiEnhancedPayload } from "../api/contracts";
import { CampisiEnhancedPanel } from "../features/pnl-attribution/components/CampisiEnhancedPanel";
import { sumCampisiEnhancedDisplayAmounts } from "../features/pnl-attribution/components/campisiEnhancedPanelSupport";
import { mockCampisiEnhanced } from "../mocks/campisiMocks";

const SECOND_ORDER_KEYS = ["convexity_effect", "cross_effect", "reinvestment_effect"] as const;

/** model 路径：无 `basis`，三项是真算出来的观测值。 */
const modelPathPayload: CampisiEnhancedPayload = {
  report_date: "2026-03-31",
  period_start: "2026-03-01",
  period_end: "2026-03-31",
  num_days: 30,
  totals: {
    income_return: 820_000,
    treasury_effect: -210_000,
    spread_effect: 160_000,
    convexity_effect: 1_800_000_000,
    cross_effect: 0,
    reinvestment_effect: 0,
    selection_effect: 95_000,
    total_return: 865_000,
    market_value_start: 128_000_000,
  },
  by_asset_class: [],
  by_bond: [],
};

function renderPanel(data: CampisiEnhancedPayload) {
  return render(<CampisiEnhancedPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);
}

describe("CampisiEnhancedPanel", () => {
  it("renders the bridge second-order effects as em-dash with a not-decomposed badge", () => {
    renderPanel(mockCampisiEnhanced);

    for (const key of SECOND_ORDER_KEYS) {
      // "0.00 亿" 与真实观测到的零无法区分，正是本次要消灭的静默。
      expect(screen.getByTestId(`campisi-enhanced-amount-${key}`)).toHaveTextContent("—");
      expect(screen.getByTestId(`campisi-enhanced-amount-${key}`)).not.toHaveTextContent("亿");
      expect(screen.getByTestId(`campisi-enhanced-not-decomposed-${key}`)).toHaveTextContent(
        "该路径不拆分",
      );
    }
  });

  it("keeps first-order bridge amounts rendered as numbers", () => {
    renderPanel(mockCampisiEnhanced);

    expect(screen.getByTestId("campisi-enhanced-amount-income_return")).toHaveTextContent("0.01 亿");
    expect(screen.getByTestId("campisi-enhanced-amount-selection_effect")).toHaveTextContent("亿");
    expect(
      screen.queryByTestId("campisi-enhanced-not-decomposed-selection_effect"),
    ).not.toBeInTheDocument();
  });

  it("tells the bridge and model decomposition stories apart in the intro copy", () => {
    const { unmount } = renderPanel(mockCampisiEnhanced);
    expect(screen.getByText(/不在本路径拆分/)).toBeInTheDocument();
    unmount();

    renderPanel(modelPathPayload);
    expect(screen.getByText(/从选券残差中拆出/)).toBeInTheDocument();
  });

  it("leaves the model path rendering untouched", () => {
    renderPanel(modelPathPayload);

    expect(screen.getByTestId("campisi-enhanced-amount-convexity_effect")).toHaveTextContent(
      "18.00 亿",
    );
    // model 路径算出来的 0 仍是观测值，必须以数字形式发布。
    expect(screen.getByTestId("campisi-enhanced-amount-cross_effect")).toHaveTextContent("0.00 亿");
    for (const key of SECOND_ORDER_KEYS) {
      expect(
        screen.queryByTestId(`campisi-enhanced-not-decomposed-${key}`),
      ).not.toBeInTheDocument();
    }
  });

  it("keeps undecomposed amounts inside the closure sum instead of degrading it to null", () => {
    // 展示层改破折号，数值层必须原样参与求和，否则 bridge 闭合断言会退化成 null。
    expect(sumCampisiEnhancedDisplayAmounts(mockCampisiEnhanced.totals)).toBe(
      mockCampisiEnhanced.totals.total_return,
    );
    expect(mockCampisiEnhanced.totals.convexity_effect).toBe(0);
    expect(mockCampisiEnhanced.totals.cross_effect).toBe(0);
    expect(mockCampisiEnhanced.totals.reinvestment_effect).toBe(0);
  });

  it("surfaces the bridge availability entries as not_decomposed rather than unavailable", () => {
    const availability = mockCampisiEnhanced.effect_availability;

    expect(availability?.convexity_effect?.status).toBe("not_decomposed");
    expect(availability?.cross_effect?.reason).toBe("bridge_second_order_not_decomposed");
    expect(availability?.reinvestment_effect?.status).not.toBe("unavailable");
  });
});
