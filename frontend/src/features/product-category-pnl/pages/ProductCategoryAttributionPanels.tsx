import type { ReactNode, RefObject } from "react";

import type {
  ProductCategoryAttributionPayload,
  ProductCategoryAttributionRow,
  ResultMeta,
} from "../../../api/contracts";
import { DataQualityBanner } from "../../../components/page/DataQualityBanner";
import {
  formatProductCategoryAttributionEffect,
  formatProductCategoryReportMonthLabel,
  formatProductCategoryRowDisplayValue,
  formatProductCategoryYieldValue,
  type ProductCategoryAttributionWaterfallSurface,
  type ProductCategoryLiabilityCurrencyMatrix,
  type ProductCategoryLiabilityCurrencyMatrixRow,
  type ProductCategoryLiabilityDetailMatrix,
  type ProductCategoryLiabilityDetailMatrixPeriod,
  type ProductCategoryLiabilityDetailMatrixRow,
  type ProductCategoryLiabilityDetailTrendRow,
  type ProductCategoryRootCauseSurface,
  selectProductCategoryClosureErrorSignal,
} from "./productCategoryPnlPageModel";

const ATTRIBUTION_EFFECT_COLUMNS = [
  ["scale_effect", "规模因素"],
  ["rate_effect", "利率因素"],
  ["day_effect", "天数因素"],
  ["ftp_effect", "FTP因素"],
  ["direct_effect", "直接因素"],
  ["unexplained_effect", "未解释"],
] as const;

const ATTRIBUTION_DETAIL_EFFECT_COLUMNS = [
  ...ATTRIBUTION_EFFECT_COLUMNS,
  ["closure_error", "闭合误差"],
] as const;

const ATTRIBUTION_POINT_COLUMNS = [
  ["scale", "日均"],
  ["cash", "收支"],
  ["yield_pct", "利率"],
  ["ftp", "FTP"],
  ["business_net_income", "净营收"],
] as const;

export type ProductCategoryAttributionCompare =
  ProductCategoryAttributionPayload["compare"];

const ATTRIBUTION_COMPARE_OPTIONS: Array<{
  value: ProductCategoryAttributionCompare;
  label: string;
}> = [
  { value: "mom", label: "月环比" },
  { value: "yoy", label: "同比" },
];

function productCategoryAttributionPriorLabel(
  compare: ProductCategoryAttributionCompare,
): string {
  return compare === "yoy" ? "去年同期" : "上期";
}

function productCategoryAttributionLoadingCopy(
  compare: ProductCategoryAttributionCompare,
): string {
  return compare === "yoy"
    ? "正在加载同比经营差异归因。"
    : "正在加载月环比经营差异归因。";
}

function productCategoryAttributionIncompleteCopy(
  compare: ProductCategoryAttributionCompare,
): string {
  return compare === "yoy"
    ? "缺少去年同期正式月度数据，暂不能做同比归因。"
    : "缺少上月正式月度数据，暂不能做月环比归因。";
}

