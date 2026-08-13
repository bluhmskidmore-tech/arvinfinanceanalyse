import { useQuery } from "@tanstack/react-query";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";

import { useApiClient } from "../../../api/client";
import type {
  LedgerPnlCandidateFinancialIndicatorAccountLineage,
  LedgerPnlCandidateFinancialIndicatorLineage,
  LedgerPnlCandidateFinancialIndicatorMetric,
  LedgerPnlCandidateFinancialIndicatorGap,
  LedgerPnlCandidateFinancialIndicatorPromotionReadiness,
  LedgerPnlCandidateFinancialIndicatorRevalidationReceipt,
  LedgerPnlCandidateFinancialIndicatorRevalidationRequest,
  LedgerPnlCandidateFinancialIndicatorsPayload,
  LedgerPnlCandidateFinancialIndicatorSource,
  LedgerPnlCandidateFinancialIndicatorValidation,
  LedgerPnlCandidatePromotionEvidencePack,
  LedgerPnlCandidatePromotionOwnerRequirement,
  LedgerPnlCandidateRequirementResolution,
  LedgerPnlCandidateRequirementResolutionItem,
  LedgerPnlCandidateSourceVersionImpact,
} from "../../../api/contracts";
import { LedgerPnlCandidatePeriodComparison } from "./LedgerPnlCandidatePeriodComparison";
import "./LedgerPnlCandidateFinancialIndicatorsPanel.css";

type Props = {
  reportMonth: string;
  currency?: "CNX" | "CNY";
  /** 视口门控：false 时不发起候选指标查询（区块尚未进入视口）。默认 true。 */
  enabled?: boolean;
};

const INCOME_METRIC_IDS = [
  "income.interest.net",
  "income.noninterest.total",
  "income.operating.mother_bank",
] as const;

const SCALE_METRIC_IDS = [
  "balance.deposit.corporate.total::point",
  "balance.deposit.retail.total::point",
  "balance.loan.corporate.total::point",
  "balance.loan.retail.total::point",
] as const;

const STATUS_LABELS: Record<LedgerPnlCandidateFinancialIndicatorMetric["status"], string> = {
  ok: "通过",
  warning: "警告",
  manual_default: "手工默认",
  error: "错误",
};

const PROMOTION_CHECK_STATUS_LABELS = {
  passed: "通过",
  blocked: "阻断",
  not_evaluated: "未执行",
} as const;

const PROMOTION_CHECK_IDS = [
  "rule_asset",
  "source_evidence",
  "validation_controls",
  "manual_inputs",
  "account_coverage",
  "formal_contract",
] as const;

const SUPPORTED_RULE_VERSIONS = new Set([
  "qdb-finance-2026-v1.0.0",
  "qdb-finance-2026-v1.0.1",
]);

type PromotionOwnerRequirementCategory = LedgerPnlCandidatePromotionOwnerRequirement["category"];
type PromotionOwnerRequirementFilter = "all" | PromotionOwnerRequirementCategory;

const PROMOTION_REQUIREMENT_CATEGORIES: ReadonlyArray<{
  category: PromotionOwnerRequirementCategory;
  label: string;
}> = [
  { category: "source_evidence", label: "来源证据" },
  { category: "validation_control", label: "控制校验" },
  { category: "manual_input", label: "手工输入" },
  { category: "account_coverage", label: "科目覆盖" },
  { category: "formal_contract", label: "正式契约" },
  { category: "business_owner_approval", label: "负责人复核" },
];

const CLIPBOARD_FEEDBACK_TIMEOUT_MS = 1500;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;

const REQUIREMENT_RESOLUTION_LABELS = {
  awaiting_owner_input: "待补",
  evidence_received: "已补·待证据核验",
  validation_failed: "校验失败",
  verified: "已核验·非正式",
} as const;

function isRequirementResolutionContract(
  resolution: LedgerPnlCandidateRequirementResolution,
  basePack: LedgerPnlCandidatePromotionEvidencePack,
  resultPackKey: string,
) {
  const baseIds = basePack.owner_requirements.map((item) => item.requirement_id);
  const resolutionIds = resolution.requirements.map((item) => item.requirement_id);
  const validStatuses = new Set(Object.keys(REQUIREMENT_RESOLUTION_LABELS));
  return resolution.contract_version === "candidate-promotion-resolution-v1"
    && SHA256_PATTERN.test(resolution.resolution_key)
    && resolution.base_evidence_pack_key === basePack.evidence_pack_key
    && resolution.result_evidence_pack_key === resultPackKey
    && JSON.stringify(resolution.base_requirement_ids) === JSON.stringify(baseIds)
    && JSON.stringify(resolutionIds) === JSON.stringify(baseIds)
    && resolution.requirements.every((item) => (
      validStatuses.has(item.status)
      && typeof item.status_detail === "string"
      && item.status_detail.trim().length > 0
      && Array.isArray(item.submitted_evidence_refs)
      && item.submitted_evidence_refs.every((ref) => typeof ref === "string" && ref.trim().length > 0)
      && Array.isArray(item.validation_evidence_refs)
      && item.validation_evidence_refs.every((ref) => typeof ref === "string" && ref.trim().length > 0)
    ));
}

function parseManualOverrides(value: string) {
  const parsed: unknown = JSON.parse(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("manual_overrides 必须是 JSON 对象。");
  }
  for (const [metricId, rawOverride] of Object.entries(parsed)) {
    if (!/^[a-z0-9][a-z0-9_.]*(?:::(?:point|ytd_average|month_average))?$/.test(metricId)) {
      throw new Error(`无效的手工指标编号：${metricId}`);
    }
    if (!rawOverride || typeof rawOverride !== "object" || Array.isArray(rawOverride)) {
      throw new Error(`${metricId} 的覆盖项必须是对象。`);
    }
    const override = rawOverride as Record<string, unknown>;
    if (
      Object.keys(override).sort().join(",") !== "submitted_evidence_refs,value_yi"
      || typeof override.value_yi !== "string"
      || !/^-?\d+(?:\.\d+)?$/.test(override.value_yi)
      || !Array.isArray(override.submitted_evidence_refs)
      || override.submitted_evidence_refs.length === 0
      || !override.submitted_evidence_refs.every(
        (ref) => typeof ref === "string" && ref.trim().length > 0,
      )
    ) {
      throw new Error(`${metricId} 必须包含十进制字符串 value_yi 和非空 submitted_evidence_refs。`);
    }
  }
  return parsed as LedgerPnlCandidateFinancialIndicatorRevalidationRequest["manual_overrides"];
}

async function isRevalidationReceiptContract(
  receipt: LedgerPnlCandidateFinancialIndicatorRevalidationReceipt,
  basePayload: LedgerPnlCandidateFinancialIndicatorsPayload,
  expectedManualOverrideCount: number,
) {
  const basePack = basePayload.promotion_readiness.evidence_pack;
  const resultPayload = receipt.result?.result;
  if (
    receipt.contract_version !== "candidate-financial-indicator-revalidation-v1"
    || receipt.revalidation_effect !== "none"
    || receipt.persisted !== false
    || receipt.formal_use_allowed !== false
    || receipt.base_candidate_idempotency_key !== basePayload.idempotency_key
    || receipt.base_evidence_pack_key !== basePack.evidence_pack_key
    || !Number.isInteger(receipt.manual_override_count)
    || receipt.manual_override_count !== expectedManualOverrideCount
    || !resultPayload
    || !isPromotionReadinessContract(resultPayload.promotion_readiness, resultPayload)
  ) return false;
  return isRequirementResolutionContract(
    receipt.requirement_resolution,
    basePack,
    resultPayload.promotion_readiness.evidence_pack.evidence_pack_key,
  ) && await hasValidRequirementResolutionKey(receipt.requirement_resolution);
}

function canonicalizeJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalizeJson);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0)
      .map(([key, item]) => [key, canonicalizeJson(item)]),
  );
}

async function hasValidRequirementResolutionKey(
  resolution: LedgerPnlCandidateRequirementResolution,
) {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return false;
  const { resolution_key: expectedKey, ...keyPayload } = resolution;
  try {
    const canonicalBytes = new TextEncoder().encode(
      JSON.stringify(canonicalizeJson(keyPayload)),
    );
    const digest = await subtle.digest("SHA-256", canonicalBytes);
    const actualKey = Array.from(new Uint8Array(digest), (byte) => (
      byte.toString(16).padStart(2, "0")
    )).join("");
    return actualKey === expectedKey;
  } catch {
    return false;
  }
}

