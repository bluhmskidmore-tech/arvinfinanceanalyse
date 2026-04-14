import type { BondAnalyticsOverviewModel } from "../lib/bondAnalyticsOverviewModel";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import type {
  BondAnalyticsAccountingClassFilter,
  BondAnalyticsAssetClassFilter,
  BondAnalyticsScenarioSetFilter,
  PeriodType,
} from "../types";
import { BondAnalyticsDecisionRail } from "./BondAnalyticsDecisionRail";
import { BondAnalyticsFilterActionStrip } from "./BondAnalyticsFilterActionStrip";
import { BondAnalyticsInstitutionalCockpit } from "./BondAnalyticsInstitutionalCockpit";
import { BondAnalyticsFuturePanel } from "./BondAnalyticsFuturePanel";
import { BondAnalyticsHeadlineZone } from "./BondAnalyticsHeadlineZone";
import { BondAnalyticsMarketContextStrip } from "./BondAnalyticsMarketContextStrip";
import { BondAnalyticsOverviewWatchlistCard } from "./BondAnalyticsOverviewWatchlistCard";
import { BondAnalyticsReadinessMatrix } from "./BondAnalyticsReadinessMatrix";
import { promotionLabel } from "./bondAnalyticsCockpitTokens";

export interface BondAnalyticsOverviewPanelsProps {
  dateOptions: Array<{ value: string; label: string }>;
  reportDate: string;
  onReportDateChange: (value: string) => void;
  periodType: PeriodType;
  onPeriodTypeChange: (value: PeriodType) => void;
  assetClass: BondAnalyticsAssetClassFilter;
  onAssetClassChange: (value: BondAnalyticsAssetClassFilter) => void;
  accountingClass: BondAnalyticsAccountingClassFilter;
  onAccountingClassChange: (value: BondAnalyticsAccountingClassFilter) => void;
  scenarioSet: BondAnalyticsScenarioSetFilter;
  onScenarioSetChange: (value: BondAnalyticsScenarioSetFilter) => void;
  spreadScenarios: string;
  onSpreadScenariosChange: (value: string) => void;
  overviewModel: BondAnalyticsOverviewModel;
  onOpenModuleDetail: (key: BondAnalyticsModuleKey) => void;
  onRefreshAnalytics?: () => void;
  isAnalyticsRefreshing?: boolean;
  analyticsRefreshError?: string | null;
  lastAnalyticsRefreshRunId?: string | null;
}

export function BondAnalyticsOverviewPanels({
  dateOptions,
  reportDate,
  onReportDateChange,
  periodType,
  onPeriodTypeChange,
  assetClass,
  onAssetClassChange,
  accountingClass,
  onAccountingClassChange,
  scenarioSet,
  onScenarioSetChange,
  spreadScenarios,
  onSpreadScenariosChange,
  overviewModel,
  onOpenModuleDetail,
  onRefreshAnalytics,
  isAnalyticsRefreshing = false,
  analyticsRefreshError = null,
  lastAnalyticsRefreshRunId = null,
}: BondAnalyticsOverviewPanelsProps) {
  const headlineTile = overviewModel.headlineTiles[0] ?? null;
  const headlineCtaLabel = headlineTile ? `Open ${headlineTile.label}` : null;
  const activeReadinessItem =
    overviewModel.readinessItems.find((item) => item.key === overviewModel.activeModuleContext.key) ??
    overviewModel.readinessItems[0];
  const watchlistItems = overviewModel.readinessItems.filter(
    (item) => item.key !== overviewModel.activeModuleContext.key,
  );
  const promotedItems = overviewModel.readinessItems.filter(
    (item) => item.promotionDestination !== "readiness-only",
  );
  const warningItems = overviewModel.readinessItems.filter(
    (item) =>
      item.statusLabel === "warning" ||
      item.statusLabel === "placeholder-blocked" ||
      item.statusLabel === "request-error",
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "grid", gap: 12 }} data-testid="bond-analysis-top-cockpit">
        <BondAnalyticsMarketContextStrip
          reportDate={reportDate}
          periodType={periodType}
          leadModuleLabel={overviewModel.activeModuleContext.label}
          leadPromotionLabel={promotionLabel(activeReadinessItem.promotionDestination)}
          truthStrip={overviewModel.truthStrip}
        />

        <BondAnalyticsFilterActionStrip
          dateOptions={dateOptions}
          reportDate={reportDate}
          onReportDateChange={onReportDateChange}
          periodType={periodType}
          onPeriodTypeChange={onPeriodTypeChange}
          assetClass={assetClass}
          onAssetClassChange={onAssetClassChange}
          accountingClass={accountingClass}
          onAccountingClassChange={onAccountingClassChange}
          scenarioSet={scenarioSet}
          onScenarioSetChange={onScenarioSetChange}
          spreadScenarios={spreadScenarios}
          onSpreadScenariosChange={onSpreadScenariosChange}
          onRefreshAnalytics={onRefreshAnalytics}
          isAnalyticsRefreshing={isAnalyticsRefreshing}
          analyticsRefreshError={analyticsRefreshError}
          lastAnalyticsRefreshRunId={lastAnalyticsRefreshRunId}
        />

        <BondAnalyticsInstitutionalCockpit reportDate={reportDate} />

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1.85fr) minmax(300px, 0.95fr)",
            gap: 12,
            alignItems: "start",
          }}
        >
          <div style={{ display: "grid", gap: 12 }}>
            <BondAnalyticsHeadlineZone
              headlineTile={headlineTile}
              headlineCtaLabel={headlineCtaLabel}
              promotedItems={promotedItems}
              warningItems={warningItems}
              onOpenModuleDetail={onOpenModuleDetail}
            />

            <BondAnalyticsOverviewWatchlistCard topAnomalies={overviewModel.topAnomalies} />
          </div>

          <div style={{ display: "grid", gap: 12 }} data-testid="bond-analysis-right-rail">
            <BondAnalyticsFuturePanel futureVisibilityItems={overviewModel.futureVisibilityItems} />

            <BondAnalyticsDecisionRail
              activeModuleContext={overviewModel.activeModuleContext}
              activeReadinessItem={activeReadinessItem}
              watchlistItems={watchlistItems}
              onOpenModuleDetail={onOpenModuleDetail}
            />

            <BondAnalyticsReadinessMatrix
              readinessItems={overviewModel.readinessItems}
              onOpenModuleDetail={onOpenModuleDetail}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default BondAnalyticsOverviewPanels;
