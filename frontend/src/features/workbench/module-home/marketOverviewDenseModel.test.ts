import { describe, expect, it } from "vitest";

import type {
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  ChoiceNewsEvent,
} from "../../../api/contracts";
import type { MacroToolkitIndicator } from "../../../api/macroToolkitClient";
import {
  buildDenseAuditStats,
  buildDenseLedgerRows,
  buildDenseMacroPulseRows,
  buildDenseNewsDensity,
  buildDenseTapeMetrics,
  formatDenseNewsTopicLabel,
} from "./marketOverviewDenseModel";
import type { ModuleHomeDetailPanel } from "./moduleHomeModel";

function point(
  overrides: Partial<ChoiceMacroLatestPoint> &
    Pick<
      ChoiceMacroLatestPoint,
      "series_id" | "series_name" | "value_numeric" | "unit"
    >,
): ChoiceMacroLatestPoint {
  return {
    trade_date: "2026-07-27",
    source_version: "source-v1",
    vendor_version: "vendor-v1",
    latest_change: null,
    ...overrides,
  };
}

function payload(
  series: ChoiceMacroLatestPoint[],
): ChoiceMacroLatestPayload {
  return { read_target: "duckdb", series };
}

function indicator(
  overrides: Partial<MacroToolkitIndicator> &
    Pick<MacroToolkitIndicator, "key" | "label" | "latest_value">,
): MacroToolkitIndicator {
  return {
    alias: overrides.key,
    group: "macro",
    unit: "%",
    row_count: 12,
    latest_date: "2026-07-27",
    previous_value: null,
    change: null,
    change_pct: null,
    source: "choice",
    series_id: overrides.key,
    quality: "ok",
    ...overrides,
  };
}

function newsEvent(
  eventKey: string,
  receivedAt: string,
  topicCode = "rates",
): ChoiceNewsEvent {
  return {
    event_key: eventKey,
    received_at: receivedAt,
    group_id: "macro",
    content_type: "news",
    serial_id: 1,
    request_id: 1,
    error_code: 0,
    error_msg: "",
    topic_code: topicCode,
    item_index: 0,
    payload_text: eventKey,
    payload_json: null,
  };
}

