import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Select, Tabs } from "antd";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { PageStateSurface } from "../../../components/page/PagePrimitives";
import {
  SECTION_HEAD_STACK_CLASSNAME,
  SectionHead,
  type SectionState,
} from "../../../components/layout";
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
import { LiabilityYieldTrendPanel } from "../components/LiabilityYieldTrendPanel";
import {
  bucketAmountToYiNumeric,
  nameAmountToYiNumeric,
  numericPctRaw,
  numericToYiNumeric,
} from "../utils/money";
import { EM_DASH } from "../../../utils/format";
import { fixedOrDash } from "../../../pageModel";
import { buildLiabilityAnalyticsPageReadModel } from "./liabilityAnalyticsPageModel";
import "./LiabilityAnalyticsPage.css";

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

function bucketFallsWithinOneYear(bucket: string) {
  const normalized = bucket.trim().toUpperCase();
  return ["0-3M", "3-6M", "6-12M", "1Y", "MATURED"].includes(normalized);
}

/** 分区头状态位：loading/error/empty 三态露一句话，正常返回 null。 */
function sectionLeadState(loading: boolean, error: boolean, isEmpty: boolean): SectionState {
  if (loading) return { label: "读取中", tone: "loading" };
  if (error) return { label: "读取失败", tone: "error" };
  if (isEmpty) return { label: "暂无数据", tone: "empty" };
  return null;
}

