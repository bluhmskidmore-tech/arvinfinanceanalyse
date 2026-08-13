import { useState } from "react";
import { Collapse } from "antd";
import type { UseQueryResult } from "@tanstack/react-query";

import type {
  ApiEnvelope,
  MacroBondLinkagePayload,
  MacroBondLinkageTopCorrelation,
} from "../../../api/contracts";
import { nonCancellingRefetchOptions } from "../../../app/externalDataRefreshPolicy";
import { KpiCard } from "../../../components/KpiCard";
import { PageAsyncSection } from "../../../components/page/PageAsyncSection";
import { toneFromSignedNumber } from "../../workbench/components/kpiFormat";
import { formatSignedNumber } from "../lib/marketDataFormat";
import { formatCorrelation } from "../lib/marketDataLinkageFormat";
import type { SpreadSlot } from "../pages/marketDataPageModel";
import { LinkageDirectionPill } from "./LinkageDirectionPill";

const TARGET_FAMILY_LABELS: Record<string, string> = {
  treasury: "国债收益率",
  cdb: "国开收益率",
  aaa_credit: "AAA 信用收益率",
  credit_spread: "信用利差",
};

const LIQUIDITY_COMPOSITE_POLARITY_NOTE =
  "流动性正值=宽松；综合分正值=对债偏紧，综合计算中流动性取反。";

function familyLabel(targetFamily: string) {
  return TARGET_FAMILY_LABELS[targetFamily] ?? targetFamily;
}

