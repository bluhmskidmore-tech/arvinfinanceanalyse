import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, expectTypeOf, it } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import type { PnlClientMethods } from "../api/pnlClient";

const clientSource = readFileSync(resolve(process.cwd(), "src/api/client.ts"), "utf8");
const clientContextSource = readFileSync(resolve(process.cwd(), "src/api/clientContext.ts"), "utf8");
const providersSource = readFileSync(resolve(process.cwd(), "src/app/providers.tsx"), "utf8");
const shellSource = readFileSync(resolve(process.cwd(), "src/layouts/WorkbenchShell.tsx"), "utf8");
const dataModeRibbonSource = readFileSync(resolve(process.cwd(), "src/components/DataModeRibbon.tsx"), "utf8");
const marketDataSource = readFileSync(resolve(process.cwd(), "src/api/marketDataClient.ts"), "utf8");
const kpiSource = readFileSync(resolve(process.cwd(), "src/api/kpiClient.ts"), "utf8");
const cubeSource = readFileSync(resolve(process.cwd(), "src/api/cubeClient.ts"), "utf8");
const agentClientSource = readFileSync(resolve(process.cwd(), "src/api/agentClient.ts"), "utf8");
const executiveClientSource = readFileSync(resolve(process.cwd(), "src/api/executiveClient.ts"), "utf8");
const balanceAnalysisClientSource = readFileSync(resolve(process.cwd(), "src/api/balanceAnalysisClient.ts"), "utf8");
const bondAnalyticsClientSource = readFileSync(resolve(process.cwd(), "src/api/bondAnalyticsClient.ts"), "utf8");
const positionsClientSource = readFileSync(resolve(process.cwd(), "src/api/positionsClient.ts"), "utf8");
const liabilityAdbClientSource = readFileSync(resolve(process.cwd(), "src/api/liabilityAdbClient.ts"), "utf8");
const productCategoryClientSource = readFileSync(resolve(process.cwd(), "src/api/productCategoryClient.ts"), "utf8");
const qdbGlMonthlyAnalysisClientSource = readFileSync(resolve(process.cwd(), "src/api/qdbGlMonthlyAnalysisClient.ts"), "utf8");
const healthClientPath = resolve(process.cwd(), "src/api/healthClient.ts");
const healthClientSource = existsSync(healthClientPath)
  ? readFileSync(healthClientPath, "utf8")
  : "";

