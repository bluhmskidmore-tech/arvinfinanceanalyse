import type { ResultMeta } from "../../../api/contracts";
import type { LiabilityYieldKpi } from "../../../api/liabilityAdbContracts";
import {
  EM_DASH,
  buildStateSurfaces,
  fixedOrDash,
  numericRaw,
  type LabeledValue,
  type StateSurfaceItem,
} from "../../../pageModel";

export type LiabilityAnalyticsTabKey = "daily" | "monthly";

export type LiabilityPageBadgeTone = "ok" | "info" | "warning" | "danger" | "mock";

export type LiabilityPageStatusBadge = {
  key: string;
  label: string;
  tone: LiabilityPageBadgeTone;
};

/** KPI band 行与共享 `LabeledValue` 同构，直接采用共享原语。 */
export type LiabilityPageKpi = LabeledValue;

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

/** 状态面条目使用共享 `StateSurfaceItem`（variant 词汇与 PageStateSurface 组件对齐）。 */
export type LiabilityPageStateSurface = StateSurfaceItem;

export type LiabilitySyntheticEvidenceInput = {
  key: string;
  title: string;
  detail: string;
};

export type LiabilityResultMetaInput = {
  key: string;
  title: string;
  required: boolean;
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

function formatBpFromPctNumeric(kpi: LiabilityYieldKpi | null) {
  const nim = numericRaw(kpi?.nim);
  if (nim === null) {
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

function buildMissingEvidenceCard(source: LiabilityResultMetaInput): LiabilityPageEvidenceCard {
  return {
    key: source.key,
    title: source.title,
    resultKind: "结果元数据未透出",
    basisLabel: "兼容端点",
    qualityLabel: "待补状态证据",
    fallbackLabel: "不可判定",
    asOfDate: EM_DASH,
    traceId: EM_DASH,
    sourceVersion: EM_DASH,
    ruleVersion: EM_DASH,
    tone: "warning",
  };
}

export function buildLiabilityAnalyticsPageReadModel(
  input: BuildLiabilityAnalyticsPageReadModelInput,
): LiabilityAnalyticsPageReadModel {
  const requested = input.requestedReportDate || input.resolvedReportDate || EM_DASH;
  const resolved = input.resolvedReportDate || EM_DASH;
  const isMock = input.mode !== "real";
  const hasDateMismatch =
    input.activeTab === "daily" &&
    Boolean(input.requestedReportDate) &&
    Boolean(input.resolvedReportDate) &&
    input.requestedReportDate !== input.resolvedReportDate;
  const resultMetas = input.resultMetas.map(buildEvidenceCard).filter(Boolean) as LiabilityPageEvidenceCard[];
  const missingMetaInputs = input.resultMetas.filter((source) => source.required && !source.meta);
  const evidenceCards = input.resultMetas.flatMap((source) => {
    if (source.meta) {
      const card = buildEvidenceCard(source);
      return card ? [card] : [];
    }
    return source.required ? [buildMissingEvidenceCard(source)] : [];
  });
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
      label:
        input.activeTab === "daily"
          ? hasDateMismatch
            ? `请求 ${requested} · 返回 ${resolved}`
            : `报告日 ${resolved}`
          : `月份 ${input.selectedMonthLabel ?? EM_DASH}`,
      tone: input.activeTab === "daily" && hasDateMismatch ? "warning" : "ok",
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
  if (missingMetaInputs.length > 0) {
    statusBadges.push({
      key: "meta-gap",
      label: `${missingMetaInputs.length} 个核心读面缺少元数据`,
      tone: "warning",
    });
  }

  const kpis: LiabilityPageKpi[] =
    input.activeTab === "daily"
      ? [
          {
            key: "liability-total",
            label: "市场负债",
            value: fixedOrDash(input.liabilityTotalYi, 2),
            unit: "亿",
            // 口径：TYWL 同业对手方总额（不含发行负债）；缺失时回退期限桶合计。
            detail: "同业对手方口径（不含发行负债）；缺失时回退期限桶合计",
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
            value: fixedOrDash(input.firstYearPressureYi, 2),
            unit: "亿",
            // 口径经后端 compute_liability_risk_buckets 确证：同业负债 + 发行负债的
            // 1 年内到期桶合计（含已到期/逾期桶），比「市场负债」的同业对手方口径宽，
            // 因此本格可以大于「市场负债」。
            detail: "同业+发行负债到期合计（含已到期），口径宽于「市场负债」",
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

  const stateSurfaces = buildStateSurfaces(
    [
      {
        when: isMock,
        key: "mock",
        variant: "mock",
        title: "当前为演示数据",
        description: "页面可用于交互验证，但不能作为正式负债经营判断。",
      },
      {
        when: hasDateMismatch,
        key: "date-mismatch",
        variant: "fallback-date",
        title: "请求报告日与返回报告日不一致",
        description: `请求 ${requested}，当前返回 ${resolved}，需要在下钻前确认是否为兜底或最新快照。`,
      },
      {
        when: fallbackCards.length > 0,
        key: "fallback",
        variant: "fallback-date",
        title: "存在兜底结果",
        description: fallbackCards.map((card) => `${card.title}: ${card.fallbackLabel}`).join("；"),
      },
      {
        when: staleCards.length > 0,
        key: "stale",
        variant: "stale",
        title: "存在供应商状态异常",
        description: staleCards
          .map((source) => `${source.title}: ${source.meta?.vendor_status ?? EM_DASH}`)
          .join("；"),
      },
      {
        when: missingMetaInputs.length > 0,
        key: "missing-meta",
        variant: "definition-pending",
        title: "核心读面结果元数据未透出",
        description: missingMetaInputs.map((source) => source.title).join("、"),
      },
      {
        when: input.syntheticSections.length > 0,
        key: "synthetic-sections",
        variant: "definition-pending",
        title: "合成/预留区块已显式降级",
        description: `${input.syntheticSections.map((section) => section.title).join("、")} 已收敛为对应区块的一行说明，不展示示意数据，不混入首屏正式判断。`,
      },
    ],
    {
      emptyFallback: {
        key: "ok",
        variant: "neutral",
        title: "状态证据已归集",
        description: "当前可见结果元数据未显示兜底、过期或质量异常。",
      },
    },
  );

  return {
    modeBadge: statusBadges[1],
    reportLine:
      input.activeTab === "daily"
        ? `请求报告日 ${requested} · 当前报告日 ${resolved}`
        : `${input.selectedYear} 年 · ${input.selectedMonthLabel ?? "未选择月份"}（月度日均）`,
    statusBadges,
    kpis,
    evidenceCards,
    stateSurfaces,
  };
}