function LinkageSpreadsAuditBridge({
  spreadSlots,
  onOpenSpreads,
}: {
  spreadSlots: SpreadSlot[];
  onOpenSpreads: () => void;
}) {
  const filledCount = spreadSlots.filter((slot) => slot.point !== null).length;

  return (
    <section
      data-testid="market-data-linkage-spreads-audit"
      className="market-data-linkage-spreads-audit"
    >
      <h2 className="market-data-linkage-panel-title">信用利差维度审计</h2>
      <p className="market-data-linkage-panel-lede">
        审计桥：仅统计 3Y / 5Y / 10Y 结构化 credit_spread 槽位覆盖；完整期限卡片与相关图在「信用利差」Tab。
      </p>
      <div
        className="market-data-linkage-spreads-audit-summary"
        data-testid="market-data-linkage-spreads-audit-count"
      >
        已覆盖 {filledCount} / {spreadSlots.length} 个期限槽位
      </div>
      <ul className="market-data-linkage-spreads-audit-slots">
        {spreadSlots.map((slot) => (
          <li
            key={slot.tenor}
            data-testid={`market-data-linkage-spreads-audit-slot-${slot.tenor}`}
            data-has-data={slot.point ? "true" : "false"}
            className="market-data-linkage-spreads-audit-slot"
          >
            <span className="market-data-linkage-spreads-audit-tenor">{slot.tenor}</span>
            <span className="market-data-linkage-spreads-audit-status">
              {slot.point ? slot.point.series_name : "无数据"}
            </span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="market-data-linkage-spreads-audit-link"
        data-testid="market-data-linkage-spreads-audit-open"
        onClick={onOpenSpreads}
      >
        查看信用利差决策视图 →
      </button>
    </section>
  );
}

function correlationTone(value: number | null | undefined): "up" | "down" | "neutral" {
  if (value == null || Number.isNaN(value) || value === 0) {
    return "neutral";
  }
  return value > 0 ? "up" : "down";
}

function renderCorrelationValue(value: number | null | undefined) {
  return (
    <span className="market-data-linkage-correlation-value" data-tone={correlationTone(value)}>
      {formatCorrelation(value)}
    </span>
  );
}

function renderCorrelationRow(point: MacroBondLinkageTopCorrelation) {
  const dimension = `${familyLabel(point.target_family)} / ${point.target_tenor ?? "期限不可用"}`;
  return (
    <div
      key={`${point.series_id}:${point.target_family}:${point.target_tenor ?? "none"}`}
      className="market-data-linkage-correlation-row"
    >
      <span
        className="market-data-linkage-correlation-name"
        title={`${point.series_name}（${point.series_id}）· ${dimension}`}
      >
        {point.series_name}
        <span className="market-data-dim-label"> {dimension}</span>
      </span>
      {renderCorrelationValue(point.correlation_3m)}
      {renderCorrelationValue(point.correlation_6m)}
      {renderCorrelationValue(point.correlation_1y)}
      <span className="market-data-linkage-correlation-value" data-tone="neutral">
        {`${point.lead_lag_days} 天`}
      </span>
      <LinkageDirectionPill direction={point.direction} />
    </div>
  );
}

type MarketDataLinkageSectionProps = {
  macroBondLinkageQuery: UseQueryResult<ApiEnvelope<MacroBondLinkagePayload>, Error>;
  macroBondLinkage: Partial<MacroBondLinkagePayload>;
  macroBondLinkageWarnings: string[];
  hasPortfolioImpact: boolean;
  spreadSlots: SpreadSlot[];
  nonSpreadTopCorrelations: MacroBondLinkageTopCorrelation[];
  onExpandedChange: (expanded: boolean) => void;
  onOpenSpreads: () => void;
};

export function MarketDataLinkageSection({
  macroBondLinkageQuery,
  macroBondLinkage,
  macroBondLinkageWarnings,
  hasPortfolioImpact,
  spreadSlots,
  nonSpreadTopCorrelations,
  onExpandedChange,
  onOpenSpreads,
}: MarketDataLinkageSectionProps) {
  const [activeKeys, setActiveKeys] = useState<string[]>([]);
  const expanded = activeKeys.includes("macro-linkage");

  return (
    <section className="market-data-section-block">
      <Collapse
        className="market-data-linkage-collapse"
        data-testid="market-data-linkage-collapse"
        bordered={false}
        activeKey={activeKeys}
        onChange={(keys) => {
          const nextKeys = Array.isArray(keys) ? keys : [keys];
          const nextExpanded = nextKeys.includes("macro-linkage");
          setActiveKeys(nextKeys);
          onExpandedChange(nextExpanded);
        }}
        items={[
          {
            key: "macro-linkage",
            label: (
              <span className="market-data-linkage-collapse-label">
                <span>宏观-债市联动</span>
                <span className="market-data-linkage-collapse-label__badge">分析口径</span>
              </span>
            ),
            children: expanded ? (
              <PageAsyncSection
                title="宏观-债市联动"
                hideHeading
                isLoading={macroBondLinkageQuery.isLoading}
                isError={macroBondLinkageQuery.isError}
                isEmpty={
                  !macroBondLinkageQuery.isLoading &&
                  !macroBondLinkageQuery.isError &&
                  (macroBondLinkage.top_correlations?.length ?? 0) === 0 &&
                  macroBondLinkageWarnings.length === 0
                }
                onRetry={() => void macroBondLinkageQuery.refetch(nonCancellingRefetchOptions)}
              >
                <div className="market-data-stack-gap-5">
                  <section data-testid="market-data-linkage-caveat" className="market-data-linkage-caveat">
                    <div className="market-data-linkage-caveat-body">
                      本区为宏观联动分析口径（非正式口径）。组合影响仅用于研究和配置讨论，属于分析估算，不代表账本口径下的损益（PnL）、
                      不代表正式估值归因，也不替代债券分析的正式读面。
                    </div>
                    {macroBondLinkageWarnings.length > 0 ? (
                      <ul data-testid="market-data-linkage-warning-list" className="market-data-linkage-warning-list">
                        {macroBondLinkageWarnings.map((warning) => (
                          <li key={warning}>{warning}</li>
                        ))}
                      </ul>
                    ) : (
                      <div className="market-data-linkage-warning-empty" data-testid="market-data-linkage-warning-empty">
                        当前无额外方法警示。
                      </div>
                    )}
                  </section>

                  <div className="market-data-summary-grid">
                    <div data-testid="market-data-linkage-composite-score">
                      <KpiCard
                        title="综合评分"
                        value={
                          macroBondLinkage.environment_score?.composite_score != null
                            ? String(macroBondLinkage.environment_score.composite_score.toFixed(2))
                            : "不可用"
                        }
                        detail={`${
                          macroBondLinkage.environment_score?.signal_description ?? "缺少环境评分数据。"
                        } ${LIQUIDITY_COMPOSITE_POLARITY_NOTE}`}
                        valueVariant="text"
                        tone={toneFromSignedNumber(
                          macroBondLinkage.environment_score?.composite_score != null
                            ? macroBondLinkage.environment_score.composite_score
                            : null,
                        )}
                      />
                    </div>
                    <div data-testid="market-data-linkage-rate-direction">
                      <KpiCard
                        title="利率方向"
                        value={macroBondLinkage.environment_score?.rate_direction ?? "不可用"}
                        detail={
                          macroBondLinkage.environment_score?.rate_direction_score != null
                            ? `direction score ${macroBondLinkage.environment_score.rate_direction_score.toFixed(2)}`
                            : "缺少方向评分。"
                        }
                        valueVariant="text"
                        tone={toneFromSignedNumber(
                          macroBondLinkage.environment_score?.rate_direction_score != null
                            ? macroBondLinkage.environment_score.rate_direction_score
                            : null,
                        )}
                      />
                    </div>
                    <div data-testid="market-data-linkage-liquidity-score">
                      <KpiCard
                        title="流动性评分"
                        value={
                          macroBondLinkage.environment_score?.liquidity_score != null
                            ? macroBondLinkage.environment_score.liquidity_score.toFixed(2)
                            : "不可用"
                        }
                        detail="正值偏松，负值偏紧；进入综合分时取反。"
                        valueVariant="text"
                        tone={toneFromSignedNumber(
                          macroBondLinkage.environment_score?.liquidity_score != null
                            ? macroBondLinkage.environment_score.liquidity_score
                            : null,
                        )}
                      />
                    </div>
                    <div data-testid="market-data-linkage-growth-score">
                      <KpiCard
                        title="增长评分"
                        value={
                          macroBondLinkage.environment_score?.growth_score != null
                            ? macroBondLinkage.environment_score.growth_score.toFixed(2)
                            : "不可用"
                        }
                        detail="宏观增长方向的简化分值。"
                        valueVariant="text"
                        tone={toneFromSignedNumber(
                          macroBondLinkage.environment_score?.growth_score != null
                            ? macroBondLinkage.environment_score.growth_score
                            : null,
                        )}
                      />
                    </div>
                  </div>

                  <section data-testid="market-data-linkage-portfolio-impact">
                    <h2 className="market-data-linkage-panel-title">组合影响估算</h2>
                    <p className="market-data-linkage-section-note">
                      以下数值为分析口径估算，基于宏观环境评分与组合在利率、利差维度上的敏感度静态映射，不代表正式损益。
                    </p>
                    {hasPortfolioImpact ? (
                      <div className="market-data-portfolio-grid">
                        <div>
                          <div className="market-data-dim-label">利率变动</div>
                          <div className="market-data-tabular">
                            {formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_rate_change_bps, " bp")}
                          </div>
                        </div>
                        <div>
                          <div className="market-data-dim-label">利差走阔</div>
                          <div className="market-data-tabular">
                            {formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_spread_widening_bps, " bp")}
                          </div>
                        </div>
                        <div>
                          <div className="market-data-dim-label">利率影响</div>
                          <div className="market-data-tabular">
                            {formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_rate_pnl_impact)}
                          </div>
                        </div>
                        <div>
                          <div className="market-data-dim-label">利差影响</div>
                          <div className="market-data-tabular">
                            {formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_spread_pnl_impact)}
                          </div>
                        </div>
                        <div>
                          <div className="market-data-dim-label">合计估算</div>
                          <div className="market-data-tabular">
                            {formatSignedNumber(macroBondLinkage.portfolio_impact?.total_estimated_impact)}
                          </div>
                        </div>
                        <div>
                          <div className="market-data-dim-label">影响占比</div>
                          <div className="market-data-tabular">
                            {macroBondLinkage.portfolio_impact?.impact_ratio_to_market_value ?? "不可用"}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div
                        data-testid="market-data-linkage-portfolio-impact-unavailable"
                        className="market-data-portfolio-empty"
                      >
                        当前报告日未返回组合影响估算，状态按不可用处理，不在前端补零。
                      </div>
                    )}
                  </section>

                  <LinkageSpreadsAuditBridge spreadSlots={spreadSlots} onOpenSpreads={onOpenSpreads} />

                  <section data-testid="market-data-linkage-top-correlations">
                    <h2 className="market-data-linkage-panel-title">相关性前十</h2>
                    {nonSpreadTopCorrelations.length > 0 || spreadSlots.some((slot) => slot.point !== null) ? (
                      <div className="market-data-linkage-correlation-list">
                        <div className="market-data-linkage-correlation-row market-data-linkage-correlation-head">
                          <span>序列 / 目标维度</span>
                          <span>3月</span>
                          <span>6月</span>
                          <span>1年</span>
                          <span>领先/滞后</span>
                          <span>方向</span>
                        </div>
                        {(macroBondLinkage.top_correlations ?? []).map((point) => renderCorrelationRow(point))}
                      </div>
                    ) : (
                      <div className="market-data-corr-empty">当前无可展示的结构化相关性结果。</div>
                    )}
                  </section>
                </div>
              </PageAsyncSection>
            ) : null,
          },
        ]}
      />
    </section>
  );
}
