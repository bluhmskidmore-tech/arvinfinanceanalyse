import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Spin, Tabs } from "antd";

import { useApiClient } from "../../../api/client";
import { externalDataQueryOptions } from "../../../app/externalDataRefreshPolicy";
import type { ChoiceNewsEvent, ChoiceNewsEventsPayload, ResearchCalendarEvent } from "../../../api/contracts";

import { tabularNumsStyle } from "../../../theme/designSystem";

export type NewsAndCalendarCalendarState = {
  rows: readonly ResearchCalendarEvent[];
  isLoading: boolean;
  isError: boolean;
};

export type NewsAndCalendarNewsState = {
  payload: ChoiceNewsEventsPayload | null;
  isLoading: boolean;
  isError: boolean;
};

function summarizeNewsLine(event: ChoiceNewsEvent) {
  if (event.payload_text?.trim()) {
    return event.payload_text.trim();
  }
  if (event.payload_json?.trim()) {
    return event.payload_json.trim();
  }
  if (event.error_code !== 0) {
    return event.error_msg || "回调空包";
  }
  return "（空内容）";
}

function formatReceivedTime(iso: string) {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) {
      return iso.slice(11, 16) || "—";
    }
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
  } catch {
    return "—";
  }
}

function calendarKindLabel(kind: ResearchCalendarEvent["kind"]) {
  if (kind === "supply") return "供给";
  if (kind === "auction") return "招标";
  if (kind === "macro") return "宏观";
  return "内部";
}

function calendarSeverityLabel(severity: ResearchCalendarEvent["severity"]) {
  if (severity === "high") return "高";
  if (severity === "medium") return "中";
  return "低";
}

export function NewsAndCalendar({
  calendarState,
  newsState,
}: {
  calendarState?: NewsAndCalendarCalendarState;
  newsState?: NewsAndCalendarNewsState;
} = {}) {
  const client = useApiClient();
  const newsQuery = useQuery({
    queryKey: ["market-data", "headlines", "choice-events", client.mode],
    queryFn: () => client.getChoiceNewsEvents({ limit: 12, offset: 0 }),
    retry: false,
    enabled: !newsState,
    ...externalDataQueryOptions({ refresh_tier: "stable", fetch_mode: "date_slice" }),
  });

  const calendarQuery = useQuery({
    queryKey: ["market-data", "calendar", "supply-auctions", client.mode],
    queryFn: () => client.getResearchCalendarEvents({}),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "stable", fetch_mode: "date_slice" }),
    enabled: !calendarState,
  });

  const newsPayload = newsState?.payload ?? newsQuery.data?.result ?? null;
  const newsIsLoading = newsState?.isLoading ?? newsQuery.isLoading;
  const newsIsError = newsState?.isError ?? newsQuery.isError;
  const headlineRows = useMemo(() => {
    const events = newsPayload?.events ?? [];
    return events.map((e) => ({
      time: formatReceivedTime(e.received_at),
      title: summarizeNewsLine(e),
    }));
  }, [newsPayload?.events]);

  const calendarRows = useMemo(() => {
    const rows = calendarState?.rows ?? calendarQuery.data ?? [];
    return [...rows].sort((a, b) => a.date.localeCompare(b.date) || a.title.localeCompare(b.title));
  }, [calendarQuery.data, calendarState?.rows]);
  const calendarIsLoading = calendarState?.isLoading ?? calendarQuery.isLoading;
  const calendarIsError = calendarState?.isError ?? calendarQuery.isError;

  return (
    <section
      data-testid="market-data-news-calendar"
      className="market-data-news-calendar-section market-data-lower-deck-panel"
    >
      <header className="market-data-news-calendar-head">
        <div>
          <span className="market-data-supplementary-kicker">终端读面</span>
          <h2 className="market-data-supplementary-title">资讯与日历</h2>
          <p className="market-data-supplementary-summary">
            Choice 资讯头条与供给/招标研究日历；稳定链路，按观察日切片。
          </p>
        </div>
      </header>
      <Tabs
        className="market-data-news-calendar-tabs"
        size="small"
        items={[
          {
            key: "news",
            label: "资讯",
            children: (
              <div className="market-data-news-calendar-pane">
                {newsIsLoading ? (
                  <div className="market-data-news-calendar-loading">
                    <Spin />
                  </div>
                ) : newsIsError ? (
                  <p className="market-data-news-calendar-empty">资讯加载失败，请稍后重试。</p>
                ) : headlineRows.length === 0 ? (
                  <p className="market-data-news-calendar-empty">当前无资讯事件，请确认数据源或稍后刷新。</p>
                ) : (
                  <ul className="market-data-news-calendar-list">
                    {headlineRows.map((row, idx) => (
                      <li key={`${row.time}-${idx}`} className="market-data-news-calendar-item">
                        <span className="market-data-news-calendar-item__time" style={tabularNumsStyle}>
                          {row.time}
                        </span>
                        <span className="market-data-news-calendar-item__title">{row.title}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ),
          },
          {
            key: "calendar",
            label: "事件日历",
            children: (
              <div className="market-data-news-calendar-pane market-data-news-calendar-pane--scroll">
                {calendarIsLoading ? (
                  <div
                    data-testid="market-data-calendar-loading"
                    className="market-data-news-calendar-loading"
                  >
                    <Spin />
                  </div>
                ) : calendarIsError ? (
                  <p data-testid="market-data-calendar-error" className="market-data-news-calendar-empty">
                    供给与招标日历加载失败，请稍后重试。
                  </p>
                ) : calendarRows.length === 0 ? (
                  <p data-testid="market-data-calendar-empty" className="market-data-news-calendar-empty">
                    当前日历区间无供给/招标事件。
                  </p>
                ) : (
                  <ul data-testid="market-data-calendar-list" className="market-data-news-calendar-list">
                    {calendarRows.map((ev) => (
                      <li key={ev.id} className="market-data-news-calendar-item market-data-news-calendar-item--event">
                        <div className="market-data-news-calendar-item__date" style={tabularNumsStyle}>
                          {ev.date}
                        </div>
                        <div className="market-data-news-calendar-item__title">{ev.title}</div>
                        <div className="market-data-news-calendar-item__meta">
                          类型 {calendarKindLabel(ev.kind)}
                          {ev.issuer ? ` · 来源 ${ev.issuer}` : ""}
                          {ev.note && !ev.issuer ? ` · ${ev.note}` : ""}
                          {ev.amount_label ? ` · ${ev.amount_label}` : ""}
                          {" · "}
                          影响 {calendarSeverityLabel(ev.severity)}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ),
          },
        ]}
      />
    </section>
  );
}
