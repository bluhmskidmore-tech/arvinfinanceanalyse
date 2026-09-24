import { Button, Select } from "antd";

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
} from "./bondAnalyticsCockpitTokens";
import styles from "./BondAnalyticsFilterActionStrip.module.css";

/** 弹层锚在条内，避免 portal 落到 body 后逃出本页深色主题。 */
const popupContainer = (trigger: HTMLElement) => trigger.parentElement ?? document.body;

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
  const refreshState = analyticsRefreshError
    ? "error"
    : isAnalyticsRefreshing
      ? "running"
      : lastAnalyticsRefreshRunId
        ? "complete"
        : "idle";
  const refreshStateLabel = analyticsRefreshError
    ? "刷新异常"
    : isAnalyticsRefreshing
      ? "刷新中"
      : lastAnalyticsRefreshRunId
        ? "最近运行"
        : "刷新状态";
  const refreshStateText =
    analyticsRefreshError ??
    (isAnalyticsRefreshing
      ? "正在刷新受治理总览状态..."
      : lastAnalyticsRefreshRunId
        ? `最近运行 ${lastAnalyticsRefreshRunId}`
        : "尚未捕获刷新运行。");

  return (
    <section data-testid="bond-analysis-filter-action-strip" className={styles.actionStrip}>
      <div data-testid="bond-analysis-command-bar" className={styles.commandBar}>
        <div className={styles.commandIntro}>
          <span className={styles.fieldLabel}>复核入口</span>
          <strong>参数与下钻边界</strong>
          <p>
            报告日、期间和刷新放在页面顶部；这里仅保留收益拆解、KRD 和信用迁移的下钻参数。
          </p>
        </div>
        <div
          data-testid="bond-analysis-refresh-state"
          className={styles.refreshState}
          data-state={refreshState}
        >
          <span className={styles.fieldLabel}>{refreshStateLabel}</span>
          <strong>{refreshStateText}</strong>
        </div>
        <div className={styles.refreshAction}>
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

        <details className={styles.advancedPanel}>
          <summary className={styles.advancedSummary}>高级筛选 / 参数调整</summary>
          <div className={styles.filterGrid}>
            <div className={styles.filterField}>
              <div className={styles.fieldLabel}>收益拆解 · 资产类</div>
              <Select
                value={assetClass}
                onChange={(value) => onAssetClassChange(value as BondAnalyticsAssetClassFilter)}
                options={[...BOND_ANALYTICS_ASSET_CLASS_FILTER_OPTIONS]}
                className={styles.filterSelect}
                size="small"
                getPopupContainer={popupContainer}
              />
            </div>
            <div className={styles.filterField}>
              <div className={styles.fieldLabel}>收益拆解 · 会计口径</div>
              <Select
                value={accountingClass}
                onChange={(value) => onAccountingClassChange(value as BondAnalyticsAccountingClassFilter)}
                options={[...BOND_ANALYTICS_ACCOUNTING_CLASS_FILTER_OPTIONS]}
                className={styles.filterSelect}
                size="small"
                getPopupContainer={popupContainer}
              />
            </div>
            <div className={styles.filterField}>
              <div className={styles.fieldLabel}>KRD 情景集</div>
              <Select
                value={scenarioSet}
                onChange={(value) => onScenarioSetChange(value as BondAnalyticsScenarioSetFilter)}
                options={[...BOND_ANALYTICS_SCENARIO_SET_OPTIONS]}
                className={styles.filterSelect}
                size="small"
                getPopupContainer={popupContainer}
              />
            </div>
            <div className={styles.filterField}>
              <div className={styles.fieldLabel}>信用迁移 · 利差(bp)</div>
              <Select
                value={spreadScenarios}
                onChange={onSpreadScenariosChange}
                options={[...BOND_ANALYTICS_SPREAD_SCENARIO_PRESETS]}
                className={styles.filterSelect}
                size="small"
                getPopupContainer={popupContainer}
              />
            </div>
          </div>
        </details>
      </div>
    </section>
  );
}
