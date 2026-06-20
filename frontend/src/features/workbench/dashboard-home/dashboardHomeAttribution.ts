export type HomeWaterfallItem = {
  id: string;
  label: string;
  value: string;
  tone: "positive" | "negative" | "neutral" | "warning";
};

function parseWaterfallNumeric(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed || trimmed === "—" || trimmed === "--") {
    return null;
  }
  const parsed = Number(trimmed.replace(/,/g, "").replace(/[^\d.-]/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function isAttributionSegment(item: HomeWaterfallItem): boolean {
  const label = item.label.trim();
  return label !== "期初" && label !== "期末" && !label.includes("合计") && item.id !== "total";
}

export function findAttributionExtremes(waterfall: readonly HomeWaterfallItem[]): {
  maxDrag: HomeWaterfallItem | null;
  maxContribution: HomeWaterfallItem | null;
} {
  let maxDrag: HomeWaterfallItem | null = null;
  let maxDragValue = 0;
  let maxContribution: HomeWaterfallItem | null = null;
  let maxContributionValue = 0;

  for (const item of waterfall) {
    if (!isAttributionSegment(item)) {
      continue;
    }
    const numeric = parseWaterfallNumeric(item.value);
    if (numeric == null) {
      continue;
    }
    if (numeric < 0 && (maxDrag == null || numeric < maxDragValue)) {
      maxDrag = item;
      maxDragValue = numeric;
    }
    if (numeric > 0 && (maxContribution == null || numeric > maxContributionValue)) {
      maxContribution = item;
      maxContributionValue = numeric;
    }
  }

  return { maxDrag, maxContribution };
}
