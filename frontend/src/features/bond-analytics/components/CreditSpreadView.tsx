import { useEffect, useMemo, useState } from "react";
import { Card, Statistic, Row, Col, Table, Alert, Spin } from "antd";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { useApiClient } from "../../../api/client";
import type {
  CreditSpreadAnalysisResponse,
  CreditSpreadDetailBondRow,
  ConcentrationMetrics,
  CreditSpreadBondDetailRow,
  CreditSpreadMigrationResponse,
} from "../types";
import { formatWan, formatBp } from "../utils/formatters";

interface Props {
  reportDate: string;
}

const spreadColumns = [
  { title: "情景", dataIndex: "scenario_name", key: "scenario_name" },
  { title: "利差变动 (bp)", dataIndex: "spread_change_bp", key: "spread_change_bp" },
  { title: "总影响", dataIndex: "pnl_impact", key: "pnl_impact", render: formatWan },
  { title: "OCI影响", dataIndex: "oci_impact", key: "oci_impact", render: formatWan },
  { title: "TPL影响", dataIndex: "tpl_impact", key: "tpl_impact", render: formatWan },
];

const migrationColumns = [
  { title: "情景", dataIndex: "scenario_name", key: "scenario_name" },
  { title: "原评级", dataIndex: "from_rating", key: "from_rating" },
  { title: "目标评级", dataIndex: "to_rating", key: "to_rating" },
  { title: "涉及债券", dataIndex: "affected_bonds", key: "affected_bonds" },
  { title: "涉及市值", dataIndex: "affected_market_value", key: "affected_market_value", render: formatWan },
  { title: "损益影响", dataIndex: "pnl_impact", key: "pnl_impact", render: formatWan },
];

const issuerConcentrationColumns = [
  { title: "名称", dataIndex: "name", key: "name" },
  { title: "权重", dataIndex: "weight", key: "weight" },
  { title: "市值", dataIndex: "market_value", key: "market_value", render: formatWan },
];

const spreadDetailColumns = [
  { title: "债券代码", dataIndex: "instrument_code", key: "instrument_code" },
  { title: "债券名称", dataIndex: "instrument_name", key: "instrument_name" },
  { title: "评级", dataIndex: "rating", key: "rating" },
  { title: "期限桶", dataIndex: "tenor_bucket", key: "tenor_bucket" },
  {
    title: "YTM",
    dataIndex: "ytm",
    key: "ytm",
    render: (value: string) => formatPctPoint(value),
  },
  {
    title: "国债基准",
    dataIndex: "benchmark_yield",
    key: "benchmark_yield",
    render: (value: string) => formatPctPoint(value),
  },
  {
    title: "利差",
    dataIndex: "credit_spread",
    key: "credit_spread",
    render: (value: string) => formatBp(value),
  },
  {
    title: "市值",
    dataIndex: "market_value",
    key: "market_value",
    render: formatWan,
  },
];

const CONCENTRATION_KEYS = [
  "concentration_by_issuer",
  "concentration_by_industry",
  "concentration_by_rating",
  "concentration_by_tenor",
] as const satisfies readonly (keyof Pick<
  CreditSpreadMigrationResponse,
  | "concentration_by_issuer"
  | "concentration_by_industry"
  | "concentration_by_rating"
  | "concentration_by_tenor"
>)[];

function hasAnyConcentrationField(data: CreditSpreadMigrationResponse): boolean {
  return CONCENTRATION_KEYS.some((k) => data[k] != null);
}

/** X 轴期限桶（与后端 tenor_bucket 对齐后映射到此顺序） */
const CREDIT_DIST_TENOR_LABELS = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"] as const;

/** Y 轴评级桶 */
const CREDIT_DIST_RATING_LABELS = ["AAA", "AA+", "AA", "AA-", "A+", "其他"] as const;

const PRIMARY_RATING_SET = new Set<string>(CREDIT_DIST_RATING_LABELS.filter((r) => r !== "其他"));

