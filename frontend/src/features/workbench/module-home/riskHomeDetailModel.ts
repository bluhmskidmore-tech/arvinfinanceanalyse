import type { CashflowProjectionPayload, Numeric, RiskTensorPayload, RiskTensorScalar } from "../../../api/contracts";
import { bondNumericDisplay, bondNumericRawOrNull } from "../../bond-analytics/adapters/bondAnalyticsAdapter";
import { formatDv01Wan, formatYi } from "../../bond-dashboard/utils/format";
import type { ModuleHomeDetailRow, ModuleHomeDetailSection, ModuleHomeTone } from "./moduleHomeDetailTypes";

type RiskTensorDisplayValue = RiskTensorScalar | null | undefined;

const RISK_YUAN_PER_WAN = 10_000;
const RISK_YUAN_PER_YI = 100_000_000;

const RISK_KRD_FIELDS: ReadonlyArray<{ key: keyof RiskTensorPayload; label: string }> = [
  { key: "krd_1y", label: "KRD 1Y" },
  { key: "krd_3y", label: "KRD 3Y" },
  { key: "krd_5y", label: "KRD 5Y" },
  { key: "krd_7y", label: "KRD 7Y" },
  { key: "krd_10y", label: "KRD 10Y" },
  { key: "krd_30y", label: "KRD 30Y" },
];

type RiskAccountingDv01FieldKey = "ac_dv01" | "oci_dv01" | "tpl_dv01" | "other_dv01";

const RISK_ACCOUNTING_DV01_FIELDS: ReadonlyArray<{ key: RiskAccountingDv01FieldKey; label: string }> = [
  { key: "ac_dv01", label: "AC DV01（摊余成本）" },
  { key: "oci_dv01", label: "OCI DV01（其他综合收益）" },
  { key: "tpl_dv01", label: "TPL DV01（交易性）" },
  { key: "other_dv01", label: "未分类 DV01" },
];

function riskTensorRawOrNull(value: RiskTensorDisplayValue): number | null {
  return bondNumericRawOrNull(value);
}

function shouldShowAccountingDv01Split(value: RiskTensorDisplayValue): boolean {
  if (!hasRiskTensorValue(value)) {
    return false;
  }
  const raw = riskTensorRawOrNull(value);
  return raw === null || raw !== 0;
}

export function riskTensorDisplay(value: RiskTensorDisplayValue): string {
  return bondNumericDisplay(value);
}

