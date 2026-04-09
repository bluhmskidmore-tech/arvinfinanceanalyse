type PlaceholderCardProps = {
  title: string;
  value: string;
  detail: string;
};

export function PlaceholderCard({
  title,
  value,
  detail,
}: PlaceholderCardProps) {
  return (
    <div
      style={{
        minHeight: 170,
        padding: 24,
        borderRadius: 18,
        background: "#fbfcfe",
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
      <div
        style={{
          marginTop: 14,
          marginBottom: 10,
          fontSize: 28,
          fontWeight: 600,
          color: "#162033",
        }}
      >
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
