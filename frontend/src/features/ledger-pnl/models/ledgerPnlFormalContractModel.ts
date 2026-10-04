import type {
  LedgerPnlFormalFinancialIndicatorContractPayload,
  LedgerPnlFormalFinancialIndicatorMetric,
  LedgerPnlFormalFinancialIndicatorRemediation,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

export function buildFormalContractMaterialChecklist(
  remediation: LedgerPnlFormalFinancialIndicatorRemediation | undefined,
) {
  const hasRemediation = remediation !== undefined;
  const hasMissingArtifact = remediation?.artifact_status === "missing";
  const guardStatus = remediation?.registration_package_guard?.status?.trim() ?? "";
  const hasBlockedRegistrationPackage = guardStatus === "blocked";
  const rows = [
    { key: "artifact", label: "物料", value: remediation?.required_artifact?.trim() ?? "" },
    { key: "blocking", label: "阻断", value: remediation?.blocking_reason?.trim() ?? "" },
    {
      key: "acceptance",
      label: "验收",
      value: remediation?.acceptance_criteria?.map((item) => item.trim()).filter(Boolean).join("；") ?? "",
    },
    {
      key: "fixtureTarget",
      label: "样本落盘",
      value: remediation?.registration_package?.fixture_target?.trim() ?? "",
    },
    {
      key: "registryTarget",
      label: "契约登记",
      value: remediation?.registration_package?.registry_target?.trim() ?? "",
    },
    {
      key: "contractBuilder",
      label: "构建入口",
      value: remediation?.registration_package?.contract_builder?.trim() ?? "",
    },
    {
      key: "releaseGate",
      label: "放行条件",
      value: remediation?.registration_package?.release_gate?.trim() ?? "",
    },
    {
      key: "registrationPackageGuard",
      label: "登记包守卫",
      value: remediation?.registration_package_guard?.status?.trim() ?? "",
    },
    {
      key: "registrationPackageRequiredFields",
      label: "必备字段",
      value: remediation?.registration_package_guard?.required_fields?.map((item) => item.trim()).filter(Boolean).join("；") ?? "",
    },
    {
      key: "registrationPackageMissingFields",
      label: "缺失字段",
      value: remediation?.registration_package_guard?.missing_fields?.map((item) => item.trim()).filter(Boolean).join("；") || "无",
    },
    {
      key: "registrationPackageBlockingRule",
      label: "守卫规则",
      value: remediation?.registration_package_guard?.blocking_rule?.trim() ?? "",
    },
    {
      key: "readbackAcceptance",
      label: remediation?.readback_acceptance?.label?.trim() || "登记后回读验收",
      value: remediation?.readback_acceptance?.readback_query?.trim() ?? "",
    },
    {
      key: "readbackAcceptanceTarget",
      label: "目标状态",
      value: remediation?.readback_acceptance?.target_state?.trim() ?? "",
    },
    {
      key: "readbackAcceptanceRelease",
      label: "待放行状态",
      value: remediation?.readback_acceptance?.release_state?.trim() ?? "",
    },
    {
      key: "readbackAcceptanceFormalUse",
      label: "不得放行",
      value: remediation?.readback_acceptance?.formal_use_guard?.trim() ?? "",
    },
    {
      key: "readbackAcceptanceSource",
      label: "来源守卫",
      value: remediation?.readback_acceptance?.source_guard?.trim() ?? "",
    },
    {
      key: "readbackAcceptanceVerification",
      label: "回读验证",
      value: remediation?.readback_acceptance?.verification?.trim() ?? "",
    },
    { key: "registration", label: "登记", value: remediation?.registration_target?.trim() ?? "" },
    { key: "verification", label: "验证", value: remediation?.verification?.trim() ?? "" },
  ];
  const readinessRows = rows.filter((row) => row.key !== "blocking");
  const readyCount = hasMissingArtifact
    ? 0
    : readinessRows.filter((row) => row.value.length > 0).length;
  const totalCount = hasMissingArtifact ? 1 : readinessRows.length;
  return {
    rows,
    hasMissingArtifact,
    hasBlockedRegistrationPackage,
    readyCount,
    totalCount,
    summary: !hasRemediation
      ? "无缺契约补证材料"
      : hasMissingArtifact
        ? `正式样本缺失 ${readyCount}/${totalCount}`
      : readyCount === totalCount
        ? `补证材料齐备 ${readyCount}/${totalCount}`
        : `补证材料待补 ${readyCount}/${totalCount}`,
  };
}

export function registeredPendingReleaseGate(
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined,
) {
  if (!contract || contract.sample_status === "missing_contract" || contract.formal_use_allowed === true) {
    return undefined;
  }
  const releaseGate = contract?.release_gate;
  return releaseGate?.status?.trim() === "registered_pending_release"
    ? releaseGate
    : undefined;
}

export function hasEmptyFormalContractMetrics(
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined,
) {
  return Boolean(
    contract &&
      contract.sample_status !== "missing_contract" &&
      contract.formal_use_allowed !== true &&
      (contract.metrics?.length ?? 0) === 0,
  );
}

export function formalContractExecutionStatus(props: {
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined;
  isLoading: boolean;
  isError: boolean;
  materialChecklist: ReturnType<typeof buildFormalContractMaterialChecklist>;
}) {
  if (props.isLoading) {
    return "读取正式契约中";
  }
  if (props.isError) {
    return "待恢复契约读取";
  }
  if (props.contract?.formal_use_allowed === true) {
    return "已读取正式契约";
  }
  if (hasEmptyFormalContractMetrics(props.contract)) {
    return "待恢复契约明细";
  }
  const releaseGate = registeredPendingReleaseGate(props.contract);
  if (releaseGate) {
    return "已登记待放行";
  }
  if (props.contract?.sample_status === "missing_contract") {
    if (props.materialChecklist.hasMissingArtifact) {
      return "待补齐正式样本";
    }
    if (props.materialChecklist.hasBlockedRegistrationPackage) {
      return "待补齐登记包";
    }
    return props.materialChecklist.readyCount === props.materialChecklist.totalCount
      ? "待登记正式契约"
      : "待补齐材料";
  }
  return "待重新读取正式契约";
}

export function formalContractReadbackAction(props: {
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined;
  isLoading: boolean;
  isError: boolean;
  materialChecklist: ReturnType<typeof buildFormalContractMaterialChecklist>;
}) {
  if (props.isLoading) {
    return "等待正式契约读取完成";
  }
  if (props.isError) {
    return "恢复读取后重新查询正式契约";
  }
  if (props.contract?.formal_use_allowed === true) {
    return "已完成正式契约回读";
  }
  if (hasEmptyFormalContractMetrics(props.contract)) {
    return "恢复明细生成后重新读取正式契约";
  }
  const releaseGate = registeredPendingReleaseGate(props.contract);
  if (releaseGate) {
    return releaseGate.readback_action?.trim() || "登记来源接入证据并重新读取正式契约";
  }
  if (props.contract?.sample_status === "missing_contract") {
    if (props.materialChecklist.hasMissingArtifact) {
      return "补齐样本并登记后刷新页面或重新查询正式契约接口";
    }
    if (props.materialChecklist.hasBlockedRegistrationPackage) {
      return "补齐登记包后再登记正式契约";
    }
    return "登记后刷新页面或重新查询正式契约接口";
  }
  return "重新读取正式契约并复核 formal_use_allowed";
}

export function formalContractMaterialSummary(props: {
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined;
  isLoading: boolean;
  isError: boolean;
  materialChecklist: ReturnType<typeof buildFormalContractMaterialChecklist>;
}) {
  if (props.isLoading) {
    return "等待正式契约读取";
  }
  if (props.isError) {
    return "等待恢复正式契约读取";
  }
  if (hasEmptyFormalContractMetrics(props.contract)) {
    return "正式契约明细缺失";
  }
  if (registeredPendingReleaseGate(props.contract)) {
    return "登记包已读，等待放行证据";
  }
  if (props.contract?.sample_status === "missing_contract") {
    return props.materialChecklist.summary;
  }
  return "无缺契约补证材料";
}

export function formalContractRemediationConclusion(props: {
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined;
  isLoading: boolean;
  isError: boolean;
  materialChecklist: ReturnType<typeof buildFormalContractMaterialChecklist>;
  readbackAction: string;
}) {
  if (props.isLoading) {
    return "等待正式契约读取后再判断补证闭环";
  }
  if (props.isError) {
    return "正式契约读取失败；先恢复读取，再复核正式契约";
  }
  if (props.contract?.formal_use_allowed === true) {
    return "正式契约已放行；无需正式补证";
  }
  if (hasEmptyFormalContractMetrics(props.contract)) {
    return "正式契约已读取但没有指标明细；先恢复明细生成，再回读正式契约";
  }
  const releaseGate = registeredPendingReleaseGate(props.contract);
  if (releaseGate) {
    return "正式契约已登记待放行；补齐放行证据后再回读确认";
  }
  if (props.contract?.sample_status === "missing_contract") {
    const reportMonth = props.contract.report_month || "本月";
    if (props.materialChecklist.hasMissingArtifact) {
      return `${reportMonth} 正式样本缺失；先补齐样本，再登记 source contract、回读正式契约并核对 QDB 候选值`;
    }
    if (props.materialChecklist.hasBlockedRegistrationPackage) {
      return `${reportMonth} 登记包不完整；先补齐登记包，再登记正式契约`;
    }
    return `${reportMonth} 正式契约待登记；${shortFormalContractReadbackAction(props.readbackAction)}`;
  }
  return "正式契约未放行；重新读取正式契约并复核 formal_use_allowed";
}

export function shortFormalContractReadbackAction(action: string) {
  if (action === "补齐样本并登记后刷新页面或重新查询正式契约接口") {
    return "补齐样本并登记后刷新正式契约";
  }
  return action === "登记后刷新页面或重新查询正式契约接口" ? "登记后刷新正式契约" : action;
}
export function summarizeFormalIndicatorContractGaps(
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined,
  isLoading: boolean,
  isError: boolean,
) {
  if (isLoading) {
    return {
      label: "正式契约读取中",
      formalPending: 0,
      qdbCandidateAligned: 0,
      needsReconciliation: 0,
    };
  }
  if (isError) {
    return {
      label: "正式契约读取失败",
      formalPending: 0,
      qdbCandidateAligned: 0,
      needsReconciliation: 0,
    };
  }
  const metrics = contract?.metrics ?? [];
  if (contract?.sample_status === "missing_contract") {
    return {
      label: `${contract.report_month || "本月"} 正式契约样本缺失`,
      formalPending: 0,
      qdbCandidateAligned: 0,
      needsReconciliation: 0,
    };
  }
  if (metrics.length === 0) {
    return {
      label: "无正式契约明细",
      formalPending: 0,
      qdbCandidateAligned: 0,
      needsReconciliation: 0,
    };
  }
  const gapMetrics = metrics.filter(
    (metric) => metric.formal_use_allowed === false || metric.value === null || metric.value === undefined || metric.value === "",
  );
  if (gapMetrics.length === 0) {
    return {
      label: "正式契约已放行",
      formalPending: 0,
      qdbCandidateAligned: 0,
      needsReconciliation: 0,
    };
  }
  return {
    label: null,
    formalPending: gapMetrics.filter((metric) => metric.source_status === "formal_pending").length,
    qdbCandidateAligned: gapMetrics.filter((metric) => metric.source_status === "candidate_qdb_aligned").length,
    needsReconciliation: gapMetrics.filter((metric) => metric.source_status === "needs_reconciliation").length,
  };
}
export const sourceStatusLabels = {
  formal_pending: "正式来源待接入",
  candidate_qdb_aligned: "QDB 候选对齐",
  needs_reconciliation: "需对账",
} as const;

export function formalSourceContractTone(metric: LedgerPnlFormalFinancialIndicatorMetric) {
  if (metric.source_status === "candidate_qdb_aligned") {
    return "analytical";
  }
  if (metric.source_status === "formal_pending") {
    return "pending";
  }
  return "warning";
}

export function formatContractMetricValue(value: string | number | null | undefined, unit: string) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  return unit ? `${value} ${unit}` : String(value);
}

