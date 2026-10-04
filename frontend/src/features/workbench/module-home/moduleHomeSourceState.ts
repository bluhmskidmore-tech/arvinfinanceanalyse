import type { UseQueryResult } from "@tanstack/react-query";
import type {
  ModuleHomeStatus,
  ModuleHomeSourceQueries,
  ModuleHomeDataState,
  ModuleHomeDataNote,
} from "./moduleHomeModel";
import {
  queryIsForbidden,
  forbiddenQueryStatus,
} from "./moduleHomeQueryPermission";
import { EM_DASH } from "../../../utils/format";
import type { ResultMeta } from "../../../api/contracts";
import type { ModuleWorkbenchHomeKind } from "./moduleHomeConfig";
import { moduleWorkbenchHomeConfigs } from "./moduleHomeConfig";
import { buildStateSurfaces } from "../../../pageModel";
import type { StateSurfaceItem } from "../../../pageModel";

export function resultMetaIsStale(meta: ResultMeta | undefined) {
  return meta?.quality_flag === "stale" || meta?.vendor_status === "vendor_stale";
}

export function resultMetaIsPartial(meta: ResultMeta | undefined) {
  return Boolean(
    meta &&
      (meta.quality_flag !== "ok" ||
        meta.vendor_status !== "ok" ||
        meta.fallback_mode !== "none" ||
        meta.fallback_date),
  );
}

export function portfolioUsesPublishedBalanceDates(queries: ModuleHomeSourceQueries): boolean {
  const publication = queries.balancePublicationStatus;
  return Boolean(publication?.isSuccess && publication.data?.enabled && publication.data.available
    && publication.data.generation && publication.data.report_dates.length > 0);
}

export function portfolioCoreReadQueries(queries: ModuleHomeSourceQueries): ModuleHomeSourceQueries {
  return {
    balanceDates: portfolioUsesPublishedBalanceDates(queries) ? undefined : queries.balanceDates,
    balancePublicationStatus: queries.balancePublicationStatus,
    balanceOverview: queries.balanceOverview,
    bondDates: queries.bondDates,
    bondHeadline: queries.bondHeadline,
    bondRisk: queries.bondRisk,
  };
}

export function portfolioWaterfallState(
  query: ModuleHomeSourceQueries["pnlVolumeRate"],
  requestedDate: string,
): StateSurfaceItem[] {
  if (!query) return [];
  const payload = query.data?.result;
  const meta = query.data?.result_meta;
  const filteredDate = meta?.filters_applied?.resolved_report_date;
  const filteredRequestDate = meta?.filters_applied?.requested_report_date;
  const dataDate = meta?.as_of_date || meta?.resolved_report_date || meta?.fallback_date
    || (typeof filteredDate === "string" ? filteredDate : "");
  const requestDate = meta?.requested_report_date
    || (typeof filteredRequestDate === "string" ? filteredRequestDate : "") || requestedDate;
  const dateDetail = `请求日 ${requestDate}；数据日 ${dataDate || EM_DASH}。`;
  const warnings = [...new Set(payload?.warnings ?? [])].filter(Boolean).join(" ");
  const hasFallback = meta?.fallback_mode === "latest_snapshot" || Boolean(meta?.fallback_date);
  return buildStateSurfaces([
    {
      key: "query-error", variant: "error", when: Boolean(query.isError),
      title: payload ? "归因刷新失败，当前显示缓存结果" : "损益变动分解读取失败",
      description: payload ? `${dateDetail}缓存结果仅供复核。` : "本图来源读取失败，请重试页面或进入归因明细复核。",
    },
    {
      key: "loading", variant: "loading", when: Boolean(query.isLoading && !payload && !query.isError),
      title: "损益变动分解读取中", description: "正在读取本图归因数据。",
    },
    {
      key: "empty", variant: "empty", when: !payload && !query.isLoading && !query.isError,
      title: "损益变动分解暂无数据", description: "本图来源尚未返回可用结果。",
    },
    {
      key: "inputs", variant: "definition-pending", when: payload?.has_complete_inputs === false,
      title: "归因输入不完整", description: "当前分解存在输入缺口，已返回金额仅供复核，缺值保留为空。",
    },
    {
      key: "quality", variant: meta?.quality_flag === "error" ? "error" : "definition-pending",
      when: Boolean(meta && ["warning", "error", "missing"].includes(meta.quality_flag)),
      title: meta?.quality_flag === "error" ? "归因数据质量错误"
        : meta?.quality_flag === "missing" ? "归因来源数据缺失" : "归因数据存在质量预警",
      description: "本图来源未通过完整质量核验，请结合明细复核。",
    },
    {
      key: "warnings", variant: "definition-pending", when: Boolean(warnings),
      title: "归因来源提示", description: warnings,
    },
    {
      key: "fallback", variant: "fallback-date", when: hasFallback,
      title: "归因使用回退数据", description: dateDetail,
    },
    {
      key: "stale", variant: "stale", when: resultMetaIsStale(meta),
      title: "归因数据已过期", description: hasFallback ? "本图来源标记为过期，仅供复核。" : dateDetail,
    },
    {
      key: "vendor", variant: "error", when: meta?.vendor_status === "vendor_unavailable",
      title: "归因数据来源不可用", description: "当前返回结果仅供复核，需核实来源后使用。",
    },
    {
      key: "source", variant: "definition-pending",
      when: Boolean(payload && (!meta || meta.basis !== "formal" || !meta.formal_use_allowed)),
      title: "归因正式使用资格待核验", description: "本图来源未确认允许正式使用，当前读数仅供分析复核。",
    },
    {
      key: "date", variant: "definition-pending", when: Boolean(payload && !dataDate),
      title: "归因数据日期待核验", description: `请求日 ${requestDate}；实际数据日未返回，不能以归因月份代替。`,
    },
    {
      key: "date-mismatch", variant: "fallback-date",
      when: Boolean(payload && dataDate && requestDate !== EM_DASH && dataDate !== requestDate && !hasFallback),
      title: "归因数据日与请求日不一致", description: dateDetail,
    },
    {
      key: "previous", variant: "empty", when: Boolean(payload && !payload.has_previous_data),
      title: "缺少上期归因数据", description: "当前无法展示两期损益变动分解。",
    },
  ]);
}
export function queryIsInitialLoading(query: UseQueryResult<unknown> | undefined) {
  return Boolean(query?.isLoading);
}

