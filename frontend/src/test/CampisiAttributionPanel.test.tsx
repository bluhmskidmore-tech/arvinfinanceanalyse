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
    expect(summary).toHaveTextContent("不能直接等同主动选券能力");
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
    expect(screen.queryByTestId("campisi-included-maturity-unavailable")).not.toBeInTheDocument();
  });

  it("discloses backend totals for included holdings with unavailable maturity", () => {
    const data: CampisiFourEffectsPayload = {
      ...mockCampisiFourEffectsModelPath,
      by_bond: [],
      input_quality: {
        included_maturity_unavailable: {
          positions: 126,
          market_value_start_abs: 43_298_000_000,
          model_residual: 53_710_000,
        },
      },
    };
    const { rerender } = render(
      <CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />,
    );

    const notice = screen.getByTestId("campisi-included-maturity-unavailable");
    expect(notice).toHaveTextContent("已纳入且到期日不可用：126 项持仓");
    expect(notice).toHaveTextContent("期初绝对市值 432.98 亿");
    expect(notice).toHaveTextContent("模型剩余项 +0.54 亿");
    expect(notice).toHaveTextContent("国债曲线可用不代表逐券久期可用");
    expect(notice).toHaveTextContent("不代表主动选券能力");

    rerender(
      <CampisiAttributionPanel
        data={{
          ...data,
          input_quality: {
            included_maturity_unavailable: {
              positions: 0,
              market_value_start_abs: 0,
              model_residual: 0,
            },
          },
        }}
        state={{ kind: "ok" }}
        onRetry={() => {}}
      />,
    );
    expect(screen.queryByTestId("campisi-included-maturity-unavailable")).not.toBeInTheDocument();

    rerender(
      <CampisiAttributionPanel
        data={{ ...data, basis: "formal_report_pnl_bridge" }}
        state={{ kind: "ok" }}
        onRetry={() => {}}
      />,
    );
    expect(screen.queryByTestId("campisi-included-maturity-unavailable")).not.toBeInTheDocument();
  });

  it("shows tiny maturity amounts in yuan instead of rounded zero yi", () => {
    const data: CampisiFourEffectsPayload = {
      ...mockCampisiFourEffectsModelPath,
      input_quality: {
        included_maturity_unavailable: {
          positions: 1,
          market_value_start_abs: 10,
          model_residual: -10,
        },
      },
    };

    const { rerender } = render(
      <CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />,
    );

    const notice = screen.getByTestId("campisi-included-maturity-unavailable");
    expect(notice).toHaveTextContent("期初绝对市值 10 元");
    expect(notice).toHaveTextContent("模型剩余项 -10 元");
    expect(notice).not.toHaveTextContent("0.00 亿");
    expect(notice).not.toHaveTextContent("-0.00 亿");

    rerender(
      <CampisiAttributionPanel
        data={{
          ...data,
          input_quality: {
            included_maturity_unavailable: {
              positions: 1,
              market_value_start_abs: 0,
              model_residual: 0,
            },
          },
        }}
        state={{ kind: "ok" }}
        onRetry={() => {}}
      />,
    );
    expect(notice).toHaveTextContent("期初绝对市值 0.00 亿");
    expect(notice).toHaveTextContent("模型剩余项 0.00 亿");
  });

  it.each([
    [-23_000_000, "-0.23 亿"],
    [13_000_000, "+0.13 亿"],
  ] as const)("keeps the signed model residual for included UNKNOWN maturity rows", (modelResidual, formatted) => {
    const data: CampisiFourEffectsPayload = {
      ...mockCampisiFourEffectsModelPath,
      input_quality: {
        included_maturity_unavailable: {
          positions: 17,
          market_value_start_abs: 120_000_000,
          model_residual: modelResidual,
        },
      },
    };
    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const notice = screen.getByTestId("campisi-included-maturity-unavailable");
    expect(notice).toHaveTextContent("17 项持仓");
    expect(notice).toHaveTextContent(`带符号模型剩余项 ${formatted}`);
    expect(notice).toHaveTextContent("不代表主动选券能力");
  });

  it("calls model-backed returns model returns while keeping bridge PnL wording", () => {
    const modelData: CampisiFourEffectsPayload = {
      ...mockCampisiFourEffectsModelPath,
      input_quality: {
        market_curve_coverage: { treasury_effect: { start_curve_used: true, end_curve_used: true } },
      },
      formal_closure: {
        basis: "pnl.bridge.total_actual_pnl",
        report_date: "2026-03-31",
        status: "unavailable",
        campisi_total_return: mockCampisiFourEffectsModelPath.totals.total_return,
        formal_actual_pnl: null,
        residual_to_formal_pnl: null,
        residual_ratio: null,
        message: "formal closure unavailable",
      },
    };
    const { rerender } = render(
      <CampisiAttributionPanel data={modelData} state={{ kind: "ok" }} onRetry={() => {}} />,
    );
    expect(screen.getByTestId("campisi-driver-summary")).toHaveTextContent("本期模型回报");
    expect(screen.getByTestId("campisi-driver-summary")).not.toHaveTextContent("本期 Campisi PnL");
    expect(screen.getByTestId("campisi-driver-summary"))
      .toHaveTextContent("当前模型归因中，剩余项不能直接等同主动选券能力");
    expect(screen.getByTestId("campisi-driver-summary"))
      .not.toHaveTextContent("当前正式闭合口径");

    rerender(
      <CampisiAttributionPanel
        data={mockCampisiFourEffectsModelPath}
        state={{ kind: "ok" }}
        onRetry={() => {}}
      />,
    );
    expect(screen.getByTestId("campisi-driver-summary")).toHaveTextContent("本期模型回报");
    expect(screen.getByTestId("campisi-capability-boundary"))
      .toHaveTextContent("本入口展示持仓模型四效应和输入覆盖；正式损益核对以返回状态为准");
    expect(screen.getByTestId("campisi-capability-boundary"))
      .not.toHaveTextContent("本页提供正式 PnL 金额闭合核对");

    rerender(
      <CampisiAttributionPanel data={mockCampisiFourEffects} state={{ kind: "ok" }} onRetry={() => {}} />,
    );
    expect(screen.getByTestId("campisi-driver-summary")).toHaveTextContent("本期 Campisi PnL");
    expect(screen.getByTestId("campisi-driver-summary"))
      .toHaveTextContent("当前正式闭合口径");
    expect(screen.getByTestId("campisi-driver-summary"))
      .toHaveTextContent("不能直接等同交易员主动选券能力");
    expect(screen.getByTestId("campisi-capability-boundary"))
      .toHaveTextContent("本页提供正式 PnL 金额闭合核对");
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

  it("keeps a partially degraded effect as a number without inferring a bias direction", () => {
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
      "贡献信息不完整",
    );
    expect(screen.getByTestId("campisi-effect-availability-spread_effect")).not.toHaveTextContent("被低估");
  });

  it("counts accrued-interest gaps only among 1595 retained holdings", () => {
    const data = payloadWithTreasuryStatus({
      ...OK_AVAILABILITY!,
      bonds: 1854,
      accrued_interest: {
        status: "partial", reason: "accrued_interest_missing",
        unavailable_bonds: 163, unavailable_market_value_start: 0,
      },
      position_change: {
        status: "partial", reason: "principal_change_without_cashflows",
        unavailable_bonds: 259, covered_bonds: 1595,
        unavailable_market_value_start: 10_000_000,
      },
    });
    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const accrued = screen.getByTestId("campisi-effect-availability-accrued_interest");
    expect(accrued).toHaveTextContent("影响 163/1595 只债券");
    expect(accrued).toHaveTextContent("应计利息缺口仅统计可归因持仓");
    expect(accrued).toHaveTextContent("不能由缺口数量推断合计回报偏差方向");
    expect(accrued).not.toHaveTextContent("合计因此被低估");
    expect(screen.getByTestId("campisi-effect-availability-position_change"))
      .toHaveTextContent("影响 259/1854 只债券");
  });

  it("does not call an unavailable accrued-interest basis a hidden effect amount", () => {
    const data = payloadWithTreasuryStatus({
      ...OK_AVAILABILITY!,
      accrued_interest: {
        status: "unavailable", reason: "accrued_interest_missing",
        unavailable_bonds: 1829, unavailable_market_value_start: 0,
      },
    });
    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const accrued = screen.getByTestId("campisi-effect-availability-accrued_interest");
    expect(accrued).toHaveTextContent("应计利息口径不可用");
    expect(accrued).toHaveTextContent("应计利息缺口仅统计可归因持仓");
    expect(accrued).not.toHaveTextContent("该效应本期没有可比输入");
    expect(accrued).not.toHaveTextContent("页面不以数字形式发布");
    expect(screen.getByTestId("campisi-effect-amount-income")).not.toHaveTextContent("不可用");
  });

  it("uses the same retained denominator when no holdings are excluded", () => {
    const data = payloadWithTreasuryStatus({
      ...OK_AVAILABILITY!,
      accrued_interest: {
        status: "partial", reason: "accrued_interest_missing",
        unavailable_bonds: 12, unavailable_market_value_start: 0,
      },
      position_change: {
        status: "ok", reason: null, unavailable_bonds: 0, covered_bonds: 1829,
        unavailable_market_value_start: 0,
      },
    });
    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const accrued = screen.getByTestId("campisi-effect-availability-accrued_interest");
    expect(accrued).toHaveTextContent("影响 12/1829 只债券");
    expect(accrued).toHaveTextContent("应计利息缺口仅统计可归因持仓");
    expect(accrued).not.toHaveTextContent("可能包含本金变化维度已排除的持仓");
    expect(screen.queryByTestId("campisi-effect-availability-position_change")).not.toBeInTheDocument();
  });

  it("labels an excluded population as a covered subtotal and uses retained effect denominators", () => {
    const data = payloadWithTreasuryStatus({
      ...OK_AVAILABILITY!,
      bonds: 2,
      position_change: {
        status: "partial", reason: "principal_change_without_cashflows",
        unavailable_bonds: 1, covered_bonds: 1,
        unavailable_market_value_start: 2_000_000,
        unavailable_market_value_end: 2_100_000,
      },
      spread_effect: {
        status: "partial", reason: "credit_spread_input_missing",
        unavailable_bonds: 1, unavailable_market_value_start: 1_000_000,
      },
      treasury_effect: {
        status: "partial", reason: "curve_unusable",
        unavailable_bonds: 1, unavailable_market_value_start: 1_000_000,
      },
      accrued_interest: {
        status: "partial", reason: "accrued_interest_missing",
        unavailable_bonds: 1, unavailable_market_value_start: 1_000_000,
      },
    });
    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    expect(screen.getByText("Campisi 四效应归因（可归因持仓小计）")).toBeInTheDocument();
    expect(screen.getByTestId("campisi-effect-availability-position_change"))
      .toHaveTextContent("影响 1/2 只债券");
    expect(screen.getByTestId("campisi-effect-availability-spread_effect"))
      .toHaveTextContent("影响 1/1 只债券");
    expect(screen.getByTestId("campisi-effect-availability-treasury_effect"))
      .toHaveTextContent("影响 1/1 只债券");
    expect(screen.getByTestId("campisi-effect-availability-accrued_interest"))
      .toHaveTextContent("影响 1/1 只债券");
  });

  it("does not publish placeholder zero effects when every model position is excluded", () => {
    const data = payloadWithTreasuryStatus({
      ...OK_AVAILABILITY!,
      bonds: 1,
      position_change: {
        status: "unavailable", reason: "principal_change_without_cashflows",
        unavailable_bonds: 1, covered_bonds: 0,
        unavailable_market_value_start: 2_000_000,
        unavailable_market_value_end: 0,
      },
    });
    data.totals = {
      ...data.totals,
      income_return: 0, treasury_effect: 0, spread_effect: 0,
      selection_effect: 0, total_return: 0, market_value_start: 0,
    };
    data.by_asset_class = [];
    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    expect(screen.getByText("Campisi 四效应归因（可归因持仓小计）")).toBeInTheDocument();
    expect(screen.getByTestId("campisi-effect-availability-position_change"))
      .toHaveTextContent("零金额只是占位");
    expect(screen.queryByTestId("campisi-driver-summary")).not.toBeInTheDocument();
    expect(screen.getByTestId("campisi-effect-amount-income")).toHaveTextContent("不可用");
    expect(screen.getByTestId("campisi-effect-amount-selection")).toHaveTextContent("不可用");
    const option = JSON.parse(screen.getByTestId("campisi-echarts-stub").textContent ?? "{}");
    expect(option.series[0].data.every((item: { value: number | null }) => item.value === null)).toBe(true);
  });
});

