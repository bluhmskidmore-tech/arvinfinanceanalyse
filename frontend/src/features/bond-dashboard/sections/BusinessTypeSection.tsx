import { useMemo } from "react";
import { Table } from "antd";
import type { TableColumnsType } from "antd";

import type { BondBusinessTypeMetricItem, Numeric } from "../../../api/contracts";
import { EM_DASH } from "../../../pageModel";
import BondDashboardSectionLead, {
  type BondDashboardSectionState,
} from "../components/BondDashboardSectionLead";
import { businessTypeMetricNumber } from "../model/bondDashboardPageModel";
import { formatRatePercent, formatYears, formatYi } from "../utils/format";
import "./BondDashboardTableSections.css";

type BusinessTypeMetricRow = BondBusinessTypeMetricItem & { key: string };

/** 数值列等宽（BondDashboardTableSections.css）。 */
const NUM_CELL = "bond-dashboard-table-num-cell";

/** 覆盖率（0-1 比率 Numeric，null=该组市值为零无分母）→ 两位百分比。 */
function coveragePercent(value: Numeric | null | undefined): string {
  const text = formatRatePercent(value);
  return text === EM_DASH ? EM_DASH : `${text}%`;
}

/**
 * 前四列与页面拆分前逐字一致（数值判空走模型层 businessTypeMetricNumber）；
 * 覆盖率两列为 2026-08-13 后端补出的质量披露（承载该指标的市值占比），
 * 解释「加权值为 EM_DASH / 低覆盖」的口径面。
 */
const BUSINESS_TYPE_METRIC_COLUMNS: TableColumnsType<BusinessTypeMetricRow> = [
  { title: "业务类型", dataIndex: "name", ellipsis: true },
  {
    title: "市值（亿）",
    dataIndex: "market_value",
    align: "right",
    className: NUM_CELL,
    render: (v: string) => formatYi(businessTypeMetricNumber(v)),
  },
  {
    /* 与 01 区 KPI 带同名（加权到期收益率），同概念不再第三种叫法。 */
    title: "加权到期收益率",
    dataIndex: "weighted_avg_ytm_pct",
    align: "right",
    className: NUM_CELL,
    render: (v: string) => {
      const pct = businessTypeMetricNumber(v);
      return pct === null ? EM_DASH : `${formatRatePercent(pct / 100)}%`;
    },
  },
  {
    title: "YTM 覆盖率",
    dataIndex: "weighted_avg_ytm_coverage_ratio",
    align: "right",
    className: NUM_CELL,
    render: coveragePercent,
  },
  {
    title: "加权久期",
    dataIndex: "weighted_avg_duration",
    align: "right",
    className: NUM_CELL,
    render: (v: string) => formatYears(businessTypeMetricNumber(v)),
  },
  {
    title: "久期覆盖率",
    dataIndex: "weighted_avg_duration_coverage_ratio",
    align: "right",
    className: NUM_CELL,
    render: coveragePercent,
  },
];

type BusinessTypeSectionProps = {
  items: BondBusinessTypeMetricItem[] | undefined;
  loading: boolean;
  error: boolean;
};

/** 分区头状态位：loading/error/empty 三态露一句话，正常返回 null。 */
function sectionLeadState(
  loading: boolean,
  error: boolean,
  isEmpty: boolean,
): BondDashboardSectionState {
  if (loading) return { label: "读取中", tone: "loading" };
  if (error) return { label: "读取失败", tone: "error" };
  if (isEmpty) return { label: "暂无数据", tone: "empty" };
  return null;
}

/** 05 业务类型指标：加权指标表 + 三态（文案与拆分前逐字一致）。 */
export default function BusinessTypeSection({ items, loading, error }: BusinessTypeSectionProps) {
  const rows = useMemo<BusinessTypeMetricRow[]>(
    () =>
      (items ?? []).map((row) => ({
        key: row.name,
        ...row,
      })),
    [items],
  );
  const isEmpty = (items?.length ?? 0) === 0;

  return (
    <section className="bond-dashboard-section" id="bond-dashboard-section-business-type">
      <BondDashboardSectionLead
        title="业务类型指标"
        state={sectionLeadState(loading, error, isEmpty)}
      />
      <div
        className="bond-dashboard-page__panel bond-dashboard-table-panel"
        data-testid="bond-dashboard-business-type-metrics"
      >
        <h3 className="bond-dashboard-table-panel__title">业务类型加权指标</h3>
        {loading ? (
          <p className="bond-dashboard-page__surface bond-dashboard-page__surface--loading">
            载入中…
          </p>
        ) : error ? (
          <p className="bond-dashboard-page__surface bond-dashboard-page__surface--error">
            指标暂不可用
          </p>
        ) : isEmpty ? (
          <p className="bond-dashboard-page__surface bond-dashboard-page__surface--empty">
            暂无数据
          </p>
        ) : (
          <Table
            size="small"
            pagination={false}
            scroll={{ x: "max-content" }}
            dataSource={rows}
            columns={BUSINESS_TYPE_METRIC_COLUMNS}
          />
        )}
      </div>
    </section>
  );
}
