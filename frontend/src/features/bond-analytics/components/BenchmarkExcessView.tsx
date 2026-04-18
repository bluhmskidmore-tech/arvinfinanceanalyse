import { useEffect, useMemo, useState } from "react";
import { Card, Statistic, Row, Col, Alert, Spin, Select, Space } from "antd";
import ReactECharts from "../../../lib/echarts";
import { FilterBar } from "../../../components/FilterBar";
import { useApiClient } from "../../../api/client";
import type { Numeric } from "../../../api/contracts";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { PeriodType, BenchmarkExcessResponse } from "../types";
import { formatBp, formatPct } from "../utils/formatters";
import { SectionLead } from "./SectionLead";

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

const CHART_TEXT = { fontSize: 13, color: "#5c6b82" } as const;

const TRANSPARENT_BAR = {
  borderColor: "transparent",
  color: "rgba(0,0,0,0)",
  borderWidth: 0,
} as const;

function formatDurationDisplay(value: Numeric): string {
  return value.display;
}

function hasDisplayMetric(value: Numeric | null | undefined): value is Numeric {
  return value != null && value.display !== "";
}

function buildBenchmarkExcessWaterfallOption(d: BenchmarkExcessResponse) {
  const durationEffect = bondNumericRaw(d.duration_effect);
  const curveEffect = bondNumericRaw(d.curve_effect);
  const spreadEffect = bondNumericRaw(d.spread_effect);
  const selectionEffect = bondNumericRaw(d.selection_effect);
  const allocationEffect = bondNumericRaw(d.allocation_effect);
  const excessReturn = bondNumericRaw(d.excess_return);

  const stepValues = [
    durationEffect,
    curveEffect,
    spreadEffect,
    selectionEffect,
    allocationEffect,
  ].map((v) => (Number.isFinite(v) ? v : 0));

  const helperRaw: number[] = [];
  const valueRaw: number[] = [];
  const barColors: string[] = [];

  let running = 0;
  for (const v of stepValues) {
    if (v >= 0) {
      helperRaw.push(running);
      valueRaw.push(v);
      barColors.push("#cf1322");
      running += v;
    } else {
      helperRaw.push(running + v);
      valueRaw.push(-v);
      barColors.push("#3f8600");
      running += v;
    }
  }

  helperRaw.push(0);
  valueRaw.push(Number.isFinite(excessReturn) ? excessReturn : 0);
  barColors.push("#1f5eff");

  const displayStrings = [
    d.duration_effect.display,
    d.curve_effect.display,
    d.spread_effect.display,
    d.selection_effect.display,
    d.allocation_effect.display,
    d.excess_return.display,
  ];

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      textStyle: CHART_TEXT,
      formatter: (items: unknown) => {
        const list = Array.isArray(items) ? items : [items];
        const bar = list.find((x: { seriesName?: string }) => x.seriesName === "效应");
        const idx = (bar as { dataIndex?: number })?.dataIndex ?? 0;
        const label = WATERFALL_CATEGORIES[idx];
        return `${label}<br/>${displayStrings[idx] ?? "—"}`;
      },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 32, containLabel: true },
    xAxis: {
      type: "category",
      data: [...WATERFALL_CATEGORIES],
      axisLabel: { interval: 0, rotate: 0, ...CHART_TEXT },
    },
    yAxis: {
      type: "value",
      axisLabel: CHART_TEXT,
    },
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
  };
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
    () => (data ? buildBenchmarkExcessWaterfallOption(data) : null),
    [data],
  );

  if (loading) return <Spin style={{ display: "block", margin: "40px auto" }} />;
  if (error) return <Alert type="error" message={`加载失败：${error}`} />;
  if (!data) return null;

  const excessNum = bondNumericRaw(data.excess_return);
  const excessColor = excessNum >= 0 ? "#cf1322" : "#3f8600";

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
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <Space direction="vertical" size={4}>
          <SectionLead
            eyebrow="Benchmark"
            title="基准超额收益"
            description="按报告日、期间和基准指数读取后端归因结果；页面只展示 benchmark excess read model，不在前端重算超额收益。"
            testId="benchmark-excess-shell-lead"
          />
          <span style={{ color: "#5c6b82", fontSize: 13 }}>
            {data.benchmark_name ? `基准：${data.benchmark_name}` : null}
          </span>
          <span style={{ color: "#8090a8", fontSize: 12 }}>
            区间 {data.period_start} — {data.period_end} · 报表日 {data.report_date}
          </span>
        </Space>
        <FilterBar>
          <span style={{ color: "#5c6b82", fontSize: 13 }}>切换基准</span>
          <Select
            value={benchmarkId}
            onChange={setBenchmarkId}
            options={BENCHMARK_OPTIONS}
            style={{ width: 200 }}
            size="small"
          />
        </FilterBar>
      </div>

      <SectionLead
        eyebrow="Summary"
        title="组合与基准摘要"
        description="先阅读组合收益、基准收益、超额收益和久期差，再进入下方效果分解和来源明细。"
        testId="benchmark-excess-summary-lead"
      />
      <Row gutter={16}>
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
            <Statistic title="组合久期" value={formatDurationDisplay(data.portfolio_duration)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="基准久期" value={formatDurationDisplay(data.benchmark_duration)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            <Statistic title="久期差" value={formatDurationDisplay(data.duration_diff)} />
          </Card>
        </Col>
      </Row>

      {hasRiskMetrics && (
        <Row gutter={16}>
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
                <Statistic title="信息比率" value={data.information_ratio.display} />
              </Card>
            </Col>
          )}
        </Row>
      )}

      <SectionLead
        eyebrow="Attribution"
        title="超额收益归因"
        description="分解、对账和来源明细沿用后端返回字段，保留解释项与 recon_error 的边界。"
        testId="benchmark-excess-attribution-lead"
      />
      <Card title="超额收益分解" size="small">
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {decomp.map((d) => {
            const num = bondNumericRaw(d.value);
            const color = num >= 0 ? "#cf1322" : "#3f8600";
            return (
              <div key={d.label} style={{ textAlign: "center", minWidth: 100 }}>
                <div style={{ fontSize: 12, color: "#8090a8" }}>{d.label}</div>
                <div
                  style={{
                    fontSize: 18,
                    fontWeight: 600,
                    color,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {formatBp(d.value)}
                </div>
              </div>
            );
          })}
        </div>
        {waterfallOption && (
          <div style={{ marginTop: 16 }}>
            <ReactECharts
              option={waterfallOption}
              style={{ height: 280, width: "100%" }}
              opts={{ renderer: "canvas" }}
            />
          </div>
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
      </Card>

      {data.excess_sources && data.excess_sources.length > 0 && (
        <Card title="超额来源明细" size="small">
          {data.excess_sources.map((s) => (
            <div
              key={s.source}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 4,
                padding: "8px 0",
                borderBottom: "1px solid rgba(0,0,0,0.06)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <span>{s.source}</span>
                <span style={{ fontVariantNumeric: "tabular-nums" }}>{formatBp(s.contribution)}</span>
              </div>
              {s.description ? (
                <span style={{ fontSize: 12, color: "#8090a8" }}>{s.description}</span>
              ) : null}
            </div>
          ))}
        </Card>
      )}

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
        <div style={{ fontSize: 12, color: "#8090a8" }}>计算时间：{data.computed_at}</div>
      ) : null}
    </div>
  );
}
