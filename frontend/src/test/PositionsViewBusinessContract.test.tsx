import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type {
  ApiEnvelope,
  BondPositionItem,
  CounterpartyStatsResponse,
  IndustryStatsResponse,
  PageResponse,
  RatingStatsResponse,
  ResultMeta,
} from "../api/contracts";
import PositionsView from "../features/positions/components/PositionsView";
import { EM_DASH } from "../utils/format";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="positions-echarts-stub" />,
}));

function meta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_test",
    vendor_version: "vv_none",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-01-02T00:00:00Z",
  };
}

function envelope<T>(resultKind: string, result: T): ApiEnvelope<T> {
  return { result_meta: meta(resultKind), result };
}

function bondPage(items: BondPositionItem[]): PageResponse<BondPositionItem> {
  return { items, total: items.length, page: 1, page_size: 20 };
}

function bondItem(
  partial: Partial<BondPositionItem> & Pick<BondPositionItem, "bond_code">,
): BondPositionItem {
  return {
    credit_name: "契约测试主体",
    sub_type: "信用债",
    asset_class: "HTM",
    market_value: "100000000.00000000",
    face_value: "100000000.00000000",
    valuation_net_price: "100.00000000",
    yield_rate: "0.03000000",
    ...partial,
  };
}

function counterpartyStats(
  partial: Partial<CounterpartyStatsResponse> = {},
): CounterpartyStatsResponse {
  return {
    start_date: "2026-01-01",
    end_date: "2026-04-30",
    num_days: 120,
    items: [],
    total_amount: "2500000000.00000000",
    total_avg_daily: "1234567890.00000000",
    total_weighted_rate: "0.02550000",
    total_weighted_coupon_rate: "0.03100000",
    total_customers: 12,
    cr10_ratio: "61.5",
    ...partial,
  };
}

function ratingStats(): RatingStatsResponse {
  return {
    start_date: "2026-01-01",
    end_date: "2026-04-30",
    num_days: 120,
    items: [],
    total_amount: "0",
    total_avg_daily: "0",
  };
}

function industryStats(): IndustryStatsResponse {
  return {
    start_date: "2026-01-01",
    end_date: "2026-04-30",
    num_days: 120,
    items: [],
    total_amount: "0",
    total_avg_daily: "0",
  };
}

/** 覆写债券 tab 首屏会触发的全部只读方法，保持用例与共享 mock 组合解耦。 */
function buildBondsClient(bondItems: BondPositionItem[]) {
  const client = createApiClient({ mode: "mock" });
  client.getBalanceAnalysisDates = vi.fn(async () =>
    envelope("balance_analysis.dates", { report_dates: ["2026-04-30"] }),
  );
  client.getPositionsBondSubTypes = vi.fn(async () =>
    envelope("positions.bonds.sub_types", { sub_types: ["Gov"] }),
  );
  client.getPositionsBondsList = vi.fn(
    async (
      options: Parameters<typeof client.getPositionsBondsList>[0],
    ): Promise<ApiEnvelope<PageResponse<BondPositionItem>>> =>
      envelope("positions.bonds.list", {
        items: bondItems,
        total: bondItems.length,
        page: options.page,
        page_size: options.pageSize,
      }),
  );
  client.getPositionsCounterpartyBonds = vi.fn(async () =>
    envelope("positions.counterparty.bonds", counterpartyStats()),
  );
  client.getPositionsStatsRating = vi.fn(async () =>
    envelope("positions.stats.rating", ratingStats()),
  );
  client.getPositionsStatsIndustry = vi.fn(async () =>
    envelope("positions.stats.industry", industryStats()),
  );
  return client;
}

