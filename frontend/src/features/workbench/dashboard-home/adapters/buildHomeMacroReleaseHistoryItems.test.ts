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
        source_name: "NBS official release",
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
        notes: ["Selected vendor: NBS official release."],
      },
    ];

    expect(buildHomeMacroReleaseHistoryItems(items)[0]).toMatchObject({
      id: "cn_growth",
      title: "中国增长",
      sourceName: "NBS official release",
      history: {
        latestLabel: "2026-Q2",
        latestValue: "4.3%",
        previousLabel: "2026-Q1",
        previousValue: "5.0%",
        changeValue: "-0.7个百分点",
        changeTone: "down",
        sourceLabel: "来源：NBS official release",
      },
    });
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
    expect(result.history.note).toContain("数据源待接入");
  });
});
