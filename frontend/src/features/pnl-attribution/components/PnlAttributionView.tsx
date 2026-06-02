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
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
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
  formatProductCategoryValue,
  formatProductCategoryYieldValue,
} from "../../product-category-pnl/pages/productCategoryPnlPageModel";

const shellStyle = {
  display: "flex",
  flexDirection: "column" as const,
  gap: designTokens.space[5],
};

const pageSurfaceColor = "#ffffff";
const pageSubtleSurfaceColor = "#fafafa";
const pageBorderColor = "#ded6ca";
const pageBorderSoftColor = "#ece6dd";
const pageTextColor = designTokens.color.warm.ink;
const pageMutedTextColor = "#665f58";

const headerCardStyle = {
  padding: designTokens.space[5],
  borderRadius: designTokens.radius.sm,
  border: `1px solid ${pageBorderColor}`,
  background: pageSurfaceColor,
  boxShadow: "0 1px 2px rgba(31, 41, 55, 0.04)",
} as const;

const modeBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
  borderRadius: 999,
  fontSize: designTokens.fontSize[12],
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
} as const;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: designTokens.space[2],
} as const;

const sectionEyebrowStyle = {
  fontSize: designTokens.fontSize[11],
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: pageMutedTextColor,
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: designTokens.fontSize[18],
  fontWeight: 600,
  color: pageTextColor,
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 900,
  color: pageMutedTextColor,
  fontSize: designTokens.fontSize[13],
  lineHeight: designTokens.lineHeight.relaxed,
} as const;

const tabBarStyle = {
  display: "flex",
  flexWrap: "wrap" as const,
  gap: designTokens.space[2],
  alignItems: "center",
};

function tabStyle(
  active: boolean,
  variant: "default" | "advanced" = "default",
) {
  const base = {
    padding: `${designTokens.space[3]}px ${designTokens.space[4]}px`,
    borderRadius: designTokens.radius.sm,
    fontWeight: 600,
    fontSize: designTokens.fontSize[14],
    cursor: "pointer",
    border: "1px solid",
    boxShadow: active ? "0 1px 2px rgba(31, 41, 55, 0.08)" : "none",
  } as const;
  if (variant === "advanced") {
    return {
      ...base,
      borderColor: active ? pageTextColor : pageBorderColor,
      background: active ? pageTextColor : pageSurfaceColor,
      color: active ? pageSurfaceColor : pageTextColor,
    };
  }
  return {
    ...base,
    borderColor: active ? pageTextColor : pageBorderColor,
    background: active ? pageTextColor : pageSurfaceColor,
    color: active ? pageSurfaceColor : pageTextColor,
  };
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
    <div data-testid={props.testId} style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
  );
}

