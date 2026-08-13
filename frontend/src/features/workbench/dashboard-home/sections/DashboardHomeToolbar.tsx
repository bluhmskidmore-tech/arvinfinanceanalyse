import { Link } from "react-router-dom";

import { LightIcon } from "../../../../components/LightIcon";
import { isAgentFrontendEnabled } from "../../../../app/navigation";
import { HomeSearchBox } from "../HomeSearchBox";
import type {
  HomeDecisionAction,
  HomeHeaderStatus,
  HomeReportDateContext,
  HomeTerminalKpi,
} from "../dashboardHomeFirstScreenTypes";
import {
  hasReportDateDivergence,
  reportDateContextLabel,
  reportDateModeLabel,
} from "../homeReportDateLabel";
import styles from "../dashboardHomeShell.module.css";

function statusPillClass(statusKind: HomeHeaderStatus["dataStatusKind"]) {
  return statusKind === "ok"
    ? styles.dhStatusPill
    : `${styles.dhStatusPill} ${styles.dhStatusPillWarning}`;
}

function statusDotClass(statusKind: HomeHeaderStatus["dataStatusKind"]) {
  return `${styles.dhDot} ${statusKind === "ok" ? styles.dhDotGreen : styles.dhDotOrange}`;
}

function marketDotClass(valuationTone: HomeHeaderStatus["valuationTone"]) {
  return `${styles.dhDot} ${valuationTone === "ok" ? styles.dhDotBlue : styles.dhDotOrange}`;
}

type DashboardHomeToolbarProps = {
  title?: string;
  toolbarTestId?: string;
  headerStatus: HomeHeaderStatus;
  reportDateInput: string;
  onReportDateChange: (value: string) => void;
  reportDateContext: HomeReportDateContext;
  toolbarSearch: string;
  onSearchChange: (value: string) => void;
  terminalKpis: readonly HomeTerminalKpi[];
  decisionActions: readonly HomeDecisionAction[];
  allowPartial: boolean;
  partialModeSupported?: boolean;
  onAllowPartialChange: (checked: boolean) => void;
  onRefresh: () => void;
  refreshLabel: string;
  refreshAriaLabel?: string;
  refreshing?: boolean;
  onOpenAgentPanel?: () => void;
};

