import type { ReactNode } from "react";

import type { NocturneThemeScope } from "../../../theme/themeScopes";

export type MarketWorkbenchPageKey =
  | "cross-asset"
  | "market-data"
  | "macro-observation"
  | "macro-toolkit"
  | "stock-analysis"
  | "news-events"
  | "market-overview";

export type MarketWorkbenchStatus = {
  label: string;
  tone: "ok" | "watch" | "error" | "muted";
  detail?: string;
};

export type MarketWorkbenchMetaItem = {
  label: string;
  value: string;
  /** 悬停提示；值被摘要截断时展示完整内容 */
  hint?: string;
};

export type MarketWorkbenchFrameProps = {
  pageKey: MarketWorkbenchPageKey;
  title: string;
  question: string;
  status: MarketWorkbenchStatus;
  metaItems: MarketWorkbenchMetaItem[];
  navDensity?: "default" | "compact";
  actions?: ReactNode;
  children: ReactNode;
  auditContent?: ReactNode;
  /**
   * 页面主题 scope（tokens.css 的 data-moss-theme-scope 选择器）。
   * frame 顶栏/子导航不在页根子树内，scope 须声明在 frame 根上
   * 才能让整个框架跟随页面色板（如 stock-analysis 的 Nocturne 换肤）。
   * 类型收窄为 palette 字面量联合，拼写错误在编译期报错。
   */
  themeScope?: NocturneThemeScope;
};
