import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ChoiceNewsEvent } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { shellTokens } from "../../../theme/tokens";
import {
  DashboardCockpitSection,
} from "./DashboardCockpitSection";
import { cockpitInsetCardStyle } from "./DashboardCockpitSection.styles";

/** 与后端 limit 一致：最多展示 5 条，下拉切换阅读。 */
const NEWS_DIGEST_LIMIT = 5;
/** 每 2 小时自动刷新列表 */
const NEWS_DIGEST_REFETCH_MS = 2 * 60 * 60 * 1000;

type NewsKindKey = "all" | "policy" | "news" | "cctv" | "major" | "research";

const KIND_OPTIONS: ReadonlyArray<{ key: NewsKindKey; label: string; groupId?: string }> = [
  { key: "all", label: "全部" },
  { key: "policy", label: "政策", groupId: "tushare_policy" },
  { key: "news", label: "快讯", groupId: "tushare_news" },
  { key: "cctv", label: "联播", groupId: "tushare_cctv" },
  { key: "major", label: "长篇", groupId: "tushare_major" },
  { key: "research", label: "研报", groupId: "tushare_research" },
];

const tusharePullButtonStyle: CSSProperties = {
  width: "fit-content",
  border: `1px solid ${shellTokens.colorBorder}`,
  background: "#ffffff",
  borderRadius: 999,
  padding: "9px 14px",
  color: shellTokens.colorTextPrimary,
  fontWeight: 700,
  cursor: "pointer",
  fontSize: 13,
};

function summarizeNewsLine(event: ChoiceNewsEvent) {
  if (event.payload_text?.trim()) {
    return event.payload_text.trim();
  }
  if (event.payload_json?.trim()) {
    return event.payload_json.trim();
  }
  if (event.error_code !== 0) {
    return event.error_msg || "回调异常";
  }
  return "（空内容）";
}

function optionLabel(event: ChoiceNewsEvent, index: number) {
  const line = summarizeNewsLine(event);
  const short = line.length > 72 ? `${line.slice(0, 72)}…` : line;
  return `${index + 1}. ${short}`;
}

function parsePayload(event: ChoiceNewsEvent): Record<string, unknown> | null {
  const raw = event.payload_json?.trim();
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function extractUrl(event: ChoiceNewsEvent): string | null {
  const parsed = parsePayload(event);
  if (!parsed) return null;
  const candidates = [
    "_url",
    "url",
    "report_url",
    "pdf_url",
    "ann_pdf_url",
    "ann_url",
    "link",
    "source_url",
    "doc_url",
  ];
  for (const key of candidates) {
    const value = parsed[key];
    if (typeof value === "string") {
      const v = value.trim();
      if (v.startsWith("http://") || v.startsWith("https://")) {
        return v;
      }
    }
  }
  return null;
}

function extractFullContent(event: ChoiceNewsEvent): string | null {
  const parsed = parsePayload(event);
  if (!parsed) return null;
  const keys = ["content", "content_html", "abstr", "abstract", "summary"];
  for (const key of keys) {
    const value = parsed[key];
    if (typeof value === "string") {
      const v = value.trim();
      if (v.length > 0) {
        return v;
      }
    }
  }
  return null;
}

function formatReceivedTime(iso: string) {
  try {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) {
      return iso.slice(11, 16) || "—";
    }
    return date.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return "—";
  }
}

function toState(
  isLoading: boolean,
  isError: boolean,
  count: number,
  digestKind: NewsKindKey,
): DataSectionState {
  if (isLoading) return { kind: "loading" };
  if (isError) return { kind: "error", message: "资讯加载失败" };
  if (count === 0) {
    const hintAll =
      "当前库中没有资讯条目（Choice 推送未入库、尚未执行 Tushare 拉取，或 DuckDB 为空）。可在下方从 Tushare 拉取要闻。";
    const hintFiltered =
      "当前分类下没有资讯。可切换到「全部」查看其它来源，或使用下方按钮从 Tushare 拉取该分类数据。";
    return {
      kind: "empty",
      hint: digestKind === "all" ? hintAll : hintFiltered,
    };
  }
  return { kind: "ok" };
}

