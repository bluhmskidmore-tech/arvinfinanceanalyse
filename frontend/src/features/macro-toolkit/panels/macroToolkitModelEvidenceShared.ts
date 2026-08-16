import { useSyncExternalStore } from "react";

import type {
  MacroToolkitHasonStrategy,
  MacroToolkitModelReadiness,
  MacroToolkitScriptChainRun,
} from "../../../api/macroToolkitClient";

export function deriveModelReadinessFromHasonStrategy(strategy: MacroToolkitHasonStrategy): MacroToolkitModelReadiness[] {
  return strategy.source_trace.map((item) => ({
    id: item.script,
    label: item.script,
    script_name: item.script,
    expected_outputs: strategy.required_runtime_outputs,
    readiness: !item.available
      ? "registered_only"
      : strategy.missing_runtime_outputs.length
        ? "missing_output"
        : strategy.stale_runtime_outputs.length
          ? "stale"
          : "unknown",
    observation_only: strategy.observation_only,
    formal_use_allowed: strategy.formal_use_allowed,
    latest_modified_at: null,
    latest_content_date: null,
    missing_outputs: strategy.missing_runtime_outputs,
    stale_outputs: strategy.stale_runtime_outputs,
    notes: [],
  }));
}

/**
 * 模型证据桥：就绪度数据由页面传给 ModelSignalMatrix（工具模式下渲染为模型链
 * 工具条），而模型链面板只接收 model-chain results 一个 prop。页面编排层不在
 * 模型区改动范围内，因此用模块级外部存储把就绪度条目与链运行回执同步给模型
 * 链卡片（状态角标 + 证据抽屉）。观察模式（showActions=false）不发布。
 */
export type ModelChainEvidenceBridgeState = {
  entries: MacroToolkitModelReadiness[];
  chainRunResult: MacroToolkitScriptChainRun | null;
  showAcceptance: boolean;
};

let modelChainEvidenceBridgeState: ModelChainEvidenceBridgeState | null = null;
const modelChainEvidenceBridgeListeners = new Set<() => void>();

export function publishModelChainEvidenceBridge(state: ModelChainEvidenceBridgeState | null) {
  modelChainEvidenceBridgeState = state;
  for (const listener of modelChainEvidenceBridgeListeners) {
    listener();
  }
}

function subscribeModelChainEvidenceBridge(listener: () => void) {
  modelChainEvidenceBridgeListeners.add(listener);
  return () => {
    modelChainEvidenceBridgeListeners.delete(listener);
  };
}

function readModelChainEvidenceBridge() {
  return modelChainEvidenceBridgeState;
}

export function useModelChainEvidenceBridge() {
  return useSyncExternalStore(
    subscribeModelChainEvidenceBridge,
    readModelChainEvidenceBridge,
    readModelChainEvidenceBridge,
  );
}

export const MODEL_SIGNAL_MATRIX_LABELS: Record<string, string> = {
  merrill_clock: "美林时钟",
  crisis_score: "Crisis Score",
  bond_futures_basis: "国债期货基差 / IRR / 安全边际",
  bond_futures_four_factor: "国债期货四因子趋势",
  funding_conditions: "资金面 / 流动性",
  crowding: "拥挤度",
  dcc_garch: "DCC-GARCH",
  cta_trend: "CTA 趋势",
  final_signal: "最终信号聚合",
  risk_monitor: "风险监控",
};

export function modelSignalMatrixLabel(item: MacroToolkitModelReadiness) {
  return MODEL_SIGNAL_MATRIX_LABELS[item.id] ?? item.label;
}

export function modelReadinessStatusLabel(readiness: MacroToolkitModelReadiness["readiness"]) {
  const labels: Record<MacroToolkitModelReadiness["readiness"], string> = {
    artifact_backed: "产物支撑",
    missing_output: "缺产物",
    stale: "陈旧",
    registered_only: "仅注册",
    degraded: "降级",
    unknown: "待确认",
  };
  return labels[readiness];
}

export function modelReadinessStatusColor(readiness: MacroToolkitModelReadiness["readiness"]) {
  if (readiness === "artifact_backed") return "green";
  if (readiness === "stale" || readiness === "degraded" || readiness === "registered_only") return "gold";
  if (readiness === "missing_output") return "red";
  return "default";
}

export function isArtifactBackedModelReadiness(readiness: MacroToolkitModelReadiness["readiness"]) {
  return readiness === "artifact_backed";
}
