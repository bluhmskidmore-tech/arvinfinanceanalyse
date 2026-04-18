import { Suspense, lazy, useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { Alert, Card, Col, Row, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

import { useApiClient } from "../../../api/client";
import type { BondTopHoldingItem, Numeric } from "../../../api/contracts";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import ReactECharts from "../../../lib/echarts";
import { formatPct, formatWan } from "../utils/formatters";
import { BondKpiRow } from "./BondKpiRow";
import { FIELD, panelStyle } from "./bondAnalyticsCockpitTokens";

const PortfolioSummaryNarrative = lazy(async () => import("./PortfolioSummaryNarrative"));
const AssetStructurePie = lazy(async () => import("./AssetStructurePie"));

const { Text } = Typography;

const phase3Fallback = (
  <div style={{ color: "#8090a8", fontSize: 13, padding: "8px 0" }}>Loading phase-3 modules…</div>
);

export interface BondAnalyticsInstitutionalCockpitProps {
  reportDate: string;
}

export function BondAnalyticsInstitutionalCockpit({ reportDate }: BondAnalyticsInstitutionalCockpitProps) {
  const client = useApiClient();

  const [headlineQ, yieldQ, spreadQ, maturityQ, industryQ, holdingsQ, portfolioHlQ] = useQueries({
    queries: [
      {
        queryKey: ["bond-analytics-institutional", "headline", client.mode, reportDate],
        queryFn: () => client.getBondDashboardHeadlineKpis(reportDate),
        enabled: Boolean(reportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "yield", client.mode, reportDate],
        queryFn: () => client.getBondDashboardYieldDistribution(reportDate),
        enabled: Boolean(reportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "spread", client.mode, reportDate],
        queryFn: () => client.getBondDashboardSpreadAnalysis(reportDate),
        enabled: Boolean(reportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "maturity", client.mode, reportDate],
        queryFn: () => client.getBondDashboardMaturityStructure(reportDate),
        enabled: Boolean(reportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "industry", client.mode, reportDate],
        queryFn: () => client.getBondDashboardIndustryDistribution(reportDate),
        enabled: Boolean(reportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "holdings", client.mode, reportDate],
        queryFn: () => client.getBondAnalyticsTopHoldings(reportDate, 10),
        enabled: Boolean(reportDate),
      },
      {
        queryKey: ["bond-analytics-institutional", "portfolio-hl", client.mode, reportDate],
        queryFn: () => client.getBondAnalyticsPortfolioHeadlines(reportDate),
        enabled: Boolean(reportDate),
      },
    ],
  });

  const headline = headlineQ.data?.result;
  const portfolioHl = portfolioHlQ.data?.result;

  const yieldBarOption = useMemo(() => {
    const items = yieldQ.data?.result.items ?? [];
    if (!items.length) return null;
    return {
      grid: { left: 48, right: 12, top: 28, bottom: 56, containLabel: false },
      tooltip: { trigger: "axis" as const },
      xAxis: {
        type: "category" as const,
        data: items.map((it) => it.yield_bucket),
        axisLabel: { rotate: 28, fontSize: 10, color: "#5c6b82" },
      },
      yAxis: {
        type: "value" as const,
        name: "亿元",
        axisLabel: { color: "#5c6b82", formatter: (v: number) => `${v.toFixed(0)}` },
      },
      series: [
        {
          type: "bar" as const,
          data: items.map((it) => parseFloat(it.total_market_value) / 1e8),
          itemStyle: { color: "#1f5eff", borderRadius: [6, 6, 0, 0] },
          barMaxWidth: 36,
        },
      ],
    };
  }, [yieldQ.data]);

  const maturityBarOption = useMemo(() => {
    const items = maturityQ.data?.result.items ?? [];
    if (!items.length) return null;
    return {
      grid: { left: 48, right: 12, top: 28, bottom: 44, containLabel: false },
      tooltip: { trigger: "axis" as const },
      xAxis: {
        type: "category" as const,
        data: items.map((it) => it.maturity_bucket),
        axisLabel: { fontSize: 10, color: "#5c6b82", interval: 0, rotate: 20 },
      },
      yAxis: {
        type: "value" as const,
        name: "亿元",
        axisLabel: { color: "#5c6b82", formatter: (v: number) => `${v.toFixed(0)}` },
      },
      series: [
        {
          type: "bar" as const,
          data: items.map((it) => parseFloat(it.total_market_value) / 1e8),
          itemStyle: { color: "#2f8f63", borderRadius: [6, 6, 0, 0] },
          barMaxWidth: 40,
        },
      ],
    };
  }, [maturityQ.data]);

  const industryBarOption = useMemo(() => {
    const items = industryQ.data?.result.items ?? [];
    if (!items.length) return null;
    const sorted = [...items].sort((a, b) => parseFloat(b.percentage) - parseFloat(a.percentage));
    return {
      grid: { left: 120, right: 24, top: 16, bottom: 24, containLabel: false },
      tooltip: { trigger: "axis" as const, axisPointer: { type: "shadow" as const } },
      xAxis: {
        type: "value" as const,
        max: 100,
        axisLabel: { formatter: "{value}%", color: "#5c6b82" },
        splitLine: { lineStyle: { type: "dashed" as const, opacity: 0.35 } },
      },
      yAxis: {
        type: "category" as const,
        data: sorted.map((it) => it.industry_name),
        axisLabel: { color: "#5c6b82", fontSize: 11 },
      },
      series: [
        {
          type: "bar" as const,
          data: sorted.map((it) => parseFloat(it.percentage)),
          itemStyle: { color: "#ff7a45", borderRadius: [0, 6, 6, 0] },
          barMaxWidth: 18,
        },
      ],
    };
  }, [industryQ.data]);

  const topHoldingsColumns: ColumnsType<BondTopHoldingItem> = [
    { title: "债券简称", dataIndex: "instrument_name", key: "instrument_name", ellipsis: true },
    { title: "面额", dataIndex: "face_value", key: "face_value", render: formatWan },
    { title: "收益率", dataIndex: "ytm", key: "ytm", render: (v: Numeric) => formatPct(v) },
    {
      title: "久期",
      dataIndex: "modified_duration",
      key: "modified_duration",
      render: (v: Numeric) => v.display,
    },
    { title: "评级", dataIndex: "rating", key: "rating" },
    { title: "浮盈", key: "upl", render: () => "—" },
    { title: "浮盈/亏", key: "upl_pct", render: () => "—" },
  ];

  const spreadColumns = [
    { title: "券种", dataIndex: "bond_type", key: "bond_type" },
    { title: "中位收益率", dataIndex: "median_yield", key: "median_yield", render: (v: string) => formatPct(v) },
    { title: "只数", dataIndex: "bond_count", key: "bond_count" },
    { title: "市值", dataIndex: "total_market_value", key: "total_market_value", render: formatWan },
  ];

  const err = headlineQ.isError ? ((headlineQ.error as Error)?.message ?? "驾驶舱数据加载失败") : null;

  const dur = headline ? parseFloat(headline.kpis.weighted_duration) : NaN;
  const cw = portfolioHl ? bondNumericRaw(portfolioHl.credit_weight) : NaN;

  return (
    <section
      data-testid="bond-analysis-phase3-cockpit"
      style={{ display: "flex", flexDirection: "column", gap: 12 }}
    >
      {err ? <Alert type="warning" showIcon message="部分驾驶舱指标未就绪" description={err} /> : null}

      <Card size="small" style={panelStyle("#fbfcfe")} styles={{ body: { paddingBlock: 16 } }}>
        <div style={FIELD}>债市 KPI（驾驶舱）</div>
        <div style={{ marginTop: 12 }}>
          <BondKpiRow
            headline={headline}
            portfolioHeadlines={portfolioHl}
            loading={headlineQ.isPending}
          />
        </div>
      </Card>

      <Suspense fallback={phase3Fallback}>
        <Row gutter={[12, 12]}>
          <Col xs={24} lg={14}>
            <PortfolioSummaryNarrative />
          </Col>
          <Col xs={24} lg={10}>
            <AssetStructurePie />
          </Col>
        </Row>
      </Suspense>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={12}>
          <Card
            size="small"
            title="收益率分布（按桶位市值）"
            style={panelStyle("#ffffff")}
            extra={
              <Text type="secondary">
                组合加权 {yieldQ.data?.result.weighted_ytm ? formatPct(yieldQ.data.result.weighted_ytm) : "—"}
              </Text>
            }
          >
            {yieldBarOption ? (
              <ReactECharts option={yieldBarOption} style={{ height: 300 }} opts={{ renderer: "canvas" }} />
            ) : (
              <Text type="secondary">暂无分布数据</Text>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="期限结构（亿元）" style={panelStyle("#ffffff")}>
            {maturityBarOption ? (
              <ReactECharts option={maturityBarOption} style={{ height: 300 }} opts={{ renderer: "canvas" }} />
            ) : (
              <Text type="secondary">暂无期限结构</Text>
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={12}>
          <Card size="small" title="行业分布（集中度参考）" style={panelStyle("#ffffff")}>
            {industryBarOption ? (
              <ReactECharts option={industryBarOption} style={{ height: 320 }} opts={{ renderer: "canvas" }} />
            ) : (
              <Text type="secondary">暂无行业数据</Text>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="利差/收益率分券种（中位数）" style={panelStyle("#ffffff")}>
            <Table
              size="small"
              pagination={false}
              dataSource={spreadQ.data?.result.items ?? []}
              columns={spreadColumns}
              rowKey={(r) => r.bond_type}
            />
          </Card>
        </Col>
      </Row>

      <Card size="small" title="重仓明细（前10）" style={panelStyle("#ffffff")}>
        <Table
          size="small"
          pagination={false}
          scroll={{ x: true }}
          dataSource={holdingsQ.data?.result.items ?? []}
          columns={topHoldingsColumns}
          rowKey={(r) => r.instrument_code}
          loading={holdingsQ.isPending}
        />
      </Card>

      <Card size="small" title="候选动作（非决策事项）" style={panelStyle("#ffffff")}>
        <ul style={{ margin: 0, paddingLeft: 18, color: "#314a66", lineHeight: 1.8 }}>
          <li>
            {Number.isFinite(dur) && dur >= 3.8
              ? "久期高于阈值：可在 KRD 模块复核曲线风险并评估对冲。"
              : "久期适中：保持对收益率突变的监测。"}
          </li>
          <li>
            {Number.isFinite(cw) && cw >= 0.35
              ? "信用权重偏高：建议在信用迁移情景下复核 OCI/TPL 分支。"
              : "信用权重可控：关注评级迁徙与行业集中度。"}
          </li>
          <li>结合异常预警与组合摘要，在「动作归因」模块记录已执行操作。</li>
        </ul>
      </Card>
    </section>
  );
}
