import { describe, expect, it } from "vitest";

import type {
  CrossAssetResearchViewCard,
  CrossAssetTransmissionAxisRow,
} from "./crossAssetDriversPageModel";
import type { ResolvedCrossAssetKpi } from "./crossAssetKpiModel";
import { buildTransmissionChainGraph } from "./crossAssetTransmissionGraph";

function makeAxis(overrides: Partial<CrossAssetTransmissionAxisRow> = {}): CrossAssetTransmissionAxisRow {
  return {
    axisKey: "global_rates",
    label: "全球利率",
    status: "ready",
    stance: "supportive",
    stanceLabel: "偏宽松",
    summary: "利率方向信号偏宽松，对拉长久期风险有支撑。",
    impactedViews: ["duration", "curve"],
    requiredSeriesIds: [],
    warnings: [],
    source: "backend",
    ...overrides,
  };
}

function makeKpi(overrides: Partial<ResolvedCrossAssetKpi> = {}): ResolvedCrossAssetKpi {
  return {
    key: "cn_gov_10y",
    label: "10Y国债",
    format: "percent",
    tag: "利率锚",
    resolvedSeriesId: "E1000180",
    sourceKind: "choice",
    tradeDate: "2026-07-22",
    unit: "%",
    valueLabel: "1.68%",
    changeLabel: "-2.0bp",
    changeTone: "positive",
    sparkline: [],
    ...overrides,
  };
}

function makeCard(overrides: Partial<CrossAssetResearchViewCard> = {}): CrossAssetResearchViewCard {
  return {
    key: "duration",
    label: "久期判断",
    stance: "conflicted",
    confidence: "high",
    summary: "利率方向与通胀/商品压力在久期上存在冲突。",
    status: "ready",
    affectedTargets: ["rates"],
    evidence: ["利率方向评分 -0.30"],
    source: "backend",
    ...overrides,
  };
}

const ALL_AXES: CrossAssetTransmissionAxisRow[] = [
  makeAxis(),
  makeAxis({ axisKey: "liquidity", label: "流动性", stance: "neutral" }),
  makeAxis({ axisKey: "equity_bond_spread", label: "股债相对估值", stance: "conflicted" }),
  makeAxis({ axisKey: "commodities_inflation", label: "商品与通胀", stance: "restrictive" }),
  makeAxis({ axisKey: "mega_cap_equities", label: "大市值结构", stance: "neutral" }),
];

const ALL_CARDS: CrossAssetResearchViewCard[] = [
  makeCard(),
  makeCard({ key: "curve", label: "曲线判断", stance: "neutral" }),
  makeCard({ key: "credit", label: "信用判断", stance: "bearish", summary: "高等级信用宜守势。" }),
  makeCard({ key: "instrument", label: "品种判断", stance: "balanced" }),
];

describe("buildTransmissionChainGraph 层结构", () => {
  it("输出三层：5 轴 / 5 资产 / 4 判断卡，节点字段完整", () => {
    const graph = buildTransmissionChainGraph({
      transmissionAxisRows: ALL_AXES,
      kpis: [makeKpi()],
      researchViewCards: ALL_CARDS,
    });

    expect(graph.layers).toHaveLength(3);
    expect(graph.layers[0]).toHaveLength(5);
    expect(graph.layers[1]).toHaveLength(5);
    expect(graph.layers[2]).toHaveLength(4);

    const l2Keys = graph.layers[1].map((node) => node.key);
    expect(l2Keys).toEqual(["y10", "dr007", "hs300", "cmdty", "usdcny"]);

    const y10 = graph.layers[1][0];
    expect(y10.label).toBe("10Y国债收益率");
    expect(y10.sub).toContain("1.68%");
    expect(y10.tradeDate).toBe("2026-07-22");

    const duration = graph.layers[2][0];
    expect(duration.stance).toBe("conflicted");
    expect(duration.summary).toContain("冲突");

    for (const node of [...graph.layers[0], ...graph.layers[1], ...graph.layers[2]]) {
      expect(node).toMatchObject({
        key: expect.any(String),
        label: expect.any(String),
        sub: expect.any(String),
        stance: expect.any(String),
        summary: expect.any(String),
        source: expect.any(String),
      });
      expect(Array.isArray(node.evidence)).toBe(true);
    }
  });
});

