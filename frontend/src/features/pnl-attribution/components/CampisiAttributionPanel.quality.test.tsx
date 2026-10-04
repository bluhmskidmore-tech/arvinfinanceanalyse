import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CampisiEffectAvailabilityReason, CampisiFormalClosure, CampisiFourEffectsPayload } from "../../../api/contracts";
import { mockCampisiFourEffects, mockCampisiFourEffectsModelPath } from "../../../mocks/campisiMocks";
import { CampisiAttributionPanel } from "./CampisiAttributionPanel";
import { campisiReasonLabel } from "./campisiAttributionPanelSupport";

vi.mock("../../../lib/echarts", () => ({
  default: () => <div data-testid="campisi-quality-chart" />,
}));

function payload(closure: Partial<CampisiFormalClosure> = {}): CampisiFourEffectsPayload {
  const total = mockCampisiFourEffects.totals.total_return;
  return {
    ...mockCampisiFourEffects,
    formal_closure: {
      basis: "pnl.bridge.total_actual_pnl",
      report_date: "2026-08-31",
      status: "closed",
      campisi_total_return: total,
      formal_actual_pnl: total,
      residual_to_formal_pnl: 0,
      residual_ratio: 0,
      bridge_quality_flag: "ok",
      bridge_vendor_status: "ok",
      bridge_fallback_mode: "none",
      message: "Campisi total return closes to formal PnL.",
      ...closure,
    },
  };
}

function show(data: CampisiFourEffectsPayload) {
  render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);
}

describe("Campisi source quality is independent of amount closure", () => {
  it("labels the actual shared-positive-tenor gap and safely handles a future reason", () => {
    expect(campisiReasonLabel("insufficient_shared_positive_tenors"))
      .toBe("两端共同的有效正收益率期限不足");
    expect(campisiReasonLabel("future_reason" as CampisiEffectAvailabilityReason))
      .toBe("未识别的缺失成因");
  });
  it("shows a quality error even when amounts close and vendor/fallback are healthy", () => {
    show(payload({ bridge_quality_flag: "error" }));
    expect(screen.getByTestId("campisi-bridge-quality-warning")).toHaveTextContent("数据质量错误");
    expect(screen.getByTestId("campisi-bridge-quality-warning")).toHaveTextContent("金额闭合不代表数据质量通过");
    expect(screen.queryByTestId("campisi-formal-closure-warning")).not.toBeInTheDocument();
    expect(screen.getByTestId("campisi-effect-amount-income")).toHaveTextContent("+0.01 亿");
  });

  it("discloses stale data and the actual fallback date separately from closure", () => {
    show(payload({ bridge_quality_flag: "error", bridge_vendor_status: "vendor_stale",
      bridge_fallback_mode: "latest_snapshot", bridge_fallback_date: "2026-08-28" }));
    const warning = screen.getByTestId("campisi-bridge-quality-warning");
    expect(warning).toHaveTextContent("上游行情数据已陈旧");
    expect(warning).toHaveTextContent("来源日期为 2026-08-28");
    expect(screen.queryByTestId("campisi-formal-closure-warning")).not.toBeInTheDocument();
  });

  it("does not manufacture a fallback date from the closure report date", () => {
    show(payload({ bridge_fallback_mode: "latest_snapshot", bridge_fallback_date: null }));
    const warning = screen.getByTestId("campisi-bridge-quality-warning");
    expect(warning).toHaveTextContent("来源日期未提供");
    expect(warning).not.toHaveTextContent("2026-08-31");
  });

  it("does not show a quality warning for a healthy closed bridge", () => {
    show(payload());
    expect(screen.queryByTestId("campisi-bridge-quality-warning")).not.toBeInTheDocument();
    expect(screen.queryByTestId("campisi-formal-closure-warning")).not.toBeInTheDocument();
  });

  it("keeps the amount difference visible without claiming a source quality error", () => {
    show(payload({ status: "warning", residual_to_formal_pnl: 100_000_000 }));
    expect(screen.getByTestId("campisi-formal-closure-warning")).toHaveTextContent("+1.00 亿");
    expect(screen.queryByTestId("campisi-bridge-quality-warning")).not.toBeInTheDocument();
    expect(screen.getByTestId("campisi-capability-boundary")).not.toHaveTextContent("本页已做到正式 PnL 闭合");
  });

  it("treats a missing formal comparison as unavailable rather than an amount gap", () => {
    show(payload({ status: "unavailable", formal_actual_pnl: null,
      residual_to_formal_pnl: null, residual_ratio: null }));
    const warning = screen.getByTestId("campisi-formal-closure-warning");
    expect(warning).toHaveTextContent("正式损益核对不可用");
    expect(warning).not.toHaveTextContent("未闭合到正式 PnL");
    expect(warning).not.toHaveTextContent("需要残差");
    expect(warning).not.toHaveTextContent("0.00 亿");
  });

  it("keeps included maturity gaps visible when formal PnL comparison is unavailable", () => {
    const data: CampisiFourEffectsPayload = {
      ...mockCampisiFourEffectsModelPath,
      report_date: "2026-08-31",
      period_start: "2026-08-01",
      period_end: "2026-08-31",
      input_quality: {
        included_maturity_unavailable: {
          positions: 126,
          market_value_start_abs: 43_298_000_000,
          model_residual: 53_710_000,
        },
      },
      formal_closure: {
        basis: "pnl.bridge.total_actual_pnl",
        report_date: "2026-08-31",
        status: "unavailable",
        campisi_total_return: mockCampisiFourEffectsModelPath.totals.total_return,
        formal_actual_pnl: null,
        residual_to_formal_pnl: null,
        residual_ratio: null,
        message: "formal closure unavailable",
      },
    };

    show(data);

    const maturity = screen.getByTestId("campisi-included-maturity-unavailable");
    expect(maturity).toHaveTextContent("已纳入且到期日不可用：126 项持仓");
    expect(maturity).toHaveTextContent("计入“剩余/选券”的带符号模型剩余项 +0.54 亿");
    expect(maturity).toHaveTextContent("不代表主动选券能力");
    expect(screen.getByTestId("campisi-formal-closure-warning"))
      .toHaveTextContent("正式损益核对不可用");
    expect(screen.getByTestId("campisi-capability-boundary"))
      .not.toHaveTextContent("本页提供正式 PnL 金额闭合核对");
    expect(screen.getByTestId("campisi-driver-summary"))
      .not.toHaveTextContent("本期 Campisi PnL");
  });

  it("does not treat missing source metadata as a passed quality check", () => {
    show(payload({ bridge_quality_flag: null, bridge_vendor_status: null, bridge_fallback_mode: null }));
    expect(screen.getByTestId("campisi-bridge-quality-warning")).toHaveTextContent("来源状态未确认");
  });

  it("shows unavailable vendor data without inventing a quality error", () => {
    show(payload({ bridge_vendor_status: "vendor_unavailable" }));
    const warning = screen.getByTestId("campisi-bridge-quality-warning");
    expect(warning).toHaveTextContent("上游行情数据不可用");
    expect(warning).not.toHaveTextContent("数据质量错误");
  });
});
