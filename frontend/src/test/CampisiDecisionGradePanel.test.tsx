import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { CampisiDecisionGradePayload } from "../api/contracts";
import { CampisiDecisionGradePanel } from "../features/pnl-attribution/components/CampisiDecisionGradePanel";

const decisionGradePayload: CampisiDecisionGradePayload = {
  basis: "campisi_decision_grade_v1",
  report_date: "2026-01-31",
  period_start: "2026-01-01",
  period_end: "2026-01-31",
  num_days: 30,
  summary: {
    formal_actual_pnl: 107,
    explained_pnl: 107,
    residual_noise: 0,
    residual_ratio: 0,
    valuation_change_516: 70,
    fvoci_valuation_change_516: 50,
    fvtpl_valuation_change_516: 20,
    main_driver: "selection_proxy",
    quality_flag: "ok",
    bond_scope_row_count: 2,
    out_of_scope_pnl_row_count: 0,
  },
  formal_pnl_view: {
    total_actual_pnl: 107,
    explained_pnl: 107,
    residual_noise: 0,
    components: {
      carry: 17,
      rate_level_effect: -20,
      curve_shape_effect: 0,
      credit_spread_effect: 0,
      convexity_effect: 5,
      realized_trading: 5,
      manual_adjustment: 2,
      selection_proxy: 98,
      residual_noise: 0,
    },
    closure: {
      status: "closed",
      difference: 0,
      basis: "fact_formal_pnl_fi.total_pnl",
    },
  },
  valuation_oci_view: {
    total_valuation_change_516: 70,
    fvoci_valuation_change_516: 50,
    fvtpl_valuation_change_516: 20,
    rows_by_accounting_basis: [
      {
        accounting_basis: "FVOCI",
        formal_pnl: 7,
        valuation_or_oci_516: 50,
        interpretation: "516 不进入正式 PnL，但进入估值/OCI 解释视图。",
      },
      {
        accounting_basis: "FVTPL",
        formal_pnl: 100,
        valuation_or_oci_516: 20,
        interpretation: "516 进入正式 PnL，也进入估值解释视图。",
      },
    ],
    reinvestment: {
      implemented: false,
      message: "数据源不足：缺少稳定短端再投资数据，v1 不伪造为 0 贡献。",
    },
  },
  effects: [
    {
      key: "carry",
      label: "票息/Carry",
      amount: 17,
      ability_treatment: "自然持有收益，不直接算主动能力",
    },
    {
      key: "selection_proxy",
      label: "剩余/选券代理",
      amount: 98,
      ability_treatment: "组合/成本中心主动管理代理，不是交易员能力",
    },
    {
      key: "residual_noise",
      label: "残差/噪音",
      amount: 0,
      ability_treatment: "缺曲线、估值噪音或数据质量问题，不算能力",
    },
  ],
  accounting_matrix: {},
  ability_matrix: [
    {
      portfolio_name: "FIOA",
      cost_center: "5010",
      carry: 17,
      market_beta: -15,
      strategy_proxy: 0,
      credit_proxy: 0,
      selection_proxy: 98,
      residual_noise: 0,
      total_actual_pnl: 107,
      confidence: "medium",
      notes: "组合/成本中心代理，不是实名交易员评价；票息和残差不算主动能力。",
    },
  ],
  risk_tensor_check: {
    available: true,
    portfolio_dv01: 2,
    component_dv01: 2,
    dv01_difference: 0,
    portfolio_cs01: 0,
    component_cs01: 0,
    cs01_difference: 0,
    quality_flag: "ok",
    total_market_value: 1700,
    bond_count: 2,
  },
  residual_diagnostics: {
    missing_curve_count: 0,
    missing_spread_count: 0,
    duplicate_position_keys: 0,
    aggregated_position_groups: 2,
    unmatched_pnl_rows: 0,
    stale_curve_fallback_count: 0,
    warnings: [],
  },
  warnings: [],
  method_notes: [
    "carry = interest_income_514。",
    "FVOCI 的 516 不进入正式 PnL，但进入估值/OCI 解释视图。",
    "selection_proxy 是组合/成本中心代理指标，不是实名交易员能力。",
    "residual_noise 专门承接缺曲线、重复 key、估值噪音和数据质量问题。",
  ],
};

describe("CampisiDecisionGradePanel", () => {
  it("renders formal PnL, valuation OCI, and ability boundary separately", () => {
    render(
      <CampisiDecisionGradePanel
        data={decisionGradePayload}
        state={{ kind: "ok" }}
        onRetry={() => {}}
      />,
    );

    expect(screen.getByTestId("campisi-decision-headline")).toHaveTextContent("主要来自");
    expect(screen.getByTestId("campisi-decision-formal-view")).toHaveTextContent("正式 PnL 视图");
    expect(screen.getByTestId("campisi-decision-valuation-view")).toHaveTextContent("估值 / OCI 视图");
    expect(screen.getByText("票息不等于主动能力")).toBeInTheDocument();
    expect(screen.getByText("残差不算能力")).toBeInTheDocument();
    expect(screen.getByText("剩余/选券只作为代理指标")).toBeInTheDocument();
    expect(screen.queryByText("交易员能力")).not.toBeInTheDocument();
  });
});
