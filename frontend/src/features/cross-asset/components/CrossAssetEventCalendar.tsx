import type { CalendarItem } from "../../../components/CalendarList";
import { CalendarList } from "../../../components/CalendarList";
import { SectionCard } from "../../../components/SectionCard";

const EVENTS: CalendarItem[] = [
  {
    date: "03-05",
    event: "国债招标",
    amount: "可能压制长端",
    level: "high",
    note: "供给",
  },
  {
    date: "03-08",
    event: "同业存单到期集中",
    amount: "短期关注",
    level: "medium",
    note: "流动性",
  },
  {
    date: "03-10",
    event: "美国非农",
    amount: "影响美债反应",
    level: "high",
    note: "海外利率",
  },
  {
    date: "03-12",
    event: "CPI 数据",
    amount: "关注通胀",
    level: "medium",
    note: "曲线",
  },
];

export function CrossAssetEventCalendar() {
  return (
    <SectionCard title="事件与供给日历">
      <CalendarList items={EVENTS} />
    </SectionCard>
  );
}
