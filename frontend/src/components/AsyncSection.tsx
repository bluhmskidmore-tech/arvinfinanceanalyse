import type { ReactNode } from "react";

import "./AsyncSection.css";

type AsyncSectionProps = {
  title: string;
  extra?: ReactNode;
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
  fillHeight?: boolean;
  onRetry: () => void;
  children: ReactNode;
};

/**
 * @deprecated Prefer `components/page/PagePrimitives` (`PageSurfacePanel` /
 * `PageStateSurface`). Kept for existing call sites while Phase 2 migrates
 * consumers to the page-v2 contract. Radius already locked to `--ib-radius`.
 */
export function AsyncSection({
  title,
  extra,
  isLoading,
  isError,
  isEmpty,
  fillHeight = true,
  onRetry,
  children,
}: AsyncSectionProps) {
  let content = children;

  if (isLoading) {
    content = (
      <>
        <span className="async-section__loading-text">正在载入{title}</span>
        <div className="async-section__skeleton">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="async-section__skeleton-bar" />
          ))}
        </div>
      </>
    );
  } else if (isError) {
    content = (
      <div className="async-section__error">
        <span className="async-section__error-title">数据载入失败。</span>
        <span className="async-section__error-message">
          当前页面保留重试入口，不在浏览器端自行拼接正式口径。
        </span>
        <button onClick={onRetry} className="async-section__retry" type="button">
          重试
        </button>
      </div>
    );
  } else if (isEmpty) {
    content = <div className="async-section__empty">当前暂无可展示内容。</div>;
  }

  const header =
    !title && !extra ? null : !title && extra ? (
      <div className="async-section__extra">{extra}</div>
    ) : (
      <div className="async-section__header">
        <span className="async-section__title">{title}</span>
        {extra}
      </div>
    );

  const sectionClassName = fillHeight ? "async-section async-section--fill" : "async-section async-section--auto";

  return (
    <section className={sectionClassName}>
      {header}
      {content}
    </section>
  );
}
