import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  ApiEnvelope,
  ConcentrationDisplayLimits,
  CreditSpreadMigrationPayload,
  ResultMeta,
} from "../api/contracts";
import { apiQueryKeys } from "../api/queryKeys";
import ConcentrationMonitorPage from "../features/concentration-monitor/ConcentrationMonitorPage";
import { routerFuture } from "../router/routerFuture";
import { EM_DASH, formatRawAsNumeric } from "../utils/format";

const resultMeta: ResultMeta = {
  trace_id: "test_credit_spread_cache_shape",
  basis: "analytical",
  result_kind: "bond_analytics.credit_spread_migration",
  formal_use_allowed: false,
  source_version: "sv_test",
  vendor_version: "vv_test",
  rule_version: "rv_test",
  cache_version: "cv_test",
  quality_flag: "warning",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  requested_report_date: "2026-03-31",
  resolved_report_date: "2026-03-31",
  as_of_date: "2026-03-31",
  date_basis: "bond_analytics_report_date",
  tables_used: ["fact_formal_bond_analytics_daily"],
  filters_applied: {
    report_date: "2026-03-31",
    spread_scenarios: "10,25,50",
  },
  evidence_rows: 10,
  generated_at: "2026-04-12T10:00:00Z",
};

/** 展示限额（后端下发，非风控正式限额）；与后端 CONCENTRATION_DISPLAY_LIMITS 过渡口径一致。 */
const BACKEND_DISPLAY_LIMITS: ConcentrationDisplayLimits = {
  issuer_single_max: 0.1,
  issuer_top5_max: 0.4,
  hhi_warning: 0.15,
  below_aa_max: 0.2,
  credit_weight_max: 0.85,
};

function creditSpreadEnvelope(
  reportDate: string,
): ApiEnvelope<CreditSpreadMigrationPayload> {
  const ratio = (raw: number) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
  const yuan = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
  const bp = (raw: number) => formatRawAsNumeric({ raw, unit: "bp", sign_aware: false });
  const dv01 = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });

  return {
    result_meta: resultMeta,
    result: {
      report_date: reportDate,
      credit_bond_count: 10,
      credit_market_value: yuan(100_000_000),
      credit_weight: ratio(0.2),
      rating_aa_and_below_weight: ratio(0.08),
      spread_dv01: dv01(12),
      weighted_avg_spread: bp(90),
      weighted_avg_spread_duration: ratio(3.2),
      spread_scenarios: [],
      migration_scenarios: [],
      concentration_by_issuer: {
        dimension: "issuer",
        hhi: ratio(0.12),
        top5_concentration: ratio(0.3),
        top_items: [
          {
            name: "Issuer A",
            weight: ratio(0.08),
            market_value: yuan(80_000_000),
          },
        ],
      },
      concentration_by_industry: {
        dimension: "industry",
        hhi: ratio(0.1),
        top5_concentration: ratio(0.25),
        top_items: [],
      },
      concentration_by_rating: {
        dimension: "rating",
        hhi: ratio(0.2),
        top5_concentration: ratio(0.4),
        top_items: [],
      },
      concentration_by_tenor: {
        dimension: "tenor",
        hhi: ratio(0.11),
        top5_concentration: ratio(0.28),
        top_items: [],
      },
      display_limits: BACKEND_DISPLAY_LIMITS,
      oci_credit_exposure: yuan(0),
      oci_spread_dv01: dv01(0),
      oci_sensitivity_25bp: yuan(0),
      warnings: [],
      computed_at: "2026-04-12T00:00:00Z",
    },
  };
}

function creditSpreadEnvelopeWith(
  reportDate: string,
  overrides: Partial<CreditSpreadMigrationPayload>,
): ApiEnvelope<CreditSpreadMigrationPayload> {
  const base = creditSpreadEnvelope(reportDate);
  return { ...base, result: { ...base.result, ...overrides } };
}

function buildClient(envelopeForDate: (reportDate: string) => ApiEnvelope<CreditSpreadMigrationPayload>): ApiClient {
  const base = createApiClient({ mode: "mock" });
  return {
    ...base,
    getBondAnalyticsDates: vi.fn(async () => ({
      result_meta: { ...resultMeta, result_kind: "bond_analytics.dates" },
      result: { report_dates: ["2026-03-31"] },
    })),
    getBondAnalyticsCreditSpreadMigration: vi.fn(async (reportDate: string) =>
      envelopeForDate(reportDate),
    ),
  };
}

