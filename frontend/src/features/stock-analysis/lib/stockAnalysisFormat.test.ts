import { describe, expect, it } from "vitest";

import { EM_DASH } from "../../../pageModel";
import {
  PENDING_TEXT,
  choiceNewsDataDateLabel,
  choiceNewsTopicLabel,
  formatChoiceNewsReceivedAt,
  formatFixed,
  formatMultiple,
  formatPointSignedPercent,
  formatRatioPercent,
  formatRatioSignedPercent,
  truncateChoiceNewsText,
} from "./stockAnalysisFormat";

describe("stockAnalysisFormat", () => {
  it("keeps ratio and point percent inputs distinct", () => {
    expect(formatRatioPercent(0.143)).toBe("14.30%");
    expect(formatRatioSignedPercent(0.123)).toBe("+12.30%");
    expect(formatRatioSignedPercent(-0.0125)).toBe("-1.25%");
    expect(formatRatioSignedPercent(0)).toBe("0.00%");
    expect(formatPointSignedPercent(1.66)).toBe("+1.66%");
    expect(formatPointSignedPercent(-3.2)).toBe("-3.20%");
  });

  it("uses the caller's fallback for missing values", () => {
    expect(formatRatioPercent(null)).toBe(EM_DASH);
    expect(formatRatioPercent(undefined, 2, PENDING_TEXT)).toBe(PENDING_TEXT);
    expect(formatFixed(Number.NaN, 2, PENDING_TEXT)).toBe(PENDING_TEXT);
    expect(formatMultiple(null)).toBe(EM_DASH);
    expect(formatMultiple(2.314)).toBe("2.3x");
    expect(formatFixed(12.4)).toBe("12.40");
  });

  it("formats Choice news dates and text consistently for the drawer and the desk", () => {
    expect(formatChoiceNewsReceivedAt("2026-08-24T15:10:00+08:00")).toBe("2026-08-24 15:10");
    expect(formatChoiceNewsReceivedAt("  ")).toBe(EM_DASH);
    expect(choiceNewsDataDateLabel("2026-08-24", 0)).toBe("2026-08-24");
    expect(choiceNewsDataDateLabel("2026-08-24", 3)).toBe("2026-08-24（已剔除未来 3 条）");
    expect(choiceNewsDataDateLabel(null, null)).toBe("待确认");
    expect(truncateChoiceNewsText("  ", 10)).toBe(EM_DASH);
    expect(truncateChoiceNewsText("一二三四五六", 3)).toBe("一二三…");
  });

  it("never shows vendor technical codes as event categories", () => {
    expect(choiceNewsTopicLabel("anything", "announcement")).toBe("公告");
    expect(choiceNewsTopicLabel("定增", null)).toBe("定增");
    expect(choiceNewsTopicLabel("EXTERNAL_VENDOR_BASIS", null)).toBe("事件分类待确认");
    expect(choiceNewsTopicLabel("source_table_x", null, "事件待确认")).toBe("事件待确认");
    expect(choiceNewsTopicLabel(null, null)).toBe("事件分类待确认");
  });
});
