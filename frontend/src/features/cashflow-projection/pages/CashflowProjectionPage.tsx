import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, Col, Row, Select, Space, Spin, Table, Typography, Alert } from "antd";

import { useApiClient } from "../../../api/client";
import type { CashflowMonthlyBucket } from "../../../api/contracts";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { shellTokens as t } from "../../../theme/tokens";

const pageStyle = { maxWidth: 1280, margin: "0 auto" } as const;

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

  const env = projectionQuery.data;
  const result = env?.result;

  const chartOption = useMemo((): EChartsOption | null => {
    const buckets: CashflowMonthlyBucket[] = result?.monthly_buckets ?? [];
    if (!buckets.length) {
      return null;
    }
    const cats = buckets.map((b) => b.year_month);
    const asset = buckets.map((b) => parseFloat(b.asset_inflow));
    const liab = buckets.map((b) => parseFloat(b.liability_outflow));
    const cum = buckets.map((b) => parseFloat(b.cumulative_net));
    return {
      grid: { left: 56, right: 24, top: 32, bottom: 40 },
      tooltip: { trigger: "axis" },
      legend: { data: ["资产流入", "负债流出", "累计净现金流"] },
      xAxis: { type: "category", data: cats, axisLabel: { rotate: 30 } },
      yAxis: [
        { type: "value", name: "当月流量", splitLine: { lineStyle: { color: "#eef2f7" } } },
        { type: "value", name: "累计", splitLine: { show: false } },
      ],
      series: [
        {
          name: "资产流入",
          type: "bar",
          data: asset,
          itemStyle: { color: "#389e0d" },
        },
        {
          name: "负债流出",
          type: "bar",
          data: liab,
          itemStyle: { color: "#cf1322" },
        },
        {
          name: "累计净现金流",
          type: "line",
          yAxisIndex: 1,
          data: cum,
          smooth: true,
          symbolSize: 6,
          lineStyle: { width: 2, color: "#1d4ed8" },
        },
      ],
    };
  }, [result?.monthly_buckets]);

  return (
    <section data-testid="cashflow-projection-page" style={pageStyle}>
      <Typography.Title level={2} style={{ marginBottom: 8 }}>
        现金流预测
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 20, maxWidth: 720 }}>
        久期缺口、利率敏感度与 24 个月现金流分桶；报告日来自资产负债分析可用日期。
      </Typography.Paragraph>

      <Space wrap style={{ marginBottom: 20 }} align="start">
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
      </Space>

      {projectionQuery.isLoading ? (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin />
        </div>
      ) : projectionQuery.isError ? (
        <Alert type="error" message="加载现金流预测失败，请稍后重试。" showIcon />
      ) : result ? (
        <>
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={24} sm={12} lg={6}>
              <Card data-testid="cashflow-kpi-duration-gap" size="small" title="久期缺口（年）">
                <Typography.Text style={{ fontSize: 20, fontWeight: 600 }}>
                  {result.duration_gap}
                </Typography.Text>
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card data-testid="cashflow-kpi-asset-dur" size="small" title="资产久期（年）">
                <Typography.Text style={{ fontSize: 20, fontWeight: 600 }}>
                  {result.asset_duration}
                </Typography.Text>
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card data-testid="cashflow-kpi-liability-dur" size="small" title="负债久期（年）">
                <Typography.Text style={{ fontSize: 20, fontWeight: 600 }}>
                  {result.liability_duration}
                </Typography.Text>
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card data-testid="cashflow-kpi-dv01" size="small" title="1bp 敏感度">
                <Typography.Text style={{ fontSize: 20, fontWeight: 600 }}>
                  {result.rate_sensitivity_1bp}
                </Typography.Text>
              </Card>
            </Col>
          </Row>

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
                <Card data-testid="cashflow-kpi-equity-dur" size="small" title="权益久期（年）">
                  <Typography.Text style={{ fontSize: 18, fontWeight: 600 }}>
                    {result.equity_duration}
                  </Typography.Text>
                </Card>
                <Card data-testid="cashflow-kpi-reinvest" size="small" title="再投资风险（12M）">
                  <Typography.Text style={{ fontSize: 18, fontWeight: 600 }}>
                    {result.reinvestment_risk_12m}
                  </Typography.Text>
                </Card>
              </Space>
            </Col>
          </Row>

          <Card
            size="small"
            title="12 个月内 Top10 到期资产"
            style={{ marginBottom: 16, borderRadius: 16, border: `1px solid ${t.colorBorderSoft}` }}
          >
            <Table
              data-testid="cashflow-top-assets-table"
              size="small"
              pagination={false}
              rowKey={(r) => r.instrument_code}
              dataSource={result.top_maturing_assets_12m}
              columns={[
                { title: "代码", dataIndex: "instrument_code" },
                { title: "名称", dataIndex: "instrument_name" },
                { title: "到期日", dataIndex: "maturity_date" },
                { title: "面值", dataIndex: "face_value", align: "right" as const },
                { title: "市值", dataIndex: "market_value", align: "right" as const },
              ]}
            />
          </Card>

          {result.warnings?.length ? (
            <Alert
              type="warning"
              showIcon
              message="提示"
              description={
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {result.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              }
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}