function renderConcentrationMonitor(client: ApiClient, queryClient: QueryClient) {
  const router = createMemoryRouter(
    [{ path: "/concentration-monitor", element: <ConcentrationMonitorPage /> }],
    {
      initialEntries: ["/concentration-monitor?report_date=2026-03-31"],
      future: routerFuture,
    },
  );

  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <RouterProvider router={router} future={routerFuture} />
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("ConcentrationMonitorPage", () => {
  it("keeps the shared credit-spread query cache as a full API envelope", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: { ...resultMeta, result_kind: "bond_analytics.dates" },
        result: { report_dates: ["2026-03-31"] },
      })),
      getBondAnalyticsCreditSpreadMigration: vi.fn(async (reportDate: string) =>
        creditSpreadEnvelope(reportDate),
      ),
    };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderConcentrationMonitor(client, queryClient);

    await waitFor(() => {
      expect(client.getBondAnalyticsCreditSpreadMigration).toHaveBeenCalledWith("2026-03-31");
    });

    const cached = queryClient.getQueryData(
      apiQueryKeys.bondAnalyticsCreditSpreadMigration("mock", "2026-03-31"),
    );

    expect(cached).toMatchObject({
      result_meta: expect.objectContaining({
        result_kind: "bond_analytics.credit_spread_migration",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: "warning",
      }),
      result: expect.objectContaining({
        report_date: "2026-03-31",
      }),
    });
  });

  it("surfaces candidate metric contract status and source evidence", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: { ...resultMeta, result_kind: "bond_analytics.dates" },
        result: { report_dates: ["2026-03-31"] },
      })),
      getBondAnalyticsCreditSpreadMigration: vi.fn(async (reportDate: string) =>
        creditSpreadEnvelope(reportDate),
      ),
    };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderConcentrationMonitor(client, queryClient);

    const contractPanel = await waitFor(() => {
      const panel = document.querySelector('[data-testid="concentration-monitor-contract-status"]');
      expect(panel).not.toBeNull();
      return panel as HTMLElement;
    });

    expect(contractPanel).toHaveTextContent("候选指标");
    expect(contractPanel).toHaveTextContent("PAGE-CONTRACT-PENDING:/concentration-monitor");
    expect(contractPanel).toHaveTextContent("正式可用：否");
    expect(contractPanel).toHaveTextContent("口径：分析口径");
    expect(contractPanel).toHaveTextContent("质量：预警");
    expect(contractPanel).toHaveTextContent("bond_analytics.credit_spread_migration");
    expect(contractPanel).toHaveTextContent("bond_analytics_report_date");
    expect(contractPanel).toHaveTextContent("fact_formal_bond_analytics_daily");
    expect(contractPanel).toHaveTextContent("证据行：10");
  });

  it("renders candidate concentration KPI ratios as two-decimal percentages", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: { ...resultMeta, result_kind: "bond_analytics.dates" },
        result: { report_dates: ["2026-03-31"] },
      })),
      getBondAnalyticsCreditSpreadMigration: vi.fn(async (reportDate: string) =>
        creditSpreadEnvelope(reportDate),
      ),
    };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderConcentrationMonitor(client, queryClient);

    const kpiGrid = await waitFor(() => {
      const panel = document.querySelector('[data-testid="concentration-monitor-kpi-grid"]');
      expect(panel).not.toBeNull();
      return panel as HTMLElement;
    });

    expect(kpiGrid).toHaveTextContent("12.00%");
    expect(kpiGrid).toHaveTextContent("30.00%");
    expect(kpiGrid).toHaveTextContent("20.00%");
    expect(kpiGrid).toHaveTextContent("8.00%");
  });

  it("compares metrics against backend-delivered display limits and annotates their origin", async () => {
    const ratio = (raw: number) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
    const yuan = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
    // 限额来自 mock 响应携带的 display_limits（后端下发），非前端常量：
    // 单一发行人 0.12 > 0.1 → 超限；前五 0.35 / 0.4 = 87.5% → 接近限额；
    // HHI 0.10 / 0.15 ≈ 66.7% → 正常；AA 及以下 0.25 > 0.2 → 超限；
    // 信用债占比 0.9 > display_limits.credit_weight_max(0.85) → KPI tone=error。
    const client = buildClient((reportDate) =>
      creditSpreadEnvelopeWith(reportDate, {
        credit_weight: ratio(0.9),
        rating_aa_and_below_weight: ratio(0.25),
        display_limits: BACKEND_DISPLAY_LIMITS,
        concentration_by_issuer: {
          dimension: "issuer",
          hhi: ratio(0.1),
          top5_concentration: ratio(0.35),
          top_items: [
            { name: "Issuer A", weight: ratio(0.12), market_value: yuan(120_000_000) },
          ],
        },
      }),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderConcentrationMonitor(client, queryClient);

    const limitNote = await waitFor(() => {
      const node = document.querySelector('[data-testid="concentration-monitor-limit-note"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });
    expect(limitNote).toHaveTextContent("展示限额（后端下发，非风控正式限额）");
    expect(limitNote).not.toHaveTextContent("前端配置");

    const statusCells = Array.from(
      document.querySelectorAll(".concentration-monitor-page__limit-status"),
    ) as HTMLElement[];
    expect(statusCells.map((cell) => cell.textContent)).toEqual([
      "超限",
      "接近限额",
      "正常",
      "超限",
    ]);
    expect(statusCells.map((cell) => cell.dataset.tone)).toEqual([
      "breach",
      "near",
      "ok",
      "breach",
    ]);

    const kpiGrid = document.querySelector(
      '[data-testid="concentration-monitor-kpi-grid"]',
    ) as HTMLElement;
    const creditWeightCard = Array.from(kpiGrid.querySelectorAll(".kpi-card")).find(
      (card) => card.querySelector(".kpi-card__title-text")?.textContent === "信用债占比",
    ) as HTMLElement;
    expect(creditWeightCard).toBeDefined();
    expect(creditWeightCard.dataset.tone).toBe("error");
  });

  it("renders EM_DASH for missing limit-row values and marks them as no-data", async () => {
    const ratio = (raw: number) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
    const client = buildClient((reportDate) =>
      creditSpreadEnvelopeWith(reportDate, {
        rating_aa_and_below_weight: undefined,
        concentration_by_issuer: {
          dimension: "issuer",
          hhi: ratio(0.12),
          top5_concentration: ratio(0.3),
          top_items: [],
        },
      }),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderConcentrationMonitor(client, queryClient);

    const valueCells = await waitFor(() => {
      const cells = Array.from(
        document.querySelectorAll(".concentration-monitor-page__limit-cell"),
      ) as HTMLElement[];
      expect(cells).toHaveLength(4);
      return cells;
    });

    // 无 top_items → 单一发行人占比缺值；未返回 AA 及以下占比 → 末行缺值。
    expect(valueCells[0].textContent).toBe(EM_DASH);
    expect(valueCells[3].textContent).toBe(EM_DASH);

    const statusCells = Array.from(
      document.querySelectorAll(".concentration-monitor-page__limit-status"),
    ) as HTMLElement[];
    expect(statusCells[3].textContent).toBe("暂无数据");
    expect(statusCells[3].dataset.missing).toBe("true");
  });

  it("shows a limits-not-delivered empty state instead of falling back to frontend constants", async () => {
    const ratio = (raw: number) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
    // 响应缺 display_limits：即便信用债占比 0.9 超过旧前端阈值 0.85，也不得回退前端常量标红。
    const client = buildClient((reportDate) =>
      creditSpreadEnvelopeWith(reportDate, {
        credit_weight: ratio(0.9),
        display_limits: undefined,
      }),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderConcentrationMonitor(client, queryClient);

    const missingSurface = await waitFor(() => {
      const node = document.querySelector(
        '[data-testid="concentration-monitor-limits-missing"]',
      );
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });
    expect(missingSurface).toHaveTextContent("限额未下发");
    expect(missingSurface).toHaveTextContent("不回退前端配置阈值");

    // 限额对照表与「后端下发」标注均不渲染。
    expect(
      document.querySelector('[data-testid="concentration-monitor-limit-note"]'),
    ).toBeNull();
    expect(
      document.querySelectorAll(".concentration-monitor-page__limit-status"),
    ).toHaveLength(0);

    // KPI 不做限额着色：信用债占比 0.9 仍为中性 tone。
    const kpiGrid = document.querySelector(
      '[data-testid="concentration-monitor-kpi-grid"]',
    ) as HTMLElement;
    const creditWeightCard = Array.from(kpiGrid.querySelectorAll(".kpi-card")).find(
      (card) => card.querySelector(".kpi-card__title-text")?.textContent === "信用债占比",
    ) as HTMLElement;
    expect(creditWeightCard).toBeDefined();
    expect(creditWeightCard.dataset.tone).toBe("default");
  });
});
