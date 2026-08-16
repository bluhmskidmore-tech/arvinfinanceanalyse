import type {
  MacroObservationAShareRiskView,
  MacroObservationSignalCardView,
} from "../model/macroObservationPageModel";
import "./MacroObservationConclusionSignal.css";

/**
 * 02 信号与风险对照：单一外框内「5 卡信号横带（发丝竖缝，1280 折 3+2、720 单列）
 * + 发丝线 + A股风险块」。deferred 是 core 首发的诚实态（模型层已给 note），
 * 渲染低饱和占位 + 骨架条，不空白也不渲染成普通空值。
 */
export default function MacroObservationSignalRiskSection({
  signalCards,
  risk,
}: {
  signalCards: MacroObservationSignalCardView[];
  risk: MacroObservationAShareRiskView;
}) {
  return (
    <div className="macro-observation-signalrisk">
      {signalCards.length ? (
        <ul className="macro-observation-signalrisk-band" aria-label="信号卡列表">
          {signalCards.map((card) => (
            <li key={card.key} className="macro-observation-signalrisk-cell" data-tone={card.tone}>
              {/* 同物双名收敛：卡面统一中文名，后端英文原名（如 Crisis Score）收 title。 */}
              <span
                className="macro-observation-signalrisk-cell-title"
                title={card.rawTitle ?? card.title}
              >
                {card.title}
              </span>
              <strong className="macro-observation-signalrisk-cell-stance">{card.stance}</strong>
              <span className="macro-observation-signalrisk-cell-score">
                <span className="macro-observation-signalrisk-cell-score-label">评分</span>{" "}
                <strong>{card.scoreText}</strong>
              </span>
              <small
                className="macro-observation-signalrisk-cell-evidence"
                title={card.evidenceText}
              >
                {card.evidenceText}
              </small>
            </li>
          ))}
        </ul>
      ) : (
        <p className="macro-observation-signalrisk-empty">
          暂无信号卡证据；宏观分析返回后自动补上。
        </p>
      )}

      <div
        className="macro-observation-signalrisk-risk"
        data-testid="macro-observation-signalrisk-risk"
        data-state={risk.state}
        aria-label="A股风险"
      >
        {risk.state === "deferred" ? (
          <div className="macro-observation-signalrisk-deferred">
            <p className="macro-observation-signalrisk-deferred-note">A股风险{risk.note}。</p>
            <div className="macro-observation-signalrisk-skeleton" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          </div>
        ) : risk.state === "empty" ? (
          <p className="macro-observation-signalrisk-deferred-note">{risk.note}</p>
        ) : (
          <>
            <div className="macro-observation-signalrisk-risk-head">
              <h3 className="macro-observation-signalrisk-risk-title">A股风险</h3>
              <span className="macro-observation-signalrisk-risk-status">{risk.statusText}</span>
              <span className="macro-observation-signalrisk-risk-date">{risk.tradeDate}</span>
            </div>
            <div className="macro-observation-signalrisk-risk-readout" data-tone={risk.tone}>
              <strong className="macro-observation-signalrisk-risk-score">{risk.scoreText}</strong>
              <span className="macro-observation-signalrisk-risk-name">{risk.name}</span>
            </div>
            <p className="macro-observation-signalrisk-risk-summary" title={risk.summary}>
              {risk.summary}
            </p>
            <p className="macro-observation-signalrisk-risk-rule">
              <span className="macro-observation-signalrisk-risk-rule-label">仓位规则</span>
              <span className="macro-observation-signalrisk-risk-rule-text">
                {risk.positionRule}
              </span>
            </p>
            {risk.watchNext.length ? (
              <div className="macro-observation-signalrisk-risk-watch">
                <span className="macro-observation-signalrisk-risk-watch-label">后续观察</span>
                <ul className="macro-observation-signalrisk-risk-watch-list">
                  {risk.watchNext.map((item, index) => (
                    <li key={`${index}-${item}`}>{item}</li>
                  ))}
                </ul>
                {risk.watchNextMoreNote ? (
                  <small className="macro-observation-signalrisk-risk-watch-more">
                    {risk.watchNextMoreNote}
                  </small>
                ) : null}
              </div>
            ) : null}
            <small className="macro-observation-signalrisk-risk-count">
              触发规则 {risk.triggeredRuleCount} 条
            </small>
          </>
        )}
      </div>
    </div>
  );
}