describe("ApiClient composition boundary", () => {
  it("keeps the public market-data source preview surface available from createApiClient", () => {
    const client = createApiClient({ mode: "mock" });

    expect(typeof client.getSourceFoundation).toBe("function");
    expect(typeof client.refreshSourcePreview).toBe("function");
    expect(typeof client.getSourcePreviewRefreshStatus).toBe("function");
    expect(typeof client.getSourceFoundationHistory).toBe("function");
    expect(typeof client.getSourceFoundationRows).toBe("function");
    expect(typeof client.getSourceFoundationTraces).toBe("function");
    expect(typeof client.getChoiceNewsEvents).toBe("function");
    expect(typeof client.ingestTushareNprNews).toBe("function");
    expect(typeof client.getResearchCalendarEvents).toBe("function");
    expect(typeof client.getKpiOwners).toBe("function");
    expect(typeof client.fetchAndRecalcKpi).toBe("function");
    expect(typeof client.getCubeDimensions).toBe("function");
    expect(typeof client.executeCubeQuery).toBe("function");
  });

  it("keeps the public Bond Dashboard surface available from createApiClient", () => {
    const client = createApiClient({ mode: "mock" });

    expect(typeof client.getBondDashboardDates).toBe("function");
    expect(typeof client.getBondDashboardHeadlineKpis).toBe("function");
    expect(typeof client.getBondDashboardAssetStructure).toBe("function");
    expect(typeof client.getBondDashboardYieldDistribution).toBe("function");
    expect(typeof client.getBondDashboardPortfolioComparison).toBe("function");
    expect(typeof client.getBondDashboardSpreadAnalysis).toBe("function");
    expect(typeof client.getBondDashboardMaturityStructure).toBe("function");
    expect(typeof client.getBondDashboardIndustryDistribution).toBe("function");
    expect(typeof client.getBondDashboardRiskIndicators).toBe("function");
  });

  it("keeps the public Bond Analytics surface available from createApiClient", () => {
    const client = createApiClient({ mode: "mock" });

    expect(typeof client.refreshBondAnalytics).toBe("function");
    expect(typeof client.getBondAnalyticsRefreshStatus).toBe("function");
    expect(typeof client.getBondAnalyticsDates).toBe("function");
    expect(typeof client.getBondAnalyticsReturnDecomposition).toBe("function");
    expect(typeof client.getBondAnalyticsBenchmarkExcess).toBe("function");
    expect(typeof client.getBondAnalyticsKrdCurveRisk).toBe("function");
    expect(typeof client.getBondAnalyticsActionAttribution).toBe("function");
    expect(typeof client.getBondAnalyticsAccountingClassAudit).toBe("function");
    expect(typeof client.getBondAnalyticsCreditSpreadMigration).toBe("function");
    expect(typeof client.getBondAnalyticsPortfolioHeadlines).toBe("function");
    expect(typeof client.getBondAnalyticsTopHoldings).toBe("function");
    expect(typeof client.getBondAnalyticsYieldCurveTermStructure).toBe("function");
    expect(typeof client.getCreditSpreadAnalysisDetail).toBe("function");
  });

  it("keeps the public Balance Analysis surface available from createApiClient", () => {
    const client = createApiClient({ mode: "mock" });

    expect(typeof client.getBalanceAnalysisDates).toBe("function");
    expect(typeof client.getBalanceAnalysisOverview).toBe("function");
    expect(typeof client.getBalanceAnalysisSummary).toBe("function");
    expect(typeof client.getBalanceAnalysisWorkbook).toBe("function");
    expect(typeof client.getBalanceAnalysisCurrentUser).toBe("function");
    expect(typeof client.getBalanceAnalysisDecisionItems).toBe("function");
    expect(typeof client.updateBalanceAnalysisDecisionStatus).toBe("function");
    expect(typeof client.getBalanceAnalysisDetail).toBe("function");
    expect(typeof client.getBalanceAnalysisSummaryByBasis).toBe("function");
    expect(typeof client.getBalanceAnalysisAdvancedAttribution).toBe("function");
    expect(typeof client.exportBalanceAnalysisSummaryCsv).toBe("function");
    expect(typeof client.exportBalanceAnalysisWorkbookXlsx).toBe("function");
    expect(typeof client.refreshBalanceAnalysis).toBe("function");
    expect(typeof client.getBalanceAnalysisRefreshStatus).toBe("function");
  });

  it("keeps the public Positions surface available from createApiClient", () => {
    const client = createApiClient({ mode: "mock" });

    expect(typeof client.getPositionsBondSubTypes).toBe("function");
    expect(typeof client.getPositionsBondsList).toBe("function");
    expect(typeof client.getPositionsCounterpartyBonds).toBe("function");
    expect(typeof client.getPositionsInterbankProductTypes).toBe("function");
    expect(typeof client.getPositionsInterbankList).toBe("function");
    expect(typeof client.getPositionsCounterpartyInterbankSplit).toBe("function");
    expect(typeof client.getPositionsStatsRating).toBe("function");
    expect(typeof client.getPositionsStatsIndustry).toBe("function");
    expect(typeof client.getPositionsCustomerDetails).toBe("function");
    expect(typeof client.getPositionsCustomerTrend).toBe("function");
  });

  it("keeps the public Liability and ADB surface available from createApiClient", () => {
    const client = createApiClient({ mode: "mock" });

    expect(typeof client.getLiabilityRiskBuckets).toBe("function");
    expect(typeof client.getLiabilityYieldMetrics).toBe("function");
    expect(typeof client.getYieldByPeriod).toBe("function");
    expect(typeof client.getLiabilityCounterparty).toBe("function");
    expect(typeof client.getLiabilityKnowledgeBrief).toBe("function");
    expect(typeof client.getCockpitWarnings).toBe("function");
    expect(typeof client.getContributionSplit).toBe("function");
    expect(typeof client.getLiabilitiesMonthly).toBe("function");
    expect(typeof client.getLiabilityAdbMonthly).toBe("function");
    expect(typeof client.getAdb).toBe("function");
    expect(typeof client.getAdbComparison).toBe("function");
    expect(typeof client.getAdbMonthly).toBe("function");
    expect(typeof client.getAdbCoverage).toBe("function");
  });

  it("keeps the public Product Category surface available from createApiClient", () => {
    const client = createApiClient({ mode: "mock" });

    expect(typeof client.getProductCategoryDates).toBe("function");
    expect(typeof client.refreshProductCategoryPnl).toBe("function");
    expect(typeof client.getProductCategoryRefreshStatus).toBe("function");
    expect(typeof client.createProductCategoryManualAdjustment).toBe("function");
    expect(typeof client.getProductCategoryManualAdjustments).toBe("function");
    expect(typeof client.exportProductCategoryManualAdjustmentsCsv).toBe("function");
    expect(typeof client.updateProductCategoryManualAdjustment).toBe("function");
    expect(typeof client.revokeProductCategoryManualAdjustment).toBe("function");
    expect(typeof client.restoreProductCategoryManualAdjustment).toBe("function");
    expect(typeof client.getProductCategoryPnl).toBe("function");
    expect(typeof client.getProductCategoryAttribution).toBe("function");
  });

  it("keeps the public QDB GL Monthly Analysis surface available from createApiClient", () => {
    const client = createApiClient({ mode: "mock" });

    expect(typeof client.getQdbGlMonthlyAnalysisDates).toBe("function");
    expect(typeof client.getQdbGlMonthlyAnalysisWorkbook).toBe("function");
    expect(typeof client.exportQdbGlMonthlyAnalysisWorkbookXlsx).toBe("function");
    expect(typeof client.refreshQdbGlMonthlyAnalysis).toBe("function");
    expect(typeof client.getQdbGlMonthlyAnalysisRefreshStatus).toBe("function");
    expect(typeof client.getQdbGlMonthlyAnalysisScenario).toBe("function");
    expect(typeof client.createQdbGlMonthlyAnalysisManualAdjustment).toBe("function");
    expect(typeof client.updateQdbGlMonthlyAnalysisManualAdjustment).toBe("function");
    expect(typeof client.revokeQdbGlMonthlyAnalysisManualAdjustment).toBe("function");
    expect(typeof client.restoreQdbGlMonthlyAnalysisManualAdjustment).toBe("function");
    expect(typeof client.getQdbGlMonthlyAnalysisManualAdjustments).toBe("function");
    expect(typeof client.exportQdbGlMonthlyAnalysisManualAdjustmentsCsv).toBe("function");
  });

  it("keeps QDB GL Monthly Analysis methods in the PnlClientMethods compatibility type", () => {
    expectTypeOf<PnlClientMethods>().toMatchTypeOf<
      Pick<
        ApiClient,
        | "getQdbGlMonthlyAnalysisDates"
        | "getQdbGlMonthlyAnalysisWorkbook"
        | "exportQdbGlMonthlyAnalysisWorkbookXlsx"
        | "refreshQdbGlMonthlyAnalysis"
        | "getQdbGlMonthlyAnalysisRefreshStatus"
        | "getQdbGlMonthlyAnalysisScenario"
        | "createQdbGlMonthlyAnalysisManualAdjustment"
        | "updateQdbGlMonthlyAnalysisManualAdjustment"
        | "revokeQdbGlMonthlyAnalysisManualAdjustment"
        | "restoreQdbGlMonthlyAnalysisManualAdjustment"
        | "getQdbGlMonthlyAnalysisManualAdjustments"
        | "exportQdbGlMonthlyAnalysisManualAdjustmentsCsv"
      >
    >();
  });

  it("routes real Positions list requests to exact backend endpoints", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_positions",
          basis: "formal",
          result_kind: "positions.list",
          formal_use_allowed: true,
          source_version: "sv_positions",
          vendor_version: "vv_none",
          rule_version: "rv_positions",
          cache_version: "cv_positions",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-05-25T09:00:00Z",
        },
        result: { items: [], total: 0, page: 1, page_size: 20 },
      }),
    }));
    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getPositionsBondsList({
      reportDate: " 2026-01-31 ",
      subType: " 信用债 ",
      page: 1,
      pageSize: 20,
      includeIssued: true,
    });
    await client.getPositionsInterbankList({
      reportDate: " 2026-01-31 ",
      productType: " 存放 ",
      direction: "Asset",
      page: 2,
      pageSize: 50,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/positions/bonds?report_date=2026-01-31&sub_type=%E4%BF%A1%E7%94%A8%E5%80%BA&page=1&page_size=20&include_issued=true",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/positions/interbank?report_date=2026-01-31&product_type=%E5%AD%98%E6%94%BE&direction=Asset&page=2&page_size=50",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
  });

  it("routes real Product Category requests to exact backend endpoints", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_product_category",
          basis: "formal",
          result_kind: "product_category_pnl",
          formal_use_allowed: true,
          source_version: "sv_product_category",
          vendor_version: "vv_none",
          rule_version: "rv_product_category",
          cache_version: "cv_product_category",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-05-25T09:00:00Z",
        },
        result: { rows: [] },
      }),
    }));
    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getProductCategoryPnl({
      reportDate: "2026-02-28",
      view: "business",
      scenarioRatePct: "1.25",
    });
    await client.getProductCategoryManualAdjustments("2026-02-28", {
      adjustmentId: "pca-001",
      adjustmentIdExact: true,
      accountCode: "1101",
      approvalStatus: "approved",
      eventType: "edited",
      currentSortField: "account_code",
      currentSortDir: "asc",
      eventSortField: "created_at",
      eventSortDir: "desc",
      createdAtFrom: "2026-04-01T00:00:00Z",
      createdAtTo: "2026-04-30T23:59:59Z",
      adjustmentLimit: 10,
      adjustmentOffset: 20,
      limit: 30,
      offset: 40,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/ui/pnl/product-category?report_date=2026-02-28&view=business&scenario_rate_pct=1.25",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/ui/pnl/product-category/manual-adjustments?report_date=2026-02-28&adjustment_id=pca-001&adjustment_id_exact=true&account_code=1101&approval_status=approved&event_type=edited&current_sort_field=account_code&current_sort_dir=asc&event_sort_field=created_at&event_sort_dir=desc&created_at_from=2026-04-01T00%3A00%3A00Z&created_at_to=2026-04-30T23%3A59%3A59Z&adjustment_limit=10&adjustment_offset=20&limit=30&offset=40",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
  });

  it("routes real QDB GL Monthly Analysis requests to exact backend endpoints", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      headers: new Headers({ "Content-Disposition": 'attachment; filename="qdb.csv"' }),
      json: async () => ({
        result_meta: {
          trace_id: "tr_qdb_gl_monthly_analysis",
          basis: "analytical",
          result_kind: "qdb-gl-monthly-analysis.workbook",
          formal_use_allowed: false,
          source_version: "sv_qdb_gl",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-05-25T09:00:00Z",
        },
        result: { report_month: "202602", sheets: [] },
      }),
      text: async () => "adjustment_id,event_type\n",
      blob: async () => new Blob(["workbook"]),
    }));
    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getQdbGlMonthlyAnalysisWorkbook({ reportMonth: "202602" });
    await client.getQdbGlMonthlyAnalysisScenario({
      reportMonth: "202602",
      scenarioName: "shock",
      deviationWarn: 0,
      deviationAlert: 2.5,
      deviationCritical: 5,
    });
    await client.createQdbGlMonthlyAnalysisManualAdjustment({
      report_month: "202602",
      adjustment_class: "analysis_adjustment",
      target: { sheet: "income", row: "fee" },
      operator: "OVERRIDE",
      value: "100",
      approval_status: "approved",
    });
    await client.exportQdbGlMonthlyAnalysisManualAdjustmentsCsv("202602");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/ui/qdb-gl-monthly-analysis/workbook?report_month=202602",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/ui/qdb-gl-monthly-analysis/scenario?report_month=202602&scenario_name=shock&deviation_warn=0&deviation_alert=2.5&deviation_critical=5",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/ui/qdb-gl-monthly-analysis/manual-adjustments",
      expect.objectContaining({
        body: JSON.stringify({
          report_month: "202602",
          adjustment_class: "analysis_adjustment",
          target: { sheet: "income", row: "fee" },
          operator: "OVERRIDE",
          value: "100",
          approval_status: "approved",
        }),
        headers: expect.objectContaining({
          Accept: "application/json",
          "Content-Type": "application/json",
        }),
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://localhost:8000/ui/qdb-gl-monthly-analysis/manual-adjustments/export?report_month=202602",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "text/csv, text/plain;q=0.9, */*;q=0.8" }),
      }),
    );
  });

  it("routes every real QDB GL Monthly Analysis endpoint after extraction", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      headers: new Headers({
        "Content-Disposition": 'attachment; filename="qdb-workbook.xlsx"',
      }),
      json: async () => ({
        result_meta: {
          trace_id: "tr_qdb_gl_monthly_analysis",
          basis: "analytical",
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_gl",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-05-25T09:00:00Z",
        },
        result: { report_months: [] },
        status: "completed",
        run_id: "run qdb/1",
        job_name: "qdb_gl_monthly_analysis",
        trigger_mode: "sync",
        cache_key: "qdb_gl_monthly_analysis.analytical",
        adjustment_id: "adj qdb/1",
        event_type: "edited",
        created_at: "2026-04-12T00:10:00Z",
        stream: "monthly_operating_analysis_adjustments",
        report_month: "202602",
        adjustment_class: "analysis_adjustment",
        target: {},
        operator: "OVERRIDE",
        value: "100",
        approval_status: "approved",
        adjustment_count: 0,
        adjustments: [],
        events: [],
      }),
      text: async () => "adjustment_id,event_type\n",
      blob: async () => new Blob(["workbook"]),
    }));
    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getQdbGlMonthlyAnalysisDates();
    await client.exportQdbGlMonthlyAnalysisWorkbookXlsx({ reportMonth: "2026 02" });
    await client.refreshQdbGlMonthlyAnalysis({ reportMonth: "2026 02" });
    await client.getQdbGlMonthlyAnalysisRefreshStatus("run qdb/1");
    await client.updateQdbGlMonthlyAnalysisManualAdjustment("adj qdb/1", {
      report_month: "202602",
      adjustment_class: "analysis_adjustment",
      target: { sheet: "income", row: "fee" },
      operator: "OVERRIDE",
      value: "200",
      approval_status: "approved",
    });
    await client.revokeQdbGlMonthlyAnalysisManualAdjustment("adj qdb/1");
    await client.restoreQdbGlMonthlyAnalysisManualAdjustment("adj qdb/1");
    await client.getQdbGlMonthlyAnalysisManualAdjustments("2026 02");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/ui/qdb-gl-monthly-analysis/dates",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/ui/qdb-gl-monthly-analysis/workbook/export?report_month=2026%2002",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept:
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/octet-stream;q=0.9, */*;q=0.8",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/ui/qdb-gl-monthly-analysis/refresh?report_month=2026%2002",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://localhost:8000/ui/qdb-gl-monthly-analysis/refresh-status?run_id=run%20qdb%2F1",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "http://localhost:8000/ui/qdb-gl-monthly-analysis/manual-adjustments/adj%20qdb%2F1/edit",
      expect.objectContaining({
        body: JSON.stringify({
          report_month: "202602",
          adjustment_class: "analysis_adjustment",
          target: { sheet: "income", row: "fee" },
          operator: "OVERRIDE",
          value: "200",
          approval_status: "approved",
        }),
        headers: expect.objectContaining({
          Accept: "application/json",
          "Content-Type": "application/json",
        }),
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "http://localhost:8000/ui/qdb-gl-monthly-analysis/manual-adjustments/adj%20qdb%2F1/revoke",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      "http://localhost:8000/ui/qdb-gl-monthly-analysis/manual-adjustments/adj%20qdb%2F1/restore",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      8,
      "http://localhost:8000/ui/qdb-gl-monthly-analysis/manual-adjustments?report_month=2026%2002",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
  });

  it("keeps QDB GL Monthly Analysis mock envelope shapes after extraction", async () => {
    const client = createApiClient({ mode: "mock" });

    await expect(client.getQdbGlMonthlyAnalysisDates()).resolves.toMatchObject({
      result_meta: {
        result_kind: "qdb-gl-monthly-analysis.dates",
        basis: "analytical",
        formal_use_allowed: false,
        source_version: "sv_qdb_gl_mock",
        rule_version: "rv_qdb_gl_monthly_analysis_v1",
        cache_version: "cv_qdb_gl_monthly_analysis_v1",
      },
      result: { report_months: [] },
    });
    await expect(
      client.getQdbGlMonthlyAnalysisWorkbook({ reportMonth: "202602" }),
    ).resolves.toMatchObject({
      result_meta: {
        result_kind: "qdb-gl-monthly-analysis.workbook",
        basis: "analytical",
      },
      result: { report_month: "202602", sheets: [] },
    });
    await expect(
      client.getQdbGlMonthlyAnalysisScenario({
        reportMonth: "202602",
        scenarioName: "shock",
        deviationWarn: 0,
      }),
    ).resolves.toMatchObject({
      result_meta: {
        result_kind: "qdb-gl-monthly-analysis.scenario",
        basis: "analytical",
      },
      result: {
        report_month: "202602",
        scenario_name: "shock",
        applied_overrides: { DEVIATION_WARN: 0 },
        sheets: [],
      },
    });
  });

  it("keeps extracted domain implementation out of client.ts", () => {
    expect(clientSource).not.toContain("MOCK_SOURCE_FOUNDATION_SUMMARIES");
    expect(clientSource).not.toContain("MOCK_CHOICE_NEWS_EVENTS");
    expect(clientSource).not.toContain("buildMockResearchCalendarEvents");
    expect(clientSource).not.toContain("buildMockChoiceNewsEnvelope");
    expect(clientSource).not.toContain("requestKpiJson");
    expect(clientSource).not.toContain("kpiQueryString");
    expect(clientSource).not.toContain("dimensionMap");
    expect(clientSource).not.toContain("buildStableDemoAgentEnvelope");
    expect(clientSource).not.toContain("/api/agent/query");
    expect(clientSource).not.toContain("/ui/home/overview");
    expect(clientSource).not.toContain("/ui/home/summary");
    expect(clientSource).not.toContain("/ui/risk/overview");
    expect(clientSource).not.toContain("/ui/home/contribution");
    expect(clientSource).not.toContain("/ui/home/alerts");
    expect(clientSource).not.toContain("/api/risk/tensor");
    expect(clientSource).not.toContain("risk.tensor");
    expect(clientSource).not.toContain("/api/bond-dashboard/");
    expect(clientSource).not.toContain("bond_dashboard.dates");
    expect(clientSource).not.toContain("bond_dashboard.headline_kpis");
    expect(clientSource).not.toContain("bond_dashboard.asset_structure");
    expect(clientSource).not.toContain("bond_dashboard.yield_distribution");
    expect(clientSource).not.toContain("bond_dashboard.portfolio_comparison");
    expect(clientSource).not.toContain("bond_dashboard.spread_analysis");
    expect(clientSource).not.toContain("bond_dashboard.maturity_structure");
    expect(clientSource).not.toContain("bond_dashboard.industry_distribution");
    expect(clientSource).not.toContain("bond_dashboard.risk_indicators");
    expect(clientSource).not.toContain("/api/bond-analytics/");
    expect(clientSource).not.toContain("/api/credit-spread-analysis/detail");
    expect(clientSource).not.toContain("bond_analytics.dates");
    expect(clientSource).not.toContain("bond_analytics.return_decomposition");
    expect(clientSource).not.toContain("bond_analytics.benchmark_excess");
    expect(clientSource).not.toContain("bond_analytics.krd_curve_risk");
    expect(clientSource).not.toContain("bond_analytics.action_attribution");
    expect(clientSource).not.toContain("bond_analytics.accounting_class_audit");
    expect(clientSource).not.toContain("bond_analytics.credit_spread_migration");
    expect(clientSource).not.toContain("bond_analytics.portfolio_headlines");
    expect(clientSource).not.toContain("bond_analytics.top_holdings");
    expect(clientSource).not.toContain("credit_spread_analysis.detail");
    expect(clientSource).not.toContain("buildBalanceAnalysisTableRows");
    expect(clientSource).not.toContain("BalanceAnalysisAmountField");
    expect(clientSource).not.toContain("/ui/balance-analysis/");
    expect(clientSource).not.toContain("balance-analysis.dates");
    expect(clientSource).not.toContain("balance-analysis.overview");
    expect(clientSource).not.toContain("balance-analysis.detail");
    expect(clientSource).not.toContain("balance-analysis.basis_breakdown");
    expect(clientSource).not.toContain("balance-analysis.advanced_attribution_bundle");
    expect(clientSource).not.toContain("balance-analysis.summary");
    expect(clientSource).not.toContain("balance-analysis.workbook");
    expect(clientSource).not.toContain("balance-analysis.decision-items");
    expect(clientSource).not.toContain("/api/positions/");
    expect(clientSource).not.toContain("positions.bonds.sub_types");
    expect(clientSource).not.toContain("positions.bonds.list");
    expect(clientSource).not.toContain("positions.counterparty.bonds");
    expect(clientSource).not.toContain("positions.interbank.product_types");
    expect(clientSource).not.toContain("positions.interbank.list");
    expect(clientSource).not.toContain("positions.counterparty.interbank.split");
    expect(clientSource).not.toContain("positions.stats.rating");
    expect(clientSource).not.toContain("positions.stats.industry");
    expect(clientSource).not.toContain("positions.customer.details");
    expect(clientSource).not.toContain("positions.customer.trend");
    expect(clientSource).not.toContain("/api/risk/buckets");
    expect(clientSource).not.toContain("/api/analysis/yield_metrics");
    expect(clientSource).not.toContain("/api/analysis/yield-by-period");
    expect(clientSource).not.toContain("/api/analysis/liabilities/counterparty");
    expect(clientSource).not.toContain("/ui/liability/business-context");
    expect(clientSource).not.toContain("/api/analysis/liabilities/cockpit-warnings");
    expect(clientSource).not.toContain("/api/analysis/liabilities/contribution-split");
    expect(clientSource).not.toContain("/api/liabilities/monthly");
    expect(clientSource).not.toContain("/api/analysis/adb");
    expect(clientSource).not.toContain("liability.cockpit_warnings");
    expect(clientSource).not.toContain("liability.contribution_split");
    expect(clientSource).not.toContain("liability.page_knowledge");
    expect(clientSource).not.toContain("requestPlainJson");
    expect(clientSource).not.toContain("requestEnvelopeOrPlainJson");
    expect(clientSource).not.toContain("requestEnvelopeOrPlainJsonWithMeta");
    expect(clientSource).not.toContain("normalizeAccountingBasisTrendItem");
    expect(clientSource).not.toContain("normalizeAdbComparisonResponse");
    expect(clientSource).not.toContain("normalizeAdbMonthlyResponse");
    expect(clientSource).not.toContain("/ui/pnl/product-category");
    expect(clientSource).not.toContain("product_category_pnl.dates");
    expect(clientSource).not.toContain("product_category_pnl:mock-run");
    expect(clientSource).not.toContain("product_category_pnl_adjustments");
    expect(clientSource).not.toContain("buildMockProductCategoryPnlEnvelope");
    expect(clientSource).not.toContain("buildMockProductCategoryAttributionEnvelope");
    expect(clientSource).not.toContain("mockManualAdjustments");
    expect(clientSource).not.toContain("mockManualAdjustmentSeq");
    expect(clientSource).not.toContain("reduceLatestManualAdjustments");
    expect(clientSource).not.toContain("filterManualAdjustments");
    expect(clientSource).not.toContain("sortManualAdjustments");
    expect(clientSource).not.toContain("buildManualAdjustmentSearchParams");
    expect(clientSource).not.toContain("/ui/qdb-gl-monthly-analysis");
    expect(clientSource).not.toContain("qdb-gl-monthly-analysis.dates");
    expect(clientSource).not.toContain("qdb-gl-monthly-analysis.workbook");
    expect(clientSource).not.toContain("qdb-gl-monthly-analysis.scenario");
    expect(clientSource).not.toContain("qdb_gl_monthly_analysis:");
    expect(clientSource).not.toContain("qdb_gl_monthly_analysis.analytical");
    expect(clientSource).not.toContain("monthly_operating_analysis_adjustments");
    expect(clientSource).not.toMatch(/async getSourceFoundation\(/);
    expect(clientSource).not.toMatch(/async refreshSourcePreview\(/);
    expect(clientSource).not.toMatch(/async getSourcePreviewRefreshStatus\(/);
    expect(clientSource).not.toMatch(/async getSourceFoundationHistory\(/);
    expect(clientSource).not.toMatch(/async getSourceFoundationRows\(/);
    expect(clientSource).not.toMatch(/async getSourceFoundationTraces\(/);
    expect(clientSource).not.toMatch(/async getChoiceNewsEvents\(/);
    expect(clientSource).not.toMatch(/async getResearchCalendarEvents\(/);
    expect(clientSource).not.toMatch(/async ingestTushareNprNews\(/);
    expect(clientSource).not.toMatch(/async getKpiOwners\(/);
    expect(clientSource).not.toMatch(/async fetchAndRecalcKpi\(/);
    expect(clientSource).not.toMatch(/async getCubeDimensions\(/);
    expect(clientSource).not.toMatch(/async executeCubeQuery\(/);
    expect(clientSource).not.toMatch(/async queryAgent\(/);
    expect(clientSource).not.toMatch(/async getOverview\(/);
    expect(clientSource).not.toMatch(/async getHomeSnapshot\(/);
    expect(clientSource).not.toMatch(/async getSummary\(/);
    expect(clientSource).not.toMatch(/async getRiskOverview\(/);
    expect(clientSource).not.toMatch(/async getRiskTensorDates\(/);
    expect(clientSource).not.toMatch(/async getRiskTensor\(/);
    expect(clientSource).not.toMatch(/async getContribution\(/);
    expect(clientSource).not.toMatch(/async getAlerts\(/);
    expect(clientSource).not.toMatch(/async getPlaceholderSnapshot\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardDates\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardHeadlineKpis\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardAssetStructure\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardYieldDistribution\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardPortfolioComparison\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardSpreadAnalysis\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardMaturityStructure\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardIndustryDistribution\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardRiskIndicators\(/);
    expect(clientSource).not.toMatch(/async refreshBondAnalytics\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsRefreshStatus\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsDates\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsReturnDecomposition\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsBenchmarkExcess\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsKrdCurveRisk\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsActionAttribution\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsAccountingClassAudit\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsCreditSpreadMigration\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsPortfolioHeadlines\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsTopHoldings\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsYieldCurveTermStructure\(/);
    expect(clientSource).not.toMatch(/async getCreditSpreadAnalysisDetail\(/);
    expect(clientSource).not.toMatch(/async getBalanceAnalysisDates\(/);
    expect(clientSource).not.toMatch(/async getBalanceAnalysisOverview\(/);
    expect(clientSource).not.toMatch(/async getBalanceAnalysisDetail\(/);
    expect(clientSource).not.toMatch(/async getBalanceAnalysisSummaryByBasis\(/);
    expect(clientSource).not.toMatch(/async getBalanceAnalysisAdvancedAttribution\(/);
    expect(clientSource).not.toMatch(/async getBalanceAnalysisSummary\(/);
    expect(clientSource).not.toMatch(/async getBalanceAnalysisWorkbook\(/);
    expect(clientSource).not.toMatch(/async getBalanceAnalysisCurrentUser\(/);
    expect(clientSource).not.toMatch(/async getBalanceAnalysisDecisionItems\(/);
    expect(clientSource).not.toMatch(/async updateBalanceAnalysisDecisionStatus\(/);
    expect(clientSource).not.toMatch(/async exportBalanceAnalysisSummaryCsv\(/);
    expect(clientSource).not.toMatch(/async exportBalanceAnalysisWorkbookXlsx\(/);
    expect(clientSource).not.toMatch(/async refreshBalanceAnalysis\(/);
    expect(clientSource).not.toMatch(/async getBalanceAnalysisRefreshStatus\(/);
    expect(clientSource).not.toMatch(/async getPositionsBondSubTypes\(/);
    expect(clientSource).not.toMatch(/async getPositionsBondsList\(/);
    expect(clientSource).not.toMatch(/async getPositionsCounterpartyBonds\(/);
    expect(clientSource).not.toMatch(/async getPositionsInterbankProductTypes\(/);
    expect(clientSource).not.toMatch(/async getPositionsInterbankList\(/);
    expect(clientSource).not.toMatch(/async getPositionsCounterpartyInterbankSplit\(/);
    expect(clientSource).not.toMatch(/async getPositionsStatsRating\(/);
    expect(clientSource).not.toMatch(/async getPositionsStatsIndustry\(/);
    expect(clientSource).not.toMatch(/async getPositionsCustomerDetails\(/);
    expect(clientSource).not.toMatch(/async getPositionsCustomerTrend\(/);
    expect(clientSource).not.toMatch(/async getLiabilityRiskBuckets\(/);
    expect(clientSource).not.toMatch(/async getLiabilityYieldMetrics\(/);
    expect(clientSource).not.toMatch(/async getYieldByPeriod\(/);
    expect(clientSource).not.toMatch(/async getLiabilityCounterparty\(/);
    expect(clientSource).not.toMatch(/async getLiabilityKnowledgeBrief\(/);
    expect(clientSource).not.toMatch(/async getCockpitWarnings\(/);
    expect(clientSource).not.toMatch(/async getContributionSplit\(/);
    expect(clientSource).not.toMatch(/async getLiabilitiesMonthly\(/);
    expect(clientSource).not.toMatch(/async getLiabilityAdbMonthly\(/);
    expect(clientSource).not.toMatch(/async getAdb\(/);
    expect(clientSource).not.toMatch(/async getAdbComparison\(/);
    expect(clientSource).not.toMatch(/async getAdbMonthly\(/);
    expect(clientSource).not.toMatch(/async getAdbCoverage\(/);
    expect(clientSource).not.toMatch(/async getProductCategoryDates\(/);
    expect(clientSource).not.toMatch(/async refreshProductCategoryPnl\(/);
    expect(clientSource).not.toMatch(/async getProductCategoryRefreshStatus\(/);
    expect(clientSource).not.toMatch(/async createProductCategoryManualAdjustment\(/);
    expect(clientSource).not.toMatch(/async getProductCategoryManualAdjustments\(/);
    expect(clientSource).not.toMatch(/async exportProductCategoryManualAdjustmentsCsv\(/);
    expect(clientSource).not.toMatch(/async updateProductCategoryManualAdjustment\(/);
    expect(clientSource).not.toMatch(/async revokeProductCategoryManualAdjustment\(/);
    expect(clientSource).not.toMatch(/async restoreProductCategoryManualAdjustment\(/);
    expect(clientSource).not.toMatch(/async getProductCategoryPnl\(/);
    expect(clientSource).not.toMatch(/async getProductCategoryAttribution\(/);
    expect(clientSource).not.toMatch(/async getQdbGlMonthlyAnalysisDates\(/);
    expect(clientSource).not.toMatch(/async getQdbGlMonthlyAnalysisWorkbook\(/);
    expect(clientSource).not.toMatch(/async exportQdbGlMonthlyAnalysisWorkbookXlsx\(/);
    expect(clientSource).not.toMatch(/async refreshQdbGlMonthlyAnalysis\(/);
    expect(clientSource).not.toMatch(/async getQdbGlMonthlyAnalysisRefreshStatus\(/);
    expect(clientSource).not.toMatch(/async getQdbGlMonthlyAnalysisScenario\(/);
    expect(clientSource).not.toMatch(/async createQdbGlMonthlyAnalysisManualAdjustment\(/);
    expect(clientSource).not.toMatch(/async updateQdbGlMonthlyAnalysisManualAdjustment\(/);
    expect(clientSource).not.toMatch(/async revokeQdbGlMonthlyAnalysisManualAdjustment\(/);
    expect(clientSource).not.toMatch(/async restoreQdbGlMonthlyAnalysisManualAdjustment\(/);
    expect(clientSource).not.toMatch(/async getQdbGlMonthlyAnalysisManualAdjustments\(/);
    expect(clientSource).not.toMatch(/async exportQdbGlMonthlyAnalysisManualAdjustmentsCsv\(/);
  });

  it("requires marketDataClient.ts to own the extracted market-data composition slice", () => {
    expect(marketDataSource).toMatch(/async getSourceFoundation\(/);
    expect(marketDataSource).toMatch(/async refreshSourcePreview\(/);
    expect(marketDataSource).toMatch(/async getSourcePreviewRefreshStatus\(/);
    expect(marketDataSource).toMatch(/async getSourceFoundationHistory\(/);
    expect(marketDataSource).toMatch(/async getSourceFoundationRows\(/);
    expect(marketDataSource).toMatch(/async getSourceFoundationTraces\(/);
    expect(marketDataSource).toMatch(/async getChoiceNewsEvents\(/);
    expect(marketDataSource).toMatch(/async getResearchCalendarEvents\(/);
    expect(marketDataSource).toMatch(/async ingestTushareNprNews\(/);
  });

  it("requires KPI and cube clients to own their extracted composition slices", () => {
    expect(kpiSource).toContain("requestKpiJson");
    expect(kpiSource).toMatch(/async getKpiOwners\(/);
    expect(kpiSource).toMatch(/async fetchAndRecalcKpi\(/);
    expect(cubeSource).toMatch(/async getCubeDimensions\(/);
    expect(cubeSource).toMatch(/async executeCubeQuery\(/);
  });

  it("requires agentClient.ts to own agent query implementations", () => {
    expect(agentClientSource).toContain("buildStableDemoAgentEnvelope");
    expect(agentClientSource).toContain("/api/agent/query");
    expect(agentClientSource).toMatch(/async queryAgent\(/);
    expect(agentClientSource).toMatch(/create(Mock|Demo)AgentClient/);
  });

  it("requires executiveClient.ts to own executive and home thin implementations", () => {
    expect(executiveClientSource).toContain("createDemoExecutiveClient");
    expect(executiveClientSource).toContain("createRealExecutiveClient");
    expect(executiveClientSource).toContain("/ui/home/overview");
    expect(executiveClientSource).toContain("/ui/home/summary");
    expect(executiveClientSource).toContain("/ui/risk/overview");
    expect(executiveClientSource).toContain("/ui/home/contribution");
    expect(executiveClientSource).toContain("/ui/home/alerts");
    expect(executiveClientSource).toContain("/api/risk/tensor/dates");
    expect(executiveClientSource).toContain("risk.tensor");
    expect(executiveClientSource).toMatch(/async getOverview\(/);
    expect(executiveClientSource).toMatch(/async getHomeSnapshot\(/);
    expect(executiveClientSource).toMatch(/async getSummary\(/);
    expect(executiveClientSource).toMatch(/async getRiskOverview\(/);
    expect(executiveClientSource).toMatch(/async getRiskTensorDates\(/);
    expect(executiveClientSource).toMatch(/async getRiskTensor\(/);
    expect(executiveClientSource).toMatch(/async getContribution\(/);
    expect(executiveClientSource).toMatch(/async getAlerts\(/);
    expect(executiveClientSource).toMatch(/async getPlaceholderSnapshot\(/);
  });

  it("requires bondAnalyticsClient.ts to own Bond Dashboard API implementations", () => {
    expect(bondAnalyticsClientSource).toContain("createDemoBondDashboardClient");
    expect(bondAnalyticsClientSource).toContain("createRealBondDashboardClient");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/dates");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/headline-kpis");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/asset-structure");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/yield-distribution");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/portfolio-comparison");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/spread-analysis");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/maturity-structure");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/industry-distribution");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/risk-indicators");
    expect(bondAnalyticsClientSource).toContain("bond_dashboard.headline_kpis");
    expect(bondAnalyticsClientSource).toContain("bond_dashboard.risk_indicators");
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardDates\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardHeadlineKpis\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardAssetStructure\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardYieldDistribution\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardPortfolioComparison\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardSpreadAnalysis\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardMaturityStructure\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardIndustryDistribution\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardRiskIndicators\(/);
  });

  it("requires bondAnalyticsClient.ts to own Bond Analytics API implementations", () => {
    expect(bondAnalyticsClientSource).toContain("createDemoBondAnalyticsClient");
    expect(bondAnalyticsClientSource).toContain("createRealBondAnalyticsClient");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/dates");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/refresh");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/refresh-status");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/return-decomposition");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/benchmark-excess");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/krd-curve-risk");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/action-attribution");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/accounting-class-audit");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/credit-spread-migration");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/portfolio-headlines");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/top-holdings");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/yield-curve-term-structure");
    expect(bondAnalyticsClientSource).toContain("/api/credit-spread-analysis/detail");
    expect(bondAnalyticsClientSource).toContain("bond_analytics.return_decomposition");
    expect(bondAnalyticsClientSource).toContain("bond_analytics.credit_spread_migration");
    expect(bondAnalyticsClientSource).toMatch(/async refreshBondAnalytics\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsRefreshStatus\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsDates\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsReturnDecomposition\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsBenchmarkExcess\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsKrdCurveRisk\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsActionAttribution\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsAccountingClassAudit\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsCreditSpreadMigration\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsPortfolioHeadlines\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsTopHoldings\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsYieldCurveTermStructure\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getCreditSpreadAnalysisDetail\(/);
  });

  it("requires balanceAnalysisClient.ts to own Balance Analysis API implementations", () => {
    expect(balanceAnalysisClientSource).toContain("createDemoBalanceAnalysisClient");
    expect(balanceAnalysisClientSource).toContain("createRealBalanceAnalysisClient");
    expect(balanceAnalysisClientSource).toContain("buildBalanceAnalysisTableRows");
    expect(balanceAnalysisClientSource).toContain("BalanceAnalysisAmountField");
    expect(balanceAnalysisClientSource).toContain("/ui/balance-analysis/dates");
    expect(balanceAnalysisClientSource).toContain("/ui/balance-analysis/overview");
    expect(balanceAnalysisClientSource).toContain("/ui/balance-analysis/summary");
    expect(balanceAnalysisClientSource).toContain("/ui/balance-analysis/workbook");
    expect(balanceAnalysisClientSource).toContain("/ui/balance-analysis/current-user");
    expect(balanceAnalysisClientSource).toContain("/ui/balance-analysis/decision-items");
    expect(balanceAnalysisClientSource).toContain("/ui/balance-analysis/decision-items/status");
    expect(balanceAnalysisClientSource).toContain("/ui/balance-analysis/summary-by-basis");
    expect(balanceAnalysisClientSource).toContain("/ui/balance-analysis/advanced-attribution");
    expect(balanceAnalysisClientSource).toContain("/ui/balance-analysis/summary/export");
    expect(balanceAnalysisClientSource).toContain("/ui/balance-analysis/workbook/export");
    expect(balanceAnalysisClientSource).toContain("/ui/balance-analysis/refresh");
    expect(balanceAnalysisClientSource).toContain("/ui/balance-analysis/refresh-status");
    expect(balanceAnalysisClientSource).toContain("balance-analysis.overview");
    expect(balanceAnalysisClientSource).toContain("balance-analysis.advanced_attribution_bundle");
    expect(balanceAnalysisClientSource).toMatch(/async getBalanceAnalysisDates\(/);
    expect(balanceAnalysisClientSource).toMatch(/async getBalanceAnalysisOverview\(/);
    expect(balanceAnalysisClientSource).toMatch(/async getBalanceAnalysisDetail\(/);
    expect(balanceAnalysisClientSource).toMatch(/async getBalanceAnalysisSummaryByBasis\(/);
    expect(balanceAnalysisClientSource).toMatch(/async getBalanceAnalysisAdvancedAttribution\(/);
    expect(balanceAnalysisClientSource).toMatch(/async getBalanceAnalysisSummary\(/);
    expect(balanceAnalysisClientSource).toMatch(/async getBalanceAnalysisWorkbook\(/);
    expect(balanceAnalysisClientSource).toMatch(/async getBalanceAnalysisCurrentUser\(/);
    expect(balanceAnalysisClientSource).toMatch(/async getBalanceAnalysisDecisionItems\(/);
    expect(balanceAnalysisClientSource).toMatch(/async updateBalanceAnalysisDecisionStatus\(/);
    expect(balanceAnalysisClientSource).toMatch(/async exportBalanceAnalysisSummaryCsv\(/);
    expect(balanceAnalysisClientSource).toMatch(/async exportBalanceAnalysisWorkbookXlsx\(/);
    expect(balanceAnalysisClientSource).toMatch(/async refreshBalanceAnalysis\(/);
    expect(balanceAnalysisClientSource).toMatch(/async getBalanceAnalysisRefreshStatus\(/);
  });

  it("requires positionsClient.ts to own Positions API implementations", () => {
    expect(positionsClientSource).toContain("createDemoPositionsClient");
    expect(positionsClientSource).toContain("createRealPositionsClient");
    expect(positionsClientSource).not.toContain("getLiabilityRiskBuckets");
    expect(positionsClientSource).not.toContain("getAdbComparison");
    expect(positionsClientSource).toContain("/api/positions/bonds/sub_types");
    expect(positionsClientSource).toContain("/api/positions/bonds");
    expect(positionsClientSource).toContain("/api/positions/counterparty/bonds");
    expect(positionsClientSource).toContain("/api/positions/interbank/product_types");
    expect(positionsClientSource).toContain("/api/positions/interbank");
    expect(positionsClientSource).toContain("/api/positions/counterparty/interbank/split");
    expect(positionsClientSource).toContain("/api/positions/stats/rating");
    expect(positionsClientSource).toContain("/api/positions/stats/industry");
    expect(positionsClientSource).toContain("/api/positions/customer/details");
    expect(positionsClientSource).toContain("/api/positions/customer/trend");
    expect(positionsClientSource).toContain("positions.bonds.sub_types");
    expect(positionsClientSource).toContain("positions.counterparty.interbank.split");
    expect(positionsClientSource).toMatch(/async getPositionsBondSubTypes\(/);
    expect(positionsClientSource).toMatch(/async getPositionsBondsList\(/);
    expect(positionsClientSource).toMatch(/async getPositionsCounterpartyBonds\(/);
    expect(positionsClientSource).toMatch(/async getPositionsInterbankProductTypes\(/);
    expect(positionsClientSource).toMatch(/async getPositionsInterbankList\(/);
    expect(positionsClientSource).toMatch(/async getPositionsCounterpartyInterbankSplit\(/);
    expect(positionsClientSource).toMatch(/async getPositionsStatsRating\(/);
    expect(positionsClientSource).toMatch(/async getPositionsStatsIndustry\(/);
    expect(positionsClientSource).toMatch(/async getPositionsCustomerDetails\(/);
    expect(positionsClientSource).toMatch(/async getPositionsCustomerTrend\(/);
  });

  it("requires liabilityAdbClient.ts to own Liability and ADB API implementations", () => {
    expect(liabilityAdbClientSource).toContain("createDemoLiabilityAdbClient");
    expect(liabilityAdbClientSource).toContain("createRealLiabilityAdbClient");
    expect(liabilityAdbClientSource).toContain("/api/risk/buckets");
    expect(liabilityAdbClientSource).toContain("/api/analysis/yield_metrics");
    expect(liabilityAdbClientSource).toContain("/api/analysis/yield-by-period");
    expect(liabilityAdbClientSource).toContain("/api/analysis/liabilities/counterparty");
    expect(liabilityAdbClientSource).toContain("/ui/liability/business-context");
    expect(liabilityAdbClientSource).toContain("/api/analysis/liabilities/cockpit-warnings");
    expect(liabilityAdbClientSource).toContain("/api/analysis/liabilities/contribution-split");
    expect(liabilityAdbClientSource).toContain("/api/liabilities/monthly");
    expect(liabilityAdbClientSource).toContain("/api/analysis/adb");
    expect(liabilityAdbClientSource).toContain("liability.cockpit_warnings");
    expect(liabilityAdbClientSource).toContain("liability.contribution_split");
    expect(liabilityAdbClientSource).toContain("liability.page_knowledge");
    expect(liabilityAdbClientSource).toContain("requestPlainJson");
    expect(liabilityAdbClientSource).toContain("requestEnvelopeOrPlainJson");
    expect(liabilityAdbClientSource).toContain("requestEnvelopeOrPlainJsonWithMeta");
    expect(liabilityAdbClientSource).toContain("normalizeAccountingBasisTrendItem");
    expect(liabilityAdbClientSource).toContain("normalizeAdbComparisonResponse");
    expect(liabilityAdbClientSource).toContain("normalizeAdbMonthlyResponse");
    expect(liabilityAdbClientSource).toMatch(/async getLiabilityRiskBuckets\(/);
    expect(liabilityAdbClientSource).toMatch(/async getLiabilityYieldMetrics\(/);
    expect(liabilityAdbClientSource).toMatch(/async getYieldByPeriod\(/);
    expect(liabilityAdbClientSource).toMatch(/async getLiabilityCounterparty\(/);
    expect(liabilityAdbClientSource).toMatch(/async getLiabilityKnowledgeBrief\(/);
    expect(liabilityAdbClientSource).toMatch(/async getCockpitWarnings\(/);
    expect(liabilityAdbClientSource).toMatch(/async getContributionSplit\(/);
    expect(liabilityAdbClientSource).toMatch(/async getLiabilitiesMonthly\(/);
    expect(liabilityAdbClientSource).toMatch(/async getLiabilityAdbMonthly\(/);
    expect(liabilityAdbClientSource).toMatch(/async getAdb\(/);
    expect(liabilityAdbClientSource).toMatch(/async getAdbComparison\(/);
    expect(liabilityAdbClientSource).toMatch(/async getAdbMonthly\(/);
    expect(liabilityAdbClientSource).toMatch(/async getAdbCoverage\(/);
  });

  it("requires productCategoryClient.ts to own Product Category API implementations", () => {
    expect(productCategoryClientSource).toContain("createDemoProductCategoryClient");
    expect(productCategoryClientSource).toContain("createRealProductCategoryClient");
    expect(productCategoryClientSource).toContain("/ui/pnl/product-category/dates");
    expect(productCategoryClientSource).toContain("/ui/pnl/product-category/refresh");
    expect(productCategoryClientSource).toContain("/ui/pnl/product-category/refresh-status");
    expect(productCategoryClientSource).toContain("/ui/pnl/product-category/manual-adjustments");
    expect(productCategoryClientSource).toContain("/ui/pnl/product-category/manual-adjustments/export");
    expect(productCategoryClientSource).toContain("/ui/pnl/product-category/attribution");
    expect(productCategoryClientSource).toContain("product_category_pnl.dates");
    expect(productCategoryClientSource).toContain("product_category_pnl:mock-run");
    expect(productCategoryClientSource).toContain("product_category_pnl_adjustments");
    expect(productCategoryClientSource).toContain("buildMockProductCategoryPnlEnvelope");
    expect(productCategoryClientSource).toContain("buildMockProductCategoryAttributionEnvelope");
    expect(productCategoryClientSource).toContain("mockManualAdjustments");
    expect(productCategoryClientSource).toContain("mockManualAdjustmentSeq");
    expect(productCategoryClientSource).toContain("reduceLatestManualAdjustments");
    expect(productCategoryClientSource).toContain("filterManualAdjustments");
    expect(productCategoryClientSource).toContain("sortManualAdjustments");
    expect(productCategoryClientSource).toContain("buildManualAdjustmentSearchParams");
    expect(productCategoryClientSource).not.toContain("getQdbGlMonthlyAnalysisDates");
    expect(productCategoryClientSource).not.toContain("/ui/qdb-gl-monthly-analysis");
    expect(productCategoryClientSource).toMatch(/async getProductCategoryDates\(/);
    expect(productCategoryClientSource).toMatch(/async refreshProductCategoryPnl\(/);
    expect(productCategoryClientSource).toMatch(/async getProductCategoryRefreshStatus\(/);
    expect(productCategoryClientSource).toMatch(/async createProductCategoryManualAdjustment\(/);
    expect(productCategoryClientSource).toMatch(/async getProductCategoryManualAdjustments\(/);
    expect(productCategoryClientSource).toMatch(/async exportProductCategoryManualAdjustmentsCsv\(/);
    expect(productCategoryClientSource).toMatch(/async updateProductCategoryManualAdjustment\(/);
    expect(productCategoryClientSource).toMatch(/async revokeProductCategoryManualAdjustment\(/);
    expect(productCategoryClientSource).toMatch(/async restoreProductCategoryManualAdjustment\(/);
    expect(productCategoryClientSource).toMatch(/async getProductCategoryPnl\(/);
    expect(productCategoryClientSource).toMatch(/async getProductCategoryAttribution\(/);
  });

  it("requires qdbGlMonthlyAnalysisClient.ts to own QDB GL Monthly Analysis API implementations", () => {
    expect(qdbGlMonthlyAnalysisClientSource).toContain("createDemoQdbGlMonthlyAnalysisClient");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("createRealQdbGlMonthlyAnalysisClient");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("/ui/qdb-gl-monthly-analysis/dates");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("/ui/qdb-gl-monthly-analysis/workbook");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("/ui/qdb-gl-monthly-analysis/workbook/export");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("/ui/qdb-gl-monthly-analysis/refresh");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("/ui/qdb-gl-monthly-analysis/refresh-status");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("/ui/qdb-gl-monthly-analysis/scenario");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("/ui/qdb-gl-monthly-analysis/manual-adjustments");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("/ui/qdb-gl-monthly-analysis/manual-adjustments/export");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("qdb-gl-monthly-analysis.dates");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("qdb-gl-monthly-analysis.workbook");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("qdb-gl-monthly-analysis.scenario");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("qdb_gl_monthly_analysis:");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("qdb_gl_monthly_analysis.analytical");
    expect(qdbGlMonthlyAnalysisClientSource).toContain("monthly_operating_analysis_adjustments");
    expect(qdbGlMonthlyAnalysisClientSource).not.toContain("/ui/pnl/product-category");
    expect(qdbGlMonthlyAnalysisClientSource).not.toContain("getCashflowProjection");
    expect(qdbGlMonthlyAnalysisClientSource).toMatch(/async getQdbGlMonthlyAnalysisDates\(/);
    expect(qdbGlMonthlyAnalysisClientSource).toMatch(/async getQdbGlMonthlyAnalysisWorkbook\(/);
    expect(qdbGlMonthlyAnalysisClientSource).toMatch(/async exportQdbGlMonthlyAnalysisWorkbookXlsx\(/);
    expect(qdbGlMonthlyAnalysisClientSource).toMatch(/async refreshQdbGlMonthlyAnalysis\(/);
    expect(qdbGlMonthlyAnalysisClientSource).toMatch(/async getQdbGlMonthlyAnalysisRefreshStatus\(/);
    expect(qdbGlMonthlyAnalysisClientSource).toMatch(/async getQdbGlMonthlyAnalysisScenario\(/);
    expect(qdbGlMonthlyAnalysisClientSource).toMatch(/async createQdbGlMonthlyAnalysisManualAdjustment\(/);
    expect(qdbGlMonthlyAnalysisClientSource).toMatch(/async updateQdbGlMonthlyAnalysisManualAdjustment\(/);
    expect(qdbGlMonthlyAnalysisClientSource).toMatch(/async revokeQdbGlMonthlyAnalysisManualAdjustment\(/);
    expect(qdbGlMonthlyAnalysisClientSource).toMatch(/async restoreQdbGlMonthlyAnalysisManualAdjustment\(/);
    expect(qdbGlMonthlyAnalysisClientSource).toMatch(/async getQdbGlMonthlyAnalysisManualAdjustments\(/);
    expect(qdbGlMonthlyAnalysisClientSource).toMatch(/async exportQdbGlMonthlyAnalysisManualAdjustmentsCsv\(/);
  });

  it("requires healthClient.ts to own health endpoint implementations", () => {
    expect(clientSource).not.toContain("/health/ready");
    expect(clientSource).not.toContain("/health/live");
    expect(clientSource).not.toMatch(/async getHealthLive\(/);
    expect(healthClientSource).toContain("/health/ready");
    expect(healthClientSource).toContain("/health/live");
    expect(healthClientSource).toContain("/health");
  });

  it("keeps first-screen providers and shell on the lightweight API context boundary", () => {
    expect(providersSource).toMatch(/from\s+["']\.\.\/api\/clientContext["']/);
    expect(providersSource).not.toMatch(/from\s+["']\.\.\/api\/client["']/);
    expect(shellSource).toMatch(/from\s+["']\.\.\/api\/clientContext["']/);
    expect(shellSource).not.toMatch(/from\s+["']\.\.\/api\/client["']/);
    expect(dataModeRibbonSource).toMatch(/from\s+["']\.\.\/api\/clientContext["']/);
    expect(dataModeRibbonSource).not.toMatch(/from\s+["']\.\.\/api\/client["']/);
    expect(clientContextSource).toContain("createDeferredApiClient");
    expect(clientContextSource).not.toMatch(/import\s+\{[^}]*createApiClient/);
    expect(clientSource).toContain("from \"./clientContext\"");
  });
});
