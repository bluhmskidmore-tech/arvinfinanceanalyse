import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type { MacroBondLinkagePayload, MacroBondLinkageTopCorrelation } from "../../../api/contracts";
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
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";

const t = designTokens;

const pageBg = t.color.neutral[50];

const detailPanelStyle = {
  padding: t.space[5],
  borderRadius: t.radius.md,
  background: t.color.primary[50],
  border: `1px solid ${t.color.neutral[200]}`,
  boxShadow: t.shadow.card,
} as const;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: t.space[2],
  marginTop: t.space[6],
} as const;

const sectionEyebrowStyle = {
  fontSize: t.fontSize[11],
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: t.color.neutral[500],
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: t.fontSize[18],
  fontWeight: 600,
  color: t.color.neutral[900],
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 860,
  color: t.color.neutral[600],
  fontSize: t.fontSize[13],
  lineHeight: t.lineHeight.relaxed,
} as const;

function linkageHeatmapRows(correlations: MacroBondLinkageTopCorrelation[]) {
  if (correlations.length === 0) {
    return [
      {
        indicator: "暂无可用排名",
        current: "—",
        mid: "—",
        eval: "等待数据",
        evalTone: "warning" as const,
      },
    ];
  }
  return correlations.slice(0, 8).map((row) => {
    const indicator = `${row.series_name} → ${row.target_family}${
      row.target_tenor ? ` (${row.target_tenor})` : ""
    }`;
    const current = row.correlation_3m != null ? row.correlation_3m.toFixed(2) : "—";
    const mid = row.correlation_6m != null ? row.correlation_6m.toFixed(2) : "—";
    let evalLabel = "中性";
    let evalTone: "bull" | "bear" | "warning" = "warning";
    if (row.direction === "positive") {
      evalLabel = "同向";
      evalTone = "bull";
    } else if (row.direction === "negative") {
      evalLabel = "反向";
      evalTone = "bear";
    }
    return { indicator, current, mid, eval: evalLabel, evalTone };
  });
}

const sparkStroke: Record<ResolvedCrossAssetKpi["changeTone"], string> = {
  positive: t.color.semantic.profit,
  negative: t.color.semantic.loss,
  warning: t.color.warning[500],
  default: t.color.primary[600],
};

