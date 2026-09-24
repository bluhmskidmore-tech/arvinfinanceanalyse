import type {
  ApiEnvelope,
  BondDashboardBundlePayload,
  BondDashboardBundleSectionEnvelopeMap,
  BondDashboardBundleSectionId,
} from "../../api/contracts";

export const BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS = [
  "headline-kpis",
  "risk-indicators",
  "asset-structure",
  "asset-structure-rating",
  "asset-structure-portfolio-name",
  "asset-structure-tenor-bucket",
  "yield-distribution",
  "portfolio-comparison",
  "spread-analysis",
  "maturity-structure",
  "industry-distribution",
  "business-type-metrics",
] as const satisfies readonly BondDashboardBundleSectionId[];

type AssetGroupBy = "bond_type" | "rating" | "portfolio_name" | "tenor_bucket";

export function bondDashboardAssetSectionForGroup(
  groupBy: AssetGroupBy,
): Extract<
  BondDashboardBundleSectionId,
  | "asset-structure"
  | "asset-structure-rating"
  | "asset-structure-portfolio-name"
  | "asset-structure-tenor-bucket"
> {
  if (groupBy === "rating") return "asset-structure-rating";
  if (groupBy === "portfolio_name") return "asset-structure-portfolio-name";
  if (groupBy === "tenor_bucket") return "asset-structure-tenor-bucket";
  return "asset-structure";
}

export function selectBondDashboardBundleSection<TSection extends BondDashboardBundleSectionId>(
  bundle: ApiEnvelope<BondDashboardBundlePayload> | undefined,
  section: TSection,
): BondDashboardBundleSectionEnvelopeMap[TSection] | undefined {
  return bundle?.result.sections[section] as
    | BondDashboardBundleSectionEnvelopeMap[TSection]
    | undefined;
}
