import { describe, expect, it } from "vitest";

import { formatMacroSignalEvidence, parseMacroSignalValue, filterCrossAssetRowsForTrader, filterCrossAssetSecondaryRows } from "./marketEvidenceVisual";
import type { ModuleHomeDetailRow } from "./moduleHomeModel";

describe("parseMacroSignalValue", () => {
  it("parses negative crisis scores", () => {
    expect(parseMacroSignalValue("宽松 · -0.2")).toEqual({
      stance: "宽松",
      score: "-0.2",
    });
  });

  it("parses positive integer scores", () => {
    expect(parseMacroSignalValue("偏松 · 78")).toEqual({
      stance: "偏松",
      score: "78",
    });
  });

  it("returns stance-only values unchanged", () => {
    expect(parseMacroSignalValue("橙色风险")).toEqual({
      stance: "橙色风险",
    });
  });
});

describe("formatMacroSignalEvidence", () => {
  it("hides raw score and regime while keeping human percentile labels", () => {
    expect(
      formatMacroSignalEvidence(["score=-0.2", "regime=宽松", "percentile=89.66%"]),
    ).toBe("历史分位 89.66%");
  });

  it("keeps readable evidence lines", () => {
    expect(formatMacroSignalEvidence(["DR007 1.82%", "score=78"])).toBe("DR007 1.82%");
  });
});

describe("filterCrossAssetRowsForTrader", () => {
  const row = (key: string, label: string): ModuleHomeDetailRow => ({
    key,
    label,
    value: "1.00",
    detail: "+1bp",
    tradeDate: "2026-06-12",
    source: "mock",
    tone: "ok",
  });

  it("prioritizes trader-relevant rows and caps total count", () => {
    const rows = [
      row("obscure-index", "冷门指数"),
      row("csi300", "沪深300"),
      row("usdcny", "USDCNY"),
      row("brent", "Brent原油"),
      row("dr007", "DR007"),
      row("nanhua", "南华商品"),
      row("hsi", "恒生指数"),
      row("spx", "标普500"),
      row("random-fx", "某小币种"),
      row("random-commod", "某商品"),
      row("another-obscure", "另一冷门"),
      row("yet-another", "再一冷门"),
    ];

    const filtered = filterCrossAssetRowsForTrader(rows);

    expect(filtered.map((item) => item.key)).toEqual([
      "dr007",
      "csi300",
      "hsi",
      "spx",
      "usdcny",
      "brent",
      "nanhua",
    ]);
  });

  it("dedupes redundant CSI300 breakdown rows while keeping price and change when available", () => {
    const rows = [
      row("csi-close", "沪深300指数收盘价"),
      row("csi-pe", "沪深300市盈率"),
      row("csi-weight", "沪深300前五大权重合计"),
      row("csi-change", "沪深300涨跌幅"),
      row("usdcny", "USDCNY"),
      row("brent", "Brent原油"),
    ];

    const filtered = filterCrossAssetRowsForTrader(rows);
    const csiKeys = filtered.filter((item) => item.key.startsWith("csi")).map((item) => item.key);

    expect(csiKeys).toEqual(expect.arrayContaining(["csi-close", "csi-change"]));
    expect(csiKeys).not.toContain("csi-pe");
    expect(filtered.some((item) => item.key === "usdcny")).toBe(true);
  });

  it("returns all rows when trader mode is disabled", () => {
    const rows = [row("a", "A"), row("b", "B")];
    expect(filterCrossAssetRowsForTrader(rows, { traderMode: false })).toEqual(rows);
  });
});

describe("filterCrossAssetSecondaryRows", () => {
  const row = (key: string, label: string): ModuleHomeDetailRow => ({
    key,
    label,
    value: "1.00",
    detail: "+1bp",
    tradeDate: "2026-06-12",
    source: "mock",
    tone: "ok",
  });

  it("excludes primary keys and returns trader-relevant secondary rows", () => {
    const rows = [
      row("dr007", "DR007"),
      row("csi300", "沪深300"),
      row("dxy", "DXY"),
      row("obscure-pe", "冷门指数市盈率"),
    ];
    const primaryKeys = new Set(["dr007", "csi300"]);

    const secondary = filterCrossAssetSecondaryRows(rows, primaryKeys);

    expect(secondary.map((item) => item.key)).toEqual(["dxy"]);
  });

  it("respects maxRows cap", () => {
    const rows = [
      row("dxy", "DXY"),
      row("hsi", "恒生指数"),
      row("spx", "标普500"),
      row("nanhua", "南华商品"),
      row("brent2", "WTI原油"),
      row("copper", "铜期货"),
      row("aluminum", "铝期货"),
    ];

    const secondary = filterCrossAssetSecondaryRows(rows, new Set(), { maxRows: 3 });

    expect(secondary).toHaveLength(3);
  });

  it("drops rows below relevance and display priority thresholds", () => {
    const rows = [row("obscure-pe", "某指数市盈率"), row("dxy", "DXY")];

    const secondary = filterCrossAssetSecondaryRows(rows, new Set());

    expect(secondary.map((item) => item.key)).toEqual(["dxy"]);
  });
});
