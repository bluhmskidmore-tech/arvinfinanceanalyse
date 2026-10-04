import { useEffect, useState } from "react";
import type { AgentClientMethods } from "../../../api/agentClient";
import type { AgentModelCatalog, AgentReasoningEffort } from "../../../api/contracts/agent";

const STORAGE_KEY = "moss.agent.model-selection.v1";
type Selection = { model: string; reasoning_effort?: AgentReasoningEffort };

function readSelection(): Selection {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
    return saved && typeof saved.model === "string" ? saved : { model: "" };
  } catch {
    return { model: "" };
  }
}

export function useAgentModelSelection(enabled: boolean, client: Pick<AgentClientMethods, "getAgentModels">) {
  const [catalog, setCatalog] = useState<AgentModelCatalog | null>(null);
  const [selection, setSelection] = useState<Selection>(readSelection);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    setLoading(true);
    setError("");
    client.getAgentModels().then((next) => {
      if (!active) return;
      if (!next || !Array.isArray(next.models)) throw new Error("Invalid model catalog");
      setCatalog(next);
      setSelection((current) => {
        const model = next.models.find((item) => item.id === current.model)
          ?? next.models.find((item) => item.id === next.default_model)
          ?? next.models[0];
        if (!model) return { model: "" };
        const preferred = current.reasoning_effort ?? "low";
        return {
          model: model.id,
          reasoning_effort: model.reasoning_efforts.includes(preferred)
            ? preferred : model.default_reasoning_effort ?? undefined,
        };
      });
    }).catch(() => {
      if (active) {
        setCatalog(null);
        setError("模型列表暂不可用，本轮使用默认配置。");
      }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [enabled, client, revision]);

  useEffect(() => {
    if (!enabled || !catalog || !selection.model) return;
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(selection)); } catch { /* Storage may be disabled. */ }
  }, [catalog, enabled, selection]);

  const currentModel = catalog?.models.find((model) => model.id === selection.model);
  return {
    catalog, currentModel, selection, loading, error,
    requestOptions: enabled && currentModel ? selection : undefined,
    selectModel(modelId: string) {
      const model = catalog?.models.find((item) => item.id === modelId);
      if (!model) return;
      setSelection((current) => ({
        model: model.id,
        reasoning_effort: current.reasoning_effort && model.reasoning_efforts.includes(current.reasoning_effort)
          ? current.reasoning_effort : model.default_reasoning_effort ?? undefined,
      }));
    },
    selectReasoning(reasoning_effort: AgentReasoningEffort) {
      if (currentModel?.reasoning_efforts.includes(reasoning_effort)) {
        setSelection((current) => ({ ...current, reasoning_effort }));
      }
    },
    reload() { setRevision((current) => current + 1); },
  };
}
