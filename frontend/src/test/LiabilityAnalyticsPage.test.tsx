import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  BalanceAnalysisDatesPayload,
  Numeric,
  ResultMeta,
} from "../api/contracts";
import type { LiabilityRiskBucketsPayload, LiabilityYieldMetricsPayload } from "../api/liabilityAdbContracts";
import type { LiabilityCounterpartyResponse } from "../api/liabilityAdbClient";
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

function meta(resultKind: string, overrides: Partial<ResultMeta> = {}): ResultMeta {
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
    ...overrides,
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
    liabilities_structure: [
      {
        name: "Interbank liabilities",
        amount: numeric(amount, "yuan"),
        amount_yi: numeric(amount / 1e8, "yi"),
      },
    ],
    liabilities_term_buckets: [
      {
        bucket: "0-3M",
        amount: numeric(amount, "yuan"),
        amount_yi: numeric(amount / 1e8, "yi"),
      },
    ],
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
    history: [],
    scatter: [],
  };
}

function counterpartyPayload(
  reportDate: string,
  totalValue = 200_000_000,
): LiabilityCounterpartyResponse {
  return {
    report_date: reportDate,
    total_value: numeric(totalValue, "yuan"),
    result_meta: meta("liability.counterparty"),
    top10_share: numeric(0.5, "pct"),
    hhi: numeric(1800, "count"),
    population_count: 2,
    is_truncated: false,
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
  it("renders a knowledge panel when note matches are available", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => riskPayload("2025-12-31")),
      getLiabilityYieldMetrics: vi.fn(async () => yieldPayload("2025-12-31")),
      getLiabilityCounterparty: vi.fn(async () => counterpartyPayload("2025-12-31")),
      getLiabilitiesMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      })),
      getLiabilityAdbMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      })),
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
              title: "Liquidity chain",
              summary: "Funding cost moves before allocation boundaries move.",
              why_it_matters: "Explains how funding pressure changes the page-level readout.",
              key_questions: ["Is the move quantity-driven or structure-driven?"],
              source_path: "D:\\PKL-WIKI\\wiki\\liquidity-chain.md",
            },
          ],
        },
      })),
    } as ApiClient);

    expect(await screen.findByTestId("liability-knowledge-panel")).toBeInTheDocument();
    expect(screen.getByText("Liquidity chain")).toBeInTheDocument();
    expect(screen.getByText(/quantity-driven or structure-driven/i)).toBeInTheDocument();
  });

  it("renders a first-screen funding conclusion from authoritative Top10 share", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => riskPayload("2025-12-31")),
      getLiabilityYieldMetrics: vi.fn(async () => yieldPayload("2025-12-31")),
      getLiabilityCounterparty: vi.fn(async () => counterpartyPayload("2025-12-31")),
      getLiabilitiesMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      })),
      getLiabilityAdbMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      })),
    });

    expect(await screen.findByTestId("liability-analytics-page")).toBeInTheDocument();
    expect(await screen.findByTestId("liability-conclusion")).toHaveTextContent(
      "资金来源集中度以后端权威指标持续跟踪",
    );
    expect(screen.getByTestId("liability-conclusion")).toHaveTextContent("Top10 占比 50.00%");
    expect(screen.getByTestId("liability-conclusion")).not.toHaveTextContent("集中度偏高");
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
        top10_share: null,
        hhi: null,
        population_count: 0,
        is_truncated: false,
        top_10: [],
        by_type: [],
      })),
      getLiabilitiesMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      })),
      getLiabilityAdbMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      })),
    });

    expect(await screen.findByTestId("liability-page-state")).toHaveTextContent(
      "所选报告日暂无负债分析数据",
    );
    expect(screen.queryByTestId("liability-conclusion")).not.toBeInTheDocument();
  });

  it("downgrades synthetic sections instead of rendering hard-coded business values", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => riskPayload("2025-12-31")),
      getLiabilityYieldMetrics: vi.fn(async () => yieldPayload("2025-12-31")),
      getLiabilityCounterparty: vi.fn(async () => counterpartyPayload("2025-12-31")),
      getCockpitWarnings: vi.fn(async () => ({
        result_meta: meta("liability.cockpit_warnings"),
        result: {
          report_date: "2025-12-31",
          watch_items: [],
          alert_events: [],
        },
      })),
      getContributionSplit: vi.fn(async () => ({
        result_meta: meta("liability.contribution_split"),
        result: {
          report_date: "2025-12-31",
          contributions: [],
        },
      })),
      getLiabilitiesMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      })),
      getLiabilityAdbMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      })),
    });

    expect(await screen.findByTestId("liability-analytics-page")).toBeInTheDocument();
    await screen.findByTestId("liability-conclusion");
    expect(await screen.findByText(/当前无待关注事项/)).toBeInTheDocument();
    expect(await screen.findByText(/未触发预警阈值/)).toBeInTheDocument();
    expect(await screen.findByText(/所选报告日无可用拆分数据/)).toBeInTheDocument();
    expect(await screen.findByText(/指标字典与口径尚未冻结/)).toBeInTheDocument();
    expect(await screen.findByText(/保留关键日历卡位/)).toBeInTheDocument();
    expect(screen.getByText("异常预警")).toBeInTheDocument();
    expect(screen.queryByText((content) => content.includes("114.54"))).not.toBeInTheDocument();
    expect(screen.queryByText("0.21%")).not.toBeInTheDocument();
  });

  it("shows null authoritative concentration metrics as em dashes instead of frontend zeroes", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => riskPayload("2025-12-31")),
      getLiabilityYieldMetrics: vi.fn(async () => yieldPayload("2025-12-31")),
      getLiabilityCounterparty: vi.fn(async () => ({
        ...counterpartyPayload("2025-12-31"),
        top10_share: null,
        hhi: null,
        population_count: 12,
        is_truncated: true,
      })),
      getLiabilitiesMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      })),
      getLiabilityAdbMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      })),
    } as ApiClient);

    expect(await screen.findByTestId("liability-analytics-page")).toBeInTheDocument();
    expect(await screen.findByTestId("liability-conclusion")).toHaveTextContent(
      "当前不对集中度做方向性判断",
    );
    expect(screen.getByTestId("liability-conclusion")).toHaveTextContent("Top10 占比 —");
    expect(screen.getByTestId("liability-conclusion")).not.toHaveTextContent("集中度偏高");
    expect(await screen.findByTestId("liability-cp-top10-share")).toHaveTextContent("—");
    expect(screen.getByTestId("liability-cp-hhi")).toHaveTextContent("—");
    expect(screen.getByTestId("liability-cp-population")).toHaveTextContent(
      "12 个对手方（仅展示前十）",
    );
  });

  it("shows counterparty result metadata on the first screen when fallback or stale states exist", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => riskPayload("2025-12-31")),
      getLiabilityYieldMetrics: vi.fn(async () => yieldPayload("2025-12-31")),
      getLiabilityCounterparty: vi.fn(async () => ({
        ...counterpartyPayload("2025-12-31"),
        result_meta: meta("liability.counterparty", {
          fallback_mode: "latest_snapshot",
          vendor_status: "vendor_stale",
        }),
      })),
      getLiabilitiesMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      })),
      getLiabilityAdbMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      })),
    } as ApiClient);

    expect(await screen.findByTestId("liability-analytics-page")).toBeInTheDocument();
    expect(await screen.findByText("1 个兜底结果")).toBeInTheDocument();
    expect(await screen.findByText("1 个供应商状态异常")).toBeInTheDocument();
    expect(screen.getAllByText("对手方集中度").length).toBeGreaterThan(0);
  });

  it("shows core fallback and optional stale metadata on the first screen without a core meta-gap", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => ({
        ...riskPayload("2025-12-31"),
        result_meta: meta("liability.risk_buckets", {
          fallback_mode: "latest_snapshot",
        }),
      })),
      getLiabilityYieldMetrics: vi.fn(async () => ({
        ...yieldPayload("2025-12-31"),
        result_meta: meta("liability.yield_metrics"),
      })),
      getLiabilityCounterparty: vi.fn(async () => counterpartyPayload("2025-12-31")),
      getCockpitWarnings: vi.fn(async () => ({
        result_meta: meta("liability.cockpit_warnings", {
          vendor_status: "vendor_stale",
        }),
        result: {
          report_date: "2025-12-31",
          watch_items: [],
          alert_events: [],
        },
      })),
      getLiabilitiesMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      })),
      getLiabilityAdbMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      })),
    } as ApiClient);

    expect(await screen.findByTestId("liability-analytics-page")).toBeInTheDocument();
    expect(await screen.findByText("1 个兜底结果")).toBeInTheDocument();
    expect(await screen.findByText("1 个供应商状态异常")).toBeInTheDocument();
    expect(screen.queryByText(/核心读面缺少元数据/)).not.toBeInTheDocument();
    expect(screen.getAllByText("负债期限结构").length).toBeGreaterThan(0);
    expect(screen.getAllByText("关注\/预警").length).toBeGreaterThan(0);
  });

  it("shows an explicit metadata gap when daily core reads do not expose result metadata", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => riskPayload("2025-12-31")),
      getLiabilityYieldMetrics: vi.fn(async () => yieldPayload("2025-12-31")),
      getLiabilityCounterparty: vi.fn(async () => counterpartyPayload("2025-12-31")),
      getLiabilitiesMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      })),
      getLiabilityAdbMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      })),
    } as ApiClient);

    expect(await screen.findByTestId("liability-analytics-page")).toBeInTheDocument();
    expect(await screen.findByText(/核心读面缺少元数据/)).toBeInTheDocument();
    expect(await screen.findByText("核心读面结果元数据未透出")).toBeInTheDocument();
    expect(screen.getByText(/负债期限结构、负债收益指标/)).toBeInTheDocument();
  });

  it("keeps the counterparty card Chinese copy while showing authority fields", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => riskPayload("2025-12-31")),
      getLiabilityYieldMetrics: vi.fn(async () => yieldPayload("2025-12-31")),
      getLiabilityCounterparty: vi.fn(async () => counterpartyPayload("2025-12-31")),
      getLiabilitiesMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      })),
      getLiabilityAdbMonthly: vi.fn(async () => ({
        year: 2026,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      })),
    } as ApiClient);

    expect(await screen.findByText("资金来源依赖度（前十对手方）")).toBeInTheDocument();
    expect(screen.getByText("机构类型结构")).toBeInTheDocument();
    expect(screen.getByTestId("liability-cp-top10-share")).toHaveTextContent(
      "Top10 占比：50.00%",
    );
    expect(screen.getByTestId("liability-cp-population")).toHaveTextContent(
      "样本覆盖：2 个对手方",
    );
  });
});