function MiniKpiCard({ kpi }: { kpi: ResolvedCrossAssetKpi }) {
  const stroke = sparkStroke[kpi.changeTone];
  const changeColor = stroke;
  return (
    <div
      style={{
        padding: `${t.space[4]}px ${t.space[4]}px ${t.space[3]}px`,
        borderRadius: t.radius.md,
        background: t.color.primary[50],
        border: `1px solid ${t.color.neutral[200]}`,
        boxShadow: t.shadow.card,
        minHeight: 132,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          fontSize: t.fontSize[11],
          color: t.color.neutral[600],
          fontWeight: 600,
          lineHeight: t.lineHeight.snug,
        }}
      >
        {kpi.label}
      </div>
      <div
        style={{
          ...tabularNumsStyle,
          fontSize: t.fontSize[20],
          fontWeight: 700,
          color: t.color.neutral[800],
          marginTop: t.space[2],
          letterSpacing: "-0.02em",
        }}
      >
        {kpi.valueLabel}
      </div>
      <div
        style={{
          fontSize: t.fontSize[12],
          fontWeight: 600,
          color: changeColor,
          marginTop: t.space[1],
        }}
      >
        {kpi.changeLabel}
      </div>
      <div style={{ marginTop: "auto", paddingTop: t.space[2] }}>
        <CrossAssetSparkline values={kpi.sparkline} stroke={stroke} height={26} />
      </div>
      <div style={{ fontSize: t.fontSize[11], color: t.color.neutral[500], marginTop: t.space[2] }}>{kpi.tag}</div>
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

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
  );
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

  const heatmapRows = useMemo(
    () => linkageHeatmapRows(macroBondLinkage.top_correlations ?? []),
    [macroBondLinkage.top_correlations],
  );

  const evalColor = {
    bull: t.color.semantic.profit,
    bear: t.color.semantic.loss,
    warning: t.color.warning[500],
  } as const;

  return (
    <section
      data-testid="cross-asset-page"
      style={{
        background: pageBg,
        minHeight: "100%",
        borderRadius: t.radius.lg,
        padding: t.space[4],
      }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: t.space[4],
          flexWrap: "wrap",
          marginBottom: t.space[5],
        }}
      >
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: t.fontSize[30],
              fontWeight: 600,
              letterSpacing: "-0.03em",
              color: t.color.neutral[900],
            }}
          >
            跨资产驱动
          </h1>
          <p style={{ margin: `${t.space[2]}px 0 0`, color: t.color.neutral[600], fontSize: t.fontSize[13] }}>
            数据日期{" "}
            <strong style={{ ...tabularNumsStyle, color: t.color.neutral[800] }}>
              {crossAssetDataDate || linkageReportDate || "—"}
            </strong>
          </p>
          <p
            style={{
              margin: `${t.space[3]}px 0 0`,
              color: t.color.neutral[600],
              fontSize: t.fontSize[16],
              lineHeight: t.lineHeight.relaxed,
            }}
          >
            当前页按“环境概览、驱动判断、走势观察、分析输出”顺序阅读。完整宏观序列仍在{" "}
            <Link to="/market-data" style={{ color: t.color.primary[600], fontWeight: 600 }}>
              市场数据
            </Link>{" "}
            查看，这里只保留跨资产驱动判断与 analytical 联动输出。
          </p>
        </div>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: `${t.space[2]}px ${t.space[3]}px`,
            borderRadius: 999,
            background: client.mode === "real" ? t.color.success[100] : t.color.primary[100],
            color: client.mode === "real" ? t.color.success[600] : t.color.primary[600],
            fontSize: t.fontSize[12],
            fontWeight: 600,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          {client.mode === "real" ? "真实分析读链路" : "本地演示数据"}
        </span>
      </header>

      <SectionLead
        eyebrow="Overview"
        title="环境概览"
        description="先看顶部环境 KPI，确认利率锚、风险资产、汇率与海外约束的当前方向，再进入判断与候选动作。"
      />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(280px, 360px)",
          gap: t.space[4],
          alignItems: "start",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: t.space[4], minWidth: 0 }}>
          <div
            data-testid="cross-asset-kpi-band"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: t.space[3],
            }}
          >
            {kpis.map((kpi) => (
              <MiniKpiCard key={kpi.key} kpi={kpi} />
            ))}
          </div>

          <SectionLead
            eyebrow="Core Read"
            title="判断、驱动与候选动作"
            description="这一层把市场判断、驱动拆解和候选动作并排组织，先形成结论，再下沉到执行候选。"
          />
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
              gap: t.space[3],
            }}
          >
            <div style={detailPanelStyle}>
              <h2
                style={{
                  margin: `0 0 ${t.space[3]}px`,
                  fontSize: t.fontSize[16],
                  fontWeight: 600,
                  color: t.color.neutral[900],
                }}
              >
                市场判断
              </h2>
              <p
                style={{
                  margin: 0,
                  color: t.color.neutral[700],
                  fontSize: t.fontSize[13],
                  lineHeight: t.lineHeight.relaxed,
                }}
              >
                {macroBondLinkageQuery.isLoading || latestQuery.isLoading
                  ? "加载联动分析…"
                  : env.signal_description ??
                    "暂无摘要文本：请结合上方 KPI 与驱动拆解阅读；若管线告警请先排查数据就绪情况。"}
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: t.space[2], marginTop: t.space[4] }}>
                <span
                  style={{
                    padding: `${t.space[1]}px ${t.space[3]}px`,
                    borderRadius: 999,
                    background: t.color.success[50],
                    color: t.color.success[600],
                    fontSize: t.fontSize[12],
                    fontWeight: 600,
                  }}
                >
                  主导因子：{envTags.primary}
                </span>
                <span
                  style={{
                    padding: `${t.space[1]}px ${t.space[3]}px`,
                    borderRadius: 999,
                    background: t.color.warning[50],
                    color: t.color.warning[600],
                    fontSize: t.fontSize[12],
                    fontWeight: 600,
                  }}
                >
                  次要扰动：{envTags.secondary}
                </span>
                <span
                  style={{
                    padding: `${t.space[1]}px ${t.space[3]}px`,
                    borderRadius: 999,
                    background: t.color.info[50],
                    color: t.color.info[600],
                    fontSize: t.fontSize[12],
                    fontWeight: 600,
                  }}
                >
                  风格判断：{envTags.style}
                </span>
              </div>
            </div>

            <div style={detailPanelStyle}>
              <h2
                style={{
                  margin: `0 0 ${t.space[3]}px`,
                  fontSize: t.fontSize[16],
                  fontWeight: 600,
                  color: t.color.neutral[900],
                }}
              >
                驱动拆解
              </h2>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                  gap: t.space[3],
                }}
              >
                {drivers.map((col) => {
                  const st = driverStanceStyle(col.tone);
                  return (
                    <div
                      key={col.title}
                      style={{
                        borderRadius: t.radius.md,
                        border: `1px solid ${t.color.neutral[100]}`,
                        padding: t.space[3],
                        background: t.color.neutral[50],
                        minHeight: 160,
                      }}
                    >
                      <div
                        style={{
                          fontSize: t.fontSize[12],
                          fontWeight: 600,
                          color: t.color.neutral[600],
                          marginBottom: t.space[2],
                        }}
                      >
                        {col.title}
                      </div>
                      <div
                        style={{
                          display: "inline-block",
                          padding: `2px ${t.space[2]}px`,
                          borderRadius: t.radius.sm,
                          fontSize: t.fontSize[12],
                          fontWeight: 700,
                          background: st.bg,
                          color: st.color,
                          marginBottom: t.space[2],
                        }}
                      >
                        {col.stance}
                      </div>
                      <ul
                        style={{
                          margin: 0,
                          paddingLeft: t.space[5],
                          color: t.color.neutral[700],
                          fontSize: t.fontSize[11],
                          lineHeight: t.lineHeight.normal,
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

          <SectionLead
            eyebrow="Observation"
            title="走势、事件与观察"
            description="在完成环境判断后，再看归一化走势、事件日历和观察清单，避免把事件噪音提前放到结论层。"
          />
          <div style={detailPanelStyle}>
            <h2
              style={{
                margin: `0 0 ${t.space[2]}px`,
                fontSize: t.fontSize[16],
                fontWeight: 600,
                color: t.color.neutral[900],
              }}
            >
              跨资产走势（近20日，统一基准 = 100）
            </h2>
            <p
              style={{
                margin: `0 0 ${t.space[2]}px`,
                color: t.color.neutral[500],
                fontSize: t.fontSize[12],
              }}
            >
              近 20 个交易日，统一归一到基准 = 100
            </p>
            {latestQuery.isLoading ? (
              <div
                style={{
                  height: 320,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: t.color.neutral[500],
                }}
              >
                加载宏观序列…
              </div>
            ) : trendOption ? (
              <ReactECharts option={trendOption} style={{ height: 320, width: "100%" }} notMerge lazyUpdate />
            ) : (
              <div style={{ height: 200, color: t.color.neutral[500], fontSize: t.fontSize[13] }}>
                缺少带历史点的序列，无法绘制联动图。
              </div>
            )}
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
              gap: t.space[3],
              alignItems: "start",
            }}
          >
            <CrossAssetEventCalendar />
            <WatchList />
          </div>

          <div style={{ ...detailPanelStyle, padding: t.space[5] }}>
            <h2
              style={{
                margin: `0 0 ${t.space[3]}px`,
                fontSize: t.fontSize[16],
                fontWeight: 600,
                color: t.color.neutral[900],
              }}
            >
              跨资产传导链（这页应该怎么用）
            </h2>
            <ol
              style={{
                margin: 0,
                paddingLeft: t.space[5],
                color: t.color.neutral[700],
                fontSize: t.fontSize[13],
                lineHeight: t.lineHeight.relaxed,
              }}
            >
              <li>先看顶部 KPI：利率锚、海外约束、风险资产与汇率是否同向。</li>
              <li>再看驱动拆解：流动性 / 海外 / 增长 / 通胀四象限是否互相抵消。</li>
              <li>最后结合估值分位与组合约束，落到久期、利差与对冲工具。</li>
            </ol>
            <p
              style={{
                margin: `${t.space[4]}px 0 0`,
                fontSize: t.fontSize[12],
                color: t.color.neutral[600],
                lineHeight: t.lineHeight.relaxed,
              }}
            >
              原则：跨资产信号只做环境标注与候选清单，执行仍需回缚到正式估值、限额与风控流程。
            </p>
          </div>

          <SectionLead
            eyebrow="Analytical"
            title="分析结果与输出"
            description="联动评分与组合影响继续保持 analytical 口径，并把页面输出与右侧热图放在同一证据层，避免误读为正式结果。"
          />
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
              <p style={{ color: t.color.neutral[600], fontSize: t.fontSize[14] }}>
                缺少可用的宏观最新交易日，无法计算联动。请稍后重试或检查市场数据管线。
              </p>
            ) : (
              <div style={{ display: "grid", gap: t.space[4] }}>
                {macroBondLinkageWarnings.length > 0 ? (
                  <ul
                    data-testid="cross-asset-linkage-warning-list"
                    style={{
                      margin: 0,
                      paddingLeft: t.space[5],
                      color: t.color.neutral[600],
                      fontSize: t.fontSize[13],
                      lineHeight: t.lineHeight.relaxed,
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
                    gap: t.space[3],
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
                  <h2
                    style={{
                      marginTop: 0,
                      marginBottom: t.space[2],
                      fontSize: t.fontSize[16],
                      fontWeight: 600,
                      color: t.color.neutral[900],
                    }}
                  >
                    组合影响估算
                  </h2>
                  <p
                    style={{
                      marginTop: 0,
                      color: t.color.neutral[600],
                      fontSize: t.fontSize[13],
                      lineHeight: t.lineHeight.relaxed,
                    }}
                  >
                    以下数值为 analytical estimate，不代表正式损益。
                  </p>
                  {hasPortfolioImpact ? (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                        gap: t.space[3],
                      }}
                    >
                      <div>
                        <div style={{ color: t.color.neutral[500], fontSize: t.fontSize[12] }}>rate change</div>
                        <div style={tabularNumsStyle}>
                          {formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_rate_change_bps, " bp")}
                        </div>
                      </div>
                      <div>
                        <div style={{ color: t.color.neutral[500], fontSize: t.fontSize[12] }}>spread widening</div>
                        <div style={tabularNumsStyle}>
                          {formatSignedNumber(
                            macroBondLinkage.portfolio_impact?.estimated_spread_widening_bps,
                            " bp",
                          )}
                        </div>
                      </div>
                      <div>
                        <div style={{ color: t.color.neutral[500], fontSize: t.fontSize[12] }}>total estimate</div>
                        <div style={tabularNumsStyle}>
                          {formatSignedNumber(macroBondLinkage.portfolio_impact?.total_estimated_impact)}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: t.color.neutral[500], fontSize: t.fontSize[14] }}>当前无组合影响估算。</div>
                  )}
                </section>
              </div>
            )}
          </AsyncSection>

          <PageOutput
            envTags={envTags}
            signalPreview={env.signal_description ?? null}
            linkageWarnings={macroBondLinkageWarnings}
            topCorrelationSummary={
              macroBondLinkage.top_correlations?.[0]
                ? `${macroBondLinkage.top_correlations[0].series_name} → ${macroBondLinkage.top_correlations[0].target_family}`
                : null
            }
          />
        </div>

        <aside
          style={{
            display: "flex",
            flexDirection: "column",
            gap: t.space[3],
            position: "sticky",
            top: t.space[4],
          }}
        >
          <div style={detailPanelStyle}>
            <h2
              style={{
                margin: `0 0 ${t.space[3]}px`,
                fontSize: t.fontSize[14],
                fontWeight: 600,
                color: t.color.neutral[900],
              }}
            >
              宏观—债市相关性（Top）
            </h2>
            <p
              style={{
                margin: `0 0 ${t.space[3]}px`,
                fontSize: t.fontSize[11],
                color: t.color.neutral[500],
                lineHeight: t.lineHeight.snug,
              }}
            >
              来源：联动分析接口返回的序列相关；列为滚动窗口 Pearson ρ，非估值分位。
            </p>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: t.fontSize[12] }}>
              <thead>
                <tr style={{ color: t.color.neutral[500], textAlign: "left" }}>
                  <th style={{ padding: `${t.space[2]}px ${t.space[1]}px`, fontWeight: 600 }}>指标</th>
                  <th style={{ padding: `${t.space[2]}px ${t.space[1]}px`, fontWeight: 600 }}>ρ(3M)</th>
                  <th style={{ padding: `${t.space[2]}px ${t.space[1]}px`, fontWeight: 600 }}>ρ(6M)</th>
                  <th style={{ padding: `${t.space[2]}px ${t.space[1]}px`, fontWeight: 600 }}>方向</th>
                </tr>
              </thead>
              <tbody>
                {heatmapRows.map((row) => (
                  <tr key={row.indicator} style={{ borderTop: `1px solid ${t.color.neutral[100]}` }}>
                    <td style={{ padding: `${t.space[2]}px ${t.space[1]}px`, color: t.color.neutral[800] }}>
                      {row.indicator}
                    </td>
                    <td
                      style={{
                        ...tabularNumsStyle,
                        padding: `${t.space[2]}px ${t.space[1]}px`,
                        color: t.color.neutral[900],
                        fontWeight: 600,
                      }}
                    >
                      {row.current}
                    </td>
                    <td
                      style={{
                        ...tabularNumsStyle,
                        padding: `${t.space[2]}px ${t.space[1]}px`,
                        color: t.color.neutral[600],
                      }}
                    >
                      {row.mid}
                    </td>
                    <td style={{ padding: `${t.space[2]}px ${t.space[1]}px`, color: evalColor[row.evalTone], fontWeight: 600 }}>
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
