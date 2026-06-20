import type { CrossAssetCandidateAction } from "../lib/crossAssetDriversPageModel";

type ActionTone = CrossAssetCandidateAction["tone"];

const TONE_META: Record<ActionTone, { label: string; rank: string }> = {
  bull: { label: "关注", rank: "P1" },
  warning: { label: "观察", rank: "P2" },
  bear: { label: "谨慎", rank: "P0" },
};

const FALLBACK_RANKS = ["P1", "P2", "P3"];

function actionRank(row: CrossAssetCandidateAction, index: number) {
  if (row.tone === "bear") return TONE_META.bear.rank;
  return FALLBACK_RANKS[index] ?? "P3";
}

export type MarketCandidateActionsProps = {
  rows: CrossAssetCandidateAction[];
};

export function MarketCandidateActions({ rows }: MarketCandidateActionsProps) {
  return (
    <section className="cross-asset-candidate-actions" data-testid="cross-asset-candidate-actions">
      <div className="cross-asset-candidate-actions__header">
        <span>Action Queue</span>
        <strong>市场候选动作</strong>
        <em>只保留可执行的讨论、配置与风控线索。</em>
      </div>
      {rows.length === 0 ? (
        <p className="cross-asset-candidate-actions__empty">当前没有足够证据形成候选动作。</p>
      ) : (
        <div className="cross-asset-candidate-actions__queue" role="list" aria-label="市场候选动作队列">
          {rows.map((row, index) => {
            const isLastOdd = rows.length % 2 === 1 && index === rows.length - 1;
            return (
              <article
                key={`${row.action}-${row.evidence}`}
                className={`cross-asset-candidate-actions__item cross-asset-candidate-actions__item--${row.tone}${
                  isLastOdd ? " cross-asset-candidate-actions__item--last-odd" : ""
                }`}
                role="listitem"
              >
                <span className="cross-asset-candidate-actions__rank">{actionRank(row, index)}</span>
                <div className="cross-asset-candidate-actions__main">
                  <strong className="cross-asset-candidate-actions__action">{row.action}</strong>
                  <p className="cross-asset-candidate-actions__reason">{row.reason}</p>
                  <p className="cross-asset-candidate-actions__evidence">{row.evidence}</p>
                </div>
                <b className="cross-asset-candidate-actions__tone">{TONE_META[row.tone].label}</b>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
