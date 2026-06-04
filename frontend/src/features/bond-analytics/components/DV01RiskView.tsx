import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Radio, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { useApiClient } from "../../../api/client";
import type {
  DV01ActionBondItem,
  DV01ActionIssuerItem,
  DV01ActionScenarioBreach,
  DV01ActionTenorItem,
  DV01LimitConfigStatusPayload,
  DV01LimitConfigStatusRow,
  DV01MovementAttributionItem,
  DV01MovementBondItem,
  DV01ReconciliationRow,
  DV01ShockScenario,
  DV01TenorBucket,
  DV01TopBondItem,
  DV01TopIssuerItem,
  Numeric,
} from "../../../api/contracts";
import { apiQueryKeys } from "../../../api/queryKeys";
import { tabularNumsStyle } from "../../../theme/designSystem";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type {
  BondAnalyticsDV01AccountingClassFilter,
  DV01ActionPlanResponse,
  DV01MovementResponse,
  DV01ReconciliationResponse,
  DV01RiskResponse,
} from "../types";
import { formatPct, formatYi } from "../utils/formatters";
import { SectionLead } from "./SectionLead";
import styles from "./DV01RiskView.module.css";

const DEFAULT_SHOCK_BPS = "1,10,25,50";
const DV01_LIMIT_REVIEW_PACKAGE_DIR = ".tmp\\bond_dv01_limit_config_review_package";
const TOP_N_OPTIONS = [10, 20, 30, 50, 100] as const;

type DV01AccountingOption = {
  label: string;
  value: BondAnalyticsDV01AccountingClassFilter;
};

const ACCOUNTING_CLASS_OPTIONS: DV01AccountingOption[] = [
  { label: "AC", value: "AC" },
  { label: "OCI", value: "OCI" },
  { label: "TPL", value: "TPL" },
  { label: "全部", value: "all" },
];

interface Props {
  reportDate: string;
}

function formatNumeric(value: Numeric | null | undefined): string {
  return value?.display || "—";
}

function formatMoneyYi(value: Numeric | null | undefined): string {
  return value ? formatYi(value) : "—";
}

function formatSignedMoneyYi(value: Numeric | null | undefined): string {
  if (!value) return "—";
  const raw = bondNumericRaw(value);
  if (!Number.isFinite(raw)) return value.display || "—";
  const absYi = Math.abs(raw) / 100_000_000;
  const sign = raw > 0 ? "+" : raw < 0 ? "-" : "";
  return `${sign}${absYi.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} 亿`;
}

function formatDurationYears(value: Numeric | null | undefined): string {
  const display = formatNumeric(value);
  return display === "—" ? display : `${display} 年`;
}

function formatCount(value: number): string {
  return value.toLocaleString("zh-CN");
}

function nullableText(value: string | null | undefined): string {
  return value?.trim() || "—";
}

function joinDisplayList(values: string[] | null | undefined): string {
  return values && values.length > 0 ? values.join("、") : "无";
}

function hasDv01RiskData(data: DV01RiskResponse): boolean {
  return (
    data.position_count > 0 ||
    data.tenor_buckets.length > 0 ||
    data.top_bonds.length > 0 ||
    data.top_issuers.length > 0
  );
}

function rowMatchesSearch(row: DV01ReconciliationRow, search: string): boolean {
  const normalized = search.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return [row.instrument_code, row.instrument_name, row.issuer_name]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(normalized));
}

