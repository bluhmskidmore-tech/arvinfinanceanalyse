import type { PropsWithChildren } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { useProductCategoryManualAdjustments } from "./useProductCategoryManualAdjustments";

const adjustment = {
  adjustment_id: "adjustment-test",
  event_type: "created",
  created_at: "2026-04-10T09:40:00Z",
  stream: "product_category_pnl_adjustments",
  report_date: "2026-02-28",
  operator: "DELTA",
  approval_status: "approved",
  account_code: "001234",
  currency: "CNX",
  account_name: "测试科目",
  monthly_pnl: "5",
} as const;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((next, fail) => { resolve = next; reject = fail; });
  return { promise, resolve, reject };
}

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity, gcTime: Infinity },
    },
  });
  const client = {
    mode: "mock" as const,
    getProductCategoryManualAdjustments: vi.fn(async (reportDate: string) => ({
      report_date: reportDate,
      adjustment_count: 0,
      adjustment_limit: 20,
      adjustment_offset: 0,
      event_total: 0,
      event_limit: 20,
      event_offset: 0,
      adjustments: [],
      events: [],
    })),
    createProductCategoryManualAdjustment: vi.fn(async () => adjustment),
    updateProductCategoryManualAdjustment: vi.fn(async () => adjustment),
    revokeProductCategoryManualAdjustment: vi.fn(async () => adjustment),
    restoreProductCategoryManualAdjustment: vi.fn(async () => adjustment),
    exportProductCategoryManualAdjustmentsCsv: vi.fn(async () => ({
      filename: "adjustments.csv",
      content: "account_code,monthly_pnl\n001234,5",
    })),
  };
  const runRefreshWorkflow = vi.fn(async () => undefined);
  function wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return { client, runRefreshWorkflow, wrapper };
}

