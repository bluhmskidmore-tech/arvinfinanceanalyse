import { useEffect, useMemo, useState } from "react";
import { Card, Statistic, Row, Col, Alert, Select, Space } from "antd";
import { type EChartsOption } from "../../../lib/echarts";
import { BaseChart } from "../../../components/charts/BaseChart";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { FilterBar } from "../../../components/FilterBar";
import { useApiClient } from "../../../api/client";
import type { Numeric } from "../../../api/contracts";
import { bondNumericDisplay, bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { PeriodType, BenchmarkExcessResponse } from "../types";
import { designTokens, nocturneTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { formatBp, formatPct } from "../utils/formatters";
import {
  DetailEmptyNote,
  DetailLoadErrorAlert,
  DetailPanelSkeleton,
  formatDetailComputedAt,
} from "./BondAnalyticsDetailPrimitives";
import detailStyles from "./BondAnalyticsDetailPrimitives.module.css";
import { SectionLead } from "./SectionLead";

/* 2026-08-11 全站决议（DESIGN §4）：绿涨红跌。正效应/正超额=绿、负效应/负超额=红；
   色值收敛到 Nocturne 去饱和语义常量（§2.2），常量同时喂 ECharts canvas 与 DOM style。 */
const POSITIVE_CONTRIBUTION = nocturneTokens.color.green;
const NEGATIVE_CONTRIBUTION = nocturneTokens.color.red;
const CHART_ACCENT = nocturneTokens.color.blue;

interface Props {
  reportDate: string;
  periodType: PeriodType;
}

const BENCHMARK_OPTIONS = [
  { value: "TREASURY_INDEX", label: "中债国债总指数" },
  { value: "CDB_INDEX", label: "中债国开债总指数" },
  { value: "AAA_CREDIT_INDEX", label: "中债AAA信用债指数" },
];

const WATERFALL_CATEGORIES = [
  "久期效应",
  "曲线效应",
  "利差效应",
  "选券效应",
  "配置效应",
  "超额收益",
] as const;

const TRANSPARENT_BAR = {
  borderColor: "transparent",
  color: "transparent",
  borderWidth: 0,
} as const;

/**
 * 后端 benchmark-excess 载荷的数值字段实测为裸字符串（如 "3.69579661"，未经 Numeric
 * 归一化），直接取 `.display` 得 undefined、antd Statistic 兜底渲染成假「0」。
 * 统一经 bondNumericRaw 解析（兼容 Numeric 与字符串），缺失 —，展示收敛 2 位小数。
 */
function formatDurationCell(value: Numeric | string | null | undefined): string {
  const raw = bondNumericRaw(value);
  if (raw === null) return EM_DASH;
  return `${raw.toFixed(2)} 年`;
}

function hasDisplayMetric(value: Numeric | string | null | undefined): boolean {
  return bondNumericRaw(value) !== null;
}

/** 缺失效应项标签（瀑布断开 + 区头 partial 披露用），与 WATERFALL_CATEGORIES 前五项对齐。 */
function missingBenchmarkEffectLabels(d: BenchmarkExcessResponse): string[] {
  return [
    { label: "久期效应", value: d.duration_effect },
    { label: "曲线效应", value: d.curve_effect },
    { label: "利差效应", value: d.spread_effect },
    { label: "选券效应", value: d.selection_effect },
    { label: "配置效应", value: d.allocation_effect },
  ]
    .filter((item) => bondNumericRaw(item.value) === null)
    .map((item) => item.label);
}

function buildBenchmarkExcessWaterfallOption(d: BenchmarkExcessResponse): EChartsOption {
  const durationEffect = bondNumericRaw(d.duration_effect);
  const curveEffect = bondNumericRaw(d.curve_effect);
  const spreadEffect = bondNumericRaw(d.spread_effect);
  const selectionEffect = bondNumericRaw(d.selection_effect);
  const allocationEffect = bondNumericRaw(d.allocation_effect);
  const excessReturn = bondNumericRaw(d.excess_return);

  /* 缺失效应不再补 0 画假柱：保留 null，该柱断开，缺口在区头 partial 注记披露。 */
  const stepValues: Array<number | null> = [
    durationEffect,
    curveEffect,
    spreadEffect,
    selectionEffect,
    allocationEffect,
  ];

  const helperRaw: Array<number | null> = [];
  const valueRaw: Array<number | null> = [];
  const barColors: string[] = [];

  let running = 0;
  for (const v of stepValues) {
    if (v === null) {
      helperRaw.push(null);
      valueRaw.push(null);
      barColors.push("transparent");
      continue;
    }
    if (v >= 0) {
      helperRaw.push(running);
      valueRaw.push(v);
      barColors.push(POSITIVE_CONTRIBUTION);
      running += v;
    } else {
      helperRaw.push(running + v);
      valueRaw.push(-v);
      barColors.push(NEGATIVE_CONTRIBUTION);
      running += v;
    }
  }

  helperRaw.push(0);
  valueRaw.push(excessReturn);
  barColors.push(CHART_ACCENT);

  const displayStrings = [
    d.duration_effect.display,
    d.curve_effect.display,
    d.spread_effect.display,
    d.selection_effect.display,
    d.allocation_effect.display,
    d.excess_return.display,
  ];

  return nocturneChartTheme.createBarChartOption({
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items: unknown) => {
        const list = Array.isArray(items) ? items : [items];
        const bar = list.find((x: { seriesName?: string }) => x.seriesName === "效应");
        const idx = (bar as { dataIndex?: number })?.dataIndex ?? 0;
        const label = WATERFALL_CATEGORIES[idx];
        return `${label}<br/>${displayStrings[idx] ?? EM_DASH}`;
      },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 32, containLabel: true },
    xAxis: {
      type: "category",
      data: [...WATERFALL_CATEGORIES],
      axisLabel: { ...nocturneChartTheme.axisLabel, interval: 0, rotate: 0 },
    },
    yAxis: {
      type: "value",
      axisLabel: {
        ...nocturneChartTheme.axisLabel,
        formatter: (value: number) => `${value} bp`,
      },
    },
    legend: { show: false },
    series: [
      {
        name: "辅助",
        type: "bar",
        stack: "waterfall",
        silent: true,
        itemStyle: TRANSPARENT_BAR,
        emphasis: { itemStyle: TRANSPARENT_BAR },
        data: helperRaw,
      },
      {
        name: "效应",
        type: "bar",
        stack: "waterfall",
        data: valueRaw.map((val, i) => ({
          value: val,
          itemStyle: { color: barColors[i] },
        })),
      },
    ],
  });
}

