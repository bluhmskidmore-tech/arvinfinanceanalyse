import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CampisiEffectAvailability, CampisiFourEffectsPayload } from "../../../api/contracts";
import { mockCampisiFourEffects } from "../../../mocks/campisiMocks";
import { CampisiAttributionPanel } from "./CampisiAttributionPanel";
import { CampisiEnhancedPanel } from "./CampisiEnhancedPanel";
import { CampisiMaturityBucketPanel } from "./CampisiMaturityBucketPanel";
import { normalizeCampisiData } from "./campisiAttributionPanelSupport";

vi.mock("../../../lib/echarts", () => ({ default: () => <div /> }));

const available = { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 } as const;
function availability(partial = false): CampisiEffectAvailability {
  return { bonds: partial ? 2 : 1, treasury_effect: available, spread_effect: available,
    accrued_interest: available, position_change: { status: partial ? "partial" : "unavailable",
      reason: "principal_change_without_cashflows", unavailable_bonds: 1, unavailable_market_value_start: 1000000,
      unavailable_market_value_end: 2000000, covered_bonds: partial ? 1 : 0 } };
}
function payload(partial = false): CampisiFourEffectsPayload {
  return { ...mockCampisiFourEffects, basis: undefined, by_asset_class: [], by_bond: [],
    totals: { income_return: 0, treasury_effect: 0, spread_effect: 0, selection_effect: partial ? 100 : 0,
      total_return: partial ? 100 : 0, market_value_start: partial ? 1000000 : 0 },
    effect_availability: availability(partial) };
}

describe("principal cashflows are unavailable", () => {
  it("does not publish an empty covered subtotal as zero portfolio return", () => {
    const data = payload();
    expect(normalizeCampisiData(data)?.total_return).toBeNull();
    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);
    expect(screen.getByTestId("campisi-effect-amount-income")).toHaveTextContent("不可用");
    expect(screen.queryByTestId("campisi-driver-summary")).not.toBeInTheDocument();
    expect(screen.getByText(/排除期初市值 1000000 元/)).toBeInTheDocument();
    expect(screen.getByText(/排除期初市值 1000000 元/)).toHaveTextContent("期末市值 2000000 元");
  });

  it("keeps the covered subtotal and discloses excluded principal without extrapolation", () => {
    expect(normalizeCampisiData(payload(true))?.total_return).toBe(100);
    render(<CampisiAttributionPanel data={payload(true)} state={{ kind: "ok" }} onRetry={() => {}} />);
    expect(screen.getByText(/影响 1\/2 只债券/)).toHaveTextContent("未外推全组合");
  });

  it("masks enhanced total return when no positions qualify", () => {
    const data = payload();
    render(<CampisiEnhancedPanel data={{ ...data, by_asset_class: [], by_bond: [], totals: { ...data.totals, convexity_effect: 0,
      cross_effect: 0, reinvestment_effect: 0 } }} state={{ kind: "ok" }} onRetry={() => {}} />);
    expect(screen.getByTestId("campisi-enhanced-amount-total_return")).toHaveTextContent("—");
  });

  it("masks maturity buckets and explains the exclusions", () => {
    render(<CampisiMaturityBucketPanel data={{ period_start: "2026-01-01", period_end: "2026-01-31",
      effect_availability: availability(), buckets: { "1-3Y": payload().totals } }}
      state={{ kind: "ok" }} onRetry={() => {}} />);
    expect(screen.queryByText("0.00")).not.toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(5);
  });

  it.each([
    { side: "bought", mixed: false }, { side: "sold", mixed: false },
    { side: "bought", mixed: true }, { side: "sold", mixed: true },
  ])("discloses $side holdings with mixed=$mixed across each Campisi panel", ({ side, mixed }) => {
    const start = side === "sold" ? 1000000 : 0;
    const end = side === "bought" ? 2000000 : 0;
    const coverage = availability(mixed);
    coverage.position_change = { ...coverage.position_change!, unavailable_market_value_start: start,
      unavailable_market_value_end: end };
    const data = { ...payload(mixed), effect_availability: coverage,
      totals: { ...payload(mixed).totals, selection_effect: mixed ? 1000000 : 0,
        total_return: mixed ? 1000000 : 0 } };
    render(<>
      <CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />
      <CampisiEnhancedPanel data={{ ...data, by_asset_class: [], by_bond: [], totals: { ...data.totals,
        convexity_effect: 0, cross_effect: 0, reinvestment_effect: 0 } }} state={{ kind: "ok" }} onRetry={() => {}} />
      <CampisiMaturityBucketPanel data={{ period_start: data.period_start, period_end: data.period_end,
        effect_availability: coverage, buckets: mixed ? { "1-3Y": data.totals } : {} }}
        state={{ kind: "ok" }} onRetry={() => {}} />
    </>);
    const notices = screen.getAllByText(new RegExp(`排除期初市值 ${start} 元`));
    expect(notices).toHaveLength(3);
    for (const notice of notices) {
      expect(notice).toHaveTextContent(`期末市值 ${end} 元`);
      expect(notice).toHaveTextContent(`影响 1/${mixed ? 2 : 1} 只债券`);
      expect(notice).toHaveTextContent("持仓新增、退出");
      expect(notice).toHaveTextContent("未外推全组合");
    }
    expect(screen.getByTestId("campisi-enhanced-amount-total_return")).toHaveTextContent(mixed ? "0.01 亿" : "—");
    expect(normalizeCampisiData(data)?.total_return).toBe(mixed ? 1000000 : null);
    if (!mixed) {
      expect(screen.queryByText("0.00 亿")).not.toBeInTheDocument();
      expect(screen.queryByTestId("campisi-driver-summary")).not.toBeInTheDocument();
    }
  });
});
