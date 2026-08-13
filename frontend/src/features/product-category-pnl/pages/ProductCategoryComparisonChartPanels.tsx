import type { ReactNode } from "react";
import type { EChartsReactProps } from "echarts-for-react/lib/types";

import type { ResultMeta } from "../../../api/contracts";
import { DataQualityBanner } from "../../../components/page/DataQualityBanner";
import type { EChartsOption } from "../../../lib/echarts";
import { LazyChartMount } from "./LazyChartMount";
import { LazyReactECharts } from "./LazyReactECharts";
import type { ProductCategoryComparisonReadout } from "./ProductCategoryComparisonCharts";
import type {
  ProductCategoryInterestSpreadAttributionSurface,
  ProductCategoryYearComparisonStatus,
} from "./productCategoryPnlPageModel";

type DerivedChartPanelProps = {
  testId: string;
  title: string;
  description: string;
  option: EChartsOption | null;
  readout?: ReactNode;
  comparisonStatus?: ProductCategoryYearComparisonStatus;
  wide?: boolean;
  onEvents?: EChartsReactProps["onEvents"];
};

export function ProductCategoryComparisonChartReadout(props: {
  readout: ProductCategoryComparisonReadout | null;
}) {
  if (!props.readout) {
    return (
      <div className="product-category-derived-chart__readout">
        <span className="product-category-derived-chart__readout-label">
          当前已载入历史中暂无共同可比月
        </span>
      </div>
    );
  }
  return (
    <div className="product-category-derived-chart__readout">
      <div className="product-category-derived-chart__readout-item">
        <span className="product-category-derived-chart__readout-label">
          {props.readout.priorPeriodLabel} · {props.readout.monthLabel}
        </span>
        <strong className="product-category-derived-chart__readout-value">
          {props.readout.priorValueLabel}
        </strong>
      </div>
      <div className="product-category-derived-chart__readout-item">
        <span className="product-category-derived-chart__readout-label">
          {props.readout.currentPeriodLabel} · {props.readout.monthLabel}
        </span>
        <strong className="product-category-derived-chart__readout-value">
          {props.readout.currentValueLabel}
        </strong>
      </div>
      <div className="product-category-derived-chart__readout-item">
        <span className="product-category-derived-chart__readout-label">
          同比差
        </span>
        <strong
          className={`product-category-derived-chart__readout-delta is-${props.readout.deltaTone}`}
        >
          {props.readout.deltaLabel}
        </strong>
      </div>
    </div>
  );
}

export function DerivedChartPanel(props: DerivedChartPanelProps) {
  if (!props.option) {
    return null;
  }
  const className = props.wide
    ? "product-category-derived-chart product-category-derived-chart--wide"
    : "product-category-derived-chart";
  const comparisonQualityLabel =
    props.comparisonStatus?.comparableMonthCount === 0
      ? "缺少可比值"
      : props.comparisonStatus?.qualityState === "ok"
        ? "数据正常"
        : props.comparisonStatus?.qualityState === "degraded"
          ? `降级${props.comparisonStatus.qualityIssueMonthCount}期`
          : "质量待核";
  const comparisonDisplayState =
    props.comparisonStatus?.comparableMonthCount === 0
      ? "unknown"
      : (props.comparisonStatus?.qualityState ?? "unknown");
  return (
    <article className={className} data-testid={props.testId}>
      <div className="product-category-derived-chart__header">
        <h3 className="product-category-derived-chart__title">{props.title}</h3>
        <p className="product-category-derived-chart__description">
          {props.description}
        </p>
      </div>
      {props.comparisonStatus ? (
        <div
          className={`product-category-derived-chart__status is-${comparisonDisplayState}`}
          data-comparison-state={
            props.comparisonStatus.comparableMonthCount === 0
              ? "insufficient"
              : "ready"
          }
          data-quality-state={props.comparisonStatus.qualityState}
        >
          <span>可比 {props.comparisonStatus.comparableMonthCount}/12</span>
          {" · "}
          <span>{comparisonQualityLabel}</span>
        </div>
      ) : null}
      {props.readout}
      <LazyChartMount
        placeholderClassName="product-category-derived-chart__canvas"
        placeholderTestId={`${props.testId}-canvas-placeholder`}
      >
        <LazyReactECharts
          option={props.option}
          className="product-category-derived-chart__canvas"
          notMerge
          lazyUpdate
          onEvents={props.onEvents}
        />
      </LazyChartMount>
    </article>
  );
}

