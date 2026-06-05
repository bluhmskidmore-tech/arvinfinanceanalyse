import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Spin, Tabs } from "antd";

import { useApiClient } from "../../../api/client";
import type { ChoiceNewsEvent } from "../../../api/contracts";

import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

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

const emptyHintStyle = {
  margin: 0,
  padding: `${designTokens.space[4]}px ${designTokens.space[1]}px`,
  color: designTokens.color.neutral[600],
  fontSize: designTokens.fontSize[13],
  lineHeight: designTokens.lineHeight.normal,
} as const;

export function NewsAndCalendar() {
  const client = useApiClient();
  const newsQuery = useQuery({
    queryKey: ["market-data", "headlines", "choice-events", client.mode],
    queryFn: () => client.getChoiceNewsEvents({ limit: 12, offset: 0 }),
    retry: false,
  });

  const headlineRows = useMemo(() => {
    const events = newsQuery.data?.result.events ?? [];
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
                  <div style={{ padding: designTokens.space[6], textAlign: "center" }}>
                    <Spin />
                  </div>
                ) : newsQuery.isError ? (
                  <p style={emptyHintStyle}>资讯加载失败，请稍后重试。</p>
                ) : headlineRows.length === 0 ? (
                  <p style={emptyHintStyle}>当前无资讯事件，请确认数据源或稍后刷新。</p>
                ) : (
                  <ul
                    style={{
                      margin: 0,
                      padding: `0 0 0 ${designTokens.space[5]}px`,
                      display: "grid",
                      gap: designTokens.space[3],
                      fontSize: designTokens.fontSize[13],
                      color: designTokens.color.neutral[900],
                      lineHeight: designTokens.lineHeight.normal,
                    }}
                  >
                    {headlineRows.map((row, idx) => (
                      <li key={`${row.time}-${idx}`}>
                        <span
                          style={{
                            ...tabularNumsStyle,
                            color: designTokens.color.neutral[600],
                            marginRight: designTokens.space[2],
                          }}
                        >
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
                <p style={emptyHintStyle}>
                  事件日历尚未接入本页专用接口；此处不展示示例日程，待后端日历读面就绪后再渲染列表。
                </p>
              </div>
            ),
          },
        ]}
      />
    </section>
  );
}
