import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Col, Row, Select, Space, Spin, Table, Typography } from "antd";

import { useApiClient } from "../../../api/client";
import { designTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import type { Numeric } from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import { FilterBar } from "../../../components/FilterBar";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { KpiCard } from "../../workbench/components/KpiCard";
import { shellTokens as t } from "../../../theme/tokens";
import { adaptCashflowProjection } from "../adapters/cashflowProjectionAdapter";
import { selectCashflowMonthlyProjectionSeries } from "./cashflowProjectionPageModel";

const pageStyle = { maxWidth: 1280, margin: "0 auto" } as const;
const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
} as const;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: 6,
  marginTop: 28,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#8090a8",
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: "#162033",
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 860,
  color: "#5c6b82",
  fontSize: 13,
  lineHeight: 1.7,
} as const;

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

function buildConclusion(durationGap: Numeric | undefined) {
  const raw = durationGap?.raw;
  if (raw === null || raw === undefined) {
    return {
      title: "当前结论",
      body: "久期缺口待确认，先核对报告日与上游现金流分桶是否齐备。",
    };
  }
  if (raw > 0.05) {
    return {
      title: "当前结论",
      body: "资产久期长于负债，当前为正久期缺口。",
    };
  }
  if (raw < -0.05) {
    return {
      title: "当前结论",
      body: "负债久期长于资产，当前为负久期缺口。",
    };
  }
  return {
    title: "当前结论",
    body: "资产与负债久期基本匹配，缺口已收敛到接近平衡区间。",
  };
}

