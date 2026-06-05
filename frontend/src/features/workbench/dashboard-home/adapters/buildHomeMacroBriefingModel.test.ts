import { describe, expect, it } from "vitest";

import type { ChoiceNewsEvent } from "../../../../api/contracts";
import {
  buildPolicyFundingSummary,
  resolveHomeMacroNewsBriefing,
  shouldUseMacroNewsFallback,
} from "./buildHomeMacroBriefingModel";

function choiceEvent(partial: Partial<ChoiceNewsEvent> & Pick<ChoiceNewsEvent, "event_key" | "received_at" | "topic_code" | "payload_text">): ChoiceNewsEvent {
  return {
    group_id: "news_cmd1",
    content_type: "sectornews",
    serial_id: 1,
    request_id: 1,
    error_code: 0,
    error_msg: "",
    item_index: 0,
    payload_json: null,
    ...partial,
  };
}

describe("shouldUseMacroNewsFallback", () => {
  it("returns true when choice news is stale", () => {
    expect(
      shouldUseMacroNewsFallback({
        newsItems: [{ id: "1", timeLabel: "04-21 15:06", topicLabel: "国际资讯", title: "test", freshnessLabel: "x" }],
        newsMessage: null,
        newsStale: true,
        newsFreshnessLabel: "x",
        newsSourceLabel: "x",
        newsAsOfLabel: "x",
        newsStatusLabel: "x",
        newsRefreshLabel: "x",
      }),
    ).toBe(true);
  });

  it("returns false when choice news is fresh", () => {
    expect(
      shouldUseMacroNewsFallback({
        newsItems: [{ id: "1", timeLabel: "05-31 09:00", topicLabel: "国际资讯", title: "test", freshnessLabel: "x" }],
        newsMessage: null,
        newsStale: false,
        newsFreshnessLabel: "x",
        newsSourceLabel: "x",
        newsAsOfLabel: "x",
        newsStatusLabel: "x",
        newsRefreshLabel: "x",
      }),
    ).toBe(false);
  });
});

