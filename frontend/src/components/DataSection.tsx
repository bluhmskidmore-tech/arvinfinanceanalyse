import type { ReactNode } from "react";

import type { DataSectionState } from "./DataSection.types";

type DataSectionProps = {
  title: string;
  extra?: ReactNode;
  state: DataSectionState;
  onRetry: () => void;
  children: ReactNode;
};

const SECTION_STYLE = {
  height: "100%",
  padding: 24,
  borderRadius: 20,
  background: "#fbfcfe",
  border: "1px solid #e4ebf5",
  boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
} as const;

const RETRY_BTN_STYLE = {
  width: "fit-content",
  border: "1px solid #d7dfea",
  background: "#ffffff",
  borderRadius: 12,
  padding: "10px 16px",
  color: "#162033",
  cursor: "pointer",
} as const;

const BANNER_BASE = {
  display: "grid",
  gap: 4,
  padding: "10px 14px",
  borderRadius: 12,
  marginBottom: 14,
  fontSize: 13,
} as const;

const STALE_BANNER = { ...BANNER_BASE, background: "#fff8f1", color: "#8a4b14", border: "1px solid #f1d3b5" };
const FALLBACK_BANNER = { ...BANNER_BASE, background: "#fff4e8", color: "#b35a16", border: "1px solid #f1d3b5" };

export function DataSection({ title, extra, state, onRetry, children }: DataSectionProps) {
  const header = renderHeader(title, extra);
  const body = renderBody({ state, onRetry, children });

  return <section style={SECTION_STYLE}>{header}{body}</section>;
}

function renderHeader(title: string, extra: ReactNode): ReactNode {
  if (!title && !extra) return null;
  if (!title && extra) {
    return <div style={{ marginBottom: 16 }}>{extra}</div>;
  }
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        marginBottom: 16,
      }}
    >
      <span style={{ fontWeight: 600 }}>{title}</span>
      {extra}
    </div>
  );
}

function renderBody(opts: {
  state: DataSectionState;
  onRetry: () => void;
  children: ReactNode;
}): ReactNode {
  const { state, onRetry, children } = opts;

  if (state.kind === "loading") {
    return (
      <div data-testid="data-section-loading">
        <span style={{ color: "#8090a8" }}>正在载入</span>
        <div style={{ display: "grid", gap: 10, marginTop: 18 }}>
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              style={{
                height: 12,
                borderRadius: 999,
                background: index === 0 ? "#e7edf5" : "#eef3f8",
                width: index === 0 ? "76%" : index === 3 ? "61%" : "100%",
              }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div data-testid="data-section-error" style={{ display: "grid", gap: 12, alignItems: "start" }}>
        <span style={{ color: "#b74c45", fontWeight: 600 }}>数据载入失败。</span>
        <span style={{ color: "#5c6b82" }}>
          {state.message ?? "当前页面保留重试入口，不在浏览器端自行拼接正式口径。"}
        </span>
        <button type="button" onClick={onRetry} style={RETRY_BTN_STYLE}>
          重试
        </button>
      </div>
    );
  }

  if (state.kind === "empty") {
    return (
      <div data-testid="data-section-empty" style={{ color: "#8090a8" }}>
        {state.hint ?? "当前暂无可展示内容。"}
      </div>
    );
  }

  if (state.kind === "vendor_unavailable") {
    return (
      <div data-testid="data-section-vendor-unavailable" style={{ display: "grid", gap: 6, color: "#5c6b82" }}>
        <span style={{ color: "#8a4b14", fontWeight: 600 }}>该业务域数据暂不可用。</span>
        {state.details ? <span>{state.details}</span> : null}
      </div>
    );
  }

  if (state.kind === "explicit_miss") {
    return (
      <div data-testid="data-section-explicit-miss" style={{ display: "grid", gap: 6, color: "#5c6b82" }}>
        <span style={{ color: "#b35a16", fontWeight: 600 }}>
          指定报告日{state.requested_date ? ` ${state.requested_date} ` : ""}无数据。
        </span>
        {state.details ? <span>{state.details}</span> : null}
      </div>
    );
  }

  if (state.kind === "stale") {
    return (
      <>
        <div data-testid="data-section-stale-banner" style={STALE_BANNER}>
          <strong>数据可能已过期</strong>
          <span>
            {state.effective_date ? `有效日 ${state.effective_date}` : null}
            {state.effective_date && state.details ? " · " : ""}
            {state.details ?? ""}
          </span>
        </div>
        {children}
      </>
    );
  }

  if (state.kind === "fallback") {
    return (
      <>
        <div data-testid="data-section-fallback-banner" style={FALLBACK_BANNER}>
          <strong>已回退至最近可用日</strong>
          <span>
            {state.effective_date ? `回退日 ${state.effective_date}` : null}
            {state.effective_date && state.details ? " · " : ""}
            {state.details ?? ""}
          </span>
        </div>
        {children}
      </>
    );
  }

  // state.kind === "ok"
  return children;
}
