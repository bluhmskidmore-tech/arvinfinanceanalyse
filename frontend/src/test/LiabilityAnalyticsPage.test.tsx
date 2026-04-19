import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  BalanceAnalysisDatesPayload,
  LiabilityCounterpartyPayload,
  LiabilityRiskBucketsPayload,
  LiabilityYieldMetricsPayload,
  Numeric,
  ResultMeta,
} from "../api/contracts";
import LiabilityAnalyticsPage from "../features/liability-analytics/pages/LiabilityAnalyticsPage";
import { formatRawAsNumeric } from "../utils/format";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="liability-echarts-stub" />,
}));

function renderLiabilityPage(client: ApiClient) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <ApiClientProvider client={client}>{children}</ApiClientProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(
    <Wrapper>
      <LiabilityAnalyticsPage />
    </Wrapper>,
  );
}

function meta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_liability_test",
    vendor_version: "vv_none",
    rule_version: "rv_liability_test",
    cache_version: "cv_liability_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-19T00:00:00Z",
  };
}

function numeric(raw: number | null, unit: Numeric["unit"], signAware = false): Numeric {
  return formatRawAsNumeric({ raw, unit, sign_aware: signAware });
}

function balanceDates(reportDates: string[]): { result_meta: ResultMeta; result: BalanceAnalysisDatesPayload } {
  return {
    result_meta: meta("balance-analysis.dates"),
    result: { report_dates: reportDates },
  };
}

function riskPayload(reportDate: string, amount = 200_000_000): LiabilityRiskBucketsPayload {
  return {
    report_date: reportDate,
    liabilities_structure: [{ name: "同业负债", amount: numeric(amount, "yuan"), amount_yi: numeric(amount / 1e8, "yi") }],
    liabilities_term_buckets: [{ bucket: "0-3M", amount: numeric(amount, "yuan"), amount_yi: numeric(amount / 1e8, "yi") }],
    interbank_liabilities_structure: [],
    interbank_liabilities_term_buckets: [],
    issued_liabilities_structure: [],
    issued_liabilities_term_buckets: [],
  };
}

function yieldPayload(reportDate: string): LiabilityYieldMetricsPayload {
  return {
    report_date: reportDate,
    kpi: {
      asset_yield: numeric(0.031, "pct", true),
      liability_cost: numeric(0.019, "pct", true),
      market_liability_cost: numeric(0.021, "pct", true),
      nim: numeric(0.01, "pct", true),
    },
  };
}

function counterpartyPayload(reportDate: string, totalValue = 200_000_000): LiabilityCounterpartyPayload {
  return {
    report_date: reportDate,
    total_value: numeric(totalValue, "yuan"),
    top_10: [
      {
        name: "Bank A",
        type: "Bank",
        value: numeric(60_000_000, "yuan"),
        weighted_cost: numeric(0.02, "pct", true),
      },
      {
        name: "Fund B",
        type: "NonBank",
        value: numeric(40_000_000, "yuan"),
        weighted_cost: numeric(0.024, "pct", true),
      },
    ],
    by_type: [
      { name: "Bank", value: numeric(140_000_000, "yuan") },
      { name: "NonBank", value: numeric(60_000_000, "yuan") },
    ],
  };
}

