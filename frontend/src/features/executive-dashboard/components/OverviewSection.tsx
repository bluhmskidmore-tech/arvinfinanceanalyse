import { DataSection } from "../../../components/DataSection";
import { shellTokens } from "../../../theme/tokens";
import { GridContainer, GridItem } from "../../../components/GridContainer";
import { KpiCard, type KpiCardProps } from "../../../components/KpiCard";
import type { DashboardAdapterOutput, DashboardOverviewMetricVM } from "../adapters/executiveDashboardAdapter";
import { selectOverviewCards } from "../selectors/executiveDashboardSelectors";

/**
 * Maps metric IDs emitted by executive_overview to their governing business
 * caliber so each card can show its data-date attribution.
 */
const METRIC_DOMAIN_MAP: Record<string, string> = {
  aum: "balance_sheet",
  yield: "pnl",
  nim: "balance_sheet",
  dv01: "balance_sheet",
};

const DOMAIN_LABELS: Record<string, string> = {
  balance_sheet: "资产负债",
  pnl: "损益",
};

const METRIC_TONE_TO_KPI_TONE: Record<DashboardOverviewMetricVM["tone"], KpiCardProps["tone"]> = {
  positive: "positive",
  negative: "negative",
  neutral: "default",
  warning: "warning",
};

type OverviewSectionProps = {
  overview: DashboardAdapterOutput["overview"];
  onRetry: () => void;
  /** Per-domain effective data dates, used to label each metric card. */
  domainsEffectiveDate?: Record<string, string>;
};

export function OverviewSection({ overview, onRetry, domainsEffectiveDate }: OverviewSectionProps) {
  const cards = selectOverviewCards(overview.vm);

  return (
    <DataSection
      title="经营总览"
      state={overview.state}
      onRetry={onRetry}
      extra={
        <span
          style={{
            padding: "5px 10px",
            borderRadius: 999,
            background: shellTokens.colorAccentSoft,
            color: shellTokens.colorAccent,
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: "0.04em",
          }}
        >
          {cards.length} 项
        </span>
      }
    >
      <GridContainer>
        {cards.map((metric) => {
          const domain = METRIC_DOMAIN_MAP[metric.id];
          const domainDate = domain && domainsEffectiveDate?.[domain];
          const domainName = domain ? (DOMAIN_LABELS[domain] ?? domain) : null;

          const dateAttr = domainDate && domainName ? `${domainName} ${domainDate}` : "";
          const detailText = metric.detail 
            ? `${metric.detail}${dateAttr ? ` · ${dateAttr}` : ""}`
            : dateAttr;

          return (
            <GridItem key={metric.id} span={8}>
              <KpiCard
                label={metric.label}
                value={metric.value.display}
                changeLabel={metric.delta.display}
                tone={METRIC_TONE_TO_KPI_TONE[metric.tone]}
                detail={detailText}
              />
            </GridItem>
          );
        })}
      </GridContainer>
    </DataSection>
  );
}