export function ProductCategoryAttributionPanel(props: {
  selectedView: string;
  compare: ProductCategoryAttributionCompare;
  payload?: ProductCategoryAttributionPayload;
  resultMeta?: ResultMeta | null;
  isLoading: boolean;
  isError: boolean;
  decisionReadout?: ReactNode;
  detailsOpen: boolean;
  detailsRef: RefObject<HTMLDetailsElement>;
  selectedDetailCategoryId: string | null;
  onCompareChange: (compare: ProductCategoryAttributionCompare) => void;
  onDetailsOpenChange: (open: boolean) => void;
  onLocateFormalRow: (categoryId: string) => void;
  onSelectDetailCategory: (categoryId: string) => void;
  onRetry: () => void;
}) {
  if (props.selectedView !== "monthly") {
    return (
      <article
        className="product-category-attribution product-category-attribution--ineligible"
        data-testid="product-category-attribution-ineligible"
      >
        <div className="product-category-attribution__header">
          <div>
            <h3 className="product-category-attribution__title">
              经营差异归因
            </h3>
            <p className="product-category-attribution__description">
              仅支持月度视图，汇总视图保持原正式明细口径。
            </p>
          </div>
          <span className="product-category-attribution__badge">正式基线</span>
        </div>
      </article>
    );
  }

  if (props.isLoading) {
    return (
      <article
        className="product-category-attribution"
        data-testid="product-category-attribution"
      >
        <div className="product-category-attribution__empty">
          {productCategoryAttributionLoadingCopy(props.compare)}
        </div>
      </article>
    );
  }

  if (props.isError) {
    return (
      <article
        className="product-category-attribution"
        data-testid="product-category-attribution"
      >
        <div className="product-category-attribution__error">
          <span>归因数据加载失败。</span>
          <button type="button" onClick={props.onRetry}>
            重试
          </button>
        </div>
      </article>
    );
  }

  if (!props.payload || props.payload.state === "incomplete") {
    return (
      <article
        className="product-category-attribution"
        data-testid="product-category-attribution"
      >
        <div className="product-category-attribution__header">
          <div>
            <h3 className="product-category-attribution__title">
              经营差异归因
            </h3>
            <p className="product-category-attribution__description">
              正式基线归因，不解释 FTP 场景差异。
            </p>
          </div>
          <ProductCategoryAttributionCompareSwitch
            compare={props.compare}
            onCompareChange={props.onCompareChange}
          />
        </div>
        <DataQualityBanner
          resultMeta={props.resultMeta}
          degradedReasons={["归因数据准备中，请稍后刷新"]}
        />
        <div
          className="product-category-attribution__empty"
          data-testid="product-category-attribution-incomplete"
        >
          {productCategoryAttributionIncompleteCopy(props.compare)}
        </div>
      </article>
    );
  }

  const headlineRow = props.payload.totals?.grand_total;
  const headline = headlineRow?.effects;
  const closureErrorSignal = selectProductCategoryClosureErrorSignal(
    headline?.closure_error,
  );
  const grandTotalRow = props.payload.totals?.grand_total
    ? { ...props.payload.totals.grand_total, category_name: "全表合计" }
    : null;
  const rows = props.payload.totals
    ? [
        ...props.payload.rows,
        props.payload.totals.asset_total,
        props.payload.totals.liability_total,
        ...(grandTotalRow ? [grandTotalRow] : []),
      ]
    : props.payload.rows;
  return (
    <article
      className="product-category-attribution"
      data-testid="product-category-attribution"
    >
      <div className="product-category-attribution__header">
        <div>
          <h3 className="product-category-attribution__title">经营差异归因</h3>
          <p className="product-category-attribution__description">
            本期{" "}
            {formatProductCategoryReportMonthLabel(
              props.payload.current_report_date,
            )}{" "}
            · 对比期{" "}
            {formatProductCategoryReportMonthLabel(
              props.payload.prior_report_date,
            )}{" "}
            · {props.compare === "yoy" ? "同比" : "月环比"}正式基线归因，不解释
            FTP 场景差异。
          </p>
        </div>
        <ProductCategoryAttributionCompareSwitch
          compare={props.compare}
          onCompareChange={props.onCompareChange}
        />
      </div>

      {headline ? (
        <div
          className="product-category-attribution__summary"
          data-testid="product-category-attribution-summary"
        >
          <AttributionMetric
            label="变动合计"
            value={headline.delta_business_net_income}
          />
          <AttributionMetric label="已解释" value={headline.explained_effect} />
          <AttributionMetric
            label="未解释"
            value={headline.unexplained_effect}
          />
          <AttributionMetric
            label="闭合误差"
            value={headline.closure_error}
            warningText={closureErrorSignal.warningText}
            warningTestId={
              closureErrorSignal.hasMaterialGap
                ? "product-category-closure-error-warning"
                : undefined
            }
          />
        </div>
      ) : null}

      {props.decisionReadout}

      <details
        className="product-category-attribution__details"
        data-testid="product-category-attribution-details"
        onToggle={(event) =>
          props.onDetailsOpenChange(event.currentTarget.open)
        }
        open={props.detailsOpen}
        ref={props.detailsRef}
      >
        <summary>
          <span>正式归因明细</span>
          <small>
            {rows.length} 行 · 对比期{" "}
            {formatProductCategoryReportMonthLabel(
              props.payload.prior_report_date,
            )}
          </small>
        </summary>
        <AttributionComparisonTable
          compare={props.compare}
          currentReportDate={props.payload.current_report_date}
          priorReportDate={props.payload.prior_report_date}
          rows={rows}
          selectedDetailCategoryId={props.selectedDetailCategoryId}
          onLocateFormalRow={props.onLocateFormalRow}
          onSelectDetailCategory={props.onSelectDetailCategory}
        />
      </details>
    </article>
  );
}