describe("product-category manual adjustment lifecycle", () => {
  it.each(["create", "edit"] as const)(
    "keeps the %s form and draft until the write and refresh both complete",
    async (kind) => {
      const { client, runRefreshWorkflow, wrapper } = setup();
      const write = deferred<typeof adjustment>();
      const refresh = deferred<undefined>();
      client.createProductCategoryManualAdjustment.mockReturnValue(write.promise);
      client.updateProductCategoryManualAdjustment.mockReturnValue(write.promise);
      runRefreshWorkflow.mockReturnValue(refresh.promise);
      const { result } = renderHook(() => useProductCategoryManualAdjustments(
        client,
        "2026-02-28",
        runRefreshWorkflow,
      ), { wrapper });
      const amount = "-9007199254740993.001200";
      act(() => {
        if (kind === "edit") {
          result.current.handleManualAdjustmentEdit(adjustment);
        } else {
          result.current.handleManualAdjustmentToggle();
          result.current.updateAdjustmentField("account_code", "001234");
        }
        result.current.updateAdjustmentField("monthly_pnl", amount);
      });

      let work!: Promise<void>;
      act(() => { work = result.current.handleManualAdjustmentSubmit(); });

      expect(result.current.adjustmentMutationKind).toBe(kind);
      expect(result.current.isSubmittingAdjustment).toBe(true);
      expect(runRefreshWorkflow).not.toHaveBeenCalled();
      await act(async () => { write.resolve(adjustment); await write.promise; });

      expect(runRefreshWorkflow).toHaveBeenCalledOnce();
      expect(result.current.lastAdjustmentId).toBe(adjustment.adjustment_id);
      expect(result.current.showManualForm).toBe(true);
      expect(result.current.adjustmentDraft.monthly_pnl).toBe(amount);
      expect(result.current.editingAdjustmentId).toBe(
        kind === "edit" ? adjustment.adjustment_id : null,
      );
      expect(result.current.isSubmittingAdjustment).toBe(true);
      if (kind === "edit") {
        expect(client.updateProductCategoryManualAdjustment).toHaveBeenCalledWith(
          adjustment.adjustment_id,
          expect.objectContaining({ monthly_pnl: amount, account_code: "001234" }),
        );
        expect(client.createProductCategoryManualAdjustment).not.toHaveBeenCalled();
      } else {
        expect(client.createProductCategoryManualAdjustment).toHaveBeenCalledWith(
          expect.objectContaining({ monthly_pnl: amount, account_code: "001234" }),
        );
        expect(client.updateProductCategoryManualAdjustment).not.toHaveBeenCalled();
      }

      await act(async () => { refresh.resolve(undefined); await work; });

      expect(result.current.showManualForm).toBe(false);
      expect(result.current.editingAdjustmentId).toBeNull();
      expect(result.current.isSubmittingAdjustment).toBe(false);
      expect(result.current.adjustmentDraft).toMatchObject({
        report_date: "2026-02-28",
        account_code: "",
        monthly_pnl: null,
      });
    },
  );

  it("retains the edit and draft when refresh fails after the write succeeds", async () => {
    const { client, runRefreshWorkflow, wrapper } = setup();
    runRefreshWorkflow.mockRejectedValueOnce(new Error("刷新未完成"));
    const { result } = renderHook(() => useProductCategoryManualAdjustments(
      client,
      "2026-02-28",
      runRefreshWorkflow,
    ), { wrapper });
    act(() => {
      result.current.handleManualAdjustmentEdit(adjustment);
      result.current.updateAdjustmentField("monthly_pnl", "0");
    });

    await act(async () => { await result.current.handleManualAdjustmentSubmit(); });

    expect(client.updateProductCategoryManualAdjustment).toHaveBeenCalledOnce();
    expect(runRefreshWorkflow).toHaveBeenCalledOnce();
    expect(result.current.lastAdjustmentId).toBe(adjustment.adjustment_id);
    expect(result.current.showManualForm).toBe(true);
    expect(result.current.editingAdjustmentId).toBe(adjustment.adjustment_id);
    expect(result.current.adjustmentDraft.monthly_pnl).toBe("0");
    expect(result.current.adjustmentError).toBe("刷新未完成");
    expect(result.current.isSubmittingAdjustment).toBe(false);
  });

  it.each([
    ["create", "write"],
    ["create", "refresh"],
    ["edit", "write"],
    ["edit", "refresh"],
  ] as const)(
    "keeps a reopened next-month form when the old %s finishes after switching during %s",
    async (kind, waitingStage) => {
      const { client, runRefreshWorkflow, wrapper } = setup();
      const write = deferred<typeof adjustment>();
      const refresh = deferred<undefined>();
      client.createProductCategoryManualAdjustment.mockReturnValueOnce(write.promise);
      client.updateProductCategoryManualAdjustment.mockReturnValueOnce(write.promise);
      runRefreshWorkflow.mockReturnValueOnce(refresh.promise);
      const { result, rerender } = renderHook(({ reportDate }) =>
        useProductCategoryManualAdjustments(client, reportDate, runRefreshWorkflow),
      { wrapper, initialProps: { reportDate: "2026-02-28" } });
      act(() => {
        if (kind === "edit") {
          result.current.handleManualAdjustmentEdit(adjustment);
        } else {
          result.current.handleManualAdjustmentToggle();
          result.current.updateAdjustmentField("account_code", "001234");
          result.current.updateAdjustmentField("monthly_pnl", "5");
        }
      });
      let oldSubmit!: Promise<void>;
      act(() => { oldSubmit = result.current.handleManualAdjustmentSubmit(); });
      if (waitingStage === "refresh") {
        await act(async () => { write.resolve(adjustment); await write.promise; });
        expect(runRefreshWorkflow).toHaveBeenCalledOnce();
      } else {
        expect(runRefreshWorkflow).not.toHaveBeenCalled();
      }

      // The previous request still belongs to February; the reader has opened
      // and started a separate March form before that request finishes.
      act(() => { result.current.handleManualAdjustmentCancel(); });
      rerender({ reportDate: "2026-03-31" });
      act(() => {
        result.current.handleManualAdjustmentToggle();
        result.current.updateAdjustmentField("account_code", "005678");
        result.current.updateAdjustmentField("monthly_pnl", "7");
      });
      expect(result.current.showManualForm).toBe(true);
      expect(result.current.adjustmentDraft.report_date).toBe("2026-03-31");

      if (waitingStage === "write") {
        await act(async () => { write.resolve(adjustment); await write.promise; });
      }
      await act(async () => { refresh.resolve(undefined); await oldSubmit; });

      const originalRequest = expect.objectContaining({
        report_date: "2026-02-28",
        account_code: "001234",
        monthly_pnl: "5",
      });
      if (kind === "edit") {
        expect(client.updateProductCategoryManualAdjustment).toHaveBeenCalledWith(
          adjustment.adjustment_id,
          originalRequest,
        );
      } else {
        expect(client.createProductCategoryManualAdjustment).toHaveBeenNthCalledWith(
          1,
          originalRequest,
        );
      }
      expect(result.current.showManualForm).toBe(true);
      expect(result.current.editingAdjustmentId).toBeNull();
      expect(result.current.adjustmentDraft).toMatchObject({
        report_date: "2026-03-31",
        account_code: "005678",
        monthly_pnl: "7",
      });
      expect(result.current.isSubmittingAdjustment).toBe(false);

      await act(async () => { await result.current.handleManualAdjustmentSubmit(); });

      expect(client.createProductCategoryManualAdjustment).toHaveBeenLastCalledWith(
        expect.objectContaining({
          report_date: "2026-03-31",
          account_code: "005678",
          monthly_pnl: "7",
        }),
      );
      expect(client.createProductCategoryManualAdjustment).toHaveBeenCalledTimes(
        kind === "create" ? 2 : 1,
      );
      expect(runRefreshWorkflow).toHaveBeenCalledTimes(2);
    },
  );

  it.each(["create", "edit"] as const)(
    "ends the old %s context on a direct month switch and submits the next draft as a new adjustment",
    async (kind) => {
      const { client, runRefreshWorkflow, wrapper } = setup();
      const refresh = deferred<undefined>();
      runRefreshWorkflow.mockReturnValueOnce(refresh.promise);
      const { result, rerender } = renderHook(({ reportDate }) =>
        useProductCategoryManualAdjustments(client, reportDate, runRefreshWorkflow),
      { wrapper, initialProps: { reportDate: "2026-02-28" } });
      act(() => {
        if (kind === "edit") {
          result.current.handleManualAdjustmentEdit(adjustment);
        } else {
          result.current.handleManualAdjustmentToggle();
          result.current.updateAdjustmentField("account_code", "001234");
          result.current.updateAdjustmentField("monthly_pnl", "5");
        }
      });
      let oldSubmit!: Promise<void>;
      act(() => { oldSubmit = result.current.handleManualAdjustmentSubmit(); });
      await waitFor(() => expect(runRefreshWorkflow).toHaveBeenCalledOnce());

      rerender({ reportDate: "2026-03-31" });

      expect(result.current.editingAdjustmentId).toBeNull();
      expect(result.current.adjustmentDraft).toMatchObject({
        report_date: "2026-03-31",
        account_code: "001234",
        monthly_pnl: "5",
      });
      act(() => {
        result.current.updateAdjustmentField("account_code", "005678");
        result.current.updateAdjustmentField("monthly_pnl", "7");
      });
      await act(async () => { refresh.resolve(undefined); await oldSubmit; });

      expect(result.current.showManualForm).toBe(true);
      expect(result.current.adjustmentDraft.report_date).toBe("2026-03-31");
      await act(async () => { await result.current.handleManualAdjustmentSubmit(); });

      expect(client.createProductCategoryManualAdjustment).toHaveBeenLastCalledWith(
        expect.objectContaining({
          report_date: "2026-03-31",
          account_code: "005678",
          monthly_pnl: "7",
        }),
      );
      expect(client.updateProductCategoryManualAdjustment).toHaveBeenCalledTimes(
        kind === "edit" ? 1 : 0,
      );
      if (kind === "edit") {
        expect(client.updateProductCategoryManualAdjustment).toHaveBeenCalledWith(
          adjustment.adjustment_id,
          expect.objectContaining({ report_date: "2026-02-28" }),
        );
      }
    },
  );

  it.each(["write", "refresh"] as const)(
    "keeps a late %s error off a form cancelled and reopened in the same month",
    async (waitingStage) => {
      const { client, runRefreshWorkflow, wrapper } = setup();
      const write = deferred<typeof adjustment>();
      const refresh = deferred<undefined>();
      client.createProductCategoryManualAdjustment.mockReturnValueOnce(write.promise);
      runRefreshWorkflow.mockReturnValueOnce(refresh.promise);
      const { result } = renderHook(() => useProductCategoryManualAdjustments(
        client,
        "2026-02-28",
        runRefreshWorkflow,
      ), { wrapper });
      act(() => {
        result.current.handleManualAdjustmentToggle();
        result.current.updateAdjustmentField("account_code", "001234");
        result.current.updateAdjustmentField("monthly_pnl", "5");
      });
      let oldSubmit!: Promise<void>;
      act(() => { oldSubmit = result.current.handleManualAdjustmentSubmit(); });
      if (waitingStage === "refresh") {
        await act(async () => { write.resolve(adjustment); await write.promise; });
        expect(runRefreshWorkflow).toHaveBeenCalledOnce();
      }
      act(() => { result.current.handleManualAdjustmentCancel(); });
      act(() => {
        result.current.handleManualAdjustmentToggle();
        result.current.updateAdjustmentField("account_code", "005678");
        result.current.updateAdjustmentField("monthly_pnl", "7");
      });

      await act(async () => {
        if (waitingStage === "write") {
          write.reject(new Error("旧写入失败"));
        } else {
          refresh.reject(new Error("旧刷新失败"));
        }
        await oldSubmit;
      });

      expect(result.current.showManualForm).toBe(true);
      expect(result.current.adjustmentError).toBeNull();
      expect(result.current.adjustmentDraft).toMatchObject({
        report_date: "2026-02-28",
        account_code: "005678",
        monthly_pnl: "7",
      });
      expect(result.current.isSubmittingAdjustment).toBe(false);
      expect(runRefreshWorkflow).toHaveBeenCalledTimes(
        waitingStage === "refresh" ? 1 : 0,
      );
    },
  );

  it("follows the selected report date without clearing entered account or amount values", async () => {
    const { client, runRefreshWorkflow, wrapper } = setup();
    const { result, rerender } = renderHook(({ reportDate }) =>
      useProductCategoryManualAdjustments(client, reportDate, runRefreshWorkflow),
    { wrapper, initialProps: { reportDate: "2026-02-28" } });
    await waitFor(() => expect(result.current.adjustmentsQuery.isSuccess).toBe(true));
    act(() => {
      result.current.handleManualAdjustmentToggle();
      result.current.updateAdjustmentField("account_code", "001234");
      result.current.updateAdjustmentField("beginning_balance", "0");
    });

    rerender({ reportDate: "2026-03-31" });

    await waitFor(() => expect(result.current.adjustmentsQuery.data?.report_date)
      .toBe("2026-03-31"));
    expect(client.getProductCategoryManualAdjustments).toHaveBeenCalledTimes(2);
    expect(result.current.adjustmentDraft).toMatchObject({
      report_date: "2026-03-31",
      account_code: "001234",
      beginning_balance: "0",
    });
    expect(result.current.showManualForm).toBe(true);
  });
});
