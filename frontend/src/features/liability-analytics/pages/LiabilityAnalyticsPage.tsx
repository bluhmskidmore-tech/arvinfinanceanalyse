import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Col, Row, Select, Space, Spin, Tabs, Typography } from "antd";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type { LiabilityYieldKpi } from "../../../api/contracts";
import { adaptLiabilityCounterparty } from "../adapters/liabilityAdapter";
import { LiabilityCounterpartyBlock, type LiabilityCpRow } from "../components/LiabilityCounterpartyBlock";
import { LiabilityCustomerTable } from "../components/LiabilityCustomerTable";
import { LiabilityMonthlySnapshotCards } from "../components/LiabilityMonthlySnapshotCards";
import { LiabilityNimStressMonthlyPanel } from "../components/LiabilityNimStressMonthlyPanel";
import { LiabilityNimStressPanel } from "../components/LiabilityNimStressPanel";
import { LiabilityStructureGrids } from "../components/LiabilityStructureGrids";
import { bucketAmountToYi, nameAmountToYi, numericToYi, numericYuanRaw, numericPctRaw } from "../utils/money";

const { Title, Text } = Typography;

type TabKey = "daily" | "monthly";

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

  const adbMonthlyQuery = useQuery({
    queryKey: ["liability", "adb-monthly", client.mode, selectedYear],
    queryFn: () => client.getLiabilityAdbMonthly(selectedYear),
    enabled: activeTab === "monthly",
    retry: false,
  });

  const yieldKpi: LiabilityYieldKpi | null = yieldQuery.data?.kpi ?? null;

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

  const mCpTotal = selectedMonthData ? numericYuanRaw(selectedMonthData.avg_total_liabilities) : 0;
  const monthlyCpRowsAll: LiabilityCpRow[] = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.counterparty_details ?? []).map((it) => {
      const valueYuan = numericYuanRaw(it.avg_value ?? null);
      return {
        name: it.name ?? "",
        valueYuan,
        pct: mCpTotal > 0 ? (valueYuan / mCpTotal) * 100 : 0,
        type: it.type ?? "",
        weightedCost: numericPctRaw(it.weighted_cost ?? null),
      };
    });
  }, [mCpTotal, selectedMonthData]);

  const monthlyByInstitution = useMemo(() => {
    if (!selectedMonthData?.by_institution_type) {
      return [];
    }
    return selectedMonthData.by_institution_type.map((x) => ({
      name: x.type ?? "",
      value: numericYuanRaw(x.avg_value ?? null),
    }));
  }, [selectedMonthData?.by_institution_type]);

  /** 与 V1 一致：柱状图优先使用后端给出的 `counterparty_top10` 顺序与集合。 */
  const monthlyCpBarRows = useMemo((): LiabilityCpRow[] | undefined => {
    const top10 = selectedMonthData?.counterparty_top10;
    if (!top10?.length || !selectedMonthData) {
      return undefined;
    }
    const total = mCpTotal;
    return top10.map((it) => {
      const valueYuan = numericYuanRaw(it.avg_value ?? null);
      return {
        name: it.name ?? "",
        valueYuan,
        pct: total > 0 ? (valueYuan / total) * 100 : 0,
        type: it.type ?? "",
        weightedCost: numericPctRaw(it.weighted_cost ?? null),
      };
    });
  }, [mCpTotal, selectedMonthData]);

  const dailyStructure = useMemo(() => {
    const raw = riskQuery.data?.liabilities_structure ?? [];
    return raw.map((x) => ({ name: x.name, amountYi: nameAmountToYi(x) }));
  }, [riskQuery.data?.liabilities_structure]);

  const dailyTerm = useMemo(() => {
    const raw = riskQuery.data?.liabilities_term_buckets ?? [];
    return raw.map((x) => ({ bucket: x.bucket, amountYi: bucketAmountToYi(x) }));
  }, [riskQuery.data?.liabilities_term_buckets]);

  const dailyIbStructure = useMemo(() => {
    const raw = riskQuery.data?.interbank_liabilities_structure ?? [];
    return raw.map((x) => ({ name: x.name, amountYi: nameAmountToYi(x) }));
  }, [riskQuery.data?.interbank_liabilities_structure]);

  const dailyIbTerm = useMemo(() => {
    const raw = riskQuery.data?.interbank_liabilities_term_buckets ?? [];
    return raw.map((x) => ({ bucket: x.bucket, amountYi: bucketAmountToYi(x) }));
  }, [riskQuery.data?.interbank_liabilities_term_buckets]);

  const dailyIssuedStructure = useMemo(() => {
    const raw = riskQuery.data?.issued_liabilities_structure ?? [];
    return raw.map((x) => ({ name: x.name, amountYi: nameAmountToYi(x) }));
  }, [riskQuery.data?.issued_liabilities_structure]);

  const dailyIssuedTerm = useMemo(() => {
    const raw = riskQuery.data?.issued_liabilities_term_buckets ?? [];
    return raw.map((x) => ({ bucket: x.bucket, amountYi: bucketAmountToYi(x) }));
  }, [riskQuery.data?.issued_liabilities_term_buckets]);

  const mStructure = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.structure_overview ?? []).map((x) => ({
      name: x.category ?? "",
      amountYi: numericToYi(x.avg_balance ?? null),
    }));
  }, [selectedMonthData]);

  const mTerm = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.term_buckets ?? []).map((x) => ({
      bucket: x.bucket ?? "",
      amountYi: numericToYi(x.avg_balance ?? null),
    }));
  }, [selectedMonthData]);

  const mIbStructure = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.interbank_by_type ?? []).map((x) => ({
      name: x.category ?? "",
      amountYi: numericToYi(x.avg_balance ?? null),
    }));
  }, [selectedMonthData]);

  const mIbTerm = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.interbank_term_buckets ?? []).map((x) => ({
      bucket: x.bucket ?? "",
      amountYi: numericToYi(x.avg_balance ?? null),
    }));
  }, [selectedMonthData]);

  const mIssuedStructure = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.issued_by_type ?? []).map((x) => ({
      name: x.category ?? "",
      amountYi: numericToYi(x.avg_balance ?? null),
    }));
  }, [selectedMonthData]);

  const mIssuedTerm = useMemo(() => {
    if (!selectedMonthData) {
      return [];
    }
    return (selectedMonthData.issued_term_buckets ?? []).map((x) => ({
      bucket: x.bucket ?? "",
      amountYi: numericToYi(x.avg_balance ?? null),
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

  return (
    <section data-testid="liability-analytics-page">
      <Row justify="space-between" align="top" gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={16}>
          <Title level={2} style={{ margin: 0 }}>
            负债结构分析
          </Title>
          <Text type="secondary" style={{ display: "block", marginTop: 8 }}>
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
        style={{ marginBottom: 16 }}
      />

      {activeTab === "daily" ? (
        <>
          <Space wrap style={{ marginBottom: 16 }} align="start">
            <div>
              <Text type="secondary">报告日</Text>
              <div>
                <Select
                  aria-label="liability-report-date"
                  style={{ minWidth: 160 }}
                  value={reportDate || undefined}
                  placeholder="选择报告日"
                  disabled={Boolean(explicitReportDate) || datesBlockingError}
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

          {datesBlockingError ? (
            <Alert type="error" showIcon message="无法加载资产负债可用日期，请稍后重试。" />
          ) : null}
          {datesEmpty ? <Alert type="info" showIcon message="暂无可用报告日。" /> : null}

          {riskQuery.isLoading ? (
            <div style={{ textAlign: "center", padding: 48 }}>
              <Spin size="large" />
            </div>
          ) : riskQuery.isError ? (
            <Alert
              type="error"
              showIcon
              message="负债结构主数据加载失败"
              description={(riskQuery.error as Error)?.message ?? "请求失败"}
            />
          ) : (
            <>
              {yieldQuery.isError ? (
                <Alert
                  type="warning"
                  showIcon
                  style={{ marginBottom: 16 }}
                  message="收益率/NIM 指标加载失败，压力测试卡片将降级为空。"
                />
              ) : null}
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <LiabilityNimStressPanel yieldKpi={yieldKpi} />
                <LiabilityCounterpartyBlock
                  totalValueYuan={cpVm.vm?.totalValueYuan ?? 0}
                  counterpartyRows={dailyCpRows}
                  byType={cpVm.vm?.byType ?? []}
                  loading={cpQuery.isLoading}
                  errorText={
                    cpQuery.isError ? (cpQuery.error as Error)?.message ?? "对手方数据加载失败" : null
                  }
                />
                <LiabilityStructureGrids
                  structure={dailyStructure}
                  term={dailyTerm}
                  interbankStructure={dailyIbStructure}
                  interbankTerm={dailyIbTerm}
                  issuedStructure={dailyIssuedStructure}
                  issuedTerm={dailyIssuedTerm}
                />
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
            <div style={{ textAlign: "center", padding: 48 }}>
              <Spin size="large" />
            </div>
          ) : monthlyQuery.isError ? (
            <Alert
              type="error"
              showIcon
              message="月度数据加载失败"
              description={(monthlyQuery.error as Error)?.message ?? "请求失败"}
            />
          ) : !selectedMonthData ? (
            <Alert type="info" showIcon message={`暂无 ${selectedYear} 年的月度数据`} />
          ) : (
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              {adbMonthlyQuery.isError ? (
                <Alert
                  type="warning"
                  showIcon
                  message="ADB 月度数据加载失败"
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
                totalValueYuan={mCpTotal}
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
