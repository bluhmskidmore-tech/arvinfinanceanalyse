import type {
  CrossAssetResearchViewCard,
  CrossAssetTransmissionAxisRow,
} from "./crossAssetDriversPageModel";
import type { ResolvedCrossAssetKpi } from "./crossAssetKpiModel";

export type TransmissionDirection = "supportive" | "restrictive" | "neutral" | "conflicted";

export type TransmissionGraphNode = {
  key: string;
  layer: 1 | 2 | 3;
  label: string;
  /** 副标题：L1 为 stanceLabel，L2 为取值+变动，L3 为 stance/confidence */
  sub: string;
  stance: TransmissionDirection;
  summary: string;
  evidence: string[];
  source: string;
  /** L2 资产节点的取值/变动/交易日，供抽屉展示 */
  tradeDate?: string | null;
};

export type TransmissionGraphEdge = {
  from: string;
  to: string;
  dir: TransmissionDirection;
  /** 1|2|3，映射为线宽 */
  weight: 1 | 2 | 3;
  label?: string;
  /** 信号待确认 → 虚线 */
  pending?: boolean;
};

export type TransmissionChainGraph = {
  layers: [TransmissionGraphNode[], TransmissionGraphNode[], TransmissionGraphNode[]];
  edges: TransmissionGraphEdge[];
};

/* ------------------------------------------------------------------ *
 * 边推导规则（固定映射表优先于动态推导）
 *
 * L1 宏观因子 → L2 市场资产：5 轴 × 5 资产的合理默认，方向语义为
 * 「该因子走强时对该资产所在链条的固收含义」：
 *   global_rates          → y10(supportive)   全球利率锚定中债利率方向
 *                         → usdcny(restrictive) 外部利差压力经汇率传导
 *   liquidity             → dr007(neutral)    资金面直接定价，方向由评分定
 *                         → hs300(neutral)    流动性外溢至权益，间接链路
 *   equity_bond_spread    → hs300(conflicted) 股债跷跷板两端互斥
 *                         → y10(conflicted)
 *   commodities_inflation → cmdty(restrictive) 通胀/商品压力利空债券
 *                         → y10(restrictive)
 *   mega_cap_equities     → hs300(neutral)    大市值结构只影响权益内部
 *
 * L2 市场资产 → L3 组合影响（research_views 的四个判断卡）：
 *   y10    → duration, curve      利率锚直接决定久期与曲线
 *   dr007  → curve, credit        资金面决定曲线形态与信用下沉空间
 *   hs300  → duration, credit     风险偏好影响久期意愿与信用利差
 *   cmdty  → instrument           通胀压力约束品种选择
 *   usdcny → instrument           汇率约束外资流向与品种
 *   方向取 L3 节点 stance 的固收语义（bullish→supportive / bearish→restrictive /
 *   防御精选类→conflicted / 其余→neutral）。
 * ------------------------------------------------------------------ */

const L2_KEYS = ["y10", "dr007", "hs300", "cmdty", "usdcny"] as const;
type L2Key = (typeof L2_KEYS)[number];

const L2_DEFS: Record<
  L2Key,
  { label: string; kpiKeys: readonly string[] }
> = {
  y10: { label: "10Y国债收益率", kpiKeys: ["cn_gov_10y"] },
  dr007: { label: "DR007", kpiKeys: ["money_market_7d"] },
  hs300: { label: "沪深300", kpiKeys: ["csi300"] },
  cmdty: { label: "布油·螺纹", kpiKeys: ["brent", "steel"] },
  usdcny: { label: "USD·CNY", kpiKeys: ["usdcny"] },
};

/** L1→L2 固定映射表 */
const L1_TO_L2: Record<string, Array<{ to: L2Key; dir: TransmissionDirection }>> = {
  global_rates: [
    { to: "y10", dir: "supportive" },
    { to: "usdcny", dir: "restrictive" },
  ],
  liquidity: [
    { to: "dr007", dir: "neutral" },
    { to: "hs300", dir: "neutral" },
  ],
  equity_bond_spread: [
    { to: "hs300", dir: "conflicted" },
    { to: "y10", dir: "conflicted" },
  ],
  commodities_inflation: [
    { to: "cmdty", dir: "restrictive" },
    { to: "y10", dir: "restrictive" },
  ],
  mega_cap_equities: [{ to: "hs300", dir: "neutral" }],
};

/** L2→L3 固定映射表 */
const L2_TO_L3: Record<L2Key, readonly string[]> = {
  y10: ["duration", "curve"],
  dr007: ["curve", "credit"],
  hs300: ["duration", "credit"],
  cmdty: ["instrument"],
  usdcny: ["instrument"],
};

const L3_ORDER = ["duration", "curve", "credit", "instrument"] as const;

/** research_view stance → 固收组合语义 */
function l3StanceToDirection(stance: string): TransmissionDirection {
  const s = stance.toLowerCase();
  if (s.includes("bullish") || s.includes("supportive") || s.includes("favorable") || s.includes("add")) {
    return "supportive";
  }
  if (s.includes("bearish") || s.includes("restrictive") || s.includes("cap")) {
    return "restrictive";
  }
  if (
    s.includes("conflicted") ||
    s.includes("defensive") ||
    s.includes("selective") ||
    s.includes("mixed") ||
    s.includes("barbell")
  ) {
    return "conflicted";
  }
  return "neutral";
}

