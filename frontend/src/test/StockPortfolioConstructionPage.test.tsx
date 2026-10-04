import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import "../app/ThemedRouteBoundary";
import type {
  ApiEnvelope,
  StockPortfolioConstructionPayload,
} from "../api/contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import StockPortfolioConstructionPage from "../features/stock-analysis/pages/StockPortfolioConstructionPage";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

function buildPortfolioPayload(
  overrides?: Partial<StockPortfolioConstructionPayload>,
): StockPortfolioConstructionPayload {
  return {
    page_id: "GAP-STOCK-ANALYSIS-PORTFOLIO",
    route: "/stock-analysis/portfolio",
    portfolio_id: "SHADOW-STOCK-RESEARCH",
    requested_as_of_date: "2026-08-24",
    as_of_date: "2026-08-24",
    resolved_as_of_date: "2026-08-24",
    basis: "analytical",
    contract_status: "proposal_only",
    formal_use_allowed: false,
    trading_instruction_allowed: false,
    execution_approval_allowed: false,
    proposal_status: "blocked_source_gate",
    context: {
      requested_as_of_date: "2026-08-24",
      resolved_as_of_date: "2026-08-24",
      portfolio_id: "SHADOW-STOCK-RESEARCH",
      source_page_id: "GAP-STOCK-ANALYSIS-PAGE",
      source_route: "/stock-analysis",
      source_module: "main",
      main_module_status: "ready",
    },
    source_gate: {
      status: "blocked",
      ready: false,
      source: "replay_closure",
      closure_status: "insufficient",
      selection_status: "no_active_certified",
      data_availability: "unsupported",
      as_of_date: "2026-08-24",
      cohort_id: null,
      primary_blocker_code: "controlled_schema_unavailable",
      reason_codes: ["controlled_schema_unavailable"],
      versions: {},
      sources: {},
    },
    source_gate_status: "blocked",
    target: {
      status: "blocked_source_gate",
      blocked: true,
      candidate_count: 1,
      weight_basis: "stock_candidates.position_size_hint.items[].equal_weight",
      block_reason: "controlled_schema_unavailable",
      items: [
        {
          status: "reference_preview",
          stock_code: "300313.SZ",
          stock_name: "天山生物",
          sector_name: "农林牧渔",
          rank: 1,
          signal_kind: "stock_candidate",
          reference_weight: 0.25,
          target_weight: null,
          target_block_reason: "controlled_schema_unavailable",
        },
      ],
    },
    rebalance: {
      status: "blocked_missing_scoped_positions",
      blocked: true,
      current_positions: [],
      scoped_positions_available: false,
      legacy_position_snapshot_used: false,
      legacy_position_snapshot_status: "ignored_unscoped",
      reason: "No portfolio-scoped current-position contract is available.",
    },
    risk_snapshot: {
      data_status: "complete",
      status: "complete",
      basis: "read_only_shadow",
      measurement_basis: "reference_preview",
      observation_only: true,
      formal_use_allowed: false,
      gross_exposure_ratio: 0.25,
      cash_ratio: 0.75,
      closure_residual_ratio: 0,
      hhi_index: 10000,
      sector_exposures: [{ sector_name: "农林牧渔", exposure_ratio: 0.25 }],
      limit_gate: {
        status: "blocked_missing_approved_policy",
        approved_policy_present: false,
      },
      warnings: ["descriptive_only"],
      reason_codes: [],
    },
    legacy_position_snapshot: {
      used: false,
      status: "ignored_unscoped",
      reason:
        "Legacy livermore_position_snapshot is not scoped to this portfolio.",
    },
    versions: {
      source_version: "sv_test",
      workbench_rule_version: "rv_test",
      portfolio_construction_rule_version:
        "rv_stock_portfolio_construction_phase2a_v1",
      portfolio_version: "SHADOW-STOCK-RESEARCH",
      proposal_version: null,
      calculation_run_id: null,
      review_run_id: null,
    },
    warnings: [
      "Proposal-only projection; it does not create a trading instruction or approval.",
      "Source replay closure is not ready; reference rows remain visible but target weights are withheld.",
    ],
    issues: [
      {
        severity: "blocking",
        code: "source_gate_not_ready",
        message:
          "Replay closure is not ready; target projection is fail-closed.",
        source: "replay_closure",
        blocker: "controlled_schema_unavailable",
      },
    ],
    ...overrides,
  };
}

function buildPortfolioClient(
  payload: StockPortfolioConstructionPayload,
): ApiClient {
  return {
    ...createApiClient({ mode: "mock" }),
    getStockAnalysisPortfolioConstruction: async (): Promise<
      ApiEnvelope<StockPortfolioConstructionPayload>
    > =>
      buildMockApiEnvelope(
        "market_data.stock_analysis.portfolio_construction",
        payload,
        {
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
          source_version: "sv_test",
          vendor_version: "vv_test",
          rule_version: "rv_stock_portfolio_construction_phase2a_v1",
        },
      ),
  };
}

