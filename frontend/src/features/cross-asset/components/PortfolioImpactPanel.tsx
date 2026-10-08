import { useState } from "react";
import { Button } from "antd";
import { Link } from "react-router-dom";

import type { MacroBondLinkagePortfolioImpact } from "../../../api/contracts/marketMacro";
import { EM_DASH, formatPercent } from "../../../utils/format";
import { buildBondTradingDeskPath } from "../../bond-trading-desk/lib/bondTradingDeskPageModel";
import { formatEstimatedImpactCny, formatSignedNumber, impactTone } from "./utils";

export function PortfolioImpactPanel({ impact, expandDetails = false }: { impact: Partial<MacroBondLinkagePortfolioImpact>; expandDetails?: boolean }) {
  const [selection, setSelection] = useState<{ entityId: string; scope: string } | null>(null);
  const scope = JSON.stringify([impact.requested_report_date, impact.risk_report_date, impact.risk_source_table, impact.risk_source_version, impact.risk_rule_version]);
  const entities = impact.entities ?? [];
  const selected = selection?.scope === scope ? entities.find((entity) => entity.entity_id === selection.entityId) : undefined;
  const coverage = impact.coverage;
  const ratio = impact.impact_ratio_to_market_value;
  const ratioReason = impact.ratio_unavailable_reason === "market_value_zero"
    ? "组合市值为零，比例不可计算"
    : impact.ratio_unavailable_reason === "market_value_missing" ? "组合市值缺失"
    : impact.ratio_unavailable_reason === "macro_signal_unavailable" ? "宏观信号不可用"
    : impact.ratio_unavailable_reason === "macro_signal_partial" ? "情景信号覆盖不完整" : "风险输入不足";

  return (
    <section data-testid="cross-asset-linkage-portfolio-impact" className="cross-asset-linkage-portfolio-impact">
      <div className="cross-asset-linkage-portfolio-impact__heading">
        <h3 className="cross-asset-linkage-portfolio-impact__title">组合影响估算</h3>
        <p className="cross-asset-linkage-portfolio-impact__description">
          以下数值属于分析口径估算，只作为环境敏感度提示，不代表正式损益。
        </p>
      </div>
      {Object.keys(impact).length ? <>
        <div className="cross-asset-linkage-portfolio-impact__grid">
          <div>
            <div className="cross-asset-linkage-portfolio-impact__label">利率变动</div>
            <div className="cross-asset-linkage-portfolio-impact__value">{formatSignedNumber(impact.estimated_rate_change_bps, " bp")}</div>
          </div>
          <div>
            <div className="cross-asset-linkage-portfolio-impact__label">利差走阔</div>
            <div className="cross-asset-linkage-portfolio-impact__value">{formatSignedNumber(impact.estimated_spread_widening_bps, " bp")}</div>
          </div>
          <div>
            <div className="cross-asset-linkage-portfolio-impact__label">合计估算</div>
            <div className={`cross-asset-linkage-portfolio-impact__value cross-asset-linkage-portfolio-impact__value--total cross-asset-linkage-portfolio-impact__value--${impactTone(impact.total_estimated_impact)}`}
              title={impact.total_estimated_impact != null ? `${impact.total_estimated_impact} 元` : undefined}>
              {formatEstimatedImpactCny(impact.total_estimated_impact)}
            </div>
          </div>
        </div>
        {impact.status === "unavailable" || impact.status === "partial" ? (
          <p role="status">{impact.availability_reason === "macro_signal_unavailable" ? "宏观信号不可用"
            : impact.availability_reason === "macro_signal_partial" ? "情景信号覆盖不完整"
            : impact.status === "partial" ? "风险输入覆盖不完整" : "风险输入不可用"}，合计估算不可用。</p>
        ) : null}
        {impact.risk_report_date !== undefined ? <p>
          目标日 {impact.requested_report_date ?? EM_DASH} · 风险日 {impact.risk_report_date ?? "不可用"}
          {impact.risk_report_date && impact.risk_report_date !== impact.requested_report_date ? "（最近可用日期）" : ""}
          {" · "}占组合市值 {ratio == null ? `不可用（${ratioReason}）` : formatPercent(Number(ratio), true)}
        </p> : null}
        <details className="cross-asset-evidence-details" open={expandDetails || undefined}>
          <summary>风险输入与实体证据</summary>
          <p>来源 {impact.risk_source_table ?? "未提供"} · 版本 {impact.risk_source_version ?? EM_DASH}</p>
          <p>DV01 {formatSignedNumber(impact.portfolio_dv01, " 元/bp")} · CS01 {formatSignedNumber(impact.portfolio_cs01, " 元/bp")} · 组合市值 {formatEstimatedImpactCny(impact.portfolio_market_value)}</p>
          {coverage?.basis === "bond_analytics_row_count" ? <p>
            已观测行覆盖：DV01 {coverage.dv01_observed_count ?? EM_DASH}/{coverage.row_count ?? EM_DASH}，
            CS01 {coverage.cs01_observed_count ?? EM_DASH}/{coverage.row_count ?? EM_DASH}，
            市值 {coverage.market_value_observed_count ?? EM_DASH}/{coverage.row_count ?? EM_DASH}。
          </p> : coverage?.basis === "risk_tensor_published_scope" ? <p>
            风险张量发布范围 {coverage.row_count ?? EM_DASH} 行；久期排除 {coverage.duration_excluded_count ?? EM_DASH} 行；质量 {coverage.quality_flag ?? "未提供"}。逐项观测覆盖未提供。
          </p> : <p>风险覆盖信息不可用。</p>}
          {selected ? <div data-testid="macro-risk-entity-detail">
            <Button onClick={() => setSelection(null)}>返回组合估算</Button>
            <p>{selected.instrument_code ?? EM_DASH} · {selected.instrument_name ?? EM_DASH} · 风险日 {selected.report_date}</p>
            <p>组合 {selected.portfolio_name ?? EM_DASH} · 成本中心 {selected.cost_center ?? EM_DASH} · 会计分类 {selected.accounting_class ?? EM_DASH} · 原币 {selected.currency_code ?? EM_DASH}</p>
            <p>DV01 {formatSignedNumber(selected.dv01, " 元/bp")} · 信用敏感度 {formatSignedNumber(selected.spread_dv01, " 元/bp")} · 市值 {formatEstimatedImpactCny(selected.market_value)}</p>
            <p>证据行 {selected.entity_id} · 来源版本 {selected.source_version || EM_DASH} · 规则 {selected.rule_version || EM_DASH}</p>
            {selected.instrument_code ? <Link to={buildBondTradingDeskPath(selected.instrument_code, selected.report_date)}>查看该券</Link> : null}
          </div> : entities.length ? <>
            <p>同风险日期的分析明细；实体按券码、组合、成本中心、会计分类及原币定位，未建立账户级持仓关联。
              {impact.entity_link_status === "same_date_only" ? "与发布风险张量的同源关系未验证。" : ""}
            </p>
            <ul>{entities.map((entity) => <li key={entity.entity_id}>
              <Button type="link" onClick={() => setSelection({ entityId: entity.entity_id, scope })}>
                {entity.instrument_code ?? EM_DASH} · {entity.portfolio_name ?? EM_DASH} · {entity.cost_center ?? EM_DASH} · {entity.accounting_class ?? EM_DASH} · {entity.currency_code ?? EM_DASH}
              </Button>
            </li>)}</ul>
          </> : <p>没有同日实体明细，不能逐券定位。</p>}
        </details>
      </> : <div className="cross-asset-linkage-portfolio-impact__empty">当前没有可用组合影响估算。</div>}
    </section>
  );
}
