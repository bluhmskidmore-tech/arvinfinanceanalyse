const LINKAGE_SUMMARY_ZH: Record<string, string> = {
  "Duration view favors adding exposure.": "久期判断偏积极，可讨论增加敞口。",
  "Duration view turns constructive as liquidity stays easy.": "流动性仍宽松，久期判断转趋积极。",
  "Curve view prefers front-end carry with selective extension.": "曲线判断偏前端票息，择机拉长。",
  "Credit view stays focused on high grade.": "信用判断聚焦高等级品种。",
  "Instrument view prefers rates plus high-grade credit.": "品种判断偏好利率与高等级信用。",
  "Prefer rates and high-grade credit over lower-quality carry.":
    "品种判断偏好利率与高等级信用，回避低质量票息。",
  "Global rates cap aggressive long-end chasing.": "全球利率制约激进拉长久期。",
};

const LINKAGE_EVIDENCE_ZH: Record<string, string> = {
  "Liquidity remains supportive.": "流动性仍偏支持。",
  "Funding stays loose.": "资金仍偏宽松。",
  "Spread beta remains controlled.": "利差 beta 仍可控。",
  "Cross-asset evidence is mixed but constructive.": "跨资产证据分化但整体偏建设性。",
  "DR007 remains contained.": "DR007 仍处可控区间。",
  "Credit beta should stay selective.": "信用 beta 宜保持精选。",
};

function normalizeLinkageCopy(value: string | null | undefined) {
  return value?.trim() ?? "";
}

function translateLinkageSummaryPattern(summary: string) {
  const equitySpread = summary.match(
    /^CSI300 equity-bond spread is ([\d.]+)ppt with CSI300 move ([+-]?[\d.]+%)\.?$/i,
  );
  if (equitySpread) {
    return `沪深300股债利差 ${equitySpread[1]}ppt，沪深300变动 ${equitySpread[2]}。`;
  }

  const megaCap = summary.match(/^CSI300 top10 weight concentration is ([\d.]+%) \(top5 ([\d.]+%)\)\.?$/i);
  if (megaCap) {
    return `沪深300前十大权重集中度 ${megaCap[1]}（前五 ${megaCap[2]}）。`;
  }

  return null;
}

export function formatCrossAssetLinkageSummary(summary: string | null | undefined): string {
  const normalized = normalizeLinkageCopy(summary);
  if (!normalized) {
    return "";
  }
  return (
    LINKAGE_SUMMARY_ZH[normalized] ??
    translateLinkageSummaryPattern(normalized) ??
    normalized
  );
}

export function formatCrossAssetLinkageEvidence(evidence: string | null | undefined): string {
  const normalized = normalizeLinkageCopy(evidence);
  if (!normalized) {
    return "";
  }
  return LINKAGE_EVIDENCE_ZH[normalized] ?? normalized;
}
