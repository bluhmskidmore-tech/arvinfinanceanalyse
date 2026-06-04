import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { modeBadgeStyle, summaryGridStyle, tableStyle } from "../../../components/page/pageStyles";
import { designTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import { shellTokens } from "../../../theme/tokens";
import { FilterBar } from "../../../components/FilterBar";
import type {
  LedgerMoneyValue,
  LedgerPnlDataItem,
  LedgerPnlDataPayload,
  LedgerPnlFormalFinancialIndicatorContractPayload,
  LedgerPnlFormalFinancialIndicatorMetric,
  LedgerPnlSummaryPayload,
  LedgerPnlSummaryByAccount,
  LedgerPnlSummaryByCurrency,
  QdbGlMonthlyAnalysisSheet,
  ResultMeta,
} from "../../../api/contracts";
import "./LedgerPnlPage.css";

const pageHeaderStyle = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  flexWrap: "wrap",
  gap: 16,
  marginBottom: 24,
} as const;

const pageSubtitleStyle = {
  marginTop: 10,
  marginBottom: 0,
  maxWidth: 860,
  color: designTokens.color.neutral[600],
  fontSize: 15,
  lineHeight: 1.75,
} as const;

const summaryGridStyleWithBottom = { ...summaryGridStyle, marginBottom: designTokens.space[5] } as const;

const summaryCardStyle = {
  border: `1px solid ${designTokens.color.neutral[200]}`,
  borderRadius: designTokens.radius.lg,
  padding: designTokens.space[4],
  background: shellTokens.colorBgSurface,
} as const;

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
    <div style={summaryCardStyle}>
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
        <div className="ledger-pnl-summary-card__note">
          {candidateMetric.metricId} · {candidateMetric.note}
        </div>
      ) : null}
    </div>
  );
}

const tableWrapStyle = {
  border: `1px solid ${designTokens.color.neutral[200]}`,
  borderRadius: designTokens.radius.lg,
  background: shellTokens.colorBgSurface,
  overflow: "auto",
} as const;

const LEDGER_TABLE_ROW_LIMIT = 200;
const LEDGER_RECONCILIATION_TOLERANCE_YUAN = 0.5;
const LEDGER_PNL_TOTAL_ACCOUNT_PREFIXES = ["5"] as const;

const ledgerTableStateCellStyle = {
  padding: designTokens.space[4],
  color: designTokens.color.neutral[500],
  fontSize: designTokens.fontSize[13],
  textAlign: "center",
} as const;

function formatMoney(value: LedgerMoneyValue | null | undefined) {
  const yi = String(value?.yi ?? "").trim();
  if (yi) {
    return `${yi} 亿元`;
  }
  const yuanRaw = String(value?.yuan ?? "").trim();
  if (!yuanRaw) {
    return "--";
  }
  const yuan = Number(yuanRaw);
  return Number.isFinite(yuan) ? `${(yuan / 100_000_000).toFixed(2)} 亿元` : "--";
}

function ledgerMoneyYuan(value: LedgerMoneyValue | null | undefined) {
  const rawYuan = String(value?.yuan ?? "").trim();
  if (!rawYuan) {
    return null;
  }
  const yuan = Number(rawYuan);
  return Number.isFinite(yuan) ? yuan : null;
}

function formatYuanAsYi(yuan: number | null | undefined) {
  return Number.isFinite(yuan) ? `${((yuan ?? 0) / 100_000_000).toFixed(2)} 亿元` : "--";
}

function formatPercent(value: number | null | undefined) {
  return Number.isFinite(value) ? `${(value ?? 0).toFixed(2)}%` : "--";
}

function ledgerMoneyAbsYuan(value: LedgerMoneyValue | null | undefined) {
  const yuan = ledgerMoneyYuan(value);
  return yuan === null ? -1 : Math.abs(yuan);
}

function sortLedgerRowsByAbsYuan<T>(
  rows: T[],
  selectMoney: (row: T) => LedgerMoneyValue | null | undefined,
) {
  if (rows.length <= LEDGER_TABLE_ROW_LIMIT) {
    return rows;
  }
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
      <td colSpan={props.colSpan} style={ledgerTableStateCellStyle}>
        {props.message}
      </td>
    </tr>
  );
}

function LedgerTableTruncationRow(props: { colSpan: number; label: string; total: number }) {
  if (props.total <= LEDGER_TABLE_ROW_LIMIT) {
    return null;
  }
  return (
    <LedgerTableStateRow
      colSpan={props.colSpan}
      message={`${props.label}已按金额绝对值展示前 ${LEDGER_TABLE_ROW_LIMIT} 条 / 总计 ${props.total} 条`}
    />
  );
}

function sumLedgerMoney<T>(rows: T[], selectMoney: (row: T) => LedgerMoneyValue | null | undefined) {
  let total = 0;
  let hasValue = false;
  for (const row of rows) {
    const yuan = ledgerMoneyYuan(selectMoney(row));
    if (yuan !== null) {
      total += yuan;
      hasValue = true;
    }
  }
  return hasValue ? total : null;
}

function isLedgerPnlTotalAccountCode(accountCode: string) {
  const normalized = accountCode.trim();
  return LEDGER_PNL_TOTAL_ACCOUNT_PREFIXES.some((prefix) => normalized.startsWith(prefix));
}

function filterPnlExplainabilityDetailRows(
  detailRows: LedgerPnlDataItem[],
  byAccount: LedgerPnlSummaryByAccount[],
) {
  const summaryAccountCodes = new Set(byAccount.map((row) => row.account_code));
  return detailRows.filter((row) =>
    summaryAccountCodes.has(row.account_code) || isLedgerPnlTotalAccountCode(row.account_code),
  );
}

function differenceYuan(source: number | null, target: number | null) {
  return source === null || target === null ? null : source - target;
}

function reconciliationStatus(diff: number | null) {
  if (diff === null) {
    return "无法校验";
  }
  return Math.abs(diff) < LEDGER_RECONCILIATION_TOLERANCE_YUAN ? "一致" : `差异 ${formatYuanAsYi(diff)}`;
}

function classifyLedgerDriver(row: Pick<LedgerPnlSummaryByAccount, "account_code" | "account_name">) {
  const text = `${row.account_code} ${row.account_name}`.toLowerCase();
  if (text.includes("掉期") || text.includes("套期") || text.includes("衍生")) {
    return "衍生品/套保";
  }
  if (text.includes("公允价值") || text.includes("估值") || text.includes("价值变动")) {
    return "估值变动";
  }
  if (text.includes("结售汇") || text.includes("外汇") || text.includes("汇兑") || text.includes("远期")) {
    return "外汇/结售汇";
  }
  if (text.includes("利息") || text.includes("贷款") || text.includes("存款") || text.includes("存单")) {
    return "利息收支";
  }
  return "其他总账科目";
}

function offsetRatioPct(positiveYuan: number, negativeYuan: number) {
  const contributionYuan = Math.abs(positiveYuan);
  const dragYuan = Math.abs(negativeYuan);
  if (
    contributionYuan < LEDGER_RECONCILIATION_TOLERANCE_YUAN ||
    dragYuan < LEDGER_RECONCILIATION_TOLERANCE_YUAN
  ) {
    return 0;
  }
  return (Math.min(contributionYuan, dragYuan) / Math.max(contributionYuan, dragYuan)) * 100;
}

function buildLedgerDriverRows(rows: LedgerPnlSummaryByAccount[]) {
  const buckets = new Map<
    string,
    {
      label: string;
      yuan: number;
      positiveYuan: number;
      negativeYuan: number;
      count: number;
      topAccount: string;
      topAbsYuan: number;
    }
  >();
  for (const row of rows) {
    const yuan = ledgerMoneyYuan(row.total_pnl);
    if (yuan === null) {
      continue;
    }
    const label = classifyLedgerDriver(row);
    const bucket = buckets.get(label) ?? {
      label,
      yuan: 0,
      positiveYuan: 0,
      negativeYuan: 0,
      count: 0,
      topAccount: "",
      topAbsYuan: -1,
    };
    bucket.yuan += yuan;
    if (yuan > 0) {
      bucket.positiveYuan += yuan;
    } else {
      bucket.negativeYuan += yuan;
    }
    bucket.count += 1;
    if (Math.abs(yuan) > bucket.topAbsYuan) {
      bucket.topAccount = `${row.account_code} ${row.account_name}`;
      bucket.topAbsYuan = Math.abs(yuan);
    }
    buckets.set(label, bucket);
  }
  return Array.from(buckets.values())
    .map((row) => ({
      ...row,
      offsetRatioPct: offsetRatioPct(row.positiveYuan, row.negativeYuan),
    }))
    .sort((left, right) => Math.abs(right.yuan) - Math.abs(left.yuan));
}

