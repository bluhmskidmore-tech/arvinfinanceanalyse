import { useMemo } from "react";
import { Button, Select, Spin, Table } from "antd";
import type { TableColumnsType } from "antd";

import type { InterbankPositionItem, PositionDirection } from "../../../api/contracts";
import type { PositionsPrimaryListTableState } from "../model/positionsPageModel";
import { EM_DASH } from "../../../utils/format";
import { formatAmountYi, formatRatePercent } from "../utils/format";
import "./PositionsInterbankSections.css";

const ALL_INTERBANK_PRODUCT = "__all_interbank_products__";

export type InterbankDirectionFilter = PositionDirection | "ALL";

const DIRECTION_OPTIONS: { value: InterbankDirectionFilter; label: string }[] = [
  { value: "ALL", label: "全部" },
  { value: "Asset", label: "资产" },
  { value: "Liability", label: "负债" },
];

type InterbankListRow = InterbankPositionItem & { key: string };

const INTERBANK_LIST_COLUMNS: TableColumnsType<InterbankListRow> = [
  { title: "交易ID", dataIndex: "deal_id", className: "positions-view__num-cell" },
  {
    title: "对手方",
    dataIndex: "counterparty",
    ellipsis: true,
    render: (v: string | null) => v || EM_DASH,
  },
  { title: "产品类型", dataIndex: "product_type", render: (v: string | null) => v || EM_DASH },
  { title: "方向", dataIndex: "direction", render: (v: string | null) => v || EM_DASH },
  {
    title: "金额",
    dataIndex: "amount",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string) => formatAmountYi(v),
  },
  {
    title: "利率",
    dataIndex: "interest_rate",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string | null) => formatRatePercent(v),
  },
  {
    title: "到期日",
    dataIndex: "maturity_date",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string | null) => v || EM_DASH,
  },
];

/**
 * 02' 同业持仓工作区：产品类型 + 方向双内联筛选（无弹层）+ 明细表 + 分页。
 * 方向切换沿用根组件 handleDirectionChange 的重置分页语义。
 */
export default function PositionsInterbankWorkspaceSection({
  reportDate,
  productTypeValue,
  productTypeOptions,
  productTypeLoading,
  onProductTypeChange,
  direction,
  onDirectionChange,
  listState,
  items,
  total,
  page,
  totalPages,
  canPrev,
  canNext,
  onPrevPage,
  onNextPage,
}: {
  reportDate: string;
  productTypeValue: string;
  productTypeOptions: string[] | undefined;
  productTypeLoading: boolean;
  onProductTypeChange: (nextProductType: string) => void;
  direction: InterbankDirectionFilter;
  onDirectionChange: (nextDirection: InterbankDirectionFilter) => void;
  listState: PositionsPrimaryListTableState;
  items: InterbankPositionItem[];
  total: number | undefined;
  page: number;
  totalPages: number;
  canPrev: boolean;
  canNext: boolean;
  onPrevPage: () => void;
  onNextPage: () => void;
}) {
  const dataSource = useMemo<InterbankListRow[]>(
    () =>
      items.map((row, index) => ({
        key: [
          page,
          index,
          row.deal_id || "",
          row.counterparty || "",
          row.amount || "",
        ].join(":"),
        ...row,
      })),
    [items, page],
  );

  return (
    <div className="positions-view__workspace">
      <div className="positions-view__workspace-toolbar">
        <label className="positions-view__field">
          <span className="positions-view__field-label">产品类型</span>
          <Select
            aria-label="positions-interbank-product-type"
            className="positions-view__scope-select"
            value={productTypeValue || ALL_INTERBANK_PRODUCT}
            loading={productTypeLoading}
            options={[
              { value: ALL_INTERBANK_PRODUCT, label: "全部产品类型" },
              ...(productTypeOptions ?? []).map((s) => ({ value: s, label: s })),
            ]}
            onChange={(next: string) =>
              onProductTypeChange(next === ALL_INTERBANK_PRODUCT ? "" : next)
            }
          />
        </label>
        <label className="positions-view__field">
          <span className="positions-view__field-label">方向</span>
          <Select
            aria-label="positions-interbank-direction"
            className="positions-interbank__direction-select"
            value={direction}
            options={DIRECTION_OPTIONS}
            onChange={(v) => onDirectionChange(v as InterbankDirectionFilter)}
          />
        </label>
      </div>

      {listState === "loading" ? (
        <div
          className="positions-view__table-state positions-view__table-state--loading"
          data-testid="positions-interbank-list-loading"
        >
          <Spin />
        </div>
      ) : listState === "error" ? (
        <p className="positions-view__table-state" data-testid="positions-interbank-list-error">
          同业持仓暂不可用
        </p>
      ) : listState === "ready" ? (
        <>
          <Table
            size="small"
            className="positions-view__table"
            pagination={false}
            scroll={{ x: "max-content" }}
            dataSource={dataSource}
            columns={INTERBANK_LIST_COLUMNS}
          />
          {total != null ? (
            <div className="positions-view__pager">
              <span className="positions-view__pager-note">
                共 {total} 条，第 {page}/{Math.max(1, totalPages)} 页
              </span>
              <div className="positions-view__pager-buttons">
                <Button disabled={!canPrev} onClick={onPrevPage}>
                  上一页
                </Button>
                <Button disabled={!canNext} onClick={onNextPage}>
                  下一页
                </Button>
              </div>
            </div>
          ) : null}
        </>
      ) : listState === "empty" ? (
        <p className="positions-view__table-state" data-testid="positions-interbank-list-empty">
          暂无数据
        </p>
      ) : (
        <p className="positions-view__table-state" data-testid="positions-interbank-list-blocked">
          {reportDate
            ? page > 1
              ? "当前页无明细，正在返回第一页"
              : "当前范围明细暂不可用"
            : "请先选择可用报告日"}
        </p>
      )}
    </div>
  );
}
