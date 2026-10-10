import { RightOutlined } from "@ant-design/icons";
import { useState } from "react";

import { EM_DASH } from "../../../../utils/format";
import type { StockCandidateReviewQueueItem } from "../../lib/stockAnalysisPageModel";
import styles from "../../pages/StockAnalysisResearchDesk.module.css";
import {
  candidateDailyChangeLabel,
  candidateNumberLabel,
  changeTone,
  COMPOSITE_SCORE_RAW_KEYS,
  poolTabLabel,
  RESEARCH_DESK_POOL_TABS,
  statusTone,
} from "./researchDeskFormatters";
import type { ResearchDeskPoolTab } from "./types";

type ResearchDeskPoolProps = {
  poolTab: ResearchDeskPoolTab;
  onPoolTabChange: (tab: ResearchDeskPoolTab) => void;
  queueSearchText: string;
  onQueueSearchTextChange: (value: string) => void;
  queueVisibleCount: number;
  queueTotalCount: number;
  queueCountLabel?: string;
  interactionsDisabled: boolean;
  selectedSectorLabel: string;
  poolCandidates: StockCandidateReviewQueueItem[];
  selectedCandidateCode: string | null;
  onSelectCandidate: (stockCode: string) => void;
  reviewQueueUsesHybridFusion: boolean;
  sectorLinkSummary: string;
  sectorLinkFocus: string;
  queueEmptyHeadline: string;
  queueEmptyDetail: string;
  historyLoading: boolean;
  historyLoaded: boolean;
};

const POOL_PAGE_SIZE = 11;

export function ResearchDeskPool({
  poolTab,
  onPoolTabChange,
  queueSearchText,
  onQueueSearchTextChange,
  queueVisibleCount,
  queueTotalCount,
  queueCountLabel,
  interactionsDisabled,
  selectedSectorLabel,
  poolCandidates,
  selectedCandidateCode,
  onSelectCandidate,
  queueEmptyHeadline,
  queueEmptyDetail,
  historyLoading,
  historyLoaded,
}: ResearchDeskPoolProps) {
  const [visibleCount, setVisibleCount] = useState(POOL_PAGE_SIZE);
  const visibleCandidates = poolCandidates.slice(0, visibleCount);
  const hasDailyChange = poolCandidates.some(
    (candidate) => candidateDailyChangeLabel(candidate) !== EM_DASH,
  );
  const hasMore = poolCandidates.length > visibleCandidates.length;
  return (
    <aside className={styles.pool} id="stock-analysis-review-queue" data-testid="stock-analysis-review-queue">
      <div className={styles.panelHeader}>
        <div className={styles.dossierIdentity}>
          <h3>标的池</h3>
          <p>{poolTabLabel(poolTab)}</p>
        </div>
        <button
          type="button"
          className={styles.panelGhost}
          aria-label="历史视图"
          title="历史视图"
          onClick={() => onPoolTabChange("history")}
          disabled={interactionsDisabled}
        >
          <RightOutlined aria-hidden="true" />
        </button>
      </div>

      <div className={styles.tabRow}>
        {RESEARCH_DESK_POOL_TABS.map(([tab, label]) => (
          <button
            key={tab}
            type="button"
            className={styles.tabButton}
            data-active={poolTab === tab}
            aria-pressed={poolTab === tab}
            onClick={() => onPoolTabChange(tab)}
            disabled={interactionsDisabled && tab !== "queue"}
          >
            {label}
          </button>
        ))}
      </div>

      <div className={styles.searchBar}>
        <input
          value={queueSearchText}
          onChange={(event) => onQueueSearchTextChange(event.target.value)}
          placeholder="搜索代码/名称"
          aria-label="搜索标的"
        />
      </div>

      <div className={styles.poolToolbarMeta} data-testid="stock-sector-filter-chips">
        <span>{queueCountLabel ?? `${queueVisibleCount} / ${queueTotalCount}`}</span>
        <span>{selectedSectorLabel} ▾</span>
      </div>

      {queueTotalCount === 0 ? (
        <div className={styles.empty}>
          <strong>{queueEmptyHeadline}</strong>
          <p>{queueEmptyDetail}</p>
        </div>
      ) : historyLoading && poolTab === "history" ? (
        <div className={styles.empty}>
          <strong>历史回测读取中</strong>
          <p>正在补齐候选历史，稍后会自动归档到左侧名单。</p>
        </div>
      ) : poolCandidates.length === 0 ? (
        <div className={styles.empty}>
          <strong>{poolTab === "watchlist" ? "自选股为空" : "当前筛选暂无标的"}</strong>
          <p>
            {poolTab === "history" && !historyLoaded
              ? "候选历史尚未加载。可点右侧动作区回溯信号历史。"
              : "调整搜索、行业或把当前标的加入自选。"}
          </p>
        </div>
      ) : (
        <div
          className={styles.poolTable}
          data-has-daily-change={hasDailyChange ? "true" : "false"}
        >
          <div className={styles.poolTableHead} aria-hidden="true">
            <span>#</span>
            <span>代码 / 名称</span>
            <span>综合得分</span>
            {hasDailyChange ? <span>涨跌幅</span> : null}
            <span>信号状态</span>
          </div>
          {!hasDailyChange ? (
            <p className={styles.poolQuoteHint}>涨跌幅请查看个股详情</p>
          ) : null}
          <div className={styles.poolList}>
            {visibleCandidates.map((candidate, index) => {
              const selected = selectedCandidateCode === candidate.stockCode;
              const dailyChange = candidateDailyChangeLabel(candidate);
              const fusionScore = candidateNumberLabel(candidate, [...COMPOSITE_SCORE_RAW_KEYS], 3);
              return (
                <div
                  // 同一只股票可能从多个信号池入队，代码本身不唯一。
                  key={`${candidate.sourcePool}:${candidate.stockCode}:${index}`}
                  className={styles.poolRow}
                  data-active={selected}
                >
                  <div className={styles.poolRank}>{index + 1}</div>
                  <button
                    type="button"
                    className={`${styles.poolMain} ${styles.poolSelectButton}`}
                    title={`${candidate.sourcePoolLabel} · 观察口径 ${candidate.distanceToBreakoutPct} · ${candidate.reviewFocus}`}
                    onClick={() => onSelectCandidate(candidate.stockCode)}
                  >
                    <div className={styles.poolIdentity}>
                      <strong>
                        {candidate.stockCode}
                        <span>{candidate.stockName}</span>
                      </strong>
                    </div>
                    <p>{candidate.sourcePoolLabel}</p>
                  </button>
                  <strong className={styles.poolScore}>{fusionScore}</strong>
                  {hasDailyChange ? (
                    <span className={styles.poolChange} data-tone={changeTone(dailyChange)}>
                      {dailyChange}
                    </span>
                  ) : null}
                  <span
                    className={styles.poolSignal}
                    data-tone={statusTone(candidate.pattern)}
                    title={candidate.pattern}
                  >
                    {candidate.pattern}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className={styles.poolFooter}>
        <button
          type="button"
          className={styles.poolLoadMore}
          disabled={!hasMore}
          onClick={() => setVisibleCount((count) => count + POOL_PAGE_SIZE)}
        >
          {queueCountLabel ? "候选待恢复" : hasMore ? "加载更多" : "已全部加载"}
        </button>
        <span>
          {queueCountLabel ?? `已加载 ${visibleCandidates.length} 条，共 ${poolCandidates.length} 条`}
        </span>
      </div>
    </aside>
  );
}