export function formatFormalContractValue(value: string | number | null | undefined, unit: string) {
  if (value === null || value === undefined || value === "") {
    return "未接入";
  }
  return formatContractMetricValue(value, unit);
}

function parseContractGap(value: string | number | null | undefined) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? Math.abs(value) : 0;
  }
  if (!value) {
    return 0;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.abs(parsed) : 0;
}

function contractActionRank(metric: LedgerPnlFormalFinancialIndicatorMetric) {
  if (metric.source_status === "needs_reconciliation") {
    return 0;
  }
  if (metric.source_status === "candidate_qdb_aligned") {
    return 1;
  }
  return 2;
}

export function contractActionTitle(metric: LedgerPnlFormalFinancialIndicatorMetric) {
  if (metric.source_status === "needs_reconciliation") {
    return "先对账 QDB 候选与 Excel 样本";
  }
  if (metric.source_status === "candidate_qdb_aligned") {
    return "候选已对齐，等待正式来源放行";
  }
  return "补正式财务指标来源";
}

export function buildFormalContractActionQueue(metrics: LedgerPnlFormalFinancialIndicatorMetric[]) {
  return [...metrics]
    .filter((metric) => metric.formal_use_allowed === false || metric.value === null || metric.value === undefined)
    .sort((left, right) => {
      const rankDelta = contractActionRank(left) - contractActionRank(right);
      if (rankDelta !== 0) {
        return rankDelta;
      }
      return parseContractGap(right.reconciliation_gap) - parseContractGap(left.reconciliation_gap);
    })
    .slice(0, 6);
}

