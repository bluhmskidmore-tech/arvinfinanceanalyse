import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type { MacroBondLinkagePayload } from "../../../api/contracts";
import ReactECharts from "../../../lib/echarts";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../../workbench/components/KpiCard";
import { toneFromSignedNumber } from "../../workbench/components/kpiFormat";
import { CrossAssetEventCalendar } from "../components/CrossAssetEventCalendar";
import { CrossAssetSparkline } from "../components/CrossAssetSparkline";
import { MarketCandidateActions } from "../components/MarketCandidateActions";
import { PageOutput } from "../components/PageOutput";
import { WatchList } from "../components/WatchList";
import {
  maxCrossAssetHeadlineTradeDate,
  resolveCrossAssetKpis,
  type ResolvedCrossAssetKpi,
} from "../lib/crossAssetKpiModel";
import { buildDriverColumns, buildEnvironmentTags, driverStanceStyle } from "../lib/crossAssetDriversModel";
import { buildCrossAssetTrendOption } from "../lib/crossAssetTrendChart";

const pageBg = "#f5f7fa";

const detailPanelStyle = {
  padding: 20,
  borderRadius: 16,
  background: "#ffffff",
  border: "1px solid #e2e8f0",
  boxShadow: "0 1px 2px rgba(15, 23, 42, 0.06), 0 4px 12px rgba(15, 23, 42, 0.05)",
} as const;

const sparkStroke: Record<ResolvedCrossAssetKpi["changeTone"], string> = {
  positive: "#52c41a",
  negative: "#f5222d",
  warning: "#fa8c16",
  default: "#1890ff",
};

function MiniKpiCard({ kpi }: { kpi: ResolvedCrossAssetKpi }) {
  const stroke = sparkStroke[kpi.changeTone];
  const changeColor = stroke;
  return (
    <div
      style={{
        padding: "14px 14px 12px",
        borderRadius: 12,
        background: "#ffffff",
        border: "1px solid #e2e8f0",
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.06), 0 4px 12px rgba(15, 23, 42, 0.05)",
        minHeight: 132,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, lineHeight: 1.3 }}>{kpi.label}</div>
      <div
        style={{
          fontSize: 20,
          fontWeight: 700,
          color: "#1e293b",
          marginTop: 8,
          letterSpacing: "-0.02em",
        }}
      >
        {kpi.valueLabel}
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color: changeColor, marginTop: 4 }}>{kpi.changeLabel}</div>
      <div style={{ marginTop: "auto", paddingTop: 8 }}>
        <CrossAssetSparkline values={kpi.sparkline} stroke={stroke} height={26} />
      </div>
      <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 6 }}>{kpi.tag}</div>
    </div>
  );
}

