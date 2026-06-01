import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type {
  DecimalLike,
  Numeric,
  ProductCategoryPnlRow,
  TPLMarketCorrelationPayload,
} from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { formatProductCategoryRowDisplayValue } from "../../product-category-pnl/pages/productCategoryPnlPageModel";

const cardStyle = {
  padding: designTokens.space[5],
  borderRadius: designTokens.radius.sm,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: "#ffffff",
  boxShadow: "0 1px 2px rgba(31, 41, 55, 0.04)",
} as const;

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const yi = value / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
}

function correlationLabel(corr: number | null): {
  level: string;
  color: string;
  bg: string;
} {
  if (corr === null) {
    return {
      level: "无数据",
      color: designTokens.color.neutral[700],
      bg: designTokens.color.neutral[100],
    };
  }
  const a = Math.abs(corr);
  if (a >= 0.7) {
    return corr < 0
      ? {
          level: "强相关",
          color: designTokens.color.semantic.profit,
          bg: designTokens.color.success[50],
        }
      : {
          level: "强相关",
          color: designTokens.color.semantic.loss,
          bg: designTokens.color.danger[50],
        };
  }
  if (a >= 0.4) {
    return {
      level: "中等相关",
      color: designTokens.color.info[600],
      bg: designTokens.color.info[50],
    };
  }
  if (a >= 0.2) {
    return {
      level: "弱相关",
      color: designTokens.color.warning[600],
      bg: designTokens.color.warning[50],
    };
  }
  return {
    level: "无显著相关",
    color: designTokens.color.neutral[700],
    bg: designTokens.color.neutral[100],
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
    return value.raw;
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
    return "—";
  }
  const display = formatProductCategoryRowDisplayValue(row, value);
  return display === "-" ? "—" : display;
}

