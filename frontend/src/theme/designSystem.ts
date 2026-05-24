/**
 * MOSS-V3 design tokens baseline — single source for scales + shell compatibility mapping.
 * Domain features may extend locally (see bond analytics cockpit tokens); prefer importing from here for new UI.
 */

export const designTokens = {
  color: {
    /**
     * Institutional blue primary — 与「总览工作台」主导航/主按钮深蓝对齐（锚点 #1850a1）。
     */
    primary: {
      50: "#e8f1fb",
      100: "#d0e3f6",
      200: "#a8c9ec",
      300: "#79a7de",
      400: "#4d84cc",
      500: "#2f68b8",
      600: "#1850a1",
      700: "#144287",
      800: "#10356a",
      900: "#0c2a54",
    },
    /** 状态绿 — 与总览 KPI 顶条、严格/正向标签的森林绿一致（锚点 #2d8a5e） */
    success: {
      50: "#ecf8f2",
      100: "#d5efe0",
      200: "#aedfc8",
      300: "#7fc8a4",
      400: "#52ad84",
      500: "#2d8a5e",
      600: "#25714d",
      700: "#1d5c40",
      800: "#174833",
      900: "#123828",
    },
    /** 警示橙 — 与总览「中」优先级等强调一致（锚点 #d97706） */
    warning: {
      50: "#fff9eb",
      100: "#fef0d4",
      200: "#fde0a8",
      300: "#fbc874",
      400: "#f8a93a",
      500: "#d97706",
      600: "#b35c05",
      700: "#8f4708",
      800: "#713a0c",
      900: "#5c300e",
    },
    danger: {
      50: "#fef2f2",
      100: "#fee2e2",
      200: "#fecaca",
      300: "#fca5a5",
      400: "#f87171",
      500: "#ef4444",
      600: "#dc2626",
      700: "#b91c1c",
      800: "#991b1b",
      900: "#7f1d1d",
    },
    /** 信息/链接蓝 — 与总览内链、次强调亮蓝一致（锚点 #3b82f6） */
    info: {
      50: "#eff6ff",
      100: "#dbeafe",
      200: "#bfdbfe",
      300: "#93c5fd",
      400: "#60a5fa",
      500: "#3b82f6",
      600: "#2563eb",
      700: "#1d4ed8",
      800: "#1e40af",
      900: "#1e3a8a",
    },
    /** Neutral — 背景与正文灰贴近总览（#f5f7f9 底、#1f2937 / #6b7280 字） */
    neutral: {
      50: "#f5f7f9",
      100: "#eceff3",
      200: "#e2e6ec",
      300: "#d1d5db",
      400: "#9ca3af",
      500: "#8b95a1",
      600: "#6b7280",
      700: "#4b5563",
      800: "#374151",
      900: "#1f2937",
    },
    /**
     * Warm cockpit palette for shell chrome and editorial surfaces.
     * Keep isolated from institutional blue scales so dashboard business semantics stay unchanged.
     */
    warm: {
      porcelain: "#f6f1e8",
      paper: "#fffdf8",
      stone: "#e4d8c8",
      taupe: "#b8a38f",
      charcoal: "#342b27",
      ink: "#2f2824",
      terracotta: "#b85c38",
      sage: "#708c74",
      burgundy: "#7c3e46",
      slateBlue: "#667a96",
      rail: "#f0e6d8",
    },
    /** Dashboard cockpit reference-fidelity palette; visual-only, no metric semantics. */
    cockpit: {
      navy950: "#06182d",
      navy925: "#08213f",
      navy900: "#09223e",
      navy875: "#0a2038",
      navy850: "#0b1f3a",
      navy825: "#0b2542",
      navy800: "#102b49",
      navy750: "#17375d",
      blue900: "#0f2544",
      blue800: "#123e73",
      blue700: "#0f4a8a",
      blue650: "#0f58ba",
      blue600: "#1d5fa7",
      blue100: "#c7daf4",
      blue75: "#dce8f5",
      blue50: "#eaf2fb",
      blue25: "#eef5ff",
      blue20: "#eef5fc",
      blueTint: "#f0f6ff",
      blueWash: "#f3f8fe",
      blueMist: "#f8fbff",
      ink900: "#0f172a",
      ink850: "#1d2939",
      ink800: "#334155",
      ink700: "#475467",
      ink650: "#475569",
      ink600: "#64748b",
      ink550: "#667085",
      ink450: "#94a3b8",
      ink400: "#98a2b3",
      ink350: "#9eb0c4",
      ink300: "#b7c6d8",
      ink200: "#cbd5e1",
      border300: "#c8d3df",
      border250: "#cfd9e6",
      border225: "#d8e0ea",
      border200: "#d8e3ef",
      border175: "#dde4ec",
      border150: "#e4e9f0",
      border125: "#e6ebf1",
      border100: "#e7ecf2",
      surface100: "#edf1f5",
      surface75: "#edf2f7",
      surface50: "#f1f5f9",
      surface40: "#f3f5f8",
      surface30: "#f6f8fb",
      surface25: "#f7f9fc",
      surface20: "#f8fafc",
      surface10: "#fafbfd",
      amber900: "#6f4400",
      amber800: "#8f6329",
      amber700: "#b76e00",
      amber600: "#b88746",
      amber300: "#ffd890",
      amber100: "#eadcc8",
      amber75: "#f8f1e8",
      amber50: "#fff7e6",
      amber25: "#fff8ed",
      amberWash: "#fffaf2",
      green600: "#197a5a",
      green400: "#58bf98",
      green50: "#eaf8f2",
      green25: "#ecfdf5",
      red700: "#b94743",
      red400: "#e58a83",
      red50: "#fff1f0",
      teal600: "#2d7f9f",
      white: "#ffffff",
      shortWhite: "#fff",
    },
    semantic: {
      /** Positive P&L, surplus, favorable move */
      profit: "#2d8a5e",
      /** Negative P&L, deficit */
      loss: "#ef4444",
      /** Market-style up (often aligned with profit in CN bond context) */
      up: "#2d8a5e",
      /** Market-style down */
      down: "#ef4444",
    },
  },
  /** 4px-based spacing scale */
  space: {
    1: 4,
    2: 8,
    3: 12,
    4: 16,
    5: 20,
    6: 24,
    7: 32,
    8: 40,
    9: 48,
    10: 64,
  },
  fontSize: {
    11: 11,
    12: 12,
    13: 13,
    14: 14,
    16: 16,
    18: 18,
    20: 20,
    24: 24,
    30: 30,
  },
  lineHeight: {
    tight: 1.25,
    snug: 1.35,
    normal: 1.5,
    relaxed: 1.7,
  },
  fontFamily: {
    /**
     * UI：Plus Jakarta Sans（拉丁）+ 中文系统栈；经 index.html Google Fonts 加载。
     */
    sans:
      '"Plus Jakarta Sans", "PingFang SC", "Microsoft YaHei UI", "Noto Sans SC", system-ui, sans-serif',
    /** 数字列、KPI（IBM Plex Mono + tabular nums） */
    tabular:
      '"IBM Plex Mono", ui-monospace, "Noto Sans Mono", Menlo, Monaco, Consolas, monospace',
  },
  radius: {
    sm: 6,
    md: 12,
    lg: 18,
    xl: 24,
  },
  shadow: {
    /** Hero / shell panels (legacy Workbench lift) */
    panel: "0 20px 44px rgba(22, 35, 46, 0.08)",
    card: "0 10px 24px rgba(22, 35, 46, 0.06)",
    popover: "0 12px 32px rgba(22, 35, 46, 0.12)",
    modal: "0 24px 48px rgba(22, 35, 46, 0.16)",
  },
  density: {
    tableRowCompact: 28,
    tableRowNormal: 36,
    tableRowComfortable: 44,
  },
  card: {
    padding: 16,
    gap: 16,
    headerPadding: 12,
  },
  motion: {
    durationFast: 150,
    durationBase: 200,
    durationSlow: 280,
    easeOut: "cubic-bezier(0.33, 1, 0.68, 1)",
    easeInOut: "cubic-bezier(0.65, 0, 0.35, 1)",
    easeEmphasized: "cubic-bezier(0.2, 0, 0, 1)",
  },
} as const;

/** Inline style helper for numeric tables / KPI values */
export const tabularNumsStyle = {
  fontVariantNumeric: "tabular-nums" as const,
  fontFamily: designTokens.fontFamily.tabular,
};

export type DesignTokens = typeof designTokens;
