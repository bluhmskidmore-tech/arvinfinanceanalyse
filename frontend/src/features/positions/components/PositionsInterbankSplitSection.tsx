import { useMemo } from "react";
import { Input, Spin, Table } from "antd";
import type { TableColumnsType } from "antd";

import type {
  CounterpartyStatItem,
  InterbankCounterpartySplitResponse,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { formatAmountYi, formatRatePercent } from "../utils/format";

type CounterpartyRow = CounterpartyStatItem & { key: string };

const INTERBANK_COUNTERPARTY_RANK_COLUMNS: TableColumnsType<CounterpartyRow> = [
  { title: "对手方", dataIndex: "customer_name", ellipsis: true },
  {
    title: "日均",
    dataIndex: "avg_daily_balance",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string) => formatAmountYi(v),
  },
  {
    title: "利率",
    dataIndex: "weighted_rate",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string | null) => formatRatePercent(v),
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
  hint,
  numDays,
  avgDaily,
  weightedRate,
  customerCount,
  rankTitle,
  emptyLabel,
  loading,
  rows,
}: {
  tone: "asset" | "liability";
  title: string;
  hint: string;
  numDays: number | undefined;
  avgDaily: string | undefined;
  weightedRate: string | null | undefined;
  customerCount: number | undefined;
  rankTitle: string;
  emptyLabel: string;
  loading: boolean;
  rows: CounterpartyRow[];
}) {
  return (
    <div className="positions-view__panel" data-side={tone}>
      <div className="positions-view__panel-head">
        <h3 className="positions-view__panel-title">{title}</h3>
        <span className="positions-view__panel-hint">{hint}</span>
      </div>
      <div className="positions-view__side-metrics">
        <div className="positions-view__side-metric">
          <span className="positions-view__quality-label">日均余额</span>
          <span
            className={`positions-view__side-value positions-view__side-value--${tone}`}
          >
            {formatAmountYi(avgDaily)}
          </span>
        </div>
        <div className="positions-view__side-metric">
          <span className="positions-view__quality-label">加权利率</span>
          <span
            className={`positions-view__side-value positions-view__side-value--${tone}`}
          >
            {weightedRate ? formatRatePercent(weightedRate) : EM_DASH}
          </span>
        </div>
      </div>
      <p className="positions-view__side-note">
        分母：{numDays ?? EM_DASH} 天，{rankTitle} {customerCount ?? 0} 户
      </p>
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
        <p className="positions-view__table-state">{emptyLabel}</p>
      )}
    </div>
  );
}

/**
 * 03' 资产负债结构：资产端/负债端汇总读数 + 客户排名表 + 对手方搜索。
 * 搜索只过滤两侧排名表，不回写查询参数。
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
      </div>
      <div className="positions-view__split-grid positions-view__split-grid--even">
        <InterbankSidePanel
          tone="asset"
          title="资产端（拆出/存放）"
          hint="Top 50，我行收取利息"
          numDays={split?.num_days}
          avgDaily={split?.asset_total_avg_daily}
          weightedRate={split?.asset_total_weighted_rate}
          customerCount={split?.asset_customer_count}
          rankTitle="资产端客户排名"
          emptyLabel="暂无资产端数据"
          loading={loading}
          rows={assetRows}
        />
        <InterbankSidePanel
          tone="liability"
          title="负债端（拆入/存入）"
          hint="Top 50，我行支付利息"
          numDays={split?.num_days}
          avgDaily={split?.liability_total_avg_daily}
          weightedRate={split?.liability_total_weighted_rate}
          customerCount={split?.liability_customer_count}
          rankTitle="负债端客户排名"
          emptyLabel="暂无负债端数据"
          loading={loading}
          rows={liabilityRows}
        />
      </div>
    </div>
  );
}
