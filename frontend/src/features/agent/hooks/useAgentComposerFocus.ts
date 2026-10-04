import { useCallback, useEffect, useRef, useState } from "react";

import { getAgentScrollBehavior } from "../lib/agentMotion";
import {
  AGENT_STICKY_BOTTOM_THRESHOLD_PX,
  shouldScrollComposerInputIntoView,
} from "../lib/agentWorkbenchModel";
import type {
  AgentConversationTurn,
  AgentCopyFeedback,
} from "../lib/agentWorkbenchModel";

/** 复制成功/失败提示的停留时长；到期后回到 idle。 */
const AGENT_COPY_FEEDBACK_TIMEOUT_MS = 1800;

type UseAgentComposerFocusOptions = {
  isWorkbench: boolean;
  hasConversation: boolean;
  loading: boolean;
  latestConversationTurn: AgentConversationTurn | null;
  streamingAnswerText: string;
  setComposerAssistHint: (hint: string | null) => void;
};

/**
 * 输入框焦点、对话滚动粘底与复制反馈。
 *
 * 只负责"看哪里 / 焦点在哪 / 复制结果如何"，不参与任何 run 生命周期或结果提交；
 * 需要改文案时通过 `setComposerAssistHint` 回调交回页面。
 */
export function useAgentComposerFocus({
  isWorkbench,
  hasConversation,
  loading,
  latestConversationTurn,
  streamingAnswerText,
  setComposerAssistHint,
}: UseAgentComposerFocusOptions) {
  const conversationRef = useRef<HTMLElement | null>(null);
  const conversationBottomRef = useRef<HTMLDivElement | null>(null);
  const composerDockRef = useRef<HTMLDivElement | null>(null);
  const composerInputRef = useRef<HTMLTextAreaElement | null>(null);
  const shouldStickConversationToBottomRef = useRef(true);
  const shouldFocusComposerRef = useRef(false);
  const copyFeedbackTimerRef = useRef<number | null>(null);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState<AgentCopyFeedback | null>(null);

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

  const scrollConversationToBottom = useCallback(() => {
    const conversation = conversationRef.current;
    if (isWorkbench && conversation && conversation.clientHeight > 0 && conversation.scrollHeight > conversation.clientHeight) {
      conversation.scrollTo({ top: conversation.scrollHeight, behavior: "instant" });
      return;
    }
    const bottom = conversationBottomRef.current;
    const scrollIntoView = bottom?.scrollIntoView;
    if (typeof scrollIntoView === "function") {
      scrollIntoView.call(bottom, { behavior: getAgentScrollBehavior(), block: "end" });
    }
  }, [isWorkbench]);

  const syncConversationStickiness = useCallback(() => {
    const conversation = conversationRef.current;
    if (isWorkbench && conversation && conversation.clientHeight > 0 && conversation.scrollHeight > conversation.clientHeight) {
      const atBottom = conversation.scrollHeight - conversation.scrollTop - conversation.clientHeight
        <= AGENT_STICKY_BOTTOM_THRESHOLD_PX;
      shouldStickConversationToBottomRef.current = atBottom;
      setShowJumpToLatest(!atBottom);
      return;
    }
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
    setShowJumpToLatest(!shouldStickConversationToBottomRef.current);
  }, [isWorkbench]);

  useEffect(() => {
    if (!hasConversation) {
      setShowJumpToLatest(false);
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
    streamingAnswerText,
    scrollConversationToBottom,
  ]);

  useEffect(() => {
    if (!conversationRef.current) {
      shouldStickConversationToBottomRef.current = true;
      return;
    }
    document.addEventListener("scroll", syncConversationStickiness, { capture: true, passive: true });
    return () => document.removeEventListener("scroll", syncConversationStickiness, true);
  }, [hasConversation, syncConversationStickiness]);

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
    };
  }, []);

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
    }, AGENT_COPY_FEEDBACK_TIMEOUT_MS);
  }

  return {
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
  };
}
