import { SectionGrid } from "../../../components/layout";
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
  actionAttributionError?: string | null;
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
  actionAttributionError = null,
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
    /*
     * DESIGN.md §9.1 区块顺序锁：宏观市场条 → 本日判断 → 组合 KPI 横带 → 三列
     * （曲线与波动｜四象策略｜收益归因）→ 三列（结构/风险/今日焦点）→ 双列
     * （事件日历｜重点券表）。本次只把两层裸 grid/flex 包装换成 SectionGrid，
     * 子节点顺序逐字不动。
     */
    <SectionGrid gap={8}>
      {/* 治理标识属证据层（DESIGN §6/§7）：叙述位只留中文结论，契约编号与状态码收进 title。 */}
      <div
        data-testid="bond-analysis-candidate-boundary"
        style={{ fontSize: 12, lineHeight: 1.6, color: "var(--dh-api-muted)" }}
      >
        本页尚未获得业主正式批准，结果仅供分析参考。
      </div>
      <BondAnalyticsMarketContextStrip
        leadModuleLabel={overviewModel.activeModuleContext.label}
        leadPromotionLabel="候选分析"
        truthStrip={overviewModel.truthStrip}
      />
      <SectionGrid gap={8} testId="bond-analysis-top-cockpit">
        <BondAnalyticsInstitutionalCockpit
          reportDate={reportDate}
          periodType={periodType}
          actionAttribution={actionAttributionResult}
          actionAttributionPending={actionAttributionPending}
          actionAttributionError={actionAttributionError}
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
      </SectionGrid>
    </SectionGrid>
  );
}
