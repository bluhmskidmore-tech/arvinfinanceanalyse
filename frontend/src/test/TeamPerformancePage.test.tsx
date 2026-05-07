import { useState, type ReactNode } from "react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  PnlByBusinessYtdItem,
  PnlByBusinessYtdPayload,
  PnlDatesPayload,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
  ResultMeta,
} from "../api/contracts";
import TeamPerformancePage from "../features/team-performance/TeamPerformancePage";

function renderTeamPerformance(client: ApiClient) {
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
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(
    <Wrapper>
      <TeamPerformancePage />
    </Wrapper>,
  );
}

function buildMeta(
  resultKind: string,
  traceId: string,
  overrides: Partial<ResultMeta> = {},
): ResultMeta {
  return {
    trace_id: traceId,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_team_test",
    vendor_version: "vv_none",
    rule_version: "rv_team_test",
    cache_version: "cv_team_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-05-07T08:00:00Z",
    ...overrides,
  };
}

function byBusinessRow(
  partial: Partial<PnlByBusinessYtdItem> & Pick<PnlByBusinessYtdItem, "row_key" | "business_type">,
): PnlByBusinessYtdItem {
  return {
    row_key: partial.row_key,
    sort_order: partial.sort_order ?? 1,
    business_type: partial.business_type,
    interest_income: partial.interest_income ?? "0",
    fair_value_change: partial.fair_value_change ?? "0",
    capital_gain: partial.capital_gain ?? "0",
    manual_adjustment: partial.manual_adjustment ?? "0",
    total_pnl: partial.total_pnl ?? "0",
    current_balance: partial.current_balance ?? "0",
    balance_yield_pct: partial.balance_yield_pct ?? null,
    source_kind: partial.source_kind ?? "formal",
    source_note: partial.source_note ?? null,
    proportion: partial.proportion ?? null,
    assets_count: partial.assets_count ?? 0,
  };
}

function productRow(
  partial: Partial<ProductCategoryPnlRow> &
    Pick<ProductCategoryPnlRow, "category_id" | "category_name" | "level" | "is_total">,
): ProductCategoryPnlRow {
  return {
    category_id: partial.category_id,
    category_name: partial.category_name,
    side: partial.side ?? "asset",
    level: partial.level,
    view: partial.view ?? "ytd",
    report_date: partial.report_date ?? "2025-12-31",
    baseline_ftp_rate_pct: partial.baseline_ftp_rate_pct ?? "0",
    cnx_scale: partial.cnx_scale ?? "0",
    cny_scale: partial.cny_scale ?? "0",
    foreign_scale: partial.foreign_scale ?? "0",
    cnx_cash: partial.cnx_cash ?? "0",
    cny_cash: partial.cny_cash ?? "0",
    foreign_cash: partial.foreign_cash ?? "0",
    cny_ftp: partial.cny_ftp ?? "0",
    foreign_ftp: partial.foreign_ftp ?? "0",
    cny_net: partial.cny_net ?? "0",
    foreign_net: partial.foreign_net ?? "0",
    business_net_income: partial.business_net_income ?? "0",
    weighted_yield: partial.weighted_yield ?? null,
    is_total: partial.is_total,
    children: partial.children ?? [],
    scenario_rate_pct: partial.scenario_rate_pct ?? null,
  };
}

function emptyProductPayload(): ProductCategoryPnlPayload {
  const grand = productRow({
    category_id: "grand_total",
    category_name: "合计",
    level: 0,
    is_total: true,
  });
  const asset = productRow({
    category_id: "asset_total",
    category_name: "资产合计",
    level: 0,
    is_total: true,
  });
  const liability = productRow({
    category_id: "liability_total",
    category_name: "负债合计",
    side: "liability",
    level: 0,
    is_total: true,
  });

  return {
    report_date: "2025-12-31",
    view: "ytd",
    available_views: ["ytd"],
    scenario_rate_pct: null,
    rows: [],
    asset_total: asset,
    liability_total: liability,
    grand_total: grand,
  };
}

