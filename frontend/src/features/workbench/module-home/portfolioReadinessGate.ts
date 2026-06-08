import type { ResultMeta } from "../../../api/contracts";

export type PortfolioGateTone = "ok" | "watch" | "error" | "muted";

export type PortfolioEvidenceSource = {
  label: string;
  hasData: boolean;
  isError?: boolean;
  isLoading?: boolean;
  reportDate?: string;
  meta?: ResultMeta;
};

export type PortfolioRiskDatesEvidence = {
  hasData: boolean;
  isError?: boolean;
  isLoading?: boolean;
  dates: string[];
  meta?: ResultMeta;
};

export type PortfolioReadinessGate = {
  coreRender: boolean;
  decisionReady: boolean;
  riskClosureReady: boolean;
  tone: PortfolioGateTone;
  blockingReasons: string[];
  warningReasons: string[];
  sourceFacts: string[];
  sourceDates: string;
  riskClosureFact: string;
};

const META_REPORT_DATE_FIELDS = [
  "resolved_report_date",
  "as_of_date",
  "requested_report_date",
] as const;

function cleanMetaDate(value: ResultMeta[(typeof META_REPORT_DATE_FIELDS)[number]] | undefined) {
  return typeof value === "string" && value.trim() ? value : "";
}

function metaReportDate(meta: ResultMeta | undefined) {
  for (const field of META_REPORT_DATE_FIELDS) {
    const value = cleanMetaDate(meta?.[field]);
    if (value) {
      return value;
    }
  }
  return "";
}

function metaReportDateEntries(meta: ResultMeta) {
  return META_REPORT_DATE_FIELDS.map((field) => ({
    field,
    date: cleanMetaDate(meta[field]),
  }));
}

function metaFallbackLabel(meta: ResultMeta) {
  return meta.fallback_mode === "none" && !meta.fallback_date
    ? "none"
    : `${meta.fallback_mode}${meta.fallback_date ? `/${meta.fallback_date}` : ""}`;
}

function collectPortfolioMetaBlockers(
  label: string,
  meta: ResultMeta | undefined,
  expectedDate: string,
  blockingReasons: string[],
  warningReasons: string[],
  sourceFacts: string[],
) {
  if (!meta) {
    blockingReasons.push(`${label}证据元数据缺失`);
    return;
  }
  const fallback = metaFallbackLabel(meta);
  sourceFacts.push(
    `${label}: basis=${meta.basis}, formal_use_allowed=${String(
      meta.formal_use_allowed,
    )}, quality=${meta.quality_flag}, fallback=${fallback}`,
  );
  if (meta.basis !== "formal") {
    blockingReasons.push(`${label} basis=${meta.basis}`);
  }
  if (!meta.formal_use_allowed) {
    blockingReasons.push(`${label} formal_use_allowed=false`);
  }
  if (meta.quality_flag !== "ok") {
    blockingReasons.push(`${label} quality=${meta.quality_flag}`);
  }
  if (meta.fallback_mode !== "none" || meta.fallback_date) {
    blockingReasons.push(`${label} fallback=${fallback}`);
  }
  if (meta.quality_flag === "warning" || meta.basis === "analytical") {
    warningReasons.push(`${label} basis=${meta.basis}, quality=${meta.quality_flag}`);
  }
  const metaDates = metaReportDateEntries(meta);
  if (metaDates.some((entry) => !entry.date)) {
    blockingReasons.push(`${label} report_date 缺失`);
  }
  for (const entry of metaDates) {
    if (expectedDate && entry.date && entry.date !== expectedDate) {
      blockingReasons.push(`${label} meta_date=${entry.date}`);
    }
  }
}

export function buildPortfolioReadinessGate(args: {
  decisionAnchorDate: string;
  readPathTone: PortfolioGateTone;
  hasCoreReads: boolean;
  evidenceSources: PortfolioEvidenceSource[];
  riskDatesEvidence?: PortfolioRiskDatesEvidence;
}): PortfolioReadinessGate {
  const blockingReasons: string[] = [];
  const warningReasons: string[] = [];
  const sourceFacts: string[] = [];
  const decisionAnchorDate = args.decisionAnchorDate;
  const dateEntries = args.evidenceSources.map((source) => ({
    label: source.label,
    date: source.reportDate || metaReportDate(source.meta) || "",
  }));

  for (const source of args.evidenceSources) {
    if (source.isError) {
      blockingReasons.push(`${source.label}读取失败`);
      continue;
    }
    if (source.isLoading) {
      blockingReasons.push(`${source.label}读取中`);
      continue;
    }
    if (!source.hasData) {
      blockingReasons.push(`${source.label}未返回`);
      continue;
    }
    collectPortfolioMetaBlockers(
      source.label,
      source.meta,
      decisionAnchorDate,
      blockingReasons,
      warningReasons,
      sourceFacts,
    );
    if (!source.reportDate) {
      blockingReasons.push(`${source.label} report_date 缺失`);
    }
    if (decisionAnchorDate && source.reportDate && source.reportDate !== decisionAnchorDate) {
      blockingReasons.push(`${source.label}=${source.reportDate}`);
    }
  }

  const comparableDates = dateEntries.filter((entry) => entry.date && entry.date !== "-");
  const uniqueDates = new Set(comparableDates.map((entry) => entry.date));
  const sourceDates = comparableDates.map((entry) => `${entry.label}=${entry.date}`).join("；") || "-";
  if (uniqueDates.size > 1) {
    blockingReasons.push(`日期不一致：${sourceDates}`);
  }

  const riskEvidence = args.riskDatesEvidence;
  const riskDates = riskEvidence?.dates ?? [];
  const latestRiskDate = riskDates[0] ?? "";
  const riskBlockingReasons: string[] = [];
  if (!decisionAnchorDate) {
    riskBlockingReasons.push("待债券报告日");
  }
  if (riskEvidence?.isError) {
    riskBlockingReasons.push("风险闭合证据读取失败");
  } else if (riskEvidence?.isLoading) {
    riskBlockingReasons.push("风险闭合证据读取中");
  } else if (!riskEvidence?.hasData) {
    riskBlockingReasons.push("风险闭合证据未返回");
  } else {
    collectPortfolioMetaBlockers(
      "风险闭合证据",
      riskEvidence.meta,
      decisionAnchorDate,
      riskBlockingReasons,
      warningReasons,
      sourceFacts,
    );
    if (riskDates.length === 0) {
      riskBlockingReasons.push("风险闭合证据为空");
    }
    if (decisionAnchorDate && riskDates.length > 0 && !riskDates.includes(decisionAnchorDate)) {
      riskBlockingReasons.push(
        `风险张量未闭合至 ${decisionAnchorDate}，最新 ${latestRiskDate || "未返回"}`,
      );
    }
  }
  const riskClosureReady = riskBlockingReasons.length === 0;
  const riskClosureFact = riskClosureReady
    ? `同日闭合 ${decisionAnchorDate}`
    : riskBlockingReasons.join("；");
  if (!riskClosureReady) {
    warningReasons.push(riskClosureFact);
  }

  const coreRender = args.readPathTone !== "error" && args.hasCoreReads;
  const decisionReady = coreRender && blockingReasons.length === 0;
  const tone: PortfolioGateTone =
    args.readPathTone === "error"
      ? "error"
      : !decisionReady || !riskClosureReady
        ? "watch"
        : "ok";

  return {
    coreRender,
    decisionReady,
    riskClosureReady,
    tone,
    blockingReasons,
    warningReasons,
    sourceFacts,
    sourceDates,
    riskClosureFact,
  };
}
