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
import { Link, useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import type {
  AdbCategoryItem,
  AdbMonthlyBreakdownItem,
  AdbMonthlyDataItem,
  ResultMeta,
} from "../../../api/contracts";
import AdbComparisonChart, { type AdbComparisonChartRow } from "./AdbComparisonChart";
import AdbMonthlyHorizontalChart, {
  type AdbMonthlyHorizontalChartRow,
} from "./AdbMonthlyHorizontalChart";
import AdbMonthlyBreakdownTable from "./AdbMonthlyBreakdownTable";

const { Title, Paragraph, Text } = Typography;
const YI = 100_000_000;

type RangeKey = "7d" | "30d" | "ytd" | "custom";
type PageTab = "daily" | "monthly";
type BreakdownKind = "asset" | "liability";
type MonthlyBarRow = AdbMonthlyHorizontalChartRow;

const pageHeaderStyle = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: 16,
  marginBottom: 24,
} as const;

const pageSubtitleStyle = {
  marginTop: 8,
  marginBottom: 0,
  maxWidth: 920,
  color: "#5c6b82",
  fontSize: 14,
  lineHeight: 1.7,
} as const;

const modeBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "8px 12px",
  borderRadius: 999,
  background: "#edf3ff",
  color: "#1f5eff",
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
} as const;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: 6,
  marginTop: 4,
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
  maxWidth: 900,
  color: "#5c6b82",
  fontSize: 13,
  lineHeight: 1.7,
} as const;

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