function mapTenorBucketToXIndex(raw: string | undefined): number | null {
  if (raw == null || String(raw).trim() === "") return null;
  const t = String(raw).trim().toUpperCase();
  const table: Record<string, number> = {
    "1M": 0,
    "3M": 0,
    "6M": 0,
    "9M": 0,
    "1Y": 0,
    "2Y": 1,
    "3Y": 2,
    "4Y": 2,
    "5Y": 3,
    "6Y": 3,
    "7Y": 4,
    "10Y": 5,
    "15Y": 5,
    "20Y": 6,
    "30Y": 7,
  };
  const idx = table[t];
  return idx === undefined ? null : idx;
}

function mapRatingToBucket(raw: string | undefined): string | null {
  if (raw == null || String(raw).trim() === "") return null;
  const up = String(raw).trim().toUpperCase();
  if (PRIMARY_RATING_SET.has(up)) return up;
  return "其他";
}

/** 将 bond 明细按评级×期限累加市值，再按信用债总市值换算占比（仅展示层聚合） */
function buildRatingTenorHeatmapData(
  bondDetails: CreditSpreadBondDetailRow[],
  creditMarketValueStr: string,
): { seriesData: [number, number, number][]; maxPct: number } | null {
  const denom = parseFloat(creditMarketValueStr);
  if (!Number.isFinite(denom) || denom <= 0) return null;

  const sums = new Map<string, number>();
  let anyMapped = false;
  for (const row of bondDetails) {
    const yKey = mapRatingToBucket(row.rating);
    const xi = mapTenorBucketToXIndex(row.tenor_bucket);
    if (yKey == null || xi == null) continue;
    const mv = parseFloat(row.market_value);
    if (!Number.isFinite(mv) || mv <= 0) continue;
    anyMapped = true;
    const key = `${yKey}|${xi}`;
    sums.set(key, (sums.get(key) ?? 0) + mv);
  }
  if (!anyMapped) return null;

  const seriesData: [number, number, number][] = [];
  let maxPct = 0;
  for (let yi = 0; yi < CREDIT_DIST_RATING_LABELS.length; yi++) {
    const rating = CREDIT_DIST_RATING_LABELS[yi];
    for (let xi = 0; xi < CREDIT_DIST_TENOR_LABELS.length; xi++) {
      const v = sums.get(`${rating}|${xi}`) ?? 0;
      const pct = (v / denom) * 100;
      if (pct > maxPct) maxPct = pct;
      seriesData.push([xi, yi, Number(pct.toFixed(4))]);
    }
  }
  if (maxPct <= 0) return null;
  return { seriesData, maxPct };
}

function formatPctPoint(value: string | null | undefined): string {
  const num = parseFloat(String(value ?? ""));
  if (!Number.isFinite(num)) return "-";
  return `${num.toFixed(2)}%`;
}

function formatPercentile(value: string | null | undefined): string {
  const num = parseFloat(String(value ?? ""));
  if (!Number.isFinite(num)) return "-";
  return `${num.toFixed(1)}%`;
}

function formatBpOrDash(value: string | null | undefined): string {
  return value == null ? "-" : formatBp(value);
}