describe("marketOverviewDenseModel", () => {
  it("keeps API units across eight real market indicators in the tape", () => {
    const rates = payload([
      point({
        series_id: "CN.GOV.10Y",
        series_name: "中债国债到期收益率:10年",
        value_numeric: 1.73,
        unit: "%",
        latest_change: 0.006,
      }),
      point({
        series_id: "CN.DR007",
        series_name: "DR007",
        value_numeric: 1.42,
        unit: "%",
        latest_change: 0.02,
      }),
      point({
        series_id: "EMM00088132",
        series_name: "公开市场操作:逆回购:7天:中标利率",
        value_numeric: 1.4,
        unit: "%",
        latest_change: 0,
      }),
      point({
        series_id: "NCD.SHIBOR.3M",
        series_name: "SHIBOR:3M",
        value_numeric: 1.428,
        unit: "%",
        latest_change: -0.002,
      }),
    ]);
    const latest = payload([
      point({
        series_id: "CA.CSI300",
        series_name: "沪深300指数收盘价",
        value_numeric: 4649.19,
        unit: "index",
      }),
      point({
        series_id: "CA.CSI300.PCT_CHG",
        series_name: "沪深300指数涨跌幅",
        value_numeric: -1.67,
        unit: "%",
      }),
      point({
        series_id: "CMD.BRENT",
        series_name: "Brent spot price",
        value_numeric: 77.54,
        unit: "USD/bbl",
        latest_change: 1.98,
      }),
      point({
        series_id: "FX.USDCNY",
        series_name: "USD/CNY",
        value_numeric: 7.1765,
        unit: "index",
        latest_change: 0.004,
      }),
      point({
        series_id: "CA.COPPER",
        series_name: "铜主力期货收盘价",
        value_numeric: 104750,
        unit: "CNY/t",
        latest_change: -1140,
      }),
    ]);

    const metrics = buildDenseTapeMetrics({ latest, rates });

    expect(metrics).toHaveLength(8);
    expect(metrics.find((item) => item.key === "gov-10y")).toMatchObject({
      value: "1.73%",
      delta: "+0.6bp",
    });
    expect(metrics.find((item) => item.key === "csi300")).toMatchObject({
      value: "4,649.19 index",
      delta: "-1.67%",
      tone: "down",
    });
    expect(metrics.find((item) => item.key === "brent")).toMatchObject({
      value: "77.54 USD/bbl",
    });
    expect(metrics.find((item) => item.key === "usd-cny")).toMatchObject({
      value: "7.1765 index",
    });
    expect(
      metrics.find((item) => item.key === "reverse-repo-7d"),
    ).toMatchObject({ value: "1.4%" });
    expect(metrics.find((item) => item.key === "shibor-3m")).toMatchObject({
      value: "1.428%",
    });
    expect(metrics.find((item) => item.key === "copper")).toMatchObject({
      value: "104,750 CNY/t",
      tone: "down",
    });
    expect(metrics.some((item) => item.key === "formal")).toBe(false);
    expect(metrics.some((item) => item.key === "news")).toBe(false);
    expect(metrics.find((item) => item.key === "gov-10y")).toMatchObject({
      tradeDate: "2026-07-27",
      title: "中债国债到期收益率:10年 · 1.73% · 2026-07-27",
    });
  });

  it("leaves the tape report date unset when the backend returns no matching series", () => {
    const metric = buildDenseTapeMetrics({
      latest: payload([]),
      rates: payload([]),
    }).find((item) => item.key === "gov-10y");

    expect(metric).toMatchObject({
      value: "—",
      delta: "未返回",
      tone: "muted",
      title: "10Y国债：后端未返回匹配序列",
    });
    expect(metric?.tradeDate).toBeUndefined();
  });

  it("fails closed when no Chinese 10Y sovereign series is available", () => {
    const rates = payload([
      point({
        series_id: "US.GOV.10Y",
        series_name: "US Treasury 10Y",
        value_numeric: 4.12,
        unit: "%",
        latest_change: 0.01,
      }),
      point({
        series_id: "UK.GILT.10Y",
        series_name: "UK Gilt 10Y",
        value_numeric: 4.02,
        unit: "%",
        latest_change: -0.02,
      }),
      point({
        series_id: "JP.JGB.10Y",
        series_name: "Japan JGB 10Y",
        value_numeric: 1.1,
        unit: "%",
      }),
    ]);

    const metric = buildDenseTapeMetrics({
      latest: payload([]),
      rates,
    }).find((item) => item.key === "gov-10y");

    expect(metric).toMatchObject({
      tone: "muted",
    });
    expect(metric?.value).not.toBe("4.12%");
    expect(metric?.value).not.toBe("4.02%");
    expect(metric?.value).not.toBe("1.1%");
  });

  it("orders preferred ledger rows without changing dates or formatted values", () => {
    const panel: ModuleHomeDetailPanel = {
      key: "key-rate-snapshot",
      title: "关键利率",
      meta: "",
      stateLabel: "已返回",
      stateDetail: "",
      tone: "ok",
      rows: [
        {
          key: "dr007",
          label: "DR007",
          value: "1.42%",
          detail: "+2bp / 2026-07-27",
          tradeDate: "2026-07-27",
          source: "CN.DR007",
          tone: "ok",
        },
        {
          key: "gov-10y",
          label: "10Y 国债",
          value: "1.73%",
          detail: "+0.6bp / 2026-07-27",
          tradeDate: "2026-07-27",
          source: "CN.GOV.10Y",
          tone: "ok",
        },
      ],
    };

    const rows = buildDenseLedgerRows([panel], 2);

    expect(rows.map((row) => row.key)).toEqual(["gov-10y", "dr007"]);
    expect(rows[0]).toMatchObject({
      value: "1.73%",
      delta: "+0.6bp",
      reportDate: "2026-07-27",
    });
  });

  it("reports coverage from the six existing read envelopes", () => {
    const stats = buildDenseAuditStats({
      latest: payload([]),
      rates: payload([]),
      catalog: { read_target: "duckdb", series: [] },
      news: {
        total_rows: 11108,
        limit: 3,
        offset: 0,
        as_of_date: "2026-07-27",
        excluded_future_rows: 0,
        events: [],
      },
      macroSectionCount: 21,
      strategySectionCount: 3,
    });

    expect(stats).toEqual({
      latest: 0,
      formal: 0,
      catalog: 0,
      macro: 21,
      strategies: 3,
      news: 11108,
    });
  });

  it("builds a four-row macro pulse from backend latest and previous values", () => {
    const rows = buildDenseMacroPulseRows({
      as_of_date: "2026-07-27",
      indicators: [
        indicator({
          key: "pmi",
          label: "PMI（制造业）",
          latest_value: 49.3,
          previous_value: 49.4,
          change: -0.1,
          unit: "index",
        }),
        indicator({
          key: "cpi",
          label: "CPI（同比）",
          latest_value: 0.3,
          previous_value: 0.2,
          change: 0.1,
        }),
        indicator({
          key: "ppi",
          label: "PPI（同比）",
          latest_value: -1.8,
          previous_value: -1.6,
          change: -0.2,
        }),
        indicator({
          key: "social-financing",
          label: "社会融资",
          latest_value: 42180,
          previous_value: 48390,
          change: -6210,
          unit: "亿元",
        }),
      ],
    });

    expect(rows.map((row) => row.key)).toEqual([
      "cpi",
      "ppi",
      "pmi",
      "social-financing",
    ]);
    expect(rows[0]).toMatchObject({
      previousValue: "0.2%",
      latestValue: "0.3%",
      change: "+0.1%",
      changeLabel: "绝对变化",
      tone: "up",
      latestDate: "2026-07-27",
    });
    expect(rows.find((row) => row.key === "pmi")).toMatchObject({
      previousValue: "49.4 index",
      latestValue: "49.3 index",
      change: "-0.1 index",
    });

    const percentageFallback = buildDenseMacroPulseRows({
      as_of_date: "2026-07-27",
      indicators: [
        indicator({
          key: "cpi",
          label: "CPI（同比）",
          latest_value: 0.3,
          previous_value: 0.2,
          change: null,
          change_pct: 50,
        }),
      ],
    });
    expect(percentageFallback[0]).toMatchObject({
      change: "+50%",
      changeLabel: "百分比变化",
    });

    const missingPrevious = buildDenseMacroPulseRows({
      as_of_date: "2026-07-27",
      indicators: [
        indicator({
          key: "ppi",
          label: "PPI（同比）",
          latest_value: -1.8,
          previous_value: null,
          change: -0.2,
        }),
      ],
    });
    expect(missingPrevious[0]?.previousValue).toBe("—");
  });

  it("groups the latest news sample by topic and two-hour bucket", () => {
    const density = buildDenseNewsDensity({
      total_rows: 11108,
      limit: 3,
      offset: 0,
      as_of_date: "2026-07-27",
      excluded_future_rows: 0,
      events: [
        newsEvent("event-a", "2026-07-27T21:45:00"),
        newsEvent("event-b", "2026-07-27T20:15:00"),
        newsEvent("event-c", "2026-07-26T08:30:00", "policy"),
        newsEvent("invalid-hour", "2026-07-27T99:15:00"),
        newsEvent("invalid-date", "2026-02-30T08:30:00"),
      ],
    });

    expect(density.rows).toHaveLength(2);
    expect(density.rows[0]?.key).toBe("rates");
    expect(density.rows[0]?.cells).toHaveLength(12);
    expect(density.rows[0]?.cells[10]).toMatchObject({
      count: 2,
      intensity: 4,
    });
    expect(density.sampledEvents).toBe(3);
    expect(density.startDate).toBe("2026-07-26");
    expect(density.endDate).toBe("2026-07-27");
  });

  it("friendly-labels only known news topics and preserves unknown topic codes", () => {
    expect(formatDenseNewsTopicLabel("major news")).toBe("主要新闻");
    expect(formatDenseNewsTopicLabel("sina")).toBe("新浪");
    expect(formatDenseNewsTopicLabel("tushare.major_news")).toBe("主要新闻");
    expect(formatDenseNewsTopicLabel("tushare_major")).toBe("主要新闻");
    expect(formatDenseNewsTopicLabel("tushare.news.sina")).toBe("新浪");
    expect(formatDenseNewsTopicLabel("tushare_news")).toBe("新浪");
    expect(
      formatDenseNewsTopicLabel("tushare.research_report.20260712_20260715"),
    ).toBe("研究报告");
    expect(formatDenseNewsTopicLabel("vendor.topic_20260712")).toBe(
      "vendor.topic_20260712",
    );
  });
});
