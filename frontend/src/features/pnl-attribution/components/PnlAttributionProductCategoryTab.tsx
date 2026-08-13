/**
 * 产品分类经营归因页签容器。
 * 自 PnlAttributionView.tsx 纯搬移（2026-08-13 拆分）：移动读数、归因/YTD
 * 表格、汇总卡与工作台，仅做 props 接线，不改行为。
 */
import type {
  ProductCategoryAttributionEffects,
  ProductCategoryAttributionPayload,
  ProductCategoryAttributionRow,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
  ResultMeta,
} from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { EM_DASH } from "../../../utils/format";
import {
  formatProductCategoryAttributionEffect,
  formatProductCategoryRowDisplayValue,
  selectProductCategoryClosureErrorSignal,
  formatProductCategoryValue,
  formatProductCategoryYieldValue,
} from "../../product-category-pnl/pages/productCategoryPnlPageModel";
import { derivePnlDataSectionState } from "../adapters/pnlAttributionAdapter";
import { cx } from "./pnlAttributionClassNames";
import { SectionLead } from "./pnlAttributionPrimitives";

const productCategoryEffectColumns: Array<
  [keyof ProductCategoryAttributionEffects, string]
> = [
  ["day_effect", "天数"],
  ["scale_effect", "规模"],
  ["rate_effect", "利率"],
  ["ftp_effect", "FTP"],
  ["direct_effect", "直接"],
  ["unexplained_effect", "未解释"],
  ["closure_error", "闭合"],
];

function ProductCategoryMobileReadoutField(props: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="pnl-attribution-mobile-table-readout__field">
      <span className="pnl-attribution-mobile-table-readout__label">
        {props.label}
      </span>
      <span className="pnl-attribution-mobile-table-readout__value">
        {props.value}
      </span>
      {props.note ? (
        <span className="pnl-attribution-mobile-table-readout__note">
          {props.note}
        </span>
      ) : null}
    </div>
  );
}

function ProductCategoryMobileReadout(props: {
  testId: string;
  title: string;
  fields: Array<{ label: string; value: string; note?: string }>;
}) {
  return (
    <div
      className="pnl-attribution-mobile-table-readout"
      data-testid={props.testId}
    >
      <div className="pnl-attribution-mobile-table-readout__header">
        {props.title}
      </div>
      <div className="pnl-attribution-mobile-table-readout__grid">
        {props.fields.map((field) => (
          <ProductCategoryMobileReadoutField
            key={field.label}
            label={field.label}
            note={field.note}
            value={field.value}
          />
        ))}
      </div>
    </div>
  );
}

function productCategoryEffectDisplayValue(
  value: ProductCategoryAttributionEffects[keyof ProductCategoryAttributionEffects],
) {
  return `${formatProductCategoryAttributionEffect(value)} 亿元`;
}

function pickProductCategoryAttributionHeadlineRow(
  rows: ProductCategoryAttributionRow[],
) {
  return rows.find((row) => row.category_id === "grand_total") ?? rows[0];
}

function pickLargestProductCategoryEffect(row: ProductCategoryAttributionRow) {
  return productCategoryEffectColumns
    .filter(([key]) => key !== "closure_error")
    .map(([key, label]) => ({
      key,
      label,
      value: row.effects[key],
      magnitude: Math.abs(Number(row.effects[key])),
    }))
    .filter((effect) => Number.isFinite(effect.magnitude))
    .sort((left, right) => right.magnitude - left.magnitude)[0];
}