function buildDailyLiabilityConclusion(args: {
  yieldKpi: LiabilityYieldKpi | null;
  authoritativeTop10ShareDisplay: string;
  authoritativeTop10ShareRaw: number | null;
}) {
  const nimRaw = numericPctRaw(args.yieldKpi?.nim ?? null);

  // 缺值守卫（DESIGN.md §6）：NIM 未返回时不做「仍为正」方向断言。
  if (nimRaw === null) {
    return {
      title: "当前结论",
      body: "NIM 读数未返回，息差判断暂缺。",
      detail: `Top10 占比 ${args.authoritativeTop10ShareDisplay}，当前 NIM ${EM_DASH}（待负债收益指标返回后更新）。`,
    };
  }

  if (nimRaw <= 0) {
    return {
      title: "当前结论",
      body: "负债成本已经压过资产收益，净息差承压。",
      detail: `当前 NIM ${args.yieldKpi?.nim?.display ?? EM_DASH}，需优先检查高成本资金来源与期限结构。`,
    };
  }

  if (args.authoritativeTop10ShareRaw === null) {
    return {
      title: "当前结论",
      body: "净息差仍为正，但对手方集中度权威指标暂缺，当前不对集中度做方向性判断。",
      detail: `Top10 占比 ${args.authoritativeTop10ShareDisplay}，当前 NIM ${args.yieldKpi?.nim?.display ?? EM_DASH}。`,
    };
  }

  return {
    title: "当前结论",
    body: "净息差仍为正，资金来源集中度以后端权威指标持续跟踪。",
    detail: `Top10 占比 ${args.authoritativeTop10ShareDisplay}，当前 NIM ${args.yieldKpi?.nim?.display ?? EM_DASH}。`,
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

  const monthlySummaryQuery = useQuery({
    queryKey: ["liability", "monthly-summary", client.mode, selectedYear],
    queryFn: () => client.getLiabilitiesMonthlySummary(selectedYear),
    enabled: activeTab === "monthly",
    retry: false,
  });

  const monthlyDetailQuery = useQuery({
    queryKey: ["liability", "monthly-detail", client.mode, selectedMonth],
    queryFn: () => client.getLiabilitiesMonthlyDetail(selectedMonth),
    enabled: activeTab === "monthly" && Boolean(selectedMonth),
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

  const reportDateYear = Number.parseInt(reportDate.slice(0, 4), 10);
  const adbMonthlyYear =
    activeTab === "daily" && Number.isFinite(reportDateYear) ? reportDateYear : selectedYear;
  const adbMonthlyQuery = useQuery({
    queryKey: ["liability", "adb-monthly", client.mode, adbMonthlyYear],
    queryFn: () => client.getLiabilityAdbMonthly(adbMonthlyYear),
    enabled: activeTab === "monthly" || (activeTab === "daily" && Boolean(reportDate)),
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
    const ms = monthlySummaryQuery.data?.months || [];
    return [...ms].sort((a, b) => (a.month > b.month ? -1 : a.month < b.month ? 1 : 0));
  }, [monthlySummaryQuery.data?.months]);

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

  const selectedMonthDetail = monthlyDetailQuery.data?.detail ?? null;

  const selectedAdbMonthData = useMemo(() => {
    if (!selectedMonth) {
      return null;
    }
    const ms = adbMonthlyQuery.data?.months || [];
    return ms.find((m) => m.month === selectedMonth) || null;
  }, [adbMonthlyQuery.data?.months, selectedMonth]);

  const monthlyCpRowsAll: LiabilityCpRow[] = useMemo(() => {
    if (!selectedMonthDetail) {
      return [];
    }
    return (selectedMonthDetail.counterparty_details ?? []).map((it) => {
      return {
        name: it.name ?? "",
        value: it.avg_value ?? null,
        share: it.proportion ?? null,
        type: it.type ?? "",
        weightedCost: it.weighted_cost ?? null,
      };
    });
  }, [selectedMonthDetail]);

  const monthlyByInstitution = useMemo(() => {
    if (!selectedMonthDetail?.by_institution_type) {
      return [];
    }
    return selectedMonthDetail.by_institution_type.map((x) => ({
      name: x.type ?? "",
      value: x.avg_value ?? null,
    }));
  }, [selectedMonthDetail?.by_institution_type]);

  /** 与 V1 一致：柱状图优先使用后端给出的 `counterparty_top10` 顺序与集合。 */
  const monthlyCpBarRows = useMemo((): LiabilityCpRow[] | undefined => {
    const top10 = selectedMonthDetail?.counterparty_top10;
    if (!top10?.length || !selectedMonthDetail) {
      return undefined;
    }
    return top10.map((it) => {
      return {
        name: it.name ?? "",
        value: it.avg_value ?? null,
        share: it.proportion ?? null,
        type: it.type ?? "",
        weightedCost: it.weighted_cost ?? null,
      };
    });
  }, [selectedMonthDetail]);

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
    if (!selectedMonthDetail) {
      return [];
    }
    return (selectedMonthDetail.structure_overview ?? []).map((x) => ({
      name: x.category ?? "",
      amountYi: numericToYiNumeric(x.avg_balance ?? null),
    }));
  }, [selectedMonthDetail]);

  const mTerm = useMemo(() => {
    if (!selectedMonthDetail) {
      return [];
    }
    return (selectedMonthDetail.term_buckets ?? []).map((x) => ({
      bucket: x.bucket ?? "",
      amountYi: numericToYiNumeric(x.avg_balance ?? null),
    }));
  }, [selectedMonthDetail]);

  const mIbStructure = useMemo(() => {
    if (!selectedMonthDetail) {
      return [];
    }
    return (selectedMonthDetail.interbank_by_type ?? []).map((x) => ({
      name: x.category ?? "",
      amountYi: numericToYiNumeric(x.avg_balance ?? null),
    }));
  }, [selectedMonthDetail]);

  const mIbTerm = useMemo(() => {
    if (!selectedMonthDetail) {
      return [];
    }
    return (selectedMonthDetail.interbank_term_buckets ?? []).map((x) => ({
      bucket: x.bucket ?? "",
      amountYi: numericToYiNumeric(x.avg_balance ?? null),
    }));
  }, [selectedMonthDetail]);

  const mIssuedStructure = useMemo(() => {
    if (!selectedMonthDetail) {
      return [];
    }
    return (selectedMonthDetail.issued_by_type ?? []).map((x) => ({
      name: x.category ?? "",
      amountYi: numericToYiNumeric(x.avg_balance ?? null),
    }));
  }, [selectedMonthDetail]);

  const mIssuedTerm = useMemo(() => {
    if (!selectedMonthDetail) {
      return [];
    }
    return (selectedMonthDetail.issued_term_buckets ?? []).map((x) => ({
      bucket: x.bucket ?? "",
      amountYi: numericToYiNumeric(x.avg_balance ?? null),
    }));
  }, [selectedMonthDetail]);

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
  /*
   * 报告日目录在途或核心期限桶读数在途都算首屏载入中；riskQuery 用 isPending
   * （v5 语义）并以 reportDate 门控，避免报告日尚未落地时闪现「暂无数据」。
   */
  const dailyLoading = datesQuery.isLoading || (Boolean(reportDate) && riskQuery.isPending);
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
  const authoritativeTop10Share = cpVm.vm?.top10Share ?? null;
  const authoritativeTop10ShareRaw = authoritativeTop10Share?.raw ?? null;
  const authoritativeTop10ShareDisplay = authoritativeTop10Share?.display ?? EM_DASH;
  const dailyConclusion = buildDailyLiabilityConclusion({
    yieldKpi,
    authoritativeTop10ShareDisplay,
    authoritativeTop10ShareRaw,
  });
  /*
   * 负债收益读面同因缺失一次性披露（DESIGN.md §6）：收益成本与压力测试两区共用
   * 同一负债收益读数，整组缺失时原因只在区头出现一次，明细格保持安静 EM_DASH。
   */
  const yieldReadGapNote = useMemo(() => {
    if (yieldQuery.isLoading) {
      return "负债收益指标读取中…";
    }
    if (yieldQuery.isError) {
      return "负债收益指标读取失败，本区读数暂缺。";
    }
    const kpi = yieldQuery.data?.kpi;
    const allMissing =
      !kpi ||
      [kpi.asset_yield, kpi.liability_cost, kpi.market_liability_cost, kpi.nim].every(
        (value) => numericPctRaw(value ?? null) === null,
      );
    return allMissing ? "负债收益读面未返回读数，本区暂缺。" : null;
  }, [yieldQuery.data?.kpi, yieldQuery.isError, yieldQuery.isLoading]);
  const liabilityTotalYi = useMemo((): number | null => {
    return sumKnownNumericRaw(dailyStructure.map((item) => item.amountYi?.raw));
  }, [dailyStructure]);
  const firstYearPressureYi = useMemo((): number | null => {
    return sumKnownNumericRaw(
      dailyTerm.filter((item) => bucketFallsWithinOneYear(item.bucket)).map((item) => item.amountYi?.raw),
    );
  }, [dailyTerm]);
  const missingMaturityCount = riskQuery.data?.missing_maturity_count ?? 0;
  /** 预警读面未成功返回（error / 报告日缺失未启用）时不能把「未知」当成 0 条。 */
  const cockpitWarnings = cockpitWarningsQuery.data?.result ?? null;
  const warningsReturned = cockpitWarnings !== null;
  const watchItems: CockpitWatchItem[] = cockpitWarnings?.watch_items ?? [];
  const alertEvents: CockpitAlertEvent[] = cockpitWarnings?.alert_events ?? [];
  const syntheticSections = useMemo(() => getLiabilitySyntheticSectionStates(), []);
  const contributionRows: ContributionSplitRow[] = contributionQuery.data?.result?.contributions ?? [];
  const monthlyDetailLoading =
    activeTab === "monthly" && Boolean(selectedMonth) && monthlyDetailQuery.isPending;
  const monthlyDetailError =
    activeTab === "monthly" && Boolean(selectedMonth) && monthlyDetailQuery.isError;
  const monthlyDetailEmpty =
    activeTab === "monthly" &&
    Boolean(selectedMonth) &&
    !monthlyDetailQuery.isPending &&
    !monthlyDetailQuery.isError &&
    !selectedMonthDetail;
  const monthlyDetailLeadState = sectionLeadState(
    monthlyDetailLoading,
    monthlyDetailError,
    monthlyDetailEmpty,
  );
  /*
   * 日常页核心读面以 reportDate 门控：报告日目录失败/为空时三条 query 一直是
   * disabled-pending，不能当成「读取中」；用 evidenceBlocked 单独露「未触发」。
   */
  const evidenceLoading =
    activeTab === "daily"
      ? datesQuery.isLoading ||
        (Boolean(reportDate) && (riskQuery.isPending || yieldQuery.isPending || cpQuery.isPending))
      : monthlySummaryQuery.isPending || monthlyDetailLoading || adbMonthlyQuery.isPending;
  const evidenceBlocked = activeTab === "daily" && (datesBlockingError || datesEmpty);
  const pageReadModel = useMemo(
    () =>
      buildLiabilityAnalyticsPageReadModel({
        mode: client.mode,
        activeTab,
        requestedReportDate:
          activeTab === "daily" ? explicitReportDate || selectedReportDate || reportDate : "",
        resolvedReportDate:
          activeTab === "daily" ? riskQuery.data?.report_date || reportDate : "",
        selectedYear,
        selectedMonthLabel: selectedMonthData?.month_label ?? null,
        yieldKpi,
        liabilityTotalYi,
        firstYearPressureYi,
        topCounterpartyShare: authoritativeTop10ShareDisplay,
        warningCount: warningsReturned ? watchItems.length : null,
        alertCount: warningsReturned ? alertEvents.length : null,
        resultMetas:
          activeTab === "daily"
            ? [
                // Daily hero + KPI band use daily reads; the embedded trend uses analytical ADB monthly.
                { key: "risk-buckets", title: "负债期限结构", required: !riskQuery.isPending, meta: riskQuery.data?.result_meta },
                { key: "yield-metrics", title: "负债收益指标", required: !yieldQuery.isPending, meta: yieldQuery.data?.result_meta },
                { key: "adb-monthly-trend", title: "ADB 月度日均趋势", required: false, meta: adbMonthlyQuery.data?.result_meta },
                { key: "dates", title: "报告日目录", required: false, meta: datesQuery.data?.result_meta },
                { key: "asset-overview", title: "资产端正式总览", required: false, meta: balanceOverviewQuery.data?.result_meta },
                { key: "counterparty", title: "对手方集中度", required: !cpQuery.isPending, meta: cpQuery.data?.result_meta },
                { key: "knowledge", title: "业务资料", required: false, meta: knowledgeQuery.data?.result_meta },
                { key: "warnings", title: "关注/预警", required: false, meta: cockpitWarningsQuery.data?.result_meta },
                { key: "contribution", title: "贡献拆分", required: false, meta: contributionQuery.data?.result_meta },
              ]
            : [
                // 月度概览先返回；所选月明细与 ADB 压力读面独立加载、独立披露。
                {
                  key: "liabilities-monthly",
                  title: "负债月度概览",
                  required: !monthlySummaryQuery.isPending,
                  meta: monthlySummaryQuery.data?.result_meta,
                },
                {
                  key: "liabilities-monthly-detail",
                  title: "所选月结构明细",
                  required: Boolean(selectedMonth) && !monthlyDetailQuery.isPending,
                  meta: monthlyDetailQuery.data?.result_meta,
                },
                { key: "adb-monthly", title: "ADB 月度日均", required: !adbMonthlyQuery.isPending, meta: adbMonthlyQuery.data?.result_meta },
              ],
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
      cpQuery.data?.result_meta,
      cpQuery.isPending,
      datesQuery.data?.result_meta,
      explicitReportDate,
      firstYearPressureYi,
      knowledgeQuery.data?.result_meta,
      liabilityTotalYi,
      monthlySummaryQuery.data?.result_meta,
      monthlySummaryQuery.isPending,
      monthlyDetailQuery.data?.result_meta,
      monthlyDetailQuery.isPending,
      adbMonthlyQuery.data?.result_meta,
      adbMonthlyQuery.isPending,
      reportDate,
      riskQuery.data?.result_meta,
      riskQuery.data?.report_date,
      riskQuery.isPending,
      selectedMonthData?.month_label,
      selectedMonth,
      selectedReportDate,
      selectedYear,
      syntheticSections.calendarItems,
      syntheticSections.riskIndicators,
      authoritativeTop10ShareDisplay,
      warningsReturned,
      watchItems.length,
      yieldQuery.data?.result_meta,
      yieldQuery.isPending,
      yieldKpi,
    ],
  );
  /** 01 结论与 02+ 业务分区共用同一就绪门：五态互斥（DESIGN.md §6）。 */
  const dailyContentReady =
    activeTab === "daily" &&
    !datesBlockingError &&
    !datesEmpty &&
    !dailyLoading &&
    !dailyPrimaryError &&
    !dailyPrimaryEmpty;
  const dailyLeadState = sectionLeadState(
    dailyLoading,
    datesBlockingError || dailyPrimaryError,
    datesEmpty || dailyPrimaryEmpty,
  );
  const monthlyLeadState = sectionLeadState(
    monthlySummaryQuery.isLoading,
    monthlySummaryQuery.isError,
    !monthlySummaryQuery.isLoading && !monthlySummaryQuery.isError && !selectedMonthData,
  );
  const monthlyContentReady =
    activeTab === "monthly" &&
    !monthlySummaryQuery.isLoading &&
    !monthlySummaryQuery.isError &&
    Boolean(selectedMonthData);
  const knowledgeSectionVisible =
    knowledgeQuery.isLoading || knowledgeQuery.isError || knowledgeNotes.length > 0;

  /*
   * 深色 owner 由外层 ThemedRouteBoundary 的 data-moss-theme="dark" 承担；
   * 页根只声明主题 scope，重复声明 owner 会让深色路由校验判定出两个 owner。
   */
  return (
    <section
      data-testid="liability-analytics-page"
      data-moss-theme-scope="liability-analytics"
      className={`liability-analytics-page theme-dh-api ${SECTION_HEAD_STACK_CLASSNAME}`}
    >
      <header className="liability-analytics-page__header">
        <div className="liability-analytics-page__header-copy">
          <h1 className="liability-analytics-page__title">负债结构分析</h1>
          <p className="liability-analytics-page__subtitle">
            先判断资金来源是否集中、负债成本是否压缩 NIM，再看短端到期与预警证据。
          </p>
        </div>
        <span className="liability-analytics-page__mode-badge" data-tone={pageReadModel.modeBadge.tone}>
          {pageReadModel.modeBadge.label}
        </span>
      </header>

      <div className="liability-analytics-page__toolbar" data-testid="liability-analytics-toolbar">
        <Tabs
          activeKey={activeTab}
          onChange={(k) => setActiveTab(k as TabKey)}
          items={[
            { key: "daily", label: "日常分析" },
            { key: "monthly", label: "月度统计" },
          ]}
          className="liability-analytics-page__tabs"
        />
        <div className="liability-analytics-page__toolbar-controls">
          {activeTab === "daily" ? (
            <>
              {explicitReportDate ? (
                <span className="liability-analytics-page__toolbar-note">已由地址栏报告日参数固定</span>
              ) : null}
              <label className="liability-analytics-page__toolbar-field">
                <span className="liability-analytics-page__toolbar-label">报告日</span>
                <Select
                  aria-label="liability-report-date"
                  className="liability-analytics-page__toolbar-select liability-analytics-page__toolbar-select--date"
                  value={reportDate || undefined}
                  placeholder="选择报告日"
                  disabled={reportDateSelectDisabled}
                  options={dateOptions.map((d) => ({ value: d, label: d }))}
                  onChange={(v) => setSelectedReportDate(v)}
                  getPopupContainer={(t) => t.parentElement ?? document.body}
                />
              </label>
            </>
          ) : (
            <>
              <label className="liability-analytics-page__toolbar-field">
                <span className="liability-analytics-page__toolbar-label">选择年份</span>
                <Select
                  aria-label="liability-monthly-year"
                  className="liability-analytics-page__toolbar-select liability-analytics-page__toolbar-select--year"
                  value={selectedYear}
                  options={yearOptions.map((y) => ({ value: y, label: `${y} 年` }))}
                  onChange={(y) => {
                    setSelectedYear(y);
                    setSelectedMonth("");
                  }}
                  getPopupContainer={(t) => t.parentElement ?? document.body}
                />
              </label>
              <label className="liability-analytics-page__toolbar-field">
                <span className="liability-analytics-page__toolbar-label">按月选择</span>
                <Select
                  aria-label="liability-monthly-month"
                  className="liability-analytics-page__toolbar-select liability-analytics-page__toolbar-select--month"
                  value={selectedMonth || undefined}
                  placeholder="选择月份"
                  options={monthlyMonthsSorted.map((m) => ({ value: m.month, label: m.month_label }))}
                  onChange={(v) => setSelectedMonth(v)}
                  getPopupContainer={(t) => t.parentElement ?? document.body}
                />
              </label>
            </>
          )}
        </div>
      </div>

      {activeTab === "daily" ? (
        <>
          {/* 01 当日结论：readiness 锚点（liability-conclusion）必须留在本文件。 */}
          <section className="liability-section" id="liability-section-verdict">
            <SectionHead title="当日结论" state={dailyLeadState} />
            {balanceOverviewQuery.isError && !datesBlockingError && !datesEmpty ? (
              <div className="liability-notice liability-notice--warning">
                <strong className="liability-notice__title">市场资产（正式总览·资产口径）加载失败</strong>
                <span className="liability-notice__description">
                  {(balanceOverviewQuery.error as Error)?.message ?? "请求失败"}
                </span>
                <button
                  type="button"
                  className="liability-notice__retry"
                  onClick={() => void balanceOverviewQuery.refetch()}
                >
                  重试
                </button>
              </div>
            ) : null}
            {datesBlockingError ? (
              <div data-testid="liability-page-state" className="liability-notice liability-notice--error">
                <strong className="liability-notice__title">无法加载资产负债可用日期，请稍后重试。</strong>
                <button
                  type="button"
                  className="liability-notice__retry"
                  onClick={() => void datesQuery.refetch()}
                >
                  重试
                </button>
              </div>
            ) : null}
            {datesEmpty ? (
              <div data-testid="liability-page-state" className="liability-notice liability-notice--info">
                <strong className="liability-notice__title">暂无可用报告日。</strong>
              </div>
            ) : null}
            {datesBlockingError || datesEmpty ? null : dailyLoading ? (
              <p className="liability-analytics-page__surface liability-analytics-page__surface--loading">
                载入中…
              </p>
            ) : dailyPrimaryError ? (
              <div data-testid="liability-page-state" className="liability-notice liability-notice--error">
                <strong className="liability-notice__title">日常负债主数据加载失败</strong>
                <span className="liability-notice__description">
                  {riskQuery.isError
                    ? (riskQuery.error as Error)?.message ?? "请求失败"
                    : (cpQuery.error as Error | undefined)?.message ?? "对手方数据加载失败"}
                </span>
                <button
                  type="button"
                  className="liability-notice__retry"
                  onClick={() => {
                    void riskQuery.refetch();
                    void cpQuery.refetch();
                    void yieldQuery.refetch();
                  }}
                >
                  重试
                </button>
              </div>
            ) : dailyPrimaryEmpty ? (
              <div data-testid="liability-page-state" className="liability-notice liability-notice--info">
                <strong className="liability-notice__title">所选报告日暂无负债分析数据。</strong>
              </div>
            ) : null}
            {dailyContentReady && yieldQuery.isError ? (
              <div className="liability-notice liability-notice--warning">
                <strong className="liability-notice__title">
                  收益率/NIM 指标加载失败，压力测试卡片将降级为空。
                </strong>
                <button
                  type="button"
                  className="liability-notice__retry"
                  onClick={() => void yieldQuery.refetch()}
                >
                  重试
                </button>
              </div>
            ) : null}
            {dailyContentReady ? (
              <section data-testid="liability-conclusion" className="liability-analytics-page__conclusion">
                <span className="liability-analytics-page__conclusion-kicker">{dailyConclusion.title}</span>
                <div className="liability-analytics-page__conclusion-body">{dailyConclusion.body}</div>
                <div className="liability-analytics-page__conclusion-detail">{dailyConclusion.detail}</div>
              </section>
            ) : null}
            <div className="liability-kpi-band" data-testid="liability-analytics-kpi-band" data-cols="6">
              {pageReadModel.kpis.map((kpi) => (
                <div key={kpi.key} className="liability-kpi-cell">
                  <span className="liability-kpi-cell__label" title={kpi.label}>
                    {kpi.label}
                  </span>
                  <span className="liability-kpi-cell__value">
                    {kpi.value}
                    {kpi.unit ? <span className="liability-kpi-cell__unit">{kpi.unit}</span> : null}
                  </span>
                  {kpi.detail ? (
                    <span className="liability-kpi-cell__note" title={kpi.detail}>
                      {kpi.detail}
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
            <div className="liability-analytics-page__status-row" data-testid="liability-analytics-data-status">
              {pageReadModel.statusBadges.map((badge) => (
                <span key={badge.key} className="liability-analytics-page__status-badge" data-tone={badge.tone}>
                  {badge.label}
                </span>
              ))}
            </div>
          </section>

          {dailyContentReady ? (
            <>
              {/* 02 收益成本与风险 */}
              <section className="liability-section">
                <SectionHead title="收益成本与风险" />
                <div className="liability-analytics-page__grid liability-analytics-page__grid--2">
                  <div className="liability-panel">
                    <h3 className="liability-panel__title">收益成本分解（静态口径）</h3>
                    {yieldReadGapNote ? (
                      <p className="liability-caption liability-caption--gap">{yieldReadGapNote}</p>
                    ) : null}
                    <div className="liability-kpi-band liability-kpi-band--compact" data-cols="2">
                      <div className="liability-kpi-cell">
                        <span className="liability-kpi-cell__label">资产收益</span>
                        <span className="liability-kpi-cell__value">
                          {yieldKpi?.asset_yield?.display ?? EM_DASH}
                        </span>
                        <span className="liability-kpi-cell__note">静态口径</span>
                      </div>
                      <div className="liability-kpi-cell">
                        <span className="liability-kpi-cell__label">市场化负债成本</span>
                        <span className="liability-kpi-cell__value">
                          {yieldKpi?.market_liability_cost?.display ?? EM_DASH}
                        </span>
                        <span className="liability-kpi-cell__note">NIM 使用的成本口径</span>
                      </div>
                      <div className="liability-kpi-cell">
                        <span className="liability-kpi-cell__label">净息差</span>
                        <span className="liability-kpi-cell__value">{yieldKpi?.nim?.display ?? EM_DASH}</span>
                        <span className="liability-kpi-cell__note">NIM</span>
                      </div>
                      <div className="liability-kpi-cell">
                        <span className="liability-kpi-cell__label">1Y压力</span>
                        <span className="liability-kpi-cell__value">
                          {fixedOrDash(firstYearPressureYi, 2)}
                          <span className="liability-kpi-cell__unit">亿</span>
                        </span>
                        <span className="liability-kpi-cell__note">已知到期日，含已到期</span>
                      </div>
                    </div>
                    <LiabilityYieldTrendPanel
                      year={adbMonthlyYear}
                      months={adbMonthlyQuery.data?.months}
                      loading={adbMonthlyQuery.isLoading}
                      error={adbMonthlyQuery.isError}
                    />
                    <p className="liability-caption">
                      静态 NIM = 资产收益率 − 市场化负债成本（同业负债 + 发行同业存单）；整体负债成本还包括其他发行负债。下方趋势采用月度日均口径。
                    </p>
                    {missingMaturityCount > 0 ? (
                      <p
                        className="liability-caption liability-caption--gap"
                        data-testid="liability-missing-maturity-warning"
                      >
                        {missingMaturityCount} 条负债记录未列到期日，期限属性待核实；单列为“到期日未提供”，不计入已知的 1 年内到期金额，到期压力尚不完整。
                      </p>
                    ) : null}
                  </div>

                  <div className="liability-panel">
                    <h3 className="liability-panel__title">资产 / 负债 / 缺口贡献</h3>
                    {contributionRows.length === 0 ? (
                      <div className="liability-notice liability-notice--info">
                        <strong className="liability-notice__title">暂无贡献拆分数据</strong>
                        <span className="liability-notice__description">
                          {contributionQuery.isLoading ? "加载中…" : "所选报告日无可用拆分数据。"}
                        </span>
                      </div>
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
                              <td className="is-label">
                                {row.category}
                                {(row.missing_rate_amount_yi ?? 0) > 0 ? (
                                  <div>
                                    利率覆盖 {row.rate_coverage_pct?.toFixed(2) ?? EM_DASH}%；
                                    缺失利率金额 {row.missing_rate_amount_yi?.toFixed(2)} 亿；
                                    已知部分贡献 {row.known_contribution_yi != null ? row.known_contribution_yi.toFixed(2) : EM_DASH} 亿；
                                    总体贡献不可用
                                  </div>
                                ) : null}
                              </td>
                              <td>
                                {/* 方向是分类不是语义状态：统一中性描边，靠文字区分（§4）。 */}
                                <span className="liability-ib-tag">
                                  {row.side === "asset" ? "资产" : "负债"}
                                </span>
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
                                {row.contribution_yi !== null ? row.contribution_yi.toFixed(2) : EM_DASH}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              </section>

              {/* 03 结构与期限 */}
              <section className="liability-section">
                <SectionHead title="期限结构（资产 / 负债 / 净缺口）" note="单位：亿元" />
                <LiabilityStructureGrids
                  structure={dailyStructure}
                  term={dailyTerm}
                  interbankStructure={dailyIbStructure}
                  interbankTerm={dailyIbTerm}
                  issuedStructure={dailyIssuedStructure}
                  issuedTerm={dailyIssuedTerm}
                />
              </section>

              {/* 04 资金来源集中度 */}
              <section className="liability-section">
                <SectionHead
                  title="资金来源集中度"
                  state={cpQuery.isLoading ? { label: "读取中", tone: "loading" } : null}
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
                <LiabilityCustomerTable
                  rows={dailyCpRows}
                  loading={cpQuery.isLoading}
                  subtitle='口径：TYWL 负债端（对手方名称 × 金额；剔除「青岛银行股份有限公司」；空值归「其它」）。'
                />
              </section>

              {/* 05 压力测试（组件自渲染编号分区帧） */}
              <LiabilityNimStressPanel yieldKpi={yieldKpi} gapNote={yieldReadGapNote} />

              {/* 06 预警与关注 */}
              <section className="liability-section">
                <SectionHead title="预警与关注" />
                <div className="liability-analytics-page__grid liability-analytics-page__grid--2">
                  <div className="liability-panel">
                    <h3 className="liability-panel__title">待关注事项</h3>
                    {watchItems.length === 0 ? (
                      <div className="liability-notice liability-notice--info">
                        {/* 空态不做「所有指标正常」全称断言：右卡预警不计入本卡口径（§7 自审）。 */}
                        <strong className="liability-notice__title">
                          {cockpitWarningsQuery.isError ? "待办事项读取失败" : "暂无结构化待办事项"}
                        </strong>
                        <span className="liability-notice__description">
                          {cockpitWarningsQuery.isLoading
                            ? "加载中…"
                            : cockpitWarningsQuery.isError
                              ? "预警读面未返回，本卡不判定为无待办。"
                              : "本卡仅统计结构化待办；预警事件见右侧卡片。"}
                        </span>
                      </div>
                    ) : (
                      <div className="liability-analytics-page__notice-stack">
                        {watchItems.map((item) => (
                          <div
                            key={item.id}
                            className={`liability-notice liability-notice--${
                              item.level === "warning" ? "warning" : "info"
                            }`}
                          >
                            <strong className="liability-notice__title">{item.label}</strong>
                            <span className="liability-notice__description">{item.detail}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="liability-panel">
                    <h3 className="liability-panel__title">预警与事件</h3>
                    {alertEvents.length === 0 ? (
                      <div className="liability-notice liability-notice--info">
                        <strong className="liability-notice__title">
                          {cockpitWarningsQuery.isError ? "预警事件读取失败" : "当前无预警事件"}
                        </strong>
                        <span className="liability-notice__description">
                          {cockpitWarningsQuery.isLoading
                            ? "加载中…"
                            : cockpitWarningsQuery.isError
                              ? "预警读面未返回，本卡不判定为未触发。"
                              : "未触发预警阈值。"}
                        </span>
                      </div>
                    ) : (
                      <div className="liability-analytics-page__notice-stack">
                        {alertEvents.map((evt) => (
                          <div
                            key={evt.id}
                            className={`liability-notice liability-notice--${
                              evt.severity === "high" ? "error" : evt.severity === "medium" ? "warning" : "info"
                            }`}
                          >
                            <strong className="liability-notice__title">{evt.title}</strong>
                            <span className="liability-notice__description">{`${evt.occurred_at}：${evt.detail}`}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                </div>
                {/* 预留区块整卡隐藏，仅留一行安静说明（§5 空态收缩；证据区仍保留降级披露）。 */}
                <p className="liability-caption">
                  {`${syntheticSections.riskIndicators.title}、${syntheticSections.calendarItems.title}：待相应接口接入后提供，当前不展示示意数据。`}
                </p>
              </section>

              {/* 07 业务资料（无笔记且无状态时整节隐藏，编号自动顺延） */}
              {knowledgeSectionVisible ? (
                <section className="liability-section">
                  <SectionHead
                    title="业务资料"
                    state={
                      knowledgeQuery.isLoading
                        ? { label: "读取中", tone: "loading" }
                        : knowledgeQuery.isError
                          ? { label: "读取失败", tone: "error" }
                          : null
                    }
                    note={!knowledgeQuery.isLoading && !knowledgeQuery.isError ? knowledgeStatusNote ?? undefined : undefined}
                  />
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
                </section>
              ) : null}
            </>
          ) : null}
        </>
      ) : (
        <>
          {/* 01 月度概览 */}
          <section className="liability-section">
            <SectionHead
              title="月度概览（月日均）"
              state={monthlyLeadState}
              note={
                monthlyContentReady && selectedMonthData
                  ? `有效天数：${selectedMonthData.num_days} 天（口径：月度日均）`
                  : undefined
              }
            />
            {monthlySummaryQuery.isLoading ? (
              <p className="liability-analytics-page__surface liability-analytics-page__surface--loading">
                载入中…
              </p>
            ) : monthlySummaryQuery.isError ? (
              <div className="liability-notice liability-notice--error">
                <strong className="liability-notice__title">月度概览加载失败</strong>
                <span className="liability-notice__description">
                  {(monthlySummaryQuery.error as Error)?.message ?? "请求失败"}
                </span>
                <button
                  type="button"
                  className="liability-notice__retry"
                  onClick={() => void monthlySummaryQuery.refetch()}
                >
                  重试
                </button>
              </div>
            ) : !selectedMonthData ? (
              <div className="liability-notice liability-notice--info">
                <strong className="liability-notice__title">{`暂无 ${selectedYear} 年的月度数据`}</strong>
              </div>
            ) : (
              <LiabilityMonthlySnapshotCards
                month={selectedMonthData}
                ytdAvgTotalLiabilities={monthlySummaryQuery.data?.ytd_avg_total_liabilities ?? null}
                ytdAvgLiabilityCost={monthlySummaryQuery.data?.ytd_avg_liability_cost ?? null}
              />
            )}
            <div className="liability-analytics-page__status-row" data-testid="liability-analytics-data-status">
              {pageReadModel.statusBadges.map((badge) => (
                <span key={badge.key} className="liability-analytics-page__status-badge" data-tone={badge.tone}>
                  {badge.label}
                </span>
              ))}
            </div>
          </section>

          {monthlyContentReady && selectedMonthData ? (
            <>
              {/* 02 压力测试（月度）：与概览、结构明细分别加载。 */}
              {adbMonthlyQuery.isPending ? (
                <section className="liability-section">
                  <SectionHead
                    title="压力测试：NIM 敏感性（负债成本 +50bps）"
                    state={{ label: "读取中", tone: "loading" }}
                  />
                  <p className="liability-analytics-page__surface liability-analytics-page__surface--loading">
                    月度 NIM 压力数据读取中…
                  </p>
                </section>
              ) : adbMonthlyQuery.isError ? (
                <section className="liability-section">
                  <SectionHead
                    title="压力测试：NIM 敏感性（负债成本 +50bps）"
                    state={{ label: "读取失败", tone: "error" }}
                  />
                  <div className="liability-notice liability-notice--error">
                    <strong className="liability-notice__title">月度 NIM 压力数据加载失败</strong>
                    <span className="liability-notice__description">
                      {(adbMonthlyQuery.error as Error)?.message ?? "请求失败"}
                    </span>
                    <button
                      type="button"
                      className="liability-notice__retry"
                      onClick={() => void adbMonthlyQuery.refetch()}
                    >
                      重试
                    </button>
                  </div>
                </section>
              ) : !selectedAdbMonthData ? (
                <section className="liability-section">
                  <SectionHead
                    title="压力测试：NIM 敏感性（负债成本 +50bps）"
                    state={{ label: "暂无数据", tone: "empty" }}
                  />
                  <div className="liability-notice liability-notice--info">
                    <strong className="liability-notice__title">所选月份暂无 ADB 压力读数</strong>
                  </div>
                </section>
              ) : (
                <LiabilityNimStressMonthlyPanel adbMonth={selectedAdbMonthData} />
              )}

              {/* 03 资金来源集中度（月度日均） */}
              <section className="liability-section">
                <SectionHead title="资金来源集中度" state={monthlyDetailLeadState} />
                {monthlyDetailError ? (
                  <div className="liability-notice liability-notice--error">
                    <strong className="liability-notice__title">所选月份结构明细加载失败</strong>
                    <span className="liability-notice__description">
                      {(monthlyDetailQuery.error as Error)?.message ?? "请求失败"}
                    </span>
                    <button
                      type="button"
                      className="liability-notice__retry"
                      onClick={() => void monthlyDetailQuery.refetch()}
                    >
                      重试
                    </button>
                  </div>
                ) : monthlyDetailEmpty ? (
                  <div className="liability-notice liability-notice--info">
                    <strong className="liability-notice__title">所选月份暂无集中度明细</strong>
                  </div>
                ) : (
                  <>
                    <LiabilityCounterpartyBlock
                      title="资金来源依赖度（前十对手方）"
                      subtitle="口径：月度日均（TYWL 负债端）。"
                      totalValue={selectedMonthDetail?.counterparty_total ?? null}
                      authoritativeTop10Share={selectedMonthDetail?.top10_share ?? null}
                      authoritativeHhi={selectedMonthDetail?.hhi ?? null}
                      populationCount={selectedMonthDetail?.population_count ?? null}
                      isTruncated={selectedMonthDetail?.is_truncated ?? false}
                      counterpartyRows={monthlyCpRowsAll}
                      barRankingRows={monthlyCpBarRows}
                      byType={monthlyByInstitution}
                      loading={monthlyDetailLoading}
                      errorText={null}
                    />
                    <LiabilityCustomerTable
                      rows={monthlyCpRowsAll}
                      loading={monthlyDetailLoading}
                      subtitle="口径：月度日均（TYWL 负债端）。"
                    />
                  </>
                )}
              </section>

              {/* 04 结构与期限（月度日均） */}
              <section className="liability-section">
                <SectionHead
                  title="期限结构（资产 / 负债 / 净缺口）"
                  note="单位：亿元"
                  state={monthlyDetailLeadState}
                />
                {monthlyDetailLoading ? (
                  <p className="liability-analytics-page__surface liability-analytics-page__surface--loading">
                    所选月份期限结构读取中…
                  </p>
                ) : monthlyDetailError ? (
                  <div className="liability-notice liability-notice--error">
                    <strong className="liability-notice__title">所选月份期限结构加载失败</strong>
                  </div>
                ) : monthlyDetailEmpty ? (
                  <div className="liability-notice liability-notice--info">
                    <strong className="liability-notice__title">所选月份暂无期限结构明细</strong>
                  </div>
                ) : (
                  <LiabilityStructureGrids
                    structure={mStructure}
                    term={mTerm}
                    interbankStructure={mIbStructure}
                    interbankTerm={mIbTerm}
                    issuedStructure={mIssuedStructure}
                    issuedTerm={mIssuedTerm}
                    structurePieCaption="同业负债业务结构（按产品类型）与发行负债业务结构（按业务种类）在总视图中的合并展示。"
                  />
                )}
              </section>
            </>
          ) : null}
        </>
      )}

      {/* 证据与口径：两个页签共用，始终后置披露。 */}
      {/* 两面板改单栏满宽 + 卡片 auto-fill 流铺（§11.2：禁止左右栏裸空白断层；ledger-pnl 先例）。 */}
      <section className="liability-section" id="liability-section-evidence">
        <SectionHead title="证据与口径" />
        <div className="liability-analytics-page__grid">
          <div className="liability-panel">
            <h3 className="liability-panel__title">状态证据</h3>
            <div className="liability-analytics-page__state-stack">
              {evidenceLoading ? (
                <PageStateSurface
                  variant="loading"
                  title="核心读面元数据读取中"
                  description="账本将在核心读面返回后生成，不提前判定为元数据缺口。"
                />
              ) : null}
              {evidenceBlocked ? (
                <PageStateSurface
                  variant={datesBlockingError ? "error" : "empty"}
                  title="核心读面未触发"
                  description={
                    datesBlockingError
                      ? "报告日目录读取失败，核心读面未发起请求，账本无法生成。"
                      : "暂无可用报告日，核心读面未发起请求，账本无法生成。"
                  }
                />
              ) : null}
              {pageReadModel.stateSurfaces.map((surface) => (
                <PageStateSurface
                  key={surface.key}
                  variant={surface.variant}
                  title={surface.title}
                  description={surface.description}
                />
              ))}
            </div>
          </div>
          <div className="liability-panel">
            <h3 className="liability-panel__title">证据账本</h3>
            <div className="liability-analytics-page__evidence-ledger">
              {evidenceLoading ? (
                <div className="liability-analytics-page__evidence-loading">证据账本读取中…</div>
              ) : null}
              {evidenceBlocked ? (
                <div className="liability-analytics-page__evidence-loading">核心读面未触发，证据账本未生成。</div>
              ) : null}
              {pageReadModel.evidenceCards.map((card) => (
                <article key={card.key} className="liability-analytics-page__evidence-card" data-tone={card.tone}>
                  <div className="liability-analytics-page__evidence-card-top">
                    <strong>{card.title}</strong>
                    <span>{card.basisLabel}</span>
                  </div>
                  <dl className="liability-analytics-page__evidence-summary">
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
                  </dl>
                  <details
                    className="liability-analytics-page__evidence-lineage"
                    data-testid={`liability-evidence-lineage-${card.key}`}
                  >
                    <summary>查看完整血缘</summary>
                    <dl>
                      <div>
                        <dt title="trace_id">追踪号</dt>
                        <dd>{card.traceId}</dd>
                      </div>
                      <div>
                        <dt title="source_version">来源版本</dt>
                        <dd>{card.sourceVersion}</dd>
                      </div>
                      <div>
                        <dt title="rule_version">规则版本</dt>
                        <dd>{card.ruleVersion}</dd>
                      </div>
                    </dl>
                  </details>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>
    </section>
  );
}
