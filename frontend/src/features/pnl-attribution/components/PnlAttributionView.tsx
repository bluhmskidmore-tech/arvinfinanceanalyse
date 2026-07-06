import { useCallback, useEffect, useState } from "react";

import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import type { DataSectionState } from "../../../components/DataSection.types";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import type {
  AdvancedAttributionSummary,
  CampisiAttributionPayload,
  CampisiDecisionGradePayload,
  CampisiEnhancedPayload,
  CampisiFourEffectsPayload,
  CampisiMaturityBucketsPayload,
  CarryRollDownPayload,
  KRDAttributionPayload,
  PnlCompositionPayload,
  ProductCategoryAttributionEffects,
  ProductCategoryAttributionPayload,
  ProductCategoryAttributionRow,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
  ResultMeta,
  SpreadAttributionPayload,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "../../../api/contracts";
import { derivePnlDataSectionState } from "../adapters/pnlAttributionAdapter";
import { AdvancedAttributionChart } from "./AdvancedAttributionChart";
import { AttributionWaterfallChart } from "./AttributionWaterfallChart";
import { CampisiAttributionPanel } from "./CampisiAttributionPanel";
import { CampisiDecisionGradePanel } from "./CampisiDecisionGradePanel";
import { CampisiEnhancedPanel } from "./CampisiEnhancedPanel";
import { CampisiMaturityBucketPanel } from "./CampisiMaturityBucketPanel";
import { PnLCompositionChart } from "./PnLCompositionChart";
import { TPLMarketChart, type ProductCategoryTplMonthlyPoint } from "./TPLMarketChart";
import { VolumeRateAnalysisChart } from "./VolumeRateAnalysisChart";
import "./PnlAttributionView.css";
import {
  buildVolumeRateBridgeSummary,
  type DualReportDateResolution,
  formatYi,
  formatMetaDateLabel,
  resolveDualReportDates,
  type VolumeRateBridgeSummary,
  type PnlAttributionTab,
} from "./pnlAttributionViewModel";
import {
  formatProductCategoryAttributionEffect,
  formatProductCategoryRowDisplayValue,
  selectProductCategoryClosureErrorSignal,
  formatProductCategoryValue,
  formatProductCategoryYieldValue,
} from "../../product-category-pnl/pages/productCategoryPnlPageModel";

function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

function tabButtonClassName(
  active: boolean,
  variant: "default" | "advanced" = "default",
) {
  return cx(
    "pnl-attribution-tab-button",
    active && "pnl-attribution-tab-button--active",
    variant === "advanced" && "pnl-attribution-tab-button--advanced",
  );
}

function valueToneClassName(value: number | undefined) {
  if (value === undefined) return "pnl-attribution-tone--neutral";
  return value >= 0
    ? "pnl-attribution-tone--positive"
    : "pnl-attribution-tone--negative";
}

const PRODUCT_CATEGORY_TPL_ROW_ID = "bond_tpl";

function findProductCategoryReportDateForPeriod(
  reportDates: readonly string[],
  period: string,
): string | null {
  const periodPrefix = `${period}-`;
  return reportDates.find((date) => date.startsWith(periodPrefix)) ?? null;
}

function selectProductCategoryTplRow(
  payload: ProductCategoryPnlPayload,
): ProductCategoryPnlRow | null {
  return (
    payload.rows.find((row) => row.category_id === PRODUCT_CATEGORY_TPL_ROW_ID) ??
    null
  );
}

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
  testId?: string;
}) {
  return (
    <div data-testid={props.testId} className="pnl-attribution-section-lead">
      <span className="pnl-attribution-section-lead__eyebrow">
        {props.eyebrow}
      </span>
      <h2 className="pnl-attribution-section-lead__title">{props.title}</h2>
      <p className="pnl-attribution-section-lead__description">
        {props.description}
      </p>
    </div>
  );
}

