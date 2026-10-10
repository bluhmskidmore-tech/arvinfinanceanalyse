import { describe, expect, it } from "vitest";

import type {
  BondPositionChangesPayload,
  BondTopHoldingsPayload,
  ChoiceNewsEvent,
  ChoiceNewsEventsPayload,
} from "../../../../api/contracts";
import { buildHomeBondNewsModel } from "./buildHomeBondNewsModel";

function choiceEvent(
  partial: Partial<ChoiceNewsEvent> &
    Pick<ChoiceNewsEvent, "event_key" | "received_at" | "topic_code">,
): ChoiceNewsEvent {
  return {
    group_id: "tushare_news",
    content_type: "news",
    serial_id: 1,
    request_id: 1,
    error_code: 0,
    error_msg: "",
    item_index: 0,
    payload_text: null,
    payload_json: null,
    ...partial,
  };
}

function bondMarketEvent(
  eventKey: string,
  title: string,
  receivedAt: string,
  extra?: Partial<ChoiceNewsEvent>,
): ChoiceNewsEvent {
  return choiceEvent({
    event_key: eventKey,
    received_at: receivedAt,
    topic_code: "tushare.news.sina",
    payload_text: title,
    payload_json: JSON.stringify({ title }),
    ...extra,
  });
}

function topHoldings(
  items: BondTopHoldingsPayload["items"],
): BondTopHoldingsPayload {
  return {
    report_date: "2026-06-01",
    top_n: items.length,
    items,
    total_market_value: {
      raw: 0,
      unit: "yuan",
      display: "0",
      precision: 0,
      sign_aware: false,
    },
    warnings: [],
    computed_at: "2026-06-01T00:00:00Z",
  };
}

function positionChanges(
  items: BondPositionChangesPayload["items"],
): BondPositionChangesPayload {
  return {
    report_date: "2026-06-01",
    prev_report_date: "2026-05-31",
    top_n: items.length,
    source_status: "ready",
    items,
    total_market_value: {
      raw: 0,
      unit: "yuan",
      display: "0",
      precision: 0,
      sign_aware: false,
    },
    prev_total_market_value: {
      raw: 0,
      unit: "yuan",
      display: "0",
      precision: 0,
      sign_aware: false,
    },
    warnings: [],
    computed_at: "2026-06-01T00:00:00Z",
  };
}

