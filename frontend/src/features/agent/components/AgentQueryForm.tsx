import { useEffect, useRef, type FormEvent, type KeyboardEvent, type MutableRefObject, type Ref } from "react";

type AgentQueryFormProps = {
  compact?: boolean;
  showAdvancedTools?: boolean;
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
  activeQuestion?: string;
  composerHint?: string | null;
  onQueryChange: (value: string) => void;
  onClearQuery?: () => void;
  onSubmit: (event?: FormEvent<HTMLFormElement>) => void;
  onQueueSubmit?: () => void;
  onStop?: () => void;
  inputRef?: Ref<HTMLTextAreaElement>;
};

function formatQuickExampleLabel(example: string) {
  return example
    .replace("请给我看 ", "")
    .replace("GitNexus context", "GitNexus 上下文")
    .replace("GitNexus processes", "GitNexus 流程");
}

function buildPromptPlaceholder(pageContext?: { page_id: string }) {
  if (pageContext?.page_id) {
    return "问当前页：主要结论？异常点？下一步复核什么？";
  }
  return "随便问一句，例如：今天哪里最值得看？久期风险在哪？";
}

function shouldSubmitByEnter(event: KeyboardEvent<HTMLTextAreaElement>, query: string) {
  const nativeEvent = event.nativeEvent as Event & {
    isComposing?: boolean;
    nativeEvent?: { isComposing?: boolean };
  };
  return (
    query.trim().length > 0 &&
    event.key === "Enter" &&
    !event.shiftKey &&
    !nativeEvent.isComposing &&
    !nativeEvent.nativeEvent?.isComposing
  );
}

function assignTextAreaRef(ref: Ref<HTMLTextAreaElement> | undefined, element: HTMLTextAreaElement | null) {
  if (!ref) {
    return;
  }
  if (typeof ref === "function") {
    ref(element);
    return;
  }
  (ref as MutableRefObject<HTMLTextAreaElement | null>).current = element;
}

function shouldScrollTextareaIntoView(textarea: HTMLTextAreaElement) {
  const visualViewport = window.visualViewport;
  const viewportTop = visualViewport?.offsetTop ?? 0;
  const viewportHeight = visualViewport?.height ?? window.innerHeight ?? document.documentElement.clientHeight;
  const viewportBottom = viewportTop + viewportHeight;
  const rect = textarea.getBoundingClientRect();
  return rect.top < viewportTop || rect.bottom > viewportBottom;
}

const primaryQuickExampleCount = 2;

