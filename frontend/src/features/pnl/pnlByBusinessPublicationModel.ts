import { type ApiClient } from "../../api/client";
import { type PnlByBusinessPrecomputeStatus } from "../../api/contracts";

export type PnlByBusinessInsightsEnvelope = Awaited<
  ReturnType<ApiClient["getPnlByBusinessInsights"]>
>;
export function usesPnlByBusinessReadinessProtocol(
  status: PnlByBusinessPrecomputeStatus | undefined,
): boolean {
  return status?.readiness !== undefined;
}

export function resolveApprovedPnlByBusinessInsightsEnvelope({
  envelope,
  insightsQuerySucceeded,
  legacyReadAllowed,
  precomputeStatusQuerySucceeded,
  publishedGeneration,
  publishedReadAllowed,
  selectedReportDate,
  usesReadinessProtocol,
}: {
  envelope: PnlByBusinessInsightsEnvelope | undefined;
  insightsQuerySucceeded: boolean;
  legacyReadAllowed: boolean;
  precomputeStatusQuerySucceeded: boolean;
  publishedGeneration: string | null;
  publishedReadAllowed: boolean;
  selectedReportDate: string;
  usesReadinessProtocol: boolean;
}): PnlByBusinessInsightsEnvelope | undefined {
  if (
    !precomputeStatusQuerySucceeded ||
    !insightsQuerySucceeded ||
    !envelope ||
    (!legacyReadAllowed && !publishedReadAllowed)
  ) {
    return undefined;
  }
  if (
    envelope.result_meta.requested_report_date !== selectedReportDate ||
    envelope.result_meta.resolved_report_date !== selectedReportDate
  ) {
    return undefined;
  }
  if (
    usesReadinessProtocol &&
    (!publishedGeneration || envelope.result.generation !== publishedGeneration)
  ) {
    return undefined;
  }
  return envelope;
}
