import { displayTokens } from "../theme/displayTokens";

export type StatusPillStatus = "normal" | "caution" | "warning" | "danger";

export type StatusPillProps = {
  status: StatusPillStatus;
  label: string;
};

const COLORS: Record<StatusPillStatus, { bg: string; fg: string; border: string }> =
  displayTokens.statusPill;

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
