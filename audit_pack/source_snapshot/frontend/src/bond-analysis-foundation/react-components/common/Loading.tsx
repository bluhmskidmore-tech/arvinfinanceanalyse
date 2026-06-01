export interface LoadingProps {
  label?: string;
  description?: string;
}

export function Loading({
  label = "正在加载债券工作台",
  description = "正在同步市场数据、组合视图和交易状态。",
}: LoadingProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        border: "1px dashed #94a3b8",
        borderRadius: 18,
        padding: 24,
        background: "#f8fafc",
      }}
    >
      <strong>{label}</strong>
      <p style={{ margin: "8px 0 0", color: "#475467" }}>{description}</p>
    </div>
  );
}
