import {
  CalendarOutlined,
  DownloadOutlined,
  FileExcelOutlined,
  FilterOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SwapOutlined,
} from "@ant-design/icons";

import type {
  BalanceCurrencyBasis,
  BalancePageCalibration,
  BalancePositionScope,
} from "../../../api/contracts";
import { CalibrationBadge } from "../../../components/CalibrationBadge";
import type { BalanceAnalysisPageReadModel } from "../pages/balanceAnalysisPageModel";
import dhStyles from "../../workbench/dashboard-home/dashboardHome.module.css";
import toolbarStyles from "./balanceAnalysisToolbar.module.css";

type BalanceAnalysisToolbarProps = {
  reportDates: readonly string[];
  selectedReportDate: string;
  positionScope: BalancePositionScope;
  currencyBasis: BalanceCurrencyBasis;
  sourceBadge: BalanceAnalysisPageReadModel["sourceBadge"];
  calibration?: BalancePageCalibration | null;
  isRefreshing: boolean;
  isExportingCsv: boolean;
  isExportingWorkbook: boolean;
  onReportDateChange: (value: string) => void;
  onPositionScopeChange: (value: BalancePositionScope) => void;
  onCurrencyBasisChange: (value: BalanceCurrencyBasis) => void;
  onRefresh: () => void;
  onExportCsv: () => void;
  onExportWorkbook: () => void;
};

export function BalanceAnalysisToolbar({
  reportDates,
  selectedReportDate,
  positionScope,
  currencyBasis,
  sourceBadge,
  calibration,
  isRefreshing,
  isExportingCsv,
  isExportingWorkbook,
  onReportDateChange,
  onPositionScopeChange,
  onCurrencyBasisChange,
  onRefresh,
  onExportCsv,
  onExportWorkbook,
}: BalanceAnalysisToolbarProps) {
  return (
    <header
      data-testid="balance-analysis-filter-tray"
      className={`${dhStyles.dhTopbar} ${toolbarStyles.baTopbarStack}`}
    >
      <div className={toolbarStyles.baTopbarRow}>
        <div className={dhStyles.dhTopbarLeft}>
          <div className={dhStyles.dhTitleBrand}>
            <span className={dhStyles.dhTitleBar} aria-hidden="true" />
            <span className={dhStyles.dhTitleMark} aria-hidden="true">
              A
            </span>
            <h1 data-testid="balance-analysis-page-title" className={dhStyles.dhTitle}>
              资产负债分析
            </h1>
          </div>
          <span className={dhStyles.dhDateLabel}>报告日</span>
          <label className={toolbarStyles.baToolbarSelect}>
            <CalendarOutlined aria-hidden />
            <select
              aria-label="balance-report-date"
              value={selectedReportDate}
              onChange={(event) => onReportDateChange(event.target.value)}
            >
              {reportDates.map((reportDate) => (
                <option key={reportDate} value={reportDate}>
                  {reportDate}
                </option>
              ))}
            </select>
          </label>
          <label className={toolbarStyles.baToolbarSelect}>
            <FilterOutlined aria-hidden />
            <select
              aria-label="balance-position-scope"
              value={positionScope}
              onChange={(event) => onPositionScopeChange(event.target.value as BalancePositionScope)}
            >
              <option value="all">全部头寸</option>
              <option value="asset">资产</option>
              <option value="liability">负债</option>
            </select>
          </label>
          <label className={toolbarStyles.baToolbarSelect}>
            <SwapOutlined aria-hidden />
            <select
              aria-label="balance-currency-basis"
              value={currencyBasis}
              onChange={(event) => onCurrencyBasisChange(event.target.value as BalanceCurrencyBasis)}
            >
              <option value="CNY">人民币</option>
              <option value="native">原币</option>
            </select>
          </label>
        </div>

        <div className={dhStyles.dhTopbarRight}>
          <CalibrationBadge calibration={calibration} />
          <span className={dhStyles.dhStatusPill} data-tone={sourceBadge.tone}>
            <SafetyCertificateOutlined aria-hidden />
            {sourceBadge.label}
          </span>
          <button
            data-testid="balance-analysis-refresh-button"
            type="button"
            className={dhStyles.dhRefreshBtn}
            onClick={onRefresh}
            disabled={!selectedReportDate || isRefreshing}
          >
            <ReloadOutlined aria-hidden />
            {isRefreshing ? "刷新中…" : "刷新正式结果"}
          </button>
          <button
            data-testid="balance-analysis-export-button"
            type="button"
            className={toolbarStyles.baToolbarAction}
            onClick={onExportCsv}
            disabled={!selectedReportDate || isExportingCsv}
          >
            <DownloadOutlined aria-hidden />
            {isExportingCsv ? "导出中…" : "导出 CSV"}
          </button>
          <button
            data-testid="balance-analysis-workbook-export-button"
            type="button"
            className={toolbarStyles.baToolbarActionPrimary}
            onClick={onExportWorkbook}
            disabled={!selectedReportDate || isExportingWorkbook}
          >
            <FileExcelOutlined aria-hidden />
            {isExportingWorkbook ? "导出中…" : "导出 Workbook"}
          </button>
        </div>
      </div>
      <p data-testid="balance-analysis-page-subtitle" className={toolbarStyles.baToolbarSubtitle}>
        当前报告日正式口径下的资产、负债、净头寸与期限缺口。
      </p>
    </header>
  );
}
