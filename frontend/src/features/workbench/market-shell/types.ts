import type { ReactNode } from "react";

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
};
