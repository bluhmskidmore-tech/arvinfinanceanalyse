import type { CSSProperties } from "react";

import type {
  BondAnalyticsPromotionDestination,
  BondAnalyticsTruthTone,
} from "../lib/bondAnalyticsOverviewModel";

export const PERIOD_OPTIONS = [
  { value: "MoM", label: "Month" },
  { value: "YTD", label: "YTD" },
  { value: "TTM", label: "TTM" },
];

export const BORDER = "#d9e4f0";
export const SHADOW = "0 16px 34px rgba(19, 37, 70, 0.07)";

export const EYEBROW: CSSProperties = {
  fontSize: 11,
  color: "#7185a0",
  textTransform: "uppercase",
  letterSpacing: "0.14em",
  fontWeight: 700,
};

export const FIELD: CSSProperties = {
  marginBottom: 6,
  color: "#667a95",
  fontSize: 11,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  fontWeight: 700,
};

export function panelStyle(background?: string): CSSProperties {
  return { borderRadius: 24, borderColor: BORDER, boxShadow: SHADOW, background };
}

export function toneColor(tone: BondAnalyticsTruthTone) {
  if (tone === "success") {
    return { background: "#ecf8f0", color: "#25724d", borderColor: "#cfe7d8", accent: "#5e9b76" };
  }
  if (tone === "warning") {
    return { background: "#fff5e8", color: "#9f5b0b", borderColor: "#f0d7b1", accent: "#d08e3d" };
  }
  if (tone === "danger") {
    return { background: "#fdeeee", color: "#a9342f", borderColor: "#efc7c6", accent: "#d06763" };
  }
  return { background: "#eff4f9", color: "#48627d", borderColor: "#d8e2ed", accent: "#88a0b8" };
}

export function readinessTagColor(statusLabel: string) {
  if (statusLabel === "eligible") return "success";
  if (statusLabel === "request-error") return "error";
  if (statusLabel === "placeholder-blocked" || statusLabel === "warning") return "warning";
  return "default";
}

export function readinessSurface(statusLabel: string) {
  if (statusLabel === "eligible") {
    return { background: "#eff8f2", borderColor: "#d0e8d8", accent: "#2f8f63", text: "#275e45" };
  }
  if (statusLabel === "request-error") {
    return { background: "#fff0f0", borderColor: "#efcccc", accent: "#b42318", text: "#7a251f" };
  }
  if (statusLabel === "placeholder-blocked" || statusLabel === "warning") {
    return { background: "#fff7eb", borderColor: "#f0debb", accent: "#b86a16", text: "#815014" };
  }
  return { background: "#f7f9fc", borderColor: "#dde6f0", accent: "#5d7691", text: "#415467" };
}

export function promotionLabel(destination: BondAnalyticsPromotionDestination) {
  if (destination === "headline") return "Headline eligible";
  if (destination === "main-rail") return "Main rail eligible";
  return "Readiness / drill only";
}
