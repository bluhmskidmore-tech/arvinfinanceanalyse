import type { FormEvent, KeyboardEvent } from "react";

import { shellTokens as t } from "../../../theme/tokens";

type AgentQueryFormProps = {
  pageContext?: { page_id: string };
  repoPath: string;
  onRepoPathChange: (value: string) => void;
  quickExamples: readonly string[];
  onQuickExample: (value: string) => void;
  isCurrentRepoPinned: boolean;
  onPinCurrentRepo: () => void;
  onUnpinCurrentRepo: () => void;
  processLoading: boolean;
  onLoadProcesses: () => void;
  processSearch: string;
  onProcessSearchChange: (value: string) => void;
  selectedProcess: string;
  filteredProcesses: string[];
  onSelectedProcessChange: (value: string) => void;
  onViewSelectedProcess: () => void;
  loading: boolean;
  query: string;
  onQueryChange: (value: string) => void;
  onSubmit: (event?: FormEvent<HTMLFormElement>) => void;
};

function formatQuickExampleLabel(example: string) {
  return example
    .replace("请给我看 ", "")
    .replace("GitNexus context", "GitNexus 上下文")
    .replace("GitNexus processes", "GitNexus 流程");
}

function buildPromptPlaceholder(pageContext?: { page_id: string }) {
  if (pageContext?.page_id) {
    return "直接问当前页：主要结论？异常点？下一步复核什么？";
  }
  return "问一句业务问题，例如：今天损益为什么变动？当前久期风险在哪里？";
}

function shouldSubmitByEnter(event: KeyboardEvent<HTMLTextAreaElement>) {
  return event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing;
}

const primaryQuickExampleCount = 4;

export function AgentQueryForm({
  pageContext,
  repoPath,
  onRepoPathChange,
  quickExamples,
  onQuickExample,
  isCurrentRepoPinned,
  onPinCurrentRepo,
  onUnpinCurrentRepo,
  processLoading,
  onLoadProcesses,
  processSearch,
  onProcessSearchChange,
  selectedProcess,
  filteredProcesses,
  onSelectedProcessChange,
  onViewSelectedProcess,
  loading,
  query,
  onQueryChange,
  onSubmit,
}: AgentQueryFormProps) {
  const primaryQuickExamples = quickExamples.slice(0, primaryQuickExampleCount);
  const advancedQuickExamples = quickExamples.slice(primaryQuickExampleCount);

  return (
    <div className="agent-chat-composer">
      <div className="agent-chat-composer__header">
        <div>
          <div className="agent-chat-composer__eyebrow">对话助手</div>
          <div className="agent-chat-composer__title">
            先问结论，再看证据和下钻建议
          </div>
        </div>
        <div className="agent-chat-composer__hint">Enter 发送 · Shift+Enter 换行</div>
      </div>

      <div className="agent-chat-composer__quick-row" aria-label="常用问题">
        {primaryQuickExamples.map((example) => (
          <button
            key={example}
            type="button"
            className="agent-chat-composer__quick-button"
            onClick={() => onQuickExample(example)}
          >
            {formatQuickExampleLabel(example)}
          </button>
        ))}
      </div>

      <form className="agent-chat-composer__form" onSubmit={(event) => void onSubmit(event)}>
        <textarea
          aria-label="agent-question-input"
          className="agent-chat-composer__input"
          rows={4}
          placeholder={buildPromptPlaceholder(pageContext)}
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={(event) => {
            if (shouldSubmitByEnter(event)) {
              event.preventDefault();
              void onSubmit();
            }
          }}
        />
        <button
          type="submit"
          disabled={loading}
          className="agent-chat-composer__send"
          style={{ background: t.colorAccent }}
        >
          {loading ? "发送中..." : "发送"}
        </button>
      </form>

      <details className="agent-chat-composer__advanced">
        <summary>高级工具：GitNexus / 流程图谱</summary>
        <div className="agent-chat-composer__advanced-body">
          <label className="agent-chat-composer__field">
            <span>GitNexus 仓库路径</span>
            <input
              aria-label="repo-path-input"
              type="text"
              placeholder="例如：F:\\MOSS-SYSTEM-V1"
              value={repoPath}
              onChange={(event) => onRepoPathChange(event.target.value)}
            />
          </label>

          <div className="agent-chat-composer__tool-row">
            {advancedQuickExamples.map((example) => (
              <button
                key={example}
                type="button"
                className="agent-chat-composer__tool-button"
                onClick={() => onQuickExample(example)}
              >
                {formatQuickExampleLabel(example)}
              </button>
            ))}
            <button
              type="button"
              className="agent-chat-composer__tool-button"
              onClick={isCurrentRepoPinned ? onUnpinCurrentRepo : onPinCurrentRepo}
            >
              {isCurrentRepoPinned ? "取消固定当前仓库" : "固定当前仓库"}
            </button>
            <button
              type="button"
              className="agent-chat-composer__tool-button"
              onClick={onLoadProcesses}
              disabled={processLoading}
            >
              {processLoading ? "读取中..." : "读取流程"}
            </button>
          </div>

          <div className="agent-chat-composer__process-grid">
            <label className="agent-chat-composer__field">
              <span>流程搜索</span>
              <input
                aria-label="process-search-input"
                type="text"
                placeholder="按流程名过滤"
                value={processSearch}
                onChange={(event) => onProcessSearchChange(event.target.value)}
              />
            </label>
            <label className="agent-chat-composer__field">
              <span>流程名称</span>
              <select
                aria-label="process-name-select"
                value={selectedProcess}
                onChange={(event) => onSelectedProcessChange(event.target.value)}
              >
                <option value="">请选择流程</option>
                {filteredProcesses.map((processName) => (
                  <option key={processName} value={processName}>
                    {processName}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="agent-chat-composer__secondary-action"
              onClick={onViewSelectedProcess}
              disabled={!selectedProcess || loading}
            >
              查看所选流程
            </button>
          </div>
        </div>
      </details>
    </div>
  );
}