function renderPortfolioPage(route: string, client: ApiClient) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[route]}>
        <QueryClientProvider client={queryClient}>
          <ApiClientProvider client={client}>{children}</ApiClientProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }
  return render(<StockPortfolioConstructionPage />, { wrapper: Wrapper });
}

describe("StockPortfolioConstructionPage", () => {
  it("renders the blocked-source reference preview without inventing target weights", async () => {
    const payload = buildPortfolioPayload({
      risk_snapshot: {
        ...buildPortfolioPayload().risk_snapshot,
        gross_exposure_ratio: "0.25",
        cash_ratio: "0.75",
        closure_residual_ratio: "0.00",
        hhi_index: "10000",
        sector_exposures: [{ sector_name: "农林牧渔", exposure_ratio: "0.25" }],
      },
    });

    renderPortfolioPage("/stock-analysis/portfolio", buildPortfolioClient(payload));

    expect(
      await screen.findByTestId("stock-analysis-portfolio-page"),
    ).toBeInTheDocument();
    const stageNav = screen.getByTestId("stock-analysis-stage-nav");
    expect(
      within(stageNav).getByRole("link", { name: /组合构建/i }),
    ).toHaveAttribute("aria-current", "page");
    const row = await screen.findByTestId(
      "stock-analysis-portfolio-row-300313.SZ",
    );
    expect(row).toHaveTextContent("天山生物");
    expect(row).toHaveTextContent("25.00%");
    expect(row).toHaveTextContent("受控回放数据结构不可用");
    expect(
      within(row).getByTitle("追溯代码：controlled_schema_unavailable"),
    ).toBeInTheDocument();
    const riskSurface = screen.getByTestId(
      "stock-analysis-portfolio-risk-surface",
    );
    expect(riskSurface).toHaveTextContent("75.00%");
    expect(riskSurface).toHaveTextContent("10,000");
    expect(riskSurface).toHaveTextContent("未接入已批准风险限额");
    expect(
      screen.getByTitle("追溯代码：blocked_missing_approved_policy"),
    ).toBeInTheDocument();
  });

  it("switches the same governed payload into the risk-focused route", async () => {
    const payload = buildPortfolioPayload({
      source_gate: {
        status: "ready",
        ready: true,
        source: "replay_closure",
        closure_status: "ready",
        selection_status: "unique_active_certified",
        data_availability: "fresh",
        as_of_date: "2026-08-24",
        cohort_id: "cohort-test",
        primary_blocker_code: null,
        reason_codes: ["current_rule_cohort_ready"],
        versions: {},
        sources: {},
      },
      source_gate_status: "ready",
      proposal_status: "reference_preview",
      target: {
        status: "reference_preview",
        blocked: false,
        candidate_count: 1,
        weight_basis:
          "stock_candidates.position_size_hint.items[].equal_weight",
        block_reason: null,
        items: [
          {
            status: "reference_preview",
            stock_code: "300313.SZ",
            stock_name: "天山生物",
            sector_name: "农林牧渔",
            rank: 1,
            signal_kind: "stock_candidate",
            reference_weight: 0.25,
            target_weight: 0.25,
            target_block_reason: null,
          },
        ],
      },
      issues: [],
    });

    renderPortfolioPage("/stock-analysis/risk?as_of_date=2026-08-24", buildPortfolioClient(payload));

    expect(
      await screen.findByTestId("stock-analysis-risk-page"),
    ).toHaveAttribute("data-focus", "risk");
    await screen.findByTestId("stock-analysis-portfolio-row-300313.SZ");
    const stageNav = screen.getByTestId("stock-analysis-stage-nav");
    expect(
      within(stageNav).getByRole("link", { name: /组合风险/i }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      screen.getByTestId("stock-analysis-portfolio-status-strip"),
    ).toHaveTextContent("描述性风险已返回");
    expect(
      screen.getByTestId("stock-analysis-portfolio-target-table"),
    ).toHaveTextContent("参考预览可见");
  });

  it.each([
    ["/stock-analysis/portfolio?as_of_date=2026-08-24", "portfolio"],
    ["/stock-analysis/risk?as_of_date=2026-08-24", "risk"],
  ] as const)("mounts the configured real page at %s", async (route, focus) => {
    renderWorkbenchApp([route], { client: buildPortfolioClient(buildPortfolioPayload()) });
    expect(await screen.findByTestId(`stock-analysis-${focus}-page`)).toHaveAttribute("data-focus", focus);
    expect(screen.getByTestId("stock-analysis-portfolio-hero")).toHaveTextContent("2026-08-24");
  });
});