export function DashboardNewsDigestSection() {
  const client = useApiClient();
  const [ingestBusy, setIngestBusy] = useState(false);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [kind, setKind] = useState<NewsKindKey>("all");
  const activeKind = KIND_OPTIONS.find((opt) => opt.key === kind) ?? KIND_OPTIONS[0];
  const query = useQuery({
    queryKey: ["dashboard", "choice-news-digest", client.mode, activeKind.groupId ?? "all"],
    queryFn: () =>
      client.getChoiceNewsEvents({
        limit: NEWS_DIGEST_LIMIT,
        offset: 0,
        groupId: activeKind.groupId,
      }),
    retry: false,
    refetchInterval: NEWS_DIGEST_REFETCH_MS,
  });

  const events = query.data?.result.events ?? [];

  useEffect(() => {
    if (selectedIndex >= events.length) {
      setSelectedIndex(0);
    }
  }, [events.length, selectedIndex]);
  useEffect(() => {
    setSelectedIndex(0);
  }, [kind]);

  const state = useMemo(
    () => toState(query.isLoading, query.isError, events.length, kind),
    [query.isLoading, query.isError, events.length, kind],
  );

  const emptyFooter =
    state.kind === "empty" ? (
      <div style={{ display: "grid", gap: 8 }}>
        <button
          type="button"
          disabled={ingestBusy}
          style={{
            ...tusharePullButtonStyle,
            opacity: ingestBusy ? 0.65 : 1,
            cursor: ingestBusy ? "wait" : "pointer",
          }}
          onClick={() => {
            setIngestError(null);
            setIngestBusy(true);
            void (async () => {
              try {
                await client.ingestTushareNprNews({ limit: 20 });
                await query.refetch();
              } catch (e) {
                setIngestError(e instanceof Error ? e.message : "拉取失败");
              } finally {
                setIngestBusy(false);
              }
            })();
          }}
        >
          {ingestBusy ? "正在从 Tushare 拉取…" : "从 Tushare 拉取要闻"}
        </button>
        {ingestError ? (
          <span style={{ color: shellTokens.colorDanger, fontSize: 12 }}>{ingestError}</span>
        ) : null}
      </div>
    ) : null;

  const selectedEvent = events[selectedIndex] ?? null;
  const selectedUrl = selectedEvent ? extractUrl(selectedEvent) : null;
  const selectedFullContent = selectedEvent ? extractFullContent(selectedEvent) : null;
  const summary = selectedEvent ? summarizeNewsLine(selectedEvent) : "";
  // Show "展开正文" only when there's substantially more text than what the card already shows.
  const hasMoreToExpand =
    !!selectedFullContent && selectedFullContent.length > summary.length + 20;
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    setExpanded(false);
  }, [selectedIndex, kind]);

  return (
    <DashboardCockpitSection
      testId="dashboard-news-digest-section"
      eyebrow="News Digest"
      title="市场资讯"
      state={state}
      onRetry={() => void query.refetch()}
      emptyFooter={emptyFooter}
    >
      <div data-testid="dashboard-news-digest-list" style={{ display: "grid", gap: 12 }}>
        <div
          role="tablist"
          aria-label="资讯类型筛选"
          style={{ display: "flex", flexWrap: "wrap", gap: 6 }}
        >
          {KIND_OPTIONS.map((opt) => {
            const active = opt.key === kind;
            return (
              <button
                key={opt.key}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setKind(opt.key)}
                style={{
                  border: `1px solid ${active ? shellTokens.colorTextPrimary : shellTokens.colorBorder}`,
                  background: active ? shellTokens.colorTextPrimary : "#ffffff",
                  color: active ? "#ffffff" : shellTokens.colorTextPrimary,
                  borderRadius: 999,
                  padding: "5px 12px",
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                  lineHeight: 1.3,
                }}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
        <label
          style={{
            display: "grid",
            gap: 6,
            fontSize: 12,
            fontWeight: 700,
            color: shellTokens.colorTextSecondary,
          }}
        >
          选择资讯
          <select
            aria-label="选择一条市场资讯"
            value={Math.min(selectedIndex, Math.max(0, events.length - 1))}
            onChange={(e) => setSelectedIndex(Number(e.target.value))}
            style={{
              width: "100%",
              maxWidth: "100%",
              padding: "10px 12px",
              borderRadius: 12,
              border: `1px solid ${shellTokens.colorBorder}`,
              background: "#fff",
              color: shellTokens.colorTextPrimary,
              fontSize: 13,
              lineHeight: 1.4,
              cursor: "pointer",
            }}
          >
            {events.map((event, index) => (
              <option key={`${event.event_key}-${event.serial_id}`} value={index}>
                {optionLabel(event, index)}
              </option>
            ))}
          </select>
        </label>
        {selectedEvent ? (
          <article
            style={{
              ...cockpitInsetCardStyle,
              gridTemplateColumns: "68px minmax(0, 1fr)",
              alignItems: "start",
              gap: 12,
            }}
          >
            <span
              style={{
                color: shellTokens.colorTextPrimary,
                fontSize: 14,
                fontWeight: 700,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {formatReceivedTime(selectedEvent.received_at)}
            </span>
            <div style={{ display: "grid", gap: 8, minWidth: 0 }}>
              <span
                style={{
                  color: shellTokens.colorTextSecondary,
                  fontSize: 13,
                  lineHeight: 1.6,
                  wordBreak: "break-word",
                  whiteSpace: "pre-wrap",
                }}
              >
                {expanded && selectedFullContent ? selectedFullContent : summary}
              </span>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
                {selectedUrl ? (
                  <a
                    href={selectedUrl}
                    target="_blank"
                    rel="noreferrer noopener"
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: shellTokens.colorAccent,
                      textDecoration: "none",
                    }}
                  >
                    查看原文 ↗
                  </a>
                ) : null}
                {hasMoreToExpand ? (
                  <button
                    type="button"
                    onClick={() => setExpanded((v) => !v)}
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: shellTokens.colorAccent,
                      background: "none",
                      border: "none",
                      padding: 0,
                      cursor: "pointer",
                    }}
                  >
                    {expanded ? "收起" : "展开正文"}
                  </button>
                ) : null}
              </div>
            </div>
          </article>
        ) : null}
      </div>
    </DashboardCockpitSection>
  );
}
