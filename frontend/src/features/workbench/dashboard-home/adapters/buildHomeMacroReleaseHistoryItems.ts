import type {
  HomeMacroChangeUnit,
  HomeMacroReleaseContextHistoryItem,
  HomeMacroReleaseContextMetric,
} from "../../../../api/contracts";
import type {
  HomeMacroReleaseChangeTone,
  HomeMacroReleaseHistoryItem,
} from "./buildHomeMacroBriefingModel";

import { EM_DASH } from "../../../../utils/format";
const GAP = EM_DASH;

function fixed(value: number, precision: number): string {
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  });
}

function metricValue(metric: HomeMacroReleaseContextMetric, value: number | null): string {
  if (value == null) {
    return GAP;
  }
  const formatted = fixed(value, metric.precision);
  if (metric.display_unit === "pct") {
    return `${formatted}%`;
  }
  return formatted;
}

function changeValue(metric: HomeMacroReleaseContextMetric): string {
  if (metric.change_value == null) {
    return GAP;
  }
  const sign = metric.change_value > 0 ? "+" : "";
  const formatted = `${sign}${fixed(metric.change_value, metric.precision)}`;
  const suffix: Record<HomeMacroChangeUnit, string> = {
    index_point: "点",
    pct_point: "个百分点",
    persons: "人",
    bp: "bp",
  };
  return `${formatted}${suffix[metric.change_unit]}`;
}

function metricSummary(
  metrics: readonly HomeMacroReleaseContextMetric[],
  field: "actual_value" | "previous_value",
): string {
  if (metrics.length === 1) {
    return metricValue(metrics[0], metrics[0][field]);
  }
  return metrics
    .map((metric) => `${metric.label} ${metricValue(metric, metric[field])}`)
    .join(" / ");
}

function changeSummary(metrics: readonly HomeMacroReleaseContextMetric[]): string {
  if (metrics.length === 1) {
    return changeValue(metrics[0]);
  }
  return metrics.map((metric) => `${metric.label} ${changeValue(metric)}`).join(" / ");
}

function changeTone(
  metrics: readonly HomeMacroReleaseContextMetric[],
): HomeMacroReleaseChangeTone {
  if (metrics.length !== 1) {
    return "neutral";
  }
  const direction = metrics[0].direction;
  return direction === "up" || direction === "down" || direction === "flat"
    ? direction
    : "neutral";
}

function importanceLabel(value: string): string {
  if (value === "high") {
    return "高优先级";
  }
  if (value === "medium") {
    return "中优先级";
  }
  return "低优先级";
}

function statusLabel(value: HomeMacroReleaseContextHistoryItem["source_status"]): string {
  const labels = {
    ready: "已更新",
    partial: "部分数据",
    stale: "数据偏旧",
    fallback: "已使用备用源",
    source_pending: "数据源待接入",
    error: "读取失败",
  } as const;
  return labels[value];
}

function sourceDisplayName(value: string | null): string | null {
  const source = value
    ?.replace(/^(?:来源\s*[:：]\s*)+/i, "")
    .trim();
  if (!source) {
    return null;
  }
  const normalized = source.toLowerCase();
  if (
    normalized === "nbs" ||
    normalized.includes("nbs official release") ||
    normalized.includes("national bureau of statistics")
  ) {
    return "国家统计局";
  }
  return source;
}

const BUSINESS_NOTE_TRANSLATIONS: ReadonlyArray<readonly [RegExp, string]> = [
  [/^metric observation dates are not aligned\.?$/i, "各指标观测期不一致，需复核。"],
  [/^previous metric observation dates are not aligned\.?$/i, "各指标前值观测期不一致，需复核。"],
  [/^source unavailable\b/i, "数据源暂不可用。"],
  [/^cadence mismatch\b/i, "数据频率与页面口径不一致。"],
  [/^unit mismatch\b/i, "数据单位与页面口径不一致。"],
  [/^current value is null\b/i, "本期值缺失。"],
  [/^previous value unavailable\b/i, "前值暂缺。"],
  [/^observation is \d+ days old\.?$/i, "数据已超过新鲜度阈值。"],
  [/^official source unavailable or invalid\b/i, "官方来源不可用，已使用备用数据源。"],
  [/^official source stale\b/i, "官方来源偏旧，已使用备用数据源。"],
  [/^higher-priority source not selected\b/i, "已使用备用数据源，请复核来源优先级。"],
];

function businessNote(note: string): string | null {
  const trimmed = note.trim();
  if (
    !trimmed ||
    /^(?:selected vendor|rejected vendor|vendor evidence|source integration pending)\b/i.test(
      trimmed,
    ) ||
    /\b(?:series_id|metric_key|vendor_name|source_status)\b/i.test(trimmed)
  ) {
    return null;
  }
  const translated = BUSINESS_NOTE_TRANSLATIONS.find(([pattern]) => pattern.test(trimmed));
  if (translated) {
    return translated[1];
  }
  return trimmed;
}

function historyNote(
  status: HomeMacroReleaseContextHistoryItem["source_status"],
  notes: readonly string[],
): string {
  const visibleNotes = notes
    .map(businessNote)
    .filter((note): note is string => Boolean(note));
  return [...new Set([statusLabel(status), ...visibleNotes])].join("；");
}

export function buildHomeMacroReleaseHistoryItems(
  items: readonly HomeMacroReleaseContextHistoryItem[],
): HomeMacroReleaseHistoryItem[] {
  return items.map((item) => {
    const sourceName = sourceDisplayName(item.source_name);
    return {
      id: item.indicator_key,
      date: item.observation_date ?? item.release_date ?? "",
      dateLabel: item.reference_period ?? item.observation_date ?? "待更新",
      daysUntilLabel: statusLabel(item.source_status),
      region: item.region,
      title: item.title,
      category: item.category,
      importance: item.importance,
      importanceLabel: importanceLabel(item.importance),
      timeLabel: item.release_date ?? EM_DASH,
      sourceName: sourceName ?? "来源待确认",
      sourceUrl: "",
      history: {
        latestLabel: item.reference_period ?? item.observation_date ?? "最近一期",
        latestValue: metricSummary(item.metrics, "actual_value"),
        previousLabel:
          item.previous_reference_period ?? item.previous_observation_date ?? "前一期",
        previousValue: metricSummary(item.metrics, "previous_value"),
        changeLabel: "变动",
        changeValue: changeSummary(item.metrics),
        changeTone: changeTone(item.metrics),
        note: historyNote(item.source_status, item.notes),
        sourceLabel: sourceName ? `来源：${sourceName}` : null,
      },
    };
  });
}
