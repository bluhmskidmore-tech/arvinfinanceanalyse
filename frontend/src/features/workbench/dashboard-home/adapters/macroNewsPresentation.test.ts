import { describe, expect, it } from "vitest";

import type { ChoiceNewsEvent } from "../../../../api/contracts";
import {
  isDisplayableMacroNewsText,
  isMacroRelevantForHomeBriefing,
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

  it("rejects text that still contains html markup", () => {
    expect(isDisplayableMacroNewsText(stripHtmlTags('<div class="main-text">央行今日开展逆回购</div>'))).toBe(true);
    expect(isDisplayableMacroNewsText('<div class="main-text">央行今日开展逆回购</div>')).toBe(false);
  });
});
