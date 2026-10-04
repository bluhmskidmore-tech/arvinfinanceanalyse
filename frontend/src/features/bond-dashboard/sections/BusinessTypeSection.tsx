import type { BondBusinessTypeMetricItem, Numeric } from "../../../api/contracts";
import { DataTable, SectionHead, type DataTableColumn } from "../../../components/layout";
import { EM_DASH } from "../../../pageModel";
import { businessTypeMetricNumber } from "../model/bondDashboardPageModel";
import {
  bondSectionState,
  bondSectionStatusFromStates,
  type BondSectionDataState,
} from "../sectionStatus";
import { formatRatePercent, formatYears, formatYi } from "../utils/format";
import "./BondDashboardTableSections.css";

/** 覆盖率（0-1 比率 Numeric，null=该组市值为零无分母）→ 两位百分比。 */
function coveragePercent(value: Numeric | null | undefined): string {
  const text = formatRatePercent(value);
  return text === EM_DASH ? EM_DASH : `${text}%`;
}

/**
 * 市值/久期列判空走模型层 businessTypeMetricNumber（原始字符串字段）；
 * 加权到期收益率列自 2026-08-26 起为 governed Numeric（与 Headline weighted_ytm 同口径），
 * 复用 coveragePercent 渲染，缺值走 raw=null → EM_DASH。
 * 覆盖率两列为 2026-08-13 后端补出的质量披露（承载该指标的市值占比），
 * 解释「加权值为 EM_DASH / 低覆盖」的口径面。
 * 数值列右对齐与等宽 tabular 由 DataTable 的 align="numeric" 承担，页面不再出列样式。
 */
const BUSINESS_TYPE_METRIC_COLUMNS: readonly DataTableColumn<BondBusinessTypeMetricItem>[] = [
  { key: "name", title: "业务类型" },
  {
    key: "market_value",
    title: "市值（亿）",
    align: "numeric",
    render: (row) => formatYi(businessTypeMetricNumber(row.market_value)),
  },
  {
    /* 与 01 区 KPI 带同名（加权到期收益率），同概念不再第三种叫法。 */
    key: "weighted_avg_ytm",
    title: "加权到期收益率",
    align: "numeric",
    render: (row) => coveragePercent(row.weighted_avg_ytm),
  },
  {
    key: "weighted_avg_ytm_coverage_ratio",
    title: "YTM 覆盖率",
    align: "numeric",
    render: (row) => coveragePercent(row.weighted_avg_ytm_coverage_ratio),
  },
  {
    key: "weighted_avg_duration",
    title: "加权久期",
    align: "numeric",
    render: (row) => formatYears(businessTypeMetricNumber(row.weighted_avg_duration)),
  },
  {
    key: "weighted_avg_duration_coverage_ratio",
    title: "久期覆盖率",
    align: "numeric",
    render: (row) => coveragePercent(row.weighted_avg_duration_coverage_ratio),
  },
];

type BusinessTypeSectionProps = {
  items: BondBusinessTypeMetricItem[] | undefined;
  state: BondSectionDataState;
};

/** 05 业务类型指标：加权指标表 + 五态（文案与拆分前逐字一致）。 */
export default function BusinessTypeSection({ items, state }: BusinessTypeSectionProps) {
  const isEmpty = (items?.length ?? 0) === 0;
  const status = bondSectionStatusFromStates([state], isEmpty);

  return (
    <section className="bond-dashboard-section" id="bond-dashboard-section-business-type">
      <SectionHead title="业务类型指标" state={bondSectionState(status)} />
      <div
        className="bond-dashboard-page__panel"
        data-testid="bond-dashboard-business-type-metrics"
      >
        <div className="bond-dashboard-page__panel-head">
          <h3 className="bond-dashboard-page__panel-head-title">业务类型加权指标</h3>
        </div>
        {/*
         * 表体状态用分区自己的读取结果，不用分区头那个含 empty 的合成状态：
         * 后者会盖掉 DataTable 对「rows 未到达 vs 真空」的区分。
         * 分区失败时后端原因优先，缺原因时保留旧文案「指标暂不可用」。
         */}
        <DataTable<BondBusinessTypeMetricItem>
          rows={items}
          rowKey="name"
          columns={BUSINESS_TYPE_METRIC_COLUMNS}
          status={state.status}
          errorMessage={state.message ?? "指标暂不可用"}
          skeletonRows={5}
        />
      </div>
    </section>
  );
}