function isPromotionReadinessContract(
  value: unknown,
  payload: LedgerPnlCandidateFinancialIndicatorsPayload,
): value is LedgerPnlCandidateFinancialIndicatorPromotionReadiness {
  if (!value || typeof value !== "object") return false;
  const readiness = value as Record<string, unknown>;
  if (
    readiness.readiness_contract_version !== "promotion-readiness-v1"
    || typeof readiness.readiness_evidence_key !== "string"
    || !/^[0-9a-f]{64}$/.test(readiness.readiness_evidence_key)
    || (readiness.status !== "blocked" && readiness.status !== "review_required")
    || !Number.isInteger(readiness.blocking_count)
    || Number(readiness.blocking_count) < 0
    || Number(readiness.blocking_count) > PROMOTION_CHECK_IDS.length
    || readiness.check_total !== PROMOTION_CHECK_IDS.length
    || typeof readiness.candidate_idempotency_key !== "string"
    || !/^[0-9a-f]{64}$/.test(readiness.candidate_idempotency_key)
    || readiness.candidate_idempotency_key !== payload.idempotency_key
    || !["missing_contract", "contract_fixture", "unavailable"].includes(
      String(readiness.formal_contract_status),
    )
    || readiness.formal_use_allowed !== false
    || readiness.owner_approval_required !== true
    || typeof readiness.next_action !== "string"
    || readiness.next_action.trim().length === 0
    || !Array.isArray(readiness.checks)
    || readiness.checks.length !== PROMOTION_CHECK_IDS.length
  ) {
    return false;
  }
  const checksValid = readiness.checks.every((check, index) => {
    if (!check || typeof check !== "object") return false;
    const item = check as Record<string, unknown>;
    const statusValid = item.status === "passed"
      || item.status === "blocked"
      || item.status === "not_evaluated";
    return item.check_id === PROMOTION_CHECK_IDS[index]
      && statusValid
      && typeof item.blocking === "boolean"
      && item.blocking === (item.status !== "passed")
      && typeof item.label === "string"
      && item.label.trim().length > 0
      && typeof item.summary === "string"
      && item.summary.trim().length > 0
      && typeof item.action === "string"
      && item.action.trim().length > 0
      && Array.isArray(item.evidence_refs)
      && item.evidence_refs.every((ref) => typeof ref === "string");
  });
  if (!checksValid) return false;
  const blockingCount = readiness.checks.filter((check) => check.blocking).length;
  if (
    readiness.blocking_count !== blockingCount
    || (readiness.status === "blocked") !== (blockingCount > 0)
  ) {
    return false;
  }
  const pack = readiness.evidence_pack;
  if (!pack || typeof pack !== "object") return false;
  const evidencePack = pack as Record<string, unknown>;
  if (
    evidencePack.contract_version !== "candidate-promotion-evidence-v1"
    || typeof evidencePack.evidence_pack_key !== "string"
    || !/^[0-9a-f]{64}$/.test(evidencePack.evidence_pack_key)
    || typeof evidencePack.report_month !== "string"
    || !/^\d{6}$/.test(evidencePack.report_month)
    || typeof evidencePack.report_date !== "string"
    || !SUPPORTED_RULE_VERSIONS.has(String(evidencePack.rule_version))
    || typeof evidencePack.rule_hash !== "string"
    || !/^[0-9a-f]{64}$/.test(evidencePack.rule_hash)
    || typeof evidencePack.source_version !== "string"
    || !["matched", "mismatch", "not_applicable", "incomplete"].includes(
      String(evidencePack.source_alignment),
    )
    || evidencePack.report_month !== payload.report_month
    || evidencePack.report_date !== payload.report_date
    || evidencePack.rule_version !== payload.rule_version
    || evidencePack.rule_hash !== payload.rule_hash
    || evidencePack.source_version !== payload.source_version
    || evidencePack.source_alignment !== payload.source_alignment
    || evidencePack.candidate_idempotency_key !== readiness.candidate_idempotency_key
    || evidencePack.readiness_contract_version !== readiness.readiness_contract_version
    || evidencePack.readiness_evidence_key !== readiness.readiness_evidence_key
    || evidencePack.metric_status !== "candidate"
    || evidencePack.formal_use_allowed !== false
    || evidencePack.owner_approval_required !== true
    || evidencePack.contains_metric_values !== false
    || evidencePack.contains_formal_values !== false
    || evidencePack.certification_effect !== "none"
    || evidencePack.blocking_count !== readiness.blocking_count
    || evidencePack.check_total !== readiness.check_total
    || evidencePack.formal_contract_status !== readiness.formal_contract_status
    || typeof evidencePack.formal_sample_id !== "string"
    || evidencePack.formal_sample_id.trim().length === 0
    || typeof evidencePack.formal_source_version !== "string"
    || evidencePack.formal_source_version.trim().length === 0
    || !(
      evidencePack.formal_release_gate_status === null
      || typeof evidencePack.formal_release_gate_status === "string"
    )
    || !Number.isInteger(evidencePack.formal_metric_count)
    || Number(evidencePack.formal_metric_count) < 0
    || !Array.isArray(evidencePack.checks)
    || JSON.stringify(evidencePack.checks) !== JSON.stringify(readiness.checks)
    || !Number.isInteger(evidencePack.owner_requirement_count)
    || Number(evidencePack.owner_requirement_count) < 1
    || !Array.isArray(evidencePack.owner_requirements)
    || evidencePack.owner_requirement_count !== evidencePack.owner_requirements.length
  ) {
    return false;
  }
  const requirementIds = new Set<string>();
  const validCategories = new Set([
    "source_evidence",
    "validation_control",
    "manual_input",
    "account_coverage",
    "formal_contract",
    "business_owner_approval",
  ]);
  const requirementsValid = evidencePack.owner_requirements.every((requirement) => {
    if (!requirement || typeof requirement !== "object") return false;
    const item = requirement as Record<string, unknown>;
    if (
      typeof item.requirement_id !== "string"
      || !/^[a-z][a-z0-9_.-]*$/.test(item.requirement_id)
      || requirementIds.has(item.requirement_id)
    ) return false;
    requirementIds.add(item.requirement_id);
    return validCategories.has(String(item.category))
      && item.status === "awaiting_owner_input"
      && item.submitted_value === null
      && Array.isArray(item.evidence_refs)
      && item.evidence_refs.every((ref) => typeof ref === "string")
      && Array.isArray(item.required_evidence)
      && item.required_evidence.length > 0
      && item.required_evidence.every((ref) => typeof ref === "string")
      && typeof item.action === "string"
      && item.action.trim().length > 0;
  });
  return requirementsValid
    && (
      (evidencePack.outcome_status === "blocked" && blockingCount > 0)
      || (evidencePack.outcome_status === "awaiting_owner_approval" && blockingCount === 0)
    );
}

function isSourceVersionImpactContract(
  value: unknown,
  payload: LedgerPnlCandidateFinancialIndicatorsPayload,
): value is LedgerPnlCandidateSourceVersionImpact {
  if (!value || typeof value !== "object") return false;
  const impact = value as Record<string, unknown>;
  const hashFields = [
    "impact_asset_sha256",
    "reference_result_sha256",
    "reference_ledger_sha256",
    "current_ledger_sha256",
    "daily_sha256",
    "reference_numeric_digest",
    "current_numeric_digest",
  ];
  if (
    impact.contract_version !== "candidate-source-version-impact-v1"
    || impact.comparison_basis !== "canonical_decimal_value"
    || impact.report_month !== payload.report_month
    || impact.reference_rule_version !== "qdb-finance-2026-v1.0.0"
    || impact.current_rule_version !== "qdb-finance-2026-v1.0.1"
    || impact.current_rule_version !== payload.rule_version
    || impact.metric_total !== 186
    || !Number.isInteger(impact.compared_metric_count)
    || Number(impact.compared_metric_count) < 0
    || Number(impact.compared_metric_count) > 186
    || !(
      impact.numeric_changed_count === null
      || (
        Number.isInteger(impact.numeric_changed_count)
        && Number(impact.numeric_changed_count) >= 0
        && Number(impact.numeric_changed_count) <= 186
      )
    )
    || !Number.isInteger(impact.serialization_only_count)
    || Number(impact.serialization_only_count) < 0
    || Number(impact.serialization_only_count) > 186
    || !Array.isArray(impact.serialization_only_metric_ids)
    || impact.serialization_only_count !== impact.serialization_only_metric_ids.length
    || impact.formal_use_allowed !== false
    || impact.certification_effect !== "none"
    || !hashFields.every((field) => (
      typeof impact[field] === "string" && SHA256_PATTERN.test(impact[field] as string)
    ))
  ) return false;

  const metricIds = impact.serialization_only_metric_ids;
  if (
    metricIds.some((metricId) => typeof metricId !== "string" || metricId.trim().length === 0)
    || new Set(metricIds).size !== metricIds.length
  ) return false;

  if (impact.status === "numerically_unchanged") {
    return impact.compared_metric_count === 186
      && impact.numeric_changed_count === 0
      && impact.current_numeric_digest === impact.reference_numeric_digest;
  }
  if (impact.status === "numeric_digest_mismatch") {
    return impact.compared_metric_count === 186
      && impact.numeric_changed_count === null
      && impact.current_numeric_digest !== impact.reference_numeric_digest
      && impact.serialization_only_count === 0;
  }
  if (impact.status === "comparison_incomplete") {
    return Number(impact.compared_metric_count) < 186
      && impact.numeric_changed_count === null
      && impact.serialization_only_count === 0;
  }
  return false;
}

