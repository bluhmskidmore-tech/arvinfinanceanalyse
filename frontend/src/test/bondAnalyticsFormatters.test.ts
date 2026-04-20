import { describe, expect, it } from "vitest";

import { designTokens } from "../theme/designSystem";
import {
  formatBp,
  formatPct,
  formatWan,
  formatYi,
  toneColor,
} from "../features/bond-analytics/utils/formatters";

describe("bond analytics formatters", () => {
  describe("formatYi", () => {
    it("formats yuan string to 亿", () => {
      expect(formatYi("100000000")).toMatch(/1(\.00)?\s*亿/);
    });

    it("returns dash for invalid input", () => {
      expect(formatYi("not-a-number")).toBe("-");
    });
  });

  describe("formatWan", () => {
    it("formats yuan string to 万", () => {
      expect(formatWan("10000")).toMatch(/1\s*万/);
    });

    it("returns dash for invalid input", () => {
      expect(formatWan("x")).toBe("-");
    });
  });

  describe("formatPct", () => {
    it("converts decimal string to percent string", () => {
      expect(formatPct("0.0255")).toBe("2.55%");
    });

    it("returns dash for invalid input", () => {
      expect(formatPct("")).toBe("-");
    });
  });

  describe("formatBp", () => {
    it("formats numeric string as bp", () => {
      expect(formatBp("12.3")).toBe("12.3 bp");
    });

    it("returns dash for invalid input", () => {
      expect(formatBp("bad")).toBe("-");
    });
  });

  describe("toneColor", () => {
    it("uses China convention: nonnegative red, negative green", () => {
      expect(toneColor(0)).toBe(designTokens.color.danger[500]);
      expect(toneColor(1)).toBe(designTokens.color.danger[500]);
      expect(toneColor(-0.01)).toBe(designTokens.color.success[600]);
    });
  });
});
