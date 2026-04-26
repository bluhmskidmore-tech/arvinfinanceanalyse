import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Row, Select, Skeleton, Space, Tabs, Tag, Typography } from "antd";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { KpiCard } from "../../../components/KpiCard";
import type { LiabilityYieldKpi } from "../../../api/contracts";
import { adaptLiabilityCounterparty, getLiabilitySyntheticSectionStates } from "../adapters/liabilityAdapter";
import { LiabilityCounterpartyBlock, type LiabilityCpRow } from "../components/LiabilityCounterpartyBlock";
import { LiabilityCustomerTable } from "../components/LiabilityCustomerTable";
import { LiabilityKnowledgePanel } from "../components/LiabilityKnowledgePanel";
import { LiabilityMonthlySnapshotCards } from "../components/LiabilityMonthlySnapshotCards";
import { LiabilityNimStressMonthlyPanel } from "../components/LiabilityNimStressMonthlyPanel";
import { LiabilityNimStressPanel } from "../components/LiabilityNimStressPanel";
import { LiabilityStructureGrids } from "../components/LiabilityStructureGrids";
import {
  bucketAmountToYiNumeric,
  nameAmountToYiNumeric,
  numericPctRaw,
  numericToYiNumeric,
  shareOfTotalNumeric,
} from "../utils/money";
import { designTokens } from "../../../theme/designSystem";

const { Title, Text } = Typography;

const numericTabularStyle = { fontVariantNumeric: "tabular-nums" as const };

type TabKey = "daily" | "monthly";

const cockpitKpiGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: designTokens.space[4],
  marginBottom: designTokens.space[5],
  ...numericTabularStyle,
} as const;

const threeColumnGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: designTokens.space[4],
  marginBottom: designTokens.space[4],
} as const;

const twoColumnGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
  gap: designTokens.space[4],
  marginBottom: designTokens.space[4],
} as const;

const sectionCardStyle = {
  borderRadius: designTokens.radius.lg,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: "#ffffff",
  boxShadow: designTokens.shadow.card,
} as const;

function sumNumericRaw(values: Array<number | null | undefined>): number {
  return values.reduce<number>((sum, value) => sum + (value ?? 0), 0);
}

function bucketFallsWithinOneYear(bucket: string) {
  const normalized = bucket.trim().toUpperCase();
  return (
    normalized.includes("M") ||
    normalized === "1Y" ||
    normalized.includes("0-3") ||
    normalized.includes("3-12") ||
    normalized.includes("6-12") ||
    normalized.includes("31-90") ||
    normalized.includes("91-1Y")
  );
}

function buildDailyLiabilityConclusion(args: {
  yieldKpi: LiabilityYieldKpi | null;
  counterpartyRows: LiabilityCpRow[];
}) {
  const topShare = Math.max(...args.counterpartyRows.map((row) => row.share?.raw ?? 0), 0);
  const nimRaw = numericPctRaw(args.yieldKpi?.nim ?? null);

  if (nimRaw !== null && nimRaw <= 0) {
    return {
      title: "当前结论",
      body: "负债成本已经压过资产收益，净息差承压。",
      detail: `当前 NIM ${args.yieldKpi?.nim?.display ?? "—"}，需优先检查高成本资金来源与期限结构。`,
    };
  }

  if (topShare >= 0.3) {
    return {
      title: "当前结论",
      body: "净息差仍为正，但资金来源集中度偏高，头部对手方依赖需要重点关注。",
      detail: `头部对手方占比 ${args.counterpartyRows[0]?.share?.display ?? "—"}，当前 NIM ${args.yieldKpi?.nim?.display ?? "—"}。`,
    };
  }

  return {
    title: "当前结论",
    body: "净息差仍为正，资金来源分布相对均衡。",
    detail: `头部对手方占比 ${args.counterpartyRows[0]?.share?.display ?? "—"}，当前 NIM ${args.yieldKpi?.nim?.display ?? "—"}。`,
  };
}