describe("LiabilityAnalyticsPage", () => {
  it("renders an obsidian business briefing panel when note matches are available", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => riskPayload("2025-12-31")),
      getLiabilityYieldMetrics: vi.fn(async () => yieldPayload("2025-12-31")),
      getLiabilityCounterparty: vi.fn(async () => counterpartyPayload("2025-12-31")),
      getLiabilitiesMonthly: vi.fn(async () => ({ year: 2026, months: [], ytd_avg_total_liabilities: null, ytd_avg_liability_cost: null })),
      getLiabilityAdbMonthly: vi.fn(async () => ({ year: 2026, months: [], ytd_avg_assets: 0, ytd_avg_liabilities: 0, ytd_asset_yield: null, ytd_liability_cost: null, ytd_nim: null, unit: "percent" })),
      getLiabilityKnowledgeBrief: vi.fn(async () => ({
        result_meta: meta("liability_analytics.knowledge"),
        result: {
          page_id: "liability-analytics",
          available: true,
          vault_path: "D:\\PKL-WIKI\\wiki",
          status_note: "obsidian-local",
          notes: [
            {
              id: "liquidity-chain",
              title: "同业负债、流动性与金融市场业务传导链",
              summary: "同业负债会先重定价资金成本，再传导到配置边界和交易动作。",
              why_it_matters: "适合解释负债成本、期限稳定性和流动性约束如何影响本页指标。",
              key_questions: [
                "当前流动性变化是总量变化还是结构变化？",
                "本行缺的是头寸还是稳定负债？",
              ],
              source_path: "D:\\PKL-WIKI\\wiki\\同业负债、流动性与金融市场业务传导链.md",
            },
          ],
        },
      })),
    } as ApiClient);

    expect(await screen.findByTestId("liability-knowledge-panel")).toBeInTheDocument();
    expect(screen.getByText("业务资料")).toBeInTheDocument();
    expect(screen.getByText("同业负债、流动性与金融市场业务传导链")).toBeInTheDocument();
    expect(screen.getByText(/当前流动性变化是总量变化还是结构变化/)).toBeInTheDocument();
  });

  it("renders a first-screen funding conclusion for daily analysis", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => riskPayload("2025-12-31")),
      getLiabilityYieldMetrics: vi.fn(async () => yieldPayload("2025-12-31")),
      getLiabilityCounterparty: vi.fn(async () => counterpartyPayload("2025-12-31")),
      getLiabilitiesMonthly: vi.fn(async () => ({ year: 2026, months: [], ytd_avg_total_liabilities: null, ytd_avg_liability_cost: null })),
      getLiabilityAdbMonthly: vi.fn(async () => ({ year: 2026, months: [], ytd_avg_assets: 0, ytd_avg_liabilities: 0, ytd_asset_yield: null, ytd_liability_cost: null, ytd_nim: null, unit: "percent" })),
    });

    expect(await screen.findByTestId("liability-analytics-page")).toBeInTheDocument();
    const conclusion = await screen.findByTestId("liability-conclusion");
    expect(conclusion).toHaveTextContent("当前结论");
    expect(conclusion).toHaveTextContent("净息差");
    expect(conclusion).toHaveTextContent("头部对手方");
    expect(screen.getByText("资金来源依赖度（Top 10 对手方）")).toBeInTheDocument();
  });

  it("surfaces an explicit page-level note when no report dates are available", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates([])),
      getLiabilityRiskBuckets: vi.fn(),
      getLiabilityYieldMetrics: vi.fn(),
      getLiabilityCounterparty: vi.fn(),
      getLiabilitiesMonthly: vi.fn(async () => ({ year: 2026, months: [], ytd_avg_total_liabilities: null, ytd_avg_liability_cost: null })),
      getLiabilityAdbMonthly: vi.fn(async () => ({ year: 2026, months: [], ytd_avg_assets: 0, ytd_avg_liabilities: 0, ytd_asset_yield: null, ytd_liability_cost: null, ytd_nim: null, unit: "percent" })),
    });

    await waitFor(() => {
      expect(screen.getByTestId("liability-page-state")).toHaveTextContent("暂无可用报告日");
    });
    await waitFor(() => {
      expect(
        screen.getAllByLabelText("liability-report-date").some((element) => (element as HTMLInputElement).disabled),
      ).toBe(true);
    });
  });

  it("surfaces an explicit page-level empty state when daily liability data is empty", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => riskPayload("2025-12-31", 0)),
      getLiabilityYieldMetrics: vi.fn(async () => yieldPayload("2025-12-31")),
      getLiabilityCounterparty: vi.fn(async () => ({
        report_date: "2025-12-31",
        total_value: numeric(0, "yuan"),
        top_10: [],
        by_type: [],
      })),
      getLiabilitiesMonthly: vi.fn(async () => ({ year: 2026, months: [], ytd_avg_total_liabilities: null, ytd_avg_liability_cost: null })),
      getLiabilityAdbMonthly: vi.fn(async () => ({ year: 2026, months: [], ytd_avg_assets: 0, ytd_avg_liabilities: 0, ytd_asset_yield: null, ytd_liability_cost: null, ytd_nim: null, unit: "percent" })),
    });

    expect(await screen.findByTestId("liability-page-state")).toHaveTextContent("所选报告日暂无负债分析数据");
    expect(screen.queryByTestId("liability-conclusion")).not.toBeInTheDocument();
  });
});
