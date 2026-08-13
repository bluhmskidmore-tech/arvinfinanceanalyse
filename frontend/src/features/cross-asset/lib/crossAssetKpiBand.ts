import { EM_DASH } from "../../../utils/format";
import type { ResolvedCrossAssetKpi } from "./crossAssetKpiModel";

export type CrossAssetKpiBandImpact = "bullish" | "bearish" | "neutral";

export type CrossAssetKpiBandItem = {
  key: string;
  label: string;
  /** 大数值（已按格式剥离单位后缀；无数据 → EM_DASH） */
  valueLabel: string;
  /** 单位（% / bp / 点 等；无数据 → ""） */
  unit: string;
  changeLabel: string;
  impact: CrossAssetKpiBandImpact;
  impactLabel: string;
  sourceLabel: string;
  /** MM-DD；无日期 → EM_DASH */
  dateLabel: string;
  /** 近 20 点 sparkline */
  spark: number[];
};

export const KPI_BAND_SPARK_LENGTH = 20;

/**
 * 利好/利空映射表（固收组合语义）：
 * - 10Y国债收益率：下行=利好，上行=利空（中债估值）
 * - DR007：下行=利好，上行=利空（公共补充）
 * - 沪深300指数：恒中性（公共补充）
 * - 布油(ICE)：上行=利空，下行=利好（公共补充）
 * - USD·CNY：恒中性（公共补充）
 * - 中美10Y利差：上行(收窄)=利好，下行(走阔)=利空（中债+UST）
 */
type KpiBandImpactRule = "down_bullish" | "up_bullish" | "always_neutral";

type KpiBandSlot = {
  key: string;
  label: string;
  sourceLabel: string;
  impactRule: KpiBandImpactRule;
};

export const KPI_BAND_SLOTS: readonly KpiBandSlot[] = [
  { key: "cn_gov_10y", label: "10Y国债收益率", sourceLabel: "中债估值", impactRule: "down_bullish" },
  { key: "money_market_7d", label: "DR007", sourceLabel: "公共补充", impactRule: "down_bullish" },
  { key: "csi300", label: "沪深300指数", sourceLabel: "公共补充", impactRule: "always_neutral" },
  { key: "brent", label: "布油(ICE)", sourceLabel: "公共补充", impactRule: "down_bullish" },
  { key: "usdcny", label: "USD·CNY", sourceLabel: "公共补充", impactRule: "always_neutral" },
  { key: "gov_spread", label: "中美10Y利差", sourceLabel: "中债+UST", impactRule: "up_bullish" },
];

const IMPACT_LABELS: Record<CrossAssetKpiBandImpact, string> = {
  bullish: "利好",
  bearish: "利空",
  neutral: "中性",
};

/** ResolvedCrossAssetKpi 只有 changeLabel 字符串，方向从符号还原。 */
function changeDirection(changeLabel: string): "up" | "down" | "flat" {
  const trimmed = changeLabel.trim();
  if (trimmed.startsWith("+")) {
    return "up";
  }
  if (trimmed.startsWith("-") || trimmed.startsWith("−")) {
    return "down";
  }
  return "flat";
}

function impactFor(rule: KpiBandImpactRule, direction: "up" | "down" | "flat"): CrossAssetKpiBandImpact {
  if (rule === "always_neutral" || direction === "flat") {
    return "neutral";
  }
  if (rule === "down_bullish") {
    return direction === "down" ? "bullish" : "bearish";
  }
  return direction === "up" ? "bullish" : "bearish";
}

/** valueLabel（"1.88%" / "45bp" / "4102.3点" / "7.1234"）拆成数值与单位。 */
function splitValueLabel(kpi: ResolvedCrossAssetKpi): { value: string; unit: string } {
  const label = kpi.valueLabel?.trim() || EM_DASH;
  if (label === EM_DASH) {
    return { value: EM_DASH, unit: "" };
  }
  if (label.endsWith("%")) {
    return { value: label.slice(0, -1), unit: "%" };
  }
  if (label.endsWith("bp")) {
    return { value: label.slice(0, -2), unit: "bp" };
  }
  if (label.endsWith("点")) {
    return { value: label.slice(0, -1), unit: "点" };
  }
  return { value: label, unit: kpi.unit ?? "" };
}

function formatBandDate(tradeDate: string | null | undefined): string {
  if (!tradeDate) {
    return EM_DASH;
  }
  const match = tradeDate.match(/^\d{4}-(\d{2})-(\d{2})/);
  return match ? `${match[1]}-${match[2]}` : tradeDate;
}

/** 来源标签：按槽位口径给出，缺数据/口径变化时按实际 sourceKind 修正。 */
function resolveSourceLabel(slot: KpiBandSlot, kpi: ResolvedCrossAssetKpi): string {
  if (kpi.sourceKind === "missing") {
    return "待接入";
  }
  if (slot.key === "gov_spread") {
    return kpi.label === "中美10Y利差" ? "中债+UST" : "中债口径";
  }
  if (slot.key === "cn_gov_10y") {
    return kpi.sourceKind === "choice" ? "中债估值" : "公共补充";
  }
  if (slot.sourceLabel === "公共补充" && kpi.sourceKind === "choice") {
    return "Choice";
  }
  return slot.sourceLabel;
}

function missingItem(slot: KpiBandSlot): CrossAssetKpiBandItem {
  return {
    key: slot.key,
    label: slot.label,
    valueLabel: EM_DASH,
    unit: "",
    changeLabel: EM_DASH,
    impact: "neutral",
    impactLabel: IMPACT_LABELS.neutral,
    sourceLabel: "待接入",
    dateLabel: EM_DASH,
    spark: [],
  };
}

/** S2 KPI 横带 6 卡装配：固定槽位顺序，sparkline 截近 20 点，null 安全。 */
export function buildKpiBandItems(
  kpis: ResolvedCrossAssetKpi[] | null | undefined,
): CrossAssetKpiBandItem[] {
  const byKey = new Map((kpis ?? []).map((kpi) => [kpi.key, kpi]));
  return KPI_BAND_SLOTS.map((slot) => {
    const kpi = byKey.get(slot.key);
    if (!kpi) {
      return missingItem(slot);
    }
    const { value, unit } = splitValueLabel(kpi);
    const impact = impactFor(slot.impactRule, changeDirection(kpi.changeLabel ?? ""));
    return {
      key: slot.key,
      label: slot.label,
      valueLabel: value,
      unit,
      changeLabel: kpi.changeLabel?.trim() || EM_DASH,
      impact,
      impactLabel: IMPACT_LABELS[impact],
      sourceLabel: resolveSourceLabel(slot, kpi),
      dateLabel: formatBandDate(kpi.tradeDate),
      spark: (kpi.sparkline ?? []).slice(-KPI_BAND_SPARK_LENGTH),
    };
  });
}