function valueTone(value: DecimalLike | null | undefined): string {
  const raw = decimalLikeRaw(value);
  if (raw === null) {
    return designTokens.color.neutral[700];
  }
  return raw >= 0
    ? designTokens.color.semantic.profit
    : designTokens.color.semantic.loss;
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
    const tpl = data.data_points.map(
      (p) => (p.tpl_fair_value_change.raw ?? 0) / 100_000_000,
    );
    const bp = data.data_points.map((p) => p.treasury_10y_change?.raw ?? null);
    return {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { fontSize: designTokens.fontSize[12] } },
      grid: { left: 56, right: 56, top: 28, bottom: 52 },
      xAxis: {
        type: "category",
        data: periods,
        axisLabel: {
          fontSize: designTokens.fontSize[11],
          color: designTokens.color.neutral[700],
        },
      },
      yAxis: [
        {
          type: "value",
          name: "FVTPL(亿)",
          axisLabel: {
            formatter: (v: number) => `${v.toFixed(1)}`,
            color: designTokens.color.neutral[700],
          },
          splitLine: {
            lineStyle: {
              type: "dashed",
              color: designTokens.color.neutral[100],
            },
          },
        },
        {
          type: "value",
          name: "BP",
          axisLabel: {
            formatter: (v: number) => `${v}`,
            color: designTokens.color.neutral[700],
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
            color: designTokens.color.info[500],
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
          lineStyle: { color: designTokens.color.danger[400], width: 2 },
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
        point.treasury_10y === null ||
        point.treasury_10y_change === null ||
        point.dr007 === null,
    ) ?? false;

  return (
    <DataSection title="FVTPL 公允价值变动 vs 10Y" state={state} onRetry={onRetry}>
      {data ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: designTokens.space[5],
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: designTokens.space[4],
            }}
          >
            <div
              style={{
                ...cardStyle,
                padding: designTokens.space[4],
                background: corr.bg,
              }}
            >
              <div
                style={{
                  fontSize: designTokens.fontSize[12],
                  color: designTokens.color.neutral[700],
                  marginBottom: designTokens.space[1],
                }}
              >
                相关系数
              </div>
              <div
                style={{
                  fontSize: designTokens.fontSize[24],
                  fontWeight: 700,
                  color: corr.color,
                  ...tabularNumsStyle,
                }}
              >
                {data.correlation_coefficient !== null
                  ? (data.correlation_coefficient.raw ?? 0).toFixed(3)
                  : "—"}
              </div>
              <div
                style={{
                  fontSize: designTokens.fontSize[12],
                  color: corr.color,
                }}
              >
                {corr.level}
              </div>
            </div>
            <div style={{ ...cardStyle, padding: designTokens.space[4] }}>
              <div
                style={{
                  fontSize: designTokens.fontSize[12],
                  color: designTokens.color.neutral[700],
                  marginBottom: designTokens.space[1],
                }}
              >
                累计 FVTPL 公允价值变动
              </div>
              <div
                style={{
                  fontSize: designTokens.fontSize[18],
                  fontWeight: 700,
                  color:
                    (data.total_tpl_fv_change.raw ?? 0) >= 0
                      ? designTokens.color.semantic.profit
                      : designTokens.color.semantic.loss,
                  ...tabularNumsStyle,
                }}
              >
                {formatYi(data.total_tpl_fv_change.raw ?? undefined)}
              </div>
            </div>
            <div style={{ ...cardStyle, padding: designTokens.space[4] }}>
              <div
                style={{
                  fontSize: designTokens.fontSize[12],
                  color: designTokens.color.neutral[700],
                  marginBottom: designTokens.space[1],
                }}
              >
                累计国债收益率变动
              </div>
              <div
                style={{
                  fontSize: designTokens.fontSize[18],
                  fontWeight: 700,
                  color:
                    (treasuryBpTotal ?? 0) <= 0
                      ? designTokens.color.semantic.profit
                      : designTokens.color.semantic.loss,
                  ...tabularNumsStyle,
                }}
              >
                {treasuryBpTotal !== null
                  ? `${treasuryBpTotal >= 0 ? "+" : ""}${treasuryBpTotal.toFixed(1)} BP`
                  : "—"}
              </div>
            </div>
            <div style={{ ...cardStyle, padding: designTokens.space[4] }}>
              <div
                style={{
                  fontSize: designTokens.fontSize[12],
                  color: designTokens.color.neutral[700],
                  marginBottom: designTokens.space[1],
                }}
              >
                分析期间
              </div>
              <div
                style={{
                  fontSize: designTokens.fontSize[18],
                  fontWeight: 700,
                  color: designTokens.color.neutral[900],
                  ...tabularNumsStyle,
                }}
              >
                {data.num_periods} 个月
              </div>
              <div
                style={{
                  fontSize: designTokens.fontSize[12],
                  color: designTokens.color.neutral[500],
                }}
              >
                {data.start_period} ~ {data.end_period}
              </div>
            </div>
          </div>

          <div style={cardStyle}>
            <h4
              style={{
                margin: `0 0 ${designTokens.space[2]}px`,
                fontSize: designTokens.fontSize[16],
                fontWeight: 600,
                color: designTokens.color.neutral[900],
              }}
            >
              相关性解读
            </h4>
            <p
              style={{
                margin: 0,
                fontSize: designTokens.fontSize[14],
                color: designTokens.color.neutral[700],
                lineHeight: designTokens.lineHeight.normal,
              }}
            >
              {data.correlation_interpretation}
            </p>
            {data.analysis_summary ? (
              <p
                style={{
                  margin: `${designTokens.space[3]}px 0 0`,
                  fontSize: designTokens.fontSize[13],
                  color: designTokens.color.neutral[500],
                }}
              >
                {data.analysis_summary}
              </p>
            ) : null}
          </div>

          {chartOption && (
            <div style={cardStyle}>
              <h3
                style={{
                  margin: `0 0 ${designTokens.space[4]}px`,
                  fontSize: designTokens.fontSize[16],
                  fontWeight: 600,
                  color: designTokens.color.neutral[900],
                }}
              >
                FVTPL 公允价值变动 vs 国债收益率变动
              </h3>
              <ReactECharts
                option={chartOption}
                style={{ height: 360 }}
                notMerge
                lazyUpdate
              />
              <p
                style={{
                  margin: `${designTokens.space[3]}px 0 0`,
                  fontSize: designTokens.fontSize[12],
                  color: designTokens.color.neutral[500],
                  textAlign: "center",
                }}
              >
                蓝柱仅解释 FVTPL 公允价值变动；下方 TPL 规模 / 损益来自产品分类正式读模型。
              </p>
            </div>
          )}

          <div style={cardStyle}>
            <h3
              style={{
                margin: `0 0 ${designTokens.space[3]}px`,
                fontSize: designTokens.fontSize[16],
                fontWeight: 600,
                color: designTokens.color.neutral[900],
              }}
            >
              月度明细
            </h3>
            <p
              style={{
                margin: `0 0 ${designTokens.space[3]}px`,
                fontSize: designTokens.fontSize[12],
                color: designTokens.color.neutral[600],
              }}
            >
              TPL 规模、TPL 损益、营业净收入取自 /ui/pnl/product-category 的 bond_tpl
              行；10Y、利率变动、DR007 取自 /api/pnl-attribution/tpl-market。
            </p>
            {hasMissingProductCategoryTpl ? (
              <div
                data-testid="tpl-market-product-category-missing"
                style={{
                  marginBottom: designTokens.space[3],
                  padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                  borderRadius: designTokens.radius.sm,
                  background: designTokens.color.warning[50],
                  color: designTokens.color.warning[700],
                  fontSize: designTokens.fontSize[12],
                }}
              >
                部分月份缺少产品分类 bond_tpl 行，TPL 规模 / 损益 / 营业净收入显示为
                —，未回退到 FVTPL 市场值。
              </div>
            ) : null}
            {hasMissingMarketData ? (
              <div
                data-testid="tpl-market-data-missing"
                style={{
                  marginBottom: designTokens.space[3],
                  padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                  borderRadius: designTokens.radius.sm,
                  background: designTokens.color.warning[50],
                  color: designTokens.color.warning[700],
                  fontSize: designTokens.fontSize[12],
                }}
              >
                部分月份缺少 10Y / 利率变动 / DR007，表格显示为 —，图表断点显示且不补 0。
              </div>
            ) : null}
            <div style={{ overflow: "auto", maxHeight: 320 }}>
              <table
                data-testid="tpl-market-monthly-detail"
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: designTokens.fontSize[13],
                }}
              >
                <thead
                  style={{
                    position: "sticky",
                    top: 0,
                    background: designTokens.color.neutral[100],
                  }}
                >
                  <tr>
                    <th
                      style={{
                        textAlign: "left",
                        padding: designTokens.space[3],
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                      }}
                    >
                      月份
                    </th>
                    <th
                      style={{
                        textAlign: "right",
                        padding: designTokens.space[3],
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                        ...tabularNumsStyle,
                      }}
                    >
                      TPL 规模(亿)
                    </th>
                    <th
                      style={{
                        textAlign: "right",
                        padding: designTokens.space[3],
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                        ...tabularNumsStyle,
                      }}
                    >
                      TPL 损益(亿)
                    </th>
                    <th
                      style={{
                        textAlign: "right",
                        padding: designTokens.space[3],
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                        ...tabularNumsStyle,
                      }}
                    >
                      营业净收入(亿)
                    </th>
                    <th
                      style={{
                        textAlign: "right",
                        padding: designTokens.space[3],
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                        ...tabularNumsStyle,
                      }}
                    >
                      10Y(%)
                    </th>
                    <th
                      style={{
                        textAlign: "right",
                        padding: designTokens.space[3],
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                        ...tabularNumsStyle,
                      }}
                    >
                      利率变动(BP)
                    </th>
                    <th
                      style={{
                        textAlign: "right",
                        padding: designTokens.space[3],
                        borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                        ...tabularNumsStyle,
                      }}
                    >
                      DR007(%)
                    </th>
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
                        style={{
                          borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
                        }}
                      >
                        <td style={{ padding: designTokens.space[3] }}>
                          {point.period_label}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: designTokens.space[3],
                            ...tabularNumsStyle,
                          }}
                        >
                          {productCategoryYi(productCategoryTpl, productCategoryTpl?.cnx_scale)}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: designTokens.space[3],
                            color: valueTone(productCategoryTpl?.cnx_cash),
                            ...tabularNumsStyle,
                          }}
                        >
                          {productCategoryYi(productCategoryTpl, productCategoryTpl?.cnx_cash)}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: designTokens.space[3],
                            color: valueTone(productCategoryTpl?.business_net_income),
                            ...tabularNumsStyle,
                          }}
                        >
                          {productCategoryYi(
                            productCategoryTpl,
                            productCategoryTpl?.business_net_income,
                          )}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: designTokens.space[3],
                            ...tabularNumsStyle,
                          }}
                        >
                          {point.treasury_10y !== null
                            ? point.treasury_10y.display
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: designTokens.space[3],
                            color:
                              (point.treasury_10y_change?.raw ?? 0) <= 0
                                ? designTokens.color.semantic.profit
                                : designTokens.color.semantic.loss,
                            ...tabularNumsStyle,
                          }}
                        >
                          {point.treasury_10y_change !== null
                            ? `${(point.treasury_10y_change.raw ?? 0) >= 0 ? "+" : ""}${(point.treasury_10y_change.raw ?? 0).toFixed(1)}`
                            : "—"}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            padding: designTokens.space[3],
                            ...tabularNumsStyle,
                          }}
                        >
                          {point.dr007 !== null ? point.dr007.display : "—"}
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
    </DataSection>
  );
}
