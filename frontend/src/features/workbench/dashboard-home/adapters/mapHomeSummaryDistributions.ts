import type {
  AssetStructurePayload,
  BondBusinessTypeMetricsResult,
  IndustryDistPayload,
  MaturityStructurePayload,
  Numeric,
  PortfolioComparisonPayload,
  SpreadAnalysisPayload,
  YieldDistributionPayload,
} from "../../../../api/contracts";

export type HomeDistributionRowView = {
  id: string;
  label: string;
  valueRaw: number | null;
  valueDisplay: string;
  percentageRaw: number | null;
  percentageDisplay?: string;
  count?: number;
};

export type HomeDistributionView = {
  key: string;
  label: string;
  reportDate: string;
  rows: readonly HomeDistributionRowView[];
};

type StructurePayload = AssetStructurePayload | MaturityStructurePayload | IndustryDistPayload;

type MapHomeSummaryDistributionsInput = {
  report_date: string;
  asset_type?: AssetStructurePayload;
  asset_rating?: AssetStructurePayload;
  maturity?: MaturityStructurePayload;
  industry?: IndustryDistPayload;
  yield_distribution?: YieldDistributionPayload;
  portfolio_comparison?: PortfolioComparisonPayload;
  spread?: SpreadAnalysisPayload;
  business_type?: BondBusinessTypeMetricsResult;
};

function numericRaw(value: Numeric | null | undefined): number | null {
  const raw = value?.raw;
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
}

function numericDisplay(value: Numeric | null | undefined): string {
  const display = value?.display?.trim();
  return display ? display : "--";
}

function maybePercentageDisplay(value: Numeric | null | undefined): string | undefined {
  const display = value?.display?.trim();
  return display || undefined;
}

function parseDisplayNumber(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }
  const normalized = value.replace(/,/g, "").trim();
  if (!normalized) {
    return null;
  }
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function withOptionalFields(
  base: Omit<HomeDistributionRowView, "percentageDisplay" | "count">,
  options: { percentageDisplay?: string; count?: number },
): HomeDistributionRowView {
  return {
    ...base,
    ...(options.percentageDisplay ? { percentageDisplay: options.percentageDisplay } : {}),
    ...(typeof options.count === "number" ? { count: options.count } : {}),
  };
}

function mapStructureSection<T extends StructurePayload["items"][number]>(
  key: string,
  label: string,
  payload: { report_date: string; items: readonly T[] } | undefined,
  getLabel: (item: T) => string,
): HomeDistributionView {
  return {
    key,
    label,
    reportDate: payload?.report_date ?? "",
    rows: (payload?.items ?? []).map((item, index) =>
      withOptionalFields(
        {
          id: `${key}-${getLabel(item) || index}`,
          label: getLabel(item) || "--",
          valueRaw: numericRaw(item.total_market_value),
          valueDisplay: numericDisplay(item.total_market_value),
          percentageRaw: numericRaw(item.percentage),
        },
        {
          percentageDisplay: maybePercentageDisplay(item.percentage),
          count: item.bond_count,
        },
      ),
    ),
  };
}

function mapYieldDistribution(payload: YieldDistributionPayload | undefined): HomeDistributionView {
  return {
    key: "yield_distribution",
    label: "Yield distribution",
    reportDate: payload?.report_date ?? "",
    rows: (payload?.items ?? []).map((item, index) => ({
      id: `yield-${item.yield_bucket || index}`,
      label: item.yield_bucket || "--",
      valueRaw: numericRaw(item.total_market_value),
      valueDisplay: numericDisplay(item.total_market_value),
      percentageRaw: null,
      count: item.bond_count,
    })),
  };
}

function mapPortfolioComparison(payload: PortfolioComparisonPayload | undefined): HomeDistributionView {
  return {
    key: "portfolio_comparison",
    label: "Portfolio comparison",
    reportDate: payload?.report_date ?? "",
    rows: (payload?.items ?? []).map((item, index) => ({
      id: `portfolio-${item.portfolio_name || index}`,
      label: item.portfolio_name || "--",
      valueRaw: numericRaw(item.total_market_value),
      valueDisplay: numericDisplay(item.total_market_value),
      percentageRaw: null,
      count: item.bond_count,
    })),
  };
}

function mapSpread(payload: SpreadAnalysisPayload | undefined): HomeDistributionView {
  return {
    key: "spread",
    label: "Spread analysis",
    reportDate: payload?.report_date ?? "",
    rows: (payload?.items ?? []).map((item, index) => ({
      id: `spread-${item.bond_type || index}`,
      label: item.bond_type || "--",
      valueRaw: numericRaw(item.total_market_value),
      valueDisplay: numericDisplay(item.total_market_value),
      percentageRaw: null,
      count: item.bond_count,
    })),
  };
}

function mapBusinessType(payload: BondBusinessTypeMetricsResult | undefined): HomeDistributionView {
  return {
    key: "business_type",
    label: "Business type",
    reportDate: payload?.report_date ?? "",
    rows: (payload?.items ?? []).map((item, index) => ({
      id: `business-type-${item.name || index}`,
      label: item.name || "--",
      valueRaw: parseDisplayNumber(item.market_value),
      valueDisplay: item.market_value || "--",
      percentageRaw: null,
    })),
  };
}

export function mapHomeSummaryDistributions(
  input: MapHomeSummaryDistributionsInput,
): HomeDistributionView[] {
  return [
    mapStructureSection("asset_type", "Asset type", input.asset_type, (item) => item.category),
    mapStructureSection("asset_rating", "Asset rating", input.asset_rating, (item) => item.category),
    mapStructureSection("maturity", "Maturity", input.maturity, (item) => item.maturity_bucket),
    mapStructureSection("industry", "Industry", input.industry, (item) => item.industry_name),
    mapYieldDistribution(input.yield_distribution),
    mapPortfolioComparison(input.portfolio_comparison),
    mapSpread(input.spread),
    mapBusinessType(input.business_type),
  ].filter((section) => section.rows.length > 0 || section.reportDate || input.report_date);
}