const BASIS_LABELS: Record<LedgerPnlCandidateFinancialIndicatorMetric["basis"], string> = {
  point: "时点余额",
  ytd_average: "年日均",
  month_average: "月日均",
  cumulative: "累计值",
};

const ALIGNMENT_LABELS = {
  matched: "锁定样本匹配",
  mismatch: "锁定样本不一致",
  not_applicable: "未配置锁定样本",
  incomplete: "来源不完整",
} as const;

const GAP_KIND_LABELS: Record<LedgerPnlCandidateFinancialIndicatorGap["kind"], string> = {
  source_missing: "来源缺失",
  source_hash: "来源哈希",
  source_parse: "来源解析",
  validation: "规则校验",
  missing_account: "科目缺失",
  manual_input: "手工输入",
  calculation: "计算错误",
};

const LINEAGE_SOURCE_LABELS: Record<
  LedgerPnlCandidateFinancialIndicatorAccountLineage["source"],
  string
> = {
  main: "主表",
  microloan: "微贷",
  ledger: "总账累计",
  microloan_ledger: "微贷总账累计",
};

const LINEAGE_LEVEL_LABELS: Record<
  LedgerPnlCandidateFinancialIndicatorAccountLineage["level"],
  string
> = {
  l1: "一级科目",
  l2: "二级科目",
  l3: "三级科目",
  full: "完整科目",
};

function sourceKindLabel(source: LedgerPnlCandidateFinancialIndicatorSource) {
  return source.source_kind === "ledger" ? "总账" : "日均";
}

function readableError(error: unknown) {
  return error instanceof Error ? error.message : "候选指标读取失败";
}

function sourceLockLabel(source: LedgerPnlCandidateFinancialIndicatorSource) {
  if (!source.exists) return "源文件缺失";
  if (source.locked_sha256 === null) return "未配置锁定样本";
  if (source.locked_hash_match === true) return "锁定版本匹配";
  if (source.locked_hash_match === false) return "锁定版本不匹配";
  return "暂时无法比较锁定样本";
}

function SourceEvidenceCard({ source }: { source: LedgerPnlCandidateFinancialIndicatorSource }) {
  return (
    <article>
      <div>
        <strong>{sourceKindLabel(source)}</strong>
        <span data-match={String(source.locked_hash_match)}>{sourceLockLabel(source)}</span>
      </div>
      <p>{source.file_name}</p>
      {source.periods.map((period) => (
        <small key={period.evidence_id}>
          <code>{period.evidence_id}</code>: {period.start}—{period.end} · {period.source_cell}
        </small>
      ))}
    </article>
  );
}

function GapEvidenceCard({ gap }: { gap: LedgerPnlCandidateFinancialIndicatorGap }) {
  return (
    <article data-severity={gap.severity}>
      <div>
        <strong>{gap.title}</strong>
        <span>{GAP_KIND_LABELS[gap.kind]} · <code>{gap.kind}</code></span>
      </div>
      <p>{gap.detail}</p>
      {gap.metric_ids.length > 0 ? (
        <small>
          影响指标 {gap.metric_ids.join(" · ")}
        </small>
      ) : null}
    </article>
  );
}