describe("TeamPerformancePage", () => {
  it("locks to 2025-12-31 and renders the matrix, detail panel, warnings, and meta evidence", async () => {
    const base = createApiClient({ mode: "mock" });
    const user = userEvent.setup();

    const getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("pnl.dates", "trace-dates"),
      result: {
        report_dates: ["2026-03-31", "2025-12-31"],
        formal_fi_report_dates: ["2025-12-31"],
        nonstd_bridge_report_dates: ["2025-12-31"],
      } satisfies PnlDatesPayload,
    }));

    const getPnlByBusinessYtd = vi.fn(async () => ({
      result_meta: buildMeta("pnl.by_business_ytd", "trace-by-business", {
        fallback_mode: "latest_snapshot",
      }),
      result: {
        year: 2025,
        period_type: "yearly",
        period_label: "2025 年累计",
        period_start_date: "2025-01-01",
        period_end_date: "2025-12-31",
        total_pnl: "12000000",
        source_tables: ["fact_formal_pnl_fi"],
        items: [
          byBusinessRow({
            row_key: "asset_zqtz_detail_structured_finance_broker",
            business_type: "其中：结构化融资（券商）",
            total_pnl: "3500000",
            current_balance: "800000000",
          }),
          byBusinessRow({
            row_key: "asset_zqtz_nonfinancial_enterprise_bond",
            business_type: "非金融企业债券",
            total_pnl: "2600000",
            current_balance: "650000000",
          }),
          byBusinessRow({
            row_key: "asset_zqtz_public_fund",
            business_type: "公募基金",
            total_pnl: "1800000",
            current_balance: "420000000",
          }),
          byBusinessRow({
            row_key: "asset_zqtz_policy_financial_bond",
            business_type: "政策性金融债",
            total_pnl: "5000000",
            current_balance: "1200000000",
          }),
          byBusinessRow({
            row_key: "asset_zqtz_local_government_bond",
            business_type: "地方政府债",
            total_pnl: "3100000",
            current_balance: "900000000",
          }),
          byBusinessRow({
            row_key: "asset_zqtz_interbank_cd",
            business_type: "同业存单",
            total_pnl: "1600000",
            current_balance: "500000000",
          }),
          byBusinessRow({
            row_key: "asset_zqtz_treasury_bond",
            business_type: "国债",
            total_pnl: "2400000",
            current_balance: "730000000",
          }),
          byBusinessRow({
            row_key: "asset_zqtz_railway_bond",
            business_type: "铁道债",
            total_pnl: "900000",
            current_balance: "220000000",
          }),
        ],
      } satisfies PnlByBusinessYtdPayload,
    }));

    const getProductCategoryPnl = vi.fn(async () => ({
      result_meta: buildMeta("product_category_pnl.detail", "trace-product-category", {
        quality_flag: "warning",
      }),
      result: {
        ...emptyProductPayload(),
        rows: [
          productRow({
            category_id: "intermediate_business_income",
            category_name: "中间业务收入",
            level: 1,
            is_total: false,
            business_net_income: "1800000",
          }),
          productRow({
            category_id: "interbank_lending_assets",
            category_name: "拆放同业资产",
            level: 1,
            is_total: false,
            business_net_income: "2200000",
            cny_net: "1500000",
            foreign_net: "700000",
            cny_scale: "900000000",
            foreign_scale: "120000000",
          }),
          productRow({
            category_id: "bond_investment",
            category_name: "债券投资",
            level: 1,
            is_total: false,
            foreign_net: "1100000",
            foreign_scale: "300000000",
          }),
          productRow({
            category_id: "interbank_deposits",
            category_name: "同业存放",
            side: "liability",
            level: 1,
            is_total: false,
            business_net_income: "600000",
            cny_net: "550000",
            foreign_net: "50000",
            cny_scale: "300000000",
          }),
          productRow({
            category_id: "interbank_borrowings",
            category_name: "同业拆入",
            side: "liability",
            level: 1,
            is_total: false,
            business_net_income: "800000",
            cny_net: "600000",
            foreign_net: "200000",
            cny_scale: "200000000",
          }),
          productRow({
            category_id: "repo_liabilities",
            category_name: "卖出回购负债",
            side: "liability",
            level: 1,
            is_total: false,
            business_net_income: "700000",
            cny_net: "650000",
            foreign_net: "50000",
            cny_scale: "500000000",
          }),
          productRow({
            category_id: "interbank_cds",
            category_name: "同业存单负债",
            side: "liability",
            level: 1,
            is_total: false,
            business_net_income: "500000",
            cny_net: "510000",
            foreign_net: "-10000",
            cny_scale: "180000000",
          }),
          productRow({
            category_id: "credit_linked_notes",
            category_name: "信用联结票据",
            side: "liability",
            level: 1,
            is_total: false,
            business_net_income: "400000",
            cny_net: "400000",
            foreign_net: "0",
            cny_scale: "100000000",
          }),
          productRow({
            category_id: "derivatives",
            category_name: "衍生品",
            level: 1,
            is_total: false,
            business_net_income: "-300000",
          }),
        ],
      } satisfies ProductCategoryPnlPayload,
    }));

    renderTeamPerformance({
      ...base,
      getFormalPnlDates,
      getPnlByBusinessYtd,
      getProductCategoryPnl,
    });

    expect(await screen.findByTestId("team-performance-page-title")).toHaveTextContent(
      "Team Performance 工作损益分析",
    );

    await waitFor(() => {
      expect(getPnlByBusinessYtd).toHaveBeenCalledWith(2025, "2025-12-31");
    });
    await waitFor(() => {
      expect(getProductCategoryPnl).toHaveBeenCalledWith({
        reportDate: "2025-12-31",
        view: "ytd",
      });
    });

    expect(screen.getByLabelText("team-performance-report-year")).toHaveValue("2025");
    expect(screen.getByLabelText("team-performance-report-date")).toHaveValue("2025-12-31");

    const summary = await screen.findByTestId("team-performance-summary-cards");
    expect(summary).toHaveTextContent("409.28");
    expect(summary).toHaveTextContent("8");

    expect(await screen.findByTestId("team-performance-warning-banner")).toHaveTextContent(
      "映射分析不代表正式中心归属",
    );
    expect(screen.getByTestId("team-performance-warning-banner")).toHaveTextContent(
      "latest_snapshot",
    );

    const matrix = await screen.findByTestId("team-performance-center-matrix");
    expect(matrix).toHaveTextContent("产品与市场室");
    expect(matrix).toHaveTextContent("金融同业部");
    expect(matrix).toHaveTextContent("济南分部");
    expect(matrix).toHaveTextContent("挂钩引用");
    expect(matrix).not.toHaveTextContent("负责人");
    expect(matrix).not.toHaveTextContent("江鹏飞");

    const detail = await screen.findByTestId("team-performance-detail");
    expect(detail).toHaveTextContent("产品与市场室 明细");
    expect(detail).toHaveTextContent("映射分析");
    expect(detail).toHaveTextContent("金融投资营业收入");
    expect(detail).toHaveTextContent("asset_zqtz_detail_structured_finance_broker");
    expect(detail).not.toHaveTextContent("江鹏飞");

    await user.click(screen.getAllByRole("button", { name: "金融同业部" })[0]);

    expect(await screen.findByTestId("team-performance-detail")).toHaveTextContent(
      "同业银团贷款中间业务收入",
    );
    expect(screen.getByTestId("team-performance-detail")).toHaveTextContent(
      "interbank_lending_assets",
    );

    const meta = await screen.findByTestId("team-performance-result-meta");
    expect(meta).toHaveTextContent("pnl.by_business_ytd");
    expect(meta).toHaveTextContent("product_category_pnl.detail");

    const q1Caliber = await screen.findByTestId("team-performance-q1-caliber");
    expect(q1Caliber).toHaveTextContent("2026 Q1实际口径拆解");
    expect(q1Caliber).toHaveTextContent("只展示实际证据");
    expect(q1Caliber).toHaveTextContent("自营中心");
    expect(q1Caliber).toHaveTextContent("债券交易室");
    expect(q1Caliber).toHaveTextContent("外汇与衍生品室");
    expect(q1Caliber).toHaveTextContent("外汇远期/掉期归代客交易");
    expect(q1Caliber).not.toHaveTextContent("2026计划");
    expect(q1Caliber).not.toHaveTextContent("完成率");
  });

  it("shows a no-substitution warning when 2025-12-31 is unavailable", async () => {
    const base = createApiClient({ mode: "mock" });
    const getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("pnl.dates", "trace-dates-missing"),
      result: {
        report_dates: ["2026-03-31"],
        formal_fi_report_dates: ["2026-03-31"],
        nonstd_bridge_report_dates: ["2026-03-31"],
      } satisfies PnlDatesPayload,
    }));
    const getPnlByBusinessYtd = vi.fn();
    const getProductCategoryPnl = vi.fn();

    renderTeamPerformance({
      ...base,
      getFormalPnlDates,
      getPnlByBusinessYtd,
      getProductCategoryPnl,
    });

    expect(await screen.findByTestId("team-performance-empty")).toHaveTextContent(
      "正式日期列表未包含 2025-12-31",
    );
    expect(screen.getByLabelText("team-performance-report-date")).toHaveValue("");
    expect(getPnlByBusinessYtd).not.toHaveBeenCalled();
    expect(getProductCategoryPnl).not.toHaveBeenCalled();
  });

  it("renders an empty state when both evidence endpoints return no mapped rows", async () => {
    const base = createApiClient({ mode: "mock" });

    const getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("pnl.dates", "trace-dates-empty"),
      result: {
        report_dates: ["2025-12-31"],
        formal_fi_report_dates: ["2025-12-31"],
        nonstd_bridge_report_dates: ["2025-12-31"],
      } satisfies PnlDatesPayload,
    }));
    const getPnlByBusinessYtd = vi.fn(async () => ({
      result_meta: buildMeta("pnl.by_business_ytd", "trace-by-business-empty"),
      result: {
        year: 2025,
        period_type: "yearly",
        period_label: "2025 年累计",
        period_start_date: "2025-01-01",
        period_end_date: "2025-12-31",
        total_pnl: "0",
        source_tables: ["fact_formal_pnl_fi"],
        items: [],
      } satisfies PnlByBusinessYtdPayload,
    }));
    const getProductCategoryPnl = vi.fn(async () => ({
      result_meta: buildMeta("product_category_pnl.detail", "trace-product-empty"),
      result: emptyProductPayload(),
    }));

    renderTeamPerformance({
      ...base,
      getFormalPnlDates,
      getPnlByBusinessYtd,
      getProductCategoryPnl,
    });

    expect(await screen.findByTestId("team-performance-empty")).toHaveTextContent(
      "未找到可展示的部室工作损益证据",
    );
  });

  it("renders an error state when governed evidence cannot be loaded", async () => {
    const base = createApiClient({ mode: "mock" });

    const getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("pnl.dates", "trace-dates-error"),
      result: {
        report_dates: ["2025-12-31"],
        formal_fi_report_dates: ["2025-12-31"],
        nonstd_bridge_report_dates: ["2025-12-31"],
      } satisfies PnlDatesPayload,
    }));
    const getPnlByBusinessYtd = vi.fn(async () => {
      throw new Error("by-business failed");
    });
    const getProductCategoryPnl = vi.fn(async () => ({
      result_meta: buildMeta("product_category_pnl.detail", "trace-product-ok"),
      result: emptyProductPayload(),
    }));

    renderTeamPerformance({
      ...base,
      getFormalPnlDates,
      getPnlByBusinessYtd,
      getProductCategoryPnl,
    });

    expect(await screen.findByTestId("team-performance-error")).toHaveTextContent(
      "2025 工作损益证据加载失败",
    );
    expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
  });
});
