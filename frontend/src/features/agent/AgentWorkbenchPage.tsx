import { useEffect, useRef, useState, type FormEvent } from "react";

import { ArrowDownOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { streamAgentLabRunEvents } from "../../api/agentLabRunStream";
import { streamAgentRunEvents } from "../../api/agentRunStream";
import { useApiClient } from "../../api/client";
import type {
  AgentConversationContext,
  AgentPageContext,
  AgentQueryRequest,
  AgentSuggestedAction,
} from "../../api/contracts";
import { AgentQueryForm } from "./components/AgentQueryForm";
import { AgentModelControls } from "./components/AgentModelControls";
import { AgentAnswerPanel } from "./components/AgentAnswerPanel";
import { AgentQueuedDraft } from "./components/AgentQueuedDraft";
import { AgentRepoMemoryPanel } from "./components/AgentRepoMemoryPanel";
import { AgentRunProgress } from "./components/AgentRunProgress";
import { AgentRuntimeStrip } from "./components/AgentRuntimeStrip";
import { AgentShortcutDrawer } from "./components/AgentShortcutDrawer";
import { AgentTurnErrorCallout } from "./components/AgentTurnErrorCallout";
import { AgentTurnResultView } from "./components/AgentTurnResultView";
import { isAbortError } from "./hooks/agentRunStatusOrchestrator";
import { runManagedAgentPolling } from "./hooks/runManagedAgentPolling";
import { useAgentTurnGate, type AgentTurnGate } from "./hooks/agentTurnGate";

import "./AgentWorkbenchPage.css";
import "./AgentModelComposer.css";

import {
  AgentDisabledQueryError,
  AgentRunCancelledError,
  GITNEXUS_QUICK_EXAMPLES,
  buildAgentRequestBody,
  buildConversationContext,
  buildErrorMessage,
  buildFinancialWorkflowRequestBody,
  buildLocalSyncAgentRun,
  buildPendingAgentRun,
  buildResearchRequestBody,
  buildRuntimeStatus,
  createAgentConversationTurn,
  extractProcessNames,
  findLatestTurnWithResult,
  findLatestTurnWithRun,
  formatAgentConnectionElapsed,
  formatAgentRunElapsed,
  formatAgentThinkingLabel,
  formatAgentThinkingText,
  formatAgentTurnWaitTitle,
  formatAgentWaitHint,
  formatAgentWaitPhase,
  formatConversationContextBadge,
  formatQueuedComposerHint,
  formatRuntimeLabel,
  getExecutableSuggestedIntent,
  getLocalAgentQueryIntent,
  getSuggestedActionKey,
  isCompactProviderChatTurn,
  isLocalOpenChatQuestion,
  isPlainAnalysisConversationQuestion,
  shouldDisplayAgentRunId,
  shouldUseLocalAnalysisConversation,
} from "./lib/agentWorkbenchModel";
import type {
  AgentConversationTurn,
  AgentNextDrill,
  AgentOrdinaryConversationMode,
  AgentQueryError,
  AgentQueryResult,
  AgentRunPayload,
  AgentWorkbenchPageProps,
  EmbeddedAgentCopilotProps,
  FinancialWorkflowShortcut,
  PendingSuggestedActionConfirmation,
  ResearchShortcut,
} from "./lib/agentWorkbenchModel";
import { useAgentComposerFocus } from "./hooks/useAgentComposerFocus";
import { useGitNexusProcessPicker } from "./hooks/useGitNexusProcessPicker";
import { useManagedAgentRun } from "./hooks/useManagedAgentRun";
import { useAgentRunRestore } from "./hooks/useAgentRunRestore";
import { useConversationPersistence } from "./hooks/useConversationPersistence";
import { useAgentModelSelection } from "./hooks/useAgentModelSelection";
import { getAgentScrollBehavior } from "./lib/agentMotion";

export function EmbeddedAgentCopilot({
  pageContext,
  variant = "workbench",
  showHeader,
  readOnly = false,
  defaultQuestion = "",
}: EmbeddedAgentCopilotProps = {}) {
  const apiClient = useApiClient();
  const isEmbedded = variant === "embedded";
  const isWorkbench = variant === "workbench";
  const modelSelection = useAgentModelSelection(isWorkbench, apiClient);
  const isContextlessWorkbench = isWorkbench && !pageContext;
  const shouldPersistConversation = isWorkbench;
  const resolvedShowHeader = showHeader ?? !isEmbedded;
  const quickExamples = pageContext
    ? GITNEXUS_QUICK_EXAMPLES
    : GITNEXUS_QUICK_EXAMPLES.filter(
        (example) => example !== "解释当前页面的主要结论和风险点",
      );
  const {
    recentRepoPaths,
    pinnedRepoPaths,
    query,
    setQuery,
    conversationTurns,
    setConversationTurns,
    queuedQueries,
    setQueuedQueries,
    initialRestoringRunId,
    rememberRepoPath,
    pinRepoPath,
    unpinRepoPath,
    movePinnedRepoPath: reorderPinnedRepoPath,
    writeComposerDraft,
    clearComposerDraftState,
    clearQueuedQueries,
    clearPersistedLatestRunId,
    persistPersistedLatestRunId,
    persistConversationTurnsNow,
  } = useConversationPersistence({
    shouldPersistConversation,
    defaultQuestion,
    variant,
  });
  const [ordinaryConversationMode, setOrdinaryConversationMode] =
    useState<AgentOrdinaryConversationMode>("unknown");
  const {
    repoPath,
    setRepoPath,
    setAvailableProcesses,
    processSearch,
    setProcessSearch,
    selectedProcess,
    setSelectedProcess,
    processLoading,
    setProcessLoading,
    filteredProcesses,
    recentUnpinnedRepoPaths,
    isCurrentRepoPinned,
    beginProcessStateRequest,
    invalidateActiveRequest,
    canCommitProcessState,
    beginProcessLoadSequence,
    isLatestProcessLoad,
  } = useGitNexusProcessPicker({ recentRepoPaths, pinnedRepoPaths });
  const [loading, setLoading] = useState(false);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [agentWaitSeconds, setAgentWaitSeconds] = useState(0);
  const [streamingAnswer, setStreamingAnswer] = useState({ turnId: "", text: "" });
  const [result, setResult] = useState<AgentQueryResult | null>(null);
  const [agentRun, setAgentRun] = useState<AgentRunPayload | null>(null);
  const [error, setError] = useState<AgentQueryError | null>(null);
  const [restoringRunId, setRestoringRunId] = useState(initialRestoringRunId);
  const [restoreErrorRunId, setRestoreErrorRunId] = useState("");
  const [restoreErrorRetryable, setRestoreErrorRetryable] = useState(false);
  const [pageContextChangeNotice, setPageContextChangeNotice] = useState(false);
  const [composerAssistHint, setComposerAssistHint] = useState<string | null>(null);
  const [pendingSuggestedActionConfirmation, setPendingSuggestedActionConfirmation] =
    useState<PendingSuggestedActionConfirmation | null>(null);
  const pageContextSummaryRef = useRef(pageContext ? formatPageContextSummary(pageContext) : "");
  const lastAppliedDefaultQuestionRef = useRef(defaultQuestion.trim());
  const lastObservedDefaultQuestionRef = useRef<string | null>(null);
  const shouldFocusRestoredDraftRef = useRef(
    shouldPersistConversation && !defaultQuestion.trim() && query.trim().length > 0,
  );
  const conversationSessionRef = useRef(0);
  const rerunTurnGateRef = useRef<AgentTurnGate | null>(null);
  const stopActiveAgentTurnRef = useRef<() => void>(() => undefined);
  const submitQueuedQueryRef = useRef<(question: string) => Promise<void>>(async () => undefined);
  const { beginAgentTurn, invalidateActiveAgentTurn, abortActiveAgentTurn } = useAgentTurnGate();
  const {
    requestBackendRunCancel,
    fetchAgentRunStatus,
    createAgentRun,
    queryAgentResult,
    trackActiveManagedRun,
    clearActiveManagedRun,
    takeActiveManagedRunId,
    releaseActiveManagedRun,
  } = useManagedAgentRun(apiClient);
  const latestConversationTurn = conversationTurns[conversationTurns.length - 1] ?? null;
  const activeConversationTurn = conversationTurns.find((turn) => turn.id === activeTurnId) ?? null;
  const latestResultTurn = findLatestTurnWithResult(conversationTurns);
  const latestRunTurn = findLatestTurnWithRun(conversationTurns);
  const runtimeResult = loading ? null : latestResultTurn?.result ?? result;
  const runtimeRun = (
    loading
      ? activeConversationTurn?.agentRun ?? agentRun
      : latestRunTurn?.agentRun ?? agentRun
  ) ?? null;
  const runtimeStatus = buildRuntimeStatus(
    runtimeResult,
    loading,
    runtimeRun,
  );
  const hasConversation = conversationTurns.length > 0 || Boolean(result || error);

  const {
    conversationRef,
    conversationBottomRef,
    composerDockRef,
    composerInputRef,
    shouldStickConversationToBottomRef,
    shouldFocusComposerRef,
    showJumpToLatest,
    setShowJumpToLatest,
    copyFeedback,
    closeResultInteractionDetails,
    closeResultInteractionDetailsExceptSuggestedActionMore,
    focusComposerInput,
    scrollConversationToBottom,
    copyAgentAnswer,
  } = useAgentComposerFocus({
    isWorkbench,
    hasConversation,
    loading,
    latestConversationTurn,
    streamingAnswerText: streamingAnswer.text,
    setComposerAssistHint,
  });

  function currentConversationSession() {
    return conversationSessionRef.current;
  }

  function isCurrentConversationSession(session: number) {
    return conversationSessionRef.current === session;
  }

  function resetConversationSession() {
    conversationSessionRef.current += 1;
  }

  function movePinnedRepoPath(path: string, direction: "up" | "down") {
    reorderPinnedRepoPath(path, direction);
    setComposerAssistHint("已调整固定仓库顺序 · 可继续提问");
    shouldFocusComposerRef.current = true;
    window.setTimeout(focusComposerInput, 0);
  }

  function updateConversationTurn(
    turnId: string,
    updater: (turn: AgentConversationTurn) => AgentConversationTurn,
  ) {
    setConversationTurns((currentTurns) =>
      currentTurns.map((turn) => (turn.id === turnId ? updater(turn) : turn)),
    );
  }

  function scrollToConversationTurn(turnId: string) {
    const turnElement = Array.from(
      conversationRef.current?.querySelectorAll<HTMLElement>("[data-agent-turn-id]") ?? [],
    ).find((element) => element.dataset.agentTurnId === turnId);
    if (typeof turnElement?.scrollIntoView !== "function") {
      return;
    }
    shouldStickConversationToBottomRef.current = false;
    turnElement.scrollIntoView({ behavior: getAgentScrollBehavior(), block: "start" });
  }

  function updateComposerQuery(nextQuery: string) {
    setComposerAssistHint(null);
    writeComposerDraft(nextQuery);
  }

  function clearComposerQuery() {
    setComposerAssistHint(null);
    clearComposerDraftState();
  }

  function clearComposerQueryFromButton() {
    clearComposerQuery();
    setComposerAssistHint("已清空输入 · 可以重新输入");
  }

  const queuedQuery = queuedQueries[0] ?? "";
  const latestConversationTurnIsUnresolved = Boolean(
    latestConversationTurn &&
      !latestConversationTurn.result &&
      !latestConversationTurn.error &&
      !latestConversationTurn.stopped,
  );

  function cancelQueuedQuery() {
    setQueuedQueries((currentQueries) => currentQueries.slice(1));
    setComposerAssistHint("已取消排队草稿 · 可以继续输入");
    focusComposerInput();
  }

  function restoreQueuedQueryToComposer() {
    if (!queuedQuery.trim()) {
      return;
    }
    updateComposerQuery(queuedQuery);
    setQueuedQueries((currentQueries) => currentQueries.slice(1));
    setComposerAssistHint("已恢复排队草稿 · Enter 重新排队");
    shouldFocusComposerRef.current = true;
    focusComposerInput();
  }

  useEffect(() => {
    if (!shouldFocusRestoredDraftRef.current) {
      return;
    }
    shouldFocusRestoredDraftRef.current = false;
    focusComposerInput();
  }, [focusComposerInput]);

  useEffect(() => {
    const nextDefaultQuestion = defaultQuestion.trim();
    if (lastObservedDefaultQuestionRef.current === nextDefaultQuestion) {
      return;
    }
    // 同一次默认问题只处理一次，清空或发送草稿后不重新回填。
    lastObservedDefaultQuestionRef.current = nextDefaultQuestion;
    if (shouldPersistConversation || !nextDefaultQuestion) {
      lastAppliedDefaultQuestionRef.current = nextDefaultQuestion;
      return;
    }
    const currentQuery = query.trim();
    const lastAppliedDefaultQuestion = lastAppliedDefaultQuestionRef.current;
    if (currentQuery && currentQuery !== lastAppliedDefaultQuestion) {
      return;
    }
    lastAppliedDefaultQuestionRef.current = nextDefaultQuestion;
    setQuery(nextDefaultQuestion);
    focusComposerInput();
  }, [defaultQuestion, focusComposerInput, query, setQuery, shouldPersistConversation]);

  useEffect(() => {
    const nextPageContextSummary = pageContext ? formatPageContextSummary(pageContext) : "";
    if (!pageContextSummaryRef.current) {
      pageContextSummaryRef.current = nextPageContextSummary;
      return;
    }
    if (nextPageContextSummary === pageContextSummaryRef.current) {
      return;
    }
    pageContextSummaryRef.current = nextPageContextSummary;
    if (isEmbedded) {
      setPageContextChangeNotice(true);
    }
  }, [isEmbedded, pageContext]);

  useEffect(() => {
    if (!loading) {
      return;
    }
    const intervalId = window.setInterval(() => {
      setAgentWaitSeconds((currentSeconds) => currentSeconds + 1);
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [loading]);

  useEffect(() => {
    return () => {
      // 卸载时只中止前端等待（SSE/轮询/同步查询），不取消后端 run：刷新或路由切换后仍可恢复。
      abortActiveAgentTurn();
    };
  }, [abortActiveAgentTurn]);

  useAgentRunRestore({
    shouldPersistConversation,
    currentConversationSession,
    isCurrentConversationSession,
    fetchAgentRunStatus,
    setRestoringRunId,
    setRestoreErrorRunId: (runId, retryable = false) => {
      setRestoreErrorRunId(runId);
      setRestoreErrorRetryable(retryable);
    },
    setOrdinaryConversationMode,
    setAgentRun,
    setConversationTurns,
    setResult,
    setError,
  });

  async function executeManagedAgentRun(
    question: string,
    turnId: string,
    turnGate: AgentTurnGate,
    conversationContext?: AgentConversationContext,
    existingRun?: AgentRunPayload,
  ) {
    const normalizedRepoPath = repoPath.trim();
    const requestVersion = beginProcessStateRequest();
    const requestBody = buildAgentRequestBody(
      question,
      normalizedRepoPath,
      selectedProcess,
      conversationContext,
      pageContext,
      undefined,
      isWorkbench ? "standalone_workbench" : undefined,
    );
    Object.assign(requestBody, modelSelection.requestOptions);
    // 回合提交门与 GitNexus 进程列表提交门解耦：run 进行中编辑仓库路径、点最近仓库、
    // 点"读取流程"只会使进程列表请求失效，不能丢弃本回合的终态结果/错误提交。
    // 回合提交只看回合版本/停止信号与会话版本（新对话/新提问会重置会话）。
    const conversationSession = currentConversationSession();
    const canCommitTurnState = () =>
      turnGate.isCurrent() && isCurrentConversationSession(conversationSession);
    let acceptedManagedRunId = existingRun?.run_id ?? "";
    clearActiveManagedRun();
    if (existingRun) {
      trackActiveManagedRun(existingRun.run_id);
    }
    setAgentRun(existingRun ?? null);
    setResult(null);
    setStreamingAnswer({ turnId, text: "" });
    let useAnswerDeltas = false;
    let lastDeltaSeq = 0;
    let partialAnswer = "";
    try {
      const finalPayload = await runManagedAgentPolling({
        requestBody,
        existingRun,
        createAgentRun: async (body: AgentQueryRequest) => {
          const payload = await createAgentRun(body);
          if (payload.run_kind !== "sync") {
            if (turnGate.signal.aborted) {
              // 用户在 run 建立前就点了停止：拿到 run_id 后立即请求后端取消。
              requestBackendRunCancel(payload.run_id);
            } else {
              acceptedManagedRunId = payload.run_id;
              trackActiveManagedRun(payload.run_id);
            }
          }
          return payload;
        },
        fetchAgentRunStatus,
        canCommit: canCommitTurnState,
        signal: turnGate.signal,
        streamAgentRunEvents: (runId, onRunUpdate, options) =>
          useAnswerDeltas
            ? streamAgentLabRunEvents(runId, {
                onRunUpdate,
                onRunDelta: (delta) => {
                  if (!canCommitTurnState()) return;
                  lastDeltaSeq = delta.seq;
                  partialAnswer += delta.text;
                  setStreamingAnswer({ turnId, text: partialAnswer });
                },
              }, { ...options, afterSeq: lastDeltaSeq })
            : streamAgentRunEvents(runId, onRunUpdate, options),
        onRunAccepted: (payload, runRequestLatencyMs) => {
          useAnswerDeltas = isWorkbench && payload.provider === "hermes";
          setOrdinaryConversationMode("managed");
          setAgentRun(payload);
          // 持久化交给 useConversationPersistence 的 write-through effect；
          // 不在 state 更新器内执行副作用（StrictMode/并发渲染下更新器可能重放）。
          setConversationTurns((currentTurns) =>
            currentTurns.map((turn) =>
              turn.id === turnId
                ? { ...turn, agentRun: payload, runRequestLatencyMs: runRequestLatencyMs ?? turn.runRequestLatencyMs }
                : turn,
            ),
          );
          persistPersistedLatestRunId(payload.run_id);
        },
        onRunUpdate: (payload) => {
          setOrdinaryConversationMode("managed");
          setAgentRun(payload);
          updateConversationTurn(turnId, (turn) => ({
            ...turn,
            agentRun: payload,
          }));
        },
      });

      if (!canCommitTurnState()) {
        return;
      }

      const payload = finalPayload.result;
      const nextProcesses = extractProcessNames(payload.cards);
      // 进程列表仍受 processState 门约束：仓库路径已改或已有新的进程请求时不覆盖列表。
      if (nextProcesses.length > 0 && canCommitProcessState(requestVersion, normalizedRepoPath)) {
        setAvailableProcesses(nextProcesses);
        setSelectedProcess((current) => (current && nextProcesses.includes(current) ? current : nextProcesses[0] ?? ""));
      }

      if (normalizedRepoPath.length > 0) {
        rememberRepoPath(normalizedRepoPath);
      }
      setResult(payload);
      updateConversationTurn(turnId, (turn) => ({
        ...turn,
        agentRun: finalPayload,
        result: payload,
        error: null,
        activeSuggestedActionPayload: null,
      }));
      shouldFocusComposerRef.current = true;
      window.setTimeout(focusComposerInput, 0);
    } catch (requestError) {
      if (isAbortError(requestError)) {
        return;
      }
      if (requestError instanceof AgentRunCancelledError) {
        if (canCommitTurnState()) {
          const cancelledRun = requestError.payload;
          setAgentRun(cancelledRun);
          updateConversationTurn(turnId, (turn) => ({
            ...turn,
            agentRun: cancelledRun,
            result: null,
            error: null,
            activeSuggestedActionPayload: null,
          }));
          shouldFocusComposerRef.current = true;
          window.setTimeout(focusComposerInput, 0);
        }
        return;
      }
      if (canCommitTurnState()) {
        if (requestError instanceof AgentDisabledQueryError) {
          const disabledError: AgentQueryError = {
            kind: "disabled",
            detail: requestError.detail,
            phase: requestError.phase,
          };
          setError(disabledError);
          updateConversationTurn(turnId, (turn) => ({ ...turn, error: disabledError }));
          shouldFocusComposerRef.current = true;
          window.setTimeout(focusComposerInput, 0);
          return;
        }
        const nextError: AgentQueryError = {
          kind: "request",
          message: buildErrorMessage(requestError),
        };
        setError(nextError);
        updateConversationTurn(turnId, (turn) => ({ ...turn, error: nextError }));
        shouldFocusComposerRef.current = true;
        window.setTimeout(focusComposerInput, 0);
      }
    } finally {
      if (turnGate.isCurrent()) {
        releaseActiveManagedRun(acceptedManagedRunId);
      }
    }
  }

  async function executeAgentQuery(
    question: string,
    mode: "query" | "processes" = "query",
    turnId?: string,
    conversationContext?: AgentConversationContext,
    contextPatch?: Record<string, unknown>,
    turnGate?: AgentTurnGate,
  ) {
    const normalizedRepoPath = repoPath.trim();
    const requestVersion = beginProcessStateRequest();
    // 同步查询提交门 = 进程状态版本门 ∧ 回合版本门：回合被停止/替换后不得再写页面状态。
    const canCommitQueryState = () =>
      canCommitProcessState(requestVersion, normalizedRepoPath) && (turnGate?.isCurrent() ?? true);
    try {
      const requestBody = buildAgentRequestBody(
        question,
        normalizedRepoPath,
        selectedProcess,
        conversationContext,
        pageContext,
        contextPatch,
      );

      const payload = await queryAgentResult(requestBody, turnGate);
      if (turnGate && !turnGate.isCurrent()) {
        return undefined;
      }

      const nextProcesses = extractProcessNames(payload.cards);
      if (nextProcesses.length > 0 && canCommitQueryState()) {
        setAvailableProcesses(nextProcesses);
        setSelectedProcess((current) => (current && nextProcesses.includes(current) ? current : nextProcesses[0] ?? ""));
      } else if (mode === "processes" && canCommitQueryState()) {
        setAvailableProcesses([]);
        setSelectedProcess("");
      }

      if (normalizedRepoPath.length > 0 && canCommitQueryState()) {
        rememberRepoPath(normalizedRepoPath);
      }
      if (canCommitQueryState()) {
        setResult(payload);
      }
      return payload;
    } catch (requestError) {
      if (isAbortError(requestError)) {
        // 停止等待 / 换新问题导致的中止：不写错误，也不让调用方补写 failed run。
        return undefined;
      }
      if (requestError instanceof AgentDisabledQueryError) {
        if (!canCommitQueryState()) {
          return undefined;
        }
        const disabledError: AgentQueryError = {
          kind: "disabled",
          detail: requestError.detail,
          phase: requestError.phase,
        };
        setError(disabledError);
        if (turnId) {
          updateConversationTurn(turnId, (turn) => ({ ...turn, error: disabledError }));
        }
        return undefined;
      }
      if (canCommitQueryState()) {
        const nextError: AgentQueryError = {
          kind: "request",
          message: buildErrorMessage(requestError),
        };
        setError(nextError);
        if (turnId) {
          updateConversationTurn(turnId, (turn) => ({ ...turn, error: nextError }));
        }
        return undefined;
      }
    }
  }

  async function executeLocalSyncConversation(
    question: string,
    turnId: string,
    turnGate: AgentTurnGate,
    conversationContext?: AgentConversationContext,
    contextPatch?: Record<string, unknown>,
  ) {
    const syncRunId = `agent_run:sync:${turnId}`;
    const runningSyncRun = buildLocalSyncAgentRun(syncRunId, question, "running");
    setOrdinaryConversationMode("local_sync");
    setAgentRun(runningSyncRun);
    setResult(null);
    updateConversationTurn(turnId, (turn) => ({
      ...turn,
      agentRun: runningSyncRun,
      error: null,
    }));

    const payload = await executeAgentQuery(
      question,
      "query",
      turnId,
      conversationContext,
      contextPatch,
      turnGate,
    );
    if (!turnGate.isCurrent()) {
      // 回合已被停止/替换：既不写 failed run，也不写结果，交给新回合接管。
      return;
    }
    if (!payload) {
      const failedSyncRun = buildLocalSyncAgentRun(
        syncRunId,
        question,
        "failed",
        null,
        "本地查询失败，请稍后重试。",
      );
      setAgentRun(failedSyncRun);
      updateConversationTurn(turnId, (turn) => ({
        ...turn,
        agentRun: failedSyncRun,
      }));
      shouldFocusComposerRef.current = true;
      window.setTimeout(focusComposerInput, 0);
      return;
    }

    const completedSyncRun = buildLocalSyncAgentRun(syncRunId, question, "completed", payload);
    setAgentRun(completedSyncRun);
    updateConversationTurn(turnId, (turn) => ({
      ...turn,
      agentRun: completedSyncRun,
      result: payload,
      error: null,
      activeSuggestedActionPayload: null,
    }));
    shouldFocusComposerRef.current = true;
    window.setTimeout(focusComposerInput, 0);
  }

  async function executeSuggestedIntentAction(action: AgentSuggestedAction, intent: string) {
    if (loading) {
      return;
    }

    const actionLabel = action.label.trim() || intent;
    const displayQuestion = `执行建议动作：${actionLabel}`;
    const context = buildConversationContext(conversationTurns);
    const turn = createAgentConversationTurn(displayQuestion, context);

    const turnGate = beginAgentTurn();
    setActiveTurnId(turn.id);
    setAgentWaitSeconds(0);
    setConversationTurns((currentTurns) => [...currentTurns, turn]);
    shouldFocusComposerRef.current = true;
    setLoading(true);
    setError(null);

    try {
      await executeLocalSyncConversation(actionLabel, turn.id, turnGate, context, {
        intent,
        suggested_action: action,
        suggested_action_requires_confirmation: action.requires_confirmation,
        ...(action.confirmation_token
          ? { suggested_action_confirmation_token: action.confirmation_token }
          : {}),
      });
    } finally {
      if (turnGate.isCurrent()) {
        setLoading(false);
        setActiveTurnId(null);
      }
    }
  }

  async function executeOrdinaryConversation(
    question: string,
    turnId: string,
    turnGate: AgentTurnGate,
    conversationContext?: AgentConversationContext,
  ) {
    setStreamingAnswer({ turnId, text: "" });
    // 纯问候不需要消耗用户选中的模型或思考额度；模型选择只影响真正的开放问题。
    if (isLocalOpenChatQuestion(question) && !conversationContext?.recent_turns.length) {
      await executeLocalSyncConversation(question, turnId, turnGate, conversationContext);
      return;
    }
    const localQueryIntent = getLocalAgentQueryIntent(question);
    if (localQueryIntent) {
      await executeLocalSyncConversation(question, turnId, turnGate, conversationContext, {
        intent: localQueryIntent,
      });
      return;
    }
    if (isWorkbench && isPlainAnalysisConversationQuestion(question)) {
      await executeManagedAgentRun(question, turnId, turnGate, conversationContext);
      return;
    }
    if (shouldUseLocalAnalysisConversation(question, conversationContext)) {
      await executeLocalSyncConversation(question, turnId, turnGate, conversationContext);
      return;
    }
    if (!isWorkbench && ordinaryConversationMode === "local_sync") {
      await executeLocalSyncConversation(question, turnId, turnGate, conversationContext);
      return;
    }
    if (ordinaryConversationMode === "managed") {
      await executeManagedAgentRun(question, turnId, turnGate, conversationContext);
      return;
    }

    await executeManagedAgentRun(question, turnId, turnGate, conversationContext);
  }

  function canRetryAgentTurn(turn: AgentConversationTurn) {
    return turn.retryMode === "ordinary" && turn.question.trim().length > 0 && Boolean(turn.error)
      && turn.agentRun?.status !== "completed";
  }

  function canReconnectAgentTurn(turn: AgentConversationTurn) {
    return turn.error?.kind === "request" && turn.agentRun?.run_kind !== "sync"
      && (turn.agentRun?.status === "queued" || turn.agentRun?.status === "running");
  }

  function canRegenerateAgentTurn(turn: AgentConversationTurn) {
    return turn.retryMode === "ordinary" && turn.question.trim().length > 0 && Boolean(turn.result);
  }

  async function rerunOrdinaryTurn(
    turn: AgentConversationTurn,
    rerunComposerHint = "正在重新发送 · 可继续输入下一句",
    existingRun?: AgentRunPayload,
  ) {
    if (loading || rerunTurnGateRef.current?.isCurrent()) {
      return;
    }

    if (turn.id !== latestConversationTurn?.id) {
      shouldStickConversationToBottomRef.current = false;
      window.setTimeout(() => scrollToConversationTurn(turn.id), 0);
    }

    const turnGate = beginAgentTurn();
    rerunTurnGateRef.current = turnGate;
    if (existingRun) {
      resetConversationSession();
      setRestoringRunId("");
      setRestoreErrorRunId("");
    }
    setActiveTurnId(turn.id);
    setAgentWaitSeconds(0);
    setLoading(true);
    setError(null);
    setAgentRun(null);
    setResult(null);
    if (query.trim() === turn.question.trim()) {
      clearComposerQuery();
    }
    setComposerAssistHint(rerunComposerHint);
    shouldFocusComposerRef.current = true;
    updateConversationTurn(turn.id, (currentTurn) => ({
      ...currentTurn,
      agentRun: existingRun ?? null,
      result: null,
      error: null,
      stopped: false,
      activeSuggestedActionPayload: null,
    }));

    try {
      if (existingRun) {
        await executeManagedAgentRun(turn.question, turn.id, turnGate, turn.conversationContext, existingRun);
      } else {
        await executeOrdinaryConversation(turn.question, turn.id, turnGate, turn.conversationContext);
      }
    } finally {
      if (rerunTurnGateRef.current === turnGate) {
        rerunTurnGateRef.current = null;
      }
      if (turnGate.isCurrent()) {
        setComposerAssistHint((currentHint) => (currentHint === rerunComposerHint ? null : currentHint));
        shouldFocusComposerRef.current = true;
        window.setTimeout(focusComposerInput, 0);
        setLoading(false);
        setActiveTurnId(null);
      }
    }
  }

  async function retryAgentTurn(turn: AgentConversationTurn) {
    if (!canRetryAgentTurn(turn)) {
      return;
    }
    if (canReconnectAgentTurn(turn) && turn.agentRun) {
      await rerunOrdinaryTurn(turn, "正在重新连接原任务 · 可继续输入下一句", turn.agentRun);
      return;
    }
    await rerunOrdinaryTurn(turn, "正在重试这一轮 · 可继续输入下一句");
  }

  async function regenerateAgentTurn(turn: AgentConversationTurn) {
    if (!canRegenerateAgentTurn(turn)) {
      return;
    }
    await rerunOrdinaryTurn(turn, "正在重新生成 · 可继续输入下一句");
  }

  function stopActiveAgentTurn() {
    if (!loading || !activeConversationTurn) {
      return;
    }

    const activeManagedRunId = takeActiveManagedRunId();
    // 回合作废 + 中止：托管 run 的 SSE/轮询与本地同步查询都不再写状态，
    // 旧回合迟到的 finally 也不会把新提交的 loading 改回 false。
    invalidateActiveAgentTurn();
    if (activeManagedRunId) {
      requestBackendRunCancel(activeManagedRunId);
    }

    invalidateActiveRequest();
    setLoading(false);
    setActiveTurnId(null);
    setAgentWaitSeconds(0);
    setAgentRun(null);
    setResult(null);
    setError(null);
    let restoredQueryToComposer = false;
    if (queuedQuery.trim()) {
      updateComposerQuery(queuedQuery);
      clearQueuedQueries();
      restoredQueryToComposer = true;
    } else if (!query.trim()) {
      updateComposerQuery(activeConversationTurn.question);
      restoredQueryToComposer = true;
    }
    if (restoredQueryToComposer) {
      setComposerAssistHint("已恢复到输入框 · 可编辑后重新发送");
    } else if (query.trim()) {
      setComposerAssistHint("已停止等待 · 可继续发送当前输入");
    }
    if (shouldPersistConversation) {
      clearPersistedLatestRunId();
    }
    shouldFocusComposerRef.current = true;
    updateConversationTurn(activeConversationTurn.id, (turn) => ({
      ...turn,
      agentRun: null,
      result: null,
      error: null,
      stopped: true,
      activeSuggestedActionPayload: null,
    }));
  }
  stopActiveAgentTurnRef.current = stopActiveAgentTurn;

  useEffect(() => {
    if (!loading) {
      return;
    }
    function handleEscapeStop(event: KeyboardEvent) {
      if (event.key !== "Escape" || event.isComposing || event.defaultPrevented) {
        return;
      }
      if (isEmbedded) {
        // 嵌入态回答中：Escape 只停止当前回答，拦截住不让宿主抽屉同时关闭；
        // 停止后（loading=false）监听被移除，再按 Escape 才走宿主的关闭逻辑。
        event.stopPropagation();
      }
      stopActiveAgentTurnRef.current();
    }
    // capture 阶段注册，才能抢在宿主（antd Drawer 等）的 Escape 处理之前拦截。
    window.addEventListener("keydown", handleEscapeStop, { capture: isEmbedded });
    return () => window.removeEventListener("keydown", handleEscapeStop, { capture: isEmbedded });
  }, [loading, isEmbedded]);

  async function handleSubmit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (loading) {
      queueCurrentQuery();
      return;
    }

    const question = query.trim();
    if (!question) {
      const nextError: AgentQueryError = {
        kind: "request",
        message: "请输入查询问题。",
      };
      setError(nextError);
      return;
    }

    const context = buildConversationContext(conversationTurns);
    const turn = createAgentConversationTurn(question, context, "ordinary");
    const turnGate = beginAgentTurn();
    setActiveTurnId(turn.id);
    setAgentWaitSeconds(0);
    resetConversationSession();
    invalidateActiveRequest();
    if (shouldPersistConversation) {
      clearPersistedLatestRunId();
    }
    if (isEmbedded) {
      setPageContextChangeNotice(false);
    }
    setRestoringRunId("");
    setRestoreErrorRunId("");
    setPendingSuggestedActionConfirmation(null);
    setAgentRun(null);
    setResult(null);
    setConversationTurns((currentTurns) => [...currentTurns, turn]);
    clearComposerQuery();
    shouldFocusComposerRef.current = true;
    setLoading(true);
    setError(null);
    try {
      await executeOrdinaryConversation(question, turn.id, turnGate, context);
    } finally {
      // 只有最新回合才能改 loading：停止后立即提交新问题时，旧回合的 finally
      // 不得把新回合的"分析中"提前显示为完成态。
      if (turnGate.isCurrent()) {
        setLoading(false);
        setActiveTurnId(null);
      }
    }
  }

  function queueCurrentQuery() {
    if (!loading || isEmbedded) {
      return;
    }
    const nextQueuedQuery = query.trim();
    if (!nextQueuedQuery) {
      return;
    }
    const nextQueuedCount = queuedQueries.length + 1;
    setQueuedQueries((currentQueries) => [...currentQueries, nextQueuedQuery]);
    clearComposerQuery();
    setComposerAssistHint(formatQueuedComposerHint(nextQueuedQuery, nextQueuedCount));
    shouldFocusComposerRef.current = true;
    focusComposerInput();
  }

  async function submitQueuedQuery(question: string) {
    const context = buildConversationContext(conversationTurns);
    const turn = createAgentConversationTurn(question, context, "ordinary");
    const turnGate = beginAgentTurn();
    setActiveTurnId(turn.id);
    setAgentWaitSeconds(0);
    setPendingSuggestedActionConfirmation(null);
    setConversationTurns((currentTurns) => [...currentTurns, turn]);
    shouldFocusComposerRef.current = true;
    setLoading(true);
    setError(null);
    setComposerAssistHint("正在发送排队问题 · 可继续输入下一句");
    try {
      await executeOrdinaryConversation(question, turn.id, turnGate, context);
    } finally {
      if (turnGate.isCurrent()) {
        setComposerAssistHint((currentHint) =>
          currentHint === "正在发送排队问题 · 可继续输入下一句" ? null : currentHint,
        );
        setLoading(false);
        setActiveTurnId(null);
        shouldFocusComposerRef.current = true;
        window.setTimeout(focusComposerInput, 0);
      }
    }
  }
  submitQueuedQueryRef.current = submitQueuedQuery;

  useEffect(() => {
    if (loading || latestConversationTurnIsUnresolved || !queuedQuery.trim()) {
      return;
    }
    const nextQueuedQuery = queuedQuery.trim();
    setQueuedQueries((currentQueries) => currentQueries.slice(1));
    void submitQueuedQueryRef.current(nextQueuedQuery);
  }, [latestConversationTurnIsUnresolved, loading, queuedQuery, setQueuedQueries]);

  async function executeFinancialWorkflow(workflow: FinancialWorkflowShortcut) {
    if (loading) {
      return;
    }

    const turn = createAgentConversationTurn(workflow.slashCommand);
    const pendingWorkflowRun = buildPendingAgentRun(
      `agent_run:workflow:${workflow.id}:pending`,
      workflow.slashCommand,
      "workflow",
    );
    const turnGate = beginAgentTurn();
    setActiveTurnId(turn.id);
    setAgentWaitSeconds(0);
    setConversationTurns((currentTurns) => [
      ...currentTurns,
      {
        ...turn,
        agentRun: pendingWorkflowRun,
        stopped: false,
      },
    ]);
    setLoading(true);
    setAgentRun(pendingWorkflowRun);
    setResult(null);
    setError(null);
    setComposerAssistHint("正在执行 Workflow · 可继续输入下一句");
    shouldFocusComposerRef.current = true;

    try {
      const payload = await queryAgentResult(
        buildFinancialWorkflowRequestBody(workflow, pageContext),
        turnGate,
      );
      if (!turnGate.isCurrent()) {
        return;
      }

      const workflowRun: AgentRunPayload = {
        run_id: `agent_run:workflow:${workflow.id}`,
        status: "completed",
        run_kind: "workflow",
        provider: formatRuntimeLabel(payload.evidence.filters_applied.provider, "local"),
        model: formatRuntimeLabel(payload.evidence.filters_applied.model, "MOSS intents"),
        transport: formatRuntimeLabel(payload.evidence.filters_applied.transport, "sync"),
        toolsets: workflow.mappedIntents.join(", "),
        result: payload,
      };
      setOrdinaryConversationMode("local_sync");
      setAgentRun(workflowRun);
      setResult(payload);
      updateConversationTurn(turn.id, (currentTurn) => ({
        ...currentTurn,
        agentRun: workflowRun,
        result: payload,
        error: null,
        activeSuggestedActionPayload: null,
      }));
      setComposerAssistHint("Workflow 执行完成 · 可以继续追问");
      shouldFocusComposerRef.current = true;
      window.setTimeout(focusComposerInput, 0);
    } catch (requestError) {
      if (isAbortError(requestError) || !turnGate.isCurrent()) {
        return;
      }
      if (requestError instanceof AgentDisabledQueryError) {
        const disabledError: AgentQueryError = {
          kind: "disabled",
          detail: requestError.detail,
          phase: requestError.phase,
        };
        setError(disabledError);
        updateConversationTurn(turn.id, (currentTurn) => ({ ...currentTurn, error: disabledError }));
        setComposerAssistHint("Workflow 执行失败 · 可重新点击或手动提问");
        shouldFocusComposerRef.current = true;
        window.setTimeout(focusComposerInput, 0);
        return;
      }
      const nextError: AgentQueryError = {
        kind: "request",
        message: buildErrorMessage(requestError),
      };
      setError(nextError);
      updateConversationTurn(turn.id, (currentTurn) => ({ ...currentTurn, error: nextError }));
      setComposerAssistHint("Workflow 执行失败 · 可重新点击或手动提问");
      shouldFocusComposerRef.current = true;
      window.setTimeout(focusComposerInput, 0);
    } finally {
      if (turnGate.isCurrent()) {
        setLoading(false);
        setActiveTurnId(null);
      }
    }
  }

  async function executeResearchShortcut(shortcut: ResearchShortcut) {
    if (loading) {
      return;
    }

    const turn = createAgentConversationTurn(shortcut.question);
    const pendingRun = buildPendingAgentRun(
      `agent_run:research:${shortcut.id}:pending`,
      shortcut.question,
      "sync",
    );
    const turnGate = beginAgentTurn();
    setActiveTurnId(turn.id);
    setAgentWaitSeconds(0);
    setConversationTurns((currentTurns) => [
      ...currentTurns,
      {
        ...turn,
        agentRun: pendingRun,
        stopped: false,
      },
    ]);
    setLoading(true);
    setAgentRun(pendingRun);
    setResult(null);
    setError(null);
    setComposerAssistHint("正在读取研究上下文 · 可继续输入下一句");
    shouldFocusComposerRef.current = true;

    try {
      const payload = await queryAgentResult(
        buildResearchRequestBody(shortcut, pageContext),
        turnGate,
      );
      if (!turnGate.isCurrent()) {
        return;
      }

      const researchRun: AgentRunPayload = {
        run_id: `agent_run:research:${shortcut.id}`,
        status: "completed",
        run_kind: "sync",
        question: shortcut.question,
        provider: formatRuntimeLabel(payload.evidence.filters_applied.provider, "dexter"),
        model: formatRuntimeLabel(payload.evidence.filters_applied.model, "default"),
        transport: formatRuntimeLabel(payload.evidence.filters_applied.transport, "sync"),
        toolsets: formatRuntimeLabel(payload.evidence.filters_applied.toolsets, "research"),
        result: payload,
      };
      setOrdinaryConversationMode("local_sync");
      setAgentRun(researchRun);
      setResult(payload);
      updateConversationTurn(turn.id, (currentTurn) => ({
        ...currentTurn,
        agentRun: researchRun,
        result: payload,
        error: null,
        activeSuggestedActionPayload: null,
      }));
      setComposerAssistHint("研究上下文已返回 · 可以继续追问");
      shouldFocusComposerRef.current = true;
      window.setTimeout(focusComposerInput, 0);
    } catch (requestError) {
      if (isAbortError(requestError) || !turnGate.isCurrent()) {
        return;
      }
      if (requestError instanceof AgentDisabledQueryError) {
        const disabledError: AgentQueryError = {
          kind: "disabled",
          detail: requestError.detail,
          phase: requestError.phase,
        };
        setError(disabledError);
        updateConversationTurn(turn.id, (currentTurn) => ({ ...currentTurn, error: disabledError }));
        setComposerAssistHint("研究快捷入口失败 · 可重新点击或手动提问");
        shouldFocusComposerRef.current = true;
        window.setTimeout(focusComposerInput, 0);
        return;
      }
      const nextError: AgentQueryError = {
        kind: "request",
        message: buildErrorMessage(requestError),
      };
      setError(nextError);
      updateConversationTurn(turn.id, (currentTurn) => ({ ...currentTurn, error: nextError }));
      setComposerAssistHint("研究快捷入口失败 · 可重新点击或手动提问");
      shouldFocusComposerRef.current = true;
      window.setTimeout(focusComposerInput, 0);
    } finally {
      if (turnGate.isCurrent()) {
        setLoading(false);
        setActiveTurnId(null);
      }
    }
  }

  async function loadGitNexusProcesses(repoPathOverride: string, requestVersion?: number) {
    const normalizedRepoPath = repoPathOverride.trim();
    const activeRequestVersion = requestVersion ?? beginProcessStateRequest();
    if (!normalizedRepoPath) {
      setError({
        kind: "request",
        message: "请先输入 GitNexus 仓库路径。",
      });
      setComposerAssistHint("请先输入 GitNexus 仓库路径 · 再读取流程");
      shouldFocusComposerRef.current = true;
      window.setTimeout(focusComposerInput, 0);
      return;
    }

    // 并发保护：多次点击"读取流程"时只有最后一次请求负责复位 processLoading，
    // 先返回的请求不得把仍在读取中的按钮改回可用态。
    const processLoadSequence = beginProcessLoadSequence();
    setProcessLoading(true);
    setComposerAssistHint("正在读取 GitNexus 流程 · 可继续输入");
    focusComposerInput();
    setError(null);
    try {
      const requestBody: AgentQueryRequest = {
        question: "请给我看 GitNexus processes",
        basis: "formal",
        filters: { repo_path: normalizedRepoPath },
        position_scope: "all",
        currency_basis: "CNY",
        context: {
          user_id: "web-user",
        },
        ...(pageContext ? { page_context: pageContext } : {}),
      };

      const payload = await queryAgentResult(requestBody);

      const nextProcesses = extractProcessNames(payload.cards);
      if (canCommitProcessState(activeRequestVersion, normalizedRepoPath)) {
        setAvailableProcesses(nextProcesses);
        setProcessSearch("");
        setSelectedProcess(nextProcesses[0] ?? "");
        setComposerAssistHint("已读取 GitNexus 流程 · 可选择流程查看");
        shouldFocusComposerRef.current = true;
        window.setTimeout(focusComposerInput, 0);
        rememberRepoPath(normalizedRepoPath);
        setResult(payload);
        setConversationTurns((currentTurns) => [
          ...currentTurns,
          {
            id: `processes:${Date.now()}:${Math.random().toString(16).slice(2)}`,
            question: requestBody.question,
            agentRun: {
              run_id: "agent_run:sync_processes",
              status: "completed",
              run_kind: "sync",
              provider: formatRuntimeLabel(payload.evidence.filters_applied.provider, "local"),
              model: formatRuntimeLabel(payload.evidence.filters_applied.model, "default"),
              transport: formatRuntimeLabel(payload.evidence.filters_applied.transport, "sync"),
              toolsets: formatRuntimeLabel(payload.evidence.filters_applied.toolsets, "GitNexus"),
              result: payload,
            },
            result: payload,
            error: null,
            stopped: false,
            activeSuggestedActionPayload: null,
          },
        ]);
      }
    } catch (requestError) {
      if (isAbortError(requestError)) {
        return;
      }
      if (canCommitProcessState(activeRequestVersion, normalizedRepoPath)) {
        setError({
          kind: "request",
          message: buildErrorMessage(requestError),
        });
        setComposerAssistHint("读取 GitNexus 流程失败 · 可修改仓库路径后重试");
        shouldFocusComposerRef.current = true;
        focusComposerInput();
      }
    } finally {
      // 不看进程状态版本号复位：读取期间任何提问/新的进程请求都会 bump 版本号，
      // 若仅在版本未变时复位，"读取流程"按钮会永久卡在"读取中..."。
      // 但要看并发序号：只有最后发起的那次读取负责把按钮改回可用态。
      if (isLatestProcessLoad(processLoadSequence)) {
        setProcessLoading(false);
      }
    }
  }

  async function viewSelectedProcess() {
    if (!selectedProcess) {
      setError({
        kind: "request",
        message: "请先从流程列表选择一个流程。",
      });
      setComposerAssistHint("请先选择 GitNexus 流程 · 再查看");
      shouldFocusComposerRef.current = true;
      focusComposerInput();
      return;
    }
    const question = `请给我看 GitNexus process/${selectedProcess}`;
    const turn = createAgentConversationTurn(question);
    const pendingSyncRun = buildPendingAgentRun(
      `agent_run:sync:${selectedProcess}:pending`,
      question,
      "sync",
    );
    const turnGate = beginAgentTurn();
    setActiveTurnId(turn.id);
    setConversationTurns((currentTurns) => [
      ...currentTurns,
      {
        ...turn,
        agentRun: pendingSyncRun,
        stopped: false,
      },
    ]);
    setAgentWaitSeconds(0);
    setAgentRun(pendingSyncRun);
    setLoading(true);
    setError(null);
    setComposerAssistHint("正在查看 GitNexus 流程 · 可继续输入");
    shouldFocusComposerRef.current = true;
    try {
      const payload = await executeAgentQuery(question, "query", turn.id, undefined, undefined, turnGate);
      if (!turnGate.isCurrent()) {
        return;
      }
      if (!payload) {
        setComposerAssistHint("查看 GitNexus 流程失败 · 可重新选择流程后重试");
        shouldFocusComposerRef.current = true;
        window.setTimeout(focusComposerInput, 0);
        return;
      }
      updateConversationTurn(turn.id, (currentTurn) => ({
        ...currentTurn,
        agentRun: {
          run_id: "agent_run:sync_query",
          status: "completed",
          run_kind: "sync",
          provider: formatRuntimeLabel(payload.evidence.filters_applied.provider, "local"),
          model: formatRuntimeLabel(payload.evidence.filters_applied.model, "default"),
          transport: formatRuntimeLabel(payload.evidence.filters_applied.transport, "sync"),
          toolsets: formatRuntimeLabel(payload.evidence.filters_applied.toolsets, "default"),
          result: payload,
        },
        result: payload,
        error: null,
        stopped: false,
        activeSuggestedActionPayload: null,
      }));
      setComposerAssistHint("已查看 GitNexus 流程 · 可继续追问");
      shouldFocusComposerRef.current = true;
      window.setTimeout(focusComposerInput, 0);
    } finally {
      if (turnGate.isCurrent()) {
        setComposerAssistHint((currentHint) =>
          currentHint === "正在查看 GitNexus 流程 · 可继续输入" ? null : currentHint,
        );
        setLoading(false);
        setActiveTurnId(null);
      }
    }
  }

  function applyQuickExample(nextQuery: string) {
    replaceComposerQuery(nextQuery);
    setComposerAssistHint("已填入快捷问题 · Enter 发送");
  }

  function replaceComposerQuery(nextQuery: string) {
    updateComposerQuery(nextQuery);
    clearQueuedQueries();
    setError(null);
    setRestoreErrorRunId("");
    focusComposerInput();
  }

  function startFreshConversation() {
    setConversationTurns([]);
    setActiveTurnId(null);
    resetConversationSession();
    invalidateActiveAgentTurn();
    setOrdinaryConversationMode("unknown");
    setAgentWaitSeconds(0);
    setResult(null);
    setAgentRun(null);
    setError(null);
    setRestoringRunId("");
    setRestoreErrorRunId("");
    clearQueuedQueries();
    clearComposerQuery();
    setComposerAssistHint("已开启新对话 · 可以直接提问");
    clearPersistedLatestRunId();
    persistConversationTurnsNow([]);
    shouldFocusComposerRef.current = true;
    window.setTimeout(focusComposerInput, 0);
  }

  function applyRecentRepoPath(nextRepoPath: string) {
    setRepoPath(nextRepoPath);
    setComposerAssistHint("已切换 GitNexus 仓库 · 可继续提问");
    shouldFocusComposerRef.current = true;
    window.setTimeout(focusComposerInput, 0);
  }

  function pinCurrentRepo() {
    const normalized = repoPath.trim();
    if (!normalized) {
      setError({
        kind: "request",
        message: "请先输入 GitNexus 仓库路径。",
      });
      setComposerAssistHint("请先输入 GitNexus 仓库路径 · 再固定仓库");
      shouldFocusComposerRef.current = true;
      window.setTimeout(focusComposerInput, 0);
      return;
    }
    pinRepoPath(normalized);
    setComposerAssistHint("已固定 GitNexus 仓库 · 可继续提问");
    shouldFocusComposerRef.current = true;
    window.setTimeout(focusComposerInput, 0);
  }

  function unpinRepo(path: string) {
    unpinRepoPath(path);
    setComposerAssistHint("已取消固定 GitNexus 仓库 · 可继续提问");
    shouldFocusComposerRef.current = true;
    window.setTimeout(focusComposerInput, 0);
  }

  function pinRememberedRepo(path: string) {
    pinRepoPath(path);
    setComposerAssistHint("已固定 GitNexus 仓库 · 可继续提问");
    shouldFocusComposerRef.current = true;
    window.setTimeout(focusComposerInput, 0);
  }

  function applyNextDrill(drill: AgentNextDrill, sourceElement?: HTMLElement) {
    setPendingSuggestedActionConfirmation(null);
    closeResultInteractionDetails(sourceElement);
    replaceComposerQuery(`请基于当前 evidence 继续下钻：${drill.label}`);
    setComposerAssistHint("已填入建议追问 · Enter 发送");
  }

  function handleSuggestedAction(turnId: string, action: AgentSuggestedAction, sourceElement?: HTMLElement) {
    if (action.type === "inspect_drill" || action.type === "refine_query") {
      setPendingSuggestedActionConfirmation(null);
      closeResultInteractionDetails(sourceElement);
      replaceComposerQuery(`请基于当前 evidence 继续下钻：${action.label}`);
      setComposerAssistHint("已填入建议追问 · Enter 发送");
      return;
    }
    if (readOnly && action.type === "execute_intent") {
      return;
    }
    const intent = getExecutableSuggestedIntent(action);
    if (intent) {
      if (action.requires_confirmation) {
        const actionKey = getSuggestedActionKey(action);
        if (
          pendingSuggestedActionConfirmation?.turnId !== turnId ||
          pendingSuggestedActionConfirmation.actionKey !== actionKey
        ) {
          closeResultInteractionDetailsExceptSuggestedActionMore(sourceElement);
          setPendingSuggestedActionConfirmation({ turnId, actionKey });
          setComposerAssistHint(`请再次确认执行建议动作：${action.label}`);
          return;
        }
      }
      setPendingSuggestedActionConfirmation(null);
      void executeSuggestedIntentAction(action, intent);
      return;
    }
    setPendingSuggestedActionConfirmation(null);
    updateConversationTurn(turnId, (turn) => ({
      ...turn,
      activeSuggestedActionPayload: action.payload,
    }));
    setComposerAssistHint("已选择建议动作 · 可继续提问");
    focusComposerInput();
  }

  function closeFollowUpDetails(sourceElement?: HTMLElement) {
    closeResultInteractionDetails(sourceElement);
  }

  function focusComposerFromFollowUp(sourceElement: HTMLElement) {
    closeFollowUpDetails(sourceElement);
    setComposerAssistHint("可以继续追问 · Enter 发送");
    focusComposerInput();
  }

  function focusComposerFromEmptyResult() {
    setComposerAssistHint("可以调整问题 · Enter 发送");
    focusComposerInput();
  }

  function applyFollowUpChip(question: string, sourceElement?: HTMLElement) {
    closeFollowUpDetails(sourceElement);
    replaceComposerQuery(question);
    setComposerAssistHint("已填入追问 · Enter 发送");
  }

  function editAgentQuestion(turn: AgentConversationTurn) {
    if (turn.retryMode !== "ordinary" || !turn.question.trim()) {
      return;
    }

    if (loading) {
      if (activeConversationTurn?.id !== turn.id) {
        return;
      }
      stopActiveAgentTurn();
    }

    replaceComposerQuery(turn.question);
    setComposerAssistHint("已放回输入框 · 改完按 Enter 发送");
  }

  function canEditAgentQuestion(turn: AgentConversationTurn, isLatestLoadingTurn: boolean) {
    if (turn.retryMode !== "ordinary" || !turn.question.trim()) {
      return false;
    }

    return !loading || isLatestLoadingTurn;
  }

  function formatPageContextSummary(context: AgentPageContext) {
    return JSON.stringify({
      page_id: context.page_id,
      current_filters: context.current_filters,
      selected_rows: context.selected_rows,
      context_note: context.context_note ?? null,
    });
  }

  function getPageContextSummaryLabel(context: AgentPageContext) {
    const attachmentCount = [
      context.page_id,
      Object.keys(context.current_filters).length > 0,
      context.selected_rows.length > 0,
      context.context_note?.trim(),
    ].filter(Boolean).length;
    return `上下文 · ${attachmentCount} 项`;
  }

  const shellClassName = isEmbedded
    ? "agent-workbench-shell agent-workbench-shell--embedded dashboard-home-panel agent-panel"
    : "agent-workbench-shell";
  const runtimeStateLabel = loading ? "分析中" : latestResultTurn?.result ? "已连接" : "待提问";

  return (
    // Nocturne scope 只落在 /agent 页根（workbench 变体）；嵌入态 AgentPanel 跟随宿主页 scope，
    // 深色 owner 仍由 ThemedRouteBoundary 独占（页根不声明 data-moss-theme="dark"）。
    <section
      className={shellClassName}
      data-chat-started={hasConversation ? "true" : "false"}
      data-testid={isEmbedded ? "agent-panel" : undefined}
      data-moss-theme-scope={isEmbedded ? undefined : "agent"}
    >
      {isEmbedded && resolvedShowHeader ? (
        <header className="agent-embedded-header">
          <div>
            <div className="agent-embedded-header__eyebrow">Hermes Copilot</div>
            <h2>页面 Copilot</h2>
          </div>
          {readOnly ? <span>只读</span> : null}
        </header>
      ) : null}

      {!isEmbedded && resolvedShowHeader ? (
        <header className="agent-workbench-header">
          <div>
            <h1>MOSS Chat</h1>
          </div>
          <div className="agent-workbench-header__actions">
              <AgentShortcutDrawer
                loading={loading}
                onExecuteWorkflow={(workflow) => void executeFinancialWorkflow(workflow)}
                onExecuteResearchShortcut={(shortcut) => void executeResearchShortcut(shortcut)}
              />
              <button
                type="button"
                className="agent-workbench-header__new-chat"
                aria-label="新对话"
                onClick={startFreshConversation}
                disabled={loading}
              >
                <PlusOutlined aria-hidden="true" />
                <span>新对话</span>
              </button>
          </div>
        </header>
      ) : null}

      <AgentRuntimeStrip
        loading={loading}
        stateLabel={runtimeStateLabel}
        runtimeStatus={runtimeStatus}
      />

      {isContextlessWorkbench ? (
        <div
          className="agent-context-status agent-context-status--missing"
          role="status"
          aria-label="业务页上下文状态"
        >
          <span>当前为独立对话。解释具体页面时，可从业务页的复核助手带入筛选和选中记录。</span>
        </div>
      ) : null}

      {!isEmbedded && restoringRunId ? (
        <div
          className="agent-restore-status"
          role="status"
          aria-live="polite"
          aria-label="正在恢复上次回答"
        >
          <div>
            <strong>正在恢复上一轮 Agent 状态</strong>
            <span>刷新后正在接回托管运行结果，恢复完成前可以继续查看本地历史。</span>
          </div>
          <code>{restoringRunId}</code>
        </div>
      ) : null}

      {!isEmbedded && restoreErrorRunId ? (
        <div
          className="agent-restore-status agent-restore-status--error"
          role="status"
          aria-live="polite"
          aria-label="上次回答恢复失败"
        >
          <div>
            <strong>上一轮 Agent 状态暂时无法恢复</strong>
            <span>{restoreErrorRetryable
              ? "已保留上次运行，连接恢复后刷新页面可继续接回回答。"
              : "上次运行已不存在或当前无权访问；你可以发起新的提问。"}</span>
          </div>
          <code>{restoreErrorRunId}</code>
        </div>
      ) : null}

      {pageContext ? (
        <details className="agent-page-context">
          <summary>{getPageContextSummaryLabel(pageContext)}</summary>
          <code className="agent-page-context__code">{formatPageContextSummary(pageContext)}</code>
        </details>
      ) : null}

      {isEmbedded && pageContextChangeNotice ? (
        <div
          className="agent-context-change-notice"
          role="status"
          aria-label="页面上下文已更新"
        >
          <strong>页面上下文已更新</strong>
          <span>下一问将使用当前页面选择</span>
        </div>
      ) : null}

      {isWorkbench && !hasConversation ? (
        <div className="agent-chat-welcome">
          <h2>今天想聊些什么？</h2>
          <p>提一个问题，或把需要整理的内容发给我。</p>
        </div>
      ) : null}

      {!hasConversation ? (
        <AgentQueryForm
          modelControls={isWorkbench ? <AgentModelControls state={modelSelection} disabled={loading} /> : undefined}
          compact={isEmbedded}
          showAdvancedTools={!isEmbedded}
          pageContext={pageContext}
          repoPath={repoPath}
          onRepoPathChange={setRepoPath}
          quickExamples={quickExamples}
          onQuickExample={applyQuickExample}
          isCurrentRepoPinned={isCurrentRepoPinned}
          onPinCurrentRepo={pinCurrentRepo}
          onUnpinCurrentRepo={() => unpinRepo(repoPath.trim())}
          processLoading={processLoading}
          onLoadProcesses={() => void loadGitNexusProcesses(repoPath)}
          processSearch={processSearch}
          onProcessSearchChange={setProcessSearch}
          selectedProcess={selectedProcess}
          filteredProcesses={filteredProcesses}
          onSelectedProcessChange={setSelectedProcess}
          onViewSelectedProcess={() => void viewSelectedProcess()}
          loading={loading}
          query={query}
          activeQuestion={activeConversationTurn?.question}
          composerHint={composerAssistHint}
          onQueryChange={updateComposerQuery}
          onClearQuery={clearComposerQueryFromButton}
          onSubmit={handleSubmit}
          onQueueSubmit={isEmbedded ? undefined : queueCurrentQuery}
          onStop={stopActiveAgentTurn}
          inputRef={composerInputRef}
        />
      ) : null}

      {isWorkbench && !hasConversation ? (
        <div className="agent-conversation-starters" aria-label="开始一个话题">
          {[
            { label: "解释一个概念", prompt: "帮我用简单的语言解释这个概念：" },
            { label: "整理一段内容", prompt: "帮我整理下面这段内容，提炼重点：" },
            { label: "比较两个方案", prompt: "帮我比较下面两个方案的区别和适用情况：" },
          ].map((starter) => (
            <button type="button" key={starter.label} onClick={() => applyQuickExample(starter.prompt)}>
              {starter.label}
            </button>
          ))}
        </div>
      ) : null}

      {hasConversation ? (
        <section className="agent-conversation" aria-label="Agent 对话记录" ref={conversationRef}>
          {conversationTurns.map((turn) => {
            const isLatestLoadingTurn = turn.id === activeTurnId && loading;
            const partialAnswer = isLatestLoadingTurn && streamingAnswer.turnId === turn.id ? streamingAnswer.text : "";
            const showThinkingPlaceholder = isLatestLoadingTurn && !turn.result && !turn.error && !partialAnswer;
            const shouldShowRunStatus = (isLatestLoadingTurn || turn.agentRun) && !isCompactProviderChatTurn(turn);
            const conversationContextBadge = formatConversationContextBadge(turn.conversationContext);
            const waitElapsedSeconds = formatAgentRunElapsed(
              turn.agentRun,
              isLatestLoadingTurn ? agentWaitSeconds : 0,
            );
            const thinkingLabel = formatAgentThinkingLabel(turn.agentRun, waitElapsedSeconds);
            const thinkingText = formatAgentThinkingText(turn.agentRun, waitElapsedSeconds);
            const runConnectionElapsed = formatAgentConnectionElapsed(turn.runRequestLatencyMs);
            return (
              <div key={turn.id} className="agent-turn" data-agent-turn-id={turn.id}>
                <div className="agent-message agent-message--user">
                  <div className="agent-message__speaker">我</div>
                  <div className="agent-user-bubble">
                    <div className="agent-message__body">{turn.question}</div>
                    {conversationContextBadge ? (
                      <div className="agent-user-bubble__context">{conversationContextBadge}</div>
                    ) : null}
                    {turn.retryMode === "ordinary" ? (
                      <button
                        type="button"
                        className="agent-user-bubble__edit"
                        aria-label={`编辑问题：${turn.question}`}
                        onClick={() => editAgentQuestion(turn)}
                        disabled={!canEditAgentQuestion(turn, isLatestLoadingTurn)}
                      >
                        <EditOutlined aria-hidden="true" />
                        <span>编辑问题</span>
                      </button>
                    ) : null}
                  </div>
                </div>

                <div className="agent-message agent-message--assistant">
                  <div className="agent-message__speaker">智能体</div>
                  <div className="agent-message__body">
                    {shouldShowRunStatus ? (
                      <div
                        className="agent-wait-status"
                        role="status"
                        aria-label={`回答状态：${turn.question}`}
                        aria-live="polite"
                      >
                        <div className="agent-wait-status__copy">
                          {showThinkingPlaceholder ? (
                            <div className="agent-thinking">
                              <span className="agent-thinking__label">{thinkingLabel}</span>
                              <span className="agent-thinking__text">{thinkingText}</span>
                              <span className="agent-thinking__dots" aria-hidden="true">
                                <span />
                                <span />
                                <span />
                              </span>
                            </div>
                          ) : null}
                          <div className="agent-wait-status__title">
                            {partialAnswer ? "正在生成回答" : formatAgentTurnWaitTitle(turn.agentRun)}
                            {isLatestLoadingTurn ? <span> · {waitElapsedSeconds} 秒</span> : null}
                          </div>
                          {isEmbedded ? <AgentRunProgress agentRun={turn.agentRun} question={turn.question} /> : null}
                        </div>
                        <div className="agent-wait-status__detail">
                          <details className="agent-wait-status__details">
                            <summary aria-label={`运行细节：${turn.question}`}>运行细节</summary>
                            <div className="agent-wait-status__detail-list">
                              <span>{formatAgentWaitPhase(turn.agentRun)}</span>
                              <span>已等待 {waitElapsedSeconds} 秒</span>
                              {runConnectionElapsed ? <span>连接耗时 {runConnectionElapsed}</span> : null}
                              {shouldDisplayAgentRunId(turn.agentRun) ? (
                                <span>run_id: {turn.agentRun?.run_id}</span>
                              ) : null}
                              <span>{formatAgentWaitHint(turn.agentRun, waitElapsedSeconds)}</span>
                            </div>
                          </details>
                          {isLatestLoadingTurn ? (
                            <button
                              type="button"
                              className="agent-wait-status__stop"
                              aria-label={`停止等待当前回答：${turn.question}`}
                              onClick={stopActiveAgentTurn}
                            >
                              停止等待
                            </button>
                          ) : null}
                        </div>
                      </div>
                    ) : null}
                    {turn.stopped ? (
                      <div className="agent-callout agent-callout--stopped" role="status">
                        <strong>已停止等待</strong>
                        <span>已停止等待这次回答。</span>
                        {turn.retryMode === "ordinary" && turn.question.trim() ? (
                          <div className="agent-callout__actions">
                            <button
                              type="button"
                              className="agent-callout__action"
                              aria-label={`编辑这句：${turn.question}`}
                              onClick={() => editAgentQuestion(turn)}
                              disabled={loading}
                            >
                              编辑这句
                            </button>
                            <button
                              type="button"
                              className="agent-callout__action"
                              aria-label={`重新发送：${turn.question}`}
                              onClick={() =>
                                void rerunOrdinaryTurn(
                                  turn,
                                  "正在重新发送已停止等待的回答 · 可继续输入下一句",
                                )
                              }
                              disabled={loading}
                            >
                              重新发送
                            </button>
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    {turn.agentRun?.status === "cancelled" && !turn.result && !turn.stopped ? (
                      <div className="agent-callout agent-callout--stopped" role="status">
                        <strong>任务已取消</strong>
                        <span>这次回答的任务已取消，不会再返回结果。</span>
                        {turn.retryMode === "ordinary" && turn.question.trim() ? (
                          <div className="agent-callout__actions">
                            <button
                              type="button"
                              className="agent-callout__action"
                              aria-label={`编辑这句：${turn.question}`}
                              onClick={() => editAgentQuestion(turn)}
                              disabled={loading}
                            >
                              编辑这句
                            </button>
                            <button
                              type="button"
                              className="agent-callout__action"
                              aria-label={`重新发送：${turn.question}`}
                              onClick={() =>
                                void rerunOrdinaryTurn(
                                  turn,
                                  "正在重新发送已取消的回答 · 可继续输入下一句",
                                )
                              }
                              disabled={loading}
                            >
                              重新发送
                            </button>
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    <AgentTurnErrorCallout
                      turn={turn}
                      loading={loading}
                      canRetry={canRetryAgentTurn(turn)}
                      canReconnect={canReconnectAgentTurn(turn)}
                      onEditQuestion={editAgentQuestion}
                      onRetry={(retryTurn) => void retryAgentTurn(retryTurn)}
                    />
                    {partialAnswer ? (
                      <div className="agent-streaming-answer" aria-label="正在生成的回答">
                        <AgentAnswerPanel answer={partialAnswer} />
                        <span className="agent-answer-notice">生成中，完整回答与依据将在完成后显示。</span>
                      </div>
                    ) : null}
                    <AgentTurnResultView
                      turn={turn}
                      isLatestResultTurn={turn.id === latestResultTurn?.id}
                      isEmbedded={isEmbedded}
                      readOnly={readOnly}
                      loading={loading}
                      latestConversationTurnId={latestConversationTurn?.id ?? null}
                      copyFeedback={copyFeedback}
                      pendingSuggestedActionConfirmation={pendingSuggestedActionConfirmation}
                      canRegenerate={canRegenerateAgentTurn(turn)}
                      onRegenerate={(retryTurn) => void regenerateAgentTurn(retryTurn)}
                      onCopyAnswer={(retryTurn) => void copyAgentAnswer(retryTurn)}
                      onApplyNextDrill={applyNextDrill}
                      onSuggestedAction={handleSuggestedAction}
                      onFocusComposerFromFollowUp={focusComposerFromFollowUp}
                      onApplyFollowUpChip={applyFollowUpChip}
                      onFocusComposerFromEmptyResult={focusComposerFromEmptyResult}
                      onSideDrawerOpen={() => {
                        window.setTimeout(scrollConversationToBottom, 0);
                      }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
          <div
            ref={conversationBottomRef}
            className="agent-conversation__bottom"
            data-testid="agent-conversation-bottom"
            aria-hidden="true"
          />

          {conversationTurns.length === 0 && error ? (
            <div className="agent-message agent-message--assistant">
              <div className="agent-message__speaker">智能体</div>
              <div className="agent-message__body">
                <AgentTurnErrorCallout
                  turn={{
                    id: "page-error",
                    question: "",
                    agentRun: null,
                    result: null,
                    error,
                    activeSuggestedActionPayload: null,
                  }}
                  loading={loading}
                  canRetry={false}
                  onEditQuestion={editAgentQuestion}
                  onRetry={(retryTurn) => void retryAgentTurn(retryTurn)}
                />
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {hasConversation ? (
        <div className="agent-composer-dock" ref={composerDockRef}>
          {isWorkbench && loading && activeConversationTurn && activeConversationTurn.id !== latestConversationTurn?.id ? (
            <div className="agent-active-turn" role="status" aria-label="正在重新回答历史问题">
              <div className="agent-active-turn__copy">
                <strong>正在重新回答</strong>
                <span title={activeConversationTurn.question}>{activeConversationTurn.question}</span>
              </div>
              <button
                type="button"
                className="agent-active-turn__locate"
                aria-label="查看正在回答的问题"
                onClick={() => scrollToConversationTurn(activeConversationTurn.id)}
              >
                查看这句
              </button>
            </div>
          ) : null}
          {isWorkbench && showJumpToLatest ? (
            <button type="button" className="agent-jump-to-latest" aria-label="回到最新回答"
              onClick={() => {
                shouldStickConversationToBottomRef.current = true;
                setShowJumpToLatest(false);
                scrollConversationToBottom();
              }}>
              <ArrowDownOutlined aria-hidden="true" />回到最新
            </button>
          ) : null}
          <AgentQueuedDraft
            queuedQueries={queuedQueries}
            onRestoreToComposer={restoreQueuedQueryToComposer}
            onCancel={cancelQueuedQuery}
          />
          <AgentQueryForm
            modelControls={isWorkbench ? <AgentModelControls state={modelSelection} disabled={loading} /> : undefined}
            compact
            showAdvancedTools={!isEmbedded}
            pageContext={pageContext}
            repoPath={repoPath}
            onRepoPathChange={setRepoPath}
            quickExamples={quickExamples}
            onQuickExample={applyQuickExample}
            isCurrentRepoPinned={isCurrentRepoPinned}
            onPinCurrentRepo={pinCurrentRepo}
            onUnpinCurrentRepo={() => unpinRepo(repoPath.trim())}
            processLoading={processLoading}
            onLoadProcesses={() => void loadGitNexusProcesses(repoPath)}
            processSearch={processSearch}
            onProcessSearchChange={setProcessSearch}
            selectedProcess={selectedProcess}
            filteredProcesses={filteredProcesses}
            onSelectedProcessChange={setSelectedProcess}
            onViewSelectedProcess={() => void viewSelectedProcess()}
            loading={loading}
            query={query}
            activeQuestion={activeConversationTurn?.question}
            composerHint={composerAssistHint}
            onQueryChange={updateComposerQuery}
            onClearQuery={clearComposerQueryFromButton}
            onSubmit={handleSubmit}
            onQueueSubmit={isEmbedded ? undefined : queueCurrentQuery}
            onStop={stopActiveAgentTurn}
            inputRef={composerInputRef}
          />
        </div>
      ) : null}

      {!isEmbedded ? (
        <AgentRepoMemoryPanel
          pinnedRepoPaths={pinnedRepoPaths}
          recentUnpinnedRepoPaths={recentUnpinnedRepoPaths}
          onApplyRecentRepoPath={applyRecentRepoPath}
          onMovePinnedRepoPath={movePinnedRepoPath}
          onUnpinRepo={unpinRepo}
          onPinRepoPath={pinRememberedRepo}
        />
      ) : null}
    </section>
  );
}

export default function AgentWorkbenchPage({ pageContext }: AgentWorkbenchPageProps = {}) {
  return <EmbeddedAgentCopilot pageContext={pageContext} showHeader variant="workbench" />;
}
