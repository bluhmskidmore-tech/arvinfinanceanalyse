import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { RiskTensorQualityEvidenceInput } from "./riskTensorEvidenceModel";
import { useRiskTensorQualityEvidence } from "./useRiskTensorQualityEvidence";

const copyChannels = [
  {
    name: "evidence",
    copy: "handleCopyQualityEvidence",
    feedback: "qualityEvidenceCopyMessage",
    success: "已复制证据摘要",
    failure: "复制失败，请手动选择证据",
  },
  {
    name: "evidence request",
    copy: "handleCopyQualityEvidenceRequest",
    feedback: "qualityEvidenceRequestCopyMessage",
    success: "已复制补证请求",
    failure: "复制失败，请手动选择补证请求",
  },
  {
    name: "payload request",
    copy: "handleCopyPayloadQualityRequest",
    feedback: "payloadQualityRequestCopyMessage",
    success: "已复制字段补证请求",
    failure: "复制失败，请手动选择字段补证请求",
  },
  {
    name: "combined request",
    copy: "handleCopyCombinedQualityRequest",
    feedback: "combinedQualityRequestCopyMessage",
    success: "已复制完整补证包",
    failure: "复制失败，请手动选择完整补证包",
  },
  {
    name: "warnings",
    copy: "handleCopyQualityWarnings",
    feedback: "qualityWarningsCopyMessage",
    success: "已复制预警清单",
    failure: "复制失败，请手动选择预警清单",
  },
  {
    name: "review record",
    copy: "handleCopyQualityEvidenceReviewRecord",
    feedback: "qualityEvidenceReviewRecordCopyMessage",
    success: "已复制确认记录",
    failure: "复制失败，请手动选择确认记录",
  },
] as const;

function evidenceInput(reportDate: string): RiskTensorQualityEvidenceInput {
  return {
    reportDate,
    result: undefined,
    blockedReportDates: [],
    highlightedBlockedReportDate: undefined,
    tensorMeta: {
      trace_id: `trace-${reportDate}`,
      basis: "formal",
      result_kind: "risk.tensor",
      formal_use_allowed: true,
      source_version: "source-test",
      vendor_version: "vendor-test",
      rule_version: "rule-test",
      cache_version: "cache-test",
      quality_flag: "warning",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-04-12T08:00:00Z",
      evidence_rows: 1,
      tables_used: ["risk_tensor_daily"],
      filters_applied: { report_date: reportDate },
    },
  };
}

function deferredCopy() {
  let resolve!: () => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<void>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function settleCopy(copy: ReturnType<typeof deferredCopy>, outcome: "success" | "failure") {
  await act(async () => {
    if (outcome === "success") copy.resolve();
    else copy.reject(new Error("clipboard denied"));
    await copy.promise.catch(() => undefined);
  });
}

describe("quality evidence latest copy feedback", () => {
  describe.each(copyChannels)("$name", (channel) => {
    it.each(["success", "failure"] as const)(
      "preserves new report-date success when an older copy finishes with %s",
      async (oldOutcome) => {
        const first = deferredCopy();
        const second = deferredCopy();
        const writeText = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
        const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
        Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

        try {
          const { result, rerender } = renderHook(useRiskTensorQualityEvidence, {
            initialProps: evidenceInput("2026-02-28"),
          });
          act(() => result.current[channel.copy]());
          rerender(evidenceInput("2026-01-31"));
          act(() => result.current[channel.copy]());
          expect(writeText).toHaveBeenCalledTimes(2);
          expect(writeText.mock.calls[0]?.[0]).toContain("报告日 2026-02-28");
          expect(writeText.mock.calls[1]?.[0]).toContain("报告日 2026-01-31");

          await settleCopy(second, "success");
          expect(result.current[channel.feedback]).toBe(channel.success);
          await settleCopy(first, oldOutcome);
          expect(result.current[channel.feedback]).toBe(channel.success);
        } finally {
          if (originalClipboard) Object.defineProperty(navigator, "clipboard", originalClipboard);
          else Reflect.deleteProperty(navigator, "clipboard");
        }
      },
    );

    it.each(["success", "failure"] as const)(
      "preserves the latest same-state copy result when an earlier copy finishes with %s",
      async (oldOutcome) => {
        const first = deferredCopy();
        const second = deferredCopy();
        const writeText = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
        const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
        Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

        try {
          const { result } = renderHook(useRiskTensorQualityEvidence, {
            initialProps: evidenceInput("2026-02-28"),
          });
          act(() => result.current[channel.copy]());
          act(() => result.current[channel.copy]());
          expect(writeText).toHaveBeenCalledTimes(2);
          expect(writeText.mock.calls[0]?.[0]).toBe(writeText.mock.calls[1]?.[0]);

          const latestOutcome = oldOutcome === "success" ? "failure" : "success";
          const latestFeedback = latestOutcome === "success" ? channel.success : channel.failure;
          await settleCopy(second, latestOutcome);
          expect(result.current[channel.feedback]).toBe(latestFeedback);
          await settleCopy(first, oldOutcome);
          expect(result.current[channel.feedback]).toBe(latestFeedback);
        } finally {
          if (originalClipboard) Object.defineProperty(navigator, "clipboard", originalClipboard);
          else Reflect.deleteProperty(navigator, "clipboard");
        }
      },
    );
  });
});
