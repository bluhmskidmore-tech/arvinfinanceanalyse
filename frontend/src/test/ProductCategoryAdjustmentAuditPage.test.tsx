import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { beforeAll, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ProductCategoryManualAdjustmentQuery } from "../api/contracts";
import { buildProductCategoryAuditListExportQuery } from "../features/product-category-pnl/pages/productCategoryAdjustmentAuditPageModel";
import { routerFuture } from "../router/routerFuture";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { createWorkbenchMemoryRouter } from "./renderWorkbenchApp";

function manualAdjustmentListOptionsWithoutPagination(
  options: ProductCategoryManualAdjustmentQuery & {
    adjustmentLimit?: number;
    adjustmentOffset?: number;
    limit?: number;
    offset?: number;
  },
) {
  const { adjustmentLimit: _a, adjustmentOffset: _b, limit: _l, offset: _o, ...rest } = options;
  return rest;
}

describe("buildProductCategoryAuditListExportQuery", () => {
  it("keeps the same filter + current_sort_* + event_sort_* fields the list call uses, without pagination", () => {
    const applied: ProductCategoryManualAdjustmentQuery = {
      adjustmentId: "x",
      adjustmentIdExact: true,
      accountCode: "5140",
      approvalStatus: "approved",
      eventType: "edited",
      currentSortField: "approval_status",
      currentSortDir: "asc",
      eventSortField: "event_type",
      eventSortDir: "asc",
      createdAtFrom: "2026-01-01T00:00:00Z",
      createdAtTo: "2026-12-31T00:00:00Z",
    };
    const listPayload = { ...applied, adjustmentLimit: 3, adjustmentOffset: 2, limit: 5, offset: 1 };
    expect(manualAdjustmentListOptionsWithoutPagination(listPayload)).toEqual(
      buildProductCategoryAuditListExportQuery(applied),
    );
  });
});
function renderAuditPageWithClient(
  client: ReturnType<typeof createApiClient>,
  initialEntry = "/product-category-pnl/audit",
) {
  const router = createWorkbenchMemoryRouter([initialEntry]);
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

async function waitForMonthlyOperatingAnalysisAuditReady() {
  await waitFor(() => {
    expect(screen.queryByTestId("monthly-operating-analysis-audit-loading")).not.toBeInTheDocument();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-submit")).not.toBeDisabled();
  });
}

describe("ProductCategoryAdjustmentAuditPage", () => {
  // 与 ProductCategoryPnlPage.test.tsx 同源的重路由预加载，20s 上限在有负载时会稳定超时。
  beforeAll(async () => {
    await preloadWorkbenchRouteModules("product-category-pnl-audit");
  }, 60_000);

  it.each([
    {
      route: "/product-category-pnl/audit",
      rootTestId: "product-category-audit-page",
      expectedScope: "product-category-pnl",
    },
    {
      route: "/product-category-pnl/audit?branch=monthly_operating_analysis",
      rootTestId: "monthly-operating-analysis-audit-page",
      expectedScope: "product-category-pnl",
    },
  ])("declares the canonical Nocturne scope for $route", async ({
    route,
    rootTestId,
    expectedScope,
  }) => {
    renderAuditPageWithClient(createApiClient({ mode: "mock" }), route);

    expect(await screen.findByTestId(rootTestId)).toHaveAttribute(
      "data-moss-theme-scope",
      expectedScope,
    );
  });

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
    expect(screen.getByText(/审计视图只记录调整事件与刷新证据/)).toBeInTheDocument();
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

  it("Unit 5: list/timeline failure surfaces AsyncSection error, hides current+event bodies, and retry refetches", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    let failList = true;
    const successAfterRetry = {
      report_date: "2026-02-28",
      adjustment_count: 1,
      adjustment_limit: 20,
      adjustment_offset: 0,
      event_total: 0,
      event_limit: 20,
      event_offset: 0,
      adjustments: [
        {
          adjustment_id: "pca-audit-retry-1",
          event_type: "created",
          created_at: "2026-04-10T12:00:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "51402010001",
          currency: "CNX",
          account_name: "after-retry-row",
          monthly_pnl: "1",
        },
      ],
      events: [],
    };
    const listSpy = vi.fn(async () => {
      if (failList) {
        throw new Error("audit-list-initial-failure");
      }
      return successAfterRetry;
    });

    renderAuditPageWithClient({
      ...baseClient,
      getProductCategoryManualAdjustments: listSpy,
    });

    await waitFor(() => {
      expect((screen.getByLabelText("审计-报表月份") as HTMLSelectElement).value).toBeTruthy();
    });

    const listAsyncRegion = await screen.findByTestId("product-category-audit-list-timeline-async");
    const retryButton = await within(listAsyncRegion).findByRole("button", { name: "重试" });
    expect(within(listAsyncRegion).getByText(/数据载入失败/)).toBeInTheDocument();
    expect(within(listAsyncRegion).getByText(/当前页面保留重试入口/)).toBeInTheDocument();
    expect(within(listAsyncRegion).queryByTestId("audit-current-state")).not.toBeInTheDocument();
    expect(within(listAsyncRegion).queryByTestId("audit-event-list")).not.toBeInTheDocument();

    failList = false;
    await user.click(retryButton);

    await waitFor(() => {
      expect(listSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
    expect(await screen.findByTestId("audit-current-state")).toBeInTheDocument();
    expect(screen.getByText("after-retry-row")).toBeInTheDocument();
  });

  it("Unit 5: failed list refetch does not leave prior current-state or timeline rows visible", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const listSpy = vi
      .fn()
      .mockResolvedValueOnce({
        report_date: "2026-02-28",
        adjustment_count: 1,
        adjustment_limit: 20,
        adjustment_offset: 0,
        event_total: 2,
        event_limit: 20,
        event_offset: 0,
        adjustments: [
          {
            adjustment_id: "pca-audit-stale-1",
            event_type: "edited",
            created_at: "2026-04-10T11:00:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "unit5-stale-marker",
            monthly_pnl: "8",
          },
        ],
        events: [
          {
            adjustment_id: "pca-audit-stale-1",
            event_type: "edited",
            created_at: "2026-04-10T11:00:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "unit5-stale-marker",
            monthly_pnl: "8",
          },
          {
            adjustment_id: "pca-audit-stale-1",
            event_type: "created",
            created_at: "2026-04-10T10:30:00Z",
            stream: "product_category_pnl_adjustments",
            report_date: "2026-02-28",
            operator: "DELTA",
            approval_status: "approved",
            account_code: "51402010001",
            currency: "CNX",
            account_name: "unit5-stale-marker",
            monthly_pnl: "5",
          },
        ],
      })
      .mockRejectedValueOnce(new Error("audit-list-refetch-failure"));

    renderAuditPageWithClient({
      ...baseClient,
      getProductCategoryManualAdjustments: listSpy,
    });

    await waitFor(() => {
      expect((screen.getByLabelText("审计-报表月份") as HTMLSelectElement).value).toBeTruthy();
    });

    expect(await screen.findByText("unit5-stale-marker")).toBeInTheDocument();
    expect(screen.getByTestId("audit-event-pca-audit-stale-1-edited")).toBeInTheDocument();

    await user.type(screen.getByTestId("audit-filter-account-code"), "5140");
    await user.click(screen.getByTestId("audit-apply-filters"));

    await waitFor(() => {
      expect(listSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
    const listAsyncRegion = await screen.findByTestId("product-category-audit-list-timeline-async");
    await within(listAsyncRegion).findByRole("button", { name: "重试" });
    expect(within(listAsyncRegion).getByText(/数据载入失败/)).toBeInTheDocument();
    expect(screen.queryByText("unit5-stale-marker")).not.toBeInTheDocument();
    expect(within(listAsyncRegion).queryByTestId("audit-current-state")).not.toBeInTheDocument();
    expect(within(listAsyncRegion).queryByTestId("audit-event-list")).not.toBeInTheDocument();
    expect(screen.queryByTestId("audit-event-pca-audit-stale-1-edited")).not.toBeInTheDocument();
  });

  it("Unit 5: export failure is reported without replacing loaded list and timeline rows", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const listSpy = vi.fn(async () => ({
      report_date: "2026-02-28",
      adjustment_count: 1,
      adjustment_limit: 20,
      adjustment_offset: 0,
      event_total: 1,
      event_limit: 20,
      event_offset: 0,
      adjustments: [
        {
          adjustment_id: "pca-audit-export-stable",
          event_type: "created",
          created_at: "2026-04-10T10:00:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "51400000000",
          currency: "CNX",
          account_name: "unit5-export-list-remains",
          monthly_pnl: "1",
        },
      ],
      events: [
        {
          adjustment_id: "pca-audit-export-stable",
          event_type: "created",
          created_at: "2026-04-10T10:00:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "51400000000",
          currency: "CNX",
          account_name: "unit5-export-list-remains",
          monthly_pnl: "1",
        },
      ],
    }));
    const exportSpy = vi.fn(async () => {
      throw new Error("audit-export-failure");
    });

    renderAuditPageWithClient({
      ...baseClient,
      getProductCategoryManualAdjustments: listSpy,
      exportProductCategoryManualAdjustmentsCsv: exportSpy,
    });

    expect(await screen.findByTestId("audit-current-state")).toBeInTheDocument();
    expect(screen.getByTestId("audit-event-list")).toBeInTheDocument();
    expect(screen.getByText("unit5-export-list-remains")).toBeInTheDocument();

    await user.click(screen.getByTestId("audit-export-button"));

    expect(await screen.findByTestId("product-category-audit-export-error")).toHaveTextContent(
      "audit-export-failure",
    );
    expect(screen.getByTestId("audit-current-state")).toBeInTheDocument();
    expect(screen.getByTestId("audit-event-list")).toBeInTheDocument();
    expect(screen.getByText("unit5-export-list-remains")).toBeInTheDocument();
    expect(screen.getByTestId("audit-event-pca-audit-export-stable-created")).toBeInTheDocument();
    expect(within(screen.getByTestId("product-category-audit-list-timeline-async")).queryByText(/数据载入失败/)).not.toBeInTheDocument();
  });

  it("disables audit revoke/restore by approval_status and states lifecycle refresh in the timeline lead", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const rowBase = {
      created_at: "2026-04-10T09:00:00Z",
      stream: "product_category_pnl_adjustments" as const,
      report_date: "2026-02-28",
      operator: "DELTA" as const,
      account_code: "51402010001",
      currency: "CNX" as const,
      account_name: "x",
      event_type: "created" as const,
      monthly_pnl: "1",
    };
    renderAuditPageWithClient({
      ...baseClient,
      getProductCategoryManualAdjustments: async () => ({
        report_date: "2026-02-28",
        adjustment_count: 3,
        adjustment_limit: 20,
        adjustment_offset: 0,
        event_total: 0,
        event_limit: 20,
        event_offset: 0,
        adjustments: [
          { ...rowBase, adjustment_id: "pca-audit-ap", approval_status: "approved" as const },
          { ...rowBase, adjustment_id: "pca-audit-pe", approval_status: "pending" as const },
          { ...rowBase, adjustment_id: "pca-audit-rj", approval_status: "rejected" as const },
        ],
        events: [],
      }),
    });

    const lead = await screen.findByTestId("product-category-audit-timeline-lead");
    expect(lead).toHaveTextContent("仅当审批通过可撤销");
    expect(lead).toHaveTextContent("刷新工作流再拉列表");
    expect(lead).toHaveTextContent("整页刷新置灰");

    await screen.findByTestId("audit-revoke-pca-audit-ap");
    expect(screen.getByTestId("audit-revoke-pca-audit-ap")).not.toBeDisabled();
    expect(screen.getByTestId("audit-restore-pca-audit-ap")).toBeDisabled();
    expect(screen.getByTestId("audit-revoke-pca-audit-pe")).toBeDisabled();
    expect(screen.getByTestId("audit-restore-pca-audit-pe")).toBeDisabled();
    expect(screen.getByTestId("audit-revoke-pca-audit-rj")).toBeDisabled();
    expect(screen.getByTestId("audit-restore-pca-audit-rj")).not.toBeDisabled();
    expect(screen.getByTestId("audit-edit-pca-audit-ap")).not.toBeDisabled();
  });

  it("requires confirmation before revoking an approved product-category adjustment", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const confirmSpy = vi.spyOn(window, "confirm");
    const revokeSpy = vi.fn(async () => ({
      adjustment_id: "pca-audit-confirm",
      event_type: "revoked" as const,
      created_at: "2026-04-10T09:10:00Z",
      stream: "product_category_pnl_adjustments" as const,
      report_date: "2026-02-28",
      operator: "DELTA" as const,
      approval_status: "rejected" as const,
      account_code: "51402010001",
      currency: "CNX" as const,
      account_name: "confirm-row",
      monthly_pnl: "1",
    }));
    const refreshSpy = vi.fn(async () => ({
      run_id: "run-confirm",
      status: "running" as const,
      job_name: "product_category_pnl",
      trigger_mode: "async",
      detail: null,
    }));
    const statusSpy = vi.fn(async () => ({
      run_id: "run-confirm",
      status: "completed" as const,
      job_name: "product_category_pnl",
      trigger_mode: "async",
      detail: null,
    }));
    const listSpy = vi.fn(async () => ({
      report_date: "2026-02-28",
      adjustment_count: 1,
      adjustment_limit: 20,
      adjustment_offset: 0,
      event_total: 0,
      event_limit: 20,
      event_offset: 0,
      adjustments: [
        {
          adjustment_id: "pca-audit-confirm",
          event_type: "created" as const,
          created_at: "2026-04-10T09:00:00Z",
          stream: "product_category_pnl_adjustments" as const,
          report_date: "2026-02-28",
          operator: "DELTA" as const,
          approval_status: "approved" as const,
          account_code: "51402010001",
          currency: "CNX" as const,
          account_name: "confirm-row",
          monthly_pnl: "1",
        },
      ],
      events: [],
    }));

    try {
      renderAuditPageWithClient({
        ...baseClient,
        getProductCategoryManualAdjustments: listSpy,
        revokeProductCategoryManualAdjustment: revokeSpy,
        refreshProductCategoryPnl: refreshSpy,
        getProductCategoryRefreshStatus: statusSpy,
      });

      const revokeButton = await screen.findByTestId("audit-revoke-pca-audit-confirm");

      confirmSpy.mockReturnValueOnce(false);
      await user.click(revokeButton);
      expect(confirmSpy).toHaveBeenCalledTimes(1);
      expect(revokeSpy).not.toHaveBeenCalled();
      expect(refreshSpy).not.toHaveBeenCalled();

      confirmSpy.mockReturnValueOnce(true);
      await user.click(revokeButton);
      await waitFor(() => {
        expect(revokeSpy).toHaveBeenCalledWith("pca-audit-confirm");
      });
      expect(refreshSpy).toHaveBeenCalledTimes(1);
    } finally {
      confirmSpy.mockRestore();
    }
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

  it("CSV export uses the same applied filter+sort as the list request (omits only pagination options)", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const exportSpy = vi.fn(async () => ({
      filename: "export.csv",
      content: "x",
    }));
    const originalCreateObjectURL = globalThis.URL.createObjectURL;
    const originalRevokeObjectURL = globalThis.URL.revokeObjectURL;
    const createObjectUrl = vi.fn(() => "blob:export-query");
    const revokeObjectUrl = vi.fn();
    const clickSpy = vi.fn();
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
    const listSpy = vi.fn(async (_reportDate: string, _options?: ProductCategoryManualAdjustmentQuery) => ({
      report_date: "2026-02-28",
      adjustment_count: 1,
      adjustment_limit: 20,
      adjustment_offset: 0,
      event_total: 0,
      event_limit: 20,
      event_offset: 0,
      adjustments: [
        {
          adjustment_id: "pca-dummy",
          event_type: "created",
          created_at: "2026-04-10T10:00:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "51400000000",
          currency: "CNX",
          account_name: "dummy",
        },
      ],
      events: [],
    }));

    try {
      renderAuditPageWithClient({
        ...baseClient,
        getProductCategoryManualAdjustments: listSpy,
        exportProductCategoryManualAdjustmentsCsv: exportSpy,
      });

      await screen.findByTestId("audit-current-state");
      await user.selectOptions(screen.getByTestId("audit-current-sort-field"), "account_code");
      await user.selectOptions(screen.getByTestId("audit-current-sort-dir"), "asc");
      await user.selectOptions(screen.getByTestId("audit-event-sort-field"), "event_type");
      await user.selectOptions(screen.getByTestId("audit-event-sort-dir"), "asc");
      await user.type(screen.getByTestId("audit-filter-account-code"), "5140");
      await user.click(screen.getByTestId("audit-apply-filters"));

      await waitFor(() => {
        expect(listSpy).toHaveBeenCalled();
      });
      const listArgs = listSpy.mock.calls.at(-1);
      expect(listArgs?.[0]).toBe("2026-02-28");
      expect(exportSpy).not.toHaveBeenCalled();

      await user.click(screen.getByTestId("audit-export-button"));

      await waitFor(() => {
        expect(exportSpy).toHaveBeenCalledWith("2026-02-28", {
          adjustmentId: "",
          adjustmentIdExact: false,
          accountCode: "5140",
          approvalStatus: "",
          eventType: "",
          currentSortField: "account_code",
          currentSortDir: "asc",
          eventSortField: "event_type",
          eventSortDir: "asc",
          createdAtFrom: "",
          createdAtTo: "",
        });
        expect(clickSpy).toHaveBeenCalledTimes(1);
      });
      expect(
        manualAdjustmentListOptionsWithoutPagination(listArgs![1] as ProductCategoryManualAdjustmentQuery & {
          adjustmentLimit?: number;
          adjustmentOffset?: number;
          limit?: number;
          offset?: number;
        }),
      ).toEqual(
        buildProductCategoryAuditListExportQuery({
          adjustmentId: "",
          adjustmentIdExact: false,
          accountCode: "5140",
          approvalStatus: "",
          eventType: "",
          currentSortField: "account_code",
          currentSortDir: "asc",
          eventSortField: "event_type",
          eventSortDir: "asc",
          createdAtFrom: "",
          createdAtTo: "",
        }),
      );
    } finally {
      createElementSpy.mockRestore();
      globalThis.URL.createObjectURL = originalCreateObjectURL;
      globalThis.URL.revokeObjectURL = originalRevokeObjectURL;
    }
  });

  it("Unit 6: export pipes API CSV into the download Blob without rewriting numbers or a BOM", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const exportCsv = "a,b,unit-6-raw\n\"x\",12.12345678901234,\"-0.0\"\n";
    const exportSpy = vi.fn(async () => ({
      filename: "unit-6-blob-passthrough.csv",
      content: exportCsv,
    }));
    const listSpy = vi.fn(async () => ({
      report_date: "2026-02-28",
      adjustment_count: 1,
      adjustment_limit: 20,
      adjustment_offset: 0,
      event_total: 0,
      event_limit: 20,
      event_offset: 0,
      adjustments: [
        {
          adjustment_id: "pca-dummy",
          event_type: "created",
          created_at: "2026-04-10T10:00:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "51400000000",
          currency: "CNX",
          account_name: "unit-6-blob",
        },
      ],
      events: [],
    }));
    const OriginalBlob = globalThis.Blob;
    const originalCreateObjectURL = globalThis.URL.createObjectURL;
    const originalRevokeObjectURL = globalThis.URL.revokeObjectURL;
    let capturedBody = "";
    class MockBlob {
      readonly size: number;
      readonly type: string;

      constructor(parts: BlobPart[], options?: BlobPropertyBag) {
        capturedBody = parts.map((part) => String(part)).join("");
        this.size = capturedBody.length;
        this.type = options?.type ?? "";
      }
    }
    globalThis.Blob = MockBlob as unknown as typeof Blob;
    const createObjectUrl = vi.fn(() => "blob:unit-6");
    const revokeObjectUrl = vi.fn();
    const clickSpy = vi.fn();
    const createElementSpy = vi.spyOn(document, "createElement");
    createElementSpy.mockImplementation(((tagName: string) => {
      const el = document.createElementNS("http://www.w3.org/1999/xhtml", tagName);
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(el, "click", { value: clickSpy, configurable: true });
      }
      return el as HTMLElement;
    }) as typeof document.createElement);
    globalThis.URL.createObjectURL = createObjectUrl;
    globalThis.URL.revokeObjectURL = revokeObjectUrl;

    try {
      renderAuditPageWithClient({
        ...baseClient,
        getProductCategoryManualAdjustments: listSpy,
        exportProductCategoryManualAdjustmentsCsv: exportSpy,
      });

      await screen.findByTestId("audit-current-state");
      await user.click(screen.getByTestId("audit-export-button"));

      await waitFor(() => {
        expect(exportSpy).toHaveBeenCalled();
        expect(clickSpy).toHaveBeenCalled();
      });
      expect(capturedBody).toBe(exportCsv);
      expect(capturedBody.codePointAt(0)).not.toBe(0xfeff);
    } finally {
      createElementSpy.mockRestore();
      globalThis.Blob = OriginalBlob;
      globalThis.URL.createObjectURL = originalCreateObjectURL;
      globalThis.URL.revokeObjectURL = originalRevokeObjectURL;
    }
  });

  it("Unit 6: a rendered audit row stays consistent with the exported CSV row for the same fixture", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const fixtureRow = {
      adjustment_id: "pca-audit-unit6-row",
      event_type: "created",
      created_at: "2026-04-10T10:30:00Z",
      stream: "product_category_pnl_adjustments",
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "approved",
      account_code: "51402010001",
      currency: "CNX",
      account_name: "unit-6-visible-row",
    } as const;
    const exportCsvRow = [
      fixtureRow.adjustment_id,
      fixtureRow.event_type,
      fixtureRow.created_at,
      fixtureRow.report_date,
      fixtureRow.operator,
      fixtureRow.approval_status,
      fixtureRow.account_code,
      fixtureRow.currency,
      fixtureRow.account_name,
    ]
      .map((value) => `"${value}"`)
      .join(",");
    const exportCsv = [
      "Current State",
      "adjustment_id,event_type,created_at,report_date,operator,approval_status,account_code,currency,account_name",
      exportCsvRow,
      "",
      "Event Timeline",
      "adjustment_id,event_type,created_at,report_date,operator,approval_status,account_code,currency,account_name",
      exportCsvRow,
    ].join("\n");
    const exportSpy = vi.fn(async () => ({
      filename: "unit-6-ui-csv-consistency.csv",
      content: exportCsv,
    }));
    const listSpy = vi.fn(async () => ({
      report_date: "2026-02-28",
      adjustment_count: 1,
      adjustment_limit: 20,
      adjustment_offset: 0,
      event_total: 1,
      event_limit: 20,
      event_offset: 0,
      adjustments: [fixtureRow],
      events: [fixtureRow],
    }));
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
    const createObjectUrl = vi.fn(() => "blob:unit-6-ui-csv");
    const revokeObjectUrl = vi.fn();
    const clickSpy = vi.fn();
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

    try {
      renderAuditPageWithClient({
        ...baseClient,
        getProductCategoryManualAdjustments: listSpy,
        exportProductCategoryManualAdjustmentsCsv: exportSpy,
      });

      await screen.findByTestId("audit-current-state");
      const rowContainer = screen
        .getByTestId(`audit-edit-${fixtureRow.adjustment_id}`)
        .closest("div");
      expect(rowContainer).not.toBeNull();
      expect(within(rowContainer as HTMLElement).getByText(fixtureRow.account_code)).toBeInTheDocument();
      expect(within(rowContainer as HTMLElement).getByText(fixtureRow.account_name)).toBeInTheDocument();
      expect(within(rowContainer as HTMLElement).getByText(fixtureRow.currency)).toBeInTheDocument();
      expect(within(rowContainer as HTMLElement).getByText(fixtureRow.operator)).toBeInTheDocument();
      expect(within(rowContainer as HTMLElement).getByText(fixtureRow.approval_status)).toBeInTheDocument();

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
        expect(clickSpy).toHaveBeenCalledTimes(1);
      });

      expect(capturedCsv).toContain(exportCsvRow);
    } finally {
      createElementSpy.mockRestore();
      globalThis.Blob = OriginalBlob;
      globalThis.URL.createObjectURL = originalCreateObjectURL;
      globalThis.URL.revokeObjectURL = originalRevokeObjectURL;
    }
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
      value: "\u519c\u4e1a",
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
            result: { report_months: ["202602", "202603"] },
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
    await waitForMonthlyOperatingAnalysisAuditReady();
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-adjustment-class"), "mapping_adjustment");
    await user.type(screen.getByTestId("monthly-operating-analysis-mapping-account-code"), "12301");
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-mapping-field"), "industry_name");
    await user.type(screen.getByTestId("monthly-operating-analysis-adjustment-value"), "\u519c\u4e1a");
    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-submit"));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith({
        report_month: "202602",
        adjustment_class: "mapping_adjustment",
        target: { account_code: "12301", field: "industry_name" },
        operator: "OVERRIDE",
        value: "\u519c\u4e1a",
        approval_status: "approved",
      });
      expect(screen.getByText(/moa-1/)).toBeInTheDocument();
    });
  });

  it("disables monthly operating analysis adjustment submit while create is running", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const approvedAdjustment = {
      adjustment_id: "moa-submit-approved",
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
      approval_status: "approved" as const,
    };
    const rejectedAdjustment = {
      ...approvedAdjustment,
      adjustment_id: "moa-submit-rejected",
      approval_status: "rejected" as const,
    };
    let resolveCreate!: (
      payload: Awaited<ReturnType<typeof baseClient.createQdbGlMonthlyAnalysisManualAdjustment>>,
    ) => void;
    const createSpy = vi.fn(
      () =>
        new Promise<Awaited<ReturnType<typeof baseClient.createQdbGlMonthlyAnalysisManualAdjustment>>>(
          (resolve) => {
            resolveCreate = resolve;
          },
        ),
    );
    const exportSpy = vi.fn();
    const revokeSpy = vi.fn();
    const restoreSpy = vi.fn();

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
            result: { report_months: ["202602", "202603"] },
          }),
          getQdbGlMonthlyAnalysisManualAdjustments: async () => ({
            report_month: "202602",
            adjustment_count: 2,
            adjustments: [approvedAdjustment, rejectedAdjustment],
            events: [],
          }),
          createQdbGlMonthlyAnalysisManualAdjustment: createSpy,
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
    await waitForMonthlyOperatingAnalysisAuditReady();
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-adjustment-class"), "mapping_adjustment");
    await user.type(screen.getByTestId("monthly-operating-analysis-mapping-account-code"), "12301");
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-mapping-field"), "industry_name");
    await user.type(screen.getByTestId("monthly-operating-analysis-adjustment-value"), "\u519c\u4e1a");

    const submitButton = screen.getByTestId("monthly-operating-analysis-adjustment-submit");
    const exportButton = screen.getByTestId("monthly-operating-analysis-adjustment-export");
    const monthSelect = screen.getByTestId("monthly-operating-analysis-audit-month-select");
    const adjustmentClassSelect = screen.getByTestId("monthly-operating-analysis-adjustment-class");
    const mappingAccountInput = screen.getByTestId("monthly-operating-analysis-mapping-account-code");
    const mappingFieldSelect = screen.getByTestId("monthly-operating-analysis-mapping-field");
    const adjustmentValueInput = screen.getByTestId("monthly-operating-analysis-adjustment-value");
    const editButton = screen.getByTestId("monthly-operating-analysis-adjustment-edit-moa-submit-approved");
    const revokeButton = screen.getByTestId("monthly-operating-analysis-adjustment-revoke-moa-submit-approved");
    const restoreButton = screen.getByTestId("monthly-operating-analysis-adjustment-restore-moa-submit-rejected");
    await user.click(submitButton);

    await waitFor(() => {
      expect(submitButton).toBeDisabled();
      expect(exportButton).toBeDisabled();
      expect(monthSelect).toBeDisabled();
      expect(adjustmentClassSelect).toBeDisabled();
      expect(mappingAccountInput).toBeDisabled();
      expect(mappingFieldSelect).toBeDisabled();
      expect(adjustmentValueInput).toBeDisabled();
      expect(editButton).toBeDisabled();
      expect(revokeButton).toBeDisabled();
      expect(restoreButton).toBeDisabled();
      expect(submitButton).toHaveTextContent("\u6b63\u5728\u63d0\u4ea4\u8c03\u6574");
    });
    await user.selectOptions(monthSelect, "202603");
    expect(monthSelect).toHaveValue("202602");
    await user.click(submitButton);
    await user.click(exportButton);
    await user.click(editButton);
    await user.click(revokeButton);
    await user.click(restoreButton);
    expect(createSpy).toHaveBeenCalledTimes(1);
    expect(exportSpy).not.toHaveBeenCalled();
    expect(revokeSpy).not.toHaveBeenCalled();
    expect(restoreSpy).not.toHaveBeenCalled();

    resolveCreate({
      adjustment_id: "moa-submit-lock",
      event_type: "created",
      created_at: "2026-04-12T00:00:00Z",
      stream: "monthly_operating_analysis_adjustments",
      report_month: "202602",
      adjustment_class: "mapping_adjustment",
      target: { account_code: "12301", field: "industry_name" },
      operator: "OVERRIDE",
      value: "\u519c\u4e1a",
      approval_status: "approved",
    });

    await waitFor(() => {
      expect(submitButton).not.toBeDisabled();
      expect(exportButton).not.toBeDisabled();
      expect(monthSelect).not.toBeDisabled();
      expect(adjustmentClassSelect).not.toBeDisabled();
      expect(mappingAccountInput).not.toBeDisabled();
      expect(mappingFieldSelect).not.toBeDisabled();
      expect(adjustmentValueInput).not.toBeDisabled();
      expect(editButton).not.toBeDisabled();
      expect(revokeButton).not.toBeDisabled();
      expect(restoreButton).not.toBeDisabled();
      expect(submitButton).toHaveTextContent("\u65b0\u589e\u8c03\u6574");
      expect(screen.getByText(/moa-submit-lock/)).toBeInTheDocument();
    });
  });
  it("opens monthly operating analysis audit on the report month provided by the analysis branch", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const listSpy = vi.fn(async (reportMonth: string) => ({
      report_month: reportMonth,
      adjustment_count: 0,
      adjustments: [],
      events: [],
    }));
    const router = createWorkbenchMemoryRouter([
      "/product-category-pnl/audit?branch=monthly_operating_analysis&report_month=202603",
    ]);
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
            result: { report_months: ["202401", "202603", "202602"] },
          }),
          getQdbGlMonthlyAnalysisManualAdjustments: listSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("monthly-operating-analysis-audit-month-select")).toHaveValue("202603");
      expect(listSpy).toHaveBeenCalledWith("202603");
    });
    expect(listSpy).not.toHaveBeenCalledWith("202401");
  });

  it("updates monthly operating analysis audit month when the route report month changes", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const listSpy = vi.fn(async (reportMonth: string) => ({
      report_month: reportMonth,
      adjustment_count: 0,
      adjustments: [],
      events: [],
    }));
    const router = createWorkbenchMemoryRouter([
      "/product-category-pnl/audit?branch=monthly_operating_analysis&report_month=202603",
    ]);
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
            result: { report_months: ["202401", "202603", "202602"] },
          }),
          getQdbGlMonthlyAnalysisManualAdjustments: listSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("monthly-operating-analysis-audit-month-select")).toHaveValue("202603");
      expect(listSpy).toHaveBeenCalledWith("202603");
    });

    await act(async () => {
      await router.navigate("/product-category-pnl/audit?branch=monthly_operating_analysis&report_month=202602");
    });

    await waitFor(() => {
      expect(screen.getByTestId("monthly-operating-analysis-audit-month-select")).toHaveValue("202602");
      expect(listSpy).toHaveBeenCalledWith("202602");
    });
  });

  it("falls back to the first available monthly operating analysis audit month when the URL month is unavailable", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const listSpy = vi.fn(async (reportMonth: string) => ({
      report_month: reportMonth,
      adjustment_count: 0,
      adjustments: [],
      events: [],
    }));
    const router = createWorkbenchMemoryRouter([
      "/product-category-pnl/audit?branch=monthly_operating_analysis&report_month=209901",
    ]);
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
            result: { report_months: ["202401", "202603", "202602"] },
          }),
          getQdbGlMonthlyAnalysisManualAdjustments: listSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("monthly-operating-analysis-audit-month-select")).toHaveValue("202401");
      expect(listSpy).toHaveBeenCalledWith("202401");
    });
    expect(listSpy).not.toHaveBeenCalledWith("209901");
  });

  it("disables monthly operating analysis audit actions when report months are unavailable", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const listSpy = vi.fn(async () => ({
      report_month: "",
      adjustment_count: 0,
      adjustments: [],
      events: [],
    }));
    const createSpy = vi.fn();
    const exportSpy = vi.fn();
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
              trace_id: "tr_qdb_dates_empty",
              basis: "analytical" as const,
              result_kind: "qdb-gl-monthly-analysis.dates",
              formal_use_allowed: false,
              source_version: "sv_qdb_test",
              vendor_version: "vv_none",
              rule_version: "rv_qdb_gl_monthly_analysis_v1",
              cache_version: "cv_qdb_gl_monthly_analysis_v1",
              quality_flag: "missing" as const,
              vendor_status: "ok" as const,
              fallback_mode: "none" as const,
              scenario_flag: false,
              generated_at: "2026-04-12T00:00:00Z",
            },
            result: { report_months: [] },
          }),
          getQdbGlMonthlyAnalysisManualAdjustments: listSpy,
          createQdbGlMonthlyAnalysisManualAdjustment: createSpy,
          exportQdbGlMonthlyAnalysisManualAdjustmentsCsv: exportSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    expect(await screen.findByTestId("monthly-operating-analysis-audit-dates-empty")).toHaveTextContent(
      /\u6ca1\u6709\u53ef\u7528\u62a5\u544a\u6708\u4efd/,
    );
    expect(screen.getByTestId("monthly-operating-analysis-audit-month-select")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-class")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-mapping-account-code")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-mapping-field")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-value")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-export")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-submit")).toBeDisabled();
    expect(listSpy).not.toHaveBeenCalled();
    expect(createSpy).not.toHaveBeenCalled();
    expect(exportSpy).not.toHaveBeenCalled();
  });

  it("surfaces monthly operating analysis audit report month load failures without leaking endpoints", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const listSpy = vi.fn(async () => ({
      report_month: "",
      adjustment_count: 0,
      adjustments: [],
      events: [],
    }));
    const router = createWorkbenchMemoryRouter(["/product-category-pnl/audit?branch=monthly_operating_analysis"]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: 0, refetchOnWindowFocus: false } },
    });

    render(
      <ApiClientProvider
        client={{
          ...baseClient,
          getQdbGlMonthlyAnalysisDates: async () => {
            throw new Error("Request failed: /ui/qdb-gl-monthly-analysis/dates (503)");
          },
          getQdbGlMonthlyAnalysisManualAdjustments: listSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    const loadError = await screen.findByTestId("monthly-operating-analysis-audit-load-error");
    expect(loadError).toHaveTextContent(/503/);
    expect(loadError).not.toHaveTextContent(/\/ui\/qdb-gl-monthly-analysis/);
    expect(loadError).not.toHaveTextContent(/Request failed:/);
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-export")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-submit")).toBeDisabled();
    expect(listSpy).not.toHaveBeenCalled();
  });

  it("surfaces monthly operating analysis audit adjustment load failures without leaking endpoints", async () => {
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
          getQdbGlMonthlyAnalysisManualAdjustments: async () => {
            throw new Error(
              "Request failed: /ui/qdb-gl-monthly-analysis/manual-adjustments?report_month=202602 (502)",
            );
          },
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    const loadError = await screen.findByTestId("monthly-operating-analysis-audit-load-error");
    expect(loadError).toHaveTextContent(/502/);
    expect(loadError).not.toHaveTextContent(/\/ui\/qdb-gl-monthly-analysis/);
    expect(loadError).not.toHaveTextContent(/manual-adjustments/);
    expect(loadError).not.toHaveTextContent(/Request failed:/);
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-export")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-submit")).toBeDisabled();
  });

  it("surfaces monthly operating analysis audit adjustment loading and locks actions", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const approvedAdjustment = {
      adjustment_id: "moa-loading-approved",
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
      approval_status: "approved" as const,
    };
    const rejectedAdjustment = {
      ...approvedAdjustment,
      adjustment_id: "moa-loading-rejected",
      approval_status: "rejected" as const,
    };
    let resolveAdjustments!: (payload: {
      report_month: string;
      adjustment_count: number;
      adjustments: typeof approvedAdjustment[];
      events: typeof approvedAdjustment[];
    }) => void;
    const listSpy = vi.fn((reportMonth: string) => {
      if (reportMonth === "202603") {
        return new Promise<{
          report_month: string;
          adjustment_count: number;
          adjustments: typeof approvedAdjustment[];
          events: typeof approvedAdjustment[];
        }>((resolve) => {
          resolveAdjustments = resolve;
        });
      }
      return Promise.resolve({
        report_month: "202602",
        adjustment_count: 2,
        adjustments: [approvedAdjustment, rejectedAdjustment],
        events: [],
      });
    });
    const createSpy = vi.fn();
    const exportSpy = vi.fn();
    const revokeSpy = vi.fn();
    const restoreSpy = vi.fn();
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
            result: { report_months: ["202602", "202603"] },
          }),
          getQdbGlMonthlyAnalysisManualAdjustments: listSpy,
          createQdbGlMonthlyAnalysisManualAdjustment: createSpy,
          exportQdbGlMonthlyAnalysisManualAdjustmentsCsv: exportSpy,
          revokeQdbGlMonthlyAnalysisManualAdjustment: revokeSpy,
          restoreQdbGlMonthlyAnalysisManualAdjustment: restoreSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    await screen.findByTestId("monthly-operating-analysis-adjustment-row-moa-loading-approved");

    const monthSelect = screen.getByTestId("monthly-operating-analysis-audit-month-select");
    const submitButton = screen.getByTestId("monthly-operating-analysis-adjustment-submit");
    const exportButton = screen.getByTestId("monthly-operating-analysis-adjustment-export");

    await userEvent.selectOptions(monthSelect, "202603");

    expect(await screen.findByTestId("monthly-operating-analysis-audit-loading")).toHaveTextContent(
      /正在加载调整记录/,
    );
    expect(screen.queryByText("当前没有调整记录。")).not.toBeInTheDocument();
    expect(submitButton).toBeDisabled();
    expect(exportButton).toBeDisabled();
    expect(screen.queryByTestId("monthly-operating-analysis-adjustment-row-moa-loading-approved")).not.toBeInTheDocument();
    expect(screen.queryByTestId("monthly-operating-analysis-adjustment-row-moa-loading-rejected")).not.toBeInTheDocument();
    await userEvent.click(submitButton);
    await userEvent.click(exportButton);
    expect(createSpy).not.toHaveBeenCalled();
    expect(exportSpy).not.toHaveBeenCalled();
    expect(revokeSpy).not.toHaveBeenCalled();
    expect(restoreSpy).not.toHaveBeenCalled();

    resolveAdjustments({
      report_month: "202603",
      adjustment_count: 0,
      adjustments: [],
      events: [],
    });

    await waitFor(() => {
      expect(screen.queryByTestId("monthly-operating-analysis-audit-loading")).not.toBeInTheDocument();
      expect(monthSelect).toHaveValue("202603");
      expect(submitButton).not.toBeDisabled();
      expect(exportButton).not.toBeDisabled();
    });
  });

  it("surfaces monthly operating analysis audit empty event history after adjustments load", async () => {
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
    await waitForMonthlyOperatingAnalysisAuditReady();

    expect(screen.getByText("当前没有调整记录。")).toBeInTheDocument();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-events")).toHaveTextContent(
      "当前没有调整事件。",
    );
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

  it("labels the real monthly operating analysis audit mode as an interface link, not read-only", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const router = createWorkbenchMemoryRouter(["/product-category-pnl/audit?branch=monthly_operating_analysis"]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: 0, refetchOnWindowFocus: false } },
    });

    render(
      <ApiClientProvider
        client={{
          ...baseClient,
          mode: "real",
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
    expect(screen.getByText("正式接口链路")).toBeInTheDocument();
    expect(screen.queryByText("正式只读链路")).not.toBeInTheDocument();
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
    await waitForMonthlyOperatingAnalysisAuditReady();
    expect(screen.getByTestId("monthly-operating-analysis-audit-title")).toHaveTextContent(
      "月度经营分析调整审计",
    );
    expect(screen.getByTestId("monthly-operating-analysis-audit-boundary-copy")).toHaveTextContent(
      "手工调整",
    );
    expect(screen.getByText(/保持与产品分类正式结果分离/)).toBeInTheDocument();
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
    await waitForMonthlyOperatingAnalysisAuditReady();
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
    await waitForMonthlyOperatingAnalysisAuditReady();
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
    let currentAdjustment = adjustment;
    const listSpy = vi.fn(async () => ({
      report_month: "202602",
      adjustment_count: 1,
      adjustments: [currentAdjustment],
      events: [currentAdjustment],
    }));
    const updateSpy = vi.fn(async () => {
      currentAdjustment = {
        ...adjustment,
        event_type: "edited",
        value: "manual_override_updated",
      };
      return currentAdjustment;
    });
    const revokeSpy = vi.fn(async () => {
      currentAdjustment = {
        ...adjustment,
        event_type: "revoked",
        approval_status: "rejected",
      };
      return currentAdjustment;
    });
    const restoreSpy = vi.fn(async () => {
      currentAdjustment = {
        ...adjustment,
        event_type: "restored",
        approval_status: "approved",
      };
      return currentAdjustment;
    });
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
      expect(screen.getByTestId("monthly-operating-analysis-adjustment-revoke-moa-1")).toBeDisabled();
      expect(screen.getByTestId("monthly-operating-analysis-adjustment-restore-moa-1")).not.toBeDisabled();
    });

    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-restore-moa-1"));
    await waitFor(() => {
      expect(restoreSpy).toHaveBeenCalledWith("moa-1");
      expect(screen.getByTestId("monthly-operating-analysis-adjustment-revoke-moa-1")).not.toBeDisabled();
      expect(screen.getByTestId("monthly-operating-analysis-adjustment-restore-moa-1")).toBeDisabled();
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

  it("cancels monthly operating analysis audit editing and restores a clean create draft", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const adjustment = {
      adjustment_id: "moa-cancel-edit",
      event_type: "created",
      created_at: "2026-04-12T00:00:00Z",
      stream: "monthly_operating_analysis_adjustments",
      report_month: "202602",
      adjustment_class: "mapping_adjustment" as const,
      target: { account_code: "12301", field: "industry_name" },
      operator: "OVERRIDE",
      value: "\u519c\u4e1a",
      approval_status: "approved",
    };
    const updateSpy = vi.fn();
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
            adjustment_count: 1,
            adjustments: [adjustment],
            events: [],
          }),
          updateQdbGlMonthlyAnalysisManualAdjustment: updateSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    await waitForMonthlyOperatingAnalysisAuditReady();
    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-submit"));
    expect(await screen.findByTestId("monthly-operating-analysis-audit-error")).toHaveTextContent(
      "\u8bf7\u586b\u5199\u8c03\u6574\u503c\u3002",
    );

    await user.click(await screen.findByTestId("monthly-operating-analysis-adjustment-edit-moa-cancel-edit"));

    expect(screen.queryByTestId("monthly-operating-analysis-audit-error")).not.toBeInTheDocument();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-submit")).toHaveTextContent("\u4fdd\u5b58\u8c03\u6574");
    expect(screen.getByTestId("monthly-operating-analysis-mapping-account-code")).toHaveValue("12301");
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-value")).toHaveValue("\u519c\u4e1a");

    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-cancel-edit"));

    expect(screen.getByTestId("monthly-operating-analysis-adjustment-submit")).toHaveTextContent("\u65b0\u589e\u8c03\u6574");
    expect(screen.getByTestId("monthly-operating-analysis-mapping-account-code")).toHaveValue("");
    expect(screen.getByTestId("monthly-operating-analysis-mapping-field")).toHaveValue("industry_name");
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-value")).toHaveValue("");
    expect(updateSpy).not.toHaveBeenCalled();
  });

  it("keeps monthly operating analysis audit edit draft after save failures", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const adjustment = {
      adjustment_id: "moa-edit-failure",
      event_type: "created",
      created_at: "2026-04-12T00:00:00Z",
      stream: "monthly_operating_analysis_adjustments",
      report_month: "202602",
      adjustment_class: "mapping_adjustment" as const,
      target: { account_code: "12301", field: "industry_name" },
      operator: "OVERRIDE",
      value: "\u519c\u4e1a",
      approval_status: "approved",
    };
    const updateSpy = vi.fn(async () => {
      throw new Error(
        "Request failed: /ui/qdb-gl-monthly-analysis/manual-adjustments/moa-edit-failure/edit (500)",
      );
    });
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
            adjustment_count: 1,
            adjustments: [adjustment],
            events: [],
          }),
          updateQdbGlMonthlyAnalysisManualAdjustment: updateSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    await user.click(await screen.findByTestId("monthly-operating-analysis-adjustment-edit-moa-edit-failure"));
    await user.clear(screen.getByTestId("monthly-operating-analysis-adjustment-value"));
    await user.type(screen.getByTestId("monthly-operating-analysis-adjustment-value"), "\u519c\u4e1a-updated");
    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-submit"));

    await waitFor(() => {
      const errorPanel = screen.getByTestId("monthly-operating-analysis-audit-error");
      expect(errorPanel).toHaveTextContent(/500/);
      expect(errorPanel).not.toHaveTextContent(/\/ui\/qdb-gl-monthly-analysis/);
      expect(errorPanel).not.toHaveTextContent(/manual-adjustments/);
      expect(errorPanel).not.toHaveTextContent(/Request failed:/);
    });
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-submit")).toHaveTextContent("\u4fdd\u5b58\u8c03\u6574");
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-cancel-edit")).toBeInTheDocument();
    expect(screen.getByTestId("monthly-operating-analysis-mapping-account-code")).toHaveValue("12301");
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-value")).toHaveValue("\u519c\u4e1a-updated");
    expect(updateSpy).toHaveBeenCalledTimes(1);
  });

  it("disables monthly operating analysis audit revoke and restore while requests are running", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const adjustment = {
      adjustment_id: "moa-lock-1",
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
    let currentAdjustment = adjustment;
    let resolveRevoke!: (
      payload: Awaited<ReturnType<typeof baseClient.revokeQdbGlMonthlyAnalysisManualAdjustment>>,
    ) => void;
    let resolveRestore!: (
      payload: Awaited<ReturnType<typeof baseClient.restoreQdbGlMonthlyAnalysisManualAdjustment>>,
    ) => void;
    const revokeSpy = vi.fn(
      () =>
        new Promise<Awaited<ReturnType<typeof baseClient.revokeQdbGlMonthlyAnalysisManualAdjustment>>>(
          (resolve) => {
            resolveRevoke = resolve;
          },
        ),
    );
    const restoreSpy = vi.fn(
      () =>
        new Promise<Awaited<ReturnType<typeof baseClient.restoreQdbGlMonthlyAnalysisManualAdjustment>>>(
          (resolve) => {
            resolveRestore = resolve;
          },
        ),
    );

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
            adjustment_count: 1,
            adjustments: [currentAdjustment],
            events: [currentAdjustment],
          }),
          revokeQdbGlMonthlyAnalysisManualAdjustment: revokeSpy,
          restoreQdbGlMonthlyAnalysisManualAdjustment: restoreSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    expect(
      await screen.findByTestId("monthly-operating-analysis-adjustment-row-moa-lock-1"),
    ).toBeInTheDocument();

    const revokeButton = screen.getByTestId("monthly-operating-analysis-adjustment-revoke-moa-lock-1");
    const editButton = screen.getByTestId("monthly-operating-analysis-adjustment-edit-moa-lock-1");
    const submitButton = screen.getByTestId("monthly-operating-analysis-adjustment-submit");
    await user.click(revokeButton);

    await waitFor(() => {
      expect(revokeButton).toBeDisabled();
      expect(editButton).toBeDisabled();
      expect(submitButton).toBeDisabled();
      expect(revokeButton).toHaveTextContent("\u6b63\u5728\u64a4\u9500");
    });
    await user.click(revokeButton);
    expect(revokeSpy).toHaveBeenCalledTimes(1);

    currentAdjustment = {
      ...adjustment,
      event_type: "revoked",
      approval_status: "rejected",
    };
    resolveRevoke(currentAdjustment);

    await waitFor(() => {
      expect(revokeButton).toBeDisabled();
      expect(editButton).not.toBeDisabled();
      expect(submitButton).not.toBeDisabled();
      expect(revokeButton).toHaveTextContent("\u64a4\u9500");
      expect(screen.getByTestId("monthly-operating-analysis-adjustment-row-moa-lock-1")).toBeInTheDocument();
    });

    const restoreButton = screen.getByTestId("monthly-operating-analysis-adjustment-restore-moa-lock-1");
    await user.click(restoreButton);

    await waitFor(() => {
      expect(restoreButton).toBeDisabled();
      expect(editButton).toBeDisabled();
      expect(submitButton).toBeDisabled();
      expect(restoreButton).toHaveTextContent("\u6b63\u5728\u6062\u590d");
    });
    await user.click(restoreButton);
    expect(restoreSpy).toHaveBeenCalledTimes(1);

    currentAdjustment = {
      ...adjustment,
      event_type: "restored",
      approval_status: "approved",
    };
    resolveRestore(currentAdjustment);

    await waitFor(() => {
      expect(screen.getByTestId("monthly-operating-analysis-adjustment-revoke-moa-lock-1")).not.toBeDisabled();
      expect(restoreButton).toBeDisabled();
      expect(editButton).not.toBeDisabled();
      expect(submitButton).not.toBeDisabled();
      expect(restoreButton).toHaveTextContent("\u6062\u590d");
      expect(screen.getByTestId("monthly-operating-analysis-adjustment-row-moa-lock-1")).toBeInTheDocument();
    });
  });

  it("disables monthly operating analysis audit revoke and restore by approval status", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const rowBase = {
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
    };

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
            adjustment_count: 3,
            adjustments: [
              { ...rowBase, adjustment_id: "moa-status-approved", approval_status: "approved" as const },
              { ...rowBase, adjustment_id: "moa-status-pending", approval_status: "pending" as const },
              { ...rowBase, adjustment_id: "moa-status-rejected", approval_status: "rejected" as const },
            ],
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
    await screen.findByTestId("monthly-operating-analysis-adjustment-row-moa-status-approved");

    expect(screen.getByTestId("monthly-operating-analysis-adjustment-revoke-moa-status-approved")).not.toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-restore-moa-status-approved")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-revoke-moa-status-pending")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-restore-moa-status-pending")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-revoke-moa-status-rejected")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-adjustment-restore-moa-status-rejected")).not.toBeDisabled();
  });

  it("surfaces monthly operating analysis audit export failures without leaking endpoints", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const exportSpy = vi.fn(async () => {
      throw new Error(
        "Request failed: /ui/qdb-gl-monthly-analysis/manual-adjustments/export?report_month=202602 (500)",
      );
    });
    const createObjectUrl = vi.fn(() => "blob:monthly-audit");
    const originalCreateObjectURL = globalThis.URL.createObjectURL;
    globalThis.URL.createObjectURL = createObjectUrl;

    const router = createWorkbenchMemoryRouter(["/product-category-pnl/audit?branch=monthly_operating_analysis"]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: 0, refetchOnWindowFocus: false } },
    });

    try {
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
              result: { report_months: ["202602", "202603"] },
            }),
            getQdbGlMonthlyAnalysisManualAdjustments: async () => ({
              report_month: "202602",
              adjustment_count: 0,
              adjustments: [],
              events: [],
            }),
            exportQdbGlMonthlyAnalysisManualAdjustmentsCsv: exportSpy,
          }}
        >
          <QueryClientProvider client={queryClient}>
            <RouterProvider router={router} future={routerFuture} />
          </QueryClientProvider>
        </ApiClientProvider>,
      );

      expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
      await waitForMonthlyOperatingAnalysisAuditReady();
      await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-export"));

      await waitFor(() => {
        const errorPanel = screen.getByTestId("monthly-operating-analysis-audit-error");
        expect(errorPanel).toHaveTextContent(/500/);
        expect(errorPanel).not.toHaveTextContent(/\/ui\/qdb-gl-monthly-analysis/);
        expect(errorPanel).not.toHaveTextContent(/manual-adjustments\/export/);
        expect(errorPanel).not.toHaveTextContent(/Request failed:/);
      }, { timeout: 10_000 });
      expect(exportSpy).toHaveBeenCalledWith("202602");
      expect(createObjectUrl).not.toHaveBeenCalled();
    } finally {
      globalThis.URL.createObjectURL = originalCreateObjectURL;
    }
  });

  it("clears monthly operating analysis audit transient messages when switching report month", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const createSpy = vi.fn(async () => ({
      adjustment_id: "moa-month-message",
      event_type: "created",
      created_at: "2026-04-12T00:00:00Z",
      stream: "monthly_operating_analysis_adjustments",
      report_month: "202602",
      adjustment_class: "mapping_adjustment" as const,
      target: { account_code: "12301", field: "industry_name" },
      operator: "OVERRIDE",
      value: "\u519c\u4e1a",
      approval_status: "approved",
    }));
    const exportSpy = vi.fn(async () => {
      throw new Error(
        "Request failed: /ui/qdb-gl-monthly-analysis/manual-adjustments/export?report_month=202602 (500)",
      );
    });
    const listSpy = vi.fn(async (reportMonth: string) => ({
      report_month: reportMonth,
      adjustment_count: 0,
      adjustments: [],
      events: [],
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
            result: { report_months: ["202602", "202603"] },
          }),
          getQdbGlMonthlyAnalysisManualAdjustments: listSpy,
          createQdbGlMonthlyAnalysisManualAdjustment: createSpy,
          exportQdbGlMonthlyAnalysisManualAdjustmentsCsv: exportSpy,
        }}
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} future={routerFuture} />
        </QueryClientProvider>
      </ApiClientProvider>,
    );

    expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
    const monthSelect = screen.getByTestId("monthly-operating-analysis-audit-month-select");
    await waitFor(() => {
      expect(listSpy).toHaveBeenCalledWith("202602");
    });

    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-export"));
    expect(await screen.findByTestId("monthly-operating-analysis-audit-error")).toHaveTextContent(/500/);

    await user.selectOptions(monthSelect, "202603");
    await waitFor(() => {
      expect(monthSelect).toHaveValue("202603");
      expect(listSpy).toHaveBeenCalledWith("202603");
      expect(screen.queryByTestId("monthly-operating-analysis-audit-error")).not.toBeInTheDocument();
    });

    await user.selectOptions(monthSelect, "202602");
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-adjustment-class"), "mapping_adjustment");
    await user.type(screen.getByTestId("monthly-operating-analysis-mapping-account-code"), "12301");
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-mapping-field"), "industry_name");
    await user.type(screen.getByTestId("monthly-operating-analysis-adjustment-value"), "\u519c\u4e1a");

    await user.selectOptions(monthSelect, "202603");
    await waitFor(() => {
      expect(monthSelect).toHaveValue("202603");
      expect(screen.getByTestId("monthly-operating-analysis-mapping-account-code")).toHaveValue("");
      expect(screen.getByTestId("monthly-operating-analysis-mapping-field")).toHaveValue("industry_name");
      expect(screen.getByTestId("monthly-operating-analysis-adjustment-value")).toHaveValue("");
    });

    await user.selectOptions(monthSelect, "202602");
    await user.type(screen.getByTestId("monthly-operating-analysis-mapping-account-code"), "12301");
    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-mapping-field"), "industry_name");
    await user.type(screen.getByTestId("monthly-operating-analysis-adjustment-value"), "\u519c\u4e1a");
    await user.click(screen.getByTestId("monthly-operating-analysis-adjustment-submit"));

    expect(await screen.findByText("moa-month-message")).toBeInTheDocument();

    await user.selectOptions(monthSelect, "202603");
    await waitFor(() => {
      expect(screen.queryByText("moa-month-message")).not.toBeInTheDocument();
    });
  });

  it("disables monthly operating analysis audit export while the request is running", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const approvedAdjustment = {
      adjustment_id: "moa-export-approved",
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
      approval_status: "approved" as const,
    };
    const rejectedAdjustment = {
      ...approvedAdjustment,
      adjustment_id: "moa-export-rejected",
      approval_status: "rejected" as const,
    };
    let resolveExport!: (payload: { filename: string; content: string }) => void;
    const exportSpy = vi.fn(
      () =>
        new Promise<{ filename: string; content: string }>((resolve) => {
          resolveExport = resolve;
        }),
    );
    const revokeSpy = vi.fn();
    const restoreSpy = vi.fn();
    const createObjectUrl = vi.fn(() => "blob:monthly-audit");
    const revokeObjectUrl = vi.fn();
    const clickSpy = vi.fn();
    const originalCreateObjectURL = globalThis.URL.createObjectURL;
    const originalRevokeObjectURL = globalThis.URL.revokeObjectURL;
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

    try {
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
              result: { report_months: ["202602", "202603"] },
            }),
            getQdbGlMonthlyAnalysisManualAdjustments: async () => ({
              report_month: "202602",
              adjustment_count: 2,
              adjustments: [approvedAdjustment, rejectedAdjustment],
              events: [],
            }),
            exportQdbGlMonthlyAnalysisManualAdjustmentsCsv: exportSpy,
            revokeQdbGlMonthlyAnalysisManualAdjustment: revokeSpy,
            restoreQdbGlMonthlyAnalysisManualAdjustment: restoreSpy,
          }}
        >
          <QueryClientProvider client={queryClient}>
            <RouterProvider router={router} future={routerFuture} />
          </QueryClientProvider>
        </ApiClientProvider>,
      );

      expect(await screen.findByTestId("monthly-operating-analysis-audit-page")).toBeInTheDocument();
      await screen.findByTestId("monthly-operating-analysis-adjustment-row-moa-export-approved");
      const monthSelect = screen.getByTestId("monthly-operating-analysis-audit-month-select");
      const exportButton = screen.getByTestId("monthly-operating-analysis-adjustment-export");
      const submitButton = screen.getByTestId("monthly-operating-analysis-adjustment-submit");
      const adjustmentClassSelect = screen.getByTestId("monthly-operating-analysis-adjustment-class");
      const adjustmentValueInput = screen.getByTestId("monthly-operating-analysis-adjustment-value");
      const editButton = screen.getByTestId("monthly-operating-analysis-adjustment-edit-moa-export-approved");
      const revokeButton = screen.getByTestId("monthly-operating-analysis-adjustment-revoke-moa-export-approved");
      const restoreButton = screen.getByTestId("monthly-operating-analysis-adjustment-restore-moa-export-rejected");
      await user.click(exportButton);

      await waitFor(() => {
        expect(exportButton).toBeDisabled();
        expect(monthSelect).toBeDisabled();
        expect(submitButton).toBeDisabled();
        expect(adjustmentClassSelect).toBeDisabled();
        expect(adjustmentValueInput).toBeDisabled();
        expect(editButton).toBeDisabled();
        expect(revokeButton).toBeDisabled();
        expect(restoreButton).toBeDisabled();
      });
      await user.selectOptions(monthSelect, "202603");
      expect(monthSelect).toHaveValue("202602");
      await user.click(exportButton);
      await user.click(submitButton);
      await user.click(editButton);
      await user.click(revokeButton);
      await user.click(restoreButton);
      expect(exportSpy).toHaveBeenCalledTimes(1);
      expect(revokeSpy).not.toHaveBeenCalled();
      expect(restoreSpy).not.toHaveBeenCalled();

      resolveExport({
        filename: "monthly-operating-analysis-audit-202602.csv",
        content: "adjustment_id,event_type\n",
      });

      await waitFor(() => {
        expect(exportButton).not.toBeDisabled();
        expect(monthSelect).not.toBeDisabled();
        expect(submitButton).not.toBeDisabled();
        expect(adjustmentClassSelect).not.toBeDisabled();
        expect(adjustmentValueInput).not.toBeDisabled();
        expect(editButton).not.toBeDisabled();
        expect(revokeButton).not.toBeDisabled();
        expect(restoreButton).not.toBeDisabled();
        expect(createObjectUrl).toHaveBeenCalledTimes(1);
        expect(clickSpy).toHaveBeenCalledTimes(1);
        expect(revokeObjectUrl).toHaveBeenCalledWith("blob:monthly-audit");
      });
    } finally {
      createElementSpy.mockRestore();
      globalThis.URL.createObjectURL = originalCreateObjectURL;
      globalThis.URL.revokeObjectURL = originalRevokeObjectURL;
    }
  });
});
