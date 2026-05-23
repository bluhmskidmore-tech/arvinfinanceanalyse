import { designTokens } from "../../../theme/designSystem";

/** 经营驾驶舱 · 投行级视觉 token（仅展示色，不参与金融计算） */

const PRIMARY = designTokens.color.primary[600];
const PRIMARY_AUX = designTokens.color.primary[500];
const PRIMARY_SOFT = designTokens.color.primary[50];

export const COCKPIT_VISUAL = {
  surface: {
    page: "#F3F5F8",
    content: "#F7F9FC",
    card: "#FFFFFF",
    cardSoft: "#FAFBFD",
    cardMuted: "#F6F8FB",
    border: "#DDE4EC",
    divider: "#E7ECF2",
  },
  brand: {
    navy: "#0B1F3A",
    primary: PRIMARY,
    primaryAux: PRIMARY_AUX,
    primarySoft: PRIMARY_SOFT,
    hover: "#F0F6FF",
  },
  sidebar: {
    bg: "#06182D",
    bgSecondary: "#0A2038",
    activeBg: PRIMARY_SOFT,
    activeText: PRIMARY,
    activeIndicator: "#B88746",
    text: "#CBD5E1",
    icon: "#94A3B8",
    group: "#64748B",
  },
  accent: {
    gold: "#B88746",
    goldSoft: "#F8F1E8",
  },
  text: {
    title: "#0B1F3A",
    body: "#1D2939",
    secondary: "#475467",
    muted: "#667085",
    weak: "#98A2B3",
  },
  semantic: {
    risk: "#B94743",
    riskBg: "#FFF1F0",
    gain: "#197A5A",
    gainBg: "#ECFDF5",
    warn: "#B76E00",
    warnBg: "#FFF7E6",
  },
  chart: {
    primary: PRIMARY,
    aux: PRIMARY_AUX,
    teal: "#2D7F9F",
    green: "#197A5A",
    gold: "#B88746",
    gray: "#667085",
    red: "#B94743",
  },
} as const;

/** 经营驾驶舱 typography（展示层，对齐 ref-fidelity 目标稿） */
export const COCKPIT_TYPOGRAPHY = {
  fontSans:
    '"Plus Jakarta Sans", "PingFang SC", "Microsoft YaHei UI", "Noto Sans SC", system-ui, sans-serif',
  fontTabular:
    '"IBM Plex Mono", ui-monospace, "Noto Sans Mono", Menlo, Monaco, Consolas, monospace',
  size: {
    base: 13,
    caption: 11,
    section: 14,
    pageTitle: 15,
    kpi: 22,
    chartAxis: 11,
  },
  weight: {
    body: 500,
    label: 600,
    title: 700,
    kpi: 700,
  },
} as const;

/** 组合分布 / 环形图 / 折线图统一色板 */
export const COCKPIT_CHART_PALETTE: readonly string[] = [
  COCKPIT_VISUAL.chart.primary,
  COCKPIT_VISUAL.chart.aux,
  COCKPIT_VISUAL.chart.teal,
  COCKPIT_VISUAL.chart.green,
  COCKPIT_VISUAL.chart.gold,
  COCKPIT_VISUAL.chart.red,
  COCKPIT_VISUAL.chart.gray,
];
