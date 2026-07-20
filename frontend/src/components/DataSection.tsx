import type { ReactNode } from "react";

import type { DataSectionState } from "./DataSection.types";
import "./DataSection.css";

type DataSectionProps = {
  title: string;
  extra?: ReactNode;
  state: DataSectionState;
  onRetry: () => void;
  children: ReactNode;
};

/**
 * @deprecated Prefer `components/page/PagePrimitives` (`PageSurfacePanel` /
 * `PageSectionLead` / `PageStateSurface`). Kept for existing call sites while
 * Phase 2 migrates consumers to the page-v2 contract.
 */
export function DataSection({ title, extra, state, onRetry, children }: DataSectionProps) {
  const header = renderHeader(title, extra);
  const body = renderBody({ state, onRetry, children });

  return <section className="data-section">{header}{body}</section>;
}

function renderHeader(title: string, extra: ReactNode): ReactNode {
  if (!title && !extra) return null;
  if (!title && extra) {
    return <div className="data-section__header-extra">{extra}</div>;
  }
  return (
    <div className="data-section__header">
      <span className="data-section__title">{title}</span>
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
        <span className="data-section__loading-label">正在载入</span>
        <div className="data-section__skeleton-stack">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="data-section__skeleton-bar" />
          ))}
        </div>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div data-testid="data-section-error" className="data-section__state-stack">
        <span className="data-section__error-title">数据载入失败。</span>
        <span className="data-section__secondary-text">
          {state.message ?? "当前页面保留重试入口，不在浏览器端自行拼接正式口径。"}
        </span>
        <button type="button" onClick={onRetry} className="data-section__retry-button">
          重试
        </button>
      </div>
    );
  }

  if (state.kind === "empty") {
    return (
      <div data-testid="data-section-empty" className="data-section__empty">
        {state.hint ?? "当前暂无可展示内容。"}
      </div>
    );
  }

  if (state.kind === "vendor_unavailable") {
    return (
      <div data-testid="data-section-vendor-unavailable" className="data-section__compact-state">
        <span className="data-section__warning-soft-title">该业务域数据暂不可用。</span>
        {state.details ? <span>{state.details}</span> : null}
      </div>
    );
  }

  if (state.kind === "explicit_miss") {
    return (
      <div data-testid="data-section-explicit-miss" className="data-section__compact-state">
        <span className="data-section__warning-title">
          指定报告日{state.requested_date ? ` ${state.requested_date} ` : ""}无数据。
        </span>
        {state.details ? <span>{state.details}</span> : null}
      </div>
    );
  }

  if (state.kind === "stale") {
    return (
      <>
        <div data-testid="data-section-stale-banner" className="data-section__banner data-section__banner--stale">
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
        <div data-testid="data-section-fallback-banner" className="data-section__banner data-section__banner--fallback">
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
