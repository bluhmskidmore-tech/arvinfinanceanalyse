import { useMemo } from "react";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type {
  AdvancedAttributionSummary,
  CarryRollDownPayload,
  KRDAttributionPayload,
  SpreadAttributionPayload,
} from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";

const cardStyle = {
  padding: designTokens.space[6],
  borderRadius: designTokens.radius.lg,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.primary[50],
} as const;

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const yi = value / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
}

type Props = {
  carryData: CarryRollDownPayload | null;
  spreadData: SpreadAttributionPayload | null;
  krdData: KRDAttributionPayload | null;
  summaryData?: AdvancedAttributionSummary | null;
  state: DataSectionState;
  onRetry: () => void;
};

/** 高级归因：Carry / Roll-down、利差解读、KRD 久期桶分解。 */
export function AdvancedAttributionChart({
  carryData,
  spreadData,
  krdData,
  summaryData,
  state,
  onRetry,
}: Props) {
  const carryOption = useMemo<EChartsOption | null>(() => {
    if (!carryData?.items?.length) {
      return null;
    }
    const rows = carryData.items.slice(0, 10);
    return {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { fontSize: designTokens.fontSize[12] } },
      grid: { left: 48, right: designTokens.space[6], top: designTokens.space[6], bottom: 48 },
      xAxis: {
        type: "category",
        data: rows.map((r) => (r.category.length > 8 ? `${r.category.slice(0, 8)}…` : r.category)),
        axisLabel: {
          fontSize: designTokens.fontSize[11],
          rotate: 20,
          color: designTokens.color.neutral[700],
        },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: (v: number) => `${v.toFixed(1)}%`,
          color: designTokens.color.neutral[700],
        },
        splitLine: { lineStyle: { type: "dashed", color: designTokens.color.neutral[100] } },
      },
      series: [
        {
          name: "Carry",
          type: "bar",
          data: rows.map((r) => r.carry.raw ?? 0),
          itemStyle: {
            color: designTokens.color.success[500],
            borderRadius: [designTokens.radius.sm, designTokens.radius.sm, 0, 0],
          },
        },
        {
          name: "Roll-down",
          type: "bar",
          data: rows.map((r) => r.rolldown.raw ?? 0),
          itemStyle: {
            color: designTokens.color.info[500],
            borderRadius: [designTokens.radius.sm, designTokens.radius.sm, 0, 0],
          },
        },
      ],
    };
  }, [carryData]);

  const krdOption = useMemo<EChartsOption | null>(() => {
    if (!krdData?.buckets?.length) {
      return null;
    }
    const tenors = krdData.buckets.map((b) => b.tenor);
    const contrib = krdData.buckets.map((b) => (b.duration_contribution.raw ?? 0) / 100_000_000);
    const ychg = krdData.buckets.map((b) => b.yield_change?.raw ?? 0);
    return {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { fontSize: designTokens.fontSize[12] } },
      grid: { left: 52, right: 52, top: designTokens.space[6], bottom: 48 },
      xAxis: {
        type: "category",
        data: tenors,
        axisLabel: { fontSize: designTokens.fontSize[11], color: designTokens.color.neutral[700] },
      },
      yAxis: [
        {
          type: "value",
          name: "久期贡献(亿)",
          axisLabel: { color: designTokens.color.neutral[700] },
          splitLine: { lineStyle: { type: "dashed", color: designTokens.color.neutral[100] } },
        },
        {
          type: "value",
          name: "BP",
          axisLabel: { color: designTokens.color.neutral[700] },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "久期贡献",
          type: "bar",
          yAxisIndex: 0,
          data: contrib.map((v) => ({
            value: v,
            itemStyle: {
              color: v >= 0 ? designTokens.color.semantic.profit : designTokens.color.semantic.loss,
              borderRadius: [designTokens.radius.sm, designTokens.radius.sm, 0, 0],
            },
          })),
        },
        {
          name: "收益率变动",
          type: "line",
          yAxisIndex: 1,
          data: ychg,
          smooth: true,
          symbolSize: 8,
          lineStyle: { color: designTokens.color.info[500], width: 2 },
        },
      ],
    };
  }, [krdData]);

  const krdCompareOption = useMemo<EChartsOption | null>(() => {
    if (!krdData?.buckets?.length) {
      return null;
    }
    return {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { fontSize: designTokens.fontSize[12] } },
      grid: { left: 48, right: designTokens.space[6], top: designTokens.space[6], bottom: 48 },
      xAxis: {
        type: "category",
        data: krdData.buckets.map((b) => b.tenor),
        axisLabel: { fontSize: designTokens.fontSize[11], color: designTokens.color.neutral[700] },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: (v: number) => `${v}%`,
          color: designTokens.color.neutral[700],
        },
      },
      series: [
        {
          name: "贡献占比",
          type: "bar",
          data: krdData.buckets.map((b) => b.contribution_pct.raw ?? 0),
          itemStyle: {
            color: designTokens.color.info[500],
            borderRadius: [designTokens.radius.sm, designTokens.radius.sm, 0, 0],
          },
        },
        {
          name: "市值占比",
          type: "bar",
          data: krdData.buckets.map((b) => b.weight.raw ?? 0),
          itemStyle: {
            color: designTokens.color.success[500],
            borderRadius: [designTokens.radius.sm, designTokens.radius.sm, 0, 0],
          },
        },
      ],
    };
  }, [krdData]);

  return (
    <DataSection title="Carry / 利差 / KRD 高级归因" state={state} onRetry={onRetry}>
      <div style={{ display: "flex", flexDirection: "column", gap: designTokens.space[5] }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: designTokens.space[3],
          }}
        >
          {carryData && (
            <>
              <div
                style={{
                  ...cardStyle,
                  padding: designTokens.space[4],
                  background: designTokens.color.success[50],
                  borderColor: designTokens.color.success[200],
                }}
              >
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.semantic.profit }}>
                  组合 Carry
                </div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[20],
                    fontWeight: 700,
                    color:
                      (carryData.portfolio_carry.raw ?? 0) >= 0
                        ? designTokens.color.semantic.profit
                        : designTokens.color.semantic.loss,
                    ...tabularNumsStyle,
                  }}
                >
                  {(carryData.portfolio_carry.raw ?? 0).toFixed(2)}%
                </div>
                <div style={{ fontSize: designTokens.fontSize[11], color: designTokens.color.success[600] }}>
                  票息 − FTP
                </div>
              </div>
              <div
                style={{
                  ...cardStyle,
                  padding: designTokens.space[4],
                  background: designTokens.color.info[50],
                  borderColor: designTokens.color.info[200],
                }}
              >
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.info[600] }}>
                  组合 Roll-down
                </div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[20],
                    fontWeight: 700,
                    color:
                      (carryData.portfolio_rolldown.raw ?? 0) >= 0
                        ? designTokens.color.info[600]
                        : designTokens.color.warning[600],
                    ...tabularNumsStyle,
                  }}
                >
                  {(carryData.portfolio_rolldown.raw ?? 0).toFixed(2)}%
                </div>
                <div style={{ fontSize: designTokens.fontSize[11], color: designTokens.color.neutral[700] }}>
                  骑乘
                </div>
              </div>
              <div
                style={{
                  ...cardStyle,
                  padding: designTokens.space[4],
                  background: designTokens.color.primary[100],
                  borderColor: designTokens.color.primary[200],
                }}
              >
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.primary[700] }}>
                  静态收益（年化近似）
                </div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[20],
                    fontWeight: 700,
                    color: designTokens.color.primary[700],
                    ...tabularNumsStyle,
                  }}
                >
                  {(
                    summaryData?.static_return_annualized?.raw ??
                    carryData.portfolio_static_return.raw ??
                    0
                  ).toFixed(2)}
                  %
                </div>
                <div style={{ fontSize: designTokens.fontSize[11], color: designTokens.color.neutral[700] }}>
                  Carry + Roll-down
                </div>
              </div>
            </>
          )}
          {spreadData && (
            <>
              <div
                style={{
                  ...cardStyle,
                  padding: designTokens.space[4],
                  background: designTokens.color.warning[50],
                  borderColor: designTokens.color.warning[200],
                }}
              >
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.warning[600] }}>
                  国债曲线效应
                </div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[18],
                    fontWeight: 700,
                    color:
                      (spreadData.total_treasury_effect.raw ?? 0) >= 0
                        ? designTokens.color.semantic.profit
                        : designTokens.color.semantic.loss,
                    ...tabularNumsStyle,
                  }}
                >
                  {formatYi(spreadData.total_treasury_effect.raw ?? undefined)}
                </div>
              </div>
              <div
                style={{
                  ...cardStyle,
                  padding: designTokens.space[4],
                  background: designTokens.color.danger[50],
                  borderColor: designTokens.color.danger[200],
                }}
              >
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.semantic.loss }}>
                  10Y 变动
                </div>
                <div
                  style={{
                    fontSize: designTokens.fontSize[18],
                    fontWeight: 700,
                    color:
                      (spreadData.treasury_10y_change?.raw ?? 0) <= 0
                        ? designTokens.color.semantic.profit
                        : designTokens.color.semantic.loss,
                    ...tabularNumsStyle,
                  }}
                >
                  {spreadData.treasury_10y_change !== null
                    ? `${(spreadData.treasury_10y_change.raw ?? 0) >= 0 ? "+" : ""}${(spreadData.treasury_10y_change.raw ?? 0).toFixed(0)} BP`
                    : "—"}
                </div>
              </div>
            </>
          )}
          {krdData && (
            <div
              style={{
                ...cardStyle,
                padding: designTokens.space[4],
                background: designTokens.color.info[50],
                borderColor: designTokens.color.info[200],
              }}
            >
              <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.info[700] }}>组合 DV01</div>
              <div
                style={{
                  fontSize: designTokens.fontSize[20],
                  fontWeight: 700,
                  color: designTokens.color.info[700],
                  ...tabularNumsStyle,
                }}
              >
                {((krdData.portfolio_dv01.raw ?? 0) / 10_000).toFixed(0)} 万
              </div>
              <div style={{ fontSize: designTokens.fontSize[11], color: designTokens.color.neutral[700] }}>
                每 BP 价值变动
              </div>
            </div>
          )}
        </div>

        {carryOption && carryData && (
          <div style={cardStyle}>
            <h3
              style={{
                margin: `0 0 ${designTokens.space[3]}px`,
                fontSize: designTokens.fontSize[16],
                fontWeight: 600,
                color: designTokens.color.neutral[900],
              }}
            >
              {"Carry & Roll-down"} 分解
            </h3>
            <ReactECharts option={carryOption} style={{ height: 300 }} notMerge lazyUpdate />
            <div style={{ marginTop: designTokens.space[3], overflow: "auto", maxHeight: 220 }}>
              <table
                style={{
                  width: "100%",
                  fontSize: designTokens.fontSize[12],
                  borderCollapse: "collapse",
                }}
              >
                <thead
                  style={{
                    background: designTokens.color.neutral[100],
                    position: "sticky",
                    top: 0,
                  }}
                >
                  <tr>
                    <th style={{ textAlign: "left", padding: designTokens.space[2] }}>类别</th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      市值(亿)
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      票息%
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      FTP%
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      Carry%
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      久期
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      Roll%
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {carryData.items.slice(0, 8).map((item, idx) => (
                    <tr
                      key={idx}
                      style={{ borderBottom: `1px solid ${designTokens.color.neutral[200]}` }}
                    >
                      <td style={{ padding: designTokens.space[2] }}>{item.category}</td>
                      <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                        {((item.market_value.raw ?? 0) / 1e8).toFixed(1)}
                      </td>
                      <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                        {(item.coupon_rate.raw ?? 0).toFixed(2)}
                      </td>
                      <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                        {(item.funding_cost.raw ?? 0).toFixed(2)}
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          padding: designTokens.space[2],
                          color:
                            (item.carry.raw ?? 0) >= 0
                              ? designTokens.color.semantic.profit
                              : designTokens.color.semantic.loss,
                          ...tabularNumsStyle,
                        }}
                      >
                        {(item.carry.raw ?? 0).toFixed(2)}
                      </td>
                      <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                        {(item.duration.raw ?? 0).toFixed(2)}
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          padding: designTokens.space[2],
                          color:
                            (item.rolldown.raw ?? 0) >= 0
                              ? designTokens.color.info[600]
                              : designTokens.color.warning[600],
                          ...tabularNumsStyle,
                        }}
                      >
                        {(item.rolldown.raw ?? 0).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {spreadData?.interpretation && (
          <div style={cardStyle}>
            <h4
              style={{
                margin: `0 0 ${designTokens.space[2]}px`,
                fontSize: designTokens.fontSize[16],
                fontWeight: 600,
                color: designTokens.color.neutral[900],
              }}
            >
              利差归因
            </h4>
            <p
              style={{
                margin: 0,
                fontSize: designTokens.fontSize[14],
                color: designTokens.color.neutral[700],
                lineHeight: designTokens.lineHeight.normal,
              }}
            >
              {spreadData.interpretation}
            </p>
            <p
              style={{
                margin: `${designTokens.space[3]}px 0 0`,
                fontSize: designTokens.fontSize[12],
                color: designTokens.color.neutral[500],
              }}
            >
              区间 {spreadData.start_date} ~ {spreadData.end_date}
            </p>
          </div>
        )}

        {krdOption && krdData && (
          <div style={cardStyle}>
            <h3
              style={{
                margin: `0 0 ${designTokens.space[3]}px`,
                fontSize: designTokens.fontSize[16],
                fontWeight: 600,
                color: designTokens.color.neutral[900],
              }}
            >
              KRD 归因
            </h3>
            {krdData.curve_interpretation && (
              <p
                style={{
                  margin: `0 0 ${designTokens.space[3]}px`,
                  fontSize: designTokens.fontSize[13],
                  color: designTokens.color.neutral[700],
                  background: designTokens.color.primary[50],
                  padding: designTokens.space[3],
                  borderRadius: designTokens.radius.md,
                }}
              >
                曲线形态：{krdData.curve_interpretation}
                {krdData.max_contribution_tenor ? (
                  <span style={{ marginLeft: designTokens.space[3], color: designTokens.color.info[600] }}>
                    最大贡献期限 {krdData.max_contribution_tenor}（{formatYi(krdData.max_contribution_value.raw ?? undefined)}）
                  </span>
                ) : null}
              </p>
            )}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: designTokens.space[4],
              }}
            >
              <ReactECharts option={krdOption} style={{ height: 280 }} notMerge lazyUpdate />
              {krdCompareOption && (
                <ReactECharts option={krdCompareOption} style={{ height: 280 }} notMerge lazyUpdate />
              )}
            </div>
            <div style={{ marginTop: designTokens.space[3], overflow: "auto" }}>
              <table
                style={{
                  width: "100%",
                  fontSize: designTokens.fontSize[12],
                  borderCollapse: "collapse",
                }}
              >
                <thead style={{ background: designTokens.color.neutral[100] }}>
                  <tr>
                    <th style={{ textAlign: "left", padding: designTokens.space[2] }}>期限</th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      债券数
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      市值(亿)
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      占比%
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      久期
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      Δyield
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      贡献(亿)
                    </th>
                    <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                      贡献占比%
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {krdData.buckets.map((b, idx) => (
                    <tr
                      key={idx}
                      style={{ borderBottom: `1px solid ${designTokens.color.neutral[200]}` }}
                    >
                      <td style={{ padding: designTokens.space[2], fontWeight: 500 }}>{b.tenor}</td>
                      <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                        {b.bond_count}
                      </td>
                      <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                        {((b.market_value.raw ?? 0) / 1e8).toFixed(1)}
                      </td>
                      <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                        {(b.weight.raw ?? 0).toFixed(1)}
                      </td>
                      <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                        {(b.bucket_duration.raw ?? 0).toFixed(2)}
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          padding: designTokens.space[2],
                          color:
                            (b.yield_change?.raw ?? 0) <= 0
                              ? designTokens.color.semantic.profit
                              : designTokens.color.semantic.loss,
                          ...tabularNumsStyle,
                        }}
                      >
                        {b.yield_change !== null ? (b.yield_change.raw ?? 0).toFixed(1) : "—"}
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          padding: designTokens.space[2],
                          color:
                            (b.duration_contribution.raw ?? 0) >= 0
                              ? designTokens.color.semantic.profit
                              : designTokens.color.semantic.loss,
                          ...tabularNumsStyle,
                        }}
                      >
                        {((b.duration_contribution.raw ?? 0) / 1e8).toFixed(2)}
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          padding: designTokens.space[2],
                          fontWeight: 600,
                          ...tabularNumsStyle,
                        }}
                      >
                        {(b.contribution_pct.raw ?? 0).toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </DataSection>
  );
}