export function BenchmarkExcessView({ reportDate, periodType }: Props) {
  const client = useApiClient();
  const [data, setData] = useState<BenchmarkExcessResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [benchmarkId, setBenchmarkId] = useState("CDB_INDEX");

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const envelope = await client.getBondAnalyticsBenchmarkExcess(
          reportDate,
          periodType,
          benchmarkId,
        );
        if (!cancelled) setData(envelope.result);
      } catch (e: unknown) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    if (reportDate) fetchData();
    return () => {
      cancelled = true;
    };
  }, [benchmarkId, client, periodType, reportDate]);

  const waterfallOption = useMemo(
    () => {
      if (!data) return null;
      const hasSeries = [
        data.duration_effect,
        data.curve_effect,
        data.spread_effect,
        data.selection_effect,
        data.allocation_effect,
        data.excess_return,
      ].some((value) => bondNumericRaw(value) !== null);
      return hasSeries ? buildBenchmarkExcessWaterfallOption(data) : null;
    },
    [data],
  );

  if (loading) return <DetailPanelSkeleton testId="benchmark-excess-loading" />;
  if (error) return <DetailLoadErrorAlert error={error} testId="benchmark-excess-error" />;
  if (!data) return null;

  const excessNum = bondNumericRaw(data.excess_return);
  const excessColor =
    excessNum === null ? nocturneTokens.color.ink : excessNum >= 0 ? POSITIVE_CONTRIBUTION : NEGATIVE_CONTRIBUTION;

  /* 组合/基准/差三项久期同时严格为 0 是后端缺失补零的占位形态（真实组合久期不可能
     恰为 0 且与驾驶舱读数矛盾）：按缺值 — 处理并显式注记，不当真零展示。 */
  const durationAllZero =
    [data.portfolio_duration, data.benchmark_duration, data.duration_diff].every(
      (value) => bondNumericRaw(value) === 0,
    );
  const durationCell = (value: Numeric): string =>
    durationAllZero ? EM_DASH : formatDurationCell(value);

  const missingEffects = missingBenchmarkEffectLabels(data);

  const decomp = [
    { label: "久期效应", value: data.duration_effect },
    { label: "曲线效应", value: data.curve_effect },
    { label: "利差效应", value: data.spread_effect },
    { label: "选券效应", value: data.selection_effect },
    { label: "配置效应", value: data.allocation_effect },
  ];

  const hasRiskMetrics =
    hasDisplayMetric(data.tracking_error) ||
    hasDisplayMetric(data.information_ratio);

  return (
    <div className={detailStyles.view}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: designTokens.space[2],
        }}
      >
        <Space direction="vertical" size={designTokens.space[1]}>
          <SectionLead
            eyebrow="基准"
            title="基准超额收益"
            description="按报告日、期间和基准指数读取后端归因结果；页面只展示基准超额读模型，不在前端重算超额收益。"
            testId="benchmark-excess-shell-lead"
          />
          <span style={{ color: "var(--dh-api-soft)", fontSize: designTokens.fontSize[13] }}>
            {data.benchmark_name ? `基准：${data.benchmark_name}` : null}
          </span>
          <span style={{ color: "var(--dh-api-muted)", fontSize: designTokens.fontSize[12] }}>
            区间 {data.period_start} — {data.period_end} · 报表日 {data.report_date}
          </span>
        </Space>
        <FilterBar>
          <span style={{ color: "var(--dh-api-soft)", fontSize: designTokens.fontSize[13] }}>切换基准</span>
          <Select
            value={benchmarkId}
            onChange={setBenchmarkId}
            options={BENCHMARK_OPTIONS}
            style={{ width: 200 }}
            size="small"
            getPopupContainer={(trigger) => trigger.parentElement ?? document.body}
          />
        </FilterBar>
      </div>

      <SectionLead
        eyebrow="汇总"
        title="组合与基准摘要"
        description="先阅读组合收益、基准收益、超额收益和久期差，再进入下方效果分解和来源明细。"
        testId="benchmark-excess-summary-lead"
      />
      <Row gutter={[12, 12]} className={detailStyles.kpiGrid}>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="组合收益" value={formatPct(data.portfolio_return)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="基准收益" value={formatPct(data.benchmark_return)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic
              title="超额收益"
              value={formatBp(data.excess_return)}
              valueStyle={{ color: excessColor }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="组合久期" value={durationCell(data.portfolio_duration)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="基准久期" value={durationCell(data.benchmark_duration)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="久期差" value={durationCell(data.duration_diff)} />
          </Card>
        </Col>
      </Row>
      {durationAllZero ? (
        <div
          data-testid="benchmark-excess-duration-gap-note"
          style={{ fontSize: designTokens.fontSize[12], color: "var(--dh-api-amber)" }}
        >
          久期读数未返回：组合久期、基准久期与久期差按 — 展示（后端本次返回全 0 占位，不作真实久期）。
        </div>
      ) : null}

      {hasRiskMetrics && (
        <Row gutter={[12, 12]} className={detailStyles.kpiGrid}>
          {hasDisplayMetric(data.tracking_error) && (
            <Col xs={24} sm={12} md={8}>
              <Card size="small">
                <Statistic title="跟踪误差" value={formatPct(data.tracking_error)} />
              </Card>
            </Col>
          )}
          {hasDisplayMetric(data.information_ratio) && (
            <Col xs={24} sm={12} md={8}>
              <Card size="small">
                <Statistic title="信息比率" value={bondNumericDisplay(data.information_ratio)} />
              </Card>
            </Col>
          )}
        </Row>
      )}

      <SectionLead
        eyebrow="归因"
        title="超额收益归因"
        description="分解、对账和来源明细沿用后端返回字段，保留解释项与对账差异的边界。"
        testId="benchmark-excess-attribution-lead"
      />
      {missingEffects.length > 0 ? (
        <div
          data-testid="benchmark-excess-partial-note"
          style={{ fontSize: designTokens.fontSize[12], color: "var(--dh-api-amber)" }}
        >
          归因部分缺失：{missingEffects.join(" / ")} 未返回，瀑布图对应柱断开，不补 0。
        </div>
      ) : null}
      <Card title="超额收益分解" size="small">
        <div className={detailStyles.effectGrid}>
          {decomp.map((d) => {
            const num = bondNumericRaw(d.value);
            const color =
              num === null ? nocturneTokens.color.ink : num >= 0 ? POSITIVE_CONTRIBUTION : NEGATIVE_CONTRIBUTION;
            return (
              <div key={d.label} className={detailStyles.effectMetric}>
                <div className={detailStyles.effectLabel}>{d.label}</div>
                <div
                  className={detailStyles.effectValue}
                  style={{
                    color,
                  }}
                >
                  {formatBp(d.value)}
                </div>
              </div>
            );
          })}
        </div>
        {waterfallOption ? (
          <div className={detailStyles.chartStage}>
            <BaseChart option={waterfallOption} height={280} />
          </div>
        ) : (
          <DetailEmptyNote testId="benchmark-excess-chart-empty">
            暂无超额收益归因序列
          </DetailEmptyNote>
        )}
      </Card>

      <Card title="超额归因对账" size="small">
        <Row gutter={16}>
          <Col span={12}>
            <Statistic title="可解释超额" value={formatBp(data.explained_excess)} />
          </Col>
          <Col span={12}>
            <Statistic title="对账残差" value={formatBp(data.recon_error)} />
          </Col>
        </Row>
        {/* 口径依据 backend/app/core_finance/bond_analytics/read_models.py：selection_effect 为
            配平残差（plug），explained_excess 因而与超额收益恒等闭合；recon_error 为剔除该配平项
            后的未解释残差（数值上等于选券效应），故可大于可解释超额，不代表对账错误。 */}
        <div
          data-testid="benchmark-excess-recon-basis-note"
          style={{
            marginTop: designTokens.space[2],
            fontSize: designTokens.fontSize[12],
            color: "var(--dh-api-muted)",
          }}
        >
          口径：可解释超额含选券配平项，与超额收益恒等闭合；对账残差为剔除选券配平后的未解释部分（数值上等于选券效应），可大于可解释超额。
        </div>
      </Card>

      <Card title="超额来源明细" size="small">
        {data.excess_sources && data.excess_sources.length > 0 ? (
          data.excess_sources.map((s) => (
            <div
              key={s.source}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 4,
                padding: "8px 0",
                borderBottom: "1px solid var(--dh-api-line-soft)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <span>{s.source}</span>
                <span style={tabularNumsStyle}>{formatBp(s.contribution)}</span>
              </div>
              {s.description ? (
                <span style={{ fontSize: designTokens.fontSize[12], color: "var(--dh-api-muted)" }}>
                  {s.description}
                </span>
              ) : null}
            </div>
          ))
        ) : (
          <DetailEmptyNote testId="benchmark-excess-sources-empty">
            暂无超额来源明细
          </DetailEmptyNote>
        )}
      </Card>

      {data.warnings.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message="提示"
          description={data.warnings.map((w, i) => (
            <div key={i}>{w}</div>
          ))}
        />
      )}

      {data.computed_at ? (
        <div style={{ fontSize: designTokens.fontSize[12], color: "var(--dh-api-muted)" }}>
          计算时间：{formatDetailComputedAt(data.computed_at)}
        </div>
      ) : null}
    </div>
  );
}
