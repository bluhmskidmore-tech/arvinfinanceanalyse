import { useMemo } from "react";
import { Button, Select, Spin, Table } from "antd";
import type { TableColumnsType } from "antd";
import { Link } from "react-router-dom";

import type { BondPositionItem } from "../../../api/contracts";
import { buildBondTradingDeskPath } from "../../bond-trading-desk/lib/bondTradingDeskPageModel";
import type { PositionsPrimaryListTableState } from "../model/positionsPageModel";
import { EM_DASH } from "../../../utils/format";
import { formatAmountYi, formatRatePercent } from "../utils/format";

const ALL_BOND_SUBTYPE = "__all_bond_subtypes__";

type BondListRow = BondPositionItem & { key: string };

/**
 * 02 债券持仓工作区：业务种类主筛选 + 明细表 + 分页。
 * 五态展示与分页/筛选回第一页的行为由根组件状态驱动，本组件只渲染。
 */
export default function PositionsBondsWorkspaceSection({
  reportDate,
  subTypeValue,
  subTypeOptions,
  subTypeLoading,
  onSubTypeChange,
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
  subTypeValue: string;
  subTypeOptions: string[] | undefined;
  subTypeLoading: boolean;
  onSubTypeChange: (nextSubType: string) => void;
  listState: PositionsPrimaryListTableState;
  items: BondPositionItem[];
  total: number | undefined;
  page: number;
  totalPages: number;
  canPrev: boolean;
  canNext: boolean;
  onPrevPage: () => void;
  onNextPage: () => void;
}) {
  const dataSource = useMemo<BondListRow[]>(
    () =>
      items.map((row, index) => ({
        key: [
          page,
          index,
          row.bond_code || "",
          row.asset_class || "",
          row.market_value || "",
        ].join(":"),
        ...row,
      })),
    [items, page],
  );

  const columns = useMemo<TableColumnsType<BondListRow>>(
    () => [
      { title: "代码", dataIndex: "bond_code", className: "positions-view__num-cell" },
      { title: "授信主体", dataIndex: "credit_name", render: (v: string | null) => v || EM_DASH },
      { title: "业务种类", dataIndex: "sub_type", render: (v: string | null) => v || EM_DASH },
      { title: "资产分类", dataIndex: "asset_class", render: (v: string | null) => v || EM_DASH },
      {
        title: "市值",
        dataIndex: "market_value",
        align: "right",
        className: "positions-view__num-cell",
        render: (v: string | null) => formatAmountYi(v),
      },
      {
        title: "面值",
        dataIndex: "face_value",
        align: "right",
        className: "positions-view__num-cell",
        render: (v: string | null) => formatAmountYi(v),
      },
      {
        title: "估值净价",
        dataIndex: "valuation_net_price",
        align: "right",
        className: "positions-view__num-cell",
        render: (v: string | null) => (v ? `${v}` : EM_DASH),
      },
      {
        title: "收益率",
        dataIndex: "yield_rate",
        align: "right",
        className: "positions-view__num-cell",
        render: (v: string | null) => formatRatePercent(v),
      },
      {
        title: "单券台",
        key: "trading_desk",
        render: (_: unknown, row: BondPositionItem) =>
          row.bond_code ? (
            <Link
              to={buildBondTradingDeskPath(row.bond_code, reportDate)}
              data-testid={`positions-bond-trading-desk-link-${row.bond_code}`}
            >
              打开
            </Link>
          ) : (
            EM_DASH
          ),
      },
    ],
    [reportDate],
  );

  return (
    <div className="positions-view__workspace">
      <div className="positions-view__workspace-toolbar">
        <label className="positions-view__field">
          <span className="positions-view__field-label">业务种类</span>
          <Select
            aria-label="positions-bond-subtype"
            data-testid="positions-bond-subtype-select"
            className="positions-view__scope-select"
            value={subTypeValue || ALL_BOND_SUBTYPE}
            loading={subTypeLoading}
            options={[
              { value: ALL_BOND_SUBTYPE, label: "全部业务种类" },
              ...(subTypeOptions ?? []).map((s) => ({ value: s, label: s })),
            ]}
            onChange={(next: string) =>
              onSubTypeChange(next === ALL_BOND_SUBTYPE ? "" : next)
            }
          />
        </label>
      </div>

      {listState === "loading" ? (
        <div
          className="positions-view__table-state positions-view__table-state--loading"
          data-testid="positions-bonds-list-loading"
        >
          <Spin />
        </div>
      ) : listState === "error" ? (
        <p className="positions-view__table-state" data-testid="positions-bonds-list-error">
          债券持仓暂不可用
        </p>
      ) : listState === "ready" ? (
        <>
          <Table
            size="small"
            className="positions-view__table"
            pagination={false}
            scroll={{ x: "max-content" }}
            dataSource={dataSource}
            columns={columns}
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
        <p className="positions-view__table-state" data-testid="positions-bonds-list-empty">
          暂无数据
        </p>
      ) : (
        <p className="positions-view__table-state" data-testid="positions-bonds-list-blocked">
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
