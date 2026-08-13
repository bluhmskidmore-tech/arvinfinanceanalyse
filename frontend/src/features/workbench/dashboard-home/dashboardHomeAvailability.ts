import type { ResultMeta } from "../../../api/contracts";
import type {
  HomeGovernanceStatusKind,
  HomeReportDateContext,
} from "./dashboardHomeFirstScreenTypes";

import { EM_DASH } from "../../../utils/format";
export type DashboardHomeAvailabilityKind =
  | "available"
  | "partial"
  | "fallback"
  | "stale"
  | "error";

export type DashboardHomeAvailabilityFailureKind =
  | "permission"
  | "requestFailed";

export type DashboardHomeSnapshotFailureCopy = {
  kind: DashboardHomeAvailabilityFailureKind;
  label: string;
  reason: string;
  recovery: string;
};

export type DashboardHomeAvailability = {
  kind: DashboardHomeAvailabilityKind;
  failureKind: DashboardHomeAvailabilityFailureKind | null;
  label: string;
  title: string;
  reason: string;
  impact: string;
  technicalDetail: string | null;
  requestedReportDate: string;
  actualReportDate: string;
  generatedAt: string | null;
  hasResolvedReportDate: boolean;
};

type BuildDashboardHomeAvailabilityInput = {
  dataStatusKind: HomeGovernanceStatusKind;
  dataSyncPrefix: string;
  reportDateContext: HomeReportDateContext;
  snapshotMeta: ResultMeta | null;
  snapshotErrorDetail?: string | null;
  snapshotRetryingAfterError?: boolean;
  missingDomainLabels?: readonly string[];
};

const SNAPSHOT_PERMISSION_PATTERN =
  /(?:not allowed to read|forbidden|permission|status(?:\s+code)?\s*[:=]?\s*403|\b403\b)/i;
const ISO_REPORT_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

function cleanOptionalText(value: string | null | undefined): string {
  const normalized = value?.trim() ?? "";
  return normalized && normalized !== EM_DASH ? normalized : "";
}

export function dashboardHomeSnapshotFailureCopy(
  detail: string | null | undefined,
): DashboardHomeSnapshotFailureCopy {
  const normalizedDetail = cleanOptionalText(detail);
  if (SNAPSHOT_PERMISSION_PATTERN.test(normalizedDetail)) {
    return {
      kind: "permission",
      label: "首页快照权限不足",
      reason: "当前账号缺少 executive 读取权限",
      recovery: "联系管理员开通 executive 读取权限后重试",
    };
  }
  return {
    kind: "requestFailed",
    label: "首页快照读取失败",
    reason: "主快照请求未完成，暂未取得可用于判断的数据",
    recovery: "重试主快照；若持续失败，再核对请求链路",
  };
}

function availabilityKind(
  status: HomeGovernanceStatusKind,
  snapshotRetryingAfterError: boolean,
): DashboardHomeAvailabilityKind {
  if (snapshotRetryingAfterError) return "error";
  if (status === "partial") return "partial";
  if (status === "fallback") return "fallback";
  if (status === "stale") return "stale";
  if (status === "error") return "error";
  return "available";
}

export function buildDashboardHomeAvailability(
  input: BuildDashboardHomeAvailabilityInput,
): DashboardHomeAvailability {
  const requestedReportDate = cleanOptionalText(
    input.reportDateContext.requestedDate,
  );
  const actualReportDate = cleanOptionalText(
    input.reportDateContext.actualDataDate,
  );
  const hasReportDateDivergence =
    requestedReportDate.length > 0 &&
    actualReportDate.length > 0 &&
    requestedReportDate !== actualReportDate;
  const kind = availabilityKind(
    input.dataStatusKind,
    input.snapshotRetryingAfterError === true,
  );
  const generatedAt =
    cleanOptionalText(
      input.reportDateContext.generatedAt || input.snapshotMeta?.generated_at,
    ) || null;
  const hasResolvedReportDate =
    ISO_REPORT_DATE_PATTERN.test(actualReportDate);
  const technicalDetail =
    cleanOptionalText(input.snapshotErrorDetail) || null;

  if (kind === "error") {
    const failure = dashboardHomeSnapshotFailureCopy(technicalDetail);
    return {
      kind,
      failureKind: failure.kind,
      label: failure.label,
      title: `${failure.label}，模块保持可见`,
      reason: failure.reason,
      impact:
        "今日判断、治理状态与核心 KPI 无法由主快照闭合；下方模块保留，并按各自接口实况展示。",
      technicalDetail,
      requestedReportDate,
      actualReportDate,
      generatedAt,
      hasResolvedReportDate,
    };
  }

  if (kind === "stale") {
    return {
      kind,
      failureKind: null,
      label: "展示上一版本",
      title: hasReportDateDivergence
        ? "新报告日读取失败，当前展示上一版本"
        : "主快照刷新失败，当前展示上一版本",
      reason:
        hasReportDateDivergence
          ? cleanOptionalText(input.reportDateContext.divergenceReason) ||
            "新报告日数据获取失败，当前沿用上一版本快照"
          : "主快照刷新未完成，当前沿用上一版本快照",
      impact:
        hasReportDateDivergence
          ? "页面读数仍对应实际快照日；用于今日判断前，需先复核请求日与实际数据日差异。"
          : "页面读数仍对应实际快照日，但不是本次刷新后的新版本；正式使用前需复核。",
      technicalDetail,
      requestedReportDate,
      actualReportDate,
      generatedAt,
      hasResolvedReportDate,
    };
  }

  if (kind === "fallback") {
    return {
      kind,
      failureKind: null,
      label: "回退快照",
      title: "首页使用回退快照，正式使用前需复核",
      reason:
        cleanOptionalText(input.reportDateContext.divergenceReason) ||
        "请求日未取得严格匹配快照，当前展示最近可用快照",
      impact:
        "核心指标与结论对应实际快照日，不应按请求日报告日直接解释。",
      technicalDetail,
      requestedReportDate,
      actualReportDate,
      generatedAt,
      hasResolvedReportDate,
    };
  }

  if (kind === "partial") {
    const missingDomains = (input.missingDomainLabels ?? [])
      .map((label) => label.trim())
      .filter(Boolean);
    return {
      kind,
      failureKind: null,
      label: "部分可用",
      title: "主快照部分可用，缺口模块需复核",
      reason:
        missingDomains.length > 0
          ? `缺失数据域：${missingDomains.join("、")}`
          : cleanOptionalText(input.dataSyncPrefix) ||
            "主快照存在未闭合的数据质量项",
      impact:
        "已落地模块可继续核对；缺口模块及受其影响的结论不可直接用于正式决策。",
      technicalDetail,
      requestedReportDate,
      actualReportDate,
      generatedAt,
      hasResolvedReportDate,
    };
  }

  return {
    kind,
    failureKind: null,
    label: "数据可用",
    title: "首页主快照可用",
    reason: cleanOptionalText(input.dataSyncPrefix) || "主快照已取得",
    impact: "核心指标与结论按受管快照口径展示。",
    technicalDetail,
    requestedReportDate,
    actualReportDate,
    generatedAt,
    hasResolvedReportDate,
  };
}
