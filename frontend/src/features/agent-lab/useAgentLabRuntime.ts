import {
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import { useCallback, useEffect, useRef, useState } from "react";

import { AgentDisabledError } from "../../api/agentClient";
import { useApiClient } from "../../api/client";
import type { AgentQueryRequest } from "../../api/contracts";
import { isAbortError } from "../agent/hooks/agentRunStatusOrchestrator";
import { runManagedAgentPolling } from "../agent/hooks/runManagedAgentPolling";
import {
  AgentDisabledQueryError,
  AgentRunCancelledError,
  buildAgentRequestBody,
  buildConversationContext,
  buildErrorMessage,
  createAgentConversationTurn,
  getAgentApiErrorStatus,
  isAgentRunPayload,
  normalizeAgentRunPayload,
} from "../agent/lib/agentWorkbenchModel";
import type {
  AgentConversationTurn,
  AgentRunPayload,
} from "../agent/lib/agentWorkbenchModel";

export type AgentLabMessagePhase = "running" | "complete" | "cancelled" | "error";

export type AgentLabMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: Date;
  phase?: AgentLabMessagePhase;
  turn?: AgentConversationTurn;
};

type ActiveLabRun = {
  assistantMessageId: string;
  controller: AbortController;
  runId: string | null;
  cancelled: boolean;
  cancelSent: boolean;
};

function convertLabMessage(message: AgentLabMessage): ThreadMessageLike {
  const status =
    message.role === "assistant"
      ? message.phase === "running"
        ? ({ type: "running" } as const)
        : message.phase === "cancelled"
          ? ({ type: "incomplete", reason: "cancelled" } as const)
          : message.phase === "error"
            ? ({ type: "incomplete", reason: "error", error: message.text } as const)
            : ({ type: "complete", reason: "stop" } as const)
      : undefined;

  return {
    id: message.id,
    role: message.role,
    content: [{ type: "text", text: message.text }],
    createdAt: message.createdAt,
    ...(status ? { status } : {}),
  };
}

function getQuestion(message: AppendMessage) {
  if (message.role !== "user") {
    return "";
  }
  return message.content
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("\n")
    .trim();
}

