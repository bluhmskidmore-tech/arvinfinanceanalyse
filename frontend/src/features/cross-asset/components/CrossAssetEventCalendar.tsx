import type { CalendarItem } from "../../../components/CalendarList";
import { CalendarList } from "../../../components/CalendarList";
import { EvidencePanel } from "../../../components/page/PagePrimitives";
import { designTokens } from "../../../theme/designSystem";

const t = designTokens;

export type CrossAssetEventCalendarProps = {
  items: CalendarItem[];
};

export function CrossAssetEventCalendar({ items }: CrossAssetEventCalendarProps) {
  return (
    <div data-testid="cross-asset-event-calendar">
      <EvidencePanel heading="事件与风险线索">
        {items.length === 0 ? (
          <p
            style={{
              margin: 0,
              color: "var(--dh-api-muted)",
              fontSize: t.fontSize[13],
              lineHeight: t.lineHeight.normal,
            }}
          >
            当前没有可用事件流；这里只保留数据驱动结果，不再展示静态示例日历。
          </p>
        ) : (
          <div className="cross-asset-event-calendar__table">
            <div className="cross-asset-event-calendar__head" aria-hidden="true">
              <span>日期</span>
              <span>事件</span>
              <span>规模</span>
              <span>级别</span>
              <span>说明</span>
            </div>
            <CalendarList items={items} />
          </div>
        )}
      </EvidencePanel>
    </div>
  );
}
