import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Select, Skeleton, Space, Tabs, Tag, Typography } from "antd";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import { KpiCard } from "../../../components/KpiCard";
import {
  AnalysisGrid,
  DataStatusStrip,
  EvidencePanel,
  KpiBand,
  KpiBandMetric,
  PageDecisionHero,
  PageFilterTray,
  PageStateSurface,
} from "../../../components/page/PagePrimitives";
import type { CockpitWatchItem, CockpitAlertEvent, ContributionSplitRow } from "../../../api/contracts";
import type { LiabilityYieldKpi } from "../../../api/liabilityAdbContracts";
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
import { EM_DASH } from "../../../utils/format";
import { buildLiabilityAnalyticsPageReadModel } from "./liabilityAnalyticsPageModel";
import "./LiabilityAnalyticsPage.css";

const { Text } = Typography;

type TabKey = "daily" | "monthly";

function sumKnownNumericRaw(values: Array<number | null | undefined>): number | null {
  let hasValue = false;
  const sum = values.reduce<number>((acc, value) => {
    if (value === null || value === undefined) {
      return acc;
    }
    hasValue = true;
    return acc + value;
  }, 0);
  return hasValue ? sum : null;
}

function formatYiOrDash(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return value.toFixed(digits);
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
      detail: `当前 NIM ${args.yieldKpi?.nim?.display ?? EM_DASH}，需优先检查高成本资金来源与期限结构。`,
    };
  }

  if (topShare >= 0.3) {
    return {
      title: "当前结论",
      body: "净息差仍为正，但资金来源集中度偏高，头部对手方依赖需要重点关注。",
      detail: `头部对手方占比 ${args.counterpartyRows[0]?.share?.display ?? EM_DASH}，当前 NIM ${args.yieldKpi?.nim?.display ?? EM_DASH}。`,
    };
  }

  return {
    title: "当前结论",
    body: "净息差仍为正，资金来源分布相对均衡。",
    detail: `头部对手方占比 ${args.counterpartyRows[0]?.share?.display ?? EM_DASH}，当前 NIM ${args.yieldKpi?.nim?.display ?? EM_DASH}。`,
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

  /** 与资产负债「资产端」一致：只含 ZQTZ/TYW 资产侧市值；发行类在事实表中为负债，不包含在本项。 */
  const balanceOverviewQuery = useQuery({
    queryKey: ["liability", "balance-overview", "asset", client.mode, reportDate],
    queryFn: () =>
      client.getBalanceAnalysisOverview({
        reportDate: reportDate || "",
        positionScope: "asset",
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

  const cockpitWarningsQuery = useQuery({
    queryKey: ["liability", "cockpit-warnings", client.mode, reportDate],
    queryFn: () => client.getCockpitWarnings(reportDate || null),
    enabled: activeTab === "daily" && Boolean(reportDate),
    retry: false,
  });

  const contributionQuery = useQuery({
    queryKey: ["liability", "contribution-split", client.mode, reportDate],
    queryFn: () => client.getContributionSplit(reportDate || null),
    enabled: activeTab === "daily" && Boolean(reportDate),
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
  /** `total_market_value_amount` 与资产负债页一致，为「元」口径；KPI 展示「亿元」需 ÷1e8。 */
  const assetTotalYi = useMemo(() => {
    const raw = balanceOverviewQuery.data?.result.total_market_value_amount;
    if (raw === null || raw === undefined || raw === "") {
      return null;
    }
    const parsed = Number.parseFloat(String(raw).replace(/,/g, ""));
    if (!Number.isFinite(parsed)) {
      return null;
    }
    return parsed / 100_000_000;
  }, [balanceOverviewQuery.data?.result.total_market_value_amount]);
  const liabilityTotalYi = useMemo((): number | null => {
    const fromCp = numericToYiNumeric(cpQuery.data?.total_value ?? null)?.raw;
    const fromBuckets = sumKnownNumericRaw(dailyStructure.map((item) => item.amountYi?.raw));
    return fromCp ?? fromBuckets;
  }, [cpQuery.data?.total_value, dailyStructure]);
  const firstYearPressureYi = useMemo((): number | null => {
    return sumKnownNumericRaw(
      dailyTerm.filter((item) => bucketFallsWithinOneYear(item.bucket)).map((item) => item.amountYi?.raw),
    );
  }, [dailyTerm]);
  const topCounterpartyShare = dailyCpRows[0]?.share?.display ?? EM_DASH;
  const watchItems: CockpitWatchItem[] = cockpitWarningsQuery.data?.result?.watch_items ?? [];
  const alertEvents: CockpitAlertEvent[] = cockpitWarningsQuery.data?.result?.alert_events ?? [];
  const syntheticSections = useMemo(() => getLiabilitySyntheticSectionStates(), []);
  /** 风险全景：维度来自真实桶/对手方衍生；展示列为前端聚合文案 */
  const riskOverviewRows = useMemo(
    () => [
      {
        label: "期限错配",
        level: firstYearPressureYi === null ? EM_DASH : firstYearPressureYi > 0 ? "中高" : "低",
        trend: "↑",
        status: "关注",
        detail: `${formatYiOrDash(firstYearPressureYi)} 亿`,
      },
      {
        label: "流动性压力",
        level: liabilityTotalYi === null ? EM_DASH : liabilityTotalYi > 0 ? "中高" : "低",
        trend: "↑",
        status: "关注",
        detail: `${formatYiOrDash(liabilityTotalYi)} 亿`,
      },
      {
        label: "负债滚续压力",
        level: firstYearPressureYi === null ? EM_DASH : firstYearPressureYi > 100 ? "高" : "中",
        trend: "↑",
        status: "预警",
        detail: `${formatYiOrDash(firstYearPressureYi)} 亿`,
      },
      { label: "对手方集中度", level: topCounterpartyShare, trend: "→", status: "关注", detail: topCounterpartyShare },
      {
        label: "已发资产",
        level: assetTotalYi === null ? EM_DASH : `${assetTotalYi.toFixed(0)} 亿`,
        trend: "↓",
        status: "正常",
        detail: balanceOverviewQuery.data?.result.report_date ?? EM_DASH,
      },
    ],
    [assetTotalYi, balanceOverviewQuery.data?.result.report_date, firstYearPressureYi, liabilityTotalYi, topCounterpartyShare],
  );
  const contributionRows: ContributionSplitRow[] = contributionQuery.data?.result?.contributions ?? [];
  const riskIndicators = [] as const;
  const calendarItems = [] as const;
  const pageReadModel = useMemo(
    () =>
      buildLiabilityAnalyticsPageReadModel({
        mode: client.mode,
        activeTab,
        requestedReportDate: explicitReportDate || selectedReportDate || reportDate,
        resolvedReportDate:
          activeTab === "daily"
            ? riskQuery.data?.report_date || reportDate
            : selectedMonthData?.month_label ?? "",
        selectedYear,
        selectedMonthLabel: selectedMonthData?.month_label ?? null,
        yieldKpi,
        liabilityTotalYi,
        firstYearPressureYi,
        topCounterpartyShare,
        warningCount: watchItems.length,
        alertCount: alertEvents.length,
        resultMetas: [
          { key: "dates", title: "报告日目录", meta: datesQuery.data?.result_meta },
          { key: "asset-overview", title: "资产端正式总览", meta: balanceOverviewQuery.data?.result_meta },
          { key: "knowledge", title: "业务资料", meta: knowledgeQuery.data?.result_meta },
          { key: "warnings", title: "关注/预警", meta: cockpitWarningsQuery.data?.result_meta },
          { key: "contribution", title: "贡献拆分", meta: contributionQuery.data?.result_meta },
        ],
        unwrappedEvidenceLabels:
          activeTab === "daily"
            ? ["risk-buckets", "yield-metrics", "counterparty"]
            : ["liabilities monthly", "ADB monthly"],
        syntheticSections: [
          syntheticSections.riskIndicators,
          syntheticSections.calendarItems,
        ].map((section) => ({
          key: section.kind,
          title: section.title,
          detail: section.detail,
        })),
      }),
    [
      activeTab,
      alertEvents.length,
      balanceOverviewQuery.data?.result_meta,
      client.mode,
      cockpitWarningsQuery.data?.result_meta,
      contributionQuery.data?.result_meta,
      datesQuery.data?.result_meta,
      explicitReportDate,
      firstYearPressureYi,
      knowledgeQuery.data?.result_meta,
      liabilityTotalYi,
      reportDate,
      riskQuery.data?.report_date,
      selectedMonthData?.month_label,
      selectedReportDate,
      selectedYear,
      syntheticSections.calendarItems,
      syntheticSections.riskIndicators,
      topCounterpartyShare,
      watchItems.length,
      yieldKpi,
    ],
  );
  const showDailyConclusion =
    activeTab === "daily" &&
    !datesBlockingError &&
    !datesEmpty &&
    !riskQuery.isLoading &&
    !dailyPrimaryError &&
    !dailyPrimaryEmpty;
  return (
    <section data-testid="liability-analytics-page" className="liability-analytics-page">
      <PageDecisionHero
        testId="liability-analytics-decision-hero"
        title="负债结构分析"
        eyebrow="分析读面"
        businessQuestion="先判断资金来源是否集中、负债成本是否压缩 NIM，再看短端到期与预警证据。"
        reportDateSlot={<span>{pageReadModel.reportLine}</span>}
        actions={
          <span className="liability-analytics-page__mode-badge" data-tone={pageReadModel.modeBadge.tone}>
            {pageReadModel.modeBadge.label}
          </span>
        }
        conclusion={
          showDailyConclusion ? (
            <div data-testid="liability-conclusion" className="liability-analytics-page__hero-conclusion">
              <strong>{dailyConclusion.body}</strong>
              <small>{dailyConclusion.detail}</small>
            </div>
          ) : (
            <span>等待当前页状态、报告日与核心负债数据完成后展示首屏判断。</span>
          )
        }
      >
        <KpiBand testId="liability-analytics-kpi-band">
          {pageReadModel.kpis.map((kpi) => (
            <KpiBandMetric
              key={kpi.key}
              label={kpi.label}
              value={
                <>
                  {kpi.value}
                  {kpi.unit ? <span className="liability-analytics-page__kpi-unit">{kpi.unit}</span> : null}
                </>
              }
              footer={kpi.detail}
            />
          ))}
        </KpiBand>
      </PageDecisionHero>

      <DataStatusStrip testId="liability-analytics-data-status">
        {pageReadModel.statusBadges.map((badge) => (
          <span key={badge.key} className="liability-analytics-page__status-badge" data-tone={badge.tone}>
            {badge.label}
          </span>
        ))}
      </DataStatusStrip>

      <AnalysisGrid columns={2} className="liability-analytics-page__evidence-grid">
        <EvidencePanel heading="状态证据">
          <div className="liability-analytics-page__state-stack">
            {pageReadModel.stateSurfaces.map((surface) => (
              <PageStateSurface
                key={surface.key}
                variant={surface.variant}
                title={surface.title}
                description={surface.description}
              />
            ))}
          </div>
        </EvidencePanel>
        <EvidencePanel heading="证据账本">
          <div className="liability-analytics-page__evidence-ledger">
            {pageReadModel.evidenceCards.map((card) => (
              <article key={card.key} className="liability-analytics-page__evidence-card" data-tone={card.tone}>
                <div className="liability-analytics-page__evidence-card-top">
                  <strong>{card.title}</strong>
                  <span>{card.basisLabel}</span>
                </div>
                <dl>
                  <div>
                    <dt title="result_kind">结果类型</dt>
                    <dd>{card.resultKind}</dd>
                  </div>
                  <div>
                    <dt title="quality_flag">质量</dt>
                    <dd>{card.qualityLabel}</dd>
                  </div>
                  <div>
                    <dt title="fallback_mode">兜底</dt>
                    <dd>{card.fallbackLabel}</dd>
                  </div>
                  <div>
                    <dt title="as_of_date">截至日</dt>
                    <dd>{card.asOfDate}</dd>
                  </div>
                  <div>
                    <dt title="trace_id">追踪号</dt>
                    <dd>{card.traceId}</dd>
                  </div>
                  <div>
                    <dt title="rule_version">规则版本</dt>
                    <dd>{card.ruleVersion}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </EvidencePanel>
      </AnalysisGrid>

      <Tabs
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as TabKey)}
        items={[
          { key: "daily", label: "日常分析" },
          { key: "monthly", label: "月度统计" },
        ]}
        className="liability-analytics-page__tabs"
      />

      {activeTab === "daily" ? (
        <>
          <PageFilterTray testId="liability-analytics-filter-tray">
            <FilterBar>
              <div className="liability-analytics-page__filter-field">
                <Text type="secondary">报告日</Text>
                <div>
                  <Select
                    aria-label="liability-report-date"
                    className="liability-analytics-page__report-date-select"
                    value={reportDate || undefined}
                    placeholder="选择报告日"
                    disabled={reportDateSelectDisabled}
                    options={dateOptions.map((d) => ({ value: d, label: d }))}
                    onChange={(v) => setSelectedReportDate(v)}
                  />
                </div>
              </div>
              {explicitReportDate ? (
                <Text type="secondary" className="liability-analytics-page__fixed-date-note">
                  已由地址栏报告日参数固定
                </Text>
              ) : null}
            </FilterBar>
          </PageFilterTray>

          {balanceOverviewQuery.isError && !datesBlockingError && !datesEmpty ? (
            <Alert
              type="warning"
              showIcon
              className="liability-analytics-page__alert-spaced"
              message="市场资产（正式总览·资产口径）加载失败"
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
            <div className="liability-analytics-page__stack">
              <Skeleton active paragraph={{ rows: 1 }} title={{ width: "40%" }} />
              <Skeleton.Node active className="liability-analytics-page__skeleton-block" />
              <Skeleton active paragraph={{ rows: 6 }} />
            </div>
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
                  className="liability-analytics-page__alert-spaced"
                  message="收益率/NIM 指标加载失败，压力测试卡片将降级为空。"
                  action={
                    <Button size="small" onClick={() => void yieldQuery.refetch()}>
                      重试
                    </Button>
                  }
                />
              ) : null}
              <div className="liability-analytics-page__stack">
                <div className="liability-analytics-page__grid-3col">
                  <Card title="收益成本分解（静态口径）" className="liability-analytics-page__section-card">
                    <div className="liability-analytics-page__section-body">
                      <div className="liability-analytics-page__kpi-grid">
                        <KpiCard
                          label="资产收益"
                          value={yieldKpi?.asset_yield?.display ?? EM_DASH}
                          detail="静态口径"
                          valueVariant="text"
                        />
                        <KpiCard
                          label="负债成本"
                          value={yieldKpi?.liability_cost?.display ?? EM_DASH}
                          detail="静态口径"
                          valueVariant="text"
                        />
                        <KpiCard
                          label="净息差"
                          value={yieldKpi?.nim?.display ?? EM_DASH}
                          detail="NIM"
                          valueVariant="text"
                        />
                        <KpiCard
                          label="1Y压力"
                          value={`${formatYiOrDash(firstYearPressureYi, 2)}亿`}
                          detail="到期负债"
                          valueVariant="text"
                        />
                      </div>
                      <div className="liability-analytics-page__section-copy">
                        这里保留静态资产收益、负债成本和净息差的首屏拆解，用来判断收益成本是否仍由资产端主导。
                      </div>
                    </div>
                  </Card>

                  <Card title="风险全景" className="liability-analytics-page__section-card">
                    <table className="liability-analytics-page__data-table">
                      <thead>
                        <tr>
                          <th>风险维度</th>
                          <th>水平</th>
                          <th>趋势</th>
                          <th>状态</th>
                          <th>说明</th>
                        </tr>
                      </thead>
                      <tbody>
                        {riskOverviewRows.map((row) => (
                          <tr key={row.label}>
                            <td className="is-label">{row.label}</td>
                            <td>{row.level}</td>
                            <td>{row.trend}</td>
                            <td>{row.status}</td>
                            <td className="is-muted">{row.detail}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </Card>
                </div>

                <div className="liability-analytics-page__grid-3col">
                  <Card title="资产 / 负债 / 缺口贡献" className="liability-analytics-page__section-card">
                    {contributionRows.length === 0 ? (
                      <Alert
                        type="info"
                        showIcon
                        message="暂无贡献拆分数据"
                        description={contributionQuery.isLoading ? "加载中…" : "所选报告日无可用拆分数据。"}
                      />
                    ) : (
                      <table className="liability-analytics-page__data-table liability-analytics-page__data-table--compact">
                        <thead>
                          <tr>
                            <th>分类</th>
                            <th>方向</th>
                            <th className="is-numeric">金额（亿）</th>
                            <th className="is-numeric">收益/成本</th>
                            <th className="is-numeric">贡献（亿）</th>
                          </tr>
                        </thead>
                        <tbody>
                          {contributionRows.map((row) => (
                            <tr key={`${row.side}-${row.category}`}>
                              <td className="is-label">{row.category}</td>
                              <td>
                                <Tag
                                  className={
                                    row.side === "asset"
                                      ? "liability-ib-tag liability-ib-tag--up"
                                      : "liability-ib-tag liability-ib-tag--warn"
                                  }
                                >
                                  {row.side === "asset" ? "资产" : "负债"}
                                </Tag>
                              </td>
                              <td className="is-numeric">
                                {row.amount_yi !== null ? row.amount_yi.toFixed(2) : EM_DASH}
                              </td>
                              <td className="is-numeric">
                                {row.yield_or_cost !== null
                                  ? `${(row.yield_or_cost * 100).toFixed(2)}%`
                                  : EM_DASH}
                              </td>
                              <td className="is-numeric">
                                {row.contribution_yi !== null ? row.contribution_yi.toFixed(4) : EM_DASH}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </Card>

                  <Card title="待关注事项" className="liability-analytics-page__section-card">
                    {watchItems.length === 0 ? (
                      <Alert
                        type="info"
                        showIcon
                        message="当前无待关注事项"
                        description={cockpitWarningsQuery.isLoading ? "加载中…" : "所有指标均在正常范围内。"}
                      />
                    ) : (
                      <div className="liability-analytics-page__stack liability-analytics-page__stack--tight">
                        {watchItems.map((item) => (
                          <Alert
                            key={item.id}
                            type={item.level === "warning" ? "warning" : "info"}
                            showIcon
                            message={item.label}
                            description={item.detail}
                          />
                        ))}
                      </div>
                    )}
                  </Card>

                  <Card title="预警与事件" className="liability-analytics-page__section-card">
                    {alertEvents.length === 0 ? (
                      <Alert
                        type="info"
                        showIcon
                        message="当前无预警事件"
                        description={cockpitWarningsQuery.isLoading ? "加载中…" : "未触发预警阈值。"}
                      />
                    ) : (
                      <div className="liability-analytics-page__stack liability-analytics-page__stack--tight">
                        {alertEvents.map((evt) => (
                          <Alert
                            key={evt.id}
                            type={evt.severity === "high" ? "error" : evt.severity === "medium" ? "warning" : "info"}
                            showIcon
                            message={evt.title}
                            description={`${evt.occurred_at}：${evt.detail}`}
                          />
                        ))}
                      </div>
                    )}
                  </Card>
                </div>

                <Card title="期限结构（资产 / 负债 / 净缺口）" className="liability-analytics-page__section-card">
                  <LiabilityStructureGrids
                    structure={dailyStructure}
                    term={dailyTerm}
                    interbankStructure={dailyIbStructure}
                    interbankTerm={dailyIbTerm}
                    issuedStructure={dailyIssuedStructure}
                    issuedTerm={dailyIssuedTerm}
                  />
                </Card>

                <div className="liability-analytics-page__grid-2col">
                  <Card title="风险指标" className="liability-analytics-page__section-card">
                    <Alert
                      type="info"
                      showIcon
                      message={syntheticSections.riskIndicators.title}
                      description={`${syntheticSections.riskIndicators.detail}（当前隐藏 ${riskIndicators.length} 个混合指标）`}
                    />
                  </Card>

                  <Card title="关键日历（负债到期关注）" className="liability-analytics-page__section-card">
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
                  authoritativeTop10Share={cpVm.vm?.top10Share ?? null}
                  authoritativeHhi={cpVm.vm?.hhi ?? null}
                  populationCount={cpVm.vm?.populationCount ?? null}
                  isTruncated={cpVm.vm?.isTruncated ?? false}
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
              </div>
            </>
          )}
        </>
      ) : (
        <>
          <Card size="small" className="liability-analytics-page__monthly-filters">
            <Space wrap align="center">
              <div className="liability-analytics-page__filter-field">
                <Text type="secondary">选择年份</Text>
                <div>
                  <Select
                    className="liability-analytics-page__select--year"
                    value={selectedYear}
                    options={yearOptions.map((y) => ({ value: y, label: `${y} 年` }))}
                    onChange={(y) => {
                      setSelectedYear(y);
                      setSelectedMonth("");
                    }}
                  />
                </div>
              </div>
              <div className="liability-analytics-page__filter-field">
                <Text type="secondary">按月选择</Text>
                <div>
                  <Select
                    className="liability-analytics-page__select--month"
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
            <div className="liability-analytics-page__stack">
              <Skeleton active paragraph={{ rows: 1 }} />
              <Skeleton active paragraph={{ rows: 8 }} />
            </div>
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
            <div className="liability-analytics-page__stack">
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
                title="资金来源依赖度（前十对手方）"
                subtitle="口径：月度日均（TYWL 负债端）。"
                totalValue={selectedMonthData.avg_total_liabilities ?? null}
                authoritativeTop10Share={selectedMonthData.top10_share ?? null}
                authoritativeHhi={selectedMonthData.hhi ?? null}
                populationCount={selectedMonthData.population_count ?? null}
                isTruncated={selectedMonthData.is_truncated ?? false}
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
            </div>
          )}
        </>
      )}
    </section>
  );
}
