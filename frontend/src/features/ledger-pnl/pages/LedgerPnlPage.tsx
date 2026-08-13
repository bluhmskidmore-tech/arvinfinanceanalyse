import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { useDeferredSectionSeen } from "../../../hooks/useDeferredSectionSeen";
import { EM_DASH } from "../../../utils/format";
import { FilterBar } from "../../../components/FilterBar";
import type {
  ApiEnvelope,
  LedgerMoneyValue,
  LedgerPnlAnalysisPayload,
  LedgerPnlAdditivityCheck,
  LedgerPnlArrangementRule,
  LedgerPnlFormalFinancialIndicatorContractPayload,
  LedgerPnlFormalFinancialIndicatorMetric,
  LedgerPnlFormalFinancialIndicatorRemediation,
  LedgerPnlFormalIndicatorRuleChecksPayload,
  LedgerPnlRatioRecomputationCheck,
  QdbGlMonthlyAnalysisWorkbookPayload,
  QdbGlMonthlyAnalysisSheet,
  ResultMeta,
} from "../../../api/contracts";
import { LedgerPnlAccountDetailDrawer } from "../components/LedgerPnlAccountDetailDrawer";
import { LedgerPnlCandidateFinancialIndicatorsPanel } from "../components/LedgerPnlCandidateFinancialIndicatorsPanel";
import { LedgerPnlFinancialIndicatorSummaryPanel } from "../components/LedgerPnlFinancialIndicatorSummaryPanel";
import {
  LedgerPnlDataTable,
  type LedgerPnlDataTableColumn,
} from "../components/LedgerPnlDataTable";
import {
  LedgerPnlSectionNav,
  type LedgerPnlSectionNavItem,
} from "../components/LedgerPnlSectionNav";
import {
  LedgerPnlWorkbookTables,
  type LedgerPnlWorkbookTableSpec,
} from "../components/LedgerPnlWorkbookTables";
import { buildLedgerPnlWorkbookGroups } from "../components/ledgerPnlWorkbookTablesSupport";
import {
  LedgerPnlAnalysisWorkbench,
  type LedgerPnlContributorSelection,
} from "../components/LedgerPnlAnalysisWorkbench";
import "./LedgerPnlPage.css";

const LEDGER_PNL_FORMAL_CONTRACT_PANEL_ID = "ledger-pnl-formal-indicator-source-contract-panel";
const LEDGER_PNL_FORMAL_CONTRACT_RELEASE_GATE_ID =
  "ledger-pnl-formal-indicator-source-contract-release-gate";
const LEDGER_PNL_FORMAL_CONTRACT_MATERIAL_CHECKLIST_ID =
  "ledger-pnl-formal-indicator-source-contract-material-checklist";
const LEDGER_PNL_REPORT_DATE_SELECT_ID = "ledger-pnl-report-date-select";
const LEDGER_PNL_RULE_CHECKS_PANEL_ID = "ledger-pnl-formal-indicator-rule-checks-panel";
/** 章节锚点：整页高度远超一屏，导航条与各区块靠这组 id 对齐。 */
const LEDGER_PNL_SECTION_IDS = {
  verdict: "ledger-pnl-section-verdict",
  summary: "ledger-pnl-section-summary",
  analysis: "ledger-pnl-section-analysis",
  indicators: "ledger-pnl-section-indicators",
  candidate: "ledger-pnl-section-candidate",
  reconciliation: "ledger-pnl-section-reconciliation",
  accounts: "ledger-pnl-section-accounts",
  detail: "ledger-pnl-section-detail",
  evidence: "ledger-pnl-section-evidence",
} as const;
const LEDGER_PNL_CURRENCY_BASIS_OPTIONS = [
  { value: "CNX", label: "CNX（综本）" },
  { value: "CNY", label: "CNY（人民币账）" },
] as const;

type LedgerPnlCurrencyBasis = (typeof LEDGER_PNL_CURRENCY_BASIS_OPTIONS)[number]["value"];

function normalizeLedgerPnlCurrencyBasis(value: string | null | undefined): LedgerPnlCurrencyBasis {
  return value?.trim() === "CNY" ? "CNY" : "CNX";
}

const ledgerCandidateSummaryMetrics = {
  ledger_monthly_pnl_core: {
    metricId: "MTR-LPN-001",
    note: "候选指标，pending_confirmation=true；不能替代正式 PnL 或产品分类 PnL。",
  },
  ledger_monthly_pnl_all: {
    metricId: "MTR-LPN-002",
    note: "候选指标，pending_confirmation=true；仅用于总账对账分析。",
  },
  ledger_net_assets: {
    metricId: "MTR-LPN-003",
    note: "候选指标，pending_confirmation=true；不是正式净资产财务指标。",
  },
} as const;

type LedgerCandidateSummaryMetricKey = keyof typeof ledgerCandidateSummaryMetrics;

type LedgerSummaryCardModel = {
  key: string;
  title: string;
  value: string;
  candidateMetricKey?: LedgerCandidateSummaryMetricKey;
};

function LedgerSummaryCard({ card }: { card: LedgerSummaryCardModel }) {
  const candidateMetric = card.candidateMetricKey
    ? ledgerCandidateSummaryMetrics[card.candidateMetricKey]
    : null;
  return (
    <div className="ledger-pnl-summary-card-frame">
      <div className="ledger-pnl-summary-card__header">
        <div className="ledger-pnl-summary-card__title">{card.title}</div>
        {candidateMetric ? (
          <span className="ledger-pnl-summary-card__badge">
            候选
          </span>
        ) : null}
      </div>
      <div className="ledger-pnl-summary-card__value">
        {card.value}
      </div>
      {candidateMetric ? (
        <div
          className="ledger-pnl-summary-card__note"
          title={`${candidateMetric.metricId} ${candidateMetric.note}`}
        >
          {candidateMetric.metricId} {candidateMetric.note}
        </div>
      ) : null}
    </div>
  );
}

const LEDGER_TABLE_PAGE_SIZE = 25;

/** 区块头右侧的状态位：ready 时不占版面，其余状态用一句中文露出（DESIGN.md §6 五态）。 */
type LedgerSectionState = { label: string; tone: "loading" | "error" | "empty" } | null;

function ledgerSectionState(
  query: { isLoading: boolean; isError: boolean },
  options?: { isEmpty?: boolean; emptyLabel?: string },
): LedgerSectionState {
  if (query.isLoading) {
    return { label: "读取中", tone: "loading" };
  }
  if (query.isError) {
    return { label: "读取失败", tone: "error" };
  }
  if (options?.isEmpty) {
    return { label: options.emptyLabel ?? "暂无数据", tone: "empty" };
  }
  return null;
}

/** 编号分区头（首页 Nocturne 语言）：序号由 CSS counter 生成，避免手写编号漂移。 */
function LedgerPnlSectionLead({
  title,
  state,
  note,
}: {
  title: string;
  state?: LedgerSectionState;
  note?: string;
}) {
  return (
    <header className="ledger-pnl-section__lead">
      <h2>{title}</h2>
      {state ? (
        <span className="ledger-pnl-section__state" data-state={state.tone} role="status">
          {state.label}
        </span>
      ) : note ? (
        <span className="ledger-pnl-section__note">{note}</span>
      ) : null}
    </header>
  );
}

function formatMoney(value: LedgerMoneyValue | null | undefined) {
  const yi = String(value?.yi ?? "").trim();
  if (yi) {
    return `${yi} 亿元`;
  }
  const yuanRaw = String(value?.yuan ?? "").trim();
  if (!yuanRaw) {
    return EM_DASH;
  }
  const yuan = Number(yuanRaw);
  return Number.isFinite(yuan) ? `${(yuan / 100_000_000).toFixed(2)} 亿元` : EM_DASH;
}

function ledgerMoneyYuan(value: LedgerMoneyValue | null | undefined) {
  const rawYuan = String(value?.yuan ?? "").trim();
  if (!rawYuan) {
    return null;
  }
  const yuan = Number(rawYuan);
  return Number.isFinite(yuan) ? yuan : null;
}

function ledgerMoneyAbsYuan(value: LedgerMoneyValue | null | undefined) {
  const yuan = ledgerMoneyYuan(value);
  return yuan === null ? -1 : Math.abs(yuan);
}

/** 默认排序：金额绝对值降序，让影响最大的科目排在首页。 */
function sortLedgerRowsByAbsYuan<T>(
  rows: T[],
  selectMoney: (row: T) => LedgerMoneyValue | null | undefined,
) {
  return rows
    .map((row, index) => ({
      row,
      index,
      absYuan: ledgerMoneyAbsYuan(selectMoney(row)),
    }))
    .sort((left, right) => right.absYuan - left.absYuan || left.index - right.index)
    .map((item) => item.row);
}

function LedgerTableStateRow(props: { colSpan: number; message: string }) {
  return (
    <tr>
      <td colSpan={props.colSpan} className="ledger-pnl-table__state-cell">
        {props.message}
      </td>
    </tr>
  );
}

/**
 * 视口门控区块的占位骨架（DESIGN.md §6：带背板与接近折叠头部的高度，防止内容到达时重排）。
 * 数据查询在区块进入视口后才发起，骨架期不出现"读取失败"之类的误导状态。
 */
