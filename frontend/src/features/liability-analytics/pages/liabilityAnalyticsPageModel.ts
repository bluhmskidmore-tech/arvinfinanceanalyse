import type { LiabilityYieldKpi, ResultMeta } from "../../../api/contracts";

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
  unwrappedEvidenceLabels: string[];
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

const DASH = "—";

function formatYi(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return DASH;
  }
  return value.toFixed(2);
}

function formatBpFromPctNumeric(kpi: LiabilityYieldKpi | null) {
  const nim = kpi?.nim?.raw;
  if (nim === null || nim === undefined || !Number.isFinite(nim)) {
    return DASH;
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
    return "formal 可用";
  }
  if (meta.basis === "formal") {
    return "formal 不可直接使用";
  }
  return `${meta.basis} 读面`;
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
    asOfDate: meta.as_of_date ?? DASH,
    traceId: meta.trace_id || DASH,
    sourceVersion: meta.source_version || DASH,
    ruleVersion: meta.rule_version || DASH,
    tone: toneForMeta(meta),
  };
}

function buildMissingEvidenceCard(key: string, title: string): LiabilityPageEvidenceCard {
  return {
    key,
    title,
    resultKind: "result_meta 未透出",
    basisLabel: "兼容端点",
    qualityLabel: "待补状态证据",
    fallbackLabel: "不可判定",
    asOfDate: DASH,
    traceId: DASH,
    sourceVersion: DASH,
    ruleVersion: DASH,
    tone: "warning",
  };
}

export function buildLiabilityAnalyticsPageReadModel(
  input: BuildLiabilityAnalyticsPageReadModelInput,
): LiabilityAnalyticsPageReadModel {
  const requested = input.requestedReportDate || input.resolvedReportDate || DASH;
  const resolved = input.resolvedReportDate || DASH;
  const isMock = input.mode !== "real";
  const hasDateMismatch =
    Boolean(input.requestedReportDate) &&
    Boolean(input.resolvedReportDate) &&
    input.requestedReportDate !== input.resolvedReportDate;
  const resultMetas = input.resultMetas.map(buildEvidenceCard).filter(Boolean) as LiabilityPageEvidenceCard[];
  const missingEvidenceCards = input.unwrappedEvidenceLabels.map((label, index) =>
    buildMissingEvidenceCard(`unwrapped-${index}`, label),
  );
  const allEvidenceCards = [...resultMetas, ...missingEvidenceCards];
  const fallbackCards = resultMetas.filter((card) => card.fallbackLabel !== "none");
  const staleCards = input.resultMetas.filter(
    (source) => source.meta?.vendor_status === "vendor_stale" || source.meta?.vendor_status === "vendor_unavailable",
  );
  const qualityCards = resultMetas.filter((card) => card.qualityLabel !== "ok");

  const statusBadges: LiabilityPageStatusBadge[] = [
    {
      key: "surface",
      label: "兼容/分析读面",
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
      label: `${fallbackCards.length} 个 fallback`,
      tone: "warning",
    });
  }
  if (staleCards.length > 0) {
    statusBadges.push({
      key: "stale",
      label: `${staleCards.length} 个 stale/vendor 异常`,
      tone: "warning",
    });
  }
  if (qualityCards.length > 0) {
    statusBadges.push({
      key: "quality",
      label: `${qualityCards.length} 个 quality 非 ok`,
      tone: "danger",
    });
  }
  if (missingEvidenceCards.length > 0) {
    statusBadges.push({
      key: "meta-gap",
      label: `${missingEvidenceCards.length} 个兼容端点缺少可见 meta`,
      tone: "warning",
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
            value: input.yieldKpi?.liability_cost?.display ?? DASH,
            detail: "后端收益指标",
          },
          {
            key: "nim",
            label: "NIM",
            value: input.yieldKpi?.nim?.display ?? DASH,
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
            value: input.topCounterpartyShare || DASH,
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
            value: input.selectedMonthLabel ?? DASH,
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
      description: `请求 ${requested}，当前返回 ${resolved}，需要在下钻前确认是否为 fallback/latest snapshot。`,
    });
  }
  if (fallbackCards.length > 0) {
    stateSurfaces.push({
      key: "fallback",
      variant: "fallback-date",
      title: "存在 fallback 结果",
      description: fallbackCards.map((card) => `${card.title}: ${card.fallbackLabel}`).join("；"),
    });
  }
  if (staleCards.length > 0) {
    stateSurfaces.push({
      key: "stale",
      variant: "stale",
      title: "存在 stale/vendor 异常",
      description: staleCards
        .map((source) => `${source.title}: ${source.meta?.vendor_status ?? DASH}`)
        .join("；"),
    });
  }
  if (missingEvidenceCards.length > 0) {
    stateSurfaces.push({
      key: "missing-meta",
      variant: "definition-pending",
      title: "兼容端点 result_meta 尚未透出",
      description: input.unwrappedEvidenceLabels.join("、"),
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
      description: "当前可见 result_meta 未显示 fallback、stale 或质量异常。",
    });
  }

  return {
    modeBadge: statusBadges[1],
    reportLine:
      input.activeTab === "daily"
        ? `请求报告日 ${requested} · 当前报告日 ${resolved}`
        : `${input.selectedYear} 年 · ${input.selectedMonthLabel ?? "未选择月份"} · 月度日均`,
    statusBadges,
    kpis,
    evidenceCards: allEvidenceCards,
    stateSurfaces,
  };
}
