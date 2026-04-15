import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ProductCategoryDatesPayload, ProductCategoryPnlPayload, ProductCategoryPnlRow, ResultMeta } from "../api/contracts";
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

function buildMeta(resultKind: string, traceId: string): ResultMeta {
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
    generated_at: "2026-04-12T08:00:00Z",
  };
}

function rowTemplate(
  partial: Partial<ProductCategoryPnlRow> & Pick<ProductCategoryPnlRow, "category_id" | "category_name" | "level" | "is_total">,
): ProductCategoryPnlRow {
  return {
    side: "asset",
    view: "monthly",
    report_date: "2026-02-28",
    baseline_ftp_rate_pct: "0",
    cnx_scale: "0",
    cny_scale: "0",
    foreign_scale: "0",
    cnx_cash: "0",
    cny_cash: "0",
    foreign_cash: "0",
    cny_ftp: "0",
    foreign_ftp: "0",
    cny_net: "0",
    foreign_net: "0",
    business_net_income: "0",
    weighted_yield: null,
    children: [],
    scenario_rate_pct: null,
    ...partial,
  };
}

describe("TeamPerformancePage", () => {
  it("renders date control, KPI cards, and level-1 contribution table", async () => {
    const base = createApiClient({ mode: "mock" });

    const datesPayload: ProductCategoryDatesPayload = {
      report_dates: ["2026-02-28", "2026-01-31"],
    };

    const grandTotal = rowTemplate({
      category_id: "grand_total",
      category_name: "合计",
      level: 0,
      is_total: true,
      business_net_income: "1000",
      cny_ftp: "12.5",
    });
    const assetTotal = rowTemplate({
      category_id: "asset_total",
      category_name: "资产合计",
      level: 0,
      is_total: true,
      business_net_income: "700",
    });
    const liabilityTotal = rowTemplate({
      category_id: "liability_total",
      category_name: "负债合计",
      level: 0,
      is_total: true,
      side: "liability",
      business_net_income: "300",
    });

    const teamAlpha = rowTemplate({
      category_id: "team_alpha",
      category_name: "Alpha组",
      level: 1,
      is_total: false,
      cny_scale: "1500000",
      business_net_income: "250",
      cny_cash: "10",
      cny_ftp: "99.5",
      cny_net: "248",
      weighted_yield: "0.03125",
    });

    const pnlPayload: ProductCategoryPnlPayload = {
      report_date: "2026-02-28",
      view: "monthly",
      available_views: ["monthly"],
      scenario_rate_pct: null,
      rows: [grandTotal, assetTotal, liabilityTotal, teamAlpha],
      asset_total: assetTotal,
      liability_total: liabilityTotal,
      grand_total: grandTotal,
    };

    const getProductCategoryDates = vi.fn(async () => ({
      result_meta: buildMeta("product_category_pnl.dates", "tr_team_dates"),
      result: datesPayload,
    }));
    const getProductCategoryPnl = vi.fn(async () => ({
      result_meta: buildMeta("product_category_pnl.detail", "tr_team_pnl"),
      result: pnlPayload,
    }));

    renderTeamPerformance({
      ...base,
      getProductCategoryDates,
      getProductCategoryPnl,
    });

    expect(await screen.findByTestId("team-performance-page-title")).toHaveTextContent("团队绩效");
    expect(screen.getByText("团队概览")).toBeInTheDocument();
    expect(screen.getByText("团队贡献")).toBeInTheDocument();

    const monthSelect = await screen.findByLabelText("团队绩效-报表月份");
    expect(monthSelect).toHaveValue("2026-02-28");

    await waitFor(() => {
      expect(getProductCategoryPnl).toHaveBeenCalledWith({
        reportDate: "2026-02-28",
        view: "monthly",
      });
    });

    const kpi = await screen.findByTestId("team-performance-kpi");
    expect(kpi).toHaveTextContent("1000");
    expect(kpi).toHaveTextContent("700");
    expect(kpi).toHaveTextContent("300");
    expect(kpi).toHaveTextContent("1");

    const table = await screen.findByTestId("team-performance-table");
    expect(table).toHaveTextContent("类别名称");
    expect(table).toHaveTextContent("日均规模");
    expect(table).toHaveTextContent("Alpha组");
    expect(table).toHaveTextContent("1500000");
    expect(table).toHaveTextContent("250");
    expect(table).toHaveTextContent("99.5");
    expect(table).toHaveTextContent("248");
    expect(table).toHaveTextContent("0.03125");
  });
});
