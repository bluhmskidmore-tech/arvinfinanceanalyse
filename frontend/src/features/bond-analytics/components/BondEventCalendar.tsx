import type { CalendarItem } from "../../../components/CalendarList";
import { CalendarList } from "../../../components/CalendarList";
import { SectionCard } from "../../../components/SectionCard";
import { BORDER, panelStyle } from "./bondAnalyticsCockpitTokens";

const EVENTS: CalendarItem[] = [
  {
    date: "03-05",
    event: "政策性金融债招标",
    amount: "提配 420 亿",
    level: "high",
    note: "发行节奏",
  },
  {
    date: "03-08",
    event: "同业存单到期集中",
    amount: "提配 256 亿",
    level: "medium",
    note: "流动性",
  },
  {
    date: "03-10",
    event: "美国非农与美债拍卖",
    amount: "海外扰动",
    level: "high",
    note: "利率敏感",
  },
  {
    date: "03-12",
    event: "CPI 数据公布",
    amount: "通胀观察",
    level: "medium",
    note: "曲线形态",
  },
  {
    date: "03-15",
    event: "2 只信用债评级调整",
    amount: "信用事件",
    level: "high",
    note: "持仓复核",
  },
];

export function BondEventCalendar() {
  return (
    <SectionCard
      title="关键事件与日历（未来两周）"
      style={{ ...panelStyle("#ffffff"), border: `1px solid ${BORDER}` }}
    >
      <CalendarList items={EVENTS} />
    </SectionCard>
  );
}

export default BondEventCalendar;
