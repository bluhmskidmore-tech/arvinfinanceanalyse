/** 利率走势：国债 10Y / 国开 5Y / SHIBOR 隔夜（Choice series_id） */
export const RATE_TREND_DEFINITIONS = [
  { series_id: "EMM00166466", name: "国债 10Y" },
  { series_id: "EMM00166462", name: "国开 5Y" },
  { series_id: "EMM00166252", name: "SHIBOR 隔夜" },
] as const;
