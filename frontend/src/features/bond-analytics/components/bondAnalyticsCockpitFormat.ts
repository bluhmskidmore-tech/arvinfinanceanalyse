import type { Numeric } from "../../../api/contracts";
import { bondNumericRaw, bondNumericRawOrNull } from "../adapters/bondAnalyticsAdapter";
import { toBp } from "../lib/bondAnalyticsHomeCalculations";
import { EM_DASH } from "../../../utils/format";
import { formatDv01Wan, formatPct, formatWan, formatYi } from "../utils/formatters";

export function isFiniteNumber(value: number | null | undefined): value is number {
  return value !== null && value !== undefined && Number.isFinite(value);
}

export function numOr(raw: Numeric | null | undefined): number {
  const n = bondNumericRaw(raw);
  return n === null ? Number.NaN : n;
}

export function numOrNullAware(raw: Numeric | null | undefined): number {
  const n = bondNumericRawOrNull(raw);
  return n === null ? Number.NaN : n;
}

export function formatNumericString(raw: string | number | null | undefined) {
  if (raw === null || raw === undefined || raw === "") {
    return EM_DASH;
  }
  const parsed = Number.parseFloat(String(raw).replace(/,/g, ""));
  if (!Number.isFinite(parsed)) {
    return String(raw);
  }
  return parsed.toLocaleString("zh-CN");
}

export function formatNumericDisplay(value: Numeric | null | undefined): string {
  return value?.display || EM_DASH;
}

export function formatTextEvidenceDisplay(value: string | null | undefined): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed : EM_DASH;
}

/**
 * 券种/资产类别后端 token 的业务标签，与筛选项文案（BOND_ANALYTICS_ASSET_CLASS_FILTER_OPTIONS）
 * 一致：rate=利率债、credit=信用债；未登记 token 原样透出（ledger-pnl 先例），缺失 —。
 */
export function assetClassLabel(value: string | null | undefined): string {
  const trimmed = value?.trim();
  if (!trimmed) return EM_DASH;
  if (trimmed === "rate") return "利率债";
  if (trimmed === "credit") return "信用债";
  return trimmed;
}

export function formatDurationDisplay(value: Numeric | null | undefined): string {
  const display = formatNumericDisplay(value);
  return display === EM_DASH ? display : `${display} 年`;
}

export function formatMoneyDisplay(value: Numeric | null | undefined): string {
  if (value == null) {
    return EM_DASH;
  }
  return formatYi(value);
}

export function formatMoneyEvidenceDisplay(value: Numeric | null | undefined): string {
  return bondNumericRawOrNull(value) === null ? EM_DASH : formatYi(value);
}

export function formatNumericEvidenceDisplay(value: Numeric | null | undefined): string {
  return bondNumericRawOrNull(value) === null ? EM_DASH : formatNumericDisplay(value);
}

export function formatPctEvidenceDisplay(value: Numeric | null | undefined): string {
  return bondNumericRawOrNull(value) === null ? EM_DASH : formatPct(value);
}

export function formatWanEvidenceDisplay(value: Numeric | null | undefined): string {
  return bondNumericRawOrNull(value) === null ? EM_DASH : formatWan(value);
}

/** DV01 是元/bp 敞口，按项目单位契约以万元/bp 两位小数展示，不与金额共用 formatWan。单位由调用处的列头或标签给出。 */
export function formatDv01EvidenceDisplay(value: Numeric | null | undefined): string {
  return bondNumericRawOrNull(value) === null ? EM_DASH : formatDv01Wan(value);
}

