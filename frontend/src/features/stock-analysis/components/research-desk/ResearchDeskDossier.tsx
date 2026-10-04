import type { EChartsOption } from "echarts";

import type {
  StockCandidateReviewQueueItem,
  StockRiskExitRow,
} from "../../lib/stockAnalysisPageModel";
import styles from "../../pages/StockAnalysisResearchDesk.module.css";
import { changeTone } from "./researchDeskFormatters";
import { ResearchDeskSummary } from "./ResearchDeskSummary";
import { ResearchDeskTabViews } from "./ResearchDeskTabViews";
import type {
  ResearchDeskDossierTab,
  ResearchDeskEndpointItem,
  ResearchDeskEvidenceItem,
  ResearchDeskFactorCell,
  ResearchDeskHistoryRow,
  ResearchDeskKeyValue,
  ResearchDeskMetricCard,
  ResearchDeskSignalWindow,
  ResearchDeskSnapshotItem,
  ResearchDeskTimelineItem,
} from "./types";

type ResearchDeskDossierProps = {
  selectedCandidate: StockCandidateReviewQueueItem | null;
  selectedRisk: StockRiskExitRow | null;
  selectedWatchlisted: boolean;
  selectedDailyChange: string;
  selectedQuote: string;
  selectedCompositeScore: string;
  compositeScoreNote: string | null;
  dossierTab: ResearchDeskDossierTab;
  onDossierTabChange: (tab: ResearchDeskDossierTab) => void;
  onJumpToEvidence: () => void;
  snapshotItems: ResearchDeskSnapshotItem[];
  marketSnapshotItems: ResearchDeskKeyValue[];
  chartOption: EChartsOption | null;
  decisionStatusLabel: string;
  decisionReason: string;
  keyFactItems: ResearchDeskKeyValue[];
  evidenceItems: ResearchDeskEvidenceItem[];
  factorCells: ResearchDeskFactorCell[];
  timelineItems: ResearchDeskTimelineItem[];
  financeItems: ResearchDeskKeyValue[];
  evidencePreviewItems: ResearchDeskEndpointItem[];
  metricCards: ResearchDeskMetricCard[];
  signalWindow: ResearchDeskSignalWindow;
  boundaryItems: string[];
  selectedHistoryRows: ResearchDeskHistoryRow[];
  emptyDetail?: string;
};

const DOSSIER_TABS: Array<[ResearchDeskDossierTab, string]> = [
  ["summary", "概要"],
  ["fundamentals", "基本面"],
  ["valuation", "估值"],
  ["momentum", "动量"],
  ["events", "事件"],
  ["finance", "财务"],
  ["research", "研报与纪要"],
  ["sentiment", "舆情"],
  ["appendix", "附录"],
];

export function ResearchDeskDossier({
  selectedCandidate,
  selectedRisk,
  selectedDailyChange,
  selectedQuote,
  selectedCompositeScore,
  compositeScoreNote,
  dossierTab,
  onDossierTabChange,
  onJumpToEvidence,
  snapshotItems,
  marketSnapshotItems,
  chartOption,
  decisionStatusLabel,
  decisionReason,
  keyFactItems,
  evidenceItems,
  factorCells,
  timelineItems,
  financeItems,
  evidencePreviewItems,
  metricCards,
  signalWindow,
  boundaryItems,
  selectedHistoryRows,
  emptyDetail,
}: ResearchDeskDossierProps) {
  return (
    <section className={styles.dossier} data-testid="stock-analysis-research-dossier">
      <div className={styles.panelHeader}>
        <div className={styles.dossierTitleLine}>
          <div>
            <h3>
              {selectedCandidate ? (
                <>
                  <span>{selectedCandidate.stockName}</span>{" "}
                  <small className={styles.dossierCode}>{selectedCandidate.stockCode}</small>
                </>
              ) : "未选择标的"}
            </h3>
            <p>
              {selectedCandidate
                ? `${selectedCandidate.sectorName} · ${selectedCandidate.sourcePoolLabel}`
                : "从左侧候选池选择一个标的"}
            </p>
          </div>
          {selectedCandidate ? (
            <div className={styles.dossierQuote}>
              <strong>{selectedQuote}</strong>
              <span data-tone={changeTone(selectedDailyChange)}>涨跌 {selectedDailyChange}</span>
            </div>
          ) : null}
        </div>
        {selectedCandidate ? (
          <div className={styles.dossierHeaderMeta}>
            {[...marketSnapshotItems, ...snapshotItems].slice(0, 4).map((item) => (
              <span key={item.label}>
                <small>{item.label}</small>
                <strong>{item.value}</strong>
              </span>
            ))}
          </div>
        ) : null}
      </div>

      <div className={styles.tabRow}>
        {DOSSIER_TABS.map(([tab, label]) => (
          <button
            key={tab}
            type="button"
            className={styles.tabButton}
            data-active={dossierTab === tab}
            aria-pressed={dossierTab === tab}
            onClick={() => onDossierTabChange(tab)}
          >
            {label}
          </button>
        ))}
      </div>

      {!selectedCandidate ? (
        <div className={styles.empty}>
          <strong>暂无研究档案</strong>
          <p>{emptyDetail || "左侧候选池恢复后，这里会自动显示研究档案和动作建议。"}</p>
        </div>
      ) : dossierTab === "summary" ? (
        <ResearchDeskSummary
          selectedCandidate={selectedCandidate}
          selectedRisk={selectedRisk}
          decisionStatusLabel={decisionStatusLabel}
          decisionReason={decisionReason}
          compositeScore={selectedCompositeScore}
          compositeScoreNote={compositeScoreNote}
          chartOption={chartOption}
          keyFactItems={keyFactItems}
          evidenceItems={evidenceItems}
          factorCells={factorCells}
          timelineItems={timelineItems}
          financeItems={financeItems}
          evidencePreviewItems={evidencePreviewItems}
          onJumpToEvidence={onJumpToEvidence}
          onOpenFundamentals={() => onDossierTabChange("fundamentals")}
        />
      ) : (
        <ResearchDeskTabViews
          dossierTab={dossierTab}
          selectedCandidate={selectedCandidate}
          selectedRisk={selectedRisk}
          metricCards={metricCards}
          evidenceItems={evidenceItems}
          boundaryItems={boundaryItems}
          signalWindow={signalWindow}
          selectedHistoryRows={selectedHistoryRows}
        />
      )}
    </section>
  );
}