describe("resolveHomeMacroNewsBriefing", () => {
  it("surfaces Choice permission errors from landed events without treating the query as failed", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-01",
      isLoading: false,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-permission-error",
          received_at: "2026-06-01T00:24:35.004899+00:00",
          topic_code: "S888010007API",
          error_code: 10001012,
          error_msg: "insufficient user access",
          payload_text: null,
        }),
      ],
      fallbackEvents: [],
    });

    expect(result.newsItems).toHaveLength(0);
    expect(result.newsMessage).toBe("Choice 新闻权限不足，请恢复数据源权限后重新采集。");
    expect(result.newsFreshnessLabel).toBe("Choice 新闻权限不足");
    expect(result.newsStatusLabel).toBe("来源状态：Choice 权限不足");
    expect(result.newsAsOfLabel).toBe("数据截至 06-01 00:24");
    expect(result.newsRefreshLabel).toBe("刷新：随页面查询读取已落库数据");
  });

  it("surfaces non-permission Choice source errors from landed events", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-01",
      isLoading: false,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-source-error",
          received_at: "2026-06-01T00:24:35.004899+00:00",
          topic_code: "S888010007API",
          error_code: 10003013,
          error_msg: "vendor timeout",
          payload_text: null,
        }),
      ],
      fallbackEvents: [],
    });

    expect(result.newsItems).toHaveLength(0);
    expect(result.newsMessage).toBe("Choice 新闻源返回错误：vendor timeout。");
    expect(result.newsFreshnessLabel).toBe("新闻源返回错误");
    expect(result.newsStatusLabel).toBe("来源状态：新闻源错误");
    expect(result.newsAsOfLabel).toBe("数据截至 06-01 00:24");
  });

  it("uses Tushare fallback when Choice macro news is stale", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-01",
      isLoading: false,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-1",
          received_at: "2026-04-21T15:06:30+08:00",
          topic_code: "S888005004API",
          payload_text: "旧 Choice 国际资讯",
        }),
      ],
      fallbackEvents: [
        choiceEvent({
          event_key: "tushare-1",
          received_at: "2026-06-01T08:19:56+00:00",
          topic_code: "tushare.news.sina",
          payload_text: "央行开展逆回购操作，市场快讯更新",
          group_id: "tushare_news",
        }),
      ],
    });

    expect(result.newsItems).toHaveLength(1);
    expect(result.newsItems[0]?.title).toBe("央行开展逆回购操作，市场快讯更新");
    expect(result.newsItems[0]?.topicLabel).toBe("市场快讯");
    expect(result.newsSourceLabel).toContain("Tushare");
    expect(result.newsStatusLabel).toBe("来源状态：Tushare 兜底");
    expect(result.newsStale).toBe(false);
    expect(result.newsAsOfLabel).toBe("数据截至 06-01 08:19");
    expect(result.newsRefreshLabel).toBe("刷新：随页面查询读取已落库数据");
  });

  it("waits for Tushare fallback before surfacing a landed Choice permission error", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-01",
      isLoading: true,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-permission-error",
          received_at: "2026-06-01T00:24:35.004899+00:00",
          topic_code: "S888010007API",
          error_code: 10001012,
          error_msg: "insufficient user access",
          payload_text: null,
        }),
      ],
      fallbackEvents: [],
    });

    expect(result.newsItems).toHaveLength(0);
    expect(result.newsMessage).toBe("正在加载政策与资金面…");
    expect(result.newsSourceLabel).toBe("来源：Tushare 宏观快讯（Choice 不可用或偏旧兜底）");
    expect(result.newsStatusLabel).toBe("来源状态：加载中");
  });

  it("uses relaxed Tushare macro fallback when Choice has a permission error and no strict funding news is available", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-01",
      isLoading: false,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-permission-error",
          received_at: "2026-06-01T00:24:35.004899+00:00",
          topic_code: "S888010007API",
          error_code: 10001012,
          error_msg: "insufficient user access",
          payload_text: null,
        }),
      ],
      fallbackEvents: [
        choiceEvent({
          event_key: "unrelated-story",
          received_at: "2026-06-01T09:30:00+00:00",
          topic_code: "tushare.major_news",
          payload_text: "影视公司发布暑期片单，票房预期升温",
          group_id: "tushare_major",
        }),
        choiceEvent({
          event_key: "macro-story",
          received_at: "2026-06-01T08:19:56+00:00",
          topic_code: "tushare.news.sina",
          payload_text: "国家统计局公布 PMI 延续扩张，经济数据改善",
          group_id: "tushare_news",
        }),
      ],
    });

    expect(result.newsItems).toHaveLength(1);
    expect(result.newsItems[0]?.title).toBe("国家统计局公布 PMI 延续扩张，经济数据改善");
    expect(result.newsItems[0]?.topicLabel).toBe("市场快讯");
    expect(result.newsMessage).toBeNull();
    expect(result.newsSourceLabel).toBe("来源：Tushare 宏观快讯（Choice 不可用时非严格资金面兜底）");
    expect(result.newsStatusLabel).toBe("来源状态：Tushare 宏观兜底（非严格资金面）");
    expect(result.newsAsOfLabel).toBe("数据截至 06-01 08:19");
  });

  it("keeps HTTP query failures separate from landed source errors", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-01",
      isLoading: false,
      isError: true,
      choiceEvents: [],
      fallbackEvents: [],
    });

    expect(result.newsItems).toHaveLength(0);
    expect(result.newsMessage).toBe("政策与资金面加载失败，请稍后刷新。");
    expect(result.newsFreshnessLabel).toBe("新闻源异常");
    expect(result.newsStatusLabel).toBe("来源状态：异常");
  });

  it("drops non-policy tushare fallback items such as pet hospital stories", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-01",
      isLoading: false,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-1",
          received_at: "2026-04-21T15:06:30+08:00",
          topic_code: "S888005004API",
          payload_text: "旧 Choice 国际资讯",
        }),
      ],
      fallbackEvents: [
        choiceEvent({
          event_key: "pet-story",
          received_at: "2026-06-01T06:44:00+00:00",
          topic_code: "tushare.major_news",
          payload_text:
            '女子的猫咪病重ICU离世，宠物医院强签免责协议，暴露医疗乱象 — <div class="main-text atc-content">',
          group_id: "tushare_major",
        }),
        choiceEvent({
          event_key: "macro-story",
          received_at: "2026-06-01T08:19:56+00:00",
          topic_code: "tushare.news.sina",
          payload_text: "央行开展 MLF 续作，资金面平稳",
          group_id: "tushare_news",
        }),
      ],
    });

    expect(result.newsItems).toHaveLength(1);
    expect(result.newsItems[0]?.title).toBe("央行开展 MLF 续作，资金面平稳");
  });

  it("keeps fresh Choice news when it is within the stale window", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-05-31",
      isLoading: false,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-1",
          received_at: "2026-05-30T09:00:00+08:00",
          topic_code: "S888005004API",
          payload_text: "央行公开市场净投放保持平稳",
        }),
      ],
      fallbackEvents: [
        choiceEvent({
          event_key: "tushare-1",
          received_at: "2026-06-01T08:19:56+00:00",
          topic_code: "tushare.news.sina",
          payload_text: "Tushare 不应覆盖",
          group_id: "tushare_news",
        }),
      ],
    });

    expect(result.newsItems[0]?.title).toBe("央行公开市场净投放保持平稳");
    expect(result.newsSourceLabel).toBe("来源：Choice 宏观新闻");
    expect(result.newsStatusLabel).toBe("来源状态：正常");
  });

  it("uses a readable topic label when Choice topic code is blank", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-01",
      isLoading: false,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-blank-topic",
          received_at: "2026-06-01T09:00:00+08:00",
          topic_code: "—",
          payload_text: "公开市场操作延续净投放",
        }),
      ],
      fallbackEvents: [],
    });

    expect(result.newsItems[0]?.topicLabel).toBe("宏观新闻");
  });

  it("uses a readable time label when Choice timestamp is blank", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-01",
      isLoading: false,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-blank-time",
          received_at: "—",
          topic_code: "S888005004API",
          payload_text: "公开市场操作延续净投放",
        }),
      ],
      fallbackEvents: [],
    });

    expect(result.newsItems[0]?.timeLabel).toBe("时间待核");
    expect(result.newsAsOfLabel).toBe("数据截至 时间待核");
  });
});

