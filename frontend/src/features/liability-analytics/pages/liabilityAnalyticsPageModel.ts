import type { ResultMeta } from "../../../api/contracts";
import type { LiabilityYieldKpi } from "../../../api/liabilityAdbContracts";
import { EM_DASH } from "../../../utils/format";

export type LiabilityAnalyticsTabKey = "daily" | "monthly";

export type LiabilityPageBadgeTone = "ok" | "info" | "warning" | "danger" | "mock";

export type LiabilityPageStatusBadge = {
  key: string;
  label: string;
  tone: LiabilityPageBadgeTone;
};

export type LiabilityPageKpi = {
  key: string;
  label: string;
  value: string;
  unit?: string;
  detail?: string;
};

export type LiabilityPageEvidenceCard = {
  key: string;
  title: string;
  resultKind: string;
  basisLabel: string;
  qualityLabel: string;
  fallbackLabel: string;
  asOfDate: string;
  traceId: string;
  sourceVersion: string;
  ruleVersion: string;
  tone: LiabilityPageBadgeTone;
};

export type LiabilityPageStateSurface = {
  key: string;
  variant: "neutral" | "fallback-date" | "mock" | "stale" | "definition-pending";
  title: string;
  description: string;
};

export type LiabilitySyntheticEvidenceInput = {
  key: string;
  title: string;
  detail: string;
};

export type LiabilityResultMetaInput = {
  key: string;
  title: string;
  meta?: ResultMeta | null;
};

export type BuildLiabilityAnalyticsPageReadModelInput = {
  mode: string;
  activeTab: LiabilityAnalyticsTabKey;
  requestedReportDate: string;
  resolvedReportDate: string;
  selectedYear: number;
  selectedMonthLabel: string | null;
  yieldKpi: LiabilityYieldKpi | null;
  liabilityTotalYi: number | null;
  firstYearPressureYi: number | null;
  topCounterpartyShare: string;
  warningCount: number;
  alertCount: number;
  resultMetas: LiabilityResultMetaInput[];
  syntheticSections: LiabilitySyntheticEvidenceInput[];
};

export type LiabilityAnalyticsPageReadModel = {
  modeBadge: LiabilityPageStatusBadge;
  reportLine: string;
  statusBadges: LiabilityPageStatusBadge[];
  kpis: LiabilityPageKpi[];
  evidenceCards: LiabilityPageEvidenceCard[];
  stateSurfaces: LiabilityPageStateSurface[];
};

function formatYi(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return value.toFixed(2);
}

function formatBpFromPctNumeric(kpi: LiabilityYieldKpi | null) {
  const nim = kpi?.nim?.raw;
  if (nim === null || nim === undefined || !Number.isFinite(nim)) {
    return EM_DASH;
  }
  return `${(nim * 10000).toFixed(1)}bp`;
}

function toneForMeta(meta: ResultMeta): LiabilityPageBadgeTone {
  if (meta.fallback_mode !== "none" || meta.vendor_status !== "ok") {
    return "warning";
  }
  if (meta.quality_flag !== "ok") {
    return "danger";
  }
  return meta.formal_use_allowed ? "ok" : "info";
}

function basisLabel(meta: ResultMeta) {
  if (meta.basis === "formal" && meta.formal_use_allowed) {
    return "正式可用";
  }
  if (meta.basis === "formal") {
    return "正式口径不可直接使用";
  }
  if (meta.basis === "analytical") {
    return "分析读面";
  }
  if (meta.basis === "scenario") {
    return "情景读面";
  }
  return meta.basis ? `${meta.basis} 读面` : "读面未标注";
}

function buildEvidenceCard(source: LiabilityResultMetaInput): LiabilityPageEvidenceCard | null {
  const meta = source.meta;
  if (!meta) {
    return null;
  }

  return {
    key: source.key,
    title: source.title,
    resultKind: meta.result_kind,
    basisLabel: basisLabel(meta),
    qualityLabel: meta.quality_flag,
    fallbackLabel: meta.fallback_mode,
    asOfDate: meta.as_of_date ?? EM_DASH,
    traceId: meta.trace_id || EM_DASH,
    sourceVersion: meta.source_version || EM_DASH,
    ruleVersion: meta.rule_version || EM_DASH,
    tone: toneForMeta(meta),
  };
}

