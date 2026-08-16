import { useCallback, useDeferredValue, useEffect, useRef, useState, type FormEvent } from "react";

import { EditOutlined, PlusOutlined } from "@ant-design/icons";
import { AgentDisabledError } from "../../api/agentClient";
import { useApiClient } from "../../api/client";
import type {
  AgentConversationContext,
  AgentPageContext,
  AgentQueryRequest,
  AgentSuggestedAction,
} from "../../api/contracts";
import { AgentQueryForm } from "./components/AgentQueryForm";
import { AgentQueuedDraft } from "./components/AgentQueuedDraft";
import { AgentRepoMemoryPanel } from "./components/AgentRepoMemoryPanel";
import { AgentRunProgress } from "./components/AgentRunProgress";
import { AgentRuntimeStrip } from "./components/AgentRuntimeStrip";
import { AgentShortcutDrawer } from "./components/AgentShortcutDrawer";
import { AgentTurnErrorCallout } from "./components/AgentTurnErrorCallout";
import { AgentTurnResultView } from "./components/AgentTurnResultView";
import { isAbortError } from "./hooks/agentRunStatusOrchestrator";
import { runManagedAgentPolling } from "./hooks/runManagedAgentPolling";

import "./AgentWorkbenchPage.css";

import {
  AGENT_STICKY_BOTTOM_THRESHOLD_PX,
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
  getAgentApiErrorPayload,
  getAgentApiErrorStatus,
  getExecutableSuggestedIntent,
  getLocalAgentQueryIntent,
  getSuggestedActionConfirmationErrorMessage,
  getSuggestedActionKey,
  isAgentQueryResult,
  isAgentRunPayload,
  isCompactProviderChatTurn,
  isLocalOpenChatQuestion,
  normalizeAgentResult,
  normalizeAgentRunPayload,
  shouldDisplayAgentRunId,
  shouldScrollComposerInputIntoView,
  shouldUseLocalAnalysisConversation,
} from "./lib/agentWorkbenchModel";
import { getAgentScrollBehavior } from "./lib/agentMotion";
import type {
  AgentConversationTurn,
  AgentCopyFeedback,
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
import { useAgentRunRestore } from "./hooks/useAgentRunRestore";
import { useConversationPersistence } from "./hooks/useConversationPersistence";

export function EmbeddedAgentCopilot({
  pageContext,
  variant = "workbench",
  showHeader,
  readOnly = false,
  defaultQuestion = "",
}: EmbeddedAgentCopilotProps = {}) {
  const apiClient = useApiClient();
  const isEmbedded = variant === "embedded";
  const shouldPersistConversation = variant === "workbench";
  const resolvedShowHeader = showHeader ?? !isEmbedded;
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
  const [repoPath, setRepoPath] = useState(() => recentRepoPaths[0] ?? "");
  const [availableProcesses, setAvailableProcesses] = useState<string[]>([]);
  const [processSearch, setProcessSearch] = useState("");
  const [selectedProcess, setSelectedProcess] = useState("");
  const [loading, setLoading] = useState(false);
  const [agentWaitSeconds, setAgentWaitSeconds] = useState(0);
  const [processLoading, setProcessLoading] = useState(false);
  const [result, setResult] = useState<AgentQueryResult | null>(null);
  const [agentRun, setAgentRun] = useState<AgentRunPayload | null>(null);
  const [error, setError] = useState<AgentQueryError | null>(null);
  const [restoringRunId, setRestoringRunId] = useState(initialRestoringRunId);
  const [restoreErrorRunId, setRestoreErrorRunId] = useState("");
  const [pageContextChangeNotice, setPageContextChangeNotice] = useState(false);
  const [composerAssistHint, setComposerAssistHint] = useState<string | null>(null);
  const [pendingSuggestedActionConfirmation, setPendingSuggestedActionConfirmation] =
    useState<PendingSuggestedActionConfirmation | null>(null);
  const repoPathRef = useRef(repoPath);
  const conversationRef = useRef<HTMLElement | null>(null);
  const conversationBottomRef = useRef<HTMLDivElement | null>(null);
  const composerDockRef = useRef<HTMLDivElement | null>(null);
  const composerInputRef = useRef<HTMLTextAreaElement | null>(null);
  const pageContextSummaryRef = useRef(pageContext ? formatPageContextSummary(pageContext) : "");
  const lastAppliedDefaultQuestionRef = useRef(defaultQuestion.trim());
  const shouldFocusRestoredDraftRef = useRef(
    shouldPersistConversation && !defaultQuestion.trim() && query.trim().length > 0,
  );
  const shouldFocusComposerRef = useRef(false);
  const processStateRequestVersionRef = useRef(0);
  const conversationSessionRef = useRef(0);
  const copyFeedbackTimerRef = useRef<number | null>(null);
  const shouldStickConversationToBottomRef = useRef(true);
  const stopActiveAgentTurnRef = useRef<() => void>(() => undefined);
  const submitQueuedQueryRef = useRef<(question: string) => Promise<void>>(async () => undefined);
  const activeManagedRunAbortRef = useRef<AbortController | null>(null);
  const activeManagedRunIdRef = useRef("");
  const [copyFeedback, setCopyFeedback] = useState<AgentCopyFeedback | null>(null);
  const deferredProcessSearch = useDeferredValue(processSearch);
  const filteredProcesses = availableProcesses.filter((processName) =>
    processName.toLowerCase().includes(deferredProcessSearch.trim().toLowerCase()),
  );
  const recentUnpinnedRepoPaths = recentRepoPaths.filter((path) => !pinnedRepoPaths.includes(path));
  const isCurrentRepoPinned = pinnedRepoPaths.includes(repoPath.trim());
  const latestConversationTurn = conversationTurns[conversationTurns.length - 1] ?? null;
  const latestResultTurn = findLatestTurnWithResult(conversationTurns);
  const latestRunTurn = findLatestTurnWithRun(conversationTurns);
  const runtimeResult = loading ? null : latestResultTurn?.result ?? result;
  const runtimeRun = (
    loading
      ? latestConversationTurn?.agentRun ?? agentRun ?? latestRunTurn?.agentRun
      : latestRunTurn?.agentRun ?? agentRun
  ) ?? null;
  const runtimeStatus = buildRuntimeStatus(
    runtimeResult,
    loading,
    runtimeRun,
  );
  const hasConversation = conversationTurns.length > 0 || Boolean(result || error);
  repoPathRef.current = repoPath;

  function beginProcessStateRequest() {
    processStateRequestVersionRef.current += 1;
    return processStateRequestVersionRef.current;
  }

  function currentConversationSession() {
    return conversationSessionRef.current;
  }

  function isCurrentConversationSession(session: number) {
    return conversationSessionRef.current === session;
  }

  function resetConversationSession() {
    conversationSessionRef.current += 1;
  }

  function invalidateActiveRequest() {
    processStateRequestVersionRef.current += 1;
  }

  function canCommitProcessState(requestVersion: number, requestRepoPath: string) {
    return (
      processStateRequestVersionRef.current === requestVersion &&
      requestRepoPath === repoPathRef.current.trim()
    );
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

  const closeResultInteractionDetails = useCallback((sourceElement?: HTMLElement) => {
    const detailsRoot = sourceElement?.closest(".agent-result-shell") ?? conversationRef.current;
    detailsRoot
      ?.querySelectorAll<HTMLDetailsElement>(
        [
          ".agent-follow-up-chips__details",
          ".agent-suggested-actions__more",
          ".agent-suggested-actions__details",
          ".agent-side-panel__details",
          ".agent-result-side-drawer",
        ].join(", "),
      )
      .forEach((details) => {
        details.open = false;
      });
  }, []);

  const closeResultInteractionDetailsExceptSuggestedActionMore = useCallback((sourceElement?: HTMLElement) => {
    const detailsRoot = sourceElement?.closest(".agent-result-shell") ?? conversationRef.current;
    detailsRoot
      ?.querySelectorAll<HTMLDetailsElement>(
        [
          ".agent-follow-up-chips__details",
          ".agent-suggested-actions__details",
          ".agent-side-panel__details",
          ".agent-result-side-drawer",
        ].join(", "),
      )
      .forEach((details) => {
        details.open = false;
      });
  }, []);

  const moveComposerCursorToEnd = useCallback((input: HTMLTextAreaElement) => {
    const cursorPosition = input.value.length;
    input.setSelectionRange(cursorPosition, cursorPosition);
  }, []);

  const focusComposerInput = useCallback(() => {
    closeResultInteractionDetails();
    const input = composerInputRef.current;
    if (!input) {
      return;
    }
    input.focus();
    moveComposerCursorToEnd(input);
    window.requestAnimationFrame(() => {
      if (composerInputRef.current === input && document.activeElement === input) {
        moveComposerCursorToEnd(input);
      }
    });
    const scrollIntoView = input.scrollIntoView;
    if (typeof scrollIntoView === "function" && shouldScrollComposerInputIntoView(input)) {
      scrollIntoView.call(input, { behavior: getAgentScrollBehavior(), block: "nearest" });
    }
  }, [closeResultInteractionDetails, moveComposerCursorToEnd]);

  function scrollConversationToBottom() {
    const bottom = conversationBottomRef.current;
    const scrollIntoView = bottom?.scrollIntoView;
    if (typeof scrollIntoView === "function") {
      scrollIntoView.call(bottom, { behavior: getAgentScrollBehavior(), block: "end" });
    }
  }

  function syncConversationStickiness() {
    const conversationBottom = conversationBottomRef.current;
    if (!conversationBottom) {
      shouldStickConversationToBottomRef.current = true;
      return;
    }

    const visualViewport = window.visualViewport;
    const viewportTop = visualViewport?.offsetTop ?? 0;
    const viewportHeight =
      visualViewport?.height ?? window.innerHeight ?? document.documentElement.clientHeight;
    const viewportBottom = viewportTop + viewportHeight;
    const composerRect = composerDockRef.current?.getBoundingClientRect();
    const composerIsVisible = Boolean(
      composerRect && composerRect.bottom > viewportTop && composerRect.top < viewportBottom,
    );
    const readableBottom = composerIsVisible
      ? Math.max(viewportTop, composerRect?.top ?? viewportBottom)
      : viewportBottom;
    const distanceFromBottom = conversationBottom.getBoundingClientRect().bottom - readableBottom;
    shouldStickConversationToBottomRef.current =
      Math.abs(distanceFromBottom) <= AGENT_STICKY_BOTTOM_THRESHOLD_PX;
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
    if (!filteredProcesses.length) {
      setSelectedProcess("");
      return;
    }
    if (!selectedProcess || !filteredProcesses.includes(selectedProcess)) {
      setSelectedProcess(filteredProcesses[0] ?? "");
    }
  }, [filteredProcesses, selectedProcess]);

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
    if (!hasConversation) {
      return;
    }
    if (!shouldStickConversationToBottomRef.current) {
      return;
    }
    scrollConversationToBottom();
  }, [
    hasConversation,
    latestConversationTurn?.id,
    latestConversationTurn?.agentRun?.status,
    latestConversationTurn?.result,
    latestConversationTurn?.error,
  ]);

  useEffect(() => {
    if (!conversationRef.current) {
      shouldStickConversationToBottomRef.current = true;
      return;
    }
    document.addEventListener("scroll", syncConversationStickiness, { capture: true, passive: true });
    return () => document.removeEventListener("scroll", syncConversationStickiness, true);
  }, [hasConversation]);

  useEffect(() => {
    if (!shouldFocusComposerRef.current) {
      return;
    }
    shouldFocusComposerRef.current = false;
    focusComposerInput();
  }, [
    focusComposerInput,
    hasConversation,
    loading,
    latestConversationTurn?.id,
    latestConversationTurn?.result,
    latestConversationTurn?.error,
  ]);

  useEffect(() => {
    return () => {
      if (copyFeedbackTimerRef.current !== null) {
        window.clearTimeout(copyFeedbackTimerRef.current);
      }
      // 卸载时只中止前端等待（SSE/轮询），不取消后端 run：刷新或路由切换后仍可恢复。
      activeManagedRunAbortRef.current?.abort();
    };
  }, []);

  function requestBackendRunCancel(runId: string) {
    if (!runId.trim()) {
      return;
    }
    void apiClient.cancelAgentRun(runId).catch(() => undefined);
  }

  async function fetchAgentRunStatus(runId: string): Promise<AgentRunPayload> {
    let payload: unknown;
    try {
      payload = await apiClient.getAgentRun(runId);
    } catch (requestError) {
      const status = getAgentApiErrorStatus(requestError);
      if (status !== null) {
        throw new Error(`智能体任务状态获取失败（${status}）`);
      }
      throw requestError;
    }
    if (!isAgentRunPayload(payload)) {
      throw new Error("智能体返回结果格式无效。");
    }
    return normalizeAgentRunPayload(payload);
  }

  useAgentRunRestore({
    shouldPersistConversation,
    currentConversationSession,
    isCurrentConversationSession,
    fetchAgentRunStatus,
    setRestoringRunId,
    setRestoreErrorRunId,
    setOrdinaryConversationMode,
    setAgentRun,
    setConversationTurns,
    setResult,
    setError,
  });

  async function createAgentRun(requestBody: AgentQueryRequest): Promise<AgentRunPayload> {
    let payload: unknown;
    try {
      payload = await apiClient.createAgentRun(requestBody);
    } catch (requestError) {
      if (requestError instanceof AgentDisabledError) {
        throw new AgentDisabledQueryError(requestError.message, requestError.phase);
      }
      const status = getAgentApiErrorStatus(requestError);
      if (status !== null) {
        throw new Error(`智能体查询失败（${status}）`);
      }
      throw requestError;
    }

    // 后端 POST /api/agent/runs 已收窄为仅返回排队回执（不再同步短路返回 AgentEnvelope）；
    // demo 桩返回的终态 run payload（含 result）同样满足该守卫。
    if (!isAgentRunPayload(payload)) {
      throw new Error("智能体返回结果格式无效。");
    }

    return normalizeAgentRunPayload(payload);
  }
  async function queryAgentResult(requestBody: AgentQueryRequest): Promise<AgentQueryResult> {
    try {
      const payload = await apiClient.queryAgent(requestBody);
      if (!isAgentQueryResult(payload)) {
        throw new Error("智能体返回结果格式无效。");
      }
      return normalizeAgentResult(payload);
    } catch (requestError) {
      if (requestError instanceof AgentDisabledError) {
        throw new AgentDisabledQueryError(requestError.message, requestError.phase);
      }
      const status = getAgentApiErrorStatus(requestError);
      const confirmationErrorMessage = getSuggestedActionConfirmationErrorMessage(
        status,
        getAgentApiErrorPayload(requestError),
      );
      if (confirmationErrorMessage) {
        throw new Error(confirmationErrorMessage);
      }
      if (status !== null) {
        throw new Error(`智能体查询失败（${status}）`);
      }
      throw requestError;
    }
  }
  async function executeManagedAgentRun(
    question: string,
    turnId: string,
    conversationContext?: AgentConversationContext,
  ) {
    const normalizedRepoPath = repoPath.trim();
    const requestVersion = beginProcessStateRequest();
    const requestBody = buildAgentRequestBody(
      question,
      normalizedRepoPath,
      selectedProcess,
      conversationContext,
      pageContext,
    );
    const abortController = new AbortController();
    // 回合提交门与 GitNexus 进程列表提交门解耦：run 进行中编辑仓库路径、点最近仓库、
    // 点"读取流程"只会使进程列表请求失效，不能丢弃本回合的终态结果/错误提交。
    // 回合提交只看停止信号（abort）与会话版本（新对话/新提问会重置会话）。
    const conversationSession = currentConversationSession();
    const canCommitTurnState = () =>
      !abortController.signal.aborted && isCurrentConversationSession(conversationSession);
    activeManagedRunAbortRef.current = abortController;
    activeManagedRunIdRef.current = "";
    setAgentRun(null);
    setResult(null);
    try {
      const finalPayload = await runManagedAgentPolling({
        requestBody,
        createAgentRun: async (body: AgentQueryRequest) => {
          const payload = await createAgentRun(body);
          if (payload.run_kind !== "sync") {
            if (abortController.signal.aborted) {
              // 用户在 run 建立前就点了停止：拿到 run_id 后立即请求后端取消。
              requestBackendRunCancel(payload.run_id);
            } else {
              activeManagedRunIdRef.current = payload.run_id;
            }
          }
          return payload;
        },
        fetchAgentRunStatus,
        canCommit: canCommitTurnState,
        signal: abortController.signal,
        onRunAccepted: (payload, runRequestLatencyMs) => {
          setOrdinaryConversationMode("managed");
          setAgentRun(payload);
          // 持久化交给 useConversationPersistence 的 write-through effect；
          // 不在 state 更新器内执行副作用（StrictMode/并发渲染下更新器可能重放）。
          setConversationTurns((currentTurns) =>
            currentTurns.map((turn) =>
              turn.id === turnId ? { ...turn, agentRun: payload, runRequestLatencyMs } : turn,
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
      if (activeManagedRunAbortRef.current === abortController) {
        activeManagedRunAbortRef.current = null;
        activeManagedRunIdRef.current = "";
      }
    }
  }

  async function executeAgentQuery(
    question: string,
    mode: "query" | "processes" = "query",
    turnId?: string,
    conversationContext?: AgentConversationContext,
    contextPatch?: Record<string, unknown>,
  ) {
    const normalizedRepoPath = repoPath.trim();
    const requestVersion = beginProcessStateRequest();
    try {
      const requestBody = buildAgentRequestBody(
        question,
        normalizedRepoPath,
        selectedProcess,
        conversationContext,
        pageContext,
        contextPatch,
      );

      const payload = await queryAgentResult(requestBody);

      const nextProcesses = extractProcessNames(payload.cards);
      if (nextProcesses.length > 0 && canCommitProcessState(requestVersion, normalizedRepoPath)) {
        setAvailableProcesses(nextProcesses);
        setSelectedProcess((current) => (current && nextProcesses.includes(current) ? current : nextProcesses[0] ?? ""));
      } else if (mode === "processes" && canCommitProcessState(requestVersion, normalizedRepoPath)) {
        setAvailableProcesses([]);
        setSelectedProcess("");
      }

      if (normalizedRepoPath.length > 0 && canCommitProcessState(requestVersion, normalizedRepoPath)) {
        rememberRepoPath(normalizedRepoPath);
      }
      if (canCommitProcessState(requestVersion, normalizedRepoPath)) {
        setResult(payload);
      }
      return payload;
    } catch (requestError) {
      if (requestError instanceof AgentDisabledQueryError) {
        if (!canCommitProcessState(requestVersion, normalizedRepoPath)) {
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
      if (canCommitProcessState(requestVersion, normalizedRepoPath)) {
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

    const payload = await executeAgentQuery(question, "query", turnId, conversationContext, contextPatch);
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

    setAgentWaitSeconds(0);
    setConversationTurns((currentTurns) => [...currentTurns, turn]);
    shouldFocusComposerRef.current = true;
    setLoading(true);
    setError(null);

    try {
      await executeLocalSyncConversation(actionLabel, turn.id, context, {
        intent,
        suggested_action: action,
        suggested_action_requires_confirmation: action.requires_confirmation,
        ...(action.confirmation_token
          ? { suggested_action_confirmation_token: action.confirmation_token }
          : {}),
      });
    } finally {
      setLoading(false);
    }
  }

  async function executeOrdinaryConversation(
    question: string,
    turnId: string,
    conversationContext?: AgentConversationContext,
  ) {
    if (isLocalOpenChatQuestion(question)) {
      await executeLocalSyncConversation(question, turnId, conversationContext);
      return;
    }
    const localQueryIntent = getLocalAgentQueryIntent(question);
    if (localQueryIntent) {
      await executeLocalSyncConversation(question, turnId, conversationContext, {
        intent: localQueryIntent,
      });
      return;
    }
    if (shouldUseLocalAnalysisConversation(question, conversationContext)) {
      await executeLocalSyncConversation(question, turnId, conversationContext);
      return;
    }
    if (ordinaryConversationMode === "local_sync") {
      await executeLocalSyncConversation(question, turnId, conversationContext);
      return;
    }
    if (ordinaryConversationMode === "managed") {
      await executeManagedAgentRun(question, turnId, conversationContext);
      return;
    }

    await executeManagedAgentRun(question, turnId, conversationContext);
  }

  function canRetryAgentTurn(turn: AgentConversationTurn) {
    return turn.retryMode === "ordinary" && turn.question.trim().length > 0 && Boolean(turn.error);
  }

  function canRegenerateAgentTurn(turn: AgentConversationTurn) {
    return turn.retryMode === "ordinary" && turn.question.trim().length > 0 && Boolean(turn.result);
  }

  async function rerunOrdinaryTurn(turn: AgentConversationTurn, rerunComposerHint = "正在重新发送 · 可继续输入下一句") {
    if (loading) {
      return;
    }

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
      agentRun: null,
      result: null,
      error: null,
      stopped: false,
      activeSuggestedActionPayload: null,
    }));

    try {
      await executeOrdinaryConversation(turn.question, turn.id, turn.conversationContext);
    } finally {
      setComposerAssistHint((currentHint) => (currentHint === rerunComposerHint ? null : currentHint));
      shouldFocusComposerRef.current = true;
      window.setTimeout(focusComposerInput, 0);
      setLoading(false);
    }
  }

  async function retryAgentTurn(turn: AgentConversationTurn) {
    if (!canRetryAgentTurn(turn)) {
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
    if (!loading || !latestConversationTurn) {
      return;
    }

    const activeAbortController = activeManagedRunAbortRef.current;
    const activeManagedRunId = activeManagedRunIdRef.current;
    activeManagedRunAbortRef.current = null;
    activeManagedRunIdRef.current = "";
    activeAbortController?.abort();
    if (activeManagedRunId) {
      requestBackendRunCancel(activeManagedRunId);
    }

    invalidateActiveRequest();
    setLoading(false);
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
      updateComposerQuery(latestConversationTurn.question);
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
    updateConversationTurn(latestConversationTurn.id, (turn) => ({
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
      if (event.key !== "Escape" || event.isComposing) {
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
      await executeOrdinaryConversation(question, turn.id, context);
    } finally {
      setLoading(false);
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
    setAgentWaitSeconds(0);
    setPendingSuggestedActionConfirmation(null);
    setConversationTurns((currentTurns) => [...currentTurns, turn]);
    shouldFocusComposerRef.current = true;
    setLoading(true);
    setError(null);
    setComposerAssistHint("正在发送排队问题 · 可继续输入下一句");
    try {
      await executeOrdinaryConversation(question, turn.id, context);
    } finally {
      setComposerAssistHint((currentHint) =>
        currentHint === "正在发送排队问题 · 可继续输入下一句" ? null : currentHint,
      );
      setLoading(false);
      shouldFocusComposerRef.current = true;
      window.setTimeout(focusComposerInput, 0);
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
      const payload = await queryAgentResult(buildFinancialWorkflowRequestBody(workflow, pageContext));

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
      setLoading(false);
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
      const payload = await queryAgentResult(buildResearchRequestBody(shortcut, pageContext));

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
      setLoading(false);
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
      // 无条件复位：读取期间任何提问/新的进程请求都会 bump 版本号，
      // 若仅在版本未变时复位，"读取流程"按钮会永久卡在"读取中..."。
      setProcessLoading(false);
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
      const payload = await executeAgentQuery(question, "query", turn.id);
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
      setComposerAssistHint((currentHint) =>
        currentHint === "正在查看 GitNexus 流程 · 可继续输入" ? null : currentHint,
      );
      setLoading(false);
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
    resetConversationSession();
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

  async function copyAgentAnswer(turn: AgentConversationTurn) {
    const answer = turn.result?.answer.trim();
    const writeText = typeof navigator === "undefined" ? undefined : navigator.clipboard?.writeText;
    if (!answer) {
      return;
    }

    let status: AgentCopyFeedback["status"] = "success";
    if (typeof writeText !== "function") {
      status = "error";
    } else {
      try {
        await writeText.call(navigator.clipboard, answer);
      } catch {
        status = "error";
      }
    }

    setCopyFeedback({ turnId: turn.id, status });
    if (status === "success") {
      setComposerAssistHint("已复制回答 · 可以继续追问");
    } else {
      setComposerAssistHint("复制失败 · 可手动选择回答文本");
    }
    focusComposerInput();
    if (copyFeedbackTimerRef.current !== null) {
      window.clearTimeout(copyFeedbackTimerRef.current);
    }
    copyFeedbackTimerRef.current = window.setTimeout(() => {
      setCopyFeedback((currentFeedback) => (currentFeedback?.turnId === turn.id ? null : currentFeedback));
      copyFeedbackTimerRef.current = null;
    }, 1800);
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
      if (latestConversationTurn?.id !== turn.id) {
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
            <div className="agent-workbench-header__eyebrow">MOSS Chat</div>
            <h1>今天想看什么？</h1>
            <p>先把问题丢给我。需要证据、运行细节或正式口径时，再展开查看。</p>
          </div>
          {hasConversation ? (
            <div className="agent-workbench-header__actions">
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
          ) : null}
        </header>
      ) : null}

      <AgentRuntimeStrip
        loading={loading}
        stateLabel={runtimeStateLabel}
        runtimeStatus={runtimeStatus}
      />

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
            <span>已清除过期运行标记；你可以继续在输入框里发起新的追问。</span>
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

      {!isEmbedded ? (
        <AgentShortcutDrawer
          loading={loading}
          onExecuteWorkflow={(workflow) => void executeFinancialWorkflow(workflow)}
          onExecuteResearchShortcut={(shortcut) => void executeResearchShortcut(shortcut)}
        />
      ) : null}

      {!hasConversation ? (
        <AgentQueryForm
          compact={isEmbedded}
          showAdvancedTools={!isEmbedded}
          pageContext={pageContext}
          repoPath={repoPath}
          onRepoPathChange={setRepoPath}
          quickExamples={GITNEXUS_QUICK_EXAMPLES}
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
          activeQuestion={latestConversationTurn?.question}
          composerHint={composerAssistHint}
          onQueryChange={updateComposerQuery}
          onClearQuery={clearComposerQueryFromButton}
          onSubmit={handleSubmit}
          onQueueSubmit={isEmbedded ? undefined : queueCurrentQuery}
          onStop={stopActiveAgentTurn}
          inputRef={composerInputRef}
        />
      ) : null}

      {hasConversation ? (
        <section className="agent-conversation" aria-label="Agent 对话记录" ref={conversationRef}>
          {conversationTurns.map((turn) => {
            const isLatestLoadingTurn = turn === latestConversationTurn && loading;
            const showThinkingPlaceholder = isLatestLoadingTurn && !turn.result && !turn.error;
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
              <div key={turn.id} className="agent-turn">
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
                          <div className="agent-wait-status__title">{formatAgentTurnWaitTitle(turn.agentRun)}</div>
                          <AgentRunProgress agentRun={turn.agentRun} question={turn.question} />
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
                      onEditQuestion={editAgentQuestion}
                      onRetry={(retryTurn) => void retryAgentTurn(retryTurn)}
                    />
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
          <AgentQueuedDraft
            queuedQueries={queuedQueries}
            onRestoreToComposer={restoreQueuedQueryToComposer}
            onCancel={cancelQueuedQuery}
          />
          <AgentQueryForm
            compact
            showAdvancedTools={!isEmbedded}
            pageContext={pageContext}
            repoPath={repoPath}
            onRepoPathChange={setRepoPath}
            quickExamples={GITNEXUS_QUICK_EXAMPLES}
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
            activeQuestion={latestConversationTurn?.question}
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
