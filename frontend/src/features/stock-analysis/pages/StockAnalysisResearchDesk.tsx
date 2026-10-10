import { ResearchDeskActionRail } from "../components/research-desk/ResearchDeskActionRail";
import { ResearchDeskAuditLedger } from "../components/research-desk/ResearchDeskAuditLedger";
import { ResearchDeskDossier } from "../components/research-desk/ResearchDeskDossier";
import { ResearchDeskPool } from "../components/research-desk/ResearchDeskPool";
import { statusTone } from "../components/research-desk/researchDeskFormatters";
import type { StockAnalysisResearchDeskProps } from "../components/research-desk/types";
import styles from "./StockAnalysisResearchDesk.module.css";

export type {
  ResearchDeskDossierTab,
  ResearchDeskPoolTab,
  StockAnalysisResearchDeskProps,
} from "../components/research-desk/types";

/**
 * 三窗研究台布局：左侧标的池、中部研究档案、右侧风险与行动、底部审计日志。
 * 所有展示数据来自 `model`（buildStockAnalysisResearchDeskModel 的输出），
 * 这里只做布局与交互接线，不再从候选 rawFields 重新推导任何指标。
 */
export function StockAnalysisResearchDesk({
  model,
  queueSearchText,
  onQueueSearchTextChange,
  sectorOptions,
  selectedSectorCode,
  poolTab,
  onPoolTabChange,
  dossierTab,
  onDossierTabChange,
  poolCandidates,
  queueVisibleCount,
  queueTotalCount,
  queueCountLabel,
  interactionsDisabled = false,
  restrictedActionsDisabled = false,
  reviewQueueUsesHybridFusion,
  selectedCandidate,
  selectedCandidateCode,
  onSelectCandidate,
  watchlistCodes,
  onToggleWatchlist,
  selectedRisk,
  noteDraft,
  onNoteDraftChange,
  savedNote,
  onSaveNote,
  onOpenDeepResearch,
  onJumpToEvidence,
  onOpenDetailDrawer,
  onOpenHistory,
  sectorLinkSummary,
  sectorLinkFocus,
  queueEmptyHeadline,
  queueEmptyDetail,
  historyLoading,
  historyLoaded,
}: StockAnalysisResearchDeskProps) {
  const { summary } = model;
  const selectedWatchlisted =
    selectedCandidate != null && watchlistCodes.includes(selectedCandidate.stockCode);
  const selectedSectorLabel =
    sectorOptions.find(([code]) => code === selectedSectorCode)?.[1] ?? "按综合得分";
  const evidencePreviewItems = summary.sourceItems.slice(0, 5);

  return (
    <section
      className={styles.root}
      data-testid="stock-analysis-research-desk"
      aria-labelledby="stock-analysis-candidate-review-title"
    >
      <div className={styles.header}>
        <div>
          <p className={styles.eyebrow}>研究流程</p>
          <h2 id="stock-analysis-candidate-review-title" className={styles.title}>
            三窗研究台
          </h2>
          <p className={styles.description}>
            左侧筛池，中部归档，右侧只保留风险与动作。
          </p>
        </div>
        <div className={styles.headerMeta}>
          <span className={styles.metaChip} data-tone={statusTone(model.statusLabel)}>
            {model.statusLabel}
          </span>
          <span className={styles.metaChip} data-tone={model.progressionTone}>
            {model.progressionLabel}
          </span>
        </div>
      </div>

      <div className={styles.grid}>
        <ResearchDeskPool
          poolTab={poolTab}
          onPoolTabChange={onPoolTabChange}
          queueSearchText={queueSearchText}
          onQueueSearchTextChange={onQueueSearchTextChange}
          queueVisibleCount={queueVisibleCount}
          queueTotalCount={queueTotalCount}
          queueCountLabel={queueCountLabel}
          interactionsDisabled={interactionsDisabled}
          selectedSectorLabel={selectedSectorLabel}
          poolCandidates={poolCandidates}
          selectedCandidateCode={selectedCandidateCode}
          onSelectCandidate={onSelectCandidate}
          reviewQueueUsesHybridFusion={reviewQueueUsesHybridFusion}
          sectorLinkSummary={sectorLinkSummary}
          sectorLinkFocus={sectorLinkFocus}
          queueEmptyHeadline={queueEmptyHeadline}
          queueEmptyDetail={queueEmptyDetail}
          historyLoading={historyLoading}
          historyLoaded={historyLoaded}
        />
        <ResearchDeskDossier
          selectedCandidate={selectedCandidate}
          selectedRisk={selectedRisk}
          selectedWatchlisted={selectedWatchlisted}
          selectedDailyChange={summary.dailyChangeLabel}
          selectedQuote={summary.quoteValue}
          selectedCompositeScore={summary.compositeScoreLabel}
          compositeScoreNote={summary.compositeScoreNote}
          dossierTab={dossierTab}
          onDossierTabChange={onDossierTabChange}
          onJumpToEvidence={onJumpToEvidence}
          snapshotItems={model.selectedHeaderItems}
          marketSnapshotItems={summary.marketSnapshotItems}
          chartOption={summary.chartOption}
          decisionStatusLabel={model.statusLabel}
          decisionReason={model.decisionReason}
          keyFactItems={summary.keyFacts}
          evidenceItems={summary.evidenceItems}
          factorCells={summary.factorCells}
          timelineItems={summary.timelineItems}
          financeItems={summary.financeItems}
          evidencePreviewItems={evidencePreviewItems}
          metricCards={model.momentumCards}
          signalWindow={model.signalWindow}
          boundaryItems={model.eventBoundaryLines}
          selectedHistoryRows={model.historyRows}
          emptyDetail={model.decisionReason}
        />
        <ResearchDeskActionRail
          hardGateItems={model.hardGateItems.map((item) => item.text)}
          riskTags={model.riskTags}
          selectedRisk={selectedRisk}
          endpointItems={summary.sourceItems}
          selectedCandidate={selectedCandidate}
          selectedWatchlisted={selectedWatchlisted}
          onToggleWatchlist={onToggleWatchlist}
          noteDraft={noteDraft}
          onNoteDraftChange={onNoteDraftChange}
          savedNote={savedNote}
          onSaveNote={onSaveNote}
          onOpenDeepResearch={onOpenDeepResearch}
          onJumpToEvidence={onJumpToEvidence}
          onOpenDetailDrawer={onOpenDetailDrawer}
          onOpenHistory={onOpenHistory}
          actionsDisabled={interactionsDisabled || selectedCandidate == null}
          disabledReason={model.decisionReason}
          evidenceDisabled={interactionsDisabled}
          deepResearchDisabled={interactionsDisabled}
          riskUnavailableReason={
            restrictedActionsDisabled
              ? "盘前资格尚未闭合，风险退出结论未读取。"
              : undefined
          }
        />
        <ResearchDeskAuditLedger
          selectedStockName={selectedCandidate?.stockName ?? null}
          rows={model.displayAuditRows}
          totalVisibleRows={model.auditTotalCount}
          emptyDetail={model.decisionReason}
        />
      </div>
    </section>
  );
}

export default StockAnalysisResearchDesk;
