import { describe, expect, it, test, vi } from "vitest";

import { createApiClient } from "../api/client";

describe("createApiClient", () => {
  it("uses mock mode by default", async () => {
    const client = createApiClient({ mode: "mock" });

    const payload = await client.getOverview();

    expect(payload.result_meta.basis).toBe("mock");
    expect(payload.result.title).toBe("经营总览（演示）");
  });

  it("includes required vendor metadata in mock envelopes", async () => {
    const client = createApiClient({ mode: "mock" });

    const payload = await client.getOverview();

    expect(payload.result_meta.vendor_status).toBe("ok");
    expect(payload.result_meta.fallback_mode).toBe("none");
  });

  it("keeps mock balance-analysis overview, detail, basis, and summary amounts consistent", async () => {
    const client = createApiClient({ mode: "mock" });
    const overview = await client.getBalanceAnalysisOverview({
      reportDate: "2025-12-31",
      positionScope: "all",
      currencyBasis: "CNY",
    });
    const summary = await client.getBalanceAnalysisSummary({
      reportDate: "2025-12-31",
      positionScope: "all",
      currencyBasis: "CNY",
      limit: 10,
      offset: 0,
    });
    const basis = await client.getBalanceAnalysisSummaryByBasis({
      reportDate: "2025-12-31",
      positionScope: "all",
      currencyBasis: "CNY",
    });

    expect(summary.result.rows).toHaveLength(3);
    expect(overview.result.summary_row_count).toBe(summary.result.total_rows);
    expect(overview.result.detail_row_count).toBe(6);
    expect(overview.result.total_market_value_amount).toBe("120200000000.00");
    expect(overview.result.total_amortized_cost_amount).toBe("112300000000.00");
    expect(overview.result.total_accrued_interest_amount).toBe("7040000000.00");

    const detail = await client.getBalanceAnalysisDetail({
      reportDate: "2025-12-31",
      positionScope: "all",
      currencyBasis: "CNY",
    });
    expect(detail.result.details).toHaveLength(6);
    expect(detail.result.summary).toHaveLength(summary.result.rows.length);
    expect(detail.result.summary[0]?.market_value_amount).toBe("72000000000.00");
    expect(detail.result.summary[1]?.market_value_amount).toBe("7200000000.00");
    expect(detail.result.summary[2]?.market_value_amount).toBe("41000000000.00");
    expect(basis.result.rows).toHaveLength(summary.result.rows.length);
    expect(basis.result.rows[2]?.market_value_amount).toBe("41000000000.00");
  });

  it("keeps mock manual-adjustment current state reduced while exposing full timeline", async () => {
    const client = createApiClient({ mode: "mock" });

    const created = await client.createProductCategoryManualAdjustment({
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "approved",
      account_code: "51402010001",
      currency: "CNX",
      account_name: "测试科目",
      monthly_pnl: "5",
    });
    await client.updateProductCategoryManualAdjustment(created.adjustment_id, {
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "approved",
      account_code: "51402010001",
      currency: "CNX",
      account_name: "测试科目",
      monthly_pnl: "8",
    });
    await client.revokeProductCategoryManualAdjustment(created.adjustment_id);

    const payload = await client.getProductCategoryManualAdjustments("2026-02-28");

    expect(payload.adjustments).toHaveLength(1);
    expect(payload.adjustments[0]?.approval_status).toBe("rejected");
    expect(payload.adjustments[0]?.event_type).toBe("revoked");
    expect(payload.events.map((event) => event.event_type)).toEqual([
      "revoked",
      "edited",
      "created",
    ]);
  });

  it("applies backend-parity sort and created_at range rules in mock manual-adjustment queries", async () => {
    const client = createApiClient({ mode: "mock" });

    await client.createProductCategoryManualAdjustment({
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "approved",
      account_code: "300",
      currency: "CNX",
      account_name: "A",
      monthly_pnl: "5",
    });
    const second = await client.createProductCategoryManualAdjustment({
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "pending",
      account_code: "100",
      currency: "CNX",
      account_name: "B",
      monthly_pnl: "6",
    });
    await client.updateProductCategoryManualAdjustment(second.adjustment_id, {
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "approved",
      account_code: "100",
      currency: "CNX",
      account_name: "B",
      monthly_pnl: "7",
    });

    const payload = await client.getProductCategoryManualAdjustments("2026-02-28", {
      currentSortField: "account_code",
      currentSortDir: "asc",
      eventSortField: "adjustment_id",
      eventSortDir: "asc",
      createdAtFrom: "2026-04-10T09:40:00Z",
      createdAtTo: "2026-04-10T09:40:00Z",
    });

    expect(payload.adjustments.map((item) => item.account_code)).toEqual(["100"]);
    expect(payload.events.map((item) => item.adjustment_id)).toEqual([second.adjustment_id]);
    expect(payload.events[0]?.event_type).toBe("edited");
  });

  it("treats eventType as an event-timeline-only filter in mock mode", async () => {
    const client = createApiClient({ mode: "mock" });

    const created = await client.createProductCategoryManualAdjustment({
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "approved",
      account_code: "51402010001",
      currency: "CNX",
      account_name: "测试科目",
      monthly_pnl: "5",
    });
    await client.updateProductCategoryManualAdjustment(created.adjustment_id, {
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "approved",
      account_code: "51402010001",
      currency: "CNX",
      account_name: "测试科目",
      monthly_pnl: "8",
    });
    await client.revokeProductCategoryManualAdjustment(created.adjustment_id);

    const payload = await client.getProductCategoryManualAdjustments("2026-02-28", {
      eventType: "edited",
    });

    expect(payload.adjustments).toHaveLength(1);
    expect(payload.adjustments[0]?.event_type).toBe("revoked");
    expect(payload.events.map((event) => event.event_type)).toEqual(["edited"]);
  });

  it("returns product-category mock rows in the authoritative display order", async () => {
    const client = createApiClient({ mode: "mock" });

    const payload = await client.getProductCategoryPnl({
      reportDate: "2026-02-28",
      view: "monthly",
    });

    expect(payload.result.rows.map((row) => row.category_name)).toEqual([
      "拆放同业",
      "买入返售",
      "债券投资",
      "TPL",
      "AC债券投资",
      "AC其他投资",
      "FVOCI",
      "估值及买卖价差等",
      "生息资产",
      "衍生品",
      "中间业务收入",
      "资产端合计",
      "同业存放",
      "同业拆入",
      "卖出回购",
      "同业存单",
      "信用联结票据",
      "负债端合计",
      "grand_total",
    ]);
  });

  it("uses real mode to fetch executive endpoints", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_overview",
          basis: "formal",
          result_kind: "executive.overview",
          formal_use_allowed: true,
          source_version: "sv_real",
          vendor_version: "vv_none",
          rule_version: "rv_real",
          cache_version: "cv_real",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-09T09:00:00Z",
        },
        result: {
          title: "经营总览",
          metrics: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getOverview();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/home/overview",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch adb comparison from the nested comparison route", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_adb_comparison",
          basis: "analytical",
          result_kind: "adb.comparison",
          formal_use_allowed: false,
          source_version: "sv_adb",
          vendor_version: "vv_none",
          rule_version: "rv_adb",
          cache_version: "cv_adb",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-15T09:00:00Z",
        },
        result: {
          report_date: "2025-06-03",
          start_date: "2025-06-02",
          end_date: "2025-06-03",
          num_days: 2,
          simulated: false,
          total_spot_assets: 250000000,
          total_avg_assets: 175000000,
          total_spot_liabilities: 0,
          total_avg_liabilities: 0,
          asset_yield: 3.3571,
          liability_cost: null,
          net_interest_margin: null,
          assets_breakdown: [],
          liabilities_breakdown: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const payload = await client.getAdbComparison("2025-06-02", "2025-06-03", { topN: 5 });

    expect(payload).not.toHaveProperty("assets");
    expect(payload).not.toHaveProperty("liabilities");
    expect(payload.result_meta?.result_kind).toBe("adb.comparison");
    expect(payload.result_meta?.source_version).toBe("sv_adb");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/analysis/adb/comparison?start_date=2025-06-02&end_date=2025-06-03&top_n=5",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch ledger pnl dates, summary, and detail payloads", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_ledger_dates",
            basis: "formal",
            result_kind: "ledger_pnl.dates",
            formal_use_allowed: true,
            source_version: "sv_ledger_dates",
            vendor_version: "vv_none",
            rule_version: "rv_ledger",
            cache_version: "cv_ledger",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-17T00:00:00Z",
          },
          result: { dates: ["2025-12-31"] },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_ledger_summary",
            basis: "formal",
            result_kind: "ledger_pnl.summary",
            formal_use_allowed: true,
            source_version: "sv_ledger_summary",
            vendor_version: "vv_none",
            rule_version: "rv_ledger",
            cache_version: "cv_ledger",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-17T00:00:00Z",
          },
          result: {
            report_date: "2025-12-31",
            source_version: "sv_ledger_summary",
            ledger_total_assets: { yuan: "10.00", yi: "0.00", wan: "0.00" },
            ledger_total_liabilities: { yuan: "5.00", yi: "0.00", wan: "0.00" },
            ledger_net_assets: { yuan: "5.00", yi: "0.00", wan: "0.00" },
            ledger_monthly_pnl_core: { yuan: "1.00", yi: "0.00", wan: "0.00" },
            ledger_monthly_pnl_all: { yuan: "2.00", yi: "0.00", wan: "0.00" },
            by_currency: [],
            by_account: [],
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_ledger_data",
            basis: "formal",
            result_kind: "ledger_pnl.data",
            formal_use_allowed: true,
            source_version: "sv_ledger_data",
            vendor_version: "vv_none",
            rule_version: "rv_ledger",
            cache_version: "cv_ledger",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-17T00:00:00Z",
          },
          result: {
            report_date: "2025-12-31",
            items: [],
            summary: {
              total_pnl_cnx: { yuan: "1.00", yi: "0.00", wan: "0.00" },
              total_pnl_cny: { yuan: "0.00", yi: "0.00", wan: "0.00" },
              total_pnl: { yuan: "1.00", yi: "0.00", wan: "0.00" },
              count: 0,
            },
          },
        }),
      });

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getLedgerPnlDates();
    await client.getLedgerPnlSummary("2025-12-31", "CNX");
    await client.getLedgerPnlData("2025-12-31", "CNX");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/ledger-pnl/dates",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/ledger-pnl/summary?date=2025-12-31&currency=CNX",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/api/ledger-pnl/data?date=2025-12-31&currency=CNX",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
  });

  it("uses real mode to fetch detailed Campisi drill-down endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_campisi_four",
            basis: "formal",
            result_kind: "campisi.four_effects",
            formal_use_allowed: true,
            source_version: "sv_campisi",
            vendor_version: "vv_none",
            rule_version: "rv_campisi",
            cache_version: "cv_campisi",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-17T00:00:00Z",
          },
          result: {
            report_date: "2026-03-31",
            period_start: "2026-03-01",
            period_end: "2026-03-31",
            num_days: 30,
            totals: {
              income_return: 1,
              treasury_effect: 2,
              spread_effect: 3,
              selection_effect: 4,
              total_return: 10,
              market_value_start: 100,
            },
            by_asset_class: [],
            by_bond: [],
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_campisi_enhanced",
            basis: "formal",
            result_kind: "campisi.enhanced",
            formal_use_allowed: true,
            source_version: "sv_campisi",
            vendor_version: "vv_none",
            rule_version: "rv_campisi",
            cache_version: "cv_campisi",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-17T00:00:00Z",
          },
          result: {
            report_date: "2026-03-31",
            period_start: "2026-03-01",
            period_end: "2026-03-31",
            num_days: 30,
            totals: {
              income_return: 1,
              treasury_effect: 2,
              spread_effect: 3,
              convexity_effect: 0.2,
              cross_effect: 0.1,
              reinvestment_effect: 0,
              selection_effect: 4,
              total_return: 10,
              market_value_start: 100,
            },
            by_asset_class: [],
            by_bond: [],
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_campisi_bucket",
            basis: "formal",
            result_kind: "campisi.maturity_buckets",
            formal_use_allowed: true,
            source_version: "sv_campisi",
            vendor_version: "vv_none",
            rule_version: "rv_campisi",
            cache_version: "cv_campisi",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-17T00:00:00Z",
          },
          result: {
            period_start: "2026-03-01",
            period_end: "2026-03-31",
            buckets: {
              "0-1Y": {
                market_value_start: 100,
                income_return: 1,
                treasury_effect: 2,
                spread_effect: 3,
                selection_effect: 4,
                total_return: 10,
              },
            },
          },
        }),
      });

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getPnlCampisiFourEffects({ endDate: "2026-03-31", lookbackDays: 30 });
    await client.getPnlCampisiEnhanced({ endDate: "2026-03-31", lookbackDays: 30 });
    await client.getPnlCampisiMaturityBuckets({ endDate: "2026-03-31", lookbackDays: 30 });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/pnl-attribution/campisi/four-effects?end_date=2026-03-31&lookback_days=30",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/pnl-attribution/campisi/enhanced?end_date=2026-03-31&lookback_days=30",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/api/pnl-attribution/campisi/maturity-buckets?end_date=2026-03-31&lookback_days=30",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
  });

  it("uses real mode to fetch source preview foundation endpoint", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_preview",
          basis: "analytical",
          result_kind: "preview.source-foundation",
          formal_use_allowed: false,
          source_version: "sv_preview",
          vendor_version: "vv_none",
          rule_version: "rv_preview",
          cache_version: "cv_preview",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-09T09:00:00Z",
        },
        result: {
          sources: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getSourceFoundation();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/preview/source-foundation",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("returns bond analytics mock envelopes for the unified detail readers", async () => {
    const client = createApiClient({ mode: "mock" });

    const returnDecomposition = await client.getBondAnalyticsReturnDecomposition(
      "2026-03-31",
      "MoM",
    );
    const benchmarkExcess = await client.getBondAnalyticsBenchmarkExcess(
      "2026-03-31",
      "MoM",
      "CDB_INDEX",
    );
    const actionAttribution = await client.getBondAnalyticsActionAttribution(
      "2026-03-31",
      "MoM",
    );
    const accountingAudit = await client.getBondAnalyticsAccountingClassAudit("2026-03-31");
    const portfolioHeadlines = await client.getBondAnalyticsPortfolioHeadlines("2026-03-31");
    const topHoldings = await client.getBondAnalyticsTopHoldings("2026-03-31", 15);

    expect(returnDecomposition.result_meta.result_kind).toBe("bond_analytics.return_decomposition");
    expect(returnDecomposition.result.report_date).toBe("2026-03-31");
    expect(benchmarkExcess.result.benchmark_id).toBe("CDB_INDEX");
    expect(actionAttribution.result_meta.result_kind).toBe("bond_analytics.action_attribution");
    expect(accountingAudit.result_meta.result_kind).toBe("bond_analytics.accounting_class_audit");
    expect(portfolioHeadlines.result_meta.result_kind).toBe("bond_analytics.portfolio_headlines");
    expect(topHoldings.result_meta.result_kind).toBe("bond_analytics.top_holdings");
    expect(topHoldings.result.top_n).toBe(15);
  });

  it("uses real mode to fetch unified bond analytics detail readers", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_rd",
            basis: "formal",
            result_kind: "bond_analytics.return_decomposition",
            formal_use_allowed: true,
            source_version: "sv_rd",
            vendor_version: "vv_rd",
            rule_version: "rv_rd",
            cache_version: "cv_rd",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-13T00:00:00Z",
          },
          result: {
            report_date: "2026-03-31",
            period_type: "MoM",
            period_start: "2026-03-01",
            period_end: "2026-03-31",
            carry: "0",
            roll_down: "0",
            rate_effect: "0",
            spread_effect: "0",
            trading: "0",
            fx_effect: "0",
            convexity_effect: "0",
            explained_pnl: "0",
            explained_pnl_accounting: "0",
            explained_pnl_economic: "0",
            oci_reserve_impact: "0",
            actual_pnl: "0",
            recon_error: "0",
            recon_error_pct: "0",
            by_asset_class: [],
            by_accounting_class: [],
            bond_details: [],
            bond_count: 0,
            total_market_value: "0",
            warnings: [],
            computed_at: "2026-04-13T00:00:00Z",
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_be",
            basis: "formal",
            result_kind: "bond_analytics.benchmark_excess",
            formal_use_allowed: true,
            source_version: "sv_be",
            vendor_version: "vv_be",
            rule_version: "rv_be",
            cache_version: "cv_be",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-13T00:00:00Z",
          },
          result: {
            report_date: "2026-03-31",
            period_type: "MoM",
            period_start: "2026-03-01",
            period_end: "2026-03-31",
            portfolio_return: "0",
            benchmark_return: "0",
            excess_return: "0",
            tracking_error: null,
            information_ratio: null,
            duration_effect: "0",
            curve_effect: "0",
            spread_effect: "0",
            selection_effect: "0",
            allocation_effect: "0",
            explained_excess: "0",
            recon_error: "0",
            portfolio_duration: "0",
            benchmark_duration: "0",
            duration_diff: "0",
            excess_sources: [],
            benchmark_id: "CDB_INDEX",
            benchmark_name: "中债国开债总指数",
            warnings: [],
            computed_at: "2026-04-13T00:00:00Z",
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_aa",
            basis: "formal",
            result_kind: "bond_analytics.action_attribution",
            formal_use_allowed: true,
            source_version: "sv_aa",
            vendor_version: "vv_aa",
            rule_version: "rv_aa",
            cache_version: "cv_aa",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-13T00:00:00Z",
          },
          result: {
            report_date: "2026-03-31",
            period_type: "MoM",
            period_start: "2026-03-01",
            period_end: "2026-03-31",
            total_actions: 0,
            total_pnl_from_actions: "0",
            by_action_type: [],
            action_details: [],
            period_start_duration: "0",
            period_end_duration: "0",
            duration_change_from_actions: "0",
            period_start_dv01: "0",
            period_end_dv01: "0",
            warnings: [],
            computed_at: "2026-04-13T00:00:00Z",
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_ac",
            basis: "formal",
            result_kind: "bond_analytics.accounting_class_audit",
            formal_use_allowed: true,
            source_version: "sv_ac",
            vendor_version: "vv_ac",
            rule_version: "rv_ac",
            cache_version: "cv_ac",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-13T00:00:00Z",
          },
          result: {
            report_date: "2026-03-31",
            total_positions: 0,
            total_market_value: "0",
            distinct_asset_classes: 0,
            divergent_asset_classes: 0,
            divergent_position_count: 0,
            divergent_market_value: "0",
            map_unclassified_asset_classes: 0,
            map_unclassified_position_count: 0,
            map_unclassified_market_value: "0",
            rows: [],
            warnings: [],
            computed_at: "2026-04-13T00:00:00Z",
          },
        }),
      });

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getBondAnalyticsReturnDecomposition("2026-03-31", "MoM");
    await client.getBondAnalyticsBenchmarkExcess("2026-03-31", "MoM", "CDB_INDEX");
    await client.getBondAnalyticsActionAttribution("2026-03-31", "MoM");
    await client.getBondAnalyticsAccountingClassAudit("2026-03-31");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/bond-analytics/return-decomposition?report_date=2026-03-31&period_type=MoM",
      expect.objectContaining({ headers: expect.objectContaining({ Accept: "application/json" }) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/bond-analytics/benchmark-excess?report_date=2026-03-31&period_type=MoM&benchmark_id=CDB_INDEX",
      expect.objectContaining({ headers: expect.objectContaining({ Accept: "application/json" }) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/api/bond-analytics/action-attribution?report_date=2026-03-31&period_type=MoM",
      expect.objectContaining({ headers: expect.objectContaining({ Accept: "application/json" }) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://localhost:8000/api/bond-analytics/accounting-class-audit?report_date=2026-03-31",
      expect.objectContaining({ headers: expect.objectContaining({ Accept: "application/json" }) }),
    );
  });

  it("returns a structured analytical macro-bond-linkage mock envelope", async () => {
    const client = createApiClient({ mode: "mock" });

    const payload = await client.getMacroBondLinkageAnalysis({
      reportDate: "2026-04-10",
    });

    expect(payload.result_meta.basis).toBe("analytical");
    expect(payload.result_meta.formal_use_allowed).toBe(false);
    expect(payload.result.report_date).toBe("2026-04-10");
    expect(payload.result.top_correlations).not.toHaveLength(0);
    expect(payload.result.top_correlations[0]).toEqual(
      expect.objectContaining({
        target_family: expect.any(String),
        target_tenor: expect.anything(),
      }),
    );
    expect(payload.result.top_correlations).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          target_family: "credit_spread",
          target_tenor: "5Y",
        }),
      ]),
    );
  });

  it("uses real mode to fetch macro-bond-linkage analysis", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_macro_bond_linkage",
          basis: "analytical",
          result_kind: "macro_bond_linkage.analysis",
          formal_use_allowed: false,
          source_version: "sv_macro_bond_linkage",
          vendor_version: "vv_choice_macro",
          rule_version: "rv_macro_bond_linkage_v1",
          cache_version: "cv_macro_bond_linkage_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-13T00:00:00Z",
        },
        result: {
          report_date: "2026-04-10",
          environment_score: {},
          portfolio_impact: {},
          top_correlations: [],
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getMacroBondLinkageAnalysis({
      reportDate: "2026-04-10",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/macro-bond-linkage/analysis?report_date=2026-04-10",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("keeps formal FX status separate from analytical FX observations in mock mode", async () => {
    const client = createApiClient({ mode: "mock" });

    const formalPayload = await client.getFxFormalStatus();
    const analyticalPayload = await client.getFxAnalytical();

    expect(formalPayload.result_meta.basis).toBe("formal");
    expect(formalPayload.result_meta.formal_use_allowed).toBe(true);
    expect(formalPayload.result.read_target).toBe("duckdb");
    expect(formalPayload.result.rows.length).toBeGreaterThan(0);

    expect(analyticalPayload.result_meta.basis).toBe("analytical");
    expect(analyticalPayload.result_meta.formal_use_allowed).toBe(false);
    expect(analyticalPayload.result.read_target).toBe("duckdb");
    expect(analyticalPayload.result.groups.length).toBeGreaterThan(0);
  });

  it("uses real mode to fetch formal FX status and analytical FX observation endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_fx_formal",
            basis: "formal",
            result_kind: "fx.formal.status",
            formal_use_allowed: true,
            source_version: "sv_fx_formal",
            vendor_version: "vv_fx_formal",
            rule_version: "rv_fx_formal",
            cache_version: "cv_fx_formal",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-12T09:00:00Z",
          },
          result: {
            read_target: "duckdb",
            vendor_priority: ["choice", "akshare", "fail_closed"],
            candidate_count: 2,
            materialized_count: 2,
            latest_trade_date: "2026-04-11",
            carry_forward_count: 0,
            rows: [],
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_fx_analytical",
            basis: "analytical",
            result_kind: "fx.analytical.groups",
            formal_use_allowed: false,
            source_version: "sv_fx_analytical",
            vendor_version: "vv_fx_analytical",
            rule_version: "rv_fx_analytical",
            cache_version: "cv_fx_analytical",
            quality_flag: "warning",
            vendor_status: "ok",
            fallback_mode: "latest_snapshot",
            scenario_flag: false,
            generated_at: "2026-04-12T09:05:00Z",
          },
          result: {
            read_target: "duckdb",
            groups: [],
          },
        }),
      });

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getFxFormalStatus();
    await client.getFxAnalytical();

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/ui/market-data/fx/formal-status",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/ui/market-data/fx/analytical",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch source preview history endpoint", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_preview_history",
          basis: "analytical",
          result_kind: "preview.source-foundation.history",
          formal_use_allowed: false,
          source_version: "sv_preview_history",
          vendor_version: "vv_none",
          rule_version: "rv_preview",
          cache_version: "cv_preview",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-09T09:00:00Z",
        },
        result: {
          limit: 50,
          offset: 0,
          total_rows: 1,
          rows: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getSourceFoundationHistory({ limit: 50, offset: 0, sourceFamily: "zqtz" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/preview/source-foundation/history?source_family=zqtz&limit=50&offset=0",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch source preview row and trace drilldown endpoints", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_preview_rows",
          basis: "analytical",
          result_kind: "preview.zqtz.rows",
          formal_use_allowed: false,
          source_version: "sv_preview_rows",
          vendor_version: "vv_none",
          rule_version: "rv_preview",
          cache_version: "cv_preview",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-09T09:00:00Z",
        },
        result: {
          source_family: "zqtz",
          ingest_batch_id: "ib_demo",
          limit: 10,
          offset: 0,
          total_rows: 1,
          rows: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getSourceFoundationRows({
      sourceFamily: "zqtz",
      ingestBatchId: "ib_demo",
      limit: 10,
      offset: 0,
    });
    await client.getSourceFoundationTraces({
      sourceFamily: "zqtz",
      ingestBatchId: "ib_demo",
      limit: 10,
      offset: 0,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/ui/preview/source-foundation/zqtz/rows?ingest_batch_id=ib_demo&limit=10&offset=0",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/ui/preview/source-foundation/zqtz/traces?ingest_batch_id=ib_demo&limit=10&offset=0",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
  });

  it("uses real mode to trigger source preview refresh", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        status: "queued",
        run_id: "source_preview_refresh:test-run",
        job_name: "source_preview_refresh",
        trigger_mode: "async",
        cache_key: "source_preview.foundation",
        preview_sources: ["zqtz", "tyw"],
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.refreshSourcePreview();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/preview/source-foundation/refresh",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch source preview refresh status", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        status: "completed",
        run_id: "source_preview_refresh:test-run",
        job_name: "source_preview_refresh",
        trigger_mode: "terminal",
        cache_key: "source_preview.foundation",
        preview_sources: ["zqtz", "tyw"],
        source_version: "sv_preview_test",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getSourcePreviewRefreshStatus("source_preview_refresh:test-run");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/preview/source-foundation/refresh-status?run_id=source_preview_refresh%3Atest-run",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("surfaces backend detail for failed action requests", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 409,
      json: async () => ({
        detail: {
          error_message: "Source preview refresh already in progress.",
          run_id: "source_preview_refresh:inflight",
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await expect(client.refreshSourcePreview()).rejects.toMatchObject({
      message: "Source preview refresh already in progress.",
      name: "ActionRequestError",
      status: 409,
      runId: "source_preview_refresh:inflight",
      errorMessage: "Source preview refresh already in progress.",
    });
  });

  it("preserves run_id on failed action responses when backend embeds it in detail", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 503,
      json: async () => ({
        detail: {
          error_message: "Source preview refresh queue dispatch failed.",
          run_id: "source_preview_refresh:failed-503",
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await expect(client.refreshSourcePreview()).rejects.toEqual(
      expect.objectContaining({
        name: "ActionRequestError",
        message: "Source preview refresh queue dispatch failed.",
        status: 503,
        runId: "source_preview_refresh:failed-503",
      }),
    );
  });

  it("preserves top-level run_id on failed action responses", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 503,
      json: async () => ({
        detail: "Pnl refresh queue dispatch failed.",
        run_id: "pnl_materialize:top-level",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await expect(client.refreshFormalPnl()).rejects.toEqual(
      expect.objectContaining({
        name: "ActionRequestError",
        message: "Pnl refresh queue dispatch failed.",
        runId: "pnl_materialize:top-level",
      }),
    );
  });

  it("preserves run_id from nested detail only on formal pnl refresh failure", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 503,
      json: async () => ({
        detail: {
          error_message: "Pnl refresh queue dispatch failed.",
          run_id: "pnl_materialize:nested-detail-only",
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await expect(client.refreshFormalPnl()).rejects.toEqual(
      expect.objectContaining({
        name: "ActionRequestError",
        message: "Pnl refresh queue dispatch failed.",
        status: 503,
        runId: "pnl_materialize:nested-detail-only",
        errorMessage: "Pnl refresh queue dispatch failed.",
      }),
    );
  });

  it("surfaces FastAPI validation detail arrays for failed action requests", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      json: async () => ({
        detail: [
          { loc: ["query", "report_date"], msg: "invalid date", type: "value_error" },
        ],
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await expect(client.refreshFormalPnl()).rejects.toThrow("invalid date");
  });

  it("uses real mode to trigger formal pnl refresh", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        status: "queued",
        run_id: "pnl_materialize:test-run",
        job_name: "pnl_materialize",
        trigger_mode: "async",
        cache_key: "pnl:phase2:materialize:formal",
        report_date: "2026-02-28",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.refreshFormalPnl();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/data/refresh_pnl",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch formal pnl refresh status by run id", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        status: "completed",
        run_id: "pnl_materialize:test-run",
        job_name: "pnl_materialize",
        trigger_mode: "terminal",
        cache_key: "pnl:phase2:materialize:formal",
        source_version: "sv_pnl_test",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getFormalPnlImportStatus("pnl_materialize:test-run");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/data/import_status/pnl?run_id=pnl_materialize%3Atest-run",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("filters and paginates Choice news events in mock mode", async () => {
    const client = createApiClient({ mode: "mock" });

    const filtered = await client.getChoiceNewsEvents({
      limit: 5,
      offset: 0,
      groupId: "news_cmd1",
      topicCode: "S888010007API",
    });
    const paged = await client.getChoiceNewsEvents({
      limit: 2,
      offset: 2,
    });
    const errorOnly = await client.getChoiceNewsEvents({
      limit: 5,
      offset: 0,
      errorOnly: true,
    });

    expect(filtered.result.total_rows).toBe(1);
    expect(filtered.result.events[0]?.topic_code).toBe("S888010007API");
    expect(paged.result.total_rows).toBe(8);
    expect(paged.result.events[0]?.event_key).toBe("ce_mock_003");
    expect(errorOnly.result.total_rows).toBe(1);
    expect(errorOnly.result.events[0]?.error_code).toBe(101);
  });

  it("uses real mode to fetch Choice news events with filters", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_choice_news",
          basis: "analytical",
          result_kind: "news.choice.latest",
          formal_use_allowed: false,
          source_version: "sv_choice_news",
          vendor_version: "vv_none",
          rule_version: "rv_choice_news_v1",
          cache_version: "cv_choice_news_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-10T09:00:00Z",
        },
        result: {
          total_rows: 1,
          limit: 2,
          offset: 0,
          events: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getChoiceNewsEvents({
      limit: 2,
      offset: 0,
      groupId: "news_cmd1",
      topicCode: "S888010007API",
      errorOnly: true,
      receivedFrom: "2026-04-10T08:00:00Z",
      receivedTo: "2026-04-10T10:00:00Z",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/news/choice-events/latest?limit=2&offset=0&group_id=news_cmd1&topic_code=S888010007API&error_only=true&received_from=2026-04-10T08%3A00%3A00Z&received_to=2026-04-10T10%3A00%3A00Z",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch macro foundation preview", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_macro_foundation",
          basis: "analytical",
          result_kind: "preview.macro-foundation",
          formal_use_allowed: false,
          source_version: "sv_macro_vendor",
          vendor_version: "vv_choice_catalog_v1",
          rule_version: "rv_phase1_macro_vendor_v1",
          cache_version: "cv_phase1_macro_vendor_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-10T09:00:00Z",
        },
        result: {
          read_target: "duckdb",
          series: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getMacroFoundation();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/preview/macro-foundation",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch latest Choice macro series", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_choice_macro_latest",
          basis: "analytical",
          result_kind: "macro.choice.latest",
          formal_use_allowed: false,
          source_version: "sv_choice_macro_latest",
          vendor_version: "vv_choice_macro_20260410",
          rule_version: "rv_choice_macro_thin_slice_v1",
          cache_version: "cv_choice_macro_thin_slice_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-10T09:00:00Z",
        },
        result: {
          read_target: "duckdb",
          series: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getChoiceMacroLatest();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/macro/choice-series/latest",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch formal pnl envelopes", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/pnl/dates")) {
        return {
          ok: true,
          json: async () => ({
            result_meta: {
              trace_id: "tr_pnl_dates",
              basis: "formal",
              result_kind: "pnl.dates",
              formal_use_allowed: true,
              source_version: "sv_pnl",
              vendor_version: "vv_none",
              rule_version: "rv_pnl",
              cache_version: "cv_pnl",
              quality_flag: "ok",
              vendor_status: "ok",
              fallback_mode: "none",
              scenario_flag: false,
              generated_at: "2026-04-11T03:00:00Z",
            },
            result: {
              report_dates: ["2026-02-28"],
              formal_fi_report_dates: ["2026-02-28"],
              nonstd_bridge_report_dates: [],
            },
          }),
        };
      }
      if (url.includes("/api/pnl/data?date=2026-02-28")) {
        return {
          ok: true,
          json: async () => ({
            result_meta: {
              trace_id: "tr_pnl_data",
              basis: "formal",
              result_kind: "pnl.data",
              formal_use_allowed: true,
              source_version: "sv_pnl",
              vendor_version: "vv_none",
              rule_version: "rv_pnl",
              cache_version: "cv_pnl",
              quality_flag: "ok",
              vendor_status: "ok",
              fallback_mode: "none",
              scenario_flag: false,
              generated_at: "2026-04-11T03:00:00Z",
            },
            result: {
              report_date: "2026-02-28",
              formal_fi_rows: [],
              nonstd_bridge_rows: [],
            },
          }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_pnl_overview",
            basis: "formal",
            result_kind: "pnl.overview",
            formal_use_allowed: true,
            source_version: "sv_pnl",
            vendor_version: "vv_none",
            rule_version: "rv_pnl",
            cache_version: "cv_pnl",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-11T03:00:00Z",
          },
          result: {
            report_date: "2026-02-28",
            formal_fi_row_count: 0,
            nonstd_bridge_row_count: 0,
            interest_income_514: "0.00",
            fair_value_change_516: "0.00",
            capital_gain_517: "0.00",
            manual_adjustment: "0.00",
            total_pnl: "0.00",
          },
        }),
      };
    });

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getFormalPnlDates();
    await client.getFormalPnlData("2026-02-28");
    await client.getFormalPnlOverview("2026-02-28");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/pnl/dates",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/pnl/data?date=2026-02-28",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/api/pnl/overview?report_date=2026-02-28",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch analytical pnl envelopes when basis is analytical", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_pnl_analytical",
          basis: "analytical",
          result_kind: "pnl.data",
          formal_use_allowed: false,
          source_version: "sv_pnl_analytical",
          vendor_version: "vv_none",
          rule_version: "rv_pnl_analytical",
          cache_version: "cv_pnl_analytical",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-11T03:00:00Z",
        },
        result: {
          report_date: "2026-02-28",
          formal_fi_rows: [],
          nonstd_bridge_rows: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getFormalPnlDates("analytical");
    await client.getFormalPnlData("2026-02-28", "analytical");
    await client.getFormalPnlOverview("2026-02-28", "analytical");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/pnl/dates?basis=analytical",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/pnl/data?date=2026-02-28&basis=analytical",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/api/pnl/overview?report_date=2026-02-28&basis=analytical",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch formal pnl bridge envelope", async () => {
    const yuan = (raw: number, signAware = true) => ({
      raw,
      unit: "yuan" as const,
      display: String(raw),
      precision: 2,
      sign_aware: signAware,
    });

    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_pnl_bridge",
          basis: "formal",
          result_kind: "pnl.bridge",
          formal_use_allowed: true,
          source_version: "sv_pnl",
          vendor_version: "vv_none",
          rule_version: "rv_pnl",
          cache_version: "cv_pnl_bridge",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-11T03:00:00Z",
        },
        result: {
          report_date: "2026-02-28",
          rows: [],
          summary: {
            row_count: 0,
            ok_count: 0,
            warning_count: 0,
            error_count: 0,
            total_beginning_dirty_mv: yuan(0, false),
            total_ending_dirty_mv: yuan(0, false),
            total_carry: yuan(0),
            total_roll_down: yuan(0),
            total_treasury_curve: yuan(0),
            total_credit_spread: yuan(0),
            total_fx_translation: yuan(0),
            total_realized_trading: yuan(0),
            total_unrealized_fv: yuan(0),
            total_manual_adjustment: yuan(0),
            total_explained_pnl: yuan(0),
            total_actual_pnl: yuan(0),
            total_residual: yuan(0),
            quality_flag: "ok",
          },
          warnings: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const payload = await client.getPnlBridge("2026-02-28");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/pnl/bridge?report_date=2026-02-28",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
    expect(payload.result.summary.total_actual_pnl).toMatchObject({
      raw: 0,
      unit: "yuan",
      sign_aware: true,
    });
  });

  it("uses real mode to fetch product-category pnl dates", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_dates",
          basis: "formal",
          result_kind: "product_category_pnl.dates",
          formal_use_allowed: true,
          source_version: "sv_real",
          vendor_version: "vv_none",
          rule_version: "rv_real",
          cache_version: "cv_real",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-09T09:00:00Z",
        },
        result: {
          report_dates: ["2026-02-28"],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getProductCategoryDates();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/pnl/product-category/dates",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to trigger product-category pnl refresh", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        status: "completed",
        run_id: "product_category_pnl:test-run",
        job_name: "product_category_pnl",
        trigger_mode: "sync",
        cache_key: "product_category_pnl.formal",
        month_count: 2,
        report_dates: ["2026-01-31", "2026-02-28"],
        rule_version: "rv_product_category_pnl_v1",
        source_version: "sv_test",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.refreshProductCategoryPnl();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/pnl/product-category/refresh",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch product-category pnl refresh status", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        status: "running",
        run_id: "product_category_pnl:test-run",
        job_name: "product_category_pnl",
        trigger_mode: "async",
        cache_key: "product_category_pnl.formal",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getProductCategoryRefreshStatus("product_category_pnl:test-run");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/pnl/product-category/refresh-status?run_id=product_category_pnl%3Atest-run",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to create a product-category manual adjustment", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        adjustment_id: "pca-test-1",
        created_at: "2026-04-10T09:40:00Z",
        stream: "product_category_pnl_adjustments",
        report_date: "2026-02-28",
        operator: "DELTA",
        approval_status: "approved",
        account_code: "13304010001",
        currency: "CNX",
        account_name: "测试科目",
        monthly_pnl: "5",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.createProductCategoryManualAdjustment({
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "approved",
      account_code: "13304010001",
      currency: "CNX",
      account_name: "测试科目",
      monthly_pnl: "5",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/pnl/product-category/manual-adjustments",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Accept: "application/json",
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "13304010001",
          currency: "CNX",
          account_name: "测试科目",
          monthly_pnl: "5",
        }),
      }),
    );
  });

  it("uses real mode to fetch product-category manual adjustments", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        report_date: "2026-02-28",
        adjustments: [],
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getProductCategoryManualAdjustments("2026-02-28");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/pnl/product-category/manual-adjustments?report_date=2026-02-28",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch filtered and paginated product-category manual adjustments", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        report_date: "2026-02-28",
        adjustment_count: 1,
        adjustment_limit: 5,
        adjustment_offset: 10,
        event_total: 2,
        event_limit: 10,
        event_offset: 20,
        adjustments: [],
        events: [],
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getProductCategoryManualAdjustments("2026-02-28", {
      adjustmentId: "pca-1",
      adjustmentIdExact: true,
      accountCode: "5140",
      approvalStatus: "approved",
      eventType: "edited",
      currentSortField: "account_code",
      currentSortDir: "asc",
      eventSortField: "event_type",
      eventSortDir: "desc",
      createdAtFrom: "2026-04-10T00:00:00Z",
      createdAtTo: "2026-04-10T23:59:59Z",
      adjustmentLimit: 5,
      adjustmentOffset: 10,
      limit: 10,
      offset: 20,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/pnl/product-category/manual-adjustments?report_date=2026-02-28&adjustment_id=pca-1&adjustment_id_exact=true&account_code=5140&approval_status=approved&event_type=edited&current_sort_field=account_code&current_sort_dir=asc&event_sort_field=event_type&event_sort_dir=desc&created_at_from=2026-04-10T00%3A00%3A00Z&created_at_to=2026-04-10T23%3A59%3A59Z&adjustment_limit=5&adjustment_offset=10&limit=10&offset=20",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to export filtered product-category manual adjustments as csv", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      headers: new Headers({
        "Content-Disposition":
          'attachment; filename="product-category-audit-2026-02-28.csv"',
      }),
      text: async () => "Current State\n...",
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const payload = await client.exportProductCategoryManualAdjustmentsCsv("2026-02-28", {
      adjustmentId: "pca-1",
      adjustmentIdExact: true,
      accountCode: "5140",
      approvalStatus: "approved",
      eventType: "edited",
      currentSortField: "account_code",
      currentSortDir: "asc",
      eventSortField: "event_type",
      eventSortDir: "desc",
      createdAtFrom: "2026-04-10T00:00:00Z",
      createdAtTo: "2026-04-10T23:59:59Z",
    });

    expect(payload.filename).toBe("product-category-audit-2026-02-28.csv");
    expect(payload.content).toContain("Current State");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/pnl/product-category/manual-adjustments/export?report_date=2026-02-28&adjustment_id=pca-1&adjustment_id_exact=true&account_code=5140&approval_status=approved&event_type=edited&current_sort_field=account_code&current_sort_dir=asc&event_sort_field=event_type&event_sort_dir=desc&created_at_from=2026-04-10T00%3A00%3A00Z&created_at_to=2026-04-10T23%3A59%3A59Z",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "text/csv, text/plain;q=0.9, */*;q=0.8",
        }),
      }),
    );
  });

  it("uses real mode to revoke a product-category manual adjustment", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        adjustment_id: "pca-test-1",
        created_at: "2026-04-10T09:50:00Z",
        stream: "product_category_pnl_adjustments",
        report_date: "2026-02-28",
        operator: "DELTA",
        approval_status: "rejected",
        account_code: "13304010001",
        currency: "CNX",
        account_name: "测试科目",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.revokeProductCategoryManualAdjustment("pca-test-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/pnl/product-category/manual-adjustments/pca-test-1/revoke",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to edit a product-category manual adjustment", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        adjustment_id: "pca-test-1",
        event_type: "edited",
        created_at: "2026-04-10T10:10:00Z",
        stream: "product_category_pnl_adjustments",
        report_date: "2026-02-28",
        operator: "DELTA",
        approval_status: "approved",
        account_code: "51402010001",
        currency: "CNX",
        account_name: "测试科目",
        monthly_pnl: "12",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.updateProductCategoryManualAdjustment("pca-test-1", {
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "approved",
      account_code: "51402010001",
      currency: "CNX",
      account_name: "测试科目",
      monthly_pnl: "12",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/pnl/product-category/manual-adjustments/pca-test-1/edit",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Accept: "application/json",
          "Content-Type": "application/json",
        }),
      }),
    );
  });

  it("uses real mode to restore a product-category manual adjustment", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        adjustment_id: "pca-test-1",
        event_type: "restored",
        created_at: "2026-04-10T10:15:00Z",
        stream: "product_category_pnl_adjustments",
        report_date: "2026-02-28",
        operator: "DELTA",
        approval_status: "approved",
        account_code: "51402010001",
        currency: "CNX",
        account_name: "测试科目",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.restoreProductCategoryManualAdjustment("pca-test-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/pnl/product-category/manual-adjustments/pca-test-1/restore",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch product-category pnl detail with scenario params", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_detail",
          basis: "scenario",
          result_kind: "product_category_pnl.detail",
          formal_use_allowed: false,
          source_version: "sv_real",
          vendor_version: "vv_none",
          rule_version: "rv_real",
          cache_version: "cv_real",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: true,
          generated_at: "2026-04-09T09:00:00Z",
        },
        result: {
          report_date: "2026-02-28",
          view: "monthly",
          available_views: ["monthly"],
          scenario_rate_pct: "2.50",
          rows: [],
          asset_total: {},
          liability_total: {},
          grand_total: {},
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getProductCategoryPnl({
      reportDate: "2026-02-28",
      view: "monthly",
      scenarioRatePct: "2.50",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/pnl/product-category?report_date=2026-02-28&view=monthly&scenario_rate_pct=2.50",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch balance-analysis envelopes", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/ui/balance-analysis/dates")) {
        return {
          ok: true,
          json: async () => ({
            result_meta: {
              trace_id: "tr_balance_dates",
              basis: "formal",
              result_kind: "balance-analysis.dates",
              formal_use_allowed: true,
              source_version: "sv_balance",
              vendor_version: "vv_none",
              rule_version: "rv_balance",
              cache_version: "cv_balance",
              quality_flag: "ok",
              vendor_status: "ok",
              fallback_mode: "none",
              scenario_flag: false,
              generated_at: "2026-04-11T04:00:00Z",
            },
            result: {
              report_dates: ["2025-12-31"],
            },
          }),
        };
      }
      if (url.includes("/ui/balance-analysis/overview?")) {
        return {
          ok: true,
          json: async () => ({
            result_meta: {
              trace_id: "tr_balance_overview",
              basis: "formal",
              result_kind: "balance-analysis.overview",
              formal_use_allowed: true,
              source_version: "sv_balance",
              vendor_version: "vv_none",
              rule_version: "rv_balance",
              cache_version: "cv_balance",
              quality_flag: "ok",
              vendor_status: "ok",
              fallback_mode: "none",
              scenario_flag: false,
              generated_at: "2026-04-11T04:00:00Z",
            },
            result: {
              report_date: "2025-12-31",
              position_scope: "all",
              currency_basis: "CNY",
              detail_row_count: 2,
              summary_row_count: 2,
              total_market_value_amount: "792.00",
              total_amortized_cost_amount: "720.00",
              total_accrued_interest_amount: "50.40",
            },
          }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_balance_detail",
            basis: "formal",
            result_kind: "balance-analysis.detail",
            formal_use_allowed: true,
            source_version: "sv_balance",
            vendor_version: "vv_none",
            rule_version: "rv_balance",
            cache_version: "cv_balance",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-11T04:00:00Z",
          },
          result: {
            report_date: "2025-12-31",
            position_scope: "all",
            currency_basis: "CNY",
            details: [],
            summary: [],
          },
        }),
      };
    });

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getBalanceAnalysisDates();
    await client.getBalanceAnalysisOverview({
      reportDate: "2025-12-31",
      positionScope: "all",
      currencyBasis: "CNY",
    });
    await client.getBalanceAnalysisDetail({
      reportDate: "2025-12-31",
      positionScope: "all",
      currencyBasis: "CNY",
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/ui/balance-analysis/dates",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/ui/balance-analysis/overview?report_date=2025-12-31&position_scope=all&currency_basis=CNY",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/ui/balance-analysis?report_date=2025-12-31&position_scope=all&currency_basis=CNY",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch balance-analysis summary and export csv", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/ui/balance-analysis/summary/export?")) {
        return {
          ok: true,
          headers: new Headers({
            "Content-Disposition":
              'attachment; filename="balance-analysis-summary-2025-12-31-asset-CNY.csv"',
          }),
          text: async () => "row_key,display_name\nrow-1,240001.IB\n",
        };
      }
      return {
        ok: true,
        json: async () => ({
          result_meta: {
            trace_id: "tr_balance_summary",
            basis: "formal",
            result_kind: "balance-analysis.summary",
            formal_use_allowed: true,
            source_version: "sv_balance",
            vendor_version: "vv_none",
            rule_version: "rv_balance",
            cache_version: "cv_balance",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-11T04:00:00Z",
          },
          result: {
            report_date: "2025-12-31",
            position_scope: "asset",
            currency_basis: "CNY",
            limit: 2,
            offset: 2,
            total_rows: 3,
            rows: [
              {
                row_key: "zqtz:240001.IB:portfolio-a:cc-1:CNY:asset:A:FVOCI",
                source_family: "zqtz",
                display_name: "240001.IB",
                owner_name: "利率债组合",
                category_name: "交易账户",
                position_scope: "asset",
                currency_basis: "CNY",
                invest_type_std: "A",
                accounting_basis: "FVOCI",
                detail_row_count: 3,
                market_value_amount: "720.00",
                amortized_cost_amount: "648.00",
                accrued_interest_amount: "36.00",
              },
            ],
          },
        }),
      };
    });

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const summary = await client.getBalanceAnalysisSummary({
      reportDate: "2025-12-31",
      positionScope: "asset",
      currencyBasis: "CNY",
      limit: 2,
      offset: 2,
    });
    const exported = await client.exportBalanceAnalysisSummaryCsv({
      reportDate: "2025-12-31",
      positionScope: "asset",
      currencyBasis: "CNY",
    });

    expect(summary.result.total_rows).toBe(3);
    expect(summary.result.rows[0]?.owner_name).toBe("利率债组合");
    expect(exported.filename).toBe("balance-analysis-summary-2025-12-31-asset-CNY.csv");
    expect(exported.content).toContain("240001.IB");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/ui/balance-analysis/summary?report_date=2025-12-31&position_scope=asset&currency_basis=CNY&limit=2&offset=2",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/ui/balance-analysis/summary/export?report_date=2025-12-31&position_scope=asset&currency_basis=CNY",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "text/csv, text/plain;q=0.9, */*;q=0.8",
        }),
      }),
    );
  });

  it("uses real mode to update balance-analysis decision status without trusting client updated_by", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        decision_key: "bal_wb_decision_gap_001::maturity_gap::Review 1-2 year gap positioning",
        status: "confirmed",
        updated_at: "2026-04-12T08:00:00Z",
        updated_by: "phase1-dev-user",
        comment: "Reviewed and accepted.",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.updateBalanceAnalysisDecisionStatus({
      reportDate: "2025-12-31",
      positionScope: "all",
      currencyBasis: "CNY",
      decisionKey: "bal_wb_decision_gap_001::maturity_gap::Review 1-2 year gap positioning",
      status: "confirmed",
      comment: "Reviewed and accepted.",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/balance-analysis/decision-items/status",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Accept: "application/json",
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          report_date: "2025-12-31",
          position_scope: "all",
          currency_basis: "CNY",
          decision_key: "bal_wb_decision_gap_001::maturity_gap::Review 1-2 year gap positioning",
          status: "confirmed",
          comment: "Reviewed and accepted.",
        }),
      }),
    );
  });

  it("omits invalid monthly operating analysis threshold params in real mode", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_qdb_scenario",
          basis: "scenario",
          result_kind: "qdb-gl-monthly-analysis.scenario",
          formal_use_allowed: false,
          source_version: "sv_real",
          vendor_version: "vv_none",
          rule_version: "rv_real",
          cache_version: "cv_real",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: true,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: {
          report_month: "202602",
          scenario_name: "threshold-stress",
          applied_overrides: {},
          sheets: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getQdbGlMonthlyAnalysisScenario({
      reportMonth: "202602",
      scenarioName: "threshold-stress",
      deviationWarn: Number.NaN,
      deviationAlert: Number.NaN,
      deviationCritical: undefined,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/qdb-gl-monthly-analysis/scenario?report_month=202602&scenario_name=threshold-stress",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch the current balance-analysis user identity", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        user_id: "decision-owner",
        role: "reviewer",
        identity_source: "header",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getBalanceAnalysisCurrentUser();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/balance-analysis/current-user",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("passes report_date when triggering formal pnl refresh for a selected month", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        status: "queued",
        run_id: "pnl_materialize:test-run",
        job_name: "pnl_materialize",
        trigger_mode: "async",
        cache_key: "pnl:phase2:materialize:formal",
        report_date: "2025-12-31",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.refreshFormalPnl("2025-12-31");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/data/refresh_pnl?report_date=2025-12-31",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("unwraps governed liability envelopes in real mode", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_liab",
          basis: "analytical",
          result_kind: "liability_analytics.risk_buckets",
          formal_use_allowed: false,
          source_version: "sv_liab",
          vendor_version: "vv_none",
          rule_version: "rv_liab",
          cache_version: "cv_liab",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-15T00:00:00Z",
        },
        result: {
          report_date: "2026-01-31",
          liabilities_structure: [],
          liabilities_term_buckets: [],
          interbank_liabilities_structure: [],
          interbank_liabilities_term_buckets: [],
          issued_liabilities_structure: [],
          issued_liabilities_term_buckets: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const payload = await client.getLiabilityRiskBuckets("2026-01-31");

    expect(payload).not.toHaveProperty("result_meta");
    expect(payload.report_date).toBe("2026-01-31");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/risk/buckets?report_date=2026-01-31",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to fetch liability business context from the obsidian bridge route", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_liability_knowledge",
          basis: "analytical",
          result_kind: "liability.page_knowledge",
          formal_use_allowed: false,
          source_version: "sv_liability_knowledge",
          vendor_version: "vv_none",
          rule_version: "rv_liability_knowledge_v1",
          cache_version: "cv_liability_knowledge_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-19T00:00:00Z",
        },
        result: {
          page_id: "liability-analytics",
          available: true,
          vault_path: "D:\\PKL-WIKI\\wiki",
          status_note: "obsidian-local",
          notes: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const payload = await client.getLiabilityKnowledgeBrief();

    expect(payload.result.available).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/liability/business-context",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to export balance-analysis workbook xlsx", async () => {
    const workbookBlob = new Blob(["xlsx-binary"], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const fetchMock = vi.fn(async () => ({
      ok: true,
      headers: new Headers({
        "Content-Disposition":
          "attachment; filename=balance-analysis-workbook-2025-12-31.xlsx; filename*=UTF-8''%E8%B5%84%E4%BA%A7%E8%B4%9F%E5%80%BA%E5%88%86%E6%9E%90_2025-12-31.xlsx",
      }),
      blob: async () => workbookBlob,
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const exported = await client.exportBalanceAnalysisWorkbookXlsx({
      reportDate: "2025-12-31",
      positionScope: "asset",
      currencyBasis: "CNY",
    });

    expect(exported.filename).toBe("资产负债分析_2025-12-31.xlsx");
    expect(exported.content).toBe(workbookBlob);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/balance-analysis/workbook/export?report_date=2025-12-31&position_scope=asset&currency_basis=CNY",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept:
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/octet-stream;q=0.9, */*;q=0.8",
        }),
      }),
    );
  });

  it("uses a balance-analysis specific fallback filename when export headers are missing", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      headers: new Headers(),
      text: async () => "row_key,display_name\nrow-1,240001.IB\n",
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const exported = await client.exportBalanceAnalysisSummaryCsv({
      reportDate: "2025-12-31",
      positionScope: "asset",
      currencyBasis: "CNY",
    });

    expect(exported.filename).toBe("balance-analysis-summary.csv");
  });

  it("returns mock research calendar events for the supply and auction feed", async () => {
    const client = createApiClient({ mode: "mock" });

    const events = await client.getResearchCalendarEvents({ reportDate: "2026-03-31" });

    expect(events.length).toBeGreaterThan(0);
    expect(events[0]).toEqual(
      expect.objectContaining({
        id: "rc_supply_001",
        date: "2026-03-31",
        title: "国债净融资节奏",
        kind: "supply",
        severity: "low",
        amount_label: "净融资 180 亿元",
        note: "供给节奏",
      }),
    );
    const auction = events.find((e) => e.kind === "auction");
    expect(auction).toEqual(
      expect.objectContaining({
        id: "rc_auction_002",
        kind: "auction",
        severity: "high",
        amount_label: "420 亿元",
        issuer: "国开行",
      }),
    );
  });

  it("uses real mode to read research calendar events for a report date", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_supply_auction_calendar",
          basis: "analytical",
          result_kind: "calendar.supply_auctions",
          formal_use_allowed: false,
          source_version: "sv_supply_auction_test",
          vendor_version: "vv_supply_auction_test",
          rule_version: "rv_supply_auction_v1",
          cache_version: "cv_supply_auction_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-23T07:00:00Z",
        },
        result: {
          series_id: "research.calendar.supply_auction",
          total_rows: 1,
          limit: 50,
          offset: 0,
          events: [
            {
              event_id: "rc_auction_001",
              series_id: "research.calendar.supply_auction",
              event_date: "2026-03-31",
              event_kind: "auction",
              title: "政策性金融债招标",
              source_family: "research_calendar",
              severity: "high",
              issuer: "国开行",
              instrument_type: "政策性金融债",
              term_label: "10Y",
              amount: 420,
              amount_unit: "亿元",
              currency: "CNY",
              status: "scheduled",
              headline_text: null,
              headline_url: null,
              headline_published_at: null,
            },
          ],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const events = await client.getResearchCalendarEvents({ reportDate: "2026-03-31" });

    expect(events).toEqual([
      expect.objectContaining({
        id: "rc_auction_001",
        date: "2026-03-31",
        title: "政策性金融债招标",
        kind: "auction",
        severity: "high",
        amount_label: "420 亿元",
        issuer: "国开行",
        note: "10Y · 已排期 · 政策性金融债 · 币种 CNY",
        source_url: null,
        source_label: null,
      }),
    ]);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/calendar/supply-auctions?end_date=2026-03-31",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("maps forward-window research calendar requests with start_date and end_date while preserving event mapping", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_supply_auction_window",
          basis: "analytical",
          result_kind: "calendar.supply_auctions",
          formal_use_allowed: false,
          source_version: "sv_supply_auction_test",
          vendor_version: "vv_supply_auction_test",
          rule_version: "rv_supply_auction_v1",
          cache_version: "cv_supply_auction_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-23T07:00:00Z",
        },
        result: {
          series_id: "research.calendar.supply_auction",
          total_rows: 1,
          limit: 50,
          offset: 0,
          events: [
            {
              event_id: "rc_macro_001",
              series_id: "research.calendar.supply_auction",
              event_date: "2026-04-02",
              event_kind: "supply",
              title: "Quarter-opening net supply",
              source_family: "research_calendar",
              severity: "medium",
              issuer: "MOF",
              instrument_type: "Treasury",
              term_label: "5Y",
              amount: 180,
              amount_unit: "bn",
              currency: "CNY",
              status: "scheduled",
            },
          ],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const events = await client.getResearchCalendarEvents({
      startDate: "2026-04-01",
      endDate: "2026-04-30",
    });

    expect(events).toEqual([
      expect.objectContaining({
        id: "rc_macro_001",
        date: "2026-04-02",
        title: "Quarter-opening net supply",
        kind: "supply",
        severity: "medium",
        amount_label: "180 bn",
        issuer: "MOF",
        note: "5Y · 已排期 · 国债 · 币种 CNY",
        source_url: null,
        source_label: null,
      }),
    ]);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/calendar/supply-auctions?start_date=2026-04-01&end_date=2026-04-30",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("returns a clearly labeled NCD funding proxy in mock mode", async () => {
    const client = createApiClient({ mode: "mock" });
    const envelope = await client.getNcdFundingProxy();
    expect(envelope.result.is_actual_ncd_matrix).toBe(false);
    expect(envelope.result.rows).toHaveLength(1);
    expect(envelope.result.rows[0].label).toBe("Shibor fixing");
    expect(envelope.result.rows.some((row) => row.row_key === "quote_median")).toBe(false);
    expect(envelope.result.warnings.join(" ")).toMatch(
      /warehouse|landed|quote medians unavailable/i,
    );
  });

  it("uses real mode to fetch NCD funding proxy", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_ncd_proxy",
          basis: "analytical",
          result_kind: "market_data.ncd_proxy",
          formal_use_allowed: false,
          source_version: "sv_ncd",
          vendor_version: "vv_ncd",
          rule_version: "rv_ncd_proxy",
          cache_version: "cv_ncd",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-24T00:00:00Z",
        },
        result: {
          as_of_date: "2026-04-24",
          proxy_label: "Test proxy",
          is_actual_ncd_matrix: false,
          rows: [],
          warnings: ["Not the issuance matrix."],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const envelope = await client.getNcdFundingProxy();
    expect(envelope.result.is_actual_ncd_matrix).toBe(false);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/market-data/ncd-funding-proxy",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
  });

  it("reads workbook right-rail sections from the existing workbook endpoint", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_balance_workbook",
          basis: "formal",
          result_kind: "balance-analysis.workbook",
          formal_use_allowed: true,
          source_version: "sv_balance",
          vendor_version: "vv_none",
          rule_version: "rv_balance",
          cache_version: "cv_balance",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-11T05:00:00Z",
        },
        result: {
          report_date: "2025-12-31",
          position_scope: "all",
          currency_basis: "CNY",
          cards: [],
          tables: [
            {
              key: "decision_items",
              title: "Decision Items",
              section_kind: "decision_items",
              columns: [{ key: "title", label: "Title" }],
              rows: [
                {
                  title: "Review 1-2 year gap positioning",
                  action_label: "Review gap",
                  severity: "high",
                  reason: "Bucket gap is 4290357.07 wan yuan.",
                  source_section: "maturity_gap",
                  rule_id: "bal_wb_decision_gap_001",
                  rule_version: "v1",
                },
              ],
            },
            {
              key: "event_calendar",
              title: "Event Calendar",
              section_kind: "event_calendar",
              columns: [{ key: "event_date", label: "Event Date" }],
              rows: [
                {
                  event_date: "2026-03-05",
                  event_type: "bond_maturity",
                  title: "240001.IB maturity",
                  source: "internal_governed_schedule",
                  impact_hint: "asset book / policy bond",
                  source_section: "maturity_gap",
                },
              ],
            },
            {
              key: "risk_alerts",
              title: "Risk Alerts",
              section_kind: "risk_alerts",
              columns: [{ key: "title", label: "Title" }],
              rows: [
                {
                  title: "Negative gap in 1-2 year bucket",
                  severity: "high",
                  reason: "Gap dropped to -128000.00 wan yuan.",
                  source_section: "maturity_gap",
                  rule_id: "bal_wb_risk_gap_001",
                  rule_version: "v1",
                },
              ],
            },
          ],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const workbook = await client.getBalanceAnalysisWorkbook({
      reportDate: "2025-12-31",
      positionScope: "all",
      currencyBasis: "CNY",
    });

    expect(workbook.result.tables.map((table) => table.section_kind)).toEqual([
      "decision_items",
      "event_calendar",
      "risk_alerts",
    ]);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/balance-analysis/workbook?report_date=2025-12-31&position_scope=all&currency_basis=CNY",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("uses real mode to trigger and poll balance-analysis refresh", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/refresh-status?run_id=")) {
        return {
          ok: true,
          json: async () => ({
            status: "completed",
            run_id: "balance_analysis_materialize:test-run",
            job_name: "balance_analysis_materialize",
            trigger_mode: "terminal",
            cache_key: "balance_analysis:materialize:formal",
            source_version: "sv_balance_test",
          }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          status: "queued",
          run_id: "balance_analysis_materialize:test-run",
          job_name: "balance_analysis_materialize",
          trigger_mode: "async",
          cache_key: "balance_analysis:materialize:formal",
          report_date: "2025-12-31",
        }),
      };
    });

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.refreshBalanceAnalysis("2025-12-31");
    await client.getBalanceAnalysisRefreshStatus("balance_analysis_materialize:test-run");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/ui/balance-analysis/refresh?report_date=2025-12-31",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/ui/balance-analysis/refresh-status?run_id=balance_analysis_materialize%3Atest-run",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  test("mock client returns KPI owners", async () => {
    const client = createApiClient({ mode: "mock" });
    const response = await client.getKpiOwners({ year: 2026 });
    expect(response.owners).toBeDefined();
    expect(response.owners.length).toBeGreaterThan(0);
    expect(response.total).toBeGreaterThan(0);
  });

  test("mock client returns KPI values", async () => {
    const client = createApiClient({ mode: "mock" });
    const response = await client.getKpiValues({
      owner_id: 1,
      as_of_date: "2026-04-13",
    });
    expect(response.owner_id).toBe(1);
    expect(response.metrics).toBeDefined();
  });

  test("mock client batch update KPI values", async () => {
    const client = createApiClient({ mode: "mock" });
    const response = await client.batchUpdateKpiValues("2026-04-13", []);
    expect(response.success_count).toBeDefined();
    expect(response.errors).toBeDefined();
  });

  test("mock client fetch and recalc KPI", async () => {
    const client = createApiClient({ mode: "mock" });
    const response = await client.fetchAndRecalcKpi(1, "2026-04-13");
    expect(response.owner_id).toBe(1);
    expect(response.total_metrics).toBeDefined();
  });

  test("mock client cube dimensions and query", async () => {
    const client = createApiClient({ mode: "mock" });
    const dims = await client.getCubeDimensions("bond_analytics");
    expect(dims.fact_table).toBe("bond_analytics");
    expect(dims.dimensions).toContain("rating");
    expect(dims.measure_fields).toContain("market_value");
    expect(dims.measures).toEqual(["sum", "avg", "count", "min", "max"]);

    const result = await client.executeCubeQuery({
      report_date: "2025-12-31",
      fact_table: "bond_analytics",
      measures: ["sum(market_value)"],
      dimensions: ["rating"],
      basis: "formal",
    });
    expect(result.report_date).toBe("2025-12-31");
    expect(result.fact_table).toBe("bond_analytics");
    expect(result.measures).toEqual(["sum(market_value)"]);
    expect(result.dimensions).toEqual(["rating"]);
    expect(result.result_meta.basis).toBe("formal");
    expect(result.result_meta.result_kind).toBe("cube.query");
  });
});
