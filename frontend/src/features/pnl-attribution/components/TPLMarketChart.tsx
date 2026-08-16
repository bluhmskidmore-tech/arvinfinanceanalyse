import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type {
  DecimalLike,
  Numeric,
  ProductCategoryPnlRow,
  TPLMarketCorrelationPayload,
} from "../../../api/contracts";
import { PageDataSection } from "../../../components/page/PageDataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { designTokens, nocturneTokens } from "../../../theme/designSystem";
import { formatProductCategoryRowDisplayValue } from "../../product-category-pnl/pages/productCategoryPnlPageModel";
import { numericRaw as sharedNumericRaw } from "../../../pageModel";
import { TONE_DH_CSS_VAR } from "../../../utils/tone";
import { EM_DASH } from "../../../utils/format";
import { formatYi } from "./pnlAttributionViewModel";
import "./TPLMarketChart.css";

// 暗色路由（theme-dh-api，Nocturne 色板）着色一律走主题感知入口：文字色用
// TONE_DH_CSS_VAR / --dh-api-* CSS 变量，背景用 --dh-api-panel-2，禁止浅色
// semantic/50 系直灌。
const CORR_CARD_BG = "var(--dh-api-panel-2)";

function correlationLabel(corr: number | null): {
  level: string;
  color: string;
  bg: string;
} {
  if (corr === null) {
    return {
      level: "无数据",
      color: TONE_DH_CSS_VAR.neutral,
      bg: CORR_CARD_BG,
    };
  }
  const a = Math.abs(corr);
  if (a >= 0.7) {
    return corr < 0
      ? {
          level: "强相关",
          color: TONE_DH_CSS_VAR.positive,
          bg: CORR_CARD_BG,
        }
      : {
          level: "强相关",
          color: TONE_DH_CSS_VAR.negative,
          bg: CORR_CARD_BG,
        };
  }
  if (a >= 0.4) {
    return {
      level: "中等相关",
      color: "var(--dh-api-blue)",
      bg: CORR_CARD_BG,
    };
  }
  if (a >= 0.2) {
    return {
      level: "弱相关",
      color: TONE_DH_CSS_VAR.warning,
      bg: CORR_CARD_BG,
    };
  }
  return {
    level: "无显著相关",
    color: TONE_DH_CSS_VAR.neutral,
    bg: CORR_CARD_BG,
  };
}

type Props = {
  data: TPLMarketCorrelationPayload | null;
  state: DataSectionState;
  onRetry: () => void;
  productCategoryTplMonthlyPoints?: ProductCategoryTplMonthlyPoint[];
};

export type ProductCategoryTplMonthlyPoint = {
  period: string;
  reportDate: string | null;
  row: ProductCategoryPnlRow | null;
};

function numericRaw(value: Numeric | number | null | undefined): number | null {
  if (typeof value === "number") {
    return value;
  }
  if (value && typeof value === "object") {
    return sharedNumericRaw(value);
  }
  return null;
}

function decimalLikeRaw(value: DecimalLike | null | undefined): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function productCategoryYi(
  row: Pick<ProductCategoryPnlRow, "side"> | null,
  value: DecimalLike | null | undefined,
): string {
  if (!row) {
    return EM_DASH;
  }
  const display = formatProductCategoryRowDisplayValue(row, value);
  return display === "-" ? EM_DASH : display;
}

function valueDirection(
  value: DecimalLike | null | undefined,
): "positive" | "negative" | "neutral" {
  const raw = decimalLikeRaw(value);
  if (raw === null) {
    return "neutral";
  }
  return raw >= 0 ? "positive" : "negative";
}

function signedDirection(
  raw: number | null | undefined,
): "positive" | "negative" | "neutral" {
  if (raw === null || raw === undefined) {
    return "neutral";
  }
  return raw >= 0 ? "positive" : "negative";
}

/** Rate-down is favorable (profit tone) for bond context. */
function rateMoveDirection(
  raw: number | null | undefined,
): "positive" | "negative" | "neutral" {
  if (raw === null || raw === undefined) {
    return "neutral";
  }
  return raw <= 0 ? "positive" : "negative";
}

/** Legacy payloads may expose BP total under `treasury_10y_total_change`. */
function treasuryTotalChangeBp(
  data: TPLMarketCorrelationPayload,
): number | null {
  const current = numericRaw(data.treasury_10y_total_change_bp);
  if (current !== null) {
    return current;
  }
  const legacy = (
    data as TPLMarketCorrelationPayload & {
      treasury_10y_total_change?: Numeric | number | null;
    }
  ).treasury_10y_total_change;
  return numericRaw(legacy);
}

