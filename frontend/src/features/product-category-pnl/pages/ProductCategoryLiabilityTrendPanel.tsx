import { Fragment } from "react";

import type { EChartsOption } from "../../../lib/echarts";
import { LazyChartCard } from "./LazyReactECharts";
import {
  ProductCategoryLiabilityCurrencyMatrixMobileReadout,
  ProductCategoryLiabilityDetailMatrixMobileReadout,
  ProductCategoryLiabilityFallbackMobileReadout,
} from "./ProductCategoryAttributionPanels";
import {
  ProductCategoryLiabilityViewToggle,
  type ProductCategoryLiabilityView,
} from "./ProductCategoryLiabilityViewToggle";
import type { ProductCategoryLiabilitySideTrendSurface } from "./productCategoryPnlPageModel";

type ProductCategoryLiabilityTrendPanelProps = {
  trendSurface: ProductCategoryLiabilitySideTrendSurface;
  matrixSurface: ProductCategoryLiabilitySideTrendSurface;
  chartOption: EChartsOption | null;
  matrixView: ProductCategoryLiabilityView;
  onMatrixViewChange: (view: ProductCategoryLiabilityView) => void;
  alternateView: {
    active: boolean;
    hasData: boolean;
    isFetching: boolean;
    isError: boolean;
  };
};

