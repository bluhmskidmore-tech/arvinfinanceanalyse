export const DASHBOARD_MACRO_NEWS_TOPIC_LIMIT = 6;

export const DASHBOARD_MACRO_NEWS_TOPICS = [
  { code: "S888010007API", label: "经济数据" },
  { code: "S888010003API", label: "宏观经济" },
  { code: "S888010005API", label: "国内经济" },
  { code: "S888005004API", label: "国际资讯" },
  { code: "C000003006", label: "政策跟踪" },
  { code: "C000003002", label: "央行动态" },
] as const;

const DASHBOARD_MACRO_NEWS_TOPIC_LABELS: ReadonlyMap<string, string> = new Map(
  DASHBOARD_MACRO_NEWS_TOPICS.map((topic) => [topic.code, topic.label] as const),
);

export function dashboardMacroNewsTopicLabel(topicCode: string): string {
  return DASHBOARD_MACRO_NEWS_TOPIC_LABELS.get(topicCode) ?? topicCode;
}
