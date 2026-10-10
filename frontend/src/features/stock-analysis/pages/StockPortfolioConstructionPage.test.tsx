import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import {
  ApiClientProvider,
  createApiClient,
  type ApiClient,
} from "../../../api/client";
import type {
  ResultMeta,
  StockPortfolioConstructionPayload,
} from "../../../api/contracts";
import { buildMockApiEnvelope } from "../../../mocks/mockApiEnvelope";
import { EM_DASH } from "../../../utils/format";
import StockPortfolioConstructionPage from "./StockPortfolioConstructionPage";

function blockedPayload(): StockPortfolioConstructionPayload {
  return {
    page_id: "GAP-STOCK-ANALYSIS-PORTFOLIO",
    route: "/stock-analysis/portfolio",
    portfolio_id: "SHADOW-STOCK-RESEARCH",
    requested_as_of_date: null,
    as_of_date: "2026-08-24",
    resolved_as_of_date: "2026-08-24",
    basis: "analytical",
    contract_status: "proposal_only",
    formal_use_allowed: false,
    trading_instruction_allowed: false,
    execution_approval_allowed: false,
    proposal_status: "blocked_source_gate",
    context: {
      requested_as_of_date: null,
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
          selection_close: 15.8,
          score: 0.81,
          equal_weight: 0.25,
          reference_weight: 0.25,
          target_weight: null,
          target_weight_basis: "position_size_hint.equal_weight",
          position_hint: null,
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
      basis: "read_only_shadow",
      measurement_basis: "reference_preview",
      portfolio_id: "SHADOW-STOCK-RESEARCH",
      as_of_date: "2026-08-24",
      source_gate_status: "blocked",
      input_line_count: 1,
      position_count: 1,
      observation_only: true,
      formal_use_allowed: false,
      target_weight_sum_ratio: 0.25,
      gross_exposure_ratio: 0.25,
      net_exposure_ratio: 0.25,
      cash_ratio: 0.75,
      closure_residual_ratio: 0,
      top1_weight_ratio: 0.25,
      top5_weight_ratio: 0.25,
      hhi_ratio: 1,
      hhi_index: 10000,
      sector_exposures: [{ sector_name: "农林牧渔", exposure_ratio: 0.25 }],
      limit_gate: {
        status: "blocked_missing_approved_policy",
        reason_code: "missing_approved_policy",
        approved_policy_present: false,
      },
      reason_codes: [],
      warnings: [],
    },
    legacy_position_snapshot: {
      used: false,
      status: "ignored_unscoped",
      reason: "Legacy snapshot is not portfolio scoped.",
    },
    versions: {
      source_version: "sv_test",
      workbench_rule_version: "rv_workbench_test",
      portfolio_construction_rule_version:
        "rv_stock_portfolio_construction_phase2a_v1",
      portfolio_version: "SHADOW-STOCK-RESEARCH",
      proposal_version: null,
      calculation_run_id: null,
      review_run_id: null,
    },
    warnings: [
      "Proposal-only projection; it does not create a trading instruction or approval.",
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
      {
        severity: "blocking",
        code: "blocked_missing_scoped_positions",
        message: "Portfolio-scoped current positions are required.",
        source: "portfolio_scope",
      },
    ],
  };
}

function renderPage(pathname: string, client: ApiClient) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: {
              retry: false,
              staleTime: 0,
              refetchOnWindowFocus: false,
            },
          },
        }),
    );
    return (
      <MemoryRouter initialEntries={[pathname]}>
        <QueryClientProvider client={queryClient}>
          <ApiClientProvider client={client}>{children}</ApiClientProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(<StockPortfolioConstructionPage />, { wrapper: Wrapper });
}

function clientWithPortfolioResult(
  payload = blockedPayload(),
  metaOverrides: Partial<ResultMeta> = {},
) {
  const client = createApiClient({ mode: "mock" });
  const request = vi
    .spyOn(client, "getStockAnalysisPortfolioConstruction")
    .mockResolvedValue(
      buildMockApiEnvelope(
        "market_data.stock_analysis.portfolio_construction",
        payload,
        {
          basis: "analytical",
          source_surface: "market_data",
          quality_flag: "warning",
          ...metaOverrides,
        },
      ),
    );
  return { client, request };
}

