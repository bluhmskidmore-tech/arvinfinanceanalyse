import type { ProductCategoryPnlRow } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import {
  formatProductCategoryReportMonthLabel,
  formatProductCategoryRowDisplayValue,
  formatProductCategoryValue,
  formatProductCategoryYieldValue,
} from "./productCategoryPnlPageModel";

type ProductCategoryFormalTableMobileReadoutProps = {
  reportDate: string;
  selectedView: string;
  selectedCategoryId: string | null;
  grandTotal?: ProductCategoryPnlRow | null;
  rows: ProductCategoryPnlRow[];
  onOpenAttributionEvidence?: (categoryId: string) => void;
};

function ProductCategoryFormalTableReadoutField(props: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="product-category-formal-table-mobile-readout__field">
      <span className="product-category-formal-table-mobile-readout__label">
        {props.label}
      </span>
      <strong className="product-category-formal-table-mobile-readout__value">
        {props.value}
      </strong>
      {props.detail ? (
        <small className="product-category-formal-table-mobile-readout__detail">
          {props.detail}
        </small>
      ) : null}
    </div>
  );
}

export function ProductCategoryFormalTableMobileReadout(
  props: ProductCategoryFormalTableMobileReadoutProps,
) {
  const focusedBusinessRow =
    props.rows.find(
      (row) => !row.is_total && row.category_id === props.selectedCategoryId,
    ) ??
    props.rows.find((row) => !row.is_total) ??
    props.rows[0] ??
    null;
  const selectedViewLabel = props.selectedView === "monthly" ? "月度" : "汇总";
  const focusedBusinessSideLabel = focusedBusinessRow
    ? focusedBusinessRow.side === "asset"
      ? "资产"
      : focusedBusinessRow.side === "liability"
        ? "负债"
        : focusedBusinessRow.side
    : "详表暂无业务行";

  return (
    <section
      id="product-category-formal-mobile-focus"
      data-testid="product-category-formal-table-mobile-readout"
      className="product-category-formal-table-mobile-readout"
      aria-label="产品分类正式表移动读数"
    >
      <div className="product-category-formal-table-mobile-readout__header">
        <span className="product-category-formal-table-mobile-readout__eyebrow">
          当前核查
        </span>
        <h3 className="product-category-formal-table-mobile-readout__title">
          {focusedBusinessRow?.category_name ?? "正式报表"}
        </h3>
      </div>
      <div className="product-category-formal-table-mobile-readout__meta">
        <span>
          {props.reportDate
            ? formatProductCategoryReportMonthLabel(props.reportDate)
            : "报告月待选"}
        </span>
        <span>视图：{selectedViewLabel}</span>
        <span>{focusedBusinessSideLabel}</span>
      </div>
      <div className="product-category-formal-table-mobile-readout__fields">
        <ProductCategoryFormalTableReadoutField
          label="规模日均"
          value={
            focusedBusinessRow
              ? formatProductCategoryRowDisplayValue(
                  focusedBusinessRow,
                  focusedBusinessRow.cnx_scale,
                )
              : EM_DASH
          }
          detail="综本规模"
        />
        <ProductCategoryFormalTableReadoutField
          label="人民币净收入"
          value={
            focusedBusinessRow
              ? formatProductCategoryValue(
                  focusedBusinessRow.cny_net,
                )
              : EM_DASH
          }
          detail="正式表返回值"
        />
        <ProductCategoryFormalTableReadoutField
          label="外币净收入"
          value={
            focusedBusinessRow
              ? formatProductCategoryValue(
                  focusedBusinessRow.foreign_net,
                )
              : EM_DASH
          }
          detail="外币原值"
        />
        <ProductCategoryFormalTableReadoutField
          label="营业净收入"
          value={
            focusedBusinessRow
              ? formatProductCategoryValue(
                  focusedBusinessRow.business_net_income,
                )
              : EM_DASH
          }
          detail="当前产品"
        />
        <ProductCategoryFormalTableReadoutField
          label="加权收益率"
          value={
            focusedBusinessRow
              ? formatProductCategoryYieldValue(
                  focusedBusinessRow.weighted_yield,
                )
              : EM_DASH
          }
          detail="正式表返回值"
        />
        <ProductCategoryFormalTableReadoutField
          label="合计经营净收入"
          value={formatProductCategoryValue(
            props.grandTotal?.business_net_income,
          )}
          detail="总表参照"
        />
      </div>
      {focusedBusinessRow && props.onOpenAttributionEvidence ? (
        <button
          aria-label={`打开 ${focusedBusinessRow.category_name} 归因证据`}
          className="product-category-formal-table-mobile-readout__action"
          onClick={() =>
            props.onOpenAttributionEvidence?.(focusedBusinessRow.category_id)
          }
          type="button"
        >
          查看当前产品归因证据
        </button>
      ) : null}
    </section>
  );
}

export function ProductCategoryFormalSelectionContext(props: {
  reportDate: string;
  selectedView: string;
  sourceLabel: string;
  row: ProductCategoryPnlRow;
  onOpenAttributionEvidence?: (categoryId: string) => void;
}) {
  return (
    <section
      id="product-category-formal-selection-context"
      data-testid="product-category-formal-selection-context"
      className="product-category-formal-selection-context"
      aria-label={`${props.row.category_name} 正式表核查上下文`}
    >
      <div className="product-category-formal-selection-context__identity">
        <span>当前核查</span>
        <h3>{props.row.category_name}</h3>
        <p>
          {formatProductCategoryReportMonthLabel(props.reportDate)} ·{" "}
          {props.selectedView === "monthly" ? "月度" : "汇总"} |{" "}
          {props.sourceLabel}
        </p>
      </div>
      <dl className="product-category-formal-selection-context__metrics">
        <div>
          <dt>规模日均</dt>
          <dd>
            {formatProductCategoryRowDisplayValue(
              props.row,
              props.row.cnx_scale,
            )}
          </dd>
        </div>
        <div>
          <dt>人民币净收入</dt>
          <dd>
            {formatProductCategoryValue(props.row.cny_net)}
          </dd>
        </div>
        <div>
          <dt>外币净收入</dt>
          <dd>
            {formatProductCategoryValue(props.row.foreign_net)}
          </dd>
        </div>
        <div>
          <dt>营业净收入</dt>
          <dd>
            {formatProductCategoryValue(props.row.business_net_income)}
          </dd>
        </div>
        <div>
          <dt>加权收益率</dt>
          <dd>{formatProductCategoryYieldValue(props.row.weighted_yield)}</dd>
        </div>
      </dl>
      {props.onOpenAttributionEvidence ? (
        <button
          type="button"
          onClick={() =>
            props.onOpenAttributionEvidence?.(props.row.category_id)
          }
        >
          查看归因证据
        </button>
      ) : null}
    </section>
  );
}