export function buildFormalContractDecision(
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined,
  isLoading: boolean,
  isError: boolean,
) {
  if (isLoading) {
    return {
      tone: "pending",
      title: "正在读取正式财务指标契约",
      detail: "读取完成前不展示正式财务指标值。",
    };
  }
  if (isError) {
    return {
      tone: "warning",
      title: "正式财务指标契约读取失败",
      detail: "本次页面不能确认正式财务指标来源，正式值不可用于展示。",
    };
  }
  if (contract?.sample_status === "missing_contract") {
    return {
      tone: "warning",
      title: "本月未登记正式财务指标契约",
      detail: "正式值不可用于展示，分析候选值不会回填。",
    };
  }
  if (!contract) {
    return {
      tone: "pending",
      title: "等待正式财务指标契约",
      detail: "选择报告日并解析出月份后读取契约状态。",
    };
  }
  if (hasEmptyFormalContractMetrics(contract)) {
    return {
      tone: "warning",
      title: "正式财务指标契约明细缺失",
      detail: "契约头已返回，但没有任何指标明细；正式值不可用于展示。",
    };
  }
  const releaseGate = registeredPendingReleaseGate(contract);
  if (releaseGate) {
    return {
      tone: "warning",
      title: "正式财务指标已登记待放行",
      detail:
        releaseGate.blocking_reason?.trim() ||
        "正式财务指标契约已登记，但尚未满足正式放行条件。",
    };
  }
  if (contract && !contract.formal_use_allowed) {
    return {
      tone: "warning",
      title: "正式财务指标尚未放行",
      detail: "当前仅展示样本与候选核对状态，不批准分析值转正式值。",
    };
  }
  return {
    tone: "ok",
    title: "正式财务指标契约已读取",
    detail: "按后端契约返回的正式值展示。",
  };
}