export function buildLiabilityAnalyticsPageReadModel(
  input: BuildLiabilityAnalyticsPageReadModelInput,
): LiabilityAnalyticsPageReadModel {
  const requested = input.requestedReportDate || input.resolvedReportDate || EM_DASH;
  const resolved = input.resolvedReportDate || EM_DASH;
  const isMock = input.mode !== "real";
  const hasDateMismatch =
    Boolean(input.requestedReportDate) &&
    Boolean(input.resolvedReportDate) &&
    input.requestedReportDate !== input.resolvedReportDate;
  const resultMetas = input.resultMetas.map(buildEvidenceCard).filter(Boolean) as LiabilityPageEvidenceCard[];
  const fallbackCards = resultMetas.filter((card) => card.fallbackLabel !== "none");
  const staleCards = input.resultMetas.filter(
    (source) => source.meta?.vendor_status === "vendor_stale" || source.meta?.vendor_status === "vendor_unavailable",
  );
  const qualityCards = resultMetas.filter((card) => card.qualityLabel !== "ok");

  const statusBadges: LiabilityPageStatusBadge[] = [
    {
      key: "surface",
      label: "分析读面",
      tone: "info",
    },
    {
      key: "mode",
      label: isMock ? "演示数据" : "真实链路",
      tone: isMock ? "mock" : "ok",
    },
    {
      key: "tab",
      label: input.activeTab === "daily" ? "日常报告日" : "月度日均",
      tone: "info",
    },
    {
      key: "date",
      label: hasDateMismatch ? `请求 ${requested} · 返回 ${resolved}` : `报告日 ${resolved}`,
      tone: hasDateMismatch ? "warning" : "ok",
    },
  ];

  if (fallbackCards.length > 0) {
    statusBadges.push({
      key: "fallback",
      label: `${fallbackCards.length} 个兜底结果`,
      tone: "warning",
    });
  }
  if (staleCards.length > 0) {
    statusBadges.push({
      key: "stale",
      label: `${staleCards.length} 个供应商状态异常`,
      tone: "warning",
    });
  }
  if (qualityCards.length > 0) {
    statusBadges.push({
      key: "quality",
      label: `${qualityCards.length} 个质量未通过`,
      tone: "danger",
    });
  }

  const kpis: LiabilityPageKpi[] =
    input.activeTab === "daily"
      ? [
          {
            key: "liability-total",
            label: "市场负债",
            value: formatYi(input.liabilityTotalYi),
            unit: "亿",
            detail: "对手方总额 / 期限桶回退",
          },
          {
            key: "liability-cost",
            label: "负债成本",
            value: input.yieldKpi?.liability_cost?.display ?? EM_DASH,
            detail: "后端收益指标",
          },
          {
            key: "nim",
            label: "NIM",
            value: input.yieldKpi?.nim?.display ?? EM_DASH,
            detail: formatBpFromPctNumeric(input.yieldKpi),
          },
          {
            key: "one-year-pressure",
            label: "1年内到期",
            value: formatYi(input.firstYearPressureYi),
            unit: "亿",
            detail: "按期限桶展示汇总",
          },
          {
            key: "top-counterparty",
            label: "头部占比",
            value: input.topCounterpartyShare || EM_DASH,
            detail: "对手方集中度",
          },
          {
            key: "warnings",
            label: "异常预警",
            value: `${input.warningCount + input.alertCount}条`,
            detail: `${input.warningCount} 关注 · ${input.alertCount} 预警`,
          },
        ]
      : [
          {
            key: "year",
            label: "统计年份",
            value: String(input.selectedYear),
            detail: "月度日均口径",
          },
          {
            key: "month",
            label: "当前月份",
            value: input.selectedMonthLabel ?? EM_DASH,
            detail: "按月选择",
          },
        ];

  const stateSurfaces: LiabilityPageStateSurface[] = [];
  if (isMock) {
    stateSurfaces.push({
      key: "mock",
      variant: "mock",
      title: "当前为演示数据",
      description: "页面可用于交互验证，但不能作为正式负债经营判断。",
    });
  }
  if (hasDateMismatch) {
    stateSurfaces.push({
      key: "date-mismatch",
      variant: "fallback-date",
      title: "请求报告日与返回报告日不一致",
      description: `请求 ${requested}，当前返回 ${resolved}，需要在下钻前确认是否为兜底或最新快照。`,
    });
  }
  if (fallbackCards.length > 0) {
    stateSurfaces.push({
      key: "fallback",
      variant: "fallback-date",
      title: "存在兜底结果",
      description: fallbackCards.map((card) => `${card.title}: ${card.fallbackLabel}`).join("；"),
    });
  }
  if (staleCards.length > 0) {
    stateSurfaces.push({
      key: "stale",
      variant: "stale",
      title: "存在供应商状态异常",
      description: staleCards
        .map((source) => `${source.title}: ${source.meta?.vendor_status ?? EM_DASH}`)
        .join("；"),
    });
  }
  if (input.syntheticSections.length > 0) {
    stateSurfaces.push({
      key: "synthetic-sections",
      variant: "definition-pending",
      title: "合成/预留区块已显式降级",
      description: `${input.syntheticSections.map((section) => section.title).join("、")} 的详情保留在对应区块，不混入首屏正式判断。`,
    });
  }
  if (stateSurfaces.length === 0) {
    stateSurfaces.push({
      key: "ok",
      variant: "neutral",
      title: "状态证据已归集",
      description: "当前可见结果元数据未显示兜底、过期或质量异常。",
    });
  }

  return {
    modeBadge: statusBadges[1],
    reportLine:
      input.activeTab === "daily"
        ? `请求报告日 ${requested} · 当前报告日 ${resolved}`
        : `${input.selectedYear} 年 · ${input.selectedMonthLabel ?? "未选择月份"}（月度日均）`,
    statusBadges,
    kpis,
    evidenceCards: resultMetas,
    stateSurfaces,
  };
}
