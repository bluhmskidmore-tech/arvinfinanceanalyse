import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Spin, Tabs } from "antd";

import { useApiClient } from "../../../api/client";
import type { ChoiceNewsEvent } from "../../../api/contracts";
import { CalendarList, type CalendarItem } from "../../../components/CalendarList";

import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

const MOCK_HEADLINES: { time: string; title: string }[] = [
  { time: "10:15", title: "【资讯】资金面延续宽松，隔夜回购加权小幅下行。" },
  { time: "09:48", title: "【观察】5 月金融数据公布在即，关注信贷结构。" },
  { time: "09:30", title: "【债券】国开行招标需求尚可，中长端情绪偏稳。" },
];

const MOCK_CALENDAR: CalendarItem[] = [
  { date: "04-15", event: "MLF 续作窗口", amount: "—", level: "high", note: "关注利率信号" },
  { date: "04-16", event: "美国零售销售", amount: "—", level: "medium", note: "外溢至美债" },
  { date: "04-17", event: "国新办发布会", amount: "—", level: "low", note: "政策沟通" },
  { date: "04-18", event: "缴税走款高峰", amount: "—", level: "medium", note: "流动性" },
];

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

export function NewsAndCalendar() {
  const client = useApiClient();
  const newsQuery = useQuery({
    queryKey: ["market-data", "headlines", "choice-events", client.mode],
    queryFn: () => client.getChoiceNewsEvents({ limit: 12, offset: 0 }),
    retry: false,
  });

  const headlines = useMemo(() => {
    const events = newsQuery.data?.result.events ?? [];
    if (events.length === 0) {
      return MOCK_HEADLINES;
    }
    return events.map((e) => ({
      time: formatReceivedTime(e.received_at),
      title: summarizeNewsLine(e),
    }));
  }, [newsQuery.data?.result.events]);

  return (
    <section data-testid="market-data-news-calendar" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>资讯与日历</h2>
      <Tabs
        size="small"
        items={[
          {
            key: "news",
            label: "资讯",
            children: (
              <div style={{ minHeight: 200 }}>
                {newsQuery.isLoading ? (
                  <div style={{ padding: 24, textAlign: "center" }}>
                    <Spin />
                  </div>
                ) : (
                  <ul
                    style={{
                      margin: 0,
                      padding: "0 0 0 18px",
                      display: "grid",
                      gap: 10,
                      fontSize: 13,
                      color: "#162033",
                      lineHeight: 1.55,
                    }}
                  >
                    {headlines.map((row, idx) => (
                      <li key={`${row.time}-${idx}`}>
                        <span style={{ fontVariantNumeric: "tabular-nums", color: "#5c6b82", marginRight: 8 }}>
                          {row.time}
                        </span>
                        {row.title}
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
              <div style={{ maxHeight: 320, overflow: "auto" }}>
                <CalendarList items={MOCK_CALENDAR} />
              </div>
            ),
          },
        ]}
      />
    </section>
  );
}
