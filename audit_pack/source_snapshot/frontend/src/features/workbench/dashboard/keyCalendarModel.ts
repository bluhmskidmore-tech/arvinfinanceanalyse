import type { ResearchCalendarEvent } from "../../../api/contracts";
import type { DashboardHubCalendarItem } from "./DashboardOverviewSections";

export type DashboardKeyCalendarStatus =
  | "ready"
  | "loading"
  | "no-data"
  | "no-high-medium"
  | "error";

export type DashboardKeyCalendarModel = {
  items: DashboardHubCalendarItem[];
  status: DashboardKeyCalendarStatus;
  message: string | null;
};

const severityRank: Record<ResearchCalendarEvent["severity"], number> = {
  high: 0,
  medium: 1,
  low: 2,
};

function compareDashboardCalendarEvents(
  left: ResearchCalendarEvent,
  right: ResearchCalendarEvent,
) {
  return (
    left.date.localeCompare(right.date) ||
    severityRank[left.severity] - severityRank[right.severity] ||
    left.title.localeCompare(right.title) ||
    left.id.localeCompare(right.id)
  );
}

function mapResearchCalendarEventToDashboardItem(
  event: ResearchCalendarEvent,
): DashboardHubCalendarItem {
  return {
    id: event.id,
    title: event.title,
    time: event.date,
    kind: event.kind === "internal" ? "internal" : event.kind,
    severity: event.severity,
  };
}

export function buildDashboardKeyCalendarModel({
  events,
  isLoading,
  isError,
  limit = 4,
}: {
  events?: ResearchCalendarEvent[];
  isLoading: boolean;
  isError: boolean;
  limit?: number;
}): DashboardKeyCalendarModel {
  if (isError) {
    return {
      items: [],
      status: "error",
      message: "关键日历外部事件加载失败。",
    };
  }

  if (isLoading) {
    return {
      items: [],
      status: "loading",
      message: "正在加载关键日历外部事件。",
    };
  }

  if (!events || events.length === 0) {
    return {
      items: [],
      status: "no-data",
      message: "近 7 天至未来 14 天暂无外部日历事件。",
    };
  }

  const items = events
    .filter((event) => event.severity === "high" || event.severity === "medium")
    .sort(compareDashboardCalendarEvents)
    .map(mapResearchCalendarEventToDashboardItem)
    .slice(0, limit);

  if (items.length === 0) {
    return {
      items: [],
      status: "no-high-medium",
      message: "近 7 天至未来 14 天暂无高/中优先级外部事件。",
    };
  }

  return {
    items,
    status: "ready",
    message: null,
  };
}