export function useAgentLabRuntime() {
  const apiClient = useApiClient();
  const [messages, setMessages] = useState<AgentLabMessage[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const activeRunRef = useRef<ActiveLabRun | null>(null);
  const mountedRef = useRef(true);
  const messageSequenceRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      // 与正式页一致：离开页面只停止前端等待，不擅自取消后台任务。
      activeRunRef.current?.controller.abort();
    };
  }, []);

  const nextMessageId = useCallback((role: AgentLabMessage["role"]) => {
    messageSequenceRef.current += 1;
    return `agent-lab:${role}:${Date.now()}:${messageSequenceRef.current}`;
  }, []);

  const updateAssistantMessage = useCallback(
    (messageId: string, update: (message: AgentLabMessage) => AgentLabMessage) => {
      if (!mountedRef.current) {
        return;
      }
      setMessages((currentMessages) =>
        currentMessages.map((message) => (message.id === messageId ? update(message) : message)),
      );
    },
    [],
  );

  const cancelBackendRun = useCallback(
    (activeRun: ActiveLabRun) => {
      if (!activeRun.runId || activeRun.cancelSent) {
        return;
      }
      activeRun.cancelSent = true;
      void apiClient.cancelAgentRun(activeRun.runId).catch(() => undefined);
    },
    [apiClient],
  );

  const createAgentRun = useCallback(
    async (requestBody: AgentQueryRequest): Promise<AgentRunPayload> => {
      let payload: unknown;
      try {
        payload = await apiClient.createAgentRun(requestBody);
      } catch (error) {
        if (error instanceof AgentDisabledError) {
          throw new AgentDisabledQueryError(error.message, error.phase);
        }
        const status = getAgentApiErrorStatus(error);
        if (status !== null) {
          throw new Error(`智能体查询失败（${status}）`);
        }
        throw error;
      }
      if (!isAgentRunPayload(payload)) {
        throw new Error("智能体返回结果格式无效。");
      }
      return normalizeAgentRunPayload(payload);
    },
    [apiClient],
  );

  const fetchAgentRunStatus = useCallback(
    async (runId: string): Promise<AgentRunPayload> => {
      let payload: unknown;
      try {
        payload = await apiClient.getAgentRun(runId);
      } catch (error) {
        const status = getAgentApiErrorStatus(error);
        if (status !== null) {
          throw new Error(`智能体任务状态获取失败（${status}）`);
        }
        throw error;
      }
      if (!isAgentRunPayload(payload)) {
        throw new Error("智能体返回结果格式无效。");
      }
      return normalizeAgentRunPayload(payload);
    },
    [apiClient],
  );

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const question = getQuestion(message);
      if (!question || activeRunRef.current?.cancelled === false) {
        return;
      }

      const conversationTurns = messages.flatMap((item) => (item.turn ? [item.turn] : []));
      const conversationContext = buildConversationContext(conversationTurns);
      const assistantMessageId = nextMessageId("assistant");
      const turn = {
        ...createAgentConversationTurn(question, conversationContext),
        id: assistantMessageId,
      };
      const activeRun: ActiveLabRun = {
        assistantMessageId,
        controller: new AbortController(),
        runId: null,
        cancelled: false,
        cancelSent: false,
      };
      activeRunRef.current = activeRun;
      setIsRunning(true);
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: nextMessageId("user"),
          role: "user",
          text: question,
          createdAt: new Date(),
        },
        {
          id: assistantMessageId,
          role: "assistant",
          text: "正在连接 MOSS Agent…",
          createdAt: new Date(),
          phase: "running",
          turn,
        },
      ]);

      try {
        const finalPayload = await runManagedAgentPolling({
          requestBody: buildAgentRequestBody(
            question,
            "",
            "",
            conversationContext,
            undefined,
            { agent_ui_experiment: "assistant-ui-external-store" },
          ),
          createAgentRun,
          fetchAgentRunStatus,
          canCommit: () => mountedRef.current,
          onRunAccepted: (payload) => {
            activeRun.runId = payload.run_id;
            if (activeRun.cancelled) {
              cancelBackendRun(activeRun);
              return;
            }
            if (activeRunRef.current !== activeRun) {
              return;
            }
            updateAssistantMessage(assistantMessageId, (current) => ({
              ...current,
              text: "任务已接收，正在整理回答…",
              turn: current.turn ? { ...current.turn, agentRun: payload } : current.turn,
            }));
          },
          onRunUpdate: (payload) => {
            if (activeRun.cancelled || activeRunRef.current !== activeRun) {
              return;
            }
            updateAssistantMessage(assistantMessageId, (current) => ({
              ...current,
              text: "任务运行中，正在整理回答…",
              turn: current.turn ? { ...current.turn, agentRun: payload } : current.turn,
            }));
          },
          signal: activeRun.controller.signal,
        });

        if (
          activeRun.cancelled ||
          activeRunRef.current !== activeRun ||
          !mountedRef.current
        ) {
          return;
        }
        updateAssistantMessage(assistantMessageId, (current) => ({
          ...current,
          text: finalPayload.result.answer,
          phase: "complete",
          turn: current.turn
            ? {
                ...current.turn,
                agentRun: finalPayload,
                result: finalPayload.result,
              }
            : current.turn,
        }));
      } catch (error) {
        if (!mountedRef.current || activeRunRef.current !== activeRun) {
          return;
        }
        if (activeRun.cancelled || isAbortError(error)) {
          return;
        }
        if (error instanceof AgentRunCancelledError) {
          updateAssistantMessage(assistantMessageId, (current) => ({
            ...current,
            text: "任务已由运行端取消。",
            phase: "cancelled",
            turn: current.turn
              ? { ...current.turn, stopped: true, agentRun: error.payload }
              : current.turn,
          }));
          return;
        }
        const errorMessage = buildErrorMessage(error);
        updateAssistantMessage(assistantMessageId, (current) => ({
          ...current,
          text: errorMessage,
          phase: "error",
          turn: current.turn
            ? {
                ...current.turn,
                error:
                  error instanceof AgentDisabledQueryError
                    ? { kind: "disabled", detail: error.detail, phase: error.phase }
                    : { kind: "request", message: errorMessage },
              }
            : current.turn,
        }));
      } finally {
        if (mountedRef.current && activeRunRef.current === activeRun) {
          activeRunRef.current = null;
          setIsRunning(false);
        }
      }
    },
    [
      cancelBackendRun,
      createAgentRun,
      fetchAgentRunStatus,
      messages,
      nextMessageId,
      updateAssistantMessage,
    ],
  );

  const onCancel = useCallback(async () => {
    const activeRun = activeRunRef.current;
    if (!activeRun || activeRun.cancelled) {
      return;
    }
    activeRun.cancelled = true;
    activeRun.controller.abort();
    setIsRunning(false);
    updateAssistantMessage(activeRun.assistantMessageId, (current) => ({
      ...current,
      text: "已停止，本轮不会写入正式对话。",
      phase: "cancelled",
      turn: current.turn ? { ...current.turn, stopped: true } : current.turn,
    }));
    cancelBackendRun(activeRun);
  }, [cancelBackendRun, updateAssistantMessage]);

  const runtime = useExternalStoreRuntime<AgentLabMessage>({
    messages,
    isRunning,
    convertMessage: convertLabMessage,
    onNew,
    onCancel,
  });

  const clearMessages = useCallback(() => {
    if (!isRunning) {
      setMessages([]);
    }
  }, [isRunning]);

  return {
    runtime,
    messages,
    isRunning,
    clearMessages,
  };
}
