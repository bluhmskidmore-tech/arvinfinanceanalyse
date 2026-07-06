import { useMemo } from "react";

import { computeSparklinePercentile } from "../lib/crossAssetAnalytics";
import type { ResolvedCrossAssetKpi } from "../lib/crossAssetKpiModel";

type CrossAssetEvidenceGroupConfig = {
  key: "rates_liquidity" | "equity_risk" | "commodity_inflation" | "fx_spread";
  title: string;
  cue: string;
  digest: string;
  summary: string;
  kpiKeys: string[];
};

const CROSS_ASSET_EVIDENCE_GROUPS: CrossAssetEvidenceGroupConfig[] = [
  {
    key: "rates_liquidity",
    title: "利率与流动性",
    cue: "债券锚",
    digest: "久期空间",
    summary: "先看长端约束和资金锚，判断债券方向是否有顺风。",
    kpiKeys: ["cn_gov_10y", "us_gov_10y", "money_market_7d"],
  },
  {
    key: "equity_risk",
    title: "权益风险偏好",
    cue: "风险偏好",
    digest: "风险约束",
    summary: "用指数、估值和权重结构判断风险偏好是否挤压债券。",
    kpiKeys: ["financial_conditions", "csi300_pe", "mega_cap_weight", "mega_cap_top5_weight"],
  },
  {
    key: "commodity_inflation",
    title: "商品通胀",
    cue: "通胀脉冲",
    digest: "通胀脉冲",
    summary: "把能源、黑色和有色拆开看，避免把商品噪声直接推成通胀结论。",
    kpiKeys: ["brent", "steel", "copper", "aluminum"],
  },
  {
    key: "fx_spread",
    title: "汇率与中美利差",
    cue: "外部约束",
    digest: "外部压力",
    summary: "汇率和利差共同决定外部压力的上限与节奏。",
    kpiKeys: ["gov_spread", "usdcny"],
  },
];

function kpiSourceLabel(kpi: ResolvedCrossAssetKpi | undefined) {
  if (!kpi) return "缺失";
  const vendorName = kpi.vendorName?.trim();
  const normalizedVendorName = vendorName?.toLowerCase();
  if (normalizedVendorName === "choice") return "Choice";
  if (normalizedVendorName?.includes("public_bond")) return "公共利率";
  if (normalizedVendorName?.includes("public")) return "公共补充";
  if (normalizedVendorName?.includes("tushare")) return "Tushare";
  if (kpi.sourceKind === "choice") return vendorName || "Choice";
  if (kpi.sourceKind === "public") return "公共补充";
  if (kpi.sourceKind === "derived") return "合成";
  return "缺失";
}

function kpiDirectionLabel(kpi: ResolvedCrossAssetKpi | undefined) {
  if (!kpi) return "待定";
  if (kpi.changeTone === "positive") return "上行";
  if (kpi.changeTone === "negative") return "下行";
  if (kpi.changeTone === "warning") return "异常";
  return "持平";
}

