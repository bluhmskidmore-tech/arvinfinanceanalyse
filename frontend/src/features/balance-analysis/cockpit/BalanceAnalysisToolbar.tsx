import {
  DownloadOutlined,
  FileExcelOutlined,
  ReloadOutlined,
} from "@ant-design/icons";

import type {
  BalancePageCalibration,
  BalancePositionScope,
} from "../../../api/contracts";
import { CalibrationBadge } from "../../../components/CalibrationBadge";
import type { BalanceAnalysisPageReadModel } from "../pages/balanceAnalysisPageModel";

type BalanceAnalysisToolbarProps = {
  reportDates: readonly string[];
  selectedReportDate: string;
  positionScope: BalancePositionScope;
  sourceBadge: BalanceAnalysisPageReadModel["sourceBadge"];
  calibration?: BalancePageCalibration | null;
  isRefreshing: boolean;
  isExportingCsv: boolean;
  isExportingWorkbook: boolean;
  onReportDateChange: (value: string) => void;
  onPositionScopeChange: (value: BalancePositionScope) => void;
  onRefresh: () => void;
  onExportCsv: () => void;
  onExportWorkbook: () => void;
};

/**
 * 首页标准包页头：20px 页题 + 12px 副题 + 模式徽标（无胶囊/大写宽字距），
 * 下方 32px 工具条（原生 select + 操作按钮）。
 */
export function BalanceAnalysisToolbar({
  reportDates,
  selectedReportDate,
  positionScope,
  sourceBadge,
  calibration,
  isRefreshing,
  isExportingCsv,
  isExportingWorkbook,
  onReportDateChange,
  onPositionScopeChange,
  onRefresh,
  onExportCsv,
  onExportWorkbook,
}: BalanceAnalysisToolbarProps) {
  const hasUnavailableSelectedDate = Boolean(
    selectedReportDate && !reportDates.includes(selectedReportDate),
  );
  return (
    <header data-testid="balance-analysis-filter-tray" className="balance-analysis-topbar">
      <div className="balance-analysis-topbar__head">
        <div className="balance-analysis-topbar__copy">
          <h1 data-testid="balance-analysis-page-title" className="balance-analysis-topbar__title">
            资产负债分析
          </h1>
          <p
            data-testid="balance-analysis-page-subtitle"
            className="balance-analysis-topbar__subtitle"
          >
            当前报告日正式口径下的资产、负债、净头寸与期限缺口。
          </p>
        </div>
        <div className="balance-analysis-topbar__badges">
          <CalibrationBadge calibration={calibration} />
          <span className="balance-analysis-topbar__mode-badge" data-tone={sourceBadge.tone}>
            {sourceBadge.label}
          </span>
        </div>
      </div>
      <div className="balance-analysis-topbar__controls">
        <label className="balance-analysis-topbar__field">
          <span className="balance-analysis-topbar__field-label">报告日</span>
          <select
            aria-label="balance-report-date"
            className="balance-analysis-topbar__select"
            value={selectedReportDate}
            onChange={(event) => onReportDateChange(event.target.value)}
          >
            {hasUnavailableSelectedDate ? (
              <option value={selectedReportDate} disabled>
                {`${selectedReportDate}（不可用）`}
              </option>
            ) : null}
            {reportDates.map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {reportDate}
              </option>
            ))}
          </select>
        </label>
        <label className="balance-analysis-topbar__field">
          <span className="balance-analysis-topbar__field-label">头寸范围</span>
          <select
            aria-label="balance-position-scope"
            className="balance-analysis-topbar__select"
            value={positionScope}
            onChange={(event) => onPositionScopeChange(event.target.value as BalancePositionScope)}
          >
            <option value="all">全部头寸</option>
            <option value="asset">资产</option>
            <option value="liability">负债</option>
          </select>
        </label>
        <label className="balance-analysis-topbar__field">
          <span className="balance-analysis-topbar__field-label">币种口径</span>
          <select
            aria-label="balance-currency-basis"
            className="balance-analysis-topbar__select"
            value="CNY"
            disabled
          >
            <option value="CNY">人民币（CNY）</option>
          </select>
        </label>
        <p
          data-testid="balance-analysis-currency-basis-note"
          className="balance-analysis-topbar__subtitle"
        >
          原币需逐币种明细，当前不做跨币种总量。
        </p>
        <div className="balance-analysis-topbar__actions">
          <button
            data-testid="balance-analysis-refresh-button"
            type="button"
            className="balance-analysis-btn"
            onClick={onRefresh}
            disabled={!selectedReportDate || isRefreshing}
          >
            <ReloadOutlined aria-hidden />
            {isRefreshing ? "刷新中…" : "刷新正式结果"}
          </button>
          <button
            data-testid="balance-analysis-export-button"
            type="button"
            className="balance-analysis-btn"
            onClick={onExportCsv}
            disabled={!selectedReportDate || isExportingCsv}
          >
            <DownloadOutlined aria-hidden />
            {isExportingCsv ? "导出中…" : "导出 CSV"}
          </button>
          <button
            data-testid="balance-analysis-workbook-export-button"
            type="button"
            className="balance-analysis-btn balance-analysis-btn--primary"
            onClick={onExportWorkbook}
            disabled={!selectedReportDate || isExportingWorkbook}
          >
            <FileExcelOutlined aria-hidden />
            {isExportingWorkbook ? "导出中…" : "导出 Workbook"}
          </button>
        </div>
      </div>
    </header>
  );
}
