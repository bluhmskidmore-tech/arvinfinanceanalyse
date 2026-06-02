import { Button, Card, Select } from "antd";

import type {
  BondAnalyticsAccountingClassFilter,
  BondAnalyticsAssetClassFilter,
  BondAnalyticsScenarioSetFilter,
} from "../types";
import {
  BOND_ANALYTICS_ACCOUNTING_CLASS_FILTER_OPTIONS,
  BOND_ANALYTICS_ASSET_CLASS_FILTER_OPTIONS,
  BOND_ANALYTICS_SCENARIO_SET_OPTIONS,
  BOND_ANALYTICS_SPREAD_SCENARIO_PRESETS,
  FIELD,
  panelStyle,
} from "./bondAnalyticsCockpitTokens";

export interface BondAnalyticsFilterActionStripProps {
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
      <div data-testid="bond-analysis-command-bar" style={{ display: "grid", gap: 12 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 16,
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "grid", gap: 4 }}>
            <div style={FIELD}>下钻参数</div>
            <div style={{ color: "#52657f", fontSize: 12, lineHeight: 1.6 }}>
              报告日、期间和刷新放在页面顶部；这里保留收益拆解、KRD 和信用迁移的下钻参数。
            </div>
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
                ? "正在刷新受治理总览状态..."
                : lastAnalyticsRefreshRunId
                  ? `最近运行 ${lastAnalyticsRefreshRunId}`
                  : "尚未捕获刷新运行。")}
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
            展开高级筛选
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
              <div style={FIELD}>信用迁移 · 利差(bp)</div>
              <Select
                value={spreadScenarios}
                onChange={onSpreadScenariosChange}
                options={[...BOND_ANALYTICS_SPREAD_SCENARIO_PRESETS]}
                style={{ width: 168 }}
                size="small"
              />
            </div>
            {onRefreshAnalytics ? (
              <Button
                type="default"
                size="small"
                loading={isAnalyticsRefreshing}
                disabled={isAnalyticsRefreshing}
                onClick={() => onRefreshAnalytics()}
                data-testid="bond-analytics-refresh-button"
              >
                刷新分析
              </Button>
            ) : null}
          </div>
        </details>
      </div>
    </Card>
  );
}
