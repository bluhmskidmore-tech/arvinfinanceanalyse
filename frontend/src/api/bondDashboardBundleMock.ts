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
}: {
  buildMockApiEnvelope: BuildMockApiEnvelope;
  reportDate: string | null;
  requestedSections: readonly BondDashboardBundleSectionId[];
  sections: Partial<BondDashboardBundleSectionEnvelopeMap>;
  industryTopN?: number;
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

  return {
    ...buildMockApiEnvelope(
      "bond_dashboard.bundle",
      {
        report_date: reportDate,
        requested_sections: [...requestedSections],
        sections,
      },
      {
        basis: reportDate ? "analytical" : "formal",
        formal_use_allowed: false,
        quality_flag: reportDate ? "ok" : "warning",
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