function spreadTermStructureOption(
  points: CreditSpreadAnalysisResponse["spread_term_structure"],
): EChartsOption | null {
  if (!points.length) return null;
  return {
    grid: { left: 48, right: 16, top: 24, bottom: 28, containLabel: false },
    tooltip: { trigger: "axis" },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: {
      type: "category",
      data: points.map((point) => point.tenor_bucket),
      axisLabel: { color: "#5c6b82", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#5c6b82", fontSize: 11, formatter: "{value} bp" },
      splitLine: { lineStyle: { type: "dashed", opacity: 0.35 } },
    },
    series: [
      {
        name: "平均",
        type: "line",
        smooth: true,
        data: points.map((point) => Number(point.avg_spread_bps)),
        itemStyle: { color: "#1f5eff" },
        lineStyle: { width: 2 },
      },
      {
        name: "最小",
        type: "line",
        data: points.map((point) => Number(point.min_spread_bps)),
        itemStyle: { color: "#2f8f63" },
        lineStyle: { type: "dashed" },
      },
      {
        name: "最大",
        type: "line",
        data: points.map((point) => Number(point.max_spread_bps)),
        itemStyle: { color: "#ff7a45" },
        lineStyle: { type: "dashed" },
      },
    ],
  };
}

function concentrationBarOption(
  metrics: ConcentrationMetrics | undefined,
  color: string,
  yAxisName: string,
): EChartsOption | null {
  const items = metrics?.top_items;
  if (!items?.length) return null;
  const names = items.map((it) => it.name);
  const pcts = items.map((it) => {
    const w = parseFloat(it.weight);
    return Number.isFinite(w) ? Number((w * 100).toFixed(4)) : 0;
  });
  return {
    grid: { left: 48, right: 12, top: 28, bottom: names.some((n) => n.length > 6) ? 52 : 36, containLabel: false },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params];
        const p = list[0] as { name?: string; value?: number };
        return `${p.name ?? ""}<br/>${yAxisName}：${p.value ?? 0}%`;
      },
    },
    xAxis: {
      type: "category",
      data: names,
      axisLabel: { color: "#5c6b82", fontSize: 11, interval: 0, rotate: names.length > 5 ? 28 : 0 },
    },
    yAxis: {
      type: "value",
      name: yAxisName,
      nameTextStyle: { color: "#8c8c8c", fontSize: 11 },
      axisLabel: { color: "#5c6b82", fontSize: 11, formatter: "{value}%" },
      splitLine: { lineStyle: { type: "dashed", opacity: 0.35 } },
    },
    series: [
      {
        type: "bar",
        name: yAxisName,
        barMaxWidth: 40,
        itemStyle: { color },
        data: pcts,
      },
    ],
  };
}

function ratingTenorHeatmapOption(seriesData: [number, number, number][], maxPct: number): EChartsOption {
  const vmax = Math.max(maxPct, 1e-6);
  return {
    tooltip: {
      position: "top",
      formatter: (raw: unknown) => {
        const p = raw as { value?: [number, number, number] | number };
        const val = Array.isArray(p.value) ? p.value : [];
        const xi = Number(val[0]);
        const yi = Number(val[1]);
        const v = Number(val[2]);
        const tenor = CREDIT_DIST_TENOR_LABELS[xi] ?? "";
        const rating = CREDIT_DIST_RATING_LABELS[yi] ?? "";
        return `${rating} × ${tenor}<br/>市值占比：${Number.isFinite(v) ? v.toFixed(2) : "—"}%`;
      },
    },
    grid: { left: 56, right: 24, top: 16, bottom: 56, containLabel: true },
    xAxis: {
      type: "category",
      data: [...CREDIT_DIST_TENOR_LABELS],
      splitArea: { show: true },
      axisLabel: { color: "#5c6b82", fontSize: 11 },
    },
    yAxis: {
      type: "category",
      data: [...CREDIT_DIST_RATING_LABELS],
      splitArea: { show: true },
      axisLabel: { color: "#5c6b82", fontSize: 11 },
    },
    visualMap: {
      min: 0,
      max: vmax,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 4,
      itemWidth: 12,
      itemHeight: 120,
      inRange: { color: ["#dfe8ff", "#1f5eff"] },
      textStyle: { fontSize: 11, color: "#5c6b82" },
      formatter: (v: number) => `${v.toFixed(1)}%`,
    },
    series: [
      {
        type: "heatmap",
        data: seriesData,
        label: {
          show: true,
          fontSize: 10,
          color: "#262626",
          formatter: (params: { value?: [number, number, number] }) => {
            const v = params.value?.[2];
            if (v == null || v === 0) return "";
            return v < 0.05 ? "" : `${v.toFixed(1)}%`;
          },
        },
        emphasis: {
          itemStyle: { shadowBlur: 8, shadowColor: "rgba(0, 0, 0, 0.12)" },
        },
      },
    ],
  };
}

