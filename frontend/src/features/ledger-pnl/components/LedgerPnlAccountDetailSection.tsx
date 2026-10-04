import { useMemo, useState, type RefObject } from "react";
import type { LedgerPnlDataItem, LedgerPnlDataPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { formatMoney, ledgerMoneyYuan, ledgerSectionState, sortLedgerRowsByAbsYuan } from "../models/ledgerPnlDisplay";
import { LEDGER_PNL_SECTION_IDS } from "../models/ledgerPnlPageConstants";
import type { LedgerPnlContributorSelection } from "./LedgerPnlAnalysisWorkbench";
import { LedgerPnlDataTable, type LedgerPnlDataTableColumn } from "./LedgerPnlDataTable";
import { LedgerPnlSectionLead } from "./LedgerPnlSectionPresentation";

const LEDGER_TABLE_PAGE_SIZE = 25;
/** R1：合成行（仅日均侧存在、总账侧填 0）account_name 为空串，占位说明来源而非留白；行内恒带来源标记。 */
function DetailAccountNameCell({ item }: { item: LedgerPnlDataItem }) {
  const isAverageOnly = item.source_presence === "average_only";
  const trimmedName = item.account_name.trim();
  const nameNode = trimmedName ? (
    <>{item.account_name}</>
  ) : (
    <span className="ledger-pnl-detail-row__placeholder">——（仅日均侧科目）</span>
  );
  if (!isAverageOnly) {
    return nameNode;
  }
  return (
    <>
      {nameNode}
      <span
        className="ledger-pnl-detail-row__source-badge"
        title="仅日均工作簿存在、总账侧填 0 的合成行"
      >
        日均侧合成
      </span>
    </>
  );
}

export function LedgerPnlAccountDetailSection({
  data,
  isLoading,
  isError,
  detailAccountFilter,
  onClearAccountFilter,
  anchorRef,
}: {
  data: LedgerPnlDataPayload | undefined;
  isLoading: boolean;
  isError: boolean;
  detailAccountFilter: LedgerPnlContributorSelection | null;
  onClearAccountFilter: () => void;
  anchorRef: RefObject<HTMLDivElement>;
}) {
  /** R1：明细表默认隐藏日均侧合成行；开关只放开过滤，不改变任何金额。 */
  const [showAverageOnlyRows, setShowAverageOnlyRows] = useState(false);
  const detailRows = useMemo(() => data?.items ?? [], [data?.items]);
  const filteredDetailRows = useMemo(
    () => detailAccountFilter
      ? detailRows.filter((item) => item.account_code === detailAccountFilter.account_code)
      : detailRows,
    [detailAccountFilter, detailRows],
  );
  /*
   * R1 明细表合成行披露：source_presence === "average_only" 的行仅日均工作簿存在、
   * 总账侧填 0，默认隐藏以消除明细噪音；开关显示时不改变任何金额，只放开过滤。
   */
  const averageOnlyDetailRowCount = useMemo(
    () => filteredDetailRows.filter((item) => item.source_presence === "average_only").length,
    [filteredDetailRows],
  );
  const presenceFilteredDetailRows = useMemo(
    () => showAverageOnlyRows
      ? filteredDetailRows
      : filteredDetailRows.filter((item) => item.source_presence !== "average_only"),
    [filteredDetailRows, showAverageOnlyRows],
  );
  const visibleDetailRows = useMemo(
    () => sortLedgerRowsByAbsYuan(presenceFilteredDetailRows, (item) => item.monthly_pnl),
    [presenceFilteredDetailRows],
  );
  /*
   * /data 的金额只汇总 5* 损益科目，items/count 则覆盖全科目。两组集合必须
   * 分开标注；旧后端没有 pnl_account_count 时只展示金额，不回退到全科目行数。
   * no_data 时后端把金额补成 0，所以按 data_status 显式收敛为不展示，避免把补零当真零；
   * 科目筛选生效时也不展示，避免全量合计与筛选后的表体互相矛盾。
   */
  const detailSummaryNote = useMemo(() => {
    if (!data || data.data_status === "no_data" || detailAccountFilter) {
      return undefined;
    }
    const total = formatMoney(data.summary?.total_pnl);
    const pnlAccountCount = data.summary?.pnl_account_count;
    if (total === EM_DASH) {
      return undefined;
    }
    return typeof pnlAccountCount === "number"
      ? `5* 损益合计 ${total} · ${pnlAccountCount} 个损益科目`
      : `5* 损益合计 ${total}`;
  }, [data, detailAccountFilter]);
  /** R1 证据行数文案：只消费后端 summary 字段，不在前端重算恒等式。 */
  const detailEvidenceRowsNote = useMemo(() => {
    if (!data || data.data_status === "no_data" || detailAccountFilter) {
      return undefined;
    }
    const ledgerEvidenceRows = data.summary?.ledger_evidence_rows;
    const averageOnlyRowCount = data.summary?.average_only_row_count;
    if (typeof ledgerEvidenceRows !== "number" || typeof averageOnlyRowCount !== "number") {
      return undefined;
    }
    return `总账证据行 ${ledgerEvidenceRows} · 日均侧合成行 ${averageOnlyRowCount}`;
  }, [data, detailAccountFilter]);
  const detailColumns = useMemo<
    LedgerPnlDataTableColumn<(typeof visibleDetailRows)[number]>[]
  >(
    () => [
      {
        key: "account_code",
        header: "科目代码",
        searchValue: (item) => item.account_code,
        sortValue: (item) => item.account_code,
        render: (item) => item.account_code,
      },
      {
        key: "account_name",
        header: "科目名称",
        searchValue: (item) => item.account_name,
        sortValue: (item) => item.account_name,
        render: (item) => <DetailAccountNameCell item={item} />,
      },
      {
        key: "currency",
        header: "币种",
        sortValue: (item) => item.currency,
        render: (item) => item.currency,
      },
      {
        key: "beginning_balance",
        header: "期初",
        numeric: true,
        sortValue: (item) => ledgerMoneyYuan(item.beginning_balance),
        render: (item) => formatMoney(item.beginning_balance),
      },
      {
        key: "ending_balance",
        header: "期末",
        numeric: true,
        sortValue: (item) => ledgerMoneyYuan(item.ending_balance),
        render: (item) => formatMoney(item.ending_balance),
      },
      {
        key: "monthly_pnl",
        header: "本月净发生额（贷－借）",
        numeric: true,
        sortValue: (item) => ledgerMoneyYuan(item.monthly_pnl),
        render: (item) => formatMoney(item.monthly_pnl),
      },
      {
        key: "daily_avg_balance",
        header: "月日均",
        numeric: true,
        sortValue: (item) => ledgerMoneyYuan(item.daily_avg_balance),
        render: (item) => formatMoney(item.daily_avg_balance),
      },
      {
        key: "days_in_period",
        header: "天数",
        numeric: true,
        sortValue: (item) => item.days_in_period,
        render: (item) => item.days_in_period,
      },
    ],
    [],
  );

  return (
      <section
        ref={anchorRef}
        tabIndex={-1}
        id={LEDGER_PNL_SECTION_IDS.detail}
        data-testid="ledger-pnl-detail-table-anchor"
        className="ledger-pnl-section"
      >
        <LedgerPnlSectionLead
          title="全科目明细"
          state={ledgerSectionState({ isLoading, isError })}
          note={detailSummaryNote}
        />
        <LedgerPnlDataTable
          testId="ledger-pnl-detail-table"
          title="全科目明细"
          caption={
            visibleDetailRows.length > 0 || presenceFilteredDetailRows.length > 0 ? (
              <span className="ledger-pnl-detail-table__caption-lines">
                <span>
                  全科目共 {visibleDetailRows.length} 行，默认按本月净发生额绝对值降序；仅 5* 科目可解释为损益
                </span>
                {detailEvidenceRowsNote ? <span>{detailEvidenceRowsNote}</span> : null}
              </span>
            ) : undefined
          }
          columns={detailColumns}
          rows={visibleDetailRows}
          rowKey={(item) => `${item.account_code}-${item.currency}`}
          isLoading={isLoading}
          isError={isError}
          loadingMessage="科目明细读取中"
          errorMessage="科目明细读取失败"
          emptyMessage="暂无科目明细数据"
          searchPlaceholder="搜索科目代码或名称"
          pageSize={LEDGER_TABLE_PAGE_SIZE}
          toolbarExtra={
            averageOnlyDetailRowCount > 0 ? (
              <label
                className="ledger-pnl-detail-table__average-only-toggle"
                data-testid="ledger-pnl-detail-average-only-toggle"
              >
                <input
                  type="checkbox"
                  checked={showAverageOnlyRows}
                  onChange={(event) => setShowAverageOnlyRows(event.target.checked)}
                />
                显示日均侧合成行（{averageOnlyDetailRowCount}）
              </label>
            ) : null
          }
          notice={
            detailAccountFilter ? (
              <div
                className="ledger-pnl-detail-account-filter"
                data-testid="ledger-pnl-detail-account-filter"
              >
                <div>
                  <strong>
                    当前仅显示 {detailAccountFilter.account_code} {detailAccountFilter.account_name}
                  </strong>
                  <span>
                    月日均不参与本次账户损益穿透；0 可能来自日均源缺行，不能解释为已观测真实零
                  </span>
                </div>
                <button
                  type="button"
                  onClick={onClearAccountFilter}
                  aria-label="清除科目筛选"
                >
                  清除筛选
                </button>
              </div>
            ) : null
          }
        />
      </section>
  );
}
