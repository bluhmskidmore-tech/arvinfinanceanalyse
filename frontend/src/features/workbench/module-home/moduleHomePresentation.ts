import {
  decimalToNumber,
  YUAN_PER_YI,
} from "./portfolioHomeModel";
import { EM_DASH } from "../../../utils/format";
import type {
  ResultMeta,
  ApiEnvelope,
} from "../../../api/contracts";
import type { UseQueryResult } from "@tanstack/react-query";
import type { ModuleHomeStatus } from "./moduleHomeModel";
import type {
  ModuleHomeDetailRow,
  ModuleHomeDetailSection,
  ModuleHomeDetailChart,
  ModuleHomeDetailPanel,
} from "./moduleHomeDetailTypes";

export function formatYiFromYuan(value: string | number | null | undefined) {
  const parsed = decimalToNumber(value);
  if (parsed === null) {
    return EM_DASH;
  }
  return `${(parsed / YUAN_PER_YI).toLocaleString("zh-CN", {
    maximumFractionDigits: 2,
  })} 亿元`;
}

export function plain(value: unknown, fallback = EM_DASH) {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  if (typeof value === "object" && "display" in value) {
    return String((value as { display?: unknown }).display ?? fallback);
  }
  return String(value);
}

export function metaLabel(meta: ResultMeta | undefined) {
  if (!meta) {
    return "无元数据";
  }
  const date = meta.as_of_date ?? meta.resolved_report_date ?? meta.fallback_date ?? "";
  const parts = [meta.result_kind, meta.basis, date].filter(Boolean);
  return parts.join(" / ");
}

export function envelopeMeta(query: UseQueryResult<ApiEnvelope<unknown>> | undefined) {
  return metaLabel(query?.data?.result_meta);
}

/** Home depth zone: keep source labels, drop YYYY-MM-DD segments from panel meta. */
export function formatPanelMetaForHome(meta: string | undefined): string | undefined {
  if (!meta?.trim()) {
    return meta;
  }
  const parts = meta
    .split(/\s*·\s*/)
    .map((part) => part.trim())
    .filter((part) => part && !/^\d{4}-\d{2}-\d{2}$/.test(part));
  return parts.length > 0 ? parts.join(" · ") : undefined;
}

export function buildDetailPanel(args: {
  key: string;
  title: string;
  meta: string;
  status: ModuleHomeStatus;
  rows: ModuleHomeDetailRow[];
  sections?: ModuleHomeDetailSection[];
  chart?: ModuleHomeDetailChart;
  showRowsWhenWarning?: boolean;
}): ModuleHomeDetailPanel {
  const ready =
    args.status.tone === "ok" ||
    (args.showRowsWhenWarning === true && args.status.tone === "watch" && args.rows.length > 0);
  const sections = ready ? args.sections : undefined;
  return {
    key: args.key,
    title: args.title,
    meta: args.meta,
    stateLabel: args.status.value,
    stateDetail: args.status.detail,
    rows: ready ? args.rows : [],
    sections,
    tone: args.status.tone,
    chart: ready ? args.chart : undefined,
  };
}
