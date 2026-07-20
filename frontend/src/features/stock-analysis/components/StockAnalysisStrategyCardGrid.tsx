import type { ComponentProps } from "react";
import {
  DatabaseOutlined,
  FireOutlined,
  LineChartOutlined,
} from "@ant-design/icons";
import { StockAnalysisInlineChip as Chip } from "./StockAnalysisStatusPrimitives";
import { useApiClient } from "../../../api/client";
import type {
  FactorScreenCandidatesPayload,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreCycleRotationFramework,
  LivermoreStrategyPayload,
  MeanReversionCandidatesPayload,
} from "../../../api/contracts";
import {
  buildConsensusDetailSelection,
  buildFactorScreenDetailSelection,
  buildMeanReversionDetailSelection,
  type StockDetailSelection,
} from "../lib/stockAnalysisDetailSelection";
import { consensusStrategyLabel, lookupStockStrategyRanks, type ConsensusSummary } from "../lib/buildConsensusSummary";

import {
  compactStockText as compactText,
  stockStrategyPanelErrorMessage as strategyPanelErrorMessage,
} from "../lib/stockAnalysisPageCopy";
import {
  buildStrategyBacktestRows,
  formatBacktestSignedPercent,
  formatCostBasisLabel,
} from "../lib/stockAnalysisBacktestModel";
import {
  cycleBoundaryLabel,
  cycleConstraintLabel,
  cycleEvidenceLabel,
  cycleGapLabel,
  cycleInputSummary,
  cycleLayerTitleLabel,
  cycleLayerWeightLabel,
  eventDetailLabel,
  eventImpactLabel,
  eventLevelLabel,
  eventNameLabel,
  eventSourceLabel,
} from "../lib/stockAnalysisPageLabels";
import {
  localizeImplementationStage,
  localizeThemeRadarBadge,
  type StockAnalysisEventMonitorRow,
  type StockCycleMacroLayerSummary,
  type StockThemeBreakoutCard,
  type StockThemeBreakoutReviewItem,
  type StockThemeEvidenceStateRow,
} from "../lib/stockAnalysisPageModel";
import { BacktestBoundaryChips } from "./StockAnalysisBacktestBoundaryChips";
import { StockAnalysisCycleRuleSummary } from "./StockAnalysisCycleRuleSummary";
import { CompactStatusTile } from "./StockAnalysisStatusPrimitives";
import { StockAnalysisStrategyReviewCards } from "./StockAnalysisStrategyReviewCards";
import { StockAnalysisThemeBreakoutPanel } from "./StockAnalysisThemeBreakoutPanel";
import { StrategyModuleCard, type StrategyModuleCardProps } from "./StrategyModuleCard";
import { StrategyPanelComplianceDetails } from "./StrategyPanelResultStrip";

type QueryState = {
  isLoading: boolean;
  isError: boolean;
  error: unknown;
};

type RefSection = {
  ref?: StrategyModuleCardProps["sectionRef"];
};

type SeenSection = RefSection & {
  seen: boolean;
};

type StrategyReviewCardsProps = ComponentProps<typeof StockAnalysisStrategyReviewCards>;
type StrategyBacktestRow = ReturnType<typeof buildStrategyBacktestRows>[number];

