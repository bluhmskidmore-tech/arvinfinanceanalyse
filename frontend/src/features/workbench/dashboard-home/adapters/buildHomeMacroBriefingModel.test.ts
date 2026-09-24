import { describe, expect, it } from "vitest";

import type { ChoiceNewsEvent } from "../../../../api/contracts";
import {
  buildHomeMacroBriefingModel,
  buildPolicyFundingSummary,
  resolveHomeMacroNewsBriefing,
  shouldRequestHomeMacroNewsFallback,
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

  it("provides narrative guidance for loading and query errors", () => {
    const loading = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-01",
      isLoading: true,
      isError: false,
      choiceEvents: [],
      fallbackEvents: [],
    });
    const queryError = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-01",
      isLoading: false,
      isError: true,
      choiceEvents: [],
      fallbackEvents: [],
    });

    expect(loading.policyFundingDiagnostics?.sourceVerdict).toBe("正在等待政策与资金面数据源返回。");
    expect(loading.policyFundingDiagnostics?.filterNarrative).toBeNull();
    expect(loading.policyFundingDiagnostics?.actionHint).toBe("等待数据源返回后再判断；无需手工改数。");
    expect(loading.policyFundingDiagnostics?.narrativeTone).toBe("info");
    expect(queryError.policyFundingDiagnostics?.sourceVerdict).toBe(
      "政策与资金面查询异常，当前无法确认源状态。",
    );
    expect(queryError.policyFundingDiagnostics?.actionHint).toBe("刷新或检查新闻查询服务后再使用本块判断。");
    expect(queryError.policyFundingDiagnostics?.narrativeTone).toBe("danger");
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

  it("keeps fresh Choice news when raw html has a clean json title", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-04",
      isLoading: false,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-html-json-title",
          received_at: "2026-06-04T09:00:00+08:00",
          topic_code: "S888005004API",
          payload_text: '<div class="main-text">央行开展逆回购操作，资金面平稳</div>',
          payload_json: JSON.stringify({ title: "央行开展逆回购操作，资金面平稳" }),
        }),
      ],
      fallbackEvents: [
        choiceEvent({
          event_key: "tushare-should-not-cover",
          received_at: "2026-06-04T09:01:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "Tushare 不应覆盖",
          group_id: "tushare_news",
        }),
      ],
    });

    const summary = buildPolicyFundingSummary(result);

    expect(result.newsItems).toHaveLength(1);
    expect(result.newsItems[0]?.title).toBe("央行开展逆回购操作，资金面平稳");
    expect(result.newsSourceLabel).toBe("来源：Choice 宏观新闻");
    expect(result.newsStatusLabel).toBe("来源状态：正常");
    expect(shouldRequestHomeMacroNewsFallback({
      choiceEvents: [
        choiceEvent({
          event_key: "choice-html-json-title",
          received_at: "2026-06-04T09:00:00+08:00",
          topic_code: "S888005004API",
          payload_text: '<div class="main-text">央行开展逆回购操作，资金面平稳</div>',
          payload_json: JSON.stringify({ title: "央行开展逆回购操作，资金面平稳" }),
        }),
      ],
      todayIsoDate: "2026-06-04",
    })).toBe(false);
    expect(summary.diagnostics?.metrics).toEqual([
      { id: "raw", label: "原始", value: "1 条", tone: "neutral" },
      { id: "eligible", label: "入选", value: "1 条", tone: "info" },
      { id: "unique", label: "去重后", value: "1 条", tone: "info" },
      { id: "displayed", label: "展示", value: "1 条", tone: "info" },
    ]);
    expect(summary.diagnostics?.reasons.map((reason) => reason.label)).not.toContain("正文不可展示");
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

  it("explains source inventory, filtering, dedupe, and display limits for fallback news", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-04",
      isLoading: false,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-stale",
          received_at: "2026-04-21T15:06:30+08:00",
          topic_code: "S888005004API",
          payload_text: "旧 Choice 国际资讯",
        }),
      ],
      fallbackEvents: [
        choiceEvent({
          event_key: "repo",
          received_at: "2026-06-03T20:17:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "本周中国央行公开市场将有9089亿元逆回购到期",
          group_id: "tushare_news",
        }),
        choiceEvent({
          event_key: "us10y",
          received_at: "2026-06-03T20:16:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "10年期美国国债收益率最新上涨2.8个基点，报4.483%。",
          group_id: "tushare_news",
        }),
        choiceEvent({
          event_key: "dr007",
          received_at: "2026-06-03T20:15:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "DR007 小幅下行，银行间资金面保持平稳",
          group_id: "tushare_news",
        }),
        choiceEvent({
          event_key: "mlf",
          received_at: "2026-06-03T20:14:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "央行开展 MLF 续作，货币政策保持稳健",
          group_id: "tushare_news",
        }),
        choiceEvent({
          event_key: "local-bond",
          received_at: "2026-06-03T20:13:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "地方债发行提速，债券市场关注供给压力",
          group_id: "tushare_news",
        }),
        choiceEvent({
          event_key: "shibor",
          received_at: "2026-06-03T20:12:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "Shibor 多数下行，货币市场流动性宽松",
          group_id: "tushare_news",
        }),
        choiceEvent({
          event_key: "cdb",
          received_at: "2026-06-03T20:11:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "政金债收益率窄幅波动，长端利率维持震荡",
          group_id: "tushare_news",
        }),
        choiceEvent({
          event_key: "repo-duplicate",
          received_at: "2026-06-03T20:10:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "本周中国央行公开市场将有9089亿元逆回购到期",
          group_id: "tushare_news",
        }),
        choiceEvent({
          event_key: "pet-story",
          received_at: "2026-06-03T20:09:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "宠物医院发布暑期服务活动",
          group_id: "tushare_news",
        }),
      ],
    });

    const summary = buildPolicyFundingSummary(result);

    expect(result.newsItems).toHaveLength(6);
    expect(summary.diagnostics?.summary).toBe(
      "当前源 Tushare 兜底：原始 9 条，入选 8 条，去重后 7 条，展示 6 条。",
    );
    expect(summary.diagnostics?.metrics).toEqual([
      { id: "raw", label: "原始", value: "9 条", tone: "neutral" },
      { id: "eligible", label: "入选", value: "8 条", tone: "info" },
      { id: "unique", label: "去重后", value: "7 条", tone: "info" },
      { id: "displayed", label: "展示", value: "6 条", tone: "info" },
    ]);
    expect(summary.diagnostics?.reasons.map((reason) => reason.label)).toEqual([
      "非政策/资金面",
      "重复标题",
      "超过展示上限",
    ]);
    expect(summary.diagnostics?.sourceVerdict).toBe(
      "当前使用 Tushare 兜底：Choice 快讯偏旧，已切换到兜底源。",
    );
    expect(summary.diagnostics?.filterNarrative).toBe(
      "已展示 6 条；另有 3 条因非政策/资金面、重复标题、超过展示上限未展示。",
    );
    expect(summary.diagnostics?.actionHint).toBeNull();
    expect(summary.diagnostics?.narrativeTone).toBe("info");
  });

  it("explains why only one policy funding item survives filtering", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-04",
      isLoading: false,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-stale",
          received_at: "2026-04-21T15:06:30+08:00",
          topic_code: "S888005004API",
          payload_text: "旧 Choice 国际资讯",
        }),
      ],
      fallbackEvents: [
        choiceEvent({
          event_key: "repo",
          received_at: "2026-06-03T20:17:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "央行公开市场逆回购到期，资金面维持平稳",
          group_id: "tushare_news",
        }),
        choiceEvent({
          event_key: "source-error",
          received_at: "2026-06-03T20:16:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: null,
          error_code: 10003013,
          error_msg: "vendor timeout",
          group_id: "tushare_news",
        }),
        choiceEvent({
          event_key: "html-story",
          received_at: "2026-06-03T20:15:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: '<div class="main-text">央行开展逆回购操作</div>',
          group_id: "tushare_news",
        }),
        choiceEvent({
          event_key: "pet-story",
          received_at: "2026-06-03T20:14:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "宠物医院发布暑期服务活动",
          group_id: "tushare_news",
        }),
      ],
    });

    const summary = buildPolicyFundingSummary(result);

    expect(result.newsItems).toHaveLength(1);
    expect(summary.diagnostics?.summary).toBe(
      "当前源 Tushare 兜底：原始 4 条，入选 1 条，去重后 1 条，展示 1 条。",
    );
    expect(summary.diagnostics?.emptyHint).toBe(
      "仅 1 条通过筛选；其余 3 条因源错误/权限、正文不可展示、非政策/资金面未展示。",
    );
    expect(summary.diagnostics?.reasons.map((reason) => reason.label)).toEqual([
      "源错误/权限",
      "正文不可展示",
      "非政策/资金面",
    ]);
    expect(summary.diagnostics?.sourceVerdict).toBe(
      "当前使用 Tushare 兜底：Choice 快讯偏旧，已切换到兜底源。",
    );
    expect(summary.diagnostics?.filterNarrative).toBe(
      "仅 1 条通过筛选；其余 3 条主要因源错误/权限、正文不可展示、非政策/资金面未展示。",
    );
    expect(summary.diagnostics?.actionHint).toBe("只剩 1 条可展示快讯，请复核兜底源原始明细与过滤规则。");
    expect(summary.diagnostics?.narrativeTone).toBe("warning");
  });

  it("explains when raw policy funding rows are all filtered out", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-04",
      isLoading: false,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-unrelated-1",
          received_at: "2026-06-04T09:01:00+08:00",
          topic_code: "S888005004API",
          payload_text: "影视公司发布暑期片单，票房预期升温",
        }),
        choiceEvent({
          event_key: "choice-unrelated-2",
          received_at: "2026-06-04T09:00:00+08:00",
          topic_code: "S888005004API",
          payload_text: "体育用品公司发布新品活动",
        }),
      ],
      fallbackEvents: [],
    });

    const summary = buildPolicyFundingSummary(result);

    expect(result.newsItems).toHaveLength(0);
    expect(summary.diagnostics?.sourceVerdict).toBe(
      "当前使用 Choice 宏观新闻，但未形成政策/资金面展示项。",
    );
    expect(summary.diagnostics?.filterNarrative).toBe(
      "0 条通过筛选；原始 2 条全部因非政策/资金面未展示。",
    );
    expect(summary.diagnostics?.actionHint).toBe(
      "请复核过滤关键词与原始明细，确认是否需要补采或放宽资金面规则。",
    );
    expect(summary.diagnostics?.narrativeTone).toBe("warning");
  });

  it("keeps html-only payloads counted as undisplayable when no clean json title exists", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-04",
      isLoading: false,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-stale",
          received_at: "2026-04-21T15:06:30+08:00",
          topic_code: "S888005004API",
          payload_text: "旧 Choice 国际资讯",
        }),
      ],
      fallbackEvents: [
        choiceEvent({
          event_key: "valid-fallback",
          received_at: "2026-06-03T20:16:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "央行公开市场逆回购到期，资金面维持平稳",
          group_id: "tushare_news",
        }),
        choiceEvent({
          event_key: "html-only-fallback",
          received_at: "2026-06-03T20:15:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: '<div class="main-text">央行开展逆回购操作，资金面平稳</div>',
          payload_json: JSON.stringify({ content: "央行开展逆回购操作，资金面平稳" }),
          group_id: "tushare_news",
        }),
      ],
    });

    const summary = buildPolicyFundingSummary(result);

    expect(result.newsItems).toHaveLength(1);
    expect(result.newsItems[0]?.title).toBe("央行公开市场逆回购到期，资金面维持平稳");
    expect(summary.diagnostics?.metrics).toEqual([
      { id: "raw", label: "原始", value: "2 条", tone: "neutral" },
      { id: "eligible", label: "入选", value: "1 条", tone: "info" },
      { id: "unique", label: "去重后", value: "1 条", tone: "info" },
      { id: "displayed", label: "展示", value: "1 条", tone: "info" },
    ]);
    expect(summary.diagnostics?.reasons.map((reason) => reason.label)).toEqual(["正文不可展示"]);
  });

  it("does not label Choice scan count as Tushare raw count while waiting for fallback", () => {
    const result = resolveHomeMacroNewsBriefing({
      todayIsoDate: "2026-06-04",
      isLoading: true,
      isError: false,
      choiceEvents: [
        choiceEvent({
          event_key: "choice-empty-1",
          received_at: "2026-06-04T09:00:00+08:00",
          topic_code: "S888005004API",
          payload_text: "宠物医院发布暑期服务活动",
        }),
        choiceEvent({
          event_key: "choice-empty-2",
          received_at: "2026-06-04T09:01:00+08:00",
          topic_code: "S888005004API",
          payload_text: "国际油价直线拉升",
        }),
      ],
      fallbackEvents: [],
    });

    const summary = buildPolicyFundingSummary(result);

    expect(result.newsItems).toHaveLength(0);
    expect(result.newsSourceLabel).toBe("来源：Tushare 宏观快讯（Choice 不可用或偏旧兜底）");
    expect(summary.diagnostics?.metrics.find((metric) => metric.id === "raw")?.value).toBe("0 条");
    expect(summary.diagnostics?.metrics.find((metric) => metric.id === "displayed")?.value).toBe("0 条");
    expect(summary.diagnostics?.summary).not.toContain("2 条");
    expect(summary.diagnostics?.emptyHint).not.toContain("2 条");
  });

  it("derives diagnostic narrative from structured source state rather than presentation labels", async () => {
    const module = await import("./buildHomeMacroBriefingModel");
    const helper = (module as {
      buildPolicyFundingDiagnosticNarrative?: (input: {
        sourceState: {
          sourceKind: "tushare_fallback";
          fallbackReason: "stale";
          freshness: "fresh";
          scope: "policy_funding";
        };
        rawCount: number;
        eligibleCount: number;
        uniqueCount: number;
        displayedCount: number;
        reasonCounts: readonly { id: "not-policy-funding"; count: number }[];
        presentationLabels?: {
          newsSourceLabel: string;
          newsStatusLabel: string;
          newsAsOfLabel: string;
        };
      }) => {
        sourceVerdict: string;
        filterNarrative: string | null;
        actionHint: string | null;
        narrativeTone: string;
      };
    }).buildPolicyFundingDiagnosticNarrative;

    if (typeof helper !== "function") {
      expect(helper).toBeTypeOf("function");
      return;
    }

    const baseInput = {
      sourceState: {
        sourceKind: "tushare_fallback" as const,
        fallbackReason: "stale" as const,
        freshness: "fresh" as const,
        scope: "policy_funding" as const,
      },
      rawCount: 4,
      eligibleCount: 1,
      uniqueCount: 1,
      displayedCount: 1,
      reasonCounts: [{ id: "not-policy-funding" as const, count: 3 }],
    };
    const baseNarrative = helper(baseInput);
    const relabeledNarrative = helper({
      ...baseInput,
      presentationLabels: {
        newsSourceLabel: "来源：Choice 宏观新闻",
        newsStatusLabel: "来源状态：正常",
        newsAsOfLabel: "数据截至 2099-01-01",
      },
    });

    expect(relabeledNarrative).toEqual(baseNarrative);
    expect(baseNarrative.sourceVerdict).toBe("当前使用 Tushare 兜底：Choice 快讯偏旧，已切换到兜底源。");
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

describe("buildHomeMacroBriefingModel release history", () => {
  it("surfaces maintained history for every visible forward release", () => {
    const result = buildHomeMacroBriefingModel({
      todayIsoDate: "2026-06-28",
      newsEvents: [],
      fallbackNewsEvents: [],
      newsLoading: false,
      newsError: false,
      supplyCalendar: {
        items: [],
        status: "empty",
        windowLabel: "2026-06-28 至 2026-08-12",
        message: null,
      },
    });

    expect(result.releaseItems).toHaveLength(6);
    expect(result.releaseItems.map((item) => item.id)).toEqual([
      "nbs-pmi-2026-06",
      "ism-manufacturing-pmi-2026-07",
      "bls-employment-situation-2026-06",
      "ism-services-pmi-2026-07",
      "nbs-cpi-ppi-2026-06",
      "bls-cpi-2026-06",
    ]);
    expect(result.releaseItems.every((item) => item.history)).toBe(true);
    expect(result.releaseItems[0]?.history).toMatchObject({
      latestValue: "5月 50.0",
      previousValue: "4月 50.3",
      changeValue: "-0.3",
    });
    expect(result.releaseItems[4]?.history).toMatchObject({
      latestValue: "5月 CPI +1.2% / PPI +3.9%",
      previousValue: "4月 CPI +1.2% / PPI +2.8%",
    });
  });

  it("keeps maintained history after its release rows leave the forward window", () => {
    const result = buildHomeMacroBriefingModel({
      todayIsoDate: "2026-07-16",
      newsEvents: [],
      fallbackNewsEvents: [],
      newsLoading: false,
      newsError: false,
      supplyCalendar: {
        items: [],
        status: "empty",
        windowLabel: "2026-07-16 to 2026-08-30",
        message: null,
      },
    });

    expect(result.releaseItems.map((item) => item.id)).toEqual([
      "fomc-2026-07",
      "bea-gdp-advance-2026-q2",
      "nbs-pmi-2026-07",
    ]);
    expect(result.releaseItems.every((item) => !item.history)).toBe(true);
    expect(result.releaseHistoryItems.map((item) => item.id)).toEqual([
      "nbs-pmi-2026-06",
      "ism-manufacturing-pmi-2026-07",
      "bls-employment-situation-2026-06",
      "ism-services-pmi-2026-07",
      "nbs-cpi-ppi-2026-06",
      "bls-cpi-2026-06",
    ]);
  });
});