export function CrossAssetEvidenceTape({
  kpis,
  testId = "cross-asset-evidence-tape",
  className,
}: {
  kpis: ResolvedCrossAssetKpi[];
  testId?: string;
  className?: string;
}) {
  const kpisByKey = useMemo(() => new Map(kpis.map((kpi) => [kpi.key, kpi])), [kpis]);
  const sectionClassName = className ? `cross-asset-evidence-tape ${className}` : "cross-asset-evidence-tape";

  return (
    <section className={sectionClassName} data-testid={testId} aria-label="关键因子矩阵">
      <div className="cross-asset-evidence-tape__head">
        <span>证据矩阵</span>
        <strong>关键因子矩阵</strong>
      </div>
      <div className="cross-asset-evidence-tape__table-wrap">
        <table className="cross-asset-evidence-tape__table">
          <thead>
            <tr>
              <th>因子</th>
              <th>当前</th>
              <th>变化</th>
              <th>方向</th>
              <th>来源</th>
            </tr>
          </thead>
          <tbody>
            {CROSS_ASSET_EVIDENCE_GROUPS.map((group) => {
              const groupKpis = group.kpiKeys
                .map((key) => kpisByKey.get(key))
                .filter((kpi): kpi is ResolvedCrossAssetKpi => Boolean(kpi));
              const leadKpi = groupKpis[0];
              return (
                <tr key={group.key}>
                  <td>
                    <span className="cross-asset-evidence-tape__factor">{group.title}</span>
                    <small>{group.cue}</small>
                  </td>
                  <td>{leadKpi ? `${leadKpi.label} ${leadKpi.valueLabel}` : "等待指标"}</td>
                  <td className={`cross-asset-evidence-tape__delta cross-asset-evidence-tape__delta--${leadKpi?.changeTone ?? "default"}`}>
                    {leadKpi?.changeLabel ?? "待确认"}
                  </td>
                  <td>{kpiDirectionLabel(leadKpi)}</td>
                  <td>{kpiSourceLabel(leadKpi)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function CrossAssetEvidenceGroups({ kpis }: { kpis: ResolvedCrossAssetKpi[] }) {
  const kpisByKey = useMemo(() => new Map(kpis.map((kpi) => [kpi.key, kpi])), [kpis]);
  const groupRows = CROSS_ASSET_EVIDENCE_GROUPS.map((group) => ({
    group,
    kpis: group.kpiKeys
      .map((key) => kpisByKey.get(key))
      .filter((kpi): kpi is ResolvedCrossAssetKpi => Boolean(kpi)),
  }));
  const ledgerRows = groupRows.flatMap(({ group, kpis: groupKpis }) =>
    groupKpis.map((kpi) => ({
      group,
      kpi,
      percentile: computeSparklinePercentile(kpi.sparkline),
    })),
  );

  return (
    <section className="cross-asset-evidence-groups cross-asset-evidence-ledger" data-testid="cross-asset-evidence-groups">
      <header className="cross-asset-evidence-ledger__head">
        <div>
          <span>指标矩阵加工台</span>
          <strong>四列因子、分位、来源一次扫完</strong>
        </div>
        <em>{ledgerRows.length} 项指标 · {groupRows.length} 个因子桶</em>
      </header>
      <div className="cross-asset-evidence-groups__grid cross-asset-evidence-ledger__layout" data-testid="cross-asset-kpi-band">
        <div className="cross-asset-evidence-ledger__matrix-grid" data-testid="cross-asset-kpi-ledger-table">
          {groupRows.map(({ group, kpis: groupKpis }) => {
            const leadKpi = groupKpis[0];
            return (
              <article
                key={group.key}
                className={`cross-asset-evidence-group cross-asset-evidence-factor cross-asset-evidence-factor--${group.key}`}
                data-testid={`cross-asset-evidence-group-${group.key}`}
                aria-labelledby={`cross-asset-evidence-group-${group.key}-title`}
              >
                <header className="cross-asset-evidence-factor__head">
                  <div>
                    <span className="cross-asset-evidence-group__cue">{group.cue}</span>
                    <h3 id={`cross-asset-evidence-group-${group.key}-title`}>{group.title}</h3>
                    <p>{group.summary}</p>
                  </div>
                  <strong>{groupKpis.length} 项</strong>
                </header>
                <table className="cross-asset-evidence-factor__table">
                  <thead>
                    <tr>
                      <th>指标</th>
                      <th>当前</th>
                      <th>变化</th>
                      <th>分位</th>
                      <th>源</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupKpis.length > 0 ? (
                      groupKpis.map((kpi) => {
                        const percentile = computeSparklinePercentile(kpi.sparkline);
                        return (
                          <tr key={`${group.key}-${kpi.key}`}>
                            <td>
                              <strong>{kpi.label}</strong>
                              <span>{kpi.tag || group.digest}</span>
                            </td>
                            <td className="cross-asset-evidence-factor__value">{kpi.valueLabel}</td>
                            <td className={`cross-asset-evidence-ledger__delta cross-asset-evidence-ledger__delta--${kpi.changeTone}`}>
                              {kpi.changeLabel}
                            </td>
                            <td>
                              <span
                                className={`cross-asset-evidence-factor__percentile cross-asset-evidence-ledger__percentile--${percentile?.zone ?? "missing"}`}
                                title={percentile ? `近期 ${kpi.sparkline.length} 日分位：${percentile.label}` : "近期序列不足"}
                              >
                                {percentile?.label ?? "不足"}
                              </span>
                            </td>
                            <td>
                              <span className="cross-asset-evidence-factor__source" title={kpi.resolvedSeriesId}>
                                {kpiSourceLabel(kpi)}
                              </span>
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={5}>该因子桶暂无可展示指标。</td>
                      </tr>
                    )}
                  </tbody>
                </table>
                <footer className="cross-asset-evidence-factor__foot">
                  <span>{leadKpi ? `主线 ${leadKpi.label}` : "主线待接入"}</span>
                  <strong className={`cross-asset-evidence-factor__signal cross-asset-evidence-factor__signal--${leadKpi?.changeTone ?? "default"}`}>
                    {kpiDirectionLabel(leadKpi)}
                  </strong>
                </footer>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