function LensBoundaryPanel() {
  return (
    <div className="pnl-attribution-lens-grid">
      <section
        data-testid="pnl-attribution-product-category-lens-card"
        aria-label="产品分类经营归因口径边界"
        className="pnl-attribution-lens-card"
      >
        <SectionLead
          eyebrow="产品分类经营口径"
          title="经营净收入归因"
          description="经营净收入、FTP 后；来源为产品分类正式读模型，只消费产品分类 monthly / YTD / attribution 接口。"
        />
        <div className="pnl-attribution-lens-status" data-testid="pnl-attribution-product-category-lens-status">
          证据状态：正式读模型已就绪；报告日由页面日期协调器校验。
        </div>
        <div className="pnl-attribution-lens-source">
          Source: /ui/pnl/product-category, /ui/pnl/product-category/attribution
        </div>
      </section>
      <section
        data-testid="pnl-attribution-formal-lens-card"
        aria-label="正式 FI 与债券分析归因口径边界"
        className="pnl-attribution-lens-card"
      >
        <SectionLead
          eyebrow="正式 FI / 债券分析口径"
          title="会计损益与债券市场归因"
          description="含非标桥接、未扣 FTP、非产品分类经营净收入；仅用于正式 FI、TPL 市场和债券分析归因。"
        />
        <div className="pnl-attribution-lens-status" data-testid="pnl-attribution-formal-lens-status">
          证据状态：正式归因口径已就绪；TPL 市场例外在工作台中单独标注。
        </div>
        <div className="pnl-attribution-lens-source">Source: /api/pnl-attribution/*</div>
      </section>
    </div>
  );
}

function formatPct(value: number | undefined): string {
  if (value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return `${value.toFixed(1)}%`;
}

function VolumeRateBridgePanel(props: {
  data: VolumeRateAttributionPayload;
  summary: VolumeRateBridgeSummary;
}) {
  const { data, summary } = props;
  const residualIsMaterial =
    summary.unexplainedEffect !== undefined &&
    Math.abs(summary.unexplainedEffect) > 10_000;
  const denominator =
    summary.pnlChange !== undefined && Math.abs(summary.pnlChange) > 10_000
      ? summary.pnlChange
      : undefined;
  const bridgeRows = [
    {
      label: "规模效应",
      formula: "Δ规模 × 上期收益率",
      value: summary.volumeEffect,
      accentClass: "pnl-attribution-bridge-table__dot--volume",
    },
    {
      label: "利率效应",
      formula: "上期规模 × Δ收益率",
      value: summary.rateEffect,
      accentClass: "pnl-attribution-bridge-table__dot--rate",
    },
    {
      label: "交叉效应",
      formula: "Δ规模 × Δ收益率",
      value: summary.interactionEffect,
      accentClass: "pnl-attribution-bridge-table__dot--interaction",
    },
    {
      label: "未解释差额",
      formula: residualIsMaterial ? "缺规模或未匹配分类" : "闭合容差内",
      value: summary.unexplainedEffect,
      accentClass: residualIsMaterial
        ? "pnl-attribution-bridge-table__dot--residual"
        : "pnl-attribution-bridge-table__dot--neutral",
      isResidual: true,
    },
  ];

  return (
    <div
      data-testid="volume-rate-bridge-panel"
      className="pnl-attribution-bridge-panel"
    >
      <div
        className="pnl-attribution-bridge-panel__grid"
      >
        <div
          className="pnl-attribution-bridge-panel__summary"
        >
          <div>
            <div className="pnl-attribution-section-lead__eyebrow">规模 / 利率效应</div>
            <h3 className="pnl-attribution-bridge-panel__title">
              损益变动桥
            </h3>
            <div
              className={cx(
                "pnl-attribution-bridge-panel__value",
                valueToneClassName(summary.pnlChange),
              )}
            >
              {formatYi(summary.pnlChange)}
            </div>
            <div className="pnl-attribution-bridge-panel__periods">
              <span>
                {data.previous_period} {formatYi(summary.previousPnl)}
              </span>
              <span>→</span>
              <span>
                {data.current_period} {formatYi(summary.currentPnl)}
              </span>
            </div>
          </div>
          <div
            className="pnl-attribution-bridge-panel__status"
            data-status={summary.status}
          >
            <span>{summary.statusLabel}</span>
            <span className="pnl-attribution-tabular">
              解释覆盖 {formatPct(summary.coveragePct)}
            </span>
          </div>
        </div>

        <div className="pnl-attribution-bridge-panel__details">
          <div className="pnl-attribution-bridge-panel__details-header">
            <div className="pnl-attribution-bridge-panel__details-title">
              变动拆分
            </div>
            <div className="pnl-attribution-bridge-panel__unit">
              单位：亿元
            </div>
          </div>
          <div className="pnl-attribution-table-scroll">
            <table className="pnl-attribution-bridge-table">
              <thead>
                <tr>
                  <th className="pnl-attribution-bridge-table__left">
                    项目
                  </th>
                  <th className="pnl-attribution-bridge-table__left">
                    计算口径
                  </th>
                  <th className="pnl-attribution-bridge-table__num">
                    金额
                  </th>
                  <th className="pnl-attribution-bridge-table__num">
                    占变动
                  </th>
                </tr>
              </thead>
              <tbody>
                {bridgeRows.map((row) => {
                  const share =
                    denominator !== undefined && row.value !== undefined
                      ? Math.abs(row.value / denominator) * 100
                      : undefined;
                   return (
                     <tr
                       key={row.label}
                       className={cx(
                         row.isResidual &&
                           residualIsMaterial &&
                           "pnl-attribution-bridge-table__row--material-residual",
                       )}
                     >
                       <td className="pnl-attribution-bridge-table__label">
                         <span
                           className={cx(
                             "pnl-attribution-bridge-table__dot",
                             row.accentClass,
                           )}
                         />
                         {row.label}
                       </td>
                       <td className="pnl-attribution-bridge-table__formula">
                         {row.formula}
                       </td>
                       <td
                         className={cx(
                           "pnl-attribution-bridge-table__amount",
                           valueToneClassName(row.value),
                         )}
                       >
                         {formatYi(row.value)}
                       </td>
                       <td className="pnl-attribution-bridge-table__share">
                         {formatPct(share)}
                       </td>
                     </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="pnl-attribution-bridge-panel__footer">
        <span>损益变动 = 当期损益 - 上期损益</span>
        <span className="pnl-attribution-tabular">
          {formatYi(summary.volumeEffect)} + {formatYi(summary.rateEffect)} +{" "}
          {formatYi(summary.interactionEffect)} +{" "}
          {formatYi(summary.unexplainedEffect)} = {formatYi(summary.pnlChange)}
        </span>
      </div>
    </div>
  );
}

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
            : "-",
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

function PnlAttributionSourceDateMessage(props: {
  resolution: DualReportDateResolution | null;
  dateError: string | null;
  isLoading: boolean;
}) {
  if (props.isLoading) {
    return (
      <div
        data-testid="pnl-attribution-date-loading"
        className="pnl-attribution-panel pnl-attribution-panel--compact"
      >
        正在加载产品分类与正式 FI 报告日...
      </div>
    );
  }
  if (props.dateError) {
    return (
      <div
        data-testid="pnl-attribution-date-error"
        className="pnl-attribution-panel pnl-attribution-panel--compact"
      >
        报告日来源加载失败：{props.dateError}
      </div>
    );
  }
  if (!props.resolution) {
    return null;
  }
  if (!props.resolution.hasFormalDate || !props.resolution.hasProductCategoryDate) {
    const source =
      props.resolution.missingSource === "formal-attribution"
        ? "正式 FI / 债券分析"
        : props.resolution.missingSource === "product-category"
          ? "产品分类"
          : "产品分类和正式 FI / 债券分析";
    return (
      <div
        data-testid="pnl-attribution-source-date-warning"
        className="pnl-attribution-panel pnl-attribution-panel--compact"
      >
        {source}来源当前无可用报告日；另一套口径仍可独立查看，不再强制共同日期。
      </div>
    );
  }
  if (!props.resolution.datesAligned) {
    return (
      <div
        data-testid="pnl-attribution-date-mismatch"
        className="pnl-attribution-panel pnl-attribution-panel--compact"
      >
        两套口径报告日不一致：正式 FI / 债券分析{" "}
        {props.resolution.formalReportDate}；产品分类{" "}
        {props.resolution.productCategoryReportDate}。页面将分开取数，不做跨口径闭合。
      </div>
    );
  }
  return null;
}

function ProductCategorySummaryCard(props: {
  label: string;
  value: string;
  subLabel: string;
}) {
  return (
    <div className="pnl-attribution-product-category-summary-card">
      <div className="pnl-attribution-product-category-summary-card__label">
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
          subLabel={props.monthlyData?.report_date ?? "-"}
        />
        <ProductCategorySummaryCard
          label="YTD 净营收"
          value={`${formatProductCategoryValue(props.ytdData?.grand_total.business_net_income)} 亿元`}
          subLabel={props.ytdData?.report_date ?? "-"}
        />
        <ProductCategorySummaryCard
          label="月度变动"
          value={`${formatProductCategoryAttributionEffect(headline?.delta_business_net_income)} 亿元`}
          subLabel={props.attributionData?.compare === "yoy" ? "同比" : "环比"}
        />
        <ProductCategorySummaryCard
          label="未解释差异"
          value={`${formatProductCategoryAttributionEffect(headline?.unexplained_effect)} 亿元`}
          subLabel={props.attributionData?.state ?? "-"}
        />
      </div>
      <div className="pnl-attribution-panel pnl-attribution-panel--compact">
        <SectionLead
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

function compactMetaValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function compactMetaStatus(value: ResultMeta["quality_flag"]) {
  if (value === "warning") {
    return {
      label: "预警",
      quality: "warning",
    };
  }
  if (value === "error" || value === "missing") {
    return {
      label: value === "missing" ? "缺失" : "错误",
      quality: value,
    };
  }
  if (value === "stale") {
    return {
      label: "陈旧",
      quality: "stale",
    };
  }
  return {
    label: "正常",
    quality: "normal",
  };
}

function CurrentViewMetaStrip(props: {
  title: string;
  meta: ResultMeta;
  testId: string;
}) {
  const quality = compactMetaStatus(props.meta.quality_flag);
  const fallback =
    props.meta.fallback_mode === "none"
      ? "未降级"
      : compactMetaValue(props.meta.fallback_mode);
  const fields = [
    [
      "口径",
      props.meta.basis === "formal"
        ? "正式口径"
        : compactMetaValue(props.meta.basis),
    ],
    ["结果类型", compactMetaValue(props.meta.result_kind)],
    ["数据截至日", compactMetaValue(props.meta.as_of_date)],
    ["生成时间", compactMetaValue(props.meta.generated_at)],
    ["追踪编号", compactMetaValue(props.meta.trace_id)],
    ["规则版本", compactMetaValue(props.meta.rule_version)],
  ];

  return (
    <section
      data-testid={props.testId}
      className="pnl-attribution-meta-strip"
    >
      <div className="pnl-attribution-meta-strip__header">
        <div className="pnl-attribution-meta-strip__copy">
          <span className="pnl-attribution-meta-strip__eyebrow">
            当前视图结果元信息
          </span>
          <strong className="pnl-attribution-meta-strip__title">
            {props.title}
          </strong>
        </div>
        <div className="pnl-attribution-meta-strip__badges">
          <span
            className="pnl-attribution-mode-badge pnl-attribution-mode-badge--plain"
            data-quality={quality.quality}
          >
            {quality.label}
          </span>
          <span
            className="pnl-attribution-mode-badge pnl-attribution-mode-badge--muted"
          >
            {fallback}
          </span>
        </div>
      </div>
      <div className="pnl-attribution-meta-strip__grid">
        {fields.map(([label, value]) => (
          <div
            key={label}
            className="pnl-attribution-meta-strip__field"
          >
            <span className="pnl-attribution-meta-strip__label">{label}</span>
            <span
              title={value}
              className="pnl-attribution-meta-strip__value"
            >
              {value}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function pnlAttributionLensSummary(activeTab: PnlAttributionTab) {
  if (activeTab === "product-category") {
    return {
      label: "产品分类经营归因",
      detail: "FTP 后经营净收入；只读取 /ui/pnl/product-category。",
      source: "/ui/pnl/product-category",
    };
  }
  if (activeTab === "tpl-market") {
    return {
      label: "TPL hybrid exception",
      detail: "市场序列来自 /api/pnl-attribution/tpl-market；bond_tpl 月度行来自 /ui/pnl/product-category。",
      source: "/api/pnl-attribution/tpl-market + /ui/pnl/product-category",
    };
  }
  if (activeTab === "advanced") {
    return {
      label: "正式 FI / Campisi 归因",
      detail: "正式 FI、债券分析、Campisi 决策级解释；不等同产品分类经营净收入。",
      source: "/api/pnl-attribution/*",
    };
  }
  return {
    label: "正式 FI / 债券归因",
    detail: "正式 FI 归因视图；不跨口径闭合产品分类经营净收入。",
    source: "/api/pnl-attribution/*",
  };
}

function formatDateResolutionSummary(
  resolution: DualReportDateResolution | null,
  activeTab: PnlAttributionTab,
) {
  if (!resolution) {
    return "报告日来源待确认";
  }
  const activeDate =
    activeTab === "product-category"
      ? resolution.productCategoryReportDate
      : resolution.formalReportDate;
  if (!resolution.hasFormalDate || !resolution.hasProductCategoryDate) {
    return `缺少来源；当前可用报告日 ${activeDate ?? "—"}`;
  }
  if (!resolution.datesAligned) {
    return `日期分离：正式 FI ${resolution.formalReportDate ?? "—"} / 产品分类 ${resolution.productCategoryReportDate ?? "—"}`;
  }
  return `共同报告日 ${activeDate ?? "—"}`;
}

function PnlAttributionDecisionStrip(props: {
  activeTab: PnlAttributionTab;
  compareType: "mom" | "yoy";
  currentViewDateTitle: string;
  currentViewMeta: ResultMeta | null;
  dateResolution: DualReportDateResolution | null;
  isLoading: boolean;
  hasError: boolean;
}) {
  const lens = pnlAttributionLensSummary(props.activeTab);
  const quality = props.currentViewMeta
    ? compactMetaStatus(props.currentViewMeta.quality_flag)
    : null;
  const qualityState = props.currentViewMeta?.quality_flag ?? "pending";
  const fallback =
    props.currentViewMeta?.fallback_mode === "none"
      ? "未降级"
      : compactMetaValue(props.currentViewMeta?.fallback_mode);
  const dateSummary = formatDateResolutionSummary(
    props.dateResolution,
    props.activeTab,
  );
  const action =
    props.hasError
      ? "先处理加载错误"
      : props.isLoading
        ? "等待当前视图加载"
        : props.activeTab === "product-category"
          ? "先看经营归因闭合"
          : props.activeTab === "tpl-market"
            ? "核对 hybrid 来源"
            : props.activeTab === "advanced"
              ? "复核 Campisi 决策级"
              : "检查正式 FI 归因";
  const fields = [
    ["Page status", "candidate_or_pending"],
    ["Formal use", "formal_use_allowed=false"],
    ["Owner approval", "owner approval pending"],
    ["Closure", "closure_approved=false"],
    ["当前口径", lens.label],
    ["报告日", dateSummary],
    ["来源", lens.source],
    ["视图期间", props.currentViewDateTitle],
    ["质量", quality?.label ?? "待加载"],
    ["降级", fallback],
    ["比较", props.compareType === "mom" ? "环比" : "同比"],
    ["下一步", action],
  ];

  return (
    <section
      data-testid="pnl-attribution-decision-strip"
      className="pnl-attribution-decision-strip"
    >
      <div className="pnl-attribution-decision-strip__header">
        <div className="pnl-attribution-decision-strip__copy">
          <span className="pnl-attribution-decision-strip__eyebrow">
            归因决策条
          </span>
          <strong className="pnl-attribution-decision-strip__title">
            {lens.label}
          </strong>
          <span className="pnl-attribution-decision-strip__detail">
            {lens.detail}
          </span>
        </div>
        <span
          className="pnl-attribution-decision-strip__badge"
          data-quality={qualityState}
        >
          {quality?.label ?? "待加载"}
        </span>
      </div>
      <div className="pnl-attribution-decision-strip__grid">
        {fields.map(([label, value]) => (
          <div className="pnl-attribution-decision-strip__field" key={label}>
            <span className="pnl-attribution-decision-strip__label">
              {label}
            </span>
            <span
              className="pnl-attribution-decision-strip__value"
              title={value}
            >
              {value}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

type Props = {
  reportDate?: string;
};

export function PnlAttributionView({ reportDate }: Props) {
  const client = useApiClient();
  const [activeTab, setActiveTab] = useState<PnlAttributionTab>("product-category");
  const [compareType, setCompareType] = useState<"mom" | "yoy">("mom");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dateLoading, setDateLoading] = useState(false);
  const [dateError, setDateError] = useState<string | null>(null);
  const [dateResolution, setDateResolution] =
    useState<DualReportDateResolution | null>(null);
  const [selectedFormalReportDate, setSelectedFormalReportDate] =
    useState<string | null>(reportDate ?? null);
  const [
    selectedProductCategoryReportDate,
    setSelectedProductCategoryReportDate,
  ] = useState<string | null>(reportDate ?? null);

  const [volumeRateData, setVolumeRateData] =
    useState<VolumeRateAttributionPayload | null>(null);
  const [tplMarketData, setTplMarketData] =
    useState<TPLMarketCorrelationPayload | null>(null);
  const [tplProductCategoryMonthlyPoints, setTplProductCategoryMonthlyPoints] =
    useState<ProductCategoryTplMonthlyPoint[]>([]);
  const [compositionData, setCompositionData] =
    useState<PnlCompositionPayload | null>(null);
  const [productCategoryMonthlyData, setProductCategoryMonthlyData] =
    useState<ProductCategoryPnlPayload | null>(null);
  const [productCategoryYtdData, setProductCategoryYtdData] =
    useState<ProductCategoryPnlPayload | null>(null);
  const [productCategoryAttributionData, setProductCategoryAttributionData] =
    useState<ProductCategoryAttributionPayload | null>(null);
  const [volumeRateMeta, setVolumeRateMeta] = useState<ResultMeta | null>(null);
  const [tplMarketMeta, setTplMarketMeta] = useState<ResultMeta | null>(null);
  const [compositionMeta, setCompositionMeta] = useState<ResultMeta | null>(
    null,
  );
  const [productCategoryMonthlyMeta, setProductCategoryMonthlyMeta] =
    useState<ResultMeta | null>(null);
  const [productCategoryYtdMeta, setProductCategoryYtdMeta] =
    useState<ResultMeta | null>(null);
  const [productCategoryAttributionMeta, setProductCategoryAttributionMeta] =
    useState<ResultMeta | null>(null);
  const [advancedSummaryMeta, setAdvancedSummaryMeta] =
    useState<ResultMeta | null>(null);

  const [carryRollDownData, setCarryRollDownData] =
    useState<CarryRollDownPayload | null>(null);
  const [spreadData, setSpreadData] = useState<SpreadAttributionPayload | null>(
    null,
  );
  const [krdData, setKrdData] = useState<KRDAttributionPayload | null>(null);
  const [advancedSummary, setAdvancedSummary] =
    useState<AdvancedAttributionSummary | null>(null);
  const [campisiData, setCampisiData] =
    useState<CampisiAttributionPayload | null>(null);
  const [campisiFourEffects, setCampisiFourEffects] =
    useState<CampisiFourEffectsPayload | null>(null);
  const [campisiEnhanced, setCampisiEnhanced] =
    useState<CampisiEnhancedPayload | null>(null);
  const [campisiMaturityBuckets, setCampisiMaturityBuckets] =
    useState<CampisiMaturityBucketsPayload | null>(null);
  const [campisiDecisionGrade, setCampisiDecisionGrade] =
    useState<CampisiDecisionGradePayload | null>(null);
  const [campisiDecisionGradeError, setCampisiDecisionGradeError] =
    useState<string | null>(null);
  const [carryMeta, setCarryMeta] = useState<ResultMeta | null>(null);
  const [spreadMeta, setSpreadMeta] = useState<ResultMeta | null>(null);
  const [krdMeta, setKrdMeta] = useState<ResultMeta | null>(null);
  const [campisiFourMeta, setCampisiFourMeta] = useState<ResultMeta | null>(
    null,
  );
  const [campisiEnhancedMeta, setCampisiEnhancedMeta] =
    useState<ResultMeta | null>(null);
  const [campisiMaturityMeta, setCampisiMaturityMeta] =
    useState<ResultMeta | null>(null);
  const [campisiDecisionGradeMeta, setCampisiDecisionGradeMeta] =
    useState<ResultMeta | null>(null);

  const isProductCategoryTab = activeTab === "product-category";
  const effectiveReportDate = isProductCategoryTab
    ? (reportDate ?? selectedProductCategoryReportDate ?? undefined)
    : (reportDate ?? selectedFormalReportDate ?? undefined);

  const loadDateOptions = useCallback(async () => {
    setDateLoading(true);
    setDateError(null);
    try {
      const [businessDatesEnvelope, productCategoryDatesEnvelope] =
        await Promise.all([
          client.getFormalPnlDates("formal"),
          client.getProductCategoryDates(),
        ]);
      const businessDates = businessDatesEnvelope.result.formal_fi_report_dates
        ?.length
        ? businessDatesEnvelope.result.formal_fi_report_dates
        : businessDatesEnvelope.result.report_dates;
      const resolution = resolveDualReportDates({
        businessDates,
        productCategoryDates: productCategoryDatesEnvelope.result.report_dates,
        preferredReportDate: reportDate,
      });
      setDateResolution(resolution);
      setSelectedFormalReportDate(reportDate ?? resolution.formalReportDate);
      setSelectedProductCategoryReportDate(reportDate ?? resolution.productCategoryReportDate);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "报告日来源加载失败";
      setDateError(msg);
      setSelectedFormalReportDate(reportDate ?? null);
      setSelectedProductCategoryReportDate(reportDate ?? null);
    } finally {
      setDateLoading(false);
    }
  }, [client, reportDate]);

  const loadData = useCallback(async () => {
    if (!effectiveReportDate) {
      return;
    }
    setLoading(true);
    setError(null);
    setCampisiDecisionGradeError(null);
    try {
      if (activeTab === "volume-rate") {
        const data = await client.getVolumeRateAttribution({
          reportDate: effectiveReportDate,
          compareType,
        });
        setVolumeRateData(data.result);
        setVolumeRateMeta(data.result_meta);
      } else if (activeTab === "tpl-market") {
        const data = await client.getTplMarketCorrelation({
          months: 12,
          reportDate: effectiveReportDate,
        });
        setTplMarketData(data.result);
        setTplMarketMeta(data.result_meta);
        const productCategoryDates = dateResolution?.productCategoryDates.length
          ? dateResolution.productCategoryDates
          : selectedProductCategoryReportDate
            ? [selectedProductCategoryReportDate]
            : [];
        const productCategoryTplPoints = await Promise.all(
          data.result.data_points.map(async (point): Promise<ProductCategoryTplMonthlyPoint> => {
            const productCategoryReportDate = findProductCategoryReportDateForPeriod(
              productCategoryDates,
              point.period,
            );
            if (!productCategoryReportDate) {
              return {
                period: point.period,
                reportDate: null,
                row: null,
              };
            }
            const monthly = await client.getProductCategoryPnl({
              reportDate: productCategoryReportDate,
              view: "monthly",
            });
            return {
              period: point.period,
              reportDate: monthly.result.report_date ?? productCategoryReportDate,
              row: selectProductCategoryTplRow(monthly.result),
            };
          }),
        );
        setTplProductCategoryMonthlyPoints(productCategoryTplPoints);
      } else if (activeTab === "composition") {
        const data = await client.getPnlCompositionBreakdown({
          reportDate: effectiveReportDate,
          includeTrend: true,
          trendMonths: 6,
        });
        setCompositionData(data.result);
        setCompositionMeta(data.result_meta);
      } else if (activeTab === "product-category") {
        const [monthly, ytd, attribution] = await Promise.all([
          client.getProductCategoryPnl({
            reportDate: effectiveReportDate,
            view: "monthly",
          }),
          client.getProductCategoryPnl({
            reportDate: effectiveReportDate,
            view: "ytd",
          }),
          client.getProductCategoryAttribution({
            reportDate: effectiveReportDate,
            compare: compareType,
          }),
        ]);
        setProductCategoryMonthlyData(monthly.result);
        setProductCategoryMonthlyMeta(monthly.result_meta);
        setProductCategoryYtdData(ytd.result);
        setProductCategoryYtdMeta(ytd.result_meta);
        setProductCategoryAttributionData(attribution.result);
        setProductCategoryAttributionMeta(attribution.result_meta);
      } else {
        const [
          carry,
          spread,
          krd,
          summary,
          campisi,
          campisiFour,
          campisiEnhancedData,
          campisiBuckets,
        ] = await Promise.all([
          client.getPnlCarryRollDown(effectiveReportDate),
          client.getPnlSpreadAttribution({
            reportDate: effectiveReportDate,
            lookbackDays: 30,
          }),
          client.getPnlKrdAttribution({
            reportDate: effectiveReportDate,
            lookbackDays: 30,
          }),
          client.getPnlAdvancedAttributionSummary(effectiveReportDate),
          client.getPnlCampisiAttribution({
            endDate: effectiveReportDate,
            lookbackDays: 30,
          }),
          client.getPnlCampisiFourEffects({
            endDate: effectiveReportDate,
            lookbackDays: 30,
          }),
          client.getPnlCampisiEnhanced({
            endDate: effectiveReportDate,
            lookbackDays: 30,
          }),
          client.getPnlCampisiMaturityBuckets({
            endDate: effectiveReportDate,
            lookbackDays: 30,
          }),
        ]);
        setCarryRollDownData(carry.result);
        setCarryMeta(carry.result_meta);
        setSpreadData(spread.result);
        setSpreadMeta(spread.result_meta);
        setKrdData(krd.result);
        setKrdMeta(krd.result_meta);
        setAdvancedSummary(summary.result);
        setAdvancedSummaryMeta(summary.result_meta);
        setCampisiData(campisi.result);
        setCampisiFourEffects(campisiFour.result);
        setCampisiFourMeta(campisiFour.result_meta);
        setCampisiEnhanced(campisiEnhancedData.result);
        setCampisiEnhancedMeta(campisiEnhancedData.result_meta);
        setCampisiMaturityBuckets(campisiBuckets.result);
        setCampisiMaturityMeta(campisiBuckets.result_meta);
        setCampisiDecisionGrade(null);
        setCampisiDecisionGradeMeta(null);
        try {
          const campisiDecision = await client.getPnlCampisiDecisionGrade({
            endDate: effectiveReportDate,
            lookbackDays: 30,
          });
          setCampisiDecisionGrade(campisiDecision.result);
          setCampisiDecisionGradeMeta(campisiDecision.result_meta);
        } catch (decisionError: unknown) {
          setCampisiDecisionGrade(null);
          setCampisiDecisionGradeMeta(null);
          setCampisiDecisionGradeError(
            decisionError instanceof Error
              ? decisionError.message
              : "Campisi 决策级解释加载失败",
          );
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "加载失败";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [
    activeTab,
    client,
    compareType,
    dateResolution,
    effectiveReportDate,
    selectedProductCategoryReportDate,
  ]);

  useEffect(() => {
    void loadDateOptions();
  }, [loadDateOptions]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const keyFindings =
    activeTab === "advanced"
      ? (advancedSummary?.key_insights ?? [])
      : [];
  const volumeRateBridgeSummary = buildVolumeRateBridgeSummary(volumeRateData);
  const currentViewMeta =
    activeTab === "volume-rate"
      ? volumeRateMeta
      : activeTab === "tpl-market"
        ? tplMarketMeta
        : activeTab === "composition"
          ? compositionMeta
          : activeTab === "product-category"
            ? (productCategoryAttributionMeta ??
              productCategoryMonthlyMeta ??
              productCategoryYtdMeta)
            : advancedSummaryMeta;
  const currentViewDate = formatMetaDateLabel(activeTab, {
    volumeRateData,
    tplMarketData,
    compositionData,
    advancedSummary,
    productCategoryAttributionData,
    productCategoryMonthlyData,
    productCategoryYtdData,
  });
  const currentViewMetaTitle = `${currentViewDate.label}：${currentViewDate.value}`;
  const advancedMetaRows: [string, ResultMeta | null][] =
    activeTab === "advanced"
      ? [
          ["Carry / Roll-down", carryMeta],
          ["利差归因", spreadMeta],
          ["KRD归因", krdMeta],
          ["高级摘要", advancedSummaryMeta],
          ["Campisi 四效应", campisiFourMeta],
          ["Campisi 六效应", campisiEnhancedMeta],
          ["Campisi 到期桶", campisiMaturityMeta],
          ["Campisi 决策级", campisiDecisionGradeMeta],
        ]
      : [];
  const advancedMetaSections = advancedMetaRows.map(([title, meta], index) => ({
    key: `advanced-${index}`,
    title,
    meta,
  }));
  const productCategoryMetaSections =
    activeTab === "product-category"
      ? [
          {
            key: "product-category-attribution",
            title: "产品分类月度归因",
            meta: productCategoryAttributionMeta,
          },
          {
            key: "product-category-monthly",
            title: "产品分类月度汇总",
            meta: productCategoryMonthlyMeta,
          },
          {
            key: "product-category-ytd",
            title: "产品分类 YTD 汇总",
            meta: productCategoryYtdMeta,
          },
        ]
      : [];

  const volumeRateState: DataSectionState = derivePnlDataSectionState({
    meta: volumeRateMeta,
    isLoading: loading && activeTab === "volume-rate",
    isError: error !== null && activeTab === "volume-rate",
    errorMessage: error,
    isEmpty: !volumeRateData || (volumeRateData.items?.length ?? 0) === 0,
  });

  const waterfallState: DataSectionState = derivePnlDataSectionState({
    meta: volumeRateMeta,
    isLoading: loading && activeTab === "volume-rate",
    isError: error !== null && activeTab === "volume-rate",
    errorMessage: error,
    isEmpty: false,
  });

  const tplMarketState: DataSectionState = derivePnlDataSectionState({
    meta: tplMarketMeta,
    isLoading: loading && activeTab === "tpl-market",
    isError: error !== null && activeTab === "tpl-market",
    errorMessage: error,
    isEmpty: !tplMarketData || (tplMarketData.data_points?.length ?? 0) === 0,
  });

  const compositionState: DataSectionState = derivePnlDataSectionState({
    meta: compositionMeta,
    isLoading: loading && activeTab === "composition",
    isError: error !== null && activeTab === "composition",
    errorMessage: error,
    isEmpty: !compositionData,
  });

  const productCategoryState: DataSectionState = derivePnlDataSectionState({
    meta:
      productCategoryAttributionMeta ??
      productCategoryMonthlyMeta ??
      productCategoryYtdMeta,
    isLoading: loading && activeTab === "product-category",
    isError: error !== null && activeTab === "product-category",
    errorMessage: error,
    isEmpty:
      !productCategoryMonthlyData &&
      !productCategoryYtdData &&
      !productCategoryAttributionData,
  });

  const advancedCarryState: DataSectionState = derivePnlDataSectionState({
    meta: carryMeta,
    isLoading: loading && activeTab === "advanced",
    isError: error !== null && activeTab === "advanced",
    errorMessage: error,
    isEmpty: !carryRollDownData || (carryRollDownData.items?.length ?? 0) === 0,
  });

  const campisiFourState: DataSectionState = derivePnlDataSectionState({
    meta: campisiFourMeta,
    isLoading: loading && activeTab === "advanced",
    isError: error !== null && activeTab === "advanced",
    errorMessage: error,
    isEmpty: !(campisiFourEffects ?? campisiData),
  });

  const campisiEnhancedState: DataSectionState = derivePnlDataSectionState({
    meta: campisiEnhancedMeta,
    isLoading: loading && activeTab === "advanced",
    isError: error !== null && activeTab === "advanced",
    errorMessage: error,
    isEmpty: !campisiEnhanced,
  });

  const campisiMaturityState: DataSectionState = derivePnlDataSectionState({
    meta: campisiMaturityMeta,
    isLoading: loading && activeTab === "advanced",
    isError: error !== null && activeTab === "advanced",
    errorMessage: error,
    isEmpty: !campisiMaturityBuckets,
  });

  const campisiDecisionGradeState: DataSectionState = derivePnlDataSectionState({
    meta: campisiDecisionGradeMeta,
    isLoading: loading && activeTab === "advanced",
    isError:
      (error !== null || campisiDecisionGradeError !== null) &&
      activeTab === "advanced",
    errorMessage: campisiDecisionGradeError ?? error,
    isEmpty: !campisiDecisionGrade,
  });

  return (
    <div className="pnl-attribution-shell">
      <div className="pnl-attribution-panel pnl-attribution-page-header">
        <div className="pnl-attribution-page-header__inner">
          <div className="pnl-attribution-page-header__copy">
            <h2
              data-testid="pnl-attribution-page-title"
              className="pnl-attribution-page-header__title"
            >
              损益归因分析
            </h2>
            <p className="pnl-attribution-page-header__description">
              本页保留产品分类经营口径与正式 FI / 债券分析口径；两套数据分开取数、
              分开元信息，不再跨口径汇总或闭合。
            </p>
          </div>
          <div className="pnl-attribution-page-header__actions">
            <span
              className="pnl-attribution-mode-badge"
              data-mode={client.mode}
            >
              {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
            </span>
            <button
              type="button"
              onClick={() => void loadData()}
              disabled={loading || dateLoading}
              className="pnl-attribution-tab-button"
            >
              {loading ? "刷新中…" : "刷新"}
            </button>
          </div>
        </div>

        {keyFindings.length > 0 && (
          <div
            className="pnl-attribution-findings"
            data-context={activeTab === "advanced" ? "advanced" : "default"}
          >
            <div className="pnl-attribution-findings__title">
              {activeTab === "advanced" ? "高级归因要点" : "关键发现"}
            </div>
            <ul className="pnl-attribution-findings__list">
              {keyFindings.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <PnlAttributionDecisionStrip
        activeTab={activeTab}
        compareType={compareType}
        currentViewDateTitle={currentViewMetaTitle}
        currentViewMeta={currentViewMeta}
        dateResolution={dateResolution}
        isLoading={loading || dateLoading}
        hasError={error !== null || dateError !== null}
      />

      <LensBoundaryPanel />

      <PnlAttributionSourceDateMessage
        resolution={dateResolution}
        dateError={dateError}
        isLoading={dateLoading}
      />

      <div className="pnl-attribution-panel pnl-attribution-panel--compact">
        <SectionLead
          eyebrow="工作台"
          title="双口径归因工作台"
          description="产品分类经营归因只读取 /ui/pnl/product-category；正式 FI / 债券分析主要读取 /api/pnl-attribution/*。TPL 市场页签是明确的 hybrid exception：/api/pnl-attribution/tpl-market 提供市场序列，/ui/pnl/product-category 提供 bond_tpl 月度行。"
          testId="pnl-attribution-workbench-lead"
        />
        <FilterBar className="pnl-attribution-tab-row">
          <button
            type="button"
            className={tabButtonClassName(activeTab === "volume-rate")}
            onClick={() => setActiveTab("volume-rate")}
          >
            规模 / 利率效应
          </button>
          <button
            type="button"
            className={tabButtonClassName(activeTab === "tpl-market")}
            onClick={() => setActiveTab("tpl-market")}
          >
            TPL 市场相关性
          </button>
          <button
            type="button"
            className={tabButtonClassName(activeTab === "composition")}
            onClick={() => setActiveTab("composition")}
          >
            损益构成
          </button>
          <button
            data-testid="pnl-attribution-tab-product-category"
            type="button"
            className={tabButtonClassName(activeTab === "product-category")}
            onClick={() => setActiveTab("product-category")}
          >
            产品分类归因
          </button>
          <button
            type="button"
            className={tabButtonClassName(activeTab === "advanced", "advanced")}
            onClick={() => setActiveTab("advanced")}
          >
            高级归因 + Campisi
          </button>
          {(activeTab === "volume-rate" ||
            activeTab === "product-category") && (
            <div className="pnl-attribution-tab-row__compare-group">
              <button
                type="button"
                className={tabButtonClassName(compareType === "mom")}
                onClick={() => setCompareType("mom")}
              >
                环比
              </button>
              <button
                type="button"
                className={tabButtonClassName(compareType === "yoy")}
                onClick={() => setCompareType("yoy")}
              >
                同比
              </button>
            </div>
          )}
        </FilterBar>
      </div>

      <SectionLead
        eyebrow="分析"
        title="当前归因视图"
        description="下方内容随页签切换；请按当前口径阅读来源、单位、报告日和质量提示。"
        testId="pnl-attribution-current-view-lead"
      />

      {activeTab === "volume-rate" &&
      volumeRateData &&
      volumeRateBridgeSummary &&
      !loading &&
      !error ? (
        <VolumeRateBridgePanel
          data={volumeRateData}
          summary={volumeRateBridgeSummary}
        />
      ) : null}

      {currentViewMeta ? (
        <CurrentViewMetaStrip
          testId="pnl-attribution-current-view-meta"
          title={currentViewMetaTitle}
          meta={currentViewMeta}
        />
      ) : null}

      {activeTab === "advanced" ? (
        <FormalResultMetaPanel
          testId="pnl-attribution-advanced-view-meta"
          title="高级归因结果元信息"
          emptyText={loading ? "加载中…" : "当前还没有可展示的高级归因元信息。"}
          sections={advancedMetaSections}
        />
      ) : null}

      {activeTab === "product-category" ? (
        <FormalResultMetaPanel
          testId="pnl-attribution-product-category-view-meta"
          title="产品分类来源元信息"
          emptyText={
            loading ? "加载中..." : "当前还没有可展示的产品分类来源元信息。"
          }
          sections={productCategoryMetaSections}
        />
      ) : null}

      {activeTab === "volume-rate" ? (
        <>
          <AttributionWaterfallChart
            data={volumeRateData}
            state={waterfallState}
            onRetry={() => void loadData()}
          />
          <VolumeRateAnalysisChart
            data={volumeRateData}
            state={volumeRateState}
            onRetry={() => void loadData()}
          />
        </>
      ) : null}

      {activeTab === "tpl-market" ? (
        <TPLMarketChart
          data={tplMarketData}
          state={tplMarketState}
          onRetry={() => void loadData()}
          productCategoryTplMonthlyPoints={tplProductCategoryMonthlyPoints}
        />
      ) : null}

      {activeTab === "composition" ? (
        <PnLCompositionChart
          data={compositionData}
          state={compositionState}
          onRetry={() => void loadData()}
        />
      ) : null}

      {activeTab === "product-category" ? (
        <ProductCategoryAttributionWorkbench
          monthlyData={productCategoryMonthlyData}
          ytdData={productCategoryYtdData}
          attributionData={productCategoryAttributionData}
          isLoading={productCategoryState.kind === "loading"}
          error={
            productCategoryState.kind === "error"
              ? (productCategoryState.message ?? "加载失败")
              : null
          }
          onRetry={() => void loadData()}
        />
      ) : null}

      {activeTab === "advanced" ? (
        <>
          <CampisiDecisionGradePanel
            data={campisiDecisionGrade}
            state={campisiDecisionGradeState}
            onRetry={() => void loadData()}
          />
          <CampisiAttributionPanel
            data={campisiFourEffects ?? campisiData}
            state={campisiFourState}
            onRetry={() => void loadData()}
          />
          <CampisiEnhancedPanel
            data={campisiEnhanced}
            state={campisiEnhancedState}
            onRetry={() => void loadData()}
          />
          <CampisiMaturityBucketPanel
            data={campisiMaturityBuckets}
            state={campisiMaturityState}
            onRetry={() => void loadData()}
          />
          <AdvancedAttributionChart
            carryData={carryRollDownData}
            spreadData={spreadData}
            krdData={krdData}
            summaryData={advancedSummary}
            state={advancedCarryState}
            onRetry={() => void loadData()}
          />
        </>
      ) : null}
    </div>
  );
}
