/** 经营驾驶舱 · 投行级视觉 token（仅展示色，不参与金融计算） */

export const COCKPIT_VISUAL = {
  surface: {
    page: "#F5F7FA",
    content: "#F8FAFC",
    card: "#FFFFFF",
    cardSoft: "#F9FBFD",
    cardMuted: "#F8FAFC",
    border: "#E5EAF0",
    divider: "#EDF1F5",
  },
  brand: {
    navy: "#0B1F3A",
    primary: "#1D4E89",
    primarySoft: "#E8F1FB",
    hover: "#F0F6FF",
  },
  sidebar: {
    bg: "#071A2F",
    bgSecondary: "#0B2542",
    activeBg: "#EAF2FF",
    activeText: "#123E73",
    text: "#CBD5E1",
    icon: "#94A3B8",
    group: "#64748B",
  },
  text: {
    title: "#101828",
    body: "#1D2939",
    secondary: "#475467",
    muted: "#667085",
    weak: "#98A2B3",
  },
  semantic: {
    risk: "#C2413A",
    riskBg: "#FFF1F0",
    gain: "#16835F",
    gainBg: "#ECFDF5",
    warn: "#C77700",
    warnBg: "#FFF7E6",
  },
  chart: {
    primary: "#1D4E89",
    navy: "#0B1F3A",
    teal: "#2F80A7",
    green: "#16835F",
    orange: "#C77700",
    gray: "#6B7280",
    red: "#C2413A",
  },
} as const;

/** 组合分布 / 环形图 / 折线图统一色板 */
export const COCKPIT_CHART_PALETTE: readonly string[] = [
  COCKPIT_VISUAL.chart.primary,
  COCKPIT_VISUAL.chart.teal,
  COCKPIT_VISUAL.chart.green,
  COCKPIT_VISUAL.chart.orange,
  COCKPIT_VISUAL.chart.gray,
  COCKPIT_VISUAL.chart.red,
  COCKPIT_VISUAL.chart.navy,
];