describe("buildTransmissionChainGraph 边映射表", () => {
  const graph = buildTransmissionChainGraph({
    transmissionAxisRows: ALL_AXES,
    kpis: [],
    researchViewCards: ALL_CARDS,
  });

  it("L1→L2 固定映射：global_rates→y10(supportive)/usdcny(restrictive)", () => {
    expect(graph.edges).toContainEqual({ from: "global_rates", to: "y10", dir: "supportive", weight: 2, pending: false });
    expect(graph.edges).toContainEqual({ from: "global_rates", to: "usdcny", dir: "restrictive", weight: 2, pending: false });
  });

  it("L1→L2 固定映射：liquidity / equity_bond_spread / commodities_inflation / mega_cap_equities", () => {
    expect(graph.edges).toContainEqual({ from: "liquidity", to: "dr007", dir: "neutral", weight: 1, pending: false });
    expect(graph.edges).toContainEqual({ from: "liquidity", to: "hs300", dir: "neutral", weight: 1, pending: false });
    expect(graph.edges).toContainEqual({ from: "equity_bond_spread", to: "hs300", dir: "conflicted", weight: 3, pending: false });
    expect(graph.edges).toContainEqual({ from: "equity_bond_spread", to: "y10", dir: "conflicted", weight: 3, pending: false });
    expect(graph.edges).toContainEqual({ from: "commodities_inflation", to: "cmdty", dir: "restrictive", weight: 2, pending: false });
    expect(graph.edges).toContainEqual({ from: "commodities_inflation", to: "y10", dir: "restrictive", weight: 2, pending: false });
    expect(graph.edges).toContainEqual({ from: "mega_cap_equities", to: "hs300", dir: "neutral", weight: 1, pending: false });
  });

  it("L2→L3 固定映射：y10→duration,curve；dr007→curve,credit；hs300→duration,credit；cmdty/usdcny→instrument", () => {
    const pairs = graph.edges.filter((edge) => ["y10", "dr007", "hs300", "cmdty", "usdcny"].includes(edge.from));
    const byPair = new Set(pairs.map((edge) => `${edge.from}->${edge.to}`));
    for (const expected of [
      "y10->duration",
      "y10->curve",
      "dr007->curve",
      "dr007->credit",
      "hs300->duration",
      "hs300->credit",
      "cmdty->instrument",
      "usdcny->instrument",
    ]) {
      expect(byPair.has(expected)).toBe(true);
    }
    // L3 方向取 stance 固收语义：duration=conflicted、credit=bearish→restrictive
    expect(pairs.find((edge) => edge.from === "y10" && edge.to === "duration")?.dir).toBe("conflicted");
    expect(pairs.find((edge) => edge.from === "dr007" && edge.to === "credit")?.dir).toBe("restrictive");
  });
});

describe("buildTransmissionChainGraph pending 透传", () => {
  it("轴为 pending_signal 时其 L1→L2 边为 pending", () => {
    const graph = buildTransmissionChainGraph({
      transmissionAxisRows: [makeAxis({ status: "pending_signal" })],
      kpis: [],
      researchViewCards: ALL_CARDS,
    });
    const axisEdges = graph.edges.filter((edge) => edge.from === "global_rates");
    expect(axisEdges.length).toBeGreaterThan(0);
    expect(axisEdges.every((edge) => edge.pending === true)).toBe(true);
  });

  it("判断卡为 pending_signal 或缺失时其 L2→L3 边为 pending", () => {
    const graph = buildTransmissionChainGraph({
      transmissionAxisRows: ALL_AXES,
      kpis: [],
      researchViewCards: [makeCard({ key: "credit", status: "pending_signal" })],
    });
    const creditEdges = graph.edges.filter((edge) => edge.to === "credit");
    expect(creditEdges.length).toBe(2);
    expect(creditEdges.every((edge) => edge.pending === true)).toBe(true);
    const durationEdges = graph.edges.filter((edge) => edge.to === "duration");
    expect(durationEdges.every((edge) => edge.pending === true)).toBe(true);
  });
});

describe("buildTransmissionChainGraph 空输入", () => {
  it("axes/cards 为空时仍输出完整 L2 层与 L2→L3 pending 边，L1 边为空", () => {
    const graph = buildTransmissionChainGraph({
      transmissionAxisRows: [],
      kpis: [],
      researchViewCards: [],
    });
    expect(graph.layers[0]).toHaveLength(0);
    expect(graph.layers[1]).toHaveLength(5);
    expect(graph.layers[2]).toHaveLength(4);
    expect(graph.layers[1].every((node) => node.sub === "待接入")).toBe(true);
    expect(graph.edges.filter((edge) => edge.from === "global_rates")).toHaveLength(0);
    expect(graph.edges).toHaveLength(8);
    expect(graph.edges.every((edge) => edge.pending === true)).toBe(true);
  });
});
