import type { CSSProperties, ReactNode } from "react";

import { displayTokens } from "../theme/displayTokens";
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

type AsyncSectionStyle = CSSProperties & {
  "--display-section-border": string;
  "--display-section-radius": string;
  "--display-section-bg": string;
  "--display-section-shadow": string;
  "--display-surface-track": string;
  "--display-surface-track-alt": string;
  "--display-text-muted": string;
  "--display-text-error": string;
  "--display-text-secondary": string;
  "--display-retry-border": string;
  "--display-retry-bg": string;
  "--display-retry-text": string;
};

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

  const sectionStyle: AsyncSectionStyle = {
    height: fillHeight ? "100%" : "auto",
    "--display-section-border": displayTokens.surface.sectionBorder,
    "--display-section-radius": `${displayTokens.radius.section}px`,
    "--display-section-bg": displayTokens.surface.section,
    "--display-section-shadow": displayTokens.surface.sectionShadow,
    "--display-surface-track": displayTokens.surface.track,
    "--display-surface-track-alt": displayTokens.surface.trackAlt,
    "--display-text-muted": displayTokens.text.muted,
    "--display-text-error": displayTokens.text.error,
    "--display-text-secondary": displayTokens.text.secondary,
    "--display-retry-border": displayTokens.interactive.retryBorder,
    "--display-retry-bg": displayTokens.interactive.retryBg,
    "--display-retry-text": displayTokens.interactive.retryText,
  };

  return (
    <section className="async-section" style={sectionStyle}>
      {header}
      {content}
    </section>
  );
}