export function queryHasData(query: UseQueryResult<unknown> | undefined) {
  return Boolean(query?.data);
}

export function queryStatus(
  key: string,
  label: string,
  query: UseQueryResult<unknown> | undefined,
  readyDetail: string,
): ModuleHomeStatus {
  if (!query) {
    return {
      key,
      label,
      value: "未接入",
      detail: "当前首页未触发该读链路。",
      tone: "muted",
    };
  }
  if (queryIsInitialLoading(query)) {
    return {
      key,
      label,
      value: "读取中",
      detail: "等待既有 API 返回。",
      tone: "muted",
    };
  }
  if (query.isError) {
    if (queryIsForbidden(query)) return forbiddenQueryStatus(key, label);
    // §6 状态去重：失败原因全页只在状态条与数据说明各说一次，分区内保持安静占位。
    return {
      key,
      label,
      value: "读取失败",
      detail: EM_DASH,
      tone: "error",
    };
  }
  if (!query.data) {
    return {
      key,
      label,
      value: "暂无数据",
      detail: "后端返回为空或该能力待接入。",
      tone: "watch",
    };
  }
  return {
    key,
    label,
    value: "已返回",
    detail: readyDetail,
    tone: "ok",
  };
}

export function emptyRowsWatchStatus(
  status: ModuleHomeStatus,
  rows: readonly unknown[],
  emptyDetail: string,
): ModuleHomeStatus {
  if (status.tone !== "ok" || rows.length > 0) {
    return status;
  }
  return {
    ...status,
    value: "明细为空",
    detail: emptyDetail,
    tone: "watch",
  };
}

export function hasError(queries: ModuleHomeSourceQueries) {
  return Object.values(queries).some((query) => query?.isError);
}

export function hasLoading(queries: ModuleHomeSourceQueries) {
  return Object.values(queries).some((query) => queryIsInitialLoading(query));
}

export function hasData(queries: ModuleHomeSourceQueries) {
  return Object.values(queries).some((query) => queryHasData(query));
}

export function queryResultMeta(
  query: UseQueryResult<unknown> | undefined,
): ResultMeta | undefined {
  const payload = query?.data;
  if (!payload || typeof payload !== "object" || !("result_meta" in payload)) {
    return undefined;
  }
  return (payload as { result_meta?: ResultMeta }).result_meta;
}

export const MODULE_HOME_STATE_LABEL: Record<ModuleHomeDataState, string> = {
  loading: "读取中",
  empty: "暂无数据",
  error: "读取失败",
  partial: "部分可用",
  stale: "数据过期",
  ready: "已接入",
};

export function metaIsFormalDecisionSource(meta: ResultMeta | undefined) {
  return Boolean(
    meta &&
      meta.basis === "formal" &&
      meta.formal_use_allowed &&
      meta.quality_flag === "ok" &&
      meta.fallback_mode === "none" &&
      !meta.fallback_date,
  );
}

export function sourceUseStatus(
  status: ModuleHomeStatus,
  meta: ResultMeta | undefined,
  blockedDetail: string,
): ModuleHomeStatus {
  if (status.tone !== "ok" || metaIsFormalDecisionSource(meta)) {
    return status;
  }
  return {
    ...status,
    value: "分析口径",
    detail: blockedDetail,
    tone: "watch",
  };
}

