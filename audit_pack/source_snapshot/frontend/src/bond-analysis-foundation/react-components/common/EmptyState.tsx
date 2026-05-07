export interface EmptyStateProps {
  title: string;
  description?: string;
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div
      style={{
        border: "1px dashed #cbd5e1",
        borderRadius: 18,
        padding: 24,
        textAlign: "center",
        background: "#f8fafc",
      }}
    >
      <strong>{title}</strong>
      {description ? <p style={{ color: "#475467", marginBottom: 0 }}>{description}</p> : null}
    </div>
  );
}
