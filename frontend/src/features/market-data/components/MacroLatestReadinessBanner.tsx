import { Alert } from "antd";

import type {
  ExternalDataWatermarkEntry,
  ExternalDataWatermarkLedger,
  ResultMeta,
} from "../../../api/contracts";

type MacroLatestReadinessBannerProps = {
  testId: string;
  isLoading: boolean;
  isError: boolean;
  hasSeries: boolean;
  meta: ResultMeta | undefined;
  watermarkLedger?: ExternalDataWatermarkLedger;
  watermarkIsLoading?: boolean;
  watermarkIsError?: boolean;
  maxStaleItems?: number;
  seriesIds?: readonly string[];
};

type MacroWatermarkFreshnessSummary = {
  laggingEntries: ExternalDataWatermarkEntry[];
  lastSuccessfulIngest: string | null;
};

function vendorStaleLabel(status: ResultMeta["vendor_status"]) {
  if (status === "vendor_stale") {
    return "供应商数据可能陈旧。";
  }
  if (status === "vendor_unavailable") {
    return "供应商不可用。";
  }
  return null;
}

function qualityLabel(value: ResultMeta["quality_flag"]) {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return value;
}

function alertType(
  tone: "loading" | "error" | "empty" | "warn" | "ok",
): "info" | "error" | "warning" | "success" {
  if (tone === "error") {
    return "error";
  }
  if (tone === "warn") {
    return "warning";
  }
  if (tone === "empty") {
    return "warning";
  }
  if (tone === "loading") {
    return "info";
  }
  return "success";
}

function isLaggingTier(entry: ExternalDataWatermarkEntry) {
  return entry.freshness_tier === "stale" || entry.freshness_tier === "expired";
}

function ageSortValue(entry: ExternalDataWatermarkEntry) {
  return typeof entry.age_days === "number" ? entry.age_days : -1;
}

function buildMacroWatermarkFreshnessSummary(
  ledger: ExternalDataWatermarkLedger | undefined,
  maxItems = 3,
  seriesIds: readonly string[] = [],
): MacroWatermarkFreshnessSummary {
  const scopedSeriesIds = new Set(seriesIds.filter(Boolean));
  const laggingEntries =
    ledger?.entries
      .filter((entry) => entry.domain === "macro")
      .filter((entry) => scopedSeriesIds.size === 0 || scopedSeriesIds.has(entry.series_id))
      .filter(isLaggingTier)
      .sort((a, b) => ageSortValue(b) - ageSortValue(a))
      .slice(0, maxItems) ?? [];

  return {
    laggingEntries,
    lastSuccessfulIngest: ledger?.summary.last_successful_ingest ?? null,
  };
}

function formatWatermarkEntry(entry: ExternalDataWatermarkEntry) {
  const name = entry.series_name || entry.series_id;
  const age = typeof entry.age_days === "number" ? `T+${entry.age_days}` : "T+未知";
  const tier = entry.freshness_tier ?? "unknown";
  return `${name} 数据 ${age}（${tier}）`;
}

export function MacroLatestReadinessBanner({
  testId,
  isLoading,
  isError,
  hasSeries,
  meta,
  watermarkLedger,
  watermarkIsLoading = false,
  watermarkIsError = false,
  maxStaleItems = 3,
  seriesIds = [],
}: MacroLatestReadinessBannerProps) {
  let tone: "loading" | "error" | "empty" | "warn" | "ok" = "ok";
  const parts: string[] = [];
  const watermarkSummary = buildMacroWatermarkFreshnessSummary(
    watermarkLedger,
    maxStaleItems,
    seriesIds,
  );

  if (isLoading) {
    tone = "loading";
    parts.push("宏观序列最新读面加载中。");
  } else if (isError) {
    tone = "error";
    parts.push("宏观序列最新读面加载失败；请使用下方区块内“重试”。");
  } else if (!hasSeries) {
    tone = "empty";
    parts.push("宏观序列最新读面返回空：当前无可展示序列（非前端补数）。");
  } else {
    parts.push("宏观序列最新读面已返回数据。");
    const stale = meta ? vendorStaleLabel(meta.vendor_status) : null;
    if (stale) {
      tone = "warn";
      parts.push(stale);
    }
    if (meta?.fallback_mode === "latest_snapshot") {
      tone = tone === "ok" ? "warn" : tone;
      parts.push("结果含最新快照降级。");
    }
    if (meta?.quality_flag && meta.quality_flag !== "ok") {
      tone = tone === "ok" ? "warn" : tone;
      parts.push(`质量标记=${qualityLabel(meta.quality_flag)}。`);
    }
    if (watermarkSummary.laggingEntries.length > 0) {
      tone = tone === "ok" ? "warn" : tone;
      parts.push(
        `最陈旧的 ${watermarkSummary.laggingEntries.length} 个序列：${watermarkSummary.laggingEntries
          .map(formatWatermarkEntry)
          .join("；")}。`,
      );
    }
  }

  if (watermarkIsLoading) {
    parts.push("外部数据水位读取中。");
  } else if (watermarkIsError) {
    tone = tone === "ok" ? "warn" : tone;
    parts.push("外部数据水位读取失败，无法判断输入年龄。");
  } else if (watermarkLedger) {
    parts.push(
      `最近成功入库：${watermarkSummary.lastSuccessfulIngest ?? "未知"}。`,
    );
  }

  return (
    <Alert
      data-testid={testId}
      type={alertType(tone)}
      showIcon
      message={parts.join(" ")}
    />
  );
}
