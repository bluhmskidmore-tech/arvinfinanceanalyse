import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MacroBondLinkagePayload } from "../../../api/contracts";
import { MarketDataLinkageBusinessDetail } from "./MarketDataLinkageBusinessDetail";

function buildPayload(): MacroBondLinkagePayload {
  return {
    report_date: "2026-07-28",
    computed_at: "2026-07-29T08:15:00Z",
    environment_score: {
      report_date: "2026-07-28",
      rate_direction: "falling",
      rate_direction_score: -0.42,
      liquidity_score: 0.31,
      growth_score: -0.17,
      inflation_score: 0.08,
      composite_score: -0.19,
      composite_formula_version: "macro_env_v3",
      signal_description: "Liquidity is offsetting growth softness.",
      composite_contributions: [
        { component: "rate_direction", raw_score: -0.42, weight: 0.4, signed_contribution: -0.168 },
        { component: "liquidity", raw_score: 0.31, weight: -0.3, signed_contribution: -0.093 },
      ],
      contributing_factors: [
        {
          category: "rate",
          series_id: "CGB10Y",
          series_name: "China 10Y",
          latest_value: 2.11,
          delta: -0.14,
          tags: ["rates", "duration"],
        },
        {
          category: "liquidity",
          note: "Funding eased",
          evidence: ["DR007 lower", "OMO net inject"],
        },
      ],
      warnings: ["Environment model is analytical only."],
    },
    portfolio_impact: {
      estimated_rate_change_bps: "-12.6",
      estimated_spread_widening_bps: "-6.2",
      estimated_rate_pnl_impact: "1820000.50",
      estimated_spread_pnl_impact: "410000.25",
      total_estimated_impact: "2230000.75",
      impact_ratio_to_market_value: "0.0041",
    },
    top_correlations: [
      {
        series_id: "HIDDEN-OBS-SPAN",
        series_name: "Do not show in business detail",
        target_family: "credit_spread",
        target_tenor: "5Y",
        correlation_3m: -0.41,
        correlation_6m: -0.58,
        correlation_1y: -0.63,
        lead_lag_days: -4,
        direction: "negative",
        effective_observation_span_days: 180,
      },
    ],
    method_variants: {
      conservative: {
        method_meta: {
          variant: "conservative",
          description: "Tighter lag discipline.",
          warnings: ["Conservative view trims timing sensitivity."],
        },
        top_correlations: [],
      },
      market_timing: {
        method_meta: {
          variant: "market_timing",
          description: "Highlights timing windows.",
          warnings: ["Market timing view is noisier."],
        },
        top_correlations: [],
      },
    },
    spread_tenor_correlations: [],
    research_views: [
      {
        key: "duration_bias",
        status: "ready",
        stance: "bullish duration",
        confidence: "high",
        summary: "Rate backdrop supports adding duration.",
        affected_targets: ["treasury_10Y", "cdb_10Y"],
        evidence: ["Composite score negative", "Liquidity supportive"],
      },
    ],
    transmission_axes: [
      {
        axis_key: "policy_to_rates",
        status: "ready",
        stance: "easing",
        summary: "Policy easing flows into the rates curve first.",
        impacted_views: ["duration_bias"],
        required_series_ids: ["DR007", "OMO_7D"],
        warnings: ["Watch offshore spillovers."],
      },
    ],
    warnings: ["Portfolio impacts are display-only analytical estimates."],
  };
}