type StockAnalysisStrategyCardGridProps = {
  cycleRotationFramework: LivermoreCycleRotationFramework | undefined;
  cycleRotationPanelSummary: StrategyModuleCardProps["summary"];
  isStrategyCardExpanded: (key: string) => boolean;
  toggleStrategyCard: (key: string) => void;
  cycleFrameworkSection: RefSection;
  cycleMacroLayerSummary: StockCycleMacroLayerSummary | null;
  candidateHistoryPortfolioBacktestQuery: QueryState;
  candidateHistoryPortfolioBacktestPayload: LivermoreCandidateHistoryPortfolioBacktestPayload | null;
  cycleProxyBacktestQuery: QueryState;
  cycleProxyBacktestPayload: LivermoreCycleProxyBacktestPayload | null;
  themeBreakoutPanelSummary: StrategyModuleCardProps["summary"];
  strategyPayload: LivermoreStrategyPayload | null;
  themeBreakoutCards: StockThemeBreakoutCard[];
  themeEvidenceRows: StockThemeEvidenceStateRow[];
  themeBreakoutReviewItems: StockThemeBreakoutReviewItem[];
  themeBreakoutUnsupported: LivermoreStrategyPayload["unsupported_outputs"][number] | undefined;
  consensusReviewPanelSummary: StrategyModuleCardProps["summary"];
  consensusSummary: ConsensusSummary;
  setDetailSelection: (selection: StockDetailSelection | null) => void;
  client: ReturnType<typeof useApiClient>;
  analyticsAsOf: StrategyReviewCardsProps["analyticsAsOf"];
  currentMarketState: StrategyReviewCardsProps["currentMarketState"];
  strategyPrioritySection: SeenSection;
  strategyScorePayload: StrategyReviewCardsProps["strategyScorePayload"];
  strategyScoreQuery: QueryState;
  strategyPriorityRows: StrategyReviewCardsProps["strategyPriorityRows"];
  marketPriorityPanelSummary: StrategyReviewCardsProps["marketPriorityPanelSummary"];
  strategyBacktestPayload: StrategyReviewCardsProps["strategyBacktestPayload"];
  strategyBacktestRows: StrategyBacktestRow[];
  strategyBacktestSampleCount: StrategyReviewCardsProps["strategyBacktestSampleCount"];
  strategyBacktestWindow: StrategyReviewCardsProps["strategyBacktestWindow"];
  strategyBacktestDateRangeLabel: StrategyReviewCardsProps["strategyBacktestDateRangeLabel"];
  strategyBacktestQuery: QueryState;
  strategyBacktestPanelSummary: StrategyReviewCardsProps["strategyBacktestPanelSummary"];
  strategyBacktestSection: RefSection;
  strategyOptimizationPayload: StrategyReviewCardsProps["strategyOptimizationPayload"];
  strategyOptimizationRows: StrategyReviewCardsProps["strategyOptimizationRows"];
  strategyOptimizationQuery: QueryState;
  strategyOptimizationPanelSummary: StrategyReviewCardsProps["strategyOptimizationPanelSummary"];
  strategyOptimizationSection: RefSection;
  observationPoolsPanelSummary: StrategyModuleCardProps["summary"];
  gateState: string | null | undefined;
  meanReversionMarketActive: boolean;
  meanReversionPayload: MeanReversionCandidatesPayload | undefined;
  factorScreenPayload: FactorScreenCandidatesPayload | undefined;
  factorScreenCoverageNote: string | null;
  eventsMonitoringPanelSummary: StrategyModuleCardProps["summary"];
  eventMonitorRows: StockAnalysisEventMonitorRow[];
};

