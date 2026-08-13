import { describe, expect, it } from "vitest";

import {
  formatBp,
  formatPct,
  formatWan,
  formatYi,
  toneColor,
} from "../features/bond-analytics/utils/formatters";
import { EM_DASH } from "../utils/format";
import { TONE_CSS_VAR } from "../utils/tone";

describe("bond analytics formatters", () => {
  describe("formatYi", () => {
    it("formats yuan string to 亿", () => {
      expect(formatYi("100000000")).toMatch(/1(\.00)?\s*亿/);
    });

    it("returns dash for invalid input", () => {
      expect(formatYi("not-a-number")).toBe(EM_DASH);
    });

    it("returns dash for nullish input", () => {
      expect(formatYi(null)).toBe(EM_DASH);
      expect(formatYi(undefined)).toBe(EM_DASH);
    });
  });

  describe("formatWan", () => {
    it("formats yuan string to 万", () => {
      expect(formatWan("10000")).toMatch(/1\s*万/);
    });

    it("returns dash for invalid input", () => {
      expect(formatWan("x")).toBe(EM_DASH);
    });

    it("returns dash for nullish input", () => {
      expect(formatWan(null)).toBe(EM_DASH);
      expect(formatWan(undefined)).toBe(EM_DASH);
    });
  });

  describe("formatPct", () => {
    it("converts decimal string to percent string", () => {
      expect(formatPct("0.0255")).toBe("2.55%");
    });

    it("returns dash for invalid input", () => {
      expect(formatPct("")).toBe(EM_DASH);
    });

    it("returns dash for nullish input", () => {
      expect(formatPct(null)).toBe(EM_DASH);
      expect(formatPct(undefined)).toBe(EM_DASH);
    });
  });

  describe("formatBp", () => {
    it("formats numeric string as bp", () => {
      expect(formatBp("12.3")).toBe("12.3 bp");
    });

    it("returns dash for invalid input", () => {
      expect(formatBp("bad")).toBe(EM_DASH);
    });

    it("returns dash for nullish input", () => {
      expect(formatBp(null)).toBe(EM_DASH);
      expect(formatBp(undefined)).toBe(EM_DASH);
    });
  });

  describe("toneColor", () => {
    it("uses China convention via theme-aware CSS vars: nonnegative red, negative green", () => {
      expect(toneColor(0)).toBe(TONE_CSS_VAR.negative);
      expect(toneColor(1)).toBe(TONE_CSS_VAR.negative);
      expect(toneColor(-0.01)).toBe(TONE_CSS_VAR.positive);
    });
  });
});
