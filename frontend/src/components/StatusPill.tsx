export type StatusPillStatus = "normal" | "caution" | "warning" | "danger";

export type StatusPillProps = {
  status: StatusPillStatus;
  label: string;
};

const COLORS: Record<StatusPillStatus, { bg: string; fg: string; border: string }> = {
  normal: { bg: "#f6ffed", fg: "#52c41a", border: "#b7eb8f" },
  caution: { bg: "#fffbe6", fg: "#faad14", border: "#ffe58f" },
  warning: { bg: "#fff7e6", fg: "#fa8c16", border: "#ffd591" },
  danger: { bg: "#fff2f0", fg: "#f5222d", border: "#ffccc7" },
};

export function StatusPill({ status, label }: StatusPillProps) {
  const c = COLORS[status];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 8px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        background: c.bg,
        color: c.fg,
        border: `1px solid ${c.border}`,
      }}
    >
      {label}
    </span>
  );
}
