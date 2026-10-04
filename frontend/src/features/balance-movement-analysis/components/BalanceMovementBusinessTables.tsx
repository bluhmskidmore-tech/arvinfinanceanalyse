import type { BalanceBusinessMovementTrendMonth, BalanceMovementRow } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { formatBalanceAmountToYiFromYuan } from "../../balance-analysis/pages/balanceAnalysisPageModel";
import { formatSignedPointNullable } from "../lib/balanceMovementShareModel";
import {
  counterpartyAmountText,
  statusToneClass,
  reconciliationTieoutSummary,
} from "../lib/balanceMovementReconciliationModel";
import { ChainReconciliationCell, ReconciliationStatusTag } from "./ReconciliationStatusTag";
import {
  type BusinessMovementMatrixRow,
  compareBusinessMatrixCell,
  compareBusinessMatrixCellToFirst,
  shareDeltaPp,
} from "../lib/balanceMovementBusinessModel";
import {
  formatTrendMonthLabel,
  formatMatrixCellWithMissing,
  formatMatrixValue,
  matrixDeltaTone,
  formatPct,
  formatSignedYiNumber,
} from "../lib/balanceMovementPresentation";
import type { BalanceMovementViewModel } from "../hooks/useBalanceMovementViewModel";

export function BusinessBalanceMatrixSection({
  months,
  liabilityRows,
  projectRows,
  balanceRows,
  accountingSnapshotsAreNonAdjacent,
}: {
  months: BalanceBusinessMovementTrendMonth[];
  liabilityRows: BusinessMovementMatrixRow[];
  projectRows: BusinessMovementMatrixRow[];
  balanceRows: BalanceMovementRow[];
  accountingSnapshotsAreNonAdjacent: boolean;
}) {
  const rows = [...liabilityRows, ...projectRows];
  const currentMonth = months.at(-1)?.report_month ?? EM_DASH;

  return (
    <section
      className="balance-movement-business-matrix balance-movement-figma-panel"
      data-testid="balance-movement-analysis-business-balance-matrix"
    >
      <header className="balance-movement-figma-header balance-movement-sec-no">
        <div>
          <h2>业务口径余额矩阵与 AC / OCI / TPL 对账</h2>
        </div>
        <p>报告月 {currentMonth} / 较上月与较年初</p>
      </header>

      <div className="balance-movement-business-matrix__scope">
        <p data-testid="balance-movement-analysis-slice-note">
          总账 AC/OCI/TPL 与业务行属于两套分类，不做简单加减核对。
        </p>
        <p data-testid="balance-movement-analysis-series-context">
          <code>business_trend_months</code>
          <span>
            {accountingSnapshotsAreNonAdjacent
              ? "相邻快照非连续，环比结论保持隐藏。"
              : `当前覆盖 ${months.length} 个月度；若仅含两个月度，较年初按序列首月解释。`}
          </span>
        </p>
      </div>

      <div className="balance-movement-business-matrix__table-wrap">
        <table
          data-testid="balance-movement-analysis-trend-table"
          className="balance-movement-business-matrix__table"
        >
          <thead>
            <tr>
              <th scope="col">明细项目</th>
              {months.map((month) => (
                <th key={month.report_date} scope="col">
                  {formatTrendMonthLabel(month.report_month)}
                </th>
              ))}
              <th scope="col">较上月</th>
              <th scope="col">较年初</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const mom = compareBusinessMatrixCell(months, row, 1);
              const ytd = compareBusinessMatrixCellToFirst(months, row);
              return (
                <tr key={row.key} data-side={row.side}>
                  <th scope="row" title={row.sourceNote}>{row.label}</th>
                  {months.map((month) => {
                    const cellMeta = row.getCellMeta?.(month);
                    return (
                      <td
                        key={`${row.key}-${month.report_date}`}
                        title={cellMeta?.hasMissingInputs ? "部分分项缺失，合计未含缺失项" : undefined}
                      >
                        {cellMeta
                          ? formatMatrixCellWithMissing(
                              row.getValue(month),
                              row.valueKind,
                              true,
                              cellMeta.hasMissingInputs,
                            )
                          : formatMatrixValue(row.getValue(month), row.valueKind, true)}
                      </td>
                    );
                  })}
                  <td className={matrixDeltaTone(mom)}>{mom}</td>
                  <td className={matrixDeltaTone(ytd)}>{ytd}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="balance-movement-business-matrix__reconciliation">
        <h3>明细 / 对账：AC / OCI / TPL 余额变动</h3>
        <div className="balance-movement-detail-table-wrap">
          <table
            data-testid="balance-movement-analysis-table"
            className="balance-movement-detail-table"
          >
            <thead>
              <tr>
                <th>分类</th>
                <th>期初余额(亿)</th>
                <th>期初占比</th>
                <th>期末余额(亿)</th>
                <th>期末占比</th>
                <th>占比变动</th>
                <th>变动(亿)</th>
                <th>变动率</th>
                <th>变动贡献</th>
                <th>ZQTZ辅助(亿)</th>
                <th>ZQTZ诊断差异(亿)</th>
                <th>跨月勾稽</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {balanceRows.map((row) => (
                <tr key={row.basis_bucket}>
                  <td>{row.basis_bucket}</td>
                  <td>{formatBalanceAmountToYiFromYuan(row.previous_balance)}</td>
                  <td>{formatPct(row.previous_balance_pct)}</td>
                  <td>{formatBalanceAmountToYiFromYuan(row.current_balance)}</td>
                  <td>{formatPct(row.current_balance_pct)}</td>
                  <td>{formatSignedPointNullable(shareDeltaPp(row))}</td>
                  <td>{formatBalanceAmountToYiFromYuan(row.balance_change)}</td>
                  <td>{formatPct(row.change_pct)}</td>
                  <td>{formatPct(row.contribution_pct)}</td>
                  <td>{counterpartyAmountText(row, formatBalanceAmountToYiFromYuan(row.zqtz_amount))}</td>
                  <td>{counterpartyAmountText(row, formatBalanceAmountToYiFromYuan(row.reconciliation_diff))}</td>
                  <ChainReconciliationCell row={row} />
                  <td className={statusToneClass(row.reconciliation_status)}>
                    <ReconciliationStatusTag status={row.reconciliation_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="balance-movement-business-matrix__tieout">
        {reconciliationTieoutSummary(balanceRows, formatSignedYiNumber)}
      </div>
    </section>
  );
}

export function SupplementaryBusinessRowsTable({
  months,
  rows,
}: {
  months: BalanceBusinessMovementTrendMonth[];
  rows: BusinessMovementMatrixRow[];
}) {
  if (rows.length === 0) {
    return null;
  }

  return (
    <section
      className="balance-movement-supplementary-matrix"
      data-testid="balance-movement-analysis-supplementary-business-matrix"
    >
      <header>
        <strong>资产端同业扩展明细</strong>
        <span>完整业务矩阵保留区 · 默认不占用决策主流程</span>
      </header>
      <div className="balance-movement-business-matrix__table-wrap">
        <table className="balance-movement-business-matrix__table">
          <thead>
            <tr>
              <th scope="col">明细项目</th>
              {months.map((month) => (
                <th key={month.report_date} scope="col">
                  {formatTrendMonthLabel(month.report_month)}
                </th>
              ))}
              <th scope="col">较上月</th>
              <th scope="col">较年初</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const mom = compareBusinessMatrixCell(months, row, 1);
              const ytd = compareBusinessMatrixCellToFirst(months, row);
              return (
                <tr key={row.key} data-side={row.side}>
                  <th scope="row" title={row.sourceNote}>{row.label}</th>
                  {months.map((month) => (
                    <td key={`${row.key}-${month.report_date}`}>
                      {formatMatrixValue(row.getValue(month), row.valueKind, true)}
                    </td>
                  ))}
                  <td className={matrixDeltaTone(mom)}>{mom}</td>
                  <td className={matrixDeltaTone(ytd)}>{ytd}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

type ZqtzAssetDetailTableProps = Pick<
  BalanceMovementViewModel,
    "businessMatrixMonths"
  | "zqtzAssetDetailRows"
  | "zqtzAssetDetailSummaryRow"
>;

export function ZqtzAssetDetailTable({
  businessMatrixMonths,
  zqtzAssetDetailRows,
  zqtzAssetDetailSummaryRow,
}: ZqtzAssetDetailTableProps) {
  return (
    <section
      data-testid="balance-movement-analysis-zqtz-detail"
      className="balance-movement-zqtz-detail-page balance-movement-figma-panel"
    >
      <header className="balance-movement-zqtz-detail-page__header balance-movement-figma-header balance-movement-sec-no">
        <div>
          <h2>金融投资资产明细变动（6个月）</h2>
        </div>
        <p>
          报告月 {businessMatrixMonths.at(-1)?.report_month ?? EM_DASH} / 单位 亿元 / {zqtzAssetDetailRows.length + (zqtzAssetDetailSummaryRow ? 1 : 0)} 行
        </p>
      </header>
      <div className="balance-movement-zqtz-detail-page__scope">
        <code title="business_trend_months.rows · source_kind ZQTZ / ledger">business_trend_months.rows</code>
        <span>来源口径 ZQTZ / 台账；“其中”项独立展示，不与上级分类重复加总。</span>
      </div>
      <div className="balance-movement-zqtz-detail-page__table-wrap">
        <table className="balance-movement-zqtz-detail-page__table">
          <thead>
            <tr>
              <th scope="col">明细项目</th>
              {businessMatrixMonths.map((month) => (
                <th key={month.report_date} scope="col">
                  {formatTrendMonthLabel(month.report_month)}
                </th>
              ))}
              <th scope="col">较上月</th>
              <th scope="col">较年初</th>
            </tr>
          </thead>
          <tbody>
            {zqtzAssetDetailRows.map((row) => {
              const mom = compareBusinessMatrixCell(businessMatrixMonths, row, 1);
              const ytd = compareBusinessMatrixCellToFirst(businessMatrixMonths, row);
              return (
                <tr
                  key={row.key}
                  className={row.isSubItem ? "balance-movement-zqtz-detail-page__row--subitem" : undefined}
                >
                  <th scope="row" title={row.sourceNote}>
                    {row.label}
                  </th>
                  {businessMatrixMonths.map((month) => {
                    const cellMeta = row.getCellMeta?.(month);
                    return (
                      <td
                        key={`${row.key}-${month.report_date}`}
                        title={
                          cellMeta?.hasMissingInputs
                            ? "部分分项缺失，合计未含缺失项"
                            : undefined
                        }
                      >
                        {cellMeta
                          ? formatMatrixCellWithMissing(
                              row.getValue(month),
                              "amount",
                              true,
                              cellMeta.hasMissingInputs,
                            )
                          : formatMatrixValue(row.getValue(month), "amount", true)}
                      </td>
                    );
                  })}
                  <td className={matrixDeltaTone(mom)}>{mom}</td>
                  <td className={matrixDeltaTone(ytd)}>{ytd}</td>
                </tr>
              );
            })}
            {zqtzAssetDetailSummaryRow
              ? (() => {
                  const mom = compareBusinessMatrixCell(businessMatrixMonths, zqtzAssetDetailSummaryRow, 1);
                  const ytd = compareBusinessMatrixCellToFirst(
                    businessMatrixMonths,
                    zqtzAssetDetailSummaryRow,
                  );
                  return (
                    <tr
                      key={zqtzAssetDetailSummaryRow.key}
                      className="balance-movement-zqtz-detail-page__row--summary"
                    >
                      <th scope="row" title={zqtzAssetDetailSummaryRow.sourceNote}>
                        {zqtzAssetDetailSummaryRow.label}
                      </th>
                      {businessMatrixMonths.map((month) => {
                        const cellMeta = zqtzAssetDetailSummaryRow.getCellMeta?.(month);
                        return (
                          <td
                            key={`${zqtzAssetDetailSummaryRow.key}-${month.report_date}`}
                            title={
                              cellMeta?.hasMissingInputs
                                ? "部分分项缺失，合计未含缺失项"
                                : undefined
                            }
                          >
                            {formatMatrixCellWithMissing(
                              zqtzAssetDetailSummaryRow.getValue(month),
                              "amount",
                              true,
                              cellMeta?.hasMissingInputs,
                            )}
                          </td>
                        );
                      })}
                      <td className={matrixDeltaTone(mom)}>{mom}</td>
                      <td className={matrixDeltaTone(ytd)}>{ytd}</td>
                    </tr>
                  );
                })()
              : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
