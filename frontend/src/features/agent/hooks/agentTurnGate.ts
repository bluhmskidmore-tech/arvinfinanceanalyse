import { useCallback, useRef } from "react";

/**
 * 单个 Agent 回合的提交门。
 *
 * 只有"最新回合"才允许改 `loading`、写入结果或错误：停止等待、发新问题、开新对话
 * 都会让旧回合失效，旧回合迟到的 `finally` 不得把新回合的进行中状态改回完成态。
 * `signal` 同时承载本地同步查询 / Workflow / Research 三条同步路径的中止。
 */
export type AgentTurnGate = {
  version: number;
  controller: AbortController;
  signal: AbortSignal;
  isCurrent: () => boolean;
};

export type AgentTurnGateController = {
  /** 开启新回合：旧回合立即失效（不中止旧请求，由调用方决定是否中止）。 */
  beginAgentTurn: () => AgentTurnGate;
  /** 让当前回合失效并中止其请求（停止等待 / 开新对话）。 */
  invalidateActiveAgentTurn: () => void;
  /** 只中止前端等待，不改变版本（卸载时使用）。 */
  abortActiveAgentTurn: () => void;
};

export function useAgentTurnGate(): AgentTurnGateController {
  const versionRef = useRef(0);
  const activeControllerRef = useRef<AbortController | null>(null);

  const beginAgentTurn = useCallback((): AgentTurnGate => {
    versionRef.current += 1;
    const version = versionRef.current;
    const controller = new AbortController();
    activeControllerRef.current = controller;
    return {
      version,
      controller,
      signal: controller.signal,
      isCurrent: () => versionRef.current === version && !controller.signal.aborted,
    };
  }, []);

  const invalidateActiveAgentTurn = useCallback(() => {
    versionRef.current += 1;
    const controller = activeControllerRef.current;
    activeControllerRef.current = null;
    controller?.abort();
  }, []);

  const abortActiveAgentTurn = useCallback(() => {
    activeControllerRef.current?.abort();
  }, []);

  return { beginAgentTurn, invalidateActiveAgentTurn, abortActiveAgentTurn };
}
