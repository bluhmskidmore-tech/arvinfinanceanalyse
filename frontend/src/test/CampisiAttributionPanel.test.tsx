import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option: unknown }) => (
    <pre data-testid="campisi-echarts-stub">{JSON.stringify(option)}</pre>
  ),
}));

import type {
  CampisiAttributionPayload,
  CampisiFourEffectsPayload,
  Numeric,
} from "../api/contracts";
import { CampisiAttributionPanel } from "../features/pnl-attribution/components/CampisiAttributionPanel";
import {
  buildEffectRows,
  normalizeCampisiData,
  sumCampisiEffectAmounts,
} from "../features/pnl-attribution/components/campisiAttributionPanelSupport";
import { sumCampisiEnhancedDisplayAmounts } from "../features/pnl-attribution/components/campisiEnhancedPanelSupport";
import {
  mockCampisiEnhanced,
  mockCampisiFourEffects,
  mockCampisiFourEffectsModelPath,
} from "../mocks/campisiMocks";

function numeric(raw: number | null, unit: Numeric["unit"], display = ""): Numeric {
  return {
    raw,
    unit,
    display,
    precision: 2,
    sign_aware: true,
  };
}

describe("CampisiAttributionPanel", () => {
  it("renders formal closure warning for current four-effect payloads", () => {
    const data: CampisiFourEffectsPayload = {
      report_date: "2026-04-30",
      period_start: "2026-03-31",
      period_end: "2026-04-30",
      num_days: 30,
      totals: {
        income_return: 600_000_000,
        treasury_effect: 200_000_000,
        spread_effect: -100_000_000,
        selection_effect: 100_000_000,
        total_return: 800_000_000,
        market_value_start: 12_000_000_000,
      },
      by_asset_class: [],
      by_bond: [],
      formal_closure: {
        basis: "pnl.bridge.total_actual_pnl",
        report_date: "2026-04-30",
        status: "warning",
        campisi_total_return: 800_000_000,
        formal_actual_pnl: 700_000_000,
        residual_to_formal_pnl: -100_000_000,
        residual_ratio: 0.142857,
        message: "Campisi total return does not close to formal PnL.",
      },
    };

    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const warning = screen.getByTestId("campisi-formal-closure-warning");
    expect(warning).toBeInTheDocument();
    expect(warning).toHaveTextContent("+8.00 亿");
    expect(screen.getByTestId("campisi-driver-summary")).toHaveTextContent("75.0%");
    // 四效应 totals 后端无占比字段，前端派生占比时必须标注非正式指标。
    expect(screen.getByTestId("campisi-share-derived-note")).toHaveTextContent(
      "展示辅助计算（非正式指标）",
    );
  });

  it("makes the main Campisi driver and quiet effects obvious", () => {
    const data: CampisiFourEffectsPayload = {
      report_date: "2026-04-30",
      period_start: "2026-03-31",
      period_end: "2026-04-30",
      num_days: 30,
      totals: {
        income_return: 529_838_963.09,
        treasury_effect: 0,
        spread_effect: 0,
        selection_effect: 6_106_054.95,
        total_return: 535_945_018.04,
        market_value_start: 343_822_795_478.69,
      },
      by_asset_class: [],
      by_bond: [],
      formal_closure: {
        basis: "pnl.bridge.total_actual_pnl",
        report_date: "2026-04-30",
        status: "closed",
        campisi_total_return: 535_945_018.04,
        formal_actual_pnl: 535_945_018.04,
        residual_to_formal_pnl: 0,
        residual_ratio: 0,
        message: "Campisi total return closes to formal PnL.",
      },
    };

    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const boundary = screen.getByTestId("campisi-capability-boundary");
    expect(boundary).toHaveTextContent("尚未实现交易员能力评价");
    expect(boundary).toHaveTextContent("个券跑赢同类基准");

    const summary = screen.getByTestId("campisi-driver-summary");
    expect(summary).toHaveTextContent("主要贡献：收入效应");
    expect(summary).toHaveTextContent("约 98.9%");
    expect(summary).toHaveTextContent("几乎没有影响：国债曲线、信用利差");
    expect(summary).toHaveTextContent("不能直接等同交易员主动选券能力");
    expect(screen.queryByTestId("campisi-formal-closure-warning")).not.toBeInTheDocument();
  });

  it("renders legacy governed pct raw ratios as percent points", () => {
    const data: CampisiAttributionPayload = {
      report_date: "2026-04-30",
      period_start: "2026-03-31",
      period_end: "2026-04-30",
      num_days: 30,
      total_market_value: numeric(12_000_000_000, "yuan", "+120.00 亿"),
      total_return: numeric(800_000_000, "yuan", "+8.00 亿"),
      total_return_pct: numeric(0.066667, "pct", "+6.67%"),
      total_income: numeric(600_000_000, "yuan", "+6.00 亿"),
      total_treasury_effect: numeric(200_000_000, "yuan", "+2.00 亿"),
      total_spread_effect: numeric(-100_000_000, "yuan", "-1.00 亿"),
      total_selection_effect: numeric(100_000_000, "yuan", "+1.00 亿"),
      income_contribution_pct: numeric(0.75, "pct", "+75.00%"),
      treasury_contribution_pct: numeric(0.25, "pct", "+25.00%"),
      spread_contribution_pct: numeric(-0.125, "pct", "-12.50%"),
      selection_contribution_pct: numeric(0.125, "pct", "+12.50%"),
      primary_driver: "income",
      interpretation: "legacy campisi",
      items: [],
    };

    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    expect(screen.getByTestId("campisi-driver-summary")).toHaveTextContent("75.0%");
    expect(screen.queryByText(/0\.8%/)).not.toBeInTheDocument();
    // 老口径占比消费后端 contribution_pct，不应出现前端派生标注。
    expect(screen.queryByTestId("campisi-share-derived-note")).not.toBeInTheDocument();
  });

  it("bridge path effect rows sum to total_return and surface decomposition_basis", () => {
    // 夹具语义：5+3+3+14=25 会静默丢 10；补齐 realized/manual/fx 后应等于 35。
    const data: CampisiFourEffectsPayload = {
      report_date: "2026-04-30",
      period_start: "2026-03-31",
      period_end: "2026-04-30",
      num_days: 30,
      decomposition_basis:
        "bridge_path: selection_effect is residual after carry, treasury, spread, realized_trading, manual_adjustment, and fx_translation",
      totals: {
        income_return: 5,
        treasury_effect: 3,
        spread_effect: 3,
        realized_trading: 4,
        manual_adjustment: 3,
        fx_translation: 3,
        selection_effect: 14,
        total_return: 35,
        market_value_start: 100,
      },
      by_asset_class: [
        {
          asset_class: "利率债",
          market_value_start: 100,
          income_return: 5,
          treasury_effect: 3,
          spread_effect: 3,
          realized_trading: 4,
          manual_adjustment: 3,
          fx_translation: 3,
          selection_effect: 14,
          total_return: 35,
        },
      ],
      by_bond: [],
    };

    const normalized = normalizeCampisiData(data);
    expect(normalized).not.toBeNull();
    const effects = buildEffectRows(normalized!);
    expect(effects.map((effect) => effect.key)).toEqual([
      "income",
      "treasury",
      "spread",
      "realized_trading",
      "manual_adjustment",
      "fx_translation",
      "selection",
    ]);
    expect(sumCampisiEffectAmounts(effects)).toBe(data.totals.total_return);

    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);
    expect(screen.getByTestId("campisi-decomposition-basis")).toHaveTextContent(
      "bridge_path: selection_effect is residual",
    );
    expect(screen.getAllByText("已实现交易").length).toBeGreaterThan(0);
    expect(screen.getAllByText("手工调整").length).toBeGreaterThan(0);
    expect(screen.getAllByText("汇兑").length).toBeGreaterThan(0);
  });

  it("model path keeps four effects only and still sums to total_return", () => {
    const normalized = normalizeCampisiData(mockCampisiFourEffectsModelPath);
    expect(normalized).not.toBeNull();
    expect(normalized!.has_bridge_details).toBe(false);
    const effects = buildEffectRows(normalized!);
    expect(effects.map((effect) => effect.key)).toEqual([
      "income",
      "treasury",
      "spread",
      "selection",
    ]);
    expect(sumCampisiEffectAmounts(effects)).toBe(
      mockCampisiFourEffectsModelPath.totals.total_return,
    );

    render(
      <CampisiAttributionPanel
        data={mockCampisiFourEffectsModelPath}
        state={{ kind: "ok" }}
        onRetry={() => {}}
      />,
    );
    expect(screen.queryByTestId("campisi-decomposition-basis")).not.toBeInTheDocument();
    expect(screen.queryByText("已实现交易")).not.toBeInTheDocument();
    expect(screen.queryByText("手工调整")).not.toBeInTheDocument();
    expect(screen.queryByText("汇兑")).not.toBeInTheDocument();
  });

  it("bridge mock payload components sum to total_return via panel effect rows", () => {
    const normalized = normalizeCampisiData(mockCampisiFourEffects);
    const effects = buildEffectRows(normalized!);
    expect(sumCampisiEffectAmounts(effects)).toBe(mockCampisiFourEffects.totals.total_return);
    expect(sumCampisiEnhancedDisplayAmounts(mockCampisiEnhanced.totals)).toBe(
      mockCampisiEnhanced.totals.total_return,
    );
  });

  it("keeps missing governed effects as null gaps and em-dash instead of zero", () => {
    const data: CampisiAttributionPayload = {
      report_date: "2026-04-30",
      period_start: "2026-03-31",
      period_end: "2026-04-30",
      num_days: 30,
      total_market_value: numeric(12_000_000_000, "yuan", "+120.00 亿"),
      total_return: numeric(800_000_000, "yuan", "+8.00 亿"),
      total_return_pct: numeric(0.066667, "pct", "+6.67%"),
      total_income: numeric(600_000_000, "yuan", "+6.00 亿"),
      total_treasury_effect: numeric(null, "yuan", "—"),
      total_spread_effect: numeric(-100_000_000, "yuan", "-1.00 亿"),
      total_selection_effect: numeric(100_000_000, "yuan", "+1.00 亿"),
      income_contribution_pct: numeric(0.75, "pct", "+75.00%"),
      treasury_contribution_pct: numeric(null, "pct", "—"),
      spread_contribution_pct: numeric(-0.125, "pct", "-12.50%"),
      selection_contribution_pct: numeric(0.125, "pct", "+12.50%"),
      primary_driver: "income",
      interpretation: "missing treasury effect",
      items: [
        {
          category: "利率债",
          income_return: numeric(300_000_000, "yuan", "+3.00 亿"),
          treasury_effect: numeric(null, "yuan", "—"),
          spread_effect: numeric(-50_000_000, "yuan", "-0.50 亿"),
          selection_effect: numeric(50_000_000, "yuan", "+0.50 亿"),
        },
      ],
    } as unknown as CampisiAttributionPayload;

    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    // 缺失效应卡片显示 —，不显示 "+0.00 亿" / "0.0%"。
    expect(screen.queryByText("+0.00 亿")).not.toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);

    // 条形图缺失效应传 null（国债曲线是第二根柱）。
    const option = JSON.parse(screen.getByTestId("campisi-echarts-stub").textContent ?? "{}");
    const barValues = option.series[0].data.map((item: { value: number | null }) => item.value);
    expect(barValues[1]).toBeNull();
    expect(barValues[0]).toBeCloseTo(6);
  });
});

