import { useMemo } from "react";
import { Input, Spin, Table } from "antd";
import type { TableColumnsType } from "antd";

import type {
  CounterpartyStatItem,
  InterbankCounterpartySplitResponse,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { formatAmountYi, formatAmountYiNumber, formatRatePercent } from "../utils/format";
import "./PositionsInterbankSections.css";

type CounterpartyRow = CounterpartyStatItem & { key: string };

const INTERBANK_COUNTERPARTY_RANK_COLUMNS: TableColumnsType<CounterpartyRow> = [
  { title: "对手方", dataIndex: "customer_name", ellipsis: true },
  {
    title: "日均(亿元)",
    dataIndex: "avg_daily_balance",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string) => formatAmountYiNumber(v),
  },
  {
    title: "利率",
    dataIndex: "weighted_rate",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string | null) => formatRatePercent(v),
  },
  {
    title: "笔数",
    dataIndex: "transaction_count",
    align: "right",
    className: "positions-view__num-cell",
  },
];

function useFilteredRows(items: CounterpartyStatItem[] | undefined, searchText: string) {
  return useMemo<CounterpartyRow[]>(() => {
    const source = items ?? [];
    const q = searchText.trim();
    const filtered = q ? source.filter((x) => x.customer_name.includes(q)) : source;
    return filtered.map((row) => ({ key: row.customer_name, ...row }));
  }, [items, searchText]);
}

function InterbankSidePanel({
  tone,
  title,
  dotTitle,
  hint,
  totalAmount,
  avgDaily,
  weightedRate,
  emptyLabel,
  sourceCount,
  loading,
  rows,
}: {
  tone: "asset" | "liability";
  title: string;
  dotTitle: string;
  hint: string;
  totalAmount: string | undefined;
  avgDaily: string | undefined;
  weightedRate: string | null | undefined;
  emptyLabel: string;
  sourceCount: number;
  loading: boolean;
  rows: CounterpartyRow[];
}) {
  const valueClass = `positions-view__side-value positions-view__side-value--${tone}`;
  return (
    <div className="positions-view__panel" data-side={tone}>
      <div className="positions-view__panel-head">
        <h3 className="positions-view__panel-title">
          <span
            className={`positions-interbank__side-dot positions-interbank__side-dot--${tone}`}
            title={dotTitle}
          />
          {title}
        </h3>
        <span className="positions-view__panel-hint" title={dotTitle}>
          {hint}
        </span>
      </div>
      <div className="positions-interbank__side-metrics">
        <div className="positions-view__side-metric">
          <span className="positions-view__quality-label">区间累计</span>
          <span className={valueClass}>{formatAmountYi(totalAmount)}</span>
        </div>
        <div className="positions-view__side-metric">
          <span className="positions-view__quality-label">日均余额</span>
          <span className={valueClass}>{formatAmountYi(avgDaily)}</span>
        </div>
        <div className="positions-view__side-metric">
          <span className="positions-view__quality-label">加权利率</span>
          <span className={valueClass}>{formatRatePercent(weightedRate)}</span>
        </div>
      </div>
      {loading ? (
        <div className="positions-view__table-state positions-view__table-state--loading">
          <Spin />
        </div>
      ) : rows.length > 0 ? (
        <Table
          size="small"
          className="positions-view__table"
          pagination={false}
          scroll={{ x: "max-content", y: 240 }}
          dataSource={rows}
          columns={INTERBANK_COUNTERPARTY_RANK_COLUMNS}
        />
      ) : (
        <p className="positions-view__table-state">
          {sourceCount > 0 ? "无匹配对手方" : emptyLabel}
        </p>
      )}
    </div>
  );
}

/**
 * 03' 资产负债结构：两侧各三格读数（区间累计/日均余额/加权利率）+ 客户排名表 +
 * 对手方搜索。搜索只过滤两侧排名表，不回写查询参数；「分母」说明全分区仅一处。
 */
export default function PositionsInterbankSplitSection({
  split,
  loading,
  searchText,
  onSearchTextChange,
}: {
  split: InterbankCounterpartySplitResponse | undefined;
  loading: boolean;
  searchText: string;
  onSearchTextChange: (next: string) => void;
}) {
  const assetRows = useFilteredRows(split?.asset_items, searchText);
  const liabilityRows = useFilteredRows(split?.liability_items, searchText);

  return (
    <div className="positions-view__workspace">
      <div className="positions-view__workspace-toolbar">
        <label className="positions-view__field positions-view__field--wide">
          <span className="positions-view__field-label">对手方搜索</span>
          <Input
            className="positions-view__search-input"
            placeholder="输入对手方名称…"
            value={searchText}
            onChange={(e) => onSearchTextChange(e.target.value)}
          />
        </label>
        <p className="positions-interbank__split-note" title="日均余额 = 区间累计 ÷ 区间天数">
          分母：{split?.num_days ?? EM_DASH} 天
        </p>
      </div>
      <div className="positions-view__split-grid positions-view__split-grid--even">
        <InterbankSidePanel
          tone="asset"
          title="资产端（拆出/存放）"
          dotTitle="资产端：我行收取利息"
          hint={`我行收取利息，共 ${split?.asset_customer_count ?? EM_DASH} 户，展示 Top 50`}
          totalAmount={split?.asset_total_amount}
          avgDaily={split?.asset_total_avg_daily}
          weightedRate={split?.asset_total_weighted_rate}
          emptyLabel="暂无资产端数据"
          sourceCount={split?.asset_items.length ?? 0}
          loading={loading}
          rows={assetRows}
        />
        <InterbankSidePanel
          tone="liability"
          title="负债端（拆入/存入）"
          dotTitle="负债端：我行支付利息"
          hint={`我行支付利息，共 ${split?.liability_customer_count ?? EM_DASH} 户，展示 Top 50`}
          totalAmount={split?.liability_total_amount}
          avgDaily={split?.liability_total_avg_daily}
          weightedRate={split?.liability_total_weighted_rate}
          emptyLabel="暂无负债端数据"
          sourceCount={split?.liability_items.length ?? 0}
          loading={loading}
          rows={liabilityRows}
        />
      </div>
    </div>
  );
}
