import { CheckOutlined, CopyOutlined, ReloadOutlined } from "@ant-design/icons";
import { memo, useMemo } from "react";

import type { AgentSuggestedAction } from "../../../api/contracts";
import {
  AGENT_FOLLOW_UP_CHIPS,
  buildGovernanceNotices,
  buildResultMetaEntries,
  formatMetaValue,
  getSuggestedActionKey,
  hasEvidenceContent,
  hasRenderableResult,
  isCompactProviderChatResult,
  isGitNexusCard,
  isGitNexusResult,
  isResearchRadarResult,
} from "../lib/agentWorkbenchModel";
import type {
  AgentConversationTurn,
  AgentCopyFeedback,
  AgentNextDrill,
  AgentQueryResult,
  PendingSuggestedActionConfirmation,
} from "../lib/agentWorkbenchModel";
import { AgentAnswerPanel } from "./AgentAnswerPanel";
import { AgentEvidencePanel } from "./AgentEvidencePanel";
import { AgentGenericCardsGrid } from "./AgentGenericCardsGrid";
import { AgentResultMetaPanel } from "./AgentResultMetaPanel";
import { AgentSuggestedActionsPanel } from "./AgentSuggestedActionsPanel";
import { GitNexusResultView as AgentGitNexusResultView } from "./GitNexusResultView";

type AgentTurnResultViewProps = {
  turn: AgentConversationTurn;
  isLatestResultTurn: boolean;
  isEmbedded: boolean;
  readOnly: boolean;
  loading: boolean;
  latestConversationTurnId: string | null;
  copyFeedback: AgentCopyFeedback | null;
  pendingSuggestedActionConfirmation: PendingSuggestedActionConfirmation | null;
  canRegenerate: boolean;
  onRegenerate: (turn: AgentConversationTurn) => void;
  onCopyAnswer: (turn: AgentConversationTurn) => void;
  onApplyNextDrill: (drill: AgentNextDrill, sourceElement?: HTMLElement) => void;
  onSuggestedAction: (
    turnId: string,
    action: AgentSuggestedAction,
    sourceElement?: HTMLElement,
  ) => void;
  onFocusComposerFromFollowUp: (sourceElement: HTMLElement) => void;
  onApplyFollowUpChip: (question: string, sourceElement?: HTMLElement) => void;
  onFocusComposerFromEmptyResult: () => void;
  onSideDrawerOpen: () => void;
};

const EMPTY_SQL_EXECUTED: string[] = [];
const StaticAgentAnswerPanel = memo(AgentAnswerPanel);
const StaticAgentEvidencePanel = memo(AgentEvidencePanel);
const StaticAgentGenericCardsGrid = memo(AgentGenericCardsGrid);
const StaticAgentResultMetaPanel = memo(AgentResultMetaPanel);
const StaticAgentGitNexusResultView = memo(AgentGitNexusResultView);

function AgentResultSideDrawer({
  turnResult,
  resultMetaEntries,
  hasEvidence,
  onSideDrawerOpen,
}: {
  turnResult: AgentQueryResult;
  resultMetaEntries: Array<[string, unknown]>;
  hasEvidence: boolean;
  onSideDrawerOpen: () => void;
}) {
  const detailSectionCount = (hasEvidence ? 1 : 0) + (resultMetaEntries.length > 0 ? 1 : 0);
  const resultSide = (
    <aside className="agent-result-side" aria-label="回答依据与运行信息">
      {hasEvidence ? (
        <StaticAgentEvidencePanel
          tablesUsed={turnResult.evidence.tables_used}
          filtersApplied={turnResult.evidence.filters_applied}
          sqlExecuted={turnResult.evidence.sql_executed ?? EMPTY_SQL_EXECUTED}
          evidenceStrength={
            turnResult.evidence.evidence_strength ??
            (typeof turnResult.result_meta.evidence_strength === "string"
              ? turnResult.result_meta.evidence_strength
              : undefined)
          }
          evidenceRows={turnResult.evidence.evidence_rows}
          qualityFlag={turnResult.evidence.quality_flag}
        />
      ) : null}
      <StaticAgentResultMetaPanel
        entries={resultMetaEntries}
        formatValue={formatMetaValue}
      />
    </aside>
  );

  return (
    <details
      className="agent-result-side-drawer"
      onToggle={(event) => {
        if (event.currentTarget.open) {
          onSideDrawerOpen();
        }
      }}
    >
      <summary>查看依据 · {detailSectionCount} 项</summary>
      {resultSide}
    </details>
  );
}