function ProductCategoryAttributionMobileReadout(props: {
  rows: ProductCategoryAttributionRow[];
}) {
  const row = pickProductCategoryAttributionHeadlineRow(props.rows);
  const largestEffect = pickLargestProductCategoryEffect(row);
  const closureErrorSignal = selectProductCategoryClosureErrorSignal(
    row.effects.closure_error,
  );
  return (
    <ProductCategoryMobileReadout
      testId="pnl-attribution-product-category-attribution-mobile-readout"
      title="移动归因读数"
      fields={[
        {
          label: "经营变动",
          value: productCategoryEffectDisplayValue(
            row.effects.delta_business_net_income,
          ),
          note: row.category_name,
        },
        {
          label: "最大拆分项",
          value: largestEffect
            ? `${largestEffect.label} ${productCategoryEffectDisplayValue(largestEffect.value)}`
            : EM_DASH,
        },
        {
          label: "未解释差异",
          value: productCategoryEffectDisplayValue(row.effects.unexplained_effect),
        },
        {
          label: "闭合误差",
          value: productCategoryEffectDisplayValue(row.effects.closure_error),
          note: closureErrorSignal.warningText ?? undefined,
        },
        {
          label: "状态",
          value: row.state,
        },
      ]}
    />
  );
}

function pickProductCategoryYtdHeadlineRow(rows: ProductCategoryPnlRow[]) {
  return (
    rows.find((row) => row.category_id === "grand_total") ??
    rows.find((row) => row.is_total && row.category_name.includes("合计")) ??
    rows[rows.length - 1]
  );
}

function ProductCategoryYtdMobileReadout(props: {
  rows: ProductCategoryPnlRow[];
}) {
  const row = pickProductCategoryYtdHeadlineRow(props.rows);
  return (
    <ProductCategoryMobileReadout
      testId="pnl-attribution-product-category-ytd-mobile-readout"
      title="移动YTD读数"
      fields={[
        {
          label: "累计净营收",
          value: `${formatProductCategoryRowDisplayValue(
            row,
            row.business_net_income,
          )} 亿元`,
          note: row.category_name,
        },
        {
          label: "累计规模",
          value: `${formatProductCategoryRowDisplayValue(row, row.cnx_scale)} 亿元`,
        },
        {
          label: "加权收益率",
          value: `${formatProductCategoryYieldValue(row.weighted_yield)}%`,
        },
        {
          label: "展示行数",
          value: String(props.rows.length),
        },
      ]}
    />
  );
}

function ProductCategorySummaryCard(props: {
  label: string;
  value: string;
  subLabel: string;
}) {
  return (
    <div className="pnl-attribution-product-category-summary-card">
      <div
        className="pnl-attribution-product-category-summary-card__label"
        title={props.label}
      >
        {props.label}
      </div>
      <div className="pnl-attribution-product-category-summary-card__value">
        {props.value}
      </div>
      <div className="pnl-attribution-product-category-summary-card__sub-label">
        {props.subLabel}
      </div>
    </div>
  );
}

