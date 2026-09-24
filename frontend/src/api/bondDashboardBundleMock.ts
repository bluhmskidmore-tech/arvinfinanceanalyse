import type {
  ApiEnvelope,
  BondDashboardBundlePayload,
  BondDashboardBundleSectionEnvelopeMap,
  BondDashboardBundleSectionId,
  ResultMeta,
} from "./contracts";

type BuildMockApiEnvelope = <T>(
  resultKind: string,
  result: T,
  metaOverrides?: Partial<ResultMeta>,
) => ApiEnvelope<T>;

export function buildMockBondDashboardBundleEnvelope({
  buildMockApiEnvelope,
  reportDate,
  requestedSections,
  sections,
  industryTopN,
  analyticsTopN,
  dv01TopN,
  dv01ShockBps,
  dv01AccountingClass,
  curveTypes,
  sectionStatuses,
  failedSections,
}: {
  buildMockApiEnvelope: BuildMockApiEnvelope;
  reportDate: string | null;
  requestedSections: readonly BondDashboardBundleSectionId[];
  sections: Partial<BondDashboardBundleSectionEnvelopeMap>;
  industryTopN?: number;
  analyticsTopN?: number;
  dv01TopN?: number;
  dv01ShockBps?: string;
  dv01AccountingClass?: string;
  curveTypes?: string;
  sectionStatuses?: BondDashboardBundlePayload["section_statuses"];
  failedSections?: readonly BondDashboardBundleSectionId[];
}): ApiEnvelope<BondDashboardBundlePayload> {
  const filtersApplied: Record<string, unknown> = {
    sections: [...requestedSections],
  };

  if (reportDate) {
    filtersApplied.report_date = reportDate;
  }
  if (requestedSections.includes("industry-distribution") && industryTopN !== undefined) {
    filtersApplied.industry_top_n = industryTopN;
  }
  if (requestedSections.includes("top-holdings") && analyticsTopN !== undefined) {
    filtersApplied.analytics_top_n = analyticsTopN;
  }
  if (
    requestedSections.some((section) => section.startsWith("dv01-risk")) &&
    dv01TopN !== undefined
  ) {
    filtersApplied.dv01_top_n = dv01TopN;
    filtersApplied.dv01_shock_bps = dv01ShockBps;
  }
  if (requestedSections.includes("dv01-risk") && dv01AccountingClass) {
    filtersApplied.dv01_accounting_class = dv01AccountingClass;
  }
  if (requestedSections.includes("yield-curve-term-structure") && curveTypes) {
    filtersApplied.curve_types = curveTypes;
  }

  const resolvedSectionStatuses = sectionStatuses ?? Object.fromEntries(
    requestedSections.map((section) => [section, { status: "ok" as const, message: null }]),
  );
  const resolvedFailedSections = [...(failedSections ?? [])];

  return {
    ...buildMockApiEnvelope(
      "bond_dashboard.bundle",
      {
        report_date: reportDate,
        requested_sections: [...requestedSections],
        sections,
        section_statuses: resolvedSectionStatuses,
        failed_sections: resolvedFailedSections,
      },
      {
        basis: reportDate ? "analytical" : "formal",
        formal_use_allowed: false,
        quality_flag: reportDate && resolvedFailedSections.length === 0 ? "ok" : "warning",
        requested_report_date: reportDate,
        resolved_report_date: reportDate,
        as_of_date: reportDate,
        date_basis: reportDate ? "bond_dashboard_report_date" : "bond_dashboard_dates",
        filters_applied: filtersApplied,
        tables_used: reportDate ? ["fact_formal_bond_analytics_daily"] : [],
        evidence_rows: 0,
      },
    ),
    data_source: "bond_analytics_facts",
  };
}
