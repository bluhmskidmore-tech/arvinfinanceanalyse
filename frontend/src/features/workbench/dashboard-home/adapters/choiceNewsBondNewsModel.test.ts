import { describe, expect, it } from "vitest";

import type { ChoiceNewsEvent, ChoiceNewsEventsPayload } from "../../../../api/contracts";
import { buildHomeBondNewsModel } from "./buildHomeBondNewsModel";

function event(
  partial: Pick<
    ChoiceNewsEvent,
    "event_key" | "received_at" | "group_id" | "topic_code" | "payload_text" | "payload_json"
  >,
): ChoiceNewsEvent {
  return {
    content_type: "news",
    serial_id: 1,
    request_id: 1,
    error_code: 0,
    error_msg: "",
    item_index: 0,
    ...partial,
  };
}

describe("ChoiceNews bond news model", () => {
  it("uses ChoiceNews payload as_of_date in the existing data date label", () => {
    const payload: ChoiceNewsEventsPayload = {
      total_rows: 0,
      limit: 10,
      offset: 0,
      as_of_date: "2026-05-08",
      excluded_future_rows: 2,
      events: [],
    };

    const model = buildHomeBondNewsModel({
      todayIsoDate: "2026-05-08",
      events: [],
      choiceNewsPayloads: [payload],
    });

    expect(model.asOfLabel).toBe("查询日期 2026-05-08 · 已剔除未来 2 条");
  });

  it("orders and labels freshness by the actual content timestamp before event receipt time", () => {
    const receivedLaterButOlderContent = event({
      event_key: "older-content",
      received_at: "2026-07-27T12:00:00Z",
      group_id: "tushare_news",
      topic_code: "tushare.news.sina",
      payload_text: "国债收益率旧闻回顾",
      payload_json: JSON.stringify({
        title: "国债收益率旧闻回顾",
        datetime: "2026-07-20T09:00:00Z",
      }),
    });
    const receivedEarlierButNewerContent = event({
      event_key: "newer-content",
      received_at: "2026-07-26T12:00:00Z",
      group_id: "tushare_research",
      topic_code: "tushare.research_report.20260725_20260727",
      payload_text: "信用债收益率最新研究观点",
      payload_json: JSON.stringify({
        title: "信用债收益率最新研究观点",
        trade_date: "20260725",
      }),
    });

    const model = buildHomeBondNewsModel({
      todayIsoDate: "2026-07-27",
      events: [receivedLaterButOlderContent, receivedEarlierButNewerContent],
      choiceNewsPayloads: [
        {
          total_rows: 2,
          limit: 8,
          offset: 0,
          as_of_date: "2026-07-27",
          excluded_future_rows: 1,
          events: [receivedLaterButOlderContent, receivedEarlierButNewerContent],
        },
      ],
    });

    expect(model.marketNews.map((item) => item.id)).toEqual([
      "newer-content",
      "older-content",
    ]);
    expect(model.marketNews[0]?.timeLabel).toBe("07-25");
    expect(model.marketNews[0]?.sourceLabel).toBe("研究观点");
    expect(model.asOfLabel).toBe("最新内容 07-25 · 已剔除未来 1 条");
    expect(model.statusLabel).toBe("来源状态：正常");
  });

  it("explains bond news source returns that do not pass the bond filter", () => {
    const model = buildHomeBondNewsModel({
      todayIsoDate: "2026-06-01",
      events: [
        event({
          event_key: "broad-equity",
          received_at: "2026-06-01T12:00:00+08:00",
          group_id: "tushare_news",
          topic_code: "tushare.news.sina",
          payload_text: "A股市场成交额放大，科技板块走强。",
          payload_json: null,
        }),
        event({
          event_key: "commodity",
          received_at: "2026-06-01T11:50:00+08:00",
          group_id: "tushare_news",
          topic_code: "tushare.major_news",
          payload_text: "国际油价震荡上行。",
          payload_json: null,
        }),
      ],
    });

    expect(model.holdingHits).toHaveLength(0);
    expect(model.marketNews).toHaveLength(0);
    expect(model.creditAndIssuanceNews).toHaveLength(0);
    expect(model.asOfLabel).toBe("已查询事件至 06-01 12:00");
    expect(model.statusLabel).toBe("来源状态：未命中债券相关内容");
    expect(model.holdingMessage).toBe("持仓命中：已查询 2 条新闻，未命中当前持仓或发行人。");
    expect(model.marketMessage).toBe("债券市场：已查询 2 条新闻，未筛出债券市场相关内容。");
    expect(model.creditMessage).toBe("发行/评级：已查询 2 条新闻，未筛出债券发行或评级内容。");
  });
});