function downloadPromotionEvidencePack(pack: LedgerPnlCandidatePromotionEvidencePack) {
  const content = JSON.stringify(pack, null, 2);
  const blob = new Blob([content], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = [
    "ledger-pnl-candidate-promotion-evidence",
    pack.report_month,
    pack.evidence_pack_key.slice(0, 12),
  ].join("-") + ".json";
  anchor.click();
  URL.revokeObjectURL(url);
}

function promotionRequirementCopyText(
  pack: LedgerPnlCandidatePromotionEvidencePack,
  requirements: LedgerPnlCandidatePromotionOwnerRequirement[],
  resolutionById?: ReadonlyMap<string, LedgerPnlCandidateRequirementResolutionItem>,
) {
  const categoryLabels = new Map(
    PROMOTION_REQUIREMENT_CATEGORIES.map(({ category, label }) => [category, label]),
  );
  return [
    "候选财务指标待补证据清单",
    `报告期：${pack.report_month} / ${pack.report_date}`,
    `证据包键：${pack.evidence_pack_key}`,
    ...requirements.flatMap((requirement, index) => {
      const resolution = resolutionById?.get(requirement.requirement_id);
      return [
        "",
        `${index + 1}. ${categoryLabels.get(requirement.category)}`,
        `要求编号：${requirement.requirement_id}`,
        `状态：${resolution ? REQUIREMENT_RESOLUTION_LABELS[resolution.status] : "待负责人补充"}`,
        `处理动作：${requirement.action}`,
        `需补材料：${requirement.required_evidence.join("；")}`,
        `证据引用：${requirement.evidence_refs.join("；") || "暂无引用"}`,
        ...(resolution ? [
          `提交证据：${resolution.submitted_evidence_refs.join("；") || "暂无引用"}`,
          `校验证据：${resolution.validation_evidence_refs.join("；") || "暂无引用"}`,
        ] : []),
      ];
    }),
  ].join("\n");
}

function PromotionEvidenceWorklist({
  pack,
  resolution,
  resultEvidencePackKey,
}: {
  pack: LedgerPnlCandidatePromotionEvidencePack;
  resolution?: LedgerPnlCandidateRequirementResolution;
  resultEvidencePackKey?: string;
}) {
  const [activeCategory, setActiveCategory] = useState<PromotionOwnerRequirementFilter>("all");
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const [copyPending, setCopyPending] = useState(false);
  const copyRequestRef = useRef(0);
  const mountedRef = useRef(true);
  const resolutionValid = resolution === undefined || (
    typeof resultEvidencePackKey === "string"
    && isRequirementResolutionContract(resolution, pack, resultEvidencePackKey)
  );
  const resolutionById = new Map(
    resolutionValid && resolution
      ? resolution.requirements.map((item) => [item.requirement_id, item] as const)
      : [],
  );

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      copyRequestRef.current += 1;
    };
  }, []);
  const categoryCounts = new Map(
    PROMOTION_REQUIREMENT_CATEGORIES.map(({ category }) => [
      category,
      pack.owner_requirements.filter((item) => item.category === category).length,
    ]),
  );
  const visibleRequirements = activeCategory === "all"
    ? pack.owner_requirements
    : pack.owner_requirements.filter((item) => item.category === activeCategory);
  const visibleGroups = PROMOTION_REQUIREMENT_CATEGORIES.map(({ category, label }) => ({
    category,
    label,
    requirements: visibleRequirements.filter((item) => item.category === category),
  })).filter((group) => group.requirements.length > 0);

  const selectCategory = (category: PromotionOwnerRequirementFilter) => {
    copyRequestRef.current += 1;
    setActiveCategory(category);
    setCopyFeedback(null);
  };

  const copyVisibleRequirements = async () => {
    if (copyPending) return;
    const requestId = copyRequestRef.current + 1;
    copyRequestRef.current = requestId;
    setCopyFeedback(null);
    setCopyPending(true);
    const clipboard = typeof navigator === "undefined" ? undefined : navigator.clipboard;
    if (!clipboard?.writeText) {
      setCopyFeedback("复制失败，请下载阻断证据 JSON");
      setCopyPending(false);
      return;
    }
    try {
      let timeoutId: ReturnType<typeof setTimeout> | undefined;
      const timeout = new Promise<never>((_resolve, reject) => {
        timeoutId = setTimeout(
          () => reject(new Error("clipboard request timed out")),
          CLIPBOARD_FEEDBACK_TIMEOUT_MS,
        );
      });
      try {
        await Promise.race([
          clipboard.writeText(promotionRequirementCopyText(
            pack,
            visibleRequirements,
            resolutionById,
          )),
          timeout,
        ]);
      } finally {
        if (timeoutId !== undefined) clearTimeout(timeoutId);
      }
      if (mountedRef.current && copyRequestRef.current === requestId) {
        setCopyFeedback(`已复制 ${visibleRequirements.length} 项待补要求`);
      }
    } catch {
      if (mountedRef.current && copyRequestRef.current === requestId) {
        setCopyFeedback("复制失败，请下载阻断证据 JSON");
      }
    } finally {
      if (mountedRef.current) setCopyPending(false);
    }
  };

  if (!resolutionValid) {
    return (
      <section className="candidate-indicators__worklist candidate-indicators__worklist--error" role="alert">
        <strong>核验回执契约错误</strong>
        <span>要求编号或证据包绑定不完整，已停止展示本次核验状态。</span>
      </section>
    );
  }

  const statusCounts = resolution
    ? Object.keys(REQUIREMENT_RESOLUTION_LABELS).map((status) => ({
      status: status as keyof typeof REQUIREMENT_RESOLUTION_LABELS,
      count: resolution.requirements.filter((item) => item.status === status).length,
    }))
    : [];

  return (
    <section
      className="candidate-indicators__worklist"
      aria-labelledby="candidate-promotion-worklist-title"
    >
      <div className="candidate-indicators__worklist-heading">
        <div>
          <span>材料交接</span>
          <h4 id="candidate-promotion-worklist-title">待补证据清单</h4>
        </div>
        <strong>显示 {visibleRequirements.length} / {pack.owner_requirement_count} 项</strong>
      </div>
      {resolution ? (
        <p className="candidate-indicators__worklist-status-counts" aria-label="本次核验状态计数">
          {statusCounts.map(({ status, count }) => (
            <span key={status}>{REQUIREMENT_RESOLUTION_LABELS[status]} {count}</span>
          ))}
        </p>
      ) : null}
      <div className="candidate-indicators__worklist-toolbar">
        <div
          className="candidate-indicators__worklist-filters"
          role="group"
          aria-label="筛选待补证据类别"
        >
          <button
            type="button"
            aria-pressed={activeCategory === "all"}
            onClick={() => selectCategory("all")}
          >
            全部 <b>{pack.owner_requirement_count}</b>
          </button>
          {PROMOTION_REQUIREMENT_CATEGORIES.map(({ category, label }) => (
            <button
              key={category}
              type="button"
              aria-pressed={activeCategory === category}
              onClick={() => selectCategory(category)}
            >
              {label} <b>{categoryCounts.get(category) ?? 0}</b>
            </button>
          ))}
        </div>
        <button
          type="button"
          className="candidate-indicators__worklist-copy"
          aria-busy={copyPending}
          disabled={copyPending || visibleRequirements.length === 0}
          onClick={() => void copyVisibleRequirements()}
        >
          复制当前清单
        </button>
      </div>
      {copyFeedback ? (
        <p className="candidate-indicators__worklist-feedback" role="status" aria-label="复制状态">
          {copyFeedback}
        </p>
      ) : null}
      {visibleGroups.length > 0 ? (
        <div className="candidate-indicators__worklist-groups">
          {visibleGroups.map(({ category, label, requirements }) => (
            <details
              key={`${activeCategory}-${category}`}
              open={activeCategory !== "all" || requirements.length <= 1}
              data-testid={`candidate-promotion-requirement-group-${category}`}
            >
              <summary>
                <span role="heading" aria-level={5}>{label}</span>
                <b>{requirements.length}</b>
              </summary>
              <div className="candidate-indicators__worklist-items">
                {requirements.map((requirement) => (
                  <article
                    key={requirement.requirement_id}
                    data-category={requirement.category}
                    data-testid="candidate-promotion-owner-requirement"
                  >
                    <header>
                      <code>{requirement.requirement_id}</code>
                      <span data-status={resolutionById.get(requirement.requirement_id)?.status}>
                        {resolutionById.has(requirement.requirement_id)
                          ? REQUIREMENT_RESOLUTION_LABELS[
                            resolutionById.get(requirement.requirement_id)!.status
                          ]
                          : "待负责人补充"}
                      </span>
                    </header>
                    <p>{requirement.action}</p>
                    <dl>
                      <div>
                        <dt>需补材料</dt>
                        <dd>{requirement.required_evidence.join("；")}</dd>
                      </div>
                      <div>
                        <dt>证据引用</dt>
                        <dd>{requirement.evidence_refs.join("；") || "暂无引用"}</dd>
                      </div>
                      {resolutionById.has(requirement.requirement_id) ? (
                        <>
                          <div>
                            <dt>提交证据</dt>
                            <dd>{resolutionById.get(requirement.requirement_id)!.submitted_evidence_refs.join("；") || "暂无引用"}</dd>
                          </div>
                          <div>
                            <dt>校验证据</dt>
                            <dd>{resolutionById.get(requirement.requirement_id)!.validation_evidence_refs.join("；") || "暂无引用"}</dd>
                          </div>
                        </>
                      ) : null}
                    </dl>
                  </article>
                ))}
              </div>
            </details>
          ))}
        </div>
      ) : (
        <p className="candidate-indicators__worklist-empty">当前类别没有待补项。</p>
      )}
      <small>清单只用于材料交接；筛选和复制不会修改后端状态，也不会产生审批或正式化效果。</small>
    </section>
  );
}

function PromotionReadinessPanel({
  readiness,
  baseEvidencePack,
  resolution,
}: {
  readiness: LedgerPnlCandidateFinancialIndicatorPromotionReadiness;
  baseEvidencePack?: LedgerPnlCandidatePromotionEvidencePack;
  resolution?: LedgerPnlCandidateRequirementResolution;
}) {
  return (
    <section
      className="candidate-indicators__promotion"
      data-status={readiness.status}
      data-testid="candidate-financial-indicators-promotion-readiness"
      aria-labelledby="candidate-promotion-title"
    >
      <div className="candidate-indicators__promotion-heading">
        <div>
          <span>正式化门禁</span>
          <h3 id="candidate-promotion-title">正式化就绪清单</h3>
        </div>
        <div className="candidate-indicators__promotion-actions">
          <strong>
            {readiness.status === "blocked"
              ? `正式化未就绪 · ${readiness.blocking_count} 项阻断`
              : "技术门禁已通过 · 待业务复核"}
          </strong>
          <button
            type="button"
            onClick={() => downloadPromotionEvidencePack(readiness.evidence_pack)}
          >
            下载阻断证据 JSON
          </button>
        </div>
      </div>
      <p>{readiness.next_action}</p>
      <div className="candidate-indicators__promotion-grid">
        {readiness.checks.map((check) => (
          <article key={check.check_id} data-status={check.status}>
            <div>
              <strong>{check.label}</strong>
              <em>{PROMOTION_CHECK_STATUS_LABELS[check.status]}</em>
            </div>
            <p>{check.summary}</p>
            <small>{check.action}</small>
            {check.evidence_refs.length > 0 ? (
              <details>
                <summary>查看证据引用（{check.evidence_refs.length}）</summary>
                <ul>
                  {check.evidence_refs.map((ref) => <li key={ref}><code>{ref}</code></li>)}
                </ul>
              </details>
            ) : null}
          </article>
        ))}
      </div>
      <PromotionEvidenceWorklist
        key={`${readiness.evidence_pack.evidence_pack_key}:${resolution?.resolution_key ?? "base"}`}
        pack={baseEvidencePack ?? readiness.evidence_pack}
        resolution={resolution}
        resultEvidencePackKey={readiness.evidence_pack.evidence_pack_key}
      />
      <div className="candidate-indicators__promotion-evidence">
        <small><span>候选幂等键</span> <code>{readiness.candidate_idempotency_key}</code></small>
        <small><span>就绪证据键</span> <code>{readiness.readiness_evidence_key}</code></small>
        <small>业务负责人审批仍为必需，正式使用保持关闭。</small>
      </div>
    </section>
  );
}

