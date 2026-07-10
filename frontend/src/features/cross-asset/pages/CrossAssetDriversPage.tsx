import { AsyncSection } from "../../../components/AsyncSection";
import ReactECharts from "../../../lib/echarts";
import { KpiCard } from "../../../components/KpiCard";
import { toneFromSignedNumber } from "../../workbench/components/kpiFormat";
import { CrossAssetEventCalendar } from "../components/CrossAssetEventCalendar";
import { MarketCandidateActions } from "../components/MarketCandidateActions";
import { PageOutput } from "../components/PageOutput";
import { WatchList } from "../components/WatchList";
import {
  formatLinkageEnvironmentScoreDetail,
  formatLinkageRateDirection,
} from "../lib/crossAssetLinkageLabels";
import "./CrossAssetDriversPage.css";
import { useCrossAssetViewModel } from "../hooks/useCrossAssetViewModel";

import { CrossAssetDecisionZone } from "../components/CrossAssetDecisionZone";
import {
  formatSignedNumber,
} from "../components/utils";

import {
  LivermoreStrategyStatusPanel,
  LivermoreSignalConfluencePanel,
} from "../components/LivermorePanels";
import { crossAssetPanelClass } from "../components/shared";

import {
  CrossAssetEvidenceTape,
  CrossAssetEvidenceGroups,
} from "../components/MarketTapePanels";
import {
  correlationLedgerCellClassName,
  splitLinkageIndicator,
} from "../components/utils";

import {
  CrossAssetReviewQueue,
  AssetClassAnalysisPanel,
} from "../components/AssetAnalysisPanels";
import { DriverWaterfallPanel } from "../components/DriverWaterfallPanel";
import { CorrelationHeatmapPanel } from "../components/CorrelationAndRegimePanels";
import { MomentumScoreboardPanel, TrendGroupToggle, VolatilityClusteringPanel, EquityBondERPPanel } from "../components/MomentumAndVolatilityPanels";
import {
  CrossAssetReferenceToolbar,
  CrossAssetReferenceSummary,
  CrossAssetReferenceMarketTape,
  CrossAssetReferenceEvidenceMatrix,
  CrossAssetReferenceSourceAudit,
  CrossAssetReferenceLowerGrid,
  CrossAssetReferenceTrendStrip,
  CrossAssetReferenceDepthSummary,
} from "../components/ReferencePanels";
import {
  NcdProxyEvidencePanel,
  TransmissionAxesPanel,
} from "../components/LegacyPanels";