function ProductCategoryAttributionTable(props: {
  rows: ProductCategoryAttributionRow[];
}) {
  if (props.rows.length === 0) {
    return (
      <div className="pnl-attribution-empty-note">
        产品分类月度归因暂无可展示行。
      </div>
    );
  }
  return (
    <>
      <ProductCategoryAttributionMobileReadout rows={props.rows} />
      <div
        data-testid="pnl-attribution-product-category-attribution-raw-grid"
        className="pnl-attribution-table-scroll"
      >
      <table
        data-testid="pnl-attribution-product-category-attribution-table"
        className="pnl-attribution-compact-table"
      >
        <thead>
          <tr>
            <th className="pnl-attribution-compact-table__left">产品分类</th>
            <th className="pnl-attribution-compact-table__num">变动</th>
            {productCategoryEffectColumns.map(([, label]) => (
              <th
                key={label}
                className="pnl-attribution-compact-table__num"
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={row.category_id}>
              <td
                className={cx(
                  "pnl-attribution-compact-table__left",
                  row.level === 0 && "pnl-attribution-compact-table__cell--strong",
                )}
              >
                {row.category_name}
              </td>
              <td className="pnl-attribution-compact-table__num">
                {formatProductCategoryAttributionEffect(
                  row.effects.delta_business_net_income,
                )}
              </td>
              {productCategoryEffectColumns.map(([key]) => (
                <td key={key} className="pnl-attribution-compact-table__num">
                  {formatProductCategoryAttributionEffect(row.effects[key])}
                  {key === "closure_error" &&
                  selectProductCategoryClosureErrorSignal(row.effects.closure_error)
                    .hasMaterialGap ? (
                    <span
                      className="pnl-attribution-compact-table__closure-flag"
                      title="对账残差非零，父级自报变动与子项之和存在缺口"
                    >
                      {" "}
                      ⚠
                    </span>
                  ) : null}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </>
  );
}

function ProductCategoryYtdTable(props: { rows: ProductCategoryPnlRow[] }) {
  if (props.rows.length === 0) {
    return (
      <div className="pnl-attribution-empty-note">
        产品分类 YTD 汇总暂无可展示行。
      </div>
    );
  }
  return (
    <>
      <ProductCategoryYtdMobileReadout rows={props.rows} />
      <div
        data-testid="pnl-attribution-product-category-ytd-raw-grid"
        className="pnl-attribution-table-scroll"
      >
      <table
        data-testid="pnl-attribution-product-category-ytd-table"
        className="pnl-attribution-compact-table"
      >
        <thead>
          <tr>
            <th className="pnl-attribution-compact-table__left">产品分类</th>
            <th className="pnl-attribution-compact-table__num">规模</th>
            <th className="pnl-attribution-compact-table__num">净营收</th>
            <th className="pnl-attribution-compact-table__num">收益率</th>
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={row.category_id}>
              <td
                className={cx(
                  "pnl-attribution-compact-table__left",
                  row.is_total && "pnl-attribution-compact-table__cell--strong",
                )}
              >
                {row.category_name}
              </td>
              <td className="pnl-attribution-compact-table__num">
                {formatProductCategoryRowDisplayValue(row, row.cnx_scale)}
              </td>
              <td className="pnl-attribution-compact-table__num">
                {formatProductCategoryRowDisplayValue(
                  row,
                  row.business_net_income,
                )}
              </td>
              <td className="pnl-attribution-compact-table__num">
                {formatProductCategoryYieldValue(row.weighted_yield)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </>
  );
}

function ProductCategoryAttributionWorkbench(props: {
  monthlyData: ProductCategoryPnlPayload | null;
  ytdData: ProductCategoryPnlPayload | null;
  attributionData: ProductCategoryAttributionPayload | null;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  if (props.isLoading) {
    return (
      <div
        data-testid="pnl-attribution-product-category-tab"
        className="pnl-attribution-panel pnl-attribution-panel--compact"
      >
        产品分类归因加载中...
      </div>
    );
  }
  if (props.error) {
    return (
      <div
        data-testid="pnl-attribution-product-category-tab"
        className="pnl-attribution-panel pnl-attribution-panel--compact"
      >
        产品分类来源加载失败：{props.error}
        <button
          type="button"
          onClick={props.onRetry}
          className="pnl-attribution-tab-button pnl-attribution-tab-button--inline"
        >
          重试
        </button>
      </div>
    );
  }
  if (!props.monthlyData && !props.ytdData && !props.attributionData) {
    return (
      <div
        data-testid="pnl-attribution-product-category-tab"
        className="pnl-attribution-panel pnl-attribution-panel--compact"
      >
        产品分类来源暂无可用报告日数据。
      </div>
    );
  }

  const totals = props.attributionData?.totals;
  const attributionRows = totals
    ? [totals.asset_total, totals.liability_total, totals.grand_total]
    : (props.attributionData?.rows.slice(0, 8) ?? []);
  const ytdRows = props.ytdData
    ? [
        ...props.ytdData.rows.slice(0, 8),
        props.ytdData.asset_total,
        props.ytdData.liability_total,
        props.ytdData.grand_total,
      ]
    : [];
  const headline = totals?.grand_total.effects;
  return (
    <div
      data-testid="pnl-attribution-product-category-tab"
      className="pnl-attribution-product-category-workbench"
    >
      <div
        className="pnl-attribution-product-category-summary-grid"
      >
        <ProductCategorySummaryCard
          label="月度净营收"
          value={`${formatProductCategoryValue(props.monthlyData?.grand_total.business_net_income)} 亿元`}
          subLabel={props.monthlyData?.report_date ?? EM_DASH}
        />
        <ProductCategorySummaryCard
          label="YTD 净营收"
          value={`${formatProductCategoryValue(props.ytdData?.grand_total.business_net_income)} 亿元`}
          subLabel={props.ytdData?.report_date ?? EM_DASH}
        />
        <ProductCategorySummaryCard
          label="月度变动"
          value={`${formatProductCategoryAttributionEffect(headline?.delta_business_net_income)} 亿元`}
          subLabel={props.attributionData?.compare === "yoy" ? "同比" : "环比"}
        />
        <ProductCategorySummaryCard
          label="未解释差异"
          value={`${formatProductCategoryAttributionEffect(headline?.unexplained_effect)} 亿元`}
          subLabel={props.attributionData?.state ?? EM_DASH}
        />
      </div>
      <div className="pnl-attribution-panel pnl-attribution-panel--compact">
        <SectionLead
          variant="card"
          eyebrow="产品分类归因"
          title="月度经营差异拆分"
          description="直接复用产品分类已开放的 monthly attribution，不把 YTD 汇总硬套到规模/利率公式。"
        />
        <div className="pnl-attribution-section-body">
          <ProductCategoryAttributionTable rows={attributionRows} />
        </div>
      </div>

      <div className="pnl-attribution-panel pnl-attribution-panel--compact">
        <SectionLead
          variant="card"
          eyebrow="产品分类 YTD"
          title="累计汇总对照"
          description="YTD 只作为产品分类汇总对照，保持产品分类页已计算好的口径。"
        />
        <div className="pnl-attribution-section-body">
          <ProductCategoryYtdTable rows={ytdRows} />
        </div>
      </div>
    </div>
  );
}

export function ProductCategoryTabPanels(props: {
  monthlyData: ProductCategoryPnlPayload | null;
  ytdData: ProductCategoryPnlPayload | null;
  attributionData: ProductCategoryAttributionPayload | null;
  monthlyMeta: ResultMeta | null;
  ytdMeta: ResultMeta | null;
  attributionMeta: ResultMeta | null;
  isLoading: boolean;
  errorMessage: string | null;
  onRetry: () => void;
}) {
  const productCategoryMetaSections = [
    {
      key: "product-category-attribution",
      title: "产品分类月度归因",
      meta: props.attributionMeta,
    },
    {
      key: "product-category-monthly",
      title: "产品分类月度汇总",
      meta: props.monthlyMeta,
    },
    {
      key: "product-category-ytd",
      title: "产品分类 YTD 汇总",
      meta: props.ytdMeta,
    },
  ];

  const productCategoryState: DataSectionState = derivePnlDataSectionState({
    meta: props.attributionMeta ?? props.monthlyMeta ?? props.ytdMeta,
    isLoading: props.isLoading,
    isError: props.errorMessage !== null,
    errorMessage: props.errorMessage,
    isEmpty:
      !props.monthlyData && !props.ytdData && !props.attributionData,
  });

  return (
    <>
      <FormalResultMetaPanel
        testId="pnl-attribution-product-category-view-meta"
        title="产品分类来源元信息"
        emptyText={
          props.isLoading ? "加载中..." : "当前还没有可展示的产品分类来源元信息。"
        }
        sections={productCategoryMetaSections}
      />
      <ProductCategoryAttributionWorkbench
        monthlyData={props.monthlyData}
        ytdData={props.ytdData}
        attributionData={props.attributionData}
        isLoading={productCategoryState.kind === "loading"}
        error={
          productCategoryState.kind === "error"
            ? (productCategoryState.message ?? "加载失败")
            : null
        }
        onRetry={props.onRetry}
      />
    </>
  );
}
