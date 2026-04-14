import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Card,
  Col,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import ReactECharts from "echarts-for-react";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type { AdbBreakdownItem, AdbComparisonRow, AdbMonthlyItem } from "../../../api/contracts";

const { Title, Text } = Typography;

type RangeKey = "7d" | "30d" | "ytd";
type PageTab = "daily" | "monthly";

const YI = 100_000_000;

function formatYi(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v / YI).toFixed(2)} 亿元`;
}

function formatPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${v.toFixed(2)}%`;
}

function rangeToParams(endDate: string, range: RangeKey): { start_date: string; end_date: string } | null {
  if (!endDate) return null;
  const end = new Date(`${endDate}T12:00:00`);
  if (Number.isNaN(end.getTime())) return null;
  const yyyy = end.getFullYear();
  const mm = String(end.getMonth() + 1).padStart(2, "0");
  const dd = String(end.getDate()).padStart(2, "0");
  const endStr = `${yyyy}-${mm}-${dd}`;
  let startStr = endStr;
  if (range === "7d") {
    const s = new Date(end);
    s.setDate(s.getDate() - 6);
    startStr = `${s.getFullYear()}-${String(s.getMonth() + 1).padStart(2, "0")}-${String(s.getDate()).padStart(2, "0")}`;
  } else if (range === "30d") {
    const s = new Date(end);
    s.setDate(s.getDate() - 29);
    startStr = `${s.getFullYear()}-${String(s.getMonth() + 1).padStart(2, "0")}-${String(s.getDate()).padStart(2, "0")}`;
  } else {
    startStr = `${yyyy}-01-01`;
  }
  return { start_date: startStr, end_date: endStr };
}

function deviationAlert(rows: AdbComparisonRow[]): { show: boolean; detail: string } {
  const pos = rows.filter((r) => r.deviation > 0);
  if (pos.length === 0) return { show: false, detail: "" };
  const top = [...pos].sort((a, b) => b.deviation - a.deviation)[0];
  const rel = top.avg > 0 ? top.deviation / top.avg : 0;
  const absOk = top.deviation >= 0.5 * YI;
  const relOk = rel >= 0.05;
  if (!absOk && !relOk) return { show: false, detail: "" };
  return {
    show: true,
    detail: `「${top.category}」期末时点高于区间日均约 ${formatYi(top.deviation)}，可能存在窗口粉饰 / 月末冲量 — 请结合业务核实。`,
  };
}

