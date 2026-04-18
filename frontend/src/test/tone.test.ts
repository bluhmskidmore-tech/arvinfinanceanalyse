import { describe, expect, it } from "vitest";

import { TONE_COLOR, toneForStatus, toneFromNumeric, type Tone } from "../utils/tone";
import type { Numeric } from "../api/contracts";

describe("TONE_COLOR", () => {
  it("has all 4 tones", () => {
    const tones: Tone[] = ["positive", "neutral", "warning", "negative"];
    for (const t of tones) {
      expect(typeof TONE_COLOR[t]).toBe("string");
      expect(TONE_COLOR[t]).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  });

  it("positive is green family, negative is red family (not swapped!)", () => {
    expect(TONE_COLOR.positive).toMatch(/^#(2f|1[0-5]|2[0-4]).{4}/);
    expect(TONE_COLOR.negative).toMatch(/^#(c[0-5]|b[0-5]|d[0-5]).{4}/i);
  });
});

describe("toneFromNumeric", () => {
  it("positive raw with sign_aware=true -> positive", () => {
    const n: Numeric = {
      raw: 12.5,
      unit: "yuan",
      display: "+12.5",
      precision: 2,
      sign_aware: true,
    };
    expect(toneFromNumeric(n)).toBe("positive");
  });

  it("negative raw with sign_aware=true -> negative", () => {
    const n: Numeric = {
      raw: -12.5,
      unit: "yuan",
      display: "-12.5",
      precision: 2,
      sign_aware: true,
    };
    expect(toneFromNumeric(n)).toBe("negative");
  });

  it("zero raw with sign_aware=true -> neutral", () => {
    const n: Numeric = {
      raw: 0,
      unit: "yuan",
      display: "0.00",
      precision: 2,
      sign_aware: true,
    };
    expect(toneFromNumeric(n)).toBe("neutral");
  });

  it("null raw -> neutral", () => {
    const n: Numeric = {
      raw: null,
      unit: "yuan",
      display: "—",
      precision: 2,
      sign_aware: true,
    };
    expect(toneFromNumeric(n)).toBe("neutral");
  });

  it("sign_aware=false -> neutral (不参与正负渲染)", () => {
    const n: Numeric = {
      raw: -12.5,
      unit: "ratio",
      display: "12.5",
      precision: 2,
      sign_aware: false,
    };
    expect(toneFromNumeric(n)).toBe("neutral");
  });
});

describe("toneForStatus", () => {
  it("maps 'ok' -> positive", () => {
    expect(toneForStatus("ok")).toBe("positive");
  });

  it("maps 'stable' -> positive", () => {
    expect(toneForStatus("stable")).toBe("positive");
  });

  it("maps 'warning' -> warning", () => {
    expect(toneForStatus("warning")).toBe("warning");
  });

  it("maps 'stale' -> warning", () => {
    expect(toneForStatus("stale")).toBe("warning");
  });

  it("maps 'watch' -> warning", () => {
    expect(toneForStatus("watch")).toBe("warning");
  });

  it("maps 'error' -> negative", () => {
    expect(toneForStatus("error")).toBe("negative");
  });

  it("maps 'vendor_unavailable' -> negative", () => {
    expect(toneForStatus("vendor_unavailable")).toBe("negative");
  });

  it("unknown string -> neutral", () => {
    expect(toneForStatus("unknown_status_xyz")).toBe("neutral");
  });
});
