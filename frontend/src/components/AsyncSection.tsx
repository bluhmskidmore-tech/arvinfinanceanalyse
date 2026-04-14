import type { ReactNode } from "react";

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
        <span style={{ color: "#8090a8" }}>正在载入{title}</span>
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
      </>
    );
  } else if (isError) {
    content = (
      <div style={{ display: "grid", gap: 12, alignItems: "start" }}>
        <span style={{ color: "#b74c45", fontWeight: 600 }}>数据载入失败。</span>
        <span style={{ color: "#5c6b82" }}>
          当前页面保留重试入口，不在浏览器端自行拼接正式口径。
        </span>
        <button
          onClick={onRetry}
          style={{
            width: "fit-content",
            border: "1px solid #d7dfea",
            background: "#ffffff",
            borderRadius: 12,
            padding: "10px 16px",
            color: "#162033",
            cursor: "pointer",
          }}
          type="button"
        >
          重试
        </button>
      </div>
    );
  } else if (isEmpty) {
    content = <div style={{ color: "#8090a8" }}>当前暂无可展示内容。</div>;
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
        borderRadius: 20,
        background: "#fbfcfe",
        border: "1px solid #e4ebf5",
        boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
      }}
    >
      {header}
      {content}
    </section>
  );
}
