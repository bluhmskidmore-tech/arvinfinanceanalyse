import { BulbOutlined, DownOutlined } from "@ant-design/icons";
import { Select } from "antd";
import { useRef } from "react";
import type { AgentReasoningEffort } from "../../../api/contracts/agent";
import type { useAgentModelSelection } from "../hooks/useAgentModelSelection";

const EFFORT_LABELS: Record<AgentReasoningEffort, string> = {
  none: "关闭思考", minimal: "轻量思考", low: "快速思考", medium: "均衡思考",
  high: "深入思考", xhigh: "深度思考", max: "最高思考", ultra: "极致思考",
};

export function AgentModelControls({ state, disabled }: {
  state: ReturnType<typeof useAgentModelSelection>;
  disabled: boolean;
}) {
  const controlsRef = useRef<HTMLDivElement>(null);
  const groups = new Map<string, Array<{ value: string; label: string }>>();
  for (const model of state.catalog?.models ?? []) {
    const provider = /^gpt-|^o[134](?:-|$)/i.test(model.id) ? "OpenAI"
      : /^deepseek/i.test(model.id) ? "DeepSeek"
        : /^minimax/i.test(model.id) ? "MiniMax" : "其他模型";
    const options = groups.get(provider) ?? [];
    options.push({ value: model.id, label: model.label });
    groups.set(provider, options);
  }
  function focusComposer() {
    // rc-select restores selector focus in a mouse-down timer; hand it back
    // to the composer after that task rather than racing its popup cleanup.
    window.setTimeout(() => {
      controlsRef.current?.closest(".agent-chat-composer")
        ?.querySelector<HTMLTextAreaElement>("textarea")?.focus({ preventScroll: true });
    }, 0);
  }
  const popupContainer = (trigger: HTMLElement) =>
    trigger.closest<HTMLElement>('[data-moss-theme-scope="agent"]') ?? trigger.parentElement!;
  return (
    <div className="agent-model-controls" aria-label="回答设置" ref={controlsRef}>
      <div className="agent-model-control">
        <Select aria-label="选择模型" value={state.currentModel?.id}
          className="agent-model-select" variant="borderless" showSearch
          optionFilterProp="label" placeholder={state.loading ? "读取模型…" : "默认模型"}
          suffixIcon={<DownOutlined aria-hidden="true" />} loading={state.loading}
          options={Array.from(groups, ([label, options]) => ({ label, options }))}
          classNames={{ popup: { root: "agent-model-popup" } }} popupMatchSelectWidth={280} placement="topLeft"
          getPopupContainer={popupContainer} listHeight={272} virtual={false}
          notFoundContent="没有匹配的模型"
          title={disabled ? "回答完成后可切换模型" : "选择模型，也可以输入名称搜索"}
          disabled={disabled || state.loading || !state.currentModel}
          onChange={state.selectModel} onSelect={focusComposer}
        />
      </div>
      <div className="agent-model-control agent-model-control--reasoning">
        <BulbOutlined aria-hidden="true" />
        <Select aria-label="思考程度" value={state.selection.reasoning_effort ?? "default"}
          variant="borderless" suffixIcon={<DownOutlined aria-hidden="true" />}
          classNames={{ popup: { root: "agent-model-popup agent-reasoning-popup" } }} popupMatchSelectWidth={184}
          placement="topLeft" getPopupContainer={popupContainer} virtual={false}
          options={state.currentModel?.reasoning_efforts.length
            ? state.currentModel.reasoning_efforts.map((effort) => ({ value: effort, label: EFFORT_LABELS[effort] }))
            : [{ value: "default", label: "默认思考" }]}
          title={state.currentModel?.reasoning_efforts.length
            ? "思考越深入，通常需要等待越久。切换只影响下一次提问。" : "当前模型使用默认思考设置"}
          disabled={disabled || state.loading || !state.currentModel?.reasoning_efforts.length}
          onChange={(effort) => state.selectReasoning(effort as AgentReasoningEffort)} onSelect={focusComposer}
        />
      </div>
      {state.error ? <div className="agent-model-controls__notice" role="status">
        {state.error}<button type="button" onClick={state.reload} disabled={disabled}>重试</button>
      </div> : null}
      {!state.error && state.catalog?.source === "cache" ? (
        <span className="agent-model-controls__notice">使用最近读取的模型列表</span>
      ) : null}
    </div>
  );
}