/** TPL 公允价值变动与国债收益率走势的双轴对比。 */
export function TPLMarketChart({
  data,
  state,
  onRetry,
  productCategoryTplMonthlyPoints = [],
}: Props) {
  const chartOption = useMemo<EChartsOption | null>(() => {
    if (!data?.data_points?.length) {
      return null;
    }
    const periods = data.data_points.map((p) =>
      p.period_label.replace("年", "-").replace("月", ""),
    );
    // 缺失公允价值变动传 null，ECharts 留空不画 0 值柱。
    const tpl = data.data_points.map((p) => {
      const raw = numericRaw(p.tpl_fair_value_change);
      return raw === null ? null : raw / 100_000_000;
    });
    const bp = data.data_points.map((p) => p.treasury_10y_change?.raw ?? null);
    // ECharts canvas 读不到 CSS 变量，按 tone.ts 指南使用 Nocturne TS 镜像 token。
    return {
      tooltip: { trigger: "axis" },
      legend: {
        bottom: 0,
        textStyle: {
          fontSize: designTokens.fontSize[12],
          color: nocturneTokens.color.inkSoft,
        },
      },
      grid: { left: 56, right: 56, top: 28, bottom: 52 },
      xAxis: {
        type: "category",
        data: periods,
        axisLabel: {
          fontSize: designTokens.fontSize[11],
          color: nocturneTokens.color.inkSoft,
        },
      },
      yAxis: [
        {
          type: "value",
          name: "FVTPL(亿)",
          axisLabel: {
            formatter: (v: number) => `${v.toFixed(1)}`,
            color: nocturneTokens.color.inkSoft,
          },
          splitLine: {
            lineStyle: {
              type: "dashed",
              color: nocturneTokens.color.lineSoft,
            },
          },
        },
        {
          type: "value",
          name: "BP",
          axisLabel: {
            formatter: (v: number) => `${v}`,
            color: nocturneTokens.color.inkSoft,
          },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "FVTPL公允价值变动",
          type: "bar",
          yAxisIndex: 0,
          data: tpl,
          itemStyle: {
            color: nocturneTokens.color.blue,
            borderRadius: [
              designTokens.radius.sm,
              designTokens.radius.sm,
              0,
              0,
            ],
          },
        },
        {
          name: "国债收益率变动",
          type: "line",
          yAxisIndex: 1,
          data: bp,
          smooth: false,
          symbolSize: 8,
          lineStyle: { color: nocturneTokens.color.red, width: 2 },
        },
      ],
    };
  }, [data]);

  const corr = correlationLabel(data?.correlation_coefficient?.raw ?? null);
  const treasuryBpTotal = data ? treasuryTotalChangeBp(data) : null;
  const productCategoryTplByPeriod = useMemo(() => {
    const byPeriod = new Map<string, ProductCategoryTplMonthlyPoint>();
    productCategoryTplMonthlyPoints.forEach((point) => {
      byPeriod.set(point.period, point);
    });
    return byPeriod;
  }, [productCategoryTplMonthlyPoints]);
  const hasMissingProductCategoryTpl =
    data?.data_points?.some(
      (point) => !productCategoryTplByPeriod.get(point.period)?.row,
    ) ?? false;
  const hasMissingMarketData =
    data?.data_points?.some(
      (point) =>
        point.treasury_10y?.raw == null ||
        point.treasury_10y_change?.raw == null ||
        point.dr007?.raw == null,
    ) ?? false;

  return (
    <PageDataSection title="FVTPL 公允价值变动 vs 10Y" state={state} onRetry={onRetry}>
      {data ? (
        <div className="tpl-market-chart">
          <div className="tpl-market-chart__metric-grid">
            <div
              className="tpl-market-chart__card tpl-market-chart__card--compact"
              style={{ background: corr.bg }}
            >
              <div className="tpl-market-chart__label">相关系数</div>
              <div className="tpl-market-chart__value" style={{ color: corr.color }}>
                {data.correlation_coefficient?.raw != null
                  ? data.correlation_coefficient.raw.toFixed(3)
                  : EM_DASH}
              </div>
              <div className="tpl-market-chart__meta" style={{ color: corr.color }}>
                {corr.level}
              </div>
            </div>
            <div className="tpl-market-chart__card tpl-market-chart__card--compact">
              <div className="tpl-market-chart__label">累计 FVTPL 公允价值变动</div>
              <div
                className="tpl-market-chart__value tpl-market-chart__value--medium"
                data-direction={signedDirection(data.total_tpl_fv_change.raw)}
              >
                {formatYi(data.total_tpl_fv_change.raw ?? undefined)}
              </div>
            </div>
            <div className="tpl-market-chart__card tpl-market-chart__card--compact">
              <div className="tpl-market-chart__label">累计国债收益率变动</div>
              <div
                className="tpl-market-chart__value tpl-market-chart__value--medium"
                data-direction={rateMoveDirection(treasuryBpTotal)}
              >
                {treasuryBpTotal !== null
                  ? `${treasuryBpTotal >= 0 ? "+" : ""}${treasuryBpTotal.toFixed(1)} BP`
                  : EM_DASH}
              </div>
            </div>
            <div className="tpl-market-chart__card tpl-market-chart__card--compact">
              <div className="tpl-market-chart__label">分析期间</div>
              <div
                className="tpl-market-chart__value tpl-market-chart__value--medium"
                data-direction="neutral"
              >
                {data.num_periods} 个月
              </div>
              <div className="tpl-market-chart__meta">
                {data.start_period} ~ {data.end_period}
              </div>
            </div>
          </div>

          <div className="tpl-market-chart__card">
            <h4 className="tpl-market-chart__section-title tpl-market-chart__section-title--tight">
              相关性解读
            </h4>
            <p className="tpl-market-chart__body">{data.correlation_interpretation}</p>
            {data.analysis_summary ? (
              <p className="tpl-market-chart__summary">{data.analysis_summary}</p>
            ) : null}
          </div>

          {chartOption && (
            <div className="tpl-market-chart__card">
              <h3 className="tpl-market-chart__section-title tpl-market-chart__section-title--spaced">
                FVTPL 公允价值变动 vs 国债收益率变动
              </h3>
              <ReactECharts
                option={chartOption}
                className="tpl-market-chart__chart"
                notMerge
                lazyUpdate
              />
              <p className="tpl-market-chart__caption">
                蓝柱仅解释 FVTPL 公允价值变动；下方 TPL 规模 / 损益来自产品分类正式读模型。
              </p>
            </div>
          )}

          <div className="tpl-market-chart__card">
            <h3 className="tpl-market-chart__section-title">月度明细</h3>
            <p className="tpl-market-chart__note">
              TPL 规模、TPL 损益、营业净收入取自 /ui/pnl/product-category 的 bond_tpl
              行；10Y、利率变动、DR007 取自 /api/pnl-attribution/tpl-market。
            </p>
            {hasMissingProductCategoryTpl ? (
              <div
                data-testid="tpl-market-product-category-missing"
                className="tpl-market-chart__warn"
              >
                部分月份缺少产品分类 bond_tpl 行，TPL 规模 / 损益 / 营业净收入显示为
                —，未回退到 FVTPL 市场值。
              </div>
            ) : null}
            {hasMissingMarketData ? (
              <div data-testid="tpl-market-data-missing" className="tpl-market-chart__warn">
                部分月份缺少 10Y / 利率变动 / DR007，表格显示为 —，图表断点显示且不补 0。
              </div>
            ) : null}
            <div className="tpl-market-chart__table-wrap">
              <table
                data-testid="tpl-market-monthly-detail"
                className="tpl-market-chart__table"
              >
                <thead>
                  <tr>
                    <th>月份</th>
                    <th data-align="right">TPL 规模(亿)</th>
                    <th data-align="right">TPL 损益(亿)</th>
                    <th data-align="right">营业净收入(亿)</th>
                    <th data-align="right">10Y(%)</th>
                    <th data-align="right">利率变动(BP)</th>
                    <th data-align="right">DR007(%)</th>
                  </tr>
                </thead>
                <tbody>
                  {data.data_points.map((point, idx) => {
                    const productCategoryTpl =
                      productCategoryTplByPeriod.get(point.period)?.row ?? null;
                    return (
                      <tr
                        key={point.period || idx}
                        data-testid={`tpl-market-monthly-row-${point.period}`}
                      >
                        <td>{point.period_label}</td>
                        <td data-align="right">
                          {productCategoryYi(productCategoryTpl, productCategoryTpl?.cnx_scale)}
                        </td>
                        <td
                          data-align="right"
                          data-direction={valueDirection(productCategoryTpl?.cnx_cash)}
                        >
                          {productCategoryYi(productCategoryTpl, productCategoryTpl?.cnx_cash)}
                        </td>
                        <td
                          data-align="right"
                          data-direction={valueDirection(
                            productCategoryTpl?.business_net_income,
                          )}
                        >
                          {productCategoryYi(
                            productCategoryTpl,
                            productCategoryTpl?.business_net_income,
                          )}
                        </td>
                        <td data-align="right">
                          {point.treasury_10y !== null
                            ? point.treasury_10y.display
                            : EM_DASH}
                        </td>
                        <td
                          data-align="right"
                          data-direction={rateMoveDirection(point.treasury_10y_change?.raw)}
                        >
                          {point.treasury_10y_change?.raw != null
                            ? `${point.treasury_10y_change.raw >= 0 ? "+" : ""}${point.treasury_10y_change.raw.toFixed(1)}`
                            : EM_DASH}
                        </td>
                        <td data-align="right">
                          {point.dr007 !== null ? point.dr007.display : EM_DASH}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </PageDataSection>
  );
}