export function DashboardHomeToolbar({
  title = "经营日报",
  toolbarTestId = "dashboard-home-toolbar",
  headerStatus,
  reportDateInput,
  onReportDateChange,
  reportDateContext,
  toolbarSearch,
  onSearchChange,
  terminalKpis,
  decisionActions,
  allowPartial,
  partialModeSupported = false,
  onAllowPartialChange,
  onRefresh,
  refreshLabel,
  refreshAriaLabel = "刷新首页数据",
  refreshing = false,
  onOpenAgentPanel,
}: DashboardHomeToolbarProps) {
  const showDateDivergence = hasReportDateDivergence(reportDateContext);
  const updateStamp =
    reportDateContext.generatedAt?.replace("T", " ").slice(0, 16) ||
    headerStatus.dataUpdatedAt;
  return (
    <header data-testid={toolbarTestId} className={styles.dhTopbar}>
      <div className={styles.dhTopbarLeft} data-role="dashboard-home-toolbar-left">
        <div className={styles.dhTitleBrand} data-role="dashboard-home-title-brand">
          <h1 className={styles.dhTitle}>{title}</h1>
        </div>

        <div className={styles.dhToolbarControl} data-role="dashboard-home-date-control">
          <span className={styles.dhDateLabel} data-role="dashboard-home-date-label">报告日</span>
          <label className={styles.dhDateSelect} data-role="dashboard-home-date-select">
            <LightIcon className={styles.dhDateSelectIcon} name="calendar" />
            <span
              className={styles.dhDateSelectValue}
              data-role="dashboard-home-date-value"
              aria-hidden="true"
            >
              {reportDateInput || "----------"}
            </span>
            <input
              aria-label="报告日"
              type="date"
              placeholder="2026-04-30"
              value={reportDateInput}
              onClick={(event) => event.currentTarget.showPicker?.()}
              onChange={(event) => onReportDateChange(event.target.value)}
            />
          </label>
          <span
            data-testid="dashboard-home-report-date-context"
            data-report-date-mode={reportDateContext.mode}
            className={`${styles.dhDateContext} ${
              showDateDivergence ? styles.dhDateContextDivergent : ""
            }`}
            title={
              showDateDivergence || reportDateContext.mode === "mock"
                ? reportDateContextLabel(reportDateContext)
                : undefined
            }
          >
            <i className={styles.dhDateContextDot} aria-hidden="true" />
            {showDateDivergence || reportDateContext.mode === "mock"
              ? reportDateContextLabel(reportDateContext)
              : reportDateContext.actualDataDate
                ? `数据截至 ${reportDateContext.actualDataDate}`
                : reportDateModeLabel(reportDateContext.mode)}
          </span>
          <span data-role="dashboard-home-update-stamp">
            {`更新 ${updateStamp}`}
          </span>
        </div>

      </div>

      <div className={styles.dhTopbarRight} data-role="dashboard-home-toolbar-right">
        <div className={styles.dhStatusRow} data-role="dashboard-home-status-row">
          <span
            data-testid="dashboard-home-data-status"
            data-status-kind={headerStatus.dataStatusKind}
            className={statusPillClass(headerStatus.dataStatusKind)}
          >
            <i className={statusDotClass(headerStatus.dataStatusKind)} aria-hidden="true" />
            {headerStatus.dataSyncPrefix}
            <span className={styles.dhNum}>{headerStatus.dataUpdatedAt}</span>
          </span>
          <span
            data-role="dashboard-home-market-status"
            className={styles.dhStatusPill}
            title={`${headerStatus.marketStatus} · ${headerStatus.valuationLabel}`}
          >
            <i className={marketDotClass(headerStatus.valuationTone)} aria-hidden="true" />
            <span>{headerStatus.marketStatus}</span>
            <span aria-hidden="true"> · </span>
            <span>{headerStatus.valuationLabel}</span>
          </span>
          {headerStatus.showRiskReview ? (
            <Link
              to="/decision-items"
              className={`${styles.dhStatusPill} ${styles.dhStatusPillAlert}`}
            >
              <LightIcon name="warning" />
              风险待复核
              <strong className={styles.dhNum}>{headerStatus.riskReviewCount}</strong>
            </Link>
          ) : null}
        </div>
        <label
          className={styles.dhPartialToggle}
          data-role="dashboard-home-partial-toggle"
          data-mode-availability={partialModeSupported ? "available" : "blocked"}
          title={
            partialModeSupported
              ? undefined
              : "部分数据模式暂不可用：日期与空值口径待后端修正"
          }
        >
          <input
            type="checkbox"
            aria-label={partialModeSupported && allowPartial ? "显示部分数据" : "仅完整数据"}
            checked={partialModeSupported && allowPartial}
            disabled={!partialModeSupported}
            onChange={(event) => {
              if (partialModeSupported) {
                onAllowPartialChange(event.target.checked);
              }
            }}
          />
          <span>{partialModeSupported && allowPartial ? "显示部分数据" : "仅完整数据"}</span>
        </label>
        <HomeSearchBox
          value={toolbarSearch}
          onValueChange={onSearchChange}
          terminalKpis={terminalKpis}
          decisionActions={decisionActions}
          reportDate={reportDateContext.actualDataDate}
        />
        <button
          type="button"
          className={styles.dhRefreshBtn}
          onClick={onRefresh}
          aria-label={refreshAriaLabel}
          aria-busy={refreshing || undefined}
          data-refreshing={refreshing ? "true" : undefined}
        >
          <LightIcon name="reload" />
          <span className={styles.dhRefreshLabel}>{refreshLabel}</span>
        </button>
        {onOpenAgentPanel && isAgentFrontendEnabled() ? (
          <button
            type="button"
            className={styles.dhAgentEntryBtn}
            data-testid="dashboard-home-agent-open"
            onClick={onOpenAgentPanel}
            aria-label="打开财顾助手"
          >
            <LightIcon name="file-search" />
            <span className={styles.dhRefreshLabel}>财顾助手</span>
          </button>
        ) : null}
      </div>
    </header>
  );
}
