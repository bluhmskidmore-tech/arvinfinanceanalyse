import type { ResearchCalendarEvent } from "../../../../api/contracts";

export type HomeResearchCalendarItem = {
  id: string;
  date: string;
  title: string;
  kindLabel: string;
  severity: ResearchCalendarEvent["severity"];
  amountLabel: string;
};

export type HomeResearchCalendarModel = {
  items: readonly HomeResearchCalendarItem[];
  status: "ready" | "loading" | "empty" | "error";
  windowLabel: string;
  message: string | null;
};

const KIND_LABEL: Record<ResearchCalendarEvent["kind"], string> = {
  macro: "宏观",
  supply: "供给",
  auction: "招标",
  internal: "内部",
};

const SEVERITY_RANK: Record<ResearchCalendarEvent["severity"], number> = {
  high: 0,
  medium: 1,
  low: 2,
};

function compareEvents(left: ResearchCalendarEvent, right: ResearchCalendarEvent): number {
  return (
    left.date.localeCompare(right.date) ||
    SEVERITY_RANK[left.severity] - SEVERITY_RANK[right.severity] ||
    left.title.localeCompare(right.title)
  );
}

function mapEvent(event: ResearchCalendarEvent): HomeResearchCalendarItem {
  return {
    id: event.id,
    date: event.date,
    title: event.title,
    kindLabel: KIND_LABEL[event.kind] ?? event.kind,
    severity: event.severity,
    amountLabel: event.amount_label?.trim() || "—",
  };
}

export function buildHomeResearchCalendarModel(input: {
  events?: readonly ResearchCalendarEvent[] | null;
  isLoading: boolean;
  isError: boolean;
  startDate: string;
  endDate: string;
  limit?: number;
}): HomeResearchCalendarModel {
  const windowLabel = `${input.startDate} 至 ${input.endDate}`;

  if (input.isError) {
    return {
      items: [],
      status: "error",
      windowLabel,
      message: "研究日历加载失败，请稍后刷新。",
    };
  }

  if (input.isLoading) {
    return {
      items: [],
      status: "loading",
      windowLabel,
      message: "正在加载研究日历…",
    };
  }

  if (!input.events || input.events.length === 0) {
    return {
      items: [],
      status: "empty",
      windowLabel,
      message: "当前窗口暂无供给/招标事件。",
    };
  }

  const limit = input.limit ?? 8;
  const items = [...input.events]
    .filter((event) => event.severity === "high" || event.severity === "medium")
    .sort(compareEvents)
    .slice(0, limit)
    .map(mapEvent);

  if (items.length === 0) {
    return {
      items: [],
      status: "empty",
      windowLabel,
      message: "当前窗口暂无高/中优先级事件。",
    };
  }

  return {
    items,
    status: "ready",
    windowLabel,
    message: null,
  };
}
