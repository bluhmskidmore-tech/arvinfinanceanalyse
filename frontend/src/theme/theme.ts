import { theme as antdTheme } from "antd";
import type { ThemeConfig } from "antd";

import { designTokens, nocturneTokens } from "./designSystem";

const routeSurfaceShadow = "none";

/*
 * antd cssinjs 基础皮肤：全站 37 个 scope Nocturne 收敛完成（2026-08-13）后，
 * token 由 dhApiTokens 钢蓝基准切至 nocturneTokens（数值源=tokens.css Nocturne
 * scope）。cssinjs 随 ConfigProvider 的 React context 生效，portal 到 body 的
 * 下拉/弹层（脱离页根 scope 容器、CSS 变量链翻不动）同样被覆盖。
 */
export const workbenchTheme: ThemeConfig = {
  algorithm: antdTheme.darkAlgorithm,
  token: {
    colorPrimary: nocturneTokens.color.blue,
    colorSuccess: nocturneTokens.color.green,
    colorWarning: nocturneTokens.color.amber,
    colorError: nocturneTokens.color.red,
    colorInfo: nocturneTokens.color.blue,
    colorLink: nocturneTokens.color.blue,
    /* hover/active 亮阶沿 tokens.css 惯例：--ib-accent-hover→accent-400、
       rail 激活文字→accent-300（Nocturne 无独立 link-active 槽位）。 */
    colorLinkHover: nocturneTokens.color.accent400,
    colorLinkActive: nocturneTokens.color.accent300,
    colorText: nocturneTokens.color.ink,
    colorTextSecondary: nocturneTokens.color.inkSoft,
    colorTextTertiary: nocturneTokens.color.inkMuted,
    colorBorder: nocturneTokens.color.line,
    colorBorderSecondary: nocturneTokens.color.lineSoft,
    colorBgBase: nocturneTokens.color.bg,
    colorBgContainer: nocturneTokens.color.panel,
    colorBgElevated: nocturneTokens.color.panel2,
    colorFillAlter: nocturneTokens.color.panel2,
    borderRadius: nocturneTokens.radius,
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
      borderRadius: nocturneTokens.radius,
      paddingInline: designTokens.space[4],
      paddingBlock: designTokens.space[2],
      fontWeight: 600,
      primaryColor: nocturneTokens.color.bg,
      primaryShadow: "none",
    },
    Input: {
      borderRadius: nocturneTokens.radius,
      paddingBlock: designTokens.space[2],
      paddingInline: designTokens.space[3],
    },
    Select: {
      borderRadius: nocturneTokens.radius,
    },
    Card: {
      borderRadiusLG: nocturneTokens.radius,
      paddingLG: designTokens.card.padding,
      headerBg: "transparent",
      boxShadow: routeSurfaceShadow,
    },
    Table: {
      borderRadius: nocturneTokens.radius,
      cellPaddingBlock: Math.round((designTokens.density.tableRowCompact - designTokens.fontSize[13] * 1.35) / 2),
      cellPaddingInline: designTokens.space[3],
      cellFontSize: designTokens.fontSize[13],
      headerBg: nocturneTokens.color.panel3,
      headerColor: nocturneTokens.color.inkSoft,
      /* --nct-accent 8%，对齐 tokens.css --moss-institutional-row-hover 的 mix 惯例。 */
      rowHoverBg: "rgba(145, 132, 217, 0.08)",
    },
    Layout: {
      bodyBg: nocturneTokens.color.bg,
      siderBg: nocturneTokens.color.rail,
      headerBg: "transparent",
    },
    Tabs: {
      horizontalMargin: `0 0 ${designTokens.space[4]}px 0`,
      titleFontSize: designTokens.fontSize[14],
      cardBg: nocturneTokens.color.panel2,
      itemSelectedColor: nocturneTokens.color.blue,
    },
    Modal: {
      boxShadow: routeSurfaceShadow,
    },
    Tooltip: {
      colorBgSpotlight: nocturneTokens.color.panel3,
    },
  },
};
