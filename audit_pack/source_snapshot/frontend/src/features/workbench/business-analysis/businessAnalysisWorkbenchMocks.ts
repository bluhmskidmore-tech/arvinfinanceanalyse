import type { AlertItem } from "../../../components/AlertList";
import type { CalendarItem } from "../../../components/CalendarList";

export const OPERATIONS_WATCH_ITEMS: AlertItem[] = [
  {
    level: "danger",
    title: "4月短端缺口压力较大",
    detail: "1年内缺口对负债占比仍处高位，需跟踪滚续与定价。",
  },
  {
    level: "warning",
    title: "发行负债集中度偏高",
    detail: "CD 占发行类负债约八成，结构弹性有限。",
  },
  {
    level: "caution",
    title: "短端缺口已覆盖率 81.8%",
    detail: "覆盖率改善但仍有尾部情景需压力测试。",
  },
  {
    level: "info",
    title: "异常资产跟踪",
    detail: "按正式读面异常资产清单持续跟踪。",
  },
];

export const OPERATIONS_CALENDAR_MOCK: CalendarItem[] = [
  {
    date: "04-18",
    event: "大额同业负债到期",
    amount: "180亿",
    level: "high",
    note: "提前确认滚续额度",
  },
  {
    date: "04-22",
    event: "同业存单集中缴款",
    amount: "95亿",
    level: "medium",
    note: "关注发行利差",
  },
  {
    date: "04-28",
    event: "月内缺口复盘会",
    amount: "—",
    level: "low",
    note: "财务与资金条线",
  },
];
