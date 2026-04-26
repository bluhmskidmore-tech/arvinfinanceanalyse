import { StatusPill, type StatusPillStatus } from "./StatusPill";
import { designTokens } from "../theme/designSystem";

const cal = designTokens;

export type CalendarItem = {
  date: string;
  /** 业务标题（事件名） */
  event: string;
  /** 发行人/主体，独立小标签，不混在副文里 */
  issuerLabel?: string;
  amount?: string;
  level: "high" | "medium" | "low";
  note?: string;
  /** 公告原文；与 `sourceLabel` 配对展示，不铺长 URL。 */
  sourceUrl?: string;
  /** 链接可用名，缺省为「查看原文」 */
  sourceLabel?: string;
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
            alignItems: "start",
            fontSize: 13,
            color: "#162033",
            lineHeight: 1.45,
          }}
        >
          <span style={{ fontVariantNumeric: "tabular-nums", paddingTop: 2 }}>{it.date}</span>
          <div style={{ display: "grid", gap: 6, minWidth: 0 }}>
            <span style={{ wordBreak: "break-word", fontWeight: 700, fontSize: cal.fontSize[13], color: cal.color.neutral[900] }}>
              {it.event}
            </span>
            {it.issuerLabel?.trim() ? (
              <span
                style={{
                  display: "inline-block",
                  alignSelf: "start",
                  maxWidth: "100%",
                  padding: `2px ${cal.space[2]}px`,
                  borderRadius: 6,
                  fontSize: cal.fontSize[11],
                  fontWeight: 600,
                  color: cal.color.neutral[600],
                  background: cal.color.neutral[50],
                  border: `1px solid ${cal.color.neutral[200]}`,
                  wordBreak: "break-word",
                }}
              >
                {it.issuerLabel.trim()}
              </span>
            ) : null}
          </div>
          <span style={{ fontVariantNumeric: "tabular-nums", color: "#5c6b82", paddingTop: 2 }}>
            {it.amount ?? "—"}
          </span>
          <div style={{ paddingTop: 2 }}>
            <StatusPill status={levelToStatus[it.level]} label={levelLabel[it.level]} />
          </div>
          <div
            style={{
              display: "grid",
              gap: 4,
              color: "#5c6b82",
              wordBreak: "break-word",
              fontSize: 12,
              minWidth: 0,
            }}
          >
            {it.note ? <span>{it.note}</span> : null}
            {it.sourceUrl ? (
              <a
                href={it.sourceUrl}
                target="_blank"
                rel="noreferrer noopener"
                style={{ color: "#2c5a79", fontWeight: 600, fontSize: 12, textDecoration: "none" }}
              >
                {it.sourceLabel?.trim() ? `${it.sourceLabel.trim()} · 打开原文` : "查看原文"}
              </a>
            ) : null}
            {!it.note && !it.sourceUrl ? <span>—</span> : null}
          </div>
        </div>
      ))}
    </div>
  );
}
