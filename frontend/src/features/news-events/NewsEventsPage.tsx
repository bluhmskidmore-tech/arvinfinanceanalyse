import { useMemo, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../api/client";
import { designTokens } from "../../theme/designSystem";
import { displayTokens } from "../../theme/displayTokens";
import { FilterBar } from "../../components/FilterBar";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { listChoiceNewsTopicFilterOptions } from "../agent/lib/choiceNewsTopicDictionary";
import { KpiCard } from "../workbench/components/KpiCard";

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

const summaryGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
};

const filterGrid: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
  width: "100%",
};

const sectionLeadWrapStyle: CSSProperties = {
  display: "grid",
  gap: 6,
  marginTop: 28,
};

const sectionEyebrowStyle: CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#8090a8",
};

const sectionTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: "#162033",
};

const sectionDescriptionStyle: CSSProperties = {
  margin: 0,
  maxWidth: 860,
  color: "#5c6b82",
  fontSize: 13,
  lineHeight: 1.7,
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
    return event.error_msg || "供应商回调返回了空错误信封。";
  }
  return "空回调信封。";
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

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
  );
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

  const events = useMemo(
    () => eventsQuery.data?.result.events ?? [],
    [eventsQuery.data?.result.events],
  );
  const totalRows = eventsQuery.data?.result.total_rows ?? 0;
  const isEmpty =
    !eventsQuery.isLoading &&
    !eventsQuery.isError &&
    events.length === 0;
  const errorRowsOnPage = useMemo(
    () => events.filter((event) => event.error_code !== 0).length,
    [events],
  );
  const activeTopicLabel = topicCode || "全部专题";
  const pageLabel = `${currentPage(offset, NEWS_EVENTS_PAGE_SIZE)} / ${totalPages(totalRows, NEWS_EVENTS_PAGE_SIZE)}`;

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
            data-testid="news-events-page-title"
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
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "8px 12px",
            borderRadius: 999,
            background:
              client.mode === "real" ? designTokens.color.success[50] : designTokens.color.primary[50],
            color:
              client.mode === "real"
                ? displayTokens.apiMode.realForeground
                : displayTokens.apiMode.mockForeground,
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          {client.mode === "real" ? "真实只读链路" : "本地演示数据"}
        </span>
      </div>

      <SectionLead
        eyebrow="总览"
        title="事件概览"
        description="先看事件总数、当前页和错误行，再进入筛选与明细列表，保持新闻事件页的阅读顺序和其他标准壳层一致。"
      />
      <div style={summaryGridStyle}>
        <div data-testid="news-events-total-count">
          <KpiCard title="事件总数" value={String(totalRows)} detail="当前查询返回的总行数" valueVariant="text" />
        </div>
        <div data-testid="news-events-current-page-kpi">
          <KpiCard title="当前页" value={pageLabel} detail="按固定分页窗口展示" valueVariant="text" />
        </div>
        <div data-testid="news-events-error-count">
          <KpiCard title="错误行数" value={String(errorRowsOnPage)} detail="当前页 error_code != 0" valueVariant="text" />
        </div>
        <div data-testid="news-events-active-topic">
          <KpiCard title="当前专题" value={activeTopicLabel} detail="切换专题后分页会自动归零" valueVariant="text" />
        </div>
      </div>

      <SectionLead
        eyebrow="浏览"
        title="筛选与事件列表"
        description="筛选条只控制 `topic_code`、错误开关与分页，不改变后端事件契约；下方表格继续显示服务端返回的事件流水。"
      />
      <section style={sectionShell}>
        <div style={sectionHeaderRow}>
          <span style={{ fontWeight: 600 }}>事件列表</span>
        </div>

        <FilterBar style={{ marginBottom: 20 }}>
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
        </FilterBar>

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
