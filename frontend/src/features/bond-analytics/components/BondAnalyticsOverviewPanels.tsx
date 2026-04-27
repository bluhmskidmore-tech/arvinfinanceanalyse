import { designTokens } from "../../../theme/designSystem";
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
import { BondAnalyticsMacroMarketBar } from "./BondAnalyticsMacroMarketBar";
import { BondAnalyticsMarketContextStrip } from "./BondAnalyticsMarketContextStrip";
import { BondAnalyticsOverviewMidCharts } from "./BondAnalyticsOverviewMidCharts";
import RiskTrendChart from "./RiskTrendChart";
import BondEventCalendar from "./BondEventCalendar";

const dt = designTokens;

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
  overviewModel: BondAnalyticsOverviewModel;
  onOpenModuleDetail: (key: BondAnalyticsModuleKey) => void;
  onRefreshAnalytics?: () => void;
  isAnalyticsRefreshing?: boolean;
  analyticsRefreshError?: string | null;
  lastAnalyticsRefreshRunId?: string | null;
  calendarItems?: CalendarItem[];
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
  actionAttributionResult = null,
  overviewModel,
  onOpenModuleDetail,
  onRefreshAnalytics,
  isAnalyticsRefreshing = false,
  analyticsRefreshError = null,
  lastAnalyticsRefreshRunId = null,
  calendarItems = [],
}: BondAnalyticsOverviewPanelsProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: dt.space[3] }}>
      <div style={{ display: "grid", gap: dt.space[3] }} data-testid="bond-analysis-top-cockpit">
        <BondAnalyticsMacroMarketBar />

        <BondAnalyticsMarketContextStrip
          reportDate={reportDate}
          periodType={periodType}
          leadModuleLabel={overviewModel.activeModuleContext.label}
          leadPromotionLabel="Drill available"
          truthStrip={overviewModel.truthStrip}
        />

        <BondAnalyticsInstitutionalCockpit
          reportDate={reportDate}
          actionAttribution={actionAttributionResult}
          topAnomalies={overviewModel.topAnomalies}
          onOpenModuleDetail={onOpenModuleDetail}
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

        <BondAnalyticsOverviewMidCharts
          reportDate={reportDate}
          periodType={periodType}
          assetClass={assetClass}
          accountingClass={accountingClass}
        />

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: dt.space[3],
            alignItems: "start",
          }}
        >
          <RiskTrendChart />
          <BondEventCalendar items={calendarItems} />
        </div>
      </div>
    </div>
  );
}
