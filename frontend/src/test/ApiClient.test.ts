import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";

describe("createApiClient", () => {
  it("uses mock mode by default", async () => {
    const client = createApiClient({ mode: "mock" });

    const payload = await client.getOverview();

    expect(payload.result_meta.basis).toBe("mock");
    expect(payload.result.title).toBe("经营总览（演示）");
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
      json: async () => ({
        detail: "Source preview refresh already in progress.",
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await expect(client.refreshSourcePreview()).rejects.toThrow(
      "Source preview refresh already in progress.",
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
        cache_key: "pnl.phase2.materialize",
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
        cache_key: "pnl.phase2.materialize",
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
    expect(paged.result.total_rows).toBe(3);
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
});
