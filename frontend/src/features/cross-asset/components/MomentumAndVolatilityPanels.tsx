import { Suspense } from "react";
import { designTokens, nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { LazyCrossAssetECharts } from "./CrossAssetECharts";
import "./MomentumAndVolatilityPanels.css";
import {
  TREND_GROUPS,
  EQUITY_BOND_SPREAD_NARROW_MAX_PCT,
  EQUITY_BOND_SPREAD_WIDE_MIN_PCT,
  type EquityBondERP,
  type MomentumRow,
  type TrendGroupKey,
  type VolatilityAlert,
} from "../lib/crossAssetAnalytics";

/**
 * 相关矩阵 / 动量 / ERP 由前端基于已加载行情序列派生（crossAssetAnalytics），
 * 属分析口径展示辅助，不替代正式指标；对应展示区必须携带本标注。
 */
export function FrontendAnalyticsChip() {
  return (
    <span
      className="ca-term-chip ca-term-chip--info"
      data-testid="cross-asset-frontend-analytics-chip"
      title="本区数值由前端基于已加载行情序列计算，属分析口径，不替代正式指标。"
    >
      分析口径 · 前端计算（非正式指标）
    </span>
  );
}

/** 方向枚举中文映射（up/down/flat 为前端派生方向，非后端枚举）。 */
const MOMENTUM_DIRECTION_LABELS: Record<MomentumRow["direction"], string> = {
  up: "上行",
  down: "下行",
  flat: "持平",
};

export function MomentumScoreboardPanel({ rows }: { rows: MomentumRow[] }) {
  const colors = nocturneTokens.color;
  const extent = Math.max(1, ...rows.map((row) => Math.abs(row.chg5d ?? 0)));
  const categories = rows.map((row) => row.key);
  const categoryAxis = {
    type: "category", inverse: true, data: categories,
    axisLine: { show: false }, axisTick: { show: false },
  };
  const option = {
    animation: false,
    grid: { left: 166, right: 132, top: 8, bottom: 28 },
    xAxis: { type: "value", min: -extent, max: extent, splitNumber: 2,
      axisLabel: { color: colors.inkMuted, formatter: (value: number) => `${value.toFixed(1)}%` },
      splitLine: { lineStyle: { color: colors.lineSoft } } },
    yAxis: [
      { ...categoryAxis, axisLabel: { color: colors.inkSoft, fontSize: 12, width: 154,
        overflow: "truncate", formatter: (_: string, index: number) => rows[index].label } },
      { ...categoryAxis, position: "right", axisLabel: { color: colors.ink, fontSize: 12,
        fontFamily: designTokens.fontFamily.tabular, margin: 12,
        formatter: (_: string, index: number) => rows[index].chg5d == null ? EM_DASH : `${rows[index].chg5d!.toFixed(2)}%` } },
      { ...categoryAxis, position: "right", offset: 80, axisLabel: { color: colors.inkSoft, fontSize: 12,
        formatter: (_: string, index: number) => MOMENTUM_DIRECTION_LABELS[rows[index].direction] } },
    ],
    series: [{ type: "bar", barWidth: 8, data: rows.map((row) => row.chg5d),
      itemStyle: { color: colors.blue } }],
  };
  return (
    <section className="ca-momentum" data-testid="cross-asset-momentum-scoreboard">
      <header>
        <span>动量</span>
        <FrontendAnalyticsChip />
        <strong>{rows.length} 项</strong>
      </header>
      <p className="ca-analytics-note">区间变动取最近 5 个观测间隔，不足时取已有窗口；方向取最近 1 个间隔。利率项展示相对变动百分比，不是基点。</p>
      {rows.length > 0 ? <div className="ca-momentum__chart-scroll">
        <div className="ca-momentum__chart" role="img" aria-label="资产区间变动条形图，详细数值见下方明细">
          <div className="ca-momentum__columns"><span>资产</span><span>区间变动</span><span>变动（%）</span><span>最新方向</span></div>
          <Suspense fallback={<p className="ca-analytics-loading">正在加载动量图…</p>}>
            <LazyCrossAssetECharts option={option} style={{ height: rows.length * 28 + 36 }} />
          </Suspense>
        </div>
      </div> : <p className="ca-analytics-note">暂无可用动量数据。</p>}
      <details className="ca-analytics-details">
        <summary>动量数值明细 <span>{rows.length} 项</span></summary>
        <div className="cross-asset-momentum-table-wrap" data-testid="cross-asset-momentum-table-wrap">
        <table>
          <thead><tr><th scope="col">资产</th><th scope="col">区间变动（%）</th><th scope="col">最新方向</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td>{row.chg5d == null ? EM_DASH : `${row.chg5d.toFixed(2)}%`}</td>
                <td>{MOMENTUM_DIRECTION_LABELS[row.direction] ?? row.direction}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </details>
    </section>
  );
}

export function TrendGroupToggle({
  active,
  onChange,
}: {
  active: TrendGroupKey;
  onChange: (group: TrendGroupKey) => void;
}) {
  return (
    <div className="cross-asset-trend-groups" data-testid="cross-asset-trend-groups" role="tablist" aria-label="走势分组">
      {TREND_GROUPS.map((group) => (
        <button
          key={group.key}
          type="button"
          role="tab"
          aria-selected={active === group.key}
          onClick={() => onChange(group.key)}
        >
          {group.label}
        </button>
      ))}
    </div>
  );
}

export function VolatilityClusteringPanel({ alert }: { alert: VolatilityAlert }) {
  const assetLabel = (asset: VolatilityAlert["assets"][number]) => {
    if (asset.label) return asset.label;
    if (asset.key === "usdcny") return "USD/CNY";
    if (asset.key === "gov_spread") return "中美10Y利差";
    if (asset.key === "cn_gov_10y") return "10Y国债";
    if (asset.key === "money_market_7d") return "DR007";
    if (asset.key === "csi300") return "沪深300";
    return asset.key;
  };
  const sortedAssets = [...alert.assets].sort((left, right) => Number(right.isElevated) - Number(left.isElevated));
  const elevatedAssets = sortedAssets.filter((asset) => asset.isElevated);

  return (
    <section className="ca-vol-alert" data-severity={alert.severity} data-testid="cross-asset-volatility-clustering">
      <header>
        <span>波动聚集</span>
        <strong>{alert.totalAssets === 0 ? "暂无足够观测数据" : alert.headline}</strong>
      </header>
      {elevatedAssets.length > 0 && <p className="ca-vol-alert__exceptions">波动偏高：{elevatedAssets.map(assetLabel).join("、")}</p>}
      {sortedAssets.length > 0 && <details className="ca-analytics-details">
        <summary data-testid="cross-asset-vol-folded-assets">波动明细 <span>{sortedAssets.length} 项资产</span></summary>
        <p className="ca-analytics-note">比值为近期窗口波动率与完整窗口波动率之比。</p>
        <div className="ca-analytics-table-scroll"><table>
          <thead><tr><th scope="col">资产</th><th scope="col">波动比值</th><th scope="col">状态</th></tr></thead>
          <tbody>{sortedAssets.map((asset) => <tr key={asset.key}>
            <td>{assetLabel(asset)}</td><td>{asset.volRatio.toFixed(2)}x</td>
            <td className={asset.isElevated ? "ca-vol-alert__elevated" : undefined}>{asset.isElevated ? "波动偏高" : "常规波动"}</td>
          </tr>)}</tbody>
        </table></div>
      </details>}
    </section>
  );
}

export function EquityBondERPPanel({ erp }: { erp: EquityBondERP }) {
  const value = erp.erpPct;
  const colors = nocturneTokens.color;
  const min = Math.min(0, value ?? 0) - 0.5;
  const max = Math.max(EQUITY_BOND_SPREAD_WIDE_MIN_PCT, value ?? 0) + 1;
  const option = {
    animation: false,
    grid: { left: 24, right: 36, top: 36, bottom: 40 },
    xAxis: { type: "value", min, max, axisLabel: { show: false }, splitLine: { show: false } },
    yAxis: { type: "value", min: -1, max: 1, show: false },
    series: [
      { type: "line", data: [[min, 0], [max, 0]], symbol: "none", lineStyle: { color: colors.line, width: 4 }, silent: true },
      { type: "scatter", data: [EQUITY_BOND_SPREAD_NARROW_MAX_PCT, EQUITY_BOND_SPREAD_WIDE_MIN_PCT].map(v => [v, 0]),
        symbol: "rect", symbolSize: [2, 16], itemStyle: { color: colors.inkMuted },
        label: { show: true, position: "bottom", distance: 10, color: colors.inkMuted,
          formatter: (params: { value: number[] }) => `阈值\n${params.value[0].toFixed(2)}%` } },
      { type: "scatter", data: [[value, 0]], symbolSize: 12, itemStyle: { color: colors.blue },
        label: { show: true, position: "top", distance: 10, color: colors.ink,
          formatter: `当前 ${value?.toFixed(2)}%` } },
    ],
  };
  return (
    <section className="ca-erp-panel" data-testid="cross-asset-equity-bond-erp">
      <span>
        股债 ERP <FrontendAnalyticsChip />
      </span>
      <span data-testid="cross-asset-erp-verdict">
        <strong>{erp.verdictLabel}</strong>{" "}
        <span className="ca-term-chip ca-term-chip--info" data-testid="cross-asset-erp-caliber">
          {erp.caliberLabel}
        </span>
      </span>
      {erp.available && value != null && <div className="ca-erp-panel__scale" role="img"
        aria-label={`ERP 当前 ${value.toFixed(2)}%，分档阈值 ${EQUITY_BOND_SPREAD_NARROW_MAX_PCT.toFixed(2)}% 和 ${EQUITY_BOND_SPREAD_WIDE_MIN_PCT.toFixed(2)}%`}>
        <Suspense fallback={<p className="ca-analytics-loading">正在加载股债 ERP 刻度…</p>}>
          <LazyCrossAssetECharts option={option} className="ca-erp-panel__chart" />
        </Suspense>
      </div>}
      <p>{erp.verdictDescription}</p>
    </section>
  );
}