export default function CashflowProjectionPage() {
  const client = useApiClient();
  const datesQuery = useQuery({
    queryKey: ["cashflow-projection", "balance-dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });

  const dateOptions = datesQuery.data?.result.report_dates ?? [];
  const [reportDate, setReportDate] = useState<string>("");

  const effectiveDate = reportDate || dateOptions[0] || "";

  const projectionQuery = useQuery({
    queryKey: ["cashflow-projection", client.mode, effectiveDate],
    queryFn: () => client.getCashflowProjection(effectiveDate),
    enabled: Boolean(effectiveDate),
    retry: false,
  });

  const adapted = useMemo(
    () =>
      adaptCashflowProjection({
        envelope: projectionQuery.data,
        isLoading: projectionQuery.isLoading,
        isError: projectionQuery.isError,
      }),
    [projectionQuery.data, projectionQuery.isLoading, projectionQuery.isError],
  );
  const vm = adapted.vm;
  const conclusion = buildConclusion(vm?.kpis.durationGap);
  const monthlySeries = useMemo(() => selectCashflowMonthlyProjectionSeries(vm), [vm]);

  const chartOption = useMemo((): EChartsOption | null => {
    if (!monthlySeries) {
      return null;
    }
    return {
      grid: { left: 56, right: 24, top: 32, bottom: 40 },
      tooltip: { trigger: "axis" },
      legend: { data: ["资产流入", "负债流出", "累计净现金流"] },
      xAxis: { type: "category", data: monthlySeries.categories, axisLabel: { rotate: 30 } },
      yAxis: [
        { type: "value", name: "当月流量", splitLine: { lineStyle: { color: "#eef2f7" } } },
        { type: "value", name: "累计", splitLine: { show: false } },
      ],
      series: [
        {
          name: "资产流入",
          type: "bar",
          data: monthlySeries.assetInflow,
          itemStyle: { color: "#389e0d" },
        },
        {
          name: "负债流出",
          type: "bar",
          data: monthlySeries.liabilityOutflow,
          itemStyle: { color: "#cf1322" },
        },
        {
          name: "累计净现金流",
          type: "line",
          yAxisIndex: 1,
          data: monthlySeries.cumulativeNet,
          smooth: true,
          symbolSize: 6,
          lineStyle: { width: 2, color: "#1d4ed8" },
        },
      ],
    };
  }, [monthlySeries]);

  return (
    <section data-testid="cashflow-projection-page" style={pageStyle}>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <div>
          <Typography.Title
            level={2}
            style={{ marginBottom: 8 }}
            data-testid="cashflow-page-title"
          >
            现金流预测
          </Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0, maxWidth: 860, lineHeight: 1.75 }}>
            久期缺口、利率敏感度与 24 个月现金流分桶；报告日来自资产负债分析可用日期。
          </Typography.Paragraph>
        </div>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "8px 12px",
            borderRadius: 999,
            background:
              client.mode === "real" ? designTokens.color.success[50] : designTokens.color.primary[50],
            color:
              client.mode === "real"
                ? displayTokens.apiMode.realForeground
                : displayTokens.apiMode.mockForeground,
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          {client.mode === "real" ? "真实只读链路" : "本地演示数据"}
        </span>
      </div>

      <FilterBar style={{ marginBottom: 20 }}>
        <div>
          <Typography.Text type="secondary">报告日</Typography.Text>
          <div style={{ marginTop: 4 }}>
            <Select
              aria-label="cashflow-report-date"
              style={{ minWidth: 200 }}
              placeholder={datesQuery.isLoading ? "加载日期…" : "选择报告日"}
              loading={datesQuery.isLoading}
              value={effectiveDate || undefined}
              options={dateOptions.map((d) => ({ value: d, label: d }))}
              onChange={(v) => setReportDate(v)}
              disabled={!dateOptions.length && !reportDate}
            />
          </div>
        </div>
      </FilterBar>

      <DataSection
        title="现金流预测结果"
        state={adapted.state}
        onRetry={() => {
          void projectionQuery.refetch();
        }}
        extra={
          effectiveDate ? (
            <Typography.Text type="secondary">{`报告日 ${effectiveDate}`}</Typography.Text>
          ) : null
        }
      >
        {projectionQuery.isLoading ? (
          <div style={{ textAlign: "center", padding: 48 }}>
            <Spin />
          </div>
        ) : projectionQuery.isError ? (
          <Alert type="error" message="加载现金流预测失败，请稍后重试。" showIcon />
        ) : vm ? (
          <>
            <Card
              data-testid="cashflow-conclusion"
              style={{
                marginBottom: 20,
                borderRadius: 16,
                border: `1px solid ${t.colorBorderSoft}`,
                background: "#f7fbff",
              }}
            >
              <Space direction="vertical" size={6}>
                <Typography.Text style={{ fontSize: 12, fontWeight: 700, color: "#56708f" }}>
                  {conclusion.title}
                </Typography.Text>
                <Typography.Title level={4} style={{ margin: 0 }}>
                  {conclusion.body}
                </Typography.Title>
                <Typography.Text type="secondary">
                  {`报告日 ${vm.reportDate} · 久期缺口 ${vm.kpis.durationGap.display}`}
                </Typography.Text>
              </Space>
            </Card>

            <SectionLead
              eyebrow="总览"
              title="现金流概览"
              description="先看久期缺口、资产负债久期和敏感度，再进入月度投影与到期资产列表，保持阅读顺序与其他标准页一致。"
            />
            <div style={summaryGridStyle}>
              <div data-testid="cashflow-kpi-duration-gap">
                <KpiCard
                  title="久期缺口（年）"
                  value={vm.kpis.durationGap.display}
                  detail="资产久期 - 负债久期"
                  valueVariant="text"
                />
              </div>
              <div data-testid="cashflow-kpi-asset-dur">
                <KpiCard title="资产久期（年）" value={vm.kpis.assetDuration.display} detail="资产侧久期" valueVariant="text" />
              </div>
              <div data-testid="cashflow-kpi-liability-dur">
                <KpiCard
                  title="负债久期（年）"
                  value={vm.kpis.liabilityDuration.display}
                  detail="负债侧久期"
                  valueVariant="text"
                />
              </div>
              <div data-testid="cashflow-kpi-dv01">
                <KpiCard
                  title="1bp 敏感度"
                  value={vm.kpis.rateSensitivity1bp.display}
                  detail="利率敏感度"
                  valueVariant="text"
                />
              </div>
              <div data-testid="cashflow-kpi-equity-dur">
                <KpiCard title="权益久期（年）" value={vm.kpis.equityDuration.display} detail="权益侧久期" valueVariant="text" />
              </div>
              <div data-testid="cashflow-kpi-reinvest">
                <KpiCard
                  title="再投资风险（12M）"
                  value={vm.kpis.reinvestmentRisk12m.display}
                  detail="12 个月再投资风险"
                  valueVariant="text"
                />
              </div>
            </div>

            <SectionLead
              eyebrow="预测"
              title="月度投影"
              description="图表区继续展示 24 个月现金流投影，右侧保留补充指标，不改变现有图表与数据口径。"
            />
            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
              <Col xs={24} lg={16}>
                <Card
                  data-testid="cashflow-monthly-chart"
                  size="small"
                  title="月度现金流投影"
                  style={{
                    borderRadius: 16,
                    border: `1px solid ${t.colorBorderSoft}`,
                    minHeight: 360,
                  }}
                >
                  {chartOption ? (
                    <ReactECharts option={chartOption} style={{ height: 320 }} />
                  ) : (
                    <Typography.Text type="secondary">暂无分桶数据</Typography.Text>
                  )}
                </Card>
              </Col>
              <Col xs={24} lg={8}>
                <Space direction="vertical" size={16} style={{ width: "100%" }}>
                  <Card size="small" title="权益久期（年）">
                    <Typography.Text style={{ fontSize: 18, fontWeight: 600 }}>
                      {vm.kpis.equityDuration.display}
                    </Typography.Text>
                  </Card>
                  <Card size="small" title="再投资风险（12M）">
                    <Typography.Text style={{ fontSize: 18, fontWeight: 600 }}>
                      {vm.kpis.reinvestmentRisk12m.display}
                    </Typography.Text>
                  </Card>
                </Space>
              </Col>
            </Row>

            <SectionLead
              eyebrow="到期"
              title="到期资产与提示"
          description="前十到期资产列表和预警区保持现有契约，只调整为更清晰的阅读层级。"
            />
            <Card
              size="small"
          title="12 个月内前十到期资产"
              style={{ marginBottom: 16, borderRadius: 16, border: `1px solid ${t.colorBorderSoft}` }}
            >
              <Table
                data-testid="cashflow-top-assets-table"
                size="small"
                pagination={false}
                rowKey={(r) => r.instrumentCode}
                dataSource={vm.topMaturingAssets}
                columns={[
                  { title: "代码", dataIndex: "instrumentCode" },
                  { title: "名称", dataIndex: "instrumentName" },
                  { title: "到期日", dataIndex: "maturityDate" },
                  {
                    title: "面值",
                    dataIndex: "faceValue",
                    align: "right" as const,
                    render: (v: Numeric) => v.display,
                  },
                  {
                    title: "市值",
                    dataIndex: "marketValue",
                    align: "right" as const,
                    render: (v: Numeric) => v.display,
                  },
                ]}
              />
            </Card>

            {vm.warnings?.length ? (
              <Alert
                type="warning"
                showIcon
                message="提示"
                description={
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {vm.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                }
              />
            ) : null}
          </>
        ) : null}
      </DataSection>
    </section>
  );
}
