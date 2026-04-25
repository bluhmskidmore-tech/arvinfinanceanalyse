import { useEffect, useMemo, useState } from "react";
import { Card, Statistic, Row, Col, Table, Alert, Spin } from "antd";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { useApiClient } from "../../../api/client";
import type { KRDScenarioResult, Numeric } from "../../../api/contracts";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { AssetClassRiskSummary, BondAnalyticsScenarioSetFilter, KRDCurveRiskResponse } from "../types";
import { formatWan, formatYi } from "../utils/formatters";
import { SectionLead } from "./SectionLead";

function formatScenarioShocks(shocks: Record<string, number>): string {
  const entries = Object.entries(shocks ?? {});
  if (entries.length === 0) {
    return "—";
  }
  return entries.map(([k, v]) => `${k} ${v}`).join(" · ");
}

interface Props {
  reportDate: string;
  scenarioSet?: BondAnalyticsScenarioSetFilter;
}

const scenarioColumns = [
  { title: "情景键", dataIndex: "scenario_name", key: "scenario_name" },
  { title: "情景", dataIndex: "scenario_description", key: "scenario_description" },
  {
    title: "冲击参数",
    dataIndex: "shocks",
    key: "shocks",
    ellipsis: true,
    render: (shocks: Record<string, number>) => formatScenarioShocks(shocks),
  },
  { title: "经济口径影响", dataIndex: "pnl_economic", key: "pnl_economic", render: formatWan },
  { title: "OCI影响", dataIndex: "pnl_oci", key: "pnl_oci", render: formatWan },
  { title: "TPL影响", dataIndex: "pnl_tpl", key: "pnl_tpl", render: formatWan },
  {
    title: "利率贡献",
    dataIndex: "rate_contribution",
    key: "rate_contribution",
    render: formatWan,
  },
  {
    title: "凸性贡献",
    dataIndex: "convexity_contribution",
    key: "convexity_contribution",
    render: formatWan,
  },
];

const SCENARIO_BY_AC_CORE_KEYS = new Set(["pnl_economic", "pnl_oci", "pnl_tpl"]);

function collectScenarioByAssetClassExtraKeys(
  bac: Record<string, Record<string, Numeric>>,
): string[] {
  const extra = new Set<string>();
  for (const metrics of Object.values(bac)) {
    for (const k of Object.keys(metrics ?? {})) {
      if (!SCENARIO_BY_AC_CORE_KEYS.has(k)) {
        extra.add(k);
      }
    }
  }
  return Array.from(extra).sort((a, b) => a.localeCompare(b));
}

function renderScenarioAssetClassBreakdown(record: KRDScenarioResult) {
  const bac = record.by_asset_class ?? {};
  const extraKeys = collectScenarioByAssetClassExtraKeys(bac);
  const rows = Object.entries(bac).map(([asset_class, metrics]) => {
    const row: Record<string, string | Numeric | undefined> = {
      asset_class,
      pnl_economic: metrics.pnl_economic,
      pnl_oci: metrics.pnl_oci,
      pnl_tpl: metrics.pnl_tpl,
    };
    for (const ek of extraKeys) {
      row[ek] = metrics[ek];
    }
    return row;
  });
  const scenarioByAssetClassColumns = [
    { title: "资产类别", dataIndex: "asset_class", key: "asset_class" },
    {
      title: "经济口径",
      dataIndex: "pnl_economic",
      key: "pnl_economic",
      render: (v: Numeric | undefined) => (v ? formatWan(v) : "—"),
    },
    {
      title: "OCI 影响",
      dataIndex: "pnl_oci",
      key: "pnl_oci",
      render: (v: Numeric | undefined) => (v ? formatWan(v) : "—"),
    },
    {
      title: "TPL 影响",
      dataIndex: "pnl_tpl",
      key: "pnl_tpl",
      render: (v: Numeric | undefined) => (v ? formatWan(v) : "—"),
    },
    ...extraKeys.map((ek) => ({
      title: ek,
      dataIndex: ek,
      key: ek,
      render: (v: Numeric | undefined) => (v ? formatWan(v) : "—"),
    })),
  ];
  if (rows.length === 0) {
    return (
      <div style={{ color: "#8090a8", fontSize: 12 }} data-testid="krd-scenario-by-asset-class-empty">
        暂无按资产类别的情景拆分
      </div>
    );
  }
  return (
    <div data-testid="krd-scenario-by-asset-class">
      {extraKeys.length > 0 ? (
        <div
          style={{ fontSize: 11, color: "#8090a8", marginBottom: 8 }}
          data-testid="krd-scenario-by-asset-class-extra-keys"
        >
          额外口径键：{extraKeys.join("、")}
        </div>
      ) : null}
      <Table
        dataSource={rows}
        columns={scenarioByAssetClassColumns}
        rowKey="asset_class"
        pagination={false}
        size="small"
        scroll={extraKeys.length > 2 ? { x: "max-content" } : undefined}
      />
    </div>
  );
}

