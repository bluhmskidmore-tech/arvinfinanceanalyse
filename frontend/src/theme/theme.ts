import { theme as antdTheme } from "antd";
import type { ThemeConfig } from "antd";

import { designTokens, nocturneTokens } from "./designSystem";

const routeSurfaceShadow = "none";
const controlPaddingBlock = (
  designTokens.density.tableRowNormal - designTokens.fontSize[13] * designTokens.lineHeight.normal
) / 2 - 1;

function hexColorWithAlpha(hexColor: string, alpha: number): string {
  const hex = /^#([0-9a-f]{6})$/i.exec(hexColor)?.[1];
  if (!hex) {
    throw new Error(`Expected a six-digit hex color, received "${hexColor}"`);
  }
  const channel = (offset: number) => Number.parseInt(hex.slice(offset, offset + 2), 16);
  return `rgba(${channel(0)}, ${channel(2)}, ${channel(4)}, ${alpha})`;
}

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
    borderRadiusLG: nocturneTokens.radius,
    borderRadiusSM: nocturneTokens.radius,
    borderRadiusXS: nocturneTokens.radius,
    wireframe: false,
    fontSize: designTokens.fontSize[13],
    fontSizeSM: designTokens.fontSize[12],
    fontSizeLG: designTokens.fontSize[14],
    fontSizeXL: designTokens.fontSize[20],
    fontSizeHeading1: designTokens.fontSize[20],
    fontSizeHeading2: designTokens.fontSize[14],
    fontSizeHeading3: designTokens.fontSize[13],
    fontSizeHeading4: designTokens.fontSize[13],
    fontSizeHeading5: designTokens.fontSize[13],
    fontWeightStrong: designTokens.fontWeight.semibold,
    fontFamily: designTokens.fontFamily.sans,
    lineHeight: designTokens.lineHeight.normal,
    lineHeightHeading1: designTokens.lineHeight.tight,
    lineHeightHeading2: designTokens.lineHeight.snug,
    lineHeightHeading3: designTokens.lineHeight.snug,
    lineHeightHeading4: designTokens.lineHeight.snug,
    lineHeightHeading5: designTokens.lineHeight.snug,
    boxShadow: "none",
    boxShadowSecondary: routeSurfaceShadow,
    padding: designTokens.space[3],
    paddingLG: designTokens.space[4],
    paddingSM: designTokens.space[2],
    paddingXS: designTokens.space[1],
    paddingXXS: 2,
    controlHeight: designTokens.density.tableRowNormal,
    controlHeightLG: designTokens.density.tableRowNormal,
    controlHeightSM: designTokens.density.tableRowNormal,
  },
  components: {
    Button: {
      borderRadius: nocturneTokens.radius,
      paddingInline: designTokens.space[4],
      paddingBlock: designTokens.space[2],
      fontWeight: designTokens.fontWeight.medium,
      contentFontSize: designTokens.fontSize[13],
      contentFontSizeLG: designTokens.fontSize[13],
      contentFontSizeSM: designTokens.fontSize[13],
      primaryColor: nocturneTokens.color.bg,
      primaryShadow: "none",
    },
    Input: {
      borderRadius: nocturneTokens.radius,
      paddingBlock: controlPaddingBlock,
      paddingBlockLG: controlPaddingBlock,
      paddingBlockSM: controlPaddingBlock,
      paddingInline: designTokens.space[3],
      inputFontSize: designTokens.fontSize[13],
      inputFontSizeLG: designTokens.fontSize[13],
      inputFontSizeSM: designTokens.fontSize[13],
    },
    Select: {
      borderRadius: nocturneTokens.radius,
      fontSize: designTokens.fontSize[13],
      fontSizeLG: designTokens.fontSize[13],
      fontSizeSM: designTokens.fontSize[13],
      optionFontSize: designTokens.fontSize[13],
    },
    DatePicker: {
      borderRadius: nocturneTokens.radius,
      paddingBlock: controlPaddingBlock,
      paddingBlockLG: controlPaddingBlock,
      paddingBlockSM: controlPaddingBlock,
      inputFontSize: designTokens.fontSize[13],
      inputFontSizeLG: designTokens.fontSize[13],
      inputFontSizeSM: designTokens.fontSize[13],
    },
    InputNumber: {
      borderRadius: nocturneTokens.radius,
      paddingBlock: controlPaddingBlock,
      paddingBlockLG: controlPaddingBlock,
      paddingBlockSM: controlPaddingBlock,
      inputFontSize: designTokens.fontSize[13],
      inputFontSizeLG: designTokens.fontSize[13],
      inputFontSizeSM: designTokens.fontSize[13],
    },
    Card: {
      borderRadiusLG: nocturneTokens.radius,
      paddingLG: designTokens.card.padding,
      headerBg: "transparent",
      boxShadow: routeSurfaceShadow,
    },
    Table: {
      borderRadius: nocturneTokens.radius,
      /* 表头圆角默认取 borderRadiusLG（8→10），与面板/控件的 8px 不一致，显式钉回。 */
      headerBorderRadius: nocturneTokens.radius,
      lineHeight: designTokens.table.lineHeight,
      cellPaddingBlock: Math.round((designTokens.table.rowHeight - designTokens.table.fontSize * designTokens.table.lineHeight - 1) / 2),
      cellPaddingBlockMD: Math.round((designTokens.table.rowHeight - designTokens.table.fontSize * designTokens.table.lineHeight - 1) / 2),
      cellPaddingBlockSM: Math.round((designTokens.table.rowHeightCompact - designTokens.table.fontSize * designTokens.table.lineHeight - 1) / 2),
      cellPaddingInline: designTokens.space[3],
      cellFontSize: designTokens.table.fontSize,
      cellFontSizeMD: designTokens.table.fontSize,
      cellFontSizeSM: designTokens.table.fontSize,
      headerBg: nocturneTokens.color.panel3,
      headerColor: nocturneTokens.color.inkSoft,
      /* 表头层级靠底色与 soft 色，不靠 600 粗体和列间竖线（对齐 DataTable 原语）。 */
      fontWeightStrong: designTokens.table.headerWeight,
      headerSplitColor: "transparent",
      /* --nct-accent 8%，对齐 tokens.css --moss-institutional-row-hover 的 mix 惯例。 */
      rowHoverBg: hexColorWithAlpha(nocturneTokens.color.blue, 0.08),
    },
    Layout: {
      bodyBg: nocturneTokens.color.bg,
      siderBg: nocturneTokens.color.rail,
      headerBg: "transparent",
    },
    Tabs: {
      horizontalMargin: `0 0 ${designTokens.space[4]}px 0`,
      titleFontSize: designTokens.fontSize[12],
      titleFontSizeLG: designTokens.fontSize[12],
      titleFontSizeSM: designTokens.fontSize[12],
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