describe("MarketDataLinkageBusinessDetail", () => {
  it("renders all business detail categories without correlation-table spillover", () => {
    render(<MarketDataLinkageBusinessDetail payload={buildPayload()} />);

    expect(screen.getByTestId("market-data-detail-linkage-business")).toBeInTheDocument();

    const environment = screen.getByTestId("market-data-detail-linkage-environment");
    expect(within(environment).getByText("2026-07-28")).toBeInTheDocument();
    expect(within(environment).getByText("falling")).toBeInTheDocument();
    expect(within(environment).getAllByText("-0.42").length).toBeGreaterThan(0);
    expect(within(environment).getAllByText("0.31").length).toBeGreaterThan(0);
    expect(within(environment).getByText("-0.17")).toBeInTheDocument();
    expect(within(environment).getByText("0.08")).toBeInTheDocument();
    expect(within(environment).getByText("-0.19")).toBeInTheDocument();
    expect(within(environment).getByText("macro_env_v3")).toBeInTheDocument();
    expect(within(environment).getByText("Liquidity is offsetting growth softness.")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-detail-linkage-composite-contributions")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-detail-linkage-contributing-factors")).toBeInTheDocument();
    expect(within(environment).getByText("Environment model is analytical only.")).toBeInTheDocument();

    const portfolioImpact = screen.getByTestId("market-data-detail-linkage-portfolio-impact");
    expect(within(portfolioImpact).getByText("-12.6 bps")).toBeInTheDocument();
    expect(within(portfolioImpact).getByText("-6.2 bps")).toBeInTheDocument();
    expect(within(portfolioImpact).getByText("1820000.50")).toBeInTheDocument();
    expect(within(portfolioImpact).getByText("410000.25")).toBeInTheDocument();
    expect(within(portfolioImpact).getByText("2230000.75")).toBeInTheDocument();
    expect(within(portfolioImpact).getByText("0.0041")).toBeInTheDocument();

    const methodVariants = screen.getByTestId("market-data-detail-linkage-method-variants");
    expect(within(methodVariants).getByText("Tighter lag discipline.")).toBeInTheDocument();
    expect(within(methodVariants).getByText("Conservative view trims timing sensitivity.")).toBeInTheDocument();
    expect(within(methodVariants).getByText("Highlights timing windows.")).toBeInTheDocument();
    expect(within(methodVariants).getByText("Market timing view is noisier.")).toBeInTheDocument();

    const researchViews = screen.getByTestId("market-data-detail-linkage-research-views");
    expect(within(researchViews).getByText("duration_bias")).toBeInTheDocument();
    expect(within(researchViews).getByText("bullish duration")).toBeInTheDocument();
    expect(within(researchViews).getByText("treasury_10Y, cdb_10Y")).toBeInTheDocument();
    expect(within(researchViews).getByText("Composite score negative, Liquidity supportive")).toBeInTheDocument();

    const transmissionAxes = screen.getByTestId("market-data-detail-linkage-transmission-axes");
    expect(within(transmissionAxes).getByText("policy_to_rates")).toBeInTheDocument();
    expect(within(transmissionAxes).getByText("Policy easing flows into the rates curve first.")).toBeInTheDocument();
    expect(within(transmissionAxes).getByText("duration_bias")).toBeInTheDocument();
    expect(within(transmissionAxes).getByText("DR007, OMO_7D")).toBeInTheDocument();
    expect(within(transmissionAxes).getByText("Watch offshore spillovers.")).toBeInTheDocument();

    expect(screen.getByTestId("market-data-detail-linkage-warnings")).toHaveTextContent(
      "Portfolio impacts are display-only analytical estimates.",
    );
    expect(screen.queryByText("Do not show in business detail")).not.toBeInTheDocument();
  });

  it("renders em dashes for missing optional values", () => {
    const payload = buildPayload();
    payload.environment_score = {
      signal_description: "",
      contributing_factors: [],
      warnings: [],
    };
    payload.portfolio_impact = {};
    payload.method_variants = undefined;
    payload.research_views = [];
    payload.transmission_axes = [];
    payload.warnings = [];

    render(<MarketDataLinkageBusinessDetail payload={payload} />);

    const environment = screen.getByTestId("market-data-detail-linkage-environment");
    expect(within(environment).getAllByText("—").length).toBeGreaterThan(0);

    const methodVariants = screen.getByTestId("market-data-detail-linkage-method-variants");
    expect(within(methodVariants).getAllByText("—").length).toBeGreaterThan(0);

    expect(screen.getByTestId("market-data-detail-linkage-research-views")).toHaveTextContent("—");
    expect(screen.getByTestId("market-data-detail-linkage-transmission-axes")).toHaveTextContent("—");
    expect(screen.getByTestId("market-data-detail-linkage-warnings")).toHaveTextContent("—");
  });
});
