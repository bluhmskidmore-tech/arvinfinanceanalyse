import type { ReactNode } from "react";

import { SkeletonBarStack } from "../SkeletonBars";
import { EvidencePanel, PageStateSurface } from "./PagePrimitives";
import "./PageAsyncSection.css";

type PageAsyncSectionProps = {
  title: string;
  extra?: ReactNode;
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
  fillHeight?: boolean;
  hideHeading?: boolean;
  onRetry: () => void;
  children: ReactNode;
  testId?: string;
};

/**
 * Phase 2.1 迁移桥：props 与旧 `AsyncSection`（isLoading / isError / isEmpty
 * 布尔契约）保持兼容，外壳换成 page-v2 `EvidencePanel`，状态分支换成
 * `PageStateSurface`。loading / error / empty 用户可见文案与旧实现逐字一致，
 * 状态优先级同旧实现（loading > error > empty > children）。
 *
 * `fillHeight` 仅保留旧的高度语义（默认撑满父容器，局部可退出），通过桥接根
 * 上的最小 class 实现，不新建布局框架。
 */
export function PageAsyncSection({
  title,
  extra,
  isLoading,
  isError,
  isEmpty,
  fillHeight = true,
  hideHeading = false,
  onRetry,
  children,
  testId,
}: PageAsyncSectionProps) {
  return (
    <EvidencePanel
      heading={!hideHeading && !extra ? title || undefined : undefined}
      className={fillHeight ? "moss-page-async-section--fill" : undefined}
      testId={testId}
    >
      {extra ? (
        <div className="moss-page-async-section__header">
          {!hideHeading && title ? (
            <h2 className="moss-page-v2-evidence-panel__heading">{title}</h2>
          ) : null}
          {extra}
        </div>
      ) : null}
      {renderStateBody({ title, isLoading, isError, isEmpty, onRetry, children })}
    </EvidencePanel>
  );
}

function renderStateBody(opts: {
  title: string;
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
  onRetry: () => void;
  children: ReactNode;
}): ReactNode {
  const { title, isLoading, isError, isEmpty, onRetry, children } = opts;

  if (isLoading) {
    return (
      <PageStateSurface
        variant="loading"
        testId="page-async-section-loading"
        description={`正在载入${title}`}
      >
        <SkeletonBarStack className="moss-skeleton-bar-stack--spaced" />
      </PageStateSurface>
    );
  }

  if (isError) {
    return (
      <PageStateSurface
        variant="error"
        testId="page-async-section-error"
        title="数据载入失败。"
        description="当前页面保留重试入口，不在浏览器端自行拼接正式口径。"
        actions={
          <button
            type="button"
            onClick={onRetry}
            className="moss-page-async-section__retry"
          >
            重试
          </button>
        }
      />
    );
  }

  if (isEmpty) {
    return (
      <PageStateSurface
        variant="empty"
        testId="page-async-section-empty"
        description="当前暂无可展示内容。"
      />
    );
  }

  return children;
}
