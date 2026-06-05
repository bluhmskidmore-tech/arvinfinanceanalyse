export const HOME_FIRST_SCREEN_FALLBACK_HEADER_STATUS = {
  dataUpdatedAt: "09:15",
  marketStatus: "市场已收盘",
  notificationCount: 12,
} as const;

export const HOME_FIRST_SCREEN_FALLBACK_REPORT_DATE = "2026-04-30";

export const HOME_FIRST_SCREEN_MARKET_PULSE_FALLBACK = [
  { id: "cgb10y", label: "10年国债", value: "1.76%", delta: "+0.02bp", deltaTone: "up" as const },
  { id: "dr007", label: "DR007", value: "1.29%", delta: "-1bp", deltaTone: "down" as const },
  { id: "slope", label: "1Y-10Y利差", value: "-26.2bp", delta: "+3bp", deltaTone: "up" as const },
  { id: "us10y", label: "美债10Y", value: "4.35%", delta: "-2.1bp", deltaTone: "down" as const },
  { id: "usdcny", label: "人民币汇率", value: "7.2431", delta: "+0.0021", deltaTone: "up" as const },
  { id: "brent", label: "原油 Brent", value: "118.26", delta: "-0.58", deltaTone: "down" as const },
  { id: "csi300", label: "A股指数 沪深300", value: "3,762.75", delta: "+0.82%", deltaTone: "up" as const },
  {
    id: "credit-spread",
    label: "信用利差 中短票AAA",
    value: "69.8bp",
    delta: "-0.6bp",
    deltaTone: "down" as const,
  },
] as const;
