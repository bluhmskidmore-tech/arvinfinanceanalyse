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

export function buildHomeMacroReleaseHistoryItems(
  items: readonly HomeMacroReleaseContextHistoryItem[],
): HomeMacroReleaseHistoryItem[] {
  return items.map((item) => ({
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
    sourceName: item.source_name ?? "来源待确认",
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
      note: [statusLabel(item.source_status), ...item.notes].filter(Boolean).join("；") || null,
      sourceLabel: item.source_name ? `来源：${item.source_name}` : null,
    },
  }));
}
