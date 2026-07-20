import type { ReactNode } from "react";

import type { DataSectionState } from "../DataSection.types";
import { SkeletonBarStack } from "../SkeletonBars";
import { EvidencePanel, PageStateSurface } from "./PagePrimitives";
import "./PageDataSection.css";

type PageDataSectionProps = {
  title: string;
  extra?: ReactNode;
  state: DataSectionState;
  onRetry: () => void;
  children: ReactNode;
  testId?: string;
};

/**
 * Phase 2.1 迁移桥：props 与旧 `DataSection` 完全兼容，外壳换成 page-v2
 * `EvidencePanel`，状态分支换成 `PageStateSurface`。所有 `data-section-*`
 * data-testid 与用户可见文案与旧实现逐字一致，存量测试无需弱化。
 *
 * variant 映射：loading→"loading"、error→"error"、empty→"empty"、
 * stale→"stale"、fallback→"fallback-date"；vendor_unavailable / explicit_miss
 * 本质是"无内容可展示 + 原因说明"，取最接近的 "empty"（testid 仍保留区分）。
 */
export function PageDataSection({
  title,
  extra,
  state,
  onRetry,
  children,
  testId,
}: PageDataSectionProps) {
  return (
    <EvidencePanel heading={extra ? undefined : title || undefined} testId={testId}>
      {extra ? (
        <div className="moss-page-data-section__header">
          {title ? (
            <h2 className="moss-page-v2-evidence-panel__heading">{title}</h2>
          ) : null}
          {extra}
        </div>
      ) : null}
      {renderStateBody({ state, onRetry, children })}
    </EvidencePanel>
  );
}

function bannerDetail(
  datePrefix: string,
  effectiveDate: string | undefined,
  details: string | undefined,
): string {
  const parts: string[] = [];
  if (effectiveDate) parts.push(`${datePrefix} ${effectiveDate}`);
  if (details) parts.push(details);
  return parts.join(" · ");
}

function renderStateBody(opts: {
  state: DataSectionState;
  onRetry: () => void;
  children: ReactNode;
}): ReactNode {
  const { state, onRetry, children } = opts;

  if (state.kind === "loading") {
    return (
      <PageStateSurface
        variant="loading"
        testId="data-section-loading"
        description="正在载入"
      >
        <SkeletonBarStack className="moss-skeleton-bar-stack--spaced" />
      </PageStateSurface>
    );
  }

  if (state.kind === "error") {
    return (
      <PageStateSurface
        variant="error"
        testId="data-section-error"
        title="数据载入失败。"
        description={
          state.message ?? "当前页面保留重试入口，不在浏览器端自行拼接正式口径。"
        }
        actions={
          <button
            type="button"
            onClick={onRetry}
            className="moss-page-data-section__retry"
          >
            重试
          </button>
        }
      />
    );
  }

  if (state.kind === "empty") {
    return (
      <PageStateSurface
        variant="empty"
        testId="data-section-empty"
        description={state.hint ?? "当前暂无可展示内容。"}
      />
    );
  }

  if (state.kind === "vendor_unavailable") {
    return (
      <PageStateSurface
        variant="empty"
        testId="data-section-vendor-unavailable"
        title="该业务域数据暂不可用。"
        description={state.details}
      />
    );
  }

  if (state.kind === "explicit_miss") {
    return (
      <PageStateSurface
        variant="empty"
        testId="data-section-explicit-miss"
        title={`指定报告日${state.requested_date ? ` ${state.requested_date} ` : ""}无数据。`}
        description={state.details}
      />
    );
  }

  if (state.kind === "stale") {
    return (
      <>
        <PageStateSurface
          variant="stale"
          testId="data-section-stale-banner"
          className="moss-page-data-section__banner"
          title="数据可能已过期"
          description={bannerDetail("有效日", state.effective_date, state.details)}
        />
        {children}
      </>
    );
  }

  if (state.kind === "fallback") {
    return (
      <>
        <PageStateSurface
          variant="fallback-date"
          testId="data-section-fallback-banner"
          className="moss-page-data-section__banner"
          title="已回退至最近可用日"
          description={bannerDetail("回退日", state.effective_date, state.details)}
        />
        {children}
      </>
    );
  }

  // state.kind === "ok"
  return children;
}
