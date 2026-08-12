import { Tag } from "antd";

import type {
  MacroToolkitCapabilityResult,
  MacroToolkitSignalCard,
} from "../../../api/macroToolkitClient";
import { PageSectionLead } from "../../../components/page/PagePrimitives";
import { formatCrisisTopContributorSummary } from "../lib/crisisScoreDisplay";
import { isCrisisComponent } from "../lib/macroToolkitCrisisSupport";
import {
  formatCrisisComponentSummaryZh,
  formatObservationEvidence,
  formatObservationSignalStance,
  formatObservationSignalTitle,
  formatSignalCardScore,
  toneTagColor,
} from "../lib/macroToolkitDisplayFormat";
import { ScoreTrack } from "./MacroToolkitPrimitives";

export function MacroToolkitSignalSection({
  showOperations,
  visibleSignalCards,
  crisisScoreResult,
}: {
  showOperations: boolean;
  visibleSignalCards: MacroToolkitSignalCard[];
  crisisScoreResult: MacroToolkitCapabilityResult | null;
}) {
  return (
    <section className="macro-toolkit-section">
      <PageSectionLead
        eyebrow={showOperations ? "信号" : "总览"}
        title="核心信号"
        description={
          showOperations
            ? "由系统内 Choice/Tushare 序列直接计算，脚本产物作为补充证据。"
            : "汇总宏观指标、市场风险和资金条件，保留当前观察所需的主要证据。"
        }
      />
      <div className="macro-toolkit-signal-grid">
        {visibleSignalCards.map((card) => (
          <div
            className={`macro-toolkit-signal-card macro-toolkit-signal-card--${card.tone}`}
            key={card.key}
          >
            <div className="macro-toolkit-signal-head">
              <span>{showOperations ? card.title : formatObservationSignalTitle(card)}</span>
              <Tag color={toneTagColor(card.tone)}>
                {showOperations ? card.stance : formatObservationSignalStance(card)}
              </Tag>
            </div>
            <strong>{formatSignalCardScore(card)}</strong>
            <ScoreTrack score={card.score} />
            {card.key === "crisis_score_cn" && crisisScoreResult
              ? (() => {
                  const rawComponents = Array.isArray(crisisScoreResult.result?.components)
                    ? crisisScoreResult.result.components.filter(isCrisisComponent)
                    : [];
                  // 英文组件原串保留在 title；卡面展示中文摘要。
                  const summary = formatCrisisTopContributorSummary(rawComponents);
                  return summary ? (
                    <small
                      className="macro-toolkit-signal-component-summary"
                      data-testid="macro-toolkit-crisis-signal-component-summary"
                      title={summary}
                    >
                      {formatCrisisComponentSummaryZh(rawComponents) ?? summary}
                    </small>
                  ) : null;
                })()
              : null}
            <small title={card.evidence.join(" / ")}>{formatObservationEvidence(card.evidence)}</small>
          </div>
        ))}
      </div>
    </section>
  );
}
