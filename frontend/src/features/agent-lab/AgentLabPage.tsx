import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAui,
} from "@assistant-ui/react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { AgentSuggestedAction } from "../../api/contracts";
import { AgentRunProgress } from "../agent/components/AgentRunProgress";
import { AgentRuntimeStrip } from "../agent/components/AgentRuntimeStrip";
import { AgentTurnErrorCallout } from "../agent/components/AgentTurnErrorCallout";
import { AgentTurnResultView } from "../agent/components/AgentTurnResultView";
import {
  buildRuntimeStatus,
  type AgentConversationTurn,
} from "../agent/lib/agentWorkbenchModel";
import { useAgentLabRuntime, type AgentLabMessage } from "./useAgentLabRuntime";

import "../agent/AgentWorkbenchPage.css";
import "./AgentLabPage.css";

function focusLabComposer() {
  window.requestAnimationFrame(() => {
    document.querySelector<HTMLTextAreaElement>("[data-agent-lab-composer]")?.focus();
  });
}

function AgentLabUserMessage() {
  return (
    <MessagePrimitive.Root className="agent-lab-message agent-lab-message--user">
      <div className="agent-lab-message__role" aria-hidden="true">
        YOU
      </div>
      <div className="agent-lab-message__bubble">
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  );
}

function AgentLabAssistantMessage({
  message,
  isRunning,
}: {
  message: AgentLabMessage;
  isRunning: boolean;
}) {
  const aui = useAui();
  const [copyStatus, setCopyStatus] = useState<"success" | "error" | null>(null);
  const turn = message.turn;

  function fillComposer(question: string) {
    aui.composer.setText(question);
    focusLabComposer();
  }

  async function copyAnswer(currentTurn: AgentConversationTurn) {
    try {
      await navigator.clipboard.writeText(currentTurn.result?.answer ?? "");
      setCopyStatus("success");
    } catch {
      setCopyStatus("error");
    }
  }

  function applySuggestedAction(action: AgentSuggestedAction) {
    const payloadQuestion = action.payload.question;
    fillComposer(typeof payloadQuestion === "string" ? payloadQuestion : action.label);
  }

  return (
    <MessagePrimitive.Root className="agent-lab-message agent-lab-message--assistant">
      <div className="agent-lab-message__role" aria-hidden="true">
        LAB
      </div>
      <div className="agent-lab-message__content">
        {message.phase === "running" && turn ? (
          <div className="agent-lab-running" role="status" aria-live="polite">
            <div className="agent-lab-running__label">{message.text}</div>
            <AgentRunProgress agentRun={turn.agentRun} question={turn.question} />
          </div>
        ) : null}

        {message.phase === "cancelled" ? (
          <div className="agent-lab-cancelled" role="status">
            {message.text}
          </div>
        ) : null}

        {message.phase === "error" && turn ? (
          <AgentTurnErrorCallout
            turn={turn}
            loading={false}
            canRetry={false}
            onEditQuestion={() => undefined}
            onRetry={() => undefined}
          />
        ) : null}

        {message.phase === "complete" && turn?.result ? (
          <AgentTurnResultView
            turn={turn}
            isLatestResultTurn
            isEmbedded={false}
            readOnly
            loading={isRunning}
            latestConversationTurnId={turn.id}
            copyFeedback={copyStatus ? { turnId: turn.id, status: copyStatus } : null}
            pendingSuggestedActionConfirmation={null}
            canRegenerate={false}
            onRegenerate={() => undefined}
            onCopyAnswer={(currentTurn) => void copyAnswer(currentTurn)}
            onApplyNextDrill={(drill) =>
              fillComposer(`请基于当前 evidence 继续下钻：${drill.label}`)
            }
            onSuggestedAction={(_turnId, action) => applySuggestedAction(action)}
            onFocusComposerFromFollowUp={() => focusLabComposer()}
            onApplyFollowUpChip={(question) => fillComposer(question)}
            onFocusComposerFromEmptyResult={() => focusLabComposer()}
            onSideDrawerOpen={() => undefined}
          />
        ) : null}
      </div>
    </MessagePrimitive.Root>
  );
}

