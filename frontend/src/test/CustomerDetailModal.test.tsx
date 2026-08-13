import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import CustomerDetailModal from "../features/positions/components/CustomerDetailModal";
import { EM_DASH } from "../utils/format";

vi.mock("../lib/echarts", () => ({
  __esModule: true,
  default: () => <div data-testid="customer-detail-echarts-stub" />,
}));

function resultMeta(resultKind: string): ResultMeta {
  return {
    trace_id: "tr_positions_customer",
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    cache_version: "cv",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T00:00:00Z",
  };
}

function renderModal(client: ReturnType<typeof createApiClient>) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
        })
      }
    >
      <ApiClientProvider client={client}>
        <MemoryRouter>
          <CustomerDetailModal
            open
            customerName="客户A"
            reportDate="2026-03-31"
            onClose={vi.fn()}
          />
        </MemoryRouter>
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("CustomerDetailModal", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders customer holding market values in yi yuan", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getPositionsCustomerDetails: vi.fn(async () => ({
        result_meta: resultMeta("positions.customer.details"),
        result: {
          customer_name: "客户A",
          report_date: "2026-03-31",
          total_market_value: "200000000",
          bond_count: 2,
          items: [
            {
              bond_code: "BOND-1",
              sub_type: "信用债",
              asset_class: "credit",
              market_value: "100000000",
              yield_rate: "0.025",
              maturity_date: "2027-03-31",
              rating: "AAA",
              industry: "金融",
            },
            {
              // 真实数据常见：rating 空串，评级列必须走 EM_DASH 纯文本（无胶囊）。
              bond_code: "BOND-2",
              sub_type: "利率债",
              asset_class: "rates",
              market_value: "100000000",
              yield_rate: "0.031",
              maturity_date: "2028-01-01",
              rating: "",
              industry: "政府",
            },
          ],
        },
      })),
      getPositionsCustomerTrend: vi.fn(async () => ({
        result_meta: resultMeta("positions.customer.trend"),
        result: {
          customer_name: "客户A",
          start_date: "2026-03-01",
          end_date: "2026-03-31",
          days: 30,
          items: [],
        },
      })),
    };

    renderModal(client);

    const link = await screen.findByTestId("customer-detail-trading-desk-link-BOND-1");
    expect(link).toHaveAttribute(
      "href",
      "/bond-trading-desk?bond_code=BOND-1&report_date=2026-03-31",
    );
    // KPI 总市值是读数（非表格列），保留亿元单位。
    expect(screen.getByText("2.00 亿元")).toBeInTheDocument();

    // 明细表市值单位收进列头（格内裸数）；行内逐格断言避免裸数字多匹配。
    // scroll.y 下 rc-table 会渲染隐藏测量行复制表头文字，故用 getAllByText。
    expect(screen.getAllByText("市值(亿元)").length).toBeGreaterThan(0);
    const bond1Row = link.closest("tr");
    expect(bond1Row).not.toBeNull();
    const bond1Cells = Array.from(bond1Row!.querySelectorAll("td")).map((td) => td.textContent);
    expect(bond1Cells).toEqual([
      "BOND-1",
      "信用债",
      "credit",
      "AAA",
      "金融",
      "1.00",
      "2.50%",
      "2027-03-31",
    ]);
    // 非空评级保留琥珀胶囊。
    expect(bond1Row!.querySelector(".positions-customer-detail__rating")).not.toBeNull();

    // 空串评级渲染 EM_DASH 纯文本，且不得出现空胶囊类。
    const bond2Row = screen
      .getByTestId("customer-detail-trading-desk-link-BOND-2")
      .closest("tr");
    expect(bond2Row).not.toBeNull();
    const bond2Cells = Array.from(bond2Row!.querySelectorAll("td")).map((td) => td.textContent);
    expect(bond2Cells).toEqual([
      "BOND-2",
      "利率债",
      "rates",
      EM_DASH,
      "政府",
      "1.00",
      "3.10%",
      "2028-01-01",
    ]);
    expect(bond2Row!.querySelector(".positions-customer-detail__rating")).toBeNull();

    // 后端已返回未用字段补展示：资产分类列（枚举值原样透出，null→EM_DASH）。
    expect(screen.getAllByText("资产分类").length).toBeGreaterThan(0);
    expect(screen.getByText("credit")).toBeInTheDocument();

    // portal 主题逃逸修复：modalRender 包的 Nocturne scope 容器必须罩住弹窗内容。
    const scopeHost = screen.getByTestId("positions-customer-detail-scope");
    expect(scopeHost).toHaveAttribute("data-moss-theme-scope", "positions");
    expect(scopeHost.contains(link)).toBe(true);

    // 趋势响应真实窗口原样透出在趋势 tab 头（mock 语义缺陷不在前端修饰）。
    fireEvent.click(screen.getByText("余额趋势"));
    expect(await screen.findByText("窗口 2026-03-01 ~ 2026-03-31")).toBeInTheDocument();
  });
});