describe("buildHomeBondNewsModel", () => {
  it("returns empty sections and default labels when events are null or empty", () => {
    const nullEvents = buildHomeBondNewsModel({
      todayIsoDate: "2026-06-01",
      events: null,
    });
    const emptyEvents = buildHomeBondNewsModel({
      todayIsoDate: "2026-06-01",
      events: [],
    });

    for (const model of [nullEvents, emptyEvents]) {
      expect(model.holdingHits).toEqual([]);
      expect(model.marketNews).toEqual([]);
      expect(model.creditAndIssuanceNews).toEqual([]);
      expect(model.holdingMessage).toBe("持仓命中：当前无相关新闻");
      expect(model.marketMessage).toBe("债券市场：暂无相关新闻");
      expect(model.creditMessage).toBe("发行/评级：暂无相关新闻");
      expect(model.sourceLabel).toBe("后端入库：Choice / Tushare 债券新闻");
      expect(model.refreshLabel).toBe("页面读取：每 5 分钟重新读取已落库数据");
      expect(model.asOfLabel).toBe("最新内容：暂无");
      expect(model.statusLabel).toBe("来源状态：暂无数据");
    }
  });

  it("maps bond market news fields and sorts by content timestamp descending", () => {
    const olderContent = bondMarketEvent(
      "older-content",
      "国债收益率曲线整体下移，债市情绪回暖",
      "2026-07-27T12:00:00Z",
      {
        payload_json: JSON.stringify({
          title: "国债收益率曲线整体下移，债市情绪回暖",
          datetime: "2026-07-20T09:00:00Z",
        }),
      },
    );
    const newerContent = choiceEvent({
      event_key: "newer-content",
      received_at: "2026-07-26T12:00:00Z",
      group_id: "tushare_research",
      topic_code: "tushare.research_report.20260725_20260727",
      payload_text: "信用债收益率最新研究观点汇总",
      payload_json: JSON.stringify({
        title: "信用债收益率最新研究观点汇总",
        trade_date: "20260725",
      }),
    });

    const model = buildHomeBondNewsModel({
      todayIsoDate: "2026-07-27",
      events: [olderContent, newerContent],
    });

    expect(model.marketNews.map((item) => item.id)).toEqual([
      "newer-content",
      "older-content",
    ]);
    expect(model.marketNews[0]).toMatchObject({
      id: "newer-content",
      title: "信用债收益率最新研究观点汇总",
      timeLabel: "07-25",
      sourceLabel: "研究观点",
      topicLabel: "债券市场",
      hitLabel: null,
    });
    expect(model.marketNews[1]?.timeLabel).toBe("07-20 09:00");
    expect(model.asOfLabel).toBe("最新内容 07-25");
    expect(model.statusLabel).toBe("来源状态：正常");
    expect(model.holdingMessage).toBe("持仓命中：当前无相关新闻");
    expect(model.marketMessage).toBeNull();
  });

  it("classifies holding hits, credit/issuance news, and market news into separate buckets", () => {
    const holdingHit = choiceEvent({
      event_key: "holding-hit",
      received_at: "2026-06-01T10:00:00+08:00",
      topic_code: "tushare.news.sina",
      payload_text: "21国开10 二级成交活跃，收益率窄幅波动",
      payload_json: JSON.stringify({ title: "21国开10 二级成交活跃，收益率窄幅波动" }),
    });
    const creditNews = choiceEvent({
      event_key: "credit-news",
      received_at: "2026-06-01T09:00:00+08:00",
      topic_code: "tushare.news.sina",
      payload_text: "某城投公司债券评级上调至 AAA，信用利差收窄",
      payload_json: JSON.stringify({
        title: "某城投公司债券评级上调至 AAA，信用利差收窄",
      }),
    });
    const marketNews = bondMarketEvent(
      "market-news",
      "地方债二级成交回暖，债券市场关注供给节奏",
      "2026-06-01T08:00:00+08:00",
    );

    const model = buildHomeBondNewsModel({
      todayIsoDate: "2026-06-01",
      events: [holdingHit, creditNews, marketNews],
      topHoldings: topHoldings([
        {
          instrument_code: "210210.IB",
          instrument_name: "21国开10",
          issuer_name: "国家开发银行",
          rating: null,
          asset_class: "policy_bank",
          market_value: {
            raw: 1,
            unit: "yuan",
            display: "1",
            precision: 0,
            sign_aware: false,
          },
          face_value: {
            raw: 1,
            unit: "yuan",
            display: "1",
            precision: 0,
            sign_aware: false,
          },
          ytm: {
            raw: 0,
            unit: "pct",
            display: "0",
            precision: 2,
            sign_aware: false,
          },
          modified_duration: {
            raw: 0,
            unit: "years",
            display: "0",
            precision: 2,
            sign_aware: false,
          },
          weight: {
            raw: 0,
            unit: "pct",
            display: "0",
            precision: 2,
            sign_aware: false,
          },
        },
      ]),
    });

    expect(model.holdingHits).toHaveLength(1);
    expect(model.holdingHits[0]).toMatchObject({
      id: "holding-hit",
      topicLabel: "持仓命中",
      hitLabel: "命中持仓：21国开10",
    });
    expect(model.creditAndIssuanceNews).toHaveLength(1);
    expect(model.creditAndIssuanceNews[0]).toMatchObject({
      id: "credit-news",
      topicLabel: "发行/评级",
      hitLabel: null,
    });
    expect(model.marketNews).toHaveLength(1);
    expect(model.marketNews[0]).toMatchObject({
      id: "market-news",
      topicLabel: "债券市场",
      hitLabel: null,
    });
  });

  it("builds holding match candidates from position changes when top holdings are absent", () => {
    const eventItem = choiceEvent({
      event_key: "issuer-hit",
      received_at: "2026-06-01T10:00:00+08:00",
      topic_code: "tushare.news.sina",
      payload_text: "某能源集团企业债二级成交回暖，信用债市场关注",
      payload_json: JSON.stringify({
        title: "某能源集团企业债二级成交回暖，信用债市场关注",
      }),
    });

    const model = buildHomeBondNewsModel({
      todayIsoDate: "2026-06-01",
      events: [eventItem],
      positionChanges: positionChanges([
        {
          instrument_code: "123456.SH",
          instrument_name: null,
          issuer_name: "某能源集团",
          rating: null,
          asset_class: "credit",
          previous_market_value: {
            raw: 0,
            unit: "yuan",
            display: "0",
            precision: 0,
            sign_aware: false,
          },
          current_market_value: {
            raw: 1,
            unit: "yuan",
            display: "1",
            precision: 0,
            sign_aware: false,
          },
          change_market_value: {
            raw: 1,
            unit: "yuan",
            display: "1",
            precision: 0,
            sign_aware: false,
          },
          previous_weight: {
            raw: 0,
            unit: "pct",
            display: "0",
            precision: 2,
            sign_aware: false,
          },
          current_weight: {
            raw: 0,
            unit: "pct",
            display: "0",
            precision: 2,
            sign_aware: false,
          },
          change_weight: {
            raw: 0,
            unit: "pct",
            display: "0",
            precision: 2,
            sign_aware: false,
          },
          direction: "increase",
          reason_label: "test",
          source_status: "ready",
        },
      ]),
    });

    expect(model.holdingHits).toHaveLength(1);
    expect(model.holdingHits[0]?.hitLabel).toBe("命中发行人：某能源集团");
  });

  it("truncates each news bucket to its display limit", () => {
    const holdingEvents = Array.from({ length: 6 }, (_, index) =>
      choiceEvent({
        event_key: `holding-${index}`,
        received_at: `2026-06-01T${String(10 - index).padStart(2, "0")}:00:00+08:00`,
        topic_code: "tushare.news.sina",
        payload_text: `21国开10 持仓相关新闻条目 ${index + 1} 号`,
        payload_json: JSON.stringify({
          title: `21国开10 持仓相关新闻条目 ${index + 1} 号`,
        }),
      }),
    );
    const marketEvents = Array.from({ length: 7 }, (_, index) =>
      bondMarketEvent(
        `market-${index}`,
        `国债收益率波动观察条目 ${index + 1} 号`,
        `2026-06-01T${String(20 - index).padStart(2, "0")}:00:00+08:00`,
      ),
    );
    const creditEvents = Array.from({ length: 6 }, (_, index) =>
      choiceEvent({
        event_key: `credit-${index}`,
        received_at: `2026-06-01T${String(30 - index).padStart(2, "0")}:00:00+08:00`,
        topic_code: "tushare.news.sina",
        payload_text: `某城投债券评级变动观察条目 ${index + 1} 号`,
        payload_json: JSON.stringify({
          title: `某城投债券评级变动观察条目 ${index + 1} 号`,
        }),
      }),
    );

    const model = buildHomeBondNewsModel({
      todayIsoDate: "2026-06-01",
      events: [...holdingEvents, ...marketEvents, ...creditEvents],
      topHoldings: topHoldings([
        {
          instrument_code: "210210.IB",
          instrument_name: "21国开10",
          issuer_name: "国家开发银行",
          rating: null,
          asset_class: "policy_bank",
          market_value: {
            raw: 1,
            unit: "yuan",
            display: "1",
            precision: 0,
            sign_aware: false,
          },
          face_value: {
            raw: 1,
            unit: "yuan",
            display: "1",
            precision: 0,
            sign_aware: false,
          },
          ytm: {
            raw: 0,
            unit: "pct",
            display: "0",
            precision: 2,
            sign_aware: false,
          },
          modified_duration: {
            raw: 0,
            unit: "years",
            display: "0",
            precision: 2,
            sign_aware: false,
          },
          weight: {
            raw: 0,
            unit: "pct",
            display: "0",
            precision: 2,
            sign_aware: false,
          },
        },
      ]),
    });

    expect(model.holdingHits).toHaveLength(4);
    expect(model.marketNews).toHaveLength(5);
    expect(model.creditAndIssuanceNews).toHaveLength(4);
  });

  it("filters error events, short titles, and duplicate titles", () => {
    const model = buildHomeBondNewsModel({
      todayIsoDate: "2026-06-01",
      events: [
        choiceEvent({
          event_key: "error-event",
          received_at: "2026-06-01T12:00:00+08:00",
          topic_code: "tushare.news.sina",
          error_code: 10003013,
          error_msg: "vendor timeout",
          payload_text: "国债收益率上行，债券市场承压",
        }),
        bondMarketEvent(
          "short-title",
          "短标题",
          "2026-06-01T11:00:00+08:00",
        ),
        bondMarketEvent(
          "first-copy",
          "国债收益率曲线整体下移，债市情绪回暖",
          "2026-06-01T10:00:00+08:00",
        ),
        bondMarketEvent(
          "duplicate-copy",
          "国债收益率曲线整体下移，债市情绪回暖",
          "2026-06-01T09:00:00+08:00",
        ),
      ],
    });

    expect(model.marketNews).toHaveLength(1);
    expect(model.marketNews[0]?.id).toBe("first-copy");
  });

  it("handles missing and null fields without throwing and degrades labels gracefully", () => {
    expect(() =>
      buildHomeBondNewsModel({
        todayIsoDate: "2026-06-01",
        events: undefined,
        choiceNewsPayloads: undefined,
        topHoldings: null,
        positionChanges: null,
        industryDistribution: null,
      }),
    ).not.toThrow();

    const model = buildHomeBondNewsModel({
      todayIsoDate: "2026-06-01",
      events: [
        choiceEvent({
          event_key: "missing-fields",
          received_at: "—",
          topic_code: "—",
          group_id: "tushare_news",
          payload_text: null,
          payload_json: null,
        }),
        choiceEvent({
          event_key: "invalid-json",
          received_at: "2026-06-01T08:00:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "国债收益率维持震荡，信用债市场平稳",
          payload_json: "{not-json",
        }),
      ],
      topHoldings: topHoldings([
        {
          instrument_code: "AB",
          instrument_name: null,
          issuer_name: null,
          rating: null,
          asset_class: "credit",
          market_value: {
            raw: 0,
            unit: "yuan",
            display: "0",
            precision: 0,
            sign_aware: false,
          },
          face_value: {
            raw: 0,
            unit: "yuan",
            display: "0",
            precision: 0,
            sign_aware: false,
          },
          ytm: {
            raw: 0,
            unit: "pct",
            display: "0",
            precision: 2,
            sign_aware: false,
          },
          modified_duration: {
            raw: 0,
            unit: "years",
            display: "0",
            precision: 2,
            sign_aware: false,
          },
          weight: {
            raw: 0,
            unit: "pct",
            display: "0",
            precision: 2,
            sign_aware: false,
          },
        },
      ]),
    });

    expect(model.marketNews).toHaveLength(1);
    expect(model.marketNews[0]).toMatchObject({
      id: "invalid-json",
      title: "国债收益率维持震荡，信用债市场平稳",
      timeLabel: "06-01 08:00",
      sourceLabel: "市场快讯",
    });
    expect(model.asOfLabel).toBe("最新事件 06-01 08:00");
  });

  it("marks stale status when the latest included news is older than seven days", () => {
    const model = buildHomeBondNewsModel({
      todayIsoDate: "2026-06-15",
      events: [
        bondMarketEvent(
          "stale-market",
          "国债收益率曲线整体下移，债市情绪回暖",
          "2026-06-01T08:00:00+08:00",
        ),
      ],
    });

    expect(model.marketNews).toHaveLength(1);
    expect(model.statusLabel).toBe("来源状态：偏旧");
  });

  it("uses choiceNewsPayload as_of_date when no bond news passes the filter", () => {
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
    expect(model.statusLabel).toBe("来源状态：暂无数据");
  });

  it("explains queried-but-unmatched bond news with section messages", () => {
    const model = buildHomeBondNewsModel({
      todayIsoDate: "2026-06-01",
      events: [
        choiceEvent({
          event_key: "equity-only",
          received_at: "2026-06-01T12:00:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "A股市场成交额放大，科技板块走强。",
        }),
        choiceEvent({
          event_key: "commodity-only",
          received_at: "2026-06-01T11:50:00+08:00",
          topic_code: "tushare.major_news",
          payload_text: "国际油价震荡上行。",
        }),
      ],
    });

    expect(model.holdingHits).toHaveLength(0);
    expect(model.marketNews).toHaveLength(0);
    expect(model.creditAndIssuanceNews).toHaveLength(0);
    expect(model.asOfLabel).toBe("已查询事件至 06-01 12:00");
    expect(model.statusLabel).toBe("来源状态：未命中债券相关内容");
    expect(model.holdingMessage).toBe(
      "持仓命中：已查询 2 条新闻，未命中当前持仓或发行人。",
    );
    expect(model.marketMessage).toBe(
      "债券市场：已查询 2 条新闻，未筛出债券市场相关内容。",
    );
    expect(model.creditMessage).toBe(
      "发行/评级：已查询 2 条新闻，未筛出债券发行或评级内容。",
    );
  });
});
