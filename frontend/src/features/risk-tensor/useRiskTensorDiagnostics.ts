import { useEffect, useRef, useState } from "react";
import { errorEvidenceMessage } from "./riskTensorPresentation";
import type { RiskTensorQualityEvidence } from "./riskTensorEvidenceModel";
import type { useRiskTensorQueries } from "./useRiskTensorQueries";

export function useRiskTensorDiagnostics(
  queries: ReturnType<typeof useRiskTensorQueries>,
  evidence: Pick<RiskTensorQualityEvidence, "metadataTablesUsed" | "metadataFiltersApplied">,
) {
  const { datesQuery, tensorQuery, explicitReportDate, reportDate, result, selectedBlockedReportDate, tensorErrorStatusCode, datesErrorStatusCode, tensorErrorReportDate, datesErrorReportDate, datesGovernanceMeta, datesEmptyTraceId } = queries;
  const tensorMeta = queries.envelope?.result_meta;
  const { metadataTablesUsed, metadataFiltersApplied } = evidence;
  const [tensorErrorCopyStatus, setTensorErrorCopyStatus] = useState<"idle" | "copied" | "failed">("idle");

  const [tensorErrorCopiedStateKey, setTensorErrorCopiedStateKey] = useState("");

  const tensorErrorCopyRequestKeyRef = useRef("");

  const [blockedDateCopyStatus, setBlockedDateCopyStatus] = useState<"idle" | "copied" | "failed">("idle");

  const [blockedDateCopiedStateKey, setBlockedDateCopiedStateKey] = useState("");

  const blockedDateCopyRequestKeyRef = useRef("");

  const [datesErrorCopyStatus, setDatesErrorCopyStatus] = useState<"idle" | "copied" | "failed">("idle");

  const [datesErrorCopiedStateKey, setDatesErrorCopiedStateKey] = useState("");

  const datesErrorCopyRequestKeyRef = useRef("");

  const [datesEmptyCopyStatus, setDatesEmptyCopyStatus] = useState<"idle" | "copied" | "failed">("idle");

  const [datesEmptyCopiedStateKey, setDatesEmptyCopiedStateKey] = useState("");

  const datesEmptyCopyRequestKeyRef = useRef("");

  const [emptyPositionCopyStatus, setEmptyPositionCopyStatus] = useState<"idle" | "copied" | "failed">("idle");

  const [emptyPositionCopiedStateKey, setEmptyPositionCopiedStateKey] = useState("");

  const emptyPositionCopyStateKeyRef = useRef("");

  const tensorErrorCopyText = [
    "风险张量主读面加载失败排查信息",
    `报告日 ${tensorErrorReportDate}`,
    `HTTP 状态 ${tensorErrorStatusCode || "未知"}`,
    `日期治理 trace_id ${datesGovernanceMeta?.trace_id ?? "未提供"}`,
    `basis ${datesGovernanceMeta?.basis ?? "未提供"}`,
    `cache_version ${datesGovernanceMeta?.cache_version ?? "未提供"}`,
    `generated_at ${datesGovernanceMeta?.generated_at ?? "未提供"}`,
    `source_version ${datesGovernanceMeta?.source_version ?? "未提供"}`,
    `rule_version ${datesGovernanceMeta?.rule_version ?? "未提供"}`,
    "主读面 trace_id 未提供",
    "请先核对正式风险张量物化和 lineage 新鲜度",
    "页面不会使用缓存或前端补算替代正式主读结果",
  ].join("\n");

  const tensorErrorCopyStateKey = [
    `report_date:${tensorErrorReportDate}`,
    `status:${tensorErrorStatusCode || "unknown"}`,
    `dates_trace_id:${datesGovernanceMeta?.trace_id ?? "missing"}`,
    `basis:${datesGovernanceMeta?.basis ?? "missing"}`,
    `cache_version:${datesGovernanceMeta?.cache_version ?? "missing"}`,
    `generated_at:${datesGovernanceMeta?.generated_at ?? "missing"}`,
    `source_version:${datesGovernanceMeta?.source_version ?? "missing"}`,
    `rule_version:${datesGovernanceMeta?.rule_version ?? "missing"}`,
  ].join("|");

  const tensorErrorCopyStatusForCurrentState =
    tensorErrorCopiedStateKey === tensorErrorCopyStateKey ? tensorErrorCopyStatus : "idle";

  const tensorErrorCopyMessage =
    tensorErrorCopyStatusForCurrentState === "copied"
      ? "已复制排查信息"
      : tensorErrorCopyStatusForCurrentState === "failed"
        ? "复制失败，请手动选择排查信息"
        : "";

  const blockedDateCopyText = [
    "风险张量报告日拦截排查信息",
    `报告日 ${selectedBlockedReportDate?.report_date ?? (explicitReportDate || "未选择")}`,
    `reason ${selectedBlockedReportDate?.reason || "后端未返回原因"}`,
    `日期治理 trace_id ${datesGovernanceMeta?.trace_id ?? "未提供"}`,
    "主读面未读取",
    "请切换到可用报告日",
  ].join("\n");

  const blockedDateCopyStateKey = [
    `report_date:${selectedBlockedReportDate?.report_date ?? (explicitReportDate || "missing")}`,
    `reason:${selectedBlockedReportDate?.reason || "missing"}`,
    `explicit_report_date:${explicitReportDate || "missing"}`,
    `trace_id:${datesGovernanceMeta?.trace_id ?? "missing"}`,
    `basis:${datesGovernanceMeta?.basis ?? "missing"}`,
    `cache_version:${datesGovernanceMeta?.cache_version ?? "missing"}`,
    `generated_at:${datesGovernanceMeta?.generated_at ?? "missing"}`,
    `source_version:${datesGovernanceMeta?.source_version ?? "missing"}`,
    `rule_version:${datesGovernanceMeta?.rule_version ?? "missing"}`,
  ].join("|");

  const blockedDateCopyStatusForCurrentState =
    blockedDateCopiedStateKey === blockedDateCopyStateKey ? blockedDateCopyStatus : "idle";

  const blockedDateCopyMessage =
    blockedDateCopyStatusForCurrentState === "copied"
      ? "已复制拦截信息"
      : blockedDateCopyStatusForCurrentState === "failed"
        ? "复制失败，请手动选择拦截信息"
        : "";

  const datesErrorCopyText = [
    "风险张量报告日列表加载失败排查信息",
    `HTTP 状态 ${datesErrorStatusCode || "未知"}`,
    `错误 ${errorEvidenceMessage(datesQuery.error) || "未提供"}`,
    "请求 /api/risk/tensor/dates",
    `报告日参数 ${datesErrorReportDate}`,
    "页面不会回退到硬编码报告日",
    "主读面未读取",
    "请核对风险张量报告日物化任务和日期治理接口",
  ].join("\n");

  const datesErrorCopyStateKey = [
    `report_date_param:${datesErrorReportDate}`,
    `status:${datesErrorStatusCode || "unknown"}`,
    `error:${errorEvidenceMessage(datesQuery.error) || "missing"}`,
  ].join("|");

  const datesErrorCopyStatusForCurrentState =
    datesErrorCopiedStateKey === datesErrorCopyStateKey ? datesErrorCopyStatus : "idle";

  const datesErrorCopyMessage =
    datesErrorCopyStatusForCurrentState === "copied"
      ? "已复制日期排查信息"
      : datesErrorCopyStatusForCurrentState === "failed"
        ? "复制失败，请手动选择日期排查信息"
        : "";

  const datesEmptyCopyStateKey = [
    `trace_id:${datesEmptyTraceId}`,
    `report_date_param:${datesErrorReportDate}`,
    `available_count:${datesQuery.data?.result.report_dates.length ?? "missing"}`,
  ].join("|");

  const datesEmptyCopyText = [
    "风险张量报告日列表为空排查信息",
    `trace_id ${datesEmptyTraceId}`,
    "可用报告日 0 个",
    `报告日参数 ${datesErrorReportDate}`,
    "页面不会回退到硬编码报告日",
    "主读面未读取",
    "请核对风险张量报告日物化任务和日期治理结果",
  ].join("\n");

  const datesEmptyCopyStatusForCurrentState =
    datesEmptyCopiedStateKey === datesEmptyCopyStateKey ? datesEmptyCopyStatus : "idle";

  const datesEmptyCopyMessage =
    datesEmptyCopyStatusForCurrentState === "copied"
      ? "已复制空日期排查信息"
      : datesEmptyCopyStatusForCurrentState === "failed"
        ? "复制失败，请手动选择空日期排查信息"
        : "";

  const emptyPositionCopyStateKey = [
    `report_date:${result?.report_date ?? (reportDate || "missing")}`,
    `bond_count:${result?.bond_count ?? "missing"}`,
    `quality_flag:${result?.quality_flag ?? tensorMeta?.quality_flag ?? "missing"}`,
    `trace_id:${tensorMeta?.trace_id ?? "missing"}`,
    `meta_quality_flag:${tensorMeta?.quality_flag ?? "missing"}`,
    `evidence_rows:${typeof tensorMeta?.evidence_rows === "number" ? tensorMeta.evidence_rows : "missing"}`,
    `tables_used:${metadataTablesUsed || "missing"}`,
    `filters_applied:${metadataFiltersApplied || "missing"}`,
  ].join("|");

  const emptyPositionCopyText = [
    "风险张量空持仓排查信息",
    `报告日 ${result?.report_date ?? (reportDate || "未选择")}`,
    `trace_id ${tensorMeta?.trace_id ?? "未提供"}`,
    `bond_count ${result?.bond_count ?? "未提供"}`,
    `quality_flag ${result?.quality_flag ?? tensorMeta?.quality_flag ?? "未提供"}`,
    `evidence_rows ${typeof tensorMeta?.evidence_rows === "number" ? tensorMeta.evidence_rows : "未提供"}`,
    `tables_used ${metadataTablesUsed || "未提供"}`,
    `filters_applied ${metadataFiltersApplied || "未提供"}`,
    "页面不会在前端补算正式指标",
    "请核对持仓快照、风险张量物化任务和元数据证据",
  ].join("\n");

  const emptyPositionCopyStatusForCurrentState =
    emptyPositionCopiedStateKey === emptyPositionCopyStateKey ? emptyPositionCopyStatus : "idle";

  const emptyPositionCopyMessage =
    emptyPositionCopyStatusForCurrentState === "copied"
      ? "已复制空持仓排查信息"
      : emptyPositionCopyStatusForCurrentState === "failed"
        ? "复制失败，请手动选择空持仓排查信息"
        : "";

  useEffect(() => {
    setTensorErrorCopyStatus("idle");
    setTensorErrorCopiedStateKey("");
  }, [tensorErrorCopyStateKey]);

  useEffect(() => {
    setBlockedDateCopyStatus("idle");
    setBlockedDateCopiedStateKey("");
  }, [blockedDateCopyStateKey]);

  useEffect(() => {
    setDatesErrorCopyStatus("idle");
    setDatesErrorCopiedStateKey("");
  }, [datesErrorCopyStateKey]);

  useEffect(() => {
    setDatesEmptyCopyStatus("idle");
    setDatesEmptyCopiedStateKey("");
  }, [datesEmptyCopyStateKey]);

  useEffect(() => {
    emptyPositionCopyStateKeyRef.current = emptyPositionCopyStateKey;
    setEmptyPositionCopyStatus("idle");
    setEmptyPositionCopiedStateKey("");
  }, [emptyPositionCopyStateKey]);

  const handleCopyTensorError = () => {
    const copiedStateKey = tensorErrorCopyStateKey;
    tensorErrorCopyRequestKeyRef.current = copiedStateKey;
    if (!navigator.clipboard?.writeText) {
      setTensorErrorCopiedStateKey(copiedStateKey);
      setTensorErrorCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(tensorErrorCopyText)
      .then(() => {
        if (tensorErrorCopyRequestKeyRef.current !== copiedStateKey) {
          return;
        }
        setTensorErrorCopiedStateKey(copiedStateKey);
        setTensorErrorCopyStatus("copied");
      })
      .catch(() => {
        if (tensorErrorCopyRequestKeyRef.current !== copiedStateKey) {
          return;
        }
        setTensorErrorCopiedStateKey(copiedStateKey);
        setTensorErrorCopyStatus("failed");
      });
  };

  const handleCopyBlockedDate = () => {
    const copiedStateKey = blockedDateCopyStateKey;
    blockedDateCopyRequestKeyRef.current = copiedStateKey;
    if (!navigator.clipboard?.writeText) {
      setBlockedDateCopiedStateKey(copiedStateKey);
      setBlockedDateCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(blockedDateCopyText)
      .then(() => {
        if (blockedDateCopyRequestKeyRef.current !== copiedStateKey) {
          return;
        }
        setBlockedDateCopiedStateKey(copiedStateKey);
        setBlockedDateCopyStatus("copied");
      })
      .catch(() => {
        if (blockedDateCopyRequestKeyRef.current !== copiedStateKey) {
          return;
        }
        setBlockedDateCopiedStateKey(copiedStateKey);
        setBlockedDateCopyStatus("failed");
      });
  };

  const clearDatesGovernanceCopyFeedback = () => {
    setBlockedDateCopyStatus("idle");
    setBlockedDateCopiedStateKey("");
    blockedDateCopyRequestKeyRef.current = "";
    setDatesErrorCopyStatus("idle");
    setDatesErrorCopiedStateKey("");
    datesErrorCopyRequestKeyRef.current = "";
    setDatesEmptyCopyStatus("idle");
    setDatesEmptyCopiedStateKey("");
    datesEmptyCopyRequestKeyRef.current = "";
  };

  const handleRetryDatesGovernance = () => {
    clearDatesGovernanceCopyFeedback();
    void datesQuery.refetch();
  };

  const handleRetryTensorMainRead = () => {
    setTensorErrorCopyStatus("idle");
    setTensorErrorCopiedStateKey("");
    tensorErrorCopyRequestKeyRef.current = "";
    void tensorQuery.refetch();
  };

  const handleCopyDatesError = () => {
    const copiedStateKey = datesErrorCopyStateKey;
    datesErrorCopyRequestKeyRef.current = copiedStateKey;
    if (!navigator.clipboard?.writeText) {
      setDatesErrorCopiedStateKey(copiedStateKey);
      setDatesErrorCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(datesErrorCopyText)
      .then(() => {
        if (datesErrorCopyRequestKeyRef.current !== copiedStateKey) {
          return;
        }
        setDatesErrorCopiedStateKey(copiedStateKey);
        setDatesErrorCopyStatus("copied");
      })
      .catch(() => {
        if (datesErrorCopyRequestKeyRef.current !== copiedStateKey) {
          return;
        }
        setDatesErrorCopiedStateKey(copiedStateKey);
        setDatesErrorCopyStatus("failed");
      });
  };

  const handleCopyDatesEmpty = () => {
    const copiedStateKey = datesEmptyCopyStateKey;
    datesEmptyCopyRequestKeyRef.current = copiedStateKey;
    if (!navigator.clipboard?.writeText) {
      setDatesEmptyCopiedStateKey(copiedStateKey);
      setDatesEmptyCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(datesEmptyCopyText)
      .then(() => {
        if (datesEmptyCopyRequestKeyRef.current !== copiedStateKey) {
          return;
        }
        setDatesEmptyCopiedStateKey(copiedStateKey);
        setDatesEmptyCopyStatus("copied");
      })
      .catch(() => {
        if (datesEmptyCopyRequestKeyRef.current !== copiedStateKey) {
          return;
        }
        setDatesEmptyCopiedStateKey(copiedStateKey);
        setDatesEmptyCopyStatus("failed");
      });
  };

  const handleCopyEmptyPosition = () => {
    const copiedStateKey = emptyPositionCopyStateKey;
    emptyPositionCopyStateKeyRef.current = copiedStateKey;
    if (!navigator.clipboard?.writeText) {
      setEmptyPositionCopiedStateKey(copiedStateKey);
      setEmptyPositionCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(emptyPositionCopyText)
      .then(() => {
        if (emptyPositionCopyStateKeyRef.current !== copiedStateKey) {
          return;
        }
        setEmptyPositionCopiedStateKey(copiedStateKey);
        setEmptyPositionCopyStatus("copied");
      })
      .catch(() => {
        if (emptyPositionCopyStateKeyRef.current !== copiedStateKey) {
          return;
        }
        setEmptyPositionCopiedStateKey(copiedStateKey);
        setEmptyPositionCopyStatus("failed");
      });
  };

  return {
    tensorErrorCopyText,
    tensorErrorCopyStatusForCurrentState,
    tensorErrorCopyMessage,
    blockedDateCopyText,
    blockedDateCopyStatusForCurrentState,
    blockedDateCopyMessage,
    datesErrorCopyText,
    datesErrorCopyStatusForCurrentState,
    datesErrorCopyMessage,
    datesEmptyCopyText,
    datesEmptyCopyStatusForCurrentState,
    datesEmptyCopyMessage,
    emptyPositionCopyText,
    emptyPositionCopyStatusForCurrentState,
    emptyPositionCopyMessage,
    handleCopyTensorError,
    handleCopyBlockedDate,
    handleRetryDatesGovernance,
    handleRetryTensorMainRead,
    handleCopyDatesError,
    handleCopyDatesEmpty,
    handleCopyEmptyPosition,
  };
}
