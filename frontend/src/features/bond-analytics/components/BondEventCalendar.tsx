import { useMemo } from "react";

import type { CalendarItem } from "../../../components/CalendarList";
import { CalendarList } from "../../../components/CalendarList";
import { EvidencePanel, PageStateSurface } from "../../../components/page/PagePrimitives";

export type BondEventCalendarProps = {
  items: CalendarItem[];
  isLoading?: boolean;
  hasError?: boolean;
};

/**
 * 说明列 `·` 配额收敛（DESIGN §7 单行最多 1 个）：note 内的 ` · ` 连接改分号，
 * 把该列的 `·` 配额留给来源链接行（「xxx · 打开原文」）。仅展示层清洗，字段语义不变。
 */
function condenseNoteSeparators(items: CalendarItem[]): CalendarItem[] {
  return items.map((item) =>
    item.note && item.note.includes("·")
      ? { ...item, note: item.note.replace(/\s*·\s*/g, "；") }
      : item,
  );
}

/**
 * 区头口径：数据源 `GET /ui/calendar/supply-auctions` 以报告日为 end_date 取历史事件
 * （marketDataClient.getResearchCalendarEvents 将 reportDate 作为 end_date），并非未来窗口；
 * 原「未来两周」承诺与数据矛盾，改按事件最大日期动态标注「数据截至 MM-DD」。
 */
function buildCalendarHeading(items: CalendarItem[]): string {
  const latest = items.reduce(
    (max, item) => (/^\d{2}-\d{2}$/.test(item.date) && item.date > max ? item.date : max),
    "",
  );
  return latest ? `近期事件（数据截至 ${latest}）` : "近期事件";
}

export function BondEventCalendar({ items, isLoading = false, hasError = false }: BondEventCalendarProps) {
  const displayItems = useMemo(() => condenseNoteSeparators(items), [items]);
  const heading = buildCalendarHeading(displayItems);

  return (
    <EvidencePanel heading={heading}>
      {displayItems.length > 0 ? (
        <CalendarList items={displayItems} />
      ) : hasError ? (
        <PageStateSurface
          variant="error"
          description="日历事件读取失败，本次未能确认是否存在事件。"
        />
      ) : isLoading ? (
        <PageStateSurface variant="loading" description="日历事件读取中。" />
      ) : (
        <PageStateSurface
          variant="empty"
          description="当前没有可用日历事件；供给与招标数据接入后会展示在这里。"
        />
      )}
    </EvidencePanel>
  );
}

export default BondEventCalendar;
