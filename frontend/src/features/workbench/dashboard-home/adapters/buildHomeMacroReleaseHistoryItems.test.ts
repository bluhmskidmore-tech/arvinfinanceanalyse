import { describe, expect, it } from "vitest";

import type { HomeMacroReleaseContextHistoryItem } from "../../../../api/contracts";
import { buildHomeMacroReleaseHistoryItems } from "./buildHomeMacroReleaseHistoryItems";

describe("buildHomeMacroReleaseHistoryItems", () => {
  it("maps the governed NBS GDP selection into the homepage history row", () => {
    const items: HomeMacroReleaseContextHistoryItem[] = [
      {
        indicator_key: "cn_growth",
        title: "中国增长",
        region: "CN",
        category: "growth",
        importance: "high",
        observation_date: "2026-06-30",
        previous_observation_date: "2026-03-31",
        reference_period: "2026-Q2",
        previous_reference_period: "2026-Q1",
        release_date: null,
        source_status: "ready",
        source_name: "来源：National Bureau of Statistics of China",
        metrics: [
          {
            metric_key: "gdp_yoy",
            label: "GDP YoY",
            actual_value: 4.3,
            previous_value: 5,
            change_value: -0.7,
            display_unit: "pct",
            change_unit: "pct_point",
            precision: 1,
            direction: "down",
          },
        ],
        notes: [
          "Selected vendor: NBS official release (nbs.macro.cn_gdp.quarterly).",
          "Rejected vendor: Tushare (older period 2026-03-31).",
          "GDP 初值，后续可能修订。",
        ],
      },
    ];

    expect(buildHomeMacroReleaseHistoryItems(items)[0]).toMatchObject({
      id: "cn_growth",
      title: "中国增长",
      sourceName: "国家统计局",
      history: {
        latestLabel: "2026-Q2",
        latestValue: "4.3%",
        previousLabel: "2026-Q1",
        previousValue: "5.0%",
        changeValue: "-0.7个百分点",
        changeTone: "down",
        note: "已更新；GDP 初值，后续可能修订。",
        sourceLabel: "来源：国家统计局",
      },
    });
    expect(buildHomeMacroReleaseHistoryItems(items)[0].history.note).not.toMatch(
      /Selected vendor|Rejected vendor|series_id/i,
    );
  });

  it("surfaces governed no-data states instead of inventing values", () => {
    const item: HomeMacroReleaseContextHistoryItem = {
      indicator_key: "us_growth",
      title: "美国增长",
      region: "US",
      category: "growth",
      importance: "high",
      observation_date: null,
      previous_observation_date: null,
      reference_period: null,
      previous_reference_period: null,
      release_date: null,
      source_status: "source_pending",
      source_name: null,
      metrics: [
        {
          metric_key: "us_gdp_yoy",
          label: "GDP YoY",
          actual_value: null,
          previous_value: null,
          change_value: null,
          display_unit: "pct",
          change_unit: "pct_point",
          precision: 1,
          direction: "unavailable",
        },
      ],
      notes: ["Source integration pending."],
    };

    const result = buildHomeMacroReleaseHistoryItems([item])[0];
    expect(result.history.latestValue).toBe("—");
    expect(result.history.note).toBe("数据源待接入");
    expect(result.history.note).not.toContain("Source integration pending");

    const partial = buildHomeMacroReleaseHistoryItems([
      {
        ...item,
        source_status: "partial",
        notes: [
          "Previous value unavailable for us_gdp_yoy.",
          "Seasonal adjustment should be reviewed.",
        ],
      },
    ])[0];
    expect(partial.history.note).toBe(
      "部分数据；前值暂缺。；Seasonal adjustment should be reviewed.",
    );

    const unitMismatch = buildHomeMacroReleaseHistoryItems([
      {
        ...item,
        source_status: "error",
        notes: ["Unit mismatch for us_gdp_yoy."],
      },
    ])[0];
    expect(unitMismatch.history.note).toBe("读取失败；数据单位与页面口径不一致。");
  });

  it("keeps the live inflation values while hiding diagnostic fields", () => {
    const item: HomeMacroReleaseContextHistoryItem = {
      indicator_key: "cn_inflation",
      title: "中国通胀",
      region: "CN",
      category: "inflation",
      importance: "high",
      observation_date: "2026-08-01",
      previous_observation_date: "2026-07-01",
      reference_period: "2026-08",
      previous_reference_period: "2026-07",
      release_date: null,
      source_status: "ready",
      source_name: "NBS official release",
      metrics: [
        {
          metric_key: "cpi_yoy",
          label: "CPI",
          actual_value: 0.8,
          previous_value: 0.5,
          change_value: 0.3,
          display_unit: "pct",
          change_unit: "pct_point",
          precision: 1,
          direction: "up",
        },
        {
          metric_key: "ppi_yoy",
          label: "PPI",
          actual_value: 3.8,
          previous_value: 3.5,
          change_value: 0.3,
          display_unit: "pct",
          change_unit: "pct_point",
          precision: 1,
          direction: "up",
        },
      ],
      notes: [
        "Selected vendor: NBS official release (nbs.macro.cn_cpi.monthly).",
        "Rejected vendor: Tushare (older period 2026-07-01).",
        "Vendor evidence: NBS official release, Tushare.",
        "series_id=nbs.macro.cn_cpi.monthly",
      ],
    };

    const result = buildHomeMacroReleaseHistoryItems([item])[0];
    expect(result.history.latestValue).toBe("CPI 0.8% / PPI 3.8%");
    expect(result.history.previousValue).toBe("CPI 0.5% / PPI 3.5%");
    expect(result.history.changeValue).toBe("CPI +0.3个百分点 / PPI +0.3个百分点");
    expect(result.history.note).toBe("已更新");
    expect(result.history.sourceLabel).toBe("来源：国家统计局");
  });
});
