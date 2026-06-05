export const DASHBOARD_MACRO_NEWS_TOPIC_LIMIT = 6;

export const DASHBOARD_MACRO_NEWS_TOPICS = [
  { code: "S888010007API", label: "经济数据" },
  { code: "S888010003API", label: "宏观经济" },
  { code: "S888010005API", label: "国内经济" },
  { code: "S888005004API", label: "国际资讯" },
  { code: "C000003006", label: "政策跟踪" },
  { code: "C000003002", label: "央行动态" },
] as const;

/** Tushare streams landed in `choice_news_event` when Choice sectornews is unavailable. */
export const DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS = [
  { code: "tushare.major_news", label: "重大新闻" },
  { code: "tushare.news.sina", label: "市场快讯" },
  { code: "tushare.npr", label: "政策要闻" },
] as const;

const DASHBOARD_MACRO_NEWS_TOPIC_LABELS: ReadonlyMap<string, string> = new Map(
  DASHBOARD_MACRO_NEWS_TOPICS.map((topic) => [topic.code, topic.label] as const),
);

const DASHBOARD_MACRO_NEWS_FALLBACK_TOPIC_LABELS: ReadonlyMap<string, string> = new Map(
  DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => [topic.code, topic.label] as const),
);

export function dashboardMacroNewsTopicLabel(topicCode: string): string {
  const normalized = topicCode.trim();
  if (!normalized || normalized === "—") {
    return "宏观新闻";
  }
  return DASHBOARD_MACRO_NEWS_TOPIC_LABELS.get(normalized) ?? "宏观新闻";
}

export function dashboardMacroNewsFallbackTopicLabel(topicCode: string): string {
  const normalized = topicCode.trim();
  if (!normalized || normalized === "—") {
    return "市场新闻";
  }
  return DASHBOARD_MACRO_NEWS_FALLBACK_TOPIC_LABELS.get(normalized) ?? "市场新闻";
}