function buildLedgerResidualDiagnosticRows(props: {
  totalYuan: number | null;
  currencyYuan: number | null;
  accountYuan: number | null;
  detailYuan: number | null;
  detailComparabilityReason: string | null;
}) {
  return [
    {
      layer: "币种层",
      reconciliationYuan: props.currencyYuan,
      diff: differenceYuan(props.totalYuan, props.currencyYuan),
      evidenceWhenMissing: "补币种汇总或确认币种口径",
      comparabilityReason: null,
    },
    {
      layer: "科目层",
      reconciliationYuan: props.accountYuan,
      diff: differenceYuan(props.totalYuan, props.accountYuan),
      evidenceWhenMissing: "补科目汇总或确认科目范围",
      comparabilityReason: null,
    },
    {
      layer: "明细层",
      reconciliationYuan: props.detailYuan,
      diff: differenceYuan(props.totalYuan, props.detailYuan),
      evidenceWhenMissing: "补明细或确认过滤口径",
      comparabilityReason: props.detailComparabilityReason,
    },
  ].map((row) => {
    if (row.comparabilityReason) {
      return {
        ...row,
        ledgerYuan: props.totalYuan,
        judgment: `${row.layer}可比性待核`,
        evidence: row.comparabilityReason,
      };
    }
    if (row.diff === null) {
      return {
        ...row,
        ledgerYuan: props.totalYuan,
        judgment: `${row.layer}待校验`,
        evidence: "补总账与对账口径数据",
      };
    }
    if (Math.abs(row.diff) < LEDGER_RECONCILIATION_TOLERANCE_YUAN) {
      return {
        ...row,
        ledgerYuan: props.totalYuan,
        judgment: `${row.layer}闭合`,
        evidence: "无需补证",
      };
    }
    return {
      ...row,
      ledgerYuan: props.totalYuan,
      judgment: `${row.layer}残差 ${formatYuanAsYi(row.diff)}`,
      evidence: row.evidenceWhenMissing,
    };
  });
}

function evidenceEntryRank(row: ReturnType<typeof buildLedgerResidualDiagnosticRows>[number]) {
  if (row.comparabilityReason) {
    return 2;
  }
  if (row.diff === null) {
    return 1;
  }
  return 0;
}

function buildCurrencyResidualRows(props: {
  byCurrency: LedgerPnlSummaryByCurrency[];
  detailRows: LedgerPnlDataItem[];
  comparabilityReason: string | null;
}) {
  const detailByCurrency = new Map<string, { yuan: number; grossYuan: number; hasValue: boolean }>();
  for (const row of props.detailRows) {
    const key = row.currency;
    const yuan = ledgerMoneyYuan(row.monthly_pnl);
    if (!key || yuan === null) {
      continue;
    }
    const current = detailByCurrency.get(key) ?? { yuan: 0, grossYuan: 0, hasValue: false };
    current.yuan += yuan;
    current.grossYuan += Math.abs(yuan);
    current.hasValue = true;
    detailByCurrency.set(key, current);
  }

  const summaryCurrencies = new Set<string>();
  const rows: Array<{
    currency: string;
    summaryYuan: number | null;
    detailYuan: number;
    detailGrossYuan: number;
    diff: number | null;
    isDetailOnly: boolean;
    judgment: string;
    comparabilityReason: string | null;
  }> = props.byCurrency.map((row) => {
    summaryCurrencies.add(row.currency);
    const summaryYuan = ledgerMoneyYuan(row.total_pnl);
    const detail = detailByCurrency.get(row.currency);
    const detailYuan = detail?.hasValue ? detail.yuan : 0;
    const diff = summaryYuan === null ? null : summaryYuan - detailYuan;
    return {
      currency: row.currency,
      summaryYuan,
      detailYuan,
      detailGrossYuan: detail?.hasValue ? detail.grossYuan : 0,
      diff,
      isDetailOnly: false,
      comparabilityReason: props.comparabilityReason,
      judgment:
        props.comparabilityReason
          ? "可比性待核"
          : diff === null
          ? "待校验"
          : Math.abs(diff) < LEDGER_RECONCILIATION_TOLERANCE_YUAN
            ? "已闭合"
            : diff > 0
              ? `疑似缺明细 ${formatYuanAsYi(diff)}`
              : `疑似明细多 ${formatYuanAsYi(Math.abs(diff))}`,
    };
  });

  for (const [currency, detail] of detailByCurrency) {
    if (summaryCurrencies.has(currency)) {
      continue;
    }
    const diff = -detail.yuan;
    rows.push({
      currency,
      summaryYuan: 0,
      detailYuan: detail.yuan,
      detailGrossYuan: detail.grossYuan,
      diff,
      isDetailOnly: true,
      comparabilityReason: props.comparabilityReason,
      judgment:
        props.comparabilityReason
          ? "可比性待核"
          : Math.abs(diff) < LEDGER_RECONCILIATION_TOLERANCE_YUAN
          ? `疑似汇总缺失毛活动 ${formatYuanAsYi(detail.grossYuan)}`
          : `疑似汇总缺失 ${formatYuanAsYi(Math.abs(diff))}`,
    });
  }

  return rows
    .filter(
      (row) =>
        row.diff === null ||
        Math.abs(row.diff) >= LEDGER_RECONCILIATION_TOLERANCE_YUAN ||
        (row.isDetailOnly && row.detailGrossYuan >= LEDGER_RECONCILIATION_TOLERANCE_YUAN),
    )
    .sort((left, right) => {
      const leftRank = Math.max(Math.abs(left.diff ?? 0), left.isDetailOnly ? left.detailGrossYuan : 0);
      const rightRank = Math.max(Math.abs(right.diff ?? 0), right.isDetailOnly ? right.detailGrossYuan : 0);
      return rightRank - leftRank;
    })
    .slice(0, 5);
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

function filterMetaString(meta: ResultMeta | null | undefined, key: string) {
  return metaString(meta?.filters_applied?.[key]);
}

function firstMetaMismatch(
  summaryMeta: ResultMeta | null | undefined,
  detailMeta: ResultMeta | null | undefined,
) {
  const checks = [
    {
      label: "resolved_report_date",
      summary: metaString(summaryMeta?.resolved_report_date),
      detail: metaString(detailMeta?.resolved_report_date),
    },
    {
      label: "as_of_date",
      summary: metaString(summaryMeta?.as_of_date),
      detail: metaString(detailMeta?.as_of_date),
    },
    {
      label: "date_basis",
      summary: metaString(summaryMeta?.date_basis),
      detail: metaString(detailMeta?.date_basis),
    },
    {
      label: "source_version",
      summary: metaString(summaryMeta?.source_version),
      detail: metaString(detailMeta?.source_version),
    },
    {
      label: "rule_version",
      summary: metaString(summaryMeta?.rule_version),
      detail: metaString(detailMeta?.rule_version),
    },
    {
      label: "cache_version",
      summary: metaString(summaryMeta?.cache_version),
      detail: metaString(detailMeta?.cache_version),
    },
    {
      label: "filters_applied.report_date",
      summary: filterMetaString(summaryMeta, "report_date"),
      detail: filterMetaString(detailMeta, "report_date"),
    },
    {
      label: "filters_applied.currency",
      summary: filterMetaString(summaryMeta, "currency"),
      detail: filterMetaString(detailMeta, "currency"),
    },
  ];

  const mismatch = checks.find((check) => check.summary !== check.detail && (check.summary || check.detail));
  return mismatch
    ? `汇总 ${mismatch.label}=${mismatch.summary ?? "缺失"}，明细 ${mismatch.label}=${mismatch.detail ?? "缺失"}`
    : null;
}

function detailSliceEvidence(meta: ResultMeta | null | undefined) {
  const resolvedReportDate = metaString(meta?.resolved_report_date) ?? "缺失";
  const asOfDate = metaString(meta?.as_of_date) ?? "缺失";
  const dateBasis = metaString(meta?.date_basis) ?? "缺失";
  return `明细切片证据：resolved_report_date=${resolvedReportDate}，as_of_date=${asOfDate}，date_basis=${dateBasis}`;
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

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error ?? "");
}

function isForbiddenLedgerError(error: unknown) {
  const message = errorMessage(error);
  return message.includes("(403)") || message.includes("not allowed") || message.includes("403");
}

function hasLedgerPnlEvidence(props: {
  summary: LedgerPnlSummaryPayload | undefined;
  summaryMeta: ResultMeta | null | undefined;
}) {
  const summaryEvidence = props.summaryMeta?.evidence_rows;
  if (typeof summaryEvidence === "number") {
    return summaryEvidence > 0;
  }
  return (props.summary?.by_account.length ?? 0) > 0;
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
  if (metrics.length === 0) {
    return {
      label: "无正式契约明细",
      formalPending: 0,
      qdbCandidateAligned: 0,
      needsReconciliation: 0,
    };
  }
  return {
    label: null,
    formalPending: metrics.filter((metric) => metric.source_status === "formal_pending").length,
    qdbCandidateAligned: metrics.filter((metric) => metric.source_status === "candidate_qdb_aligned").length,
    needsReconciliation: metrics.filter((metric) => metric.source_status === "needs_reconciliation").length,
  };
}

