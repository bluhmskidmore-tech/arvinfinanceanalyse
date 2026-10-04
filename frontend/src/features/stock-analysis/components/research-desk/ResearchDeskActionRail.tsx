import type {
  StockCandidateReviewQueueItem,
  StockRiskExitRow,
} from "../../lib/stockAnalysisPageModel";
import styles from "../../pages/StockAnalysisResearchDesk.module.css";
import type { ResearchDeskEndpointItem } from "./types";

const boundaryCopy = new Map<string, string>([
  [
    "候选来自 workbench 首屏只读队列；门禁与正式用途边界以接口状态为准。",
    "候选仅供研究参考，不代表交易建议。",
  ],
  [
    "当前覆盖 · 非时点 · 不可历史使用 · 仅观察",
    "题材归属采用当前成分，仅供观察；缺少历史时点记录，不能用于历史回测。",
  ],
  [
    "研究候选可复核，仍有数据或边界事项待确认；当日研究数据可用；盘前资格尚未闭合（当前数据尚未绑定已发布版本），风险与执行结论保持关闭。",
    "研究数据可查看。盘前数据尚未绑定发布版本，暂不提供风险与执行结论。",
  ],
]);

function boundaryText(text: string): string {
  return boundaryCopy.get(text) ?? text;
}

type ResearchDeskActionRailProps = {
  hardGateItems: string[];
  riskTags: string[];
  selectedRisk: StockRiskExitRow | null;
  endpointItems: ResearchDeskEndpointItem[];
  selectedCandidate: StockCandidateReviewQueueItem | null;
  selectedWatchlisted: boolean;
  onToggleWatchlist: (stockCode: string) => void;
  noteDraft: string;
  onNoteDraftChange: (value: string) => void;
  savedNote: string;
  onSaveNote: () => void;
  onOpenDeepResearch: () => void;
  onJumpToEvidence: () => void;
  onOpenDetailDrawer: () => void;
  onOpenHistory: () => void;
  actionsDisabled?: boolean;
  disabledReason?: string;
  evidenceDisabled?: boolean;
  deepResearchDisabled?: boolean;
  riskUnavailableReason?: string;
};

export function ResearchDeskActionRail({
  hardGateItems,
  riskTags,
  selectedRisk,
  endpointItems,
  selectedCandidate,
  selectedWatchlisted,
  onToggleWatchlist,
  noteDraft,
  onNoteDraftChange,
  savedNote,
  onSaveNote,
  onOpenDeepResearch,
  onJumpToEvidence,
  onOpenDetailDrawer,
  onOpenHistory,
  actionsDisabled,
  disabledReason,
  evidenceDisabled = false,
  deepResearchDisabled = false,
  riskUnavailableReason,
}: ResearchDeskActionRailProps) {
  const candidateActionsDisabled = Boolean(actionsDisabled || selectedCandidate == null);

  return (
    <aside className={styles.rail} id="stock-analysis-risk-section" data-testid="stock-analysis-action-rail">
      <div className={styles.panelHeader}>
        <div>
          <h3>风险与行动</h3>
          <p>只回答为什么还不能推进，以及下一步能做什么。</p>
        </div>
      </div>

      <section className={styles.railCard}>
        <div className={styles.railCardHeading}>
          <strong>复核边界（{hardGateItems.length} 条）</strong>
        </div>
        {hardGateItems.map((item) => (
          <p key={item} className={styles.railBoundaryText} title={item}>
            {boundaryText(item)}
          </p>
        ))}
      </section>

      <section className={styles.railCard}>
        <strong>风险标签</strong>
        <div className={styles.riskTags}>
          {riskTags.map((item) => (
            <span key={item} title={item}>{item}</span>
          ))}
        </div>
        {selectedRisk ? (
          <p>{selectedRisk.reason}</p>
        ) : (
          <p>{riskUnavailableReason ?? "该标的当前没有单独的风险退出记录，沿用总门控与边界提示。"}</p>
        )}
      </section>

      <section className={`${styles.railCard} ${styles.railCardCompact}`}>
        <div className={styles.railCardHeading}>
          <strong>证据溯源</strong>
          <button
            type="button"
            className={styles.railLink}
            onClick={onJumpToEvidence}
            disabled={evidenceDisabled}
          >
            查看全部
          </button>
        </div>
        {endpointItems.slice(0, 6).map((item) => (
          <div
            key={item.key}
            className={styles.sourcePreview}
            data-tone={item.tone}
            title={item.description}
          >
            <span>
              <strong>{item.label}</strong>
              <small>{item.businessDateLabel}</small>
            </span>
            <em>{item.statusLabel}</em>
          </div>
        ))}
        {endpointItems.length === 0 ? <small>当前没有可展示的接口证据。</small> : null}
      </section>

      <section className={styles.actionCard}>
        <strong>下一步行动</strong>
        <p className={styles.actionDisclosure}>
          {candidateActionsDisabled ? disabledReason || "选择候选后才能继续研究。" : "只读观察，不形成交易指令。"}
        </p>
        <button
          type="button"
          className={styles.actionPrimary}
          onClick={onOpenDeepResearch}
          disabled={candidateActionsDisabled || deepResearchDisabled}
          title={deepResearchDisabled ? "研究资格尚未闭合，只读深研入口保持关闭。" : undefined}
        >
          开始深度研究
        </button>
        <button
          type="button"
          className={styles.actionWatch}
          onClick={() => {
            if (selectedCandidate) onToggleWatchlist(selectedCandidate.stockCode);
          }}
          disabled={candidateActionsDisabled}
        >
          {selectedWatchlisted ? "移出自选" : "加入自选"}
        </button>
        <button type="button" className={styles.actionSecondary} onClick={onOpenHistory} disabled={candidateActionsDisabled}>
          回溯该信号历史表现
        </button>
        <button type="button" className={styles.actionSecondary} onClick={onOpenDetailDrawer} disabled={candidateActionsDisabled}>
          打开原始详情抽屉
        </button>
      </section>

      <section className={`${styles.railCard} ${styles.railCardCompact}`}>
        <strong>备注</strong>
        <textarea
          aria-label="研究备注"
          value={noteDraft}
          maxLength={200}
          rows={2}
          onChange={(event) => onNoteDraftChange(event.target.value)}
          placeholder="输入备注，回车保存"
          disabled={candidateActionsDisabled}
        />
        <div className={styles.noteMeta}>
          <span>{savedNote || `${noteDraft.length} / 200`}</span>
          <button type="button" className={styles.inlineGhost} onClick={onSaveNote} disabled={candidateActionsDisabled}>
            保存
          </button>
        </div>
      </section>
    </aside>
  );
}