function buildDetailColumns(kind: BreakdownKind): ColumnsType<AdbCategoryItem> {
  return [
    { title: "分类", dataIndex: "category", key: "category" },
    { title: "期末时点（亿元）", dataIndex: "spot_balance", key: "spot_balance", align: "right", render: (value: number) => (value / YI).toFixed(2) },
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

function ResultMetaNotice(props: {
  meta?: ResultMeta;
  testId: string;
}) {
  if (!props.meta) return null;
  const hasQualityIssue =
    props.meta.quality_flag !== "ok" || props.meta.fallback_mode !== "none";
  const qualityLabel =
    props.meta.quality_flag === "ok"
      ? "正常"
      : props.meta.quality_flag === "warning"
        ? "预警"
        : props.meta.quality_flag === "error"
          ? "错误"
          : props.meta.quality_flag === "stale"
            ? "陈旧"
            : props.meta.quality_flag;
  const fallbackLabel =
    props.meta.fallback_mode === "none"
      ? "未降级"
      : props.meta.fallback_mode === "latest_snapshot"
        ? "最新快照降级"
        : props.meta.fallback_mode;
  return (
    <Alert
      data-testid={props.testId}
      type={hasQualityIssue ? "warning" : "info"}
      showIcon
      message={[
        `日均余额后端链路：${props.meta.result_kind}`,
        props.meta.basis,
        `来源=${props.meta.source_version}`,
        `规则=${props.meta.rule_version}`,
        `质量=${qualityLabel}`,
        `降级=${fallbackLabel}`,
      ].join(" · ")}
    />
  );
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

  const formalAnalysisHref = useMemo(() => {
    const params = new URLSearchParams();
    if (reportDate) params.set("report_date", reportDate);
    params.set("position_scope", "all");
    params.set("currency_basis", "CNY");
    return `/balance-analysis?${params.toString()}`;
  }, [reportDate]);

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

  const comparisonRows = useMemo<AdbComparisonChartRow[]>(() => {
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
      <div style={pageHeaderStyle}>
        <div>
          <Title level={2} data-testid="average-balance-page-title" style={{ margin: 0 }}>
            日均管理
          </Title>
          <Paragraph data-testid="average-balance-page-subtitle" style={pageSubtitleStyle}>
            聚焦期末时点与日均偏离、区间日均结构与月度 NIM 变化。页面只消费后端返回结果，
            不在前端补算正式金融口径，正式资产负债分析仍从专用正式页面进入。
          </Paragraph>
          <Space size="small" style={{ marginTop: 10, flexWrap: "wrap" }}>
            <Text type="secondary">当前页面为资产负债分析的分析口径子视图。</Text>
            <Link to={formalAnalysisHref}>打开正式资产负债分析</Link>
          </Space>
        </div>
        <span style={modeBadgeStyle}>
          {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
        </span>
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
                <SectionLead
                  eyebrow="日度"
                  title="区间日均分析"
                  description="先选择报告日和观察区间，再阅读期末时点与日均偏离、收益成本和分类明细；这里保持分析口径视图，不提升为正式口径。"
                />
                <Card size="small">
                  <Row gutter={[16, 16]} align="middle" justify="space-between">
                    <Col flex="auto">
                      <FilterBar>
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
                        <Button type={rangeKey === "7d" ? "primary" : "default"} onClick={() => applyPreset("7d")}>7日</Button>
                        <Button type={rangeKey === "30d" ? "primary" : "default"} onClick={() => applyPreset("30d")}>30日</Button>
                        <Button type={rangeKey === "ytd" ? "primary" : "default"} onClick={() => applyPreset("ytd")}>年初至今</Button>
                        <Input aria-label="adb-start-date" type="date" value={startDate} onChange={(event) => onCustomRangeChange("start", event.target.value)} style={{ width: 160 }} />
                        <Input aria-label="adb-end-date" type="date" value={endDate} onChange={(event) => onCustomRangeChange("end", event.target.value)} style={{ width: 160 }} />
                      </FilterBar>
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
                    <Alert type="info" showIcon message={`口径说明：期末时点=期末（${dailyData.end_date}）时点规模；区间日均=区间日均规模`} />
                    <ResultMetaNotice
                      meta={dailyData.result_meta}
                      testId="adb-daily-result-meta"
                    />
                    {deviationWarning ? <Alert type="warning" showIcon message={deviationWarning} /> : null}

                    <Row gutter={[16, 16]}>
                      {[
                        { title: "期末时点总资产", value: formatYi(dailyData.total_spot_assets) },
                        { title: "日均总资产", value: formatYi(dailyData.total_avg_assets) },
                        { title: "偏离度（资产）", value: formatSignedPct(assetDeviationPct), danger: assetDeviationPct > 5 },
                        { title: "期末时点总负债", value: formatYi(dailyData.total_spot_liabilities) },
                        { title: "日均总负债", value: formatYi(dailyData.total_avg_liabilities) },
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

                    <Card title="期末时点与日均偏离对比" size="small">
                      <AdbComparisonChart rows={comparisonRows} />
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
                <SectionLead
                  eyebrow="月度"
                  title="月度日均统计"
                  description="按年份查看年初至今日均摘要、月度汇总表和单月深度分布，继续复用后端日均余额月度读模型。"
                />
                <Card size="small">
                  <FilterBar>
                    <Text type="secondary">年份</Text>
                    <Select aria-label="adb-year" style={{ width: 140 }} value={selectedYear} options={yearOptions} onChange={setSelectedYear} />
                  </FilterBar>
                </Card>

                {monthlyQuery.isLoading ? <Spin /> : null}
                {monthlyQuery.isError ? <Alert type="error" showIcon message="月度统计加载失败" /> : null}

                {monthlyData ? (
                  <>
                    <ResultMetaNotice
                      meta={monthlyData.result_meta}
                      testId="adb-monthly-result-meta"
                    />
                    <Row gutter={[16, 16]}>
                      {[
                        { title: "年初至今日均资产", value: formatYi(monthlyData.ytd_avg_assets) },
                        { title: "年初至今日均负债", value: formatYi(monthlyData.ytd_avg_liabilities) },
                        { title: "年初至今资产收益率", value: formatPct(monthlyData.ytd_asset_yield) },
                        { title: "年初至今负债付息率", value: formatPct(monthlyData.ytd_liability_cost) },
                        { title: "年初至今净息差", value: formatPct(monthlyData.ytd_nim) },
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
                              <AdbMonthlyHorizontalChart rows={monthlyAssetRows} title={`${selectedMonthData.month_label} 资产端`} color="#2563EB" style={{ marginBottom: 16 }} />
                              <AdbMonthlyBreakdownTable rows={selectedMonthData.breakdown_assets} columns={monthlyAssetColumns} rowKeyPrefix="asset-deep" />
                            </Card>
                          </Col>
                          <Col xs={24} xl={12}>
                            <Card size="small" title="负债端分类明细">
                              <AdbMonthlyHorizontalChart rows={monthlyLiabilityRows} title={`${selectedMonthData.month_label} 负债端`} color="#DC2626" style={{ marginBottom: 16 }} />
                              <AdbMonthlyBreakdownTable rows={selectedMonthData.breakdown_liabilities} columns={monthlyLiabilityColumns} rowKeyPrefix="liability-deep" />
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
