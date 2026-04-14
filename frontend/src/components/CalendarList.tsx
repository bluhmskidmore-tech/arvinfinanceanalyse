import { StatusPill, type StatusPillStatus } from "./StatusPill";

export type CalendarItem = {
  date: string;
  event: string;
  amount?: string;
  level: "high" | "medium" | "low";
  note?: string;
};

export type CalendarListProps = {
  items: CalendarItem[];
};

const levelToStatus: Record<CalendarItem["level"], StatusPillStatus> = {
  high: "danger",
  medium: "warning",
  low: "normal",
};

const levelLabel: Record<CalendarItem["level"], string> = {
  high: "高",
  medium: "中",
  low: "低",
};

export function CalendarList({ items }: CalendarListProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {items.map((it, idx) => (
        <div
          key={`${it.date}-${it.event}-${idx}`}
          style={{
            display: "grid",
            gridTemplateColumns: "88px minmax(0, 1fr) 96px auto minmax(0, 1fr)",
            gap: "8px 12px",
            alignItems: "center",
            fontSize: 13,
            color: "#162033",
            lineHeight: 1.45,
          }}
        >
          <span style={{ fontVariantNumeric: "tabular-nums" }}>{it.date}</span>
          <span style={{ wordBreak: "break-word" }}>{it.event}</span>
          <span style={{ fontVariantNumeric: "tabular-nums", color: "#5c6b82" }}>
            {it.amount ?? "—"}
          </span>
          <StatusPill status={levelToStatus[it.level]} label={levelLabel[it.level]} />
          <span style={{ color: "#5c6b82", wordBreak: "break-word" }}>{it.note ?? "—"}</span>
        </div>
      ))}
    </div>
  );
}
