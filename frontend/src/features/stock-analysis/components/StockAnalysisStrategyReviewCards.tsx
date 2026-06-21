import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import type {
  BacktestWindowSummary,
  LivermoreCandidateHistoryPayload,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyScorePayload,
} from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import {
  backtestStatsText,
  buildStrategyBacktestMarketStateRows,
  buildStrategyBacktestRows,
  strategyBacktestHorizonLabels,
  strategyBacktestHorizonShortLabels,
  strategyBacktestHorizons,
  strategyDisplayLabel,
} from "../lib/stockAnalysisBacktestModel";
import {
  buildStrategyMaturityCandidates,
  buildStrategyMaturityWindow,
  buildStrategyPriorityHeadline,
  formatPriorityScore,
  resolveStrategyMaturityRow,
  strategyCandidateReturnText,
  strategyMaturityHorizonText,
  strategyMaturityRemainingText,
  strategyPriorityDiagnosticLabels,
  strategyPriorityReasonLabel,
  strategyPriorityScopeLabel,
  strategyPriorityStatusLabel,
  strategyPrioritySummaryReason,
  type StrategyPriorityRow,
} from "../lib/stockAnalysisPriorityModel";
import {
  strategyOptimizationDateWeightedText,
  strategyOptimizationPrimaryStats,
  strategyOptimizationReasonLabel,
  strategyOptimizationSliceLabel,
  strategyOptimizationSlicePair,
  type StrategyOptimizationSummary,
} from "../lib/stockAnalysisOptimizationModel";
import { localizeMarketDataStatus, localizeStockBackendText } from "../lib/stockAnalysisPageModel";
import { stockStrategyPanelErrorMessage } from "../lib/stockAnalysisPageCopy";
import { stockAnalysisReadQueryOptions } from "../lib/stockAnalysisQueryOptions";
import { StrategyModuleCard, type StrategyModuleCardProps } from "./StrategyModuleCard";

type StrategyBacktestRow = ReturnType<typeof buildStrategyBacktestRows>[number];

type StockAnalysisStrategyReviewCardsProps = {
  client: ReturnType<typeof useApiClient>;
  analyticsAsOf: string | null;
  currentMarketState: string | null;
  strategyPrioritySeen: boolean;
  strategyScorePayload: LivermoreStrategyScorePayload | null;
  strategyScoreLoading: boolean;
  strategyScoreError: boolean;
  strategyScoreErrorValue: unknown;
  strategyPriorityRows: StrategyPriorityRow[];
  marketPriorityPanelSummary: StrategyModuleCardProps["summary"];
  marketPriorityExpanded: boolean;
  onToggleMarketPriority: () => void;
  marketPrioritySectionRef?: StrategyModuleCardProps["sectionRef"];
  strategyBacktestPayload: LivermoreCandidateHistoryPayload | null;
  strategyBacktestRows: StrategyBacktestRow[];
  strategyBacktestSampleCount: number;
  strategyBacktestWindow: BacktestWindowSummary | null;
  strategyBacktestDateRangeLabel: string;
  strategyBacktestLoading: boolean;
  strategyBacktestError: boolean;
  strategyBacktestErrorValue: unknown;
  strategyBacktestPanelSummary: StrategyModuleCardProps["summary"];
  strategyBacktestExpanded: boolean;
  onToggleStrategyBacktest: () => void;
  strategyBacktestSectionRef?: StrategyModuleCardProps["sectionRef"];
  strategyOptimizationPayload: LivermoreStrategyOptimizationPayload | null;
  strategyOptimizationRows: StrategyOptimizationSummary[];
  strategyOptimizationLoading: boolean;
  strategyOptimizationError: boolean;
  strategyOptimizationErrorValue: unknown;
  strategyOptimizationPanelSummary: StrategyModuleCardProps["summary"];
  strategyOptimizationExpanded: boolean;
  onToggleStrategyOptimization: () => void;
  strategyOptimizationSectionRef?: StrategyModuleCardProps["sectionRef"];
};

