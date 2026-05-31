import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApiClient } from "../../api/client";
import { apiQueryKeys } from "../../api/queryKeys";
import type {
  PnlByBusinessAnalysisDimension,
  PnlByBusinessAnalysisRow,
  PnlByBusinessManualAdjustmentPayload,
  PnlByBusinessManualAdjustmentRequest,
  PnlByBusinessMonthlyBucket,
  PnlByBusinessMonthlyItem,
  PnlByBusinessRow,
  PnlByBusinessYtdItem,
} from "../../api/contracts";
import { FilterBar } from "../../components/FilterBar";
import { KpiCard } from "../../components/KpiCard";
import { FormalResultMetaPanel } from "../../components/page/FormalResultMetaPanel";
import {
  AnalysisGrid,
  DataStatusStrip,
  EvidencePanel,
  KpiBand,
  KpiBandMetric,
  PageDecisionHero,
  PageFilterTray,
  PageSectionLead,
  PageStateSurface,
  PageV2Shell,
} from "../../components/page/PagePrimitives";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { formatAnnualizedYieldPctDisplay, inclusiveCalendarDays } from "./pnlByBusinessAnnualizedYield";
import { downloadPnlByBusinessExcel } from "./pnlByBusinessExport";
import {
  VIEW_MODE_SUBTITLES,
  buildPnlByBusinessPageModel,
  formatAnalysisYieldPct,
  formatAvgBalanceYi,
  formatAvgBalanceYiMetric,
  formatRatioPct,
  formatYuanAsWanUnit,
  isDetailZqtzBusinessRow,
  isParentZqtzBusinessRow,
  toneFromSigned,
} from "./pnlByBusinessPageModel";
import { resolveAdbAvgYuan } from "./zqtzAdbAvgRollup";
import "./PnlByBusinessPage.css";

function pnlKpiToneClassName(
  tone: "default" | "positive" | "negative" | "warning" | "error" | undefined,
): string {
  if (tone === "positive") {
    return "pnl-by-business-kpi-metric--positive";
  }
  if (tone === "negative") {
    return "pnl-by-business-kpi-metric--negative";
  }
  return "";
}

