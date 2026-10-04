import { useRef } from "react";

import { AgentApiError, AgentDisabledError } from "../../../api/agentClient";
import type { ApiClient } from "../../../api/client";
import type { AgentQueryRequest } from "../../../api/contracts";
import {
  AgentDisabledQueryError,
  getAgentApiErrorPayload,
  getAgentApiErrorStatus,
  getSuggestedActionConfirmationErrorMessage,
  isAgentQueryResult,
  isAgentRunPayload,
  normalizeAgentResult,
  normalizeAgentRunPayload,
} from "../lib/agentWorkbenchModel";
import type { AgentQueryResult, AgentRunPayload } from "../lib/agentWorkbenchModel";
import type { AgentTurnGate } from "./agentTurnGate";

/**
 * 托管 run 的 API 适配层与"当前可取消 run"的归属。
 *
 * 这里只负责把 `apiClient` 的原始响应收敛成工作台需要的形状（校验 + 归一化 + 错误信息本地化），
 * 以及记录"哪个 run 还能被停止按钮取消"。回合状态如何写回页面由调用方决定，
 * 这样这层不需要反向注入十几个 setter。
 */
export function useManagedAgentRun(apiClient: ApiClient) {
  const activeManagedRunIdRef = useRef("");

  /** 后端取消是尽力而为：失败不影响前端已经作废的回合。 */
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
      if (requestError instanceof AgentApiError) {
        throw new AgentApiError(`智能体任务状态获取失败（${requestError.status}）`, {
          status: requestError.status,
          path: requestError.path,
          payload: requestError.payload,
        });
      }
      throw requestError;
    }
    if (!isAgentRunPayload(payload)) {
      throw new Error("智能体返回结果格式无效。");
    }
    return normalizeAgentRunPayload(payload);
  }

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

  async function queryAgentResult(
    requestBody: AgentQueryRequest,
    turnGate?: AgentTurnGate,
  ): Promise<AgentQueryResult> {
    try {
      const payload = await apiClient.queryAgent(
        requestBody,
        turnGate ? { signal: turnGate.signal } : undefined,
      );
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

  /** 记录本回合刚建立、且尚未被停止的托管 run。 */
  function trackActiveManagedRun(runId: string) {
    activeManagedRunIdRef.current = runId;
  }

  function clearActiveManagedRun() {
    activeManagedRunIdRef.current = "";
  }

  /** 停止按钮取走当前可取消的 run，同时清空登记，避免重复取消。 */
  function takeActiveManagedRunId() {
    const runId = activeManagedRunIdRef.current;
    activeManagedRunIdRef.current = "";
    return runId;
  }

  /** 回合结束时只释放自己登记的那个 run，不动后来者登记的 run。 */
  function releaseActiveManagedRun(runId: string) {
    if (runId && activeManagedRunIdRef.current === runId) {
      activeManagedRunIdRef.current = "";
    }
  }

  return {
    requestBackendRunCancel,
    fetchAgentRunStatus,
    createAgentRun,
    queryAgentResult,
    trackActiveManagedRun,
    clearActiveManagedRun,
    takeActiveManagedRunId,
    releaseActiveManagedRun,
  };
}