function renderPositionsWithClient(client: ReturnType<typeof createApiClient>) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <MemoryRouter initialEntries={["/positions"]}>
          <PositionsView />
        </MemoryRouter>
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("PositionsView business contract", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("requests the bonds list with includeIssued=false and null sub-type by default", async () => {
    const client = buildBondsClient(bondPage([bondItem({ bond_code: "CONTRACT-001" })]).items);

    renderPositionsWithClient(client);

    await waitFor(() =>
      expect(client.getPositionsBondsList).toHaveBeenCalledWith(
        expect.objectContaining({
          includeIssued: false,
          subType: null,
          reportDate: "2026-04-30",
          page: 1,
          pageSize: 20,
        }),
      ),
    );
    expect(await screen.findByText("CONTRACT-001")).toBeInTheDocument();
  });

  it("converts yuan decimal strings to 亿元 and decimal rates to half-up percentages", async () => {
    const client = buildBondsClient([
      bondItem({
        bond_code: "UNIT-001",
        market_value: "150000000.00000000",
        yield_rate: "0.03125000",
      }),
    ]);

    renderPositionsWithClient(client);

    const codeCell = await screen.findByText("UNIT-001");
    const row = codeCell.closest("tr");
    expect(row).not.toBeNull();
    // 金额单位收进列头（格内裸数）；scroll.x 渲染隐藏测量行会复制表头，用 AllBy。
    expect(screen.getAllByText("市值(亿元)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("面值(亿元)").length).toBeGreaterThan(0);
    // 行内逐格断言：市值元→亿元裸数（150,000,000 元 = 1.50）；
    // 收益率小数→百分比，half-up 舍入（0.03125 → 3.13%）。
    const cells = Array.from(row!.querySelectorAll("td")).map((td) => td.textContent);
    expect(cells).toEqual([
      "UNIT-001",
      "契约测试主体",
      "信用债",
      "HTM",
      "1.50",
      "1.00",
      "100.00000000",
      "3.13%",
      "打开",
    ]);

    // KPI 横带与列表使用同一套单位换算（区间累计 / 日均 / 加权收益率 / 加权付息率 / 客户数）
    const kpiBand = screen.getByTestId("positions-kpi-band");
    await waitFor(() => expect(kpiBand).toHaveTextContent("25.00 亿元"));
    expect(kpiBand).toHaveTextContent("12.35 亿元");
    expect(kpiBand).toHaveTextContent("2.55%");
    expect(kpiBand).toHaveTextContent("3.10%");
    expect(kpiBand).toHaveTextContent("12 户");
  });

  it("renders EM_DASH for null numeric fields while keeping zero values as real zeros", async () => {
    const client = buildBondsClient([
      bondItem({
        bond_code: "NULL-001",
        credit_name: null,
        sub_type: null,
        asset_class: null,
        market_value: null,
        face_value: null,
        valuation_net_price: null,
        yield_rate: null,
      }),
      bondItem({
        bond_code: "ZERO-001",
        credit_name: "零值主体",
        sub_type: "Gov",
        market_value: "0.00000000",
        valuation_net_price: "0.00000000",
        yield_rate: "0.00000000",
      }),
    ]);

    renderPositionsWithClient(client);

    const nullRow = (await screen.findByText("NULL-001")).closest("tr");
    expect(nullRow).not.toBeNull();
    const nullDashCells = Array.from(nullRow!.querySelectorAll("td")).filter(
      (td) => td.textContent === EM_DASH,
    );
    // 授信主体 / 业务种类 / 市值 / 估值净价 / 收益率 五列缺失均走 EM_DASH 基元
    expect(nullDashCells.length).toBeGreaterThanOrEqual(5);

    const zeroRow = screen.getByText("ZERO-001").closest("tr");
    expect(zeroRow).not.toBeNull();
    // 0 是真实数值：不得渲染为 EM_DASH（null 与 0 语义区分）。
    // 市值列裸数 "0.00"（单位在列头），逐格断言避免裸数字多匹配。
    const zeroCells = Array.from(zeroRow!.querySelectorAll("td")).map((td) => td.textContent);
    expect(zeroCells).toEqual([
      "ZERO-001",
      "零值主体",
      "Gov",
      "HTM",
      "0.00",
      "1.00",
      "0.00000000",
      "0.00%",
      "打开",
    ]);
    const zeroDashCells = Array.from(zeroRow!.querySelectorAll("td")).filter(
      (td) => td.textContent === EM_DASH,
    );
    expect(zeroDashCells).toHaveLength(0);
  });

  it("applies one sub-type filter consistently across list, counterparty stats, and rating stats", async () => {
    const client = buildBondsClient([bondItem({ bond_code: "FILTER-001" })]);

    renderPositionsWithClient(client);
    expect(await screen.findByText("FILTER-001")).toBeInTheDocument();
    await waitFor(() =>
      expect(client.getPositionsBondsList).toHaveBeenCalledWith(
        expect.objectContaining({ subType: null }),
      ),
    );

    const subTypeSelect = await screen.findByTestId("positions-bond-subtype-select");
    fireEvent.mouseDown(subTypeSelect.querySelector(".ant-select-selector") ?? subTypeSelect);
    fireEvent.click(await screen.findByTitle("Gov"));

    // 同一筛选值必须同步作用于：明细列表、授信主体统计、评级分布统计
    await waitFor(() => {
      expect(client.getPositionsBondsList).toHaveBeenCalledWith(
        expect.objectContaining({ subType: "Gov", page: 1 }),
      );
      expect(client.getPositionsCounterpartyBonds).toHaveBeenCalledWith(
        expect.objectContaining({ subType: "Gov" }),
      );
      expect(client.getPositionsStatsRating).toHaveBeenCalledWith(
        expect.objectContaining({ subType: "Gov" }),
      );
    });
    // 首屏筛选状态条与主筛选保持一致
    expect(screen.getByTestId("positions-data-status")).toHaveTextContent("Gov");
  });
});
