import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ActionRequestError, createApiClient } from "../api/client";
import { buildMockProductCategoryPnlEnvelope } from "../mocks/productCategoryPnl";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

function renderWorkbenchAppWithClient(client: ReturnType<typeof createApiClient>) {
  return renderWorkbenchApp(["/product-category-pnl"], { client });
}

describe("ProductCategoryPnlPage", () => {
  it("renders the page shell, summary, and table structure", async () => {
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    const table = await screen.findByTestId("product-category-table");
    expect(screen.getByTestId("product-category-page-title")).toHaveTextContent("产品分类损益");
    expect(screen.getByTestId("product-category-page-subtitle")).toHaveTextContent(
      "按业务分类查看损益、FTP 和净收入",
    );
    expect(screen.getByTestId("product-category-role-badge")).toHaveTextContent("System Layer");
    expect(screen.getByTestId("product-category-boundary-copy")).toHaveTextContent("系统层经营口径");
    expect(screen.getByTestId("product-category-adjustment-lead")).toHaveTextContent(
      "手工调整与审计",
    );
    expect(screen.getByTestId("product-category-scenario-lead")).toHaveTextContent(
      "scenario 查询",
    );
    expect(screen.getByTestId("product-category-formal-table-lead")).toHaveTextContent(
      "正式产品类别损益表",
    );
    expect(screen.getByTestId("product-category-summary")).toHaveTextContent("1.75");
    expect(screen.getByTestId("product-category-summary")).toHaveTextContent("2.85");
    expect(screen.getByTestId("product-category-footer-total")).toHaveTextContent("2.85");
    const metaPanel = screen.getByTestId("product-category-result-meta-baseline");
    expect(metaPanel).toHaveTextContent("formal");
    expect(metaPanel).toHaveTextContent("product_category_pnl.detail");
    expect(metaPanel).toHaveTextContent("fallback_mode");
    expect(metaPanel).toHaveTextContent("none");
    expect(metaPanel).toHaveTextContent("mock_product_category_pnl.detail");
    expect(screen.getByTestId("product-category-governance-strip")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-as-of-date-gap")).toHaveTextContent("as_of_date");
    expect(
      screen.queryByTestId("product-category-governance-notice-fallback_mode"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("product-category-formal-scenario-meta-distinct"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("product-category-audit-link")).toHaveAttribute(
      "href",
      "/product-category-pnl/audit",
    );
    expect(screen.getByTestId("product-category-ledger-link")).toHaveAttribute(
      "href",
      "/ledger-pnl?report_date=2026-02-28",
    );
    expect(within(table).getAllByRole("row")).toHaveLength(20);
  });

  it("applies a scenario rate only after the apply action", async () => {
    const user = userEvent.setup();
    renderWorkbenchAppWithClient(createApiClient({ mode: "mock" }));

    await screen.findByTestId("product-category-table");
    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[1]!, "2.50");
    await user.click(screen.getByTestId("product-category-apply-scenario-button"));

    await waitFor(() => {
      expect(screen.getByTestId("product-category-summary")).toHaveTextContent("2.50");
      expect(screen.getByTestId("product-category-summary")).toHaveTextContent("0.52");
      expect(screen.getByTestId("product-category-result-meta-scenario")).toHaveTextContent(
        "scenario",
      );
      expect(screen.getByTestId("product-category-result-meta-scenario")).toHaveTextContent(
        "true",
      );
      const distinct = screen.getByTestId("product-category-formal-scenario-meta-distinct");
      expect(distinct).toHaveTextContent("formal basis=formal");
      expect(distinct).toHaveTextContent("scenario basis=scenario");
      expect(distinct).toHaveTextContent("trace_id=mock_product_category_pnl.detail");
    });
  });

  it("surfaces degraded result_meta (fallback, vendor, quality) in the governance strip, not only inside the meta panel", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryPnl: vi.fn(async (options) => {
        const env = buildMockProductCategoryPnlEnvelope(options);
        return {
          ...env,
          result_meta: {
            ...env.result_meta,
            fallback_mode: "latest_snapshot" as const,
            vendor_status: "vendor_stale" as const,
            quality_flag: "warning" as const,
          },
        };
      }),
    });

    await screen.findByTestId("product-category-table");
    expect(screen.getByTestId("product-category-governance-notice-fallback_mode")).toHaveTextContent(
      "latest_snapshot",
    );
    expect(screen.getByTestId("product-category-governance-notice-vendor_status")).toHaveTextContent(
      "vendor_stale",
    );
    expect(screen.getByTestId("product-category-governance-notice-quality_flag")).toHaveTextContent(
      "warning",
    );
  });

  it("polls refresh status when the refresh job is queued", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => ({
      status: "queued",
      run_id: "product_category_pnl:test-run",
      job_name: "product_category_pnl",
      trigger_mode: "async",
      cache_key: "product_category_pnl.formal",
    }));
    const statusSpy = vi
      .fn()
      .mockResolvedValueOnce({
        status: "running",
        run_id: "product_category_pnl:test-run",
        job_name: "product_category_pnl",
        trigger_mode: "async",
        cache_key: "product_category_pnl.formal",
      })
      .mockResolvedValueOnce({
        status: "completed",
        run_id: "product_category_pnl:test-run",
        job_name: "product_category_pnl",
        trigger_mode: "async",
        cache_key: "product_category_pnl.formal",
        month_count: 2,
        report_dates: ["2026-01-31", "2026-02-28"],
        rule_version: "rv_product_category_pnl_v1",
        source_version: "sv_test",
      });

    renderWorkbenchAppWithClient({
      ...baseClient,
      refreshProductCategoryPnl: refreshSpy,
      getProductCategoryRefreshStatus: statusSpy,
    });

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-refresh-button"));

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledTimes(1);
      expect(statusSpy).toHaveBeenCalledTimes(2);
      expect(statusSpy).toHaveBeenCalledWith("product_category_pnl:test-run");
      expect(screen.getByText(/product_category_pnl:test-run/)).toBeInTheDocument();
    });
  });

  it("surfaces refresh conflict (409) with explicit copy and does not record a successful run id", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => {
      throw new ActionRequestError("Product-category refresh already in progress.", {
        status: 409,
      });
    });

    renderWorkbenchAppWithClient({
      ...baseClient,
      refreshProductCategoryPnl: refreshSpy,
    });

    await screen.findByTestId("product-category-table");
    expect(screen.queryByText(/^最近刷新任务：/)).not.toBeInTheDocument();

    await user.click(screen.getByTestId("product-category-refresh-button"));

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledTimes(1);
      expect(
        screen.getByText("Product-category refresh already in progress."),
      ).toBeInTheDocument();
    });

    expect(screen.queryByText(/^最近刷新任务：/)).not.toBeInTheDocument();
    expect(screen.getByTestId("product-category-refresh-button")).toHaveTextContent("刷新损益数据");
  });

  it("surfaces sync-fallback service failure (503) with explicit copy and does not record a successful run id", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => {
      throw new ActionRequestError("Product-category refresh failed during sync fallback.", {
        status: 503,
      });
    });

    renderWorkbenchAppWithClient({
      ...baseClient,
      refreshProductCategoryPnl: refreshSpy,
    });

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-refresh-button"));

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledTimes(1);
      expect(
        screen.getByText("Product-category refresh failed during sync fallback."),
      ).toBeInTheDocument();
    });

    expect(screen.queryByText(/^最近刷新任务：/)).not.toBeInTheDocument();
    expect(screen.getByTestId("product-category-refresh-button")).toHaveTextContent("刷新损益数据");
  });

  it("surfaces terminal failed refresh status as an error (not silent success)", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => ({
      status: "queued",
      run_id: "product_category_pnl:failed-run",
      job_name: "product_category_pnl",
      trigger_mode: "async",
      cache_key: "product_category_pnl.formal",
    }));
    const statusSpy = vi.fn(async () => ({
      status: "failed",
      run_id: "product_category_pnl:failed-run",
      job_name: "product_category_pnl",
      trigger_mode: "async",
      cache_key: "product_category_pnl.formal",
      detail: "Product-category refresh run failed (test).",
    }));

    renderWorkbenchAppWithClient({
      ...baseClient,
      refreshProductCategoryPnl: refreshSpy,
      getProductCategoryRefreshStatus: statusSpy,
    });

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-refresh-button"));

    await waitFor(() => {
      expect(screen.getByText("Product-category refresh run failed (test).")).toBeInTheDocument();
    });

    expect(screen.getByText(/product_category_pnl:failed-run/)).toBeInTheDocument();
    expect(screen.getByTestId("product-category-refresh-button")).toHaveTextContent("刷新损益数据");
  });

  it("submits a manual adjustment and refreshes afterwards", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const createAdjustmentSpy = vi.fn(async () => ({
      adjustment_id: "pca-test-1",
      event_type: "created",
      created_at: "2026-04-10T09:40:00Z",
      stream: "product_category_pnl_adjustments",
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "approved",
      account_code: "13304010001",
      currency: "CNX",
      account_name: "test-account",
      monthly_pnl: "5",
      beginning_balance: null,
      ending_balance: null,
      daily_avg_balance: null,
      annual_avg_balance: null,
    }));
    const refreshSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "product_category_pnl:refresh-after-adjustment",
      job_name: "product_category_pnl",
      trigger_mode: "sync-fallback",
      cache_key: "product_category_pnl.formal",
      month_count: 2,
      report_dates: ["2026-01-31", "2026-02-28"],
      rule_version: "rv_product_category_pnl_v1",
      source_version: "sv_test",
    }));

    renderWorkbenchAppWithClient({
      ...baseClient,
      createProductCategoryManualAdjustment: createAdjustmentSpy,
      refreshProductCategoryPnl: refreshSpy,
    });

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-manual-button"));

    const form = screen.getByTestId("product-category-manual-form");
    const textboxes = within(form).getAllByRole("textbox");
    await user.type(textboxes[1]!, "13304010001");
    await user.type(textboxes[2]!, "test-account");
    await user.type(textboxes[5]!, "5");
    await user.click(screen.getByTestId("product-category-manual-submit"));

    await waitFor(() => {
      expect(createAdjustmentSpy).toHaveBeenCalledTimes(1);
      expect(refreshSpy).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/pca-test-1/)).toBeInTheDocument();
    });
  });

  it("shows adjustment summary on the main page and keeps full timeline in audit view", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const listSpy = vi.fn(async () => ({
      report_date: "2026-02-28",
      adjustment_count: 1,
      adjustment_limit: 20,
      adjustment_offset: 0,
      event_total: 2,
      event_limit: 20,
      event_offset: 0,
      adjustments: [
        {
          adjustment_id: "pca-existing-1",
          created_at: "2026-04-10T09:30:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "51402010001",
          currency: "CNX",
          account_name: "test-account",
          event_type: "edited",
          monthly_pnl: "6",
        },
      ],
      events: [
        {
          adjustment_id: "pca-existing-1",
          created_at: "2026-04-10T09:35:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "51402010001",
          currency: "CNX",
          account_name: "test-account",
          event_type: "edited",
          monthly_pnl: "6",
        },
        {
          adjustment_id: "pca-existing-1",
          created_at: "2026-04-10T09:30:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "approved",
          account_code: "51402010001",
          currency: "CNX",
          account_name: "test-account",
          event_type: "created",
          monthly_pnl: "5",
        },
      ],
    }));
    const revokeSpy = vi.fn(async () => ({
      adjustment_id: "pca-existing-1",
      event_type: "revoked",
      created_at: "2026-04-10T09:35:00Z",
      stream: "product_category_pnl_adjustments",
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "rejected",
      account_code: "51402010001",
      currency: "CNX",
      account_name: "test-account",
    }));
    const refreshSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "product_category_pnl:revoke-refresh",
      job_name: "product_category_pnl",
      trigger_mode: "sync-fallback",
      cache_key: "product_category_pnl.formal",
      month_count: 2,
      report_dates: ["2026-01-31", "2026-02-28"],
      rule_version: "rv_product_category_pnl_v1",
      source_version: "sv_test",
    }));

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryManualAdjustments: listSpy,
      revokeProductCategoryManualAdjustment: revokeSpy,
      refreshProductCategoryPnl: refreshSpy,
    });

    await screen.findByTestId("product-category-adjustment-history");
    expect(screen.queryByTestId("product-category-event-pca-existing-1-edited")).not.toBeInTheDocument();
    expect(screen.getByTestId("product-category-adjustment-history")).toHaveTextContent("2");
    expect(screen.getByTestId("product-category-audit-link")).toHaveAttribute(
      "href",
      "/product-category-pnl/audit",
    );

    await user.click(screen.getByTestId("product-category-revoke-pca-existing-1"));

    await waitFor(() => {
      expect(revokeSpy).toHaveBeenCalledWith("pca-existing-1");
      expect(refreshSpy).toHaveBeenCalledTimes(1);
    });
  });

  it("edits and restores a rejected adjustment", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
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
          adjustment_id: "pca-existing-2",
          created_at: "2026-04-10T09:40:00Z",
          stream: "product_category_pnl_adjustments",
          report_date: "2026-02-28",
          operator: "DELTA",
          approval_status: "rejected",
          account_code: "51402010001",
          currency: "CNX",
          account_name: "test-account-2",
          event_type: "rejected",
          monthly_pnl: "8",
        },
      ],
      events: [],
    }));
    const editSpy = vi.fn(async () => ({
      adjustment_id: "pca-existing-2",
      created_at: "2026-04-10T09:45:00Z",
      stream: "product_category_pnl_adjustments",
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "rejected",
      account_code: "51402010001",
      currency: "CNX",
      account_name: "test-account-2",
      event_type: "edited",
      monthly_pnl: "9",
    }));
    const restoreSpy = vi.fn(async () => ({
      adjustment_id: "pca-existing-2",
      created_at: "2026-04-10T09:50:00Z",
      stream: "product_category_pnl_adjustments",
      report_date: "2026-02-28",
      operator: "DELTA",
      approval_status: "approved",
      account_code: "51402010001",
      currency: "CNX",
      account_name: "test-account-2",
      event_type: "restored",
      monthly_pnl: "9",
    }));
    const refreshSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "product_category_pnl:edit-restore-refresh",
      job_name: "product_category_pnl",
      trigger_mode: "sync-fallback",
      cache_key: "product_category_pnl.formal",
      month_count: 2,
      report_dates: ["2026-01-31", "2026-02-28"],
      rule_version: "rv_product_category_pnl_v1",
      source_version: "sv_test",
    }));

    renderWorkbenchAppWithClient({
      ...baseClient,
      getProductCategoryManualAdjustments: listSpy,
      updateProductCategoryManualAdjustment: editSpy,
      restoreProductCategoryManualAdjustment: restoreSpy,
      refreshProductCategoryPnl: refreshSpy,
    });

    await screen.findByTestId("product-category-adjustment-history");
    await user.click(screen.getByTestId("product-category-edit-pca-existing-2"));

    const form = screen.getByTestId("product-category-manual-form");
    const textboxes = within(form).getAllByRole("textbox");
    await user.clear(textboxes[5]!);
    await user.type(textboxes[5]!, "9");
    await user.click(screen.getByTestId("product-category-manual-submit"));

    await waitFor(() => {
      expect(editSpy).toHaveBeenCalledTimes(1);
      expect(refreshSpy).toHaveBeenCalledTimes(1);
    });

    const restoreButton = await screen.findByTestId("product-category-restore-pca-existing-2");
    await waitFor(() => {
      expect(restoreButton).not.toBeDisabled();
    });
    await user.click(restoreButton);

    await waitFor(() => {
      expect(restoreSpy).toHaveBeenCalledWith("pca-existing-2");
      expect(refreshSpy).toHaveBeenCalledTimes(2);
    });
  });

  it("disables revoke/restore by approval_status and states lifecycle refresh in the adjustment lead", async () => {
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
    renderWorkbenchAppWithClient({
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
          { ...rowBase, adjustment_id: "pca-st-approved", approval_status: "approved" as const },
          { ...rowBase, adjustment_id: "pca-st-pending", approval_status: "pending" as const },
          { ...rowBase, adjustment_id: "pca-st-rejected", approval_status: "rejected" as const },
        ],
        events: [],
      }),
    });

    const lead = await screen.findByTestId("product-category-adjustment-lead");
    expect(lead).toHaveTextContent("仅当审批通过可撤销");
    expect(lead).toHaveTextContent("仅当已拒绝可恢复");
    expect(lead).toHaveTextContent("刷新工作流");

    await screen.findByTestId("product-category-revoke-pca-st-approved");
    expect(screen.getByTestId("product-category-revoke-pca-st-approved")).not.toBeDisabled();
    expect(screen.getByTestId("product-category-restore-pca-st-approved")).toBeDisabled();
    expect(screen.getByTestId("product-category-revoke-pca-st-pending")).toBeDisabled();
    expect(screen.getByTestId("product-category-restore-pca-st-pending")).toBeDisabled();
    expect(screen.getByTestId("product-category-revoke-pca-st-rejected")).toBeDisabled();
    expect(screen.getByTestId("product-category-restore-pca-st-rejected")).not.toBeDisabled();

    expect(screen.getByTestId("product-category-edit-pca-st-approved")).not.toBeDisabled();
    expect(screen.getByTestId("product-category-edit-pca-st-pending")).not.toBeDisabled();
    expect(screen.getByTestId("product-category-edit-pca-st-rejected")).not.toBeDisabled();
  });
});
