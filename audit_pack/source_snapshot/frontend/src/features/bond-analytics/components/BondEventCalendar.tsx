import type { CalendarItem } from "../../../components/CalendarList";
import { CalendarList } from "../../../components/CalendarList";
import { SectionCard } from "../../../components/SectionCard";
import { BORDER, panelStyle } from "./bondAnalyticsCockpitTokens";

export type BondEventCalendarProps = {
  items: CalendarItem[];
};

export function BondEventCalendar({ items }: BondEventCalendarProps) {
  return (
    <SectionCard
      title="关键事件与日历（未来两周）"
      style={{ ...panelStyle("#ffffff"), border: `1px solid ${BORDER}` }}
    >
      {items.length === 0 ? (
        <p style={{ margin: 0, color: "#5c6b82", fontSize: 13, lineHeight: 1.6 }}>
          当前没有可用日历事件；供给与招标数据接入后会展示在这里。
        </p>
      ) : (
        <CalendarList items={items} />
      )}
    </SectionCard>
  );
}

export default BondEventCalendar;
