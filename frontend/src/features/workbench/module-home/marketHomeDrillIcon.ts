const DRILL_KEY_ICONS: Record<string, string> = {
  "market-overview": "HO",
  "market-data": "MD",
  "macro-observation": "MO",
  "macro-toolkit": "MT",
  "cross-asset": "XA",
  "stock-analysis": "EQ",
  "news-events": "NE",
  "source-preview": "SP",
};

export function marketDrillIconLabel(key: string): string {
  return DRILL_KEY_ICONS[key] ?? key.slice(0, 2).toUpperCase();
}
