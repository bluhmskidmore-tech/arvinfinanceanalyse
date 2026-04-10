import { useMemo, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ChoiceNewsEvent } from "../../../api/contracts";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { getChoiceNewsTopicPresentation } from "../lib/choiceNewsTopicDictionary";
import { PlaceholderCard } from "../../workbench/components/PlaceholderCard";

const PAGE_SIZE = 2;

type FilterState = {
  groupId: string;
  topicCode: string;
  receivedFrom: string;
  receivedTo: string;
  errorOnly: boolean;
};

const defaultFilters: FilterState = {
  groupId: "",
  topicCode: "",
  receivedFrom: "",
  receivedTo: "",
  errorOnly: false,
};

const sectionShell: CSSProperties = {
  padding: 24,
  borderRadius: 20,
  background: "#fbfcfe",
  border: "1px solid #e4ebf5",
  boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
};

const inputStyle: CSSProperties = {
  width: "100%",
  border: "1px solid #d7dfea",
  borderRadius: 12,
  padding: "10px 12px",
  fontSize: 14,
  color: "#162033",
  background: "#ffffff",
  boxSizing: "border-box",
};

const buttonStyle: CSSProperties = {
  border: "1px solid #d7dfea",
  background: "#ffffff",
  borderRadius: 12,
  padding: "10px 16px",
  color: "#162033",
  cursor: "pointer",
};

function summarizePayload(event: ChoiceNewsEvent) {
  if (event.payload_text?.trim()) {
    return event.payload_text;
  }
  if (event.payload_json?.trim()) {
    return event.payload_json;
  }
  if (event.error_code !== 0) {
    return event.error_msg || "Vendor callback returned an error envelope.";
  }
  return "Empty callback envelope.";
}

function buildEventTone(event: ChoiceNewsEvent) {
  return event.error_code === 0 ? "#1f5eff" : "#c2410c";
}

function buildErrorTone(event: ChoiceNewsEvent) {
  return event.topic_code === "__callback__" ? "#7c3aed" : "#c2410c";
}

function isVisibleSliceErrorEvent(event: ChoiceNewsEvent, isCallbackEnvelope: boolean) {
  return event.error_code !== 0 || isCallbackEnvelope;
}

