import { useEffect, useMemo, useState } from "react";
import { Card, Statistic, Row, Col, Table, Alert, Spin } from "antd";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { useApiClient } from "../../../api/client";
import type { AssetClassRiskSummary, BondAnalyticsScenarioSetFilter, KRDCurveRiskResponse } from "../types";
import { formatWan } from "../utils/formatters";
import { SectionLead } from "./SectionLead";

interface Props {
  reportDate: string;
  scenarioSet?: BondAnalyticsScenarioSetFilter;
}

const scenarioColumns = [
  { title: "情景", dataIndex: "scenario_description", key: "scenario_description" },
  { title: "经济口径影响", dataIndex: "pnl_economic", key: "pnl_economic", render: formatWan },
  { title: "OCI影响", dataIndex: "pnl_oci", key: "pnl_oci", render: formatWan },
  { title: "TPL影响", dataIndex: "pnl_tpl", key: "pnl_tpl", render: formatWan },
];

const assetClassColumns = [
  { title: "资产类别", dataIndex: "asset_class", key: "asset_class" },
  { title: "市值", dataIndex: "market_value", key: "market_value", render: formatWan },
  { title: "久期", dataIndex: "duration", key: "duration" },
  { title: "DV01", dataIndex: "dv01", key: "dv01", render: formatWan },
  { title: "权重", dataIndex: "weight", key: "weight" },
];

const ASSET_CLASS_SLICE_COLORS: Record<string, string> = {
  rate: "#1f5eff",
  credit: "#ff7a45",
  other: "#8c8c8c",
};

const DEFAULT_SLICE_COLOR = "#bfbfbf";

function sliceColorForAssetClass(assetClass: string): string {
  const key = assetClass.trim().toLowerCase();
  return ASSET_CLASS_SLICE_COLORS[key] ?? DEFAULT_SLICE_COLOR;
}

function buildAssetStructurePieOption(rows: AssetClassRiskSummary[]) {
  const pieData = rows.map((row) => ({
    name: row.asset_class,
    value: parseFloat(row.market_value),
    marketValueRaw: row.market_value,
    weight: row.weight,
    itemStyle: { color: sliceColorForAssetClass(row.asset_class) },
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
            text: "资产结构",
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

export function KRDCurveRiskView({ reportDate, scenarioSet = "standard" }: Props) {
  const client = useApiClient();
  const [data, setData] = useState<KRDCurveRiskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const envelope =
          scenarioSet === "standard"
            ? await client.getBondAnalyticsKrdCurveRisk(reportDate)
            : await client.getBondAnalyticsKrdCurveRisk(reportDate, { scenarioSet });
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
  }, [client, reportDate, scenarioSet]);

  const krdChartOption = useMemo((): EChartsOption | null => {
    if (!data?.krd_buckets?.length) return null;
    const buckets = data.krd_buckets;
    return {
      grid: { left: 52, right: 16, top: 36, bottom: 28, containLabel: false },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params) => {
          const arr = Array.isArray(params) ? params : [params];
          const p = arr[0];
          if (!p || typeof p.dataIndex !== "number") return "";
          const b = buckets[p.dataIndex];
          const krd = parseFloat(b.krd);
          const dv01 = parseFloat(b.dv01);
          const w = parseFloat(b.market_value_weight);
          return [
            `<div style="font-weight:600;margin-bottom:4px">${b.tenor}</div>`,
            `KRD：${Number.isFinite(krd) ? krd.toFixed(3) : b.krd}`,
            `DV01：${Number.isFinite(dv01) ? dv01.toFixed(6) : b.dv01}`,
            `market_value_weight：${Number.isFinite(w) ? w.toFixed(6) : b.market_value_weight}`,
          ].join("<br/>");
        },
      },
      xAxis: {
        type: "category",
        data: buckets.map((b) => b.tenor),
        axisLabel: { color: "#5c6b82", fontSize: 11 },
        axisTick: { alignWithLabel: true },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          color: "#5c6b82",
          fontSize: 11,
          formatter: (v: number) => v.toFixed(3),
        },
        splitLine: { lineStyle: { type: "dashed", opacity: 0.35 } },
      },
      series: [
        {
          type: "bar",
          barMaxWidth: 48,
          data: buckets.map((b) => {
            const krd = parseFloat(b.krd);
            const color = krd >= 0 ? "#1f5eff" : "#ff4d4f";
            return {
              value: krd,
              itemStyle: { color },
              label: {
                show: true,
                position: krd >= 0 ? "top" : "bottom",
                formatter: Number.isFinite(krd) ? krd.toFixed(3) : b.krd,
                color: "#333",
                fontSize: 11,
                fontVariantNumeric: "tabular-nums",
              },
            };
          }),
        },
      ],
    };
  }, [data]);

  const assetStructurePieOption = useMemo(
    () => buildAssetStructurePieOption(data?.by_asset_class ?? []),
    [data?.by_asset_class],
  );

  if (loading) return <Spin style={{ display: "block", margin: "40px auto" }} />;
  if (error) return <Alert type="error" message={`加载失败：${error}`} />;
  if (!data) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SectionLead
        eyebrow="KRD Curve Risk"
        title="曲线风险概览"
        description="按报告日读取后端 KRD curve risk read model；页面只展示久期、修正久期、DV01 和凸性，不在前端补算正式风险指标。"
        testId="krd-curve-risk-shell-lead"
      />
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="组合久期" value={parseFloat(data.portfolio_duration).toFixed(2)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="修正久期" value={parseFloat(data.portfolio_modified_duration).toFixed(2)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="DV01 (万元/bp)" value={formatWan(data.portfolio_dv01)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="凸性" value={parseFloat(data.portfolio_convexity).toFixed(2)} />
          </Card>
        </Col>
      </Row>

      <SectionLead
        eyebrow="Buckets"
        title="KRD 桶位与情景冲击"
        description="KRD 分布和情景冲击沿用后端返回的 krd_buckets 与 scenarios，前端仅做图表和表格展示。"
        testId="krd-curve-risk-buckets-lead"
      />
      {data.krd_buckets.length > 0 && krdChartOption && (
        <Card title="KRD 分布" size="small">
          <ReactECharts
            option={krdChartOption}
            style={{ width: "100%", height: 240 }}
            opts={{ renderer: "canvas" }}
          />
        </Card>
      )}

      {data.scenarios.length > 0 && (
        <Card title="情景冲击" size="small">
          <Table
            dataSource={data.scenarios}
            columns={scenarioColumns}
            rowKey="scenario_name"
            pagination={false}
            size="small"
          />
        </Card>
      )}

      <SectionLead
        eyebrow="Asset Class"
        title="资产类别风险拆分"
        description="资产结构饼图和 by_asset_class 表格保留后端语义，不调整市值、久期、DV01 或权重。"
        testId="krd-curve-risk-asset-lead"
      />
      {data.by_asset_class.length > 0 && (
        <Card title="按资产类别拆分" size="small">
          <ReactECharts
            option={assetStructurePieOption}
            style={{ height: 220, width: "100%" }}
            opts={{ renderer: "canvas" }}
          />
          <Table
            dataSource={data.by_asset_class}
            columns={assetClassColumns}
            rowKey="asset_class"
            pagination={false}
            size="small"
          />
        </Card>
      )}

      {data.warnings.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message="提示"
          description={data.warnings.map((w, i) => <div key={i}>{w}</div>)}
        />
      )}
    </div>
  );
}
