import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  BalanceAnalysisDatesPayload,
  Numeric,
  ResultMeta,
} from "../api/contracts";
import type { AdbMonthlyDataItem, AdbMonthlyResponse } from "../api/contracts/cubeAdb";
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
    missing_maturity_count: 0,
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

function emptyRiskPayload(reportDate: string): LiabilityRiskBucketsPayload {
  return {
    report_date: reportDate,
    missing_maturity_count: 0,
    liabilities_structure: [],
    liabilities_term_buckets: [],
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

function adbMonth(
  month: string,
  monthLabel: string,
  assetYield: number,
  liabilityCost: number,
  nim: number,
): AdbMonthlyDataItem {
  return {
    month,
    month_label: monthLabel,
    num_days: 30,
    avg_assets: null,
    avg_liabilities: null,
    asset_yield: assetYield,
    liability_cost: liabilityCost,
    net_interest_margin: nim,
    mom_change_assets: null,
    mom_change_pct_assets: null,
    mom_change_liabilities: null,
    mom_change_pct_liabilities: null,
    breakdown_assets: [],
    breakdown_liabilities: [],
  };
}

function adbMonthlyPayload(year: number): AdbMonthlyResponse {
  return {
    result_meta: meta("adb.monthly", { basis: "analytical", formal_use_allowed: false }),
    year,
    months: [
      adbMonth(`${year}-01`, "1月", 2.42, 1.77, 0.65),
      adbMonth(`${year}-02`, "2月", 2.46, 1.75, 0.71),
      adbMonth(`${year}-03`, "3月", 2.43, 1.58, 0.85),
    ],
    ytd_avg_assets: null,
    ytd_avg_liabilities: null,
    ytd_asset_yield: null,
    ytd_liability_cost: null,
    ytd_nim: null,
    unit: "percent",
  };
}

function nullYieldPayload(reportDate: string): LiabilityYieldMetricsPayload {
  return {
    report_date: reportDate,
    kpi: {
      asset_yield: numeric(null, "pct", true),
      liability_cost: numeric(null, "pct", true),
      market_liability_cost: numeric(null, "pct", true),
      nim: numeric(null, "pct", true),
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
    // 整区默认折叠；来源绝对路径只保留在 title，不在正文暴露本机路径。
    const details = screen
      .getByTestId("liability-knowledge-panel")
      .querySelector("details.liability-knowledge__details");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");
    expect(screen.getByText(/业务笔记 1 篇/)).toBeInTheDocument();
    expect(screen.queryByText(/D:\\PKL-WIKI/)).not.toBeInTheDocument();
    expect(screen.getByText("来源：本机 Obsidian 笔记")).toHaveAttribute(
      "title",
      "D:\\PKL-WIKI\\wiki\\liquidity-chain.md",
    );
  });

  it("renders a first-screen funding conclusion from authoritative Top10 share", async () => {
    const base = createApiClient({ mode: "real" });
    const getLiabilityAdbMonthly = vi.fn(async (year: number) => adbMonthlyPayload(year));

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
      getLiabilityAdbMonthly,
    });

    expect(await screen.findByTestId("liability-analytics-page")).toBeInTheDocument();
    expect(await screen.findByTestId("liability-conclusion")).toHaveTextContent(
      "资金来源集中度以后端权威指标持续跟踪",
    );
    expect(screen.getByTestId("liability-conclusion")).toHaveTextContent("Top10 占比 50.00%");
    expect(screen.getByTestId("liability-conclusion")).not.toHaveTextContent("集中度偏高");
    // 迁入 ChartCard 后：年份在 unit · asOf 元信息位，口径在问题句位，卡片本体是 role=figure。
    const yieldTrend = await screen.findByTestId("liability-yield-trend");
    expect(yieldTrend).toHaveTextContent("% · 2025 年");
    expect(yieldTrend).toHaveTextContent("月度日均口径");
    expect(getLiabilityAdbMonthly).toHaveBeenCalledWith(2025);
    expect(
      screen.getByRole("figure", { name: "月度日均资产收益、负债成本与净息差趋势" }),
    ).toBeInTheDocument();
  });

  it("surfaces an explicit page-level empty state when daily liability data is empty", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => emptyRiskPayload("2025-12-31")),
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
    // 空态不做「所有指标正常」全称断言；预警口径归右卡。
    expect(await screen.findByText(/暂无结构化待办事项/)).toBeInTheDocument();
    expect(await screen.findByText(/预警事件见右侧卡片/)).toBeInTheDocument();
    expect(screen.queryByText(/所有指标均在正常范围内/)).not.toBeInTheDocument();
    expect(await screen.findByText(/未触发预警阈值/)).toBeInTheDocument();
    expect(await screen.findByText(/所选报告日无可用拆分数据/)).toBeInTheDocument();
    // 预留区块整卡隐藏，只留一行安静说明；「隐藏 0 个」开发语不再出现。
    expect(await screen.findByText(/待相应接口接入后提供，当前不展示示意数据/)).toBeInTheDocument();
    expect(screen.queryByText("风险全景")).not.toBeInTheDocument();
    expect(screen.queryByText("期限错配")).not.toBeInTheDocument();
    expect(screen.queryByText(/当前隐藏/)).not.toBeInTheDocument();
    expect(screen.queryByText(/指标字典与口径尚未冻结/)).not.toBeInTheDocument();
    expect(screen.queryByText(/保留关键日历卡位/)).not.toBeInTheDocument();
    expect(screen.getByText("异常预警")).toBeInTheDocument();
    expect(screen.queryByText((content) => content.includes("114.54"))).not.toBeInTheDocument();
    expect(screen.queryByText("0.21%")).not.toBeInTheDocument();
  });

  it("discloses missing rate coverage and leaves the total contribution unavailable", async () => {
    const base = createApiClient({ mode: "real" });
    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => riskPayload("2025-12-31")),
      getLiabilityYieldMetrics: vi.fn(async () => yieldPayload("2025-12-31")),
      getLiabilityCounterparty: vi.fn(async () => counterpartyPayload("2025-12-31")),
      getContributionSplit: vi.fn(async () => ({
        result_meta: meta("liability.contribution_split", { quality_flag: "warning" }),
        result: {
          report_date: "2025-12-31",
          contributions: [{
            category: "缺失利率核验",
            side: "liability" as const,
            amount_yi: 10,
            yield_or_cost: null,
            contribution_yi: null,
            known_contribution_yi: 0.02,
            missing_rate_amount_yi: 9,
            rate_coverage_pct: 10,
          }],
        },
      })),
    });

    const label = await screen.findByText("缺失利率核验");
    const row = label.closest("tr")!;
    expect(within(row).getAllByText("—")).toHaveLength(2);
    expect(row).toHaveTextContent("利率覆盖 10.00%");
    expect(row).toHaveTextContent("缺失利率金额 9.00 亿");
    expect(row).toHaveTextContent("已知部分贡献 0.02 亿");
    expect(row).toHaveTextContent("总体贡献不可用");
  });

  it("shows the warnings KPI as em dash instead of zero when the report-date directory fails", async () => {
    const base = createApiClient({ mode: "real" });
    const getCockpitWarnings = vi.fn(async () => {
      throw new Error("LEDGER_READ_FAILED: 后端服务不可用(502)");
    });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => {
        throw new Error("后端服务不可用(502)");
      }),
      getCockpitWarnings,
    } as ApiClient);

    expect(await screen.findByTestId("liability-page-state")).toHaveTextContent(
      "无法加载资产负债可用日期",
    );
    // 报告日缺失 → 预警 query 未启用；计数位不能把「未知」显示成 0。
    const kpiBand = screen.getByTestId("liability-analytics-kpi-band");
    expect(kpiBand).toHaveTextContent("异常预警");
    expect(kpiBand).toHaveTextContent("预警读面未返回");
    expect(kpiBand).toHaveTextContent("—");
    expect(kpiBand).not.toHaveTextContent("0条");
    expect(kpiBand).not.toHaveTextContent("0 关注");
    expect(kpiBand).not.toHaveTextContent("0 预警");
    expect(getCockpitWarnings).not.toHaveBeenCalled();
    // 证据区不再永远停在「读取中」，改为明确的「未触发」。
    expect(screen.getByText("核心读面未触发")).toBeInTheDocument();
    expect(screen.getByText("核心读面未触发，证据账本未生成。")).toBeInTheDocument();
    expect(screen.queryByText("核心读面元数据读取中")).not.toBeInTheDocument();
    expect(screen.queryByText("证据账本读取中…")).not.toBeInTheDocument();
  });

  it("shows the warnings KPI as em dash when the warnings read itself fails", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => riskPayload("2025-12-31")),
      getLiabilityYieldMetrics: vi.fn(async () => yieldPayload("2025-12-31")),
      getLiabilityCounterparty: vi.fn(async () => counterpartyPayload("2025-12-31")),
      getCockpitWarnings: vi.fn(async () => {
        throw new Error("warnings unavailable");
      }),
      getLiabilityAdbMonthly: vi.fn(async (year: number) => adbMonthlyPayload(year)),
    } as ApiClient);

    await screen.findByTestId("liability-conclusion");
    const kpiBand = screen.getByTestId("liability-analytics-kpi-band");
    await waitFor(() => expect(kpiBand).toHaveTextContent("预警读面未返回"));
    expect(kpiBand).not.toHaveTextContent("0条");
    expect(kpiBand).not.toHaveTextContent("0 关注");
    expect(await screen.findByText("待办事项读取失败")).toBeInTheDocument();
    expect(screen.getByText("预警事件读取失败")).toBeInTheDocument();
    expect(screen.queryByText("未触发预警阈值。")).not.toBeInTheDocument();
  });

  it("suspends the NIM direction claim and discloses the yield read gap when yield values are missing", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => riskPayload("2025-12-31")),
      getLiabilityYieldMetrics: vi.fn(async () => nullYieldPayload("2025-12-31")),
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

    // NIM 缺失时结论不做「仍为正」方向断言（缺值守卫）。
    expect(await screen.findByTestId("liability-conclusion")).toHaveTextContent(
      "NIM 读数未返回，息差判断暂缺",
    );
    expect(screen.getByTestId("liability-conclusion")).not.toHaveTextContent("净息差仍为正");
    // 同因缺失一次性披露：收益成本与压力测试两区各在区头露一次原因。
    expect(await screen.findAllByText("负债收益读面未返回读数，本区暂缺。")).toHaveLength(2);
    expect(screen.getByTestId("liability-yield-trend")).toHaveTextContent(
      "暂无足够月度序列，至少需要 2 个月",
    );
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
    expect(screen.getAllByText("sv_liability_test").length).toBeGreaterThan(0);
  });

  it("keeps total scope consistent and excludes undated balances from known maturity pressure", async () => {
    const base = createApiClient({ mode: "real" });

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates(["2025-12-31"])),
      getLiabilityRiskBuckets: vi.fn(async () => ({
        ...riskPayload("2025-12-31"),
        missing_maturity_count: 2,
        liabilities_structure: [{ name: "全部负债", amount: numeric(900_000_000, "yuan") }],
        liabilities_term_buckets: [
          { bucket: "0-3M", amount: numeric(200_000_000, "yuan") },
          { bucket: "Matured", amount: numeric(100_000_000, "yuan") },
          { bucket: "到期日未提供", amount: numeric(600_000_000, "yuan") },
        ],
      })),
      getLiabilityYieldMetrics: vi.fn(async () => yieldPayload("2025-12-31")),
      getLiabilityCounterparty: vi.fn(async () => counterpartyPayload("2025-12-31")),
    } as ApiClient);

    expect(await screen.findByText(/2 条负债记录未列到期日，期限属性待核实/)).toBeInTheDocument();
    expect(screen.getByTestId("liability-missing-maturity-warning")).toHaveTextContent("到期压力尚不完整");
    const band = screen.getByTestId("liability-analytics-kpi-band");
    const totalCell = band.querySelectorAll(".liability-kpi-cell")[0];
    expect(totalCell).toHaveTextContent("负债总额9.00亿");
    expect(band.querySelectorAll(".liability-kpi-cell")[3]).toHaveTextContent("1年内到期3.00亿");
    const decomposition = screen.getByRole("heading", { name: "收益成本分解（静态口径）" }).parentElement!;
    expect(decomposition.querySelectorAll(".liability-kpi-cell")[1]).toHaveTextContent("市场化负债成本+2.10%");
  });

  it("uses the backend monthly counterparty population for both scale and proportion", async () => {
    const base = createApiClient({ mode: "real" });
    const year = new Date().getFullYear();

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates([`${year}-06-30`])),
      getLiabilitiesMonthlySummary: vi.fn(async () => ({
        result_meta: meta("liability_analytics.monthly_summary", {
          basis: "analytical",
          formal_use_allowed: false,
        }),
        year,
        months: [
          {
            month: `${year}-06`,
            month_label: `${year}年6月`,
            avg_total_liabilities: numeric(200_000_000, "yuan"),
            avg_interbank_liabilities: numeric(100_000_000, "yuan"),
            avg_issued_liabilities: numeric(100_000_000, "yuan"),
            avg_liability_cost: numeric(0.02, "pct"),
            mom_change: numeric(20_000_000, "yuan", true),
            mom_change_pct: numeric(0.1, "pct", true),
            yoy_change: numeric(-10_000_000, "yuan", true),
            yoy_change_pct: numeric(-0.047619, "pct", true),
            num_days: 30,
          },
        ],
        ytd_avg_total_liabilities: numeric(200_000_000, "yuan"),
        ytd_avg_liability_cost: numeric(0.02, "pct"),
      })),
      getLiabilitiesMonthlyDetail: vi.fn(async () => ({
        result_meta: meta("liability_analytics.monthly_detail", {
          basis: "analytical",
          formal_use_allowed: false,
        }),
        year,
        selected_month: `${year}-06`,
        detail: {
          month: `${year}-06`,
          month_label: `${year}年6月`,
          counterparty_total: numeric(100_000_000, "yuan"),
          top10_share: numeric(0.8, "pct"),
          hhi: numeric(1800, "count"),
          population_count: 2,
          is_truncated: false,
          counterparty_details: [
            {
              name: "Bank Monthly",
              avg_value: numeric(60_000_000, "yuan"),
              proportion: numeric(0.6, "pct"),
              pct: numeric(0.3, "pct"),
              weighted_cost: numeric(0.02, "pct"),
              type: "Bank",
            },
          ],
          counterparty_top10: [
              {
                name: "Bank Monthly",
                avg_value: numeric(60_000_000, "yuan"),
                proportion: numeric(0.6, "pct"),
                pct: numeric(0.3, "pct"),
                weighted_cost: numeric(0.02, "pct"),
                type: "Bank",
              },
          ],
          by_institution_type: [],
          structure_overview: [],
          term_buckets: [],
          interbank_by_type: [],
          interbank_term_buckets: [],
          issued_by_type: [],
          issued_term_buckets: [],
          num_days: 30,
        },
      })),
      getLiabilityAdbMonthly: vi.fn(async () => ({
        result_meta: meta("adb.monthly", { basis: "analytical", formal_use_allowed: false }),
        year,
        months: [adbMonth(`${year}-06`, `${year}年6月`, 2.5, 1.8, 0.7)],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      })),
    } as ApiClient);

    fireEvent.click(screen.getByText("月度统计"));

    expect(await screen.findByText("Bank Monthly")).toBeInTheDocument();
    expect(screen.getByText("60.00%")).toBeInTheDocument();
    expect(screen.queryByText("30.00%")).not.toBeInTheDocument();
    expect(screen.getByRole("figure", { name: "资金来源依赖度（前十对手方）" })).toHaveTextContent("总规模：1.00 亿");
    expect(screen.getAllByText("2.00 亿元").length).toBeGreaterThan(0);
    expect(screen.getByText("+0.20 亿元")).toBeInTheDocument();
    expect(screen.getByText("+10.00%")).toBeInTheDocument();
    expect(screen.getByText("-0.10 亿元")).toBeInTheDocument();
    expect(screen.getByText("-4.76%")).toBeInTheDocument();
    expect(screen.queryByText(/请求报告日与返回报告日不一致/)).not.toBeInTheDocument();
    expect(screen.getByText(/月度规模卡优先采用发行负债摊余成本/)).toBeInTheDocument();
    expect(screen.getByTestId("liability-evidence-lineage-liabilities-monthly")).not.toHaveAttribute("open");
    expect(screen.getByTestId("liability-evidence-lineage-liabilities-monthly-detail")).not.toHaveAttribute("open");
    expect(screen.getByTestId("liability-evidence-lineage-adb-monthly")).not.toHaveAttribute("open");
  });

  it("renders the monthly overview before selected-month detail finishes loading", async () => {
    const base = createApiClient({ mode: "real" });
    const year = new Date().getFullYear();

    renderLiabilityPage({
      ...base,
      getBalanceAnalysisDates: vi.fn(async () => balanceDates([`${year}-06-30`])),
      getLiabilitiesMonthlySummary: vi.fn(async () => ({
        result_meta: meta("liability_analytics.monthly_summary", {
          basis: "analytical",
          formal_use_allowed: false,
        }),
        year,
        months: [
          {
            month: `${year}-06`,
            month_label: `${year}年6月`,
            avg_total_liabilities: numeric(200_000_000, "yuan"),
            avg_interbank_liabilities: numeric(100_000_000, "yuan"),
            avg_issued_liabilities: numeric(100_000_000, "yuan"),
            avg_liability_cost: numeric(0.02, "pct"),
            mom_change: numeric(20_000_000, "yuan", true),
            mom_change_pct: numeric(0.1, "pct", true),
            yoy_change: numeric(-10_000_000, "yuan", true),
            yoy_change_pct: numeric(-0.047619, "pct", true),
            num_days: 30,
          },
        ],
        ytd_avg_total_liabilities: numeric(200_000_000, "yuan"),
        ytd_avg_liability_cost: numeric(0.02, "pct"),
      })),
      getLiabilitiesMonthlyDetail: vi.fn(() => new Promise(() => undefined)),
      getLiabilityAdbMonthly: vi.fn(async () => adbMonthlyPayload(year)),
    } as ApiClient);

    fireEvent.click(screen.getByText("月度统计"));

    expect(await screen.findAllByText("2.00 亿元")).not.toHaveLength(0);
    expect(screen.getByText("所选月份期限结构读取中…")).toBeInTheDocument();
    expect(screen.queryByText("Bank Monthly")).not.toBeInTheDocument();
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
    // 类型列中文化（Bank → 银行 / NonBank → 非银金融），未登记枚举原样透出。
    expect(await screen.findByText("银行")).toBeInTheDocument();
    expect(screen.getByText("非银金融")).toBeInTheDocument();
    // 加权负债成本是水平值：剥掉 sign_aware 前导「+」，数值精度不变。
    expect(screen.getByText("2.00%")).toBeInTheDocument();
    expect(screen.queryByText("+2.00%")).not.toBeInTheDocument();
  });
});