export function combinedQueryStatus(
  key: string,
  label: string,
  queries: Array<UseQueryResult<unknown> | undefined>,
  readyDetail: string,
): ModuleHomeStatus {
  const active = queries.filter(Boolean);
  if (active.length === 0) {
    return queryStatus(key, label, undefined, readyDetail);
  }
  if (active.some((query) => query?.isError)) {
    // §6 状态去重：同 queryStatus，失败原因不在每个分区重复。
    return {
      key,
      label,
      value: "读取失败",
      detail: EM_DASH,
      tone: "error",
    };
  }
  if (active.some((query) => queryIsInitialLoading(query))) {
    return {
      key,
      label,
      value: "读取中",
      detail: "等待既有 API 返回。",
      tone: "muted",
    };
  }
  if (active.every((query) => !query?.data)) {
    return {
      key,
      label,
      value: "暂无数据",
      detail: "后端返回为空或该能力待接入。",
      tone: "watch",
    };
  }
  return {
    key,
    label,
    value: "已返回",
    detail: readyDetail,
    tone: "ok",
  };
}

/**
 * 组合首页专用：依赖报告日列表的读链路在上游日期 query 失败或未返回时是 enabled:false
 * （pending/idle、无 data、非 error），通用 queryStatus 会把它误判成「暂无数据 / 后端返回为空」。
 * 这里先看上游，把归因落在报告日读取上。
 */
function upstreamDateBlockedStatus(
  key: string,
  label: string,
  upstream: UseQueryResult<unknown> | undefined,
): ModuleHomeStatus | null {
  if (upstream?.isError) {
    return {
      key,
      label,
      value: "上游失败",
      detail: "报告日列表读取失败，本读链路未触发。",
      tone: "error",
    };
  }
  if (queryIsInitialLoading(upstream)) {
    return {
      key,
      label,
      value: "读取中",
      detail: "等待报告日列表返回。",
      tone: "muted",
    };
  }
  return null;
}

function queryIsIdleWithoutData(query: UseQueryResult<unknown> | undefined) {
  return Boolean(query) && !query?.data && !query?.isError;
}

export function dependentQueryStatus(
  key: string,
  label: string,
  query: UseQueryResult<unknown> | undefined,
  upstream: UseQueryResult<unknown> | undefined,
  readyDetail: string,
): ModuleHomeStatus {
  if (queryIsIdleWithoutData(query)) {
    const blocked = upstreamDateBlockedStatus(key, label, upstream);
    if (blocked) {
      return blocked;
    }
  }
  return queryStatus(key, label, query, readyDetail);
}

export function dependentCombinedQueryStatus(
  key: string,
  label: string,
  queries: Array<UseQueryResult<unknown> | undefined>,
  upstream: UseQueryResult<unknown> | undefined,
  readyDetail: string,
): ModuleHomeStatus {
  const active = queries.filter(Boolean);
  if (active.length > 0 && active.every((query) => queryIsIdleWithoutData(query))) {
    const blocked = upstreamDateBlockedStatus(key, label, upstream);
    if (blocked) {
      return blocked;
    }
  }
  return combinedQueryStatus(key, label, queries, readyDetail);
}

function countFailedQueries(queries: ModuleHomeSourceQueries) {
  return Object.values(queries).filter((query) => query?.isError).length;
}

/**
 * 按底层 error 引用去重：组合首页把 home-summary 一次请求派生成 9 个投影（spread 复制，
 * error 引用相同），一次失败不能被写成「9 项来源读取失败」。
 */
export function countDistinctFailedQueries(queries: ModuleHomeSourceQueries) {
  const failed = Object.values(queries).filter((query) => query?.isError);
  return new Set(failed.map((query) => query?.error ?? query)).size;
}

export function baseDataNote(
  kind: ModuleWorkbenchHomeKind,
  queries: ModuleHomeSourceQueries,
  errorCount = countFailedQueries(queries),
): ModuleHomeDataNote {
  const config = moduleWorkbenchHomeConfigs[kind];
  // §6 状态去重：同一失败原因合并为一行，不随失败来源数量重复。
  const errorLines =
    errorCount > 0 ? [`${errorCount} 项来源读取失败：不使用前端补数。`] : [];
  return {
    title: "数据说明",
    lines: [...config.dataNotes, ...errorLines],
    tone: errorLines.length > 0 ? "error" : "ok",
  };
}

export function metaEvidenceLine(label: string, meta: ResultMeta | undefined): string | null {
  if (!meta) {
    return null;
  }
  const reportDate =
    meta.resolved_report_date ??
    meta.as_of_date ??
    meta.requested_report_date ??
    meta.fallback_date ??
    EM_DASH;
  const table = meta.tables_used?.length ? meta.tables_used.join(" / ") : "未披露";
  const rows =
    typeof meta.evidence_rows === "number" ? `${meta.evidence_rows} 行` : "未披露";
  const fallback =
    meta.fallback_mode === "none" && !meta.fallback_date
      ? "none"
      : `${meta.fallback_mode}${meta.fallback_date ? `/${meta.fallback_date}` : ""}`;
  return `${label}证据：report_date=${reportDate}；basis=${meta.basis}；formal_use_allowed=${String(
    meta.formal_use_allowed,
  )}；quality=${meta.quality_flag}；result_kind=${meta.result_kind}；tables=${table}；evidence_rows=${rows}；fallback=${fallback}。`;
}