const ISSUER_SLICE_COLORS = ["#1f5eff", "#ff7a45", "#2f8f63", "#cc7a1a", "#8c8c8c"];

function concentrationPieOption(metrics: ConcentrationMetrics): EChartsOption {
  return {
    title: {
      text: `${metrics.dimension}  HHI ${metrics.hhi}  Top5 ${metrics.top5_concentration}`,
      left: "center",
      top: 4,
      textStyle: { fontSize: 11 },
    },
    tooltip: {
      trigger: "item",
      formatter: (p) => {
        const item = p as { name: string; value: number; percent: number };
        return `${item.name}: ${formatWan(String(item.value))} (${item.percent}%)`;
      },
    },
    series: [
      {
        type: "pie",
        radius: "55%",
        center: ["50%", "56%"],
        data: metrics.top_items.map((it) => ({
          name: it.name,
          value: parseFloat(it.market_value) || 0,
        })),
      },
    ],
  };
}

function buildIssuerConcentrationPieOption(metrics: ConcentrationMetrics): EChartsOption {
  const pieData = metrics.top_items.map((it, idx) => ({
    name: it.name,
    value: parseFloat(it.market_value) || 0,
    marketValueRaw: it.market_value,
    weight: it.weight,
    itemStyle: { color: ISSUER_SLICE_COLORS[idx % ISSUER_SLICE_COLORS.length] },
  }));

  return {
    tooltip: {
      trigger: "item" as const,
      formatter: (params: { data?: { name: string; marketValueRaw: string; weight: string } }) => {
        const d = params.data;
        if (!d) return "";
        return `${d.name}<br/>市值：${formatWan(d.marketValueRaw)}<br/>权重：${d.weight}`;
      },
    },
    graphic: {
      elements: [
        {
          type: "text" as const,
          left: "center",
          top: "center",
          style: {
            text: "发行人集中度",
            textAlign: "center" as const,
            fill: "#262626",
            fontSize: 14,
            fontWeight: 500,
          },
        },
      ],
    },
    series: [
      {
        type: "pie" as const,
        radius: ["42%", "68%"],
        center: ["50%", "50%"],
        avoidLabelOverlap: true,
        label: {
          show: true,
          formatter: "{b}: {d}%",
        },
        data: pieData,
      },
    ],
  };
}

function ConcentrationPieCell({ metrics }: { metrics: ConcentrationMetrics | undefined }) {
  const option = useMemo(() => {
    if (!metrics?.top_items?.length) return null;
    return concentrationPieOption(metrics);
  }, [metrics]);

  if (!option) {
    return (
      <div
        style={{
          height: 200,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "rgba(0,0,0,0.45)",
        }}
      >
        暂无数据
      </div>
    );
  }

  return <ReactECharts option={option} style={{ height: 200 }} />;
}

