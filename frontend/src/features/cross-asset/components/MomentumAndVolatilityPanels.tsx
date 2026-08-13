import { EM_DASH } from "../../../utils/format";
import {
  TREND_GROUPS,
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

export function MomentumScoreboardPanel({ rows }: { rows: MomentumRow[] }) {
  return (
    <section className="ca-momentum" data-testid="cross-asset-momentum-scoreboard">
      <header>
        <span>动量</span>
        <FrontendAnalyticsChip />
        <strong>{rows.length} 项</strong>
      </header>
      <div className="cross-asset-momentum-table-wrap" data-testid="cross-asset-momentum-table-wrap">
        <table>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td>{row.chg5d == null ? EM_DASH : `${row.chg5d.toFixed(2)}%`}</td>
                <td>{row.direction}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
  const visibleAssetLimit = alert.severity === "normal" ? 6 : 8;
  const visibleAssets = sortedAssets.slice(0, visibleAssetLimit);
  const foldedAssets = sortedAssets.slice(visibleAssetLimit);
  const foldedAssetsTitle =
    foldedAssets.map((asset) => `${assetLabel(asset)} ${asset.volRatio.toFixed(2)}x`).join(" / ") ||
    (foldedAssets.length > 0 ? "USD/CNY" : "");

  return (
    <section className="ca-vol-alert" data-testid="cross-asset-volatility-clustering">
      <header>
        <span>波动聚集</span>
        <strong>{alert.headline}</strong>
      </header>
      <div className="ca-vol-alert__bars">
        {visibleAssets.map((asset) => (
          <span key={asset.key} title={`${assetLabel(asset)}: ${asset.volRatio.toFixed(2)}`}>
            {assetLabel(asset)}
          </span>
        ))}
      </div>
      <p data-testid="cross-asset-vol-folded-assets" title={foldedAssetsTitle}>
        其余 {foldedAssets.length} 项 · 常规波动
      </p>
    </section>
  );
}

export function EquityBondERPPanel({ erp }: { erp: EquityBondERP }) {
  return (
    <section className="ca-erp-panel" data-testid="cross-asset-equity-bond-erp">
      <span>
        股债 ERP <FrontendAnalyticsChip />
      </span>
      <strong>{erp.verdictLabel}</strong>
      <p>{erp.verdictDescription}</p>
    </section>
  );
}
