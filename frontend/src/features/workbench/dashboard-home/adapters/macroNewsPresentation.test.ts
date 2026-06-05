import { describe, expect, it } from "vitest";

import type { ChoiceNewsEvent } from "../../../../api/contracts";
import {
  isDisplayableMacroNewsText,
  isMacroRelevantForHomeBriefing,
  isPolicyFundingRelevantForHomeBriefing,
  shouldIncludeMacroNewsEvent,
  stripHtmlTags,
  summarizeMacroNewsEvent,
} from "./macroNewsPresentation";

function event(partial: Partial<ChoiceNewsEvent> & Pick<ChoiceNewsEvent, "event_key" | "received_at" | "topic_code">): ChoiceNewsEvent {
  return {
    group_id: "tushare_major",
    content_type: "major_news",
    serial_id: 0,
    request_id: 0,
    error_code: 0,
    error_msg: "",
    item_index: 0,
    payload_text: "",
    payload_json: null,
    ...partial,
  };
}

describe("macroNewsPresentation", () => {
  it("strips raw html tags from tushare major news payloads", () => {
    const title = summarizeMacroNewsEvent(
      event({
        event_key: "html-1",
        received_at: "2026-06-01T06:44:00+00:00",
        topic_code: "tushare.major_news",
        payload_text:
          '女子的猫咪病重ICU离世，宠物医院强签免责协议，暴露医疗乱象 — <div class="main-text atc-content"><div id="contentApp"><p/>',
        payload_json: JSON.stringify({ title: "女子的猫咪病重ICU离世，宠物医院强签免责协议，暴露医疗乱象" }),
      }),
    );

    expect(title).toBe("女子的猫咪病重ICU离世，宠物医院强签免责协议，暴露医疗乱象");
    expect(title).not.toContain("<div");
  });

  it("filters out non-macro tushare fallback items", () => {
    expect(
      shouldIncludeMacroNewsEvent(
        event({
          event_key: "pet-1",
          received_at: "2026-06-01T06:44:00+00:00",
          topic_code: "tushare.major_news",
          payload_text: "女子的猫咪病重ICU离世，宠物医院强签免责协议，暴露医疗乱象",
          payload_json: JSON.stringify({ title: "女子的猫咪病重ICU离世，宠物医院强签免责协议，暴露医疗乱象" }),
        }),
        { requireMacroRelevance: true },
      ),
    ).toBe(false);
  });

  it("keeps macro-relevant tushare fallback items", () => {
    expect(isMacroRelevantForHomeBriefing("央行今日开展 500 亿元 7 天期逆回购操作")).toBe(true);
    expect(isMacroRelevantForHomeBriefing("gdp nowcast revised higher after pmi surprise")).toBe(true);
    expect(
      shouldIncludeMacroNewsEvent(
        event({
          event_key: "macro-1",
          received_at: "2026-06-01T08:19:56+00:00",
          topic_code: "tushare.news.sina",
          payload_text: "标普500股指期货上涨0.3%",
        }),
        { requireMacroRelevance: true },
      ),
    ).toBe(true);
  });

  it("removes leading separators from tushare market flash titles", () => {
    const title = summarizeMacroNewsEvent(
      event({
        event_key: "market-flash-1",
        received_at: "2026-06-01T08:19:56+00:00",
        topic_code: "tushare.news.sina",
        payload_text: " — 【高盛上调2026年底铜价预测】高盛周一将铜价预测上调",
      }),
    );

    expect(title).toBe("【高盛上调2026年底铜价预测】高盛周一将铜价预测上调");
  });

  it("keeps only policy and funding news when requested", () => {
    expect(isPolicyFundingRelevantForHomeBriefing("央行公开市场净投放保持平稳")).toBe(true);
    expect(isPolicyFundingRelevantForHomeBriefing("财政政策继续发力支持稳增长")).toBe(true);
    expect(isPolicyFundingRelevantForHomeBriefing("银行间市场流动性保持充裕")).toBe(true);
    expect(isPolicyFundingRelevantForHomeBriefing("10年期美国国债收益率最新上涨2.8个基点")).toBe(true);
    expect(isPolicyFundingRelevantForHomeBriefing("日本10年期国债收益率上涨2个基点")).toBe(true);
    expect(isPolicyFundingRelevantForHomeBriefing("国际油价直线拉升")).toBe(false);
    expect(isPolicyFundingRelevantForHomeBriefing("西部数据股东拟置换高级可转换债券")).toBe(false);
    expect(isPolicyFundingRelevantForHomeBriefing("公司无限售流通股占总股本18.79%，流动性不足")).toBe(false);
    expect(isPolicyFundingRelevantForHomeBriefing("采购工作受财政、法律、技术因素影响进展缓慢")).toBe(false);
    expect(
      isPolicyFundingRelevantForHomeBriefing("A股策略称资金面受ETF持续净流出影响，板块短期扰动"),
    ).toBe(false);
    expect(
      shouldIncludeMacroNewsEvent(
        event({
          event_key: "stock-1",
          received_at: "2026-06-01T08:19:56+00:00",
          topic_code: "S888005004API",
          payload_text: "标普500股指期货上涨0.3%",
        }),
        { requireMacroRelevance: false, requirePolicyFundingRelevance: true },
      ),
    ).toBe(false);
  });

  it("rejects text that still contains html markup", () => {
    expect(isDisplayableMacroNewsText(stripHtmlTags('<div class="main-text">央行今日开展逆回购</div>'))).toBe(true);
    expect(isDisplayableMacroNewsText('<div class="main-text">央行今日开展逆回购</div>')).toBe(false);
  });
});
