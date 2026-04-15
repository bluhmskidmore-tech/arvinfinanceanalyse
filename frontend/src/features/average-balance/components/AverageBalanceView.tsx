import { WarningFilled } from "@ant-design/icons";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type {
  AdbCategoryItem,
  AdbMonthlyBreakdownItem,
  AdbMonthlyDataItem,
} from "../../../api/contracts";
import ReactECharts from "../../../lib/echarts";

const { Title, Paragraph, Text } = Typography;
const YI = 100_000_000;

type RangeKey = "7d" | "30d" | "ytd" | "custom";
type PageTab = "daily" | "monthly";
type BreakdownKind = "asset" | "liability";
type ComparisonChartRow = { label: string; spot: number; avg: number; deviationPct: number };
type MonthlyBarRow = { category: string; avgYi: number; weightedRate: number | null };

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value / YI).toFixed(2)} 亿元`;
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(2)}%`;
}

function formatSignedPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function toDateInput(date: Date): string {
  return [
    date.getFullYear(),
    `${date.getMonth() + 1}`.padStart(2, "0"),
    `${date.getDate()}`.padStart(2, "0"),
  ].join("-");
}

function buildPresetRange(reportDate: string, rangeKey: Exclude<RangeKey, "custom">) {
  if (!reportDate) return null;
  const end = new Date(`${reportDate}T12:00:00`);
  if (Number.isNaN(end.getTime())) return null;
  const start = new Date(end);
  if (rangeKey === "7d") start.setDate(start.getDate() - 6);
  if (rangeKey === "30d") start.setDate(start.getDate() - 29);
  if (rangeKey === "ytd") start.setMonth(0, 1);
  return { startDate: toDateInput(start), endDate: toDateInput(end) };
}

function buildComparisonOption(rows: ComparisonChartRow[]) {
  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items: { dataIndex: number }[]) => {
        if (!items.length) return "";
        const row = rows[items[0].dataIndex];
        return [
          row.label,
          `Spot：${(row.spot / YI).toFixed(2)} 亿元`,
          `ADB：${(row.avg / YI).toFixed(2)} 亿元`,
          `偏离度：${formatSignedPct(row.deviationPct)}`,
        ].join("<br/>");
      },
    },
    legend: { data: ["Spot（期末）", "ADB（日均）"], top: 0 },
    grid: { left: 24, right: 24, top: 44, bottom: 76 },
    xAxis: {
      type: "category",
      data: rows.map((row) => row.label),
      axisLabel: { interval: 0, rotate: 20, fontSize: 11 },
    },
    yAxis: { type: "value", axisLabel: { formatter: (value: number) => `${(value / YI).toFixed(0)}亿` } },
    series: [
      { name: "Spot（期末）", type: "bar", data: rows.map((row) => row.spot), itemStyle: { color: "#3b82f6" }, barGap: "10%" },
      {
        name: "ADB（日均）",
        type: "bar",
        data: rows.map((row) => row.avg),
        itemStyle: { color: "#f97316" },
        label: {
          show: true,
          position: "top",
          formatter: ({ dataIndex }: { dataIndex: number }) => formatSignedPct(rows[dataIndex]?.deviationPct ?? 0),
          color: "#475569",
          fontSize: 11,
        },
      },
    ],
  };
}

function buildHorizontalOption(rows: MonthlyBarRow[], title: string, color: string) {
  return {
    title: { text: title, left: 0, textStyle: { fontSize: 13, fontWeight: 600 } },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items: { dataIndex: number }[]) => {
        if (!items.length) return "";
        const row = rows[items[0].dataIndex];
        return [row.category, `日均：${row.avgYi.toFixed(2)} 亿元`, `加权利率：${formatPct(row.weightedRate)}`].join("<br/>");
      },
    },
    grid: { left: 120, right: 24, top: 44, bottom: 24 },
    xAxis: { type: "value", axisLabel: { formatter: (value: number) => `${value.toFixed(0)}亿` } },
    yAxis: { type: "category", data: rows.map((row) => row.category), axisLabel: { fontSize: 11 } },
    series: [
      {
        type: "bar",
        data: rows.map((row) => row.avgYi),
        itemStyle: { color },
        label: { show: true, position: "right", formatter: ({ dataIndex }: { dataIndex: number }) => rows[dataIndex]?.avgYi.toFixed(2) ?? "0.00" },
      },
    ],
  };
}