const shockColumns: ColumnsType<DV01ShockScenario> = [
  { title: "情景", dataIndex: "scenario_name", key: "scenario_name" },
  {
    title: "利率冲击",
    dataIndex: "shock_bp",
    key: "shock_bp",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "估算损益影响",
    dataIndex: "estimated_pnl",
    key: "estimated_pnl",
    render: formatSignedMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

const tenorColumns: ColumnsType<DV01TenorBucket> = [
  { title: "期限桶", dataIndex: "tenor_bucket", key: "tenor_bucket" },
  {
    title: "面值",
    dataIndex: "face_value",
    key: "face_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "市值",
    dataIndex: "market_value",
    key: "market_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "DV01",
    dataIndex: "dv01",
    key: "dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "DV01 占比",
    dataIndex: "dv01_share",
    key: "dv01_share",
    render: formatPct,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "加权久期",
    dataIndex: "face_weighted_modified_duration",
    key: "face_weighted_modified_duration",
    render: formatDurationYears,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "持仓数",
    dataIndex: "position_count",
    key: "position_count",
    render: formatCount,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

const topBondColumns: ColumnsType<DV01TopBondItem> = [
  { title: "代码", dataIndex: "instrument_code", key: "instrument_code" },
  {
    title: "名称",
    dataIndex: "instrument_name",
    key: "instrument_name",
    render: nullableText,
  },
  {
    title: "发行人",
    dataIndex: "issuer_name",
    key: "issuer_name",
    render: nullableText,
  },
  { title: "评级", dataIndex: "rating", key: "rating", render: nullableText },
  { title: "期限桶", dataIndex: "tenor_bucket", key: "tenor_bucket" },
  { title: "分类", dataIndex: "accounting_class", key: "accounting_class" },
  {
    title: "面值",
    dataIndex: "face_value",
    key: "face_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "市值",
    dataIndex: "market_value",
    key: "market_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "修正久期",
    dataIndex: "modified_duration",
    key: "modified_duration",
    render: formatDurationYears,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "DV01",
    dataIndex: "dv01",
    key: "dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "占比",
    dataIndex: "dv01_share",
    key: "dv01_share",
    render: formatPct,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

const topIssuerColumns: ColumnsType<DV01TopIssuerItem> = [
  { title: "发行人", dataIndex: "issuer_name", key: "issuer_name" },
  {
    title: "面值",
    dataIndex: "face_value",
    key: "face_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "市值",
    dataIndex: "market_value",
    key: "market_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "加权久期",
    dataIndex: "face_weighted_modified_duration",
    key: "face_weighted_modified_duration",
    render: formatDurationYears,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "DV01",
    dataIndex: "dv01",
    key: "dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "占比",
    dataIndex: "dv01_share",
    key: "dv01_share",
    render: formatPct,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "持仓数",
    dataIndex: "position_count",
    key: "position_count",
    render: formatCount,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

const reconciliationColumns: ColumnsType<DV01ReconciliationRow> = [
  { title: "债券代码", dataIndex: "instrument_code", key: "instrument_code", fixed: "left", width: 120 },
  {
    title: "债券名称",
    dataIndex: "instrument_name",
    key: "instrument_name",
    render: nullableText,
    width: 160,
  },
  { title: "会计分类", dataIndex: "accounting_class", key: "accounting_class", width: 90 },
  {
    title: "发行人",
    dataIndex: "issuer_name",
    key: "issuer_name",
    render: nullableText,
    width: 140,
  },
  { title: "评级", dataIndex: "rating", key: "rating", render: nullableText, width: 80 },
  { title: "期限桶", dataIndex: "tenor_bucket", key: "tenor_bucket", width: 90 },
  {
    title: "面值",
    dataIndex: "face_value",
    key: "face_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "市值",
    dataIndex: "market_value",
    key: "market_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "修正久期",
    dataIndex: "modified_duration",
    key: "modified_duration",
    render: formatDurationYears,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 110,
  },
  {
    title: "DV01",
    dataIndex: "dv01",
    key: "dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "DV01 占比",
    dataIndex: "dv01_share",
    key: "dv01_share",
    render: formatPct,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 110,
  },
  { title: "source_version", dataIndex: "source_version", key: "source_version", width: 150 },
  { title: "rule_version", dataIndex: "rule_version", key: "rule_version", width: 130 },
  { title: "trace_id", dataIndex: "trace_id", key: "trace_id", width: 140 },
];

const movementAttributionColumns: ColumnsType<DV01MovementAttributionItem> = [
  { title: "解释项", dataIndex: "driver_label", key: "driver_label" },
  {
    title: "DV01 变动",
    dataIndex: "dv01_delta",
    key: "dv01_delta",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "变动占比",
    dataIndex: "dv01_delta_share",
    key: "dv01_delta_share",
    render: formatPct,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "涉及债券",
    dataIndex: "position_count",
    key: "position_count",
    render: formatCount,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

const movementBondColumns: ColumnsType<DV01MovementBondItem> = [
  { title: "债券代码", dataIndex: "instrument_code", key: "instrument_code", fixed: "left", width: 120 },
  {
    title: "债券名称",
    dataIndex: "instrument_name",
    key: "instrument_name",
    render: nullableText,
    width: 160,
  },
  {
    title: "发行人",
    dataIndex: "issuer_name",
    key: "issuer_name",
    render: nullableText,
    width: 140,
  },
  { title: "原因", dataIndex: "reason_label", key: "reason_label", width: 130 },
  { title: "上期分类", dataIndex: "previous_accounting_class", key: "previous_accounting_class", render: nullableText, width: 90 },
  { title: "本期分类", dataIndex: "current_accounting_class", key: "current_accounting_class", render: nullableText, width: 90 },
  {
    title: "上期 DV01",
    dataIndex: "previous_dv01",
    key: "previous_dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "本期 DV01",
    dataIndex: "current_dv01",
    key: "current_dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "DV01 变动",
    dataIndex: "dv01_delta",
    key: "dv01_delta",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "本期面值",
    dataIndex: "current_face_value",
    key: "current_face_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "本期久期",
    dataIndex: "current_modified_duration",
    key: "current_modified_duration",
    render: formatDurationYears,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 110,
  },
];

const methodologyCheckColumns: ColumnsType<DV01MovementBondItem> = [
  { title: "债券代码", dataIndex: "instrument_code", key: "instrument_code", fixed: "left", width: 120 },
  {
    title: "债券名称",
    dataIndex: "instrument_name",
    key: "instrument_name",
    render: nullableText,
    width: 160,
  },
  {
    title: "发行人",
    dataIndex: "issuer_name",
    key: "issuer_name",
    render: nullableText,
    width: 140,
  },
  {
    title: "系统 DV01",
    dataIndex: "current_dv01",
    key: "current_dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "面值久期估算",
    dataIndex: "estimated_dv01_from_face_duration",
    key: "estimated_dv01_from_face_duration",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 140,
  },
  {
    title: "估算差异",
    dataIndex: "dv01_estimate_gap",
    key: "dv01_estimate_gap",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "本期面值",
    dataIndex: "current_face_value",
    key: "current_face_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "本期久期",
    dataIndex: "current_modified_duration",
    key: "current_modified_duration",
    render: formatDurationYears,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 110,
  },
];

const actionScenarioColumns: ColumnsType<DV01ActionScenarioBreach> = [
  { title: "情景", dataIndex: "scenario_name", key: "scenario_name" },
  {
    title: "利率上行",
    dataIndex: "shock_bp",
    key: "shock_bp",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "估算损失",
    dataIndex: "estimated_loss",
    key: "estimated_loss",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "损失阈值",
    dataIndex: "loss_threshold",
    key: "loss_threshold",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  { title: "状态", dataIndex: "risk_level", key: "risk_level" },
];

const actionTenorColumns: ColumnsType<DV01ActionTenorItem> = [
  { title: "期限桶", dataIndex: "tenor_bucket", key: "tenor_bucket" },
  {
    title: "DV01",
    dataIndex: "dv01",
    key: "dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "占比",
    dataIndex: "dv01_share",
    key: "dv01_share",
    render: formatPct,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "建议压降 DV01",
    dataIndex: "suggested_reduction_dv01",
    key: "suggested_reduction_dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "持仓数",
    dataIndex: "position_count",
    key: "position_count",
    render: formatCount,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

const actionIssuerColumns: ColumnsType<DV01ActionIssuerItem> = [
  { title: "发行人", dataIndex: "issuer_name", key: "issuer_name" },
  {
    title: "DV01",
    dataIndex: "dv01",
    key: "dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "占比",
    dataIndex: "dv01_share",
    key: "dv01_share",
    render: formatPct,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "建议压降 DV01",
    dataIndex: "suggested_reduction_dv01",
    key: "suggested_reduction_dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "持仓数",
    dataIndex: "position_count",
    key: "position_count",
    render: formatCount,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

const actionBondColumns: ColumnsType<DV01ActionBondItem> = [
  { title: "债券代码", dataIndex: "instrument_code", key: "instrument_code", fixed: "left", width: 120 },
  {
    title: "债券名称",
    dataIndex: "instrument_name",
    key: "instrument_name",
    render: nullableText,
    width: 160,
  },
  {
    title: "发行人",
    dataIndex: "issuer_name",
    key: "issuer_name",
    render: nullableText,
    width: 140,
  },
  { title: "评级", dataIndex: "rating", key: "rating", render: nullableText, width: 80 },
  { title: "期限桶", dataIndex: "tenor_bucket", key: "tenor_bucket", width: 90 },
  { title: "分类", dataIndex: "accounting_class", key: "accounting_class", width: 80 },
  {
    title: "面值",
    dataIndex: "face_value",
    key: "face_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "修正久期",
    dataIndex: "modified_duration",
    key: "modified_duration",
    render: formatDurationYears,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 110,
  },
  {
    title: "DV01",
    dataIndex: "dv01",
    key: "dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "建议压降 DV01",
    dataIndex: "suggested_reduction_dv01",
    key: "suggested_reduction_dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 140,
  },
];

function riskLevelLabel(value: string | null | undefined): string {
  if (value === "breach") return "超限";
  if (value === "watch") return "关注";
  if (value === "ok") return "可接受";
  if (value === "no_data") return "无数据";
  return value || "—";
}

function actionPolicyBasisLabel(value: string | null | undefined): string {
  if (value === "formal_limit") return "正式限额口径";
  return "页面预警阈值 fallback";
}

function actionPolicyBasisDescription(value: string | null | undefined): string {
  if (value === "formal_limit") return "动作计划按已接入的正式 DV01 限额计算。";
  return "正式限额未接入，风险动作仅用于预警排查；正式超限结论以 business-approved 限额验收通过后为准。";
}

function limitConfigOverallLabel(value: string | null | undefined): string {
  if (value === "ready") return "整体已配置";
  if (value === "incomplete") return "整体未完成";
  return value || "—";
}

function limitConfigStatusLabel(value: string | null | undefined): string {
  if (value === "ready") return "已配置";
  if (value === "missing") return "未配置";
  if (value === "invalid") return "配置无效";
  return value || "—";
}

function limitConfigAcceptanceLabel(value: string | null | undefined): string {
  if (value === "ready") return "已通过";
  if (value === "blocked") return "未通过";
  return value || "—";
}

function numericKey(value: Numeric | null | undefined): string {
  if (!value) return "na";
  return `${value.raw}-${value.unit}-${value.display}`;
}

function actionBondRowKey(row: DV01ActionBondItem | DV01TopBondItem): string {
  return [
    row.instrument_code,
    row.accounting_class,
    row.tenor_bucket,
    row.issuer_name,
    numericKey(row.face_value),
    numericKey(row.dv01),
  ].join("|");
}

function movementBondRowKey(prefix: string, row: DV01MovementBondItem): string {
  return [
    prefix,
    row.instrument_code,
    row.previous_accounting_class,
    row.current_accounting_class,
    row.reason_label,
    numericKey(row.previous_dv01),
    numericKey(row.current_dv01),
    numericKey(row.dv01_delta),
  ].join("|");
}

function reconciliationRowKey(row: DV01ReconciliationRow): string {
  return [
    row.report_date,
    row.instrument_code,
    row.accounting_class,
    row.trace_id,
    row.source_version,
    row.rule_version,
    numericKey(row.face_value),
    numericKey(row.dv01),
  ].join("|");
}

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className={styles.kpiCard}>
      <span className={styles.kpiLabel}>{label}</span>
      <span className={styles.kpiValue}>{value}</span>
    </div>
  );
}

function limitEffectiveDateLabel(value: string | null | undefined): string {
  return value?.trim() || "未配置";
}

function selectedLimitConfigRow(
  data: DV01LimitConfigStatusPayload | null,
  accountingClass: BondAnalyticsDV01AccountingClassFilter,
): DV01LimitConfigStatusRow | null {
  if (!data) return null;
  const target = accountingClass.toLowerCase();
  return data.rows.find((row) => row.accounting_class.toLowerCase() === target) ?? null;
}

function missingBusinessFieldLines(data: DV01LimitConfigStatusPayload | null): string[] {
  if (!data) return [];
  const missingBusinessFields =
    Object.keys(data.missing_business_fields_by_class ?? {}).length > 0
      ? data.missing_business_fields_by_class
      : Object.fromEntries(
          (data.missing_accounting_classes ?? []).map((accountingClass) => [
            accountingClass,
            data.required_fields ?? [],
          ]),
        );
  return Object.entries(missingBusinessFields ?? {}).map(
    ([accountingClass, fields]) => `${accountingClass}: ${joinDisplayList(fields)}`,
  );
}

function inferredLimitConfigAcceptanceStatus(
  data: DV01LimitConfigStatusPayload | null,
): "ready" | "blocked" | undefined {
  if (!data) return undefined;
  if (data.acceptance_status) return data.acceptance_status;
  if (
    data.overall_status === "ready" &&
    (data.missing_count ?? 0) === 0 &&
    (data.invalid_count ?? 0) === 0
  ) {
    return "ready";
  }
  return "blocked";
}

function fallbackLimitConfigReviewPackageCommand(
  data: DV01LimitConfigStatusPayload | null,
): string {
  const reportDate = data?.report_date?.trim();
  if (!reportDate) return "";
  return [
    "python -m backend.app.tasks.bond_dv01_limit_config_import",
    `--review-package-dir ${DV01_LIMIT_REVIEW_PACKAGE_DIR}`,
    `--report-date ${reportDate}`,
  ].join(" ");
}

function fallbackLimitConfigDryRunCommand(
  data: DV01LimitConfigStatusPayload | null,
): string {
  const reportDate = data?.report_date?.trim();
  if (!reportDate) return "";
  return [
    "python -m backend.app.tasks.bond_dv01_limit_config_import",
    `--config-path ${DV01_LIMIT_REVIEW_PACKAGE_DIR}\\bond_dv01_limit_config_review_${reportDate}.csv`,
    `--report-date ${reportDate}`,
    "--dry-run",
  ].join(" ");
}

function fallbackLimitConfigCheckStatusCommand(
  data: DV01LimitConfigStatusPayload | null,
): string {
  const reportDate = data?.report_date?.trim();
  if (!reportDate) return "";
  return [
    "python -m backend.app.tasks.bond_dv01_limit_config_import",
    "--check-status",
    `--report-date ${reportDate}`,
  ].join(" ");
}

function limitConfigBusinessCsvPath(dryRunCommand: string): string {
  const match = dryRunCommand.match(/--config-path\s+(.+?)\s+--report-date\b/);
  return match?.[1]?.trim() ?? "";
}

function limitConfigSampleDoNotImportPath(businessCsvPath: string): string {
  return businessCsvPath.replace(/\.csv$/i, "_sample_do_not_import.csv");
}

function limitConfigAcceptanceChecklistLines(args: {
  data: DV01LimitConfigStatusPayload | null;
  acceptanceStatus: "ready" | "blocked" | undefined;
  businessCsvPath: string;
  dryRunCommand: string;
}): string[] {
  const { data, acceptanceStatus, businessCsvPath, dryRunCommand } = args;
  if (!data || acceptanceStatus !== "blocked") return [];
  const lines = [];
  if (businessCsvPath) {
    lines.push(`填写业务文件 ${businessCsvPath}`);
    lines.push(`不要导入 sample_do_not_import.csv：${limitConfigSampleDoNotImportPath(businessCsvPath)}`);
  }
  lines.push("业务批准后再填写正式限额字段");
  if ((data.missing_accounting_classes ?? []).length > 0) {
    lines.push(`补齐分类 ${joinDisplayList(data.missing_accounting_classes)}`);
  }
  lines.push("accounting_class 只允许 AC、OCI、TPL、all");
  const missingFields = Array.from(
    new Set(Object.values(data.missing_business_fields_by_class ?? {}).flat()),
  );
  const businessFields = missingFields.length > 0 ? missingFields : data.required_fields;
  if ((businessFields ?? []).length > 0) {
    lines.push(`补齐字段 ${joinDisplayList(businessFields)}`);
  }
  lines.push("limit_dv01、warning_dv01、hedge_target_dv01 必须大于 0");
  lines.push("阈值顺序 hedge_target_dv01 <= warning_dv01 <= limit_dv01");
  lines.push("limit_effective_date 使用 ISO 日期");
  if (dryRunCommand) {
    lines.push("先执行 dry-run，通过后再导入正式配置");
    lines.push("期望 status=validated");
    lines.push("期望 import_readiness_status=ready_for_import");
    lines.push("期望 validation_errors 为空");
    lines.push("期望 records_written=0");
    lines.push("复核 limit_utilization_preview.summary.highest_severity_status");
  }
  return lines;
}

function shouldShowLimitConfigOperatorCommands(
  data: DV01LimitConfigStatusPayload | null,
  acceptanceStatus: "ready" | "blocked" | undefined,
): boolean {
  if (!data || acceptanceStatus !== "blocked") return false;
  return Boolean(
    data.review_package_command ||
      data.dry_run_command ||
      (data.missing_count ?? 0) > 0 ||
      (data.invalid_count ?? 0) > 0 ||
      (data.missing_accounting_classes ?? []).length > 0,
  );
}

function limitConfigAcceptanceMessage(
  data: DV01LimitConfigStatusPayload | null,
  acceptanceStatus: "ready" | "blocked" | undefined,
): string {
  if (data?.acceptance_message?.trim()) return data.acceptance_message;
  if (acceptanceStatus === "ready") return "正式 DV01 限额配置验收通过。";
  if (acceptanceStatus === "blocked") {
    return "正式 DV01 限额配置验收未通过；需补齐 AC、OCI、TPL、all 的业务限额字段。";
  }
  return "";
}

function limitConfigNextAction(
  data: DV01LimitConfigStatusPayload | null,
  acceptanceStatus: "ready" | "blocked" | undefined,
): string {
  if (data?.next_action?.trim()) return data.next_action;
  if (acceptanceStatus === "blocked") {
    return "生成 review package CSV，补齐正式限额字段后先执行 dry-run 校验，再导入正式配置。";
  }
  return "";
}

function DV01LimitConfigStatusPanel({
  data,
  accountingClass,
  isLoading,
  isError,
  error,
}: {
  data: DV01LimitConfigStatusPayload | null;
  accountingClass: BondAnalyticsDV01AccountingClassFilter;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
}) {
  const selectedRow = selectedLimitConfigRow(data, accountingClass);
  const missingFieldLines = missingBusinessFieldLines(data);
  const acceptanceStatus = inferredLimitConfigAcceptanceStatus(data);
  const reviewPackageCommand =
    data?.review_package_command || fallbackLimitConfigReviewPackageCommand(data);
  const dryRunCommand = data?.dry_run_command || fallbackLimitConfigDryRunCommand(data);
  const checkStatusCommand = fallbackLimitConfigCheckStatusCommand(data);
  const businessCsvPath = limitConfigBusinessCsvPath(dryRunCommand);
  const acceptanceChecklistLines = limitConfigAcceptanceChecklistLines({
    data,
    acceptanceStatus,
    businessCsvPath,
    dryRunCommand,
  });
  const hasOperatorCommands = shouldShowLimitConfigOperatorCommands(data, acceptanceStatus);

  return (
    <section className={styles.panel} data-testid="dv01-limit-config-status-panel">
      <div className={styles.reconciliationHeader}>
        <div>
          <h3 className={styles.panelTitle}>限额配置状态</h3>
          <div className={styles.reconciliationMeta}>
            {limitConfigOverallLabel(data?.overall_status)} · 已配置 {formatCount(data?.configured_count ?? 0)} 项 · 缺失{" "}
            {formatCount(data?.missing_count ?? 0)} 项 · 无效 {formatCount(data?.invalid_count ?? 0)} 项
          </div>
        </div>
        <span className={styles.reconciliationCount}>
          当前 {accountingClass}
        </span>
      </div>

      {isError ? (
        <Alert
          type="error"
          showIcon
          message="DV01 正式限额配置状态加载失败"
          description={error instanceof Error ? error.message : String(error)}
        />
      ) : isLoading && !data ? (
        <div className={styles.loadingState} data-testid="dv01-limit-config-status-loading">
          <Spin />
        </div>
      ) : !data || !selectedRow ? (
        <div className={styles.emptyState} data-testid="dv01-limit-config-status-empty-state">
          该报告日暂无 DV01 正式限额配置状态
        </div>
      ) : (
        <>
          {data.warnings.length > 0 ? (
            <Alert
              type="warning"
              showIcon
              message="正式限额配置提示"
              description={data.warnings.map((warning, index) => (
                <div key={index}>{warning}</div>
              ))}
            />
          ) : null}
          <div className={styles.movementSummaryGrid}>
            <KpiCard label="验收结论" value={limitConfigAcceptanceLabel(acceptanceStatus)} />
            <KpiCard label="正式配置流" value={nullableText(data.config_stream)} />
            <KpiCard label="已接入分类" value={joinDisplayList(data.configured_accounting_classes)} />
            <KpiCard label="待补分类" value={joinDisplayList(data.missing_accounting_classes)} />
            <KpiCard label="无效分类" value={joinDisplayList(data.invalid_accounting_classes)} />
            <KpiCard label="会计分类" value={selectedRow.accounting_class} />
            <KpiCard label="配置状态" value={limitConfigStatusLabel(selectedRow.status)} />
            <KpiCard label="正式限额 DV01" value={formatNumeric(selectedRow.limit_dv01)} />
            <KpiCard label="预警 DV01" value={formatNumeric(selectedRow.warning_dv01)} />
            <KpiCard label="对冲目标 DV01" value={formatNumeric(selectedRow.hedge_target_dv01)} />
            <KpiCard label="限额来源" value={nullableText(selectedRow.limit_source)} />
            <KpiCard label="来源版本" value={nullableText(selectedRow.limit_source_version)} />
            <KpiCard label="规则版本" value={nullableText(selectedRow.limit_rule_version)} />
            <KpiCard label="生效日" value={limitEffectiveDateLabel(selectedRow.limit_effective_date)} />
          </div>
          <div className={styles.reconciliationMeta}>
            验收说明 {nullableText(limitConfigAcceptanceMessage(data, acceptanceStatus))}
          </div>
          <div className={styles.reconciliationMeta}>
            下一步动作 {nullableText(limitConfigNextAction(data, acceptanceStatus))}
          </div>
          <div className={styles.reconciliationMeta}>
            必填字段 {joinDisplayList(data.required_fields)}
          </div>
          {acceptanceChecklistLines.length > 0 ? (
            <div className={styles.operatorBlock} data-testid="dv01-limit-config-acceptance-checklist">
              <div className={styles.operatorLabel}>业务验收清单</div>
              {acceptanceChecklistLines.map((line) => (
                <div key={line} className={styles.operatorText}>
                  {line}
                </div>
              ))}
            </div>
          ) : null}
          {missingFieldLines.length > 0 ? (
            <div className={styles.operatorBlock} data-testid="dv01-limit-config-missing-fields">
              <div className={styles.operatorLabel}>missing_business_fields_by_class</div>
              {missingFieldLines.map((line) => (
                <div key={line} className={styles.operatorText}>
                  {line}
                </div>
              ))}
            </div>
          ) : null}
          {hasOperatorCommands ? (
            <div className={styles.operatorBlock} data-testid="dv01-limit-config-operator-commands">
              {businessCsvPath ? (
                <>
                  <div className={styles.operatorLabel}>业务填写文件</div>
                  <code className={styles.commandText}>{businessCsvPath}</code>
                </>
              ) : null}
              {reviewPackageCommand ? (
                <>
                  <div className={styles.operatorLabel}>review_package_command</div>
                  <code className={styles.commandText}>{reviewPackageCommand}</code>
                </>
              ) : null}
              {dryRunCommand ? (
                <>
                  <div className={styles.operatorLabel}>dry_run_command</div>
                  <code className={styles.commandText}>{dryRunCommand}</code>
                </>
              ) : null}
              {checkStatusCommand ? (
                <>
                  <div className={styles.operatorLabel}>check_status_command</div>
                  <code className={styles.commandText}>{checkStatusCommand}</code>
                </>
              ) : null}
            </div>
          ) : null}
          <div className={styles.reconciliationMeta}>{selectedRow.message}</div>
        </>
      )}
    </section>
  );
}

function DV01ActionLimitKpis({ data }: { data: DV01ActionPlanResponse }) {
  return (
    <div className={styles.movementSummaryGrid}>
      <KpiCard label="风险状态" value={riskLevelLabel(data.risk_level)} />
      <KpiCard label="限额来源" value={nullableText(data.limit_source)} />
      <KpiCard label="限额版本" value={nullableText(data.limit_source_version)} />
      <KpiCard label="预警 DV01" value={formatNumeric(data.warning_dv01)} />
      <KpiCard label="限额 DV01" value={formatNumeric(data.limit_dv01)} />
      <KpiCard label="使用率" value={formatNumeric(data.limit_usage)} />
      <KpiCard label="剩余额度" value={formatNumeric(data.remaining_limit_dv01)} />
      <KpiCard label="需压降 DV01" value={formatNumeric(data.dv01_to_reduce)} />
      <KpiCard label="每手对冲 DV01" value={formatNumeric(data.hedge_instrument_dv01)} />
      <KpiCard label="建议对冲手数" value={formatNumeric(data.suggested_hedge_units)} />
    </div>
  );
}

function DV01ActionDetailTables({ data }: { data: DV01ActionPlanResponse }) {
  return (
    <>
      <Table<DV01ActionScenarioBreach>
        data-testid="dv01-action-plan-scenarios-table"
        dataSource={data.scenario_breaches}
        columns={actionScenarioColumns}
        rowKey={(row) => `${row.scenario_name}|${numericKey(row.shock_bp)}|${row.risk_level}`}
        pagination={false}
        size="small"
        scroll={{ x: true }}
      />
      <div className={styles.twoColumnGrid}>
        <section className={styles.subPanel}>
          <h4 className={styles.subPanelTitle}>期限优先处理</h4>
          <Table<DV01ActionTenorItem>
            data-testid="dv01-action-plan-tenors-table"
            dataSource={data.tenor_actions}
            columns={actionTenorColumns}
            rowKey={(row) => `${row.tenor_bucket}|${numericKey(row.dv01)}|${numericKey(row.suggested_reduction_dv01)}`}
            pagination={false}
            size="small"
            scroll={{ x: true, y: 320 }}
          />
        </section>
        <section className={styles.subPanel}>
          <h4 className={styles.subPanelTitle}>发行人优先处理</h4>
          <Table<DV01ActionIssuerItem>
            data-testid="dv01-action-plan-issuers-table"
            dataSource={data.issuer_actions}
            columns={actionIssuerColumns}
            rowKey={(row) => `${row.issuer_name}|${numericKey(row.dv01)}|${numericKey(row.suggested_reduction_dv01)}`}
            pagination={false}
            size="small"
            scroll={{ x: true, y: 320 }}
          />
        </section>
      </div>
      <Table<DV01ActionBondItem>
        data-testid="dv01-action-plan-bonds-table"
        dataSource={data.bond_actions}
        columns={actionBondColumns}
        rowKey={actionBondRowKey}
        pagination={false}
        size="small"
        scroll={{ x: 1300, y: 360 }}
      />
    </>
  );
}

function DV01ActionPlanPanel({
  data,
  isLoading,
  isError,
  error,
}: {
  data: DV01ActionPlanResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
}) {
  return (
    <section className={styles.panel} data-testid="dv01-action-plan-panel">
      <div className={styles.reconciliationHeader}>
        <div>
          <h3 className={styles.panelTitle}>DV01 风险动作</h3>
          <div className={styles.reconciliationMeta}>
            {data?.threshold_note || "页面预警阈值，不代表正式限额。"} · 当前状态 {riskLevelLabel(data?.risk_level)} · 触发{" "}
            {formatCount(data?.breach_count ?? 0)} 项 · 规则 {nullableText(data?.limit_rule_version)} · 生效{" "}
            {limitEffectiveDateLabel(data?.limit_effective_date)}
          </div>
        </div>
        <span className={styles.reconciliationCount}>
          持仓 {formatCount(data?.position_count ?? 0)}
        </span>
      </div>

      {isError ? (
        <Alert
          type="error"
          showIcon
          message="DV01 风险动作加载失败"
          description={error instanceof Error ? error.message : String(error)}
        />
      ) : isLoading && !data ? (
        <div className={styles.loadingState} data-testid="dv01-action-plan-loading">
          <Spin />
        </div>
      ) : !data ? (
        <div className={styles.emptyState} data-testid="dv01-action-plan-empty-state">
          该报告日/分类暂无债券 DV01 风险动作数据
        </div>
      ) : (
        <>
          {data.warnings.length > 0 ? (
            <Alert
              type="warning"
              showIcon
              message="DV01 动作口径提示"
              description={data.warnings.map((warning, index) => (
                <div key={index}>{warning}</div>
              ))}
            />
          ) : null}
          <Alert
            type={data.policy_basis === "formal_limit" ? "success" : "warning"}
            showIcon
            data-testid="dv01-action-plan-policy-basis"
            message={`当前动作口径：${actionPolicyBasisLabel(data.policy_basis)}`}
            description={actionPolicyBasisDescription(data.policy_basis)}
          />
          <DV01ActionLimitKpis data={data} />
          {data.risk_level === "no_data" ? (
            <div className={styles.emptyState} data-testid="dv01-action-plan-empty-state">
              该报告日/分类暂无债券 DV01 风险动作数据
            </div>
          ) : (
            <DV01ActionDetailTables data={data} />
          )}
        </>
      )}
    </section>
  );
}

function DV01MovementPanel({
  data,
  isLoading,
  isError,
  error,
}: {
  data: DV01MovementResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
}) {
  return (
    <section className={styles.panel} data-testid="dv01-movement-panel">
      <div className={styles.reconciliationHeader}>
        <div>
          <h3 className={styles.panelTitle}>较上一报告日变化</h3>
          <div className={styles.reconciliationMeta}>
            上一报告日 {data?.previous_report_date ?? "—"} · 本期 DV01 {formatNumeric(data?.current_total_dv01)} · 上期 DV01{" "}
            {formatNumeric(data?.previous_total_dv01)} · 变动 {formatNumeric(data?.delta_dv01)}
          </div>
        </div>
        <span className={styles.reconciliationCount}>
          本期 {formatCount(data?.current_position_count ?? 0)} / 上期 {formatCount(data?.previous_position_count ?? 0)}
        </span>
      </div>

      {isError ? (
        <Alert
          type="error"
          showIcon
          message="DV01 变化加载失败"
          description={error instanceof Error ? error.message : String(error)}
        />
      ) : isLoading && !data ? (
        <div className={styles.loadingState} data-testid="dv01-movement-loading">
          <Spin />
        </div>
      ) : !data || data.source_status === "empty" ? (
        <div className={styles.emptyState} data-testid="dv01-movement-empty-state">
          该报告日/分类暂无可对比的 DV01 变化数据
        </div>
      ) : (
        <>
          {data.warnings.length > 0 ? (
            <Alert
              type="warning"
              showIcon
              message="DV01 变化提示"
              description={data.warnings.map((warning, index) => (
                <div key={index}>{warning}</div>
              ))}
            />
          ) : null}
          <div className={styles.movementSummaryGrid}>
            <KpiCard label="本期总 DV01" value={formatNumeric(data.current_total_dv01)} />
            <KpiCard label="上期总 DV01" value={formatNumeric(data.previous_total_dv01)} />
            <KpiCard label="DV01 变动" value={formatNumeric(data.delta_dv01)} />
            <KpiCard label="本期加权久期" value={formatDurationYears(data.current_face_weighted_modified_duration)} />
          </div>
          <Table<DV01MovementAttributionItem>
            data-testid="dv01-movement-attribution-table"
            dataSource={data.attribution}
            columns={movementAttributionColumns}
            rowKey={(row) => `${row.driver_key}|${numericKey(row.dv01_delta)}|${row.position_count}`}
            pagination={false}
            size="small"
            scroll={{ x: true }}
          />
          <div className={styles.twoColumnGrid}>
            <section className={styles.subPanel}>
              <h4 className={styles.subPanelTitle}>异常单券</h4>
              <Table<DV01MovementBondItem>
                data-testid="dv01-movement-anomaly-table"
                dataSource={data.anomaly_bonds}
                columns={movementBondColumns}
                rowKey={(row) => movementBondRowKey("anomaly", row)}
                pagination={false}
                size="small"
                scroll={{ x: 1300, y: 360 }}
              />
            </section>
            <section className={styles.subPanel}>
              <h4 className={styles.subPanelTitle}>口径核验</h4>
              <Table<DV01MovementBondItem>
                data-testid="dv01-methodology-check-table"
                dataSource={data.methodology_checks}
                columns={methodologyCheckColumns}
                rowKey={(row) => movementBondRowKey("methodology", row)}
                pagination={false}
                size="small"
                scroll={{ x: 1200, y: 360 }}
              />
            </section>
          </div>
        </>
      )}
    </section>
  );
}

function DV01ReconciliationPanel({
  data,
  isLoading,
  isError,
  error,
  search,
  onSearchChange,
}: {
  data: DV01ReconciliationResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  search: string;
  onSearchChange: (value: string) => void;
}) {
  const rows = data?.rows ?? [];
  const filteredRows = rows.filter((row) => rowMatchesSearch(row, search));

  return (
    <section className={styles.panel} data-testid="dv01-reconciliation-panel">
      <div className={styles.reconciliationHeader}>
        <div>
          <h3 className={styles.panelTitle}>单券明细对账</h3>
          <div className={styles.reconciliationMeta}>
            后端合计：面值 {formatMoneyYi(data?.total_face_value)} · 市值 {formatMoneyYi(data?.total_market_value)} · 久期{" "}
            {formatDurationYears(data?.face_weighted_modified_duration)} · DV01 {formatNumeric(data?.total_dv01)} · 持仓{" "}
            {formatCount(data?.position_count ?? 0)}
          </div>
        </div>
        <div className={styles.reconciliationControls}>
          <span className={styles.reconciliationCount}>
            当前筛选 {formatCount(filteredRows.length)} / {formatCount(rows.length)}
          </span>
          <input
            className={styles.searchInput}
            data-testid="dv01-reconciliation-search"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="搜索代码/名称/发行人"
          />
        </div>
      </div>

      {data?.warnings.length ? (
        <Alert
          type="warning"
          showIcon
          message="明细口径提示"
          description={data.warnings.map((warning, index) => (
            <div key={index}>{warning}</div>
          ))}
        />
      ) : null}

      {isError ? (
        <Alert
          type="error"
          showIcon
          message="DV01 明细对账加载失败"
          description={error instanceof Error ? error.message : String(error)}
        />
      ) : isLoading && !data ? (
        <div className={styles.loadingState} data-testid="dv01-reconciliation-loading">
          <Spin />
        </div>
      ) : !data || rows.length === 0 ? (
        <div className={styles.emptyState} data-testid="dv01-reconciliation-empty-state">
          该报告日/分类暂无债券 DV01 明细数据
        </div>
      ) : (
        <Table<DV01ReconciliationRow>
          data-testid="dv01-reconciliation-table"
          dataSource={filteredRows}
          columns={reconciliationColumns}
          rowKey={reconciliationRowKey}
          pagination={{ pageSize: 20, showSizeChanger: true }}
          size="small"
          scroll={{ x: 1600, y: 520 }}
        />
      )}
    </section>
  );
}

export function DV01RiskView({ reportDate }: Props) {
  const client = useApiClient();
  const [accountingClass, setAccountingClass] =
    useState<BondAnalyticsDV01AccountingClassFilter>("OCI");
  const [topN, setTopN] = useState<number>(20);
  const [reconciliationSearch, setReconciliationSearch] = useState("");

  const queryOptions = useMemo(
    () => ({
      accountingClass,
      topN,
      shockBps: DEFAULT_SHOCK_BPS,
    }),
    [accountingClass, topN],
  );

  const query = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsDv01Risk(
      client.mode,
      reportDate,
      accountingClass,
      topN,
      DEFAULT_SHOCK_BPS,
    ),
    queryFn: () => client.getBondAnalyticsDv01Risk(reportDate, queryOptions),
    enabled: Boolean(reportDate),
    retry: false,
  });
  const reconciliationQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsDv01Reconciliation(
      client.mode,
      reportDate,
      accountingClass,
    ),
    queryFn: () =>
      client.getBondAnalyticsDv01Reconciliation(reportDate, {
        accountingClass,
      }),
    enabled: Boolean(reportDate),
    retry: false,
  });
  const movementQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsDv01Movement(
      client.mode,
      reportDate,
      accountingClass,
      topN,
    ),
    queryFn: () =>
      client.getBondAnalyticsDv01Movement(reportDate, {
        accountingClass,
        topN,
      }),
    enabled: Boolean(reportDate),
    retry: false,
  });
  const actionPlanQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsDv01ActionPlan(
      client.mode,
      reportDate,
      accountingClass,
      topN,
    ),
    queryFn: () =>
      client.getBondAnalyticsDv01ActionPlan(reportDate, {
        accountingClass,
        topN,
      }),
    enabled: Boolean(reportDate),
    retry: false,
  });
  const limitConfigStatusQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsDv01LimitConfigStatus(client.mode, reportDate),
    queryFn: () => client.getBondAnalyticsDv01LimitConfigStatus(reportDate),
    enabled: Boolean(reportDate),
    retry: false,
  });

  const data = query.data?.result ?? null;
  const hasData = data ? hasDv01RiskData(data) : false;
  const reconciliationData = reconciliationQuery.data?.result ?? null;
  const movementData = movementQuery.data?.result ?? null;
  const actionPlanData = actionPlanQuery.data?.result ?? null;
  const limitConfigStatusData = limitConfigStatusQuery.data?.result ?? null;

  if (!reportDate) {
    return null;
  }

  return (
    <div className={styles.shell} data-testid="dv01-risk-view">
      <SectionLead
        eyebrow="DV01 风险"
        title="当前报告日利率风险横截面"
        description="读取后端 formal 债券分析事实表中的行级 DV01，展示会计分类、利率冲击、期限桶、债券和发行人集中度；页面不重新计算 DV01。"
        testId="dv01-risk-shell-lead"
      />

      <div className={styles.toolbar}>
        <div className={styles.controlGroup}>
          <span className={styles.controlLabel}>会计分类</span>
          <Radio.Group
            data-testid="dv01-risk-accounting-class"
            optionType="button"
            buttonStyle="solid"
            options={ACCOUNTING_CLASS_OPTIONS}
            value={accountingClass}
            onChange={(event) =>
              setAccountingClass(event.target.value as BondAnalyticsDV01AccountingClassFilter)
            }
          />
        </div>
        <div className={styles.controlGroup}>
          <label className={styles.controlLabel} htmlFor="dv01-risk-topn">
            Top N
          </label>
          <select
            id="dv01-risk-topn"
            className={styles.select}
            data-testid="dv01-risk-topn"
            value={topN}
            onChange={(event) => setTopN(Number(event.target.value))}
          >
            {TOP_N_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      </div>

      {query.isLoading && !data ? (
        <div className={styles.loadingState} data-testid="dv01-risk-loading">
          <Spin />
        </div>
      ) : query.isError ? (
        <Alert
          type="error"
          showIcon
          message="DV01 风险加载失败"
          description={query.error instanceof Error ? query.error.message : String(query.error)}
        />
      ) : !data ? null : (
        <>
          {data.warnings.length > 0 ? (
            <Alert
              type="warning"
              showIcon
              message="提示"
              description={data.warnings.map((warning, index) => (
                <div key={index}>{warning}</div>
              ))}
            />
          ) : null}

          <div className={styles.kpiGrid}>
            <KpiCard label="总面值" value={formatMoneyYi(data.total_face_value)} />
            <KpiCard label="总市值" value={formatMoneyYi(data.total_market_value)} />
            <KpiCard
              label="面值加权修正久期"
              value={formatDurationYears(data.face_weighted_modified_duration)}
            />
            <KpiCard label="总 DV01" value={formatNumeric(data.total_dv01)} />
            <KpiCard label="持仓数" value={formatCount(data.position_count)} />
          </div>

          {!hasData ? (
            <div className={styles.emptyState} data-testid="dv01-risk-empty-state">
              该报告日/分类暂无债券 DV01 数据
            </div>
          ) : (
            <>
              {data.shock_scenarios.length > 0 ? (
                <section className={styles.panel}>
                  <h3 className={styles.panelTitle}>利率冲击表</h3>
                  <Table<DV01ShockScenario>
                    data-testid="dv01-risk-shocks-table"
                    dataSource={data.shock_scenarios}
                    columns={shockColumns}
                    rowKey={(row) => `${row.scenario_name}|${numericKey(row.shock_bp)}`}
                    pagination={false}
                    size="small"
                    scroll={{ x: true }}
                  />
                </section>
              ) : null}

              <section className={styles.panel}>
                <h3 className={styles.panelTitle}>期限桶 DV01</h3>
                <Table<DV01TenorBucket>
                  data-testid="dv01-risk-tenor-table"
                  dataSource={data.tenor_buckets}
                  columns={tenorColumns}
                  rowKey={(row) => `${row.tenor_bucket}|${numericKey(row.dv01)}|${row.position_count}`}
                  pagination={false}
                  size="small"
                  scroll={{ x: true }}
                />
              </section>

              <div className={styles.twoColumnGrid}>
                <section className={styles.panel}>
                  <h3 className={styles.panelTitle}>Top 债券</h3>
                  <Table<DV01TopBondItem>
                    data-testid="dv01-risk-top-bonds-table"
                    dataSource={data.top_bonds}
                    columns={topBondColumns}
                    rowKey={actionBondRowKey}
                    pagination={false}
                    size="small"
                    scroll={{ x: true, y: 420 }}
                  />
                </section>

                <section className={styles.panel}>
                  <h3 className={styles.panelTitle}>Top 发行人</h3>
                  <Table<DV01TopIssuerItem>
                    data-testid="dv01-risk-top-issuers-table"
                    dataSource={data.top_issuers}
                    columns={topIssuerColumns}
                    rowKey={(row) => `${row.issuer_name}|${numericKey(row.dv01)}|${row.position_count}`}
                    pagination={false}
                    size="small"
                    scroll={{ x: true, y: 420 }}
                  />
                </section>
              </div>
            </>
          )}

          <DV01LimitConfigStatusPanel
            data={limitConfigStatusData}
            accountingClass={accountingClass}
            isLoading={limitConfigStatusQuery.isLoading}
            isError={limitConfigStatusQuery.isError}
            error={limitConfigStatusQuery.error}
          />

          <DV01ActionPlanPanel
            data={actionPlanData}
            isLoading={actionPlanQuery.isLoading}
            isError={actionPlanQuery.isError}
            error={actionPlanQuery.error}
          />

          <DV01MovementPanel
            data={movementData}
            isLoading={movementQuery.isLoading}
            isError={movementQuery.isError}
            error={movementQuery.error}
          />

          <DV01ReconciliationPanel
            data={reconciliationData}
            isLoading={reconciliationQuery.isLoading}
            isError={reconciliationQuery.isError}
            error={reconciliationQuery.error}
            search={reconciliationSearch}
            onSearchChange={setReconciliationSearch}
          />
        </>
      )}
    </div>
  );
}

export default DV01RiskView;
