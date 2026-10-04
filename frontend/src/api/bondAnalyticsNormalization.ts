import type { ApiEnvelope, BondPortfolioHeadlinesPayload, CreditSpreadMigrationPayload } from "./contracts";
import { normalizeNumeric } from "./numeric";

function normalizeConcentration(
  value: unknown,
): CreditSpreadMigrationPayload["concentration_by_rating"] {
  if (!value || typeof value !== "object") {
    return undefined;
  }
  const source = value as Record<string, unknown>;
  const topItems = Array.isArray(source.top_items) ? source.top_items : [];
  return {
    ...source,
    dimension: String(source.dimension ?? ""),
    hhi: normalizeNumeric(source.hhi, "ratio", false),
    top5_concentration: normalizeNumeric(source.top5_concentration, "ratio", false),
    top_items: topItems.map((item) => {
      const row = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
      return {
        ...row,
        name: String(row.name ?? ""),
        weight: normalizeNumeric(row.weight, "ratio", false),
        market_value: normalizeNumeric(row.market_value, "yuan", false),
      };
    }),
  };
}

/**
 * envelope.result 关键结构运行时检查：后端返回可能偏离声明类型，
 * 非对象时披露并返回 null，由调用方走既有请求失败错误态。
 */
function envelopeResultRecord(value: unknown, endpoint: string): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  console.error(`[bondAnalyticsClient] ${endpoint} 返回的 envelope.result 不是对象，无法归一化。`);
  return null;
}

export function normalizeCreditSpreadMigrationEnvelope(
  envelope: ApiEnvelope<CreditSpreadMigrationPayload>,
): ApiEnvelope<CreditSpreadMigrationPayload> {
  const source = envelopeResultRecord(envelope.result, "credit-spread-migration");
  if (!source) {
    throw new Error("credit-spread-migration envelope.result 缺失关键结构");
  }
  const spreadScenarios = Array.isArray(source.spread_scenarios) ? source.spread_scenarios : [];
  const migrationScenarios = Array.isArray(source.migration_scenarios) ? source.migration_scenarios : [];
  return {
    ...envelope,
    result: {
      ...envelope.result,
      credit_market_value: normalizeNumeric(source.credit_market_value, "yuan", false),
      credit_weight: normalizeNumeric(source.credit_weight, "ratio", false),
      rating_aa_and_below_weight: normalizeNumeric(source.rating_aa_and_below_weight, "ratio", false),
      spread_dv01: normalizeNumeric(source.spread_dv01, "dv01", false),
      weighted_avg_spread: normalizeNumeric(source.weighted_avg_spread, "bp", false, 2),
      weighted_avg_spread_duration: normalizeNumeric(source.weighted_avg_spread_duration, "ratio", false),
      spread_scenarios: spreadScenarios.map((item) => {
        const row = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
        return {
          ...row,
          scenario_name: String(row.scenario_name ?? ""),
          spread_change_bp: normalizeNumeric(row.spread_change_bp, "bp", true),
          pnl_impact: normalizeNumeric(row.pnl_impact, "yuan", true),
          oci_impact: normalizeNumeric(row.oci_impact, "yuan", true),
          tpl_impact: normalizeNumeric(row.tpl_impact, "yuan", true),
        };
      }),
      migration_scenarios: migrationScenarios.map((item) => {
        const row = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
        /* 缺失 ≠ 0：字段缺失/不可解析时透传 null（消费方渲染 —），不得改写成「影响 0 只债券」。 */
        const affectedBondsRaw =
          row.affected_bonds === null || row.affected_bonds === undefined
            ? null
            : Number(row.affected_bonds);
        return {
          ...row,
          scenario_name: String(row.scenario_name ?? ""),
          from_rating: String(row.from_rating ?? ""),
          to_rating: String(row.to_rating ?? ""),
          affected_bonds:
            affectedBondsRaw !== null && Number.isFinite(affectedBondsRaw) ? affectedBondsRaw : null,
          affected_market_value: normalizeNumeric(row.affected_market_value, "yuan", false),
          pnl_impact: normalizeNumeric(row.pnl_impact, "yuan", true),
          oci_impact: normalizeNumeric(row.oci_impact, "yuan", true),
        };
      }),
      concentration_by_issuer: normalizeConcentration(source.concentration_by_issuer),
      concentration_by_industry: normalizeConcentration(source.concentration_by_industry),
      concentration_by_rating: normalizeConcentration(source.concentration_by_rating),
      concentration_by_tenor: normalizeConcentration(source.concentration_by_tenor),
      oci_credit_exposure: normalizeNumeric(source.oci_credit_exposure, "yuan", false),
      oci_spread_dv01: normalizeNumeric(source.oci_spread_dv01, "dv01", false),
      oci_sensitivity_25bp: normalizeNumeric(source.oci_sensitivity_25bp, "yuan", true),
    },
  };
}

export function normalizePortfolioHeadlinesEnvelope(
  envelope: ApiEnvelope<BondPortfolioHeadlinesPayload>,
): ApiEnvelope<BondPortfolioHeadlinesPayload> {
  const source = envelopeResultRecord(envelope.result, "portfolio-headlines");
  if (!source) {
    throw new Error("portfolio-headlines envelope.result 缺失关键结构");
  }
  const byAssetClass = Array.isArray(source.by_asset_class) ? source.by_asset_class : [];
  return {
    ...envelope,
    result: {
      ...envelope.result,
      total_market_value: normalizeNumeric(source.total_market_value, "yuan", false),
      weighted_ytm: normalizeNumeric(source.weighted_ytm, "pct", true),
      weighted_duration: normalizeNumeric(source.weighted_duration, "ratio", false),
      weighted_coupon: normalizeNumeric(source.weighted_coupon, "pct", true),
      total_dv01: normalizeNumeric(source.total_dv01, "dv01", false),
      credit_weight: normalizeNumeric(source.credit_weight, "ratio", false),
      issuer_hhi: normalizeNumeric(source.issuer_hhi, "ratio", false),
      issuer_top5_weight: normalizeNumeric(source.issuer_top5_weight, "ratio", false),
      by_asset_class: byAssetClass.map((item) => {
        const row = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
        return {
          ...row,
          asset_class: String(row.asset_class ?? ""),
          market_value: normalizeNumeric(row.market_value, "yuan", false),
          duration: normalizeNumeric(row.duration, "ratio", false),
          dv01: normalizeNumeric(row.dv01, "dv01", false),
          weight: normalizeNumeric(row.weight, "ratio", false),
        };
      }),
    },
  };
}
