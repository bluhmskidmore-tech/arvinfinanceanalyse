import { Button, Card, Select } from "antd";

import type {
  BondAnalyticsAccountingClassFilter,
  BondAnalyticsAssetClassFilter,
  BondAnalyticsScenarioSetFilter,
  PeriodType,
} from "../types";
import {
  BOND_ANALYTICS_ACCOUNTING_CLASS_FILTER_OPTIONS,
  BOND_ANALYTICS_ASSET_CLASS_FILTER_OPTIONS,
  BOND_ANALYTICS_SCENARIO_SET_OPTIONS,
  BOND_ANALYTICS_SPREAD_SCENARIO_PRESETS,
  FIELD,
  panelStyle,
  PERIOD_OPTIONS,
} from "./bondAnalyticsCockpitTokens";

export interface BondAnalyticsFilterActionStripProps {
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
  onRefreshAnalytics?: () => void;
  isAnalyticsRefreshing?: boolean;
  analyticsRefreshError?: string | null;
  lastAnalyticsRefreshRunId?: string | null;
}

export function BondAnalyticsFilterActionStrip({
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
  onRefreshAnalytics,
  isAnalyticsRefreshing = false,
  analyticsRefreshError = null,
  lastAnalyticsRefreshRunId = null,
}: BondAnalyticsFilterActionStripProps) {
  return (
    <Card
      size="small"
      data-testid="bond-analysis-filter-action-strip"
      style={panelStyle("#fcfdff")}
      styles={{ body: { paddingBlock: 12 } }}
    >
      <div
        data-testid="bond-analysis-command-bar"
        style={{ display: "grid", gap: 12 }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
            <div>
              <div style={FIELD}>报表日期</div>
              <Select
                value={reportDate}
                onChange={onReportDateChange}
                options={dateOptions}
                style={{ width: 172 }}
                size="small"
                placeholder="选择报表日"
              />
            </div>
            <div>
              <div style={FIELD}>统计区间</div>
              <Select
                value={periodType}
                onChange={(value) => onPeriodTypeChange(value as PeriodType)}
                options={PERIOD_OPTIONS}
                style={{ width: 132 }}
                size="small"
              />
            </div>
          {onRefreshAnalytics ? (
            <div>
              <div style={FIELD}>Refresh</div>
              <Button
                type="default"
                size="small"
                loading={isAnalyticsRefreshing}
                disabled={isAnalyticsRefreshing}
                onClick={() => onRefreshAnalytics()}
                data-testid="bond-analytics-refresh-button"
              >
                Refresh analytics
              </Button>
            </div>
          ) : null}
          </div>
          <div
            style={{
              color: analyticsRefreshError ? "#a9342f" : "#52657f",
              fontSize: 12,
              lineHeight: 1.6,
              minWidth: 220,
              textAlign: "right",
            }}
          >
            {analyticsRefreshError ??
              (isAnalyticsRefreshing
                ? "Refreshing governed overview state..."
                : lastAnalyticsRefreshRunId
                  ? `Latest run ${lastAnalyticsRefreshRunId}`
                  : "No refresh run has been captured yet.")}
          </div>
        </div>

        <details>
          <summary
            style={{
              cursor: "pointer",
              color: "#52657f",
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
            }}
          >
            高级筛选
          </summary>
          <div
            style={{
              display: "flex",
              alignItems: "flex-end",
              gap: 12,
              flexWrap: "wrap",
              marginTop: 12,
            }}
          >
            <div>
              <div style={FIELD}>收益拆解 · 资产类</div>
              <Select
                value={assetClass}
                onChange={(value) => onAssetClassChange(value as BondAnalyticsAssetClassFilter)}
                options={[...BOND_ANALYTICS_ASSET_CLASS_FILTER_OPTIONS]}
                style={{ width: 140 }}
                size="small"
              />
            </div>
            <div>
              <div style={FIELD}>收益拆解 · 会计口径</div>
              <Select
                value={accountingClass}
                onChange={(value) => onAccountingClassChange(value as BondAnalyticsAccountingClassFilter)}
                options={[...BOND_ANALYTICS_ACCOUNTING_CLASS_FILTER_OPTIONS]}
                style={{ width: 120 }}
                size="small"
              />
            </div>
            <div>
              <div style={FIELD}>KRD 情景集</div>
              <Select
                value={scenarioSet}
                onChange={(value) => onScenarioSetChange(value as BondAnalyticsScenarioSetFilter)}
                options={[...BOND_ANALYTICS_SCENARIO_SET_OPTIONS]}
                style={{ width: 132 }}
                size="small"
              />
            </div>
            <div>
              <div style={FIELD}>信用迁移 ·利差(bp)</div>
              <Select
                value={spreadScenarios}
                onChange={onSpreadScenariosChange}
                options={[...BOND_ANALYTICS_SPREAD_SCENARIO_PRESETS]}
                style={{ width: 168 }}
                size="small"
              />
            </div>
          </div>
        </details>
      </div>
    </Card>
  );
}