function LedgerSectionSkeleton(props: {
  testId: string;
  title: string;
  minHeight: number;
}) {
  const style = {
    "--ledger-pnl-skeleton-min-height": `${props.minHeight}px`,
  } as CSSProperties;
  return (
    <div
      data-testid={props.testId}
      className="ledger-pnl-section-skeleton"
      style={style}
      role="status"
      aria-label={`${props.title}待加载`}
    >
      <div className="ledger-pnl-section-skeleton__title">{props.title}</div>
      <div className="ledger-pnl-section-skeleton__note">该区块进入视口后自动加载数据。</div>
      <div className="ledger-pnl-section-skeleton__bars" aria-hidden>
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

function metaString(value: unknown) {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
}

function formatMetaQuality(meta: ResultMeta | null | undefined) {
  const labels: Record<string, string> = {
    ok: "正常",
    warning: "预警",
    error: "错误",
    stale: "陈旧",
    missing: "缺失",
  };
  const value = metaString(meta?.quality_flag);
  return value ? (labels[value] ?? value) : "缺失";
}

function collectSourceRiskSegments(label: string, meta: ResultMeta | null | undefined) {
  const segments: string[] = [];
  const fallbackMode = metaString(meta?.fallback_mode);
  const vendorStatus = metaString(meta?.vendor_status);
  const scenarioFlag = meta?.scenario_flag === true;
  if (fallbackMode && fallbackMode !== "none") {
    segments.push(`${label} fallback=${fallbackMode}`);
  }
  if (vendorStatus && vendorStatus !== "ok") {
    segments.push(`${label} vendor=${vendorStatus}`);
  }
  if (scenarioFlag) {
    segments.push(`${label} scenario=true`);
  }
  return segments;
}

function missingSourceEvidenceFields(label: string, meta: ResultMeta | null | undefined) {
  if (!meta) {
    return [];
  }
  const fields = [
    metaString(meta.source_version) ? null : `${label} source_version 缺失`,
    metaString(meta.rule_version) ? null : `${label} rule_version 缺失`,
    metaString(meta.cache_version) ? null : `${label} cache_version 缺失`,
    (meta.tables_used?.length ?? 0) > 0 ? null : `${label} tables_used 缺失`,
  ];
  return fields.filter((field): field is string => Boolean(field));
}

type MonthlyWorkbookAuditState = {
  status: string;
  action: string;
  blockingDetail: string | null;
  isTrusted: boolean;
};

function monthlyWorkbookAuditState(props: {
  requestedReportMonth: string;
  hasMatchingAnalysisMonth: boolean;
  isMonthlyAnalysisDatesLoading: boolean;
  isMonthlyAnalysisDatesError: boolean;
  isMonthlyAnalysisWorkbookLoading: boolean;
  isMonthlyAnalysisWorkbookError: boolean;
  monthlyAnalysisWorkbook: QdbGlMonthlyAnalysisWorkbookPayload | undefined;
  monthlyAnalysisWorkbookMeta: ResultMeta | null | undefined;
}): MonthlyWorkbookAuditState {
  if (!props.requestedReportMonth) {
    return {
      status: "等待报告月份",
      action: "先选择报告日生成 report_month",
      blockingDetail: null,
      isTrusted: false,
    };
  }
  if (props.isMonthlyAnalysisDatesLoading) {
    return {
      status: "月度月份读取中",
      action: "等待月度分析月份读取完成",
      blockingDetail: null,
      isTrusted: false,
    };
  }
  if (props.isMonthlyAnalysisDatesError) {
    return {
      status: "月度月份读取失败",
      action: "恢复月度分析月份读取",
      blockingDetail: null,
      isTrusted: false,
    };
  }
  if (!props.hasMatchingAnalysisMonth) {
    return {
      status: `${props.requestedReportMonth} 无匹配`,
      action: `补齐 ${props.requestedReportMonth} QDB 月度分析工作簿`,
      blockingDetail: null,
      isTrusted: false,
    };
  }
  if (props.isMonthlyAnalysisWorkbookLoading) {
    return {
      status: "月度工作簿读取中",
      action: "等待月度工作簿读取完成",
      blockingDetail: null,
      isTrusted: false,
    };
  }
  if (props.isMonthlyAnalysisWorkbookError) {
    return {
      status: "月度工作簿读取失败",
      action: `重新读取 ${props.requestedReportMonth} 月度分析工作簿`,
      blockingDetail: null,
      isTrusted: false,
    };
  }
  if (!props.monthlyAnalysisWorkbook) {
    return {
      status: "月度工作簿未返回",
      action: `重新读取 ${props.requestedReportMonth} 月度分析工作簿`,
      blockingDetail: "月度工作簿 payload 缺失",
      isTrusted: false,
    };
  }

  const workbookReportMonth = metaString(props.monthlyAnalysisWorkbook.report_month);
  if (workbookReportMonth !== props.requestedReportMonth) {
    const returnedMonth = workbookReportMonth ?? "缺失";
    return {
      status: `${props.requestedReportMonth}/${returnedMonth} 不一致`,
      action: `重新读取 ${props.requestedReportMonth} 月度分析工作簿`,
      blockingDetail: `月度工作簿请求 ${props.requestedReportMonth}，返回 ${returnedMonth}`,
      isTrusted: false,
    };
  }

  if (!props.monthlyAnalysisWorkbookMeta) {
    return {
      status: "月度工作簿 result_meta 缺失",
      action: "补齐月度工作簿来源版本、规则版本、缓存版本和表清单",
      blockingDetail: "月度工作簿 result_meta 缺失",
      isTrusted: false,
    };
  }
  const missingFields = missingSourceEvidenceFields("月度工作簿", props.monthlyAnalysisWorkbookMeta);
  if (missingFields.length > 0) {
    const detail = missingFields.join("；");
    return {
      status: "月度工作簿来源证据不完整",
      action: "补齐月度工作簿来源版本、规则版本、缓存版本和表清单",
      blockingDetail: detail,
      isTrusted: false,
    };
  }

  return {
    status: `${props.requestedReportMonth} 已匹配`,
    action: "月度分析工作簿已匹配",
    blockingDetail: null,
    isTrusted: true,
  };
}

function formatEvidenceRows(meta: ResultMeta | null | undefined) {
  return typeof meta?.evidence_rows === "number" ? String(meta.evidence_rows) : "缺失";
}

type LedgerFunctionalDrill = {
  key: string;
  label: string;
  detail: string;
};

function normalizeLedgerNextDrill(item: NonNullable<ResultMeta["next_drill"]>[number]): LedgerFunctionalDrill | null {
  if (typeof item === "string") {
    const label = item.trim();
    return label ? { key: label, label, detail: "" } : null;
  }
  if (typeof item !== "object" || item === null) {
    return null;
  }
  const label = typeof item.label === "string" ? item.label.trim() : "";
  const detail = typeof item.detail === "string" ? item.detail.trim() : "";
  if (!label && !detail) {
    return null;
  }
  return {
    key: `${label}|${detail}`,
    label: label || "补证动作",
    detail,
  };
}

function collectLedgerNextDrills(
  ...metas: Array<ResultMeta | null | undefined>
): LedgerFunctionalDrill[] {
  const seen = new Set<string>();
  const rows: LedgerFunctionalDrill[] = [];
  for (const meta of metas) {
    for (const item of meta?.next_drill ?? []) {
      const normalized = normalizeLedgerNextDrill(item);
      if (!normalized || seen.has(normalized.key)) {
        continue;
      }
      seen.add(normalized.key);
      rows.push(normalized);
      if (rows.length >= 3) {
        return rows;
      }
    }
  }
  return rows;
}

function formalContractRemediationDrill(
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined,
): LedgerFunctionalDrill | null {
  if (contract?.sample_status !== "missing_contract" || !contract.remediation?.action_label) {
    return null;
  }
  return {
    key: `formal-contract-remediation|${contract.remediation.action_label}`,
    label: contract.remediation.action_label,
    detail: contract.remediation.action_detail,
  };
}

function appendLedgerDrill(
  drills: LedgerFunctionalDrill[],
  drill: LedgerFunctionalDrill | null,
): LedgerFunctionalDrill[] {
  if (!drill || drills.some((row) => row.key === drill.key)) {
    return drills;
  }
  return [...drills, drill].slice(0, 3);
}

function focusLedgerFormalContractTarget(props: {
  requestedReportMonth?: string;
  formalIndicatorSourceContract?: LedgerPnlFormalFinancialIndicatorContractPayload;
}) {
  const { requestedReportMonth, formalIndicatorSourceContract } = props;
  if (!requestedReportMonth) {
    const reportDateSelect = document.getElementById(LEDGER_PNL_REPORT_DATE_SELECT_ID);
    reportDateSelect?.scrollIntoView?.({ block: "center", inline: "nearest" });
    reportDateSelect?.focus({ preventScroll: true });
    return;
  }
  const target =
    (registeredPendingReleaseGate(formalIndicatorSourceContract)
      ? document.getElementById(LEDGER_PNL_FORMAL_CONTRACT_RELEASE_GATE_ID)
      : null) ??
    document.getElementById(LEDGER_PNL_FORMAL_CONTRACT_MATERIAL_CHECKLIST_ID) ??
    document.getElementById(LEDGER_PNL_FORMAL_CONTRACT_PANEL_ID);

  target?.scrollIntoView?.({ block: "center", inline: "nearest" });
  target?.focus({ preventScroll: true });
}

function buildFormalContractMaterialChecklist(
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

function registeredPendingReleaseGate(
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

function hasEmptyFormalContractMetrics(
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined,
) {
  return Boolean(
    contract &&
      contract.sample_status !== "missing_contract" &&
      contract.formal_use_allowed !== true &&
      (contract.metrics?.length ?? 0) === 0,
  );
}

function formalContractExecutionStatus(props: {
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

function formalContractReadbackAction(props: {
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

function formalContractMaterialSummary(props: {
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

function formalContractRemediationConclusion(props: {
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

function shortFormalContractReadbackAction(action: string) {
  if (action === "补齐样本并登记后刷新页面或重新查询正式契约接口") {
    return "补齐样本并登记后刷新正式契约";
  }
  return action === "登记后刷新页面或重新查询正式契约接口" ? "登记后刷新正式契约" : action;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error ?? "");
}

function isForbiddenLedgerError(error: unknown) {
  const message = errorMessage(error);
  return message.includes("(403)") || message.includes("not allowed") || message.includes("403");
}

function summarizeFormalIndicatorContractGaps(
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

type LedgerFunctionalAuditProps = {
  selectedReportDate: string;
  selectedReportDateMissingFromDates: boolean;
  reportDates: string[];
  datesMeta: ResultMeta | null | undefined;
  analysisEnvelope: ApiEnvelope<LedgerPnlAnalysisPayload> | undefined;
  analysisError: unknown;
  requestedReportMonth: string;
  monthlyAnalysisWorkbook: QdbGlMonthlyAnalysisWorkbookPayload | undefined;
  monthlyAnalysisWorkbookMeta: ResultMeta | null | undefined;
  formalIndicatorSourceContract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined;
  hasMatchingAnalysisMonth: boolean;
  isMonthlyAnalysisDatesLoading: boolean;
  isMonthlyAnalysisDatesError: boolean;
  isMonthlyAnalysisWorkbookLoading: boolean;
  isMonthlyAnalysisWorkbookError: boolean;
  isFormalContractLoading: boolean;
  isFormalContractError: boolean;
  isDatesLoading: boolean;
  isDatesError: boolean;
  isAnalysisLoading: boolean;
  isAnalysisError: boolean;
  /** 对账区块尚未进入视口：月度工作簿与正式契约查询被视口门控，尚未发起。 */
  reconciliationDeferred: boolean;
};

/*
 * 后端状态枚举的中文呈现（DESIGN.md §7 一页一语域）。
 * 未登记的枚举原样透出，避免新状态被翻译层吞成已知值。
 */
const LEDGER_ANALYSIS_STATUS_COPY: Record<string, string> = {
  ready: "可用",
  no_data: "无数据",
};

const LEDGER_METRIC_STATUS_COPY: Record<string, string> = {
  candidate: "候选口径",
};

const LEDGER_BASIS_AVAILABILITY_COPY: Record<string, string> = {
  ready: "可用",
  no_data: "无数据",
};

function ledgerEnumCopy(value: string | null | undefined, dictionary: Record<string, string>) {
  const raw = String(value ?? "").trim();
  if (!raw) {
    return "未返回";
  }
  return dictionary[raw] ?? raw;
}

function buildLedgerAnalysisAuditState(props: LedgerFunctionalAuditProps) {
  const payload = props.analysisEnvelope?.result;
  const meta = props.analysisEnvelope?.result_meta;
  const requestedDate = props.selectedReportDate || "缺失";
  const resolvedDate = metaString(meta?.resolved_report_date) ?? payload?.report_date ?? "缺失";
  const asOfDate = metaString(meta?.as_of_date) ?? "缺失";
  const sourceVersion = metaString(meta?.source_version) ?? payload?.source_version ?? "缺失";
  const evidenceRows = formatEvidenceRows(meta);
  const analysisStatus = payload
    ? `${ledgerEnumCopy(payload.analysis_status, LEDGER_ANALYSIS_STATUS_COPY)} · ${ledgerEnumCopy(
        payload.metric_status,
        LEDGER_METRIC_STATUS_COPY,
      )}`
    : "未返回";
  const basisStatus = payload
    ? `${payload.currency_basis}；CNX ${ledgerEnumCopy(
        payload.basis_availability.CNX,
        LEDGER_BASIS_AVAILABILITY_COPY,
      )} / CNY ${ledgerEnumCopy(payload.basis_availability.CNY, LEDGER_BASIS_AVAILABILITY_COPY)}`
    : "未返回";
  const sourceRisk = collectSourceRiskSegments("候选分析", meta);
  const sourceStatus = sourceRisk.length > 0 ? sourceRisk.join("；") : "来源正常";
  const sourceAction = sourceRisk.length > 0 ? "先确认分析降级来源" : "来源状态正常";
  const evidenceIssues = meta
    ? [
        ...missingSourceEvidenceFields("候选分析", meta),
        meta.basis === "ledger" ? null : `basis=${meta.basis}`,
        meta.result_kind === "ledger_pnl.analysis" ? null : `result_kind=${meta.result_kind}`,
        meta.formal_use_allowed === false ? null : "formal_use_allowed 必须为 false",
        typeof meta.evidence_rows === "number" ? null : "evidence_rows 缺失",
      ].filter((item): item is string => Boolean(item))
    : props.analysisEnvelope
      ? ["候选分析 result_meta 缺失"]
      : [];
  const evidenceStatus = evidenceIssues.length > 0 ? evidenceIssues.join("；") : "分析证据完整";
  const evidenceAction = evidenceIssues.length > 0 ? "补齐 /analysis 契约与来源元数据" : "使用后端分析 DTO";
  const dateMismatch =
    props.selectedReportDate && resolvedDate !== "缺失" && resolvedDate !== props.selectedReportDate
      ? `请求 ${props.selectedReportDate}，解析 ${resolvedDate}`
      : null;
  const dateStatus = dateMismatch ? `解析回退：${dateMismatch}` : resolvedDate === "缺失" ? "解析报告日缺失" : "请求/解析一致";
  const dateAction = dateMismatch
    ? "恢复请求报告日对应源文件"
    : resolvedDate === "缺失"
      ? "补 resolved_report_date"
      : "报告日一致";
  const monthlyWorkbookState = monthlyWorkbookAuditState({
    requestedReportMonth: props.requestedReportMonth,
    hasMatchingAnalysisMonth: props.hasMatchingAnalysisMonth,
    isMonthlyAnalysisDatesLoading: props.isMonthlyAnalysisDatesLoading,
    isMonthlyAnalysisDatesError: props.isMonthlyAnalysisDatesError,
    isMonthlyAnalysisWorkbookLoading: props.isMonthlyAnalysisWorkbookLoading,
    isMonthlyAnalysisWorkbookError: props.isMonthlyAnalysisWorkbookError,
    monthlyAnalysisWorkbook: props.monthlyAnalysisWorkbook,
    monthlyAnalysisWorkbookMeta: props.monthlyAnalysisWorkbookMeta,
  });
  const formalUseAllowed = props.formalIndicatorSourceContract?.formal_use_allowed === true;
  const releaseGate = registeredPendingReleaseGate(props.formalIndicatorSourceContract);
  const emptyFormalContractMetrics = hasEmptyFormalContractMetrics(props.formalIndicatorSourceContract);
  const formalStatus = props.reconciliationDeferred
    ? "对账区块未加载"
    : !props.requestedReportMonth
    ? "等待报告月份"
    : props.isFormalContractLoading
      ? "正式契约读取中"
      : props.isFormalContractError
        ? "正式契约读取失败"
        : formalUseAllowed
          ? "正式值可用"
          : releaseGate
            ? "正式契约已登记，待放行"
            : emptyFormalContractMetrics
              ? "正式契约明细缺失，正式值不可用"
              : props.formalIndicatorSourceContract?.sample_status === "missing_contract"
                ? "正式契约缺失，正式值不可用"
                : "正式值不可用，仅作候选核对";
  const shared = {
    requestedDate,
    resolvedDate,
    asOfDate,
    sourceVersion,
    analysisStatus,
    basisStatus,
    sourceStatus,
    sourceAction,
    evidenceRows,
    evidenceStatus,
    evidenceAction,
    dateStatus,
    dateAction,
    monthlyAnalysisStatus: props.reconciliationDeferred
      ? "对账区块未加载"
      : monthlyWorkbookState.status,
    monthlyAnalysisAction: props.reconciliationDeferred
      ? "滚动到对账区或经章节导航进入后自动加载"
      : monthlyWorkbookState.action,
    formalStatus,
  };

  if (props.isAnalysisError) {
    const message = errorMessage(props.analysisError);
    return {
      tone: "warning",
      title: isForbiddenLedgerError(props.analysisError) ? "无权限读取候选分析" : "候选分析读取失败",
      detail: message || "本次不能形成候选总账分析判断。",
      ...shared,
    };
  }
  if (props.isDatesError) {
    return { tone: "warning", title: "报告日读取失败", detail: "无法确认候选分析报告日清单。", ...shared };
  }
  if (props.isDatesLoading || props.isAnalysisLoading) {
    return { tone: "pending", title: "候选分析读取中", detail: "等待 /api/ledger-pnl/analysis 返回。", ...shared };
  }
  if (props.reportDates.length === 0) {
    return { tone: "warning", title: "没有可选报告日", detail: "日期接口没有返回总账报告日。", ...shared };
  }
  if (!props.selectedReportDate) {
    return { tone: "warning", title: "缺少报告日", detail: "没有报告日就不能读取候选分析。", ...shared };
  }
  if (props.selectedReportDateMissingFromDates) {
    return { tone: "warning", title: "报告日未列入可选清单", detail: "请核对日期清单和源文件登记。", ...shared };
  }
  if (!props.analysisEnvelope || !payload || !meta) {
    return { tone: "warning", title: "候选分析响应缺失", detail: "未收到完整 /analysis envelope，不以 0 补齐。", ...shared };
  }
  if (payload.analysis_status === "no_data") {
    return { tone: "warning", title: "候选分析无数据", detail: "当前报告日与账务口径无分析数据，不解释为真实 0。", ...shared };
  }
  if (evidenceIssues.length > 0) {
    return { tone: "warning", title: "候选分析证据不完整", detail: evidenceStatus, ...shared };
  }
  if (dateMismatch || resolvedDate === "缺失") {
    return { tone: "warning", title: "候选分析报告日不可信", detail: dateMismatch ?? "解析报告日缺失。", ...shared };
  }
  if (sourceRisk.length > 0) {
    return { tone: "warning", title: "候选分析来源降级", detail: sourceStatus, ...shared };
  }
  if (formalUseAllowed) {
    return { tone: "ok", title: "正式财务指标可用", detail: "正式值由正式契约展示；候选分析仅保留为旁证。", ...shared };
  }
  if (props.reconciliationDeferred) {
    return {
      tone: "pending",
      title: "候选分析可用，对账区待加载",
      detail: "月度工作簿与正式契约在对账区块进入视口后加载；此前不形成正式指标结论。",
      ...shared,
    };
  }
  if (monthlyWorkbookState.blockingDetail && props.requestedReportMonth && props.hasMatchingAnalysisMonth) {
    return { tone: "warning", title: "候选分析可用，月度工作簿不可信", detail: monthlyWorkbookState.blockingDetail, ...shared };
  }
  if (props.isFormalContractLoading) {
    return { tone: "pending", title: "候选分析可用，正式契约读取中", detail: `后端分析证据 ${evidenceRows} 行；正式契约仍在读取。`, ...shared };
  }
  if (props.isFormalContractError) {
    return { tone: "warning", title: "候选分析可用，正式契约读取失败", detail: `后端分析证据 ${evidenceRows} 行；不能形成正式指标结论。`, ...shared };
  }
  if (emptyFormalContractMetrics) {
    return { tone: "warning", title: "候选分析可用，正式契约明细缺失", detail: "正式财务指标契约没有指标明细。", ...shared };
  }
  if (releaseGate) {
    return { tone: "warning", title: "正式财务指标已登记待放行", detail: releaseGate.blocking_reason?.trim() || "尚未满足正式放行条件。", ...shared };
  }
  if (props.requestedReportMonth && !props.isMonthlyAnalysisDatesLoading && !props.isMonthlyAnalysisDatesError && !props.hasMatchingAnalysisMonth) {
    return { tone: "warning", title: "候选分析可用，月度工作簿缺失", detail: `${props.requestedReportMonth} 月度分析工作簿未匹配。`, ...shared };
  }
  if (props.formalIndicatorSourceContract?.sample_status === "missing_contract") {
    return { tone: "warning", title: "候选分析可用，正式指标不可判定", detail: "正式财务指标契约缺失。", ...shared };
  }
  return { tone: "ok", title: "后端候选分析可用", detail: "候选业务结论以 /api/ledger-pnl/analysis 返回为准。", ...shared };
}

function LedgerFunctionalAuditStrip(props: LedgerFunctionalAuditProps) {
  const state = buildLedgerAnalysisAuditState(props);
  const analysisMeta = props.analysisEnvelope?.result_meta;
  const analysisPayload = props.analysisEnvelope?.result;
  const candidateReady = analysisPayload?.analysis_status === "ready";
  const candidateNextDrills = collectLedgerNextDrills(props.datesMeta, analysisMeta);
  const formalNextDrill = formalContractRemediationDrill(props.formalIndicatorSourceContract);
  const nextDrills = appendLedgerDrill(candidateNextDrills, formalNextDrill);
  const formalGapSummary = summarizeFormalIndicatorContractGaps(
    props.formalIndicatorSourceContract,
    props.isFormalContractLoading,
    props.isFormalContractError,
  );
  const materialChecklist = buildFormalContractMaterialChecklist(
    props.formalIndicatorSourceContract?.remediation,
  );
  const executionStatus = formalContractExecutionStatus({
    contract: props.formalIndicatorSourceContract,
    isLoading: props.isFormalContractLoading,
    isError: props.isFormalContractError,
    materialChecklist,
  });
  const readbackAction = formalContractReadbackAction({
    contract: props.formalIndicatorSourceContract,
    isLoading: props.isFormalContractLoading,
    isError: props.isFormalContractError,
    materialChecklist,
  });
  const formalConclusion = formalContractRemediationConclusion({
    contract: props.formalIndicatorSourceContract,
    isLoading: props.isFormalContractLoading,
    isError: props.isFormalContractError,
    materialChecklist,
    readbackAction,
  });
  const candidateEvidencePath = candidateNextDrills[0]?.label ?? (candidateReady ? "候选分析证据完整" : "等待分析证据");
  const candidateEvidenceSummary = `${analysisMeta?.result_kind ?? "ledger_pnl.analysis"} · evidence ${formatEvidenceRows(analysisMeta)}`;
  const formalEvidencePath = props.requestedReportMonth
    ? formalNextDrill?.label ?? shortFormalContractReadbackAction(readbackAction)
    : "先选择报告日生成 report_month";
  const formalEvidenceActionable =
    props.formalIndicatorSourceContract?.formal_use_allowed !== true;
  const materialSummary = formalContractMaterialSummary({
    contract: props.formalIndicatorSourceContract,
    isLoading: props.isFormalContractLoading,
    isError: props.isFormalContractError,
    materialChecklist,
  });
  return (
    <section
      data-testid="ledger-pnl-functional-audit-strip"
      className={`ledger-pnl-functional-strip ledger-pnl-functional-strip--${state.tone}`}
    >
      <div className="ledger-pnl-functional-strip__main">
        <div className="ledger-pnl-functional-strip__eyebrow">功能性审计</div>
        <h2 className="ledger-pnl-functional-strip__title">{state.title}</h2>
        <div className="ledger-pnl-functional-strip__detail">{state.detail}</div>
      </div>
      <div className="ledger-pnl-functional-strip__headline-facts">
        <div>
          <span>解析报告日</span>
          <strong>{state.resolvedDate}</strong>
        </div>
        <div>
          <span>数据截至日</span>
          <strong>{state.asOfDate}</strong>
        </div>
        <div>
          <span>分析证据行</span>
          <strong>{state.evidenceRows}</strong>
        </div>
        <div>
          <span>候选分析状态</span>
          <strong>{state.analysisStatus}</strong>
        </div>
        <div>
          <span>正式边界</span>
          <strong>{state.formalStatus}</strong>
        </div>
      </div>
      <details className="ledger-pnl-functional-strip__audit">
        <summary className="ledger-pnl-functional-strip__audit-summary">
          审计明细与判断链
        </summary>
        <div className="ledger-pnl-functional-strip__audit-body">
      <div className="ledger-pnl-functional-strip__facts">
        <div>
          <span>请求报告日</span>
          <strong>{state.requestedDate}</strong>
        </div>
        <div>
          <span>分析质量</span>
          <strong>{formatMetaQuality(analysisMeta)}</strong>
        </div>
        <div>
          <span>来源版本</span>
          <strong>{state.sourceVersion}</strong>
        </div>
        <div>
          <span>分析口径</span>
          <strong>{state.basisStatus}</strong>
        </div>
        <div>
          <span>报告日匹配</span>
          <strong>{state.dateStatus}</strong>
        </div>
        <div>
          <span>候选分析证据</span>
          <strong>{candidateEvidenceSummary}</strong>
        </div>
        <div>
          <span>来源状态</span>
          <strong>{state.sourceStatus}</strong>
        </div>
        <div>
          <span>来源证据</span>
          <strong>{state.evidenceStatus}</strong>
        </div>
        <div>
          <span>月度工作簿</span>
          <strong>{state.monthlyAnalysisStatus}</strong>
        </div>
        <div>
          <span>正式契约缺口</span>
          <strong>
            {formalGapSummary.label ??
              `正式待接入 ${formalGapSummary.formalPending} / QDB候选 ${formalGapSummary.qdbCandidateAligned} / 需对账 ${formalGapSummary.needsReconciliation}`}
          </strong>
        </div>
      </div>
      <div className="ledger-pnl-functional-strip__explainability">
        <span>候选分析审计</span>
        <div className="ledger-pnl-functional-strip__explainability-list">
          <strong>{state.analysisStatus}</strong>
          <em>{candidateEvidenceSummary}</em>
          <em>账务口径 {state.basisStatus}</em>
          <em>候选补证入口 {candidateEvidencePath}</em>
        </div>
      </div>
      <div data-testid="ledger-pnl-decision-path" className="ledger-pnl-functional-strip__decision-path">
        <span>判断链</span>
        <div className="ledger-pnl-functional-strip__decision-list">
          <div>
            <span>正式状态</span>
            <strong>{state.formalStatus}</strong>
          </div>
          <div>
            <span>候选分析状态</span>
            <strong>{state.analysisStatus}</strong>
          </div>
          <div>
            <span>候选补证路径</span>
            <strong>{candidateEvidencePath}</strong>
          </div>
          <div>
            <span>分析证据处理路径</span>
            <strong>{state.evidenceAction}</strong>
          </div>
          <div>
            <span>报告日处理路径</span>
            <strong>{state.dateAction}</strong>
          </div>
          <div>
            <span>来源处理路径</span>
            <strong>{state.sourceAction}</strong>
          </div>
          <div>
            <span>月度分析工作簿</span>
            <strong>{state.monthlyAnalysisStatus}</strong>
          </div>
          <div>
            <span>月度补证路径</span>
            <strong>{state.monthlyAnalysisAction}</strong>
          </div>
          <div>
            <span>正式补证路径</span>
            {formalEvidenceActionable ? (
              <button
                type="button"
                className="ledger-pnl-functional-strip__evidence-button"
                aria-label={`正式补证路径 ${formalEvidencePath}`}
                onClick={() =>
                  focusLedgerFormalContractTarget({
                    requestedReportMonth: props.requestedReportMonth,
                    formalIndicatorSourceContract: props.formalIndicatorSourceContract,
                  })
                }
              >
                {formalEvidencePath}
              </button>
            ) : (
              <strong>{formalEvidencePath}</strong>
            )}
          </div>
          <div>
            <span>正式补证结论</span>
            <strong>{formalConclusion}</strong>
          </div>
          <div>
            <span>材料完整性</span>
            <strong>{materialSummary}</strong>
          </div>
          <div>
            <span>执行状态</span>
            <strong>{executionStatus}</strong>
          </div>
          <div>
            <span>回读动作</span>
            <strong>{shortFormalContractReadbackAction(readbackAction)}</strong>
          </div>
        </div>
      </div>
      {nextDrills.length > 0 ? (
        <div className="ledger-pnl-functional-strip__drill">
          <span>下一步补证</span>
          <div className="ledger-pnl-functional-strip__drill-list">
            {nextDrills.map((drill) => (
              <div key={drill.key} className="ledger-pnl-functional-strip__drill-item">
                {drill.key.startsWith("formal-contract-remediation|") ? (
                  <button
                    type="button"
                    className="ledger-pnl-functional-strip__evidence-button"
                    aria-label={`下一步补证 ${drill.label}`}
                    onClick={() =>
                      focusLedgerFormalContractTarget({
                        requestedReportMonth: props.requestedReportMonth,
                        formalIndicatorSourceContract: props.formalIndicatorSourceContract,
                      })
                    }
                  >
                    {drill.label}
                  </button>
                ) : (
                  <strong>{drill.label}</strong>
                )}
                {drill.detail ? <em>{drill.detail}</em> : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
        </div>
      </details>
    </section>
  );
}

function reportDateToMonth(reportDate: string) {
  const match = /^(\d{4})-(\d{2})/.exec(reportDate.trim());
  return match ? `${match[1]}${match[2]}` : "";
}

function formatAnalysisValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  if (typeof value === "number") {
    return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
  }
  return String(value);
}

function findAnalysisSheet(
  sheets: QdbGlMonthlyAnalysisSheet[] | undefined,
  key: string,
) {
  return sheets?.find((sheet) => sheet.key === key);
}

type FinancialIndicatorStatusRow = {
  name: string;
  value: unknown;
  unit: string;
  status: string;
  source: string;
};

function textCell(row: Record<string, unknown>, column: string | undefined) {
  return column ? String(row[column] ?? "").trim() : "";
}

function buildFinancialIndicatorStatusRows(sheet: QdbGlMonthlyAnalysisSheet | undefined) {
  const columns = sheet?.columns ?? [];
  const nameColumn = columns.find((column) => column === "指标") ?? columns[0];
  const valueColumn = columns.find((column) => column === "当前值") ?? columns[1];
  const unitColumn = columns.find((column) => column === "单位") ?? columns[2];
  const statusColumn = columns.find((column) => column === "口径状态") ?? columns[3];
  const sourceColumn = columns.find((column) => column === "口径来源") ?? columns[4];

  return (sheet?.rows ?? [])
    .map((row): FinancialIndicatorStatusRow => ({
      name: textCell(row, nameColumn),
      value: valueColumn ? row[valueColumn] : undefined,
      unit: textCell(row, unitColumn),
      status: textCell(row, statusColumn),
      source: textCell(row, sourceColumn),
    }))
    .filter((row) => row.name);
}

function financialIndicatorTone(row: FinancialIndicatorStatusRow) {
  if (row.status.includes("QDB")) {
    return "analytical";
  }
  if (row.status.includes("待接入") || row.source.startsWith("formal_pending:")) {
    return "pending";
  }
  return "warning";
}

function formatFinancialIndicatorValue(row: FinancialIndicatorStatusRow) {
  if (row.value === null || row.value === undefined || row.value === "") {
    return "未接入";
  }
  const formatted = formatAnalysisValue(row.value);
  return row.unit && row.unit !== "待确认" ? `${formatted} ${row.unit}` : formatted;
}

function FinancialIndicatorStatusPanel(props: { rows: FinancialIndicatorStatusRow[] }) {
  const qdbCount = props.rows.filter((row) => financialIndicatorTone(row) === "analytical").length;
  const pendingCount = props.rows.filter((row) => financialIndicatorTone(row) === "pending").length;
  const sourceGapCount = props.rows.filter((row) => row.source.includes("source_missing") || row.source.includes("formal_pending")).length;

  return (
    <section data-testid="ledger-pnl-formal-indicator-status-panel" className="ledger-pnl-analysis__status-panel">
      <div className="ledger-pnl-analysis__status-header">
        <div>
          <h3 className="ledger-pnl-analysis__status-title">正式财务指标状态</h3>
          <div className="ledger-pnl-analysis__status-subtitle">
            展示后端月度工作簿返回的指标值、口径状态和来源缺口。
          </div>
        </div>
        <div className="ledger-pnl-analysis__status-summary">
          <span>QDB 可复算 {qdbCount}</span>
          <span>正式待接入 {pendingCount}</span>
          <span>缺口说明 {sourceGapCount}</span>
        </div>
      </div>
      {props.rows.length > 0 ? (
        <div className="ledger-pnl-analysis__status-list">
          {props.rows.map((row) => {
            const tone = financialIndicatorTone(row);
            return (
              <article
                key={row.name}
                className={`ledger-pnl-analysis__status-row ledger-pnl-analysis__status-row--${tone}`}
              >
                <div className="ledger-pnl-analysis__status-main">
                  <span className="ledger-pnl-analysis__status-name">{row.name}</span>
                  <span className="ledger-pnl-analysis__status-badge">{row.status || "口径待确认"}</span>
                </div>
                <div className="ledger-pnl-analysis__status-value">
                  {formatFinancialIndicatorValue(row)}
                </div>
                <div className="ledger-pnl-analysis__status-source">{row.source || "来源待确认"}</div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="ledger-pnl-analysis__empty">暂无财务指标状态数据</div>
      )}
    </section>
  );
}

const sourceStatusLabels = {
  formal_pending: "正式来源待接入",
  candidate_qdb_aligned: "QDB 候选对齐",
  needs_reconciliation: "需对账",
} as const;

function formalSourceContractTone(metric: LedgerPnlFormalFinancialIndicatorMetric) {
  if (metric.source_status === "candidate_qdb_aligned") {
    return "analytical";
  }
  if (metric.source_status === "formal_pending") {
    return "pending";
  }
  return "warning";
}

function formatContractMetricValue(value: string | number | null | undefined, unit: string) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return unit ? `${value} ${unit}` : String(value);
}

function formatFormalContractValue(value: string | number | null | undefined, unit: string) {
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

function contractActionTitle(metric: LedgerPnlFormalFinancialIndicatorMetric) {
  if (metric.source_status === "needs_reconciliation") {
    return "先对账 QDB 候选与 Excel 样本";
  }
  if (metric.source_status === "candidate_qdb_aligned") {
    return "候选已对齐，等待正式来源放行";
  }
  return "补正式财务指标来源";
}

function buildFormalContractActionQueue(metrics: LedgerPnlFormalFinancialIndicatorMetric[]) {
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

function buildFormalContractDecision(
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

function formatFormalContractNote(
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

function FormalIndicatorSourceContractPanel(props: {
  contract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined;
  requestedReportMonth: string;
  isLoading: boolean;
  isError: boolean;
}) {
  const metrics = props.contract?.metrics ?? [];
  const counts = {
    formal_pending: metrics.filter((metric) => metric.source_status === "formal_pending").length,
    candidate_qdb_aligned: metrics.filter((metric) => metric.source_status === "candidate_qdb_aligned").length,
    needs_reconciliation: metrics.filter((metric) => metric.source_status === "needs_reconciliation").length,
  };
  const decision = buildFormalContractDecision(props.contract, props.isLoading, props.isError);
  const contractNote = formatFormalContractNote(props.contract);
  const actionQueue = buildFormalContractActionQueue(metrics);
  const hasActionQueue = actionQueue.length > 0;
  const releaseGate = registeredPendingReleaseGate(props.contract);
  const materialChecklist = buildFormalContractMaterialChecklist(props.contract?.remediation);
  const executionStatus = formalContractExecutionStatus({
    contract: props.contract,
    isLoading: props.isLoading,
    isError: props.isError,
    materialChecklist,
  });
  const readbackAction = formalContractReadbackAction({
    contract: props.contract,
    isLoading: props.isLoading,
    isError: props.isError,
    materialChecklist,
  });

  return (
    <section
      id={LEDGER_PNL_FORMAL_CONTRACT_PANEL_ID}
      data-testid="ledger-pnl-formal-indicator-source-contract-panel"
      tabIndex={-1}
      className="ledger-pnl-analysis__status-panel ledger-pnl-analysis__status-panel--source-contract"
    >
      <div className="ledger-pnl-analysis__status-header">
        <div>
          <h3 className="ledger-pnl-analysis__status-title">正式财务指标源契约</h3>
          <div className="ledger-pnl-analysis__status-subtitle">
            Excel 样本值、系统候选值与正式展示值分列；正式值没有来源时保持未接入。
          </div>
        </div>
        <div className="ledger-pnl-analysis__status-summary">
          <span>report_month {props.contract?.report_month || props.requestedReportMonth || "-"}</span>
          <span>sample_status {props.contract?.sample_status ?? "-"}</span>
          <span>formal_use_allowed={String(props.contract?.formal_use_allowed ?? false)}</span>
          <span>formal_pending {counts.formal_pending}</span>
          <span>candidate_qdb_aligned {counts.candidate_qdb_aligned}</span>
          <span>needs_reconciliation {counts.needs_reconciliation}</span>
        </div>
      </div>

      <div
        data-testid="ledger-pnl-formal-indicator-source-contract-decision"
        className={`ledger-pnl-analysis__source-contract-decision ledger-pnl-analysis__source-contract-decision--${decision.tone}`}
      >
        <strong>{decision.title}</strong>
        <span>{decision.detail}</span>
      </div>

      {contractNote ? (
        <div className="ledger-pnl-analysis__source-contract-note">{contractNote}</div>
      ) : null}

      {releaseGate ? (
        <div
          id={LEDGER_PNL_FORMAL_CONTRACT_RELEASE_GATE_ID}
          data-testid="ledger-pnl-formal-indicator-source-contract-release-gate"
          tabIndex={-1}
          className="ledger-pnl-analysis__source-contract-release-gate"
        >
          <strong>release_gate {releaseGate.status}</strong>
          {releaseGate.blocking_reason ? <span>{releaseGate.blocking_reason}</span> : null}
          {releaseGate.required_evidence?.length ? (
            <div>
              <span>required_evidence</span>
              {releaseGate.required_evidence.map((item) => (
                <small key={item}>{item}</small>
              ))}
            </div>
          ) : null}
          {releaseGate.readback_action ? (
            <small>readback_action {releaseGate.readback_action}</small>
          ) : null}
        </div>
      ) : null}

      {props.isLoading ? (
        <div className="ledger-pnl-analysis__empty">正式财务指标源契约读取中</div>
      ) : props.isError ? (
        <div className="ledger-pnl-analysis__empty">正式财务指标源契约读取失败</div>
      ) : metrics.length > 0 ? (
        <>
          {hasActionQueue ? (
            <div
              data-testid="ledger-pnl-formal-indicator-source-contract-action-queue"
              className="ledger-pnl-analysis__source-contract-actions"
            >
              <div className="ledger-pnl-analysis__source-contract-actions-header">
                <strong>下一步核账队列</strong>
                <span>先处理有系统候选但未对齐的项目，再补正式来源。</span>
              </div>
              <div className="ledger-pnl-analysis__source-contract-action-list">
                {actionQueue.map((metric, index) => (
                  <article
                    key={metric.metric_key}
                    data-testid={`ledger-pnl-formal-indicator-source-contract-action-item-${metric.metric_key}`}
                    className="ledger-pnl-analysis__source-contract-action-item"
                  >
                    <strong>{index + 1}</strong>
                    <div>
                      <span>{metric.metric_name}</span>
                      <em>{contractActionTitle(metric)}</em>
                      <small>
                        Excel {formatContractMetricValue(metric.excel_value, metric.unit)} / 系统候选值{" "}
                        {formatContractMetricValue(metric.system_value, metric.unit)}
                      </small>
                      {metric.reconciliation_gap ? (
                        <small>对账差异 {formatContractMetricValue(metric.reconciliation_gap, metric.unit)}</small>
                      ) : null}
                      <small>{metric.cell_ref}</small>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          <div className="ledger-pnl-analysis__source-contract-list">
            {metrics.map((metric) => {
              const tone = formalSourceContractTone(metric);
              return (
                <article
                  key={metric.metric_key}
                  data-testid={`ledger-pnl-formal-indicator-source-contract-row-${metric.metric_key}`}
                  className={`ledger-pnl-analysis__status-row ledger-pnl-analysis__status-row--${tone}`}
                >
                  <div className="ledger-pnl-analysis__status-main">
                    <span className="ledger-pnl-analysis__status-name">{metric.metric_name}</span>
                    <span className="ledger-pnl-analysis__status-badge">
                      {metric.source_status}
                    </span>
                  </div>
                  <div className="ledger-pnl-analysis__source-contract-status">
                    {sourceStatusLabels[metric.source_status]}
                  </div>
                  <div className="ledger-pnl-analysis__source-contract-values">
                    <div>
                      <span>正式展示值</span>
                      <strong>{formatFormalContractValue(metric.value, metric.unit)}</strong>
                    </div>
                    <div>
                      <span>Excel 样本值</span>
                      <strong>{formatContractMetricValue(metric.excel_value, metric.unit)}</strong>
                    </div>
                    <div>
                      <span>系统候选值</span>
                      <strong>{formatContractMetricValue(metric.system_value, metric.unit)}</strong>
                    </div>
                  </div>
                  {metric.reconciliation_gap ? (
                    <div className="ledger-pnl-analysis__source-contract-gap">
                      对账差异 {metric.reconciliation_gap}
                    </div>
                  ) : null}
                  <div className="ledger-pnl-analysis__status-source">{metric.missing_reason}</div>
                  <div className="ledger-pnl-analysis__source-contract-ref">{metric.cell_ref}</div>
                </article>
              );
            })}
          </div>
        </>
      ) : props.contract?.sample_status === "missing_contract" ? (
        <div className="ledger-pnl-analysis__source-contract-actions">
          <div className="ledger-pnl-analysis__source-contract-actions-header">
            <strong>缺契约补证动作</strong>
            <span>
              {props.contract.remediation?.action_label ??
                `登记 ${props.contract.report_month || props.requestedReportMonth || "-"} 正式财务指标契约`}
            </span>
          </div>
          <div className="ledger-pnl-analysis__source-contract-action-list">
            <article className="ledger-pnl-analysis__source-contract-action-item">
              <strong>1</strong>
              <div>
                <span>
                  {props.contract.remediation?.action_detail ??
                    "从 Excel 正式样本冻结 source contract，再重新核对 QDB 候选值。"}
                </span>
                <div
                  id={LEDGER_PNL_FORMAL_CONTRACT_MATERIAL_CHECKLIST_ID}
                  data-testid="ledger-pnl-formal-indicator-source-contract-material-checklist"
                  tabIndex={-1}
                  className="ledger-pnl-analysis__source-contract-material-checklist"
                >
                  <strong>{materialChecklist.summary}</strong>
                  {materialChecklist.rows.map((row) => (
                    <small key={row.key}>
                      <span>{row.label}</span>
                      {row.value || "待补"}
                    </small>
                  ))}
                  <small>
                    <span>执行状态</span>
                    {executionStatus}
                  </small>
                  <small>
                    <span>回读动作</span>
                    {readbackAction}
                  </small>
                </div>
                <small>正式值保持未接入，不能用分析候选值补齐。</small>
              </div>
            </article>
          </div>
        </div>
      ) : (
        <div className="ledger-pnl-analysis__empty">暂无正式财务指标源契约数据</div>
      )}
    </section>
  );
}

function ruleCheckBadgeTone(status: string) {
  if (status === "matched" || status === "exact" || status === "pass") {
    return "ok";
  }
  if (status === "mismatch" || status === "fail") {
    return "danger";
  }
  return "neutral";
}

function formatRuleCheckValue(value: string | number | null | undefined, unit: string) {
  return formatContractMetricValue(value, unit);
}

function RatioRecomputationTable(props: { rows: LedgerPnlRatioRecomputationCheck[] }) {
  if (props.rows.length === 0) {
    return <div className="ledger-pnl-analysis__empty">暂无比率复算检查</div>;
  }
  return (
    <table className="ledger-pnl-analysis__residual-table">
      <thead>
        <tr>
          <th>指标</th>
          <th>契约值</th>
          <th>复算值</th>
          <th>差异</th>
          <th>状态</th>
          <th>说明</th>
        </tr>
      </thead>
      <tbody>
        {props.rows.map((row) => (
          <tr key={row.check_key} data-testid={`ledger-pnl-rule-checks-ratio-row-${row.check_key}`}>
            <td>{row.metric_name}</td>
            <td>{formatRuleCheckValue(row.contract_value, row.unit)}</td>
            <td>{formatRuleCheckValue(row.recomputed_value, row.unit)}</td>
            <td>{formatRuleCheckValue(row.diff, row.unit)}</td>
            <td>
              <span
                className={`ledger-pnl-analysis__status-badge ledger-pnl-analysis__status-badge--${ruleCheckBadgeTone(row.status)}`}
              >
                {row.status}
              </span>
            </td>
            <td>
              {row.status === "insufficient_inputs" && row.missing_inputs?.length
                ? `缺失输入：${row.missing_inputs.join("；")}`
                : row.note ?? "-"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AdditivityChecksTable(props: { rows: LedgerPnlAdditivityCheck[] }) {
  if (props.rows.length === 0) {
    return <div className="ledger-pnl-analysis__empty">暂无合并勾稽检查</div>;
  }
  return (
    <table className="ledger-pnl-analysis__residual-table">
      <thead>
        <tr>
          <th>勾稽项</th>
          <th>总额</th>
          <th>分项合计</th>
          <th>残差</th>
          <th>状态</th>
          <th>说明</th>
        </tr>
      </thead>
      <tbody>
        {props.rows.map((row) => (
          <tr key={row.check_key} data-testid={`ledger-pnl-rule-checks-additivity-row-${row.check_key}`}>
            <td>{row.metric_name}</td>
            <td>{formatRuleCheckValue(row.total_value, row.unit)}</td>
            <td>{formatRuleCheckValue(row.components_sum, row.unit)}</td>
            <td>{formatRuleCheckValue(row.residual, row.unit)}</td>
            <td>
              <span
                className={`ledger-pnl-analysis__status-badge ledger-pnl-analysis__status-badge--${ruleCheckBadgeTone(row.status)}`}
              >
                {row.status}
              </span>
            </td>
            <td>{row.status === "residual_present" ? row.note ?? "残差需在正式来源接入时解释" : "分项合计与总额一致"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function arrangementRuleDetail(rule: LedgerPnlArrangementRule) {
  if (rule.status === "insufficient_inputs" && rule.missing_inputs?.length) {
    return `缺失输入：${rule.missing_inputs.join("；")}`;
  }
  if (rule.status === "pass" || rule.status === "fail") {
    return `实际值 ${rule.actual_value ?? "-"}${rule.unit ?? ""} ${rule.comparator ?? "<="} 目标值 ${rule.target_value ?? "-"}${rule.unit ?? ""}（${rule.quarter_end_type ?? "-"}）`;
  }
  if (rule.status === "informational") {
    return `管理层测算假设：${rule.assumption_value ?? "-"}${rule.assumption_unit ?? ""}。${rule.note ?? ""}`;
  }
  if (rule.status === "summary") {
    return `引用勾稽 ${rule.referenced_additivity_check_keys?.join("、") ?? "-"}；exact ${rule.exact_count ?? 0} / residual_present ${rule.residual_present_count ?? 0}`;
  }
  return rule.note ?? "-";
}

function ArrangementRulesList(props: { rows: LedgerPnlArrangementRule[] }) {
  if (props.rows.length === 0) {
    return <div className="ledger-pnl-analysis__empty">暂无安排规则检查</div>;
  }
  return (
    <div className="ledger-pnl-analysis__status-list">
      {props.rows.map((rule) => (
        <article
          key={rule.rule_key}
          data-testid={`ledger-pnl-rule-checks-arrangement-row-${rule.rule_key}`}
          className="ledger-pnl-analysis__status-row"
        >
          <div className="ledger-pnl-analysis__status-main">
            <span className="ledger-pnl-analysis__status-name">{rule.rule_name}</span>
            <span
              className={`ledger-pnl-analysis__status-badge ledger-pnl-analysis__status-badge--${ruleCheckBadgeTone(rule.status)}`}
            >
              {rule.status}
            </span>
          </div>
          <div className="ledger-pnl-analysis__status-source">{arrangementRuleDetail(rule)}</div>
          <div className="ledger-pnl-analysis__source-contract-ref">{rule.source_ref}</div>
        </article>
      ))}
    </div>
  );
}

function FormalIndicatorRuleChecksPanel(props: {
  ruleChecks: LedgerPnlFormalIndicatorRuleChecksPayload | undefined;
  requestedReportMonth: string;
  isLoading: boolean;
  isError: boolean;
}) {
  const { ruleChecks, requestedReportMonth, isLoading, isError } = props;
  const summary = ruleChecks?.summary;

  return (
    <section
      id={LEDGER_PNL_RULE_CHECKS_PANEL_ID}
      data-testid="ledger-pnl-formal-indicator-rule-checks-panel"
      tabIndex={-1}
      className="ledger-pnl-analysis__status-panel"
    >
      <div className="ledger-pnl-analysis__status-header">
        <div>
          <h3 className="ledger-pnl-analysis__status-title">规则符合性检查</h3>
          <div className="ledger-pnl-analysis__status-subtitle">
            对冻结契约值做比率复算、合并勾稽与管理安排规则校验；仅用于契约分析核对，不产生新的正式指标值。
          </div>
        </div>
        <div className="ledger-pnl-analysis__status-summary">
          <span>report_month {ruleChecks?.report_month || requestedReportMonth || "-"}</span>
          <span>formal_use_allowed={String(ruleChecks?.formal_use_allowed ?? false)}</span>
          <span>sample_status {ruleChecks?.sample_status ?? "-"}</span>
          {summary ? (
            <>
              <span>比率复算 {summary.ratio_recomputation.matched}/{summary.ratio_recomputation.total} matched</span>
              <span>勾稽 {summary.additivity_checks.exact}/{summary.additivity_checks.total} exact</span>
              <span>安排规则 {summary.arrangement_rules.pass}/{summary.arrangement_rules.total} pass</span>
            </>
          ) : null}
        </div>
      </div>

      {isLoading ? (
        <div className="ledger-pnl-analysis__empty">规则符合性检查读取中</div>
      ) : isError ? (
        <div className="ledger-pnl-analysis__empty">规则符合性检查读取失败</div>
      ) : !ruleChecks || ruleChecks.sample_status === "missing_contract" ? (
        <div
          data-testid="ledger-pnl-rule-checks-missing-contract"
          className="ledger-pnl-analysis__source-contract-actions"
        >
          <div className="ledger-pnl-analysis__source-contract-actions-header">
            <strong>
              {(ruleChecks?.report_month || requestedReportMonth || "本月")} 正式契约缺失，无法执行规则检查
            </strong>
            <span>{ruleChecks?.contract_note ?? "后台未登记该月正式财务指标契约，规则符合性检查无法执行。"}</span>
          </div>
          {ruleChecks?.remediation ? (
            <div className="ledger-pnl-analysis__source-contract-action-list">
              <article className="ledger-pnl-analysis__source-contract-action-item">
                <strong>1</strong>
                <div>
                  <span>{ruleChecks.remediation.action_label}</span>
                  <small>{ruleChecks.remediation.action_detail}</small>
                  <small>登记入口 {ruleChecks.remediation.registration_target}</small>
                  <small>验证 {ruleChecks.remediation.verification}</small>
                </div>
              </article>
            </div>
          ) : null}
        </div>
      ) : (
        <>
          <div className="ledger-pnl-analysis__table ledger-pnl-analysis__residual-table-wrap">
            <div className="ledger-pnl-analysis__table-title">比率复算</div>
            <RatioRecomputationTable rows={ruleChecks.ratio_recomputation} />
          </div>

          <div className="ledger-pnl-analysis__table ledger-pnl-analysis__residual-table-wrap">
            <div className="ledger-pnl-analysis__table-title">合并勾稽</div>
            <AdditivityChecksTable rows={ruleChecks.additivity_checks} />
          </div>

          <div className="ledger-pnl-analysis__table ledger-pnl-analysis__residual-table-wrap">
            <div className="ledger-pnl-analysis__table-title">管理安排规则</div>
            <ArrangementRulesList rows={ruleChecks.arrangement_rules} />
          </div>
        </>
      )}
    </section>
  );
}

export default function LedgerPnlPage() {
  const client = useApiClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedContributor, setSelectedContributor] = useState<LedgerPnlContributorSelection | null>(null);
  const [detailAccountFilter, setDetailAccountFilter] = useState<LedgerPnlContributorSelection | null>(null);
  const detailTableRef = useRef<HTMLDivElement>(null);
  const reportDateFromQuery = searchParams.get("report_date")?.trim() ?? "";
  const currencyFromQuery = searchParams.get("currency")?.trim() ?? "";
  const currency = normalizeLedgerPnlCurrencyBasis(currencyFromQuery);

  const datesQuery = useQuery({
    queryKey: ["ledger-pnl", "dates", client.mode],
    queryFn: () => client.getLedgerPnlDates(),
    retry: false,
  });

  const reportDates = useMemo(() => datesQuery.data?.result.dates ?? [], [datesQuery.data?.result.dates]);
  const selectedReportDate = reportDateFromQuery || reportDates[0] || "";

  const summaryQuery = useQuery({
    queryKey: ["ledger-pnl", "summary", client.mode, selectedReportDate, currency],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getLedgerPnlSummary(selectedReportDate, currency),
    retry: false,
  });

  const dataQuery = useQuery({
    queryKey: ["ledger-pnl", "data", client.mode, selectedReportDate, currency],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getLedgerPnlData(selectedReportDate, currency),
    retry: false,
  });

  const analysisQuery = useQuery({
    queryKey: ["ledger-pnl", "analysis", client.mode, selectedReportDate, currency],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getLedgerPnlAnalysis(selectedReportDate, currency),
    retry: false,
  });

  const monthlyAnalysisDatesQuery = useQuery({
    queryKey: ["ledger-pnl", "monthly-analysis", "dates", client.mode],
    queryFn: () => client.getLedgerPnlMonthlyAnalysisDates(),
    retry: false,
  });

  const summary = summaryQuery.data?.result;
  const data = dataQuery.data?.result;
  const accountSummaryRows = useMemo(() => summary?.by_account ?? [], [summary?.by_account]);
  const visibleAccountSummaryRows = useMemo(
    () => sortLedgerRowsByAbsYuan(accountSummaryRows, (item) => item.total_pnl),
    [accountSummaryRows],
  );
  const detailRows = useMemo(() => data?.items ?? [], [data?.items]);
  const filteredDetailRows = useMemo(
    () => detailAccountFilter
      ? detailRows.filter((item) => item.account_code === detailAccountFilter.account_code)
      : detailRows,
    [detailAccountFilter, detailRows],
  );
  const visibleDetailRows = useMemo(
    () => sortLedgerRowsByAbsYuan(filteredDetailRows, (item) => item.monthly_pnl),
    [filteredDetailRows],
  );
  /*
   * 明细区块头的后端汇总位：/data 已返回本口径合计与行数，页面此前只消费了 items。
   * no_data 时后端把金额补成 0，所以按 data_status 显式收敛为不展示，避免把补零当真零；
   * 科目筛选生效时也不展示，避免全量合计与筛选后的表体互相矛盾。
   */
  const detailSummaryNote = useMemo(() => {
    if (!data || data.data_status === "no_data" || detailAccountFilter) {
      return undefined;
    }
    const total = formatMoney(data.summary?.total_pnl);
    const count = data.summary?.count;
    if (total === EM_DASH || typeof count !== "number") {
      return undefined;
    }
    return `合计 ${total} · ${count} 行`;
  }, [data, detailAccountFilter]);

  const accountSummaryColumns = useMemo<
    LedgerPnlDataTableColumn<(typeof visibleAccountSummaryRows)[number]>[]
  >(
    () => [
      {
        key: "account",
        header: "科目",
        searchValue: (item) => `${item.account_code} ${item.account_name}`,
        sortValue: (item) => item.account_code,
        render: (item) => (
          <>
            <div>{item.account_code}</div>
            <div className="ledger-pnl-table__td-sub">{item.account_name}</div>
          </>
        ),
      },
      {
        key: "total_pnl",
        header: "损益",
        numeric: true,
        sortValue: (item) => ledgerMoneyYuan(item.total_pnl),
        render: (item) => formatMoney(item.total_pnl),
      },
      {
        key: "count",
        header: "笔数",
        numeric: true,
        sortValue: (item) => item.count,
        render: (item) => item.count,
      },
    ],
    [],
  );

  const detailColumns = useMemo<
    LedgerPnlDataTableColumn<(typeof visibleDetailRows)[number]>[]
  >(
    () => [
      {
        key: "account_code",
        header: "科目代码",
        searchValue: (item) => item.account_code,
        sortValue: (item) => item.account_code,
        render: (item) => item.account_code,
      },
      {
        key: "account_name",
        header: "科目名称",
        searchValue: (item) => item.account_name,
        sortValue: (item) => item.account_name,
        render: (item) => item.account_name,
      },
      {
        key: "currency",
        header: "币种",
        sortValue: (item) => item.currency,
        render: (item) => item.currency,
      },
      {
        key: "beginning_balance",
        header: "期初",
        numeric: true,
        sortValue: (item) => ledgerMoneyYuan(item.beginning_balance),
        render: (item) => formatMoney(item.beginning_balance),
      },
      {
        key: "ending_balance",
        header: "期末",
        numeric: true,
        sortValue: (item) => ledgerMoneyYuan(item.ending_balance),
        render: (item) => formatMoney(item.ending_balance),
      },
      {
        key: "monthly_pnl",
        header: "月损益",
        numeric: true,
        sortValue: (item) => ledgerMoneyYuan(item.monthly_pnl),
        render: (item) => formatMoney(item.monthly_pnl),
      },
      {
        key: "daily_avg_balance",
        header: "月日均",
        numeric: true,
        sortValue: (item) => ledgerMoneyYuan(item.daily_avg_balance),
        render: (item) => formatMoney(item.daily_avg_balance),
      },
      {
        key: "days_in_period",
        header: "天数",
        numeric: true,
        sortValue: (item) => item.days_in_period,
        render: (item) => item.days_in_period,
      },
    ],
    [],
  );

  const locateContributorInDetail = (selection: LedgerPnlContributorSelection) => {
    setDetailAccountFilter(selection);
    detailTableRef.current?.scrollIntoView({ block: "start", inline: "nearest" });
    detailTableRef.current?.focus({ preventScroll: true });
  };
  const monthlyAnalysisMonths = monthlyAnalysisDatesQuery.data?.result.report_months ?? [];
  const requestedAnalysisMonth = reportDateToMonth(selectedReportDate);
  const selectedReportDateMissingFromDates =
    Boolean(selectedReportDate) &&
    !datesQuery.isLoading &&
    reportDates.length > 0 &&
    !reportDates.includes(selectedReportDate);
  const hasMatchingAnalysisMonth =
    Boolean(requestedAnalysisMonth) && monthlyAnalysisMonths.includes(requestedAnalysisMonth);
  const selectedAnalysisMonth = hasMatchingAnalysisMonth ? requestedAnalysisMonth : "";

  /*
   * 视口门控：三个重区块（经营指标 / 候选指标 / 对账与日均）进入视口才发起查询，
   * 首屏只保留 dates/summary/data/analysis 与轻量的月度日期清单。
   * 兜底延时取 0：jsdom（无 IntersectionObserver）里一个宏任务后即视为可见，
   * 现有页面级集成测试的 waitFor 足以覆盖，无需逐条改造。
   * seen 一旦为 true 不再回退，区块挂载后的行为与门控前完全一致。
   */
  const indicatorsSection = useDeferredSectionSeen<HTMLDivElement>(true, 0);
  const candidateSection = useDeferredSectionSeen<HTMLDivElement>(true, 0);
  const reconciliationSection = useDeferredSectionSeen<HTMLElement>(true, 0);

  const formalIndicatorSourceContractQuery = useQuery({
    queryKey: ["ledger-pnl", "formal-financial-indicators", client.mode, requestedAnalysisMonth],
    enabled: reconciliationSection.seen && Boolean(requestedAnalysisMonth),
    queryFn: () => client.getLedgerPnlFormalFinancialIndicators(requestedAnalysisMonth),
    retry: false,
  });

  const formalIndicatorRuleChecksQuery = useQuery({
    queryKey: ["ledger-pnl", "formal-indicator-rule-checks", client.mode, requestedAnalysisMonth],
    enabled: reconciliationSection.seen && Boolean(requestedAnalysisMonth),
    queryFn: () => client.getLedgerPnlFormalIndicatorRuleChecks(requestedAnalysisMonth),
    retry: false,
  });

  const monthlyAnalysisWorkbookQuery = useQuery({
    queryKey: ["ledger-pnl", "monthly-analysis", "workbook", client.mode, selectedAnalysisMonth],
    enabled: reconciliationSection.seen && hasMatchingAnalysisMonth,
    queryFn: () => client.getLedgerPnlMonthlyAnalysisWorkbook({ reportMonth: selectedAnalysisMonth }),
    retry: false,
  });

  const monthlyAnalysisWorkbook = monthlyAnalysisWorkbookQuery.data?.result;
  const formalIndicatorSourceContract = formalIndicatorSourceContractQuery.data?.result;
  const formalIndicatorRuleChecks = formalIndicatorRuleChecksQuery.data?.result;
  const monthlyWorkbookState = monthlyWorkbookAuditState({
    requestedReportMonth: requestedAnalysisMonth,
    hasMatchingAnalysisMonth,
    isMonthlyAnalysisDatesLoading: monthlyAnalysisDatesQuery.isLoading,
    isMonthlyAnalysisDatesError: monthlyAnalysisDatesQuery.isError,
    isMonthlyAnalysisWorkbookLoading: monthlyAnalysisWorkbookQuery.isLoading,
    isMonthlyAnalysisWorkbookError: monthlyAnalysisWorkbookQuery.isError,
    monthlyAnalysisWorkbook,
    monthlyAnalysisWorkbookMeta: monthlyAnalysisWorkbookQuery.data?.result_meta,
  });
  const trustedMonthlyAnalysisWorkbook = monthlyWorkbookState.isTrusted ? monthlyAnalysisWorkbook : undefined;
  const overviewSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "overview");
  const financialIndicatorStatusSheet = findAnalysisSheet(
    trustedMonthlyAnalysisWorkbook?.sheets,
    "financial_indicator_status",
  );
  const financialIndicatorStatusRows = useMemo(
    () => buildFinancialIndicatorStatusRows(financialIndicatorStatusSheet),
    [financialIndicatorStatusSheet],
  );
  const summary3dSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "summary_3d");
  const assetStructureSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "asset_structure");
  const liabilityStructureSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "liability_structure");
  const loanIndustrySheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "loan_industry");
  const depositDemandIndustrySheet = findAnalysisSheet(
    trustedMonthlyAnalysisWorkbook?.sheets,
    "deposit_demand_industry",
  );
  const depositTermIndustrySheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "deposit_term_industry");
  const top11dSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "top_11d");
  const alertsSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "alerts");
  const foreignCurrencySheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "foreign_currency");
  const segmentBaseScaleSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "segment_base_scale");
  const segmentScaleCompareSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "segment_scale_compare");
  const companyScaleSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "company_scale");
  const companyScaleCompareSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "company_scale_compare");
  const retailScaleSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "retail_scale");
  const retailScaleCompareSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "retail_scale_compare");
  const financialMarketScaleSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "financial_market_scale");
  const financialMarketScaleCompareSheet = findAnalysisSheet(
    trustedMonthlyAnalysisWorkbook?.sheets,
    "financial_market_scale_compare",
  );
  const incomeRateAnalysisSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "income_rate_analysis");
  const incomeRateAttributionSheet = findAnalysisSheet(
    trustedMonthlyAnalysisWorkbook?.sheets,
    "income_rate_attribution",
  );
  const depositInterestSplitSheet = findAnalysisSheet(
    trustedMonthlyAnalysisWorkbook?.sheets,
    "deposit_interest_split",
  );
  const parentCompanyRevenueSheet = findAnalysisSheet(
    trustedMonthlyAnalysisWorkbook?.sheets,
    "parent_company_revenue_components",
  );
  const industryGapSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "industry_gap");
  const monthlyWorkbookGroups = useMemo(() => {
    const specs: LedgerPnlWorkbookTableSpec[] = [
      { title: "财务指标落地状态", sheet: financialIndicatorStatusSheet, testId: "ledger-pnl-monthly-analysis-financial-indicator-status", columnLimit: 5, rowLimit: 20 },
      { title: "3位科目总览", sheet: summary3dSheet, testId: "ledger-pnl-monthly-analysis-summary-3d", columnLimit: 8, rowLimit: 8 },
      { title: "资产结构", sheet: assetStructureSheet, testId: "ledger-pnl-monthly-analysis-asset-structure", columnLimit: 6, rowLimit: 8 },
      { title: "负债结构", sheet: liabilityStructureSheet, testId: "ledger-pnl-monthly-analysis-liability-structure", columnLimit: 6, rowLimit: 8 },
      { title: "贷款行业", sheet: loanIndustrySheet, testId: "ledger-pnl-monthly-analysis-loan-industry", columnLimit: 7, rowLimit: 8 },
      { title: "存款行业_活期", sheet: depositDemandIndustrySheet, testId: "ledger-pnl-monthly-analysis-deposit-demand-industry", columnLimit: 7, rowLimit: 8 },
      { title: "存款行业_定期", sheet: depositTermIndustrySheet, testId: "ledger-pnl-monthly-analysis-deposit-term-industry", columnLimit: 7, rowLimit: 8 },
      { title: "11位偏离TOP", sheet: top11dSheet, testId: "ledger-pnl-monthly-analysis-top-11d", columnLimit: 5 },
      { title: "异动预警", sheet: alertsSheet, testId: "ledger-pnl-monthly-analysis-alerts", columnLimit: 5 },
      { title: "分部基础规模", sheet: segmentBaseScaleSheet, testId: "ledger-pnl-monthly-analysis-segment-base-scale", columnLimit: 5 },
      { title: "分部规模同比环比", sheet: segmentScaleCompareSheet, testId: "ledger-pnl-monthly-analysis-segment-scale-compare", columnLimit: 7 },
      { title: "公司规模", sheet: companyScaleSheet, testId: "ledger-pnl-monthly-analysis-company-scale", columnLimit: 5 },
      { title: "公司规模同比环比", sheet: companyScaleCompareSheet, testId: "ledger-pnl-monthly-analysis-company-scale-compare", columnLimit: 7 },
      { title: "零售规模", sheet: retailScaleSheet, testId: "ledger-pnl-monthly-analysis-retail-scale", columnLimit: 5 },
      { title: "零售规模同比环比", sheet: retailScaleCompareSheet, testId: "ledger-pnl-monthly-analysis-retail-scale-compare", columnLimit: 7 },
      { title: "金融市场规模", sheet: financialMarketScaleSheet, testId: "ledger-pnl-monthly-analysis-financial-market-scale", columnLimit: 5 },
      { title: "金融市场规模同比环比", sheet: financialMarketScaleCompareSheet, testId: "ledger-pnl-monthly-analysis-financial-market-scale-compare", columnLimit: 7 },
      { title: "收益率分析（总账可复算）", sheet: incomeRateAnalysisSheet, testId: "ledger-pnl-monthly-analysis-income-rate", columnLimit: 7 },
      { title: "收益量价归因（年累计同比）", sheet: incomeRateAttributionSheet, testId: "ledger-pnl-monthly-analysis-income-rate-attribution", columnLimit: 9 },
      { title: "存款利息拆分", sheet: depositInterestSplitSheet, testId: "ledger-pnl-monthly-analysis-deposit-interest-split", columnLimit: 11, rowLimit: 9 },
      { title: "母公司营收分项", sheet: parentCompanyRevenueSheet, testId: "ledger-pnl-monthly-analysis-parent-company-revenue", columnLimit: 11, rowLimit: 17 },
      { title: "外币分析", sheet: foreignCurrencySheet, testId: "ledger-pnl-monthly-analysis-foreign-currency", columnLimit: 6, rowLimit: 8 },
      { title: "行业存贷差", sheet: industryGapSheet, testId: "ledger-pnl-monthly-analysis-industry-gap", columnLimit: 5 },
    ];
    return buildLedgerPnlWorkbookGroups(
      Object.fromEntries(specs.map((spec) => [spec.title, spec])),
    );
  }, [
    alertsSheet,
    assetStructureSheet,
    companyScaleCompareSheet,
    companyScaleSheet,
    depositDemandIndustrySheet,
    depositInterestSplitSheet,
    depositTermIndustrySheet,
    financialIndicatorStatusSheet,
    financialMarketScaleCompareSheet,
    financialMarketScaleSheet,
    foreignCurrencySheet,
    incomeRateAnalysisSheet,
    incomeRateAttributionSheet,
    industryGapSheet,
    liabilityStructureSheet,
    loanIndustrySheet,
    parentCompanyRevenueSheet,
    retailScaleCompareSheet,
    retailScaleSheet,
    segmentBaseScaleSheet,
    segmentScaleCompareSheet,
    summary3dSheet,
    top11dSheet,
  ]);
  const overviewLabelColumn = overviewSheet?.columns[0];
  const overviewValueColumn = overviewSheet?.columns[1];
  const overviewRows =
    overviewLabelColumn && overviewValueColumn
      ? overviewSheet.rows.slice(0, 8).map((row) => ({
          label: formatAnalysisValue(row[overviewLabelColumn]),
          value: formatAnalysisValue(row[overviewValueColumn]),
        }))
      : [];
  const summaryCards: LedgerSummaryCardModel[] = [
    {
      key: "ledger_monthly_pnl_core",
      title: "核心损益",
      value: summary?.data_status === "no_data" ? EM_DASH : formatMoney(summary?.ledger_monthly_pnl_core),
      candidateMetricKey: "ledger_monthly_pnl_core",
    },
    {
      key: "ledger_monthly_pnl_all",
      title: "全量损益",
      value: summary?.data_status === "no_data" ? EM_DASH : formatMoney(summary?.ledger_monthly_pnl_all),
      candidateMetricKey: "ledger_monthly_pnl_all",
    },
    {
      key: "ledger_total_assets",
      title: "总资产",
      value: summary?.data_status === "no_data" ? EM_DASH : formatMoney(summary?.ledger_total_assets),
    },
    {
      key: "ledger_total_liabilities",
      title: "总负债",
      value: summary?.data_status === "no_data" ? EM_DASH : formatMoney(summary?.ledger_total_liabilities),
    },
    {
      key: "ledger_net_assets",
      title: "净资产",
      value: summary?.data_status === "no_data" ? EM_DASH : formatMoney(summary?.ledger_net_assets),
      candidateMetricKey: "ledger_net_assets",
    },
  ];

  const sectionNavItems = useMemo<LedgerPnlSectionNavItem[]>(
    () => [
      { id: LEDGER_PNL_SECTION_IDS.verdict, label: "当日结论" },
      { id: LEDGER_PNL_SECTION_IDS.summary, label: "账面总览" },
      { id: LEDGER_PNL_SECTION_IDS.analysis, label: "损益分析" },
      { id: LEDGER_PNL_SECTION_IDS.indicators, label: "经营指标" },
      { id: LEDGER_PNL_SECTION_IDS.candidate, label: "候选指标" },
      { id: LEDGER_PNL_SECTION_IDS.reconciliation, label: "对账与日均" },
      { id: LEDGER_PNL_SECTION_IDS.accounts, label: "科目汇总" },
      { id: LEDGER_PNL_SECTION_IDS.detail, label: "科目明细" },
      { id: LEDGER_PNL_SECTION_IDS.evidence, label: "证据与元信息" },
    ],
    [],
  );

  /**
   * 章节导航直达前，唤醒目标及其上方全部门控区块：
   * 只唤醒目标会让滚动途中的骨架在 IO 触发后才加载，
   * 上方内容高度随后变化，目标锚点被推移（锚点漂移）。
   */
  const wakeSectionsForNavigate = (targetId: string) => {
    const gatedSections = [
      { id: LEDGER_PNL_SECTION_IDS.indicators, markSeen: indicatorsSection.markSeen },
      { id: LEDGER_PNL_SECTION_IDS.candidate, markSeen: candidateSection.markSeen },
      { id: LEDGER_PNL_SECTION_IDS.reconciliation, markSeen: reconciliationSection.markSeen },
    ];
    const navOrder = sectionNavItems.map((item) => item.id);
    const targetIndex = navOrder.indexOf(targetId);
    if (targetIndex < 0) {
      return;
    }
    for (const gated of gatedSections) {
      const gatedIndex = navOrder.indexOf(gated.id);
      if (gatedIndex >= 0 && gatedIndex <= targetIndex) {
        gated.markSeen();
      }
    }
  };

  useEffect(() => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("report_date");
    nextParams.delete("currency");
    if (selectedReportDate) {
      nextParams.set("report_date", selectedReportDate);
    }
    nextParams.set("currency", currency);

    const nextSearch = nextParams.toString();
    if (nextSearch !== searchParams.toString()) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [currency, searchParams, selectedReportDate, setSearchParams]);

  /*
   * 深色 owner 由外层 ThemedRouteBoundary 的 data-moss-theme="dark" 承担；
   * 页根只声明 Nocturne scope，重复声明 owner 会让深色路由校验判定出两个 owner。
   */
  return (
    <section
      data-testid="ledger-pnl-page"
      data-moss-theme-scope="ledger-pnl"
      className="ledger-pnl-page theme-dh-api"
    >
      <div className="ledger-pnl-header">
        <div>
          <h1 data-testid="ledger-pnl-page-title" className="ledger-pnl-header__title">
            总账损益
          </h1>
          <p data-testid="ledger-pnl-page-subtitle" className="ledger-pnl-header__subtitle">
            科目口径损益总览、币种汇总与账户明细。页面直接消费后端总账口径读模型，
            不在前端补算会计科目聚合。
          </p>
        </div>
        <span
          className={`ledger-pnl-header__mode-badge ledger-pnl-header__mode-badge--${
            client.mode === "real" ? "real" : "mock"
          }`}
        >
          {client.mode === "real" ? "真实 API 只读链路 · 非正式口径" : "本地演示数据"}
        </span>
      </div>

      <FilterBar className="ledger-pnl-filters">
        <label>
          <span className="ledger-pnl-filters__label">报告日</span>
          <select
            id={LEDGER_PNL_REPORT_DATE_SELECT_ID}
            data-testid="ledger-pnl-report-date-control"
            aria-label="总账损益报告日"
            value={selectedReportDate}
            onChange={(event) => {
              const nextParams = new URLSearchParams(searchParams);
              nextParams.delete("report_date");
              nextParams.delete("currency");
              if (event.target.value) {
                nextParams.set("report_date", event.target.value);
              }
              nextParams.set("currency", currency);
              setSearchParams(nextParams, { replace: true });
            }}
            className="ledger-pnl-filters__select"
          >
            {selectedReportDate && !reportDates.includes(selectedReportDate) ? (
              <option value={selectedReportDate}>{selectedReportDate}</option>
            ) : null}
            {reportDates.length === 0 && !selectedReportDate ? <option value="">暂无可选报告日</option> : null}
            {reportDates.map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {reportDate}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="ledger-pnl-filters__label">
            账务口径
          </span>
          <select
            data-testid="ledger-pnl-currency-control"
            aria-label="总账损益账务口径"
            value={currency}
            onChange={(event) => {
              const nextParams = new URLSearchParams(searchParams);
              nextParams.set("currency", normalizeLedgerPnlCurrencyBasis(event.target.value));
              setSearchParams(nextParams, { replace: true });
            }}
            className="ledger-pnl-filters__select ledger-pnl-filters__select--currency"
          >
            {LEDGER_PNL_CURRENCY_BASIS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <p className="ledger-pnl-filters__note">
          CNX（综本）与 CNY（人民币账）是重叠账务口径，不可相加。
          {selectedReportDateMissingFromDates ? (
            <span className="ledger-pnl-filters__note--warn">
              当前报告日不在可选列表中，仍按查询日期读取总账数据
            </span>
          ) : null}
        </p>
      </FilterBar>

      <LedgerPnlSectionNav
        items={sectionNavItems}
        onBeforeNavigate={wakeSectionsForNavigate}
      />

      {/* 首屏必须先回答「本报告日总账口径能得出什么判断、证据是否可信」（DESIGN.md §9 首屏一问）。 */}
      <section id={LEDGER_PNL_SECTION_IDS.verdict} className="ledger-pnl-section">
        <LedgerPnlSectionLead title="当日结论" note="总账候选口径" />
        <LedgerFunctionalAuditStrip
          selectedReportDate={selectedReportDate}
          selectedReportDateMissingFromDates={selectedReportDateMissingFromDates}
          reportDates={reportDates}
          datesMeta={datesQuery.data?.result_meta}
          analysisEnvelope={analysisQuery.data}
          analysisError={analysisQuery.error}
          requestedReportMonth={requestedAnalysisMonth}
          monthlyAnalysisWorkbook={monthlyAnalysisWorkbook}
          monthlyAnalysisWorkbookMeta={monthlyAnalysisWorkbookQuery.data?.result_meta}
          formalIndicatorSourceContract={formalIndicatorSourceContract}
          hasMatchingAnalysisMonth={hasMatchingAnalysisMonth}
          isMonthlyAnalysisDatesLoading={monthlyAnalysisDatesQuery.isLoading}
          isMonthlyAnalysisDatesError={monthlyAnalysisDatesQuery.isError}
          isMonthlyAnalysisWorkbookLoading={monthlyAnalysisWorkbookQuery.isLoading}
          isMonthlyAnalysisWorkbookError={monthlyAnalysisWorkbookQuery.isError}
          isFormalContractLoading={formalIndicatorSourceContractQuery.isLoading}
          isFormalContractError={formalIndicatorSourceContractQuery.isError}
          isDatesLoading={datesQuery.isLoading}
          isDatesError={datesQuery.isError}
          isAnalysisLoading={analysisQuery.isLoading}
          isAnalysisError={analysisQuery.isError}
          reconciliationDeferred={!reconciliationSection.seen}
        />
      </section>

      <section id={LEDGER_PNL_SECTION_IDS.summary} className="ledger-pnl-section">
        <LedgerPnlSectionLead
          title="账面总览"
          state={ledgerSectionState(summaryQuery, {
            isEmpty: summary?.data_status === "no_data",
            emptyLabel: "当期无总账证据",
          })}
          note={`${currency} 口径 · 亿元`}
        />
        <div
          data-testid="ledger-pnl-summary-cards"
          className="ledger-pnl-summary-grid"
        >
          {summaryCards.map((card) => (
            <LedgerSummaryCard key={card.key} card={card} />
          ))}
        </div>
      </section>

      <LedgerPnlAccountDetailDrawer
        selection={selectedContributor}
        reportDate={selectedReportDate}
        currency={currency}
        onClose={() => setSelectedContributor(null)}
        onLocate={locateContributorInDetail}
      />

      <section id={LEDGER_PNL_SECTION_IDS.analysis} className="ledger-pnl-section">
        <LedgerPnlSectionLead title="损益分析" state={ledgerSectionState(analysisQuery)} />
        <LedgerPnlAnalysisWorkbench
          envelope={analysisQuery.data}
          isLoading={analysisQuery.isLoading}
          isError={analysisQuery.isError}
          error={analysisQuery.error}
          onRetry={() => {
            void analysisQuery.refetch();
          }}
          onSelectContributor={setSelectedContributor}
        />
      </section>

      <section
        id={LEDGER_PNL_SECTION_IDS.indicators}
        ref={indicatorsSection.ref}
        className="ledger-pnl-section"
      >
        <LedgerPnlSectionLead title="经营指标" note={`${requestedAnalysisMonth || EM_DASH} · 总账口径`} />
        {indicatorsSection.seen ? (
          <LedgerPnlFinancialIndicatorSummaryPanel
            reportMonth={requestedAnalysisMonth}
            currency={currency}
          />
        ) : (
          <LedgerSectionSkeleton
            testId="ledger-pnl-indicators-skeleton"
            title="经营指标情况表（总账口径）"
            minHeight={260}
          />
        )}
      </section>

      <section
        id={LEDGER_PNL_SECTION_IDS.candidate}
        ref={candidateSection.ref}
        className="ledger-pnl-section"
      >
        <LedgerPnlSectionLead title="候选指标" note="候选口径，不可正式使用" />
        {candidateSection.seen ? (
          <LedgerPnlCandidateFinancialIndicatorsPanel
            reportMonth={requestedAnalysisMonth}
            currency={currency}
          />
        ) : (
          <LedgerSectionSkeleton
            testId="ledger-pnl-candidate-skeleton"
            title="候选财务指标"
            minHeight={320}
          />
        )}
      </section>

      <section
        id={LEDGER_PNL_SECTION_IDS.reconciliation}
        ref={reconciliationSection.ref}
        className="ledger-pnl-section"
      >
        <LedgerPnlSectionLead title="对账与日均" note="月度工作簿口径" />
        <section
          data-testid="ledger-pnl-monthly-analysis-panel"
          className="ledger-pnl-analysis"
        >
        <div className="ledger-pnl-analysis__header">
          <div>
            <h3 className="ledger-pnl-analysis__title">
              总账对账 + 日均分析
            </h3>
          </div>
          <span data-testid="ledger-pnl-monthly-analysis-month" className="ledger-pnl-analysis__month">
            {selectedAnalysisMonth ||
              (monthlyAnalysisDatesQuery.isError
                ? "月份读取失败"
                : requestedAnalysisMonth
                  ? `${requestedAnalysisMonth} 无匹配`
                  : "暂无月份")}
          </span>
        </div>

        {!reconciliationSection.seen ? (
          <LedgerSectionSkeleton
            testId="ledger-pnl-reconciliation-skeleton"
            title="对账明细与正式契约"
            minHeight={420}
          />
        ) : (
          <>
        {monthlyAnalysisDatesQuery.isError ? (
          <div data-testid="ledger-pnl-monthly-analysis-error" className="ledger-pnl-analysis__empty">
            月度分析月份读取失败
          </div>
        ) : null}

        {!hasMatchingAnalysisMonth &&
        !monthlyAnalysisDatesQuery.isLoading &&
        !monthlyAnalysisDatesQuery.isError ? (
          <div data-testid="ledger-pnl-monthly-analysis-missing-month" className="ledger-pnl-analysis__empty">
            当前报告日没有对应月度分析工作簿
          </div>
        ) : null}

        {monthlyAnalysisWorkbookQuery.isError ? (
          <div data-testid="ledger-pnl-monthly-analysis-error" className="ledger-pnl-analysis__empty">
            月度分析工作簿读取失败
          </div>
        ) : null}

        {monthlyWorkbookState.blockingDetail && hasMatchingAnalysisMonth ? (
          <div data-testid="ledger-pnl-monthly-analysis-trust-warning" className="ledger-pnl-analysis__empty">
            {monthlyWorkbookState.blockingDetail}；月度分析表已隐藏，避免把不可信 QDB 工作簿当作本月分析结果。
          </div>
        ) : null}

        <FormalIndicatorSourceContractPanel
          contract={formalIndicatorSourceContract}
          requestedReportMonth={requestedAnalysisMonth}
          isLoading={formalIndicatorSourceContractQuery.isLoading}
          isError={formalIndicatorSourceContractQuery.isError}
        />

        <FormalIndicatorRuleChecksPanel
          ruleChecks={formalIndicatorRuleChecks}
          requestedReportMonth={requestedAnalysisMonth}
          isLoading={formalIndicatorRuleChecksQuery.isLoading}
          isError={formalIndicatorRuleChecksQuery.isError}
        />

        <FinancialIndicatorStatusPanel rows={financialIndicatorStatusRows} />

        {overviewRows.length > 0 ? (
          <div data-testid="ledger-pnl-monthly-analysis-overview" className="ledger-pnl-analysis__kpis">
            {overviewRows.map((row) => (
              <div key={row.label} className="ledger-pnl-analysis__kpi">
                <div className="ledger-pnl-analysis__kpi-label">
                  {row.label}
                </div>
                <div className="ledger-pnl-analysis__kpi-value">
                  {row.value}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div data-testid="ledger-pnl-monthly-analysis-overview" className="ledger-pnl-analysis__empty">
            暂无经营概览数据
          </div>
        )}

        <LedgerPnlWorkbookTables groups={monthlyWorkbookGroups} />
          </>
        )}
        </section>
      </section>

      <section id={LEDGER_PNL_SECTION_IDS.accounts} className="ledger-pnl-section">
        <LedgerPnlSectionLead
          title="科目汇总"
          state={ledgerSectionState(summaryQuery)}
          note={`${(summary?.by_account ?? []).length} 个科目`}
        />
        <div className="ledger-pnl-summary-table-grid">
        <div data-testid="ledger-pnl-currency-summary-table" className="ledger-pnl-table-shell">
          <div className="ledger-pnl-table-shell__title">
            币种汇总
          </div>
          <table className="ledger-pnl-table">
            <thead>
              <tr className="ledger-pnl-table__head-row">
                <th className="ledger-pnl-table__th">币种</th>
                <th className="ledger-pnl-table__th ledger-pnl-table__th--num">损益</th>
              </tr>
            </thead>
            <tbody>
              {summaryQuery.isLoading ? (
                <LedgerTableStateRow colSpan={2} message="币种汇总读取中" />
              ) : summaryQuery.isError ? (
                <LedgerTableStateRow colSpan={2} message="币种汇总读取失败" />
              ) : (summary?.by_currency ?? []).length > 0 ? (
                (summary?.by_currency ?? []).map((item) => (
                  <tr key={item.currency} className="ledger-pnl-table__row">
                    <td className="ledger-pnl-table__td">{item.currency}</td>
                    <td className="ledger-pnl-table__td ledger-pnl-table__td--num">{formatMoney(item.total_pnl)}</td>
                  </tr>
                ))
              ) : (
                <LedgerTableStateRow colSpan={2} message="暂无币种汇总数据" />
              )}
            </tbody>
          </table>
        </div>

        <LedgerPnlDataTable
          testId="ledger-pnl-account-summary-table"
          title="科目汇总"
          caption={
            visibleAccountSummaryRows.length > 0
              ? `共 ${visibleAccountSummaryRows.length} 个科目，默认按损益绝对值降序`
              : undefined
          }
          columns={accountSummaryColumns}
          rows={visibleAccountSummaryRows}
          rowKey={(item) => item.account_code}
          isLoading={summaryQuery.isLoading}
          isError={summaryQuery.isError}
          loadingMessage="科目汇总读取中"
          errorMessage="科目汇总读取失败"
          emptyMessage="暂无科目汇总数据"
          searchPlaceholder="搜索科目代码或名称"
          pageSize={LEDGER_TABLE_PAGE_SIZE}
        />
        </div>
      </section>

      <section
        ref={detailTableRef}
        tabIndex={-1}
        id={LEDGER_PNL_SECTION_IDS.detail}
        data-testid="ledger-pnl-detail-table-anchor"
        className="ledger-pnl-section"
      >
        <LedgerPnlSectionLead
          title="科目明细"
          state={ledgerSectionState(dataQuery)}
          note={detailSummaryNote}
        />
        <LedgerPnlDataTable
          testId="ledger-pnl-detail-table"
          title="科目明细"
          caption={
            visibleDetailRows.length > 0
              ? `共 ${visibleDetailRows.length} 行，默认按月损益绝对值降序`
              : undefined
          }
          columns={detailColumns}
          rows={visibleDetailRows}
          rowKey={(item) => `${item.account_code}-${item.currency}`}
          isLoading={dataQuery.isLoading}
          isError={dataQuery.isError}
          loadingMessage="科目明细读取中"
          errorMessage="科目明细读取失败"
          emptyMessage="暂无科目明细数据"
          searchPlaceholder="搜索科目代码或名称"
          pageSize={LEDGER_TABLE_PAGE_SIZE}
          notice={
            detailAccountFilter ? (
              <div
                className="ledger-pnl-detail-account-filter"
                data-testid="ledger-pnl-detail-account-filter"
              >
                <div>
                  <strong>
                    当前仅显示 {detailAccountFilter.account_code} {detailAccountFilter.account_name}
                  </strong>
                  <span>
                    月日均不参与本次账户损益穿透；0 可能来自日均源缺行，不能解释为已观测真实零
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setDetailAccountFilter(null)}
                  aria-label="清除科目筛选"
                >
                  清除筛选
                </button>
              </div>
            ) : null
          }
        />
      </section>

      <section id={LEDGER_PNL_SECTION_IDS.evidence} className="ledger-pnl-section">
        <LedgerPnlSectionLead title="证据与元信息" note="接口口径与来源版本" />
        <div className="ledger-pnl-evidence-layer">
      <FormalResultMetaPanel
        testId="ledger-pnl-result-meta-panel"
        sections={[
          { key: "dates", title: "Ledger 报告日", meta: datesQuery.data?.result_meta },
          { key: "summary", title: "Ledger 汇总", meta: summaryQuery.data?.result_meta },
          { key: "data", title: "Ledger 明细", meta: dataQuery.data?.result_meta },
          { key: "analysis", title: "Ledger 候选分析", meta: analysisQuery.data?.result_meta },
          { key: "monthly-analysis-dates", title: "月度分析月份", meta: monthlyAnalysisDatesQuery.data?.result_meta },
          {
            key: "monthly-analysis-workbook",
            title: "月度分析工作簿",
            meta: monthlyAnalysisWorkbookQuery.data?.result_meta,
          },
          {
            key: "formal-financial-indicator-source-contract",
            title: "正式财务指标源契约",
            meta: formalIndicatorSourceContractQuery.data?.result_meta,
          },
        ]}
      />
        </div>
      </section>
    </section>
  );
}
