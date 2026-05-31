import { Link } from "react-router-dom";
import {
  CalendarOutlined,
  ReloadOutlined,
  SearchOutlined,
  WarningFilled,
} from "@ant-design/icons";

import type { DashboardHomeView } from "../dashboardHomeView";
import styles from "../dashboardHome.module.css";

function statusPillClass(statusKind: DashboardHomeView["headerStatus"]["dataStatusKind"]) {
  return statusKind === "ok"
    ? styles.dhStatusPill
    : `${styles.dhStatusPill} ${styles.dhStatusPillWarning}`;
}

function statusDotClass(statusKind: DashboardHomeView["headerStatus"]["dataStatusKind"]) {
  return `${styles.dhDot} ${statusKind === "ok" ? styles.dhDotGreen : styles.dhDotOrange}`;
}

type DashboardHomeToolbarProps = {
  headerStatus: DashboardHomeView["headerStatus"];
  reportDateInput: string;
  onReportDateChange: (value: string) => void;
  toolbarSearch: string;
  onSearchChange: (value: string) => void;
  allowPartial: boolean;
  onAllowPartialChange: (checked: boolean) => void;
  onRefresh: () => void;
  refreshLabel: string;
};

export function DashboardHomeToolbar({
  headerStatus,
  reportDateInput,
  onReportDateChange,
  toolbarSearch,
  onSearchChange,
  allowPartial,
  onAllowPartialChange,
  onRefresh,
  refreshLabel,
}: DashboardHomeToolbarProps) {
  return (
    <header data-testid="dashboard-home-toolbar" className={styles.dhTopbar}>
      <div className={styles.dhTopbarLeft}>
        <div className={styles.dhTitleBrand}>
          <span className={styles.dhTitleBar} aria-hidden="true" />
          <span className={styles.dhTitleMark} aria-hidden="true">
            M
          </span>
          <h1 className={styles.dhTitle}>经营驾驶舱</h1>
        </div>
        <span className={styles.dhDateLabel}>报告日</span>
        <label className={styles.dhDateSelect}>
          <CalendarOutlined className={styles.dhDateSelectIcon} />
          <input
            aria-label="报告日"
            type="date"
            placeholder="2026-04-30"
            value={reportDateInput}
            onClick={(event) => event.currentTarget.showPicker?.()}
            onChange={(event) => onReportDateChange(event.target.value)}
          />
        </label>
        <label className={styles.dhSearch}>
          <SearchOutlined className={styles.dhSearchIcon} />
          <input
            aria-label="搜索指标 / 报表 / 功能"
            placeholder="搜索指标 / 报表 / 功能"
            value={toolbarSearch}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </label>
      </div>

      <div className={styles.dhTopbarRight}>
        <div className={styles.dhStatusRow}>
          <span
            data-testid="dashboard-home-data-status"
            data-status-kind={headerStatus.dataStatusKind}
            className={statusPillClass(headerStatus.dataStatusKind)}
          >
            <i
              className={statusDotClass(headerStatus.dataStatusKind)}
              aria-hidden="true"
            />
            {headerStatus.dataSyncPrefix}{" "}
            <span className={styles.dhNum}>{headerStatus.dataUpdatedAt}</span>
          </span>
          <span className={styles.dhStatusPill}>
            <i className={`${styles.dhDot} ${styles.dhDotOrange}`} aria-hidden="true" />
            {headerStatus.marketStatus}
          </span>
          <span className={styles.dhStatusPill}>
            <i className={`${styles.dhDot} ${styles.dhDotBlue}`} aria-hidden="true" />
            {headerStatus.valuationLabel}
          </span>
          {headerStatus.showRiskReview ? (
            <Link
              to="/decision-items"
              className={`${styles.dhStatusPill} ${styles.dhStatusPillAlert}`}
            >
              <WarningFilled />
              风险待复核
              <strong className={styles.dhNum}>{headerStatus.riskReviewCount}</strong>
            </Link>
          ) : null}
        </div>
        <label className={styles.dhPartialToggle}>
          <input
            type="checkbox"
            checked={allowPartial}
            onChange={(event) => onAllowPartialChange(event.target.checked)}
          />
          <span>含缺域</span>
        </label>
        <button type="button" className={styles.dhRefreshBtn} onClick={onRefresh}>
          <ReloadOutlined />
          {refreshLabel}
        </button>
      </div>
    </header>
  );
}
