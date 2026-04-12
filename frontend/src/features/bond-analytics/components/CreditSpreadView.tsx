import { useEffect, useMemo, useState } from "react";
import { Card, Statistic, Row, Col, Table, Alert, Spin } from "antd";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { ConcentrationMetrics, CreditSpreadMigrationResponse } from "../types";
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
  const [data, setData] = useState<CreditSpreadMigrationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ report_date: reportDate });
        const res = await fetch(`/api/bond-analytics/credit-spread-migration?${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) setData(json.result);
      } catch (e: unknown) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    if (reportDate) fetchData();
    return () => { cancelled = true; };
  }, [reportDate]);

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

  if (loading) return <Spin style={{ display: "block", margin: "40px auto" }} />;
  if (error) return <Alert type="error" message={`加载失败：${error}`} />;
  if (!data) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="信用债数量" value={data.credit_bond_count} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="信用债市值"
              value={formatWan(data.credit_market_value)}
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
            <Statistic title="加权平均利差" value={formatBp(data.weighted_avg_spread)} />
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