export function StockAnalysisStrategyCardGrid({
  cycleRotationFramework,
  cycleRotationPanelSummary,
  isStrategyCardExpanded,
  toggleStrategyCard,
  cycleFrameworkSection,
  cycleMacroLayerSummary,
  candidateHistoryPortfolioBacktestQuery,
  candidateHistoryPortfolioBacktestPayload,
  cycleProxyBacktestQuery,
  cycleProxyBacktestPayload,
  themeBreakoutPanelSummary,
  strategyPayload,
  themeBreakoutCards,
  themeEvidenceRows,
  themeBreakoutReviewItems,
  themeBreakoutUnsupported,
  consensusReviewPanelSummary,
  consensusSummary,
  setDetailSelection,
  client,
  analyticsAsOf,
  currentMarketState,
  strategyPrioritySection,
  strategyScorePayload,
  strategyScoreQuery,
  strategyPriorityRows,
  marketPriorityPanelSummary,
  strategyBacktestPayload,
  strategyBacktestRows,
  strategyBacktestSampleCount,
  strategyBacktestWindow,
  strategyBacktestDateRangeLabel,
  strategyBacktestQuery,
  strategyBacktestPanelSummary,
  strategyBacktestSection,
  strategyOptimizationPayload,
  strategyOptimizationRows,
  strategyOptimizationQuery,
  strategyOptimizationPanelSummary,
  strategyOptimizationSection,
  observationPoolsPanelSummary,
  gateState,
  meanReversionMarketActive,
  meanReversionPayload,
  factorScreenPayload,
  factorScreenCoverageNote,
  eventsMonitoringPanelSummary,
  eventMonitorRows,
}: StockAnalysisStrategyCardGridProps) {
  const consensusReviewDetail = consensusReviewPanelSummary?.detail ?? "No consensus review observations.";
  const consensusReviewBadgeLabel =
    consensusReviewPanelSummary?.badgeLabel ?? (consensusReviewPanelSummary?.tone === "positive" ? "已就绪" : "待复核");
  const observationPoolsBadgeLabel = observationPoolsPanelSummary?.badgeLabel ?? "观察池";
  const eventsMonitoringBadgeLabel = eventsMonitoringPanelSummary?.badgeLabel ?? "事件";

  return (
    <>
              <div className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-6">
              {cycleRotationFramework ? (
                <StrategyModuleCard
                  id="cycle-rotation"
                  title={cycleRotationFramework.display_name}
                  subtitle="周期轮动"
                  badgeLabel={
                    cycleRotationPanelSummary?.badgeLabel ??
                    localizeImplementationStage(cycleRotationFramework.implementation_stage)
                  }
                  summary={cycleRotationPanelSummary}
                  summaryTestId="stock-analysis-cycle-panel-summary"
                  expanded={isStrategyCardExpanded("cycle-rotation")}
                  onToggleExpand={() => toggleStrategyCard("cycle-rotation")}
                  mountDetail
                  sectionRef={cycleFrameworkSection.ref}
                  sectionTestId="stock-analysis-cycle-rotation-framework"
                  className="flex flex-col gap-4"
                >
                  <StrategyPanelComplianceDetails
                    complianceDetail={cycleRotationPanelSummary?.complianceDetail}
                    testId="stock-analysis-cycle-panel-compliance"
                  />
                  <StockAnalysisCycleRuleSummary framework={cycleRotationFramework} />
                  {cycleMacroLayerSummary ? (
                    <div
                      className="flex flex-col gap-2 p-4 bg-default-50 rounded-large"
                      data-testid="stock-analysis-cycle-macro-layer"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <strong className="text-foreground">宏观层</strong>
                        <Chip size="sm" variant="flat">
                          {cycleMacroLayerSummary.statusLabel}
                        </Chip>
                      </div>
                      <p className="text-sm text-foreground">
                        宏观分 {cycleMacroLayerSummary.macroScoreLabel}
                      </p>
                      <p className="text-sm text-default-600">{cycleEvidenceLabel(cycleMacroLayerSummary.evidence)}</p>
                      <small className="text-xs text-default-500">
                        {cycleInputSummary(cycleMacroLayerSummary.availableInputs, cycleMacroLayerSummary.missingInputs)}
                      </small>
                      {cycleMacroLayerSummary.macroGapLabels.length > 0 ? (
                        <div className="flex flex-wrap gap-2 mt-2">
                          {cycleMacroLayerSummary.macroGapLabels.map((gap) => (
                            <Chip key={gap} size="sm" variant="bordered">{cycleGapLabel(gap)}</Chip>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {cycleRotationFramework.lifecourt_overlay ? (
                    <div className="flex flex-col gap-2 p-4 bg-warning-50 rounded-large mt-4">
                      <strong className="text-foreground">{cycleRotationFramework.lifecourt_overlay.display_name}</strong>
                      <p className="text-sm text-default-600">{cycleBoundaryLabel(cycleRotationFramework.lifecourt_overlay.boundary)}</p>
                      <small className="text-xs text-default-500">
                        {cycleInputSummary(
                          cycleRotationFramework.lifecourt_overlay.available_inputs,
                          cycleRotationFramework.lifecourt_overlay.missing_inputs,
                        )}
                      </small>
                      <div className="flex flex-wrap gap-2 mt-2">
                        {cycleRotationFramework.lifecourt_overlay.life_long_gates.map((gate) => (
                          <Chip key={gate} size="sm" variant="flat" color="warning">{cycleConstraintLabel(gate)}</Chip>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                    {cycleRotationFramework.layers.map((layer) => (
                      <article className="flex flex-col gap-1 p-3 border border-default-200 rounded-medium bg-background" key={layer.key}>
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-foreground">{cycleLayerTitleLabel(layer)}</span>
                          <strong className="text-sm text-foreground">{cycleLayerWeightLabel(layer)}</strong>
                        </div>
                        <em className="not-italic text-xs text-default-500">{localizeImplementationStage(layer.status)}</em>
                        <p className="text-sm text-default-600">{cycleEvidenceLabel(layer.evidence)}</p>
                        <small className="text-xs text-default-500">
                          {cycleInputSummary(layer.available_inputs, layer.missing_inputs)}
                        </small>
                      </article>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-2 mt-4">
                    {cycleRotationFramework.constraints.map((constraint) => (
                      <Chip key={constraint} size="sm" variant="bordered">{cycleConstraintLabel(constraint)}</Chip>
                    ))}
                  </div>
                  <div
                    className="flex flex-col gap-4 p-4 mt-4 border border-default-200 rounded-large"
                    data-testid="stock-analysis-candidate-history-portfolio-backtest"
                  >
                    {candidateHistoryPortfolioBacktestQuery.isLoading ? (
                      <p className="text-default-500 text-sm py-4 text-center">组合回测加载中。</p>
                    ) : null}
                    {candidateHistoryPortfolioBacktestQuery.isError ? (
                      <p className="text-warning text-sm py-4 px-4 bg-warning-50 rounded-medium">
                        组合回测暂不可用：{strategyPanelErrorMessage(candidateHistoryPortfolioBacktestQuery.error)}
                      </p>
                    ) : null}
                    {!candidateHistoryPortfolioBacktestQuery.isLoading &&
                    !candidateHistoryPortfolioBacktestQuery.isError ? (
                      candidateHistoryPortfolioBacktestPayload?.status === "portfolio_proxy" &&
                      candidateHistoryPortfolioBacktestPayload.summary ? (
                        <>
                          <BacktestBoundaryChips
                            label="组合回测"
                            missingInputs={candidateHistoryPortfolioBacktestPayload.missing_full_strategy_inputs}
                            testId="stock-analysis-portfolio-backtest-boundary"
                          />
                          {formatCostBasisLabel(candidateHistoryPortfolioBacktestPayload.summary.cost_basis) ? (
                            <small
                              className="text-xs text-default-500"
                              data-testid="stock-analysis-portfolio-backtest-cost-basis"
                            >
                              {formatCostBasisLabel(candidateHistoryPortfolioBacktestPayload.summary.cost_basis)}
                            </small>
                          ) : null}
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-2">
                            <div className="flex flex-col gap-1">
                              <span className="text-xs text-default-500">组合回测收益</span>
                              <strong className="text-foreground">
                                {formatBacktestSignedPercent(
                                  candidateHistoryPortfolioBacktestPayload.summary.cumulative_return,
                                )}
                              </strong>
                            </div>
                            <div className="flex flex-col gap-1">
                              <span className="text-xs text-default-500">最大上涨区间</span>
                              <strong className="text-success">
                                {formatBacktestSignedPercent(
                                  candidateHistoryPortfolioBacktestPayload.summary.max_gain.return,
                                )}
                              </strong>
                              <small className="text-xs text-default-400">
                                {candidateHistoryPortfolioBacktestPayload.summary.max_gain.start_date} 至{" "}
                                {candidateHistoryPortfolioBacktestPayload.summary.max_gain.end_date}
                              </small>
                            </div>
                            <div className="flex flex-col gap-1">
                              <span className="text-xs text-default-500">最大回撤区间</span>
                              <strong className="text-danger">
                                {formatBacktestSignedPercent(
                                  candidateHistoryPortfolioBacktestPayload.summary.max_drawdown.return,
                                )}
                              </strong>
                              <small className="text-xs text-default-400">
                                {candidateHistoryPortfolioBacktestPayload.summary.max_drawdown.peak_date} 至{" "}
                                {candidateHistoryPortfolioBacktestPayload.summary.max_drawdown.trough_date}
                              </small>
                            </div>
                          </div>
                        </>
                      ) : (
                        <CompactStatusTile
                          icon={<LineChartOutlined />}
                          label="组合回测"
                          value="样本不足"
                          testId="stock-analysis-portfolio-backtest-empty"
                        />
                      )
                    ) : null}
                  </div>
                  <div
                    className="flex flex-col gap-4 p-4 mt-4 border border-default-200 rounded-large"
                    data-testid="stock-analysis-cycle-proxy-backtest"
                  >
                    {cycleProxyBacktestQuery.isLoading ? (
                      <p className="text-default-500 text-sm py-4 text-center">代理回测加载中。</p>
                    ) : null}
                    {cycleProxyBacktestQuery.isError ? (
                      <p className="text-warning text-sm py-4 px-4 bg-warning-50 rounded-medium">
                        代理回测暂不可用：{strategyPanelErrorMessage(cycleProxyBacktestQuery.error)}
                      </p>
                    ) : null}
                    {!cycleProxyBacktestQuery.isLoading && !cycleProxyBacktestQuery.isError ? (
                      cycleProxyBacktestPayload?.status === "proxy" && cycleProxyBacktestPayload.summary ? (
                        <>
                          <BacktestBoundaryChips
                            label="代理回测"
                            missingInputs={cycleProxyBacktestPayload.missing_full_strategy_inputs}
                            testId="stock-analysis-cycle-proxy-boundary"
                          />
                          {formatCostBasisLabel(cycleProxyBacktestPayload.summary.cost_basis) ? (
                            <small
                              className="text-xs text-default-500"
                              data-testid="stock-analysis-cycle-proxy-cost-basis"
                            >
                              {formatCostBasisLabel(cycleProxyBacktestPayload.summary.cost_basis)}
                            </small>
                          ) : null}
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-2">
                            <div className="flex flex-col gap-1">
                              <span className="text-xs text-default-500">累计收益</span>
                              <strong className="text-foreground">{formatBacktestSignedPercent(cycleProxyBacktestPayload.summary.cumulative_return)}</strong>
                            </div>
                            <div className="flex flex-col gap-1">
                              <span className="text-xs text-default-500">最大上涨区间</span>
                              <strong className="text-success">
                                {formatBacktestSignedPercent(cycleProxyBacktestPayload.summary.max_gain.return)}
                              </strong>
                              <small className="text-xs text-default-400">
                                {cycleProxyBacktestPayload.summary.max_gain.start_date} 至{" "}
                                {cycleProxyBacktestPayload.summary.max_gain.end_date}
                              </small>
                            </div>
                            <div className="flex flex-col gap-1">
                              <span className="text-xs text-default-500">最大回撤区间</span>
                              <strong className="text-danger">
                                {formatBacktestSignedPercent(cycleProxyBacktestPayload.summary.max_drawdown.return)}
                              </strong>
                              <small className="text-xs text-default-400">
                                {cycleProxyBacktestPayload.summary.max_drawdown.peak_date} 至{" "}
                                {cycleProxyBacktestPayload.summary.max_drawdown.trough_date}
                              </small>
                            </div>
                          </div>
                        </>
                      ) : (
                        <CompactStatusTile
                          icon={<LineChartOutlined />}
                          label="代理回测"
                          value="样本不足"
                          testId="stock-analysis-cycle-proxy-empty"
                        />
                      )
                    ) : null}
                  </div>
                </StrategyModuleCard>
              ) : null}


              <StrategyModuleCard
                id="theme-breakout"
                title="题材突变观察"
                subtitle="题材代理"
                badgeLabel={
                  themeBreakoutPanelSummary?.badgeLabel ??
                  `${localizeThemeRadarBadge(
                    strategyPayload?.theme_breakout?.is_proxy === true,
                    strategyPayload?.theme_breakout?.formula_version,
                  )}${themeBreakoutCards.length > 0 ? ` · ${themeBreakoutCards.length} 项` : ""}`
                }
                summary={themeBreakoutPanelSummary}
                summaryTestId="stock-analysis-theme-panel-summary"
                expanded={isStrategyCardExpanded("theme-breakout")}
                onToggleExpand={() => toggleStrategyCard("theme-breakout")}
                mountDetail
                sectionTestId="stock-analysis-theme-breakout"
              >
                <StrategyPanelComplianceDetails
                            complianceDetail={themeBreakoutPanelSummary?.complianceDetail}
                            testId="stock-analysis-theme-panel-compliance"
                          />
                <StockAnalysisThemeBreakoutPanel
                  cards={themeBreakoutCards}
                  evidenceRows={themeEvidenceRows}
                  reviewItems={themeBreakoutReviewItems}
                  emptyMessage={
                    themeBreakoutUnsupported
                      ? themeBreakoutPanelSummary?.detail ?? "No theme breakout observations."
                      : "No theme breakout observations."
                  }
                />
              </StrategyModuleCard>

              <StrategyModuleCard
                id="consensus-review"
                title="历史复核 / T+5 共振"
                subtitle="T+5 共振"
                badgeLabel={consensusReviewBadgeLabel}
                summary={consensusReviewPanelSummary}
                summaryTestId="stock-analysis-consensus-panel-summary"
                expanded={isStrategyCardExpanded("consensus-review")}
                onToggleExpand={() => toggleStrategyCard("consensus-review")}
                mountDetail
                sectionTestId="stock-analysis-consensus-review-panel"
              >
                <div
                  className="flex flex-col gap-1 mb-4"
                  data-testid="stock-analysis-historical-review-section"
                >
                  <strong className="text-foreground">历史复核摘要</strong>
                  <span className="text-sm text-default-500">T+5 共振 · 候选历史与评分</span>
                </div>
                <div className="flex flex-col gap-4" data-testid="stock-analysis-consensus">
                          <div className="flex flex-wrap gap-4 text-sm text-default-600 p-4 bg-default-50 rounded-large">
                            <span>
                              趋势 <strong className="text-foreground">{consensusSummary.strategyCounts.livermore}</strong> 只
                            </span>
                            <span>
                              融合策略 <strong className="text-foreground">{consensusSummary.strategyCounts.hybrid_fusion}</strong> 只
                            </span>
                            <span>
                              超跌反弹观察 <strong className="text-foreground">{consensusSummary.strategyCounts.mean_reversion}</strong> 只
                            </span>
                            <span>
                              多因子 <strong className="text-foreground">{consensusSummary.strategyCounts.factor_screen}</strong> 只
                            </span>
                            <span>
                              合计去重 <strong className="text-foreground">{consensusSummary.totalUnion}</strong> 只
                            </span>
                          </div>

                          {!consensusSummary.hasAnyStrategy ? (
                            <p className="text-default-500 text-sm py-8 text-center">
                              {consensusReviewDetail}
                            </p>
                          ) : consensusSummary.items.length === 0 ? (
                            <p className="text-default-500 text-sm py-8 text-center">
                              {consensusReviewDetail}
                            </p>
                          ) : (
                            <ul className="flex flex-col divide-y divide-default-100">
                              {consensusSummary.items.map((row) => {
                                const isTriple = row.consensusCount >= 3;
                                const openDetail = () => {
                                  setDetailSelection(buildConsensusDetailSelection(row));
                                };
                                return (
                                  <li
                                    key={row.stockCode}
                                    className={`flex flex-col gap-2 p-3 hover:bg-default-50 transition-colors cursor-pointer${
                                      isTriple ? " bg-primary-50/50" : ""
                                    }`}
                                    data-testid={`consensus-row-${row.stockCode}`}
                                    onClick={openDetail}
                                    role="button"
                                    tabIndex={0}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter" || e.key === " ") {
                                        e.preventDefault();
                                        openDetail();
                                      }
                                    }}
                                  >
                                    <div className="flex items-center gap-3">
                                      <Chip size="sm" color={isTriple ? "primary" : "default"} variant="flat">
                                        {isTriple ? "三策略共振" : "核心共振"}
                                      </Chip>
                                      <strong className="text-foreground">
                                        <span className="font-mono">
                                          {row.stockCode}
                                        </span>{" "}
                                        {row.stockName}
                                      </strong>
                                      <small className="font-mono text-default-500">
                                        {row.sectorName || "-"}
                                      </small>
                                      <span className="flex gap-2 ml-auto">
                                        {row.strategies.map((kind) => (
                                          <Chip key={kind} size="sm" variant="flat" color="default">
                                            {consensusStrategyLabel(kind)}
                                          </Chip>
                                        ))}
                                      </span>
                                    </div>
                                    <div className="flex gap-4 text-xs text-default-500 ml-10">
                                      {row.livermoreRank != null && (
                                        <span>趋势 #{row.livermoreRank}</span>
                                      )}
                                      {row.hybridFusionRank != null && (
                                        <span>融合策略 #{row.hybridFusionRank}</span>
                                      )}
                                      {row.meanReversionRank != null && (
                                        <span>超跌反弹 #{row.meanReversionRank}</span>
                                      )}
                                      {row.factorScreenRank != null && (
                                        <span>多因子 #{row.factorScreenRank}</span>
                                      )}
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          )}
                          <p className="text-xs text-default-400 mt-2 text-right">
                            T+5 共振 · 超跌仅观察
                          </p>
                        </div>
              </StrategyModuleCard>

                            <StockAnalysisStrategyReviewCards
                client={client}
                analyticsAsOf={analyticsAsOf}
                currentMarketState={currentMarketState}
                strategyPrioritySeen={strategyPrioritySection.seen}
                strategyScorePayload={strategyScorePayload}
                strategyScoreLoading={strategyScoreQuery.isLoading}
                strategyScoreError={strategyScoreQuery.isError}
                strategyScoreErrorValue={strategyScoreQuery.error}
                strategyPriorityRows={strategyPriorityRows}
                marketPriorityPanelSummary={marketPriorityPanelSummary}
                marketPriorityExpanded={isStrategyCardExpanded("market-priority")}
                onToggleMarketPriority={() => toggleStrategyCard("market-priority")}
                marketPrioritySectionRef={strategyPrioritySection.ref}
                strategyBacktestPayload={strategyBacktestPayload}
                strategyBacktestRows={strategyBacktestRows}
                strategyBacktestSampleCount={strategyBacktestSampleCount}
                strategyBacktestWindow={strategyBacktestWindow}
                strategyBacktestDateRangeLabel={strategyBacktestDateRangeLabel}
                strategyBacktestLoading={strategyBacktestQuery.isLoading}
                strategyBacktestError={strategyBacktestQuery.isError}
                strategyBacktestErrorValue={strategyBacktestQuery.error}
                strategyBacktestPanelSummary={strategyBacktestPanelSummary}
                strategyBacktestExpanded={isStrategyCardExpanded("strategy-backtest")}
                onToggleStrategyBacktest={() => toggleStrategyCard("strategy-backtest")}
                strategyBacktestSectionRef={strategyBacktestSection.ref}
                strategyOptimizationPayload={strategyOptimizationPayload}
                strategyOptimizationRows={strategyOptimizationRows}
                strategyOptimizationLoading={strategyOptimizationQuery.isLoading}
                strategyOptimizationError={strategyOptimizationQuery.isError}
                strategyOptimizationErrorValue={strategyOptimizationQuery.error}
                strategyOptimizationPanelSummary={strategyOptimizationPanelSummary}
                strategyOptimizationExpanded={isStrategyCardExpanded("strategy-optimization")}
                onToggleStrategyOptimization={() => toggleStrategyCard("strategy-optimization")}
                strategyOptimizationSectionRef={strategyOptimizationSection.ref}
              />

              <StrategyModuleCard
                id="observation-pools"
                title="多策略观察池"
                subtitle="观察池"
                badgeLabel={observationPoolsBadgeLabel}
                summary={observationPoolsPanelSummary}
                summaryTestId="stock-analysis-observation-pools-panel-summary"
                expanded={isStrategyCardExpanded("observation-pools")}
                onToggleExpand={() => toggleStrategyCard("observation-pools")}
                mountDetail
                sectionTestId="stock-analysis-mean-reversion"
              >
                <div className="flex flex-col gap-4">
                  <div className="flex items-center justify-between mb-2">
                    <strong className="text-foreground">超跌反弹观察池</strong>
                    <Chip size="sm" variant="flat">条件触发</Chip>
                  </div>
                          {gateState && !meanReversionMarketActive ? (
                            <CompactStatusTile
                              icon={<FireOutlined />}
                              label="超跌"
                              value="暂停"
                              tone="warning"
                              testId="stock-analysis-mean-reversion-empty"
                            />
                          ) : null}
                          {meanReversionMarketActive && !meanReversionPayload ? (
                            <CompactStatusTile
                              icon={<FireOutlined />}
                              label="超跌"
                              value="未就绪"
                              tone="warning"
                              testId="stock-analysis-mean-reversion-empty"
                            />
                          ) : null}
                          {meanReversionMarketActive &&
                          meanReversionPayload &&
                          meanReversionPayload.items.length === 0 ? (
                            <CompactStatusTile
                              icon={<FireOutlined />}
                              label="超跌"
                              value="0 候选"
                              testId="stock-analysis-mean-reversion-empty"
                            />
                          ) : null}
                          {meanReversionMarketActive &&
                          meanReversionPayload &&
                          meanReversionPayload.items.length > 0 ? (
                            <ul className="flex flex-col divide-y divide-default-100">
                              {meanReversionPayload.items.map((row) => {
                                const openMeanReversionDetail = () => {
                                  const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                                  setDetailSelection(buildMeanReversionDetailSelection({ row, ranks }));
                                };

                                return (
                                  <li
                                    key={row.stock_code}
                                    className="flex flex-col gap-2 p-3 hover:bg-default-50 transition-colors cursor-pointer"
                                    onClick={openMeanReversionDetail}
                                    role="button"
                                    tabIndex={0}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter" || e.key === " ") {
                                        e.preventDefault();
                                        openMeanReversionDetail();
                                      }
                                    }}
                                  >
                                    <div>
                                      <strong>#{row.rank}</strong>{" "}
                                      <span className="font-mono">{row.stock_code}</span>{" "}
                                      {row.stock_name}{" "}
                                      <small className="font-mono text-default-500">
                                        {row.sector_name || row.sector_code || "-"}
                                      </small>
                                    </div>
                                    <div className="flex gap-4 text-xs text-default-500 font-mono ml-6">
                                      <span className="text-danger">
                                        20日回撤{" "}
                                        {row.drawdown_20d != null && Number.isFinite(row.drawdown_20d)
                                          ? `${(row.drawdown_20d * 100).toFixed(1)}%`
                                          : "待补"}
                                      </span>
                                      <span>
                                        收盘强度{" "}
                                        {row.close_strength != null && Number.isFinite(row.close_strength)
                                          ? `${(row.close_strength * 100).toFixed(0)}%`
                                          : "待补"}
                                      </span>
                                      <span>
                                        量比{" "}
                                        {row.vol_ratio != null && Number.isFinite(row.vol_ratio)
                                          ? `${row.vol_ratio.toFixed(1)}x`
                                          : "待补"}
                                      </span>
                                      <span>
                                        得分{" "}
                                        {row.score != null && Number.isFinite(row.score)
                                          ? row.score.toFixed(2)
                                          : "待补"}
                                      </span>
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          ) : null}
                          <div className="flex flex-wrap gap-2 mt-4" aria-label="超跌筛选规则">
                            {["价格回撤", "企稳", "放量", "门控停用"].map((label) => (
                              <Chip
                                key={label}
                                size="sm" variant="flat"
                              >
                                <FireOutlined aria-hidden="true" /> {label}
                              </Chip>
                            ))}
                          </div>
                        </div>
                <div className="flex flex-col gap-4 mt-8">
                  <div className="flex items-center justify-between mb-2">
                    <strong className="text-foreground">多因子选股</strong>
                    <Chip size="sm" variant="flat">
                      {factorScreenPayload?.candidate_count ?? 0} 只 ·{" "}
                      {factorScreenCoverageNote ?? "数据未就绪"}
                    </Chip>
                  </div>
                          {!factorScreenPayload ? (
                            <CompactStatusTile
                              icon={<DatabaseOutlined />}
                              label="多因子"
                              value="未就绪"
                              tone="warning"
                              testId="stock-analysis-factor-screen-empty"
                            />
                          ) : factorScreenPayload.items.length === 0 ? (
                            <CompactStatusTile
                              icon={<DatabaseOutlined />}
                              label="多因子"
                              value="0 候选"
                              testId="stock-analysis-factor-screen-empty"
                            />
                          ) : (
                            <ul className="flex flex-col divide-y divide-default-100">
                              {factorScreenPayload.items.map((row) => (
                                <li
                                  key={row.stock_code}
                                  className="flex flex-col gap-2 p-3 hover:bg-default-50 transition-colors cursor-pointer"
                                  onClick={() => {
                                    const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                                    setDetailSelection(buildFactorScreenDetailSelection({ row, ranks }));
                                  }}
                                  role="button"
                                  tabIndex={0}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter" || e.key === " ") {
                                      e.preventDefault();
                                      const ranks = lookupStockStrategyRanks(strategyPayload ?? null, row.stock_code);
                                      setDetailSelection(buildFactorScreenDetailSelection({ row, ranks }));
                                    }
                                  }}
                                >
                                  <div>
                                    <strong>#{row.rank}</strong>{" "}
                                    <span className="font-mono">{row.stock_code}</span>{" "}
                                    {row.stock_name}{" "}
                                    <small className="font-mono text-default-500">
                                      {row.sector_name || row.industry || "-"}
                                    </small>
                                  </div>
                                  <div className="flex gap-4 text-xs text-default-500 font-mono ml-6">
                                    <span>得分 {row.score.toFixed(3)}</span>
                                    {row.pe != null && <span>PE {row.pe.toFixed(1)}</span>}
                                    {row.roe != null && <span>ROE {(row.roe * 100).toFixed(1)}%</span>}
                                    {row.three_month_return != null && (
                                      <span>3月 {(row.three_month_return * 100).toFixed(1)}%</span>
                                    )}
                                    {row.dividend_yield != null && row.dividend_yield > 0 && (
                                      <span>股息 {(row.dividend_yield * 100).toFixed(2)}%</span>
                                    )}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          )}
                          <div className="flex flex-wrap gap-2 mt-4" aria-label="多因子选股因子">
                            {["价值", "质量", "动量", "低波", "股息"].map((label) => (
                              <Chip
                                key={label}
                                size="sm" variant="flat"
                              >
                                <DatabaseOutlined aria-hidden="true" /> {label}
                              </Chip>
                            ))}
                            {factorScreenCoverageNote ? (
                              <Chip
                                size="sm" color="primary" variant="flat"
                                title={factorScreenCoverageNote}
                              >
                                覆盖 {compactText(factorScreenCoverageNote, 14)}
                              </Chip>
                            ) : null}
                          </div>
                        </div>
              </StrategyModuleCard>

              <StrategyModuleCard
                id="events-monitoring"
                title="关键事件与监控"
                subtitle="事件风险"
                badgeLabel={eventsMonitoringBadgeLabel}
                summary={eventsMonitoringPanelSummary}
                summaryTestId="stock-analysis-events-panel-summary"
                expanded={isStrategyCardExpanded("events-monitoring")}
                onToggleExpand={() => toggleStrategyCard("events-monitoring")}
                mountDetail
                sectionTestId="stock-analysis-events-monitoring"
              >
                {eventMonitorRows.length > 0 ? (
                  <div className="overflow-x-auto w-full mt-4">
                    <table className="w-full text-sm text-left border-collapse">
                      <thead>
                        <tr className="border-b border-default-200">
                          <th scope="col" className="py-2 px-3">来源</th>
                          <th scope="col" className="py-2 px-3">级别</th>
                          <th scope="col" className="py-2 px-3">事件</th>
                          <th scope="col" className="py-2 px-3">影响</th>
                          <th scope="col" className="py-2 px-3">明细</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-default-100">
                        {eventMonitorRows.map((row) => (
                          <tr key={row.key} data-level={row.level} className="hover:bg-default-50">
                            <td className="py-2 px-3">{eventSourceLabel(row.source)}</td>
                            <td className="py-2 px-3">
                              <Chip size="sm" variant="flat" color={row.level === "error" ? "danger" : row.level === "warning" ? "warning" : "default"}>
                                {eventLevelLabel(row.level)}
                              </Chip>
                            </td>
                            <td className="py-2 px-3">{eventNameLabel(row)}</td>
                            <td className="py-2 px-3">{eventImpactLabel(row)}</td>
                            <td className="py-2 px-3" title={eventDetailLabel(row)}>{compactText(eventDetailLabel(row), 26)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                        ) : (
                  <CompactStatusTile
                    icon={<FireOutlined />}
                    label="关键事件"
                    value="0"
                    testId="stock-analysis-events-empty"
                  />
                )}
              </StrategyModuleCard>
              </div>
    </>
  );
}
