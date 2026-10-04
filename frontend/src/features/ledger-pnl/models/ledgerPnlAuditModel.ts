import type {
  ApiEnvelope,
  LedgerPnlAnalysisPayload,
  LedgerPnlFormalFinancialIndicatorContractPayload,
  QdbGlMonthlyAnalysisWorkbookPayload,
  ResultMeta,
} from "../../../api/contracts";
import {
  LEDGER_PNL_FORMAL_CONTRACT_PANEL_ID,
  LEDGER_PNL_FORMAL_CONTRACT_RELEASE_GATE_ID,
  LEDGER_PNL_FORMAL_CONTRACT_MATERIAL_CHECKLIST_ID,
  LEDGER_PNL_REPORT_DATE_SELECT_ID,
} from "./ledgerPnlPageConstants";
import {
  collectSourceRiskSegments,
  formatEvidenceRows,
  metaString,
  missingSourceEvidenceFields,
  monthlyWorkbookAuditState,
} from "./ledgerPnlSourceEvidence";
import { hasEmptyFormalContractMetrics, registeredPendingReleaseGate } from "./ledgerPnlFormalContractModel";

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

export function collectLedgerNextDrills(
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

export function formalContractRemediationDrill(
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

export function appendLedgerDrill(
  drills: LedgerFunctionalDrill[],
  drill: LedgerFunctionalDrill | null,
): LedgerFunctionalDrill[] {
  if (!drill || drills.some((row) => row.key === drill.key)) {
    return drills;
  }
  return [...drills, drill].slice(0, 3);
}

export function focusLedgerFormalContractTarget(props: {
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

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error ?? "");
}

function isForbiddenLedgerError(error: unknown) {
  const message = errorMessage(error);
  return message.includes("(403)") || message.includes("not allowed") || message.includes("403");
}
export type LedgerFunctionalAuditProps = {
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

export function buildLedgerAnalysisAuditState(props: LedgerFunctionalAuditProps) {
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
