import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import ProductCategoryAdjustmentAuditPage from "../features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage";

function renderAuditPageWithClient(client: ReturnType<typeof createApiClient>) {
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
        <ProductCategoryAdjustmentAuditPage />
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

    expect(await screen.findByTestId("audit-current-state")).toBeInTheDocument();
    expect(screen.getByTestId("audit-event-list")).toBeInTheDocument();
    expect(screen.getByText("audit-account")).toBeInTheDocument();
    expect(screen.getByTestId("audit-event-pca-audit-1-edited")).toBeInTheDocument();
    expect(screen.getByTestId("audit-event-pca-audit-1-created")).toBeInTheDocument();
  });

  it("applies independent audit sort and UTC time-range filters, then paginates events", async () => {
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
    await user.selectOptions(screen.getByTestId("audit-current-sort-field"), "account_code");
    await user.selectOptions(screen.getByTestId("audit-current-sort-dir"), "asc");
    await user.selectOptions(screen.getByTestId("audit-event-sort-field"), "event_type");
    await user.selectOptions(screen.getByTestId("audit-event-sort-dir"), "asc");
    await user.type(screen.getByTestId("audit-created-at-from"), "2026-04-10T10:30:00Z");
    await user.type(screen.getByTestId("audit-created-at-to"), "2026-04-10T11:00:00Z");
    await user.click(screen.getByTestId("audit-apply-filters"));

    await waitFor(() => {
      expect(listSpy).toHaveBeenLastCalledWith("2026-02-28", {
        adjustmentId: "pca-audit-1",
        adjustmentIdExact: true,
        accountCode: "",
        approvalStatus: "",
        eventType: "edited",
        currentSortField: "account_code",
        currentSortDir: "asc",
        eventSortField: "event_type",
        eventSortDir: "asc",
        createdAtFrom: "2026-04-10T10:30:00Z",
        createdAtTo: "2026-04-10T11:00:00Z",
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
        currentSortField: "account_code",
        currentSortDir: "asc",
        eventSortField: "event_type",
        eventSortDir: "asc",
        createdAtFrom: "2026-04-10T10:30:00Z",
        createdAtTo: "2026-04-10T11:00:00Z",
        adjustmentLimit: 20,
        adjustmentOffset: 0,
        limit: 2,
        offset: 2,
      });
    });
  });

  it("resets current/event pagination on apply-reset and exports the applied audit query", async () => {
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
    await user.selectOptions(screen.getByTestId("audit-current-sort-field"), "account_code");
    await user.selectOptions(screen.getByTestId("audit-current-sort-dir"), "asc");
    await user.type(screen.getByTestId("audit-created-at-from"), "2026-04-10T10:30:00Z");
    await user.type(screen.getByTestId("audit-created-at-to"), "2026-04-10T10:32:00Z");
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
        createdAtFrom: "2026-04-10T10:30:00Z",
        createdAtTo: "2026-04-10T10:32:00Z",
        adjustmentLimit: 2,
        adjustmentOffset: 0,
        limit: 20,
        offset: 0,
      });
    });

    await user.click(screen.getByTestId("audit-reset-filters"));

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
        adjustmentOffset: 0,
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
});