function ValidationEvidenceCard({
  validation,
}: {
  validation: LedgerPnlCandidateFinancialIndicatorValidation;
}) {
  return (
    <article data-severity={validation.severity}>
      <div>
        <code>{validation.validation_id}</code>
        <span>{validation.severity === "error" ? "错误" : "警告"} · {validation.severity}</span>
      </div>
      <p>{validation.message}</p>
      {validation.delta_yi !== null ? <small>差额 {validation.delta_yi} 亿元</small> : null}
      {validation.sample.length > 0 ? <small>样本 {validation.sample.join(" · ")}</small> : null}
    </article>
  );
}

function MetricValue({ metric }: { metric: LedgerPnlCandidateFinancialIndicatorMetric | undefined }) {
  return (
    <>
      <strong>{metric?.value ?? "—"}</strong>
      <span>{metric?.value === null || metric === undefined ? "" : metric.unit}</span>
    </>
  );
}

function LineageEvidence({ lineage }: { lineage: LedgerPnlCandidateFinancialIndicatorLineage }) {
  if (lineage.lineage_type === "account") {
    return (
      <article className="candidate-indicators__lineage-row">
        <div>
          <span>科目证据</span>
          <code>{lineage.code}</code>
        </div>
        <p>
          {LINEAGE_SOURCE_LABELS[lineage.source]}、{lineage.basis ? BASIS_LABELS[lineage.basis] : "无期间口径"}、{LINEAGE_LEVEL_LABELS[lineage.level]}
        </p>
        <small>
          原始口径 <code>{lineage.source}</code> / <code>{lineage.basis ?? "none"}</code> / <code>{lineage.level}</code>
        </small>
        <dl>
          <div><dt>权重</dt><dd>{lineage.weight}</dd></div>
          <div><dt>原始金额（元）</dt><dd>{lineage.raw_yuan}</dd></div>
          <div><dt>贡献</dt><dd>{lineage.contribution_yi} 亿元</dd></div>
        </dl>
        <p>{lineage.observed ? "源表已观测" : "源表未观测 / 候选按 0 代入"}</p>
        <small>{lineage.evidence_refs.join(" · ")}</small>
      </article>
    );
  }
  if (lineage.lineage_type === "metric") {
    return (
      <article className="candidate-indicators__lineage-row">
        <div>
          <span>指标依赖</span>
          <code>{lineage.metric_id}</code>
        </div>
        <p>状态 {STATUS_LABELS[lineage.dependency_status]} · 权重 {lineage.weight}</p>
        <dl>
          <div><dt>依赖值</dt><dd>{lineage.metric_value_yi === null ? "—" : `${lineage.metric_value_yi} 亿元`}</dd></div>
          <div><dt>贡献</dt><dd>{lineage.contribution_yi === null ? "—" : `${lineage.contribution_yi} 亿元`}</dd></div>
        </dl>
      </article>
    );
  }
  return (
    <article className="candidate-indicators__lineage-row">
      <div>
        <span>手工输入</span>
        <strong>{lineage.supplied ? "已提供" : "未提供"}</strong>
      </div>
      <p>规则当前值 {lineage.value_yi} 亿元</p>
    </article>
  );
}

function CandidateRevalidationPanel({
  reportMonth,
  basePayload,
  runRevalidation,
  enabled,
  receipt,
  onReceipt,
}: {
  reportMonth: string;
  basePayload: LedgerPnlCandidateFinancialIndicatorsPayload;
  runRevalidation: (
    reportMonth: string,
    request: LedgerPnlCandidateFinancialIndicatorRevalidationRequest,
  ) => Promise<LedgerPnlCandidateFinancialIndicatorRevalidationReceipt>;
  enabled: boolean;
  receipt: LedgerPnlCandidateFinancialIndicatorRevalidationReceipt | null;
  onReceipt: (receipt: LedgerPnlCandidateFinancialIndicatorRevalidationReceipt | null) => void;
}) {
  const [input, setInput] = useState("{}");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const binding = [
    reportMonth,
    basePayload.idempotency_key,
    basePayload.promotion_readiness.evidence_pack.evidence_pack_key,
  ].join(":");
  const currentBindingRef = useRef(binding);
  const requestGenerationRef = useRef(0);
  const mountedRef = useRef(true);
  if (currentBindingRef.current !== binding) {
    currentBindingRef.current = binding;
    requestGenerationRef.current += 1;
  }

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestGenerationRef.current += 1;
    };
  }, []);

  useEffect(() => {
    setPending(false);
    setError(null);
  }, [binding]);

  const run = async () => {
    onReceipt(null);
    if (!enabled) return;
    let manualOverrides: LedgerPnlCandidateFinancialIndicatorRevalidationRequest["manual_overrides"];
    try {
      manualOverrides = parseManualOverrides(input);
    } catch (parseError) {
      setError(`手工覆盖 JSON 无效：${readableError(parseError)}`);
      return;
    }
    const requestBinding = binding;
    const requestGeneration = requestGenerationRef.current + 1;
    requestGenerationRef.current = requestGeneration;
    const isCurrentRequest = () => (
      mountedRef.current
      && requestGenerationRef.current === requestGeneration
      && currentBindingRef.current === requestBinding
    );
    setPending(true);
    setError(null);
    try {
      const nextReceipt = await runRevalidation(reportMonth, {
        base_candidate_idempotency_key: basePayload.idempotency_key,
        base_evidence_pack_key: basePayload.promotion_readiness.evidence_pack.evidence_pack_key,
        manual_overrides: manualOverrides,
      });
      if (!isCurrentRequest()) return;
      const receiptValid = await isRevalidationReceiptContract(
        nextReceipt,
        basePayload,
        Object.keys(manualOverrides).length,
      );
      if (!isCurrentRequest()) return;
      if (!receiptValid) {
        setError("核验回执契约错误：证据包或要求编号未完整绑定。");
        onReceipt(null);
        return;
      }
      onReceipt(nextReceipt);
    } catch (requestError) {
      if (!isCurrentRequest()) return;
      setError(readableError(requestError));
    } finally {
      if (isCurrentRequest()) setPending(false);
    }
  };

  return (
    <section
      className="candidate-indicators__revalidation"
      aria-labelledby="candidate-revalidation-title"
    >
      <div className="candidate-indicators__revalidation-heading">
        <div>
          <span>证据核验沙箱</span>
          <h3 id="candidate-revalidation-title">本次核验（不保存）</h3>
        </div>
        {receipt ? <strong>本次结果 · 未保存</strong> : null}
      </div>
      <p>只在当前页面内存中重算；刷新页面后丢失。结果禁止正式使用，不是审批，也不会保存证据。</p>
      <label htmlFor="candidate-revalidation-manual-overrides">手工覆盖 JSON</label>
      <textarea
        id="candidate-revalidation-manual-overrides"
        value={input}
        onChange={(event) => {
          setInput(event.target.value);
          setError(null);
          onReceipt(null);
        }}
        rows={5}
        spellCheck={false}
        disabled={pending || !enabled}
        placeholder={'{"input.adjustment.noninterest.r010":{"value_yi":"0","submitted_evidence_refs":["voucher://..."]}}'}
      />
      <small>候选幂等键与证据包键自动取自当前响应，不能在此修改。</small>
      {!enabled ? (
        <p className="candidate-indicators__revalidation-error" role="note">
          演示数据不支持本次核验，请切换真实 API
        </p>
      ) : null}
      <div className="candidate-indicators__revalidation-actions">
        <button type="button" disabled={pending || !enabled} onClick={() => void run()}>
          {pending ? "正在核验…" : "运行本次核验（不保存）"}
        </button>
        {receipt ? (
          <button type="button" disabled={pending} onClick={() => onReceipt(null)}>
            清除本次结果
          </button>
        ) : null}
      </div>
      {error ? <p className="candidate-indicators__revalidation-error" role="alert">{error}</p> : null}
    </section>
  );
}