function buildLedgerFunctionalAuditState(props: {
  selectedReportDate: string;
  selectedReportDateMissingFromDates: boolean;
  reportDates: string[];
  summary: LedgerPnlSummaryPayload | undefined;
  data: LedgerPnlDataPayload | undefined;
  datesMeta: ResultMeta | null | undefined;
  summaryMeta: ResultMeta | null | undefined;
  dataMeta: ResultMeta | null | undefined;
  formalIndicatorSourceContract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined;
  isLoading: boolean;
  isError: boolean;
  readErrors: unknown[];
}) {
  const pnlEvidenceAvailable = hasLedgerPnlEvidence(props);
  const requestedDate = props.selectedReportDate || "缺失";
  const resolvedDate =
    metaString(props.summaryMeta?.resolved_report_date) ??
    metaString(props.dataMeta?.resolved_report_date) ??
    props.summary?.report_date ??
    props.data?.report_date ??
    "缺失";
  const asOfDate =
    metaString(props.summaryMeta?.as_of_date) ??
    metaString(props.dataMeta?.as_of_date) ??
    "缺失";
  const sourceVersion =
    metaString(props.summaryMeta?.source_version) ??
    metaString(props.dataMeta?.source_version) ??
    props.summary?.source_version ??
    "缺失";
  const formalUseAllowed = props.formalIndicatorSourceContract?.formal_use_allowed === true;
  const formalStatus = formalUseAllowed
    ? "正式值可用"
    : props.formalIndicatorSourceContract?.sample_status === "missing_contract"
      ? "正式契约缺失，正式值不可用"
      : "正式值不可用，仅作候选核对";

  if (props.isLoading) {
    return {
      tone: "pending",
      title: "总账链路读取中",
      detail: "等待汇总、明细和正式财务指标契约返回后再判断。",
      requestedDate,
      resolvedDate,
      asOfDate,
      sourceVersion,
      formalStatus,
    };
  }
  if (props.isError) {
    const forbidden = props.readErrors.some(isForbiddenLedgerError);
    return {
      tone: "warning",
      title: forbidden ? "无权限读取总账损益" : "总账链路读取失败",
      detail: forbidden
        ? "当前用户没有 ledger_pnl 读取权限；本次不能形成总账损益判断。"
        : "本次不能形成总账损益判断；请先恢复接口读取。",
      requestedDate,
      resolvedDate,
      asOfDate,
      sourceVersion,
      formalStatus,
    };
  }
  if (props.reportDates.length === 0) {
    return {
      tone: "warning",
      title: "没有可选报告日",
      detail: "日期接口没有返回总账报告日，需要先确认源文件发现链路。",
      requestedDate,
      resolvedDate,
      asOfDate,
      sourceVersion,
      formalStatus,
    };
  }
  if (!props.selectedReportDate) {
    return {
      tone: "warning",
      title: "缺少报告日",
      detail: "没有报告日就不能确定总账切片，也不能判断月度工作簿匹配关系。",
      requestedDate,
      resolvedDate,
      asOfDate,
      sourceVersion,
      formalStatus,
    };
  }
  if (props.selectedReportDateMissingFromDates) {
    return {
      tone: "warning",
      title: "报告日未列入可选清单",
      detail: "接口仍按查询日期返回了总账切片，但需要核对日期清单和源文件登记。",
      requestedDate,
      resolvedDate,
      asOfDate,
      sourceVersion,
      formalStatus,
    };
  }
  if (!pnlEvidenceAvailable) {
    return {
      tone: "warning",
      title: "总账损益证据缺失",
      detail: "汇总没有损益证据行，不能把总账明细或空汇总解释为真实 PnL 0。",
      requestedDate,
      resolvedDate,
      asOfDate,
      sourceVersion,
      formalStatus,
    };
  }
  return {
    tone: "ok",
    title: "总账候选口径可分析",
    detail: "当前有总账损益证据行，可做候选对账和解释；正式 PnL 与正式财务指标仍需单独放行。",
    requestedDate,
    resolvedDate,
    asOfDate,
    sourceVersion,
    formalStatus,
  };
}