describe("buildPolicyFundingSummary", () => {
  it("summarizes fallback news into source chips and scan groups", () => {
    const result = buildPolicyFundingSummary({
      newsItems: [
        {
          id: "repo",
          timeLabel: "06-03 20:01",
          topicLabel: "市场快讯",
          title: "本周中国央行公开市场将有9089亿元逆回购到期",
          freshnessLabel: "最近更新 06-03 20:01",
        },
        {
          id: "us10y",
          timeLabel: "06-03 20:17",
          topicLabel: "市场快讯",
          title: "10年期美国国债收益率最新上涨2.8个基点，报4.483%。",
          freshnessLabel: "最近更新 06-03 20:17",
        },
      ],
      newsMessage: null,
      newsStale: false,
      newsFreshnessLabel: "最近更新 06-03 20:17",
      newsSourceLabel: "来源：Tushare 宏观快讯（Choice 不可用或偏旧兜底）",
      newsAsOfLabel: "数据截至 06-03 20:17",
      newsStatusLabel: "来源状态：Tushare 兜底",
      newsRefreshLabel: "刷新：随页面查询读取已落库数据",
    });

    expect(result.headline).toBe("2 条政策与资金面快讯，重点集中在央行/公开市场、利率/债券。");
    expect(result.chips.map((chip) => chip.label)).toEqual(["Tushare 兜底", "数据截至 06-03 20:17", "最近更新 06-03 20:17"]);
    expect(result.groups.map((group) => group.label)).toEqual(["央行/公开市场", "利率/债券"]);
    expect(result.groups[0]?.items[0]?.id).toBe("repo");
    expect(result.groups[1]?.items[0]?.id).toBe("us10y");
  });

  it("keeps stale and empty states explicit without implying a market conclusion", () => {
    const stale = buildPolicyFundingSummary({
      newsItems: [],
      newsMessage: "政策与资金面：暂无债券相关更新",
      newsStale: true,
      newsFreshnessLabel: "暂无更新",
      newsSourceLabel: "来源：Choice 宏观新闻",
      newsAsOfLabel: "数据截至：暂无",
      newsStatusLabel: "来源状态：偏旧",
      newsRefreshLabel: "刷新：随页面查询读取已落库数据",
    });

    expect(stale.headline).toBe("暂无可展示的政策与资金面快讯。");
    expect(stale.groups).toHaveLength(0);
    expect(stale.chips.map((chip) => chip.label)).toContain("新闻源偏旧");
    expect(stale.chips.map((chip) => chip.label)).toContain("暂无更新");
  });
});