function SourceVersionImpactCard({
  impact,
}: {
  impact: LedgerPnlCandidateSourceVersionImpact | null | undefined;
}) {
  if (!impact) {
    return (
      <section
        className="candidate-indicators__version-impact candidate-indicators__version-impact--unavailable"
        data-testid="candidate-source-version-impact-unavailable"
      >
        <div>
          <span>来源版本影响</span>
          <h3>暂无可核对的版本基准</h3>
        </div>
        <p>当前结果仍可按候选口径分析，但不能推断源文件换版是否改变指标数值。</p>
      </section>
    );
  }

  const unchanged = impact.status === "numerically_unchanged";
  return (
    <section
      className="candidate-indicators__version-impact"
      data-status={impact.status}
      data-testid="candidate-source-version-impact"
    >
      <div className="candidate-indicators__version-impact-copy">
        <span>来源版本影响</span>
        <h3>{unchanged ? "规则换版未改变指标数值" : "规则换版数值影响待复核"}</h3>
        <p>
          {impact.reference_rule_version} → {impact.current_rule_version}；
          比较采用 Decimal 规范值，不把尾随零差异误判为金额变化。
        </p>
      </div>
      <div className="candidate-indicators__version-impact-metrics">
        <article>
          <span>完成核对</span>
          <strong>{impact.compared_metric_count} / {impact.metric_total}</strong>
          <small>候选指标</small>
        </article>
        <article>
          <span>数值变化</span>
          <strong>{impact.numeric_changed_count ?? "待确认"}</strong>
          <small>Decimal 数值</small>
        </article>
        <article>
          <span>仅格式差异</span>
          <strong>{impact.serialization_only_count}</strong>
          <small>尾随零序列化</small>
        </article>
      </div>
      {impact.serialization_only_metric_ids.length > 0 ? (
        <details>
          <summary>查看仅格式差异的指标（{impact.serialization_only_metric_ids.length}）</summary>
          <ul>
            {impact.serialization_only_metric_ids.map((metricId) => (
              <li key={metricId}><code>{metricId}</code></li>
            ))}
          </ul>
        </details>
      ) : null}
      <small>该核对没有正式化效果；正式使用仍受独立治理门禁约束。</small>
    </section>
  );
}