export function ProductCategoryInterestSpreadAttributionPanel(props: {
  surface: ProductCategoryInterestSpreadAttributionSurface | null;
  resultMeta?: ResultMeta | null;
}) {
  if (!props.surface) {
    return null;
  }
  const basisLabel =
    props.surface.selected.basis === "cny" ? "人民币口径" : "全口径";
  return (
    <article
      className="product-category-interest-spread-attribution"
      data-testid="product-category-interest-spread-attribution"
    >
      <div className="product-category-interest-spread-attribution__header">
        <div>
          <h3 className="product-category-interest-spread-attribution__title">
            后端利差字段归因
          </h3>
          <p className="product-category-interest-spread-attribution__description">
            {basisLabel} {props.surface.selected.month}月 ·{" "}
            使用后端返回的含TPL口径利差字段，不代表已激活正式指标
          </p>
        </div>
        <span className="product-category-interest-spread-attribution__badge">
          {props.surface.complete ? "字段闭合" : "待补数"}
        </span>
      </div>
      <div className="product-category-interest-spread-attribution__summary">
        {props.surface.rows.map((row) => (
          <div
            className="product-category-interest-spread-attribution__metric"
            key={row.key}
          >
            <span className="product-category-interest-spread-attribution__metric-label">
              {row.label}
            </span>
            <strong>{row.contributionLabel}</strong>
            <span>
              {row.priorLabel} → {row.currentLabel}
            </span>
          </div>
        ))}
      </div>
      <DataQualityBanner
        resultMeta={props.resultMeta}
        degradedReasons={props.surface.incompleteReasons}
      />
      <div className="product-category-interest-spread-attribution__table-wrap">
        <table className="product-category-interest-spread-attribution__table">
          <thead>
            <tr>
              <th>{"\u6307\u6807"}</th>
              <th>{"\u4e0a\u5e74\u540c\u6708"}</th>
              <th>{"\u5f53\u524d\u6708"}</th>
              <th>{"\u53d8\u5316(bp)"}</th>
              <th>{"\u5f52\u56e0\u8bf4\u660e"}</th>
            </tr>
          </thead>
          <tbody>
            {props.surface.rows.map((row) => (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td>{row.priorLabel}</td>
                <td>{row.currentLabel}</td>
                <td>{row.contributionLabel}</td>
                <td>{row.explanation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="product-category-interest-spread-attribution__details">
        {props.surface.details.map((detail) => (
          <section
            className="product-category-interest-spread-attribution__detail"
            key={detail.key}
          >
            <h4>{detail.label}</h4>
            <div className="product-category-interest-spread-attribution__detail-grid">
              {[detail.prior, detail.current].map((point, index) => (
                <dl
                  className="product-category-interest-spread-attribution__detail-list"
                  key={`${detail.key}-${index}`}
                >
                  <dt>{point.reportLabel}</dt>
                  <dd>
                    {"\u65e5\u5747\u989d"} {point.amountLabel}
                  </dd>
                  <dd>
                    {"\u5229\u606f\u6536\u652f"} {point.cashLabel}
                  </dd>
                  <dd>
                    {"\u6536\u76ca\u7387/\u6210\u672c"} {point.yieldLabel}
                  </dd>
                </dl>
              ))}
            </div>
          </section>
        ))}
      </div>
    </article>
  );
}