function normalizeAxisStance(stance: string): TransmissionDirection {
  const s = stance.toLowerCase();
  if (s.includes("supportive")) return "supportive";
  if (s.includes("restrictive")) return "restrictive";
  if (s.includes("conflicted")) return "conflicted";
  return "neutral";
}

/** 轴 stance 调强/调弱 → 线宽 */
function weightFromStance(stance: TransmissionDirection): 1 | 2 | 3 {
  if (stance === "conflicted") return 3;
  if (stance === "neutral") return 1;
  return 2;
}

function findKpi(kpis: ResolvedCrossAssetKpi[], key: string): ResolvedCrossAssetKpi | undefined {
  return kpis.find((kpi) => kpi.key === key);
}

function buildL2Node(kpis: ResolvedCrossAssetKpi[], key: L2Key): TransmissionGraphNode {
  const def = L2_DEFS[key];
  const resolved = def.kpiKeys
    .map((kpiKey) => findKpi(kpis, kpiKey))
    .filter((kpi): kpi is ResolvedCrossAssetKpi => Boolean(kpi));
  const parts = resolved
    .map((kpi) => `${kpi.valueLabel} ${kpi.changeLabel}`.trim())
    .filter(Boolean);
  const tradeDates = resolved.map((kpi) => kpi.tradeDate).filter((d): d is string => Boolean(d));
  const tradeDate = tradeDates.length > 0 ? tradeDates.sort((a, b) => b.localeCompare(a))[0] : null;
  return {
    key,
    layer: 2,
    label: def.label,
    sub: parts.join(" / ") || "待接入",
    stance: "neutral",
    summary: parts.length > 0 ? `${def.label}：${parts.join(" / ")}` : `${def.label}数据待接入。`,
    evidence: resolved.map((kpi) => `${kpi.label} ${kpi.valueLabel}（${kpi.changeLabel}）`),
    source: resolved.some((kpi) => kpi.sourceKind !== "missing") ? "backend" : "unavailable",
    tradeDate,
  };
}

export function buildTransmissionChainGraph(input: {
  transmissionAxisRows: CrossAssetTransmissionAxisRow[];
  kpis: ResolvedCrossAssetKpi[];
  researchViewCards: CrossAssetResearchViewCard[];
}): TransmissionChainGraph {
  const { transmissionAxisRows, kpis, researchViewCards } = input;

  const l1Nodes: TransmissionGraphNode[] = transmissionAxisRows.map((axis) => ({
    key: axis.axisKey,
    layer: 1,
    label: axis.label,
    sub: axis.stanceLabel || axis.stance,
    stance: normalizeAxisStance(axis.stance),
    summary: axis.summary,
    evidence: [...axis.impactedViews.map((view) => `影响判断：${view}`), ...axis.warnings],
    source: axis.source,
  }));

  const l2Nodes: TransmissionGraphNode[] = L2_KEYS.map((key) => buildL2Node(kpis, key));

  const l3ByKey = new Map(researchViewCards.map((card) => [card.key, card]));
  const l3Nodes: TransmissionGraphNode[] = L3_ORDER.map((key) => {
    const card = l3ByKey.get(key);
    if (!card) {
      return {
        key,
        layer: 3,
        label: key,
        sub: "待接入",
        stance: "neutral" as const,
        summary: "该判断卡暂未生成。",
        evidence: [],
        source: "unavailable",
      };
    }
    return {
      key: card.key,
      layer: 3 as const,
      label: card.label,
      sub: `${card.stance} · ${card.confidence}`,
      stance: l3StanceToDirection(card.stance),
      summary: card.summary,
      evidence: card.evidence,
      source: card.source,
    };
  });

  const edges: TransmissionGraphEdge[] = [];

  // L1→L2：固定映射表；轴为 pending_signal 时整条边透传 pending（虚线）
  for (const axis of transmissionAxisRows) {
    const mapping = L1_TO_L2[axis.axisKey];
    if (!mapping) continue;
    const pending = axis.status !== "ready";
    for (const { to, dir } of mapping) {
      edges.push({
        from: axis.axisKey,
        to,
        dir,
        weight: weightFromStance(dir),
        pending,
      });
    }
  }

  // L2→L3：固定映射表；方向取 L3 stance 的固收语义；判断卡 pending 时虚线
  for (const l2Key of L2_KEYS) {
    for (const l3Key of L2_TO_L3[l2Key]) {
      const card = l3ByKey.get(l3Key);
      const dir = card ? l3StanceToDirection(card.stance) : "neutral";
      edges.push({
        from: l2Key,
        to: l3Key,
        dir,
        weight: weightFromStance(dir),
        pending: !card || card.status !== "ready",
      });
    }
  }

  return { layers: [l1Nodes, l2Nodes, l3Nodes], edges };
}