export function LedgerPnlCandidateFinancialIndicatorsPanel({
  reportMonth,
  currency = "CNX",
  enabled = true,
}: Props) {
  const client = useApiClient();
  const normalizedReportMonth = reportMonth.trim();
  const [activeView, setActiveView] = useState<"analysis" | "governance" | null>(null);
  const [searchText, setSearchText] = useState("");
  const [selectedMetricId, setSelectedMetricId] = useState<string | null>(null);
  const [revalidationReceipt, setRevalidationReceipt] = useState<
    LedgerPnlCandidateFinancialIndicatorRevalidationReceipt | null
  >(null);
  const detailDialogRef = useRef<HTMLElement>(null);
  const detailCloseButtonRef = useRef<HTMLButtonElement>(null);
  const detailOpenerRef = useRef<HTMLButtonElement | null>(null);
  const baseQuery = useQuery({
    queryKey: [
      "ledger-pnl",
      "candidate-financial-indicators",
      client.mode,
      normalizedReportMonth,
      "base",
    ] as const,
    queryFn: () => client.getLedgerPnlCandidateFinancialIndicators(normalizedReportMonth, {
      includeLineage: false,
    }),
    enabled: enabled && Boolean(normalizedReportMonth),
    retry: false,
  });
  const detailQuery = useQuery({
    queryKey: [
      "ledger-pnl",
      "candidate-financial-indicators",
      client.mode,
      normalizedReportMonth,
      selectedMetricId ?? "__none",
      "lineage",
    ] as const,
    queryFn: () => client.getLedgerPnlCandidateFinancialIndicators(normalizedReportMonth, {
      includeLineage: true,
      metricId: selectedMetricId ?? undefined,
    }),
    enabled: Boolean(normalizedReportMonth && selectedMetricId),
    retry: false,
  });
  const basePayload = baseQuery.data?.result;
  const activeRevalidationReceipt = revalidationReceipt
    && basePayload
    && revalidationReceipt.base_candidate_idempotency_key === basePayload.idempotency_key
    && revalidationReceipt.base_evidence_pack_key
      === basePayload.promotion_readiness.evidence_pack.evidence_pack_key
    && revalidationReceipt.result.result.report_month === normalizedReportMonth
    ? revalidationReceipt
    : null;
  const payload = activeRevalidationReceipt?.result.result ?? basePayload;
  const normalizedSearch = searchText.trim().toLocaleLowerCase();
  const filteredMetrics = useMemo(() => {
    if (!payload) return [];
    if (!normalizedSearch) return payload.metrics;
    return payload.metrics.filter((metric) => (
      `${metric.metric_id} ${metric.name} ${metric.category} ${metric.basis} ${BASIS_LABELS[metric.basis]}`
        .toLocaleLowerCase()
        .includes(normalizedSearch)
    ));
  }, [normalizedSearch, payload]);

  const closeDetail = () => {
    setSelectedMetricId(null);
    globalThis.requestAnimationFrame(() => detailOpenerRef.current?.focus());
  };

  const openDetail = (
    metricId: string,
    event: ReactMouseEvent<HTMLButtonElement>,
  ) => {
    detailOpenerRef.current = event.currentTarget;
    setSelectedMetricId(metricId);
  };

  useEffect(() => {
    if (!selectedMetricId) return undefined;
    detailCloseButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeDetail();
        return;
      }
      if (event.key !== "Tab" || !detailDialogRef.current) return;
      const focusable = Array.from(
        detailDialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (focusable.length === 0) {
        event.preventDefault();
        detailDialogRef.current.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [selectedMetricId]);

  useEffect(() => {
    setRevalidationReceipt(null);
    setActiveView(null);
  }, [normalizedReportMonth, basePayload?.idempotency_key]);

  const renderHeader = () => (
    <header className="candidate-indicators__header">
      <div>
        <span className="candidate-indicators__eyebrow">财务指标引擎</span>
        <h2>候选财务指标</h2>
        <p>后端规则计算结果、来源信任状态与逐项追溯；前端只展示，不复算。</p>
      </div>
      <div className="candidate-indicators__header-meta">
        <span>候选口径 · 禁止正式使用</span>
        <small>{normalizedReportMonth || "未选择月份"} · CNX</small>
      </div>
    </header>
  );

  if (!normalizedReportMonth) {
    return (
      <section className="candidate-indicators">
        {renderHeader()}
        <div
          className="candidate-indicators__state"
          data-testid="candidate-financial-indicators-no-data"
          data-state="no_data"
        >
          <strong>未选择报告月份</strong>
          <span>请选择报告日后再读取候选财务指标；空月份不会发起后端请求。</span>
        </div>
      </section>
    );
  }

  if (baseQuery.isPending) {
    return (
      <section className="candidate-indicators" aria-busy="true">
        {renderHeader()}
        <div
          className="candidate-indicators__state"
          data-testid="candidate-financial-indicators-loading"
          data-state="loading"
        >
          <strong>正在读取候选财务指标…</strong>
          <span>正在校验来源、规则版本与 186 项计算结果。</span>
        </div>
      </section>
    );
  }

  if (baseQuery.isError) {
    return (
      <section className="candidate-indicators">
        {renderHeader()}
        <div
          className="candidate-indicators__state candidate-indicators__state--error"
          data-testid="candidate-financial-indicators-error"
          data-state="error"
          role="alert"
        >
          <strong>候选指标读取失败</strong>
          <span>{readableError(baseQuery.error)}</span>
          <button type="button" onClick={() => void baseQuery.refetch()}>重新读取</button>
        </div>
      </section>
    );
  }

  if (!payload) {
    return (
      <section className="candidate-indicators">
        {renderHeader()}
        <div
          className="candidate-indicators__state candidate-indicators__state--error"
          data-testid="candidate-financial-indicators-contract-error"
          data-state="error"
          role="alert"
        >
          <strong>候选指标响应不完整</strong>
          <span>响应缺少 result，已按契约错误阻断展示。</span>
        </div>
      </section>
    );
  }

  if (!isPromotionReadinessContract(payload.promotion_readiness, payload)) {
    return (
      <section className="candidate-indicators">
        {renderHeader()}
        <div
          className="candidate-indicators__state candidate-indicators__state--error"
          data-testid="candidate-financial-indicators-contract-error"
          data-state="error"
          role="alert"
        >
          <strong>候选指标响应不完整</strong>
          <span>响应缺少 promotion_readiness，已按契约错误阻断展示。</span>
        </div>
      </section>
    );
  }

  if (payload.calculation_status === "no_data") {
    return (
      <section className="candidate-indicators">
        {renderHeader()}
        <div
          className="candidate-indicators__state candidate-indicators__state--evidence"
          data-testid="candidate-financial-indicators-no-data"
          data-state="no_data"
        >
          <strong>{payload.report_month} 暂无可计算的候选财务指标</strong>
          <span>缺失值保持为空，不按零值展示。请先登记当月总账与日均来源。</span>
          <div className="candidate-indicators__source-list" aria-label="缺失来源">
            {payload.sources.map((source) => (
              <SourceEvidenceCard key={source.source_kind} source={source} />
            ))}
          </div>
          <div className="candidate-indicators__queue" aria-label="缺失来源待办">
            {payload.gaps.map((gap) => <GapEvidenceCard key={gap.gap_id} gap={gap} />)}
          </div>
        </div>
        <PromotionReadinessPanel readiness={payload.promotion_readiness} />
      </section>
    );
  }

  if (payload.calculation_status === "error") {
    return (
      <section
        className="candidate-indicators"
        data-testid="candidate-financial-indicators-panel"
        data-calculation-state="blocked"
      >
        {renderHeader()}
        {currency !== "CNX" ? (
          <div className="candidate-indicators__currency-note" role="note">
            <strong>仅支持 CNX 综合本口径</strong>
            <span>当前页面选择为 {currency}；本区仍遵守后端 CNX 候选口径。</span>
          </div>
        ) : null}
        <div
          className="candidate-indicators__blocked"
          data-testid="candidate-financial-indicators-blocked"
          data-state="blocked"
        >
          <div className="candidate-indicators__blocked-message" role="alert">
            <strong>候选指标计算被阻断</strong>
            <span>后端返回业务计算错误，关键值与指标目录已隐藏，不能解释为有效结果。</span>
          </div>
          <div className="candidate-indicators__source-list" aria-label="阻断来源摘要">
            {payload.sources.map((source) => (
              <SourceEvidenceCard key={source.source_kind} source={source} />
            ))}
          </div>
          <div className="candidate-indicators__queue" aria-label="阻断缺口摘要">
            {payload.gaps.map((gap) => (
              <GapEvidenceCard key={gap.gap_id} gap={gap} />
            ))}
          </div>
        </div>
        <PromotionReadinessPanel readiness={payload.promotion_readiness} />
      </section>
    );
  }

  const metricById = new Map(payload.metrics.map((metric) => [metric.metric_id, metric]));
  const sourceVersionImpact = isSourceVersionImpactContract(
    payload.source_version_impact,
    payload,
  ) ? payload.source_version_impact : null;
  const displayedView = activeView ?? (
    sourceVersionImpact?.status === "numerically_unchanged"
      ? "analysis"
      : "governance"
  );
  const mismatchedSources = payload.sources.filter((source) => source.locked_hash_match === false);
  const failedValidations = payload.validations.filter((validation) => !validation.passed);
  const visibleMetrics = filteredMetrics.slice(0, 50);
  const detailPayload = detailQuery.data?.result;
  const detailMetric = detailPayload?.requested_metric_id === selectedMetricId
    ? detailPayload.metrics.find((metric) => metric.metric_id === selectedMetricId)
    : undefined;
  const detailUnavailable = Boolean(
    detailPayload && (
      detailPayload.calculation_status === "error" ||
      detailPayload.calculation_status === "no_data" ||
      detailPayload.requested_metric_id !== selectedMetricId ||
      !detailMetric
    )
  );
  const catalogCountLabel = normalizedSearch
    ? filteredMetrics.length > visibleMetrics.length
      ? `匹配 ${filteredMetrics.length}，当前展示 ${visibleMetrics.length} / ${payload.summary.metric_total}`
      : `显示 ${filteredMetrics.length} / ${payload.summary.metric_total}`
    : `显示 ${visibleMetrics.length} / ${payload.summary.metric_total}`;

  return (
    <section
      className="candidate-indicators"
      data-testid="candidate-financial-indicators-panel"
      data-calculation-state={payload.calculation_status === "warning" ? "partial" : "ready"}
    >
      {renderHeader()}

      {currency !== "CNX" ? (
        <div className="candidate-indicators__currency-note" role="note">
          <strong>仅支持 CNX 综合本口径</strong>
          <span>当前页面选择为 {currency}；本区仍显示后端返回的 CNX 候选结果。</span>
        </div>
      ) : null}

      {mismatchedSources.length > 0 ? (
        <div
          className="candidate-indicators__trust-warning"
          data-testid="candidate-financial-indicators-stale-warning"
          data-state="stale-warning"
          role="alert"
        >
          {mismatchedSources.map((source) => {
            const gap = payload.gaps.find(
              (item) => item.gap_id === `source_hash.${source.source_kind}`,
            );
            return (
              <article key={source.source_kind}>
                <div>
                  <strong>{sourceKindLabel(source)}来源与锁定样本不一致</strong>
                  <span>{gap?.detail ?? "当前来源哈希与规则包锁定值不同。"}</span>
                </div>
                <p>
                  当前 <code>{source.sha256}</code>
                  <span>锁定 <code>{source.locked_sha256}</code></span>
                </p>
              </article>
            );
          })}
        </div>
      ) : null}

      <div className="candidate-indicators__summary-strip" aria-label="候选指标计算摘要">
        <div><span>计算状态</span><strong>{payload.calculation_status === "warning" ? "部分可用" : "可用"}</strong></div>
        <div><span>指标覆盖</span><strong>已计算 {payload.summary.metric_evaluated} / {payload.summary.metric_total}</strong></div>
        <div><span>规则验证</span><strong>规则验证 {payload.summary.validation_passed} / {payload.summary.validation_total} 通过</strong></div>
        <div><span>手工默认</span><strong>{payload.summary.manual_default_count} 项</strong></div>
      </div>

      <div
        className="candidate-indicators__view-switcher"
        role="tablist"
        aria-label="候选财务指标视图"
      >
        <button
          id="candidate-analysis-tab"
          type="button"
          role="tab"
          aria-controls="candidate-analysis-view"
          aria-selected={displayedView === "analysis"}
          onClick={() => setActiveView("analysis")}
        >
          <span>经营分析</span>
          <small>结论、规模、收入与指标目录</small>
        </button>
        <button
          id="candidate-governance-tab"
          type="button"
          role="tab"
          aria-controls="candidate-governance-view"
          aria-selected={displayedView === "governance"}
          onClick={() => setActiveView("governance")}
        >
          <span>治理与补证</span>
          <small>{payload.promotion_readiness.blocking_count} 项门禁仍阻断</small>
        </button>
      </div>

      <div
        id="candidate-governance-view"
        className="candidate-indicators__governance-view"
        data-testid="candidate-governance-view"
        role="tabpanel"
        aria-labelledby="candidate-governance-tab"
        hidden={displayedView !== "governance"}
      >
        <PromotionReadinessPanel
          readiness={payload.promotion_readiness}
          baseEvidencePack={basePayload?.promotion_readiness.evidence_pack}
          resolution={activeRevalidationReceipt?.requirement_resolution}
        />

        {basePayload ? (
          <CandidateRevalidationPanel
            reportMonth={normalizedReportMonth}
            basePayload={basePayload}
            runRevalidation={client.revalidateLedgerPnlCandidateFinancialIndicators}
            enabled={client.mode === "real"}
            receipt={activeRevalidationReceipt}
            onReceipt={setRevalidationReceipt}
          />
        ) : null}
      </div>

      <div
        id="candidate-analysis-view"
        className="candidate-indicators__analysis-view"
        data-testid="candidate-analysis-view"
        role="tabpanel"
        aria-labelledby="candidate-analysis-tab"
        hidden={displayedView !== "analysis"}
      >
        <section className="candidate-indicators__decision-brief" aria-labelledby="candidate-decision-title">
          <div>
            <span>本期经营判断</span>
            <h3 id="candidate-decision-title">
              {sourceVersionImpact?.status === "numerically_unchanged"
                ? "来源已换版，核心指标数值保持一致"
                : "候选指标可分析，正式结论仍待治理"}
            </h3>
            <p>
              当前来源状态为 {ALIGNMENT_LABELS[payload.source_alignment]}；
              页面展示后端候选值与血缘，不在前端补算，也不替代正式财务结果。
            </p>
          </div>
          <dl>
            <div><dt>规则版本</dt><dd>{payload.rule_version}</dd></div>
            <div><dt>正式门禁</dt><dd>{payload.promotion_readiness.blocking_count} 项阻断</dd></div>
            <div><dt>使用边界</dt><dd>仅分析 · 禁止正式使用</dd></div>
          </dl>
        </section>

        {displayedView === "analysis" ? (
          <LedgerPnlCandidatePeriodComparison reportMonth={normalizedReportMonth} />
        ) : null}

        <SourceVersionImpactCard impact={sourceVersionImpact} />

      <div className="candidate-indicators__section-heading">
        <div>
          <span>核心结论</span>
          <h3>收入结构与期末规模</h3>
        </div>
        <small>{payload.report_date} · {payload.rule_version}</small>
      </div>

      <div className="candidate-indicators__income-grid">
        {INCOME_METRIC_IDS.map((metricId) => {
          const metric = metricById.get(metricId);
          return (
            <article key={metricId} data-testid={`candidate-headline-${metricId}`}>
              <span>{metric?.name ?? metricId}</span>
              <MetricValue metric={metric} />
              <small>{metric ? BASIS_LABELS[metric.basis] : "—"}</small>
              {metric ? (
                <>
                  <em className="candidate-indicators__metric-status" data-status={metric.status}>
                    {STATUS_LABELS[metric.status]}
                  </em>
                  <button
                    type="button"
                    className="candidate-indicators__trace-action"
                    onClick={(event) => openDetail(metric.metric_id, event)}
                    aria-label={`${metric.name} ${metric.value ?? "无值"} 查看追溯`}
                  >
                    查看追溯
                  </button>
                </>
              ) : null}
            </article>
          );
        })}
      </div>

      <div className="candidate-indicators__scale-grid" aria-label="期末规模指标">
        {SCALE_METRIC_IDS.map((metricId) => {
          const metric = metricById.get(metricId);
          return (
            <article key={metricId} data-testid={`candidate-scale-${metricId}`}>
              <span>{metric?.name ?? metricId}</span>
              <div><MetricValue metric={metric} /></div>
              {metric ? (
                <>
                  <em className="candidate-indicators__metric-status" data-status={metric.status}>
                    {STATUS_LABELS[metric.status]}
                  </em>
                  <button
                    type="button"
                    className="candidate-indicators__trace-action"
                    onClick={(event) => openDetail(metric.metric_id, event)}
                    aria-label={`${metric.name} ${metric.value ?? "无值"} 查看追溯`}
                  >
                    查看追溯
                  </button>
                </>
              ) : null}
            </article>
          );
        })}
      </div>
      </div>

      <div className="candidate-indicators__evidence-layout">
        <section
          className="candidate-indicators__evidence"
          aria-labelledby="candidate-evidence-title"
          hidden={displayedView !== "governance"}
        >
          <div className="candidate-indicators__section-heading">
            <div>
              <span>审计待办</span>
              <h3 id="candidate-evidence-title">证据与待办</h3>
            </div>
            <small>
              {ALIGNMENT_LABELS[payload.source_alignment]} · <code>{payload.source_alignment}</code>
            </small>
          </div>

          <div className="candidate-indicators__source-list">
            {payload.sources.map((source) => (
              <SourceEvidenceCard key={source.source_kind} source={source} />
            ))}
          </div>

          <div className="candidate-indicators__queue">
            {failedValidations.map((validation) => (
              <ValidationEvidenceCard key={validation.validation_id} validation={validation} />
            ))}
            {payload.gaps.map((gap) => (
              <GapEvidenceCard key={gap.gap_id} gap={gap} />
            ))}
          </div>
        </section>

        <section
          className="candidate-indicators__catalog candidate-indicators__catalog--full"
          aria-labelledby="candidate-catalog-title"
          hidden={displayedView !== "analysis"}
        >
          <div className="candidate-indicators__section-heading">
            <div>
              <span>指标目录</span>
              <h3 id="candidate-catalog-title">全部指标</h3>
            </div>
            <small>{catalogCountLabel}</small>
          </div>
          <label className="candidate-indicators__search">
            <span>搜索全部财务指标</span>
            <input
              type="search"
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="指标名称、ID、分类或口径"
              aria-label="搜索全部财务指标"
            />
          </label>
          <div className="candidate-indicators__metric-list">
            {visibleMetrics.map((metric) => (
              <button
                key={metric.metric_id}
                type="button"
                onClick={(event) => openDetail(metric.metric_id, event)}
                aria-label={`${metric.name} ${metric.value ?? "无值"} 查看追溯`}
              >
                <span>
                  <strong>{metric.name}</strong>
                  <code>{metric.metric_id}</code>
                </span>
                <span>
                  <strong>{metric.value ?? "—"}</strong>
                  <small>{metric.unit} · {STATUS_LABELS[metric.status]}</small>
                </span>
              </button>
            ))}
            {visibleMetrics.length === 0 ? <p>没有匹配的指标。</p> : null}
          </div>
        </section>
      </div>

      {selectedMetricId ? (
        <>
          <button
            type="button"
            className="candidate-indicators__detail-backdrop"
            onClick={closeDetail}
            aria-label="关闭指标追溯详情"
            tabIndex={-1}
          />
          <aside
            ref={detailDialogRef}
            className="candidate-indicators__detail"
            aria-label="指标追溯详情"
            aria-modal="true"
            role="dialog"
            tabIndex={-1}
          >
            <header>
              <div>
                <span>追溯详情</span>
                <h3>
                  {detailMetric?.name ?? (detailQuery.isPending ? "正在读取指标追溯" : "指标追溯不可用")}
                </h3>
                <code>{selectedMetricId}</code>
              </div>
              <button
                ref={detailCloseButtonRef}
                type="button"
                onClick={closeDetail}
                aria-label="关闭指标追溯详情"
              >
                关闭
              </button>
            </header>
            {detailQuery.isPending ? <p>正在读取该指标的后端血缘…</p> : null}
            {detailQuery.isError ? (
              <div role="alert">
                <strong>指标追溯读取失败</strong>
                <span>{readableError(detailQuery.error)}</span>
                <button type="button" onClick={() => void detailQuery.refetch()}>重试追溯</button>
              </div>
            ) : null}
            {!detailQuery.isPending && !detailQuery.isError && detailUnavailable ? (
              <div role="status" className="candidate-indicators__detail-unavailable">
                <strong>指标追溯不可用</strong>
                <span>
                  后端业务状态为 {detailPayload?.calculation_status ?? "响应不完整"}，
                  或返回指标与请求 ID 不一致；未把空结果当作加载中。
                </span>
                {detailPayload?.gaps.map((gap) => (
                  <small key={gap.gap_id}>{gap.title}：{gap.detail}</small>
                ))}
              </div>
            ) : null}
            {detailMetric && !detailUnavailable ? (
              <div className="candidate-indicators__detail-body">
                <dl>
                  <div><dt>值</dt><dd>{detailMetric.value ?? "—"} {detailMetric.unit}</dd></div>
                  <div>
                    <dt>口径</dt>
                    <dd>{BASIS_LABELS[detailMetric.basis]} · <code>{detailMetric.basis}</code></dd>
                  </div>
                  <div><dt>状态</dt><dd>{STATUS_LABELS[detailMetric.status]}</dd></div>
                  <div><dt>规则</dt><dd>{detailPayload?.rule_version}</dd></div>
                </dl>
                {detailMetric.reasons.length > 0 ? (
                  <section className="candidate-indicators__reasons" aria-label="指标原因">
                    <strong>指标原因</strong>
                    <ul>
                      {detailMetric.reasons.map((reason) => <li key={reason}><code>{reason}</code></li>)}
                    </ul>
                  </section>
                ) : null}
                <div className="candidate-indicators__lineage-list">
                  {detailMetric.lineage.map((lineage, index) => (
                    <LineageEvidence key={`${lineage.lineage_type}-${index}`} lineage={lineage} />
                  ))}
                  {detailMetric.lineage.length === 0 ? <p>后端未返回血缘证据。</p> : null}
                </div>
              </div>
            ) : null}
          </aside>
        </>
      ) : null}
    </section>
  );
}
