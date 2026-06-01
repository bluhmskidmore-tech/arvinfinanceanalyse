import macroReleaseCalendarRaw from "../../../../../../config/dashboard_macro_release_calendar_2026.json";
import type { ChoiceNewsEvent } from "../../../../api/contracts";
import {
  dashboardMacroNewsFallbackTopicLabel,
  dashboardMacroNewsTopicLabel,
} from "../../dashboard/dashboardMacroNewsTopics";
import { addDaysToIsoDate } from "../../pages/dashboardPageHelpers";
import {
  shouldIncludeMacroNewsEvent,
  summarizeMacroNewsEvent,
} from "./macroNewsPresentation";
import type { HomeResearchCalendarModel } from "./buildHomeResearchCalendarModel";

export type HomeMacroReleaseItem = {
  id: string;
  date: string;
  dateLabel: string;
  daysUntilLabel: string;
  region: string;
  title: string;
  category: string;
  importance: string;
  importanceLabel: string;
  timeLabel: string;
  sourceName: string;
  sourceUrl: string;
};

export type HomeMacroNewsItem = {
  id: string;
  timeLabel: string;
  topicLabel: string;
  title: string;
  freshnessLabel: string;
};

export type HomeMacroSupplyItem = {
  id: string;
  label: string;
};

export type HomeMacroBriefingModel = {
  releaseItems: readonly HomeMacroReleaseItem[];
  releaseWindowLabel: string;
  releaseMessage: string | null;
  newsItems: readonly HomeMacroNewsItem[];
  newsMessage: string | null;
  newsStale: boolean;
  newsFreshnessLabel: string;
  newsSourceLabel: string;
  newsAsOfLabel: string;
  newsStatusLabel: string;
  newsRefreshLabel: string;
  supplyItems: readonly HomeMacroSupplyItem[];
};

type MacroReleaseCalendarRow = {
  id: string;
  date: string;
  time_label: string;
  region: string;
  title: string;
  category: string;
  importance: string;
  source_name: string;
  source_url: string;
};

type MacroNewsItemsResult = Pick<
  HomeMacroBriefingModel,
  "newsItems" | "newsMessage" | "newsStale" | "newsFreshnessLabel" | "newsSourceLabel" | "newsAsOfLabel" | "newsStatusLabel" | "newsRefreshLabel"
>;

const RELEASE_WINDOW_DAYS = 45;
const RELEASE_LIMIT = 6;
const NEWS_LIMIT = 6;
const NEWS_STALE_DAYS = 7;
const MACRO_NEWS_CHOICE_SOURCE_LABEL = "来源：Choice 宏观新闻";
const MACRO_NEWS_FALLBACK_SOURCE_LABEL = "来源：Tushare 宏观快讯（Choice 不可用或偏旧兜底）";
const MACRO_NEWS_REFRESH_LABEL = "刷新：随页面查询自动更新";
const macroReleaseCalendar = macroReleaseCalendarRaw as readonly MacroReleaseCalendarRow[];

function importanceLabel(importance: string): string {
  if (importance === "high") {
    return "高优先级";
  }
  if (importance === "medium") {
    return "中优先级";
  }
  if (importance === "low") {
    return "低优先级";
  }
  return importance || "待确认";
}

function dateLabel(date: string): string {
  return date.length >= 10 ? date.slice(5, 10) : date;
}

function dateTimeLabel(value: string): string {
  const normalized = value.trim();
  if (!normalized || normalized === "—") {
    return "时间待核";
  }
  if (normalized.length >= 16) {
    return `${normalized.slice(5, 10)} ${normalized.slice(11, 16)}`;
  }
  return dateLabel(normalized);
}

