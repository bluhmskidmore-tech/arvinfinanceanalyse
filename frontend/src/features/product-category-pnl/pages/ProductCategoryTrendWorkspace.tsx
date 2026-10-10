import type { ResultMeta } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { LazyChartCard } from "./LazyReactECharts";
import { loadReactECharts } from "./lazyReactEChartsLoader";
import {
  DerivedChartPanel,
  ProductCategoryComparisonChartReadout,
  ProductCategoryInterestSpreadAttributionPanel,
} from "./ProductCategoryComparisonChartPanels";
import {
  ProductCategoryLiabilityViewToggle,
  type ProductCategoryLiabilityView,
} from "./ProductCategoryLiabilityViewToggle";
import type {
  ProductCategoryDiagnosticsSurface,
  ProductCategoryInterestSpreadBasis,
  ProductCategoryLiabilitySideTrendSurface,
} from "./productCategoryPnlPageModel";
import type { ProductCategoryTrendCharts } from "./useProductCategoryTrendCharts";

type ProductCategoryTrendWorkspaceProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  reportPeriodCount: number;
  charts: ProductCategoryTrendCharts;
  spreadViewLabel: string;
  diagnosticsSurface: ProductCategoryDiagnosticsSurface;
  liabilityTrendSurface: ProductCategoryLiabilitySideTrendSurface;
  liabilityMatrixView: ProductCategoryLiabilityView;
  onLiabilityMatrixViewChange: (view: ProductCategoryLiabilityView) => void;
  comparisonCoverage: {
    priorPeriodLabel: string;
    currentPeriodLabel: string;
    comparableMonthCount: number;
    loadState: "loading" | "partial" | "complete" | "error";
    loadLabel: string;
  };
  resultMeta?: ResultMeta;
  onInterestSpreadAttributionPointClick: (
    basis: ProductCategoryInterestSpreadBasis,
    monthKeys: number[] | undefined,
    params: { dataIndex?: number },
  ) => void;
};

