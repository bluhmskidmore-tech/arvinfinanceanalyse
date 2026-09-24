const LINKAGE_WARNING_PATTERNS: ReadonlyArray<{ pattern: RegExp; replace: string | ((match: RegExpMatchArray) => string) }> = [
  {
    pattern: /^Indicator history too short:\s*(.+)$/i,
    replace: (match) => `指标历史偏短：${formatLinkageIndicatorName(match[1])}。`,
  },
  {
    pattern: /^Indicator score unavailable:\s*(.+)$/i,
    replace: (match) => `指标暂不可用：${formatLinkageIndicatorName(match[1])}。`,
  },
  {
    pattern: /^Inflation score defaulted to 0 due to missing indicators\.?$/i,
    replace: "通胀因子缺数，评分按 0 处理。",
  },
  {
    pattern: /^风险张量使用最近日期\s+([0-9-]+)\s*，目标日期为\s+([0-9-]+)\s*。?$/,
    replace: (match) => `风险张量沿用 ${match[1]}，报告日 ${match[2]} 无更新。`,
  },
];

function formatLinkageIndicatorName(raw: string): string {
  const trimmed = raw.trim();
  const shiborMatch = trimmed.match(/^SHIBOR:(.+)$/i);
  if (shiborMatch) {
    return `Shibor ${shiborMatch[1]}`;
  }
  return trimmed;
}

export function localizeCrossAssetLinkageWarning(warning: string): string {
  const trimmed = warning.trim();
  if (!trimmed) {
    return trimmed;
  }
  for (const entry of LINKAGE_WARNING_PATTERNS) {
    const match = trimmed.match(entry.pattern);
    if (match) {
      return typeof entry.replace === "string" ? entry.replace : entry.replace(match);
    }
  }
  return trimmed;
}

export function formatCrossAssetLinkageWarnings(warnings: string[]): string[] {
  return [...new Set(warnings.map(localizeCrossAssetLinkageWarning).filter(Boolean))];
}

export function summarizeCrossAssetLinkageWarnings(warnings: string[]): string | null {
  const formatted = formatCrossAssetLinkageWarnings(warnings);
  if (formatted.length === 0) {
    return null;
  }
  if (formatted.length === 1) {
    return formatted[0];
  }
  return `${formatted[0]}；另有 ${formatted.length - 1} 项告警。`;
}