function buildDetailColumns(kind: BreakdownKind): ColumnsType<AdbCategoryItem> {
  return [
    { title: "分类", dataIndex: "category", key: "category" },
    { title: "Spot(亿元)", dataIndex: "spot_balance", key: "spot_balance", align: "right", render: (value: number) => (value / YI).toFixed(2) },
    { title: "日均(亿元)", dataIndex: "avg_balance", key: "avg_balance", align: "right", render: (value: number) => (value / YI).toFixed(2) },
    { title: "占比(%)", dataIndex: "proportion", key: "proportion", align: "right", render: (value: number) => value.toFixed(2) },
    { title: kind === "asset" ? "收益率(%)" : "付息率(%)", dataIndex: "weighted_rate", key: "weighted_rate", align: "right", render: (value: number | null | undefined) => formatPct(value) },
  ];
}

function buildMonthlyBreakdownColumns(kind: BreakdownKind): ColumnsType<AdbMonthlyBreakdownItem> {
  return [
    { title: "分类", dataIndex: "category", key: "category" },
    { title: "日均(亿元)", dataIndex: "avg_balance", key: "avg_balance", align: "right", render: (value: number) => (value / YI).toFixed(2) },
    { title: "占比(%)", dataIndex: "proportion", key: "proportion", align: "right", render: (value: number | null | undefined) => (value === null || value === undefined ? "—" : value.toFixed(2)) },
    { title: kind === "asset" ? "收益率(%)" : "付息率(%)", dataIndex: "weighted_rate", key: "weighted_rate", align: "right", render: (value: number | null | undefined) => formatPct(value) },
  ];
}

function buildMonthlyRows(breakdown: AdbMonthlyBreakdownItem[]): MonthlyBarRow[] {
  return breakdown
    .slice()
    .sort((left, right) => right.avg_balance - left.avg_balance)
    .slice(0, 10)
    .map((row) => ({ category: row.category, avgYi: row.avg_balance / YI, weightedRate: row.weighted_rate ?? null }));
}