function LedgerFunctionalAuditStrip(props: {
  selectedReportDate: string;
  selectedReportDateMissingFromDates: boolean;
  reportDates: string[];
  summary: LedgerPnlSummaryPayload | undefined;
  data: LedgerPnlDataPayload | undefined;
  datesMeta: ResultMeta | null | undefined;
  summaryMeta: ResultMeta | null | undefined;
  dataMeta: ResultMeta | null | undefined;
  formalIndicatorSourceContract: LedgerPnlFormalFinancialIndicatorContractPayload | undefined;
  isFormalContractLoading: boolean;
  isFormalContractError: boolean;
  isLoading: boolean;
  isError: boolean;
  readErrors: unknown[];
}) {
  const state = buildLedgerFunctionalAuditState(props);
  const nextDrills = collectLedgerNextDrills(props.datesMeta, props.summaryMeta, props.dataMeta);
  const formalGapSummary = summarizeFormalIndicatorContractGaps(
    props.formalIndicatorSourceContract,
    props.isFormalContractLoading,
    props.isFormalContractError,
  );
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
      <div className="ledger-pnl-functional-strip__facts">
        <div>
          <span>请求报告日</span>
          <strong>{state.requestedDate}</strong>
        </div>
        <div>
          <span>解析报告日</span>
          <strong>{state.resolvedDate}</strong>
        </div>
        <div>
          <span>数据截至日</span>
          <strong>{state.asOfDate}</strong>
        </div>
        <div>
          <span>汇总证据行</span>
          <strong>{formatEvidenceRows(props.summaryMeta)}</strong>
        </div>
        <div>
          <span>明细证据行</span>
          <strong>{formatEvidenceRows(props.dataMeta)}</strong>
        </div>
        <div>
          <span>质量</span>
          <strong>汇总{formatMetaQuality(props.summaryMeta)} / 明细{formatMetaQuality(props.dataMeta)}</strong>
        </div>
        <div>
          <span>来源版本</span>
          <strong>{state.sourceVersion}</strong>
        </div>
        <div>
          <span>正式边界</span>
          <strong>{state.formalStatus}</strong>
        </div>
        <div>
          <span>正式契约缺口</span>
          <strong>
            {formalGapSummary.label ??
              `正式待接入 ${formalGapSummary.formalPending} / QDB候选 ${formalGapSummary.qdbCandidateAligned} / 需对账 ${formalGapSummary.needsReconciliation}`}
          </strong>
        </div>
      </div>
      {nextDrills.length > 0 ? (
        <div className="ledger-pnl-functional-strip__drill">
          <span>下一步补证</span>
          <div className="ledger-pnl-functional-strip__drill-list">
            {nextDrills.map((drill) => (
              <div key={drill.key} className="ledger-pnl-functional-strip__drill-item">
                <strong>{drill.label}</strong>
                {drill.detail ? <em>{drill.detail}</em> : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function buildDetailResidualAccountRows(props: {
  byAccount: LedgerPnlSummaryByAccount[];
  detailRows: LedgerPnlDataItem[];
  comparabilityReason: string | null;
}) {
  const detailByAccount = new Map<string, { yuan: number; hasValue: boolean; accountName: string }>();
  for (const row of props.detailRows) {
    const key = row.account_code;
    const yuan = ledgerMoneyYuan(row.monthly_pnl);
    if (!key || yuan === null) {
      continue;
    }
    const current = detailByAccount.get(key) ?? { yuan: 0, hasValue: false, accountName: row.account_name };
    current.yuan += yuan;
    current.hasValue = true;
    current.accountName ||= row.account_name;
    detailByAccount.set(key, current);
  }

  const summaryAccountCodes = new Set<string>();
  const rows: Array<{
    accountCode: string;
    accountName: string;
    summaryYuan: number | null;
    detailYuan: number;
    diff: number | null;
    judgment: string;
    comparabilityReason: string | null;
  }> = props.byAccount.map((row) => {
    summaryAccountCodes.add(row.account_code);
    const summaryYuan = ledgerMoneyYuan(row.total_pnl);
    const detail = detailByAccount.get(row.account_code);
    const detailYuan = detail?.hasValue ? detail.yuan : 0;
    const diff = summaryYuan === null ? null : summaryYuan - detailYuan;
    return {
      accountCode: row.account_code,
      accountName: row.account_name,
      summaryYuan,
      detailYuan,
      diff,
      comparabilityReason: props.comparabilityReason,
      judgment:
        props.comparabilityReason
          ? "可比性待核"
          : diff === null
          ? "待校验"
          : Math.abs(diff) < LEDGER_RECONCILIATION_TOLERANCE_YUAN
            ? "已闭合"
            : diff > 0
              ? `缺明细 ${formatYuanAsYi(diff)}`
              : `明细多 ${formatYuanAsYi(Math.abs(diff))}`,
    };
  });

  for (const [accountCode, detail] of detailByAccount) {
    if (summaryAccountCodes.has(accountCode)) {
      continue;
    }
    const diff = -detail.yuan;
    rows.push({
      accountCode,
      accountName: detail.accountName,
      summaryYuan: 0,
      detailYuan: detail.yuan,
      diff,
      comparabilityReason: props.comparabilityReason,
      judgment:
        props.comparabilityReason
          ? "可比性待核"
          : Math.abs(diff) < LEDGER_RECONCILIATION_TOLERANCE_YUAN
          ? "已闭合"
          : `汇总缺失 ${formatYuanAsYi(Math.abs(diff))}`,
    });
  }

  return rows
    .filter((row) => row.diff === null || Math.abs(row.diff) >= LEDGER_RECONCILIATION_TOLERANCE_YUAN)
    .sort((left, right) => Math.abs(right.diff ?? 0) - Math.abs(left.diff ?? 0))
    .slice(0, 5);
}

function buildDetailExposureIntensityRows(detailRows: LedgerPnlDataItem[]) {
  return detailRows
    .map((row) => {
      const monthlyPnlYuan = ledgerMoneyYuan(row.monthly_pnl);
      const dailyAvgBalanceYuan = ledgerMoneyYuan(row.daily_avg_balance);
      const daysInPeriod = row.days_in_period;
      if (
        monthlyPnlYuan === null ||
        dailyAvgBalanceYuan === null ||
        !Number.isFinite(daysInPeriod) ||
        daysInPeriod <= 0 ||
        Math.abs(dailyAvgBalanceYuan) < LEDGER_RECONCILIATION_TOLERANCE_YUAN
      ) {
        return null;
      }
      const exposureTimeYuan = Math.abs(dailyAvgBalanceYuan) * (daysInPeriod / 365);
      if (exposureTimeYuan < LEDGER_RECONCILIATION_TOLERANCE_YUAN) {
        return null;
      }
      return {
        accountCode: row.account_code,
        accountName: row.account_name,
        monthlyPnlYuan,
        dailyAvgBalanceYuan,
        daysInPeriod,
        annualizedIntensityPct: (monthlyPnlYuan / exposureTimeYuan) * 100,
      };
    })
    .filter((row): row is {
      accountCode: string;
      accountName: string;
      monthlyPnlYuan: number;
      dailyAvgBalanceYuan: number;
      daysInPeriod: number;
      annualizedIntensityPct: number;
    } => row !== null)
    .sort((left, right) => Math.abs(right.annualizedIntensityPct) - Math.abs(left.annualizedIntensityPct))
    .slice(0, 5);
}

function buildLedgerExplainabilityModel(props: {
  totalPnl: LedgerMoneyValue | null | undefined;
  byCurrency: LedgerPnlSummaryByCurrency[];
  byAccount: LedgerPnlSummaryByAccount[];
  detailRows: LedgerPnlDataItem[];
  summaryMeta: ResultMeta | null | undefined;
  detailMeta: ResultMeta | null | undefined;
  formalUseAllowed: boolean | undefined;
  sourceContractStatus: string | undefined;
}) {
  const totalYuan = ledgerMoneyYuan(props.totalPnl);
  const currencyYuan = sumLedgerMoney(props.byCurrency, (row) => row.total_pnl);
  const accountYuan = sumLedgerMoney(props.byAccount, (row) => row.total_pnl);
  const detailYuan = sumLedgerMoney(props.detailRows, (row) => row.monthly_pnl);
  const summaryDetailComparabilityReason = firstMetaMismatch(props.summaryMeta, props.detailMeta);
  const checks = [
    { label: "币种合计", diff: differenceYuan(totalYuan, currencyYuan), comparabilityReason: null },
    { label: "科目汇总", diff: differenceYuan(totalYuan, accountYuan), comparabilityReason: null },
    { label: "明细", diff: differenceYuan(totalYuan, detailYuan), comparabilityReason: summaryDetailComparabilityReason },
  ];
  const comparableChecks = checks.filter((check) => !check.comparabilityReason);
  const largestResidualCheck =
    comparableChecks
      .filter(
        (check): check is { label: string; diff: number; comparabilityReason: string | null } => check.diff !== null,
      )
      .sort((left, right) => Math.abs(right.diff) - Math.abs(left.diff))[0] ?? null;
  const hasMaterialGap = comparableChecks.some(
    (check) => check.diff !== null && Math.abs(check.diff) >= LEDGER_RECONCILIATION_TOLERANCE_YUAN,
  );
  const hasPendingCheck = checks.some((check) => check.diff === null || check.comparabilityReason);
  const hasUnknownCheck = checks.some((check) => check.diff === null);
  const residualDiagnosticRows = buildLedgerResidualDiagnosticRows({
    totalYuan,
    currencyYuan,
    accountYuan,
    detailYuan,
    detailComparabilityReason: summaryDetailComparabilityReason,
  });
  const evidenceEntryPoint =
    residualDiagnosticRows
      .filter((row) => row.diff === null || Math.abs(row.diff) >= LEDGER_RECONCILIATION_TOLERANCE_YUAN)
      .sort(
        (left, right) =>
          evidenceEntryRank(right) - evidenceEntryRank(left) ||
          Math.abs(right.diff ?? 0) - Math.abs(left.diff ?? 0),
      )[0]?.evidence ?? "暂无补证入口";
  const residualYuan =
    largestResidualCheck && (hasMaterialGap || !hasPendingCheck) ? largestResidualCheck.diff : null;
  const largestResidualStatus = largestResidualCheck
    ? `${largestResidualCheck.label}${reconciliationStatus(largestResidualCheck.diff)}`
    : null;
  const bottleneck =
    hasMaterialGap && largestResidualStatus
      ? largestResidualStatus
      : summaryDetailComparabilityReason ?? largestResidualStatus ?? "暂无可校验卡点";
  const absTotalYuan = totalYuan === null ? null : Math.abs(totalYuan);
  const absResidualYuan = residualYuan === null ? null : Math.abs(residualYuan);
  const explanationCoveragePct =
    absTotalYuan === null || absResidualYuan === null
      ? null
      : absTotalYuan < LEDGER_RECONCILIATION_TOLERANCE_YUAN
        ? absResidualYuan < LEDGER_RECONCILIATION_TOLERANCE_YUAN
          ? 100
          : 0
        : Math.max(0, Math.min(100, (1 - absResidualYuan / absTotalYuan) * 100));
  return {
    totalYuan,
    checks,
    verdict: hasMaterialGap
        ? "解释链未闭合"
        : hasPendingCheck
          ? "解释链待校验"
          : "解释链闭合",
    comparabilityStatus: summaryDetailComparabilityReason
      ? "汇总/明细口径待核"
      : hasUnknownCheck
        ? "切片可比/数据待补"
        : "当前切片可比",
    explanationCoveragePct,
    bottleneck,
    evidenceEntryPoint,
    driverRows: buildLedgerDriverRows(props.byAccount),
    residualDiagnosticRows,
    currencyResidualRows: buildCurrencyResidualRows({
      byCurrency: props.byCurrency,
      detailRows: props.detailRows,
      comparabilityReason: summaryDetailComparabilityReason,
    }),
    detailResidualAccountRows: buildDetailResidualAccountRows({
      byAccount: props.byAccount,
      detailRows: props.detailRows,
      comparabilityReason: summaryDetailComparabilityReason,
    }),
    exposureIntensityRows: buildDetailExposureIntensityRows(props.detailRows),
    exposureIntensityEvidence: detailSliceEvidence(props.detailMeta),
    residualYuan,
    formalBoundary:
      props.formalUseAllowed === true
        ? "正式口径已放行"
        : props.sourceContractStatus === "missing_contract"
          ? "正式财务指标未接入"
          : "正式口径待确认",
  };
}

function LedgerExplainabilityPanel(props: {
  model: ReturnType<typeof buildLedgerExplainabilityModel>;
  isLoading: boolean;
  isError: boolean;
}) {
  return (
    <section data-testid="ledger-pnl-explainability-panel" className="ledger-pnl-analysis">
      <div className="ledger-pnl-analysis__header">
        <div>
          <h2 className="ledger-pnl-analysis__title">损益解释模型</h2>
          <div className="ledger-pnl-analysis__subtitle">
            分析口径：先校验总账闭环，再按科目名称做经济驱动归类；不替代正式财务指标。
          </div>
        </div>
        <span className="ledger-pnl-analysis__month">{props.model.formalBoundary}</span>
      </div>

      {props.isLoading ? (
        <div className="ledger-pnl-analysis__empty">损益解释模型读取中</div>
      ) : props.isError ? (
        <div className="ledger-pnl-analysis__empty">损益解释模型读取失败</div>
      ) : (
        <>
          <div className="ledger-pnl-analysis__kpis">
            <div className="ledger-pnl-analysis__kpi">
              <div className="ledger-pnl-analysis__kpi-label">结论等级</div>
              <div className="ledger-pnl-analysis__kpi-value">{props.model.verdict}</div>
            </div>
            <div className="ledger-pnl-analysis__kpi">
              <div className="ledger-pnl-analysis__kpi-label">口径状态</div>
              <div className="ledger-pnl-analysis__kpi-value">{props.model.comparabilityStatus}</div>
            </div>
            <div className="ledger-pnl-analysis__kpi">
              <div className="ledger-pnl-analysis__kpi-label">解释覆盖率</div>
              <div className="ledger-pnl-analysis__kpi-value">
                {formatPercent(props.model.explanationCoveragePct)}
              </div>
            </div>
            <div className="ledger-pnl-analysis__kpi">
              <div className="ledger-pnl-analysis__kpi-label">最大卡点</div>
              <div className="ledger-pnl-analysis__kpi-value">{props.model.bottleneck}</div>
            </div>
            <div className="ledger-pnl-analysis__kpi">
              <div className="ledger-pnl-analysis__kpi-label">补证入口</div>
              <div className="ledger-pnl-analysis__kpi-value">{props.model.evidenceEntryPoint}</div>
            </div>
            <div className="ledger-pnl-analysis__kpi">
              <div className="ledger-pnl-analysis__kpi-label">总账全量损益</div>
              <div className="ledger-pnl-analysis__kpi-value">{formatYuanAsYi(props.model.totalYuan)}</div>
            </div>
            {props.model.checks.map((check) => (
              <div key={check.label} className="ledger-pnl-analysis__kpi">
                <div className="ledger-pnl-analysis__kpi-label">{check.label}</div>
                <div className="ledger-pnl-analysis__kpi-value">
                  {check.comparabilityReason ? "可比性待核" : `${check.label}${reconciliationStatus(check.diff)}`}
                </div>
              </div>
            ))}
            <div className="ledger-pnl-analysis__kpi">
              <div className="ledger-pnl-analysis__kpi-label">未解释残差</div>
              <div className="ledger-pnl-analysis__kpi-value">
                未解释残差 {formatYuanAsYi(props.model.residualYuan)}
              </div>
            </div>
          </div>

          <div
            data-testid="ledger-pnl-residual-diagnostic-table"
            className="ledger-pnl-analysis__table ledger-pnl-analysis__residual-table-wrap"
          >
            <div className="ledger-pnl-analysis__table-title">残差诊断表</div>
            <table className="ledger-pnl-analysis__residual-table">
              <thead>
                <tr>
                  <th>卡点层级</th>
                  <th>总账金额</th>
                  <th>对账金额</th>
                  <th>差异金额</th>
                  <th>诊断判断</th>
                  <th>需要补的证据</th>
                </tr>
              </thead>
              <tbody>
                {props.model.residualDiagnosticRows.map((row) => (
                  <tr key={row.layer}>
                    <td>{row.layer}</td>
                    <td>{formatYuanAsYi(row.ledgerYuan)}</td>
                    <td>{formatYuanAsYi(row.reconciliationYuan)}</td>
                    <td>{formatYuanAsYi(row.diff)}</td>
                    <td>{row.judgment}</td>
                    <td>{row.evidence}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div
            data-testid="ledger-pnl-currency-residual-table"
            className="ledger-pnl-analysis__table ledger-pnl-analysis__residual-table-wrap"
          >
            <div className="ledger-pnl-analysis__table-title">币种残差候选</div>
            <div className="ledger-pnl-analysis__source-contract-note">
              当前仅按本页总账汇总与明细切片的币种代码和元金额派生；币种映射、折算规则或报告日期不一致时，差异只能作为待核线索。
            </div>
            {props.model.currencyResidualRows.length > 0 ? (
              <table className="ledger-pnl-analysis__residual-table">
                <thead>
                  <tr>
                    <th>币种</th>
                    <th>币种汇总金额</th>
                    <th>明细币种金额</th>
                    <th>明细毛活动</th>
                    <th>差异金额</th>
                    <th>诊断判断</th>
                    <th>口径证据</th>
                  </tr>
                </thead>
                <tbody>
                  {props.model.currencyResidualRows.map((row) => (
                    <tr key={row.currency}>
                      <td>{row.currency}</td>
                      <td>{formatYuanAsYi(row.summaryYuan)}</td>
                      <td>{formatYuanAsYi(row.detailYuan)}</td>
                      <td>{formatYuanAsYi(row.detailGrossYuan)}</td>
                      <td>{formatYuanAsYi(row.diff)}</td>
                      <td>{row.judgment}</td>
                      <td>{row.comparabilityReason ?? "当前切片可比"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="ledger-pnl-analysis__empty">暂无币种级明细残差候选</div>
            )}
          </div>

          <div
            data-testid="ledger-pnl-detail-residual-account-table"
            className="ledger-pnl-analysis__table ledger-pnl-analysis__residual-table-wrap"
          >
            <div className="ledger-pnl-analysis__table-title">明细残差候选科目</div>
            {props.model.detailResidualAccountRows.length > 0 ? (
              <table className="ledger-pnl-analysis__residual-table">
                <thead>
                  <tr>
                    <th>科目</th>
                    <th>科目汇总金额</th>
                    <th>明细合计金额</th>
                    <th>差异金额</th>
                    <th>诊断判断</th>
                    <th>口径证据</th>
                  </tr>
                </thead>
                <tbody>
                  {props.model.detailResidualAccountRows.map((row) => (
                    <tr key={row.accountCode}>
                      <td>
                        {row.accountCode} {row.accountName}
                      </td>
                      <td>{formatYuanAsYi(row.summaryYuan)}</td>
                      <td>{formatYuanAsYi(row.detailYuan)}</td>
                      <td>{formatYuanAsYi(row.diff)}</td>
                      <td>{row.judgment}</td>
                      <td>{row.comparabilityReason ?? "当前切片可比"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="ledger-pnl-analysis__empty">暂无科目级明细残差候选</div>
            )}
          </div>

          <div
            data-testid="ledger-pnl-driver-direction-table"
            className="ledger-pnl-analysis__table ledger-pnl-analysis__residual-table-wrap"
          >
            <div className="ledger-pnl-analysis__table-title">损益方向拆解</div>
            <div className="ledger-pnl-analysis__empty">
              候选归类：按总账科目代码和名称启发式归类，用于定位解释线索，不是正式产品、策略或管理归因维度。
            </div>
            {props.model.driverRows.length > 0 ? (
              <table className="ledger-pnl-analysis__residual-table ledger-pnl-analysis__direction-table">
                <thead>
                  <tr>
                    <th>经济驱动</th>
                    <th>净额金额</th>
                    <th>毛贡献金额</th>
                    <th>毛拖累金额</th>
                    <th>净额抵消率</th>
                    <th>最大科目</th>
                  </tr>
                </thead>
                <tbody>
                  {props.model.driverRows.map((row) => (
                    <tr key={row.label}>
                      <td>{row.label}</td>
                      <td>{formatYuanAsYi(row.yuan)}</td>
                      <td>{formatYuanAsYi(row.positiveYuan)}</td>
                      <td>{formatYuanAsYi(row.negativeYuan)}</td>
                      <td>{formatPercent(row.offsetRatioPct)}</td>
                      <td>{row.topAccount}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="ledger-pnl-analysis__empty">暂无可拆解的损益方向数据</div>
            )}
          </div>

          <div
            data-testid="ledger-pnl-exposure-intensity-table"
            className="ledger-pnl-analysis__table ledger-pnl-analysis__residual-table-wrap"
          >
            <div className="ledger-pnl-analysis__table-title">规模时间强度候选</div>
            <div className="ledger-pnl-analysis__source-contract-note">
              明细派生候选：按月损益 / (|日均规模| × 天数 / 365) 计算，仅用于定位异常解释线索，不是正式收益率或财务指标。
            </div>
            <div className="ledger-pnl-analysis__source-contract-note">{props.model.exposureIntensityEvidence}</div>
            {props.model.exposureIntensityRows.length > 0 ? (
              <table className="ledger-pnl-analysis__residual-table">
                <thead>
                  <tr>
                    <th>科目</th>
                    <th>月损益</th>
                    <th>日均规模</th>
                    <th>天数</th>
                    <th>候选年化强度</th>
                  </tr>
                </thead>
                <tbody>
                  {props.model.exposureIntensityRows.map((row, index) => (
                    <tr key={`${row.accountCode}-${row.daysInPeriod}-${index}`}>
                      <td>
                        {row.accountCode} {row.accountName}
                      </td>
                      <td>{formatYuanAsYi(row.monthlyPnlYuan)}</td>
                      <td>{formatYuanAsYi(row.dailyAvgBalanceYuan)}</td>
                      <td>{row.daysInPeriod}</td>
                      <td>{formatPercent(row.annualizedIntensityPct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="ledger-pnl-analysis__empty">暂无可计算的规模时间强度候选</div>
            )}
          </div>

          <div className="ledger-pnl-analysis__tables">
            {props.model.driverRows.length > 0 ? (
              props.model.driverRows.map((row) => (
                <article key={row.label} className="ledger-pnl-analysis__status-row ledger-pnl-analysis__status-row--analytical">
                  <div className="ledger-pnl-analysis__status-main">
                    <span className="ledger-pnl-analysis__status-name">{row.label}</span>
                    <span className="ledger-pnl-analysis__status-badge">{row.count} 科目</span>
                  </div>
                  <div className="ledger-pnl-analysis__status-value">{formatYuanAsYi(row.yuan)}</div>
                  <div className="ledger-pnl-analysis__status-source">{row.topAccount}</div>
                </article>
              ))
            ) : (
              <div className="ledger-pnl-analysis__empty">暂无可归类的科目驱动数据</div>
            )}
          </div>

          <div className="ledger-pnl-analysis__source-contract-note">
            {props.model.formalBoundary}；本区仅用于解释总账分析链路，正式口径待确认前不得把候选解释写作正式财务结论。
          </div>
        </>
      )}
    </section>
  );
}

function reportDateToMonth(reportDate: string) {
  const match = /^(\d{4})-(\d{2})/.exec(reportDate.trim());
  return match ? `${match[1]}${match[2]}` : "";
}

function formatAnalysisValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
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

function pickDisplayColumns(sheet: QdbGlMonthlyAnalysisSheet | undefined, limit = 4) {
  return (sheet?.columns ?? []).slice(0, limit);
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

  return (
    <section
      data-testid="ledger-pnl-formal-indicator-source-contract-panel"
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

      {props.isLoading ? (
        <div className="ledger-pnl-analysis__empty">正式财务指标源契约读取中</div>
      ) : props.isError ? (
        <div className="ledger-pnl-analysis__empty">正式财务指标源契约读取失败</div>
      ) : metrics.length > 0 ? (
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
      ) : (
        <div className="ledger-pnl-analysis__empty">暂无正式财务指标源契约数据</div>
      )}
    </section>
  );
}

function AnalysisTable(props: {
  title: string;
  sheet: QdbGlMonthlyAnalysisSheet | undefined;
  testId: string;
  columnLimit?: number;
  rowLimit?: number;
}) {
  const columns = pickDisplayColumns(props.sheet, props.columnLimit ?? 4);
  const rows = props.sheet?.rows.slice(0, props.rowLimit ?? 5) ?? [];
  return (
    <section data-testid={props.testId} className="ledger-pnl-analysis__table">
      <div className="ledger-pnl-analysis__table-title">
        {props.title}
      </div>
      {columns.length > 0 && rows.length > 0 ? (
        <table style={tableStyle}>
          <thead>
            <tr className="ledger-pnl-analysis__table-head-row">
              {columns.map((column) => (
                <th key={column} className="ledger-pnl-analysis__th">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={`${props.testId}-${rowIndex}`} className="ledger-pnl-analysis__tr">
                {columns.map((column) => (
                  <td key={column} className="ledger-pnl-analysis__td">
                    {formatAnalysisValue(row[column])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="ledger-pnl-analysis__empty">暂无可展示数据</div>
      )}
    </section>
  );
}

export default function LedgerPnlPage() {
  const client = useApiClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const reportDateFromQuery = searchParams.get("report_date")?.trim() ?? "";
  const currencyFromQuery = searchParams.get("currency")?.trim() ?? "";
  const [selectedReportDate, setSelectedReportDate] = useState(reportDateFromQuery);
  const [currency, setCurrency] = useState(currencyFromQuery || "ALL");
  const lastSyncedReportDateFromQueryRef = useRef(reportDateFromQuery);

  const datesQuery = useQuery({
    queryKey: ["ledger-pnl", "dates", client.mode],
    queryFn: () => client.getLedgerPnlDates(),
    retry: false,
  });

  const reportDates = useMemo(() => datesQuery.data?.result.dates ?? [], [datesQuery.data?.result.dates]);

  useEffect(() => {
    if (reportDateFromQuery) {
      if (lastSyncedReportDateFromQueryRef.current !== reportDateFromQuery) {
        lastSyncedReportDateFromQueryRef.current = reportDateFromQuery;
        setSelectedReportDate((current) => (current === reportDateFromQuery ? current : reportDateFromQuery));
      }
      return;
    }
    lastSyncedReportDateFromQueryRef.current = "";
    const firstDate = reportDates[0];
    if (!firstDate) {
      return;
    }
    if (!selectedReportDate || !reportDates.includes(selectedReportDate)) {
      setSelectedReportDate(firstDate);
    }
  }, [reportDateFromQuery, reportDates, selectedReportDate]);

  const effectiveCurrency = currency === "ALL" ? undefined : currency;

  const summaryQuery = useQuery({
    queryKey: ["ledger-pnl", "summary", client.mode, selectedReportDate, effectiveCurrency],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getLedgerPnlSummary(selectedReportDate, effectiveCurrency),
    retry: false,
  });

  const dataQuery = useQuery({
    queryKey: ["ledger-pnl", "data", client.mode, selectedReportDate, effectiveCurrency],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getLedgerPnlData(selectedReportDate, effectiveCurrency),
    retry: false,
  });

  const monthlyAnalysisDatesQuery = useQuery({
    queryKey: ["ledger-pnl", "monthly-analysis", "dates", client.mode],
    queryFn: () => client.getQdbGlMonthlyAnalysisDates(),
    retry: false,
  });

  const summary = summaryQuery.data?.result;
  const data = dataQuery.data?.result;
  const accountSummaryRows = useMemo(() => summary?.by_account ?? [], [summary?.by_account]);
  const visibleAccountSummaryRows = useMemo(
    () =>
      sortLedgerRowsByAbsYuan(accountSummaryRows, (item) => item.total_pnl).slice(
        0,
        LEDGER_TABLE_ROW_LIMIT,
      ),
    [accountSummaryRows],
  );
  const detailRows = useMemo(() => data?.items ?? [], [data?.items]);
  const pnlExplainabilityDetailRows = useMemo(
    () => filterPnlExplainabilityDetailRows(detailRows, accountSummaryRows),
    [accountSummaryRows, detailRows],
  );
  const visibleDetailRows = useMemo(
    () =>
      sortLedgerRowsByAbsYuan(detailRows, (item) => item.monthly_pnl).slice(
        0,
        LEDGER_TABLE_ROW_LIMIT,
      ),
    [detailRows],
  );
  const monthlyAnalysisMonths = monthlyAnalysisDatesQuery.data?.result.report_months ?? [];
  const requestedAnalysisMonth = reportDateToMonth(selectedReportDate) || reportDateToMonth(reportDateFromQuery);
  const selectedReportDateMissingFromDates =
    Boolean(selectedReportDate) &&
    !datesQuery.isLoading &&
    reportDates.length > 0 &&
    !reportDates.includes(selectedReportDate);
  const hasMatchingAnalysisMonth =
    Boolean(requestedAnalysisMonth) && monthlyAnalysisMonths.includes(requestedAnalysisMonth);
  const selectedAnalysisMonth = hasMatchingAnalysisMonth ? requestedAnalysisMonth : "";

  const formalIndicatorSourceContractQuery = useQuery({
    queryKey: ["ledger-pnl", "formal-financial-indicators", client.mode, requestedAnalysisMonth],
    enabled: Boolean(requestedAnalysisMonth),
    queryFn: () => client.getLedgerPnlFormalFinancialIndicators(requestedAnalysisMonth),
    retry: false,
  });

  const monthlyAnalysisWorkbookQuery = useQuery({
    queryKey: ["ledger-pnl", "monthly-analysis", "workbook", client.mode, selectedAnalysisMonth],
    enabled: hasMatchingAnalysisMonth,
    queryFn: () => client.getQdbGlMonthlyAnalysisWorkbook({ reportMonth: selectedAnalysisMonth }),
    retry: false,
  });

  const monthlyAnalysisWorkbook = monthlyAnalysisWorkbookQuery.data?.result;
  const formalIndicatorSourceContract = formalIndicatorSourceContractQuery.data?.result;
  const ledgerExplainabilityModel = useMemo(
    () =>
      buildLedgerExplainabilityModel({
        totalPnl: summary?.ledger_monthly_pnl_all,
        byCurrency: summary?.by_currency ?? [],
        byAccount: accountSummaryRows,
        detailRows: pnlExplainabilityDetailRows,
        summaryMeta: summaryQuery.data?.result_meta,
        detailMeta: dataQuery.data?.result_meta,
        formalUseAllowed: formalIndicatorSourceContract?.formal_use_allowed,
        sourceContractStatus: formalIndicatorSourceContract?.sample_status,
      }),
    [
      accountSummaryRows,
      formalIndicatorSourceContract?.formal_use_allowed,
      formalIndicatorSourceContract?.sample_status,
      pnlExplainabilityDetailRows,
      dataQuery.data?.result_meta,
      summary?.by_currency,
      summary?.ledger_monthly_pnl_all,
      summaryQuery.data?.result_meta,
    ],
  );
  const overviewSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "overview");
  const financialIndicatorStatusSheet = findAnalysisSheet(
    monthlyAnalysisWorkbook?.sheets,
    "financial_indicator_status",
  );
  const financialIndicatorStatusRows = useMemo(
    () => buildFinancialIndicatorStatusRows(financialIndicatorStatusSheet),
    [financialIndicatorStatusSheet],
  );
  const summary3dSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "summary_3d");
  const assetStructureSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "asset_structure");
  const liabilityStructureSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "liability_structure");
  const loanIndustrySheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "loan_industry");
  const depositDemandIndustrySheet = findAnalysisSheet(
    monthlyAnalysisWorkbook?.sheets,
    "deposit_demand_industry",
  );
  const depositTermIndustrySheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "deposit_term_industry");
  const top11dSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "top_11d");
  const alertsSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "alerts");
  const foreignCurrencySheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "foreign_currency");
  const segmentBaseScaleSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "segment_base_scale");
  const segmentScaleCompareSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "segment_scale_compare");
  const companyScaleSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "company_scale");
  const companyScaleCompareSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "company_scale_compare");
  const retailScaleSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "retail_scale");
  const retailScaleCompareSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "retail_scale_compare");
  const financialMarketScaleSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "financial_market_scale");
  const financialMarketScaleCompareSheet = findAnalysisSheet(
    monthlyAnalysisWorkbook?.sheets,
    "financial_market_scale_compare",
  );
  const incomeRateAnalysisSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "income_rate_analysis");
  const incomeRateAttributionSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "income_rate_attribution");
  const depositInterestSplitSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "deposit_interest_split");
  const parentCompanyRevenueSheet = findAnalysisSheet(
    monthlyAnalysisWorkbook?.sheets,
    "parent_company_revenue_components",
  );
  const industryGapSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "industry_gap");
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
      value: formatMoney(summary?.ledger_monthly_pnl_core),
      candidateMetricKey: "ledger_monthly_pnl_core",
    },
    {
      key: "ledger_monthly_pnl_all",
      title: "全量损益",
      value: formatMoney(summary?.ledger_monthly_pnl_all),
      candidateMetricKey: "ledger_monthly_pnl_all",
    },
    {
      key: "ledger_total_assets",
      title: "总资产",
      value: formatMoney(summary?.ledger_total_assets),
    },
    {
      key: "ledger_total_liabilities",
      title: "总负债",
      value: formatMoney(summary?.ledger_total_liabilities),
    },
    {
      key: "ledger_net_assets",
      title: "净资产",
      value: formatMoney(summary?.ledger_net_assets),
      candidateMetricKey: "ledger_net_assets",
    },
  ];

  const currencyOptions = useMemo(() => {
    const seen = new Set(["ALL"]);
    if (currencyFromQuery) {
      seen.add(currencyFromQuery);
    }
    if (currency !== "ALL") {
      seen.add(currency);
    }
    for (const item of summary?.by_currency ?? []) {
      if (item.currency) {
        seen.add(item.currency);
      }
    }
    for (const item of data?.items ?? []) {
      if (item.currency) {
        seen.add(item.currency);
      }
    }
    return Array.from(seen);
  }, [currency, currencyFromQuery, data?.items, summary?.by_currency]);

  useEffect(() => {
    if (!currencyFromQuery) {
      return;
    }
    setCurrency((current) => (current === currencyFromQuery ? current : currencyFromQuery));
  }, [currencyFromQuery]);

  useEffect(() => {
    const nextParams = new URLSearchParams(searchParams);
    if (selectedReportDate) {
      nextParams.set("report_date", selectedReportDate);
    } else {
      nextParams.delete("report_date");
    }
    if (currency !== "ALL") {
      nextParams.set("currency", currency);
    } else {
      nextParams.delete("currency");
    }

    const nextSearch = nextParams.toString();
    if (nextSearch !== searchParams.toString()) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [currency, searchParams, selectedReportDate, setSearchParams]);

  return (
    <section data-testid="ledger-pnl-page">
      <div style={pageHeaderStyle}>
        <div>
          <h1
            data-testid="ledger-pnl-page-title"
            style={{ margin: 0, fontSize: 32, fontWeight: 600, letterSpacing: 0 }}
          >
            总账损益
          </h1>
          <p data-testid="ledger-pnl-page-subtitle" style={pageSubtitleStyle}>
            科目口径损益总览、币种汇总与账户明细。页面直接消费后端总账口径读模型，
            不在前端补算会计科目聚合。
          </p>
        </div>
        <span
          style={{
            ...modeBadgeStyle,
            background:
              client.mode === "real" ? designTokens.color.success[50] : designTokens.color.primary[50],
            color:
              client.mode === "real"
                ? displayTokens.apiMode.realForeground
                : displayTokens.apiMode.mockForeground,
            whiteSpace: "nowrap",
          }}
        >
          {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
        </span>
      </div>

      <FilterBar style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 20 }}>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: designTokens.color.neutral[600] }}>报告日</span>
          <select
            aria-label="ledger-pnl-report-date"
            value={selectedReportDate}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            disabled={reportDates.length === 0}
            style={{
              minWidth: 180,
              padding: "10px 12px",
              borderRadius: designTokens.radius.md,
              border: `1px solid ${designTokens.color.neutral[200]}`,
            }}
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
          {selectedReportDateMissingFromDates ? (
            <div className="ledger-pnl-analysis__empty" style={{ padding: "6px 0 0" }}>
              当前报告日不在可选列表中，仍按查询日期读取总账数据
            </div>
          ) : null}
        </label>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: designTokens.color.neutral[600] }}>币种</span>
          <select
            aria-label="ledger-pnl-currency"
            value={currency}
            onChange={(event) => setCurrency(event.target.value)}
            style={{
              minWidth: 140,
              padding: "10px 12px",
              borderRadius: designTokens.radius.md,
              border: `1px solid ${designTokens.color.neutral[200]}`,
            }}
          >
            {currencyOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </FilterBar>

      <LedgerFunctionalAuditStrip
        selectedReportDate={selectedReportDate}
        selectedReportDateMissingFromDates={selectedReportDateMissingFromDates}
        reportDates={reportDates}
        summary={summary}
        data={data}
        datesMeta={datesQuery.data?.result_meta}
        summaryMeta={summaryQuery.data?.result_meta}
        dataMeta={dataQuery.data?.result_meta}
        formalIndicatorSourceContract={formalIndicatorSourceContract}
        isFormalContractLoading={formalIndicatorSourceContractQuery.isLoading}
        isFormalContractError={formalIndicatorSourceContractQuery.isError}
        isLoading={
          datesQuery.isLoading ||
          summaryQuery.isLoading ||
          dataQuery.isLoading ||
          formalIndicatorSourceContractQuery.isLoading
        }
        isError={datesQuery.isError || summaryQuery.isError || dataQuery.isError}
        readErrors={[datesQuery.error, summaryQuery.error, dataQuery.error]}
      />

      <div data-testid="ledger-pnl-summary-cards" style={summaryGridStyleWithBottom}>
        {summaryCards.map((card) => (
          <LedgerSummaryCard key={card.key} card={card} />
        ))}
      </div>

      <section data-testid="ledger-pnl-monthly-analysis-panel" className="ledger-pnl-analysis">
        <div className="ledger-pnl-analysis__header">
          <div>
            <h2 className="ledger-pnl-analysis__title">
              总账对账 + 日均分析
            </h2>
            <div className="ledger-pnl-analysis__subtitle">
              月度工作簿口径，直接展示后端已重建的分析结果。
            </div>
          </div>
          <span data-testid="ledger-pnl-monthly-analysis-month" className="ledger-pnl-analysis__month">
            {selectedAnalysisMonth || (requestedAnalysisMonth ? `${requestedAnalysisMonth} 无匹配` : "暂无月份")}
          </span>
        </div>

        {!hasMatchingAnalysisMonth && !monthlyAnalysisDatesQuery.isLoading ? (
          <div data-testid="ledger-pnl-monthly-analysis-missing-month" className="ledger-pnl-analysis__empty">
            当前报告日没有对应月度分析工作簿
          </div>
        ) : null}

        {monthlyAnalysisDatesQuery.isError ? (
          <div data-testid="ledger-pnl-monthly-analysis-error" className="ledger-pnl-analysis__empty">
            月度分析月份读取失败
          </div>
        ) : null}

        {monthlyAnalysisWorkbookQuery.isError ? (
          <div data-testid="ledger-pnl-monthly-analysis-error" className="ledger-pnl-analysis__empty">
            月度分析工作簿读取失败
          </div>
        ) : null}

        <FormalIndicatorSourceContractPanel
          contract={formalIndicatorSourceContract}
          requestedReportMonth={requestedAnalysisMonth}
          isLoading={formalIndicatorSourceContractQuery.isLoading}
          isError={formalIndicatorSourceContractQuery.isError}
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

        <div className="ledger-pnl-analysis__tables">
          <AnalysisTable
            title="财务指标落地状态"
            sheet={financialIndicatorStatusSheet}
            testId="ledger-pnl-monthly-analysis-financial-indicator-status"
            columnLimit={5}
            rowLimit={20}
          />
          <AnalysisTable
            title="3位科目总览"
            sheet={summary3dSheet}
            testId="ledger-pnl-monthly-analysis-summary-3d"
            columnLimit={8}
            rowLimit={8}
          />
          <AnalysisTable
            title="资产结构"
            sheet={assetStructureSheet}
            testId="ledger-pnl-monthly-analysis-asset-structure"
            columnLimit={6}
            rowLimit={8}
          />
          <AnalysisTable
            title="负债结构"
            sheet={liabilityStructureSheet}
            testId="ledger-pnl-monthly-analysis-liability-structure"
            columnLimit={6}
            rowLimit={8}
          />
          <AnalysisTable
            title="贷款行业"
            sheet={loanIndustrySheet}
            testId="ledger-pnl-monthly-analysis-loan-industry"
            columnLimit={7}
            rowLimit={8}
          />
          <AnalysisTable
            title="存款行业_活期"
            sheet={depositDemandIndustrySheet}
            testId="ledger-pnl-monthly-analysis-deposit-demand-industry"
            columnLimit={7}
            rowLimit={8}
          />
          <AnalysisTable
            title="存款行业_定期"
            sheet={depositTermIndustrySheet}
            testId="ledger-pnl-monthly-analysis-deposit-term-industry"
            columnLimit={7}
            rowLimit={8}
          />
          <AnalysisTable
            title="11位偏离TOP"
            sheet={top11dSheet}
            testId="ledger-pnl-monthly-analysis-top-11d"
            columnLimit={5}
          />
          <AnalysisTable
            title="异动预警"
            sheet={alertsSheet}
            testId="ledger-pnl-monthly-analysis-alerts"
            columnLimit={5}
          />
          <AnalysisTable
            title="分部基础规模"
            sheet={segmentBaseScaleSheet}
            testId="ledger-pnl-monthly-analysis-segment-base-scale"
            columnLimit={5}
          />
          <AnalysisTable
            title="分部规模同比环比"
            sheet={segmentScaleCompareSheet}
            testId="ledger-pnl-monthly-analysis-segment-scale-compare"
            columnLimit={7}
          />
          <AnalysisTable
            title="公司规模"
            sheet={companyScaleSheet}
            testId="ledger-pnl-monthly-analysis-company-scale"
            columnLimit={5}
          />
          <AnalysisTable
            title="公司规模同比环比"
            sheet={companyScaleCompareSheet}
            testId="ledger-pnl-monthly-analysis-company-scale-compare"
            columnLimit={7}
          />
          <AnalysisTable
            title="零售规模"
            sheet={retailScaleSheet}
            testId="ledger-pnl-monthly-analysis-retail-scale"
            columnLimit={5}
          />
          <AnalysisTable
            title="零售规模同比环比"
            sheet={retailScaleCompareSheet}
            testId="ledger-pnl-monthly-analysis-retail-scale-compare"
            columnLimit={7}
          />
          <AnalysisTable
            title="金融市场规模"
            sheet={financialMarketScaleSheet}
            testId="ledger-pnl-monthly-analysis-financial-market-scale"
            columnLimit={5}
          />
          <AnalysisTable
            title="金融市场规模同比环比"
            sheet={financialMarketScaleCompareSheet}
            testId="ledger-pnl-monthly-analysis-financial-market-scale-compare"
            columnLimit={7}
          />
          <AnalysisTable
            title="收益率分析（总账可复算）"
            sheet={incomeRateAnalysisSheet}
            testId="ledger-pnl-monthly-analysis-income-rate"
            columnLimit={7}
          />
          <AnalysisTable
            title="收益量价归因（年累计同比）"
            sheet={incomeRateAttributionSheet}
            testId="ledger-pnl-monthly-analysis-income-rate-attribution"
            columnLimit={9}
          />
          <AnalysisTable
            title="存款利息拆分"
            sheet={depositInterestSplitSheet}
            testId="ledger-pnl-monthly-analysis-deposit-interest-split"
            columnLimit={11}
            rowLimit={9}
          />
          <AnalysisTable
            title="母公司营收分项"
            sheet={parentCompanyRevenueSheet}
            testId="ledger-pnl-monthly-analysis-parent-company-revenue"
            columnLimit={11}
            rowLimit={17}
          />
          <AnalysisTable
            title="外币分析"
            sheet={foreignCurrencySheet}
            testId="ledger-pnl-monthly-analysis-foreign-currency"
            columnLimit={6}
            rowLimit={8}
          />
          <AnalysisTable
            title="行业存贷差"
            sheet={industryGapSheet}
            testId="ledger-pnl-monthly-analysis-industry-gap"
            columnLimit={5}
          />
        </div>
      </section>

      <LedgerExplainabilityPanel
        model={ledgerExplainabilityModel}
        isLoading={summaryQuery.isLoading || dataQuery.isLoading || formalIndicatorSourceContractQuery.isLoading}
        isError={summaryQuery.isError || dataQuery.isError || formalIndicatorSourceContractQuery.isError}
      />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
        <div data-testid="ledger-pnl-currency-summary-table" style={tableWrapStyle}>
          <div
            style={{
              padding: designTokens.space[4],
              fontWeight: 600,
              borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
            }}
          >
            币种汇总
          </div>
          <table style={tableStyle}>
            <thead>
              <tr style={{ background: designTokens.color.neutral[50] }}>
                <th style={{ textAlign: "left", padding: designTokens.space[3] }}>币种</th>
                <th style={{ textAlign: "right", padding: designTokens.space[3] }}>损益</th>
              </tr>
            </thead>
            <tbody>
              {summaryQuery.isLoading ? (
                <LedgerTableStateRow colSpan={2} message="币种汇总读取中" />
              ) : summaryQuery.isError ? (
                <LedgerTableStateRow colSpan={2} message="币种汇总读取失败" />
              ) : (summary?.by_currency ?? []).length > 0 ? (
                (summary?.by_currency ?? []).map((item) => (
                  <tr key={item.currency} style={{ borderTop: `1px solid ${designTokens.color.neutral[100]}` }}>
                    <td style={{ padding: designTokens.space[3] }}>{item.currency}</td>
                    <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.total_pnl)}</td>
                  </tr>
                ))
              ) : (
                <LedgerTableStateRow colSpan={2} message="暂无币种汇总数据" />
              )}
            </tbody>
          </table>
        </div>

        <div data-testid="ledger-pnl-account-summary-table" style={tableWrapStyle}>
          <div
            style={{
              padding: designTokens.space[4],
              fontWeight: 600,
              borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
            }}
          >
            科目汇总
          </div>
          <table style={tableStyle}>
            <thead>
              <tr style={{ background: designTokens.color.neutral[50] }}>
                <th style={{ textAlign: "left", padding: designTokens.space[3] }}>科目</th>
                <th style={{ textAlign: "right", padding: designTokens.space[3] }}>损益</th>
                <th style={{ textAlign: "right", padding: designTokens.space[3] }}>笔数</th>
              </tr>
            </thead>
            <tbody>
              {summaryQuery.isLoading ? (
                <LedgerTableStateRow colSpan={3} message="科目汇总读取中" />
              ) : summaryQuery.isError ? (
                <LedgerTableStateRow colSpan={3} message="科目汇总读取失败" />
              ) : accountSummaryRows.length > 0 ? (
                <>
                  {visibleAccountSummaryRows.map((item) => (
                    <tr key={item.account_code} style={{ borderTop: `1px solid ${designTokens.color.neutral[100]}` }}>
                      <td style={{ padding: designTokens.space[3] }}>
                        <div>{item.account_code}</div>
                        <div style={{ color: designTokens.color.neutral[600], fontSize: designTokens.fontSize[12] }}>
                          {item.account_name}
                        </div>
                      </td>
                      <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.total_pnl)}</td>
                      <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{item.count}</td>
                    </tr>
                  ))}
                  <LedgerTableTruncationRow
                    colSpan={3}
                    label="科目汇总"
                    total={accountSummaryRows.length}
                  />
                </>
              ) : (
                <LedgerTableStateRow colSpan={3} message="暂无科目汇总数据" />
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div data-testid="ledger-pnl-detail-table" style={tableWrapStyle}>
        <div
          style={{
            padding: designTokens.space[4],
            fontWeight: 600,
            borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
          }}
        >
          科目明细
        </div>
        <table style={tableStyle}>
          <thead>
            <tr style={{ background: designTokens.color.neutral[50] }}>
              <th style={{ textAlign: "left", padding: designTokens.space[3] }}>科目代码</th>
              <th style={{ textAlign: "left", padding: designTokens.space[3] }}>科目名称</th>
              <th style={{ textAlign: "left", padding: designTokens.space[3] }}>币种</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>期初</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>期末</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>月损益</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>月日均</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>天数</th>
            </tr>
          </thead>
          <tbody>
            {dataQuery.isLoading ? (
              <LedgerTableStateRow colSpan={8} message="科目明细读取中" />
            ) : dataQuery.isError ? (
              <LedgerTableStateRow colSpan={8} message="科目明细读取失败" />
            ) : detailRows.length > 0 ? (
              <>
                {visibleDetailRows.map((item) => (
                  <tr key={`${item.account_code}-${item.currency}`} style={{ borderTop: `1px solid ${designTokens.color.neutral[100]}` }}>
                    <td style={{ padding: designTokens.space[3] }}>{item.account_code}</td>
                    <td style={{ padding: designTokens.space[3] }}>{item.account_name}</td>
                    <td style={{ padding: designTokens.space[3] }}>{item.currency}</td>
                    <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.beginning_balance)}</td>
                    <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.ending_balance)}</td>
                    <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.monthly_pnl)}</td>
                    <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.daily_avg_balance)}</td>
                    <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{item.days_in_period}</td>
                  </tr>
                ))}
                <LedgerTableTruncationRow colSpan={8} label="科目明细" total={detailRows.length} />
              </>
            ) : (
              <LedgerTableStateRow colSpan={8} message="暂无科目明细数据" />
            )}
          </tbody>
        </table>
      </div>

      <FormalResultMetaPanel
        testId="ledger-pnl-result-meta-panel"
        sections={[
          { key: "dates", title: "Ledger 报告日", meta: datesQuery.data?.result_meta },
          { key: "summary", title: "Ledger 汇总", meta: summaryQuery.data?.result_meta },
          { key: "data", title: "Ledger 明细", meta: dataQuery.data?.result_meta },
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
    </section>
  );
}
