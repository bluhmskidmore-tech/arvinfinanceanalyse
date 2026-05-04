import type { ChoiceMacroLatestPoint, ChoiceMacroRecentPoint } from "./contracts";

function buildMockChoiceMacroRecentPoints(
  endDate: string,
  count: number,
  finalValue: number,
  amplitude: number,
  lineage: Pick<ChoiceMacroRecentPoint, "source_version" | "vendor_version">,
): ChoiceMacroRecentPoint[] {
  const out: ChoiceMacroRecentPoint[] = [];
  for (let i = 0; i < count; i++) {
    const dayOffset = -(count - 1 - i);
    const d = new Date(`${endDate}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() + dayOffset);
    const trade_date = d.toISOString().slice(0, 10);
    const t = count > 1 ? i / (count - 1) : 1;
    const wobble = Math.sin(i * 0.8 + amplitude) * amplitude * 0.15;
    const value_numeric = Number((finalValue + (t - 1) * amplitude * 0.35 + wobble).toFixed(4));
    out.push({
      trade_date,
      value_numeric,
      source_version: lineage.source_version,
      vendor_version: lineage.vendor_version,
      quality_flag: "ok",
    });
  }
  out[out.length - 1] = {
    ...out[out.length - 1],
    value_numeric: finalValue,
  };
  return out;
}

export const MOCK_CHOICE_MACRO_TUSHARE_EQUITY_SERIES: ChoiceMacroLatestPoint[] = [
  {
    series_id: "CA.CSI300",
    series_name: "沪深300指数收盘价",
    trade_date: "2026-04-10",
    value_numeric: 4102.25,
    frequency: "daily",
    unit: "index",
    source_version: "sv_tushare_index_daily_mock",
    vendor_version: "vv_tushare_index_daily_000300SH_20260410",
    vendor_name: "tushare",
    refresh_tier: "stable",
    fetch_mode: "latest",
    fetch_granularity: "batch",
    policy_note: "Tushare index_daily supplement for CSI300 cross-asset risk sentiment",
    latest_change: 17.13,
    recent_points: buildMockChoiceMacroRecentPoints("2026-04-10", 20, 4102.25, 45, {
      source_version: "sv_tushare_index_daily_mock",
      vendor_version: "vv_tushare_index_daily_000300SH_20260410",
    }),
  },
  {
    series_id: "CA.CSI300_PE",
    series_name: "沪深300市盈率",
    trade_date: "2026-04-10",
    value_numeric: 14.64,
    frequency: "daily",
    unit: "x",
    source_version: "sv_tushare_index_dailybasic_mock",
    vendor_version: "vv_tushare_index_dailybasic_000300SH_20260410",
    vendor_name: "tushare",
    refresh_tier: "stable",
    fetch_mode: "latest",
    fetch_granularity: "batch",
    policy_note: "Tushare index_dailybasic PE supplement for CSI300 equity-bond spread",
    latest_change: 0.22,
    recent_points: buildMockChoiceMacroRecentPoints("2026-04-10", 20, 14.64, 0.4, {
      source_version: "sv_tushare_index_dailybasic_mock",
      vendor_version: "vv_tushare_index_dailybasic_000300SH_20260410",
    }),
  },
  {
    series_id: "CA.MEGA_CAP_WEIGHT",
    series_name: "沪深300前十大权重合计",
    trade_date: "2026-04-10",
    value_numeric: 18.4,
    frequency: "daily",
    unit: "%",
    source_version: "sv_tushare_index_weight_mock",
    vendor_version: "vv_tushare_index_weight_000300SH_20260410",
    vendor_name: "tushare",
    refresh_tier: "stable",
    fetch_mode: "latest",
    fetch_granularity: "batch",
    policy_note: "Tushare index_weight top10 concentration supplement for mega-cap equity leadership",
    latest_change: 0.35,
    recent_points: buildMockChoiceMacroRecentPoints("2026-04-10", 20, 18.4, 0.7, {
      source_version: "sv_tushare_index_weight_mock",
      vendor_version: "vv_tushare_index_weight_000300SH_20260410",
    }),
  },
  {
    series_id: "CA.MEGA_CAP_TOP5_WEIGHT",
    series_name: "沪深300前五大权重合计",
    trade_date: "2026-04-10",
    value_numeric: 13.7,
    frequency: "daily",
    unit: "%",
    source_version: "sv_tushare_index_weight_mock",
    vendor_version: "vv_tushare_index_weight_000300SH_20260410",
    vendor_name: "tushare",
    refresh_tier: "stable",
    fetch_mode: "latest",
    fetch_granularity: "batch",
    policy_note: "Tushare index_weight top5 concentration supplement for mega-cap equity leadership",
    latest_change: 0.28,
    recent_points: buildMockChoiceMacroRecentPoints("2026-04-10", 20, 13.7, 0.5, {
      source_version: "sv_tushare_index_weight_mock",
      vendor_version: "vv_tushare_index_weight_000300SH_20260410",
    }),
  },
];
