import type {
  ApiQuality,
  BalanceAnalysisBasisBreakdownPayload,
  BondBusinessTypeMetricsPayload,
  Numeric,
  PnlAttributionAnalysisSummary,
  PortfolioComparisonPayload,
  RiskIndicatorsPayload,
  SpreadAnalysisPayload,
  YieldDistributionPayload,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { bondNumericDisplay } from "../../bond-analytics/adapters/bondAnalyticsAdapter";
import {
  formatDv01Wan,
  formatRatePercent,
  formatYi,
  formatYears,
  nativeToNumber,
} from "../../bond-dashboard/utils/format";
import type { ModuleHomeDetailChart, ModuleHomeDetailRow, ModuleHomeTone } from "./moduleHomeModel";
import { pnlDriverLabel } from "./portfolioDecisionModel";

// 组合首页专属的明细面板行/图表构建函数与其私有格式化工具，自 moduleHomeModel.ts 抽出；
// 只依赖 moduleHomeModel 的类型（import type），不形成运行时循环依赖。

export const YUAN_PER_YI = 100_000_000;

export function decimalToNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = typeof value === "number" ? value : Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * 组合首页专用：固定两位小数，避免同一列出现「551.2 亿元」与「629.48 亿元」并排。
 * 绩效首页仍用 formatYiFromYuan（其测试依赖「1 亿元」这类无尾零输出）。
 */
export function formatPortfolioYiFromYuan(value: string | number | null | undefined) {
  const parsed = decimalToNumber(value);
  if (parsed === null) {
    return EM_DASH;
  }
  return `${(parsed / YUAN_PER_YI).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} 亿元`;
}

/** 业务类型久期为后端字符串（如 "3.44449712"，空串表示缺失）；保留两位并加单位。 */
export function formatBusinessTypeDuration(value: string | number | null | undefined) {
  const parsed = decimalToNumber(value);
  if (parsed === null) {
    return EM_DASH;
  }
  return `${parsed.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} 年`;
}

const BASIS_POSITION_SCOPE_LABEL: Record<string, string> = {
  asset: "资产",
  liability: "负债",
};

export function basisPositionScopeLabel(scope: string) {
  return BASIS_POSITION_SCOPE_LABEL[scope] ?? scope;
}

export function buildRiskIndicatorDetailRows(risk: RiskIndicatorsPayload): ModuleHomeDetailRow[] {
  const reportDate = risk.report_date;
  return [
    {
      key: "risk-total-market-value",
      label: "组合市值",
      value: `${formatYi(risk.total_market_value)} 亿元`,
      tradeDate: reportDate,
      source: "total_market_value",
      tone: "ok",
    },
    {
      key: "risk-total-dv01",
      label: "DV01",
      value: `${formatDv01Wan(risk.total_dv01)} 万元`,
      tradeDate: reportDate,
      source: "total_dv01",
      tone: "ok",
    },
    {
      key: "risk-weighted-duration",
      label: "加权久期",
      value: `${formatYears(risk.weighted_duration)} 年`,
      tradeDate: reportDate,
      source: "weighted_duration",
      tone: "ok",
    },
    {
      key: "risk-credit-ratio",
      label: "信用占比",
      value: `${formatRatePercent(risk.credit_ratio)}%`,
      tradeDate: reportDate,
      source: "credit_ratio",
      tone: "ok",
    },
    {
      key: "risk-weighted-convexity",
      label: "凸性(加权)",
      value: (() => {
        const raw = nativeToNumber(risk.weighted_convexity);
        return raw === null ? EM_DASH : raw.toFixed(4);
      })(),
      tradeDate: reportDate,
      source: "weighted_convexity",
      tone: "ok",
    },
    {
      key: "risk-spread-dv01",
      label: "利差 DV01",
      value: `${formatDv01Wan(risk.total_spread_dv01)} 万元`,
      tradeDate: reportDate,
      source: "total_spread_dv01",
      tone: "ok",
    },
    {
      key: "risk-reinvestment-ratio",
      label: "1年内再投资占比",
      value: `${formatRatePercent(risk.reinvestment_ratio_1y)}%`,
      tradeDate: reportDate,
      source: "reinvestment_ratio_1y",
      tone: "ok",
    },
  ];
}

export function buildPortfolioComparisonRows(
  payload: PortfolioComparisonPayload,
): ModuleHomeDetailRow[] {
  return payload.items
    .slice(0, 8)
    .map((item, index) => {
      const portfolioLabel = item.portfolio_name.trim() || `未命名组合 ${index + 1}`;
      return {
        key: `portfolio-${portfolioLabel}`,
        label: portfolioLabel,
        value: `${formatYi(item.total_market_value)} 亿`,
        tradeDate: payload.report_date,
        source: `DV01 ${formatDv01Wan(item.total_dv01)} 万 · ${item.bond_count} 只`,
        tone: "ok",
        scaleDisplay: `${formatYi(item.total_market_value)} 亿`,
        durationDisplay: `${formatYears(item.weighted_duration)} 年`,
        ytmDisplay: nativeToNumber(item.weighted_ytm) === null ? EM_DASH : `${formatRatePercent(item.weighted_ytm)}%`,
        coverageNote: formatYtmCoverageNote(item.weighted_ytm_coverage_ratio),
        dv01Display: `${formatDv01Wan(item.total_dv01)} 万`,
        countDisplay: item.bond_count.toLocaleString("zh-CN"),
      };
    });
}

export function buildPortfolioComparisonChart(
  payload: PortfolioComparisonPayload,
): ModuleHomeDetailChart {
  const items = payload.items.slice(0, 8);
  return {
    title: "子组合市值规模",
    unit: "亿元",
    orientation: "horizontal",
    categories: items.map((item, index) => item.portfolio_name.trim() || `未命名组合 ${index + 1}`),
    values: items.map((item) => {
      const raw = nativeToNumber(item.total_market_value);
      return raw === null ? null : raw / 1e8;
    }),
  };
}

export function buildYieldDistributionChart(payload: YieldDistributionPayload): ModuleHomeDetailChart {
  const items = payload.items.slice(0, 8);
  return {
    title: "收益率桶市值分布",
    unit: "亿元",
    orientation: "vertical",
    categories: items.map((item) => item.yield_bucket),
    values: items.map((item) => {
      const raw = nativeToNumber(item.total_market_value);
      return raw === null ? null : raw / 1e8;
    }),
  };
}

export function buildSpreadAnalysisChart(payload: SpreadAnalysisPayload): ModuleHomeDetailChart {
  const items = payload.items.slice(0, 8);
  return {
    title: "券种规模分布",
    unit: "亿元",
    orientation: "horizontal",
    categories: items.map((item) => item.bond_type),
    values: items.map((item) => {
      const raw = nativeToNumber(item.total_market_value);
      return raw === null ? null : raw / 1e8;
    }),
  };
}

export function buildBusinessTypeChart(
  payload: BondBusinessTypeMetricsPayload["result"],
): ModuleHomeDetailChart {
  const items = payload.items.slice(0, 8);
  return {
    title: "业务类型市值分布",
    unit: "亿元",
    orientation: "horizontal",
    categories: items.map((item) => item.name),
    values: items.map((item) => {
      const raw = decimalToNumber(item.market_value);
      return raw === null ? null : raw / 1e8;
    }),
  };
}

export function formatYtmCoverageNote(coverage: Numeric | null | undefined): string | undefined {
  const ratio = nativeToNumber(coverage);
  return ratio !== null && ratio < 1
    ? `YTM 有效样本覆盖 ${formatRatePercent(coverage)}%（按加权市值）`
    : undefined;
}

export function buildYieldDistributionRows(payload: YieldDistributionPayload): ModuleHomeDetailRow[] {
  const coverageNote = formatYtmCoverageNote(payload.weighted_ytm_coverage_ratio);
  const rows: ModuleHomeDetailRow[] = payload.items.slice(0, 8).map((item) => ({
    key: `yield-${item.yield_bucket}`,
    label: item.yield_bucket,
    value: `${formatYi(item.total_market_value)} 亿元`,
    tradeDate: payload.report_date,
    source: `${item.bond_count} 只`,
    tone: "ok" as ModuleHomeTone,
  }));
  if (rows.length > 0 || coverageNote) {
    rows.unshift({
      key: "yield-weighted-ytm",
      label: "组合加权 YTM",
      value: nativeToNumber(payload.weighted_ytm) === null ? EM_DASH : `${formatRatePercent(payload.weighted_ytm)}%`,
      coverageNote,
      tradeDate: payload.report_date,
      source: "weighted_ytm",
      tone: "ok",
    });
  }
  return rows;
}

export function buildSpreadAnalysisRows(payload: SpreadAnalysisPayload): ModuleHomeDetailRow[] {
  return payload.items.slice(0, 8).map((item) => ({
    key: `spread-${item.bond_type}`,
    label: item.bond_type,
    value: item.median_yield ? `${formatRatePercent(item.median_yield)}%` : EM_DASH,
    tradeDate: payload.report_date,
    source: `${formatYi(item.total_market_value)} 亿 · ${item.bond_count} 只`,
    tone: "ok",
  }));
}

export function buildBusinessTypeRows(
  payload: BondBusinessTypeMetricsPayload["result"],
  qualityFlag?: ApiQuality,
): ModuleHomeDetailRow[] {
  // quality_flag=warning（该日无事实行）时降级为 watch，不再写死 ok。
  const tone: ModuleHomeTone = qualityFlag && qualityFlag !== "ok" ? "watch" : "ok";
  return payload.items.slice(0, 8).map((item) => {
    // weighted_avg_ytm 现为 governed Numeric（raw=null 表示缺覆盖），不再是
    // 会被当成真实数据拼出「YTM %」的空串。
    const ytmText = formatRatePercent(item.weighted_avg_ytm);
    return {
      key: `business-type-${item.name}`,
      label: item.name,
      value: `YTM ${ytmText === EM_DASH ? EM_DASH : `${ytmText}%`} · 久期 ${formatBusinessTypeDuration(
        item.weighted_avg_duration,
      )}`,
      tradeDate: payload.report_date,
      source: ["市值 " + formatPortfolioYiFromYuan(item.market_value), item.duration_source]
        .filter((part) => part.trim().length > 0)
        .join(" · "),
      tone,
    };
  });
}

export function buildBalanceBasisRows(
  payload: BalanceAnalysisBasisBreakdownPayload,
): ModuleHomeDetailRow[] {
  // 同一 source_family/invest_type/accounting_basis 会按资产、负债各出一行，标签补仓位维度以区分。
  return payload.rows.slice(0, 10).map((row, index) => ({
    key: `basis-${row.source_family}-${row.accounting_basis}-${index}`,
    label: `${row.source_family.toUpperCase()} · ${basisPositionScopeLabel(row.position_scope)} · ${row.invest_type_std} · ${row.accounting_basis}`,
    value: formatPortfolioYiFromYuan(row.market_value_amount),
    tradeDate: payload.report_date,
    source: `摊余 ${formatPortfolioYiFromYuan(row.amortized_cost_amount)} · 应计 ${formatPortfolioYiFromYuan(row.accrued_interest_amount)}`,
    tone: "ok",
  }));
}

export function buildPnlSummaryRows(summary: PnlAttributionAnalysisSummary): ModuleHomeDetailRow[] {
  const rows: ModuleHomeDetailRow[] = [
    {
      key: "pnl-primary-driver",
      label: "主驱动",
      value: `${pnlDriverLabel(summary.primary_driver)} · ${bondNumericDisplay(summary.primary_driver_pct)}`,
      tradeDate: summary.report_date,
      source: "primary_driver",
      tone: "ok",
    },
    {
      key: "pnl-tpl-alignment",
      label: "TPL 与市场",
      value: summary.tpl_market_aligned ? "方向一致" : "待核验",
      tradeDate: summary.report_date,
      source: summary.tpl_market_note,
      tone: summary.tpl_market_aligned ? "ok" : "watch",
    },
  ];
  for (const [index, finding] of summary.key_findings.slice(0, 4).entries()) {
    rows.push({
      key: `pnl-finding-${index}`,
      label: `发现 ${index + 1}`,
      value: finding,
      tradeDate: summary.report_date,
      source: "key_findings",
      tone: "ok",
    });
  }
  return rows;
}