export function AgentQueryForm({
  compact = false,
  showAdvancedTools = true,
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
  activeQuestion = "",
  composerHint,
  onQueryChange,
  onClearQuery,
  onSubmit,
  onQueueSubmit,
  onStop,
  inputRef,
}: AgentQueryFormProps) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const primaryQuickExamples = quickExamples.slice(0, primaryQuickExampleCount);
  const advancedQuickExamples = quickExamples.slice(primaryQuickExampleCount);
  const hasQuery = query.trim().length > 0;
  const submitHint = loading
    ? onQueueSubmit
      ? "回答中 · Enter 排队下一句 · Shift+Enter 换行"
      : "正在回答 · Shift+Enter 换行"
    : "Enter 发送 · Shift+Enter 换行";
  const visibleComposerHint = composerHint ?? submitHint;
  const quickExampleRow =
    primaryQuickExamples.length > 0 ? (
      <div
        className={
          compact
            ? "agent-chat-composer__quick-row agent-chat-composer__quick-row--compact"
            : "agent-chat-composer__quick-row"
        }
        aria-label="常用问题"
      >
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
    ) : null;

  function focusTextarea() {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    textarea.focus();
    const scrollIntoView = textarea.scrollIntoView;
    if (typeof scrollIntoView === "function" && shouldScrollTextareaIntoView(textarea)) {
      scrollIntoView.call(textarea, { behavior: "smooth", block: "nearest" });
    }
  }

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    if (!query) {
      textarea.style.height = "";
      return;
    }
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [query]);

  return (
    <div className={compact ? "agent-chat-composer agent-chat-composer--compact" : "agent-chat-composer"}>
      {!compact ? (
        <>
          <div className="agent-chat-composer__header">
            <div>
              <div className="agent-chat-composer__title">问我</div>
            </div>
            <div
              className="agent-chat-composer__hint"
              role="status"
              aria-label="输入提示"
              aria-live="polite"
              aria-atomic="true"
            >
              {visibleComposerHint}
            </div>
          </div>

          {quickExampleRow}
        </>
      ) : null}
      {compact ? quickExampleRow : null}

      <form className="agent-chat-composer__form" onSubmit={(event) => void onSubmit(event)}>
        <div className="agent-chat-composer__input-wrap">
          <textarea
            aria-label="向 Agent 提问"
            data-testid="agent-panel-question"
            className="agent-chat-composer__input"
            ref={(element) => {
              textareaRef.current = element;
              assignTextAreaRef(inputRef, element);
            }}
            rows={compact ? 2 : 3}
            placeholder={buildPromptPlaceholder(pageContext)}
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            onKeyDown={(event) => {
              if (shouldSubmitByEnter(event, query)) {
                event.preventDefault();
                if (loading && onQueueSubmit) {
                  onQueueSubmit();
                  return;
                }
                void onSubmit();
              }
            }}
          />
          {hasQuery ? (
            <button
              type="button"
              className="agent-chat-composer__clear"
              aria-label={`清空输入：${query}`}
              onClick={() => {
                if (onClearQuery) {
                  onClearQuery();
                } else {
                  onQueryChange("");
                }
                focusTextarea();
              }}
            >
              清空输入
            </button>
          ) : null}
        </div>
        {compact ? (
          <div
            className="agent-chat-composer__hint"
            role="status"
            aria-label="输入提示"
            aria-live="polite"
            aria-atomic="true"
          >
            {visibleComposerHint}
          </div>
        ) : null}
        <div
          className={
            loading && onStop
              ? "agent-chat-composer__actions agent-chat-composer__actions--running"
              : "agent-chat-composer__actions"
          }
        >
          {loading && onStop ? (
            <>
              {onQueueSubmit ? (
                <button
                  type="button"
                  className="agent-chat-composer__queue"
                  data-testid="agent-panel-queue-submit"
                  disabled={!hasQuery}
                  onClick={onQueueSubmit}
                >
                  发送下一句
                </button>
              ) : null}
              <button
                type="button"
                data-testid="agent-panel-submit"
                className="agent-chat-composer__send agent-chat-composer__send--stop"
                aria-label={
                  activeQuestion.trim()
                    ? `停止等待当前回答：${activeQuestion.trim()}`
                    : "停止等待"
                }
                onClick={onStop}
              >
                停止等待
              </button>
            </>
          ) : (
            <button
              type="submit"
              data-testid="agent-panel-submit"
              disabled={loading || !hasQuery}
              className="agent-chat-composer__send"
            >
              {loading ? "发送中..." : "发送"}
            </button>
          )}
        </div>
      </form>

      {showAdvancedTools ? (
        <details className="agent-chat-composer__advanced">
          <summary>工具</summary>
          <div className="agent-chat-composer__advanced-body">
            <label className="agent-chat-composer__field">
              <span>GitNexus 仓库路径</span>
              <input
                aria-label="GitNexus 仓库路径"
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

            <details className="agent-chat-composer__process-details">
              <summary>{filteredProcesses.length > 0 ? `流程筛选与查看 · ${filteredProcesses.length} 项` : "流程筛选与查看"}</summary>
              <div className="agent-chat-composer__process-grid">
                <label className="agent-chat-composer__field">
                  <span>流程搜索</span>
                  <input
                    aria-label="流程搜索"
                    type="text"
                    placeholder="按流程名过滤"
                    value={processSearch}
                    onChange={(event) => onProcessSearchChange(event.target.value)}
                  />
                </label>
                <label className="agent-chat-composer__field">
                  <span>流程名称</span>
                  <select
                    aria-label="流程名称"
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
                  disabled={loading}
                >
                  查看所选流程
                </button>
              </div>
            </details>
          </div>
        </details>
      ) : null}
    </div>
  );
}