export function StockAnalysisStrategyReviewCards({
  client,
  analyticsAsOf,
  currentMarketState,
  strategyPrioritySeen,
  strategyScorePayload,
  strategyScoreLoading,
  strategyScoreError,
  strategyScoreErrorValue,
  strategyPriorityRows,
  marketPriorityPanelSummary,
  marketPriorityExpanded,
  onToggleMarketPriority,
  marketPrioritySectionRef,
  strategyBacktestPayload,
  strategyBacktestRows,
  strategyBacktestSampleCount,
  strategyBacktestWindow,
  strategyBacktestDateRangeLabel,
  strategyBacktestLoading,
  strategyBacktestError,
  strategyBacktestErrorValue,
  strategyBacktestPanelSummary,
  strategyBacktestExpanded,
  onToggleStrategyBacktest,
  strategyBacktestSectionRef,
  strategyOptimizationPayload,
  strategyOptimizationRows,
  strategyOptimizationLoading,
  strategyOptimizationError,
  strategyOptimizationErrorValue,
  strategyOptimizationPanelSummary,
  strategyOptimizationExpanded,
  onToggleStrategyOptimization,
  strategyOptimizationSectionRef,
}: StockAnalysisStrategyReviewCardsProps) {
  const strategyPriorityHeadline = useMemo(
    () => buildStrategyPriorityHeadline(strategyPriorityRows),
    [strategyPriorityRows],
  );
  const strategyPriorityReason = useMemo(
    () => strategyPrioritySummaryReason(strategyPriorityRows),
    [strategyPriorityRows],
  );
  const strategyMaturityRow = useMemo(
    () => resolveStrategyMaturityRow(strategyPriorityRows),
    [strategyPriorityRows],
  );
  const strategyMaturityWindow = useMemo(
    () => buildStrategyMaturityWindow(strategyMaturityRow),
    [strategyMaturityRow],
  );
  const strategyMaturity = strategyMaturityWindow.maturity;
  const strategyMaturitySnapshots = strategyMaturityWindow.snapshots;
  const strategyBacktestMarketStateRows = useMemo(
    () => buildStrategyBacktestMarketStateRows(strategyBacktestPayload),
    [strategyBacktestPayload],
  );
  const strategyOptimizationSlices = useMemo(
    () => strategyOptimizationSlicePair(strategyOptimizationPayload),
    [strategyOptimizationPayload],
  );

  const strategyMaturityDetailQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-candidate-history-maturity-detail",
      strategyMaturityRow?.signal_kind ?? "__none",
      strategyMaturityWindow.snapshotFrom ?? "__none",
      strategyMaturityWindow.snapshotTo ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCandidateHistory({
        snapshotFrom: strategyMaturityWindow.snapshotFrom ?? undefined,
        snapshotTo: strategyMaturityWindow.snapshotTo ?? undefined,
        limit: 500,
      }),
    enabled: Boolean(
      analyticsAsOf &&
        strategyPrioritySeen &&
        strategyMaturityRow &&
        strategyMaturityWindow.snapshotFrom &&
        strategyMaturityWindow.snapshotTo,
    ),
    ...stockAnalysisReadQueryOptions,
  });

  const strategyMaturityCandidateRows = useMemo(
    () =>
      buildStrategyMaturityCandidates(
        (strategyMaturityDetailQuery.data?.result as LivermoreCandidateHistoryPayload | null) ?? null,
        strategyMaturityRow,
        strategyMaturitySnapshots,
      ),
    [strategyMaturityDetailQuery.data, strategyMaturityRow, strategyMaturitySnapshots],
  );

  const marketPriorityBadgeLabel =
    marketPriorityPanelSummary?.badgeLabel ??
    (strategyScorePayload?.primary_horizon === "return_1d"
      ? "T+1"
      : strategyScorePayload?.primary_horizon === "return_20d"
        ? "T+20"
        : "T+5");
  const strategyOptimizationBadgeLabel =
    strategyOptimizationPanelSummary?.badgeLabel ??
    (strategyOptimizationPayload?.primary_horizon === "return_1d"
      ? "T+1"
      : strategyOptimizationPayload?.primary_horizon === "return_10d"
        ? "T+10"
        : strategyOptimizationPayload?.primary_horizon === "return_20d"
          ? "T+20"
          : "T+5");

  return (
    <>
      <StrategyModuleCard
        id="market-priority"
        title="当前市场策略优先级"
        subtitle="T+5 排序"
        badgeLabel={marketPriorityBadgeLabel}
        summary={marketPriorityPanelSummary}
        summaryTestId="stock-analysis-market-priority-panel-summary"
        expanded={marketPriorityExpanded}
        onToggleExpand={onToggleMarketPriority}
        mountDetail
        sectionRef={marketPrioritySectionRef}
        sectionTestId="stock-analysis-market-priority-summary"
      >
        {strategyScoreLoading ? (
          <p className="stock-analysis-page__empty">当前市场策略优先级加载中。</p>
        ) : null}
        {strategyScoreError ? (
          <p className="stock-analysis-page__notice">
            当前市场策略优先级暂不可用：{stockStrategyPanelErrorMessage(strategyScoreErrorValue)}
          </p>
        ) : null}
        {!strategyScoreLoading && !strategyScoreError ? (
          <>
            <div className="stock-analysis-page__filter-status" data-testid="stock-analysis-market-priority-current">
              <span>
                {localizeMarketDataStatus(
                  strategyScorePayload?.current_market_state ?? currentMarketState ?? "UNKNOWN",
                )}
              </span>
              <strong>{strategyPriorityHeadline}</strong>
              <small>
                {strategyPriorityReason} · 阈值 {strategyScorePayload?.min_sample ?? 30} · 只读排序
              </small>
            </div>
            {strategyPriorityRows.length > 0 ? (
              <div className="stock-analysis-page__table-wrap">
                <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                  <thead>
                    <tr>
                      <th scope="col">策略</th>
                      <th scope="col">状态</th>
                      <th className="stock-analysis-page__table-number" scope="col">
                        评分
                      </th>
                      {strategyBacktestHorizons.map((horizon) => (
                        <th scope="col" key={horizon}>
                          {strategyBacktestHorizonLabels[horizon]}
                        </th>
                      ))}
                      <th scope="col">原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {strategyPriorityRows.map((row) => {
                      const diagnosticLabels = strategyPriorityDiagnosticLabels(row);
                      return (
                        <tr
                          key={`${row.market_state}:${row.signal_kind}`}
                          data-testid={`stock-analysis-market-priority-row-${row.market_state}-${row.signal_kind}`}
                        >
                          <td>{strategyDisplayLabel(row.strategy_label, row.signal_kind)}</td>
                          <td>{strategyPriorityStatusLabel(row.priority_label)}</td>
                          <td className="stock-analysis-page__table-number" data-testid="stock-analysis-market-priority-score">
                            {formatPriorityScore(row.priority_score)}
                          </td>
                          {strategyBacktestHorizons.map((horizon) => (
                            <td className="stock-analysis-page__table-number" key={horizon}>
                              {backtestStatsText(row.stats[horizon])}
                            </td>
                          ))}
                          <td>
                            <span>{strategyPriorityReasonLabel(row)}</span>
                            {diagnosticLabels.length > 0 ? (
                              <div className="stock-analysis-page__strategy-diagnostic-tags">
                                {diagnosticLabels.map((label) => (
                                  <span key={label}>{label}</span>
                                ))}
                              </div>
                            ) : null}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="stock-analysis-page__empty">样本不足</p>
            )}
            {strategyMaturityRow && strategyMaturity && strategyMaturitySnapshots.length > 0 ? (
              <div data-testid="stock-analysis-candidate-maturity">
                <div className="stock-analysis-page__filter-status">
                  <span>当前候选成熟进度</span>
                  <strong>
                    {strategyDisplayLabel(strategyMaturityRow.strategy_label, strategyMaturityRow.signal_kind)}
                    {strategyMaturityRow.diagnostics?.priority_scope_label
                      ? ` / ${strategyPriorityScopeLabel(strategyMaturityRow.diagnostics.priority_scope_label)}`
                      : ""}
                  </strong>
                  <small>
                    {strategyMaturityRemainingText(strategyMaturity)}，
                    {localizeStockBackendText(strategyMaturity.reason, strategyMaturityRow.signal_kind)}
                  </small>
                </div>
                <div className="stock-analysis-page__table-wrap">
                  <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                    <thead>
                      <tr>
                        <th scope="col">快照</th>
                        <th className="stock-analysis-page__table-number" scope="col">
                          候选
                        </th>
                        {strategyBacktestHorizons.map((horizon) => (
                          <th scope="col" key={horizon}>
                            {strategyBacktestHorizonShortLabels[horizon]}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {strategyMaturitySnapshots.map((snapshot) => (
                        <tr key={snapshot.snapshot_as_of_date}>
                          <td>{snapshot.snapshot_as_of_date}</td>
                          <td className="stock-analysis-page__table-number">{snapshot.candidate_count}</td>
                          {strategyBacktestHorizons.map((horizon) => (
                            <td key={horizon}>{strategyMaturityHorizonText(snapshot, horizon)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="stock-analysis-page__filter-status">
                  <span>候选明细</span>
                  <strong>
                    {strategyDisplayLabel(strategyMaturityRow.strategy_label, strategyMaturityRow.signal_kind)}
                  </strong>
                  <small>快照明细 · 按排名</small>
                </div>
                {strategyMaturityDetailQuery.isLoading ? (
                  <p className="stock-analysis-page__empty">候选明细加载中。</p>
                ) : null}
                {strategyMaturityDetailQuery.isError ? (
                  <p className="stock-analysis-page__notice">
                    候选明细暂不可用：{stockStrategyPanelErrorMessage(strategyMaturityDetailQuery.error)}
                  </p>
                ) : null}
                {!strategyMaturityDetailQuery.isLoading && !strategyMaturityDetailQuery.isError ? (
                  strategyMaturityCandidateRows.length > 0 ? (
                    <div className="stock-analysis-page__table-wrap">
                      <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                        <thead>
                          <tr>
                            <th scope="col">快照</th>
                            <th scope="col">排名</th>
                            <th scope="col">候选</th>
                            <th scope="col">板块</th>
                            <th className="stock-analysis-page__table-number" scope="col">
                              T+1
                            </th>
                            <th className="stock-analysis-page__table-number" scope="col">
                              T+5
                            </th>
                            <th className="stock-analysis-page__table-number" scope="col">
                              T+20
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {strategyMaturityCandidateRows.map((candidate) => (
                            <tr
                              key={`${candidate.snapshot_as_of_date}:${candidate.stock_code}:${candidate.candidate_rank}`}
                            >
                              <td>{candidate.snapshot_as_of_date}</td>
                              <td>#{candidate.candidate_rank}</td>
                              <td>
                                <span>{candidate.stock_name ?? candidate.stock_code}</span>
                                <small> {candidate.stock_code}</small>
                              </td>
                              <td>{candidate.sector_name ?? "-"}</td>
                              <td className="stock-analysis-page__table-number">
                                {strategyCandidateReturnText(candidate.return_1d)}
                              </td>
                              <td className="stock-analysis-page__table-number">
                                {strategyCandidateReturnText(candidate.return_5d)}
                              </td>
                              <td className="stock-analysis-page__table-number">
                                {strategyCandidateReturnText(candidate.return_20d)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="stock-analysis-page__empty">当前可见快照暂无候选明细。</p>
                  )
                ) : null}
              </div>
            ) : null}
          </>
        ) : null}
      </StrategyModuleCard>

      <StrategyModuleCard
        id="strategy-backtest"
        title="策略回溯表现"
        subtitle="回溯胜率"
        badgeLabel={strategyBacktestPanelSummary?.badgeLabel ?? strategyBacktestDateRangeLabel}
        summary={strategyBacktestPanelSummary}
        summaryTestId="stock-analysis-strategy-backtest-panel-summary"
        expanded={strategyBacktestExpanded}
        onToggleExpand={onToggleStrategyBacktest}
        mountDetail
        sectionRef={strategyBacktestSectionRef}
        sectionTestId="stock-analysis-strategy-backtest"
      >
        {strategyBacktestLoading ? (
          <p className="stock-analysis-page__empty">策略回溯表现加载中。</p>
        ) : null}
        {strategyBacktestError ? (
          <p className="stock-analysis-page__notice">
            策略回溯表现暂不可用：{stockStrategyPanelErrorMessage(strategyBacktestErrorValue)}
          </p>
        ) : null}
        {!strategyBacktestLoading && !strategyBacktestError ? (
          <>
            <div className="stock-analysis-page__filter-status">
              <span>有效样本</span>
              <strong>{strategyBacktestSampleCount} 条</strong>
              <small>
                完成日期 {strategyBacktestWindow?.replay_dates_completed ?? 0} / 待成熟{" "}
                {strategyBacktestWindow?.replay_dates_pending ?? 0} / 不支持{" "}
                {strategyBacktestWindow?.replay_dates_unsupported ?? 0}
              </small>
            </div>
            <div className="stock-analysis-page__table-wrap">
              <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                <thead>
                  <tr>
                    <th scope="col">策略</th>
                    <th scope="col">入选数</th>
                    {strategyBacktestHorizons.map((horizon) => (
                      <th scope="col" key={horizon}>
                        {strategyBacktestHorizonLabels[horizon]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {strategyBacktestRows.map((row) => (
                    <tr key={row.kind} data-testid={`stock-analysis-strategy-backtest-${row.kind}`}>
                      <td>{row.label}</td>
                      <td className="stock-analysis-page__table-number">{row.count}</td>
                      {strategyBacktestHorizons.map((horizon) => (
                        <td className="stock-analysis-page__table-number" key={horizon}>
                          {row.stats[horizon]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {strategyBacktestMarketStateRows.length > 0 ? (
              <div data-testid="stock-analysis-strategy-backtest-market-state">
                <p className="stock-analysis-page__footnote">市场状态分段</p>
                <div className="stock-analysis-page__table-wrap">
                  <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                    <thead>
                      <tr>
                        <th scope="col">市场状态</th>
                        <th scope="col">策略</th>
                        {strategyBacktestHorizons.map((horizon) => (
                          <th scope="col" key={horizon}>
                            {strategyBacktestHorizonLabels[horizon]}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {strategyBacktestMarketStateRows.map((row) => (
                        <tr
                          key={`${row.marketState}:${row.kind}`}
                          data-testid={`stock-analysis-strategy-backtest-market-state-${row.marketState}-${row.kind}`}
                        >
                          <td>{localizeMarketDataStatus(row.marketState)}</td>
                          <td>{row.label}</td>
                          {strategyBacktestHorizons.map((horizon) => (
                            <td className="stock-analysis-page__table-number" key={horizon}>
                              {row.stats[horizon]}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </StrategyModuleCard>

      <StrategyModuleCard
        id="strategy-optimization"
        title="优化诊断"
        subtitle="切片 T+5"
        badgeLabel={strategyOptimizationBadgeLabel}
        summary={strategyOptimizationPanelSummary}
        summaryTestId="stock-analysis-strategy-optimization-panel-summary"
        expanded={strategyOptimizationExpanded}
        onToggleExpand={onToggleStrategyOptimization}
        mountDetail
        sectionRef={strategyOptimizationSectionRef}
        sectionTestId="stock-analysis-strategy-optimization"
      >
        {strategyOptimizationLoading ? (
          <p className="stock-analysis-page__empty">优化诊断加载中。</p>
        ) : null}
        {strategyOptimizationError ? (
          <p className="stock-analysis-page__notice">
            优化诊断暂不可用：{stockStrategyPanelErrorMessage(strategyOptimizationErrorValue)}
          </p>
        ) : null}
        {!strategyOptimizationLoading && !strategyOptimizationError ? (
          <>
            <div className="stock-analysis-page__filter-status">
              <span>当前最新日期收益</span>
              <strong>
                {(strategyOptimizationPayload?.pending_summary.pending_rows ?? 0) > 0 ? "待成熟" : "已成熟"}
              </strong>
              <small>
                {localizeStockBackendText(
                  strategyOptimizationPayload?.pending_summary.message ?? "T+5 收益成熟状态待补。",
                )}
              </small>
            </div>
            <p className="stock-analysis-page__footnote">复核排序 · 不改规则</p>
            <div className="stock-analysis-page__filter-status">
              <span>三策略 T+5 排名</span>
              <strong>{strategyOptimizationRows.length} 组</strong>
              <small>阈值 {strategyOptimizationPayload?.min_sample ?? 30} · 收益/胜率/成熟度</small>
            </div>
            {strategyOptimizationRows.length > 0 ? (
              <div className="stock-analysis-page__table-wrap">
                <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                  <thead>
                    <tr>
                      <th scope="col">策略</th>
                      <th scope="col">复核状态</th>
                      <th scope="col">T+5 收益</th>
                      <th scope="col">按日等权</th>
                      <th scope="col">原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {strategyOptimizationRows.map((row) => (
                      <tr key={row.summary_key}>
                        <td>{strategyDisplayLabel(row.strategy_label, row.signal_kind)}</td>
                        <td>{strategyPriorityStatusLabel(row.recommendation.priority_label)}</td>
                        <td className="stock-analysis-page__table-number">
                          {backtestStatsText(strategyOptimizationPrimaryStats(row, strategyOptimizationPayload))}
                        </td>
                        <td className="stock-analysis-page__table-number">
                          {strategyOptimizationDateWeightedText(row, strategyOptimizationPayload)}
                        </td>
                        <td>{strategyOptimizationReasonLabel(row)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="stock-analysis-page__empty">优化诊断样本不足。</p>
            )}
            <div className="stock-analysis-page__filter-status">
              <span>各策略最强 / 最弱切片</span>
              <strong>
                {strategyOptimizationSlices.strongest
                  ? strategyOptimizationSliceLabel(strategyOptimizationSlices.strongest)
                  : "最强待补"}{" "}
                /{" "}
                {strategyOptimizationSlices.weakest
                  ? strategyOptimizationSliceLabel(strategyOptimizationSlices.weakest)
                  : "最弱待补"}
              </strong>
              <small>
                {strategyOptimizationSlices.weakest
                  ? `${strategyDisplayLabel(
                      strategyOptimizationSlices.weakest.strategy_label,
                      strategyOptimizationSlices.weakest.signal_kind,
                    )} ${strategyOptimizationSliceLabel(
                      strategyOptimizationSlices.weakest,
                    )}：${strategyPriorityStatusLabel(
                      strategyOptimizationSlices.weakest.recommendation.priority_label,
                    )}`
                  : "切片样本不足，暂不做降权判断。"}
              </small>
            </div>
            {strategyOptimizationSlices.strongest || strategyOptimizationSlices.weakest ? (
              <div className="stock-analysis-page__table-wrap">
                <table className="stock-analysis-page__table stock-analysis-page__table--dense">
                  <thead>
                    <tr>
                      <th scope="col">切片</th>
                      <th scope="col">策略</th>
                      <th scope="col">复核状态</th>
                      <th scope="col">T+5 收益</th>
                    </tr>
                  </thead>
                  <tbody>
                    {([
                      ["最强", strategyOptimizationSlices.strongest],
                      ["最弱", strategyOptimizationSlices.weakest],
                    ] as const).map(([label, slice]) =>
                      slice ? (
                        <tr key={`${label}:${slice.slice_key}`}>
                          <td>
                            {label}：{strategyOptimizationSliceLabel(slice)}
                          </td>
                          <td>{strategyDisplayLabel(slice.strategy_label, slice.signal_kind)}</td>
                          <td>{strategyPriorityStatusLabel(slice.recommendation.priority_label)}</td>
                          <td className="stock-analysis-page__table-number">
                            {backtestStatsText(strategyOptimizationPrimaryStats(slice, strategyOptimizationPayload))}
                          </td>
                        </tr>
                      ) : null,
                    )}
                  </tbody>
                </table>
              </div>
            ) : null}
          </>
        ) : null}
      </StrategyModuleCard>
    </>
  );
}
