import { theme as antdTheme } from "antd";
import type { ThemeConfig } from "antd";

import { designTokens, dhApiTokens } from "./designSystem";

const routeSurfaceShadow = "none";

export const workbenchTheme: ThemeConfig = {
  algorithm: antdTheme.darkAlgorithm,
  token: {
    colorPrimary: dhApiTokens.color.blue,
    colorSuccess: dhApiTokens.color.green,
    colorWarning: dhApiTokens.color.amber,
    colorError: dhApiTokens.color.red,
    colorInfo: dhApiTokens.color.blue,
    colorLink: dhApiTokens.color.blue,
    colorLinkHover: dhApiTokens.color.blueHover,
    colorLinkActive: dhApiTokens.color.blueActive,
    colorText: dhApiTokens.color.ink,
    colorTextSecondary: dhApiTokens.color.inkSoft,
    colorTextTertiary: dhApiTokens.color.inkMuted,
    colorBorder: dhApiTokens.color.line,
    colorBorderSecondary: dhApiTokens.color.lineSoft,
    colorBgBase: dhApiTokens.color.bg,
    colorBgContainer: dhApiTokens.color.panel,
    colorBgElevated: dhApiTokens.color.panel2,
    colorFillAlter: dhApiTokens.color.panel2,
    borderRadius: 2,
    wireframe: false,
    fontSize: designTokens.fontSize[13],
    fontSizeHeading1: designTokens.fontSize[30],
    fontSizeHeading2: designTokens.fontSize[24],
    fontSizeHeading3: designTokens.fontSize[20],
    fontSizeHeading4: designTokens.fontSize[18],
    fontSizeHeading5: designTokens.fontSize[16],
    fontFamily: designTokens.fontFamily.sans,
    lineHeight: designTokens.lineHeight.normal,
    boxShadow: "none",
    boxShadowSecondary: routeSurfaceShadow,
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
      borderRadius: 2,
      paddingInline: designTokens.space[4],
      paddingBlock: designTokens.space[2],
      fontWeight: 600,
      primaryColor: dhApiTokens.color.bg,
      primaryShadow: "none",
    },
    Input: {
      borderRadius: 2,
      paddingBlock: designTokens.space[2],
      paddingInline: designTokens.space[3],
    },
    Select: {
      borderRadius: 2,
    },
    Card: {
      borderRadiusLG: 2,
      paddingLG: designTokens.card.padding,
      headerBg: "transparent",
      boxShadow: routeSurfaceShadow,
    },
    Table: {
      borderRadius: 2,
      cellPaddingBlock: Math.round((designTokens.density.tableRowCompact - designTokens.fontSize[13] * 1.35) / 2),
      cellPaddingInline: designTokens.space[3],
      cellFontSize: designTokens.fontSize[13],
      headerBg: dhApiTokens.color.panel3,
      headerColor: dhApiTokens.color.inkSoft,
      rowHoverBg: "rgba(114, 167, 220, 0.08)",
    },
    Layout: {
      bodyBg: dhApiTokens.color.bg,
      siderBg: dhApiTokens.color.rail,
      headerBg: "transparent",
    },
    Tabs: {
      horizontalMargin: `0 0 ${designTokens.space[4]}px 0`,
      titleFontSize: designTokens.fontSize[14],
      cardBg: dhApiTokens.color.panel2,
      itemSelectedColor: dhApiTokens.color.blue,
    },
    Modal: {
      boxShadow: routeSurfaceShadow,
    },
    Tooltip: {
      colorBgSpotlight: dhApiTokens.color.panel3,
    },
  },
};