export function ProductCategoryLiabilityTrendPanel({
  trendSurface,
  matrixSurface,
  chartOption,
  matrixView,
  onMatrixViewChange,
  alternateView,
}: ProductCategoryLiabilityTrendPanelProps) {
  return (
    <article
      className="product-category-diagnostics__card product-category-liability-side-trend"
      data-testid="product-category-liability-side-trend"
    >
      <div className="product-category-diagnostics__header">
        <div className="product-category-diagnostics__intro">
          <h3 className="product-category-diagnostics__title">
            负债端趋势分析
          </h3>
          <p className="product-category-diagnostics__description">
            负债侧产品类别口径：使用当前产品分类 payload
            的负债明细行和后端 liability_total，展示日均额与利率走势。
          </p>
        </div>
        <span className="product-category-diagnostics__summary">
          负债侧产品类别口径
        </span>
      </div>
      {chartOption ? (
        <LazyChartCard
          flat
          ariaLabel="负债端趋势分析"
          height={280}
          option={chartOption}
          canvasClassName="product-category-derived-chart__canvas"
          testId="product-category-liability-side-trend-chart"
        />
      ) : (
        <div
          className="product-category-diagnostics__empty"
          data-testid="product-category-liability-side-trend-empty"
        >
          {trendSurface.emptyCopy ??
            "负债端趋势数据不完整，无法绘制完整走势。"}
        </div>
      )}
      {trendSurface.incompleteReasons.length > 0 ? (
        <div
          className="product-category-diagnostics__empty"
          data-testid="product-category-liability-side-trend-incomplete"
        >
          {trendSurface.incompleteReasons.join("；")}
        </div>
      ) : null}
      {trendSurface.detailMatrix.rows.length > 0 ? (
        <>
          <ProductCategoryLiabilityViewToggle
            ariaLabel="负债明细矩阵展示口径"
            className="product-category-liability-matrix__controls"
            testId="product-category-liability-matrix-display-mode"
            value={matrixView}
            onChange={onMatrixViewChange}
          />
          <p
            className="product-category-liability-matrix__mode-note"
            data-testid="product-category-liability-matrix-caliber-note"
            role={
              alternateView.active &&
              alternateView.isFetching
                ? "status"
                : undefined
            }
          >
            {alternateView.active &&
            alternateView.isFetching
              ? `正在载入后端原始${matrixView === "ytd" ? "年初至今累计" : "单月"}口径…`
              : alternateView.active &&
                  (alternateView.isError ||
                    !alternateView.hasData)
                ? `后端原始${matrixView === "ytd" ? "年初至今累计" : "单月"}口径暂不可用，当前保留原口径。`
                : `当前显示后端原始${matrixView === "ytd" ? "年初至今累计" : "单月"}口径。`}
          </p>
          <ProductCategoryLiabilityDetailMatrixMobileReadout
            matrix={matrixSurface.detailMatrix}
          />
          <details
            className="product-category-liability-matrix__disclosure"
            data-testid="product-category-liability-side-detail-disclosure"
          >
            <summary>
              <span>全币种明细矩阵</span>
              <small>
                {
                  matrixSurface.detailMatrix.periods
                    .length
                }
                期 ·{" "}
                {matrixSurface.detailMatrix.rows.length}
                行
              </small>
            </summary>
            <div className="product-category-diagnostics__table-wrap product-category-liability-matrix__wrap">
              <table
                className="product-category-diagnostics__table product-category-liability-matrix"
                data-testid="product-category-liability-side-detail-matrix"
                aria-label="负债端明细趋势矩阵"
              >
                <thead>
                  <tr>
                    <th
                      className="product-category-diagnostics__table-head product-category-liability-matrix__item-head"
                      rowSpan={2}
                      scope="col"
                    >
                      负债明细
                    </th>
                    {matrixSurface.detailMatrix.periods.map(
                      (period) => (
                        <th
                          key={period.key}
                          className="product-category-diagnostics__table-head product-category-liability-matrix__group-head"
                          colSpan={2}
                          scope="colgroup"
                          data-testid={`product-category-liability-side-period-${period.key}`}
                        >
                          {period.label}
                        </th>
                      ),
                    )}
                    <th
                      className="product-category-diagnostics__table-head product-category-liability-matrix__group-head"
                      colSpan={2}
                      scope="colgroup"
                    >
                      {
                        matrixSurface.detailMatrix
                          .movementGroupLabel
                      }
                    </th>
                  </tr>
                  <tr>
                    {matrixSurface.detailMatrix.periods.map(
                      (period) => (
                        <Fragment key={period.key}>
                          <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                            日均额
                          </th>
                          <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                            收益率
                          </th>
                        </Fragment>
                      ),
                    )}
                    <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                      日均额
                    </th>
                    <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                      收益率
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {matrixSurface.detailMatrix.rows.map(
                    (item) => (
                      <tr
                        key={item.categoryId}
                        className={
                          item.isSummary
                            ? "product-category-liability-matrix__summary-row"
                            : undefined
                        }
                        data-testid={`product-category-liability-side-detail-${item.categoryId}`}
                      >
                        <td className="product-category-diagnostics__table-cell product-category-liability-matrix__item-cell">
                          {item.categoryLabel}
                        </td>
                        {item.cells.map((cell) => (
                          <Fragment key={cell.periodKey}>
                            <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                              {cell.amountLabel}
                            </td>
                            <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                              {cell.rateLabel}
                            </td>
                          </Fragment>
                        ))}
                        <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                          {item.movement.amountLabel}
                        </td>
                        <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                          {item.movement.rateLabel}
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          </details>
          <div className="product-category-liability-matrix__currency-grid">
            {matrixSurface.detailMatrix.currencyMatrices.map(
              (currencyMatrix) => (
                <section
                  key={currencyMatrix.currencyKey}
                  className="product-category-liability-matrix__currency-section"
                >
                  <h3 className="product-category-liability-matrix__currency-title">
                    {currencyMatrix.currencyLabel}
                  </h3>
                  <p className="product-category-diagnostics__description">
                    成本率沿用该产品全币种综合口径，不代表分币种成本率。
                  </p>
                  <ProductCategoryLiabilityCurrencyMatrixMobileReadout
                    matrix={currencyMatrix}
                    periods={
                      matrixSurface.detailMatrix.periods
                    }
                  />
                  <details
                    className="product-category-liability-matrix__disclosure"
                    data-testid={`product-category-liability-side-currency-disclosure-${currencyMatrix.currencyKey}`}
                  >
                    <summary>
                      <span>完整明细矩阵</span>
                      <small>
                        {
                          matrixSurface.detailMatrix
                            .periods.length
                        }
                        期 · {currencyMatrix.rows.length}行
                      </small>
                    </summary>
                    <div className="product-category-diagnostics__table-wrap product-category-liability-matrix__wrap">
                      <table
                        className="product-category-diagnostics__table product-category-liability-matrix product-category-liability-matrix--currency"
                        data-testid={`product-category-liability-side-currency-matrix-${currencyMatrix.currencyKey}`}
                        aria-label={`${currencyMatrix.currencyLabel}负债结构`}
                      >
                        <thead>
                          <tr>
                            <th
                              className="product-category-diagnostics__table-head product-category-liability-matrix__item-head"
                              rowSpan={2}
                              scope="col"
                            >
                              负债明细
                            </th>
                            {matrixSurface.detailMatrix.periods.map(
                              (period) => (
                                <th
                                  key={period.key}
                                  className="product-category-diagnostics__table-head product-category-liability-matrix__group-head"
                                  colSpan={2}
                                  scope="colgroup"
                                >
                                  {period.label}
                                </th>
                              ),
                            )}
                            <th
                              className="product-category-diagnostics__table-head product-category-liability-matrix__group-head"
                              colSpan={2}
                              scope="colgroup"
                            >
                              {currencyMatrix.movementGroupLabel}
                            </th>
                          </tr>
                          <tr>
                            {matrixSurface.detailMatrix.periods.map(
                              (period) => (
                                <Fragment key={period.key}>
                                  <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                    日均额
                                  </th>
                                  <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                                    综合成本率
                                  </th>
                                </Fragment>
                              ),
                            )}
                            <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                              日均额
                            </th>
                            <th className="product-category-diagnostics__table-head product-category-liability-matrix__metric-head">
                              综合成本率
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {currencyMatrix.rows.map((item) => (
                            <tr
                              key={item.categoryId}
                              className={
                                item.isSummary
                                  ? "product-category-liability-matrix__summary-row"
                                  : undefined
                              }
                              data-testid={`product-category-liability-side-currency-detail-${currencyMatrix.currencyKey}-${item.categoryId}`}
                            >
                              <td className="product-category-diagnostics__table-cell product-category-liability-matrix__item-cell">
                                {item.categoryLabel}
                              </td>
                              {item.cells.map((cell) => (
                                <Fragment key={cell.periodKey}>
                                  <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                    {cell.amountLabel}
                                  </td>
                                  <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                    {cell.rateLabel}
                                  </td>
                                </Fragment>
                              ))}
                              <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                {item.movement.amountLabel}
                              </td>
                              <td className="product-category-diagnostics__table-cell product-category-liability-matrix__number-cell">
                                {item.movement.rateLabel}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                </section>
              ),
            )}
          </div>
        </>
      ) : trendSurface.detailRows.length > 0 ? (
        <>
          <ProductCategoryLiabilityFallbackMobileReadout
            rows={trendSurface.detailRows}
          />
          <div className="product-category-diagnostics__table-wrap">
            <table
              className="product-category-diagnostics__table"
              data-testid="product-category-liability-side-detail-table"
            >
              <thead>
                <tr>
                  <th className="product-category-diagnostics__table-head">
                    负债明细
                  </th>
                  <th className="product-category-diagnostics__table-head">
                    最新日均额
                  </th>
                  <th className="product-category-diagnostics__table-head">
                    日均额变动
                  </th>
                  <th className="product-category-diagnostics__table-head">
                    最新利率
                  </th>
                  <th className="product-category-diagnostics__table-head">
                    利率变动
                  </th>
                  <th className="product-category-diagnostics__table-head">
                    对比期
                  </th>
                </tr>
              </thead>
              <tbody>
                {trendSurface.detailRows.map((item) => (
                  <tr
                    key={item.categoryId}
                    data-testid={`product-category-liability-side-detail-${item.categoryId}`}
                  >
                    <td className="product-category-diagnostics__table-cell">
                      {item.categoryLabel}
                    </td>
                    <td className="product-category-diagnostics__table-cell">
                      {item.latestAmountLabel}
                    </td>
                    <td className="product-category-diagnostics__table-cell">
                      {item.amountDeltaLabel}
                    </td>
                    <td className="product-category-diagnostics__table-cell">
                      {item.latestRateLabel}
                    </td>
                    <td className="product-category-diagnostics__table-cell">
                      {item.rateDeltaLabel}
                    </td>
                    <td className="product-category-diagnostics__table-cell">
                      {item.comparisonLabel}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </article>
  );
}