export default function LiabilityAnalyticsPage() {
  const client = useApiClient();
  const [searchParams] = useSearchParams();
  const explicitReportDate = searchParams.get("report_date")?.trim() || "";

  const [activeTab, setActiveTab] = useState<TabKey>("daily");
  const [selectedYear, setSelectedYear] = useState(() => new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState<string>("");

  const datesQuery = useQuery({
    queryKey: ["liability", "balance-analysis-dates", client.mode],
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
    if (explicitReportDate) {
      return explicitReportDate;
    }
    return selectedReportDate || datesQuery.data?.result.report_dates[0] || "";
  }, [datesQuery.data?.result.report_dates, explicitReportDate, selectedReportDate]);

  const balanceOverviewQuery = useQuery({
    queryKey: ["liability", "balance-overview", client.mode, reportDate],
    queryFn: () =>
      client.getBalanceAnalysisOverview({
        reportDate: reportDate || "",
        positionScope: "all",
        currencyBasis: "CNY",
      }),
    enabled: activeTab === "daily" && Boolean(reportDate),
    retry: false,
  });

  const riskQuery = useQuery({
    queryKey: ["liability", "risk-buckets", client.mode, reportDate],
    queryFn: () => client.getLiabilityRiskBuckets(reportDate || null),
    enabled: activeTab === "daily" && Boolean(reportDate),
    retry: false,
  });

  const yieldQuery = useQuery({
    queryKey: ["liability", "yield-metrics", client.mode, reportDate],
    queryFn: () => client.getLiabilityYieldMetrics(reportDate || null),
    enabled: activeTab === "daily" && Boolean(reportDate),
    retry: false,
  });

  const cpQuery = useQuery({
    queryKey: ["liability", "counterparty", client.mode, reportDate],
    queryFn: () =>
      client.getLiabilityCounterparty({
        reportDate: reportDate || null,
        topN: 2000,
      }),
    enabled: activeTab === "daily" && Boolean(reportDate),
    retry: false,
  });

  const monthlyQuery = useQuery({
    queryKey: ["liability", "monthly", client.mode, selectedYear],
    queryFn: () => client.getLiabilitiesMonthly(selectedYear),
    enabled: activeTab === "monthly",
    retry: false,
  });

  const knowledgeQuery = useQuery({
    queryKey: ["liability", "knowledge-brief", client.mode],
    queryFn: () => client.getLiabilityKnowledgeBrief(),
    enabled: activeTab === "daily",
    retry: false,
  });

  const adbMonthlyQuery = useQuery({
    queryKey: ["liability", "adb-monthly", client.mode, selectedYear],
    queryFn: () => client.getLiabilityAdbMonthly(selectedYear),
    enabled: activeTab === "monthly",
    retry: false,
  });

  const yieldKpi: LiabilityYieldKpi | null = yieldQuery.data?.kpi ?? null;
  const knowledgeNotes = knowledgeQuery.data?.result.notes ?? [];
  const knowledgeStatusNote = knowledgeQuery.data?.result.status_note ?? null;

  const cpVm = useMemo(
    () =>
      adaptLiabilityCounterparty({
        payload: cpQuery.data,
        isLoading: cpQuery.isLoading,
        isError: cpQuery.isError,
      }),
    [cpQuery.data, cpQuery.isLoading, cpQuery.isError],
  );
  const dailyCpRows = cpVm.vm?.rows ?? [];

  const monthlyMonthsSorted = useMemo(() => {
    const ms = monthlyQuery.data?.months || [];
    return [...ms].sort((a, b) => (a.month > b.month ? -1 : a.month < b.month ? 1 : 0));
  }, [monthlyQuery.data?.months]);

  useEffect(() => {
    if (activeTab !== "monthly") {
      return;
    }
    if (selectedMonth) {
      return;
    }
    if (monthlyMonthsSorted.length > 0) {
      setSelectedMonth(monthlyMonthsSorted[0].month);
    }
  }, [activeTab, monthlyMonthsSorted, selectedMonth]);

  const selectedMonthData = useMemo(() => {
    if (!selectedMonth) {
      return null;
    }
    return monthlyMonthsSorted.find((m) => m.month === selectedMonth) || null;
  }, [monthlyMonthsSorted, selectedMonth]);

  const selectedAdbMonthData = useMemo(() => {
    if (!selectedMonth) {
      return null;
    }
    const ms = adbMonthlyQuery.data?.months || [];
    return ms.find((m) => m.month === selectedMonth) || null;
  }, [adbMonthlyQuery.data?.months, selectedMonth]);

  const monthlyCpRowsAll: LiabilityCpRow[] = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.counterparty_details ?? []).map((it) => {
      return {
        name: it.name ?? "",
        value: it.avg_value ?? null,
        share: shareOfTotalNumeric(it.avg_value ?? null, selectedMonthData.avg_total_liabilities ?? null),
        type: it.type ?? "",
        weightedCost: it.weighted_cost ?? null,
      };
    });
  }, [selectedMonthData]);

  const monthlyByInstitution = useMemo(() => {
    if (!selectedMonthData?.by_institution_type) {
      return [];
    }
    return selectedMonthData.by_institution_type.map((x) => ({
      name: x.type ?? "",
      value: x.avg_value ?? null,
    }));
  }, [selectedMonthData?.by_institution_type]);

  /** 与 V1 一致：柱状图优先使用后端给出的 `counterparty_top10` 顺序与集合。 */
  const monthlyCpBarRows = useMemo((): LiabilityCpRow[] | undefined => {
    const top10 = selectedMonthData?.counterparty_top10;
    if (!top10?.length || !selectedMonthData) {
      return undefined;
    }
    return top10.map((it) => {
      return {
        name: it.name ?? "",
        value: it.avg_value ?? null,
        share: shareOfTotalNumeric(it.avg_value ?? null, selectedMonthData.avg_total_liabilities ?? null),
        type: it.type ?? "",
        weightedCost: it.weighted_cost ?? null,
      };
    });
  }, [selectedMonthData]);

  const dailyStructure = useMemo(() => {
    const raw = riskQuery.data?.liabilities_structure ?? [];
    return raw.map((x) => ({ name: x.name, amountYi: nameAmountToYiNumeric(x) }));
  }, [riskQuery.data?.liabilities_structure]);

  const dailyTerm = useMemo(() => {
    const raw = riskQuery.data?.liabilities_term_buckets ?? [];
    return raw.map((x) => ({ bucket: x.bucket, amountYi: bucketAmountToYiNumeric(x) }));
  }, [riskQuery.data?.liabilities_term_buckets]);

  const dailyIbStructure = useMemo(() => {
    const raw = riskQuery.data?.interbank_liabilities_structure ?? [];
    return raw.map((x) => ({ name: x.name, amountYi: nameAmountToYiNumeric(x) }));
  }, [riskQuery.data?.interbank_liabilities_structure]);

  const dailyIbTerm = useMemo(() => {
    const raw = riskQuery.data?.interbank_liabilities_term_buckets ?? [];
    return raw.map((x) => ({ bucket: x.bucket, amountYi: bucketAmountToYiNumeric(x) }));
  }, [riskQuery.data?.interbank_liabilities_term_buckets]);

  const dailyIssuedStructure = useMemo(() => {
    const raw = riskQuery.data?.issued_liabilities_structure ?? [];
    return raw.map((x) => ({ name: x.name, amountYi: nameAmountToYiNumeric(x) }));
  }, [riskQuery.data?.issued_liabilities_structure]);

  const dailyIssuedTerm = useMemo(() => {
    const raw = riskQuery.data?.issued_liabilities_term_buckets ?? [];
    return raw.map((x) => ({ bucket: x.bucket, amountYi: bucketAmountToYiNumeric(x) }));
  }, [riskQuery.data?.issued_liabilities_term_buckets]);

  const mStructure = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.structure_overview ?? []).map((x) => ({
      name: x.category ?? "",
      amountYi: numericToYiNumeric(x.avg_balance ?? null),
    }));
  }, [selectedMonthData]);

  const mTerm = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.term_buckets ?? []).map((x) => ({
      bucket: x.bucket ?? "",
      amountYi: numericToYiNumeric(x.avg_balance ?? null),
    }));
  }, [selectedMonthData]);

  const mIbStructure = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.interbank_by_type ?? []).map((x) => ({
      name: x.category ?? "",
      amountYi: numericToYiNumeric(x.avg_balance ?? null),
    }));
  }, [selectedMonthData]);

  const mIbTerm = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.interbank_term_buckets ?? []).map((x) => ({
      bucket: x.bucket ?? "",
      amountYi: numericToYiNumeric(x.avg_balance ?? null),
    }));
  }, [selectedMonthData]);

  const mIssuedStructure = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.issued_by_type ?? []).map((x) => ({
      name: x.category ?? "",
      amountYi: numericToYiNumeric(x.avg_balance ?? null),
    }));
  }, [selectedMonthData]);

  const mIssuedTerm = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.issued_term_buckets ?? []).map((x) => ({
      bucket: x.bucket ?? "",
      amountYi: numericToYiNumeric(x.avg_balance ?? null),
    }));
  }, [selectedMonthData]);

  const yearOptions = useMemo(() => {
    const y = new Date().getFullYear();
    return [y - 1, y, y + 1];
  }, []);

  const datesBlockingError = datesQuery.isError && !reportDate;
  const datesEmpty =
    !explicitReportDate &&
    !datesQuery.isLoading &&
    !datesBlockingError &&
    (datesQuery.data?.result.report_dates.length ?? 0) === 0;
  const reportDateSelectDisabled = Boolean(explicitReportDate) || datesBlockingError || datesEmpty;
  const dailyPrimaryError = activeTab === "daily" && (riskQuery.isError || cpVm.state.kind === "error");
  const dailyPrimaryEmpty =
    activeTab === "daily" &&
    !datesBlockingError &&
    !datesEmpty &&
    !riskQuery.isLoading &&
    !riskQuery.isError &&
    cpVm.state.kind === "empty" &&
    dailyStructure.length === 0 &&
    dailyTerm.length === 0 &&
    dailyIbStructure.length === 0 &&
    dailyIbTerm.length === 0 &&
    dailyIssuedStructure.length === 0 &&
    dailyIssuedTerm.length === 0;
  const dailyConclusion = buildDailyLiabilityConclusion({
    yieldKpi,
    counterpartyRows: dailyCpRows,
  });
  const assetTotalYi = useMemo(() => {
    const raw = balanceOverviewQuery.data?.result.total_market_value_amount;
    if (raw === null || raw === undefined || raw === "") {
      return null;
    }
    const parsed = Number.parseFloat(String(raw).replace(/,/g, ""));
    return Number.isFinite(parsed) ? parsed : null;
  }, [balanceOverviewQuery.data?.result.total_market_value_amount]);
  const liabilityTotalYi = useMemo((): number => {
    const fromCp = numericToYiNumeric(cpQuery.data?.total_value ?? null)?.raw;
    const fromBuckets = sumNumericRaw(dailyStructure.map((item) => item.amountYi?.raw));
    return (fromCp ?? fromBuckets) ?? 0;
  }, [cpQuery.data?.total_value, dailyStructure]);
  const nimRaw = numericPctRaw(yieldKpi?.nim ?? null);
  const staticSpreadBp = useMemo(() => {
    if (nimRaw === null) return null;
    return nimRaw * 10000;
  }, [nimRaw]);
  const firstYearPressureYi = useMemo((): number => {
    return sumNumericRaw(
      dailyTerm.filter((item) => bucketFallsWithinOneYear(item.bucket)).map((item) => item.amountYi?.raw),
    );
  }, [dailyTerm]);
  const floatingGapYi = useMemo(() => {
    if (assetTotalYi === null) return null;
    return assetTotalYi - liabilityTotalYi;
  }, [assetTotalYi, liabilityTotalYi]);
  const topCounterpartyShare = dailyCpRows[0]?.share?.display ?? "—";
  // TODO(orchestrator-review): backend gap — 待关注事项为 cockpit 示意文案，待统一预警/限额 API
  const watchItems = [] as const;
  const alertEvents = [] as const;
  const syntheticSections = getLiabilitySyntheticSectionStates();
  /** 风险全景：维度来自真实桶/对手方衍生；展示列为前端聚合文案 */
  const riskOverviewRows = useMemo(
    () => [
      { label: "期限错配", level: firstYearPressureYi > 0 ? "中高" : "低", trend: "↑", status: "关注", detail: `${firstYearPressureYi.toFixed(0)} 亿` },
      { label: "流动性压力", level: liabilityTotalYi > 0 ? "中高" : "低", trend: "↑", status: "关注", detail: `${liabilityTotalYi.toFixed(0)} 亿` },
      { label: "负债滚续压力", level: firstYearPressureYi > 100 ? "高" : "中", trend: "↑", status: "预警", detail: `${firstYearPressureYi.toFixed(0)} 亿` },
      { label: "对手方集中度", level: topCounterpartyShare, trend: "→", status: "关注", detail: topCounterpartyShare },
      { label: "已发资产", level: assetTotalYi === null ? "—" : `${assetTotalYi.toFixed(0)} 亿`, trend: "↓", status: "正常", detail: balanceOverviewQuery.data?.result.report_date ?? "—" },
    ],
    [assetTotalYi, balanceOverviewQuery.data?.result.report_date, firstYearPressureYi, liabilityTotalYi, topCounterpartyShare],
  );
  // TODO(orchestrator-review): backend gap — 分项资产负债贡献仍为示意拆分；债券/同业行为 balance overview + 负债桶，合计行为真实接口
  const contributionRows = [] as const;
  const riskIndicators = [] as const;
  const calendarItems = [] as const;
  const liabilityHeadlineCards = useMemo(
    () => [
      { label: "市场资产", value: assetTotalYi !== null ? assetTotalYi.toFixed(2) : "—", unit: "亿", detail: "balance overview" },
      { label: "市场负债", value: liabilityTotalYi.toFixed(2), unit: "亿", detail: "funding total" },
      { label: "静态资产收益率", value: yieldKpi?.asset_yield?.display ?? "—", detail: "当前加权" },
      { label: "静态负债成本", value: yieldKpi?.liability_cost?.display ?? "—", detail: "当前加权" },
      { label: "静态利差", value: staticSpreadBp !== null ? `${staticSpreadBp.toFixed(1)}bp` : "—", detail: "资产收益-负债成本" },
      { label: "1年内到期负债", value: firstYearPressureYi.toFixed(2), unit: "亿", detail: "短端承压" },
      { label: "净估值差额", value: floatingGapYi !== null ? `${floatingGapYi >= 0 ? "+" : ""}${floatingGapYi.toFixed(2)}` : "—", unit: "亿", detail: "资产-负债" },
      {
        label: "异常预警",
        value: "待定",
        detail: `${syntheticSections.watchItems.detail}（当前隐藏 ${watchItems.length} 条示意项）`,
        valueVariant: "text" as const,
      },
    ],
    [assetTotalYi, floatingGapYi, firstYearPressureYi, liabilityTotalYi, staticSpreadBp, syntheticSections.watchItems.detail, watchItems.length, yieldKpi?.asset_yield?.display, yieldKpi?.liability_cost?.display],
  );
  return (
    <section data-testid="liability-analytics-page">
      <Row
        justify="space-between"
        align="top"
        gutter={[designTokens.space[4], designTokens.space[4]]}
        style={{ marginBottom: designTokens.space[4] }}
      >
        <Col xs={24} lg={16}>
          <Title
            level={2}
            style={{
              margin: 0,
              fontSize: designTokens.fontSize[24],
              color: designTokens.color.neutral[900],
            }}
          >
            负债结构分析
          </Title>
          <Text
            type="secondary"
            style={{
              display: "block",
              marginTop: designTokens.space[2],
              fontSize: designTokens.fontSize[13],
            }}
          >
            数据日期：
            {activeTab === "daily"
              ? riskQuery.data?.report_date || reportDate || "—"
              : selectedMonthData
                ? `${selectedMonthData.month_label}（月日均）`
                : `${selectedYear} 年度月度统计`}
          </Text>
        </Col>
        <Col xs={24} lg={8}>
          <Card size="small" styles={{ body: { textAlign: "right" } }}>
            <Text type="secondary">负债分析（资金来源）</Text>
          </Card>
        </Col>
      </Row>

      <Tabs
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as TabKey)}
        items={[
          { key: "daily", label: "日常分析" },
          { key: "monthly", label: "月度统计" },
        ]}
        style={{ marginBottom: designTokens.space[4] }}
      />

      {activeTab === "daily" ? (
        <>
          <Space wrap style={{ marginBottom: designTokens.space[4] }} align="start">
            <div>
              <Text type="secondary">报告日</Text>
              <div>
                <Select
                  aria-label="liability-report-date"
                  style={{ minWidth: 160 }}
                  value={reportDate || undefined}
                  placeholder="选择报告日"
                  disabled={reportDateSelectDisabled}
                  options={dateOptions.map((d) => ({ value: d, label: d }))}
                  onChange={(v) => setSelectedReportDate(v)}
                />
              </div>
            </div>
            {explicitReportDate ? (
              <Text type="secondary" style={{ alignSelf: "flex-end" }}>
                已由 URL <code>?report_date=</code> 固定
              </Text>
            ) : null}
          </Space>

          {balanceOverviewQuery.isError && !datesBlockingError && !datesEmpty ? (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: designTokens.space[4] }}
              message="市场资产（balance overview）加载失败"
              description={(balanceOverviewQuery.error as Error)?.message ?? "请求失败"}
              action={
                <Button size="small" onClick={() => void balanceOverviewQuery.refetch()}>
                  重试
                </Button>
              }
            />
          ) : null}

          {datesBlockingError ? (
            <Alert
              data-testid="liability-page-state"
              type="error"
              showIcon
              message="无法加载资产负债可用日期，请稍后重试。"
              action={
                <Button size="small" type="primary" onClick={() => void datesQuery.refetch()}>
                  重试
                </Button>
              }
            />
          ) : null}
          {datesEmpty ? (
            <Alert
              data-testid="liability-page-state"
              type="info"
              showIcon
              message="暂无可用报告日。"
            />
          ) : null}

          {datesBlockingError || datesEmpty ? null : riskQuery.isLoading ? (
            <Space direction="vertical" size="large" style={{ width: "100%" }}>
              <Skeleton active paragraph={{ rows: 1 }} title={{ width: "40%" }} />
              <Skeleton.Node active style={{ width: "100%", height: 120 }} />
              <Skeleton active paragraph={{ rows: 6 }} />
            </Space>
          ) : dailyPrimaryError ? (
            <Alert
              data-testid="liability-page-state"
              type="error"
              showIcon
              message="日常负债主数据加载失败"
              description={
                riskQuery.isError
                  ? (riskQuery.error as Error)?.message ?? "请求失败"
                  : (cpQuery.error as Error | undefined)?.message ?? "对手方数据加载失败"
              }
              action={
                <Button
                  size="small"
                  type="primary"
                  onClick={() => {
                    void riskQuery.refetch();
                    void cpQuery.refetch();
                    void yieldQuery.refetch();
                  }}
                >
                  重试
                </Button>
              }
            />
          ) : dailyPrimaryEmpty ? (
            <Alert
              data-testid="liability-page-state"
              type="info"
              showIcon
              message="所选报告日暂无负债分析数据。"
            />
          ) : (
            <>
              {yieldQuery.isError ? (
                <Alert
                  type="warning"
                  showIcon
                  style={{ marginBottom: designTokens.space[4] }}
                  message="收益率/NIM 指标加载失败，压力测试卡片将降级为空。"
                  action={
                    <Button size="small" onClick={() => void yieldQuery.refetch()}>
                      重试
                    </Button>
                  }
                />
              ) : null}
              <Space direction="vertical" size={designTokens.space[4]} style={{ width: "100%" }}>
                <Card
                  data-testid="liability-conclusion"
                  title="本期资产负债摘要"
                  style={sectionCardStyle}
                >
                  <Space direction="vertical" size={designTokens.space[2]} style={{ width: "100%" }}>
                    <span
                      style={{
                        fontSize: designTokens.fontSize[11],
                        fontWeight: 700,
                        letterSpacing: "0.06em",
                        textTransform: "uppercase",
                        color: designTokens.color.neutral[600],
                      }}
                    >
                      {dailyConclusion.title}
                    </span>
                    <div
                      style={{
                        fontSize: designTokens.fontSize[20],
                        fontWeight: 600,
                        color: designTokens.color.neutral[900],
                        lineHeight: designTokens.lineHeight.snug,
                      }}
                    >
                      {dailyConclusion.body}
                    </div>
                    <div
                      style={{
                        color: designTokens.color.neutral[700],
                        fontSize: designTokens.fontSize[13],
                        lineHeight: designTokens.lineHeight.relaxed,
                      }}
                    >
                      {dailyConclusion.detail}
                    </div>
                    <Space wrap>
                      <Tag color="green">资产特征</Tag>
                      <Tag color="gold">负债特征</Tag>
                      <Tag color="blue">关注要点</Tag>
                    </Space>
                  </Space>
                </Card>
                <div style={cockpitKpiGridStyle}>
                  {liabilityHeadlineCards.map((card) => (
                    <KpiCard
                      key={card.label}
                      label={card.label}
                      value={card.value}
                      unit={card.unit}
                      detail={card.detail}
                      valueVariant={card.valueVariant ?? "metric"}
                      status={card.label === "异常预警" ? "warning" : "normal"}
                    />
                  ))}
                </div>

                <div style={threeColumnGridStyle}>
                  <Card title="收益成本分解（静态口径）" style={sectionCardStyle}>
                    <div style={{ display: "grid", gap: designTokens.space[3] }}>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
                          gap: designTokens.space[3],
                          ...numericTabularStyle,
                        }}
                      >
                        <KpiCard label="资产收益" value={yieldKpi?.asset_yield?.display ?? "—"} detail="静态口径" valueVariant="text" />
                        <KpiCard label="负债成本" value={yieldKpi?.liability_cost?.display ?? "—"} detail="静态口径" valueVariant="text" />
                        <KpiCard label="净息差" value={yieldKpi?.nim?.display ?? "—"} detail="NIM" valueVariant="text" />
                        <KpiCard label="1Y压力" value={`${firstYearPressureYi.toFixed(2)}亿`} detail="到期负债" valueVariant="text" />
                      </div>
                      <div
                        style={{
                          color: designTokens.color.neutral[700],
                          fontSize: designTokens.fontSize[13],
                          lineHeight: designTokens.lineHeight.relaxed,
                        }}
                      >
                        这里保留静态资产收益、负债成本和净息差的首屏拆解，用来判断收益成本是否仍由资产端主导。
                      </div>
                    </div>
                  </Card>

                  <Card title="风险全景" style={sectionCardStyle}>
                    <table
                      style={{
                        width: "100%",
                        borderCollapse: "collapse",
                        fontSize: designTokens.fontSize[13],
                        ...numericTabularStyle,
                      }}
                    >
                      <thead>
                        <tr style={{ textAlign: "left", color: designTokens.color.neutral[600] }}>
                          <th style={{ paddingBottom: 8 }}>风险维度</th>
                          <th style={{ paddingBottom: 8 }}>水平</th>
                          <th style={{ paddingBottom: 8 }}>趋势</th>
                          <th style={{ paddingBottom: 8 }}>状态</th>
                          <th style={{ paddingBottom: 8 }}>说明</th>
                        </tr>
                      </thead>
                      <tbody>
                        {riskOverviewRows.map((row) => (
                          <tr
                            key={row.label}
                            style={{ borderTop: `1px solid ${designTokens.color.neutral[200]}` }}
                          >
                            <td
                              style={{
                                padding: "10px 0",
                                color: designTokens.color.neutral[900],
                                fontWeight: 600,
                              }}
                            >
                              {row.label}
                            </td>
                            <td style={{ padding: "10px 0" }}>{row.level}</td>
                            <td style={{ padding: "10px 0" }}>{row.trend}</td>
                            <td style={{ padding: "10px 0" }}>{row.status}</td>
                            <td style={{ padding: "10px 0", color: designTokens.color.neutral[700] }}>
                              {row.detail}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </Card>
                </div>

                <div style={threeColumnGridStyle}>
                  <Card title="资产 / 负债 / 缺口贡献" style={sectionCardStyle}>
                    <Alert
                      type="warning"
                      showIcon
                      message={syntheticSections.contributionRows.title}
                      description={`${syntheticSections.contributionRows.detail}（当前隐藏 ${contributionRows.length} 条示意行）`}
                    />
                  </Card>

                  <Card title="待关注事项" style={sectionCardStyle}>
                    <Alert
                      type="info"
                      showIcon
                      message={syntheticSections.watchItems.title}
                      description={`${syntheticSections.watchItems.detail}（当前隐藏 ${watchItems.length} 条示意项）`}
                    />
                  </Card>

                  <Card title="预警与事件" style={sectionCardStyle}>
                    <Alert
                      type="info"
                      showIcon
                      message={syntheticSections.alertEvents.title}
                      description={`${syntheticSections.alertEvents.detail}（当前隐藏 ${alertEvents.length} 条示意事件）`}
                    />
                  </Card>
                </div>

                <Card title="期限结构（资产 / 负债 / 净缺口）" style={sectionCardStyle}>
                  <LiabilityStructureGrids
                    structure={dailyStructure}
                    term={dailyTerm}
                    interbankStructure={dailyIbStructure}
                    interbankTerm={dailyIbTerm}
                    issuedStructure={dailyIssuedStructure}
                    issuedTerm={dailyIssuedTerm}
                  />
                </Card>

                <div style={twoColumnGridStyle}>
                  <Card title="风险指标" style={sectionCardStyle}>
                    <Alert
                      type="info"
                      showIcon
                      message={syntheticSections.riskIndicators.title}
                      description={`${syntheticSections.riskIndicators.detail}（当前隐藏 ${riskIndicators.length} 个混合指标）`}
                    />
                  </Card>

                  <Card title="关键日历（负债到期关注）" style={sectionCardStyle}>
                    <Alert
                      type="info"
                      showIcon
                      message={syntheticSections.calendarItems.title}
                      description={`${syntheticSections.calendarItems.detail}（当前隐藏 ${calendarItems.length} 条示意日历）`}
                    />
                  </Card>
                </div>

                <LiabilityKnowledgePanel
                  notes={knowledgeNotes}
                  loading={knowledgeQuery.isLoading}
                  errorText={
                    knowledgeQuery.isError
                      ? (knowledgeQuery.error as Error)?.message ?? "业务资料加载失败"
                      : null
                  }
                  statusNote={knowledgeStatusNote}
                />
                <LiabilityCounterpartyBlock
                  totalValue={cpVm.vm?.totalValue ?? null}
                  counterpartyRows={dailyCpRows}
                  byType={cpVm.vm?.byType ?? []}
                  loading={cpQuery.isLoading}
                  errorText={
                    cpQuery.isError ? (cpQuery.error as Error)?.message ?? "对手方数据加载失败" : null
                  }
                />
                <LiabilityNimStressPanel yieldKpi={yieldKpi} />
                <LiabilityCustomerTable
                  rows={dailyCpRows}
                  loading={cpQuery.isLoading}
                  subtitle='口径：TYWL 负债端（对手方名称 × 金额；剔除「青岛银行股份有限公司」；空值归「其它」）。'
                />
              </Space>
            </>
          )}
        </>
      ) : (
        <>
          <Card size="small" style={{ marginBottom: 16 }}>
            <Space wrap align="center">
              <div>
                <Text type="secondary">选择年份</Text>
                <div>
                  <Select
                    style={{ minWidth: 120 }}
                    value={selectedYear}
                    options={yearOptions.map((y) => ({ value: y, label: `${y} 年` }))}
                    onChange={(y) => {
                      setSelectedYear(y);
                      setSelectedMonth("");
                    }}
                  />
                </div>
              </div>
              <div>
                <Text type="secondary">按月选择</Text>
                <div>
                  <Select
                    style={{ minWidth: 200 }}
                    value={selectedMonth || undefined}
                    placeholder="选择月份"
                    options={monthlyMonthsSorted.map((m) => ({ value: m.month, label: m.month_label }))}
                    onChange={(v) => setSelectedMonth(v)}
                  />
                </div>
              </div>
              {selectedMonthData ? (
                <Text type="secondary">有效天数：{selectedMonthData.num_days} 天（口径：月度日均）</Text>
              ) : null}
            </Space>
          </Card>

          {monthlyQuery.isLoading ? (
            <Space direction="vertical" size="large" style={{ width: "100%" }}>
              <Skeleton active paragraph={{ rows: 1 }} />
              <Skeleton active paragraph={{ rows: 8 }} />
            </Space>
          ) : monthlyQuery.isError ? (
            <Alert
              type="error"
              showIcon
              message="月度数据加载失败"
              description={(monthlyQuery.error as Error)?.message ?? "请求失败"}
              action={
                <Button size="small" type="primary" onClick={() => void monthlyQuery.refetch()}>
                  重试
                </Button>
              }
            />
          ) : !selectedMonthData ? (
            <Alert type="info" showIcon message={`暂无 ${selectedYear} 年的月度数据`} />
          ) : (
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              {adbMonthlyQuery.isError ? (
                <Alert
                  type="warning"
                  showIcon
                  message="日均月度数据加载失败"
                  description={(adbMonthlyQuery.error as Error)?.message ?? "请求失败"}
                />
              ) : null}
              <LiabilityMonthlySnapshotCards
                month={selectedMonthData}
                ytdAvgTotalLiabilities={monthlyQuery.data?.ytd_avg_total_liabilities ?? null}
                ytdAvgLiabilityCost={monthlyQuery.data?.ytd_avg_liability_cost ?? null}
              />
              <LiabilityNimStressMonthlyPanel adbMonth={selectedAdbMonthData} />
              <LiabilityCounterpartyBlock
                title="资金来源依赖度（Top 10 对手方）"
                subtitle="口径：月度日均（TYWL 负债端）。"
                totalValue={selectedMonthData.avg_total_liabilities ?? null}
                counterpartyRows={monthlyCpRowsAll}
                barRankingRows={monthlyCpBarRows}
                byType={monthlyByInstitution}
                loading={false}
                errorText={null}
              />
              <LiabilityStructureGrids
                structure={mStructure}
                term={mTerm}
                interbankStructure={mIbStructure}
                interbankTerm={mIbTerm}
                issuedStructure={mIssuedStructure}
                issuedTerm={mIssuedTerm}
                structurePieCaption="同业负债业务结构（按产品类型）与发行负债业务结构（按业务种类）在总视图中的合并展示。"
              />
              <LiabilityCustomerTable
                rows={monthlyCpRowsAll}
                loading={false}
                subtitle="口径：月度日均（TYWL 负债端）。"
              />
            </Space>
          )}
        </>
      )}
    </section>
  );
}
