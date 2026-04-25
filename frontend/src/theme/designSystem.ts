/**
 * MOSS-V3 design tokens baseline — single source for scales + shell compatibility mapping.
 * Domain features may extend locally (see bond analytics cockpit tokens); prefer importing from here for new UI.
 */

export const designTokens = {
  color: {
    /** Institutional blue-green primary scale (accent anchored ~ #2c5a79) */
    primary: {
      50: "#eff4f8",
      100: "#dde9f1",
      200: "#bcd4e4",
      300: "#8fb4cd",
      400: "#5d8faf",
      500: "#3f7394",
      600: "#2c5a79",
      700: "#254963",
      800: "#1f3c52",
      900: "#172f40",
    },
    success: {
      50: "#ecf8f0",
      100: "#d6efe0",
      200: "#b0dfc8",
      300: "#83c9a8",
      400: "#52ad84",
      500: "#3c7a58",
      600: "#306648",
      700: "#27543c",
      800: "#1f4330",
      900: "#163424",
    },
    warning: {
      50: "#faf3e7",
      100: "#f3e4cc",
      200: "#e9cfa5",
      300: "#dab57a",
      400: "#c9944f",
      500: "#b56f22",
      600: "#935a1c",
      700: "#764816",
      800: "#5e3912",
      900: "#4a2e0f",
    },
    danger: {
      50: "#fbeceb",
      100: "#f5d5d2",
      200: "#ecb0aa",
      300: "#de8279",
      400: "#cf5d52",
      500: "#b04f42",
      600: "#934038",
      700: "#78342e",
      800: "#602923",
      900: "#4d211d",
    },
    info: {
      50: "#e8f4fc",
      100: "#d2e8f8",
      200: "#a8d0f0",
      300: "#74b2e5",
      400: "#4495d7",
      500: "#2f79bb",
      600: "#25649c",
      700: "#1e527f",
      800: "#184066",
      900: "#12334f",
    },
    /** Neutral / gray for surfaces, borders, readable text */
    neutral: {
      50: "#f1f3f2",
      100: "#e9eeeb",
      200: "#e4ebe8",
      300: "#d6dedc",
      400: "#bec8c6",
      500: "#9eadab",
      600: "#7a8795",
      700: "#586575",
      800: "#3d4a56",
      900: "#1c2833",
    },
    semantic: {
      /** Positive P&L, surplus, favorable move */
      profit: "#15803d",
      /** Negative P&L, deficit */
      loss: "#b91c1c",
      /** Market-style up (often aligned with profit in CN bond context) */
      up: "#15803d",
      /** Market-style down */
      down: "#b91c1c",
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
     * UI + 中文：使用系统黑体栈，避免页面级外部字体依赖。
     * Ant Design `ConfigProvider` 使用本字段作为全局 `fontFamily`。
     */
    sans: '"PingFang SC", "Microsoft YaHei UI", "Noto Sans SC", system-ui, sans-serif',
    /** 数字列、KPI 等 */
    tabular: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Noto Sans Mono", monospace',
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