export default function AverageBalanceView() {
  const client = useApiClient();
  const [searchParams] = useSearchParams();
  const explicitReportDate = searchParams.get("report_date")?.trim() || "";

  const datesQuery = useQuery({
    queryKey: ["average-balance", "balance-analysis-dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });

  const dateOptions = useMemo(() => {
    const dates = datesQuery.data?.result.report_dates ?? [];
    if (explicitReportDate && !dates.includes(explicitReportDate)) {
      return [explicitReportDate, ...dates];
    }
    return dates;
  }, [datesQuery.data?.result.report_dates, explicitReportDate]);

  const [selectedReportDate, setSelectedReportDate] = useState("");
  const reportDate = useMemo(() => {
    if (explicitReportDate) return explicitReportDate;
    return selectedReportDate || datesQuery.data?.result.report_dates[0] || "";
  }, [datesQuery.data?.result.report_dates, explicitReportDate, selectedReportDate]);

  const [range, setRange] = useState<RangeKey>("30d");
  const [activeTab, setActiveTab] = useState<PageTab>("daily");
  const [selectedYear, setSelectedYear] = useState(() => new Date().getFullYear());
  const [expandedMonth, setExpandedMonth] = useState<string | null>(null);
  const [selectedMonthForBreakdown, setSelectedMonthForBreakdown] = useState("");

  const rangeParams = useMemo(() => rangeToParams(reportDate, range), [reportDate, range]);

  const adbQuery = useQuery({
    queryKey: ["average-balance", "adb", client.mode, rangeParams?.start_date, rangeParams?.end_date],
    queryFn: async () => {
      const p = rangeParams!;
      return client.getAdb({ startDate: p.start_date, endDate: p.end_date });
    },
    enabled: activeTab === "daily" && Boolean(rangeParams),
    retry: false,
  });

  const cmpQuery = useQuery({
    queryKey: ["average-balance", "adb-cmp", client.mode, rangeParams?.start_date, rangeParams?.end_date],
    queryFn: async () => {
      const p = rangeParams!;
      return client.getAdbComparison({ startDate: p.start_date, endDate: p.end_date, topN: 20 });
    },
    enabled: activeTab === "daily" && Boolean(rangeParams),
    retry: false,
  });

  const monthlyQuery = useQuery({
    queryKey: ["average-balance", "adb-monthly", client.mode, selectedYear],
    queryFn: () => client.getAdbMonthly(selectedYear),
    enabled: activeTab === "monthly",
    retry: false,
  });

  useEffect(() => {
    const months = monthlyQuery.data?.months ?? [];
    if (months.length > 0 && !selectedMonthForBreakdown) {
      setSelectedMonthForBreakdown(months[0].month);
    }
  }, [monthlyQuery.data?.months, selectedMonthForBreakdown]);

  const selectedMonthData = useMemo(() => {
    return monthlyQuery.data?.months.find((m) => m.month === selectedMonthForBreakdown) ?? null;
  }, [monthlyQuery.data?.months, selectedMonthForBreakdown]);

  const assetRows = useMemo(
    () => (adbQuery.data?.breakdown ?? []).filter((x) => x.side === "Asset"),
    [adbQuery.data?.breakdown],
  );
  const liabilityRows = useMemo(
    () => (adbQuery.data?.breakdown ?? []).filter((x) => x.side === "Liability"),
    [adbQuery.data?.breakdown],
  );

  const assetTotal = useMemo(() => assetRows.reduce((s, x) => s + (Number(x.avg_balance) || 0), 0), [assetRows]);
  const liabilityTotal = useMemo(
    () => liabilityRows.reduce((s, x) => s + (Number(x.avg_balance) || 0), 0),
    [liabilityRows],
  );
  const assetMax = useMemo(
    () => assetRows.reduce((m, x) => Math.max(m, Number(x.avg_balance) || 0), 0),
    [assetRows],
  );
  const liabilityMax = useMemo(
    () => liabilityRows.reduce((m, x) => Math.max(m, Number(x.avg_balance) || 0), 0),
    [liabilityRows],
  );

  const cmpAssets = useMemo(
    () =>
      (cmpQuery.data?.assets ?? []).map((it) => ({
        category: it.category,
        spot_yi: (it.spot || 0) / YI,
        avg_yi: (it.avg || 0) / YI,
        deviation_yi: (it.deviation || 0) / YI,
      })),
    [cmpQuery.data?.assets],
  );
  const cmpLiab = useMemo(
    () =>
      (cmpQuery.data?.liabilities ?? []).map((it) => ({
        category: it.category,
        spot_yi: (it.spot || 0) / YI,
        avg_yi: (it.avg || 0) / YI,
        deviation_yi: (it.deviation || 0) / YI,
      })),
    [cmpQuery.data?.liabilities],
  );

  const dressingAssets = useMemo(
    () => deviationAlert(cmpQuery.data?.assets ?? []),
    [cmpQuery.data?.assets],
  );
  const dressingLiab = useMemo(
    () => deviationAlert(cmpQuery.data?.liabilities ?? []),
    [cmpQuery.data?.liabilities],
  );

  const trendOption = useMemo(() => {
    const data = adbQuery.data?.trend ?? [];
    return {
      tooltip: { trigger: "axis" },
      legend: { data: ["每日规模", "30日滚动均值"] },
      grid: { left: 48, right: 24, top: 40, bottom: 48 },
      xAxis: { type: "category", data: data.map((d) => d.date) },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (v: number) => `${(v / YI).toFixed(0)}` },
        name: "亿元",
      },
      series: [
        {
          name: "每日规模",
          type: "line",
          smooth: true,
          areaStyle: { opacity: 0.12 },
          data: data.map((d) => d.daily_balance),
        },
        {
          name: "30日滚动均值",
          type: "line",
          smooth: true,
          data: data.map((d) => d.moving_average_30d),
        },
      ],
    };
  }, [adbQuery.data?.trend]);

  function barOption(rows: { category: string; spot_yi: number; avg_yi: number }[], title: string) {
    return {
      title: { text: title, left: 0, textStyle: { fontSize: 13 } },
      tooltip: {
        trigger: "axis",
        formatter: (items: { name: string; value: number; seriesName: string; dataIndex: number }[]) => {
          if (!items?.length) return "";
          const idx = items[0].dataIndex;
          const row = rows[idx];
          if (!row) return "";
          const dev = row.spot_yi - row.avg_yi;
          const hint =
            dev > 0
              ? `时点较日均高 ${dev.toFixed(2)} 亿元（关注窗口粉饰 / 月末冲量）`
              : dev < 0
                ? `时点较日均低 ${Math.abs(dev).toFixed(2)} 亿元`
                : "时点与日均基本一致";
          return `${row.category}<br/>时点：${row.spot_yi.toFixed(2)} 亿<br/>日均：${row.avg_yi.toFixed(2)} 亿<br/><span style="color:${dev > 0 ? "#b91c1c" : "#1d4ed8"}">${hint}</span>`;
        },
      },
      grid: { left: 12, right: 12, top: 36, bottom: 72 },
      xAxis: {
        type: "category",
        data: rows.map((r) => r.category),
        axisLabel: { rotate: 25, fontSize: 10 },
      },
      yAxis: { type: "value", name: "亿元" },
      series: [
        { name: "时点", type: "bar", data: rows.map((r) => r.spot_yi), itemStyle: { color: "#2563eb" } },
        { name: "日均", type: "bar", data: rows.map((r) => r.avg_yi), itemStyle: { color: "#93c5fd" } },
      ],
    };
  }

  const breakdownColumns: ColumnsType<AdbBreakdownItem> = [
    { title: "类别", dataIndex: "category", key: "category" },
    {
      title: "日均(亿元)",
      dataIndex: "avg_balance",
      key: "avg_balance",
      align: "right",
      render: (v: number) => (v / YI).toFixed(2),
    },
    {
      title: "占比",
      key: "pct",
      align: "right",
      render: (_: unknown, row) => {
        const total = row.side === "Asset" ? assetTotal : liabilityTotal;
        const pct = total > 0 ? (row.avg_balance / total) * 100 : 0;
        return `${pct.toFixed(2)}%`;
      },
    },
    {
      title: "规模条",
      key: "bar",
      render: (_: unknown, row) => {
        const total = row.side === "Asset" ? assetTotal : liabilityTotal;
        const max = row.side === "Asset" ? assetMax : liabilityMax;
        const pct = total > 0 ? (row.avg_balance / total) * 100 : 0;
        const w = max > 0 ? Math.min(100, (row.avg_balance / max) * 100) : 0;
        return (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>
              {pct.toFixed(1)}%
            </Text>
            <div style={{ height: 6, background: "#f1f5f9", borderRadius: 2 }}>
              <div
                style={{
                  width: `${w}%`,
                  height: 6,
                  borderRadius: 2,
                  background: row.side === "Asset" ? "#2563eb" : "#dc2626",
                }}
              />
            </div>
          </div>
        );
      },
    },
  ];

  const monthlyColumns: ColumnsType<AdbMonthlyItem> = [
    {
      title: "月份",
      dataIndex: "month_label",
      key: "ml",
      render: (t: string) => <Text strong>{t}</Text>,
    },
    { title: "日均资产", dataIndex: "avg_assets", key: "aa", align: "right", render: (v: number) => formatYi(v) },
    { title: "日均负债", dataIndex: "avg_liabilities", key: "al", align: "right", render: (v: number) => formatYi(v) },
    {
      title: "资产环比",
      dataIndex: "assets_mom_change",
      key: "am",
      align: "right",
      render: (v: number | null) =>
        v === null || v === undefined ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`,
    },
    {
      title: "负债环比",
      dataIndex: "liabilities_mom_change",
      key: "lm",
      align: "right",
      render: (v: number | null) =>
        v === null || v === undefined ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`,
    },
    {
      title: "收益率",
      dataIndex: "asset_yield",
      key: "ay",
      align: "right",
      render: (v: number | null) => formatPct(v),
    },
    {
      title: "付息率",
      dataIndex: "liability_cost",
      key: "lc",
      align: "right",
      render: (v: number | null) => formatPct(v),
    },
    {
      title: "净息差",
      dataIndex: "net_interest_margin",
      key: "nim",
      align: "right",
      render: (v: number | null) => (
        <Text type={v !== null && v < 0 ? "danger" : undefined}>{formatPct(v)}</Text>
      ),
    },
    { title: "天数", dataIndex: "num_days", key: "nd", align: "right" },
  ];

  const loadingDaily = adbQuery.isLoading || datesQuery.isLoading;
  const errorDaily = adbQuery.error ? String(adbQuery.error) : null;

  return (
    <div style={{ padding: 16 }}>
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <Row justify="space-between" align="middle" gutter={[16, 16]}>
          <Col flex="auto">
            <Title level={3} style={{ margin: 0 }}>
              日均资产负债（ADB）
            </Title>
            <Text type="secondary">
              {activeTab === "daily" && rangeParams
                ? `区间：${rangeParams.start_date} ~ ${rangeParams.end_date}`
                : `${selectedYear} 年度月度统计`}
            </Text>
          </Col>
          <Col>
            <Tabs
              activeKey={activeTab}
              onChange={(k) => setActiveTab(k as PageTab)}
              items={[
                { key: "daily", label: "日均分析" },
                { key: "monthly", label: "月度统计" },
              ]}
            />
          </Col>
          {activeTab === "daily" && (
            <Col>
              <Space>
                <Text type="secondary">报告日</Text>
                <Select
                  style={{ minWidth: 160 }}
                  value={reportDate || undefined}
                  options={dateOptions.map((d) => ({ label: d, value: d }))}
                  onChange={(v) => setSelectedReportDate(v)}
                  disabled={Boolean(explicitReportDate)}
                  placeholder="选择日期"
                />
              </Space>
            </Col>
          )}
        </Row>

        {activeTab === "daily" && (
          <>
            {errorDaily && (
              <Alert type="error" message="日均分析加载失败" description={errorDaily} showIcon />
            )}
            <Segmented<RangeKey>
              value={range}
              onChange={(v) => setRange(v)}
              options={[
                { label: "近7天", value: "7d" },
                { label: "近30天", value: "30d" },
                { label: "本年至今(YTD)", value: "ytd" },
              ]}
            />

            {loadingDaily ? (
              <Spin tip="加载中…" />
            ) : (
              <>
                <Row gutter={[16, 16]}>
                  {[
                    ["资产期末时点", adbQuery.data?.summary.end_spot_assets],
                    ["资产区间日均", adbQuery.data?.summary.total_avg_assets],
                    ["负债期末时点", adbQuery.data?.summary.end_spot_liabilities],
                    ["负债区间日均", adbQuery.data?.summary.total_avg_liabilities],
                  ].map(([label, val]) => (
                    <Col xs={24} sm={12} lg={6} key={String(label)}>
                      <Card size="small">
                        <Text type="secondary">{label}</Text>
                        <Title level={4} style={{ marginTop: 8 }}>
                          {formatYi(val as number)}
                        </Title>
                      </Card>
                    </Col>
                  ))}
                </Row>

                <Card title="资产规模趋势（Spot vs 滚动日均）" size="small">
                  <ReactECharts option={trendOption} style={{ height: 360 }} notMerge lazyUpdate />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    浅线：每日实际规模；深线：30日滚动均值（不足 30 天按可用窗口）。Y 轴单位：亿元。
                  </Text>
                </Card>

                {(dressingAssets.show || dressingLiab.show) && (
                  <Alert
                    type="warning"
                    showIcon
                    message="窗口粉饰风险提示"
                    description={
                      <div>
                        {dressingAssets.show && <div>资产端：{dressingAssets.detail}</div>}
                        {dressingLiab.show && <div>负债端：{dressingLiab.detail}</div>}
                      </div>
                    }
                  />
                )}

                <Card
                  title="时点 vs 日均偏离（按类别）"
                  size="small"
                  extra={
                    <Space direction="vertical" align="end" size={0}>
                      {cmpQuery.data?.simulated && (
                        <Text type="warning" style={{ fontSize: 12 }}>
                          当前区间仅 1 天：已启用稳态模拟日均（与 V1 一致，便于展示对比逻辑）
                        </Text>
                      )}
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        Spot=期末时点；Avg=区间日均（元口径聚合，图内为亿元）
                      </Text>
                    </Space>
                  }
                >
                  {cmpQuery.isLoading ? (
                    <Spin />
                  ) : cmpQuery.isError ? (
                    <Alert type="error" message={String(cmpQuery.error)} />
                  ) : (
                    <Row gutter={[16, 16]}>
                      <Col xs={24} lg={12}>
                        <ReactECharts
                          option={barOption(cmpAssets, "资产端 Top偏离")}
                          style={{ height: 380 }}
                          notMerge
                          lazyUpdate
                        />
                      </Col>
                      <Col xs={24} lg={12}>
                        <ReactECharts
                          option={barOption(cmpLiab, "负债端 Top 偏离")}
                          style={{ height: 380 }}
                          notMerge
                          lazyUpdate
                        />
                      </Col>
                    </Row>
                  )}
                </Card>

                <Row gutter={[16, 16]}>
                  <Col xs={24} lg={12}>
                    <Card title="资产端分类日均规模" size="small">
                      <Table
                        size="small"
                        pagination={false}
                        rowKey={(r) => `a-${r.category}`}
                        columns={breakdownColumns}
                        dataSource={assetRows}
                        locale={{ emptyText: "暂无数据" }}
                      />
                    </Card>
                  </Col>
                  <Col xs={24} lg={12}>
                    <Card title="负债端分类日均规模" size="small">
                      <Table
                        size="small"
                        pagination={false}
                        rowKey={(r) => `l-${r.category}`}
                        columns={breakdownColumns}
                        dataSource={liabilityRows}
                        locale={{ emptyText: "暂无数据" }}
                      />
                    </Card>
                  </Col>
                </Row>
              </>
            )}
          </>
        )}

        {activeTab === "monthly" && (
          <>
            <Space>
              <Text>年份</Text>
              <Select
                style={{ width: 120 }}
                value={selectedYear}
                onChange={(y) => {
                  setSelectedYear(y);
                  setExpandedMonth(null);
                  setSelectedMonthForBreakdown("");
                }}
                options={[2023, 2024, 2025, 2026].map((y) => ({ label: `${y}年`, value: y }))}
              />
            </Space>
            {monthlyQuery.isLoading ? (
              <Spin />
            ) : monthlyQuery.isError ? (
              <Alert type="error" message={String(monthlyQuery.error)} />
            ) : (
              <>
                {monthlyQuery.data && monthlyQuery.data.months.length > 0 && (
                  <Alert
                    type="info"
                    showIcon
                    message="YTD 汇总（年初至今）"
                    description={
                      <Space wrap size="large">
                        <Text>日均资产：{formatYi(monthlyQuery.data.ytd_avg_assets)}</Text>
                        <Text>日均负债：{formatYi(monthlyQuery.data.ytd_avg_liabilities)}</Text>
                        <Text>资产收益率：{formatPct(monthlyQuery.data.ytd_asset_yield)}</Text>
                        <Text>负债付息率：{formatPct(monthlyQuery.data.ytd_liability_cost)}</Text>
                        <Text strong>净息差：{formatPct(monthlyQuery.data.ytd_net_interest_margin)}</Text>
                      </Space>
                    }
                  />
                )}
                <Card title="月度统计" size="small">
                  <Table<AdbMonthlyItem>
                    size="small"
                    pagination={false}
                    rowKey={(r) => r.month}
                    columns={monthlyColumns}
                    dataSource={monthlyQuery.data?.months ?? []}
                    expandable={{
                      expandRowByClick: true,
                      expandedRowRender: (row) => (
                        <Row gutter={16}>
                          <Col span={12}>
                            <Title level={5}>资产端分类明细</Title>
                            <Table
                              size="small"
                              pagination={false}
                              rowKey={(b) => `ba-${b.category}`}
                              dataSource={row.breakdown_assets}
                              columns={[
                                { title: "分类", dataIndex: "category", key: "c" },
                                {
                                  title: "日均(亿)",
                                  dataIndex: "avg_balance",
                                  key: "a",
                                  align: "right",
                                  render: (v: number) => (v / YI).toFixed(2),
                                },
                                {
                                  title: "占比",
                                  dataIndex: "proportion",
                                  key: "p",
                                  align: "right",
                                  render: (v: number) => `${v?.toFixed?.(1) ?? v}%`,
                                },
                                {
                                  title: "收益率",
                                  dataIndex: "weighted_rate",
                                  key: "w",
                                  align: "right",
                                  render: (v: number | null) => formatPct(v),
                                },
                              ]}
                            />
                          </Col>
                          <Col span={12}>
                            <Title level={5}>负债端分类明细</Title>
                            <Table
                              size="small"
                              pagination={false}
                              rowKey={(b) => `bl-${b.category}`}
                              dataSource={row.breakdown_liabilities}
                              columns={[
                                { title: "分类", dataIndex: "category", key: "c" },
                                {
                                  title: "日均(亿)",
                                  dataIndex: "avg_balance",
                                  key: "a",
                                  align: "right",
                                  render: (v: number) => (v / YI).toFixed(2),
                                },
                                {
                                  title: "占比",
                                  dataIndex: "proportion",
                                  key: "p",
                                  align: "right",
                                  render: (v: number) => `${v?.toFixed?.(1) ?? v}%`,
                                },
                                {
                                  title: "付息率",
                                  dataIndex: "weighted_rate",
                                  key: "w",
                                  align: "right",
                                  render: (v: number | null) => formatPct(v),
                                },
                              ]}
                            />
                          </Col>
                        </Row>
                      ),
                      expandedRowKeys: expandedMonth ? [expandedMonth] : [],
                      onExpand: (expanded, record) => {
                        setExpandedMonth(expanded ? record.month : null);
                      },
                    }}
                  />
                </Card>

                {selectedMonthData && (
                  <Card
                    title="按月度日均 — 资产负债结构"
                    size="small"
                    extra={
                      <Select
                        style={{ width: 140 }}
                        value={selectedMonthForBreakdown}
                        onChange={setSelectedMonthForBreakdown}
                        options={(monthlyQuery.data?.months ?? []).map((m) => ({
                          label: m.month_label,
                          value: m.month,
                        }))}
                      />
                    }
                  >
                    <Row gutter={16}>
                      <Col xs={24} lg={12}>
                        <Title level={5}>{selectedMonthData.month_label} · 资产</Title>
                        <Table
                          size="small"
                          pagination={false}
                          dataSource={selectedMonthData.breakdown_assets}
                          rowKey={(b) => `sa-${b.category}`}
                          columns={[
                            { title: "类别", dataIndex: "category", key: "c" },
                            {
                              title: "日均(亿元)",
                              dataIndex: "avg_balance",
                              key: "a",
                              align: "right",
                              render: (v: number) => (v / YI).toFixed(2),
                            },
                            {
                              title: "占比",
                              dataIndex: "proportion",
                              key: "p",
                              align: "right",
                              render: (v: number) => `${v?.toFixed?.(2) ?? v}%`,
                            },
                          ]}
                        />
                      </Col>
                      <Col xs={24} lg={12}>
                        <Title level={5}>{selectedMonthData.month_label} · 负债</Title>
                        <Table
                          size="small"
                          pagination={false}
                          dataSource={selectedMonthData.breakdown_liabilities}
                          rowKey={(b) => `sl-${b.category}`}
                          columns={[
                            { title: "类别", dataIndex: "category", key: "c" },
                            {
                              title: "日均(亿元)",
                              dataIndex: "avg_balance",
                              key: "a",
                              align: "right",
                              render: (v: number) => (v / YI).toFixed(2),
                            },
                            {
                              title: "占比",
                              dataIndex: "proportion",
                              key: "p",
                              align: "right",
                              render: (v: number) => `${v?.toFixed?.(2) ?? v}%`,
                            },
                          ]}
                        />
                      </Col>
                    </Row>
                  </Card>
                )}
              </>
            )}
          </>
        )}
      </Space>
    </div>
  );
}