function formatRiskTensorYuanAmount(
  value: RiskTensorDisplayValue,
  raw: number | null,
  divisor: number,
): string {
  if (raw === null) {
    return riskTensorDisplay(value);
  }
  // 保留正负号：负缺口/空头 KRD 的方向有业务含义，与风险张量页保持一致。
  return (raw / divisor).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function riskTensorWanWithUnit(value: RiskTensorDisplayValue): string {
  const raw = riskTensorRawOrNull(value);
  const display = formatRiskTensorYuanAmount(value, raw, RISK_YUAN_PER_WAN);
  return raw === null ? display : `${display} 万元/bp`;
}

export function riskTensorYiWithUnit(value: RiskTensorDisplayValue): string {
  const raw = riskTensorRawOrNull(value);
  const display = formatRiskTensorYuanAmount(value, raw, RISK_YUAN_PER_YI);
  return raw === null ? display : `${display} 亿元`;
}

export function riskTensorRatioPercent(value: RiskTensorDisplayValue): string {
  const display = riskTensorDisplay(value);
  if (display.includes("%")) {
    return display;
  }
  // legacy 字符串（riskTensor.ts 标注的历史/mock 兼容分支）没有单位契约：
  // abs≤1→×100 的双阈值启发式会把 (0,1] 的百分点值放大 100 倍。
  // 无 "%" 单位时不再猜测，原文透出（空串已由 display 归一为 EM_DASH）。
  if (typeof value === "string") {
    return display;
  }
  // 正式 Numeric 路径（后端 /api/risk/tensor 契约 raw）保留比例换算。
  const raw = riskTensorRawOrNull(value);
  if (raw === null) {
    return display;
  }
  const abs = Math.abs(raw);
  if (abs <= 1) {
    return `${(raw * 100).toFixed(1)}%`;
  }
  if (abs <= 100) {
    return `${raw.toFixed(1)}%`;
  }
  return display;
}

export function riskTensorValueTone(value: RiskTensorDisplayValue): ModuleHomeTone {
  const raw = riskTensorRawOrNull(value);
  if (raw === null) {
    return "watch";
  }
  return "ok";
}

export function riskTensorPendingOrWan(value: RiskTensorDisplayValue): string {
  return hasRiskTensorValue(value) ? riskTensorWanWithUnit(value) : "待接入";
}

export function hasRiskTensorValue(value: RiskTensorDisplayValue): boolean {
  return value !== null && value !== undefined;
}

function pushRiskTensorDetailRow(
  rows: ModuleHomeDetailRow[],
  key: string,
  label: string,
  value: RiskTensorDisplayValue,
  format: RiskTensorDetailFormat,
  reportDate: string,
) {
  if (!hasRiskTensorValue(value)) {
    return;
  }
  const formatted =
    format === "wan"
      ? riskTensorWanWithUnit(value)
      : format === "yi"
        ? riskTensorYiWithUnit(value)
        : format === "ratio"
          ? riskTensorRatioPercent(value)
          : riskTensorDisplay(value);
  rows.push({
    key,
    label,
    value: formatted,
    tradeDate: reportDate,
    source: key,
    tone: "ok",
  });
}

type RiskTensorDetailFormat = "wan" | "yi" | "display" | "ratio";

type RiskTensorDetailField = {
  key: keyof RiskTensorPayload | RiskAccountingDv01FieldKey;
  label: string;
  format: RiskTensorDetailFormat;
};

type RiskTensorDetailSectionSpec = Omit<ModuleHomeDetailSection, "rows"> & {
  fields: readonly RiskTensorDetailField[];
  nonzeroOnly?: boolean;
};

const RISK_TENSOR_DETAIL_SECTIONS: readonly RiskTensorDetailSectionSpec[] = [
  {
    key: "rate-sensitivity",
    title: "利率敏感度",
    subtitle: "监管 / 估值 / 利率风险 / CS01 / 凸性",
    defaultExpanded: true,
    fields: [
      { key: "regulatory_dv01", label: "监管口径 DV01", format: "wan" },
      { key: "portfolio_dv01", label: "估值 DV01", format: "wan" },
      { key: "rate_risk_dv01", label: "利率风险 DV01", format: "wan" },
      { key: "cs01", label: "CS01", format: "wan" },
      { key: "portfolio_convexity", label: "组合凸性", format: "display" },
    ],
  },
  {
    key: "accounting-dv01",
    title: "会计分类 DV01",
    subtitle: "AC / OCI / TPL 拆分",
    defaultExpanded: true,
    nonzeroOnly: true,
    fields: RISK_ACCOUNTING_DV01_FIELDS.map((field) => ({ ...field, format: "wan" as const })),
  },
  {
    key: "krd-detail",
    title: "KRD 明细",
    subtitle: "上方图表已展示分布，展开查看数值",
    defaultExpanded: false,
    fields: RISK_KRD_FIELDS.map((field) => ({ ...field, format: "wan" as const })),
  },
  {
    key: "concentration",
    title: "集中度",
    defaultExpanded: false,
    fields: [
      { key: "issuer_concentration_hhi", label: "发行人 HHI", format: "display" },
      { key: "issuer_top5_weight", label: "前五大发行人权重", format: "ratio" },
    ],
  },
  {
    key: "liquidity-detail",
    title: "流动性明细",
    defaultExpanded: false,
    fields: [
      { key: "liquidity_gap_30d", label: "30 日流动性缺口", format: "yi" },
      { key: "liquidity_gap_90d", label: "90 日流动性缺口", format: "yi" },
      { key: "liquidity_gap_30d_ratio", label: "30 日缺口比例", format: "ratio" },
      { key: "asset_cashflow_30d", label: "30 日资产现金流", format: "yi" },
      { key: "asset_cashflow_90d", label: "90 日资产现金流", format: "yi" },
      { key: "liability_cashflow_30d", label: "30 日负债现金流", format: "yi" },
      { key: "liability_cashflow_90d", label: "90 日负债现金流", format: "yi" },
    ],
  },
];

/** Keep declared field and section order; absent fields and zero accounting splits stay hidden. */
export function buildRiskTensorDetailSections(tensor: RiskTensorPayload): ModuleHomeDetailSection[] {
  const values = tensor as RiskTensorPayload &
    Partial<Record<RiskAccountingDv01FieldKey, RiskTensorDisplayValue>>;
  return RISK_TENSOR_DETAIL_SECTIONS.flatMap((section) => {
    const rows: ModuleHomeDetailRow[] = [];
    for (const field of section.fields) {
      const value = values[field.key] as RiskTensorDisplayValue;
      if (section.nonzeroOnly && !shouldShowAccountingDv01Split(value)) {
        continue;
      }
      pushRiskTensorDetailRow(rows, field.key, field.label, value, field.format, tensor.report_date);
    }
    return rows.length > 0
      ? [{
          key: section.key,
          title: section.title,
          ...(section.subtitle === undefined ? {} : { subtitle: section.subtitle }),
          rows,
          defaultExpanded: section.defaultExpanded,
        }]
      : [];
  });
}
function numericDetailRow(
  key: string,
  label: string,
  value: Numeric,
  reportDate: string,
  source: string,
): ModuleHomeDetailRow {
  return {
    key,
    label,
    value: bondNumericDisplay(value),
    tradeDate: reportDate,
    source,
    tone: "ok",
  };
}

export function buildCashflowDetailSections(cashflow: CashflowProjectionPayload): ModuleHomeDetailSection[] {
  const reportDate = cashflow.report_date;
  const forecastRows: ModuleHomeDetailRow[] = [
    numericDetailRow("duration_gap", "久期缺口", cashflow.duration_gap, reportDate, "duration_gap"),
    numericDetailRow(
      "asset_duration",
      "资产久期",
      cashflow.asset_duration,
      reportDate,
      "asset_duration",
    ),
    numericDetailRow(
      "liability_duration",
      "负债久期",
      cashflow.liability_duration,
      reportDate,
      "liability_duration",
    ),
    numericDetailRow(
      "equity_duration",
      "权益久期",
      cashflow.equity_duration,
      reportDate,
      "equity_duration",
    ),
    {
      key: "rate_sensitivity_1bp",
      label: "1bp 敏感度",
      value: `${formatDv01Wan(cashflow.rate_sensitivity_1bp)} 万元`,
      tradeDate: reportDate,
      source: "rate_sensitivity_1bp",
      tone: "ok",
    },
    numericDetailRow(
      "reinvestment_risk_12m",
      "12M 再投资风险",
      cashflow.reinvestment_risk_12m,
      reportDate,
      "reinvestment_risk_12m",
    ),
  ];

  const monthlyRows: ModuleHomeDetailRow[] = [];
  for (const bucket of cashflow.monthly_buckets.slice(0, 6)) {
    monthlyRows.push({
      key: `bucket-${bucket.year_month}`,
      label: `${bucket.year_month} 净现金流`,
      value: `${formatYi(bucket.net_cashflow)} 亿元`,
      tradeDate: bucket.year_month,
      source: "net_cashflow",
      tone: "ok",
    });
    monthlyRows.push({
      key: `bucket-cum-${bucket.year_month}`,
      label: `${bucket.year_month} 累计净现金流`,
      value: `${formatYi(bucket.cumulative_net)} 亿元`,
      tradeDate: bucket.year_month,
      source: "cumulative_net",
      tone: "ok",
    });
  }

  const sections: ModuleHomeDetailSection[] = [
    {
      key: "cashflow-forecast",
      title: "现金流预测",
      subtitle: "久期四要素 / 1bp / 12M 再投资",
      rows: forecastRows,
      defaultExpanded: true,
    },
  ];
  if (monthlyRows.length > 0) {
    sections.push({
      key: "monthly-buckets",
      title: "月度净现金流",
      subtitle: "近 6 个月 bucket",
      rows: monthlyRows,
      defaultExpanded: false,
    });
  }
  return sections;
}