/**
 * 2026-07-31：曲线事实停在 06-30，`treasury_effect` 恒为 0。以前页面把它当成一个
 * 数字发布，使用者读成"利率没动"。下面两条把"输入缺失"和"观测为零"分别锁住——
 * 只有后者才允许出现 0。
 */
describe("CampisiAttributionPanel effect availability", () => {
  function payloadWithTreasuryStatus(
    availability: CampisiFourEffectsPayload["effect_availability"],
  ): CampisiFourEffectsPayload {
    return {
      report_date: "2026-07-31",
      period_start: "2026-06-30",
      period_end: "2026-07-31",
      num_days: 31,
      totals: {
        income_return: 529_838_963.09,
        treasury_effect: 0,
        spread_effect: -100_000_000,
        selection_effect: 6_106_054.95,
        total_return: 435_945_018.04,
        market_value_start: 343_822_795_478.69,
      },
      by_asset_class: [
        {
          asset_class: "利率债",
          market_value_start: 343_822_795_478.69,
          income_return: 529_838_963.09,
          treasury_effect: 0,
          spread_effect: -100_000_000,
          selection_effect: 6_106_054.95,
          total_return: 435_945_018.04,
        },
      ],
      by_bond: [],
      effect_availability: availability,
    };
  }

  const OK_AVAILABILITY: CampisiFourEffectsPayload["effect_availability"] = {
    bonds: 1829,
    treasury_effect: {
      status: "ok",
      reason: null,
      unavailable_bonds: 0,
      unavailable_market_value_start: 0,
    },
    spread_effect: {
      status: "ok",
      reason: null,
      unavailable_bonds: 0,
      unavailable_market_value_start: 0,
    },
    accrued_interest: {
      status: "ok",
      reason: null,
      unavailable_bonds: 0,
      unavailable_market_value_start: 0,
      basis: "dirty_price",
    },
  };

  it("renders an unavailable treasury effect as text with its cause, never as 0", () => {
    const data = payloadWithTreasuryStatus({
      ...OK_AVAILABILITY!,
      treasury_effect: {
        status: "unavailable",
        reason: "curve_absent",
        unavailable_bonds: 1829,
        unavailable_market_value_start: 343_822_795_478.69,
      },
    });

    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const amount = screen.getByTestId("campisi-effect-amount-treasury");
    expect(amount).toHaveTextContent("不可用");
    expect(amount).toHaveTextContent("该交易日没有曲线事实");
    expect(amount.textContent).not.toMatch(/0/);

    const notice = screen.getByTestId("campisi-effect-availability-treasury_effect");
    expect(notice).toHaveTextContent("国债曲线效应不可用");
    expect(notice).toHaveTextContent("影响 1829/1829 只债券");
    expect(notice).toHaveTextContent("不能读成“市场没有变动”");

    // "几乎没有影响"是对观测量的判断，不可用的效应不该被这样描述。
    expect(screen.getByTestId("campisi-driver-summary")).not.toHaveTextContent(
      "几乎没有影响：国债曲线",
    );

    // 条形图不画 0 值柱（国债曲线是第二根）。
    const option = JSON.parse(screen.getByTestId("campisi-echarts-stub").textContent ?? "{}");
    expect(option.series[0].data[1].value).toBeNull();
  });

  it("still shows a plain 0 when the curve existed and the effect really was zero", () => {
    render(
      <CampisiAttributionPanel
        data={payloadWithTreasuryStatus(OK_AVAILABILITY)}
        state={{ kind: "ok" }}
        onRetry={() => {}}
      />,
    );

    const amount = screen.getByTestId("campisi-effect-amount-treasury");
    expect(amount).toHaveTextContent("+0.00 亿");
    expect(amount).not.toHaveTextContent("不可用");
    expect(screen.queryByTestId("campisi-effect-availability")).not.toBeInTheDocument();
    expect(screen.getByTestId("campisi-driver-summary")).toHaveTextContent(
      "几乎没有影响：国债曲线",
    );
  });

  it("keeps a partially degraded effect as a number but discloses the understatement", () => {
    const data = payloadWithTreasuryStatus({
      ...OK_AVAILABILITY!,
      spread_effect: {
        status: "partial",
        reason: "credit_spread_input_missing",
        unavailable_bonds: 12,
        unavailable_market_value_start: 4_000_000_000,
      },
    });

    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    expect(screen.getByTestId("campisi-effect-amount-spread")).toHaveTextContent("-1.00 亿");
    expect(screen.getByTestId("campisi-effect-availability-spread_effect")).toHaveTextContent(
      "合计因此被低估",
    );
  });
});
