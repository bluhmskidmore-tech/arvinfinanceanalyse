import { Link } from "react-router-dom";

import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";

export type DashboardCockpitHeaderProps = {
  viewModel: Pick<
    DashboardCockpitHomeViewModel,
    "reportDate" | "headerStatus"
  >;
  toolbarSearch: string;
  onSearchChange: (value: string) => void;
  reportDateInput: string;
  onReportDateChange: (value: string) => void;
  allowPartial: boolean;
  onAllowPartialChange: (checked: boolean) => void;
  modeLabel: string;
  onRefresh: () => void;
  refreshLabel: string;
};

function toDateInputValue(value: string): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : "";
}

export function DashboardCockpitHeader({
  viewModel,
  toolbarSearch,
  onSearchChange,
  reportDateInput,
  onReportDateChange,
  allowPartial,
  onAllowPartialChange,
  modeLabel,
  onRefresh,
  refreshLabel,
}: DashboardCockpitHeaderProps) {
  const { reportDate, headerStatus } = viewModel;
  const dateInputValue = toDateInputValue(reportDateInput) || toDateInputValue(reportDate);
  const valuationClass =
    headerStatus.valuationTone === "ok"
      ? "dashboard-cockpit-header__pill dashboard-cockpit-header__pill--ok"
      : "dashboard-cockpit-header__pill dashboard-cockpit-header__pill--muted";

  return (
    <header
      data-testid="dashboard-home-toolbar"
      className="dashboard-cockpit-header"
    >
      <div className="dashboard-cockpit-header__left">
        <div className="dashboard-cockpit-header__brand">
          <h1
            data-testid="dashboard-executive-hero-title"
            className="dashboard-cockpit-header__title"
          >
            经营驾驶舱
          </h1>
        </div>
        <label className="dashboard-cockpit-header__date">
          <span>报告日</span>
          <input
            aria-label="报告日"
            type="text"
            inputMode="numeric"
            pattern="\d{4}-\d{2}-\d{2}"
            placeholder="2026-04-30"
            value={dateInputValue}
            onChange={(event) => onReportDateChange(event.target.value)}
            style={tabularNumsStyle}
          />
        </label>
        <label className="dashboard-cockpit-header__partial">
          <input
            aria-label="允许历史日（含缺域）"
            type="checkbox"
            checked={allowPartial}
            onChange={(event) => onAllowPartialChange(event.target.checked)}
          />
          含缺域
        </label>
      </div>

      <label className="dashboard-cockpit-header__search dashboard-home-toolbar__search">
        <span aria-hidden="true">⌕</span>
        <input
          aria-label="搜索指标 / 报表 / 功能"
          placeholder="搜索指标 / 报表 / 功能"
          value={toolbarSearch}
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </label>

      <div className="dashboard-cockpit-header__right dashboard-home-toolbar__actions">
        <div className="dashboard-cockpit-header__status-group">
          <span className="dashboard-cockpit-header__pill dashboard-cockpit-header__pill--info" style={tabularNumsStyle}>
            {headerStatus.dataSyncPrefix} {headerStatus.dataUpdatedAt}
          </span>
          <span className="dashboard-cockpit-header__pill">{headerStatus.marketStatus}</span>
          {headerStatus.valuationLabel ? (
            <span className={valuationClass}>{headerStatus.valuationLabel}</span>
          ) : null}
          {headerStatus.showRiskReview ? (
            <Link
              to="/decision-items"
              className="dashboard-cockpit-header__pill dashboard-cockpit-header__pill--warn"
            >
              风险待复核 <strong style={tabularNumsStyle}>{headerStatus.riskReviewCount}</strong>
            </Link>
          ) : null}
          <span className="dashboard-cockpit-header__mode">{modeLabel}</span>
        </div>
        <nav className="dashboard-cockpit-header__links" aria-label="快捷入口">
          <Link
            to="/platform-config"
            className="dashboard-cockpit-header__icon-btn"
            title="数据中心"
            aria-label="数据中心"
          >
            数
          </Link>
          <Link
            to="/reports"
            className="dashboard-cockpit-header__icon-btn"
            title="报表中心"
            aria-label="报表中心"
          >
            报
          </Link>
          <Link
            to="/decision-items"
            className="dashboard-cockpit-header__icon-btn"
            title="预警中心"
            aria-label="预警中心"
          >
            警
          </Link>
        </nav>
        <button
          type="button"
          onClick={onRefresh}
          className="dashboard-cockpit-header__refresh"
        >
          {refreshLabel}
        </button>
      </div>
    </header>
  );
}