function numeric(raw: string | number | null | undefined): number | null {
  if (raw === null || raw === undefined || raw === "") {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

/** 与日均分析页明细表「日均(亿元)」列一致：两位小数，单位写在表头 */
const YUAN_PER_YI = 100_000_000;
const FTP_RATE_PCT = 1.6;
const FTP_RATE_RATIO = 0.016;
const ANALYSIS_QUERY_STALE_MS = 5 * 60 * 1000;

type ManualAdjustmentDraft = Pick<
  PnlByBusinessManualAdjustmentRequest,
  "manual_adjustment" | "approval_status" | "reason"
>;

const EMPTY_MANUAL_ADJUSTMENT_DRAFT: ManualAdjustmentDraft = {
  manual_adjustment: "",
  approval_status: "approved",
  reason: "",
};

function formatPnlWan(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return (value / 10_000).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function formatAdbAvgYiCell(yuan: number): string {
  return (yuan / YUAN_PER_YI).toFixed(2);
}

function formatYuanAsYiCell(raw: string | number | null | undefined): string {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return (value / YUAN_PER_YI).toFixed(2);
}

function formatAdjustmentStatus(status: string): string {
  if (status === "approved") {
    return "已批准";
  }
  if (status === "pending") {
    return "待确认";
  }
  if (status === "rejected") {
    return "已撤销";
  }
  return status || "-";
}

function formatAdjustmentEvent(eventType: string): string {
  if (eventType === "created") {
    return "新增";
  }
  if (eventType === "edited") {
    return "编辑";
  }
  if (eventType === "revoked") {
    return "撤销";
  }
  if (eventType === "restored") {
    return "恢复";
  }
  return eventType || "-";
}

function normalizeAdjustmentStatus(status: string): PnlByBusinessManualAdjustmentRequest["approval_status"] {
  if (status === "pending" || status === "rejected") {
    return status;
  }
  return "approved";
}

function annualizedYieldPctValue(
  totalPnl: string | number | null | undefined,
  avgBalance: number | undefined,
  calendarDays: number | null,
): number | null {
  const pnl = numeric(totalPnl);
  if (pnl === null || avgBalance === undefined || avgBalance <= 0 || !calendarDays || calendarDays <= 0) {
    return null;
  }
  return (pnl / avgBalance) * (365 / calendarDays) * 100;
}

function ftpValuesForYtdRow(
  totalPnl: string | number | null | undefined,
  avgBalance: number | undefined,
  calendarDays: number | null,
): { ftpCost: number | null; ftpNetPnl: number | null; ftpNetYieldPct: number | null } {
  const pnl = numeric(totalPnl);
  const annualizedYield = annualizedYieldPctValue(totalPnl, avgBalance, calendarDays);
  if (
    pnl === null ||
    annualizedYield === null ||
    avgBalance === undefined ||
    avgBalance <= 0 ||
    !calendarDays ||
    calendarDays <= 0
  ) {
    return { ftpCost: null, ftpNetPnl: null, ftpNetYieldPct: null };
  }
  const ftpCost = avgBalance * FTP_RATE_RATIO * (calendarDays / 365);
  return {
    ftpCost,
    ftpNetPnl: pnl - ftpCost,
    ftpNetYieldPct: annualizedYield - FTP_RATE_PCT,
  };
}

/** 单日 formal 接口 `yield_pct`：与后端 SQL 一致，为百分数点（如 10.14 表示 10.14%），非 0–1 占比 */
function formatFormalYieldPctPoints(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return `${value.toFixed(2)}%`;
}

function buildYtdRangeFromResultDates(
  periodStartDate: string | null | undefined,
  periodEndDate: string | null | undefined,
): { startDate: string; endDate: string } | null {
  if (!periodStartDate || !periodEndDate) {
    return null;
  }
  if (inclusiveCalendarDays(periodStartDate, periodEndDate) === null) {
    return null;
  }
  return {
    startDate: periodStartDate,
    endDate: periodEndDate,
  };
}

function BusinessRowsTable({
  rows,
  adbAvgByBusinessType,
  ytdCalendarDays,
  selectedRowKey,
  onSelectRow,
}: {
  rows: PnlByBusinessYtdItem[];
  adbAvgByBusinessType: Map<string, number>;
  ytdCalendarDays: number | null;
  selectedRowKey: string | null;
  onSelectRow: (row: PnlByBusinessYtdItem) => void;
}) {
  const parentRows = useMemo(() => rows.filter(isParentZqtzBusinessRow), [rows]);
  const detailRows = useMemo(() => rows.filter(isDetailZqtzBusinessRow), [rows]);

  const parentFooter = useMemo(() => {
    let interest = 0;
    let fairValue = 0;
    let capital = 0;
    let manual = 0;
    let totalPnl = 0;
    let assets = 0;
    let adbSum = 0;
    for (const row of parentRows) {
      interest += numeric(row.interest_income) ?? 0;
      fairValue += numeric(row.fair_value_change) ?? 0;
      capital += numeric(row.capital_gain) ?? 0;
      manual += numeric(row.manual_adjustment) ?? 0;
      totalPnl += numeric(row.total_pnl) ?? 0;
      assets += row.assets_count;
      const adb = resolveAdbAvgYuan(row.business_type, adbAvgByBusinessType);
      if (adb !== undefined && adb > 0) {
        adbSum += adb;
      }
    }
    const adbCell = adbSum > 0 ? formatAdbAvgYiCell(adbSum) : "-";
    const ftp = ftpValuesForYtdRow(totalPnl, adbSum > 0 ? adbSum : undefined, ytdCalendarDays);
    return {
      interest,
      fairValue,
      capital,
      manual,
      totalPnl,
      assets,
      adbSum,
      adbCell,
      yieldPct: "—",
      ftpNetPnl: ftp.ftpNetPnl,
      ftpNetYieldPct: ftp.ftpNetYieldPct,
    };
  }, [parentRows, adbAvgByBusinessType, ytdCalendarDays]);

  const renderRow = (row: PnlByBusinessYtdItem, selectable: boolean) => {
    const adbAvg = resolveAdbAvgYuan(row.business_type, adbAvgByBusinessType);
    const avgDisplay = adbAvg !== undefined && adbAvg > 0 ? formatAdbAvgYiCell(adbAvg) : "-";
    const ftp = ftpValuesForYtdRow(row.total_pnl, adbAvg, ytdCalendarDays);
    return (
      <tr
        key={row.row_key}
        className={selectable && row.row_key === selectedRowKey ? "pnl-by-business-table-row-selected" : undefined}
        onClick={selectable ? () => onSelectRow(row) : undefined}
        onKeyDown={
          selectable
            ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectRow(row);
                }
              }
            : undefined
        }
        role={selectable ? "button" : undefined}
        tabIndex={selectable ? 0 : undefined}
      >
        <td>{row.business_type}</td>
        <td>{avgDisplay}</td>
        <td>{formatPnlWan(row.interest_income)}</td>
        <td>{formatPnlWan(row.fair_value_change)}</td>
        <td>{formatPnlWan(row.capital_gain)}</td>
        <td>{formatPnlWan(row.manual_adjustment)}</td>
        <td>{formatPnlWan(row.total_pnl)}</td>
        <td>{formatAnnualizedYieldPctDisplay(numeric(row.total_pnl), adbAvg, ytdCalendarDays)}</td>
        <td>{formatPnlWan(ftp.ftpNetPnl)}</td>
        <td>{formatAnalysisYieldPct(ftp.ftpNetYieldPct)}</td>
        <td>{formatRatioPct(row.proportion)}</td>
        <td>{row.assets_count}</td>
      </tr>
    );
  };

  return (
    <>
      <div className="pnl-by-business-table-shell" data-testid="pnl-by-business-table">
        <table className="pnl-by-business-table">
          <thead>
            <tr>
              <th>业务种类</th>
              <th>日均(亿元)</th>
              <th>利息收入（万元）</th>
              <th>公允价值变动（万元）</th>
              <th>资本利得（万元）</th>
              <th>手工调整（万元）</th>
              <th>合计损益（万元）</th>
              <th>年化收益率</th>
              <th>FTP后收益（万元）</th>
              <th>FTP后收益率</th>
              <th>占比</th>
              <th>资产数</th>
            </tr>
          </thead>
          <tbody>{parentRows.map((row) => renderRow(row, true))}</tbody>
          {parentRows.length > 0 ? (
            <tfoot>
              <tr data-testid="pnl-by-business-table-parent-footer">
                <td className="pnl-by-business-table-footer-cell">父级汇总</td>
                <td className="pnl-by-business-table-footer-cell">{parentFooter.adbCell}</td>
                <td className="pnl-by-business-table-footer-cell">{formatPnlWan(parentFooter.interest)}</td>
                <td className="pnl-by-business-table-footer-cell">{formatPnlWan(parentFooter.fairValue)}</td>
                <td className="pnl-by-business-table-footer-cell">{formatPnlWan(parentFooter.capital)}</td>
                <td className="pnl-by-business-table-footer-cell">{formatPnlWan(parentFooter.manual)}</td>
                <td className="pnl-by-business-table-footer-cell">{formatPnlWan(parentFooter.totalPnl)}</td>
                <td className="pnl-by-business-table-footer-cell">{parentFooter.yieldPct}</td>
                <td className="pnl-by-business-table-footer-cell">{formatPnlWan(parentFooter.ftpNetPnl)}</td>
                <td className="pnl-by-business-table-footer-cell">
                  {formatAnalysisYieldPct(parentFooter.ftpNetYieldPct)}
                </td>
                <td className="pnl-by-business-table-footer-cell">—</td>
                <td className="pnl-by-business-table-footer-cell">{parentFooter.assets}</td>
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>
      {detailRows.length > 0 ? (
        <div className="pnl-by-business-detail-block" data-testid="pnl-by-business-detail-table">
          <div className="pnl-by-business-detail-heading">
            <h3>其中项明细</h3>
            <p>这些行为父级分类的拆解项，不参与父级汇总和资产数加总。</p>
          </div>
          <div className="pnl-by-business-table-shell">
            <table className="pnl-by-business-table">
              <thead>
                <tr>
                  <th>业务种类</th>
                  <th>日均(亿元)</th>
                  <th>利息收入（万元）</th>
                  <th>公允价值变动（万元）</th>
                  <th>资本利得（万元）</th>
                  <th>手工调整（万元）</th>
                  <th>合计损益（万元）</th>
                  <th>年化收益率</th>
                  <th>FTP后收益（万元）</th>
                  <th>FTP后收益率</th>
                  <th>占比</th>
                  <th>资产数</th>
                </tr>
              </thead>
              <tbody>{detailRows.map((row) => renderRow(row, false))}</tbody>
            </table>
          </div>
        </div>
      ) : null}
    </>
  );
}

function MonthlyBusinessRowsTable({ month }: { month: PnlByBusinessMonthlyBucket }) {
  const parentRows = month.items.filter(isParentZqtzBusinessRow);
  const detailRows = month.items.filter(isDetailZqtzBusinessRow);
  return (
    <>
      <div
        className="pnl-by-business-table-shell pnl-by-business-month-table-shell"
        data-testid={`pnl-by-business-monthly-table-${month.month_key}`}
      >
        <table className="pnl-by-business-table">
          <thead>
            <tr>
              <th>业务种类</th>
              <th>日均(亿元)</th>
              <th>期末余额(亿元)</th>
              <th>利息收入（万元）</th>
              <th>公允价值变动（万元）</th>
              <th>资本利得（万元）</th>
              <th>手工调整（万元）</th>
              <th>合计损益（万元）</th>
              <th>年化收益率</th>
              <th>FTP后收益（万元）</th>
              <th>FTP后收益率</th>
              <th>占比</th>
              <th>资产数</th>
            </tr>
          </thead>
          <tbody>
            {parentRows.map((row: PnlByBusinessMonthlyItem) => (
              <tr key={row.row_key}>
                <td>{row.business_type}</td>
                <td>{formatAvgBalanceYi(row.avg_balance)}</td>
                <td>{formatYuanAsYiCell(row.current_balance)}</td>
                <td>{formatPnlWan(row.interest_income)}</td>
                <td>{formatPnlWan(row.fair_value_change)}</td>
                <td>{formatPnlWan(row.capital_gain)}</td>
                <td>{formatPnlWan(row.manual_adjustment)}</td>
                <td>{formatPnlWan(row.total_pnl)}</td>
                <td>{formatAnalysisYieldPct(row.annualized_yield_pct)}</td>
                <td>{formatPnlWan(row.ftp_net_pnl)}</td>
                <td>{formatAnalysisYieldPct(row.ftp_net_annualized_yield_pct)}</td>
                <td>{formatRatioPct(row.proportion)}</td>
                <td>{row.asset_count}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td className="pnl-by-business-table-footer-cell">父级汇总</td>
              <td className="pnl-by-business-table-footer-cell">{formatAvgBalanceYi(month.summary.avg_balance)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatYuanAsYiCell(month.summary.current_balance)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(month.summary.interest_income)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(month.summary.fair_value_change)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(month.summary.capital_gain)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(month.summary.manual_adjustment)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(month.summary.total_pnl)}</td>
              <td className="pnl-by-business-table-footer-cell">
                {formatAnalysisYieldPct(month.summary.annualized_yield_pct)}
              </td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(month.summary.ftp_net_pnl)}</td>
              <td className="pnl-by-business-table-footer-cell">
                {formatAnalysisYieldPct(month.summary.ftp_net_annualized_yield_pct)}
              </td>
              <td className="pnl-by-business-table-footer-cell">—</td>
              <td className="pnl-by-business-table-footer-cell">{month.summary.asset_count}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      {detailRows.length > 0 ? (
        <div
          className="pnl-by-business-detail-block"
          data-testid={`pnl-by-business-monthly-detail-table-${month.month_key}`}
        >
          <div className="pnl-by-business-detail-heading">
            <h3>其中项明细</h3>
            <p>这些行为父级分类的拆解项，不参与父级汇总和资产数加总。</p>
          </div>
          <div className="pnl-by-business-table-shell pnl-by-business-month-table-shell">
            <table className="pnl-by-business-table">
              <thead>
                <tr>
                  <th>业务种类</th>
                  <th>日均(亿元)</th>
                  <th>期末余额(亿元)</th>
                  <th>利息收入（万元）</th>
                  <th>公允价值变动（万元）</th>
                  <th>资本利得（万元）</th>
                  <th>手工调整（万元）</th>
                  <th>合计损益（万元）</th>
                  <th>年化收益率</th>
                  <th>FTP后收益（万元）</th>
                  <th>FTP后收益率</th>
                  <th>占比</th>
                  <th>资产数</th>
                </tr>
              </thead>
              <tbody>
                {detailRows.map((row: PnlByBusinessMonthlyItem) => (
                  <tr key={row.row_key}>
                    <td>{row.business_type}</td>
                    <td>{formatAvgBalanceYi(row.avg_balance)}</td>
                    <td>{formatYuanAsYiCell(row.current_balance)}</td>
                    <td>{formatPnlWan(row.interest_income)}</td>
                    <td>{formatPnlWan(row.fair_value_change)}</td>
                    <td>{formatPnlWan(row.capital_gain)}</td>
                    <td>{formatPnlWan(row.manual_adjustment)}</td>
                    <td>{formatPnlWan(row.total_pnl)}</td>
                    <td>{formatAnalysisYieldPct(row.annualized_yield_pct)}</td>
                    <td>{formatPnlWan(row.ftp_net_pnl)}</td>
                    <td>{formatAnalysisYieldPct(row.ftp_net_annualized_yield_pct)}</td>
                    <td>{formatRatioPct(row.proportion)}</td>
                    <td>{row.asset_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </>
  );
}

function MonthlyBusinessBreakdownPanel({
  months,
  isLoading,
  isError,
  openMonthKeys,
  onToggleMonth,
  title = "月报业务种类明细",
  description = "每个月单独展开，查看该月损益、月度日均、期末余额与 FTP 后收益。",
  forceOpenSingleMonth = false,
}: {
  months: PnlByBusinessMonthlyBucket[];
  isLoading: boolean;
  isError: boolean;
  openMonthKeys: Set<string>;
  onToggleMonth: (monthKey: string) => void;
  title?: string;
  description?: string;
  forceOpenSingleMonth?: boolean;
}) {
  return (
    <section
      className="pnl-by-business-analysis-block pnl-by-business-monthly-section"
      data-testid="pnl-by-business-monthly-breakdown"
    >
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        {!isLoading && !isError && months.length > 0 ? (
          <span className="pnl-by-business-section-pill">{months.length} 个月</span>
        ) : null}
      </div>
      {isLoading ? (
        <div className="pnl-by-business-analysis-state">加载中</div>
      ) : isError ? (
        <div className="pnl-by-business-analysis-state">月度业务种类数据读取失败</div>
      ) : months.length === 0 ? (
        <div className="pnl-by-business-analysis-state">暂无月度业务种类数据</div>
      ) : (
        <div className="pnl-by-business-monthly-list">
          {months.map((month) => {
            const isOpen = openMonthKeys.has(month.month_key) || (forceOpenSingleMonth && months.length === 1);
            return (
              <div
                className={
                  isOpen
                    ? "pnl-by-business-month-row pnl-by-business-month-row-open"
                    : "pnl-by-business-month-row"
                }
                key={month.month_key}
              >
                <button
                  type="button"
                  className="pnl-by-business-month-button"
                  aria-expanded={isOpen}
                  onClick={() => onToggleMonth(month.month_key)}
                >
                  <span className="pnl-by-business-month-chevron">{isOpen ? "⌄" : "›"}</span>
                  <span className="pnl-by-business-month-title">
                    <strong>{month.month_key}</strong>
                    <span>
                      {month.period_start_date} - {month.period_end_date} · {month.calendar_days} 天
                    </span>
                  </span>
                  <span className="pnl-by-business-month-metrics">
                    <span>
                      <small>日均余额</small>
                      <strong>{formatAvgBalanceYiMetric(month.summary.avg_balance)}</strong>
                    </span>
                    <span>
                      <small>总损益</small>
                      <strong>{formatPnlWan(month.summary.total_pnl)} 万元</strong>
                    </span>
                    <span>
                      <small>年化收益率</small>
                      <strong>{formatAnalysisYieldPct(month.summary.annualized_yield_pct)}</strong>
                    </span>
                    <span>
                      <small>FTP后收益率</small>
                      <strong>{formatAnalysisYieldPct(month.summary.ftp_net_annualized_yield_pct)}</strong>
                    </span>
                    <span>
                      <small>资产数</small>
                      <strong>{month.summary.asset_count}</strong>
                    </span>
                  </span>
                </button>
                {isOpen ? (
                  <div className="pnl-by-business-month-panel">
                    <MonthlyBusinessRowsTable month={month} />
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function PnlByBusinessManualAdjustmentPanel({
  rows,
  selectedReportDate,
  selectedBusinessRow,
  selectedRowKey,
  draft,
  editingAdjustmentId,
  adjustmentError,
  isLoading,
  isSaving,
  isActionBusy,
  adjustments,
  events,
  onSelectRowKey,
  onDraftChange,
  onSubmit,
  onEdit,
  onCancelEdit,
  onRevoke,
  onRestore,
}: {
  rows: PnlByBusinessYtdItem[];
  selectedReportDate: string;
  selectedBusinessRow: PnlByBusinessYtdItem | undefined;
  selectedRowKey: string;
  draft: ManualAdjustmentDraft;
  editingAdjustmentId: string | null;
  adjustmentError: string;
  isLoading: boolean;
  isSaving: boolean;
  isActionBusy: boolean;
  adjustments: PnlByBusinessManualAdjustmentPayload[];
  events: PnlByBusinessManualAdjustmentPayload[];
  onSelectRowKey: (rowKey: string) => void;
  onDraftChange: <K extends keyof ManualAdjustmentDraft>(key: K, value: ManualAdjustmentDraft[K]) => void;
  onSubmit: () => void;
  onEdit: (item: PnlByBusinessManualAdjustmentPayload) => void;
  onCancelEdit: () => void;
  onRevoke: (adjustmentId: string) => void;
  onRestore: (adjustmentId: string) => void;
}) {
  return (
    <section
      className="pnl-by-business-analysis-block pnl-by-business-adjustment-panel"
      data-testid="pnl-by-business-manual-adjustments"
    >
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>手工调整</h2>
          <p>
            {selectedReportDate} · {selectedBusinessRow?.business_type ?? "-"}
          </p>
        </div>
        <span className="pnl-by-business-section-pill">{adjustments.length} 当前</span>
      </div>

      <div className="pnl-by-business-adjustment-form">
        <label className="pnl-by-business-filter-label">
          业务种类
          <select
            aria-label="pnl-by-business-adjustment-row"
            className="pnl-by-business-control"
            value={selectedRowKey}
            onChange={(event) => onSelectRowKey(event.target.value)}
          >
            {rows.map((row) => (
              <option key={row.row_key} value={row.row_key}>
                {row.business_type}
              </option>
            ))}
          </select>
        </label>
        <label className="pnl-by-business-filter-label">
          调整金额（元）
          <input
            aria-label="pnl-by-business-adjustment-amount"
            className="pnl-by-business-control"
            inputMode="decimal"
            value={draft.manual_adjustment}
            onChange={(event) => onDraftChange("manual_adjustment", event.target.value)}
          />
        </label>
        <label className="pnl-by-business-filter-label">
          审批状态
          <select
            aria-label="pnl-by-business-adjustment-status"
            className="pnl-by-business-control"
            value={draft.approval_status}
            onChange={(event) =>
              onDraftChange(
                "approval_status",
                event.target.value as PnlByBusinessManualAdjustmentRequest["approval_status"],
              )
            }
          >
            <option value="approved">已批准</option>
            <option value="pending">待确认</option>
            <option value="rejected">已撤销</option>
          </select>
        </label>
        <label className="pnl-by-business-filter-label pnl-by-business-adjustment-reason-field">
          原因
          <input
            aria-label="pnl-by-business-adjustment-reason"
            className="pnl-by-business-control"
            value={draft.reason ?? ""}
            onChange={(event) => onDraftChange("reason", event.target.value)}
          />
        </label>
        <div className="pnl-by-business-adjustment-actions">
          <button
            type="button"
            className="pnl-by-business-action-button pnl-by-business-action-button-primary"
            disabled={isSaving || !selectedReportDate || !selectedRowKey}
            onClick={onSubmit}
          >
            {editingAdjustmentId ? "保存编辑" : "保存调整"}
          </button>
          {editingAdjustmentId ? (
            <button
              type="button"
              className="pnl-by-business-action-button"
              disabled={isSaving}
              onClick={onCancelEdit}
            >
              取消
            </button>
          ) : null}
        </div>
      </div>
      {adjustmentError ? <div className="pnl-by-business-adjustment-error">{adjustmentError}</div> : null}

      <div className="pnl-by-business-adjustment-columns">
        <div className="pnl-by-business-adjustment-list">
          <div className="pnl-by-business-adjustment-list-heading">
            <strong>当前调整</strong>
            <span>{isLoading ? "读取中" : `${adjustments.length} 条`}</span>
          </div>
          {isLoading ? (
            <div className="pnl-by-business-analysis-state">加载中</div>
          ) : adjustments.length === 0 ? (
            <div className="pnl-by-business-analysis-state">暂无手工调整</div>
          ) : (
            <div className="pnl-by-business-table-shell pnl-by-business-adjustment-table-shell">
              <table className="pnl-by-business-table pnl-by-business-adjustment-table">
                <thead>
                  <tr>
                    <th>业务种类</th>
                    <th>金额（万元）</th>
                    <th>状态</th>
                    <th>原因</th>
                    <th>最近事件</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {adjustments.map((item) => (
                    <tr key={`adjustment-current-${item.adjustment_id}`}>
                      <td>{item.business_type || item.row_key}</td>
                      <td>{formatPnlWan(item.manual_adjustment)}</td>
                      <td>{formatAdjustmentStatus(item.approval_status)}</td>
                      <td>{item.reason || "-"}</td>
                      <td>{formatAdjustmentEvent(item.event_type)}</td>
                      <td>
                        <div className="pnl-by-business-row-actions">
                          <button type="button" onClick={() => onEdit(item)} disabled={isActionBusy}>
                            编辑
                          </button>
                          <button
                            type="button"
                            onClick={() => onRevoke(item.adjustment_id)}
                            disabled={isActionBusy || item.approval_status !== "approved"}
                          >
                            撤销
                          </button>
                          <button
                            type="button"
                            onClick={() => onRestore(item.adjustment_id)}
                            disabled={isActionBusy || item.approval_status !== "rejected"}
                          >
                            恢复
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="pnl-by-business-adjustment-list">
          <div className="pnl-by-business-adjustment-list-heading">
            <strong>历史事件</strong>
            <span>{isLoading ? "读取中" : `${events.length} 条`}</span>
          </div>
          {isLoading ? (
            <div className="pnl-by-business-analysis-state">加载中</div>
          ) : events.length === 0 ? (
            <div className="pnl-by-business-analysis-state">暂无历史事件</div>
          ) : (
            <div className="pnl-by-business-table-shell pnl-by-business-adjustment-table-shell">
              <table className="pnl-by-business-table pnl-by-business-adjustment-table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>事件</th>
                    <th>业务种类</th>
                    <th>金额（万元）</th>
                    <th>状态</th>
                    <th>原因</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((item) => (
                    <tr key={`adjustment-event-${item.adjustment_id}-${item.event_type}-${item.created_at}`}>
                      <td>{item.created_at}</td>
                      <td>{formatAdjustmentEvent(item.event_type)}</td>
                      <td>{item.business_type || item.row_key}</td>
                      <td>{formatPnlWan(item.manual_adjustment)}</td>
                      <td>{formatAdjustmentStatus(item.approval_status)}</td>
                      <td>{item.reason || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

type PnlByBusinessViewMode = "monthly" | "ytd" | "formal";

const ANALYSIS_DIMENSION_LABELS: Record<PnlByBusinessAnalysisDimension, string> = {
  monthly: "月份",
  portfolio: "组合",
  accounting: "会计分类",
  cost_center: "成本中心",
  instrument: "资产明细",
  bond_bucket: "债券四类",
  bond_bucket_monthly: "四类月度",
};

function FormalBusinessRowsTable({ rows }: { rows: PnlByBusinessRow[] }) {
  const footer = useMemo(() => {
    let interest = 0;
    let fairValue = 0;
    let capital = 0;
    let manual = 0;
    let totalPnl = 0;
    let scale = 0;
    let pnlRows = 0;
    for (const row of rows) {
      interest += numeric(row.interest_income_514) ?? 0;
      fairValue += numeric(row.fair_value_change_516) ?? 0;
      capital += numeric(row.capital_gain_517) ?? 0;
      manual += numeric(row.manual_adjustment) ?? 0;
      totalPnl += numeric(row.total_pnl) ?? 0;
      scale += numeric(row.scale_amount) ?? 0;
      pnlRows += row.pnl_row_count;
    }
    return { interest, fairValue, capital, manual, totalPnl, scale, pnlRows };
  }, [rows]);

  return (
    <div className="pnl-by-business-table-shell" data-testid="pnl-by-business-formal-table">
      <table className="pnl-by-business-table">
        <thead>
          <tr>
            <th>业务种类（primary）</th>
            <th>币种</th>
            <th>规模(亿元)</th>
            <th>利息收入（万元）</th>
            <th>公允价值变动（万元）</th>
            <th>资本利得（万元）</th>
            <th>手工调整（万元）</th>
            <th>合计损益（万元）</th>
            <th>表内收益率</th>
            <th>损益行数</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.report_date}-${row.business_type_primary}-${row.currency_basis}`}>
              <td>{row.business_type_primary}</td>
              <td>{row.currency_basis}</td>
              <td>{formatAdbAvgYiCell(numeric(row.scale_amount) ?? 0)}</td>
              <td>{formatPnlWan(row.interest_income_514)}</td>
              <td>{formatPnlWan(row.fair_value_change_516)}</td>
              <td>{formatPnlWan(row.capital_gain_517)}</td>
              <td>{formatPnlWan(row.manual_adjustment)}</td>
              <td>{formatPnlWan(row.total_pnl)}</td>
              <td>{formatFormalYieldPctPoints(row.yield_pct)}</td>
              <td>{row.pnl_row_count}</td>
            </tr>
          ))}
        </tbody>
        {rows.length > 0 ? (
          <tfoot>
            <tr data-testid="pnl-by-business-formal-table-footer">
              <td className="pnl-by-business-table-footer-cell">全表合计</td>
              <td className="pnl-by-business-table-footer-cell">—</td>
              <td className="pnl-by-business-table-footer-cell">{formatAdbAvgYiCell(footer.scale)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(footer.interest)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(footer.fairValue)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(footer.capital)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(footer.manual)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(footer.totalPnl)}</td>
              <td className="pnl-by-business-table-footer-cell">—</td>
              <td className="pnl-by-business-table-footer-cell">{footer.pnlRows}</td>
            </tr>
          </tfoot>
        ) : null}
      </table>
    </div>
  );
}

function DriverOverviewPanel({
  rows,
  adbAvgByBusinessType,
  ytdCalendarDays,
}: {
  rows: PnlByBusinessYtdItem[];
  adbAvgByBusinessType: Map<string, number>;
  ytdCalendarDays: number | null;
}) {
  const topRows = [...rows]
    .filter((row) => (numeric(row.total_pnl) ?? 0) > 0)
    .sort((left, right) => (numeric(right.total_pnl) ?? 0) - (numeric(left.total_pnl) ?? 0))
    .slice(0, 5);
  const bottomRows = [...rows]
    .filter((row) => (numeric(row.total_pnl) ?? 0) < 0)
    .sort((left, right) => (numeric(left.total_pnl) ?? 0) - (numeric(right.total_pnl) ?? 0))
    .slice(0, 5);
  const yieldRows = [...rows]
    .map((row) => {
      const adbAvg = resolveAdbAvgYuan(row.business_type, adbAvgByBusinessType);
      return { row, yieldPct: annualizedYieldPctValue(row.total_pnl, adbAvg, ytdCalendarDays) };
    })
    .filter((item) => item.yieldPct !== null)
    .sort((left, right) => Math.abs(right.yieldPct ?? 0) - Math.abs(left.yieldPct ?? 0))
    .slice(0, 5);
  const gapRows = [...rows]
    .map((row) => {
      const adbAvg = resolveAdbAvgYuan(row.business_type, adbAvgByBusinessType);
      const current = numeric(row.current_balance) ?? 0;
      return { row, gap: adbAvg !== undefined ? current - adbAvg : null };
    })
    .filter((item) => item.gap !== null)
    .sort((left, right) => Math.abs(right.gap ?? 0) - Math.abs(left.gap ?? 0))
    .slice(0, 5);

  return (
    <section className="pnl-by-business-analysis-block" data-testid="pnl-by-business-driver-overview">
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>驱动概览</h2>
          <p>按 YTD 损益、分项、年化收益率和日均/期末差异看业务种类贡献。</p>
        </div>
      </div>
      <div className="pnl-by-business-driver-grid">
        <div className="pnl-by-business-mini-table">
          <h3>Top 贡献</h3>
          <table>
            <tbody>
              {topRows.length > 0 ? (
                topRows.map((row) => (
                  <tr key={row.row_key}>
                    <td>{row.business_type}</td>
                    <td>{formatPnlWan(row.total_pnl)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={2}>暂无正贡献</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="pnl-by-business-mini-table">
          <h3>Bottom 拖累</h3>
          <table>
            <tbody>
              {bottomRows.length > 0 ? (
                bottomRows.map((row) => (
                  <tr key={row.row_key}>
                    <td>{row.business_type}</td>
                    <td>{formatPnlWan(row.total_pnl)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={2}>暂无负贡献</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="pnl-by-business-mini-table">
          <h3>收益率排行</h3>
          <table>
            <tbody>
              {yieldRows.length > 0 ? (
                yieldRows.map(({ row, yieldPct }) => (
                  <tr key={row.row_key}>
                    <td>{row.business_type}</td>
                    <td>{formatAnalysisYieldPct(yieldPct)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={2}>日均缺失</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="pnl-by-business-mini-table">
          <h3>日均 vs 期末</h3>
          <table>
            <tbody>
              {gapRows.length > 0 ? (
                gapRows.map(({ row, gap }) => (
                  <tr key={row.row_key}>
                    <td>{row.business_type}</td>
                    <td>{formatYuanAsYiCell(gap ?? 0)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={2}>日均缺失</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function AnalysisRowsTable({
  rows,
  dimension,
  testId = "pnl-by-business-analysis-table",
}: {
  rows: PnlByBusinessAnalysisRow[];
  dimension: PnlByBusinessAnalysisDimension;
  testId?: string;
}) {
  return (
    <div className="pnl-by-business-table-shell" data-testid={testId}>
      <table className="pnl-by-business-table">
        <thead>
          <tr>
            <th>{ANALYSIS_DIMENSION_LABELS[dimension]}</th>
            <th>日均(亿元)</th>
            <th>期末余额(亿元)</th>
            <th>利息收入（万元）</th>
            <th>公允价值变动（万元）</th>
            <th>资本利得（万元）</th>
            <th>手工调整（万元）</th>
            <th>合计损益（万元）</th>
            <th>年化收益率</th>
            <th>FTP成本（万元）</th>
            <th>FTP后收益（万元）</th>
            <th>FTP后收益率</th>
            <th>资产数</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.dimension_key}>
              <td>{row.dimension_label}</td>
              <td>{formatAvgBalanceYi(row.avg_balance)}</td>
              <td>{formatYuanAsYiCell(row.current_balance)}</td>
              <td>{formatPnlWan(row.interest_income)}</td>
              <td>{formatPnlWan(row.fair_value_change)}</td>
              <td>{formatPnlWan(row.capital_gain)}</td>
              <td>{formatPnlWan(row.manual_adjustment)}</td>
              <td>{formatPnlWan(row.total_pnl)}</td>
              <td>{formatAnalysisYieldPct(row.annualized_yield_pct)}</td>
              <td>{formatPnlWan(row.ftp_cost)}</td>
              <td>{formatPnlWan(row.ftp_net_pnl)}</td>
              <td>{formatAnalysisYieldPct(row.ftp_net_annualized_yield_pct)}</td>
              <td>{row.asset_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BondBucketAnalysisPanel({
  rows,
  isLoading,
  isError,
}: {
  rows: PnlByBusinessAnalysisRow[];
  isLoading: boolean;
  isError: boolean;
}) {
  return (
    <section className="pnl-by-business-analysis-block" data-testid="pnl-by-business-bond-bucket-analysis">
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>债券四类统计</h2>
          <p>按利率债、信用债、金融债、其它债券归一次类，FTP 年化利率固定为 1.6%。</p>
        </div>
      </div>
      {isLoading ? (
        <div className="pnl-by-business-analysis-state">加载中</div>
      ) : isError ? (
        <div className="pnl-by-business-analysis-state">债券四类数据读取失败</div>
      ) : rows.length === 0 ? (
        <div className="pnl-by-business-analysis-state">暂无债券四类数据</div>
      ) : (
        <AnalysisRowsTable rows={rows} dimension="bond_bucket" testId="pnl-by-business-bond-bucket-table" />
      )}
    </section>
  );
}

function FtpBridgePanel({
  selectedRow,
  adbAvgByBusinessType,
  ytdCalendarDays,
}: {
  selectedRow: PnlByBusinessYtdItem | undefined;
  adbAvgByBusinessType: Map<string, number>;
  ytdCalendarDays: number | null;
}) {
  const avgBalance = selectedRow ? resolveAdbAvgYuan(selectedRow.business_type, adbAvgByBusinessType) : undefined;
  const ftp = ftpValuesForYtdRow(selectedRow?.total_pnl, avgBalance, ytdCalendarDays);
  return (
    <section className="pnl-by-business-analysis-block" data-testid="pnl-by-business-ftp-bridge">
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>FTP后收益桥</h2>
          <p>{selectedRow?.business_type ?? "-"} · FTP 年化利率 1.6%</p>
        </div>
      </div>
      <div className="pnl-by-business-analysis-kpis">
        <KpiCard
          label="合计损益"
          value={formatYuanAsWanUnit(selectedRow?.total_pnl)}
          detail="扣 FTP 前"
          tone={toneFromSigned(selectedRow?.total_pnl)}
        />
        <KpiCard
          label="FTP成本"
          value={formatYuanAsWanUnit(ftp.ftpCost)}
          detail={avgBalance && avgBalance > 0 ? "日均 × 1.6%" : "日均缺失"}
          tone={ftp.ftpCost && ftp.ftpCost > 0 ? "negative" : "default"}
        />
        <KpiCard
          label="FTP后收益"
          value={formatYuanAsWanUnit(ftp.ftpNetPnl)}
          detail="合计损益 - FTP成本"
          tone={toneFromSigned(ftp.ftpNetPnl)}
        />
        <KpiCard
          label="FTP后收益率"
          value={formatAnalysisYieldPct(ftp.ftpNetYieldPct)}
          detail="年化收益率 - 1.6%"
          tone={toneFromSigned(ftp.ftpNetYieldPct)}
        />
      </div>
    </section>
  );
}

function BondBucketMonthlyPanel({
  rows,
  isLoading,
  isError,
}: {
  rows: PnlByBusinessAnalysisRow[];
  isLoading: boolean;
  isError: boolean;
}) {
  return (
    <section className="pnl-by-business-analysis-block" data-testid="pnl-by-business-bond-bucket-monthly">
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>四类债券月度趋势</h2>
          <p>按月观察利率债、信用债、金融债和其它债券的 FTP 后收益变化。</p>
        </div>
      </div>
      {isLoading ? (
        <div className="pnl-by-business-analysis-state">加载中</div>
      ) : isError ? (
        <div className="pnl-by-business-analysis-state">四类债券月度趋势读取失败</div>
      ) : rows.length === 0 ? (
        <div className="pnl-by-business-analysis-state">暂无四类债券月度趋势</div>
      ) : (
        <AnalysisRowsTable
          rows={rows}
          dimension="bond_bucket_monthly"
          testId="pnl-by-business-bond-bucket-monthly-table"
        />
      )}
    </section>
  );
}

function NegativeFtpListPanel({
  rows,
  isLoading,
  isError,
}: {
  rows: PnlByBusinessAnalysisRow[];
  isLoading: boolean;
  isError: boolean;
}) {
  const negativeRows = rows
    .filter((row) => (numeric(row.ftp_net_pnl) ?? 0) < 0)
    .sort((left, right) => (numeric(left.ftp_net_pnl) ?? 0) - (numeric(right.ftp_net_pnl) ?? 0))
    .slice(0, 10);
  return (
    <section className="pnl-by-business-analysis-block" data-testid="pnl-by-business-negative-ftp-list">
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>负FTP后收益清单</h2>
          <p>筛出扣除 1.6% FTP 后为负的资产明细，优先看拖累最大的项目。</p>
        </div>
      </div>
      {isLoading ? (
        <div className="pnl-by-business-analysis-state">加载中</div>
      ) : isError ? (
        <div className="pnl-by-business-analysis-state">负 FTP 后收益清单读取失败</div>
      ) : negativeRows.length === 0 ? (
        <div className="pnl-by-business-analysis-state">暂无 FTP 后收益为负的资产</div>
      ) : (
        <AnalysisRowsTable rows={negativeRows} dimension="instrument" testId="pnl-by-business-negative-ftp-table" />
      )}
    </section>
  );
}

export default function PnlByBusinessPage() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [viewMode, setViewMode] = useState<PnlByBusinessViewMode>("monthly");
  const [selectedBusinessKey, setSelectedBusinessKey] = useState<string | null>(null);
  const [analysisDimension, setAnalysisDimension] = useState<PnlByBusinessAnalysisDimension>("monthly");
  const [analysisLoadStage, setAnalysisLoadStage] = useState(0);
  const [openMonthlyKeys, setOpenMonthlyKeys] = useState<Set<string>>(() => new Set());
  const [editingAdjustmentId, setEditingAdjustmentId] = useState<string | null>(null);
  const [adjustmentDraft, setAdjustmentDraft] = useState<ManualAdjustmentDraft>(() => ({
    ...EMPTY_MANUAL_ADJUSTMENT_DRAFT,
  }));
  const [adjustmentError, setAdjustmentError] = useState("");
  const [exportError, setExportError] = useState("");
  const [exportingExcel, setExportingExcel] = useState(false);

  const datesQuery = useQuery({
    queryKey: ["pnl-by-business", "dates", client.mode],
    queryFn: () => client.getFormalPnlDates("formal"),
    retry: false,
  });

  const reportDates = useMemo(
    () => datesQuery.data?.result.formal_fi_report_dates ?? datesQuery.data?.result.report_dates ?? [],
    [datesQuery.data?.result.formal_fi_report_dates, datesQuery.data?.result.report_dates],
  );

  useEffect(() => {
    const firstDate = reportDates[0];
    if (!firstDate) {
      return;
    }
    if (!selectedReportDate || !reportDates.includes(selectedReportDate)) {
      setSelectedReportDate(firstDate);
    }
  }, [reportDates, selectedReportDate]);

  const selectedYear = selectedReportDate ? Number(selectedReportDate.slice(0, 4)) : new Date().getFullYear();
  const businessQuery = useQuery({
    queryKey: ["pnl-by-business", "ytd", client.mode, selectedYear, selectedReportDate],
    enabled: Boolean(selectedReportDate && selectedYear && viewMode === "ytd"),
    queryFn: () => client.getPnlByBusinessYtd(selectedYear, selectedReportDate),
    retry: false,
  });
  const ytdResult = businessQuery.data?.result;

  const formalBusinessQuery = useQuery({
    queryKey: ["pnl-by-business", "formal", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate && viewMode === "formal"),
    queryFn: () => client.getPnlByBusiness(selectedReportDate),
    retry: false,
  });

  const ytdRange = useMemo(
    () => buildYtdRangeFromResultDates(ytdResult?.period_start_date, ytdResult?.period_end_date),
    [ytdResult?.period_start_date, ytdResult?.period_end_date],
  );

  const ytdCalendarDays = useMemo(() => {
    if (!ytdRange?.startDate || !ytdRange?.endDate) {
      return null;
    }
    return inclusiveCalendarDays(ytdRange.startDate, ytdRange.endDate);
  }, [ytdRange?.startDate, ytdRange?.endDate]);

  const adbComparisonQuery = useQuery({
    queryKey: ["pnl-by-business", "adb-comparison-ytd", client.mode, ytdRange?.startDate, ytdRange?.endDate],
    enabled: Boolean(ytdRange?.startDate && ytdRange?.endDate && viewMode === "ytd"),
    queryFn: () =>
      client.getAdbComparison(ytdRange!.startDate, ytdRange!.endDate, {
        topN: 200,
      }),
    retry: false,
  });

  const adbAvgByBusinessType = useMemo(() => {
    const map = new Map<string, number>();
    for (const item of adbComparisonQuery.data?.assets_breakdown ?? []) {
      const label = item.category?.trim();
      if (label) {
        map.set(label, item.avg_balance);
      }
    }
    return map;
  }, [adbComparisonQuery.data?.assets_breakdown]);

  const formalResult = formalBusinessQuery.data?.result;
  const pageModel = useMemo(
    () =>
      buildPnlByBusinessPageModel({
        viewMode,
        selectedReportDate,
        selectedYear,
        selectedBusinessKey,
        clientMode: client.mode,
        datesState: { isLoading: datesQuery.isLoading, isError: datesQuery.isError },
        monthlyState: { isLoading: false, isError: false },
        ytdState: { isLoading: businessQuery.isLoading, isError: businessQuery.isError },
        formalState: { isLoading: formalBusinessQuery.isLoading, isError: formalBusinessQuery.isError },
        ytdResult,
        ytdMeta: businessQuery.data?.result_meta,
        formalResult,
        formalMeta: formalBusinessQuery.data?.result_meta,
      }),
    [
      viewMode,
      selectedReportDate,
      selectedYear,
      selectedBusinessKey,
      client.mode,
      datesQuery.isLoading,
      datesQuery.isError,
      businessQuery.isLoading,
      businessQuery.isError,
      businessQuery.data?.result_meta,
      formalBusinessQuery.isLoading,
      formalBusinessQuery.isError,
      formalBusinessQuery.data?.result_meta,
      ytdResult,
      formalResult,
    ],
  );
  const {
    ytdRows,
    defaultBusinessRow,
    selectedBusinessRow,
    formalRows,
  } = pageModel;
  const adbComparisonSettled = adbComparisonQuery.isSuccess || adbComparisonQuery.isError;
  const analysisBaseReady = Boolean(
    selectedReportDate &&
      selectedYear &&
      selectedBusinessRow?.row_key &&
      viewMode === "ytd" &&
      businessQuery.isSuccess &&
      adbComparisonSettled,
  );

  useEffect(() => {
    if (viewMode !== "ytd" || !defaultBusinessRow) {
      return;
    }
    if (!selectedBusinessKey || !ytdRows.some((row) => row.row_key === selectedBusinessKey)) {
      setSelectedBusinessKey(defaultBusinessRow.row_key);
    }
  }, [defaultBusinessRow, selectedBusinessKey, viewMode, ytdRows]);

  useEffect(() => {
    setAnalysisLoadStage(0);
  }, [selectedReportDate, selectedBusinessRow?.row_key, viewMode]);

  useEffect(() => {
    setOpenMonthlyKeys(new Set());
  }, [selectedReportDate, viewMode]);

  useEffect(() => {
    if (!analysisBaseReady) {
      return;
    }
    setAnalysisLoadStage((stage) => Math.max(stage, 1));
  }, [analysisBaseReady]);

  const monthlyBusinessQuery = useQuery({
    queryKey: ["pnl-by-business", "monthly-business", client.mode, selectedYear, selectedReportDate],
    enabled: Boolean(
      selectedReportDate &&
        selectedYear &&
        (viewMode === "monthly" || (viewMode === "ytd" && analysisBaseReady && analysisLoadStage >= 1)),
    ),
    queryFn: () => client.getPnlByBusinessMonthly(selectedYear, selectedReportDate),
    retry: false,
    staleTime: ANALYSIS_QUERY_STALE_MS,
  });

  const analysisQuery = useQuery({
    queryKey: apiQueryKeys.pnlByBusinessAnalysis(
      client.mode,
      selectedYear,
      selectedReportDate,
      analysisDimension,
      selectedBusinessRow?.row_key,
    ),
    enabled: Boolean(analysisBaseReady && analysisLoadStage >= 4),
    queryFn: () =>
      client.getPnlByBusinessAnalysis({
        year: selectedYear,
        asOfDate: selectedReportDate,
        businessKey: selectedBusinessRow!.row_key,
        dimension: analysisDimension,
      }),
    retry: false,
    staleTime: ANALYSIS_QUERY_STALE_MS,
  });
  const analysisRows = analysisQuery.data?.result.rows ?? [];

  const bondBucketQuery = useQuery({
    queryKey: apiQueryKeys.pnlByBusinessAnalysis(
      client.mode,
      selectedYear,
      selectedReportDate,
      "bond_bucket",
    ),
    enabled: Boolean(analysisBaseReady && analysisLoadStage >= 2),
    queryFn: () =>
      client.getPnlByBusinessAnalysis({
        year: selectedYear,
        asOfDate: selectedReportDate,
        dimension: "bond_bucket",
      }),
    retry: false,
    staleTime: ANALYSIS_QUERY_STALE_MS,
  });
  const bondBucketRows = bondBucketQuery.data?.result.rows ?? [];

  const bondBucketMonthlyQuery = useQuery({
    queryKey: apiQueryKeys.pnlByBusinessAnalysis(
      client.mode,
      selectedYear,
      selectedReportDate,
      "bond_bucket_monthly",
    ),
    enabled: Boolean(analysisBaseReady && analysisLoadStage >= 3),
    queryFn: () =>
      client.getPnlByBusinessAnalysis({
        year: selectedYear,
        asOfDate: selectedReportDate,
        dimension: "bond_bucket_monthly",
      }),
    retry: false,
    staleTime: ANALYSIS_QUERY_STALE_MS,
  });
  const bondBucketMonthlyRows = bondBucketMonthlyQuery.data?.result.rows ?? [];

  const negativeFtpInstrumentQuery = useQuery({
    queryKey: [
      ...apiQueryKeys.pnlByBusinessAnalysis(
        client.mode,
        selectedYear,
        selectedReportDate,
        "instrument",
        selectedBusinessRow?.row_key,
      ),
      "negative-ftp",
    ],
    enabled: Boolean(analysisBaseReady && analysisLoadStage >= 5),
    queryFn: () =>
      client.getPnlByBusinessAnalysis({
        year: selectedYear,
        asOfDate: selectedReportDate,
        businessKey: selectedBusinessRow!.row_key,
        dimension: "instrument",
      }),
    retry: false,
    staleTime: ANALYSIS_QUERY_STALE_MS,
  });
  const negativeFtpInstrumentRows = negativeFtpInstrumentQuery.data?.result.rows ?? [];

  const manualAdjustmentQuery = useQuery({
    queryKey: ["pnl-by-business", "manual-adjustments", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate && viewMode === "ytd"),
    queryFn: () => client.getPnlByBusinessManualAdjustments(selectedReportDate),
    retry: false,
  });
  const currentAdjustments = manualAdjustmentQuery.data?.adjustments ?? [];
  const adjustmentEvents = manualAdjustmentQuery.data?.events ?? [];

  const invalidatePnlByBusinessQueries = async () => {
    await queryClient.invalidateQueries({ queryKey: ["pnl-by-business"] });
  };

  const resetAdjustmentDraft = () => {
    setEditingAdjustmentId(null);
    setAdjustmentDraft({ ...EMPTY_MANUAL_ADJUSTMENT_DRAFT });
  };

  const saveAdjustmentMutation = useMutation({
    mutationFn: (payload: PnlByBusinessManualAdjustmentRequest) =>
      editingAdjustmentId
        ? client.updatePnlByBusinessManualAdjustment(editingAdjustmentId, payload)
        : client.createPnlByBusinessManualAdjustment(payload),
    onSuccess: async () => {
      setAdjustmentError("");
      resetAdjustmentDraft();
      setAnalysisLoadStage(0);
      await invalidatePnlByBusinessQueries();
    },
    onError: (error) => {
      setAdjustmentError(error instanceof Error ? error.message : "保存手工调整失败");
    },
  });

  const adjustmentActionMutation = useMutation({
    mutationFn: ({ adjustmentId, action }: { adjustmentId: string; action: "revoke" | "restore" }) =>
      action === "revoke"
        ? client.revokePnlByBusinessManualAdjustment(adjustmentId)
        : client.restorePnlByBusinessManualAdjustment(adjustmentId),
    onSuccess: async () => {
      setAdjustmentError("");
      setAnalysisLoadStage(0);
      await invalidatePnlByBusinessQueries();
    },
    onError: (error) => {
      setAdjustmentError(error instanceof Error ? error.message : "更新手工调整状态失败");
    },
  });

  useEffect(() => {
    if (analysisLoadStage === 1 && (monthlyBusinessQuery.isSuccess || monthlyBusinessQuery.isError)) {
      setAnalysisLoadStage(2);
    }
  }, [analysisLoadStage, monthlyBusinessQuery.isError, monthlyBusinessQuery.isSuccess]);

  useEffect(() => {
    if (analysisLoadStage === 2 && (bondBucketQuery.isSuccess || bondBucketQuery.isError)) {
      setAnalysisLoadStage(3);
    }
  }, [analysisLoadStage, bondBucketQuery.isError, bondBucketQuery.isSuccess]);

  useEffect(() => {
    if (analysisLoadStage === 3 && (bondBucketMonthlyQuery.isSuccess || bondBucketMonthlyQuery.isError)) {
      setAnalysisLoadStage(4);
    }
  }, [analysisLoadStage, bondBucketMonthlyQuery.isError, bondBucketMonthlyQuery.isSuccess]);

  useEffect(() => {
    if (analysisLoadStage === 4 && (analysisQuery.isSuccess || analysisQuery.isError)) {
      setAnalysisLoadStage(5);
    }
  }, [analysisLoadStage, analysisQuery.isError, analysisQuery.isSuccess]);

  const toggleMonthlyBucket = (monthKey: string) => {
    setOpenMonthlyKeys((current) => {
      const next = new Set(current);
      if (next.has(monthKey)) {
        next.delete(monthKey);
      } else {
        next.add(monthKey);
      }
      return next;
    });
  };

  const updateAdjustmentDraft = <K extends keyof ManualAdjustmentDraft>(
    key: K,
    value: ManualAdjustmentDraft[K],
  ) => {
    setAdjustmentDraft((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const handleSubmitAdjustment = () => {
    setAdjustmentError("");
    const targetRow = selectedBusinessRow;
    if (!selectedReportDate || !targetRow?.row_key) {
      setAdjustmentError("请选择报表日和业务种类。");
      return;
    }
    const amount = adjustmentDraft.manual_adjustment.trim();
    if (!amount) {
      setAdjustmentError("请填写调整金额。");
      return;
    }
    if (!Number.isFinite(Number(amount))) {
      setAdjustmentError("调整金额必须是数字。");
      return;
    }

    saveAdjustmentMutation.mutate({
      report_date: selectedReportDate,
      row_key: targetRow.row_key,
      business_type: targetRow.business_type,
      operator: "DELTA",
      approval_status: adjustmentDraft.approval_status,
      manual_adjustment: amount,
      reason: adjustmentDraft.reason?.trim() ?? "",
    });
  };

  const handleEditAdjustment = (item: PnlByBusinessManualAdjustmentPayload) => {
    setAdjustmentError("");
    setEditingAdjustmentId(item.adjustment_id);
    setSelectedBusinessKey(item.row_key);
    setAdjustmentDraft({
      manual_adjustment: item.manual_adjustment,
      approval_status: normalizeAdjustmentStatus(item.approval_status),
      reason: item.reason ?? "",
    });
  };

  const completePageModel = useMemo(
    () =>
      buildPnlByBusinessPageModel({
        viewMode,
        selectedReportDate,
        selectedYear,
        selectedBusinessKey,
        clientMode: client.mode,
        datesState: { isLoading: datesQuery.isLoading, isError: datesQuery.isError },
        monthlyState: { isLoading: monthlyBusinessQuery.isLoading, isError: monthlyBusinessQuery.isError },
        ytdState: { isLoading: businessQuery.isLoading, isError: businessQuery.isError },
        formalState: { isLoading: formalBusinessQuery.isLoading, isError: formalBusinessQuery.isError },
        monthlyResult: monthlyBusinessQuery.data?.result,
        monthlyMeta: monthlyBusinessQuery.data?.result_meta,
        ytdResult,
        ytdMeta: businessQuery.data?.result_meta,
        formalResult,
        formalMeta: formalBusinessQuery.data?.result_meta,
      }),
    [
      viewMode,
      selectedReportDate,
      selectedYear,
      selectedBusinessKey,
      client.mode,
      datesQuery.isLoading,
      datesQuery.isError,
      monthlyBusinessQuery.isLoading,
      monthlyBusinessQuery.isError,
      monthlyBusinessQuery.data?.result,
      monthlyBusinessQuery.data?.result_meta,
      businessQuery.isLoading,
      businessQuery.isError,
      businessQuery.data?.result_meta,
      formalBusinessQuery.isLoading,
      formalBusinessQuery.isError,
      formalBusinessQuery.data?.result_meta,
      ytdResult,
      formalResult,
    ],
  );
  const {
    monthlyBusinessMonths,
    activeMonthlyBucket,
    loading,
    error,
    empty,
    statusStrip,
    summaryCards,
    hero,
    stateSurfaces,
  } = completePageModel;

  useEffect(() => {
    if (viewMode !== "monthly" || !activeMonthlyBucket?.month_key) {
      return;
    }
    setOpenMonthlyKeys((current) => {
      if (current.has(activeMonthlyBucket.month_key)) {
        return current;
      }
      const next = new Set(current);
      next.add(activeMonthlyBucket.month_key);
      return next;
    });
  }, [activeMonthlyBucket?.month_key, viewMode]);

  const handleExportExcel = async () => {
    if (!selectedReportDate || exportingExcel) {
      return;
    }
    setExportError("");
    setExportingExcel(true);
    try {
      const exportMonths =
        viewMode === "monthly"
          ? monthlyBusinessQuery.isSuccess
            ? monthlyBusinessMonths
            : []
          : monthlyBusinessQuery.isSuccess
            ? monthlyBusinessMonths
            : [];
      await downloadPnlByBusinessExcel({
        viewMode,
        reportDate: selectedReportDate,
        year: selectedYear,
        periodStart: ytdResult?.period_start_date,
        periodEnd: ytdResult?.period_end_date,
        periodLabel: ytdResult?.period_label,
        ytdRows: viewMode === "ytd" && businessQuery.isSuccess ? ytdRows : [],
        adbAvgByBusinessType,
        formalRows: viewMode === "formal" && formalBusinessQuery.isSuccess ? formalRows : [],
        months: exportMonths,
        adjustments: viewMode === "ytd" && manualAdjustmentQuery.isSuccess ? currentAdjustments : [],
        adjustmentEvents: viewMode === "ytd" && manualAdjustmentQuery.isSuccess ? adjustmentEvents : [],
        bondBucketRows: viewMode === "ytd" && bondBucketQuery.isSuccess ? bondBucketRows : [],
        bondBucketMonthlyRows: viewMode === "ytd" && bondBucketMonthlyQuery.isSuccess ? bondBucketMonthlyRows : [],
        negativeFtpRows: viewMode === "ytd" && negativeFtpInstrumentQuery.isSuccess ? negativeFtpInstrumentRows : [],
        analysisDimension: viewMode === "ytd" && analysisQuery.isSuccess ? analysisDimension : undefined,
        analysisRows: viewMode === "ytd" && analysisQuery.isSuccess ? analysisRows : [],
        selectedBusinessLabel: viewMode === "ytd" ? selectedBusinessRow?.business_type : undefined,
      });
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "导出 Excel 失败");
    } finally {
      setExportingExcel(false);
    }
  };

  const exportExcelDisabled =
    !selectedReportDate ||
    loading ||
    error ||
    empty ||
    exportingExcel ||
    (viewMode === "ytd" && !businessQuery.isSuccess) ||
    (viewMode === "monthly" && !monthlyBusinessQuery.isSuccess) ||
    (viewMode === "formal" && !formalBusinessQuery.isSuccess);

  const evidenceMetaSections =
    viewMode === "monthly" && monthlyBusinessQuery.data
      ? [{ key: "by-business-monthly", title: "业务种类月报", meta: monthlyBusinessQuery.data.result_meta }]
      : viewMode === "ytd" && businessQuery.data
        ? [{ key: "by-business-ytd", title: "业务种类损益", meta: businessQuery.data.result_meta }]
        : viewMode === "formal" && formalBusinessQuery.data
          ? [
              {
                key: "by-business-formal",
                title: "业务种类损益（formal）",
                meta: formalBusinessQuery.data.result_meta,
              },
            ]
          : [];

  return (
    <main data-testid="pnl-by-business-page" className="pnl-by-business-page">
      <PageV2Shell testId="pnl-by-business-page-shell">
        <PageDecisionHero
          testId="pnl-by-business-contract-hero"
          className="pnl-by-business-hero"
          title="业务种类损益"
          titleTestId="pnl-by-business-page-title"
          questionTestId="pnl-by-business-page-subtitle"
          eyebrow="组合工作台"
          businessQuestion={hero.businessQuestion}
          reportDateSlot={
            <span className="pnl-by-business-hero-report-date" data-testid="pnl-by-business-report-date-slot">
              <strong>
                {hero.reportDateLabel} {hero.requestedReportDate}
              </strong>
              <span>{hero.reportDateNote}</span>
            </span>
          }
          conclusion={
            <span className="pnl-by-business-hero-conclusion">
              <strong>{hero.conclusionTitle}</strong>
              <span>{hero.conclusionDetail}</span>
              <span className="pnl-by-business-hero-conclusion__mode">{VIEW_MODE_SUBTITLES[viewMode]}</span>
            </span>
          }
          actions={
            <span
              className={`pnl-by-business-mode-pill ${client.mode === "real" ? "pnl-by-business-mode-pill--real" : "pnl-by-business-mode-pill--mock"}`}
            >
              {client.mode === "real" ? "正式读路径" : "Mock 回放"}
            </span>
          }
        >
          <PageFilterTray testId="pnl-by-business-filter-tray">
            <FilterBar className="pnl-by-business-filter">
              <label className="pnl-by-business-filter-label">
                {viewMode === "monthly" ? "报表月份" : "分析截止日"}
                <select
                  aria-label="pnl-by-business-report-date"
                  value={selectedReportDate}
                  onChange={(event) => setSelectedReportDate(event.target.value)}
                  className="pnl-by-business-control"
                >
                  {reportDates.map((date) => (
                    <option key={date} value={date}>
                      {date}
                    </option>
                  ))}
                </select>
              </label>
              <label className="pnl-by-business-filter-label">
                视图口径
                <select
                  aria-label="pnl-by-business-view-mode"
                  value={viewMode}
                  onChange={(event) => setViewMode(event.target.value as PnlByBusinessViewMode)}
                  className="pnl-by-business-control"
                >
                  <option value="monthly">月报（ZQTZ）</option>
                  <option value="ytd">年累计（YTD）</option>
                  <option value="formal">primary 对账（/api/pnl/by-business）</option>
                </select>
              </label>
              <div className="pnl-by-business-filter-export-slot">
                <button
                  type="button"
                  className="pnl-by-business-action-button pnl-by-business-action-button-primary"
                  aria-label="pnl-by-business-export-excel"
                  disabled={exportExcelDisabled}
                  onClick={handleExportExcel}
                >
                  {exportingExcel ? "导出中..." : "导出 Excel"}
                </button>
                {exportError ? (
                  <p className="pnl-by-business-export-error" role="alert">
                    {exportError}
                  </p>
                ) : null}
              </div>
            </FilterBar>
          </PageFilterTray>
        </PageDecisionHero>

        <DataStatusStrip testId="pnl-by-business-data-status-strip" className="pnl-by-business-data-status-strip">
          <div className="pnl-by-business-data-status-strip__grid">
            <span className="pnl-by-business-data-status-strip__item">
              <small>当前口径</small>
              <strong>{statusStrip.viewModeLabel}</strong>
            </span>
            <span className="pnl-by-business-data-status-strip__item">
              <small>数据状态</small>
              <strong>{statusStrip.dataStatus}</strong>
            </span>
            <span className="pnl-by-business-data-status-strip__item">
              <small>数据截至</small>
              <strong>{statusStrip.asOfDate}</strong>
            </span>
            <span className="pnl-by-business-data-status-strip__item">
              <small>降级模式</small>
              <strong>{statusStrip.fallbackMode}</strong>
            </span>
          </div>
          <div className="pnl-by-business-data-status-strip__meta">
            <span>供应商：{statusStrip.vendorStatus}</span>
            <span>证据行：{statusStrip.evidenceRows}</span>
            <span>生成：{statusStrip.generatedAt}</span>
            <span>Trace：{statusStrip.traceId}</span>
          </div>
        </DataStatusStrip>

        {stateSurfaces.length > 0 ? (
          <div className="pnl-by-business-state-stack" data-testid="pnl-by-business-state-surfaces">
            {stateSurfaces.map((surface) => (
              <PageStateSurface
                key={surface.key}
                testId={`pnl-by-business-state-${surface.key}`}
                variant={surface.variant}
                title={surface.title}
                description={surface.description}
              />
            ))}
          </div>
        ) : null}

        <AsyncSection
          title="业务种类损益"
          isLoading={loading}
          isError={error}
          isEmpty={empty}
          fillHeight={false}
          onRetry={() => {
            setAnalysisLoadStage(0);
            const chain = [
              datesQuery.refetch(),
              businessQuery.refetch(),
              formalBusinessQuery.refetch(),
              monthlyBusinessQuery.refetch(),
              adbComparisonQuery.refetch(),
              manualAdjustmentQuery.refetch(),
            ];
            void Promise.all(chain);
          }}
        >
        <section className="pnl-by-business-content">
          <KpiBand testId="pnl-by-business-summary-cards" className="pnl-by-business-kpi-band">
            {summaryCards.map((card) => (
              <div
                key={card.label}
                className={pnlKpiToneClassName(card.tone) ? `pnl-by-business-kpi-item ${pnlKpiToneClassName(card.tone)}` : "pnl-by-business-kpi-item"}
              >
                <KpiBandMetric
                  testId={`pnl-by-business-kpi-${card.label}`}
                  label={card.label}
                  value={
                    <span
                      className={
                        card.valueVariant === "text"
                          ? "pnl-by-business-kpi-metric__text-value"
                          : "pnl-by-business-kpi-metric__tabular-value"
                      }
                    >
                      {card.value}
                    </span>
                  }
                  footer={card.detail}
                />
              </div>
            ))}
          </KpiBand>

          {evidenceMetaSections.length > 0 ? (
            <EvidencePanel
              heading="数据来源、口径与血缘"
              testId="pnl-by-business-evidence-panel"
              className="pnl-by-business-evidence-panel"
            >
              <FormalResultMetaPanel
                testId="pnl-by-business-result-meta-panel"
                sections={evidenceMetaSections}
              />
            </EvidencePanel>
          ) : null}

          <AnalysisGrid columns={1} testId="pnl-by-business-analysis-grid" className="pnl-by-business-analysis-grid">
            {viewMode === "monthly" ? (
            <>
              <PageSectionLead
                eyebrow="Monthly Report"
                title={`${selectedYear} 月报（截至 ${
                  activeMonthlyBucket?.month_key ?? selectedReportDate.slice(0, 7)
                }）`}
                description="月报与累计视图使用同一套 ZQTZ 管理披露分类：金额列为万元，日均与期末余额为亿元，收益率按各月自然日数年化。该视图列出截至当前报表日已加载的月报；切换到「年累计」可查看这些月报的累计结果。"
              />
              <MonthlyBusinessBreakdownPanel
                months={monthlyBusinessMonths}
                isLoading={monthlyBusinessQuery.isLoading || monthlyBusinessQuery.isFetching}
                isError={monthlyBusinessQuery.isError}
                openMonthKeys={openMonthlyKeys}
                onToggleMonth={toggleMonthlyBucket}
                title="月报业务种类明细"
                description="按月份展开 ZQTZ 管理披露分类，查看各月损益、月度日均、期末余额与 FTP 后收益。"
                forceOpenSingleMonth
              />
            </>
          ) : viewMode === "ytd" ? (
            <>
              <PageSectionLead
                eyebrow="Business Type"
                title={`${selectedYear} 年累计明细`}
                description="表中利息至合计损益为万元（接口为元÷1万）；日均(亿元)与日均分析同源，区间采用后端 YTD 结果返回的起止日期；「非底层投资资产」父级日均由下列细类目相加。年化收益率为（累计损益÷同区间日均余额）×（365÷自然日数，含首尾），与日均列同源；无日均或区间不可算时显示「-」。口径提示：同一资产在 ZQTZ 规则下可同时命中父类「非底层投资资产」与「其中」细类（如证券业资管计划、本币专户/市值法、外币委外、结构化融资（券商）等），故多行损益金额可能重叠展示——核对「证券业资管」量级时宜看该行及同前缀下的细分行，勿与父级简单相加以免重复。表末「父级汇总」仅对父级行求和（排除「其中」细分），占比与收益率列不宜相加故置「—」。"
              />
              <BusinessRowsTable
                rows={ytdRows}
                adbAvgByBusinessType={adbAvgByBusinessType}
                ytdCalendarDays={ytdCalendarDays}
                selectedRowKey={selectedBusinessRow?.row_key ?? null}
                onSelectRow={(row) => setSelectedBusinessKey(row.row_key)}
              />
              <PnlByBusinessManualAdjustmentPanel
                rows={ytdRows}
                selectedReportDate={selectedReportDate}
                selectedBusinessRow={selectedBusinessRow}
                selectedRowKey={selectedBusinessRow?.row_key ?? ""}
                draft={adjustmentDraft}
                editingAdjustmentId={editingAdjustmentId}
                adjustmentError={adjustmentError}
                isLoading={manualAdjustmentQuery.isLoading || manualAdjustmentQuery.isFetching}
                isSaving={saveAdjustmentMutation.isPending}
                isActionBusy={adjustmentActionMutation.isPending}
                adjustments={currentAdjustments}
                events={adjustmentEvents}
                onSelectRowKey={(rowKey) => setSelectedBusinessKey(rowKey)}
                onDraftChange={updateAdjustmentDraft}
                onSubmit={handleSubmitAdjustment}
                onEdit={handleEditAdjustment}
                onCancelEdit={resetAdjustmentDraft}
                onRevoke={(adjustmentId) => adjustmentActionMutation.mutate({ adjustmentId, action: "revoke" })}
                onRestore={(adjustmentId) => adjustmentActionMutation.mutate({ adjustmentId, action: "restore" })}
              />
              <MonthlyBusinessBreakdownPanel
                months={monthlyBusinessMonths}
                isLoading={
                  analysisBaseReady &&
                  (analysisLoadStage < 1 || monthlyBusinessQuery.isLoading || monthlyBusinessQuery.isFetching)
                }
                isError={monthlyBusinessQuery.isError}
                openMonthKeys={openMonthlyKeys}
                onToggleMonth={toggleMonthlyBucket}
                title="月报业务种类明细"
                description="逐月展开已发布月报，YTD 金额可用父级行与这些月报合计核对。"
              />
              <FtpBridgePanel
                selectedRow={selectedBusinessRow}
                adbAvgByBusinessType={adbAvgByBusinessType}
                ytdCalendarDays={ytdCalendarDays}
              />
              <BondBucketAnalysisPanel
                rows={bondBucketRows}
                isLoading={analysisBaseReady && (analysisLoadStage < 2 || bondBucketQuery.isLoading || bondBucketQuery.isFetching)}
                isError={bondBucketQuery.isError}
              />
              <BondBucketMonthlyPanel
                rows={bondBucketMonthlyRows}
                isLoading={
                  analysisBaseReady &&
                  (analysisLoadStage < 3 || bondBucketMonthlyQuery.isLoading || bondBucketMonthlyQuery.isFetching)
                }
                isError={bondBucketMonthlyQuery.isError}
              />
              <NegativeFtpListPanel
                rows={negativeFtpInstrumentRows}
                isLoading={
                  analysisBaseReady &&
                  (analysisLoadStage < 5 || negativeFtpInstrumentQuery.isLoading || negativeFtpInstrumentQuery.isFetching)
                }
                isError={negativeFtpInstrumentQuery.isError}
              />
              <DriverOverviewPanel
                rows={ytdRows}
                adbAvgByBusinessType={adbAvgByBusinessType}
                ytdCalendarDays={ytdCalendarDays}
              />
              <section className="pnl-by-business-analysis-block" data-testid="pnl-by-business-analysis-panel">
                <div className="pnl-by-business-analysis-heading">
                  <div>
                    <h2>多维下钻</h2>
                    <p>{selectedBusinessRow?.business_type ?? "-"}</p>
                  </div>
                  <label className="pnl-by-business-filter-label">
                    维度
                    <select
                      aria-label="pnl-by-business-analysis-dimension"
                      value={analysisDimension}
                      onChange={(event) => setAnalysisDimension(event.target.value as PnlByBusinessAnalysisDimension)}
                      className="pnl-by-business-control"
                    >
                      {(Object.keys(ANALYSIS_DIMENSION_LABELS) as PnlByBusinessAnalysisDimension[]).map((key) => (
                        <option key={key} value={key}>
                          {ANALYSIS_DIMENSION_LABELS[key]}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="pnl-by-business-analysis-kpis">
                  <KpiCard
                    label="选中业务损益"
                    value={formatYuanAsWanUnit(selectedBusinessRow?.total_pnl)}
                    detail={selectedBusinessRow?.business_type ?? "-"}
                    tone={toneFromSigned(selectedBusinessRow?.total_pnl)}
                  />
                  <KpiCard
                    label="日均"
                    value={formatAvgBalanceYi(
                      selectedBusinessRow
                        ? resolveAdbAvgYuan(selectedBusinessRow.business_type, adbAvgByBusinessType)
                        : null,
                    )}
                    detail="ADB 同区间"
                  />
                  <KpiCard
                    label="期末余额"
                    value={formatYuanAsYiCell(selectedBusinessRow?.current_balance)}
                    detail={ytdResult?.period_end_date ?? selectedReportDate}
                  />
                  <KpiCard
                    label="年化收益率"
                    value={formatAnnualizedYieldPctDisplay(
                      numeric(selectedBusinessRow?.total_pnl),
                      selectedBusinessRow
                        ? resolveAdbAvgYuan(selectedBusinessRow.business_type, adbAvgByBusinessType)
                        : undefined,
                      ytdCalendarDays,
                    )}
                    detail="YTD 损益 / 日均"
                  />
                </div>
                {analysisBaseReady && (analysisLoadStage < 4 || analysisQuery.isLoading || analysisQuery.isFetching) ? (
                  <div className="pnl-by-business-analysis-state">加载中</div>
                ) : analysisQuery.isError ? (
                  <div className="pnl-by-business-analysis-state">维度数据读取失败</div>
                ) : analysisRows.length === 0 ? (
                  <div className="pnl-by-business-analysis-state">暂无维度数据</div>
                ) : (
                  <AnalysisRowsTable rows={analysisRows} dimension={analysisDimension} />
                )}
              </section>
            </>
          ) : (
            <>
              <PageSectionLead
                eyebrow="Business Type"
                title={`${selectedReportDate} primary 对账明细`}
                description="与 GET /api/pnl/by-business 一致：来自 fact_formal_pnl_fi / fact_nonstd_pnl_bridge 与 fact_formal_zqtz_balance_daily 的 join 聚合。这里按 primary 分类展示，用于源数据追溯；月报和累计按 ZQTZ 管理披露分类展示，二者不要混加。"
              />
              <FormalBusinessRowsTable rows={formalRows} />
            </>
          )}
          </AnalysisGrid>
        </section>
      </AsyncSection>
      </PageV2Shell>
    </main>
  );
}