describe("CampisiAttributionPanel formal bridge coverage", () => {
  const data: CampisiFourEffectsPayload = {
    report_date: "2026-08-31",
    period_start: "2026-08-01",
    period_end: "2026-08-31",
    num_days: 31,
    basis: "formal_report_pnl_bridge",
    totals: {
      income_return: 5_000_000,
      treasury_effect: 0,
      spread_effect: 0,
      selection_effect: 2_000_000,
      total_return: 7_000_000,
      market_value_start: 100_000_000,
    },
    by_asset_class: [],
    by_bond: [],
    formal_closure: {
      basis: "pnl.bridge.total_actual_pnl",
      report_date: "2026-08-31",
      status: "closed",
      campisi_total_return: 7_000_000,
      formal_actual_pnl: 7_000_000,
      residual_to_formal_pnl: 0,
      residual_ratio: 0,
      bridge_quality_flag: "error",
      bridge_vendor_status: "ok",
      bridge_fallback_mode: "none",
      message: "Synthetic closed bridge with a source quality error.",
    },
    input_quality: {
      formal_bridge_coverage: {
        source: "pnl.bridge.rows",
        basis: "formal_report_pnl_bridge",
        status: "partial",
        bridge_rows: 8,
        attributed_rows: 7,
      },
    },
    effect_availability: {
      bonds: 17,
      treasury_effect: {
        status: "unavailable", reason: "bridge_curve_unavailable",
        unavailable_bonds: 3, unavailable_market_value_start: 0,
      },
      spread_effect: {
        status: "ok", reason: null,
        unavailable_bonds: 0, unavailable_market_value_start: 0,
      },
      accrued_interest: {
        status: "ok", reason: null,
        unavailable_bonds: 0, unavailable_market_value_start: 0,
      },
      position_change: {
        status: "ok", reason: null,
        unavailable_bonds: 0, covered_bonds: 17, unavailable_market_value_start: 0,
      },
      roll_down_availability: {
        status: "partial", unavailable_rows: 2, applicable_rows: 5,
        reasons: ["roll_window_missing"],
      },
      treasury_curve_availability: {
        status: "unavailable", unavailable_rows: 3, applicable_rows: 3,
        reasons: ["same_source_curve"],
      },
      credit_spread_availability: {
        status: "not_applicable", unavailable_rows: 0, applicable_rows: 0,
        reasons: ["not_credit_book"],
      },
    },
  };

  it("discloses accounting-row inclusion and each effect's own denominator even when amounts close", () => {
    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const coverage = screen.getByTestId("campisi-formal-bridge-coverage");
    expect(coverage).toHaveTextContent("已纳入 7/8 个会计记录行");
    expect(coverage).toHaveTextContent("部分纳入");
    expect(coverage).toHaveTextContent("不代表市场效应输入完整或本金变化检查通过");
    expect(screen.getByTestId("campisi-bridge-effect-availability-roll_down"))
      .toHaveTextContent("2/5 个适用行");
    expect(screen.getByTestId("campisi-bridge-effect-availability-roll_down"))
      .not.toHaveTextContent("被低估");
    expect(screen.getByTestId("campisi-bridge-effect-availability-treasury_curve"))
      .toHaveTextContent("3/3 个适用行");
    expect(screen.getByTestId("campisi-bridge-effect-availability-credit_spread"))
      .toHaveTextContent("本期无适用行");
    expect(screen.getByTestId("campisi-effect-availability")).not.toHaveTextContent("只债券");
    expect(screen.queryByTestId("campisi-effect-availability-position_change")).not.toBeInTheDocument();
    expect(screen.getByTestId("campisi-bridge-quality-warning"))
      .toHaveTextContent("金额闭合不代表数据质量通过");
    expect(screen.queryByTestId("campisi-formal-closure-warning")).not.toBeInTheDocument();
    expect(screen.getByTestId("campisi-effect-amount-treasury")).toHaveTextContent("不可用");
    expect(screen.getByTestId("campisi-effect-amount-income")).toHaveTextContent("+0.05 亿");
  });

  it("keeps successful effect coverage separate from accounting-row inclusion", () => {
    render(<CampisiAttributionPanel data={{
      ...data,
      input_quality: {
        formal_bridge_coverage: {
          source: "pnl.bridge.rows", basis: "formal_report_pnl_bridge",
          status: "ok", bridge_rows: 8, attributed_rows: 8,
        },
      },
      effect_availability: {
        ...data.effect_availability!,
        roll_down_availability: { status: "ok", applicable_rows: 5, unavailable_rows: 0, reasons: [] },
        treasury_curve_availability: { status: "ok", applicable_rows: 3, unavailable_rows: 0, reasons: [] },
        credit_spread_availability: { status: "ok", applicable_rows: 2, unavailable_rows: 0, reasons: [] },
      },
    }} state={{ kind: "ok" }} onRetry={() => {}} />);

    expect(screen.getByTestId("campisi-formal-bridge-coverage"))
      .toHaveTextContent("已全部纳入：已纳入 8/8 个会计记录行");
    expect(screen.getByTestId("campisi-bridge-effect-availability-roll_down"))
      .toHaveTextContent("0/5 个适用行不可用");
    expect(screen.getByTestId("campisi-bridge-effect-availability-treasury_curve"))
      .toHaveTextContent("0/3 个适用行不可用");
    expect(screen.getByTestId("campisi-bridge-effect-availability-credit_spread"))
      .toHaveTextContent("0/2 个适用行不可用");
  });

  const missingInclusionEvidence: Array<
    NonNullable<CampisiFourEffectsPayload["input_quality"]>["formal_bridge_coverage"]
  > = [
    undefined,
    null,
    { source: "pnl.bridge.rows", basis: "formal_report_pnl_bridge", status: "ok", bridge_rows: null, attributed_rows: 7 },
    { source: "pnl.bridge.rows", basis: "formal_report_pnl_bridge", status: "ok", bridge_rows: 8, attributed_rows: 7 },
  ];

  it.each(missingInclusionEvidence)("does not infer full inclusion from missing or inconsistent evidence (%j)", (coverage) => {
    render(<CampisiAttributionPanel data={{
      ...data, input_quality: { formal_bridge_coverage: coverage },
    }} state={{ kind: "ok" }} onRetry={() => {}} />);

    const notice = screen.getByTestId("campisi-formal-bridge-coverage");
    expect(notice).toHaveTextContent("纳入覆盖未确认");
    expect(notice).toHaveTextContent("不能判断全覆盖");
    expect(notice).not.toHaveTextContent("已全部纳入");
    expect(notice).not.toHaveTextContent("17");
  });

  it("does not borrow another effect's denominator when a formal effect block is absent", () => {
    render(<CampisiAttributionPanel data={{
      ...data,
      effect_availability: { ...data.effect_availability!, credit_spread_availability: undefined },
    }} state={{ kind: "ok" }} onRetry={() => {}} />);

    const notice = screen.getByTestId("campisi-bridge-effect-availability-credit_spread");
    expect(notice).toHaveTextContent("信用利差效应覆盖未确认");
    expect(notice).toHaveTextContent("不能判断全覆盖");
    expect(notice).not.toHaveTextContent("本期无适用行");
    expect(screen.getByTestId("campisi-bridge-effect-availability-roll_down"))
      .toHaveTextContent("2/5 个适用行");
  });

  it("discloses unavailable accounting-row inclusion independently of closed amounts", () => {
    render(<CampisiAttributionPanel data={{
      ...data,
      input_quality: {
        formal_bridge_coverage: {
          source: "pnl.bridge.rows", basis: "formal_report_pnl_bridge",
          status: "unavailable", bridge_rows: 8, attributed_rows: 0,
        },
      },
    }} state={{ kind: "ok" }} onRetry={() => {}} />);

    expect(screen.getByTestId("campisi-formal-bridge-coverage"))
      .toHaveTextContent("纳入覆盖不可用：已纳入 0/8 个会计记录行");
    expect(screen.getByTestId("campisi-bridge-quality-warning"))
      .toHaveTextContent("数据质量错误");
    expect(screen.queryByTestId("campisi-formal-closure-warning")).not.toBeInTheDocument();
  });

  it("keeps a null bridge denominator unavailable without replacing it with model counts", () => {
    render(<CampisiAttributionPanel data={{
      ...data,
      input_quality: {
        formal_bridge_coverage: {
          source: "pnl.bridge.rows", basis: "formal_report_pnl_bridge",
          status: "unavailable", bridge_rows: null, attributed_rows: 7,
        },
      },
    }} state={{ kind: "ok" }} onRetry={() => {}} />);

    const notice = screen.getByTestId("campisi-formal-bridge-coverage");
    expect(notice).toHaveTextContent("纳入覆盖不可用");
    expect(notice).toHaveTextContent("已纳入 7 个会计记录行");
    expect(notice).toHaveTextContent("总行数未提供，不能判断全覆盖");
    expect(notice).not.toHaveTextContent("7/0");
    expect(notice).not.toHaveTextContent("7/17");
  });

  it("preserves model holding coverage without treating formal counts as principal evidence", () => {
    render(<CampisiAttributionPanel data={{
      ...data,
      basis: undefined,
      effect_availability: {
        ...data.effect_availability!,
        position_change: {
          status: "partial", reason: "principal_change_without_cashflows",
          unavailable_bonds: 2, covered_bonds: 15, unavailable_market_value_start: 2_000_000,
        },
      },
    }} state={{ kind: "ok" }} onRetry={() => {}} />);

    expect(screen.queryByTestId("campisi-formal-bridge-coverage")).not.toBeInTheDocument();
    expect(screen.queryByTestId("campisi-bridge-effect-availability-roll_down")).not.toBeInTheDocument();
    expect(screen.getByText("Campisi 四效应归因（可归因持仓小计）")).toBeInTheDocument();
    expect(screen.getByTestId("campisi-effect-availability-position_change"))
      .toHaveTextContent("影响 2/17 只债券");
    expect(screen.getByTestId("campisi-effect-availability-treasury_effect"))
      .toHaveTextContent("影响 3/15 只债券");
  });
});
