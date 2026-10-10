import type {
  StockCandidateReviewQueueItem,
  StockRiskExitRow,
} from "../../lib/stockAnalysisPageModel";
import styles from "../../pages/StockAnalysisResearchDesk.module.css";
import type {
  ResearchDeskDossierTab,
  ResearchDeskEvidenceItem,
  ResearchDeskHistoryRow,
  ResearchDeskMetricCard,
  ResearchDeskSignalWindow,
} from "./types";

type ResearchDeskTabViewsProps = {
  dossierTab: Exclude<ResearchDeskDossierTab, "summary">;
  selectedCandidate: StockCandidateReviewQueueItem;
  selectedRisk: StockRiskExitRow | null;
  metricCards: ResearchDeskMetricCard[];
  evidenceItems: ResearchDeskEvidenceItem[];
  boundaryItems: string[];
  signalWindow: ResearchDeskSignalWindow;
  selectedHistoryRows: ResearchDeskHistoryRow[];
};

function MetricCards({ items }: { items: ResearchDeskMetricCard[] }) {
  return (
    <div className={styles.metricGrid}>
      {items.map((item) => (
        <article key={item.key} className={styles.metricCard} data-accent={item.accent}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
          <small>{item.detail}</small>
        </article>
      ))}
    </div>
  );
}

export function ResearchDeskTabViews({
  dossierTab,
  selectedCandidate,
  selectedRisk,
  metricCards,
  evidenceItems,
  boundaryItems,
  signalWindow,
  selectedHistoryRows,
}: ResearchDeskTabViewsProps) {
  if (dossierTab === "fundamentals") {
    return (
      <div className={styles.bodyGrid}>
        <section className={styles.card}>
          <strong>研究观点</strong>
          <p>{selectedCandidate.reviewFocus}</p>
          <p>{selectedCandidate.patternNote}</p>
        </section>
        <section className={styles.card}>
          <strong>触发与失效</strong>
          <ul>
            {selectedCandidate.invalidationRules.slice(0, 4).map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
        </section>
      </div>
    );
  }

  if (dossierTab === "valuation") {
    return <MetricCards items={metricCards.slice(0, 4)} />;
  }

  if (dossierTab === "momentum") {
    return (
      <div className={styles.bodyGrid}>
        <section className={styles.card}>
          <strong>动量读数</strong>
          <MetricCards items={metricCards} />
        </section>
        <section className={styles.card}>
          <strong>信号窗口</strong>
          {signalWindow ? (
            <div className={styles.signalCard} data-tone={signalWindow.tone}>
              <span>{signalWindow.horizonLabel}</span>
              <strong>{signalWindow.winRateLabel}</strong>
              <p>{signalWindow.medianLabel}</p>
              <small>
                {signalWindow.sampleLabel}
                {signalWindow.longHorizonLabel ? ` · ${signalWindow.longHorizonLabel}` : ""}
              </small>
              <p>{signalWindow.guidance}</p>
            </div>
          ) : (
            <div className={styles.emptyCompact}>当前未请求到该来源池的信号窗口统计。</div>
          )}
        </section>
      </div>
    );
  }

  if (dossierTab === "events") {
    return (
      <div className={styles.bodyGrid}>
        <section className={styles.card}>
          <strong>最新信号与关键证据</strong>
          {evidenceItems.map((item) => (
            <div key={item.key} className={styles.factRow} data-rail={item.rail}>
              <span>{item.label}</span>
              <p>{item.value}</p>
            </div>
          ))}
        </section>
        <section className={styles.card}>
          <strong>事件时间线</strong>
          {boundaryItems.length > 0 ? (
            <ul>
              {boundaryItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <div className={styles.emptyCompact}>当前没有额外边界事件。</div>
          )}
        </section>
      </div>
    );
  }

  if (dossierTab === "finance") {
    return (
      <div className={styles.bodyGrid}>
        <section className={styles.card}>
          <strong>财务与估值摘要</strong>
          <MetricCards items={metricCards} />
        </section>
        <section className={styles.card}>
          <strong>风险关注点</strong>
          {selectedRisk ? (
            <>
              <p>{selectedRisk.reason}</p>
              <div className={styles.heroStrip}>
                <div className={styles.heroCell}>
                  <span>最新收盘</span>
                  <strong>{selectedRisk.latestClose}</strong>
                </div>
                <div className={styles.heroCell}>
                  <span>退出价</span>
                  <strong>{selectedRisk.exitWatchPrice}</strong>
                </div>
                <div className={styles.heroCell}>
                  <span>距退出</span>
                  <strong>{selectedRisk.distanceToExitPct}</strong>
                </div>
              </div>
            </>
          ) : (
            <div className={styles.emptyCompact}>当前没有该标的的独立风险退出记录。</div>
          )}
        </section>
      </div>
    );
  }

  if (dossierTab === "research" || dossierTab === "sentiment") {
    const isResearch = dossierTab === "research";
    return (
      <div className={styles.bodyGrid}>
        <section className={styles.card}>
          <strong>{isResearch ? "研报与纪要" : "舆情"}</strong>
          <div className={styles.emptyCompact}>
            {isResearch
              ? "研报与纪要来源尚未接入该工作台，契约就绪后在此按时间列出。"
              : "舆情来源尚未接入该工作台，契约就绪后在此按热度列出。"}
          </div>
        </section>
        <section className={styles.card}>
          <strong>当前可用证据</strong>
          {evidenceItems.map((item) => (
            <div key={item.key} className={styles.factRow} data-rail={item.rail}>
              <span>{item.label}</span>
              <p>{item.value}</p>
            </div>
          ))}
        </section>
      </div>
    );
  }

  return (
    <div className={styles.bodyGrid}>
      <section className={styles.card}>
        <strong>原始字段</strong>
        <div className={styles.rawFieldGrid}>
          {selectedCandidate.rawFields.slice(0, 14).map((field) => (
            <div key={field.key} className={styles.rawField}>
              <span>{field.label}</span>
              <strong>{field.value}</strong>
            </div>
          ))}
        </div>
      </section>
      <section className={styles.card}>
        <strong>近端回放记录</strong>
        {selectedHistoryRows.length > 0 ? (
          <div className={styles.historyList}>
            {selectedHistoryRows.map((row) => (
              <article key={`${row.snapshot_as_of_date}-${row.candidate_rank}`} className={styles.historyRow}>
                <div>
                  <strong>{row.snapshot_as_of_date}</strong>
                  <span>{row.signalLabel}</span>
                </div>
                <p>
                  Rank {row.candidate_rank} · 1D {row.return1d} · 5D {row.return5d} · 20D {row.return20d}
                </p>
                <small>{row.data_status}</small>
              </article>
            ))}
          </div>
        ) : (
          <div className={styles.emptyCompact}>近 {60} 日没有该标的回放样本。</div>
        )}
      </section>
    </div>
  );
}
