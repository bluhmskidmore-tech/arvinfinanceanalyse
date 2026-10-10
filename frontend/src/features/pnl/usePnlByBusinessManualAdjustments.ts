import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ApiClient } from "../../api/client";
import { type PnlByBusinessManualAdjustmentPayload, type PnlByBusinessManualAdjustmentRequest, type PnlByBusinessYtdItem } from "../../api/contracts";
import { type ManualAdjustmentDraft, EMPTY_MANUAL_ADJUSTMENT_DRAFT, normalizeAdjustmentStatus } from "./pnlByBusinessAdjustmentState";
import { type PnlByBusinessViewMode } from "./pnlByBusinessPageModel";

/** 手工调整草稿、审批记录与操作回执始终随页面挂载，切换显示区块不丢失编辑状态。 */
export function usePnlByBusinessManualAdjustments({
  client,
  selectedReportDate,
  manualAdjustmentReportDate,
  viewMode,
  selectedBusinessRow,
  setSelectedBusinessKey,
  setAnalysisLoadStage,
}: {
  client: ApiClient;
  selectedReportDate: string;
  manualAdjustmentReportDate: string;
  viewMode: PnlByBusinessViewMode;
  selectedBusinessRow: PnlByBusinessYtdItem | undefined;
  setSelectedBusinessKey: (rowKey: string) => void;
  setAnalysisLoadStage: (stage: number) => void;
}) {
  const queryClient = useQueryClient();
  const [editingAdjustmentId, setEditingAdjustmentId] = useState<string | null>(null);
  const [adjustmentDraft, setAdjustmentDraft] = useState<ManualAdjustmentDraft>(() => ({
    ...EMPTY_MANUAL_ADJUSTMENT_DRAFT,
  }));
  const [adjustmentError, setAdjustmentError] = useState("");
  const manualAdjustmentQuery = useQuery({
    queryKey: ["pnl-by-business", "manual-adjustments", client.mode, manualAdjustmentReportDate],
    enabled: Boolean(manualAdjustmentReportDate && viewMode !== "formal"),
    queryFn: () => client.getPnlByBusinessManualAdjustments(manualAdjustmentReportDate),
    retry: false,
  });
  const manualAdjustmentDateMismatch = Boolean(
    manualAdjustmentQuery.data && manualAdjustmentQuery.data.report_date !== manualAdjustmentReportDate,
  );
  const manualAdjustmentReadError = manualAdjustmentQuery.isError
    ? "审批记录读取失败，请勿据此判断调整数量或新增重复记录。"
    : manualAdjustmentDateMismatch
      ? `审批记录报表日 ${manualAdjustmentQuery.data?.report_date ?? "未返回"} 与所选报表日 ${manualAdjustmentReportDate} 不一致，未采用该记录。`
      : null;
  const currentAdjustments = manualAdjustmentDateMismatch ? [] : (manualAdjustmentQuery.data?.adjustments ?? []);
  const adjustmentEvents = manualAdjustmentDateMismatch ? [] : (manualAdjustmentQuery.data?.events ?? []);
  const approvedAdjustmentCount = currentAdjustments.filter(
    (adjustment) => adjustment.approval_status === "approved",
  ).length;

  const invalidatePnlByBusinessQueries = async () => {
    await queryClient.invalidateQueries({ queryKey: ["pnl-by-business"] });
  };

  const resetAdjustmentDraft = () => {
    setEditingAdjustmentId(null);
    setAdjustmentDraft({ ...EMPTY_MANUAL_ADJUSTMENT_DRAFT });
  };

  const saveAdjustmentMutation = useMutation({
    mutationFn: (payload: PnlByBusinessManualAdjustmentRequest) =>
      editingAdjustmentId
        ? client.updatePnlByBusinessManualAdjustment(editingAdjustmentId, payload)
        : client.createPnlByBusinessManualAdjustment(payload),
    onSuccess: async () => {
      setAdjustmentError("");
      resetAdjustmentDraft();
      setAnalysisLoadStage(0);
      await invalidatePnlByBusinessQueries();
    },
    onError: (error) => {
      setAdjustmentError(error instanceof Error ? error.message : "保存手工调整失败");
    },
  });

  const adjustmentActionMutation = useMutation({
    mutationFn: ({ adjustmentId, action }: { adjustmentId: string; action: "revoke" | "restore" }) =>
      action === "revoke"
        ? client.revokePnlByBusinessManualAdjustment(adjustmentId)
        : client.restorePnlByBusinessManualAdjustment(adjustmentId),
    onSuccess: async () => {
      setAdjustmentError("");
      setAnalysisLoadStage(0);
      await invalidatePnlByBusinessQueries();
    },
    onError: (error) => {
      setAdjustmentError(error instanceof Error ? error.message : "更新手工调整状态失败");
    },
  });
  const updateAdjustmentDraft = <K extends keyof ManualAdjustmentDraft>(
    key: K,
    value: ManualAdjustmentDraft[K],
  ) => {
    setAdjustmentDraft((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const handleSubmitAdjustment = () => {
    setAdjustmentError("");
    const targetRow = selectedBusinessRow;
    if (!selectedReportDate || !targetRow?.row_key) {
      setAdjustmentError("请选择报表日和业务种类。");
      return;
    }
    const amount = adjustmentDraft.manual_adjustment.trim();
    if (!amount) {
      setAdjustmentError("请填写调整金额。");
      return;
    }
    if (!Number.isFinite(Number(amount))) {
      setAdjustmentError("调整金额必须是数字。");
      return;
    }

    saveAdjustmentMutation.mutate({
      report_date: selectedReportDate,
      row_key: targetRow.row_key,
      business_type: targetRow.business_type,
      operator: "DELTA",
      approval_status: adjustmentDraft.approval_status,
      manual_adjustment: amount,
      reason: adjustmentDraft.reason?.trim() ?? "",
    });
  };

  const handleEditAdjustment = (item: PnlByBusinessManualAdjustmentPayload) => {
    setAdjustmentError("");
    setEditingAdjustmentId(item.adjustment_id);
    setSelectedBusinessKey(item.row_key);
    setAdjustmentDraft({
      manual_adjustment: item.manual_adjustment,
      approval_status: normalizeAdjustmentStatus(item.approval_status),
      reason: item.reason ?? "",
    });
  };

  return {
    manualAdjustmentQuery,
    manualAdjustmentDateMismatch,
    manualAdjustmentReadError,
    currentAdjustments,
    adjustmentEvents,
    approvedAdjustmentCount,
    adjustmentDraft,
    editingAdjustmentId,
    adjustmentError,
    saveAdjustmentMutation,
    adjustmentActionMutation,
    resetAdjustmentDraft,
    updateAdjustmentDraft,
    handleSubmitAdjustment,
    handleEditAdjustment,
  };
}
