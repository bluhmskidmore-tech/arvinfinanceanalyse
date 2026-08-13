import type { ProductCategorySpreadReadoutSurface } from "./model/productCategoryPnlSpreadReadoutModel";

const HEADLINE_METRIC_KEYS = new Set([
  "interest_earning_spread",
  "interest_spread_with_tpl",
]);

type ProductCategorySpreadReadoutProps = {
  reportDate: string;
  surface: ProductCategorySpreadReadoutSurface;
};

/**
 * 主屏利差读数：直出后端两个口径的收益率/成本率/利差，并显式标注单月还是累计。
 * 所有数值来自 payload 的 `interest_earning_spread` / `interest_spread` /
 * `liability_cost_decomposition`，前端不重算。
 */
export function ProductCategorySpreadReadout(
  props: ProductCategorySpreadReadoutProps,
) {
  const { surface } = props;
  return (
    <section
      data-testid="product-category-spread-readout"
      className="product-category-formal-readiness product-category-spread-readout"
      aria-label="整体利差读数"
    >
      <div className="product-category-formal-readiness__header">
        <div className="product-category-formal-readiness__copy">
          <h2 className="product-category-formal-readiness__title">整体利差</h2>
          <p
            data-testid="product-category-spread-readout-caliber"
            className="product-category-formal-readiness__description"
          >
            {surface.caliberNote}
          </p>
        </div>
        <div className="product-category-formal-readiness__headline-meta">
          <span>{props.reportDate || "待选报告日"}</span>
          <strong data-testid="product-category-spread-readout-view">
            {surface.viewLabel}
          </strong>
        </div>
      </div>

      {surface.state === "ready" ? (
        <div
          data-testid="product-category-spread-readout-metrics"
          className="product-category-formal-readiness__totals product-category-spread-readout__totals"
        >
          {surface.metrics.map((item) => (
            <div
              key={item.key}
              data-testid={`product-category-spread-readout-metric-${item.key}`}
              className={
                HEADLINE_METRIC_KEYS.has(item.key)
                  ? "product-category-formal-readiness__metric product-category-spread-readout__metric--headline"
                  : "product-category-formal-readiness__metric"
              }
            >
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              <small>{item.note}</small>
            </div>
          ))}
        </div>
      ) : (
        <p
          data-testid="product-category-spread-readout-unavailable"
          className="product-category-spread-readout__gap"
        >
          {surface.reason}
        </p>
      )}

      <div className="product-category-spread-readout__caption">
        <strong>负债端 CLN 拖累</strong>
        <span>信用联结票据对负债端成本率的影响，后端直出</span>
      </div>
      {surface.liability.state === "ready" ? (
        <div
          data-testid="product-category-spread-readout-liability"
          className="product-category-formal-readiness__totals product-category-spread-readout__totals product-category-spread-readout__totals--liability"
        >
          {surface.liability.metrics.map((item) => (
            <div
              key={item.key}
              data-testid={`product-category-spread-readout-liability-metric-${item.key}`}
              className="product-category-formal-readiness__metric"
            >
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              <small>{item.note}</small>
            </div>
          ))}
        </div>
      ) : (
        <p
          data-testid="product-category-spread-readout-liability-gap"
          className="product-category-spread-readout__gap"
        >
          {surface.liability.reason}
        </p>
      )}
    </section>
  );
}
