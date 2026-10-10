import { EM_DASH } from "../utils/format";
import { StatusPill, type StatusPillStatus } from "./StatusPill";
import "./CalendarList.css";

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
    <div className="calendar-list">
      {items.map((it, idx) => (
        <div key={`${it.date}-${it.event}-${idx}`} className="calendar-list__item">
          <span className="calendar-list__date">{it.date}</span>
          <div className="calendar-list__event-cell">
            <span className="calendar-list__event-title">{it.event}</span>
            {it.issuerLabel?.trim() ? (
              <span className="calendar-list__issuer">{it.issuerLabel.trim()}</span>
            ) : null}
          </div>
          <span className="calendar-list__amount">{it.amount ?? EM_DASH}</span>
          <div className="calendar-list__level">
            <StatusPill status={levelToStatus[it.level]} label={levelLabel[it.level]} />
          </div>
          <div className="calendar-list__detail">
            {it.note ? <span>{it.note}</span> : null}
            {it.sourceUrl ? (
              <a
                href={it.sourceUrl}
                target="_blank"
                rel="noreferrer noopener"
                className="calendar-list__source-link"
              >
                {it.sourceLabel?.trim() ? `${it.sourceLabel.trim()} · 打开原文` : "查看原文"}
              </a>
            ) : null}
            {!it.note && !it.sourceUrl ? <span>{EM_DASH}</span> : null}
          </div>
        </div>
      ))}
    </div>
  );
}