describe("StockPortfolioConstructionPage", () => {
  it("keeps reference weight visible while formal target and execution remain blocked", async () => {
    const { client, request } = clientWithPortfolioResult();
    renderPage("/stock-analysis/portfolio", client);

    const row = await screen.findByTestId(
      "stock-analysis-portfolio-row-300313.SZ",
    );
    expect(within(row).getByText("天山生物")).toBeInTheDocument();
    expect(within(row).getByText("25.00%")).toBeInTheDocument();
    expect(within(row).getByText(EM_DASH)).toBeInTheDocument();
    expect(screen.getByText(/目标权重与调仓结果继续锁定/)).toBeInTheDocument();
    expect(screen.getAllByText("75.00%").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/缺少组合级当前持仓/).length).toBeGreaterThan(0);
    expect(screen.getByText(/未接入已批准风险限额/)).toBeInTheDocument();
    expect(
      screen.getByTitle(/原因代码：missing_approved_policy/),
    ).toBeInTheDocument();
    const statusStrip = screen.getByTestId(
      "stock-analysis-portfolio-status-strip",
    );
    expect(statusStrip).not.toHaveTextContent("blocked_source_gate");
    expect(statusStrip).not.toHaveTextContent("controlled_schema_unavailable");
    expect(
      screen.getAllByTitle("追溯代码：blocked_source_gate").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByTestId(
        "stock-analysis-portfolio-issue-source_gate_not_ready",
      ),
    ).toHaveTextContent("source_gate_not_ready");
    expect(
      screen.queryByRole("button", { name: /买入|卖出|下单|执行审批/ }),
    ).not.toBeInTheDocument();

    await waitFor(() => {
      expect(request).toHaveBeenCalledWith({
        portfolioId: "SHADOW-STOCK-RESEARCH",
        asOfDate: undefined,
      });
    });
  });

  it("uses the same read-only payload on the risk route and marks risk as current", async () => {
    const { client } = clientWithPortfolioResult();
    renderPage("/stock-analysis/risk", client);

    expect(
      await screen.findByTestId("stock-analysis-risk-page"),
    ).toHaveAttribute("data-focus", "risk");
    expect(screen.getByRole("link", { name: /组合风险/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByText(/暴露、现金和集中度/)).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByTestId("stock-analysis-portfolio-risk-state"),
      ).toHaveAttribute("data-status", "partial");
    });
  });

  it("does not treat a ready candidate source as a completed portfolio mapping", async () => {
    const payload = blockedPayload();
    const { client } = clientWithPortfolioResult({
      ...payload,
      proposal_status: "blocked_main_module",
      source_gate_status: "ready",
      source_gate: {
        ...payload.source_gate,
        status: "ready",
        ready: true,
        primary_blocker_code: null,
      },
      target: {
        ...payload.target,
        status: "blocked_main_module",
        blocked: true,
        block_reason: "main_module_unavailable",
      },
    });
    renderPage("/stock-analysis/portfolio", client);

    expect(await screen.findByText(/主研究模块不可用/)).toBeInTheDocument();
    expect(
      screen.getByTestId("stock-analysis-portfolio-status-strip"),
    ).toHaveTextContent("主研究模块未完成映射");
    expect(
      screen.getAllByTitle("追溯代码：blocked_main_module").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByTestId("stock-analysis-portfolio-risk-state"),
    ).toHaveAttribute("data-status", "partial");
  });

  it("surfaces stale and fallback semantics across the frame and risk block", async () => {
    const payload = blockedPayload();
    const { client } = clientWithPortfolioResult(payload, {
      quality_flag: "stale",
      vendor_status: "vendor_stale",
      fallback_mode: "latest_snapshot",
    });
    renderPage("/stock-analysis/risk", client);

    expect(await screen.findByText(/当前展示的是延迟快照/)).toBeInTheDocument();
    expect(
      screen.getByTestId("stock-analysis-portfolio-status-strip"),
    ).toHaveTextContent("描述性风险为延迟快照");
    expect(
      screen.getByTestId("stock-analysis-portfolio-risk-state"),
    ).toHaveAttribute("data-status", "stale");
    expect(
      screen.getByTestId("stock-analysis-portfolio-risk-state"),
    ).toHaveTextContent("最近可用快照");
    expect(screen.getByTitle("追溯代码：latest_snapshot")).toBeInTheDocument();
  });

  it("renders an actionable error state without inventing portfolio data", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getStockAnalysisPortfolioConstruction").mockRejectedValue(
      new Error("portfolio endpoint unavailable"),
    );
    renderPage("/stock-analysis/portfolio", client);

    expect(
      await screen.findByTestId("stock-analysis-portfolio-page-error"),
    ).toHaveTextContent("portfolio endpoint unavailable");
    expect(
      screen.getByRole("button", { name: "重新读取" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("天山生物")).not.toBeInTheDocument();
  });
});
