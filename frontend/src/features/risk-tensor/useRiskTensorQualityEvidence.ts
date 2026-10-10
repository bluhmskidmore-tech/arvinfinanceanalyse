import { useEffect, useRef, useState } from "react";
import {
  buildRiskTensorQualityCopyTexts,
  buildRiskTensorQualityEvidence,
  type RiskTensorQualityEvidenceInput,
} from "./riskTensorEvidenceModel";

type QualityCopyChannel = "evidence" | "evidenceRequest" | "payloadRequest" | "combinedRequest" | "warnings" | "reviewRecord";

export function useRiskTensorQualityEvidence(input: RiskTensorQualityEvidenceInput) {
  const [qualityEvidenceCopyStatus, setQualityEvidenceCopyStatus] = useState<"idle" | "copied" | "failed">("idle");

  const [qualityEvidenceCopiedStateKey, setQualityEvidenceCopiedStateKey] = useState("");

  const [qualityEvidenceReviewConfirmed, setQualityEvidenceReviewConfirmed] = useState(false);

  const [qualityEvidenceReviewRecordCopyStatus, setQualityEvidenceReviewRecordCopyStatus] = useState<
    "idle" | "copied" | "failed"
  >("idle");

  const [qualityEvidenceReviewRecordCopiedStateKey, setQualityEvidenceReviewRecordCopiedStateKey] = useState("");

  const [qualityEvidenceRequestCopyStatus, setQualityEvidenceRequestCopyStatus] = useState<"idle" | "copied" | "failed">(
    "idle",
  );

  const [qualityEvidenceRequestCopiedStateKey, setQualityEvidenceRequestCopiedStateKey] = useState("");

  const [payloadQualityRequestCopyStatus, setPayloadQualityRequestCopyStatus] = useState<"idle" | "copied" | "failed">(
    "idle",
  );

  const [payloadQualityRequestCopiedStateKey, setPayloadQualityRequestCopiedStateKey] = useState("");

  const [combinedQualityRequestCopyStatus, setCombinedQualityRequestCopyStatus] = useState<
    "idle" | "copied" | "failed"
  >("idle");

  const [combinedQualityRequestCopiedStateKey, setCombinedQualityRequestCopiedStateKey] = useState("");

  const [qualityWarningsCopyStatus, setQualityWarningsCopyStatus] = useState<"idle" | "copied" | "failed">("idle");

  const [qualityWarningsCopiedStateKey, setQualityWarningsCopiedStateKey] = useState("");

  const evidence = buildRiskTensorQualityEvidence(input);
  const { qualityStateKey, hasMissingQualityEvidence } = evidence;
  const qualityCopyRequestsRef = useRef<{
    stateKey: string;
    sequences: Partial<Record<QualityCopyChannel, number>>;
  }>({ stateKey: qualityStateKey, sequences: {} });

  useEffect(() => {
    // A fresh context also invalidates requests if the page later returns to the same evidence key.
    qualityCopyRequestsRef.current = { stateKey: qualityStateKey, sequences: {} };
    setQualityEvidenceCopyStatus("idle");
    setQualityEvidenceCopiedStateKey("");
  }, [qualityStateKey]);

  useEffect(() => {
    setQualityEvidenceReviewConfirmed(false);
    setQualityEvidenceReviewRecordCopyStatus("idle");
    setQualityEvidenceReviewRecordCopiedStateKey("");
    setQualityEvidenceRequestCopyStatus("idle");
    setQualityEvidenceRequestCopiedStateKey("");
    setPayloadQualityRequestCopyStatus("idle");
    setPayloadQualityRequestCopiedStateKey("");
    setCombinedQualityRequestCopyStatus("idle");
    setCombinedQualityRequestCopiedStateKey("");
    setQualityWarningsCopyStatus("idle");
    setQualityWarningsCopiedStateKey("");
  }, [qualityStateKey]);

  const qualityEvidenceCopyStatusForCurrentState =
    qualityEvidenceCopiedStateKey === qualityStateKey ? qualityEvidenceCopyStatus : "idle";

  const canConfirmQualityEvidenceReview =
    !hasMissingQualityEvidence &&
    qualityEvidenceCopyStatusForCurrentState === "copied" &&
    !qualityEvidenceReviewConfirmed;

  const qualityReviewStateLabel =
    hasMissingQualityEvidence
      ? "证据不完整，待补证"
      : qualityEvidenceReviewConfirmed
        ? "业务已确认"
      : qualityEvidenceCopyStatusForCurrentState === "copied"
        ? "证据已复制，待业务确认"
        : qualityEvidenceCopyStatusForCurrentState === "failed"
          ? "复制失败，需手动选择证据"
          : "待复核";


  const texts = buildRiskTensorQualityCopyTexts(evidence, qualityReviewStateLabel);
  const { qualityTraceCopyText, qualityEvidenceRequestCopyText, payloadQualityRequestCopyText, combinedQualityRequestCopyText, qualityWarningsCopyText, qualityEvidenceReviewRecordCopyText } = texts;
  const qualityEvidenceCopyMessage =
    qualityEvidenceCopyStatusForCurrentState === "copied"
      ? "已复制证据摘要"
      : qualityEvidenceCopyStatusForCurrentState === "failed"
        ? "复制失败，请手动选择证据"
        : "";

  const qualityEvidenceRequestCopyStatusForCurrentState =
    qualityEvidenceRequestCopiedStateKey === qualityStateKey ? qualityEvidenceRequestCopyStatus : "idle";

  const qualityEvidenceRequestCopyMessage =
    qualityEvidenceRequestCopyStatusForCurrentState === "copied"
      ? "已复制补证请求"
      : qualityEvidenceRequestCopyStatusForCurrentState === "failed"
        ? "复制失败，请手动选择补证请求"
        : "";

  const qualityEvidenceReviewRecordCopyMessage =
    qualityEvidenceReviewRecordCopiedStateKey === qualityStateKey && qualityEvidenceReviewRecordCopyStatus === "copied"
      ? "已复制确认记录"
      : qualityEvidenceReviewRecordCopiedStateKey === qualityStateKey &&
          qualityEvidenceReviewRecordCopyStatus === "failed"
        ? "复制失败，请手动选择确认记录"
        : "";

  const payloadQualityRequestCopyStatusForCurrentState =
    payloadQualityRequestCopiedStateKey === qualityStateKey ? payloadQualityRequestCopyStatus : "idle";

  const payloadQualityRequestCopyMessage =
    payloadQualityRequestCopyStatusForCurrentState === "copied"
      ? "已复制字段补证请求"
      : payloadQualityRequestCopyStatusForCurrentState === "failed"
        ? "复制失败，请手动选择字段补证请求"
        : "";

  const combinedQualityRequestCopyStatusForCurrentState =
    combinedQualityRequestCopiedStateKey === qualityStateKey ? combinedQualityRequestCopyStatus : "idle";

  const combinedQualityRequestCopyMessage =
    combinedQualityRequestCopyStatusForCurrentState === "copied"
      ? "已复制完整补证包"
      : combinedQualityRequestCopyStatusForCurrentState === "failed"
        ? "复制失败，请手动选择完整补证包"
        : "";

  const qualityWarningsCopyMessage =
    qualityWarningsCopiedStateKey === qualityStateKey && qualityWarningsCopyStatus === "copied"
      ? "已复制预警清单"
      : qualityWarningsCopiedStateKey === qualityStateKey && qualityWarningsCopyStatus === "failed"
        ? "复制失败，请手动选择预警清单"
        : "";

  const beginQualityCopy = (channel: QualityCopyChannel) => {
    const context = qualityCopyRequestsRef.current;
    const sequence = (context.sequences[channel] ?? 0) + 1;
    context.sequences[channel] = sequence;
    return () =>
      qualityCopyRequestsRef.current === context &&
      context.stateKey === qualityStateKey &&
      context.sequences[channel] === sequence;
  };

  const handleCopyQualityEvidence = () => {
    const copiedStateKey = qualityStateKey;
    const isCurrentCopy = beginQualityCopy("evidence");
    if (!navigator.clipboard?.writeText) {
      setQualityEvidenceCopiedStateKey(copiedStateKey);
      setQualityEvidenceCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(qualityTraceCopyText)
      .then(() => {
        if (!isCurrentCopy()) return;
        setQualityEvidenceCopiedStateKey(copiedStateKey);
        setQualityEvidenceCopyStatus("copied");
      })
      .catch(() => {
        if (!isCurrentCopy()) return;
        setQualityEvidenceCopiedStateKey(copiedStateKey);
        setQualityEvidenceCopyStatus("failed");
      });
  };

  const handleCopyQualityEvidenceRequest = () => {
    const copiedStateKey = qualityStateKey;
    const isCurrentCopy = beginQualityCopy("evidenceRequest");
    if (!navigator.clipboard?.writeText) {
      setQualityEvidenceRequestCopiedStateKey(copiedStateKey);
      setQualityEvidenceRequestCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(qualityEvidenceRequestCopyText)
      .then(() => {
        if (!isCurrentCopy()) return;
        setQualityEvidenceRequestCopiedStateKey(copiedStateKey);
        setQualityEvidenceRequestCopyStatus("copied");
      })
      .catch(() => {
        if (!isCurrentCopy()) return;
        setQualityEvidenceRequestCopiedStateKey(copiedStateKey);
        setQualityEvidenceRequestCopyStatus("failed");
      });
  };

  const handleCopyPayloadQualityRequest = () => {
    const copiedStateKey = qualityStateKey;
    const isCurrentCopy = beginQualityCopy("payloadRequest");
    if (!navigator.clipboard?.writeText) {
      setPayloadQualityRequestCopiedStateKey(copiedStateKey);
      setPayloadQualityRequestCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(payloadQualityRequestCopyText)
      .then(() => {
        if (!isCurrentCopy()) return;
        setPayloadQualityRequestCopiedStateKey(copiedStateKey);
        setPayloadQualityRequestCopyStatus("copied");
      })
      .catch(() => {
        if (!isCurrentCopy()) return;
        setPayloadQualityRequestCopiedStateKey(copiedStateKey);
        setPayloadQualityRequestCopyStatus("failed");
      });
  };

  const handleCopyCombinedQualityRequest = () => {
    const copiedStateKey = qualityStateKey;
    const isCurrentCopy = beginQualityCopy("combinedRequest");
    if (!navigator.clipboard?.writeText) {
      setCombinedQualityRequestCopiedStateKey(copiedStateKey);
      setCombinedQualityRequestCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(combinedQualityRequestCopyText)
      .then(() => {
        if (!isCurrentCopy()) return;
        setCombinedQualityRequestCopiedStateKey(copiedStateKey);
        setCombinedQualityRequestCopyStatus("copied");
      })
      .catch(() => {
        if (!isCurrentCopy()) return;
        setCombinedQualityRequestCopiedStateKey(copiedStateKey);
        setCombinedQualityRequestCopyStatus("failed");
      });
  };

  const handleCopyQualityWarnings = () => {
    const copiedStateKey = qualityStateKey;
    const isCurrentCopy = beginQualityCopy("warnings");
    if (!navigator.clipboard?.writeText) {
      setQualityWarningsCopiedStateKey(copiedStateKey);
      setQualityWarningsCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(qualityWarningsCopyText)
      .then(() => {
        if (!isCurrentCopy()) return;
        setQualityWarningsCopiedStateKey(copiedStateKey);
        setQualityWarningsCopyStatus("copied");
      })
      .catch(() => {
        if (!isCurrentCopy()) return;
        setQualityWarningsCopiedStateKey(copiedStateKey);
        setQualityWarningsCopyStatus("failed");
      });
  };

  const handleConfirmQualityEvidenceReview = () => {
    setQualityEvidenceReviewConfirmed(true);
  };

  const handleCopyQualityEvidenceReviewRecord = () => {
    const copiedStateKey = qualityStateKey;
    const isCurrentCopy = beginQualityCopy("reviewRecord");
    if (!navigator.clipboard?.writeText) {
      setQualityEvidenceReviewRecordCopiedStateKey(copiedStateKey);
      setQualityEvidenceReviewRecordCopyStatus("failed");
      return;
    }
    void navigator.clipboard
      .writeText(qualityEvidenceReviewRecordCopyText)
      .then(() => {
        if (!isCurrentCopy()) return;
        setQualityEvidenceReviewRecordCopiedStateKey(copiedStateKey);
        setQualityEvidenceReviewRecordCopyStatus("copied");
      })
      .catch(() => {
        if (!isCurrentCopy()) return;
        setQualityEvidenceReviewRecordCopiedStateKey(copiedStateKey);
        setQualityEvidenceReviewRecordCopyStatus("failed");
      });
  };

  return {
    ...evidence,
    ...texts,
    qualityEvidenceReviewConfirmed,
    qualityEvidenceReviewRecordCopiedStateKey,
    qualityEvidenceReviewRecordCopyStatus,
    qualityWarningsCopiedStateKey,
    qualityWarningsCopyStatus,
    qualityEvidenceCopyStatusForCurrentState,
    canConfirmQualityEvidenceReview,
    qualityReviewStateLabel,
    qualityEvidenceCopyMessage,
    qualityEvidenceRequestCopyStatusForCurrentState,
    qualityEvidenceRequestCopyMessage,
    qualityEvidenceReviewRecordCopyMessage,
    payloadQualityRequestCopyStatusForCurrentState,
    payloadQualityRequestCopyMessage,
    combinedQualityRequestCopyStatusForCurrentState,
    combinedQualityRequestCopyMessage,
    qualityWarningsCopyMessage,
    handleCopyQualityEvidence,
    handleCopyQualityEvidenceRequest,
    handleCopyPayloadQualityRequest,
    handleCopyCombinedQualityRequest,
    handleCopyQualityWarnings,
    handleConfirmQualityEvidenceReview,
    handleCopyQualityEvidenceReviewRecord,
  };
}
