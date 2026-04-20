import type { ThemeConfig } from "antd";

import { designTokens } from "./designSystem";
import { shellTokens } from "./tokens";

export const workbenchTheme: ThemeConfig = {
  token: {
    colorPrimary: shellTokens.colorAccent,
    colorSuccess: shellTokens.colorSuccess,
    colorWarning: shellTokens.colorWarning,
    colorError: shellTokens.colorDanger,
    colorInfo: designTokens.color.info[500],
    colorText: shellTokens.colorTextPrimary,
    colorTextSecondary: shellTokens.colorTextSecondary,
    colorTextTertiary: shellTokens.colorTextMuted,
    colorBorder: shellTokens.colorBorder,
    colorBorderSecondary: shellTokens.colorBorderSoft,
    colorBgBase: shellTokens.colorBgSurface,
    colorBgContainer: shellTokens.colorBgSurface,
    colorBgElevated: shellTokens.colorBgCanvas,
    colorFillAlter: shellTokens.colorBgMuted,
    borderRadius: shellTokens.radiusCard,
    wireframe: false,
    fontSize: designTokens.fontSize[13],
    fontSizeHeading1: designTokens.fontSize[30],
    fontSizeHeading2: designTokens.fontSize[24],
    fontSizeHeading3: designTokens.fontSize[20],
    fontSizeHeading4: designTokens.fontSize[18],
    fontSizeHeading5: designTokens.fontSize[16],
    fontFamily: designTokens.fontFamily.sans,
    lineHeight: designTokens.lineHeight.normal,
    boxShadow: designTokens.shadow.card,
    boxShadowSecondary: designTokens.shadow.popover,
    padding: designTokens.space[3],
    paddingLG: designTokens.space[4],
    paddingSM: designTokens.space[2],
    paddingXS: designTokens.space[1],
    paddingXXS: 2,
    controlHeight: designTokens.density.tableRowNormal,
    controlHeightLG: 40,
    controlHeightSM: designTokens.density.tableRowCompact,
  },
  components: {
    Button: {
      borderRadius: designTokens.radius.sm,
      paddingInline: designTokens.space[4],
      paddingBlock: designTokens.space[2],
      fontWeight: 500,
      primaryShadow: "none",
    },
    Input: {
      borderRadius: designTokens.radius.sm,
      paddingBlock: designTokens.space[2],
      paddingInline: designTokens.space[3],
    },
    Select: {
      borderRadius: designTokens.radius.sm,
    },
    Card: {
      borderRadiusLG: shellTokens.radiusCard,
      paddingLG: designTokens.card.padding,
      headerBg: "transparent",
    },
    Table: {
      borderRadius: designTokens.radius.sm,
      cellPaddingBlock: Math.round((designTokens.density.tableRowNormal - designTokens.fontSize[13] * 1.35) / 2),
      cellPaddingInline: designTokens.space[3],
      cellFontSize: designTokens.fontSize[13],
      headerBg: designTokens.color.neutral[100],
      headerColor: shellTokens.colorTextSecondary,
      rowHoverBg: designTokens.color.neutral[50],
    },
    Layout: {
      bodyBg: shellTokens.colorBgApp,
      siderBg: shellTokens.colorBgSurface,
      headerBg: "transparent",
    },
    Tabs: {
      horizontalMargin: `0 0 ${designTokens.space[4]}px 0`,
      titleFontSize: designTokens.fontSize[14],
    },
    Modal: {
      boxShadow: designTokens.shadow.modal,
    },
    Tooltip: {
      colorBgSpotlight: designTokens.color.neutral[800],
    },
  },
};