function LensBoundaryPanel() {
  const lensCardStyle = {
    ...headerCardStyle,
    padding: designTokens.space[4],
    display: "grid",
    gap: designTokens.space[2],
  } as const;
  const lensSourceStyle = {
    fontSize: designTokens.fontSize[12],
    color: pageMutedTextColor,
    ...tabularNumsStyle,
  } as const;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
        gap: designTokens.space[4],
      }}
    >
      <section
        data-testid="pnl-attribution-product-category-lens-card"
        style={lensCardStyle}
      >
        <SectionLead
          eyebrow="产品分类经营口径"
          title="经营净收入归因"
          description="经营净收入、FTP 后；来源为产品分类正式读模型，只消费产品分类 monthly / YTD / attribution 接口。"
        />
        <div style={lensSourceStyle}>
          Source: /ui/pnl/product-category, /ui/pnl/product-category/attribution
        </div>
      </section>
      <section
        data-testid="pnl-attribution-formal-lens-card"
        style={lensCardStyle}
      >
        <SectionLead
          eyebrow="正式 FI / 债券分析口径"
          title="会计损益与债券市场归因"
          description="含非标桥接、未扣 FTP、非产品分类经营净收入；仅用于正式 FI、TPL 市场和债券分析归因。"
        />
        <div style={lensSourceStyle}>Source: /api/pnl-attribution/*</div>
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

function valueTone(
  value: number | undefined,
  fallback = designTokens.color.neutral[900],
) {
  if (value === undefined) {
    return fallback;
  }
  return value >= 0
    ? designTokens.color.semantic.profit
    : designTokens.color.semantic.loss;
}

function VolumeRateBridgePanel(props: {
  data: VolumeRateAttributionPayload;
  summary: VolumeRateBridgeSummary;
}) {
  const { data, summary } = props;
  const residualIsMaterial =
    summary.unexplainedEffect !== undefined &&
    Math.abs(summary.unexplainedEffect) > 10_000;
  const statusSurface =
    summary.status === "closed"
      ? {
          background: designTokens.color.success[50],
          borderColor: designTokens.color.success[200],
          color: designTokens.color.success[700],
        }
      : summary.status === "residual"
        ? {
            background: designTokens.color.warning[50],
            borderColor: designTokens.color.warning[200],
            color: designTokens.color.warning[700],
          }
        : {
            background: designTokens.color.neutral[50],
            borderColor: designTokens.color.neutral[200],
            color: designTokens.color.neutral[700],
          };
  const denominator =
    summary.pnlChange !== undefined && Math.abs(summary.pnlChange) > 10_000
      ? summary.pnlChange
      : undefined;
  const bridgeRows = [
    {
      label: "规模效应",
      formula: "Δ规模 × 上期收益率",
      value: summary.volumeEffect,
      accent: designTokens.color.success[600],
    },
    {
      label: "利率效应",
      formula: "上期规模 × Δ收益率",
      value: summary.rateEffect,
      accent: designTokens.color.warm.slateBlue,
    },
    {
      label: "交叉效应",
      formula: "Δ规模 × Δ收益率",
      value: summary.interactionEffect,
      accent: designTokens.color.neutral[600],
    },
    {
      label: "未解释差额",
      formula: residualIsMaterial ? "缺规模或未匹配分类" : "闭合容差内",
      value: summary.unexplainedEffect,
      accent: residualIsMaterial
        ? designTokens.color.warning[600]
        : designTokens.color.neutral[500],
      isResidual: true,
    },
  ];

  return (
    <div
      data-testid="volume-rate-bridge-panel"
      style={{
        borderRadius: designTokens.radius.sm,
        border: `1px solid ${pageBorderColor}`,
        background: pageSurfaceColor,
        boxShadow: "0 1px 2px rgba(31, 41, 55, 0.04)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "minmax(min(100%, 260px), 0.76fr) minmax(min(100%, 520px), 1.24fr)",
          gap: 0,
          padding: designTokens.space[5],
        }}
      >
        <div
          style={{
            display: "grid",
            alignContent: "space-between",
            gap: designTokens.space[4],
            paddingRight: designTokens.space[5],
            borderRight: `1px solid ${pageBorderSoftColor}`,
          }}
        >
          <div>
            <div style={sectionEyebrowStyle}>规模 / 利率效应</div>
            <h3
              style={{
                margin: `${designTokens.space[2]}px 0 0`,
                fontSize: designTokens.fontSize[20],
                color: pageTextColor,
              }}
            >
              损益变动桥
            </h3>
            <div
              style={{
                marginTop: designTokens.space[3],
                fontSize: designTokens.fontSize[30],
                fontWeight: 800,
                color: valueTone(summary.pnlChange),
                ...tabularNumsStyle,
              }}
            >
              {formatYi(summary.pnlChange)}
            </div>
            <div
              style={{
                display: "flex",
                gap: designTokens.space[2],
                flexWrap: "wrap",
                marginTop: designTokens.space[3],
                fontSize: designTokens.fontSize[12],
                color: pageMutedTextColor,
              }}
            >
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
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: designTokens.space[3],
              padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
              borderRadius: designTokens.radius.sm,
              border: `1px solid ${statusSurface.borderColor}`,
              background: statusSurface.background,
              color: statusSurface.color,
              fontSize: designTokens.fontSize[12],
              fontWeight: 700,
            }}
          >
            <span>{summary.statusLabel}</span>
            <span style={tabularNumsStyle}>
              解释覆盖 {formatPct(summary.coveragePct)}
            </span>
          </div>
        </div>

        <div style={{ minWidth: 0, paddingLeft: designTokens.space[5] }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: designTokens.space[3],
              alignItems: "baseline",
              marginBottom: designTokens.space[3],
            }}
          >
            <div
              style={{
                color: pageTextColor,
                fontSize: designTokens.fontSize[14],
                fontWeight: 700,
              }}
            >
              变动拆分
            </div>
            <div
              style={{
                color: pageMutedTextColor,
                fontSize: designTokens.fontSize[12],
              }}
            >
              单位：亿元
            </div>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                minWidth: 520,
                borderCollapse: "collapse",
                fontSize: designTokens.fontSize[12],
              }}
            >
              <thead>
                <tr
                  style={{ borderBottom: `1px solid ${pageBorderSoftColor}` }}
                >
                  <th
                    style={{
                      padding: `${designTokens.space[2]}px 0`,
                      textAlign: "left",
                      color: pageMutedTextColor,
                    }}
                  >
                    项目
                  </th>
                  <th
                    style={{
                      padding: `${designTokens.space[2]}px`,
                      textAlign: "left",
                      color: pageMutedTextColor,
                    }}
                  >
                    计算口径
                  </th>
                  <th
                    style={{
                      padding: `${designTokens.space[2]}px`,
                      textAlign: "right",
                      color: pageMutedTextColor,
                    }}
                  >
                    金额
                  </th>
                  <th
                    style={{
                      padding: `${designTokens.space[2]}px 0`,
                      textAlign: "right",
                      color: pageMutedTextColor,
                    }}
                  >
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
                      style={{
                        borderBottom: `1px solid ${pageBorderSoftColor}`,
                        background:
                          row.isResidual && residualIsMaterial
                            ? "rgba(255, 249, 235, 0.62)"
                            : "transparent",
                      }}
                    >
                      <td
                        style={{
                          padding: `${designTokens.space[3]}px 0`,
                          color: pageTextColor,
                          fontWeight: 700,
                        }}
                      >
                        <span
                          style={{
                            display: "inline-block",
                            width: 7,
                            height: 7,
                            borderRadius: 999,
                            background: row.accent,
                            marginRight: designTokens.space[2],
                            verticalAlign: "middle",
                          }}
                        />
                        {row.label}
                      </td>
                      <td
                        style={{
                          padding: `${designTokens.space[3]}px ${designTokens.space[2]}px`,
                          color: pageMutedTextColor,
                        }}
                      >
                        {row.formula}
                      </td>
                      <td
                        style={{
                          padding: `${designTokens.space[3]}px ${designTokens.space[2]}px`,
                          textAlign: "right",
                          color: valueTone(row.value),
                          fontWeight: 800,
                          ...tabularNumsStyle,
                        }}
                      >
                        {formatYi(row.value)}
                      </td>
                      <td
                        style={{
                          padding: `${designTokens.space[3]}px 0`,
                          textAlign: "right",
                          color: pageMutedTextColor,
                          ...tabularNumsStyle,
                        }}
                      >
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

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: designTokens.space[3],
          flexWrap: "wrap",
          padding: `${designTokens.space[3]}px ${designTokens.space[5]}px`,
          borderTop: `1px solid ${pageBorderSoftColor}`,
          background: pageSubtleSurfaceColor,
          color: pageMutedTextColor,
          fontSize: designTokens.fontSize[12],
        }}
      >
        <span>损益变动 = 当期损益 - 上期损益</span>
        <span style={tabularNumsStyle}>
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

const compactTableStyle = {
  width: "100%",
  borderCollapse: "collapse" as const,
  fontSize: designTokens.fontSize[12],
};

const compactCellStyle = {
  padding: `${designTokens.space[3]}px ${designTokens.space[2]}px`,
  borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
  verticalAlign: "middle" as const,
};

function PnlAttributionSourceDateMessage(props: {
  resolution: DualReportDateResolution | null;
  dateError: string | null;
  isLoading: boolean;
}) {
  if (props.isLoading) {
    return (
      <div
        data-testid="pnl-attribution-date-loading"
        style={{ ...headerCardStyle, padding: designTokens.space[4] }}
      >
        正在加载产品分类与正式 FI 报告日...
      </div>
    );
  }
  if (props.dateError) {
    return (
      <div
        data-testid="pnl-attribution-date-error"
        style={{ ...headerCardStyle, padding: designTokens.space[4] }}
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
        style={{ ...headerCardStyle, padding: designTokens.space[4] }}
      >
        {source}来源当前无可用报告日；另一套口径仍可独立查看，不再强制共同日期。
      </div>
    );
  }
  if (!props.resolution.datesAligned) {
    return (
      <div
        data-testid="pnl-attribution-date-mismatch"
        style={{ ...headerCardStyle, padding: designTokens.space[4] }}
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
    <div style={{ ...headerCardStyle, padding: designTokens.space[4] }}>
      <div
        style={{
          fontSize: designTokens.fontSize[12],
          color: designTokens.color.neutral[700],
        }}
      >
        {props.label}
      </div>
      <div
        style={{
          fontSize: designTokens.fontSize[20],
          fontWeight: 700,
          color: pageTextColor,
          ...tabularNumsStyle,
        }}
      >
        {props.value}
      </div>
      <div
        style={{
          fontSize: designTokens.fontSize[12],
          color: designTokens.color.neutral[500],
        }}
      >
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
      <div style={{ color: designTokens.color.neutral[600] }}>
        产品分类月度归因暂无可展示行。
      </div>
    );
  }
  return (
    <div style={{ overflowX: "auto" }}>
      <table
        data-testid="pnl-attribution-product-category-attribution-table"
        style={compactTableStyle}
      >
        <thead>
          <tr>
            <th style={{ ...compactCellStyle, textAlign: "left" }}>产品分类</th>
            <th style={{ ...compactCellStyle, textAlign: "right" }}>变动</th>
            {productCategoryEffectColumns.map(([, label]) => (
              <th
                key={label}
                style={{ ...compactCellStyle, textAlign: "right" }}
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
                style={{
                  ...compactCellStyle,
                  fontWeight: row.level === 0 ? 700 : 500,
                }}
              >
                {row.category_name}
              </td>
              <td
                style={{
                  ...compactCellStyle,
                  textAlign: "right",
                  ...tabularNumsStyle,
                }}
              >
                {formatProductCategoryAttributionEffect(
                  row.effects.delta_business_net_income,
                )}
              </td>
              {productCategoryEffectColumns.map(([key]) => (
                <td
                  key={key}
                  style={{
                    ...compactCellStyle,
                    textAlign: "right",
                    ...tabularNumsStyle,
                  }}
                >
                  {formatProductCategoryAttributionEffect(row.effects[key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProductCategoryYtdTable(props: { rows: ProductCategoryPnlRow[] }) {
  if (props.rows.length === 0) {
    return (
      <div style={{ color: designTokens.color.neutral[600] }}>
        产品分类 YTD 汇总暂无可展示行。
      </div>
    );
  }
  return (
    <div style={{ overflowX: "auto" }}>
      <table
        data-testid="pnl-attribution-product-category-ytd-table"
        style={compactTableStyle}
      >
        <thead>
          <tr>
            <th style={{ ...compactCellStyle, textAlign: "left" }}>产品分类</th>
            <th style={{ ...compactCellStyle, textAlign: "right" }}>规模</th>
            <th style={{ ...compactCellStyle, textAlign: "right" }}>净营收</th>
            <th style={{ ...compactCellStyle, textAlign: "right" }}>收益率</th>
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={row.category_id}>
              <td
                style={{
                  ...compactCellStyle,
                  fontWeight: row.is_total ? 700 : 500,
                }}
              >
                {row.category_name}
              </td>
              <td
                style={{
                  ...compactCellStyle,
                  textAlign: "right",
                  ...tabularNumsStyle,
                }}
              >
                {formatProductCategoryRowDisplayValue(row, row.cnx_scale)}
              </td>
              <td
                style={{
                  ...compactCellStyle,
                  textAlign: "right",
                  ...tabularNumsStyle,
                }}
              >
                {formatProductCategoryRowDisplayValue(
                  row,
                  row.business_net_income,
                )}
              </td>
              <td
                style={{
                  ...compactCellStyle,
                  textAlign: "right",
                  ...tabularNumsStyle,
                }}
              >
                {formatProductCategoryYieldValue(row.weighted_yield)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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
        style={{ ...headerCardStyle, padding: designTokens.space[4] }}
      >
        产品分类归因加载中...
      </div>
    );
  }
  if (props.error) {
    return (
      <div
        data-testid="pnl-attribution-product-category-tab"
        style={{ ...headerCardStyle, padding: designTokens.space[4] }}
      >
        产品分类来源加载失败：{props.error}
        <button
          type="button"
          onClick={props.onRetry}
          style={{ ...tabStyle(false), marginLeft: designTokens.space[3] }}
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
        style={{ ...headerCardStyle, padding: designTokens.space[4] }}
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
      style={{ display: "grid", gap: designTokens.space[4] }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: designTokens.space[3],
        }}
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
      <div style={{ ...headerCardStyle, padding: designTokens.space[4] }}>
        <SectionLead
          eyebrow="产品分类归因"
          title="月度经营差异拆分"
          description="直接复用产品分类已开放的 monthly attribution，不把 YTD 汇总硬套到规模/利率公式。"
        />
        <div style={{ marginTop: designTokens.space[3] }}>
          <ProductCategoryAttributionTable rows={attributionRows} />
        </div>
      </div>

      <div style={{ ...headerCardStyle, padding: designTokens.space[4] }}>
        <SectionLead
          eyebrow="产品分类 YTD"
          title="累计汇总对照"
          description="YTD 只作为产品分类汇总对照，保持产品分类页已计算好的口径。"
        />
        <div style={{ marginTop: designTokens.space[3] }}>
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
      borderColor: designTokens.color.warning[200],
      background: designTokens.color.warning[50],
      color: designTokens.color.warning[700],
    };
  }
  if (value === "error" || value === "missing") {
    return {
      label: value === "missing" ? "缺失" : "错误",
      borderColor: designTokens.color.danger[200],
      background: designTokens.color.danger[50],
      color: designTokens.color.danger[700],
    };
  }
  if (value === "stale") {
    return {
      label: "陈旧",
      borderColor: designTokens.color.warning[200],
      background: designTokens.color.warning[50],
      color: designTokens.color.warning[700],
    };
  }
  return {
    label: "正常",
    borderColor: designTokens.color.success[200],
    background: designTokens.color.success[50],
    color: designTokens.color.success[700],
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
      style={{
        display: "grid",
        gap: designTokens.space[3],
        padding: `${designTokens.space[3]}px ${designTokens.space[4]}px`,
        borderRadius: designTokens.radius.sm,
        border: `1px solid ${pageBorderColor}`,
        background: pageSurfaceColor,
        boxShadow: "0 1px 2px rgba(31, 41, 55, 0.04)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: designTokens.space[3],
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "grid", gap: designTokens.space[1] }}>
          <span
            style={{
              fontSize: designTokens.fontSize[11],
              fontWeight: 700,
              color: pageMutedTextColor,
            }}
          >
            当前视图结果元信息
          </span>
          <strong
            style={{
              color: pageTextColor,
              fontSize: designTokens.fontSize[14],
            }}
          >
            {props.title}
          </strong>
        </div>
        <div
          style={{
            display: "flex",
            gap: designTokens.space[2],
            flexWrap: "wrap",
          }}
        >
          <span
            style={{
              ...modeBadgeStyle,
              letterSpacing: 0,
              textTransform: "none",
              border: `1px solid ${quality.borderColor}`,
              background: quality.background,
              color: quality.color,
            }}
          >
            {quality.label}
          </span>
          <span
            style={{
              ...modeBadgeStyle,
              letterSpacing: 0,
              textTransform: "none",
              border: `1px solid ${pageBorderSoftColor}`,
              background: pageSubtleSurfaceColor,
              color: pageMutedTextColor,
            }}
          >
            {fallback}
          </span>
        </div>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: `${designTokens.space[2]}px ${designTokens.space[4]}px`,
          paddingTop: designTokens.space[3],
          borderTop: `1px solid ${pageBorderSoftColor}`,
          fontSize: designTokens.fontSize[12],
        }}
      >
        {fields.map(([label, value]) => (
          <div
            key={label}
            style={{ display: "grid", gap: designTokens.space[1], minWidth: 0 }}
          >
            <span style={{ color: pageMutedTextColor }}>{label}</span>
            <span
              title={value}
              style={{
                color: pageTextColor,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                ...tabularNumsStyle,
              }}
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
    <div style={shellStyle}>
      <div style={headerCardStyle}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: designTokens.space[4],
            flexWrap: "wrap",
          }}
        >
          <div>
            <h2
              data-testid="pnl-attribution-page-title"
              style={{
                margin: 0,
                fontSize: designTokens.fontSize[20],
                fontWeight: 700,
                color: pageTextColor,
              }}
            >
              损益归因分析
            </h2>
            <p
              style={{
                margin: `${designTokens.space[2]}px 0 0`,
                fontSize: designTokens.fontSize[13],
                color: pageMutedTextColor,
                maxWidth: 640,
                lineHeight: designTokens.lineHeight.normal,
              }}
            >
              本页保留产品分类经营口径与正式 FI / 债券分析口径；两套数据分开取数、
              分开元信息，不再跨口径汇总或闭合。
            </p>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: designTokens.space[3],
              flexWrap: "wrap",
            }}
          >
            <span
              style={{
                ...modeBadgeStyle,
                background:
                  client.mode === "real"
                    ? designTokens.color.success[50]
                    : pageSubtleSurfaceColor,
                color:
                  client.mode === "real"
                    ? designTokens.color.success[600]
                    : pageMutedTextColor,
                border: `1px solid ${client.mode === "real" ? designTokens.color.success[200] : pageBorderSoftColor}`,
              }}
            >
              {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
            </span>
            <button
              type="button"
              onClick={() => void loadData()}
              disabled={loading || dateLoading}
              style={{
                ...tabStyle(false),
                alignSelf: "flex-start",
                opacity: loading || dateLoading ? 0.6 : 1,
              }}
            >
              {loading ? "刷新中…" : "刷新"}
            </button>
          </div>
        </div>

        {keyFindings.length > 0 && (
          <div
            style={{
              marginTop: designTokens.space[4],
              padding: designTokens.space[4],
              borderRadius: designTokens.radius.md,
              border: "1px solid",
              borderColor:
                activeTab === "advanced"
                  ? pageBorderColor
                  : designTokens.color.warning[200],
              background:
                activeTab === "advanced"
                  ? pageSubtleSurfaceColor
                  : designTokens.color.warning[50],
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: designTokens.fontSize[13],
                marginBottom: designTokens.space[2],
                color: pageTextColor,
              }}
            >
              {activeTab === "advanced" ? "高级归因要点" : "关键发现"}
            </div>
            <ul
              style={{
                margin: 0,
                paddingLeft: designTokens.space[6],
                color: pageMutedTextColor,
                fontSize: designTokens.fontSize[13],
                lineHeight: designTokens.lineHeight.normal,
              }}
            >
              {keyFindings.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <LensBoundaryPanel />

      <PnlAttributionSourceDateMessage
        resolution={dateResolution}
        dateError={dateError}
        isLoading={dateLoading}
      />

      <div style={{ ...headerCardStyle, padding: designTokens.space[4] }}>
        <SectionLead
          eyebrow="工作台"
          title="双口径归因工作台"
          description="产品分类经营归因只读取产品分类接口；正式 FI / 债券分析页签只读取 /api/pnl-attribution/*，不互相解释。"
          testId="pnl-attribution-workbench-lead"
        />
        <FilterBar style={{ ...tabBarStyle, marginTop: designTokens.space[4] }}>
          <button
            type="button"
            style={tabStyle(activeTab === "volume-rate")}
            onClick={() => setActiveTab("volume-rate")}
          >
            规模 / 利率效应
          </button>
          <button
            type="button"
            style={tabStyle(activeTab === "tpl-market")}
            onClick={() => setActiveTab("tpl-market")}
          >
            TPL 市场相关性
          </button>
          <button
            type="button"
            style={tabStyle(activeTab === "composition")}
            onClick={() => setActiveTab("composition")}
          >
            损益构成
          </button>
          <button
            data-testid="pnl-attribution-tab-product-category"
            type="button"
            style={tabStyle(activeTab === "product-category")}
            onClick={() => setActiveTab("product-category")}
          >
            产品分类归因
          </button>
          <button
            type="button"
            style={tabStyle(activeTab === "advanced", "advanced")}
            onClick={() => setActiveTab("advanced")}
          >
            高级归因 + Campisi
          </button>
          {(activeTab === "volume-rate" ||
            activeTab === "product-category") && (
            <div
              style={{
                marginLeft: "auto",
                display: "flex",
                gap: designTokens.space[2],
              }}
            >
              <button
                type="button"
                style={tabStyle(compareType === "mom")}
                onClick={() => setCompareType("mom")}
              >
                环比
              </button>
              <button
                type="button"
                style={tabStyle(compareType === "yoy")}
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
