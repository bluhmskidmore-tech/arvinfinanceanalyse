import { EM_DASH } from "../../../utils/format";

export function formatCorrelation(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "不可用";
  }
  return value.toFixed(2);
}

export type LinkageDirectionTone = "up" | "down" | "neutral";

export function linkageDirectionTone(direction: string | null | undefined): LinkageDirectionTone {
  if (!direction || direction === EM_DASH) {
    return "neutral";
  }
  if (/上|涨|升|多|强|positive/i.test(direction)) {
    return "up";
  }
  if (/下|跌|降|弱|空|negative|falling/i.test(direction)) {
    return "down";
  }
  return "neutral";
}

export function formatLinkageDirectionLabel(direction: string | null | undefined): string {
  if (!direction || direction === EM_DASH) {
    return EM_DASH;
  }
  const normalized = direction.trim().toLowerCase();
  if (normalized === "positive") {
    return "偏正";
  }
  if (normalized === "negative") {
    return "偏负";
  }
  if (normalized === "neutral") {
    return "中性";
  }
  if (/上|涨|升|多|强/.test(direction)) {
    return "偏强";
  }
  if (/下|跌|降|弱|空/.test(direction)) {
    return "偏弱";
  }
  return direction;
}

export function linkageDirectionPillClass(direction: string | null | undefined): string {
  const tone = linkageDirectionTone(direction);
  if (tone === "up") {
    return "market-data-dir-pill market-data-dir-pill--pos";
  }
  if (tone === "down") {
    return "market-data-dir-pill market-data-dir-pill--neg";
  }
  return "market-data-dir-pill market-data-dir-pill--neu";
}

export function correlationStrength(value: number | null | undefined): "none" | "weak" | "strong" {
  if (value == null || Number.isNaN(value)) {
    return "none";
  }
  return Math.abs(value) >= 0.5 ? "strong" : "weak";
}
