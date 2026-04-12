import { useMemo, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../api/client";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { listChoiceNewsTopicFilterOptions } from "../agent/lib/choiceNewsTopicDictionary";

const NEWS_EVENTS_PAGE_SIZE = 50;

const sectionShell: CSSProperties = {
  height: "100%",
  padding: 24,
  borderRadius: 20,
  background: "#fbfcfe",
  border: "1px solid #e4ebf5",
  boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
};

const sectionHeaderRow: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
  marginBottom: 16,
};

const pagerRow: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  marginTop: 14,
};

const filterGrid: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
  marginBottom: 20,
};

function summarizeNewsPayload(event: {
  payload_text: string | null;
  payload_json: string | null;
  error_code: number;
  error_msg: string;
}) {
  if (event.payload_text?.trim()) {
    return event.payload_text;
  }
  if (event.payload_json?.trim()) {
    return event.payload_json;
  }
  if (event.error_code !== 0) {
    return event.error_msg || "Vendor callback returned an empty error envelope.";
  }
  return "Empty callback envelope.";
}

function clampOffset(offset: number) {
  return Math.max(0, offset);
}

function pagerDisabled(offset: number, pageSize: number, totalRows: number) {
  return offset + pageSize >= totalRows;
}

function currentPage(offset: number, pageSize: number) {
  return Math.floor(offset / pageSize) + 1;
}

function totalPages(totalRows: number, pageSize: number) {
  return Math.max(1, Math.ceil(totalRows / pageSize));
}

export default function NewsEventsPage() {
  const client = useApiClient();
  const topicOptions = useMemo(() => listChoiceNewsTopicFilterOptions(), []);
  const [topicCode, setTopicCode] = useState("");
  const [errorOnly, setErrorOnly] = useState(false);
  const [offset, setOffset] = useState(0);

  const eventsQuery = useQuery({
    queryKey: [
      "news-events",
      "choice-events",
      client.mode,
      topicCode,
      errorOnly,
      offset,
    ],
    queryFn: () =>
      client.getChoiceNewsEvents({
        limit: NEWS_EVENTS_PAGE_SIZE,
        offset,
        topicCode: topicCode.trim() || undefined,
        errorOnly,
      }),
    retry: false,
  });

  const events = eventsQuery.data?.result.events ?? [];
  const totalRows = eventsQuery.data?.result.total_rows ?? 0;
  const isEmpty =
    !eventsQuery.isLoading &&
    !eventsQuery.isError &&
    events.length === 0;

  return (
    <section>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <div>
          <h1
            style={{
              marginTop: 0,
              marginBottom: 10,
              fontSize: 32,
              fontWeight: 600,
              letterSpacing: "-0.03em",
            }}
          >
            新闻事件
          </h1>
          <p
            style={{
              marginTop: 0,
              marginBottom: 0,
              color: "#5c6b82",
              fontSize: 15,
              lineHeight: 1.75,
            }}
          >
            查看 Choice 新闻回调事件流水，可按专题与错误筛选，数据来自服务端最新事件接口。
          </p>
        </div>
      </div>

      <section style={sectionShell}>
        <div style={sectionHeaderRow}>
          <span style={{ fontWeight: 600 }}>事件列表</span>
        </div>

        <div style={filterGrid}>
          <label style={{ display: "grid", gap: 8 }}>
            <span>专题 (topic_code)</span>
            <select
              aria-label="news-events-topic-code"
              value={topicCode}
              onChange={(e) => {
                setTopicCode(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">全部</option>
              {topicOptions.map((opt) => (
                <option key={opt.topicCode} value={opt.topicCode}>
                  {opt.label} ({opt.topicCode})
                </option>
              ))}
            </select>
          </label>
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginTop: 24,
            }}
          >
            <input
              type="checkbox"
              aria-label="news-events-error-only"
              checked={errorOnly}
              onChange={(e) => {
                setErrorOnly(e.target.checked);
                setOffset(0);
              }}
            />
            <span>仅错误 (error_only)</span>
          </label>
        </div>

        <AsyncSection
          title="新闻事件"
          isLoading={eventsQuery.isLoading}
          isError={eventsQuery.isError}
          isEmpty={isEmpty}
          onRetry={() => void eventsQuery.refetch()}
        >
          <div style={{ overflowX: "auto" }}>
            <table
              data-testid="news-events-table"
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: 13,
              }}
            >
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "1px solid #d7dfea" }}>
                  <th
                    scope="col"
                    style={{
                      padding: "10px 8px",
                      whiteSpace: "nowrap",
                      color: "#5c6b82",
                      fontWeight: 600,
                    }}
                  >
                    received_at
                  </th>
                  <th
                    scope="col"
                    style={{
                      padding: "10px 8px",
                      whiteSpace: "nowrap",
                      color: "#5c6b82",
                      fontWeight: 600,
                    }}
                  >
                    topic_code
                  </th>
                  <th
                    scope="col"
                    style={{
                      padding: "10px 8px",
                      whiteSpace: "nowrap",
                      color: "#5c6b82",
                      fontWeight: 600,
                    }}
                  >
                    group_id
                  </th>
                  <th
                    scope="col"
                    style={{
                      padding: "10px 8px",
                      color: "#5c6b82",
                      fontWeight: 600,
                    }}
                  >
                    内容摘要
                  </th>
                  <th
                    scope="col"
                    style={{
                      padding: "10px 8px",
                      whiteSpace: "nowrap",
                      color: "#5c6b82",
                      fontWeight: 600,
                    }}
                  >
                    error_code
                  </th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => {
                  const isErrorRow = event.error_code !== 0;
                  return (
                    <tr
                      key={event.event_key}
                      style={{
                        borderBottom: "1px solid #e4ebf5",
                        background: isErrorRow ? "#fff0f0" : undefined,
                      }}
                    >
                      <td
                        style={{
                          padding: "10px 8px",
                          verticalAlign: "top",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {event.received_at}
                      </td>
                      <td
                        style={{
                          padding: "10px 8px",
                          verticalAlign: "top",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {event.topic_code}
                      </td>
                      <td
                        style={{
                          padding: "10px 8px",
                          verticalAlign: "top",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {event.group_id}
                      </td>
                      <td
                        style={{
                          padding: "10px 8px",
                          verticalAlign: "top",
                          whiteSpace: "normal",
                          wordBreak: "break-word",
                          maxWidth: 480,
                        }}
                      >
                        {summarizeNewsPayload(event)}
                      </td>
                      <td
                        style={{
                          padding: "10px 8px",
                          verticalAlign: "top",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {event.error_code}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div style={pagerRow}>
            <button
              type="button"
              data-testid="news-events-prev"
              disabled={offset === 0}
              onClick={() =>
                setOffset((current) =>
                  clampOffset(current - NEWS_EVENTS_PAGE_SIZE),
                )
              }
            >
              上一页
            </button>
            <button
              type="button"
              data-testid="news-events-next"
              disabled={pagerDisabled(
                offset,
                NEWS_EVENTS_PAGE_SIZE,
                totalRows,
              )}
              onClick={() =>
                setOffset((current) => current + NEWS_EVENTS_PAGE_SIZE)
              }
            >
              下一页
            </button>
            <span data-testid="news-events-page">
              {currentPage(offset, NEWS_EVENTS_PAGE_SIZE)} /{" "}
              {totalPages(totalRows, NEWS_EVENTS_PAGE_SIZE)}
            </span>
            <span data-testid="news-events-total">事件数 {totalRows}</span>
          </div>
        </AsyncSection>
      </section>
    </section>
  );
}
