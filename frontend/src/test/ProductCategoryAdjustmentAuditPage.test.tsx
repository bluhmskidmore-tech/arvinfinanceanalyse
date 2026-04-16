import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ProductCategoryManualAdjustmentQuery } from "../api/contracts";
import { routerFuture } from "../router/routerFuture";
import { createWorkbenchMemoryRouter } from "./renderWorkbenchApp";

function renderAuditPageWithClient(client: ReturnType<typeof createApiClient>) {
  const router = createWorkbenchMemoryRouter(["/product-category-pnl/audit"]);
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: 0,
        refetchOnWindowFocus: false,
      },
    },
  });

  return render(
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} future={routerFuture} />
      </QueryClientProvider>
    </ApiClientProvider>,
  );
}

describe("ProductCategoryAdjustmentAuditPage", () => {
  it("renders the independent audit view with current-state rows and timeline rows", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderAuditPageWithClient({
      ...baseClient,
      getProductCategoryManualAdjustments: async () => ({
        report_date: "2026-02-28",
        adjustment_count: 1,
        adjustment_limit: 20,
        adjustment_offset: 0,
        event_total: 2,
        event_limit: 20,
        event_offset: 0,
        adjustments: [
          {
            adjustment_id: "pca-audit-1",
            event_type: "edited",
            created_at: "2026-04-10T11:00:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "audit-account",
            monthly_pnl: "8",
          },
        ],
        events: [
          {
            adjustment_id: "pca-audit-1",
            event_type: "edited",
            created_at: "2026-04-10T11:00:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "audit-account",
            monthly_pnl: "8",
          },
          {
            adjustment_id: "pca-audit-1",
            event_type: "created",
            created_at: "2026-04-10T10:30:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "audit-account",
            monthly_pnl: "5",
          },
        ],
      }),
    });

    expect(await screen.findByTestId("product-category-audit-page-title")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-audit-boundary-copy")).toHaveTextContent(
      "查看产品类别损益",
    );
    expect(screen.getByText(/Audit view records adjustment events/)).toBeInTheDocument();
    expect(screen.getByTestId("product-category-audit-filter-lead")).toHaveTextContent(
      "审计筛选与排序",
    );
    expect(screen.getByTestId("product-category-audit-manual-lead")).toHaveTextContent(
      "手工调整录入",
    );
    expect(screen.getByTestId("product-category-audit-timeline-lead")).toHaveTextContent(
      "调整审计时间线",
    );
    expect(await screen.findByTestId("audit-current-state")).toBeInTheDocument();
    expect(screen.getByTestId("audit-event-list")).toBeInTheDocument();
    expect(screen.getByText("audit-account")).toBeInTheDocument();
    expect(screen.getByTestId("audit-event-pca-audit-1-edited")).toBeInTheDocument();
    expect(screen.getByTestId("audit-event-pca-audit-1-created")).toBeInTheDocument();
  });

  it("applies audit filters and paginates timeline requests", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const listSpy = vi
      .fn()
      .mockResolvedValueOnce({
        report_date: "2026-02-28",
        adjustment_count: 1,
        adjustment_limit: 2,
        adjustment_offset: 0,
        event_total: 3,
        event_limit: 2,
        event_offset: 0,
        adjustments: [],
        events: [
          {
            adjustment_id: "pca-audit-1",
            event_type: "edited",
            created_at: "2026-04-10T11:00:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "audit-account",
          },
          {
            adjustment_id: "pca-audit-1",
            event_type: "created",
            created_at: "2026-04-10T10:30:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "audit-account",
          },
        ],
      })
      .mockResolvedValueOnce({
        report_date: "2026-02-28",
        adjustment_count: 0,
        adjustment_limit: 2,
        adjustment_offset: 0,
        event_total: 1,
        event_limit: 2,
        event_offset: 0,
        adjustments: [],
        events: [
          {
            adjustment_id: "pca-audit-1",
            event_type: "edited",
            created_at: "2026-04-10T11:00:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "audit-account",
          },
        ],
      })
      .mockResolvedValueOnce({
        report_date: "2026-02-28",
        adjustment_count: 0,
        adjustment_limit: 2,
        adjustment_offset: 0,
        event_total: 3,
        event_limit: 2,
        event_offset: 2,
        adjustments: [],
        events: [
          {
            adjustment_id: "pca-audit-1",
            event_type: "restored",
            created_at: "2026-04-10T11:30:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "audit-account",
          },
        ],
      })
      .mockResolvedValue({
        report_date: "2026-02-28",
        adjustment_count: 0,
        adjustment_limit: 2,
        adjustment_offset: 0,
        event_total: 3,
        event_limit: 2,
        event_offset: 2,
        adjustments: [],
        events: [
          {
            adjustment_id: "pca-audit-1",
            event_type: "restored",
            created_at: "2026-04-10T11:30:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "audit-account",
          },
        ],
      });

    renderAuditPageWithClient({
      ...baseClient,
      getProductCategoryManualAdjustments: listSpy,
    });

    await screen.findByTestId("audit-current-state");
    await user.click(screen.getByTestId("audit-exact-adjustment-id"));
    await user.selectOptions(screen.getByTestId("audit-page-size-select"), "2");
    await user.type(screen.getByTestId("audit-filter-adjustment-id"), "pca-audit-1");
    await user.selectOptions(screen.getByTestId("audit-filter-event-type"), "edited");
    await user.click(screen.getByTestId("audit-apply-filters"));

    await waitFor(() => {
      expect(listSpy).toHaveBeenLastCalledWith("2026-02-28", {
        adjustmentId: "pca-audit-1",
        adjustmentIdExact: true,
        accountCode: "",
        approvalStatus: "",
        eventType: "edited",
        currentSortField: "created_at",
        currentSortDir: "desc",
        eventSortField: "created_at",
        eventSortDir: "desc",
        createdAtFrom: "",
        createdAtTo: "",
        adjustmentLimit: 20,
        adjustmentOffset: 0,
        limit: 2,
        offset: 0,
      });
    });

    await user.click(screen.getByTestId("audit-next-page"));

    await waitFor(() => {
      expect(listSpy).toHaveBeenLastCalledWith("2026-02-28", {
        adjustmentId: "pca-audit-1",
        adjustmentIdExact: true,
        accountCode: "",
        approvalStatus: "",
        eventType: "edited",
        currentSortField: "created_at",
        currentSortDir: "desc",
        eventSortField: "created_at",
        eventSortDir: "desc",
        createdAtFrom: "",
        createdAtTo: "",
        adjustmentLimit: 20,
        adjustmentOffset: 0,
        limit: 2,
        offset: 2,
      });
    });
  });

  it("pages current-state rows and exports the filtered audit dataset", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const OriginalBlob = globalThis.Blob;
    const originalCreateObjectURL = globalThis.URL.createObjectURL;
    const originalRevokeObjectURL = globalThis.URL.revokeObjectURL;
    let capturedCsv = "";
    class MockBlob {
      readonly size: number;
      readonly type: string;

      constructor(parts: BlobPart[], options?: BlobPropertyBag) {
        capturedCsv = parts.map((part) => String(part)).join("");
        this.size = capturedCsv.length;
        this.type = options?.type ?? "";
      }
    }
    globalThis.Blob = MockBlob as unknown as typeof Blob;

    let capturedBlob: unknown = null;
    const createObjectUrl = vi.fn((blob: unknown) => {
      capturedBlob = blob;
      return "blob:mock";
    });
    const revokeObjectUrl = vi.fn();
    const clickSpy = vi.fn();
    const appendSpy = vi.spyOn(document.body, "appendChild");
    const removeSpy = vi.spyOn(document.body, "removeChild");
    const createElementSpy = vi.spyOn(document, "createElement");
    const exportSpy = vi.fn(async () => ({
      filename: "product-category-audit-2026-02-28.csv",
      content: [
        "Current State",
        "adjustment_id,event_type,created_at,report_date,operator,approval_status,account_code,currency,account_name",
        '"pca-audit-1","created","2026-04-10T10:30:00Z","2026-02-28","DELTA","approved","51402010001","CNX","audit-account-1"',
        '"pca-audit-2","created","2026-04-10T10:31:00Z","2026-02-28","DELTA","approved","51402010002","CNX","audit-account-2"',
        '"pca-audit-3","created","2026-04-10T10:32:00Z","2026-02-28","DELTA","pending","51402010003","CNY","audit-account-3"',
        "",
        "Event Timeline",
        "adjustment_id,event_type,created_at,report_date,operator,approval_status,account_code,currency,account_name",
        '"pca-audit-1","created","2026-04-10T10:30:00Z","2026-02-28","DELTA","approved","51402010001","CNX","audit-account-1"',
      ].join("\n"),
    }));

    globalThis.URL.createObjectURL = createObjectUrl;
    globalThis.URL.revokeObjectURL = revokeObjectUrl;

    createElementSpy.mockImplementation(((tagName: string) => {
      const element = document.createElementNS("http://www.w3.org/1999/xhtml", tagName);
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(element, "click", {
          value: clickSpy,
          configurable: true,
        });
      }
      return element as HTMLElement;
    }) as typeof document.createElement);

    const listSpy = vi
      .fn()
      .mockResolvedValueOnce({
        report_date: "2026-02-28",
        adjustment_count: 3,
        adjustment_limit: 2,
        adjustment_offset: 0,
        event_total: 1,
        event_limit: 20,
        event_offset: 0,
        adjustments: [
          {
            adjustment_id: "pca-audit-1",
            event_type: "created",
            created_at: "2026-04-10T10:30:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "audit-account-1",
          },
          {
            adjustment_id: "pca-audit-2",
            event_type: "created",
            created_at: "2026-04-10T10:31:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010002",
            currency: "CNX",
            account_name: "audit-account-2",
          },
        ],
        events: [
          {
            adjustment_id: "pca-audit-1",
            event_type: "created",
            created_at: "2026-04-10T10:30:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "audit-account-1",
          },
        ],
      })
      .mockResolvedValueOnce({
        report_date: "2026-02-28",
        adjustment_count: 3,
        adjustment_limit: 2,
        adjustment_offset: 2,
        event_total: 1,
        event_limit: 20,
        event_offset: 0,
        adjustments: [
          {
            adjustment_id: "pca-audit-3",
            event_type: "created",
            created_at: "2026-04-10T10:32:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "pending",
            account_code: "51402010003",
            currency: "CNY",
            account_name: "audit-account-3",
          },
        ],
        events: [
          {
            adjustment_id: "pca-audit-1",
            event_type: "created",
            created_at: "2026-04-10T10:30:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "audit-account-1",
          },
        ],
      })
      .mockResolvedValue({
        report_date: "2026-02-28",
        adjustment_count: 3,
        adjustment_limit: 2,
        adjustment_offset: 2,
        event_total: 1,
        event_limit: 20,
        event_offset: 0,
        adjustments: [
          {
            adjustment_id: "pca-audit-3",
            event_type: "created",
            created_at: "2026-04-10T10:32:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "pending",
            account_code: "51402010003",
            currency: "CNY",
            account_name: "audit-account-3",
          },
        ],
        events: [
          {
            adjustment_id: "pca-audit-1",
            event_type: "created",
            created_at: "2026-04-10T10:30:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "audit-account-1",
          },
        ],
      });

    renderAuditPageWithClient({
      ...baseClient,
      getProductCategoryManualAdjustments: listSpy,
      exportProductCategoryManualAdjustmentsCsv: exportSpy,
    });

    await screen.findByTestId("audit-current-state");
    await user.selectOptions(screen.getByTestId("audit-current-page-size-select"), "2");
    await user.click(screen.getByTestId("audit-current-next-page"));

    await waitFor(() => {
      expect(listSpy).toHaveBeenLastCalledWith("2026-02-28", {
        adjustmentId: "",
        adjustmentIdExact: false,
        accountCode: "",
        approvalStatus: "",
        eventType: "",
        currentSortField: "created_at",
        currentSortDir: "desc",
        eventSortField: "created_at",
        eventSortDir: "desc",
        createdAtFrom: "",
        createdAtTo: "",
        adjustmentLimit: 2,
        adjustmentOffset: 2,
        limit: 20,
        offset: 0,
      });
    });

    await user.click(screen.getByTestId("audit-export-button"));

    await waitFor(() => {
      expect(exportSpy).toHaveBeenCalledWith("2026-02-28", {
        adjustmentId: "",
        adjustmentIdExact: false,
        accountCode: "",
        approvalStatus: "",
        eventType: "",
        currentSortField: "created_at",
        currentSortDir: "desc",
        eventSortField: "created_at",
        eventSortDir: "desc",
        createdAtFrom: "",
        createdAtTo: "",
      });
      expect(createObjectUrl).toHaveBeenCalledTimes(1);
      expect(clickSpy).toHaveBeenCalledTimes(1);
      expect(appendSpy).toHaveBeenCalled();
      expect(removeSpy).toHaveBeenCalled();
      expect(revokeObjectUrl).toHaveBeenCalledWith("blob:mock");
    });
    expect(capturedBlob).not.toBeNull();
    expect(capturedCsv).toContain("pca-audit-1");
    expect(capturedCsv).toContain("pca-audit-2");
    expect(capturedCsv).toContain("pca-audit-3");

    appendSpy.mockRestore();
    removeSpy.mockRestore();
    createElementSpy.mockRestore();
    globalThis.URL.createObjectURL = originalCreateObjectURL;
    globalThis.URL.revokeObjectURL = originalRevokeObjectURL;
    globalThis.Blob = OriginalBlob;
  });

  it("keeps current and event sort controls independent and resets pagination on time-range apply/reset", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const listSpy = vi.fn(async (_reportDate: string, options?: ProductCategoryManualAdjustmentQuery) => ({
      report_date: "2026-02-28",
      adjustment_count: 4,
      adjustment_limit: options?.adjustmentLimit ?? 20,
      adjustment_offset: options?.adjustmentOffset ?? 0,
      event_total: 4,
      event_limit: options?.limit ?? 20,
      event_offset: options?.offset ?? 0,
      adjustments: [
        {
          adjustment_id: "pca-audit-1",
          event_type: "edited",
          created_at: "2026-04-10T11:00:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "51402010001",
          currency: "CNX",
          account_name: "audit-account-1",
        },
      ],
      events: [
        {
          adjustment_id: "pca-audit-1",
          event_type: "edited",
          created_at: "2026-04-10T11:00:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "51402010001",
          currency: "CNX",
          account_name: "audit-account-1",
        },
      ],
    }));

    renderAuditPageWithClient({
      ...baseClient,
      getProductCategoryManualAdjustments: listSpy,
    });

    await screen.findByTestId("audit-current-state");
    await user.selectOptions(screen.getByTestId("audit-current-page-size-select"), "2");
    await user.selectOptions(screen.getByTestId("audit-page-size-select"), "2");
    await user.click(screen.getByTestId("audit-current-next-page"));
    await user.click(screen.getByTestId("audit-next-page"));

    await waitFor(() => {
      expect(listSpy).toHaveBeenLastCalledWith("2026-02-28", expect.objectContaining({
        adjustmentOffset: 2,
        offset: 2,
      }));
    });

    await user.selectOptions(screen.getByTestId("audit-current-sort-field"), "account_code");
    await user.selectOptions(screen.getByTestId("audit-current-sort-dir"), "asc");
    await user.click(screen.getByTestId("audit-apply-filters"));

    await waitFor(() => {
      expect(listSpy).toHaveBeenLastCalledWith("2026-02-28", {
        adjustmentId: "",
        adjustmentIdExact: false,
        accountCode: "",
        approvalStatus: "",
        eventType: "",
        currentSortField: "account_code",
        currentSortDir: "asc",
        eventSortField: "created_at",
        eventSortDir: "desc",
        createdAtFrom: "",
        createdAtTo: "",
        adjustmentLimit: 2,
        adjustmentOffset: 0,
        limit: 2,
        offset: 2,
      });
    });

    await user.selectOptions(screen.getByTestId("audit-event-sort-field"), "adjustment_id");
    await user.selectOptions(screen.getByTestId("audit-event-sort-dir"), "asc");
    await user.click(screen.getByTestId("audit-apply-filters"));

    await waitFor(() => {
      expect(listSpy).toHaveBeenLastCalledWith("2026-02-28", {
        adjustmentId: "",
        adjustmentIdExact: false,
        accountCode: "",
        approvalStatus: "",
        eventType: "",
        currentSortField: "account_code",
        currentSortDir: "asc",
        eventSortField: "adjustment_id",
        eventSortDir: "asc",
        createdAtFrom: "",
        createdAtTo: "",
        adjustmentLimit: 2,
        adjustmentOffset: 0,
        limit: 2,
        offset: 0,
      });
    });

    await user.click(screen.getByTestId("audit-current-next-page"));
    await user.click(screen.getByTestId("audit-next-page"));
    await user.type(screen.getByTestId("audit-created-at-from"), "2026-04-10T00:00:00Z");
    await user.type(screen.getByTestId("audit-created-at-to"), "2026-04-10T23:59:59Z");
    await user.click(screen.getByTestId("audit-apply-filters"));

    await waitFor(() => {
      expect(listSpy).toHaveBeenLastCalledWith("2026-02-28", {
        adjustmentId: "",
        adjustmentIdExact: false,
        accountCode: "",
        approvalStatus: "",
        eventType: "",
        currentSortField: "account_code",
        currentSortDir: "asc",
        eventSortField: "adjustment_id",
        eventSortDir: "asc",
        createdAtFrom: "2026-04-10T00:00:00Z",
        createdAtTo: "2026-04-10T23:59:59Z",
        adjustmentLimit: 2,
        adjustmentOffset: 0,
        limit: 2,
        offset: 0,
      });
    });

    await user.click(screen.getByTestId("audit-current-next-page"));
    await user.click(screen.getByTestId("audit-next-page"));
    await user.click(screen.getByTestId("audit-reset-time-range"));

    await waitFor(() => {
      expect(listSpy).toHaveBeenLastCalledWith("2026-02-28", {
        adjustmentId: "",
        adjustmentIdExact: false,
        accountCode: "",
        approvalStatus: "",
        eventType: "",
        currentSortField: "account_code",
        currentSortDir: "asc",
        eventSortField: "adjustment_id",
        eventSortDir: "asc",
        createdAtFrom: "",
        createdAtTo: "",
        adjustmentLimit: 2,
        adjustmentOffset: 0,
        limit: 2,
        offset: 0,
      });
    });
  });

  it("renders the monthly operating analysis audit branch and creates an adjustment", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const createSpy = vi.fn(async () => ({
      adjustment_id: "moa-1",
      event_type: "created",
      created_at: "2026-04-12T00:00:00Z",
      stream: "monthly_operating_analysis_adjustments",
      report_month: "202602",
      adjustment_class: "mapping_adjustment" as const,
      target: { account_code: "12301", field: "industry_name" },
      operator: "OVERRIDE",
      value: "农业",
      approval_status: "approved",
    }));

    const router = createWorkbenchMemoryRouter(["/product-category-pnl/audit?branch=monthly_operating_analysis"]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: 0, refetchOnWindowFocus: false } },
    });

    render(
      <ApiClientProvider
        client={{
          ...baseClient,
          getQdbGlMonthlyAnalysisDates: async () => ({
            result_meta: {
              trace_id: "tr_qdb_dates",
              basis: "analytical" as const,
              result_kind: "qdb-gl-monthly-analysis.dates",
              formal_use_allowed: false,
              source_version: "sv_qdb_test",
              vendor_version: "vv_none",
              rule_version: "rv_qdb_gl_monthly_analysis_v1",
              cache_version: "cv_qdb_gl_monthly_analysis_v1",
              quality_flag: "ok" as const,
              vendor_status: "ok" as const,
              fallback_mode: "none" as const,
              scenario_flag: false,
              generated_at: "2026-04-12T00:00:00Z",
            },
            result: { report_months: ["202602"] },
          }),
          getQdbGlMonthlyAnalysisManualAdjustments: async () => ({
            report_month: "202602",
            adjustment_count: 0,
            adjustments: [],
            events: [],
          }),
          createQdbGlMonthlyAnalysisManualAdjustment: createSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-adjustment-class"), "mapping_adjustment");
    await user.type(screen.getByTestId("monthly-operating-analysis-mapping-account-code"), "12301");
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-mapping-field"), "industry_name");
    await user.type(screen.getByTestId("monthly-operating-analysis-adjustment-value"), "农业");
    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-submit"));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith({
        report_month: "202602",
        adjustment_class: "mapping_adjustment",
        target: { account_code: "12301", field: "industry_name" },
        operator: "OVERRIDE",
        value: "农业",
        approval_status: "approved",
      });
      expect(screen.getByText(/moa-1/)).toBeInTheDocument();
    });
  });

  it("shows structured Chinese guidance for mapping adjustments", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const router = createWorkbenchMemoryRouter(["/product-category-pnl/audit?branch=monthly_operating_analysis"]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: 0, refetchOnWindowFocus: false } },
    });

    render(
      <ApiClientProvider
        client={{
          ...baseClient,
          getQdbGlMonthlyAnalysisDates: async () => ({
            result_meta: {
              trace_id: "tr_qdb_dates",
              basis: "analytical" as const,
              result_kind: "qdb-gl-monthly-analysis.dates",
              formal_use_allowed: false,
              source_version: "sv_qdb_test",
              vendor_version: "vv_none",
              rule_version: "rv_qdb_gl_monthly_analysis_v1",
              cache_version: "cv_qdb_gl_monthly_analysis_v1",
              quality_flag: "ok" as const,
              vendor_status: "ok" as const,
              fallback_mode: "none" as const,
              scenario_flag: false,
              generated_at: "2026-04-12T00:00:00Z",
            },
            result: { report_months: ["202602"] },
          }),
          getQdbGlMonthlyAnalysisManualAdjustments: async () => ({
            report_month: "202602",
            adjustment_count: 0,
            adjustments: [],
            events: [],
          }),
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-adjustment-class"), "mapping_adjustment");

    expect(screen.getByText("映射目标")).toBeInTheDocument();
    expect(screen.getByLabelText("映射科目代码")).toBeInTheDocument();
    expect(screen.getByLabelText("映射字段")).toBeInTheDocument();
    expect(screen.getByText("用于修正名称类映射，不直接改分析结果。")).toBeInTheDocument();
  });

  it("validates structured analysis adjustment fields before submit", async () => {
    const user = userEvent.setup();
    const createSpy = vi.fn();
    const baseClient = createApiClient({ mode: "mock" });
    const router = createWorkbenchMemoryRouter(["/product-category-pnl/audit?branch=monthly_operating_analysis"]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: 0, refetchOnWindowFocus: false } },
    });

    render(
      <ApiClientProvider
        client={{
          ...baseClient,
          getQdbGlMonthlyAnalysisDates: async () => ({
            result_meta: {
              trace_id: "tr_qdb_dates",
              basis: "analytical" as const,
              result_kind: "qdb-gl-monthly-analysis.dates",
              formal_use_allowed: false,
              source_version: "sv_qdb_test",
              vendor_version: "vv_none",
              rule_version: "rv_qdb_gl_monthly_analysis_v1",
              cache_version: "cv_qdb_gl_monthly_analysis_v1",
              quality_flag: "ok" as const,
              vendor_status: "ok" as const,
              fallback_mode: "none" as const,
              scenario_flag: false,
              generated_at: "2026-04-12T00:00:00Z",
            },
            result: { report_months: ["202602"] },
          }),
          getQdbGlMonthlyAnalysisManualAdjustments: async () => ({
            report_month: "202602",
            adjustment_count: 0,
            adjustments: [],
            events: [],
          }),
          createQdbGlMonthlyAnalysisManualAdjustment: createSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    expect(screen.getByTestId("monthly-operating-analysis-audit-title")).toHaveTextContent(
      "月度经营分析调整审计",
    );
    expect(screen.getByTestId("monthly-operating-analysis-audit-boundary-copy")).toHaveTextContent(
      "手工调整",
    );
    expect(screen.getByText(/preserves separation from legacy product-category formal results/)).toBeInTheDocument();
    expect(screen.getByTestId("monthly-operating-analysis-audit-form-lead")).toHaveTextContent(
      "月度经营调整录入",
    );
    expect(screen.getByTestId("monthly-operating-analysis-audit-list-lead")).toHaveTextContent(
      "月度经营调整记录",
    );
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-adjustment-class"), "analysis_adjustment");
    await user.type(screen.getByTestId("monthly-operating-analysis-adjustment-value"), "manual_override");
    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-submit"));

    expect(createSpy).not.toHaveBeenCalled();
    expect(screen.getByText("请完整填写分析调整的工作表、行标识和指标标识。")).toBeInTheDocument();
  });

  it("uses controlled analysis target options and submits structured payload", async () => {
    const user = userEvent.setup();
    const createSpy = vi.fn(async () => ({
      adjustment_id: "moa-analysis-1",
      event_type: "created",
      created_at: "2026-04-12T00:00:00Z",
      stream: "monthly_operating_analysis_adjustments",
      report_month: "202602",
      adjustment_class: "analysis_adjustment" as const,
      target: {
        section_key: "overview",
        row_key: "loan_ratio",
        metric_key: "value",
      },
      operator: "OVERRIDE",
      value: "70.5",
      approval_status: "approved",
    }));
    const baseClient = createApiClient({ mode: "mock" });
    const router = createWorkbenchMemoryRouter(["/product-category-pnl/audit?branch=monthly_operating_analysis"]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: 0, refetchOnWindowFocus: false } },
    });

    render(
      <ApiClientProvider
        client={{
          ...baseClient,
          getQdbGlMonthlyAnalysisDates: async () => ({
            result_meta: {
              trace_id: "tr_qdb_dates",
              basis: "analytical" as const,
              result_kind: "qdb-gl-monthly-analysis.dates",
              formal_use_allowed: false,
              source_version: "sv_qdb_test",
              vendor_version: "vv_none",
              rule_version: "rv_qdb_gl_monthly_analysis_v1",
              cache_version: "cv_qdb_gl_monthly_analysis_v1",
              quality_flag: "ok" as const,
              vendor_status: "ok" as const,
              fallback_mode: "none" as const,
              scenario_flag: false,
              generated_at: "2026-04-12T00:00:00Z",
            },
            result: { report_months: ["202602"] },
          }),
          getQdbGlMonthlyAnalysisManualAdjustments: async () => ({
            report_month: "202602",
            adjustment_count: 0,
            adjustments: [],
            events: [],
          }),
          createQdbGlMonthlyAnalysisManualAdjustment: createSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-adjustment-class"), "analysis_adjustment");
    expect(screen.getByRole("option", { name: "经营概览 (overview)" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "异动预警 (alerts)" })).toBeInTheDocument();
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-analysis-section-key"), "overview");
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-analysis-row-key"), "loan_ratio");
    expect(screen.getByRole("option", { name: "指标值 (value)" })).toBeInTheDocument();
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-analysis-metric-key"), "value");
    await user.type(screen.getByTestId("monthly-operating-analysis-adjustment-value"), "70.5");
    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-submit"));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith({
        report_month: "202602",
        adjustment_class: "analysis_adjustment",
        target: {
          section_key: "overview",
          row_key: "loan_ratio",
          metric_key: "value",
        },
        operator: "OVERRIDE",
        value: "70.5",
        approval_status: "approved",
      });
    });
  });

  it("updates analysis row_key candidates when section changes", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const router = createWorkbenchMemoryRouter(["/product-category-pnl/audit?branch=monthly_operating_analysis"]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: 0, refetchOnWindowFocus: false } },
    });

    render(
      <ApiClientProvider
        client={{
          ...baseClient,
          getQdbGlMonthlyAnalysisDates: async () => ({
            result_meta: {
              trace_id: "tr_qdb_dates",
              basis: "analytical" as const,
              result_kind: "qdb-gl-monthly-analysis.dates",
              formal_use_allowed: false,
              source_version: "sv_qdb_test",
              vendor_version: "vv_none",
              rule_version: "rv_qdb_gl_monthly_analysis_v1",
              cache_version: "cv_qdb_gl_monthly_analysis_v1",
              quality_flag: "ok" as const,
              vendor_status: "ok" as const,
              fallback_mode: "none" as const,
              scenario_flag: false,
              generated_at: "2026-04-12T00:00:00Z",
            },
            result: { report_months: ["202602"] },
          }),
          getQdbGlMonthlyAnalysisManualAdjustments: async () => ({
            report_month: "202602",
            adjustment_count: 0,
            adjustments: [],
            events: [],
          }),
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-adjustment-class"), "analysis_adjustment");
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-analysis-section-key"), "alerts");

    expect(screen.getByRole("option", { name: "14001000001 / 买入返售" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "预警级别 (alert_level)" })).toBeInTheDocument();
    expect(screen.getByTestId("monthly-operating-analysis-analysis-row-key")).toHaveValue("");
  });

  it("supports edit, revoke, restore, and export in the monthly operating analysis audit branch", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const adjustment = {
      adjustment_id: "moa-1",
      event_type: "created",
      created_at: "2026-04-12T00:00:00Z",
      stream: "monthly_operating_analysis_adjustments",
      report_month: "202602",
      adjustment_class: "analysis_adjustment" as const,
      target: {
        section_key: "alerts",
        row_key: "14001000001",
        metric_key: "alert_level",
      },
      operator: "OVERRIDE",
      value: "manual_override",
      approval_status: "approved",
    };
    const listSpy = vi.fn(async () => ({
      report_month: "202602",
      adjustment_count: 1,
      adjustments: [adjustment],
      events: [adjustment],
    }));
    const updateSpy = vi.fn(async () => ({
      ...adjustment,
      event_type: "edited",
      value: "manual_override_updated",
    }));
    const revokeSpy = vi.fn(async () => ({
      ...adjustment,
      event_type: "revoked",
      approval_status: "rejected",
    }));
    const restoreSpy = vi.fn(async () => ({
      ...adjustment,
      event_type: "restored",
      approval_status: "approved",
    }));
    const exportSpy = vi.fn(async () => ({
      filename: "monthly-operating-analysis-audit-202602.csv",
      content: "adjustment_id,event_type\nmoa-1,edited\n",
    }));

    const OriginalBlob = globalThis.Blob;
    const originalCreateObjectURL = globalThis.URL.createObjectURL;
    const originalRevokeObjectURL = globalThis.URL.revokeObjectURL;
    class MockBlob {
      readonly size: number;
      readonly type: string;

      constructor(parts: BlobPart[], options?: BlobPropertyBag) {
        this.size = parts.map((part) => String(part)).join("").length;
        this.type = options?.type ?? "";
      }
    }
    globalThis.Blob = MockBlob as unknown as typeof Blob;
    const clickSpy = vi.fn();
    const createObjectUrl = vi.fn(() => "blob:monthly-audit");
    const revokeObjectUrl = vi.fn();
    const createElementSpy = vi.spyOn(document, "createElement");
    createElementSpy.mockImplementation(((tagName: string) => {
      const element = document.createElementNS("http://www.w3.org/1999/xhtml", tagName);
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(element, "click", {
          value: clickSpy,
          configurable: true,
        });
      }
      return element as HTMLElement;
    }) as typeof document.createElement);
    globalThis.URL.createObjectURL = createObjectUrl;
    globalThis.URL.revokeObjectURL = revokeObjectUrl;

    const router = createWorkbenchMemoryRouter(["/product-category-pnl/audit?branch=monthly_operating_analysis"]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: 0, refetchOnWindowFocus: false } },
    });

    render(
      <ApiClientProvider
        client={{
          ...baseClient,
          getQdbGlMonthlyAnalysisDates: async () => ({
            result_meta: {
              trace_id: "tr_qdb_dates",
              basis: "analytical" as const,
              result_kind: "qdb-gl-monthly-analysis.dates",
              formal_use_allowed: false,
              source_version: "sv_qdb_test",
              vendor_version: "vv_none",
              rule_version: "rv_qdb_gl_monthly_analysis_v1",
              cache_version: "cv_qdb_gl_monthly_analysis_v1",
              quality_flag: "ok" as const,
              vendor_status: "ok" as const,
              fallback_mode: "none" as const,
              scenario_flag: false,
              generated_at: "2026-04-12T00:00:00Z",
            },
            result: { report_months: ["202602"] },
          }),
          getQdbGlMonthlyAnalysisManualAdjustments: listSpy,
          updateQdbGlMonthlyAnalysisManualAdjustment: updateSpy,
          revokeQdbGlMonthlyAnalysisManualAdjustment: revokeSpy,
          restoreQdbGlMonthlyAnalysisManualAdjustment: restoreSpy,
          exportQdbGlMonthlyAnalysisManualAdjustmentsCsv: exportSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    expect(
      await screen.findByTestId("monthly-operating-analysis-adjustment-row-moa-1"),
    ).toBeInTheDocument();
    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-edit-moa-1"));
    expect(screen.getByTestId("monthly-operating-analysis-analysis-section-key")).toHaveValue("alerts");
    expect(screen.getByTestId("monthly-operating-analysis-analysis-row-key")).toHaveValue("14001000001");
    expect(screen.getByTestId("monthly-operating-analysis-analysis-metric-key")).toHaveValue("alert_level");
    await user.clear(screen.getByTestId("monthly-operating-analysis-adjustment-value"));
    await user.type(screen.getByTestId("monthly-operating-analysis-adjustment-value"), "manual_override_updated");
    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-submit"));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith("moa-1", {
        report_month: "202602",
        adjustment_class: "analysis_adjustment",
        target: {
          section_key: "alerts",
          row_key: "14001000001",
          metric_key: "alert_level",
        },
        operator: "OVERRIDE",
        value: "manual_override_updated",
        approval_status: "approved",
      });
    });

    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-revoke-moa-1"));
    await waitFor(() => {
      expect(revokeSpy).toHaveBeenCalledWith("moa-1");
    });

    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-restore-moa-1"));
    await waitFor(() => {
      expect(restoreSpy).toHaveBeenCalledWith("moa-1");
    });

    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-export"));
    await waitFor(() => {
      expect(exportSpy).toHaveBeenCalledWith("202602");
      expect(createObjectUrl).toHaveBeenCalledTimes(1);
      expect(clickSpy).toHaveBeenCalledTimes(1);
      expect(revokeObjectUrl).toHaveBeenCalledWith("blob:monthly-audit");
    });

    createElementSpy.mockRestore();
    globalThis.URL.createObjectURL = originalCreateObjectURL;
    globalThis.URL.revokeObjectURL = originalRevokeObjectURL;
    globalThis.Blob = OriginalBlob;
  });
});