function daysBetween(leftIso: string, rightIso: string): number | null {
  const left = new Date(`${leftIso.slice(0, 10)}T00:00:00Z`);
  const right = new Date(`${rightIso.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(left.getTime()) || Number.isNaN(right.getTime())) {
    return null;
  }
  return Math.floor((left.getTime() - right.getTime()) / 86_400_000);
}

function daysUntilLabel(date: string, todayIsoDate: string): string {
  const days = daysBetween(date, todayIsoDate);
  if (days == null) {
    return "待确认";
  }
  if (days === 0) {
    return "今日";
  }
  if (days === 1) {
    return "明日";
  }
  if (days > 1) {
    return `${days}天后`;
  }
  return `${Math.abs(days)}天前`;
}

function buildReleaseItems(todayIsoDate: string): HomeMacroReleaseItem[] {
  const windowEndDate = addDaysToIsoDate(todayIsoDate, RELEASE_WINDOW_DAYS);
  return macroReleaseCalendar
    .filter((item) => item.date >= todayIsoDate && item.date <= windowEndDate)
    .sort((left, right) => left.date.localeCompare(right.date) || left.title.localeCompare(right.title, "zh-CN"))
    .slice(0, RELEASE_LIMIT)
    .map((item) => ({
      id: item.id,
      date: item.date,
      dateLabel: dateLabel(item.date),
      daysUntilLabel: daysUntilLabel(item.date, todayIsoDate),
      region: item.region,
      title: item.title,
      category: item.category,
      importance: item.importance,
      importanceLabel: importanceLabel(item.importance),
      timeLabel: item.time_label,
      sourceName: item.source_name,
      sourceUrl: item.source_url,
    }));
}

function buildNewsItemsFromEvents(input: {
  events?: readonly ChoiceNewsEvent[] | null;
  todayIsoDate: string;
  topicLabel: (topicCode: string) => string;
  sourceLabel: string;
  emptyMessage: string;
  statusWhenFresh: string;
  statusWhenStale: string;
  statusWhenEmpty: string;
  requireMacroRelevance?: boolean;
}): MacroNewsItemsResult {
  const seenTitles = new Set<string>();
  const sortedEvents = (input.events ?? [])
    .filter((event) =>
      shouldIncludeMacroNewsEvent(event, { requireMacroRelevance: Boolean(input.requireMacroRelevance) }),
    )
    .slice()
    .sort((left, right) => right.received_at.localeCompare(left.received_at));
  const newsItems = sortedEvents
    .flatMap((event) => {
      const title = summarizeMacroNewsEvent(event);
      const key = title.trim().toLowerCase();
      if (!title || seenTitles.has(key)) {
        return [];
      }
      seenTitles.add(key);
      const timeLabel = dateTimeLabel(event.received_at);
      return [
        {
          id: event.event_key,
          timeLabel,
          topicLabel: input.topicLabel(event.topic_code),
          title,
          freshnessLabel: `最近更新 ${timeLabel}`,
        },
      ];
    })
    .slice(0, NEWS_LIMIT);

  const latestDate = sortedEvents[0]?.received_at.slice(0, 10) ?? "";
  const staleDays = latestDate ? daysBetween(input.todayIsoDate, latestDate) : null;
  const newsStale = staleDays != null && staleDays > NEWS_STALE_DAYS;
  const newsFreshnessLabel = newsItems[0]?.freshnessLabel ?? "暂无更新";
  const newsAsOfLabel = newsItems[0]?.timeLabel ? `数据截至 ${newsItems[0].timeLabel}` : "数据截至：暂无";

  return {
    newsItems,
    newsMessage: newsItems.length > 0 ? null : input.emptyMessage,
    newsStale,
    newsFreshnessLabel,
    newsSourceLabel: input.sourceLabel,
    newsAsOfLabel,
    newsStatusLabel:
      newsItems.length > 0 ? (newsStale ? input.statusWhenStale : input.statusWhenFresh) : input.statusWhenEmpty,
    newsRefreshLabel: MACRO_NEWS_REFRESH_LABEL,
  };
}

export function shouldUseMacroNewsFallback(choiceNews: MacroNewsItemsResult): boolean {
  if (choiceNews.newsItems.length === 0) {
    return true;
  }
  return choiceNews.newsStale;
}

export function resolveHomeMacroNewsBriefing(input: {
  choiceEvents?: readonly ChoiceNewsEvent[] | null;
  fallbackEvents?: readonly ChoiceNewsEvent[] | null;
  todayIsoDate: string;
  isLoading: boolean;
  isError: boolean;
}): MacroNewsItemsResult {
  if (input.isError) {
    return {
      newsItems: [],
      newsMessage: "宏观新闻加载失败，请稍后刷新。",
      newsStale: false,
      newsFreshnessLabel: "新闻源异常",
      newsSourceLabel: MACRO_NEWS_CHOICE_SOURCE_LABEL,
      newsAsOfLabel: "数据截至：不可用",
      newsStatusLabel: "来源状态：异常",
      newsRefreshLabel: MACRO_NEWS_REFRESH_LABEL,
    };
  }
  if (input.isLoading && !input.choiceEvents?.length && !input.fallbackEvents?.length) {
    return {
      newsItems: [],
      newsMessage: "正在加载国内外宏观新闻…",
      newsStale: false,
      newsFreshnessLabel: "加载中",
      newsSourceLabel: MACRO_NEWS_CHOICE_SOURCE_LABEL,
      newsAsOfLabel: "数据截至：加载中",
      newsStatusLabel: "来源状态：加载中",
      newsRefreshLabel: MACRO_NEWS_REFRESH_LABEL,
    };
  }

  const choiceNews = buildNewsItemsFromEvents({
    events: input.choiceEvents,
    todayIsoDate: input.todayIsoDate,
    topicLabel: dashboardMacroNewsTopicLabel,
    sourceLabel: MACRO_NEWS_CHOICE_SOURCE_LABEL,
    emptyMessage: "暂无可展示的宏观新闻。",
    statusWhenFresh: "来源状态：正常",
    statusWhenStale: "来源状态：偏旧",
    statusWhenEmpty: "来源状态：暂无数据",
  });

  if (!shouldUseMacroNewsFallback(choiceNews)) {
    return choiceNews;
  }

  const fallbackNews = buildNewsItemsFromEvents({
    events: input.fallbackEvents,
    todayIsoDate: input.todayIsoDate,
    topicLabel: dashboardMacroNewsFallbackTopicLabel,
    sourceLabel: MACRO_NEWS_FALLBACK_SOURCE_LABEL,
    emptyMessage: "暂无可展示的宏观新闻。",
    statusWhenFresh: "来源状态：Tushare 兜底",
    statusWhenStale: "来源状态：偏旧",
    statusWhenEmpty: "来源状态：暂无数据",
    requireMacroRelevance: true,
  });

  if (fallbackNews.newsItems.length > 0) {
    return fallbackNews;
  }

  return choiceNews;
}

function buildSupplyItems(calendar: HomeResearchCalendarModel): HomeMacroSupplyItem[] {
  if (calendar.status === "loading") {
    return [{ id: "supply-loading", label: "供给/招标：加载中" }];
  }
  if (calendar.status === "error") {
    return [{ id: "supply-error", label: "供给/招标：加载失败" }];
  }
  if (calendar.items.length === 0) {
    return [{ id: "supply-empty", label: "供给/招标：当前窗口无事件" }];
  }
  return calendar.items.slice(0, 2).map((item) => ({
    id: item.id,
    label: `供给/招标：${dateLabel(item.date)} ${item.title}${item.amountLabel !== "—" ? ` · ${item.amountLabel}` : ""}`,
  }));
}

export function buildHomeMacroBriefingModel(input: {
  todayIsoDate: string;
  newsEvents?: readonly ChoiceNewsEvent[] | null;
  fallbackNewsEvents?: readonly ChoiceNewsEvent[] | null;
  newsLoading: boolean;
  newsError: boolean;
  supplyCalendar: HomeResearchCalendarModel;
}): HomeMacroBriefingModel {
  const releaseItems = buildReleaseItems(input.todayIsoDate);
  const news = resolveHomeMacroNewsBriefing({
    choiceEvents: input.newsEvents,
    fallbackEvents: input.fallbackNewsEvents,
    todayIsoDate: input.todayIsoDate,
    isLoading: input.newsLoading,
    isError: input.newsError,
  });

  return {
    releaseItems,
    releaseWindowLabel:
      releaseItems.length > 0 ? `未来 ${RELEASE_WINDOW_DAYS} 天 · ${releaseItems.length} 项` : `未来 ${RELEASE_WINDOW_DAYS} 天`,
    releaseMessage: releaseItems.length > 0 ? null : "暂无已维护发布日期，请补充配置清单。",
    ...news,
    supplyItems: buildSupplyItems(input.supplyCalendar),
  };
}
