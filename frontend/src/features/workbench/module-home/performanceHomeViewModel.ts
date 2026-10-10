import { EM_DASH } from "../../../utils/format";
import type {
  KpiPeriodMetricSummary,
  KpiPeriodSummaryResponse,
  PnlByBusinessYtdItem,
} from "../../../api/contracts";
import type {
  ModuleHomeDetailRow,
  ModuleHomeTone,
} from "./moduleHomeDetailTypes";
import { formatRatioPct } from "../../pnl/pnlByBusinessPageModel";
import {
  formatYiFromYuan,
  buildDetailPanel,
} from "./moduleHomePresentation";
import type {
  ModuleHomeSourceQueries,
  ModuleHomeDataState,
  ModuleHomeView,
} from "./moduleHomeModel";
import type { UseQueryResult } from "@tanstack/react-query";
import {
  queryIsInitialLoading,
  queryHasData,
  queryResultMeta,
  resultMetaIsStale,
  resultMetaIsPartial,
  emptyRowsWatchStatus,
  queryStatus,
  MODULE_HOME_STATE_LABEL,
  baseDataNote,
} from "./moduleHomeSourceState";

function formatKpiDecimal(value: string | null | undefined, decimals = 2): string {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  const num = Number.parseFloat(value);
  if (Number.isNaN(num)) {
    return String(value);
  }
  return num.toLocaleString("zh-CN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatKpiMetricDetailValue(metric: KpiPeriodMetricSummary): string {
  const score = formatKpiDecimal(metric.period_score_value, 2);
  const actual = formatKpiDecimal(metric.period_actual_value, 2);
  const target = formatKpiDecimal(metric.target_value, 2);
  const unit = metric.unit ? ` ${metric.unit}` : "";
  return `得分 ${score} · 实际 ${actual}${unit} / 目标 ${target}${unit}`;
}

function buildPerformanceKpiDetailRows(kpi: KpiPeriodSummaryResponse): ModuleHomeDetailRow[] {
  return kpi.metrics.slice(0, 10).map((metric) => ({
    key: `kpi-metric-${metric.metric_id}`,
    label: metric.metric_name,
    value: formatKpiMetricDetailValue(metric),
    tradeDate: metric.data_date ?? metric.period_end_date,
    source: metric.metric_code,
    tone: "ok",
  }));
}

function buildPerformanceBusinessPnlRows(
  items: PnlByBusinessYtdItem[],
  periodEndDate: string,
): ModuleHomeDetailRow[] {
  const sorted = [...items].sort((left, right) => left.sort_order - right.sort_order);
  return sorted.slice(0, 10).map((item) => {
    const proportion =
      item.proportion !== null && item.proportion !== undefined && item.proportion !== ""
        ? formatRatioPct(item.proportion)
        : null;
    const balance = formatYiFromYuan(item.current_balance);
    const pnlValue = formatYiFromYuan(item.total_pnl);
    const valueParts = [pnlValue];
    if (proportion && proportion !== EM_DASH) {
      valueParts.push(`占比 ${proportion}`);
    }
    const sourceParts = [item.row_key];
    if (balance !== EM_DASH) {
      sourceParts.push(`规模 ${balance}`);
    }
    return {
      key: `pnl-business-${item.row_key}`,
      label: item.business_type,
      value: valueParts.join(" · "),
      tradeDate: periodEndDate,
      source: sourceParts.join(" · "),
      tone: "ok",
    };
  });
}

function performanceSourceMeta(source: string, periodLabel: string): string {
  return `来源 ${source} · ${periodLabel || EM_DASH}`;
}

function performanceHomeDataState(args: {
  queries: ModuleHomeSourceQueries;
  hasContent: boolean;
  hasKpiContent: boolean;
  hasPnlContent: boolean;
}): ModuleHomeDataState {
  const active = [args.queries.kpiOwners, args.queries.kpiSummary, args.queries.pnlYtd].filter(
    Boolean,
  ) as Array<UseQueryResult<unknown>>;
  if (active.some((query) => queryIsInitialLoading(query))) {
    return "loading";
  }

  const withData = active.filter((query) => queryHasData(query));
  const withError = active.filter((query) => query.isError);
  if (withError.length > 0) {
    return withData.length > 0 ? "partial" : "error";
  }
  if (active.length === 0 || withData.length === 0 || !args.hasContent) {
    return "empty";
  }
  if (withData.length < active.length) {
    return "partial";
  }

  const pnlMeta = queryResultMeta(args.queries.pnlYtd);
  if (resultMetaIsStale(pnlMeta)) {
    return "stale";
  }
  if ((pnlMeta && resultMetaIsPartial(pnlMeta)) || !args.hasKpiContent || !args.hasPnlContent) {
    return "partial";
  }
  return "ready";
}

export function performanceView(
  queries: ModuleHomeSourceQueries,
): Omit<ModuleHomeView, "kind" | "title" | "question" | "summary" | "sourceScope"> {
  const owners = queries.kpiOwners?.data;
  const kpi = queries.kpiSummary?.data;
  const pnl = queries.pnlYtd?.data?.result;

  const kpiDetailRows = kpi ? buildPerformanceKpiDetailRows(kpi) : [];
  const kpiDetailStatus =
    owners?.total === 0
      ? {
          key: "kpi-metric-detail",
          label: "KPI 指标明细",
          value: "暂无考核对象",
          detail: "本年没有活跃 KPI Owner，无法读取个人 KPI 汇总；请进入绩效考核页配置负责人。",
          tone: "watch" as ModuleHomeTone,
        }
      : emptyRowsWatchStatus(
          queryStatus(
            "kpi-metric-detail",
            "KPI 指标明细",
            queries.kpiSummary,
            `KPI 汇总已返回 ${kpiDetailRows.length} 条指标。`,
          ),
          kpiDetailRows,
          "KPI 汇总已返回，但没有指标明细；请进入绩效考核页核验指标配置。",
        );
  const kpiDetailPanel = buildDetailPanel({
    key: "kpi-metric-detail",
    title: "KPI 指标明细",
    meta: performanceSourceMeta("kpi", kpi?.period_label ?? String(kpi?.year ?? EM_DASH)),
    status: kpiDetailStatus,
    rows: kpiDetailRows,
  });

  const businessPnlRows = pnl
    ? buildPerformanceBusinessPnlRows(pnl.items, pnl.period_end_date)
    : [];
  const businessPnlStatus = emptyRowsWatchStatus(
    queryStatus(
      "business-pnl-detail",
      "业务种类损益",
      queries.pnlYtd,
      `本年业务损益已返回 ${businessPnlRows.length} 条。`,
    ),
    businessPnlRows,
    "本年业务损益接口已返回，但没有明细项目；请进入业务种类损益页核验报告期与来源。",
  );
  const businessPnlPanel = buildDetailPanel({
    key: "business-pnl-detail",
    title: "业务种类损益",
    meta: performanceSourceMeta("pnl/by-business", pnl?.period_label ?? String(pnl?.year ?? EM_DASH)),
    status: businessPnlStatus,
    rows: businessPnlRows,
  });

  const dataState = performanceHomeDataState({
    queries,
    hasContent: Boolean(owners?.total) || kpiDetailRows.length > 0 || businessPnlRows.length > 0,
    hasKpiContent: Boolean(owners?.total) && kpiDetailRows.length > 0,
    hasPnlContent: businessPnlRows.length > 0,
  });
  const stateDetail =
    dataState === "loading"
      ? "正在读取 KPI 负责人、绩效汇总与本年业务损益。"
      : dataState === "error"
        ? "绩效读链路失败，不使用前端补数；请重试或进入下钻页核验。"
        : dataState === "empty"
          ? "本年尚无活跃 KPI 负责人和业务损益明细；请先进入绩效考核页核验负责人及指标配置。"
          : dataState === "partial"
            ? "部分绩效来源暂无可用明细；已返回的数据继续展示，不使用前端补数。"
            : dataState === "stale"
              ? "绩效数据已返回，但业务损益结果已过期；复盘前请先核验报告期与来源。"
              : `KPI Owner ${owners?.total ?? EM_DASH} 个，业务损益项目 ${pnl?.items.length ?? EM_DASH} 条。`;

  return {
    dataState,
    stateLabel: MODULE_HOME_STATE_LABEL[dataState],
    stateDetail,
    kpis: [
      {
        key: "owner-count",
        label: "KPI Owner",
        value: String(owners?.total ?? EM_DASH),
        detail: owners ? "本年活跃考核负责人数。" : "考核负责人清单读取失败或未返回。",
        detailTitle: "getKpiOwners",
        tone: owners && owners.total > 0 ? "ok" : "watch",
      },
      {
        key: "kpi-score",
        label: "本期得分",
        value: kpi?.total_score ? `${kpi.total_score} 分` : EM_DASH,
        detail: kpi ? `${kpi.period_label} · ${kpi.owner_name}` : "KPI 汇总未返回。",
        detailTitle: "getKpiValuesSummary",
        tone: kpi ? "ok" : "watch",
      },
      {
        key: "metric-count",
        label: "指标数",
        value: String(kpi?.total ?? EM_DASH),
        detail: kpi ? "本期考核指标总数。" : "KPI 汇总未返回。",
        detailTitle: "getKpiValuesSummary.total",
        tone: kpi ? "ok" : "watch",
      },
      {
        key: "business-pnl",
        label: "YTD 业务损益",
        value: formatYiFromYuan(pnl?.total_pnl),
        detail: pnl ? `${pnl.period_label}正式口径汇总。` : "业务损益 YTD 未返回。",
        detailTitle: pnl ? `getPnlByBusinessYtd · ${pnl.source_tables.join(" / ")}` : "getPnlByBusinessYtd",
        tone: pnl ? "ok" : "watch",
      },
    ],
    statuses: [
      queryStatus("owners", "KPI Owner", queries.kpiOwners, "owners 已返回。"),
      { ...kpiDetailStatus, key: "summary", label: "KPI 汇总" },
      { ...businessPnlStatus, key: "pnl", label: "业务损益" },
      {
        key: "team",
        label: "团队绩效",
        value: "下钻页",
        detail: "团队映射和复盘规则在 /team-performance 展示。",
        tone: "muted",
      },
    ],
    briefings: [
      ...(owners?.total === 0
        ? []
        : [
            {
              title: "KPI 完成",
              conclusion: kpi
                ? `${kpi.period_label} 指标 ${kpi.total} 个，总分 ${kpi.total_score}。`
                : "KPI 汇总暂无可用数据。",
              evidence: "只展示 KPI 汇总接口返回值。",
              tone: kpi ? ("ok" as ModuleHomeTone) : ("watch" as ModuleHomeTone),
            },
          ]),
      {
        title: "团队贡献",
        conclusion: owners ? `当前活跃考核负责人 ${owners.total} 个。` : "考核负责人清单未返回。",
        evidence: "团队贡献明细进入团队绩效页。",
        tone: owners ? "ok" : "watch",
      },
      {
        title: "损益复盘",
        conclusion: pnl ? `YTD 业务损益 ${formatYiFromYuan(pnl.total_pnl)}。` : "业务损益摘要未返回。",
        evidence: "使用 /pnl/by-business YTD 字段，不在首页重算 FTP 或收益率。",
        tone: pnl ? "ok" : "watch",
      },
    ],
    detailPanels: [kpiDetailPanel, businessPnlPanel],
    dataNote: baseDataNote("performance", queries),
  };
}