function formatSignedNumber(value: number | string | null | undefined, suffix = "") {
  if (value == null || value === "") {
    return "不可用";
  }
  const numericValue = typeof value === "number" ? value : Number.parseFloat(String(value));
  if (Number.isNaN(numericValue)) {
    return String(value);
  }
  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${numericValue.toFixed(2)}${suffix}`;
}

export default function CrossAssetPage() {
  const client = useApiClient();
  const latestQuery = useQuery({
    queryKey: ["cross-asset", "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
  });
  const latestSeries = useMemo(() => latestQuery.data?.result.series ?? [], [latestQuery.data?.result.series]);

  const crossAssetDataDate = useMemo(() => maxCrossAssetHeadlineTradeDate(latestSeries), [latestSeries]);

  const linkageReportDate = useMemo(() => {
    if (latestSeries.length === 0) {
      return "";
    }
    return latestSeries.map((point) => point.trade_date).sort((left, right) => right.localeCompare(left))[0];
  }, [latestSeries]);

  const macroBondLinkageQuery = useQuery({
    queryKey: ["cross-asset", "macro-bond-linkage", client.mode, linkageReportDate],
    queryFn: () => client.getMacroBondLinkageAnalysis({ reportDate: linkageReportDate }),
    enabled: Boolean(linkageReportDate),
    retry: false,
  });

  const macroBondLinkage = useMemo(
    () => macroBondLinkageQuery.data?.result ?? ({} as Partial<MacroBondLinkagePayload>),
    [macroBondLinkageQuery.data?.result],
  );
  const macroBondLinkageWarnings = macroBondLinkage.warnings ?? [];
  const hasPortfolioImpact = Object.keys(macroBondLinkage.portfolio_impact ?? {}).length > 0;
  const linkageBodyEmpty =
    macroBondLinkageQuery.isSuccess &&
    Boolean(linkageReportDate) &&
    macroBondLinkage.environment_score?.composite_score == null &&
    !hasPortfolioImpact &&
    macroBondLinkageWarnings.length === 0;

  const env = useMemo(
    () => macroBondLinkage.environment_score ?? {},
    [macroBondLinkage.environment_score],
  );
  const kpis = useMemo(() => resolveCrossAssetKpis(latestSeries), [latestSeries]);
  const trendOption = useMemo(() => buildCrossAssetTrendOption(latestSeries), [latestSeries]);
  const drivers = useMemo(() => buildDriverColumns(env), [env]);
  const envTags = useMemo(() => buildEnvironmentTags(env), [env]);

  const heatmapRows = [
    { indicator: "10Y国债收益率", current: "1.94%", pct: "18%", eval: "中性", evalTone: "warning" as const },
    { indicator: "5Y国开-国债", current: "12bp", pct: "72%", eval: "偏贵宜", evalTone: "bull" as const },
    { indicator: "AAA 3Y", current: "45bp", pct: "10%", eval: "偏拥挤", evalTone: "bear" as const },
    { indicator: "1Y AAA存单", current: "28bp", pct: "81%", eval: "可配", evalTone: "bull" as const },
    { indicator: "中美国债利差", current: "-210bp", pct: "5%", eval: "倒挂", evalTone: "bear" as const },
  ];

  const evalColor = {
    bull: "#52c41a",
    bear: "#f5222d",
    warning: "#fa8c16",
  } as const;

  return (
    <section
      data-testid="cross-asset-page"
      style={{ background: pageBg, minHeight: "100%", borderRadius: 18, padding: 16 }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          flexWrap: "wrap",
          marginBottom: 20,
        }}
      >
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: 28,
              fontWeight: 600,
              letterSpacing: "-0.03em",
              color: "#0f172a",
            }}
          >
            跨资产驱动
          </h1>
          <p style={{ margin: "8px 0 0", color: "#64748b", fontSize: 14 }}>
            数据日期{" "}
            <strong style={{ color: "#334155" }}>
              {crossAssetDataDate || linkageReportDate || "—"}
            </strong>
            <span style={{ marginLeft: 12 }}>
              完整序列见{" "}
              <Link to="/market-data" style={{ color: "#1890ff", fontWeight: 600 }}>
                市场数据
              </Link>
            </span>
          </p>
        </div>
      </header>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(280px, 360px)",
          gap: 16,
          alignItems: "start",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
          <div
            data-testid="cross-asset-kpi-band"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: 12,
            }}
          >
            {kpis.map((kpi) => (
              <MiniKpiCard key={kpi.key} kpi={kpi} />
            ))}
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
              gap: 12,
            }}
          >
            <div style={detailPanelStyle}>
              <h2 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 600, color: "#0f172a" }}>市场判断</h2>
              <p style={{ margin: 0, color: "#475569", fontSize: 13, lineHeight: 1.75 }}>
                {env.signal_description ??
                  "加载联动分析后可在此查看环境评分生成的判断摘要；当前为占位说明。"}
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 14 }}>
                <span
                  style={{
                    padding: "4px 10px",
                    borderRadius: 999,
                    background: "rgba(82, 196, 26, 0.12)",
                    color: "#52c41a",
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                >
                  主导因子：{envTags.primary}
                </span>
                <span
                  style={{
                    padding: "4px 10px",
                    borderRadius: 999,
                    background: "rgba(250, 140, 22, 0.12)",
                    color: "#fa8c16",
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                >
                  次要扰动：{envTags.secondary}
                </span>
                <span
                  style={{
                    padding: "4px 10px",
                    borderRadius: 999,
                    background: "rgba(24, 144, 255, 0.1)",
                    color: "#1890ff",
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                >
                  风格判断：{envTags.style}
                </span>
              </div>
            </div>

            <div style={detailPanelStyle}>
              <h2 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 600, color: "#0f172a" }}>驱动拆解</h2>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                  gap: 10,
                }}
              >
                {drivers.map((col) => {
                  const st = driverStanceStyle(col.tone);
                  return (
                    <div
                      key={col.title}
                      style={{
                        borderRadius: 12,
                        border: "1px solid #f1f5f9",
                        padding: 10,
                        background: "#fafbfc",
                        minHeight: 160,
                      }}
                    >
                      <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>
                        {col.title}
                      </div>
                      <div
                        style={{
                          display: "inline-block",
                          padding: "2px 8px",
                          borderRadius: 8,
                          fontSize: 12,
                          fontWeight: 700,
                          background: st.bg,
                          color: st.color,
                          marginBottom: 8,
                        }}
                      >
                        {col.stance}
                      </div>
                      <ul
                        style={{
                          margin: 0,
                          paddingLeft: 18,
                          color: "#475569",
                          fontSize: 11,
                          lineHeight: 1.65,
                        }}
                      >
                        {col.bullets.map((b) => (
                          <li key={b}>{b}</li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <MarketCandidateActions />

          <div style={detailPanelStyle}>
            <h2 style={{ margin: "0 0 8px", fontSize: 15, fontWeight: 600, color: "#0f172a" }}>跨资产走势</h2>
            <p style={{ margin: "0 0 8px", color: "#94a3b8", fontSize: 12 }}>近 20 个交易日，归一化至基期=100</p>
            {latestQuery.isLoading ? (
              <div style={{ height: 320, display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8" }}>
                加载宏观序列…
              </div>
            ) : trendOption ? (
              <ReactECharts option={trendOption} style={{ height: 320, width: "100%" }} notMerge lazyUpdate />
            ) : (
              <div style={{ height: 200, color: "#94a3b8", fontSize: 13 }}>缺少带历史点的序列，无法绘制联动图。</div>
            )}
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
              gap: 12,
              alignItems: "start",
            }}
          >
            <CrossAssetEventCalendar />
            <WatchList />
          </div>

          <div style={{ ...detailPanelStyle, padding: 18 }}>
            <h2 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 600, color: "#0f172a" }}>跨资产传导链</h2>
            <ol style={{ margin: 0, paddingLeft: 20, color: "#475569", fontSize: 13, lineHeight: 1.85 }}>
              <li>先看顶部 KPI：利率锚、海外约束、风险资产与汇率是否同向。</li>
              <li>再看驱动拆解：流动性 / 海外 / 增长 / 通胀四象限是否互相抵消。</li>
              <li>最后结合估值分位与组合约束，落到久期、利差与对冲工具。</li>
            </ol>
            <p style={{ margin: "14px 0 0", fontSize: 12, color: "#64748b", lineHeight: 1.7 }}>
              原则：跨资产信号只做环境标注与候选清单，执行仍需回缚到正式估值、限额与风控流程。
            </p>
          </div>

          <AsyncSection
            title="宏观 — 债券联动（评分与组合影响）"
            isLoading={macroBondLinkageQuery.isLoading || latestQuery.isLoading}
            isError={macroBondLinkageQuery.isError || latestQuery.isError}
            isEmpty={linkageBodyEmpty}
            onRetry={() => {
              void latestQuery.refetch();
              void macroBondLinkageQuery.refetch();
            }}
          >
            {!linkageReportDate ? (
              <p style={{ color: "#5c6b82", fontSize: 14 }}>
                缺少可用的宏观最新交易日，无法计算联动。请稍后重试或检查市场数据管线。
              </p>
            ) : (
              <div style={{ display: "grid", gap: 14 }}>
                {macroBondLinkageWarnings.length > 0 ? (
                  <ul
                    data-testid="cross-asset-linkage-warning-list"
                    style={{
                      margin: 0,
                      paddingLeft: 20,
                      color: "#5c6b82",
                      fontSize: 13,
                      lineHeight: 1.8,
                    }}
                  >
                    {macroBondLinkageWarnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                ) : null}

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
                    gap: 12,
                  }}
                >
                  <div data-testid="cross-asset-linkage-composite-score">
                    <KpiCard
                      title="综合评分"
                      value={
                        env.composite_score != null ? String(env.composite_score.toFixed(2)) : "不可用"
                      }
                      detail={env.signal_description ?? "缺少环境评分数据。"}
                      valueVariant="text"
                      tone={toneFromSignedNumber(env.composite_score != null ? env.composite_score : null)}
                    />
                  </div>
                  <div data-testid="cross-asset-linkage-rate-direction">
                    <KpiCard
                      title="利率方向"
                      value={env.rate_direction ?? "不可用"}
                      detail={
                        env.rate_direction_score != null
                          ? `direction score ${env.rate_direction_score.toFixed(2)}`
                          : "缺少方向评分。"
                      }
                      valueVariant="text"
                      tone={toneFromSignedNumber(
                        env.rate_direction_score != null ? env.rate_direction_score : null,
                      )}
                    />
                  </div>
                  <div data-testid="cross-asset-linkage-liquidity-score">
                    <KpiCard
                      title="流动性评分"
                      value={env.liquidity_score != null ? env.liquidity_score.toFixed(2) : "不可用"}
                      detail="正值偏松，负值偏紧。"
                      valueVariant="text"
                      tone={toneFromSignedNumber(env.liquidity_score != null ? env.liquidity_score : null)}
                    />
                  </div>
                  <div data-testid="cross-asset-linkage-growth-score">
                    <KpiCard
                      title="增长评分"
                      value={env.growth_score != null ? env.growth_score.toFixed(2) : "不可用"}
                      detail="宏观增长方向的简化分值。"
                      valueVariant="text"
                      tone={toneFromSignedNumber(env.growth_score != null ? env.growth_score : null)}
                    />
                  </div>
                </div>

                <section data-testid="cross-asset-linkage-portfolio-impact" style={detailPanelStyle}>
                  <h2 style={{ marginTop: 0, marginBottom: 8, fontSize: 16, fontWeight: 600 }}>组合影响估算</h2>
                  <p style={{ marginTop: 0, color: "#5c6b82", fontSize: 13, lineHeight: 1.7 }}>
                    以下数值为 analytical estimate，不代表正式损益。
                  </p>
                  {hasPortfolioImpact ? (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                        gap: 12,
                      }}
                    >
                      <div>
                        <div style={{ color: "#8090a8", fontSize: 12 }}>rate change</div>
                        <div>
                          {formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_rate_change_bps, " bp")}
                        </div>
                      </div>
                      <div>
                        <div style={{ color: "#8090a8", fontSize: 12 }}>spread widening</div>
                        <div>
                          {formatSignedNumber(
                            macroBondLinkage.portfolio_impact?.estimated_spread_widening_bps,
                            " bp",
                          )}
                        </div>
                      </div>
                      <div>
                        <div style={{ color: "#8090a8", fontSize: 12 }}>total estimate</div>
                        <div>{formatSignedNumber(macroBondLinkage.portfolio_impact?.total_estimated_impact)}</div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: "#8090a8", fontSize: 14 }}>当前无组合影响估算。</div>
                  )}
                </section>
              </div>
            )}
          </AsyncSection>

          <PageOutput />
        </div>

        <aside style={{ display: "flex", flexDirection: "column", gap: 12, position: "sticky", top: 16 }}>
          <div style={detailPanelStyle}>
            <h2 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600, color: "#0f172a" }}>
              估值 / 分位热图
            </h2>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ color: "#94a3b8", textAlign: "left" }}>
                  <th style={{ padding: "6px 4px", fontWeight: 600 }}>指标</th>
                  <th style={{ padding: "6px 4px", fontWeight: 600 }}>当前</th>
                  <th style={{ padding: "6px 4px", fontWeight: 600 }}>分位</th>
                  <th style={{ padding: "6px 4px", fontWeight: 600 }}>评估</th>
                </tr>
              </thead>
              <tbody>
                {heatmapRows.map((row) => (
                  <tr key={row.indicator} style={{ borderTop: "1px solid #f1f5f9" }}>
                    <td style={{ padding: "8px 4px", color: "#334155" }}>{row.indicator}</td>
                    <td style={{ padding: "8px 4px", color: "#0f172a", fontWeight: 600 }}>{row.current}</td>
                    <td style={{ padding: "8px 4px", color: "#64748b" }}>{row.pct}</td>
                    <td style={{ padding: "8px 4px", color: evalColor[row.evalTone], fontWeight: 600 }}>
                      {row.eval}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </aside>
      </div>
    </section>
  );
}