export default function AgentPlaceholderPage() {
  const client = useApiClient();
  const [draftFilters, setDraftFilters] = useState<FilterState>(defaultFilters);
  const [appliedFilters, setAppliedFilters] = useState<FilterState>(defaultFilters);
  const [offset, setOffset] = useState(0);

  const newsQuery = useQuery({
    queryKey: [
      "choice-news-events",
      client.mode,
      appliedFilters.groupId,
      appliedFilters.topicCode,
      appliedFilters.receivedFrom,
      appliedFilters.receivedTo,
      appliedFilters.errorOnly,
      offset,
    ],
    queryFn: () =>
      client.getChoiceNewsEvents({
        limit: PAGE_SIZE,
        offset,
        groupId: appliedFilters.groupId || undefined,
        topicCode: appliedFilters.topicCode || undefined,
        errorOnly: appliedFilters.errorOnly,
        receivedFrom: appliedFilters.receivedFrom || undefined,
        receivedTo: appliedFilters.receivedTo || undefined,
      }),
    retry: false,
  });

  const result = newsQuery.data?.result;
  const meta = newsQuery.data?.result_meta;
  const events = useMemo(() => result?.events ?? [], [result?.events]);
  const totalRows = result?.total_rows ?? 0;
  const isEmpty = !newsQuery.isLoading && !newsQuery.isError && events.length === 0;
  const visibleEvents = useMemo(
    () =>
      events.map((event) => ({
        event,
        topicPresentation: getChoiceNewsTopicPresentation({
          groupId: event.group_id,
          topicCode: event.topic_code,
        }),
        isCallbackEnvelope: event.topic_code === "__callback__",
      })),
    [events],
  );
  const summary = useMemo(() => {
    const topicCount = new Set(visibleEvents.map(({ event }) => event.topic_code)).size;
    const errorCount = visibleEvents.filter(({ event, isCallbackEnvelope }) =>
      isVisibleSliceErrorEvent(event, isCallbackEnvelope),
    ).length;
    const callbackCount = visibleEvents.filter(({ isCallbackEnvelope }) => isCallbackEnvelope).length;

    return {
      pageCount: visibleEvents.length,
      topicCount,
      errorCount,
      callbackCount,
    };
  }, [visibleEvents]);
  const errorEvents = useMemo(
    () => visibleEvents.filter(({ event, isCallbackEnvelope }) => isVisibleSliceErrorEvent(event, isCallbackEnvelope)),
    [visibleEvents],
  );

  function applyFilters() {
    setOffset(0);
    setAppliedFilters(draftFilters);
  }

  function clearFilters() {
    setOffset(0);
    setDraftFilters(defaultFilters);
    setAppliedFilters(defaultFilters);
  }

  return (
    <section>
      <div
        style={{
          display: "grid",
          gap: 16,
          marginBottom: 28,
        }}
      >
        <span
          style={{
            display: "inline-flex",
            width: "fit-content",
            alignItems: "center",
            padding: "8px 12px",
            borderRadius: 999,
            background: "#edf3ff",
            color: "#1f5eff",
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          Analytical Only
        </span>
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: 34,
              fontWeight: 600,
              letterSpacing: "-0.03em",
            }}
          >
            新闻事件工作台
          </h1>
          <p
            style={{
              marginTop: 10,
              marginBottom: 0,
              maxWidth: 840,
              color: "#5c6b82",
              fontSize: 15,
              lineHeight: 1.75,
            }}
          >
            Choice news event feed backed by the DuckDB materialization path. This surface is
            analytical read-only, keeps callback anomalies visible, and does not touch any formal
            finance path.
          </p>
        </div>
      </div>

      <section style={sectionShell}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 16,
          }}
        >
          <label style={{ display: "grid", gap: 8 }}>
            <span>Group ID</span>
            <input
              aria-label="agent-news-group-id"
              type="text"
              value={draftFilters.groupId}
              onChange={(event) =>
                setDraftFilters((current) => ({ ...current, groupId: event.target.value }))
              }
              style={inputStyle}
            />
          </label>
          <label style={{ display: "grid", gap: 8 }}>
            <span>Topic code</span>
            <input
              aria-label="agent-news-topic-code"
              type="text"
              value={draftFilters.topicCode}
              onChange={(event) =>
                setDraftFilters((current) => ({ ...current, topicCode: event.target.value }))
              }
              style={inputStyle}
            />
          </label>
          <label style={{ display: "grid", gap: 8 }}>
            <span>Received from</span>
            <input
              aria-label="agent-news-received-from"
              type="text"
              placeholder="2026-04-10T08:00:00Z"
              value={draftFilters.receivedFrom}
              onChange={(event) =>
                setDraftFilters((current) => ({ ...current, receivedFrom: event.target.value }))
              }
              style={inputStyle}
            />
          </label>
          <label style={{ display: "grid", gap: 8 }}>
            <span>Received to</span>
            <input
              aria-label="agent-news-received-to"
              type="text"
              placeholder="2026-04-10T10:00:00Z"
              value={draftFilters.receivedTo}
              onChange={(event) =>
                setDraftFilters((current) => ({ ...current, receivedTo: event.target.value }))
              }
              style={inputStyle}
            />
          </label>
        </div>

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: 12,
            marginTop: 16,
          }}
        >
          <label
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              color: "#334155",
            }}
          >
            <input
              aria-label="agent-news-error-only"
              type="checkbox"
              checked={draftFilters.errorOnly}
              onChange={(event) =>
                setDraftFilters((current) => ({ ...current, errorOnly: event.target.checked }))
              }
            />
            Error events only
          </label>
          <button
            type="button"
            onClick={applyFilters}
            style={buttonStyle}
            data-testid="agent-news-apply-filters"
          >
            Apply filters
          </button>
          <button
            type="button"
            onClick={clearFilters}
            style={buttonStyle}
            data-testid="agent-news-clear-filters"
          >
            Clear
          </button>
          <span style={{ color: "#5c6b82", fontSize: 13 }}>
            Active query: {PAGE_SIZE} rows per page, {totalRows} matching rows available for
            pagination
          </span>
        </div>
      </section>

      <section
        style={{
          marginTop: 18,
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 16,
        }}
      >
        <div data-testid="agent-news-visible-events">
          <PlaceholderCard
            title="Visible page rows"
            value={String(summary.pageCount)}
            detail="Rows rendered from the visible page result.events slice."
          />
        </div>
        <div data-testid="agent-news-topic-count">
          <PlaceholderCard
            title="Visible page topics"
            value={String(summary.topicCount)}
            detail="Distinct topic codes present on the visible page slice."
          />
        </div>
        <div data-testid="agent-news-error-count">
          <PlaceholderCard
            title="Visible page error rows"
            value={String(summary.errorCount)}
            detail="Rows with non-zero error_code or callback anomalies in the visible page slice."
          />
        </div>
        <div data-testid="agent-news-callback-count">
          <PlaceholderCard
            title="Visible slice callback envelopes"
            value={String(summary.callbackCount)}
            detail="Visible slice rows where topic_code resolves to __callback__."
          />
        </div>
      </section>

      <section
        style={{
          marginTop: 18,
          display: "grid",
          gridTemplateColumns: "minmax(0, 2fr) minmax(280px, 1fr)",
          gap: 18,
        }}
      >
        <AsyncSection
          title="Choice news events"
          isLoading={newsQuery.isLoading}
          isError={newsQuery.isError}
          isEmpty={isEmpty}
          onRetry={() => void newsQuery.refetch()}
          extra={
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                style={buttonStyle}
                disabled={offset === 0}
                onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
                data-testid="agent-news-prev-page"
              >
                Prev
              </button>
              <button
                type="button"
                style={buttonStyle}
                disabled={offset + PAGE_SIZE >= totalRows}
                onClick={() => setOffset((current) => current + PAGE_SIZE)}
                data-testid="agent-news-next-page"
              >
                Next
              </button>
            </div>
          }
        >
          <div style={{ display: "grid", gap: 12 }} data-testid="agent-news-event-list">
            {visibleEvents.map(({ event, topicPresentation, isCallbackEnvelope }) => (
              <article
                key={event.event_key}
                data-testid={`agent-news-event-${event.event_key}`}
                style={{
                  padding: 16,
                  borderRadius: 16,
                  border: "1px solid #e4ebf5",
                  background: "#ffffff",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 12,
                    marginBottom: 10,
                  }}
                >
                  <div style={{ display: "grid", gap: 4 }}>
                    <strong>{topicPresentation.displayPair}</strong>
                    <span style={{ color: "#5c6b82", fontSize: 13 }}>
                      {event.received_at}
                    </span>
                  </div>
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      padding: "6px 10px",
                      borderRadius: 999,
                      background: "#f8fafc",
                      color: buildEventTone(event),
                      fontSize: 12,
                      fontWeight: 600,
                    }}
                  >
                    {event.error_code === 0 ? "OK" : `ERR ${event.error_code}`}
                  </span>
                </div>
                <div style={{ color: "#162033", lineHeight: 1.6 }}>{summarizePayload(event)}</div>
                <div
                  style={{
                    marginTop: 10,
                    color: "#5c6b82",
                    fontSize: 12,
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 12,
                  }}
                >
                  <span>group_id {event.group_id}</span>
                  <span>topic_code {event.topic_code}</span>
                  {topicPresentation.usesFallback ? (
                    <span>visible fallback raw group_id/topic_code</span>
                  ) : (
                    <span>mapped via canonical topic dictionary</span>
                  )}
                  {isCallbackEnvelope ? <span>callback envelope</span> : null}
                  <span>event_key {event.event_key}</span>
                  <span>serial {event.serial_id}</span>
                  <span>request {event.request_id}</span>
                  <span>item {event.item_index}</span>
                </div>
              </article>
            ))}
          </div>
        </AsyncSection>

        <div style={{ display: "grid", gap: 18 }}>
          <section style={sectionShell}>
            <div
              style={{
                display: "grid",
                gap: 10,
              }}
            >
              <h2
                style={{
                  margin: 0,
                  fontSize: 18,
                  fontWeight: 600,
                }}
              >
                Result metadata
              </h2>
              <div style={{ color: "#5c6b82", fontSize: 14, lineHeight: 1.6 }}>
                <div>basis: {meta?.basis ?? "pending"}</div>
                <div>result kind: {meta?.result_kind ?? "pending"}</div>
                <div>source version: {meta?.source_version ?? "pending"}</div>
                <div>rule version: {meta?.rule_version ?? "pending"}</div>
                <div>generated at: {meta?.generated_at ?? "pending"}</div>
              </div>
              <div
                style={{
                  marginTop: 8,
                  padding: 14,
                  borderRadius: 14,
                  background: "#ffffff",
                  border: "1px solid #e4ebf5",
                  color: "#5c6b82",
                  fontSize: 13,
                  lineHeight: 1.7,
                }}
              >
                This page reads from the analytical Choice news event surface only. It does not
                change subscription state, materialization, or any formal finance path.
              </div>
            </div>
          </section>

          <section style={sectionShell} data-testid="agent-news-error-pane">
            <div
              style={{
                display: "grid",
                gap: 10,
              }}
            >
              <h2
                style={{
                  margin: 0,
                  fontSize: 18,
                  fontWeight: 600,
                }}
              >
                Visible slice error pane
              </h2>
              <div style={{ color: "#5c6b82", fontSize: 13, lineHeight: 1.7 }}>
                This pane only reflects current paged result.events with non-zero error_code or
                callback anomaly envelopes from the visible slice.
              </div>
              {errorEvents.length === 0 ? (
                <div
                  style={{
                    padding: 14,
                    borderRadius: 14,
                    background: "#ffffff",
                    border: "1px solid #e4ebf5",
                    color: "#5c6b82",
                    fontSize: 13,
                    lineHeight: 1.7,
                  }}
                >
                  No visible slice error events on this page.
                </div>
              ) : (
                <div style={{ display: "grid", gap: 12 }}>
                  {errorEvents.map(({ event, topicPresentation, isCallbackEnvelope }) => (
                    <article
                      key={`error-${event.event_key}`}
                      data-testid={`agent-news-error-${event.event_key}`}
                      style={{
                        padding: 14,
                        borderRadius: 14,
                        background: "#ffffff",
                        border: "1px solid #e4ebf5",
                        display: "grid",
                        gap: 8,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          flexWrap: "wrap",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: 8,
                        }}
                      >
                        <strong>{topicPresentation.displayPair}</strong>
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            padding: "6px 10px",
                            borderRadius: 999,
                            background: "#f8fafc",
                            color: buildErrorTone(event),
                            fontSize: 12,
                            fontWeight: 600,
                          }}
                        >
                          {isCallbackEnvelope ? "Callback anomaly" : `ERR ${event.error_code}`}
                        </span>
                      </div>
                      <div style={{ color: "#162033", lineHeight: 1.6 }}>{summarizePayload(event)}</div>
                      <div
                        style={{
                          color: "#5c6b82",
                          fontSize: 12,
                          display: "flex",
                          flexWrap: "wrap",
                          gap: 12,
                        }}
                      >
                        <span>group_id {event.group_id}</span>
                        <span>topic_code {event.topic_code}</span>
                        <span>received_at {event.received_at}</span>
                        <span>error_code {event.error_code}</span>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </div>
          </section>
        </div>
      </section>
    </section>
  );
}