export function formatSignedPct(pct: number | null): string {
  if (!isFiniteNumber(pct)) {
    return EM_DASH;
  }
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

export function normalizeSpreadBp(spreadMedian: Numeric | null | undefined): number {
  return toBp(spreadMedian) ?? Number.NaN;
}

/** 水平值（非变动量）不带前导 +：符号只保留给变动量读数（formatSignedPct）。 */
export function stripLeadingPlus(display: string): string {
  return display.startsWith("+") ? display.slice(1) : display;
}

/**
 * 信用债 YTM 中位数按百分比展示（后端字段 credit_spread_median 实为信用债 YTM 中位数）。
 * 经 toBp 归一后再转 %，bp/pct/ratio 三种后端单位都安全；直接用 formatPct 会把
 * bp 形态的 raw ×100（85bp → 8500.00%），禁止回退到该写法。
 * 水平值不带前导 +（负值保留负号如实披露）。
 */
export function formatSpreadYtmPctDisplay(spreadMedian: Numeric | null | undefined): string {
  const spreadBp = toBp(spreadMedian);
  if (spreadBp === null) {
    return EM_DASH;
  }
  const pct = spreadBp / 100;
  return `${pct.toFixed(2)}%`;
}

export function buildReadoutFacts(args: {
  duration: number;
  creditWeight: number;
  spreadMedianBp: number;
}) {
  const { duration, creditWeight, spreadMedianBp } = args;
  const facts: string[] = [];

  if (Number.isFinite(duration)) {
    facts.push(`久期 ${duration.toFixed(2)} 年`);
  }
  if (Number.isFinite(spreadMedianBp)) {
    facts.push(`信用债收益率中位数 ${(spreadMedianBp / 100).toFixed(2)}%`);
  }
  if (Number.isFinite(creditWeight)) {
    facts.push(`信用占比 ${(creditWeight * 100).toFixed(1)}%`);
  }

  return facts;
}

export function buildMissingReadoutLabels(args: {
  duration: number;
  creditWeight: number;
  spreadMedianBp: number;
}) {
  const missing: string[] = [];

  if (!Number.isFinite(args.duration)) {
    missing.push("久期");
  }
  if (!Number.isFinite(args.spreadMedianBp)) {
    missing.push("信用债收益率中位数");
  }
  if (!Number.isFinite(args.creditWeight)) {
    missing.push("信用占比");
  }

  return missing;
}

export function buildCockpitConclusion(args: {
  duration: number;
  creditWeight: number;
  spreadMedianBp: number;
}) {
  const facts = buildReadoutFacts(args);
  const missingReadouts = buildMissingReadoutLabels(args);

  if (facts.length === 0) {
    return {
      title: "读面待确认",
      body: "核心债券读面仍在返回。",
      detail: "等待久期、信用债收益率中位数或组合信用摘要返回后更新首屏读面。",
    };
  }

  if (missingReadouts.length > 0) {
    return {
      title: "部分读面",
      body: "部分核心债券读面已返回。",
      detail: `${facts.join(" · ")}；待返回 ${missingReadouts.join(" / ")}。`,
    };
  }

  return {
    title: "核心读面",
    body: "久期、信用债收益率中位数与信用占比读面已返回。",
    detail: "口径：市值加权久期 / 信用债 YTM 中位数 / 信用债市值占比；读数见下方 KPI 横带。",
  };
}

export function buildDeskVerdictFields(args: {
  duration: number;
  creditWeight: number;
  spreadMedianBp: number;
  dv01Display: string;
  reportDate: string;
  dashboardReportDate: string;
  isDashboardDateFallback: boolean;
  headlinePending: boolean;
  hasHeadline: boolean;
  hasCurveReadout: boolean;
  curvePending: boolean;
}) {
  const {
    duration,
    creditWeight,
    spreadMedianBp,
    dv01Display,
    reportDate,
    dashboardReportDate,
    isDashboardDateFallback,
    headlinePending,
    hasHeadline,
    hasCurveReadout,
    curvePending,
  } = args;
  const displayDate = dashboardReportDate || EM_DASH;
  const requestedDate = reportDate || EM_DASH;

  if (isDashboardDateFallback) {
    return [
      {
        label: "核心读面",
        value: "目标日快照缺口",
        detail: `请求 ${requestedDate}，展示 ${displayDate} 历史快照。`,
      },
      {
        label: "数据边界",
        value: "目标报告日读面",
        detail: "待读面补齐后再更新当前报告日首屏。",
      },
      {
        label: "报告日状态",
        value: `快照回退 ${displayDate}`,
        detail: headlinePending ? "headline KPI 加载中。" : "仅作历史快照参考。",
      },
      {
        label: "下钻入口",
        value: "等待目标日快照",
        detail: "回退快照不形成当前结论。",
      },
    ];
  }

  const readoutFacts = buildReadoutFacts({ duration, creditWeight, spreadMedianBp });
  const readoutField = readoutFacts.length > 0
    ? {
        value: readoutFacts.join(" / "),
        detail: "仅展示已返回读面。",
      }
    : {
        value: "久期 / 利差 / 信用占比待返回",
        detail: "核心债券读面仍在返回。",
      };

  const boundaryField = !hasCurveReadout
    ? {
        value: curvePending ? "正式曲线加载中" : "正式曲线待返回",
        detail: curvePending ? "期限点加载中。" : "正式曲线待读面。",
      }
    : {
        value: "正式曲线已返回",
        detail: "期限点收益率与日变动可读。",
      };

  return [
    {
      label: "核心读面",
      value: readoutField.value,
      detail: readoutField.detail,
    },
    {
      label: "数据边界",
      value: boundaryField.value,
      detail: boundaryField.detail,
    },
    {
      label: "报告日状态",
      value: headlinePending ? "headline 加载中" : hasHeadline ? "报告日匹配" : "等 headline",
      detail: `报告日 ${displayDate}。`,
    },
    {
      label: "下钻入口",
      value: hasCurveReadout ? "打开正式下钻" : "正式下钻待返回",
      detail: hasCurveReadout ? `组合 DV01 ${dv01Display}。` : "先展示已返回读面，不补造下钻结论。",
    },
  ];
}
