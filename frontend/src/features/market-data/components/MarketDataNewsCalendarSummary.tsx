import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "antd";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/clientContext";
import type { ResearchCalendarEvent } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { useLazyMount } from "../lib/useLazyMount";
import { MarketDataSeriesCategoryCard } from "./MarketDataSeriesCategoryCard";

/** PAGE-MKT-001 §C NewsAndCalendar：驾驶舱只保留最近 3 条事件摘要，完整内容在新闻事件页。 */
const NEWS_CALENDAR_EVENT_LIMIT = 3;

/** 本卡口径为利率/供给相关事件；internal（内部事项）不属于该口径。 */
const RATE_SUPPLY_KINDS: ReadonlySet<ResearchCalendarEvent["kind"]> = new Set([
  "macro",
  "supply",
  "auction",
]);

const KIND_LABELS: Record<ResearchCalendarEvent["kind"], string> = {
  macro: "宏观",
  supply: "供给面",
  auction: "发行/招标",
  internal: "内部",
};

function selectRecentRateSupplyEvents(
  events: readonly ResearchCalendarEvent[],
): ResearchCalendarEvent[] {
  return events
    .filter((event) => RATE_SUPPLY_KINDS.has(event.kind))
    .slice()
    .sort((left, right) => right.date.localeCompare(left.date))
    .slice(0, NEWS_CALENDAR_EVENT_LIMIT);
}

type MarketDataNewsCalendarSummaryProps = {
  /** 页面数据日（观察日或联动报告日），作为日历查询的报告日锚点；为空时不发请求。 */
  reportDate: string;
};

export function MarketDataNewsCalendarSummary({ reportDate }: MarketDataNewsCalendarSummaryProps) {
  const client = useApiClient();
  // 与页面 lazyExtended/lazySupplementary 一致：接近视口才启用查询；卡壳与契约 testid 常驻 DOM。
  const lazy = useLazyMount({ rootMargin: "300px", fallbackDelayMs: 0 });
  const eventsQuery = useQuery({
    // 与 cross-asset 同一客户端方法与参数形态；该方法返回纯事件数组（envelope 的
    // result_meta 已在客户端被剥离），读不到 stale/quality 语义，改以底部
    // "截至 {reportDate}" 常驻标注让数据新鲜度可自证（行内日期同样可见）。
    queryKey: ["market-data", "news-calendar-summary", client.mode, reportDate],
    queryFn: () => client.getResearchCalendarEvents({ reportDate }),
    enabled: lazy.shouldMount && Boolean(reportDate),
    retry: false,
  });
  const rows = useMemo(
    () => selectRecentRateSupplyEvents(eventsQuery.data ?? []),
    [eventsQuery.data],
  );
  const showEmpty = eventsQuery.isSuccess && rows.length === 0;
  const showRows = eventsQuery.isSuccess && rows.length > 0;

  // 行样式复用既有 fx-event 紧凑事件行皮肤：页面 CSS ratchet 已无新增预算（4705 行上限）。
  return (
    <div ref={lazy.ref} data-lazy-mount="news-calendar-summary">
      <MarketDataSeriesCategoryCard
        title="资讯与日历"
        caption="分析口径 · 最近 3 条利率/供给相关事件，不作为正式市场结论。"
        tone="analytical"
        showLinkTierTag={false}
        count={showRows ? rows.length : undefined}
        testId="market-data-news-calendar-summary"
      >
        <div className="market-data-stack-gap-3">
          {eventsQuery.isError ? (
            <div
              className="market-data-terminal-empty"
              data-testid="market-data-news-calendar-error"
            >
              <span>资讯与日历读取失败。</span>
              <div>
                <Button size="small" onClick={() => void eventsQuery.refetch()}>
                  重试
                </Button>
              </div>
            </div>
          ) : showEmpty ? (
            <div
              className="market-data-terminal-empty"
              data-testid="market-data-news-calendar-empty"
            >
              暂无覆盖事件
            </div>
          ) : showRows ? (
            <div className="market-data-fx-event-list" data-testid="market-data-news-calendar-list">
              {rows.map((event) => (
                <article
                  key={event.id}
                  className="market-data-fx-event-item"
                  data-testid="market-data-news-calendar-item"
                >
                  {/* 契约"每条一行"：日期 + 事件名 + 类别（必要状态），金额标签有则跟随。 */}
                  <div className="market-data-fx-event-item__meta">
                    <span>{event.date.trim() || EM_DASH}</span>
                    <span className="market-data-fx-event-item__title">
                      {event.title.trim() || EM_DASH}
                    </span>
                    <span className="market-data-fx-event-item__currency">
                      {KIND_LABELS[event.kind]}
                    </span>
                    {event.amount_label?.trim() ? <span>{event.amount_label.trim()}</span> : null}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div
              className="market-data-rail-skeleton"
              data-testid="market-data-news-calendar-loading"
              aria-hidden="true"
            >
              <div className="market-data-rail-skeleton-item" />
              <div className="market-data-rail-skeleton-item" />
              <div className="market-data-rail-skeleton-item" />
            </div>
          )}
          <div className="market-data-catalog-meta">
            {eventsQuery.isSuccess && reportDate ? (
              <span data-testid="market-data-news-calendar-asof">截至 {reportDate} · </span>
            ) : null}
            <Link to="/news-events" data-testid="market-data-news-calendar-link">
              完整日历见新闻事件页
            </Link>
          </div>
        </div>
      </MarketDataSeriesCategoryCard>
    </div>
  );
}