export function formatFormalContractNote(
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined,
) {
  if (!contract?.contract_note) {
    return "";
  }
  if (contract.sample_status === "missing_contract") {
    return "后台未登记本月正式财务指标契约；正式值保持不可用，不能用分析候选值补齐。";
  }
  if (registeredPendingReleaseGate(contract)) {
    return "当前契约已登记但未放行；QDB 候选值仍只能用于核对，不能转为正式展示。";
  }
  if (!contract.formal_use_allowed) {
    return "当前契约只冻结样本与来源状态；QDB 候选值仅用于核对，不能转为正式展示。";
  }
  return contract.contract_note;
}

/**
 * B5：正式财务指标源契约卡 + 缺契约补证 runbook 默认折叠为一行摘要（DESIGN.md §6 证据分层）。
 * 展开区内容零删减——本函数只产出摘要文案，不影响 FormalIndicatorSourceContractPanel 本身渲染。
 */
export function formalContractCollapsedSummary(
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined,
  isLoading: boolean,
  isError: boolean,
): string {
  if (!isLoading && !isError && contract?.sample_status === "missing_contract") {
    return "本月正式财务指标契约未登记，正式值不可用；候选值不回填。";
  }
  const decision = buildFormalContractDecision(contract, isLoading, isError);
  return `${decision.title}；${decision.detail}`;
}
