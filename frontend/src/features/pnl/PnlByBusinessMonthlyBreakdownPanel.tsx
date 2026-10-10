import { type PnlByBusinessMonthlyBucket, type PnlByBusinessMonthlyItem } from "../../api/contracts";
import { formatAnalysisYieldPct, formatAvgBalanceYi, formatAvgBalanceYiMetric, formatRatioPct, isDetailZqtzBusinessRow, isParentZqtzBusinessRow } from "./pnlByBusinessPageModel";
import { numeric, formatPnlWan, formatYuanAsYiCell } from "./pnlByBusinessDisplay";
import { PnlWanCell } from "./PnlByBusinessPnlCell";
import { UnallocatedPnlPanel } from "./PnlByBusinessUnallocatedPanel";

function MonthlyBusinessRowsTable({ month }: { month: PnlByBusinessMonthlyBucket }) {
  const parentRows = month.items.filter(isParentZqtzBusinessRow);
  const detailRows = month.items.filter(isDetailZqtzBusinessRow);
  const evidenceComplete = month.unallocated_evidence_complete === true;
  const reconciliationClosed = evidenceComplete && (numeric(month.reconciliation_delta) ?? Number.NaN) === 0;
  const expectedCoverageDays = month.expected_days ?? month.calendar_days;
  const coverageIncomplete =
    typeof month.coverage_days === "number" &&
    expectedCoverageDays > 0 &&
    month.coverage_days < expectedCoverageDays;
  const coverageSummaryText = `余额覆盖 ${month.coverage_days ?? "待返回"}/${
    month.expected_days ?? month.calendar_days ?? "待返回"
  } 天${month.sample_filled ? "（样本填充）" : ""}`;
  return (
    <>
      {month.balance_quality_issues?.map((issue) => (
        <div className="pnl-by-business-detail-warning" key={issue.issue_id}>
          {issue.report_date} 余额来源待核实：{issue.reason} 本月日均、收益率和 FTP 为暂列值，取得正确源表后重算。
        </div>
      ))}
      {coverageIncomplete ? (
        <div
          className="pnl-by-business-detail-warning"
          data-testid={`pnl-by-business-monthly-coverage-warning-${month.month_key}`}
        >
          日均余额仅覆盖 {month.coverage_days}/{expectedCoverageDays} 天。下表日均、年化收益率、FTP 成本及 FTP
          后结果为观测样本估算，仅供对账，暂不作为完整月度结论。
        </div>
      ) : null}
      <div
        className="pnl-by-business-table-shell pnl-by-business-month-table-shell"
        data-testid={`pnl-by-business-monthly-table-${month.month_key}`}
      >
        <table className="pnl-by-business-table">
          <thead>
            <tr>
              <th>业务种类</th>
              <th>{coverageIncomplete ? "观测日均(亿元)" : "日均(亿元)"}</th>
              <th>期末余额(亿元)</th>
              <th>利息收入（万元）</th>
              <th>公允价值变动（万元）</th>
              <th>资本利得（万元）</th>
              <th>手工调整（万元）</th>
              <th>合计损益（万元）</th>
              <th>{coverageIncomplete ? "年化收益率（待核对）" : "年化收益率"}</th>
              <th>{coverageIncomplete ? "FTP成本（待核对，万元）" : "FTP成本（万元）"}</th>
              <th>{coverageIncomplete ? "FTP后收益（待核对，万元）" : "FTP后收益（万元）"}</th>
              <th>{coverageIncomplete ? "FTP后收益率（待核对）" : "FTP后收益率"}</th>
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
                <PnlWanCell raw={row.interest_income} />
                <PnlWanCell raw={row.fair_value_change} />
                <PnlWanCell raw={row.capital_gain} />
                <PnlWanCell raw={row.manual_adjustment} />
                <PnlWanCell raw={row.total_pnl} />
                <td>{formatAnalysisYieldPct(row.annualized_yield_pct)}</td>
                <PnlWanCell raw={row.ftp_cost} />
                <PnlWanCell raw={row.ftp_net_pnl} />
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
              <PnlWanCell className="pnl-by-business-table-footer-cell" raw={month.summary.interest_income} />
              <PnlWanCell className="pnl-by-business-table-footer-cell" raw={month.summary.fair_value_change} />
              <PnlWanCell className="pnl-by-business-table-footer-cell" raw={month.summary.capital_gain} />
              <PnlWanCell className="pnl-by-business-table-footer-cell" raw={month.summary.manual_adjustment} />
              <PnlWanCell className="pnl-by-business-table-footer-cell" raw={month.summary.total_pnl} />
              <td className="pnl-by-business-table-footer-cell">
                {formatAnalysisYieldPct(month.summary.annualized_yield_pct)}
              </td>
              <PnlWanCell className="pnl-by-business-table-footer-cell" raw={month.summary.ftp_cost} />
              <PnlWanCell className="pnl-by-business-table-footer-cell" raw={month.summary.ftp_net_pnl} />
              <td className="pnl-by-business-table-footer-cell">
                {formatAnalysisYieldPct(month.summary.ftp_net_annualized_yield_pct)}
              </td>
              <td className="pnl-by-business-table-footer-cell">—</td>
              <td className="pnl-by-business-table-footer-cell">{month.summary.asset_count}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <div
        className={
          reconciliationClosed
            ? "pnl-by-business-monthly-reconciliation pnl-by-business-monthly-reconciliation--closed"
            : "pnl-by-business-monthly-reconciliation pnl-by-business-monthly-reconciliation--warning"
        }
        data-testid={`pnl-by-business-monthly-reconciliation-${month.month_key}`}
        title={coverageIncomplete ? coverageSummaryText : undefined}
      >
        <span>
          源损益 {formatPnlWan(month.source_total_pnl)} 万元 = 父级 {formatPnlWan(month.classified_parent_total_pnl)} 万元 + 未分类{" "}
          {formatPnlWan(month.unallocated_pnl)} 万元
        </span>
        <span>
          差异 {formatPnlWan(month.reconciliation_delta)} 万元 · {reconciliationClosed ? "已闭合" : "待核对"}
        </span>
        {/* 覆盖不足时该事实已由上方表内警示条承载，闭合条内收进 title 去重（§6 ≤2 处）；
            覆盖完整或天数待返回时此处是唯一披露位，保持可见。 */}
        {coverageIncomplete ? null : <span>{coverageSummaryText}</span>}
      </div>
      <UnallocatedPnlPanel
        breakdown={month.unallocated_breakdown}
        items={month.unallocated_items}
        totalPnl={month.unallocated_pnl}
        totalAbsPnl={month.unallocated_abs_pnl}
        rowCount={month.unallocated_row_count}
        testIdPrefix={`pnl-by-business-monthly-unallocated-${month.month_key}`}
        evidenceComplete={evidenceComplete}
      />
      {detailRows.length > 0 ? (
        <div
          className="pnl-by-business-detail-block"
          data-testid={`pnl-by-business-monthly-detail-table-${month.month_key}`}
        >
          <div
            className="pnl-by-business-detail-warning"
            data-testid={`pnl-by-business-monthly-detail-overlap-warning-${month.month_key}`}
          >
            以下金额已包含在上方父级行中，与父级行金额存在重叠，不可与父级行相加，也不可跨行相加。
          </div>
          <div className="pnl-by-business-detail-heading">
            <h3>其中项明细</h3>
            <p>这些行为父级分类的拆解项，不参与父级汇总和资产数加总。</p>
          </div>
          <div className="pnl-by-business-table-shell pnl-by-business-month-table-shell">
            <table className="pnl-by-business-table">
              <thead>
                <tr>
                  <th>业务种类</th>
                  <th>{coverageIncomplete ? "观测日均(亿元)" : "日均(亿元)"}</th>
                  <th>期末余额(亿元)</th>
                  <th>利息收入（万元）</th>
                  <th>公允价值变动（万元）</th>
                  <th>资本利得（万元）</th>
                  <th>手工调整（万元）</th>
                  <th>合计损益（万元）</th>
                  <th>{coverageIncomplete ? "年化收益率（待核对）" : "年化收益率"}</th>
                  <th>{coverageIncomplete ? "FTP成本（待核对，万元）" : "FTP成本（万元）"}</th>
                  <th>{coverageIncomplete ? "FTP后收益（待核对，万元）" : "FTP后收益（万元）"}</th>
                  <th>{coverageIncomplete ? "FTP后收益率（待核对）" : "FTP后收益率"}</th>
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
                    <PnlWanCell raw={row.interest_income} />
                    <PnlWanCell raw={row.fair_value_change} />
                    <PnlWanCell raw={row.capital_gain} />
                    <PnlWanCell raw={row.manual_adjustment} />
                    <PnlWanCell raw={row.total_pnl} />
                    <td>{formatAnalysisYieldPct(row.annualized_yield_pct)}</td>
                    <PnlWanCell raw={row.ftp_cost} />
                    <PnlWanCell raw={row.ftp_net_pnl} />
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

export function MonthlyBusinessBreakdownPanel({
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
            const expectedCoverageDays = month.expected_days ?? month.calendar_days;
            const coverageIncomplete =
              typeof month.coverage_days === "number" &&
              expectedCoverageDays > 0 &&
              month.coverage_days < expectedCoverageDays;
            const manualAdjustment = numeric(month.summary.manual_adjustment);
            const hasManualAdjustment = manualAdjustment !== null && manualAdjustment !== 0;
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
                      <small>
                        {coverageIncomplete
                          ? `观测日均（${month.coverage_days}/${expectedCoverageDays}天）`
                          : "日均余额"}
                      </small>
                      <strong>{formatAvgBalanceYiMetric(month.summary.avg_balance)}</strong>
                    </span>
                    <span>
                      <small>{hasManualAdjustment ? "调整后损益" : "总损益"}</small>
                      <strong>{formatPnlWan(month.summary.total_pnl)} 万元</strong>
                    </span>
                    <span>
                      <small>年化收益率</small>
                      <strong>
                        {coverageIncomplete ? "待核对" : formatAnalysisYieldPct(month.summary.annualized_yield_pct)}
                      </strong>
                    </span>
                    <span>
                      <small>FTP后收益率</small>
                      <strong>
                        {coverageIncomplete
                          ? "待核对"
                          : formatAnalysisYieldPct(month.summary.ftp_net_annualized_yield_pct)}
                      </strong>
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
