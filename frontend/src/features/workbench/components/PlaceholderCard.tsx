type PlaceholderCardSurfaceTone = "default" | "ok" | "warning" | "error";

type PlaceholderCardProps = {
  title: string;
  value: string;
  detail: string;
  /** 列表型要点使用 text，大数字演示使用 metric（默认） */
  valueVariant?: "metric" | "text";
  surfaceTone?: PlaceholderCardSurfaceTone;
};

const surfaceToneBackground: Record<PlaceholderCardSurfaceTone, string> = {
  default: "#fbfcfe",
  ok: "#e8f6ee",
  warning: "#fffbeb",
  error: "#fff0f0",
};

export function PlaceholderCard({
  title,
  value,
  detail,
  valueVariant = "metric",
  surfaceTone = "default",
}: PlaceholderCardProps) {
  const valueStyle =
    valueVariant === "text"
      ? {
          marginTop: 10,
          marginBottom: 8,
          fontSize: 16,
          fontWeight: 600,
          color: "#162033",
          lineHeight: 1.5,
        }
      : {
          marginTop: 14,
          marginBottom: 10,
          fontSize: 28,
          fontWeight: 600,
          color: "#162033",
        };

  return (
    <div
      style={{
        minHeight: valueVariant === "text" ? 140 : 170,
        padding: 24,
        borderRadius: 18,
        background: surfaceToneBackground[surfaceTone],
        border: "1px solid #e4ebf5",
        boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
      }}
    >
      <div
        style={{
          color: "#6c7b91",
          fontSize: 13,
          letterSpacing: "0.02em",
        }}
      >
        {title}
      </div>
      <div style={valueStyle}>
        {value}
      </div>
      <p
        style={{
          marginBottom: 0,
          color: "#5c6b82",
          fontSize: 14,
        }}
      >
        {detail}
      </p>
    </div>
  );
}