export function ProductCategoryTrendWorkspace({
  open,
  onOpenChange,
  reportPeriodCount,
  charts,
  spreadViewLabel,
  diagnosticsSurface,
  liabilityTrendSurface,
  liabilityMatrixView,
  onLiabilityMatrixViewChange,
  comparisonCoverage,
  resultMeta,
  onInterestSpreadAttributionPointClick,
}: ProductCategoryTrendWorkspaceProps) {
  const liabilityTrendReadout = charts.liabilityReadout;

  return (
    <details
      className="product-category-trend-terminal"
      data-testid="product-category-trend-workspace"
      open={open}
      onToggle={(event) => {
        const isOpen = event.currentTarget.open;
        onOpenChange(isOpen);
      }}
    >
      <summary onPointerEnter={() => void loadReactECharts()}>
        <div className="product-category-trend-terminal__header">
          <div className="product-category-trend-terminal__copy">
            <span>趋势与利差</span>
            <strong>趋势与利差候选图表</strong>
            <small>
              最近 {reportPeriodCount || 8} 个报告期 · 正式接口历史
            </small>
          </div>
          <div
            className="product-category-trend-terminal__metrics"
            aria-label="最新趋势读数"
          >
            <span>
              <small>生息规模</small>
              <strong>{charts.headerMetrics.earningScale}</strong>
            </span>
            <span>
              <small>负债均额</small>
              <strong>{charts.headerMetrics.liabilityAverage}</strong>
            </span>
            <span>
              <small>利差（含TPL）</small>
              <strong>{charts.headerMetrics.netSpread}</strong>
            </span>
          </div>
          <span
            className="product-category-trend-terminal__toggle"
            aria-hidden="true"
          >
            {open ? "收起趋势 ↑" : "展开趋势 ↓"}
          </span>
        </div>
      </summary>

      {open ? (
        <div className="product-category-trend-terminal__body">
          <section
            className="product-category-trend-terminal__core"
            data-testid="product-category-trend-core-charts"
          >
            <div
              className="product-category-derived-charts product-category-trend-terminal__grid"
              data-testid="product-category-derived-chart-grid"
            >
              <DerivedChartPanel
                testId="product-category-derived-chart-tpl-scale-yield"
                title="TPL资产规模收益率走势图"
                description="跟踪TPL资产人民币规模、外币规模与综合收益率变化。"
                option={charts.options.tplScaleYield}
              />
              <DerivedChartPanel
                testId="product-category-derived-chart-currency-net-income"
                title="人民币/外币净收入走势分析图"
                description="按全市场净收入拆分人民币与外币贡献，观察币种结构变化。"
                option={charts.options.currencyNetIncome}
              />
              <DerivedChartPanel
                testId="product-category-derived-chart-interest-earning-income-scale"
                title="生息资产收入规模趋势图"
                description="跟踪近8个报告期生息资产收入规模的变化趋势。"
                option={charts.options.interestEarningIncomeScale}
              />
              <DerivedChartPanel
                testId="product-category-derived-chart-interest-spread"
                title="资产负债利差趋势图"
                description="资产端为含TPL 口径：跟踪近8个报告期资产端收益率（含TPL）、负债端成本率与资产负债利差（含TPL）的变化趋势。"
                option={charts.options.interestSpread}
              />
              <DerivedChartPanel
                testId="product-category-derived-chart-interest-earning-spread"
                title="生息资产负债利差趋势图"
                description={`${spreadViewLabel}。历史点分别展示对应期间的年化收益率、成本率及利差。`}
                option={charts.options.interestEarningSpread}
              />
              <DerivedChartPanel
                testId="product-category-derived-chart-interest-earning-asset-liability-scale"
                title="生息资产和附息负债走势图"
                description={`${spreadViewLabel}。历史点分别展示对应期间生息资产与附息负债的日均余额。`}
                option={charts.options.interestEarningAssetLiabilityScale}
              />
            </div>
          </section>

          <section
            className="product-category-trend-terminal__analysis product-category-trend-terminal__grid"
            data-testid="product-category-trend-analysis"
          >
            <article
              className="product-category-diagnostics__card product-category-trend-terminal__analysis-card"
              data-testid="product-category-trend-spread-attribution"
            >
              <div className="product-category-diagnostics__intro">
                <h3 className="product-category-diagnostics__title">
                  利差变动归因
                </h3>
                <p className="product-category-diagnostics__description">
                  资产端收益率（含TPL）− 负债端成本率
                </p>
              </div>
              <div className="product-category-diagnostics__spread-grid">
                <div className="product-category-diagnostics__spread-card">
                  <span className="product-category-diagnostics__spread-caption">
                    {diagnosticsSurface.spreadAttribution.currentLabel}
                  </span>
                  <span className="product-category-diagnostics__spread-value">
                    {
                      diagnosticsSurface.spreadAttribution
                        .currentSpreadLabel
                    }
                  </span>
                  <span className="product-category-diagnostics__spread-detail">
                    资产{" "}
                    {
                      diagnosticsSurface.spreadAttribution
                        .currentAssetYieldLabel
                    }{" "}
                    / 负债{" "}
                    {
                      diagnosticsSurface.spreadAttribution
                        .currentLiabilityYieldLabel
                    }
                  </span>
                </div>
                <div className="product-category-diagnostics__spread-card">
                  <span className="product-category-diagnostics__spread-caption">
                    {diagnosticsSurface.spreadAttribution.priorLabel}
                  </span>
                  <span className="product-category-diagnostics__spread-value">
                    {diagnosticsSurface.spreadAttribution.priorSpreadLabel}
                  </span>
                  <span className="product-category-diagnostics__spread-detail">
                    资产变动{" "}
                    {
                      diagnosticsSurface.spreadAttribution
                        .assetYieldDeltaLabel
                    }{" "}
                    / 负债变动{" "}
                    {
                      diagnosticsSurface.spreadAttribution
                        .liabilityYieldDeltaLabel
                    }
                  </span>
                </div>
                <div className="product-category-diagnostics__spread-card">
                  <span className="product-category-diagnostics__spread-caption">
                    归因结论
                  </span>
                  <span className="product-category-diagnostics__spread-value">
                    {diagnosticsSurface.spreadAttribution.spreadDeltaLabel}
                  </span>
                  <span className="product-category-diagnostics__spread-detail">
                    {diagnosticsSurface.spreadAttribution.driverHint}
                  </span>
                </div>
              </div>
              {diagnosticsSurface.spreadAttribution.state ===
              "incomplete" ? (
                <div className="product-category-diagnostics__empty">
                  {diagnosticsSurface.spreadAttribution.reason}
                </div>
              ) : (
                <p className="product-category-trend-terminal__driver-note">
                  本期利差变动{" "}
                  {diagnosticsSurface.spreadAttribution.spreadDeltaLabel}：
                  {diagnosticsSurface.spreadAttribution.driverHint}。
                </p>
              )}
            </article>

            <article
              className="product-category-diagnostics__card product-category-trend-terminal__analysis-card product-category-trend-terminal__liability"
              data-testid="product-category-trend-liability-card"
            >
              <div className="product-category-diagnostics__header">
                <div className="product-category-diagnostics__intro">
                  <h3 className="product-category-diagnostics__title">
                    负债端趋势分析
                  </h3>
                  <p className="product-category-diagnostics__description">
                    负债总额的正式接口历史走势
                  </p>
                </div>
                <a href="#product-category-liabilities">负债侧口径 →</a>
              </div>
              <ProductCategoryLiabilityViewToggle
                ariaLabel="负债趋势展示口径"
                testId="product-category-trend-liability-view-mode"
                value={liabilityMatrixView}
                onChange={onLiabilityMatrixViewChange}
              />
              {charts.options.liabilitySideTrend ? (
                <LazyChartCard
                  flat
                  ariaLabel="负债端趋势分析"
                  height={280}
                  option={charts.options.liabilitySideTrend}
                  canvasClassName="product-category-derived-chart__canvas"
                  testId="product-category-trend-liability-chart"
                />
              ) : (
                <div className="product-category-diagnostics__empty">
                  {liabilityTrendSurface.emptyCopy ??
                    "负债端趋势数据不完整。"}
                </div>
              )}
              <div className="product-category-trend-terminal__liability-metrics">
                <span>
                  <small>最新日均额</small>
                  <strong>
                    {liabilityTrendReadout?.latestAmountLabel ?? EM_DASH}
                  </strong>
                </span>
                <span>
                  <small>最新收益率</small>
                  <strong>
                    {liabilityTrendReadout?.latestRateLabel ?? EM_DASH}
                  </strong>
                </span>
                <span>
                  <small>日均额变动</small>
                  <strong>
                    {liabilityTrendReadout?.amountDeltaLabel ?? EM_DASH}
                  </strong>
                </span>
                <span>
                  <small>收益率变动</small>
                  <strong>
                    {liabilityTrendReadout?.rateDeltaLabel ?? EM_DASH}
                  </strong>
                </span>
              </div>
            </article>
          </section>

          <section
            className="product-category-trend-terminal__supporting"
            data-testid="product-category-trend-supporting"
          >
            <header>
              <span>同比趋势与后端字段归因</span>
              <small>
                {comparisonCoverage.priorPeriodLabel} →{" "}
                {comparisonCoverage.currentPeriodLabel}
                {" · "}日期覆盖 {comparisonCoverage.comparableMonthCount}/12
              </small>
            </header>
            <div
              className="product-category-trend-comparison__statusbar"
              data-testid="product-category-trend-comparison-status"
            >
              <div className="product-category-trend-comparison__periods">
                <span className="product-category-trend-comparison__period">
                  上年参考：{comparisonCoverage.priorPeriodLabel}
                </span>
                <span className="product-category-trend-comparison__period">
                  当前观察：{comparisonCoverage.currentPeriodLabel}
                </span>
                <span className="product-category-trend-comparison__period">
                  日期覆盖 {comparisonCoverage.comparableMonthCount}/12
                </span>
              </div>
              <span
                className={`product-category-trend-comparison__load-state is-${comparisonCoverage.loadState}`}
              >
                {comparisonCoverage.loadLabel}
              </span>
            </div>
            <div
              className="product-category-derived-charts product-category-trend-terminal__grid"
              data-testid="product-category-trend-comparison-charts"
            >
              <DerivedChartPanel
                testId="product-category-derived-chart-interest-earning-spread-yoy"
                title="生息资产利差：今年与上年同月"
                description="上图对齐两年利差水平，下图直接显示同月同比差（bp）；未进入当前观察期的月份仅保留上年弱参考。"
                option={charts.comparisons.interestEarningSpread.option}
                comparisonStatus={
                  charts.comparisons.interestEarningSpread.chart?.comparisonStatus
                }
                readout={
                  <ProductCategoryComparisonChartReadout
                    readout={charts.comparisons.interestEarningSpread.readout}
                  />
                }
              />
              <DerivedChartPanel
                testId="product-category-derived-chart-interest-earning-spread-yoy-cny"
                title="人民币生息资产利差：今年与上年同月"
                description="上图对齐人民币利差水平，下图直接显示同月同比差（bp）；未进入当前观察期的月份仅保留上年弱参考。"
                option={charts.comparisons.cnyInterestEarningSpread.option}
                comparisonStatus={
                  charts.comparisons.cnyInterestEarningSpread.chart?.comparisonStatus
                }
                readout={
                  <ProductCategoryComparisonChartReadout
                    readout={charts.comparisons.cnyInterestEarningSpread.readout}
                  />
                }
              />
              <DerivedChartPanel
                testId="product-category-derived-chart-interest-spread-yoy"
                title="资产负债利差：今年与上年同月"
                description="上图看全口径利差水平，下图看同月同比差（bp）；点击月份联动后端利差字段归因。"
                option={charts.comparisons.interestSpread.option}
                comparisonStatus={
                  charts.comparisons.interestSpread.chart?.comparisonStatus
                }
                readout={
                  <ProductCategoryComparisonChartReadout
                    readout={charts.comparisons.interestSpread.readout}
                  />
                }
                onEvents={{
                  click: (params: unknown) =>
                    onInterestSpreadAttributionPointClick(
                      "weighted",
                      charts.comparisons.interestSpread.chart?.monthKeys,
                      params as { dataIndex?: number },
                    ),
                }}
              />
              <DerivedChartPanel
                testId="product-category-derived-chart-interest-spread-yoy-cny"
                title="人民币资产负债利差：今年与上年同月"
                description="上图看人民币利差水平，下图看同月同比差（bp）；点击月份联动后端利差字段归因。"
                option={charts.comparisons.cnyInterestSpread.option}
                comparisonStatus={
                  charts.comparisons.cnyInterestSpread.chart?.comparisonStatus
                }
                readout={
                  <ProductCategoryComparisonChartReadout
                    readout={charts.comparisons.cnyInterestSpread.readout}
                  />
                }
                onEvents={{
                  click: (params: unknown) =>
                    onInterestSpreadAttributionPointClick(
                      "cny",
                      charts.comparisons.cnyInterestSpread.chart?.monthKeys,
                      params as { dataIndex?: number },
                    ),
                }}
              />
              <DerivedChartPanel
                testId="product-category-derived-chart-intermediate-business-income-yoy"
                title="中间业务收入：今年与上年同月"
                description="并列柱比较同月收入，保留零基线与负值；金额及同比差单位均为亿元。"
                option={charts.comparisons.intermediateBusinessIncome.option}
                comparisonStatus={
                  charts.comparisons.intermediateBusinessIncome.chart?.comparisonStatus
                }
                readout={
                  <ProductCategoryComparisonChartReadout
                    readout={charts.comparisons.intermediateBusinessIncome.readout}
                  />
                }
                wide
              />
            </div>
            <ProductCategoryInterestSpreadAttributionPanel
              surface={charts.interestSpreadAttributionSurface}
              resultMeta={resultMeta}
            />
          </section>
        </div>
      ) : null}
    </details>
  );
}
