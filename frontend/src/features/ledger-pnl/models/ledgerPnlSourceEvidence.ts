import type { QdbGlMonthlyAnalysisWorkbookPayload, ResultMeta } from "../../../api/contracts";

export function metaString(value: unknown) {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
}

export function formatMetaQuality(meta: ResultMeta | null | undefined) {
  const labels: Record<string, string> = {
    ok: "正常",
    warning: "预警",
    error: "错误",
    stale: "陈旧",
    missing: "缺失",
  };
  const value = metaString(meta?.quality_flag);
  return value ? (labels[value] ?? value) : "缺失";
}

export function collectSourceRiskSegments(label: string, meta: ResultMeta | null | undefined) {
  const segments: string[] = [];
  const fallbackMode = metaString(meta?.fallback_mode);
  const vendorStatus = metaString(meta?.vendor_status);
  const scenarioFlag = meta?.scenario_flag === true;
  if (fallbackMode && fallbackMode !== "none") {
    segments.push(`${label} fallback=${fallbackMode}`);
  }
  if (vendorStatus && vendorStatus !== "ok") {
    segments.push(`${label} vendor=${vendorStatus}`);
  }
  if (scenarioFlag) {
    segments.push(`${label} scenario=true`);
  }
  return segments;
}

export function missingSourceEvidenceFields(label: string, meta: ResultMeta | null | undefined) {
  if (!meta) {
    return [];
  }
  const fields = [
    metaString(meta.source_version) ? null : `${label} source_version 缺失`,
    metaString(meta.rule_version) ? null : `${label} rule_version 缺失`,
    metaString(meta.cache_version) ? null : `${label} cache_version 缺失`,
    (meta.tables_used?.length ?? 0) > 0 ? null : `${label} tables_used 缺失`,
  ];
  return fields.filter((field): field is string => Boolean(field));
}

type MonthlyWorkbookAuditState = {
  status: string;
  action: string;
  blockingDetail: string | null;
  isTrusted: boolean;
};

export function monthlyWorkbookAuditState(props: {
  requestedReportMonth: string;
  hasMatchingAnalysisMonth: boolean;
  isMonthlyAnalysisDatesLoading: boolean;
  isMonthlyAnalysisDatesError: boolean;
  isMonthlyAnalysisWorkbookLoading: boolean;
  isMonthlyAnalysisWorkbookError: boolean;
  monthlyAnalysisWorkbook: QdbGlMonthlyAnalysisWorkbookPayload | undefined;
  monthlyAnalysisWorkbookMeta: ResultMeta | null | undefined;
}): MonthlyWorkbookAuditState {
  if (!props.requestedReportMonth) {
    return {
      status: "等待报告月份",
      action: "先选择报告日生成 report_month",
      blockingDetail: null,
      isTrusted: false,
    };
  }
  if (props.isMonthlyAnalysisDatesLoading) {
    return {
      status: "月度月份读取中",
      action: "等待月度分析月份读取完成",
      blockingDetail: null,
      isTrusted: false,
    };
  }
  if (props.isMonthlyAnalysisDatesError) {
    return {
      status: "月度月份读取失败",
      action: "恢复月度分析月份读取",
      blockingDetail: null,
      isTrusted: false,
    };
  }
  if (!props.hasMatchingAnalysisMonth) {
    return {
      status: `${props.requestedReportMonth} 无匹配`,
      action: `补齐 ${props.requestedReportMonth} QDB 月度分析工作簿`,
      blockingDetail: null,
      isTrusted: false,
    };
  }
  if (props.isMonthlyAnalysisWorkbookLoading) {
    return {
      status: "月度工作簿读取中",
      action: "等待月度工作簿读取完成",
      blockingDetail: null,
      isTrusted: false,
    };
  }
  if (props.isMonthlyAnalysisWorkbookError) {
    return {
      status: "月度工作簿读取失败",
      action: `重新读取 ${props.requestedReportMonth} 月度分析工作簿`,
      blockingDetail: null,
      isTrusted: false,
    };
  }
  if (!props.monthlyAnalysisWorkbook) {
    return {
      status: "月度工作簿未返回",
      action: `重新读取 ${props.requestedReportMonth} 月度分析工作簿`,
      blockingDetail: "月度工作簿 payload 缺失",
      isTrusted: false,
    };
  }

  const workbookReportMonth = metaString(props.monthlyAnalysisWorkbook.report_month);
  if (workbookReportMonth !== props.requestedReportMonth) {
    const returnedMonth = workbookReportMonth ?? "缺失";
    return {
      status: `${props.requestedReportMonth}/${returnedMonth} 不一致`,
      action: `重新读取 ${props.requestedReportMonth} 月度分析工作簿`,
      blockingDetail: `月度工作簿请求 ${props.requestedReportMonth}，返回 ${returnedMonth}`,
      isTrusted: false,
    };
  }

  if (!props.monthlyAnalysisWorkbookMeta) {
    return {
      status: "月度工作簿 result_meta 缺失",
      action: "补齐月度工作簿来源版本、规则版本、缓存版本和表清单",
      blockingDetail: "月度工作簿 result_meta 缺失",
      isTrusted: false,
    };
  }
  const missingFields = missingSourceEvidenceFields("月度工作簿", props.monthlyAnalysisWorkbookMeta);
  if (missingFields.length > 0) {
    const detail = missingFields.join("；");
    return {
      status: "月度工作簿来源证据不完整",
      action: "补齐月度工作簿来源版本、规则版本、缓存版本和表清单",
      blockingDetail: detail,
      isTrusted: false,
    };
  }

  return {
    status: `${props.requestedReportMonth} 已匹配`,
    action: "月度分析工作簿已匹配",
    blockingDetail: null,
    isTrusted: true,
  };
}

export function formatEvidenceRows(meta: ResultMeta | null | undefined) {
  return typeof meta?.evidence_rows === "number" ? String(meta.evidence_rows) : "缺失";
}
