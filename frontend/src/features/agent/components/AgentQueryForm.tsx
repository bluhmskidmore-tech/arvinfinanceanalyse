import type { FormEvent } from "react";

import { shellTokens as t } from "../../../theme/tokens";

type AgentQueryFormProps = {
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

export function AgentQueryForm({
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
  return (
    <>
      <div
        style={{
          marginTop: 16,
          marginBottom: 20,
          display: "grid",
          gap: 10,
        }}
      >
        <label
          style={{
            display: "grid",
            gap: 8,
            color: t.colorTextSecondary,
            fontSize: 13,
          }}
        >
          <span>GitNexus 仓库路径</span>
          <input
            aria-label="repo-path-input"
            type="text"
            placeholder="例如：F:\\MOSS-SYSTEM-V1"
            value={repoPath}
            onChange={(event) => onRepoPathChange(event.target.value)}
            style={{
              padding: "11px 14px",
              borderRadius: 14,
              border: `1px solid ${t.colorBorder}`,
              background: t.colorBgCanvas,
              color: t.colorTextPrimary,
              fontSize: 14,
              outline: "none",
              boxSizing: "border-box",
            }}
          />
        </label>

        <div
          style={{
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
          }}
        >
          {quickExamples.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => onQuickExample(example)}
              style={{
                padding: "8px 12px",
                borderRadius: 999,
                border: `1px solid ${t.colorBorder}`,
                background: t.colorBgCanvas,
                color: t.colorTextSecondary,
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {formatQuickExampleLabel(example)}
            </button>
          ))}
          <button
            type="button"
            onClick={isCurrentRepoPinned ? onUnpinCurrentRepo : onPinCurrentRepo}
            style={{
              padding: "8px 12px",
              borderRadius: 999,
              border: `1px solid ${t.colorBorder}`,
              background: isCurrentRepoPinned ? t.colorBgMuted : t.colorBgCanvas,
              color: t.colorTextSecondary,
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {isCurrentRepoPinned ? "取消固定当前仓库" : "固定当前仓库"}
          </button>
          <button
            type="button"
            onClick={onLoadProcesses}
            disabled={processLoading}
            style={{
              padding: "8px 12px",
              borderRadius: 999,
              border: `1px solid ${t.colorBorder}`,
              background: t.colorBgCanvas,
              color: t.colorTextSecondary,
              fontSize: 12,
              fontWeight: 600,
              cursor: processLoading ? "default" : "pointer",
              opacity: processLoading ? 0.72 : 1,
            }}
          >
            {processLoading ? "读取中..." : "读取流程"}
          </button>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 10,
            alignItems: "end",
          }}
        >
          <label
            style={{
              display: "grid",
              gap: 8,
              color: t.colorTextSecondary,
              fontSize: 13,
            }}
          >
            <span>流程搜索</span>
            <input
              aria-label="process-search-input"
              type="text"
              placeholder="按流程名过滤"
              value={processSearch}
              onChange={(event) => onProcessSearchChange(event.target.value)}
              style={{
                padding: "11px 14px",
                borderRadius: 14,
                border: `1px solid ${t.colorBorder}`,
                background: t.colorBgCanvas,
                color: t.colorTextPrimary,
                fontSize: 14,
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </label>
          <label
            style={{
              display: "grid",
              gap: 8,
              color: t.colorTextSecondary,
              fontSize: 13,
            }}
          >
            <span>流程名称</span>
            <select
              aria-label="process-name-select"
              value={selectedProcess}
              onChange={(event) => onSelectedProcessChange(event.target.value)}
              style={{
                padding: "11px 14px",
                borderRadius: 14,
                border: `1px solid ${t.colorBorder}`,
                background: t.colorBgCanvas,
                color: t.colorTextPrimary,
                fontSize: 14,
                outline: "none",
                boxSizing: "border-box",
              }}
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
            onClick={onViewSelectedProcess}
            disabled={!selectedProcess || loading}
            style={{
              padding: "12px 16px",
              borderRadius: 14,
              border: `1px solid ${t.colorBorder}`,
              background: t.colorBgCanvas,
              color: t.colorTextSecondary,
              fontSize: 13,
              fontWeight: 600,
              cursor: !selectedProcess || loading ? "default" : "pointer",
              opacity: !selectedProcess || loading ? 0.72 : 1,
            }}
          >
            查看所选流程
          </button>
        </div>
      </div>

      <form
        onSubmit={(event) => void onSubmit(event)}
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          marginTop: 20,
          marginBottom: 24,
        }}
      >
        <input
          type="text"
          placeholder="例如：组合概览、损益汇总、久期风险、信用集中度、GitNexus 仓库图谱..."
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          style={{
            flex: "1 1 320px",
            minWidth: 0,
            padding: "12px 16px",
            borderRadius: 14,
            border: `1px solid ${t.colorBorder}`,
            background: t.colorBgCanvas,
            color: t.colorTextPrimary,
            fontSize: 15,
            outline: "none",
            boxSizing: "border-box",
          }}
        />
        <button
          type="submit"
          disabled={loading}
          style={{
            padding: "12px 24px",
            borderRadius: 14,
            border: "none",
            background: t.colorAccent,
            color: t.colorBgCanvas,
            fontSize: 15,
            fontWeight: 600,
            cursor: loading ? "default" : "pointer",
            opacity: loading ? 0.72 : 1,
          }}
        >
          {loading ? "查询中..." : "查询"}
        </button>
      </form>
    </>
  );
}
