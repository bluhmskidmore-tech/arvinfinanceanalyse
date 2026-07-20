import type { CalendarItem } from "../../../components/CalendarList";
import { CalendarList } from "../../../components/CalendarList";
import { EvidencePanel, PageStateSurface } from "../../../components/page/PagePrimitives";

export type BondEventCalendarProps = {
  items: CalendarItem[];
};

export function BondEventCalendar({ items }: BondEventCalendarProps) {
  return (
    <EvidencePanel heading="关键事件与日历（未来两周）">
      {items.length === 0 ? (
        <PageStateSurface
          variant="empty"
          description="当前没有可用日历事件；供给与招标数据接入后会展示在这里。"
        />
      ) : (
        <CalendarList items={items} />
      )}
    </EvidencePanel>
  );
}

export default BondEventCalendar;