export function AgentTurnResultView({
  turn,
  isEmbedded,
  readOnly,
  loading,
  latestConversationTurnId,
  copyFeedback,
  pendingSuggestedActionConfirmation,
  canRegenerate,
  onRegenerate,
  onCopyAnswer,
  onApplyNextDrill,
  onSuggestedAction,
  onFocusComposerFromFollowUp,
  onApplyFollowUpChip,
  onFocusComposerFromEmptyResult,
  onSideDrawerOpen,
}: AgentTurnResultViewProps) {
  const turnResult = turn.result;
  // Result payloads are immutable snapshots; interaction state stays outside this cached model.
  const staticResultModel = useMemo(() => {
    if (!turnResult) {
      return null;
    }

    const compactProviderChatResult = isCompactProviderChatResult(turnResult);
    const visibleCards = compactProviderChatResult ? [] : turnResult.cards;
    const gitNexusResult = isGitNexusResult(turnResult);

    return {
      governanceNotices: buildGovernanceNotices(turnResult),
      researchRadarResult: isResearchRadarResult(turnResult),
      compactProviderChatResult,
      resultMetaEntries: buildResultMetaEntries(turnResult.result_meta),
      visibleCards,
      gitNexusCards: gitNexusResult ? visibleCards : visibleCards.filter(isGitNexusCard),
      genericCards: gitNexusResult
        ? []
        : visibleCards.filter((card) => !isGitNexusCard(card)),
      renderableResult: hasRenderableResult(turnResult),
      hasEvidence: hasEvidenceContent(turnResult.evidence),
    };
  }, [turnResult]);

  if (!turnResult || !staticResultModel) {
    return null;
  }
  // 治理警示（stale/降级/禁止正式使用）跟随结果本身常显，不随新回合出现而消失。
  const {
    governanceNotices,
    researchRadarResult,
    compactProviderChatResult,
    resultMetaEntries,
    visibleCards,
    gitNexusCards,
    genericCards,
    renderableResult,
    hasEvidence,
  } = staticResultModel;
  const copyStatus = copyFeedback?.turnId === turn.id ? copyFeedback.status : null;
  const copyLabel = copyStatus === "success" ? "已复制" : copyStatus === "error" ? "复制失败" : "复制回答";
  const copyStatusMessage =
    copyStatus === "success" ? "回答已复制" : copyStatus === "error" ? "复制失败，请手动选择回答文本。" : "";
  const resultCards =
    visibleCards.length > 0 ? (
      <div className="agent-result-card-stack">
        {gitNexusCards.length > 0 ? <StaticAgentGitNexusResultView cards={gitNexusCards} /> : null}
        <StaticAgentGenericCardsGrid cards={genericCards} formatValue={formatMetaValue} />
      </div>
    ) : null;
  const answerMessage = turnResult.answer.trim() ? (
    <div className="agent-answer-message">
      <StaticAgentAnswerPanel
        answer={turnResult.answer}
        testId={isEmbedded && turn.id === latestConversationTurnId ? "agent-panel-answer" : undefined}
      />
      {!researchRadarResult ? (
        <div className="agent-result-toolbar" aria-label="回答操作">
          {canRegenerate ? (
            <button
              type="button"
              className="agent-result-toolbar__button"
              aria-label={`重新生成：${turn.question}`}
              onClick={() => onRegenerate(turn)}
              disabled={loading}
            >
              <ReloadOutlined aria-hidden="true" />
              <span>重新生成</span>
            </button>
          ) : null}
          <button
            type="button"
            className="agent-result-toolbar__button"
            aria-label={`${copyLabel}：${turn.question}`}
            onClick={() => onCopyAnswer(turn)}
            disabled={!turnResult.answer.trim()}
          >
            {copyStatus === "success" ? <CheckOutlined aria-hidden="true" /> : <CopyOutlined aria-hidden="true" />}
            <span>{copyLabel}</span>
          </button>
          {copyStatus ? (
            <span
              aria-label="复制状态"
              aria-live="polite"
              aria-atomic="true"
              role="status"
              className={`agent-copy-feedback agent-copy-feedback--${copyStatus}`}
            >
              {copyStatusMessage}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  ) : null;

  return (
    <div className="agent-result-shell">
      {governanceNotices.length > 0 ? (
        <div
          className="agent-callout agent-callout--warning agent-governance-callout"
          role="status"
          aria-label="数据可信状态提示"
        >
          <strong>数据状态提示</strong>
          {governanceNotices.map((notice) => (
            <span key={notice}>{notice}</span>
          ))}
        </div>
      ) : null}
      {renderableResult ? (
        <div className="agent-result-grid">
          <div className="agent-result-main">
            {researchRadarResult ? resultCards : answerMessage}
            {researchRadarResult ? answerMessage : resultCards}

            {turnResult.next_drill.length > 0 ? (
              <div className="agent-next-drill-row" aria-label="继续下钻">
                {turnResult.next_drill.map((drill) => (
                  <button
                    key={drill.dimension}
                    type="button"
                    aria-label={`继续下钻：${drill.label}`}
                    onClick={(event) => onApplyNextDrill(drill, event.currentTarget)}
                    disabled={loading}
                  >
                    {drill.label}
                  </button>
                ))}
              </div>
            ) : null}

            <AgentSuggestedActionsPanel
              actions={turnResult.suggested_actions}
              formatValue={formatMetaValue}
              readOnly={readOnly}
              activePayload={turn.activeSuggestedActionPayload}
              pendingConfirmationKey={
                pendingSuggestedActionConfirmation?.turnId === turn.id
                  ? pendingSuggestedActionConfirmation.actionKey
                  : null
              }
              getActionKey={getSuggestedActionKey}
              onActionClick={(action, sourceElement) => onSuggestedAction(turn.id, action, sourceElement)}
            />

            <div className="agent-follow-up-chips" aria-label="继续追问">
              <button
                type="button"
                className="agent-follow-up-chips__button agent-follow-up-chips__button--primary"
                aria-label={`继续输入：${turn.question}`}
                onClick={(event) => onFocusComposerFromFollowUp(event.currentTarget)}
                disabled={loading}
              >
                继续输入
              </button>
              <details className="agent-follow-up-chips__details">
                <summary>更多追问</summary>
                <div className="agent-follow-up-chips__options">
                  {AGENT_FOLLOW_UP_CHIPS.map((chip) => (
                    <button
                      key={chip.label}
                      type="button"
                      className="agent-follow-up-chips__button"
                      aria-label={`${chip.label}：${turn.question}`}
                      onClick={(event) => onApplyFollowUpChip(chip.question, event.currentTarget)}
                      disabled={loading}
                    >
                      {chip.label}
                    </button>
                  ))}
                </div>
              </details>
            </div>
          </div>

          {compactProviderChatResult ? null : (
            <AgentResultSideDrawer
              turnResult={turnResult}
              resultMetaEntries={resultMetaEntries}
              hasEvidence={hasEvidence}
              onSideDrawerOpen={onSideDrawerOpen}
            />
          )}
        </div>
      ) : (
        <div className="agent-callout agent-callout--empty" role="status" aria-label="空结果状态">
          <strong>没有可展示结果</strong>
          <span>本次查询未返回可展示结果。请调整问题后重试。</span>
          <div className="agent-callout__actions">
            <button
              type="button"
              className="agent-callout__action"
              aria-label={`继续输入：${turn.question}`}
              onClick={onFocusComposerFromEmptyResult}
              disabled={loading}
            >
              继续输入
            </button>
            {canRegenerate ? (
              <button
                type="button"
                className="agent-callout__action"
                aria-label={`重新生成：${turn.question}`}
                onClick={() => onRegenerate(turn)}
                disabled={loading}
              >
                重新生成
              </button>
            ) : null}
          </div>
        </div>
      )}

      {!renderableResult ? (
        <details className="agent-result-details">
          <summary>查看依据 · {resultMetaEntries.length} 项</summary>
          <StaticAgentResultMetaPanel
            entries={resultMetaEntries}
            formatValue={formatMetaValue}
          />
        </details>
      ) : null}
    </div>
  );
}
