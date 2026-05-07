import { describe, expect, it } from "vitest";

import { getChoiceNewsTopicPresentation } from "./choiceNewsTopicDictionary";

describe("choiceNewsTopicDictionary", () => {
  it("returns mapped labels and metadata for known group/topic codes", () => {
    const result = getChoiceNewsTopicPresentation({
      groupId: "news_cmd1",
      topicCode: "S888010007API",
    });

    expect(result.displayPair).toBe("Choice News Topics 2026-04-09 / 经济数据");
    expect(result.rawPair).toBe("news_cmd1 / S888010007API");
    expect(result.groupName).toBe("Choice News Topics 2026-04-09");
    expect(result.topicName).toBe("经济数据");
    expect(result.groupTags).toEqual(expect.arrayContaining(["choice", "news", "macro"]));
    expect(result.groupIsCore).toBe(true);
    expect(result.usesFallback).toBe(false);
  });

  it("falls back to raw ids when the topic mapping is unknown", () => {
    const result = getChoiceNewsTopicPresentation({
      groupId: "news_cmd1",
      topicCode: "__callback__",
    });

    expect(result.displayPair).toBe("news_cmd1 / __callback__");
    expect(result.rawPair).toBe("news_cmd1 / __callback__");
    expect(result.groupName).toBe("Choice News Topics 2026-04-09");
    expect(result.topicName).toBeNull();
    expect(result.groupIsCore).toBe(true);
    expect(result.usesFallback).toBe(true);
  });

  it("falls back to raw ids when both mappings are unknown", () => {
    const result = getChoiceNewsTopicPresentation({
      groupId: "unknown_group",
      topicCode: "unknown_topic",
    });

    expect(result.displayPair).toBe("unknown_group / unknown_topic");
    expect(result.rawPair).toBe("unknown_group / unknown_topic");
    expect(result.groupName).toBeNull();
    expect(result.topicName).toBeNull();
    expect(result.groupTags).toEqual([]);
    expect(result.groupIsCore).toBe(false);
    expect(result.usesFallback).toBe(true);
  });
});