export function CreditSpreadView({ reportDate }: Props) {
  const client = useApiClient();
  const [summaryData, setSummaryData] = useState<CreditSpreadMigrationResponse | null>(null);
  const [detailData, setDetailData] = useState<CreditSpreadAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      setDetailError(null);
      try {
        const [summaryResult, detailResult] = await Promise.allSettled([
          client.getBondAnalyticsCreditSpreadMigration(reportDate),
          client.getCreditSpreadAnalysisDetail(reportDate),
        ]);

        if (cancelled) {
          return;
        }

        if (summaryResult.status === "rejected") {
          throw summaryResult.reason;
        }

        setSummaryData(summaryResult.value.result);
        if (detailResult.status === "fulfilled") {
          setDetailData(detailResult.value.result);
        } else {
          setDetailData(null);
          setDetailError(
            detailResult.reason instanceof Error ? detailResult.reason.message : "unknown error",
          );
        }
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
  }, [client, reportDate]);

  const data = summaryData;

  const spreadChartOption = useMemo((): EChartsOption | null => {
    if (!data?.spread_scenarios?.length) return null;
    const scenarios = data.spread_scenarios;
    return {
      grid: { left: 52, right: 16, top: 24, bottom: 28, containLabel: false },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: unknown) => {
          const list = Array.isArray(params) ? params : [params];
          const p = list[0] as {
            name?: string;
            value?: number | { value: number };
            data?: { value?: number };
          };
          const name = p?.name ?? "";
          const raw = p?.value ?? p?.data?.value;
          const num =
            typeof raw === "object" && raw !== null && "value" in raw
              ? (raw as { value: number }).value
              : Number(raw);
          return `${name}<br/>损益影响：${formatWan(String(num))}`;
        },
      },
      xAxis: {
        type: "category",
        data: scenarios.map((s) => s.scenario_name),
        axisLabel: { color: "#5c6b82", fontSize: 11, interval: 0, rotate: 15 },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#5c6b82", fontSize: 11 },
        splitLine: { lineStyle: { type: "dashed", opacity: 0.35 } },
      },
      series: [
        {
          type: "bar",
          name: "损益影响",
          barMaxWidth: 48,
          data: scenarios.map((s) => {
            const v = parseFloat(s.pnl_impact);
            return {
              value: Number.isFinite(v) ? v : 0,
              itemStyle: { color: v >= 0 ? "#cf1322" : "#3f8600" },
            };
          }),
        },
      ],
    };
  }, [data]);

  const issuerConcentrationPieOption = useMemo((): EChartsOption | null => {
    if (!data?.concentration_by_issuer?.top_items?.length) return null;
    return buildIssuerConcentrationPieOption(data.concentration_by_issuer);
  }, [data]);

  const termStructureOption = useMemo(
    () => spreadTermStructureOption(detailData?.spread_term_structure ?? []),
    [detailData],
  );

  const creditDistributionView = useMemo(() => {
    if (!data) return { kind: "empty" as const };
    const heat =
      data.bond_details && data.bond_details.length > 0
        ? buildRatingTenorHeatmapData(data.bond_details, data.credit_market_value)
        : null;
    if (heat) {
      return {
        kind: "heatmap" as const,
        option: ratingTenorHeatmapOption(heat.seriesData, heat.maxPct),
      };
    }
    const ratingOpt = concentrationBarOption(data.concentration_by_rating, "#1f5eff", "市值占比");
    const tenorOpt = concentrationBarOption(data.concentration_by_tenor, "#ff7a45", "市值占比");
    if (ratingOpt || tenorOpt) {
      return { kind: "bars" as const, ratingOption: ratingOpt, tenorOption: tenorOpt };
    }
    return { kind: "empty" as const };
  }, [data]);

  if (loading) return <Spin style={{ display: "block", margin: "40px auto" }} />;
  if (error) return <Alert type="error" message={`加载失败：${error}`} />;
  if (!data) return null;

  const mergedWarnings = Array.from(
    new Set([
      ...data.warnings,
      ...(detailData?.warnings ?? []),
          ...(detailError ? [`深度利差明细暂不可用：${normalizeClientError(detailError)}`] : []),
        ]),
      );
  const displayCreditBondCount = detailData?.credit_bond_count ?? data.credit_bond_count;
  const displayCreditMarketValue = detailData?.total_credit_market_value ?? data.credit_market_value;
  const displayWeightedAvgSpread = detailData
    ? formatBp(detailData.weighted_avg_spread_bps)
    : "-";
  const historicalContext = detailData?.historical_context;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="信用债数量" value={displayCreditBondCount} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="信用债市值"
              value={formatWan(displayCreditMarketValue)}
              suffix={`(${(parseFloat(data.credit_weight) * 100).toFixed(1)}%)`}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="Spread DV01 (万元/bp)" value={formatWan(data.spread_dv01)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="加权平均利差（个券）" value={displayWeightedAvgSpread} />
          </Card>
        </Col>
      </Row>

      <Card title="OCI敏感度" size="small">
        <Row gutter={16}>
          <Col span={8}>
            <Statistic title="OCI信用债敞口" value={formatWan(data.oci_credit_exposure)} />
          </Col>
          <Col span={8}>
            <Statistic title="OCI Spread DV01" value={formatWan(data.oci_spread_dv01)} />
          </Col>
          <Col span={8}>
            <Statistic title="利差走阔25bp影响" value={formatWan(data.oci_sensitivity_25bp)} />
          </Col>
        </Row>
      </Card>

      {data.spread_scenarios.length > 0 && (
        <Card title="利差情景冲击" size="small">
          {spreadChartOption && (
            <div style={{ marginBottom: 16 }}>
              <ReactECharts
                option={spreadChartOption}
                style={{ height: 280, width: "100%" }}
                opts={{ renderer: "canvas" }}
              />
            </div>
          )}
          <Table
            dataSource={data.spread_scenarios}
            columns={spreadColumns}
            rowKey="scenario_name"
            pagination={false}
            size="small"
          />
        </Card>
      )}

      <Card title="信用债分布" size="small">
        {creditDistributionView.kind === "heatmap" && (
          <ReactECharts
            option={creditDistributionView.option}
            style={{ height: 400, width: "100%" }}
            opts={{ renderer: "canvas" }}
          />
        )}
        {creditDistributionView.kind === "bars" && (
          <Row gutter={16}>
            <Col xs={24} lg={12}>
              <div
                style={{
                  marginBottom: 8,
                  fontSize: 12,
                  color: "rgba(0,0,0,0.65)",
                  textAlign: "center",
                }}
              >
                {data.concentration_by_rating?.dimension ?? "评级"}（Top 市值）
              </div>
              {creditDistributionView.ratingOption ? (
                <ReactECharts
                  option={creditDistributionView.ratingOption}
                  style={{ height: 300, width: "100%" }}
                  opts={{ renderer: "canvas" }}
                />
              ) : (
                <div
                  style={{
                    height: 300,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "rgba(0,0,0,0.45)",
                  }}
                >
                  暂无评级分布
                </div>
              )}
            </Col>
            <Col xs={24} lg={12}>
              <div
                style={{
                  marginBottom: 8,
                  fontSize: 12,
                  color: "rgba(0,0,0,0.65)",
                  textAlign: "center",
                }}
              >
                {data.concentration_by_tenor?.dimension ?? "期限"}（Top 市值）
              </div>
              {creditDistributionView.tenorOption ? (
                <ReactECharts
                  option={creditDistributionView.tenorOption}
                  style={{ height: 300, width: "100%" }}
                  opts={{ renderer: "canvas" }}
                />
              ) : (
                <div
                  style={{
                    height: 300,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "rgba(0,0,0,0.45)",
                  }}
                >
                  暂无期限分布
                </div>
              )}
            </Col>
          </Row>
        )}
        {creditDistributionView.kind === "empty" && (
          <div
            style={{
              minHeight: 120,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "rgba(0,0,0,0.45)",
            }}
          >
            暂无评级×期限明细或集中度数据，无法展示分布图
          </div>
        )}
      </Card>

      {detailData && (
        <>
          <Card title="利差期限结构" size="small">
            {termStructureOption ? (
              <ReactECharts
                option={termStructureOption}
                style={{ height: 320, width: "100%" }}
                opts={{ renderer: "canvas" }}
              />
            ) : (
              <div
                style={{
                  minHeight: 120,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "rgba(0,0,0,0.45)",
                }}
              >
                暂无期限结构数据
              </div>
            )}
          </Card>

          <Card title="历史分位" size="small">
            <Row gutter={16}>
              <Col span={6}>
                <Statistic
                  title="当前利差"
                  value={formatBpOrDash(historicalContext?.current_spread_bps)}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="1年历史分位"
                  value={formatPercentile(historicalContext?.percentile_1y)}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="3年历史分位"
                  value={formatPercentile(historicalContext?.percentile_3y)}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="1年中位数"
                  value={formatBpOrDash(historicalContext?.median_1y)}
                />
              </Col>
            </Row>
          </Card>

          <Row gutter={16}>
            <Col span={12}>
              <Card title="高利差债券" size="small">
                <Table<CreditSpreadDetailBondRow>
                  dataSource={detailData.top_spread_bonds}
                  columns={spreadDetailColumns}
                  rowKey={(row) => `${row.instrument_code}-${row.tenor_bucket}-top`}
                  pagination={false}
                  size="small"
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="低利差债券" size="small">
                <Table<CreditSpreadDetailBondRow>
                  dataSource={detailData.bottom_spread_bonds}
                  columns={spreadDetailColumns}
                  rowKey={(row) => `${row.instrument_code}-${row.tenor_bucket}-bottom`}
                  pagination={false}
                  size="small"
                />
              </Card>
            </Col>
          </Row>
        </>
      )}

      {hasAnyConcentrationField(data) && (
        <Card title="信用集中度" size="small">
          <Row gutter={[16, 16]}>
            <Col span={12}>
              {data.concentration_by_issuer?.top_items?.length ? (
                <>
                  <div
                    style={{
                      marginBottom: 8,
                      fontSize: 12,
                      color: "rgba(0,0,0,0.65)",
                      textAlign: "center",
                    }}
                  >
                    {data.concentration_by_issuer.dimension} HHI {data.concentration_by_issuer.hhi} Top5{" "}
                    {data.concentration_by_issuer.top5_concentration}
                  </div>
                  <Row gutter={16} align="middle">
                    <Col xs={24} md={12}>
                      <Table
                        dataSource={data.concentration_by_issuer.top_items}
                        columns={issuerConcentrationColumns}
                        rowKey={(r) => r.name}
                        pagination={false}
                        size="small"
                      />
                    </Col>
                    <Col xs={24} md={12}>
                      {issuerConcentrationPieOption && (
                        <div style={{ marginTop: 16 }}>
                          <ReactECharts
                            option={issuerConcentrationPieOption}
                            style={{ height: 280, width: "100%" }}
                            opts={{ renderer: "canvas" }}
                          />
                        </div>
                      )}
                    </Col>
                  </Row>
                </>
              ) : (
                <ConcentrationPieCell metrics={data.concentration_by_issuer} />
              )}
            </Col>
            <Col span={12}>
              <ConcentrationPieCell metrics={data.concentration_by_industry} />
            </Col>
            <Col span={12}>
              <ConcentrationPieCell metrics={data.concentration_by_rating} />
            </Col>
            <Col span={12}>
              <ConcentrationPieCell metrics={data.concentration_by_tenor} />
            </Col>
          </Row>
        </Card>
      )}

      {data.migration_scenarios.length > 0 && (
        <Card title="评级迁徙情景" size="small">
          <Table
            dataSource={data.migration_scenarios}
            columns={migrationColumns}
            rowKey="scenario_name"
            pagination={false}
            size="small"
          />
        </Card>
      )}

      {mergedWarnings.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message="提示"
          description={mergedWarnings.map((w, i) => <div key={i}>{w}</div>)}
        />
      )}
    </div>
  );
}

function normalizeClientError(message: string): string {
  const match = message.match(/\((\d{3})\)\s*$/);
  if (match?.[1]) {
    return `HTTP ${match[1]}`;
  }
  return message;
}
