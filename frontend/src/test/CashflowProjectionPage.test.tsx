import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import CashflowProjectionPage from "../features/cashflow-projection/pages/CashflowProjectionPage";
import { formatRawAsNumeric } from "../utils/format";

const CASHFLOW_PAGE_CSS_PATH = resolve(
  process.cwd(),
  "src/features/cashflow-projection/pages/CashflowProjectionPage.module.css",
);
const CASHFLOW_PAGE_TSX_PATH = resolve(
  process.cwd(),
  "src/features/cashflow-projection/pages/CashflowProjectionPage.tsx",
);

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="cashflow-echarts-stub" />,
}));

describe("CashflowProjectionPage", () => {
  it("binds page tokens to IB aliases and keeps duration-gap off --ib-up", () => {
    const css = readFileSync(CASHFLOW_PAGE_CSS_PATH, "utf8");
    const tsx = readFileSync(CASHFLOW_PAGE_TSX_PATH, "utf8");
    const source = `${css}\n${tsx}`;

    expect(source).not.toMatch(/moss-color-warm-|designTokens\.color\.warm/);
    expect(source).not.toMatch(/rgba\((255, 253, 248|240, 230, 216|52, 43, 39)/);
    expect(source).not.toMatch(/#(fffdf8|f0e6d8|e4d8c8|b8a38f|342b27|6f6258|8f7e70|b85c38|708c74|7c3e46|667a96)/i);

    expect(css).toContain("--cf-paper: var(--ib-surface)");
    expect(css).toContain("--cf-positive: var(--ib-up)");
    expect(css).toContain("--cf-negative: var(--ib-down)");
    expect(css).toContain("--cf-accent: var(--ib-warn)");
    expect(css).toContain("--cf-subtle: var(--ib-ink-secondary)");
    expect(css).toContain("border-radius: var(--ib-radius)");

    // Positive duration gap chrome must use warn/secondary, never --ib-up / --cf-positive.
    const positiveDeck = css.slice(css.indexOf(".decisionDeck_positive"));
    expect(positiveDeck).toContain("var(--cf-accent)");
    expect(positiveDeck.split(".decisionDeck_negative")[0]).not.toContain("var(--cf-positive)");
    expect(css).toContain(".metricCell_gapPositive strong");
    expect(css).toMatch(/\.metricCell_gapPositive strong\s*\{\s*color:\s*var\(--cf-subtle\)/);

    expect(tsx).toContain("selectCashflowDurationGapTone");
    expect(tsx).not.toMatch(/(["'`])--\1/);
    expect(tsx).toContain("EM_DASH");
  });

  it("mounts KPI cards when projection loads", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CashflowProjectionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("cashflow-projection-page")).toBeInTheDocument();
    expect(screen.getByTestId("cashflow-page-title")).toHaveTextContent("现金流预测");
    expect(await screen.findByTestId("cashflow-kpi-duration-gap")).toBeInTheDocument();
    expect(await screen.findByTestId("cashflow-kpi-asset-dur")).toBeInTheDocument();
    expect(await screen.findByTestId("cashflow-kpi-liability-dur")).toBeInTheDocument();
    expect(await screen.findByTestId("cashflow-kpi-dv01")).toBeInTheDocument();
    expect(await screen.findByTestId("cashflow-kpi-equity-dur")).toBeInTheDocument();
    expect(await screen.findByTestId("cashflow-kpi-reinvest")).toBeInTheDocument();
    expect(screen.getByText("现金流概览")).toBeInTheDocument();
    expect(screen.getByText("月度投影")).toBeInTheDocument();
    expect(screen.getByText("到期资产与提示")).toBeInTheDocument();
  });

  it("renders chart region when monthly buckets are present", async () => {
    const client = createApiClient({ mode: "mock" });
    const orig = client.getBalanceAnalysisDates.bind(client);
    client.getBalanceAnalysisDates = async () => {
      const r = await orig();
      return {
        ...r,
        result: { ...r.result, report_dates: ["2026-04-01"] },
      };
    };
    client.getCashflowProjection = async (reportDate: string) => {
      const r = await createApiClient({ mode: "mock" }).getCashflowProjection(reportDate);
      return {
        ...r,
        result: {
          ...r.result,
          monthly_buckets: [
            {
              year_month: "2026-04",
              asset_inflow: formatRawAsNumeric({ raw: 100, unit: "yuan", sign_aware: false }),
              liability_outflow: formatRawAsNumeric({ raw: 40, unit: "yuan", sign_aware: false }),
              net_cashflow: formatRawAsNumeric({ raw: 60, unit: "yuan", sign_aware: true }),
              cumulative_net: formatRawAsNumeric({ raw: 60, unit: "yuan", sign_aware: true }),
            },
          ],
        },
      };
    };

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CashflowProjectionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("cashflow-echarts-stub")).toBeInTheDocument();
    expect(await screen.findByTestId("cashflow-risk-readout")).toHaveTextContent("累计净流风险读数");
    expect(screen.getByTestId("cashflow-risk-readout")).toHaveTextContent("未见累计净现金流为负月份");
    expect(screen.getByTestId("cashflow-risk-readout")).toHaveTextContent("期末累计净流");
  });

  it("requests projection for the first available balance-analysis report date", async () => {
    const client = createApiClient({ mode: "mock" });
    const origDates = client.getBalanceAnalysisDates.bind(client);
    client.getBalanceAnalysisDates = async () => {
      const r = await origDates();
      return {
        ...r,
        result: { ...r.result, report_dates: ["2026-04-01", "2026-03-01"] },
      };
    };
    const spy = vi.spyOn(client, "getCashflowProjection");

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CashflowProjectionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(spy).toHaveBeenCalledWith("2026-04-01"));
  });

  it("surfaces a first-screen conclusion from the duration gap", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CashflowProjectionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("cashflow-conclusion")).toHaveTextContent("当前结论");
    expect(screen.getByTestId("cashflow-conclusion")).toHaveTextContent("资产久期长于负债");
  });

  it("displays the 1bp sensitivity KPI in yi-yuan even when the API display is raw yuan", async () => {
    const client = createApiClient({ mode: "mock" });
    const orig = client.getCashflowProjection.bind(client);
    client.getCashflowProjection = async (reportDate: string) => {
      const envelope = await orig(reportDate);
      return {
        ...envelope,
        result: {
          ...envelope.result,
          rate_sensitivity_1bp: {
            raw: 125_000_000,
            unit: "yuan",
            display: "+125,000,000.00",
            precision: 2,
            sign_aware: true,
          },
        },
      };
    };

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CashflowProjectionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const page = await screen.findByTestId("cashflow-projection-page");
    expect(await screen.findByTestId("cashflow-kpi-dv01")).toHaveTextContent("+1.25");
    expect(page).not.toHaveTextContent("+125,000,000.00");
  });

  it("renders negative 1bp sensitivity as equity-loss semantics", async () => {
    const client = createApiClient({ mode: "mock" });
    const orig = client.getCashflowProjection.bind(client);
    client.getCashflowProjection = async (reportDate: string) => {
      const envelope = await orig(reportDate);
      return {
        ...envelope,
        result: {
          ...envelope.result,
          rate_sensitivity_1bp: {
            raw: -80_000_000,
            unit: "yuan",
            display: "-80,000,000.00",
            precision: 2,
            sign_aware: true,
          },
        },
      };
    };

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CashflowProjectionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const dv01 = await screen.findByTestId("cashflow-kpi-dv01");
    expect(dv01).toHaveTextContent("-0.80");
    expect(dv01).toHaveTextContent("利率上行 1bp → 权益减少");
  });

  it("renders Chinese caveat summaries and collapses English originals into details", async () => {
    const registered =
      "Liability duration uses a remaining-term proxy (years to maturity), not a cashflow-weighted duration.";
    const unregistered = "Some brand-new backend caveat that the frontend has not registered.";
    const client = createApiClient({ mode: "mock" });
    const orig = client.getCashflowProjection.bind(client);
    client.getCashflowProjection = async (reportDate: string) => {
      const envelope = await orig(reportDate);
      return {
        ...envelope,
        result: {
          ...envelope.result,
          warnings: [registered, unregistered],
        },
      };
    };

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CashflowProjectionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    // 登记句显示中文摘要；未登记句原样透出。
    expect(
      await screen.findByText("负债久期为剩余期限（到期年限）代理，非现金流加权久期。"),
    ).toBeInTheDocument();
    expect(screen.getByText(unregistered)).toBeInTheDocument();

    // 英文原文收进默认折叠的 details，且只收登记句（未登记句不重复）。
    const details = screen.getByTestId("cashflow-warning-originals");
    expect(details.tagName).toBe("DETAILS");
    expect(details).not.toHaveAttribute("open");
    expect(details).toHaveTextContent("英文原文（1 条）");
    expect(details).toHaveTextContent(registered);
  });

  it("uses DataSection fallback banner when result_meta marks latest_snapshot fallback", async () => {
    const client = createApiClient({ mode: "mock" });
    const orig = client.getCashflowProjection.bind(client);
    client.getCashflowProjection = async (reportDate: string) => {
      const envelope = await orig(reportDate);
      return {
        ...envelope,
        result_meta: {
          ...envelope.result_meta,
          fallback_mode: "latest_snapshot",
          requested_report_date: "2026-03-31",
          resolved_report_date: "2026-03-29",
          as_of_date: "2026-03-29",
          fallback_date: "2026-03-29",
          filters_applied: { report_date: "2026-03-31" },
        },
      };
    };

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CashflowProjectionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const fallbackBanner = await screen.findByTestId("data-section-fallback-banner");
    expect(fallbackBanner).toHaveTextContent("已回退至最近可用日");
    expect(fallbackBanner).toHaveTextContent("回退日 2026-03-29");
    expect(fallbackBanner).not.toHaveTextContent("回退日 2026-03-31");
  });

  it("surfaces candidate metric contract status and source evidence", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CashflowProjectionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const contractPanel = await screen.findByTestId("cashflow-contract-status");

    expect(contractPanel).toHaveTextContent("候选指标");
    expect(contractPanel).toHaveTextContent("PAGE-CFP-001");
    expect(contractPanel).toHaveTextContent("临时例外");
    expect(contractPanel).toHaveTextContent("正式可用: 否");
    expect(contractPanel).toHaveTextContent("口径 analytical");
    expect(contractPanel).toHaveTextContent("质量 warning");
    expect(contractPanel).toHaveTextContent("cashflow_projection.overview");
    expect(contractPanel).toHaveTextContent("cashflow_projection_report_date");
    expect(contractPanel).toHaveTextContent("回退 none");
    expect(contractPanel).toHaveTextContent("请求日");
    expect(contractPanel).toHaveTextContent("解析日");
    expect(contractPanel).toHaveTextContent("数据截至日");
    expect(contractPanel).toHaveTextContent("fact_formal_zqtz_balance_daily");
    expect(contractPanel).toHaveTextContent("fact_formal_tyw_balance_daily");
    expect(contractPanel).toHaveTextContent("证据行 0");

    const dateSourceNote = screen.getByTestId("cashflow-date-source-note");
    expect(dateSourceNote).toHaveTextContent("报告日取自资产负债分析可用日期");
    expect(dateSourceNote).toHaveTextContent("date_basis");
  });
});
