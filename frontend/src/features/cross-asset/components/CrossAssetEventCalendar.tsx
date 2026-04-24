import type { CalendarItem } from "../../../components/CalendarList";
import { CalendarList } from "../../../components/CalendarList";
import { SectionCard } from "../../../components/SectionCard";

export type CrossAssetEventCalendarProps = {
  items: CalendarItem[];
};

export function CrossAssetEventCalendar({ items }: CrossAssetEventCalendarProps) {
  return (
    <div data-testid="cross-asset-event-calendar">
      <SectionCard title="事件与风险线索">
        {items.length === 0 ? (
          <p style={{ margin: 0, color: "#5c6b82", fontSize: 13, lineHeight: 1.6 }}>
            当前没有可用事件流；这里只保留数据驱动结果，不再展示静态示例日历。
          </p>
        ) : (
          <CalendarList items={items} />
        )}
      </SectionCard>
    </div>
  );
}