const assetClassColumns = [
  { title: "资产类别", dataIndex: "asset_class", key: "asset_class" },
  { title: "市值", dataIndex: "market_value", key: "market_value", render: formatYi },
  {
    title: "久期",
    dataIndex: "duration",
    key: "duration",
    render: (v: Numeric) => v.display,
  },
  {
    title: "DV01",
    dataIndex: "dv01",
    key: "dv01",
    render: (v: Numeric) => v.display,
  },
  {
    title: "权重",
    dataIndex: "weight",
    key: "weight",
    render: (v: Numeric) => v.display,
  },
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
    value: bondNumericRaw(row.market_value),
    marketValueRaw: row.market_value,
    weight: row.weight,
    itemStyle: { color: sliceColorForAssetClass(row.asset_class) },
  }));

  return {
    tooltip: {
      trigger: "item" as const,
      formatter: (params: {
        data?: { name: string; marketValueRaw: Numeric; weight: Numeric };
      }) => {
        const d = params.data;
        if (!d) return "";
        return `${d.name}<br/>市值：${formatYi(d.marketValueRaw)}<br/>权重：${d.weight.display}`;
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
          const krd = bondNumericRaw(b.krd);
          const dv01 = bondNumericRaw(b.dv01);
          const w = bondNumericRaw(b.market_value_weight);
          return [
            `<div style="font-weight:600;margin-bottom:4px">${b.tenor}</div>`,
            `KRD：${Number.isFinite(krd) ? krd.toFixed(3) : b.krd.display}`,
            `DV01：${Number.isFinite(dv01) ? dv01.toFixed(6) : b.dv01.display}`,
            `market_value_weight：${Number.isFinite(w) ? w.toFixed(6) : b.market_value_weight.display}`,
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
            const krd = bondNumericRaw(b.krd);
            const color = krd >= 0 ? "#1f5eff" : "#ff4d4f";
            return {
              value: krd,
              itemStyle: { color },
              label: {
                show: true,
                position: krd >= 0 ? "top" : "bottom",
                formatter: Number.isFinite(krd) ? krd.toFixed(3) : b.krd.display,
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
      {data.computed_at ? (
        <div style={{ fontSize: 12, color: "#8090a8" }} data-testid="krd-computed-at">
          计算时间：{data.computed_at}
        </div>
      ) : null}
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="组合久期" value={data.portfolio_duration.display} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="修正久期" value={data.portfolio_modified_duration.display} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="DV01 (万元/bp)" value={data.portfolio_dv01.display} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="凸性" value={data.portfolio_convexity.display} />
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
            data-testid="krd-scenarios-table"
            dataSource={data.scenarios}
            columns={scenarioColumns}
            rowKey="scenario_name"
            pagination={false}
            size="small"
            expandable={{ expandedRowRender: renderScenarioAssetClassBreakdown }}
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
