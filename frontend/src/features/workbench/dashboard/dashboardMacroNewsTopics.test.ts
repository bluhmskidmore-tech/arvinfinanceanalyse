import { describe, expect, it } from "vitest";

import {
  DASHBOARD_MACRO_NEWS_FALLBACK_SCAN_LIMIT,
  DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS,
  DASHBOARD_MACRO_NEWS_TOPIC_LIMIT,
} from "./dashboardMacroNewsTopics";

describe("dashboard macro news topics", () => {
  it("scans a wider Tushare market-news window before policy funding filtering", () => {
    const marketNewsFallback = DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.find(
      (topic) => topic.code === "tushare.news.sina",
    );

    expect(DASHBOARD_MACRO_NEWS_FALLBACK_SCAN_LIMIT).toBeGreaterThan(DASHBOARD_MACRO_NEWS_TOPIC_LIMIT);
    expect(marketNewsFallback?.queryLimit).toBe(DASHBOARD_MACRO_NEWS_FALLBACK_SCAN_LIMIT);
  });
});
