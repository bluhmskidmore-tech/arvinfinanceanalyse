import type { CalendarItem } from "../../../components/CalendarList";
import type { BondAnalyticsOverviewModel } from "../lib/bondAnalyticsOverviewModel";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import type {
  ActionAttributionResponse,
  BondAnalyticsAccountingClassFilter,
  BondAnalyticsAssetClassFilter,
  BondAnalyticsScenarioSetFilter,
  PeriodType,
} from "../types";
import { BondAnalyticsFilterActionStrip } from "./BondAnalyticsFilterActionStrip";
import { BondAnalyticsInstitutionalCockpit } from "./BondAnalyticsInstitutionalCockpit";
import { BondAnalyticsMarketContextStrip } from "./BondAnalyticsMarketContextStrip";

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
  actionAttributionResult?: ActionAttributionResponse | null;
  actionAttributionPending?: boolean;
  overviewModel: BondAnalyticsOverviewModel;
  onOpenModuleDetail: (key: BondAnalyticsModuleKey) => void;
  onRefreshAnalytics?: () => void;
  isAnalyticsRefreshing?: boolean;
  analyticsRefreshError?: string | null;
  lastAnalyticsRefreshRunId?: string | null;
  calendarItems?: CalendarItem[];
  calendarLoading?: boolean;
  calendarError?: boolean;
}

export function BondAnalyticsOverviewPanels({
  dateOptions: _dateOptions,
  reportDate,
  onReportDateChange: _onReportDateChange,
  periodType,
  onPeriodTypeChange: _onPeriodTypeChange,
  assetClass,
  onAssetClassChange,
  accountingClass,
  onAccountingClassChange,
  scenarioSet,
  onScenarioSetChange,
  spreadScenarios,
  onSpreadScenariosChange,
  actionAttributionResult = null,
  actionAttributionPending = false,
  overviewModel,
  onOpenModuleDetail,
  onRefreshAnalytics,
  isAnalyticsRefreshing = false,
  analyticsRefreshError = null,
  lastAnalyticsRefreshRunId = null,
  calendarItems = [],
  calendarLoading = false,
  calendarError = false,
}: BondAnalyticsOverviewPanelsProps) {
  const activeReadinessItem =
    overviewModel.readinessItems.find((item) => item.key === overviewModel.activeModuleContext.key) ??
    overviewModel.readinessItems[0];
  const decisionWatchlistItems = overviewModel.readinessItems.filter(
    (item) => item.key !== activeReadinessItem.key,
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div
        data-testid="bond-analysis-candidate-boundary"
        style={{ fontSize: 12, lineHeight: 1.6, color: "var(--dh-api-muted)" }}
      >
        PAGE-BOND-ANALYSIS-001 · candidate · formal_use_allowed=false · owner approval pending；
        页面结果仅供候选分析，不代表公式或正式批准。
      </div>
      <BondAnalyticsMarketContextStrip
        leadModuleLabel={overviewModel.activeModuleContext.label}
        leadPromotionLabel="candidate"
        truthStrip={overviewModel.truthStrip}
      />
      <div style={{ display: "grid", gap: 8 }} data-testid="bond-analysis-top-cockpit">
        <BondAnalyticsInstitutionalCockpit
          reportDate={reportDate}
          periodType={periodType}
          actionAttribution={actionAttributionResult}
          actionAttributionPending={actionAttributionPending}
          topAnomalies={overviewModel.topAnomalies}
          decisionRail={{
            activeModuleContext: overviewModel.activeModuleContext,
            activeReadinessItem,
            watchlistItems: decisionWatchlistItems,
          }}
          onOpenModuleDetail={onOpenModuleDetail}
          calendarItems={calendarItems}
          calendarLoading={calendarLoading}
          calendarError={calendarError}
        />

        <BondAnalyticsFilterActionStrip
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
      </div>
    </div>
  );
}
