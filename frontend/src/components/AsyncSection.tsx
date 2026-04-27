import type { ReactNode } from "react";

import { displayTokens } from "../theme/displayTokens";

type AsyncSectionProps = {
  title: string;
  extra?: ReactNode;
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
  onRetry: () => void;
  children: ReactNode;
};

export function AsyncSection({
  title,
  extra,
  isLoading,
  isError,
  isEmpty,
  onRetry,
  children,
}: AsyncSectionProps) {
  let content = children;

  if (isLoading) {
    content = (
      <>
        <span style={{ color: displayTokens.text.muted }}>正在载入{title}</span>
        <div style={{ display: "grid", gap: 10, marginTop: 18 }}>
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              style={{
                height: 12,
                borderRadius: 999,
                background: index === 0 ? displayTokens.surface.track : displayTokens.surface.trackAlt,
                width: index === 0 ? "76%" : index === 3 ? "61%" : "100%",
              }}
            />
          ))}
        </div>
      </>
    );
  } else if (isError) {
    content = (
      <div style={{ display: "grid", gap: 12, alignItems: "start" }}>
        <span style={{ color: displayTokens.text.error, fontWeight: 600 }}>数据载入失败。</span>
        <span style={{ color: displayTokens.text.secondary }}>
          当前页面保留重试入口，不在浏览器端自行拼接正式口径。
        </span>
        <button
          onClick={onRetry}
          style={{
            width: "fit-content",
            border: displayTokens.interactive.retryBorder,
            background: displayTokens.interactive.retryBg,
            borderRadius: 12,
            padding: "10px 16px",
            color: displayTokens.interactive.retryText,
            cursor: "pointer",
          }}
          type="button"
        >
          重试
        </button>
      </div>
    );
  } else if (isEmpty) {
    content = <div style={{ color: displayTokens.text.muted }}>当前暂无可展示内容。</div>;
  }

  const header =
    !title && !extra ? null : !title && extra ? (
      <div style={{ marginBottom: 16 }}>{extra}</div>
    ) : (
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

  return (
    <section
      style={{
        height: "100%",
        padding: 24,
        borderRadius: displayTokens.radius.section,
        background: displayTokens.surface.section,
        border: displayTokens.surface.sectionBorder,
        boxShadow: displayTokens.surface.sectionShadow,
      }}
    >
      {header}
      {content}
    </section>
  );
}
