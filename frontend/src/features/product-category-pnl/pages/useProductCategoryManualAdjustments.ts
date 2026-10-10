import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import type { ProductCategoryManualAdjustmentRequest } from "../../../api/contracts";

type ProductCategoryAdjustmentMutationKind =
  "create" | "edit" | "revoke" | "restore";

type ManualAdjustmentsClient = Pick<
  ApiClient,
  | "mode"
  | "getProductCategoryManualAdjustments"
  | "createProductCategoryManualAdjustment"
  | "updateProductCategoryManualAdjustment"
  | "revokeProductCategoryManualAdjustment"
  | "restoreProductCategoryManualAdjustment"
  | "exportProductCategoryManualAdjustmentsCsv"
>;

function buildAdjustmentDraft(
  reportDate: string,
): ProductCategoryManualAdjustmentRequest {
  return {
    report_date: reportDate,
    operator: "DELTA",
    approval_status: "approved",
    account_code: "",
    currency: "CNX",
    account_name: "",
    beginning_balance: null,
    ending_balance: null,
    monthly_pnl: null,
    daily_avg_balance: null,
    annual_avg_balance: null,
  };
}

function downloadProductCategoryAdjustmentsCsv(
  filename: string,
  content: string,
) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

/** Keeps adjustment writes, refresh completion, and form state in one lifecycle. */
export function useProductCategoryManualAdjustments(
  client: ManualAdjustmentsClient,
  selectedDate: string,
  runRefreshWorkflow: () => Promise<unknown>,
) {
  const [showManualForm, setShowManualForm] = useState(false);
  const [editingAdjustmentId, setEditingAdjustmentId] = useState<string | null>(
    null,
  );
  const [adjustmentMutationKind, setAdjustmentMutationKind] =
    useState<ProductCategoryAdjustmentMutationKind | null>(null);
  const [isExportingAdjustments, setIsExportingAdjustments] = useState(false);
  const [adjustmentError, setAdjustmentError] = useState<string | null>(null);
  const [adjustmentExportError, setAdjustmentExportError] = useState<
    string | null
  >(null);
  const [exportedAdjustmentFilename, setExportedAdjustmentFilename] = useState<
    string | null
  >(null);
  const [lastAdjustmentId, setLastAdjustmentId] = useState<string | null>(null);
  const [adjustmentDraft, setAdjustmentDraft] =
    useState<ProductCategoryManualAdjustmentRequest>(buildAdjustmentDraft(""));
  const adjustmentFormVersion = useRef(0);

  useEffect(() => {
    adjustmentFormVersion.current += 1;
    setEditingAdjustmentId(null);
    setAdjustmentError(null);
    setAdjustmentDraft((current) => ({
      ...current,
      report_date: selectedDate,
    }));
  }, [selectedDate]);

  const adjustmentsQuery = useQuery({
    queryKey: [
      "product-category-pnl",
      "adjustments",
      client.mode,
      selectedDate,
    ],
    queryFn: () => client.getProductCategoryManualAdjustments(selectedDate),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  function updateAdjustmentField<
    K extends keyof ProductCategoryManualAdjustmentRequest,
  >(key: K, value: ProductCategoryManualAdjustmentRequest[K]) {
    setAdjustmentDraft((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function handleManualAdjustmentSubmit() {
    setAdjustmentError(null);
    if (!adjustmentDraft.report_date) {
      setAdjustmentError("请选择报表月份。");
      return;
    }
    if (!adjustmentDraft.account_code.trim()) {
      setAdjustmentError("请输入科目代码。");
      return;
    }
    if (
      !adjustmentDraft.beginning_balance &&
      !adjustmentDraft.ending_balance &&
      !adjustmentDraft.monthly_pnl &&
      !adjustmentDraft.daily_avg_balance &&
      !adjustmentDraft.annual_avg_balance
    ) {
      setAdjustmentError("至少填写一个调整数值。");
      return;
    }

    const submittedFormVersion = adjustmentFormVersion.current;
    setAdjustmentMutationKind(editingAdjustmentId ? "edit" : "create");
    try {
      const payload = editingAdjustmentId
        ? await client.updateProductCategoryManualAdjustment(
            editingAdjustmentId,
            adjustmentDraft,
          )
        : await client.createProductCategoryManualAdjustment(adjustmentDraft);
      setLastAdjustmentId(payload.adjustment_id);
      await runRefreshWorkflow();
      // Date changes and reopened forms belong to a new editing context.
      // The completed write still refreshes reads, but must not reset that form.
      if (adjustmentFormVersion.current !== submittedFormVersion) {
        return;
      }
      setShowManualForm(false);
      setEditingAdjustmentId(null);
      setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
    } catch (error) {
      if (adjustmentFormVersion.current === submittedFormVersion) {
        setAdjustmentError(
          error instanceof Error ? error.message : "手工录入失败",
        );
      }
    } finally {
      setAdjustmentMutationKind(null);
    }
  }

  async function handleManualAdjustmentRevoke(adjustmentId: string) {
    if (
      !window.confirm(
        `Confirm revoke product-category adjustment ${adjustmentId}?`,
      )
    ) {
      return;
    }
    setAdjustmentError(null);
    setAdjustmentMutationKind("revoke");
    try {
      await client.revokeProductCategoryManualAdjustment(adjustmentId);
      await runRefreshWorkflow();
    } catch (error) {
      setAdjustmentError(
        error instanceof Error ? error.message : "撤销手工录入失败",
      );
    } finally {
      setAdjustmentMutationKind(null);
    }
  }

  async function handleManualAdjustmentRestore(adjustmentId: string) {
    setAdjustmentError(null);
    setAdjustmentMutationKind("restore");
    try {
      await client.restoreProductCategoryManualAdjustment(adjustmentId);
      await runRefreshWorkflow();
    } catch (error) {
      setAdjustmentError(
        error instanceof Error ? error.message : "恢复手工录入失败",
      );
    } finally {
      setAdjustmentMutationKind(null);
    }
  }

  async function handleManualAdjustmentsExport() {
    setAdjustmentExportError(null);
    if (!selectedDate) {
      setAdjustmentExportError("请选择报表月份后再导出。");
      return;
    }
    setIsExportingAdjustments(true);
    try {
      const payload =
        await client.exportProductCategoryManualAdjustmentsCsv(selectedDate);
      downloadProductCategoryAdjustmentsCsv(payload.filename, payload.content);
      setExportedAdjustmentFilename(payload.filename);
    } catch (error) {
      setAdjustmentExportError(
        error instanceof Error ? error.message : "导出手工调整失败",
      );
    } finally {
      setIsExportingAdjustments(false);
    }
  }

  function handleManualAdjustmentEdit(adjustment: {
    adjustment_id: string;
    report_date: string;
    operator: "ADD" | "DELTA" | "OVERRIDE";
    approval_status: "approved" | "pending" | "rejected";
    account_code: string;
    currency: "CNX" | "CNY";
    account_name?: string;
    beginning_balance?: string | null;
    ending_balance?: string | null;
    monthly_pnl?: string | null;
    daily_avg_balance?: string | null;
    annual_avg_balance?: string | null;
  }) {
    adjustmentFormVersion.current += 1;
    setEditingAdjustmentId(adjustment.adjustment_id);
    setAdjustmentDraft({
      report_date: adjustment.report_date,
      operator: adjustment.operator,
      approval_status: adjustment.approval_status,
      account_code: adjustment.account_code,
      currency: adjustment.currency,
      account_name: adjustment.account_name ?? "",
      beginning_balance: adjustment.beginning_balance ?? null,
      ending_balance: adjustment.ending_balance ?? null,
      monthly_pnl: adjustment.monthly_pnl ?? null,
      daily_avg_balance: adjustment.daily_avg_balance ?? null,
      annual_avg_balance: adjustment.annual_avg_balance ?? null,
    });
    setAdjustmentError(null);
    setShowManualForm(true);
  }

  function handleManualAdjustmentToggle() {
    adjustmentFormVersion.current += 1;
    setShowManualForm((current) => !current);
    setEditingAdjustmentId(null);
    setAdjustmentError(null);
    if (showManualForm) {
      setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
    }
  }

  function handleManualAdjustmentCancel() {
    adjustmentFormVersion.current += 1;
    setShowManualForm(false);
    setEditingAdjustmentId(null);
    setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
  }

  function handleManualAdjustmentCreate() {
    adjustmentFormVersion.current += 1;
    setEditingAdjustmentId(null);
    setAdjustmentError(null);
    setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
    setShowManualForm(true);
    const scrollToForm = () =>
      document
        .getElementById("product-category-manual-adjustment-form")
        ?.scrollIntoView?.({ block: "center" });
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(scrollToForm);
    } else {
      scrollToForm();
    }
  }

  return {
    adjustmentsQuery,
    showManualForm,
    editingAdjustmentId,
    adjustmentMutationKind,
    isSubmittingAdjustment: adjustmentMutationKind !== null,
    isExportingAdjustments,
    adjustmentError,
    adjustmentExportError,
    exportedAdjustmentFilename,
    lastAdjustmentId,
    adjustmentDraft,
    updateAdjustmentField,
    handleManualAdjustmentSubmit,
    handleManualAdjustmentRevoke,
    handleManualAdjustmentRestore,
    handleManualAdjustmentsExport,
    handleManualAdjustmentEdit,
    handleManualAdjustmentToggle,
    handleManualAdjustmentCancel,
    handleManualAdjustmentCreate,
  };
}