export default function CrossAssetDriversPage() {
  const {
    assetClassAnalysisRows,
    candidateActions,
    correlationMatrix,
    crossAssetDataDate,
    drivers,
    env,
    envTags,
    equityEvidenceItems,
    erpData,
    eventItems,
    firstScreenDisplay,
    hasPortfolioImpact,
    heatmapRows,
    kpis,
    latestMeta,
    latestQuery,
    linkageBodyEmpty,
    linkageMeta,
    linkageReportDate,
    livermoreAsOfDate,
    livermoreManualPositionMutation,
    livermoreManualSubmitError,
    livermoreSignalConfluencePayload,
    livermoreSignalConfluenceQuery,
    livermoreStrategyPayload,
    livermoreStrategyQuery,
    livermoreStrategyResolvedAsOfDate,
    macroBondLinkage,
    macroBondLinkageQuery,
    macroBondLinkageWarnings,
    momentumRows,
    ncdFundingProxyQuery,
    ncdProxyEvidence,
    researchCalendarQuery,
    researchViewCards,
    statusFlags,
    setTrendGroup,
    topCorrelationSummary,
    transmissionAxisRows,
    trendGroup,
    trendSummary,
    visibleTrendOption,
    volAlert,
    waterfallBars,
    watchRows,
  } = useCrossAssetViewModel();
  return (
      <section
        className="cross-asset-drivers-page"
        data-testid="cross-asset-drivers-page"
      >
        <div data-testid="cross-asset-page" className="cross-asset-drivers-page__shell">
        <section className="cross-asset-first-screen cross-asset-reference-screen" data-testid="cross-asset-first-screen">
          <CrossAssetReferenceToolbar
            reportDate={crossAssetDataDate || linkageReportDate}
            onRefresh={() => {
              void latestQuery.refetch();
              void macroBondLinkageQuery.refetch();
            }}
          />
          <CrossAssetReferenceSummary
            display={firstScreenDisplay}
            latestMeta={latestMeta}
            linkageMeta={linkageMeta}
          />
          <CrossAssetReferenceMarketTape kpis={kpis} />
          <section
            className="cross-asset-command-center cross-asset-first-screen-grid cross-asset-reference-evidence-grid"
            data-testid="cross-asset-first-screen-grid"
          >
            <div className="cross-asset-fusion-layout cross-asset-reference-fusion-layout" data-testid="cross-asset-fusion-layout">
              <CrossAssetReferenceEvidenceMatrix
                kpis={kpis}
                sourceBlockedFlag={firstScreenDisplay.status.sourceBlockedFlag}
              />
              <div className="cross-asset-fusion-side-panel cross-asset-reference-fusion-side-panel" data-testid="cross-asset-fusion-side-panel">
                <CrossAssetReferenceSourceAudit
                  reportDate={crossAssetDataDate || linkageReportDate}
                  latestMeta={latestMeta}
                  linkageMeta={linkageMeta}
                  statusFlags={statusFlags}
                  envTags={envTags}
                  researchViews={researchViewCards}
                  isLoading={macroBondLinkageQuery.isLoading || latestQuery.isLoading}
                />
                <CrossAssetReviewQueue
                  statusFlags={statusFlags}
                  latestMeta={latestMeta}
                  linkageMeta={linkageMeta}
                  isLoading={macroBondLinkageQuery.isLoading || latestQuery.isLoading}
                />
              </div>
            </div>
          </section>
          <CrossAssetReferenceLowerGrid
            matrix={correlationMatrix}
            rows={transmissionAxisRows}
            cards={researchViewCards}
            sourceBlockedFlag={firstScreenDisplay.status.sourceBlockedFlag}
          />
          <CrossAssetReferenceTrendStrip kpis={kpis} />
        </section>

        <div className="cross-asset-drivers-page__flow">
          <CrossAssetReferenceDepthSummary
            kpis={kpis}
            heatmapCount={heatmapRows.length}
            transmissionRows={transmissionAxisRows}
            assetRows={assetClassAnalysisRows}
            momentumRows={momentumRows}
            correlationMatrix={correlationMatrix}
            candidateActions={candidateActions}
            eventCount={eventItems.length}
            watchCount={watchRows.length}
            statusFlags={statusFlags}
          />
          <div className="cross-asset-decision-board cross-asset-reference-depth" data-testid="cross-asset-decision-display">
            <CrossAssetDecisionZone testId="cross-asset-zone-evidence" title="证据与指标">
              <CrossAssetEvidenceTape kpis={kpis} />
              <details
                open
                className="cross-asset-evidence-details"
                data-testid="cross-asset-evidence-details"
                aria-label="指标明细与相关性热力"
              >
                <summary>
                  <span>指标明细与相关性热力</span>
                  <strong>{kpis.length} 项指标</strong>
                </summary>
                <CrossAssetEvidenceGroups kpis={kpis} />
                <section className="cross-asset-linkage-heatmap-ledger" data-testid="cross-asset-linkage-heatmap-ledger">
                  <header className="cross-asset-linkage-heatmap-ledger__head">
                    <div className="cross-asset-linkage-heatmap-ledger__title">
                      <span>相关性热力</span>
                      <strong>{heatmapRows.length} 条联动链路</strong>
                    </div>
                    <div className="cross-asset-linkage-heatmap-ledger__legend" aria-label="相关性颜色图例">
                      <span className="cross-asset-linkage-heatmap-ledger__legend-item cross-asset-linkage-heatmap-ledger__legend-item--negative">负相关</span>
                      <span className="cross-asset-linkage-heatmap-ledger__legend-item cross-asset-linkage-heatmap-ledger__legend-item--missing">不可用</span>
                      <span className="cross-asset-linkage-heatmap-ledger__legend-item cross-asset-linkage-heatmap-ledger__legend-item--positive">正相关</span>
                    </div>
                  </header>
                  <table className="cross-asset-drivers-page__heatmap cross-asset-drivers-page__heatmap--flat">
                    <thead>
                      <tr>
                        <th>指标</th>
                        <th>3月相关</th>
                        <th>6月相关</th>
                        <th>方向</th>
                      </tr>
                    </thead>
                    <tbody>
                      {heatmapRows.map((row) => {
                        const indicator = splitLinkageIndicator(row.indicator);
                        return (
                          <tr key={row.id}>
                            <td className="cross-asset-linkage-heatmap-ledger__pair">
                              <strong>{indicator.source}</strong>
                              {indicator.target ? <span>→ {indicator.target}</span> : null}
                            </td>
                            <td className={correlationLedgerCellClassName(row.current)}>{row.current}</td>
                            <td className={correlationLedgerCellClassName(row.mid)}>{row.mid}</td>
                            <td className={`cross-asset-drivers-page__eval-tone cross-asset-drivers-page__eval-tone--${row.evalTone}`}>
                              {row.eval}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </section>
              </details>
            </CrossAssetDecisionZone>

            <CrossAssetDecisionZone testId="cross-asset-zone-transmission" title="传导与行动">
              <TransmissionAxesPanel rows={transmissionAxisRows} />
              <AssetClassAnalysisPanel
                rows={assetClassAnalysisRows}
                equityEvidenceItems={equityEvidenceItems}
                bondJudgment={firstScreenDisplay.judgments.bond}
              />
              <div className="cross-asset-drivers-page__drivers-grid cross-asset-drivers-page__drivers-grid--flat">
                {drivers.map((col) => (
                  <div key={col.title} className="cross-asset-drivers-page__driver-cell">
                    <div className="cross-asset-drivers-page__driver-title">{col.title}</div>
                    <div className={`cross-asset-drivers-page__driver-stance cross-asset-drivers-page__driver-stance--${col.tone}`}>
                      {col.stance}
                    </div>
                    <ul className="cross-asset-drivers-page__driver-list">
                      {col.bullets.map((bullet) => (
                        <li key={bullet}>{bullet}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
              <div className="cross-asset-zone-analytics-grid" data-testid="cross-asset-zone-analytics-grid">
                <DriverWaterfallPanel bars={waterfallBars} env={env} />
                <div className="cross-asset-risk-snapshot-grid" data-testid="cross-asset-risk-snapshot-grid">
                  <VolatilityClusteringPanel alert={volAlert} />
                  <EquityBondERPPanel erp={erpData} />
                </div>
              </div>
              <MarketCandidateActions rows={candidateActions} />
              <NcdProxyEvidencePanel evidence={ncdProxyEvidence} isLoading={ncdFundingProxyQuery.isLoading} />
            </CrossAssetDecisionZone>

            <CrossAssetDecisionZone
              testId="cross-asset-zone-observation"
              title="走势与观察"
              className="cross-asset-zone-observation"
            >
            <div data-testid="cross-asset-trend-panel" className="cross-asset-trend-panel">
              <h3 className="cross-asset-decision-zone__block-title">跨资产走势（近 20 日，基准 = 100）</h3>
              <div className="cross-asset-trend-panel__body">
                <div className="cross-asset-trend-panel__toolbar">
                  <TrendGroupToggle active={trendGroup} onChange={setTrendGroup} />
                  <details className="cross-asset-trend-panel__method">
                    <summary>口径说明（LOCF 归一化）</summary>
                    <p className="cross-asset-trend-panel__note">
                      各资产发布日与休市不同，在统一时间轴上先对缺失日沿用「上一有效观测」(LOCF)，再按窗口内首次观测 = 100
                      归一化。曲线在两次真实更新之间为水平持有，不代表日内波动。
                    </p>
                  </details>
                </div>
                {trendSummary ? (
                  <div className={`cross-asset-trend-panel__summary cross-asset-trend-panel__summary--${trendSummary.tone}`} data-testid="cross-asset-trend-summary">
                    <span className="cross-asset-trend-panel__summary-dot" />
                    <span className="cross-asset-trend-panel__summary-text">{trendSummary.headline}</span>
                    <div className="cross-asset-trend-panel__summary-signals">
                      {trendSummary.signals.map((sig) => (
                        <span key={sig.label} className={`cross-asset-trend-panel__signal cross-asset-trend-panel__signal--${sig.tone}`} title={sig.description}>
                          {sig.label}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
                {latestQuery.isLoading ? (
                  <div className="cross-asset-trend-panel__loading">
                    <div className="cross-asset-trend-panel__spinner" />
                    正在加载宏观序列…
                  </div>
                ) : visibleTrendOption ? (
                  <div className="cross-asset-trend-chart">
                    <ReactECharts
                      option={visibleTrendOption}
                      className="cross-asset-trend-chart__canvas"
                      notMerge
                      lazyUpdate
                    />
                  </div>
                ) : (
                  <div className="cross-asset-trend-panel__empty">
                    当前没有足够历史点，无法绘制跨资产走势。
                  </div>
                )}
              </div>
            </div>

            <div className="cross-asset-observation-support-grid" data-testid="cross-asset-observation-support-grid">
              <MomentumScoreboardPanel rows={momentumRows} />
              <CorrelationHeatmapPanel matrix={correlationMatrix} />
            </div>

            <details
              open
              className="cross-asset-observation-secondary"
              data-testid="cross-asset-observation-secondary"
            >
              <summary>
                <span>事件与观察清单</span>
                <strong>{eventItems.length + watchRows.length} 项待观察材料</strong>
              </summary>
              <div className="cross-asset-observation-secondary-grid" data-testid="cross-asset-observation-secondary-grid">
                <CrossAssetEventCalendar items={eventItems} />
                <WatchList rows={watchRows} />
              </div>
            </details>

            <details open className="cross-asset-decision-appendix" data-testid="cross-asset-decision-appendix">
              <summary>
                <span>补充复核</span>
                <strong>A股策略 · 宏观联动 · 结构化输出</strong>
              </summary>
              <div className="cross-asset-decision-appendix__body">
                <LivermoreStrategyStatusPanel
                  payload={livermoreStrategyPayload}
                  isLoading={livermoreStrategyQuery.isLoading}
                  isError={livermoreStrategyQuery.isError}
                  asOfDate={livermoreAsOfDate}
                  onManualSubmit={(positions, asOfDate) =>
                    livermoreManualPositionMutation.mutateAsync({ asOfDate, positions })
                  }
                  manualSubmitPending={livermoreManualPositionMutation.isPending}
                  manualSubmitError={livermoreManualSubmitError}
                  manualResultRowCount={livermoreManualPositionMutation.data?.row_count ?? null}
                />
                <LivermoreSignalConfluencePanel
                  payload={livermoreSignalConfluencePayload}
                  isLoading={livermoreSignalConfluenceQuery.isLoading}
                  isError={livermoreSignalConfluenceQuery.isError}
                  asOfDate={livermoreStrategyResolvedAsOfDate}
                />
                <AsyncSection
                  title="宏观 - 债券联动（评分与组合影响）"
                  isLoading={macroBondLinkageQuery.isLoading || latestQuery.isLoading}
                  isError={macroBondLinkageQuery.isError || latestQuery.isError}
                  isEmpty={linkageBodyEmpty}
                  onRetry={() => {
                    void latestQuery.refetch();
                    void macroBondLinkageQuery.refetch();
                    void researchCalendarQuery.refetch();
                  }}
                >
                  {!linkageReportDate ? (
                    <p className="cross-asset-linkage__missing-date">
                      缺少可用交易日，当前无法计算宏观-债券联动分析。
                    </p>
                  ) : (
                    <div className="cross-asset-linkage__body">
                      {macroBondLinkageWarnings.length > 0 ? (
                        <ul
                          data-testid="cross-asset-linkage-warning-list"
                          className="cross-asset-linkage__warnings"
                        >
                          {macroBondLinkageWarnings.map((warning) => (
                            <li key={warning}>{warning}</li>
                          ))}
                        </ul>
                      ) : null}

                      <div className="cross-asset-linkage__kpi-grid">
                        <div data-testid="cross-asset-linkage-composite-score">
                          <KpiCard
                            title="综合评分"
                            value={env.composite_score != null ? String(env.composite_score.toFixed(2)) : "不可用"}
                            detail={env.signal_description ?? "缺少环境评分数据。"}
                            valueVariant="text"
                            tone={toneFromSignedNumber(env.composite_score != null ? env.composite_score : null)}
                          />
                        </div>
                        <div data-testid="cross-asset-linkage-rate-direction">
                          <KpiCard
                            title="利率方向"
                            value={formatLinkageRateDirection(env.rate_direction)}
                            detail={formatLinkageEnvironmentScoreDetail(
                              "方向分值",
                              env.rate_direction_score,
                              "缺少方向评分。",
                            )}
                            valueVariant="text"
                            tone={toneFromSignedNumber(env.rate_direction_score != null ? env.rate_direction_score : null)}
                          />
                        </div>
                        <div data-testid="cross-asset-linkage-liquidity-score">
                          <KpiCard
                            title="流动性评分"
                            value={env.liquidity_score != null ? env.liquidity_score.toFixed(2) : "不可用"}
                            detail="正值偏松，负值偏紧。"
                            valueVariant="text"
                            tone={toneFromSignedNumber(env.liquidity_score != null ? env.liquidity_score : null)}
                          />
                        </div>
                        <div data-testid="cross-asset-linkage-growth-score">
                          <KpiCard
                            title="增长评分"
                            value={env.growth_score != null ? env.growth_score.toFixed(2) : "不可用"}
                            detail="宏观增长方向的简化分值。"
                            valueVariant="text"
                            tone={toneFromSignedNumber(env.growth_score != null ? env.growth_score : null)}
                          />
                        </div>
                      </div>

                      <section
                        data-testid="cross-asset-linkage-portfolio-impact"
                        className={`${crossAssetPanelClass} cross-asset-linkage-portfolio-impact`}
                      >
                        <h2 className="cross-asset-linkage-portfolio-impact__title">
                          组合影响估算
                        </h2>
                        <p className="cross-asset-linkage-portfolio-impact__description">
                          以下数值属于分析口径估算，只作为环境敏感度提示，不代表正式损益。
                        </p>
                        {hasPortfolioImpact ? (
                          <div className="cross-asset-linkage-portfolio-impact__grid">
                            <div>
                              <div className="cross-asset-linkage-portfolio-impact__label">利率变动</div>
                              <div className="cross-asset-linkage-portfolio-impact__value">{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_rate_change_bps, " bp")}</div>
                            </div>
                            <div>
                              <div className="cross-asset-linkage-portfolio-impact__label">利差走阔</div>
                              <div className="cross-asset-linkage-portfolio-impact__value">{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_spread_widening_bps, " bp")}</div>
                            </div>
                            <div>
                              <div className="cross-asset-linkage-portfolio-impact__label">合计估算</div>
                              <div className="cross-asset-linkage-portfolio-impact__value">{formatSignedNumber(macroBondLinkage.portfolio_impact?.total_estimated_impact)}</div>
                            </div>
                          </div>
                        ) : (
                          <div className="cross-asset-linkage-portfolio-impact__empty">当前没有可用组合影响估算。</div>
                        )}
                      </section>
                    </div>
                  )}
                </AsyncSection>

                <details open className="cross-asset-structured-output">
                  <summary>结构化输出与联动摘要</summary>
                  <div data-testid="cross-asset-page-output">
                    <PageOutput
                      envTags={envTags}
                      signalPreview={env.signal_description ?? null}
                      linkageWarnings={macroBondLinkageWarnings}
                      topCorrelationSummary={topCorrelationSummary}
                    />
                  </div>
                </details>
              </div>
            </details>
            </CrossAssetDecisionZone>
          </div>
        </div>
        </div>
      </section>
  );
}