export function ProductCategoryAttributionBridge(props: {
  waterfall: ProductCategoryAttributionWaterfallSurface;
  rootCause: ProductCategoryRootCauseSurface;
  onOpenDetails: (categoryId: string) => void;
}) {
  const candidateStatus = props.waterfall.metricStatus;
  return (
    <section
      aria-label="归因差异桥与主导根因"
      className="product-category-attribution-bridge"
      data-testid="product-category-attribution-bridge"
    >
      <div className="product-category-attribution-bridge__header">
        <div>
          <span className="product-category-attribution-bridge__eyebrow">
            候选经营解读
          </span>
          <h4>主导产品与前三驱动</h4>
        </div>
        <span
          className="product-category-attribution-bridge__status"
          data-testid="product-category-attribution-candidate-status"
          title={candidateStatus.disclaimer}
        >
          <strong>{candidateStatus.label}</strong>
          <small>不可用于正式签署</small>
        </span>
      </div>

      <div className="product-category-attribution-bridge__decision-grid">
        <article
          className="product-category-attribution-bridge__panel"
          data-testid="product-category-root-cause"
        >
          {props.rootCause.emptyCopy || !props.rootCause.headline ? (
            <div className="product-category-attribution-bridge__empty">
              {props.rootCause.emptyCopy}
            </div>
          ) : (
            <div className="product-category-attribution-bridge__root-cause">
              <div className="product-category-attribution-bridge__root-cause-overview">
                <div className="product-category-attribution-bridge__root-cause-head">
                  <div>
                    <span>主导产品</span>
                    <strong>{props.rootCause.headline.categoryLabel}</strong>
                    <small>{props.rootCause.headline.conclusionLabel}</small>
                  </div>
                  <div className="product-category-attribution-bridge__root-cause-action">
                    <b className={`is-${props.rootCause.headline.tone}`}>
                      {props.rootCause.headline.deltaLabel}
                    </b>
                    <button
                      type="button"
                      onClick={() =>
                        props.onOpenDetails(
                          props.rootCause.headline!.categoryId,
                        )
                      }
                    >
                      查看正式明细
                    </button>
                  </div>
                </div>
                <div className="product-category-attribution-bridge__root-cause-metrics">
                  <span>
                    本期 {props.rootCause.headline.currentNetIncomeLabel}
                  </span>
                  <span>
                    对比期 {props.rootCause.headline.priorNetIncomeLabel}
                  </span>
                  <span>规模 {props.rootCause.headline.scaleLabel}</span>
                  <span>收益率 {props.rootCause.headline.yieldLabel}</span>
                </div>
              </div>
              <div className="product-category-attribution-bridge__driver-readout">
                <div className="product-category-attribution-bridge__driver-readout-head">
                  <strong>前三驱动</strong>
                  <small>按影响绝对值排序</small>
                </div>
                <div className="product-category-attribution-bridge__root-cause-drivers">
                  {props.rootCause.driverRows.slice(0, 3).map((row) => (
                    <div
                      className="product-category-attribution-bridge__root-cause-driver"
                      data-testid="product-category-root-cause-driver"
                      key={row.key}
                    >
                      <span>{row.label}</span>
                      <b className={`is-${row.tone}`}>{row.valueLabel}</b>
                      <small>{row.shareLabel}</small>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </article>
        <details
          className="product-category-attribution-bridge__full-path"
          data-testid="product-category-attribution-full-path"
        >
          <summary>
            <span>候选归因路径</span>
            <small>{props.waterfall.rows.length} 项 · 前端派生</small>
          </summary>
          <div className="product-category-attribution-bridge__evidence">
            {props.rootCause.evidenceItems.map((item) => (
              <small key={item}>{item}</small>
            ))}
          </div>
          <article
            className="product-category-attribution-bridge__panel product-category-attribution-bridge__panel--waterfall"
            data-testid="product-category-attribution-waterfall"
          >
            <div className="product-category-attribution-bridge__panel-head">
              <div>
                <h4>经营差异瀑布</h4>
                <p>
                  变动合计 {props.waterfall.deltaLabel}{" "}
                  亿元，按正式归因完整展开。
                </p>
              </div>
            </div>
            {props.waterfall.emptyCopy ? (
              <div className="product-category-attribution-bridge__empty">
                {props.waterfall.emptyCopy}
              </div>
            ) : (
              <div className="product-category-attribution-bridge__waterfall">
                {props.waterfall.rows.map((row) => (
                  <div
                    className="product-category-attribution-bridge__waterfall-row"
                    data-testid={`product-category-attribution-bridge-driver-${row.key}`}
                    key={row.key}
                  >
                    <span>{row.label}</span>
                    <b className={`is-${row.tone}`}>{row.valueLabel}</b>
                    <small>累计 {row.cumulativeLabel}</small>
                  </div>
                ))}
              </div>
            )}
          </article>
        </details>
      </div>
    </section>
  );
}

function ProductCategoryAttributionCompareSwitch(props: {
  compare: ProductCategoryAttributionCompare;
  onCompareChange: (compare: ProductCategoryAttributionCompare) => void;
}) {
  return (
    <div className="product-category-attribution__actions">
      <span className="product-category-attribution__badge">正式基线</span>
      <div
        aria-label="归因对比方式"
        className="product-category-attribution__segmented"
        role="group"
      >
        {ATTRIBUTION_COMPARE_OPTIONS.map((option) => (
          <button
            aria-pressed={props.compare === option.value}
            className={[
              "product-category-attribution__segmented-button",
              props.compare === option.value
                ? "product-category-attribution__segmented-button--active"
                : "",
            ]
              .filter(Boolean)
              .join(" ")}
            key={option.value}
            onClick={() => props.onCompareChange(option.value)}
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function AttributionMetric(props: {
  label: string;
  value:
    ProductCategoryAttributionRow["effects"]["scale_effect"] | null | undefined;
  warningText?: string | null;
  warningTestId?: string;
}) {
  return (
    <div
      className="product-category-attribution__metric"
      data-testid="product-category-attribution-summary-metric"
    >
      <span className="product-category-attribution__metric-label">
        {props.label}
      </span>
      <span className="product-category-attribution__metric-value">
        {formatProductCategoryAttributionEffect(props.value)}
      </span>
      {props.warningText ? (
        <span
          className="product-category-attribution__metric-warning"
          data-testid={props.warningTestId}
        >
          <span
            className="product-category-attribution__metric-warning-icon"
            aria-hidden="true"
          >
            ⚠
          </span>
          {props.warningText}
        </span>
      ) : null}
    </div>
  );
}

function ProductCategoryAttributionMobileReadoutField(props: {
  label: string;
  value: string;
  detail?: string;
  testId?: string;
}) {
  return (
    <div
      className="product-category-attribution-mobile-readout__field"
      data-testid={props.testId}
    >
      <span className="product-category-attribution-mobile-readout__label">
        {props.label}
      </span>
      <strong className="product-category-attribution-mobile-readout__value">
        {props.value}
      </strong>
      {props.detail ? (
        <small className="product-category-attribution-mobile-readout__detail">
          {props.detail}
        </small>
      ) : null}
    </div>
  );
}

function ProductCategoryAttributionMobileReadout(props: {
  testId: string;
  eyebrow: string;
  title: string;
  meta: string[];
  className?: string;
  fields: Array<{
    label: string;
    value: string;
    detail?: string;
    testId?: string;
  }>;
}) {
  const className = props.className
    ? `product-category-attribution-mobile-readout ${props.className}`
    : "product-category-attribution-mobile-readout";
  return (
    <section
      className={className}
      data-testid={props.testId}
      aria-label={props.title}
    >
      <div className="product-category-attribution-mobile-readout__header">
        <span className="product-category-attribution-mobile-readout__eyebrow">
          {props.eyebrow}
        </span>
        <h4 className="product-category-attribution-mobile-readout__title">
          {props.title}
        </h4>
      </div>
      <div className="product-category-attribution-mobile-readout__meta">
        {props.meta.map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
      <div className="product-category-attribution-mobile-readout__fields">
        {props.fields.map((field) => (
          <ProductCategoryAttributionMobileReadoutField
            detail={field.detail}
            key={`${field.label}-${field.value}`}
            label={field.label}
            testId={field.testId}
            value={field.value}
          />
        ))}
      </div>
    </section>
  );
}

function pickProductCategoryLiabilityReadoutRow<
  Row extends
    | ProductCategoryLiabilityDetailMatrixRow
    | ProductCategoryLiabilityCurrencyMatrixRow,
>(rows: Row[]): Row | null {
  return rows.find((row) => row.isSummary) ?? rows[0] ?? null;
}

function latestProductCategoryLiabilityReadoutCell(
  row:
    | ProductCategoryLiabilityDetailMatrixRow
    | ProductCategoryLiabilityCurrencyMatrixRow,
) {
  return row.cells[row.cells.length - 1] ?? null;
}

function latestProductCategoryLiabilityReadoutPeriod(
  periods: ProductCategoryLiabilityDetailMatrixPeriod[],
) {
  return periods[periods.length - 1] ?? null;
}

export function ProductCategoryLiabilityDetailMatrixMobileReadout(props: {
  matrix: ProductCategoryLiabilityDetailMatrix;
}) {
  const row = pickProductCategoryLiabilityReadoutRow(props.matrix.rows);
  if (!row) {
    return null;
  }
  const latestCell = latestProductCategoryLiabilityReadoutCell(row);
  const latestPeriod = latestProductCategoryLiabilityReadoutPeriod(
    props.matrix.periods,
  );
  return (
    <ProductCategoryAttributionMobileReadout
      className="product-category-liability-mobile-readout"
      testId="product-category-liability-side-detail-matrix-mobile-readout"
      eyebrow="全币种"
      title="负债结构核查"
      meta={[
        row.categoryLabel,
        latestPeriod?.label ?? "\u6700\u65b0\u671f\u95f4",
        `${props.matrix.periods.length} \u4e2a\u671f\u95f4`,
      ]}
      fields={[
        {
          label: "\u6700\u65b0\u65e5\u5747\u989d",
          value: latestCell?.amountLabel ?? "-",
          testId:
            "product-category-liability-side-detail-matrix-mobile-readout-latest-amount",
        },
        {
          label: "\u6700\u65b0\u6536\u76ca\u7387",
          value: latestCell?.rateLabel ?? "-",
          testId:
            "product-category-liability-side-detail-matrix-mobile-readout-latest-rate",
        },
        {
          label: "\u65e5\u5747\u989d\u53d8\u52a8",
          value: row.movement.amountLabel,
          testId:
            "product-category-liability-side-detail-matrix-mobile-readout-amount-movement",
        },
        {
          label: "\u6536\u76ca\u7387\u53d8\u52a8",
          value: row.movement.rateLabel,
          detail: props.matrix.movementGroupLabel,
          testId:
            "product-category-liability-side-detail-matrix-mobile-readout-rate-movement",
        },
      ]}
    />
  );
}

export function ProductCategoryLiabilityCurrencyMatrixMobileReadout(props: {
  matrix: ProductCategoryLiabilityCurrencyMatrix;
  periods: ProductCategoryLiabilityDetailMatrixPeriod[];
}) {
  const row = pickProductCategoryLiabilityReadoutRow(props.matrix.rows);
  if (!row) {
    return null;
  }
  const latestCell = latestProductCategoryLiabilityReadoutCell(row);
  const latestPeriod = latestProductCategoryLiabilityReadoutPeriod(
    props.periods,
  );
  return (
    <ProductCategoryAttributionMobileReadout
      className="product-category-liability-mobile-readout"
      testId={`product-category-liability-side-currency-matrix-${props.matrix.currencyKey}-mobile-readout`}
      eyebrow="币种结构"
      title={`${props.matrix.currencyLabel}核查`}
      meta={[
        props.matrix.currencyLabel,
        props.matrix.currencyKey,
        latestPeriod?.label ?? "\u6700\u65b0\u671f\u95f4",
      ]}
      fields={[
        {
          label: "\u6700\u65b0\u65e5\u5747\u989d",
          value: latestCell?.amountLabel ?? "-",
          testId: `product-category-liability-side-currency-matrix-${props.matrix.currencyKey}-mobile-readout-latest-amount`,
        },
        {
          label: "\u6700\u65b0\u6536\u76ca\u7387",
          value: latestCell?.rateLabel ?? "-",
          testId: `product-category-liability-side-currency-matrix-${props.matrix.currencyKey}-mobile-readout-latest-rate`,
        },
        {
          label: "\u65e5\u5747\u989d\u53d8\u52a8",
          value: row.movement.amountLabel,
          testId: `product-category-liability-side-currency-matrix-${props.matrix.currencyKey}-mobile-readout-amount-movement`,
        },
        {
          label: "\u6536\u76ca\u7387\u53d8\u52a8",
          value: row.movement.rateLabel,
          detail: props.matrix.movementGroupLabel,
          testId: `product-category-liability-side-currency-matrix-${props.matrix.currencyKey}-mobile-readout-rate-movement`,
        },
      ]}
    />
  );
}

export function ProductCategoryLiabilityFallbackMobileReadout(props: {
  rows: ProductCategoryLiabilityDetailTrendRow[];
}) {
  const row =
    props.rows.find((item) => item.categoryId === "liability_total") ??
    props.rows[0] ??
    null;
  if (!row) {
    return null;
  }
  return (
    <ProductCategoryAttributionMobileReadout
      className="product-category-liability-mobile-readout"
      testId="product-category-liability-side-detail-table-mobile-readout"
      eyebrow="负债明细"
      title="负债结构核查"
      meta={[
        row.categoryLabel,
        row.comparisonLabel,
        "\u539f\u8868\u4fdd\u7559",
      ]}
      fields={[
        {
          label: "\u6700\u65b0\u65e5\u5747\u989d",
          value: row.latestAmountLabel,
          testId:
            "product-category-liability-side-detail-table-mobile-readout-latest-amount",
        },
        {
          label: "\u65e5\u5747\u989d\u53d8\u52a8",
          value: row.amountDeltaLabel,
          testId:
            "product-category-liability-side-detail-table-mobile-readout-amount-delta",
        },
        {
          label: "\u6700\u65b0\u6536\u76ca\u7387",
          value: row.latestRateLabel,
          testId:
            "product-category-liability-side-detail-table-mobile-readout-latest-rate",
        },
        {
          label: "\u6536\u76ca\u7387\u53d8\u52a8",
          value: row.rateDeltaLabel,
          detail: "\u539f\u59cb\u8868\u683c\u4fdd\u7559\u5728\u4e0b\u65b9",
          testId:
            "product-category-liability-side-detail-table-mobile-readout-rate-delta",
        },
      ]}
    />
  );
}

function pickProductCategoryAttributionHeadlineRow(
  rows: ProductCategoryAttributionRow[],
) {
  return (
    rows.find((row) => row.category_id === "grand_total") ?? rows[0] ?? null
  );
}

function isProductCategoryAttributionTotalRow(
  row: ProductCategoryAttributionRow,
): boolean {
  return (
    row.category_id.endsWith("_total") || row.category_id === "grand_total"
  );
}

export function isProductCategoryAttributionDetailRow(
  row: ProductCategoryAttributionRow,
): boolean {
  return !isProductCategoryAttributionTotalRow(row);
}

function pickProductCategoryAttributionDetailRow(
  rows: ProductCategoryAttributionRow[],
  selectedCategoryId?: string | null,
) {
  const detailRows = rows.filter(isProductCategoryAttributionDetailRow);
  return (
    detailRows.find((row) => row.category_id === selectedCategoryId) ??
    detailRows[0] ??
    rows[0] ??
    null
  );
}

function pickLargestProductCategoryAttributionEffect(
  row: ProductCategoryAttributionRow,
) {
  return ATTRIBUTION_EFFECT_COLUMNS.filter(
    ([key]) => key !== "unexplained_effect",
  )
    .map(([key, label]) => ({
      label,
      value: row.effects[key],
      magnitude: Math.abs(Number(row.effects[key])),
    }))
    .filter((effect) => Number.isFinite(effect.magnitude))
    .sort((left, right) => right.magnitude - left.magnitude)[0];
}

function ProductCategoryAttributionComparisonMobileReadout(props: {
  compare: ProductCategoryAttributionCompare;
  currentReportDate: string;
  priorReportDate: string;
  rows: ProductCategoryAttributionRow[];
}) {
  const row = pickProductCategoryAttributionHeadlineRow(props.rows);
  if (!row) {
    return null;
  }
  const largestEffect = pickLargestProductCategoryAttributionEffect(row);
  return (
    <ProductCategoryAttributionMobileReadout
      testId="product-category-attribution-comparison-mobile-readout"
      eyebrow="Attribution bridge"
      title={"\u79fb\u52a8\u5f52\u56e0\u8bfb\u6570"}
      meta={[
        `${formatProductCategoryReportMonthLabel(props.currentReportDate)}`,
        `${productCategoryAttributionPriorLabel(props.compare)} ${formatProductCategoryReportMonthLabel(
          props.priorReportDate,
        )}`,
        row.category_name,
      ]}
      fields={[
        {
          label: "\u53d8\u52a8\u5408\u8ba1",
          value: formatProductCategoryAttributionEffect(
            row.effects.delta_business_net_income,
          ),
          testId:
            "product-category-attribution-comparison-mobile-readout-delta",
        },
        {
          label: "\u6700\u5927\u62c6\u5206\u9879",
          value: largestEffect
            ? `${largestEffect.label} ${formatProductCategoryAttributionEffect(largestEffect.value)}`
            : "-",
          testId:
            "product-category-attribution-comparison-mobile-readout-largest-effect",
        },
        {
          label: "\u672a\u89e3\u91ca",
          value: formatProductCategoryAttributionEffect(
            row.effects.unexplained_effect,
          ),
          testId:
            "product-category-attribution-comparison-mobile-readout-unexplained",
        },
        {
          label: "\u95ed\u5408\u8bef\u5dee",
          value: formatProductCategoryAttributionEffect(
            row.effects.closure_error,
          ),
          testId:
            "product-category-attribution-comparison-mobile-readout-closure-error",
        },
        {
          label: "\u884c\u72b6\u6001",
          value: row.state,
          detail: "\u539f\u59cb\u8868\u683c\u4fdd\u7559\u5728\u4e0b\u65b9",
          testId:
            "product-category-attribution-comparison-mobile-readout-state",
        },
      ]}
    />
  );
}

function ProductCategoryAttributionDetailMobileReadout(props: {
  compare: ProductCategoryAttributionCompare;
  currentReportDate: string;
  priorReportDate: string;
  rows: ProductCategoryAttributionRow[];
  selectedDetailCategoryId: string | null;
}) {
  const row = pickProductCategoryAttributionDetailRow(
    props.rows,
    props.selectedDetailCategoryId,
  );
  if (!row) {
    return null;
  }
  return (
    <ProductCategoryAttributionMobileReadout
      testId="product-category-attribution-detail-mobile-readout"
      eyebrow="Point detail"
      title={"\u79fb\u52a8\u660e\u7ec6\u8bfb\u6570"}
      meta={[
        row.category_name,
        `${formatProductCategoryReportMonthLabel(props.currentReportDate)}`,
        `${productCategoryAttributionPriorLabel(props.compare)} ${formatProductCategoryReportMonthLabel(
          props.priorReportDate,
        )}`,
      ]}
      fields={[
        {
          label: "\u672c\u671f\u7ecf\u8425\u51c0\u6536\u5165",
          value: formatAttributionPointValue(
            row,
            row.current,
            "business_net_income",
          ),
          testId:
            "product-category-attribution-detail-mobile-readout-current-income",
        },
        {
          label: "\u5bf9\u6bd4\u671f\u7ecf\u8425\u51c0\u6536\u5165",
          value: formatAttributionPointValue(
            row,
            row.prior,
            "business_net_income",
          ),
          testId:
            "product-category-attribution-detail-mobile-readout-prior-income",
        },
        {
          label: "\u672c\u671f\u89c4\u6a21",
          value: formatAttributionPointValue(row, row.current, "scale"),
          testId:
            "product-category-attribution-detail-mobile-readout-current-scale",
        },
        {
          label: "\u5bf9\u6bd4\u671f\u89c4\u6a21",
          value: formatAttributionPointValue(row, row.prior, "scale"),
          testId:
            "product-category-attribution-detail-mobile-readout-prior-scale",
        },
        {
          label: "\u672c\u671f\u6536\u76ca\u7387",
          value: formatAttributionPointValue(row, row.current, "yield_pct"),
          testId:
            "product-category-attribution-detail-mobile-readout-current-yield",
        },
        {
          label: "\u5bf9\u6bd4\u671f\u6536\u76ca\u7387",
          value: formatAttributionPointValue(row, row.prior, "yield_pct"),
          detail: "\u539f\u59cb\u8868\u683c\u4fdd\u7559\u5728\u4e0b\u65b9",
          testId:
            "product-category-attribution-detail-mobile-readout-prior-yield",
        },
      ]}
    />
  );
}

function ProductCategoryAttributionDetailSelector(props: {
  rows: ProductCategoryAttributionRow[];
  selectedDetailCategoryId: string | null;
  onSelectDetailCategory: (categoryId: string) => void;
}) {
  const row = pickProductCategoryAttributionDetailRow(
    props.rows,
    props.selectedDetailCategoryId,
  );
  const detailRows = props.rows.filter(isProductCategoryAttributionDetailRow);
  if (!row || detailRows.length <= 1) {
    return null;
  }
  return (
    <label className="product-category-attribution__mobile-selector">
      <span>{"\u67e5\u770b\u4ea7\u54c1"}</span>
      <select
        aria-label={"\u67e5\u770b\u4ea7\u54c1"}
        onChange={(event) => props.onSelectDetailCategory(event.target.value)}
        value={row.category_id}
      >
        {detailRows.map((detailRow) => (
          <option key={detailRow.category_id} value={detailRow.category_id}>
            {detailRow.category_name}
          </option>
        ))}
      </select>
    </label>
  );
}

function ProductCategoryAttributionSelectedDetail(props: {
  compare: ProductCategoryAttributionCompare;
  currentReportDate: string;
  priorReportDate: string;
  row: ProductCategoryAttributionRow;
  onLocateFormalRow: (categoryId: string) => void;
}) {
  const decisionFields = [
    {
      label: "\u53d8\u52a8\u5408\u8ba1",
      value: formatProductCategoryAttributionEffect(
        props.row.effects.delta_business_net_income,
      ),
    },
    {
      label: "\u672c\u671f\u7ecf\u8425\u51c0\u6536\u5165",
      value: formatAttributionPointValue(
        props.row,
        props.row.current,
        "business_net_income",
      ),
    },
    {
      label: "\u5bf9\u6bd4\u671f\u7ecf\u8425\u51c0\u6536\u5165",
      value: formatAttributionPointValue(
        props.row,
        props.row.prior,
        "business_net_income",
      ),
    },
    {
      label: "\u95ed\u5408\u8bef\u5dee",
      value: formatProductCategoryAttributionEffect(
        props.row.effects.closure_error,
      ),
    },
  ];
  const evidencePointFields = [
    {
      label: "\u672c\u671f\u89c4\u6a21",
      value: formatAttributionPointValue(props.row, props.row.current, "scale"),
    },
    {
      label: "\u5bf9\u6bd4\u671f\u89c4\u6a21",
      value: formatAttributionPointValue(props.row, props.row.prior, "scale"),
    },
    {
      label: "\u672c\u671f\u6536\u76ca\u7387",
      value: formatAttributionPointValue(
        props.row,
        props.row.current,
        "yield_pct",
      ),
    },
    {
      label: "\u5bf9\u6bd4\u671f\u6536\u76ca\u7387",
      value: formatAttributionPointValue(
        props.row,
        props.row.prior,
        "yield_pct",
      ),
    },
    {
      label: "\u672c\u671f\u5229\u606f\u6536\u652f",
      value: formatAttributionPointValue(props.row, props.row.current, "cash"),
    },
    {
      label: "\u5bf9\u6bd4\u671f\u5229\u606f\u6536\u652f",
      value: formatAttributionPointValue(props.row, props.row.prior, "cash"),
    },
    {
      label: "\u672c\u671f FTP",
      value: formatAttributionPointValue(props.row, props.row.current, "ftp"),
    },
    {
      label: "\u5bf9\u6bd4\u671f FTP",
      value: formatAttributionPointValue(props.row, props.row.prior, "ftp"),
    },
  ];
  const primaryDrivers = ATTRIBUTION_EFFECT_COLUMNS.filter(
    ([key]) => key !== "unexplained_effect",
  )
    .map(([key, label]) => ({
      key,
      label,
      value: props.row.effects[key],
      magnitude: Math.abs(Number(props.row.effects[key])),
    }))
    .filter(
      (driver) => Number.isFinite(driver.magnitude) && driver.magnitude > 0,
    )
    .sort((left, right) => right.magnitude - left.magnitude)
    .slice(0, 3);
  return (
    <section
      className="product-category-attribution__selected-detail"
      data-testid="product-category-attribution-selected-detail"
      id="product-category-attribution-selected-detail"
    >
      <div
        className="product-category-attribution__selected-decision"
        data-testid="product-category-attribution-selected-decision"
      >
        <div className="product-category-attribution__selected-detail-head">
          <div>
            <span>{"\u6b63\u5f0f\u4ea7\u54c1\u8bc1\u636e"}</span>
            <strong>{props.row.category_name}</strong>
            <small>
              {formatProductCategoryReportMonthLabel(props.currentReportDate)}
              {" \u00b7 "}
              {productCategoryAttributionPriorLabel(props.compare)}{" "}
              {formatProductCategoryReportMonthLabel(props.priorReportDate)}
            </small>
          </div>
          <div className="product-category-attribution__selected-detail-actions">
            <b
              className={attributionToneClass(
                props.row.effects.delta_business_net_income,
              )}
            >
              {formatProductCategoryAttributionEffect(
                props.row.effects.delta_business_net_income,
              )}
            </b>
            <button
              className="product-category-attribution__selected-detail-action"
              onClick={() => props.onLocateFormalRow(props.row.category_id)}
              type="button"
            >
              定位正式报表
            </button>
          </div>
        </div>
        <div className="product-category-attribution__selected-decision-metrics">
          {decisionFields.map((field) => (
            <div key={field.label}>
              <span>{field.label}</span>
              <strong>{field.value}</strong>
            </div>
          ))}
        </div>
      </div>
      <div className="product-category-attribution__selected-drivers">
        <div className="product-category-attribution__selected-drivers-head">
          <span>主要驱动</span>
          <small>按绝对影响值排序 · 前 {primaryDrivers.length} 项</small>
        </div>
        <div className="product-category-attribution__selected-driver-grid">
          {primaryDrivers.map((driver) => (
            <div
              data-testid="product-category-attribution-selected-driver"
              key={driver.key}
            >
              <span>{driver.label}</span>
              <strong className={attributionToneClass(driver.value)}>
                {formatProductCategoryAttributionEffect(driver.value)}
              </strong>
            </div>
          ))}
        </div>
      </div>
      <details
        className="product-category-attribution__selected-full-evidence"
        data-testid="product-category-attribution-selected-full-evidence"
      >
        <summary>
          <span>完整口径与证据</span>
          <small>
            {evidencePointFields.length} 项点位 ·{" "}
            {ATTRIBUTION_DETAIL_EFFECT_COLUMNS.length} 项因素
          </small>
        </summary>
        <div className="product-category-attribution__selected-full-evidence-body">
          <div className="product-category-attribution__selected-detail-points">
            {evidencePointFields.map((field) => (
              <div key={field.label}>
                <span>{field.label}</span>
                <strong>{field.value}</strong>
              </div>
            ))}
          </div>
          <div className="product-category-attribution__selected-detail-effects">
            {ATTRIBUTION_DETAIL_EFFECT_COLUMNS.map(([key, label]) => (
              <div key={key}>
                <span>{label}</span>
                <strong
                  className={attributionToneClass(props.row.effects[key])}
                >
                  {formatProductCategoryAttributionEffect(
                    props.row.effects[key],
                  )}
                </strong>
              </div>
            ))}
          </div>
        </div>
      </details>
    </section>
  );
}

function AttributionComparisonTable(props: {
  compare: ProductCategoryAttributionCompare;
  currentReportDate: string;
  priorReportDate: string;
  rows: ProductCategoryAttributionRow[];
  selectedDetailCategoryId: string | null;
  onLocateFormalRow: (categoryId: string) => void;
  onSelectDetailCategory: (categoryId: string) => void;
}) {
  const priorLabel = productCategoryAttributionPriorLabel(props.compare);
  const selectedDetailRow = pickProductCategoryAttributionDetailRow(
    props.rows,
    props.selectedDetailCategoryId,
  );
  const selectedDetailCategoryId = selectedDetailRow?.category_id ?? null;
  return (
    <div className="product-category-attribution__compare-wrap">
      <div className="product-category-attribution__section-head">
        <div>
          <div className="product-category-attribution__section-title">
            归因拆分
          </div>
          <p className="product-category-attribution__section-note">
            先看变动闭合，再按需查看本期与{priorLabel}的日均、收支、利率和 FTP
            明细。
          </p>
        </div>
      </div>
      <ProductCategoryAttributionComparisonMobileReadout
        compare={props.compare}
        currentReportDate={props.currentReportDate}
        priorReportDate={props.priorReportDate}
        rows={props.rows}
      />
      <div className="product-category-attribution__table-wrap">
        <table
          className="product-category-attribution__table product-category-attribution__table--breakdown"
          data-testid="product-category-attribution-comparison-table"
        >
          <thead>
            <tr>
              <th>项目</th>
              <th>变动</th>
              {ATTRIBUTION_EFFECT_COLUMNS.map(([, label]) => (
                <th key={`effect-${label}`}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {props.rows.map((row) => (
              <tr
                className={attributionRowClassName(
                  row,
                  selectedDetailCategoryId,
                )}
                data-selected={
                  isProductCategoryAttributionDetailRow(row) &&
                  row.category_id === selectedDetailCategoryId
                    ? "true"
                    : undefined
                }
                data-testid={`product-category-attribution-comparison-row-${row.category_id}`}
                key={row.category_id}
              >
                <td className="product-category-attribution__item-cell">
                  {isProductCategoryAttributionDetailRow(row) ? (
                    <button
                      aria-pressed={
                        row.category_id === selectedDetailCategoryId
                      }
                      className="product-category-attribution__row-name-button"
                      onClick={() =>
                        props.onSelectDetailCategory(row.category_id)
                      }
                      type="button"
                    >
                      {row.category_name}
                    </button>
                  ) : (
                    <span className="product-category-attribution__row-name">
                      {row.category_name}
                    </span>
                  )}
                  {row.state === "partial" ? (
                    <span className="product-category-attribution__row-state">
                      部分
                    </span>
                  ) : null}
                </td>
                <td
                  className={attributionToneClass(
                    row.effects.delta_business_net_income,
                  )}
                >
                  {formatProductCategoryAttributionEffect(
                    row.effects.delta_business_net_income,
                  )}
                </td>
                {ATTRIBUTION_EFFECT_COLUMNS.map(([key]) => (
                  <td
                    className={[
                      "product-category-attribution__effect-cell",
                      attributionToneClass(row.effects[key]),
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    key={`effect-${key}`}
                  >
                    {formatProductCategoryAttributionEffect(row.effects[key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="product-category-attribution__section-head product-category-attribution__section-head--detail">
        <div>
          <div className="product-category-attribution__section-title">
            本期 / {priorLabel}明细
          </div>
          <p className="product-category-attribution__section-note">
            本期{" "}
            {formatProductCategoryReportMonthLabel(props.currentReportDate)} ·{" "}
            {priorLabel}{" "}
            {formatProductCategoryReportMonthLabel(props.priorReportDate)}
          </p>
        </div>
      </div>
      <ProductCategoryAttributionDetailSelector
        onSelectDetailCategory={props.onSelectDetailCategory}
        rows={props.rows}
        selectedDetailCategoryId={selectedDetailCategoryId}
      />
      {selectedDetailRow ? (
        <ProductCategoryAttributionSelectedDetail
          compare={props.compare}
          currentReportDate={props.currentReportDate}
          priorReportDate={props.priorReportDate}
          row={selectedDetailRow}
          onLocateFormalRow={props.onLocateFormalRow}
        />
      ) : null}
      <ProductCategoryAttributionDetailMobileReadout
        compare={props.compare}
        currentReportDate={props.currentReportDate}
        priorReportDate={props.priorReportDate}
        rows={props.rows}
        selectedDetailCategoryId={selectedDetailCategoryId}
      />
      <div className="product-category-attribution__table-wrap">
        <table
          className="product-category-attribution__table product-category-attribution__table--detail"
          data-testid="product-category-attribution-detail-table"
        >
          <thead>
            <tr>
              <th rowSpan={2}>项目</th>
              <th
                className="product-category-attribution__group-head--current"
                colSpan={5}
              >
                本期{" "}
                {formatProductCategoryReportMonthLabel(props.currentReportDate)}
              </th>
              <th
                className="product-category-attribution__group-head--prior"
                colSpan={5}
              >
                {priorLabel}{" "}
                {formatProductCategoryReportMonthLabel(props.priorReportDate)}
              </th>
            </tr>
            <tr>
              {ATTRIBUTION_POINT_COLUMNS.map(([, label]) => (
                <th key={`detail-current-${label}`}>{label}</th>
              ))}
              {ATTRIBUTION_POINT_COLUMNS.map(([, label]) => (
                <th key={`detail-prior-${label}`}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {props.rows.map((row) => (
              <tr
                className={attributionRowClassName(
                  row,
                  selectedDetailCategoryId,
                )}
                data-selected={
                  isProductCategoryAttributionDetailRow(row) &&
                  row.category_id === selectedDetailCategoryId
                    ? "true"
                    : undefined
                }
                data-testid={`product-category-attribution-detail-row-${row.category_id}`}
                key={`detail-${row.category_id}`}
              >
                <td className="product-category-attribution__item-cell">
                  {isProductCategoryAttributionDetailRow(row) ? (
                    <button
                      aria-pressed={
                        row.category_id === selectedDetailCategoryId
                      }
                      className="product-category-attribution__row-name-button"
                      onClick={() =>
                        props.onSelectDetailCategory(row.category_id)
                      }
                      type="button"
                    >
                      {row.category_name}
                    </button>
                  ) : (
                    <span className="product-category-attribution__row-name">
                      {row.category_name}
                    </span>
                  )}
                  {row.state === "partial" ? (
                    <span className="product-category-attribution__row-state">
                      部分
                    </span>
                  ) : null}
                </td>
                {ATTRIBUTION_POINT_COLUMNS.map(([key]) => (
                  <td key={`detail-current-${key}`}>
                    {formatAttributionPointValue(row, row.current, key)}
                  </td>
                ))}
                {ATTRIBUTION_POINT_COLUMNS.map(([key]) => (
                  <td
                    className="product-category-attribution__prior-cell"
                    key={`detail-prior-${key}`}
                  >
                    {formatAttributionPointValue(row, row.prior, key)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatAttributionPointValue(
  row: Pick<ProductCategoryAttributionRow, "side">,
  point: ProductCategoryAttributionRow["current"],
  key: (typeof ATTRIBUTION_POINT_COLUMNS)[number][0],
): string {
  if (!point) {
    return "-";
  }
  if (key === "yield_pct") {
    const value = formatProductCategoryYieldValue(point.yield_pct);
    return value === "-" ? "-" : `${value}%`;
  }
  if (key === "scale") {
    return formatProductCategoryRowDisplayValue(
      { side: row.side },
      point.scale,
    );
  }
  return formatProductCategoryAttributionEffect(point[key]);
}

function attributionToneClass(
  value: ProductCategoryAttributionRow["effects"]["scale_effect"],
): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) {
    return "";
  }
  return numeric > 0
    ? "product-category-attribution__number--positive"
    : "product-category-attribution__number--negative";
}

function attributionRowClassName(
  row: ProductCategoryAttributionRow,
  selectedDetailCategoryId?: string | null,
): string | undefined {
  const classNames = [
    isProductCategoryAttributionTotalRow(row)
      ? "product-category-attribution__total-row"
      : null,
    isProductCategoryAttributionDetailRow(row) &&
    row.category_id === selectedDetailCategoryId
      ? "product-category-attribution__selected-row"
      : null,
  ].filter((className): className is string => Boolean(className));
  return classNames.length > 0 ? classNames.join(" ") : undefined;
}