export default function AverageBalanceView() {
  const client = useApiClient();
  const [searchParams] = useSearchParams();
  const explicitReportDate = searchParams.get("report_date")?.trim() || "";
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [activeTab, setActiveTab] = useState<PageTab>("daily");
  const [rangeKey, setRangeKey] = useState<RangeKey>("ytd");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState("");

  const datesQuery = useQuery({
    queryKey: ["average-balance", "balance-analysis-dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });

  const dateOptions = useMemo(() => {
    const dates = datesQuery.data?.result.report_dates ?? [];
    if (explicitReportDate && !dates.includes(explicitReportDate)) return [explicitReportDate, ...dates];
    return dates;
  }, [datesQuery.data?.result.report_dates, explicitReportDate]);

  const reportDate = useMemo(() => {
    if (explicitReportDate) return explicitReportDate;
    return selectedReportDate || datesQuery.data?.result.report_dates[0] || "";
  }, [datesQuery.data?.result.report_dates, explicitReportDate, selectedReportDate]);

  useEffect(() => {
    if (rangeKey === "custom") return;
    const range = buildPresetRange(reportDate, rangeKey);
    if (!range) return;
    setStartDate(range.startDate);
    setEndDate(range.endDate);
  }, [rangeKey, reportDate]);

  useEffect(() => {
    const year = Number(reportDate.slice(0, 4));
    if (Number.isFinite(year) && year > 0) setSelectedYear(year);
  }, [reportDate]);

  const comparisonQuery = useQuery({
    queryKey: ["average-balance", "comparison", client.mode, startDate, endDate],
    queryFn: () => client.getAdbComparison(startDate, endDate),
    enabled: activeTab === "daily" && Boolean(startDate && endDate),
    retry: false,
  });

  const monthlyQuery = useQuery({
    queryKey: ["average-balance", "monthly", client.mode, selectedYear],
    queryFn: () => client.getAdbMonthly(selectedYear),
    enabled: activeTab === "monthly",
    retry: false,
  });

  useEffect(() => {
    const months = monthlyQuery.data?.months ?? [];
    if (!months.length) {
      setSelectedMonth("");
      return;
    }
    if (!selectedMonth || !months.some((item) => item.month === selectedMonth)) {
      setSelectedMonth(months[0].month);
    }
  }, [monthlyQuery.data?.months, selectedMonth]);

  const dailyData = comparisonQuery.data;
  const dailyBootstrapBlocked = !explicitReportDate && datesQuery.isError;
  const canRunDailyQuery = Boolean(startDate && endDate) && !dailyBootstrapBlocked;
  const assetDeviationPct =
    dailyData && dailyData.total_avg_assets > 0
      ? ((dailyData.total_spot_assets - dailyData.total_avg_assets) / dailyData.total_avg_assets) * 100
      : 0;
  const liabilityDeviationPct =
    dailyData && dailyData.total_avg_liabilities > 0
      ? ((dailyData.total_spot_liabilities - dailyData.total_avg_liabilities) / dailyData.total_avg_liabilities) * 100
      : 0;

  const comparisonRows = useMemo<ComparisonChartRow[]>(() => {
    if (!dailyData) return [];
    const mapRows = (items: AdbCategoryItem[], prefix: string) =>
      items.map((item) => ({
        label: `${prefix} · ${item.category}`,
        spot: item.spot_balance,
        avg: item.avg_balance,
        deviationPct: item.avg_balance > 0 ? ((item.spot_balance - item.avg_balance) / item.avg_balance) * 100 : 0,
      }));
    return [...mapRows(dailyData.assets_breakdown, "资产"), ...mapRows(dailyData.liabilities_breakdown, "负债")];
  }, [dailyData]);

  const monthlyData = monthlyQuery.data;
  const selectedMonthData = monthlyData?.months.find((item) => item.month === selectedMonth) ?? null;
  const monthlyAssetRows = useMemo(() => buildMonthlyRows(selectedMonthData?.breakdown_assets ?? []), [selectedMonthData?.breakdown_assets]);
  const monthlyLiabilityRows = useMemo(() => buildMonthlyRows(selectedMonthData?.breakdown_liabilities ?? []), [selectedMonthData?.breakdown_liabilities]);

  const dailyAssetColumns = useMemo(() => buildDetailColumns("asset"), []);
  const dailyLiabilityColumns = useMemo(() => buildDetailColumns("liability"), []);
  const monthlyAssetColumns = useMemo(() => buildMonthlyBreakdownColumns("asset"), []);
  const monthlyLiabilityColumns = useMemo(() => buildMonthlyBreakdownColumns("liability"), []);

  const monthlyTableColumns: ColumnsType<AdbMonthlyDataItem> = useMemo(
    () => [
      { title: "月份", dataIndex: "month_label", key: "month_label", render: (value: string) => <Text strong>{value}</Text> },
      { title: "天数", dataIndex: "num_days", key: "num_days", align: "right" },
      { title: "日均资产(亿元)", dataIndex: "avg_assets", key: "avg_assets", align: "right", render: (value: number) => (value / YI).toFixed(2) },
      { title: "日均负债(亿元)", dataIndex: "avg_liabilities", key: "avg_liabilities", align: "right", render: (value: number) => (value / YI).toFixed(2) },
      { title: "资产收益率", dataIndex: "asset_yield", key: "asset_yield", align: "right", render: (value: number | null) => formatPct(value) },
      { title: "负债付息率", dataIndex: "liability_cost", key: "liability_cost", align: "right", render: (value: number | null) => formatPct(value) },
      {
        title: "NIM",
        dataIndex: "net_interest_margin",
        key: "net_interest_margin",
        align: "right",
        render: (value: number | null) => <Text type={value !== null && value < 0 ? "danger" : undefined}>{formatPct(value)}</Text>,
      },
      {
        title: "资产环比",
        dataIndex: "mom_change_pct_assets",
        key: "mom_change_pct_assets",
        align: "right",
        render: (_value: number | null, row) => formatSignedPct(row.mom_change_pct_assets ?? row.mom_change_assets),
      },
      {
        title: "负债环比",
        dataIndex: "mom_change_pct_liabilities",
        key: "mom_change_pct_liabilities",
        align: "right",
        render: (_value: number | null, row) => formatSignedPct(row.mom_change_pct_liabilities ?? row.mom_change_liabilities),
      },
    ],
    [],
  );

  const yearOptions = useMemo(() => {
    const reportYear = Number(reportDate.slice(0, 4));
    const currentYear = new Date().getFullYear();
    return Array.from(new Set([currentYear - 2, currentYear - 1, currentYear, reportYear].filter((item) => Number.isFinite(item) && item > 0)))
      .sort((left, right) => right - left)
      .map((item) => ({ label: `${item}`, value: item }));
  }, [reportDate]);

  const applyPreset = (nextKey: Exclude<RangeKey, "custom">) => {
    setRangeKey(nextKey);
    const range = buildPresetRange(reportDate, nextKey);
    if (!range) return;
    setStartDate(range.startDate);
    setEndDate(range.endDate);
  };

  const onCustomRangeChange = (field: "start" | "end", value: string) => {
    setRangeKey("custom");
    if (field === "start") {
      setStartDate(value);
      return;
    }
    setEndDate(value);
  };

  const deviationWarning =
    assetDeviationPct > 5 || liabilityDeviationPct > 5
      ? "偏离度 > 5%，存在“窗口粉饰”风险，请结合实际头寸变化核查。"
      : null;
  const dailyErrorMessage = dailyBootstrapBlocked
    ? "可用报告日加载失败，请先恢复报告日列表后再查看日均分析。"
    : datesQuery.isError
      ? "可用报告日加载失败"
      : comparisonQuery.isError
        ? "日均分析加载失败"
        : null;

  return (
    <section data-testid="average-balance-page">
      <div style={{ marginBottom: 24 }}>
        <Title level={2} style={{ margin: 0 }}>
          日均管理
        </Title>
        <Paragraph style={{ marginTop: 8, marginBottom: 0, maxWidth: 920, color: "#5c6b82" }}>
          聚焦 Spot vs ADB 偏离、区间日均结构与月度 NIM 变化。页面只消费后端返回结果，不在前端补算正式金融口径。
        </Paragraph>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as PageTab)}
        destroyOnHidden
        items={[
          {
            key: "daily",
            label: "日均分析",
            children: (
              <Space direction="vertical" size="large" style={{ width: "100%" }}>
                <Card size="small">
                  <Row gutter={[16, 16]} align="middle" justify="space-between">
                    <Col flex="auto">
                      <Space wrap>
                        <Text type="secondary">报告日</Text>
                        <Select
                          aria-label="adb-report-date"
                          style={{ minWidth: 160 }}
                          value={reportDate || undefined}
                          options={dateOptions.map((item) => ({ label: item, value: item }))}
                          onChange={setSelectedReportDate}
                          disabled={Boolean(explicitReportDate)}
                          placeholder="选择日期"
                        />
                        <Button type={rangeKey === "7d" ? "primary" : "default"} onClick={() => applyPreset("7d")}>7D</Button>
                        <Button type={rangeKey === "30d" ? "primary" : "default"} onClick={() => applyPreset("30d")}>30D</Button>
                        <Button type={rangeKey === "ytd" ? "primary" : "default"} onClick={() => applyPreset("ytd")}>YTD</Button>
                        <Input aria-label="adb-start-date" type="date" value={startDate} onChange={(event) => onCustomRangeChange("start", event.target.value)} style={{ width: 160 }} />
                        <Input aria-label="adb-end-date" type="date" value={endDate} onChange={(event) => onCustomRangeChange("end", event.target.value)} style={{ width: 160 }} />
                      </Space>
                    </Col>
                    <Col>
                      <Text strong>有效天数：{dailyData?.num_days ?? "—"} 天</Text>
                    </Col>
                  </Row>
                  {dailyData?.simulated ? (
                    <Alert style={{ marginTop: 16 }} type="info" showIcon message="当前区间仅 1 天时，日均为稳态模拟，便于演示图表逻辑" />
                  ) : null}
                </Card>

                {datesQuery.isLoading || comparisonQuery.isLoading ? <Spin /> : null}
                {dailyErrorMessage ? <Alert type="error" showIcon message={dailyErrorMessage} /> : null}
                {!datesQuery.isLoading &&
                !datesQuery.isError &&
                !explicitReportDate &&
                dateOptions.length === 0 ? (
                  <Alert type="warning" showIcon message="暂无可用报告日，暂无法展示日均分析。" />
                ) : null}

                {canRunDailyQuery && dailyData ? (
                  <>
                    <Alert type="info" showIcon message={`口径说明：Spot=期末（${dailyData.end_date}）时点规模；Avg=区间日均规模`} />
                    {deviationWarning ? <Alert type="warning" showIcon message={deviationWarning} /> : null}

                    <Row gutter={[16, 16]}>
                      {[
                        { title: "Spot 总资产", value: formatYi(dailyData.total_spot_assets) },
                        { title: "ADB 总资产", value: formatYi(dailyData.total_avg_assets) },
                        { title: "偏离度（资产）", value: formatSignedPct(assetDeviationPct), danger: assetDeviationPct > 5 },
                        { title: "Spot 总负债", value: formatYi(dailyData.total_spot_liabilities) },
                        { title: "ADB 总负债", value: formatYi(dailyData.total_avg_liabilities) },
                        { title: "偏离度（负债）", value: formatSignedPct(liabilityDeviationPct), danger: liabilityDeviationPct > 5 },
                      ].map((item) => (
                        <Col xs={24} sm={12} xl={8} key={item.title}>
                          <Card size="small">
                            <Text type="secondary">{item.title}</Text>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10 }}>
                              <Title level={4} style={{ margin: 0 }} type={item.danger ? "danger" : undefined}>
                                {item.value}
                              </Title>
                              {item.danger ? <WarningFilled style={{ color: "#cf1322", fontSize: 16 }} /> : null}
                            </div>
                          </Card>
                        </Col>
                      ))}
                    </Row>

                    <Row gutter={[16, 16]}>
                      {[
                        { title: "资产收益率（年化）", value: formatPct(dailyData.asset_yield) },
                        { title: "负债付息率（年化）", value: formatPct(dailyData.liability_cost) },
                        { title: "NIM（年化）", value: formatPct(dailyData.net_interest_margin), danger: dailyData.net_interest_margin !== null && dailyData.net_interest_margin < 0 },
                      ].map((item) => (
                        <Col xs={24} md={8} key={item.title}>
                          <Card size="small">
                            <Text type="secondary">{item.title}</Text>
                            <Title level={4} style={{ marginTop: 10, marginBottom: 0 }} type={item.danger ? "danger" : undefined}>
                              {item.value}
                            </Title>
                          </Card>
                        </Col>
                      ))}
                    </Row>

                    <Card title="Spot vs ADB 偏离对比" size="small">
                      <ReactECharts option={buildComparisonOption(comparisonRows)} style={{ height: 420 }} notMerge lazyUpdate />
                    </Card>

                    <Row gutter={[16, 16]}>
                      <Col xs={24} xl={12}>
                        <Card title="资产端分类明细" size="small">
                          <Table size="small" pagination={false} rowKey={(row) => `asset-${row.category}`} columns={dailyAssetColumns} dataSource={dailyData.assets_breakdown} locale={{ emptyText: "暂无数据" }} />
                        </Card>
                      </Col>
                      <Col xs={24} xl={12}>
                        <Card title="负债端分类明细" size="small">
                          <Table size="small" pagination={false} rowKey={(row) => `liability-${row.category}`} columns={dailyLiabilityColumns} dataSource={dailyData.liabilities_breakdown} locale={{ emptyText: "暂无数据" }} />
                        </Card>
                      </Col>
                    </Row>
                  </>
                ) : null}
              </Space>
            ),
          },
          {
            key: "monthly",
            label: "月度统计",
            children: (
              <Space direction="vertical" size="large" style={{ width: "100%" }}>
                <Card size="small">
                  <Space wrap>
                    <Text type="secondary">年份</Text>
                    <Select aria-label="adb-year" style={{ width: 140 }} value={selectedYear} options={yearOptions} onChange={setSelectedYear} />
                  </Space>
                </Card>

                {monthlyQuery.isLoading ? <Spin /> : null}
                {monthlyQuery.isError ? <Alert type="error" showIcon message="月度统计加载失败" /> : null}

                {monthlyData ? (
                  <>
                    <Row gutter={[16, 16]}>
                      {[
                        { title: "YTD 日均资产", value: formatYi(monthlyData.ytd_avg_assets) },
                        { title: "YTD 日均负债", value: formatYi(monthlyData.ytd_avg_liabilities) },
                        { title: "YTD 资产收益率", value: formatPct(monthlyData.ytd_asset_yield) },
                        { title: "YTD 负债付息率", value: formatPct(monthlyData.ytd_liability_cost) },
                        { title: "YTD NIM", value: formatPct(monthlyData.ytd_nim) },
                      ].map((item) => (
                        <Col xs={24} sm={12} xl={4} key={item.title}>
                          <Card size="small">
                            <Text type="secondary">{item.title}</Text>
                            <Title level={4} style={{ marginTop: 10, marginBottom: 0 }}>{item.value}</Title>
                          </Card>
                        </Col>
                      ))}
                    </Row>

                    <Card title="月度汇总表" size="small">
                      <Table<AdbMonthlyDataItem>
                        size="small"
                        rowKey={(row) => row.month}
                        pagination={false}
                        columns={monthlyTableColumns}
                        dataSource={monthlyData.months}
                        expandable={{
                          expandedRowRender: (row) => (
                            <Row gutter={[16, 16]}>
                              <Col xs={24} xl={12}>
                                <Card size="small" title="资产端分类明细">
                                  <Table size="small" pagination={false} rowKey={(item) => `expanded-asset-${row.month}-${item.category}`} columns={monthlyAssetColumns} dataSource={row.breakdown_assets} />
                                </Card>
                              </Col>
                              <Col xs={24} xl={12}>
                                <Card size="small" title="负债端分类明细">
                                  <Table size="small" pagination={false} rowKey={(item) => `expanded-liability-${row.month}-${item.category}`} columns={monthlyLiabilityColumns} dataSource={row.breakdown_liabilities} />
                                </Card>
                              </Col>
                            </Row>
                          ),
                        }}
                      />
                    </Card>

                    {selectedMonthData ? (
                      <Card
                        title="按月度日均分析 - 深度分析"
                        size="small"
                        extra={<Select aria-label="adb-month" style={{ width: 160 }} value={selectedMonth} options={monthlyData.months.map((item) => ({ label: item.month_label, value: item.month }))} onChange={setSelectedMonth} />}
                      >
                        <Row gutter={[16, 16]}>
                          <Col xs={24} xl={12}>
                            <Card size="small" title="资产端分类明细">
                              <ReactECharts option={buildHorizontalOption(monthlyAssetRows, `${selectedMonthData.month_label} 资产端`, "#2563EB")} style={{ height: 320, marginBottom: 16 }} notMerge lazyUpdate />
                              <Table size="small" pagination={false} rowKey={(row) => `asset-deep-${row.category}`} columns={monthlyAssetColumns} dataSource={selectedMonthData.breakdown_assets} />
                            </Card>
                          </Col>
                          <Col xs={24} xl={12}>
                            <Card size="small" title="负债端分类明细">
                              <ReactECharts option={buildHorizontalOption(monthlyLiabilityRows, `${selectedMonthData.month_label} 负债端`, "#DC2626")} style={{ height: 320, marginBottom: 16 }} notMerge lazyUpdate />
                              <Table size="small" pagination={false} rowKey={(row) => `liability-deep-${row.category}`} columns={monthlyLiabilityColumns} dataSource={selectedMonthData.breakdown_liabilities} />
                            </Card>
                          </Col>
                        </Row>
                      </Card>
                    ) : null}
                  </>
                ) : null}
              </Space>
            ),
          },
        ]}
      />
    </section>
  );
}
