import { useMemo, useState } from "react";
import type { LedgerPnlSummaryPayload } from "../../../api/contracts";
import { formatMoney, ledgerMoneyYuan, ledgerSectionState, sortLedgerRowsByAbsYuan } from "../models/ledgerPnlDisplay";
import { LEDGER_PNL_SECTION_IDS } from "../models/ledgerPnlPageConstants";
import { LedgerPnlDataTable, type LedgerPnlDataTableColumn } from "./LedgerPnlDataTable";
import { LedgerPnlSectionLead } from "./LedgerPnlSectionPresentation";

/** B6：科目汇总默认只渲染前 N 行（后端既有排序），"展开全部"切换到全量。 */
const LEDGER_ACCOUNT_SUMMARY_TOP_N = 20;
function LedgerTableStateRow(props: { colSpan: number; message: string }) {
  return (
    <tr>
      <td colSpan={props.colSpan} className="ledger-pnl-table__state-cell">
        {props.message}
      </td>
    </tr>
  );
}

export function LedgerPnlAccountSummarySection({
  summary,
  isLoading,
  isError,
}: {
  summary: LedgerPnlSummaryPayload | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  /** B6：科目汇总默认 Top 20 + 展开全部（纯本地 UI 状态，不影响后端排序/请求）。 */
  const [accountSummaryExpanded, setAccountSummaryExpanded] = useState(false);
  const [accountSummarySearchTerm, setAccountSummarySearchTerm] = useState("");
  const accountSummaryRows = useMemo(() => summary?.by_account ?? [], [summary?.by_account]);
  const visibleAccountSummaryRows = useMemo(
    () => sortLedgerRowsByAbsYuan(accountSummaryRows, (item) => item.total_pnl),
    [accountSummaryRows],
  );
  /*
   * B6：默认只渲染前 LEDGER_ACCOUNT_SUMMARY_TOP_N 行（沿用后端既有排序，不改排序行为）；
   * 搜索词非空时改在全量 visibleAccountSummaryRows 上过滤，不受 Top N 限制。
   */
  const accountSummarySearchNormalized = accountSummarySearchTerm.trim().toLowerCase();
  const accountSummarySearchFilteredRows = useMemo(() => {
    if (!accountSummarySearchNormalized) return visibleAccountSummaryRows;
    return visibleAccountSummaryRows.filter((item) =>
      `${item.account_code} ${item.account_name}`.toLowerCase().includes(accountSummarySearchNormalized),
    );
  }, [visibleAccountSummaryRows, accountSummarySearchNormalized]);
  const accountSummaryDisplayRows = useMemo(() => {
    if (accountSummarySearchNormalized) return accountSummarySearchFilteredRows;
    if (accountSummaryExpanded) return visibleAccountSummaryRows;
    return visibleAccountSummaryRows.slice(0, LEDGER_ACCOUNT_SUMMARY_TOP_N);
  }, [accountSummarySearchNormalized, accountSummarySearchFilteredRows, accountSummaryExpanded, visibleAccountSummaryRows]);
  const accountSummaryColumns = useMemo<
    LedgerPnlDataTableColumn<(typeof visibleAccountSummaryRows)[number]>[]
  >(
    () => [
      {
        key: "account",
        header: "科目",
        searchValue: (item) => `${item.account_code} ${item.account_name}`,
        sortValue: (item) => item.account_code,
        render: (item) => (
          <div className="ledger-pnl-table__account">
            <span>{item.account_code}</span>
            <span className="ledger-pnl-table__td-sub">{item.account_name}</span>
          </div>
        ),
      },
      {
        key: "total_pnl",
        header: "损益",
        numeric: true,
        sortValue: (item) => ledgerMoneyYuan(item.total_pnl),
        render: (item) => formatMoney(item.total_pnl),
      },
      {
        key: "count",
        header: "笔数",
        numeric: true,
        sortValue: (item) => item.count,
        render: (item) => item.count,
      },
    ],
    [],
  );

  return (
      <section id={LEDGER_PNL_SECTION_IDS.accounts} className="ledger-pnl-section">
        <LedgerPnlSectionLead
          title="科目汇总"
          state={ledgerSectionState({ isLoading, isError })}
          note={`${(summary?.by_account ?? []).length} 个科目`}
        />
        <div className="ledger-pnl-summary-table-grid">
        <div data-testid="ledger-pnl-currency-summary-table" className="ledger-pnl-table-shell">
          <div className="ledger-pnl-table-shell__title">
            币种汇总
          </div>
          <table className="ledger-pnl-table">
            <thead>
              <tr className="ledger-pnl-table__head-row">
                <th className="ledger-pnl-table__th">币种</th>
                <th className="ledger-pnl-table__th ledger-pnl-table__th--num">损益</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <LedgerTableStateRow colSpan={2} message="币种汇总读取中" />
              ) : isError ? (
                <LedgerTableStateRow colSpan={2} message="币种汇总读取失败" />
              ) : (summary?.by_currency ?? []).length > 0 ? (
                (summary?.by_currency ?? []).map((item) => (
                  <tr key={item.currency} className="ledger-pnl-table__row">
                    <td className="ledger-pnl-table__td">{item.currency}</td>
                    <td className="ledger-pnl-table__td ledger-pnl-table__td--num">{formatMoney(item.total_pnl)}</td>
                  </tr>
                ))
              ) : (
                <LedgerTableStateRow colSpan={2} message="暂无币种汇总数据" />
              )}
            </tbody>
          </table>
        </div>

        <LedgerPnlDataTable
          testId="ledger-pnl-account-summary-table"
          title="科目汇总"
          caption={
            visibleAccountSummaryRows.length === 0
              ? undefined
              : accountSummarySearchNormalized
                ? `共 ${visibleAccountSummaryRows.length} 个科目，搜索匹配 ${accountSummaryDisplayRows.length} 条`
                : accountSummaryExpanded
                  ? `共 ${visibleAccountSummaryRows.length} 个科目，默认按损益绝对值降序`
                  : `共 ${visibleAccountSummaryRows.length} 个科目，默认按损益绝对值降序显示前 ${LEDGER_ACCOUNT_SUMMARY_TOP_N} 行`
          }
          columns={accountSummaryColumns}
          rows={accountSummaryDisplayRows}
          rowKey={(item) => item.account_code}
          isLoading={isLoading}
          isError={isError}
          loadingMessage="科目汇总读取中"
          errorMessage="科目汇总读取失败"
          emptyMessage={
            accountSummarySearchNormalized
              ? `没有匹配"${accountSummarySearchTerm.trim()}"的记录`
              : "暂无科目汇总数据"
          }
          pageSize={0}
          toolbarExtra={
            <>
              <input
                type="search"
                className="ledger-pnl-account-summary-search"
                data-testid="ledger-pnl-account-summary-table-search"
                placeholder="搜索科目代码或名称"
                aria-label="科目汇总搜索"
                value={accountSummarySearchTerm}
                onChange={(event) => setAccountSummarySearchTerm(event.target.value)}
              />
              {!accountSummarySearchNormalized && visibleAccountSummaryRows.length > LEDGER_ACCOUNT_SUMMARY_TOP_N ? (
                <button
                  type="button"
                  className="ledger-pnl-account-summary-expand"
                  data-testid="ledger-pnl-account-summary-table-expand"
                  onClick={() => setAccountSummaryExpanded((expanded) => !expanded)}
                >
                  {accountSummaryExpanded ? "收起" : `展开全部（${visibleAccountSummaryRows.length}）`}
                </button>
              ) : null}
            </>
          }
        />
        </div>
      </section>
  );
}