function AgentLabThread({
  messages,
  isRunning,
  clearMessages,
}: {
  messages: AgentLabMessage[];
  isRunning: boolean;
  clearMessages: () => void;
}) {
  const aui = useAui();
  const messageById = useMemo(
    () => new Map(messages.map((message) => [message.id, message])),
    [messages],
  );
  const latestAssistant = [...messages].reverse().find((message) => message.role === "assistant");
  const latestTurn = latestAssistant?.turn ?? null;
  const runtimeStatus = buildRuntimeStatus(
    latestTurn?.result ?? null,
    isRunning,
    latestTurn?.agentRun ?? null,
  );
  const stateLabel = isRunning
    ? "实验运行中"
    : latestAssistant?.phase === "complete"
      ? "实验结果已就绪"
      : latestAssistant?.phase === "error"
        ? "实验请求失败"
        : "实验接口待命";

  return (
    <main className="agent-workbench-shell agent-lab-shell" data-moss-theme-scope="agent">
      <header className="agent-lab-header">
        <div>
          <div className="agent-lab-header__eyebrow">assistant-ui / ExternalStoreRuntime</div>
          <h1>Agent Lab</h1>
          <p>用同一套 MOSS run/SSE 与金融结果卡片，隔离验证线程滚动、输入和停止体验。</p>
        </div>
        <div className="agent-lab-header__actions">
          <Link className="agent-lab-link" to="/agent">
            返回正式 Agent
          </Link>
          <button
            type="button"
            className="agent-lab-clear"
            onClick={clearMessages}
            disabled={isRunning || messages.length === 0}
          >
            清空本次实验
          </button>
        </div>
      </header>

      <section className="agent-lab-boundary" aria-label="实验边界">
        <span className="agent-lab-boundary__signal" aria-hidden="true" />
        <strong>隔离实验</strong>
        <span>纯内存 · 不读取或写入正式对话、草稿与恢复记录</span>
      </section>

      <AgentRuntimeStrip loading={isRunning} stateLabel={stateLabel} runtimeStatus={runtimeStatus} />

      <ThreadPrimitive.Root className="agent-lab-thread">
        <ThreadPrimitive.Viewport
          className="agent-lab-thread__viewport"
          turnAnchor="top"
          scrollToBottomOnInitialize={false}
        >
          {messages.length === 0 ? (
            <section className="agent-lab-empty">
              <div className="agent-lab-empty__mark" aria-hidden="true">
                LAB
              </div>
              <div>
                <h2>从一条真实问题开始</h2>
                <p>建议用同一问题分别测试正式页和实验页，重点比较长回答、连续追问与中途停止。</p>
              </div>
              <div className="agent-lab-empty__examples" aria-label="问题示例">
                <button
                  type="button"
                  onClick={() => {
                    aui.composer.setText("组合概览：规模、损益、久期和信用风险有什么变化？");
                    focusLabComposer();
                  }}
                >
                  组合风险概览
                </button>
                <button
                  type="button"
                  onClick={() => {
                    aui.composer.setText("解释当前页面的主要结论和风险点");
                    focusLabComposer();
                  }}
                >
                  解释主要结论
                </button>
              </div>
            </section>
          ) : null}

          <ThreadPrimitive.Messages>
            {({ message: threadMessage }) => {
              const message = messageById.get(threadMessage.id);
              if (!message) {
                return null;
              }
              return message.role === "user" ? (
                <AgentLabUserMessage />
              ) : (
                <AgentLabAssistantMessage message={message} isRunning={isRunning} />
              );
            }}
          </ThreadPrimitive.Messages>

          <ThreadPrimitive.ViewportFooter className="agent-lab-composer-dock">
            <ThreadPrimitive.ScrollToBottom
              className="agent-lab-scroll-bottom"
              aria-label="滚动到最新消息"
            >
              ↓
            </ThreadPrimitive.ScrollToBottom>
            <ComposerPrimitive.Root className="agent-lab-composer">
              <ComposerPrimitive.Input
                className="agent-lab-composer__input"
                aria-label="向 Agent Lab 提问"
                placeholder="输入真实问题，Enter 发送，Shift + Enter 换行"
                submitMode="enter"
                maxRows={8}
                data-agent-lab-composer
              />
              <div className="agent-lab-composer__footer">
                <span>本页不保存输入与回答</span>
                {isRunning ? (
                  <ComposerPrimitive.Cancel
                    className="agent-lab-composer__action agent-lab-composer__action--stop"
                    aria-label="停止当前任务"
                  >
                    停止
                  </ComposerPrimitive.Cancel>
                ) : (
                  <ComposerPrimitive.Send
                    className="agent-lab-composer__action"
                    aria-label="发送"
                  >
                    发送
                  </ComposerPrimitive.Send>
                )}
              </div>
            </ComposerPrimitive.Root>
          </ThreadPrimitive.ViewportFooter>
        </ThreadPrimitive.Viewport>
      </ThreadPrimitive.Root>
    </main>
  );
}

export default function AgentLabPage() {
  const { runtime, messages, isRunning, clearMessages } = useAgentLabRuntime();

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AgentLabThread
        messages={messages}
        isRunning={isRunning}
        clearMessages={clearMessages}
      />
    </AssistantRuntimeProvider>
  );
}
