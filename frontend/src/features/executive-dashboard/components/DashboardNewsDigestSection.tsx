import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ChoiceNewsEvent } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { shellTokens } from "../../../theme/tokens";
import {
  DashboardCockpitSection,
} from "./DashboardCockpitSection";
import { cockpitInsetCardStyle } from "./DashboardCockpitSection.styles";

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
): DataSectionState {
  if (isLoading) return { kind: "loading" };
  if (isError) return { kind: "error", message: "资讯加载失败" };
  if (count === 0) return { kind: "empty", hint: "当前没有可用的 Choice 资讯条目。" };
  return { kind: "ok" };
}

export function DashboardNewsDigestSection() {
  const client = useApiClient();
  const query = useQuery({
    queryKey: ["dashboard", "choice-news-digest", client.mode],
    queryFn: () => client.getChoiceNewsEvents({ limit: 8, offset: 0 }),
    retry: false,
  });

  const events = query.data?.result.events ?? [];
  const state = useMemo(
    () => toState(query.isLoading, query.isError, events.length),
    [query.isLoading, query.isError, events.length],
  );

  return (
    <DashboardCockpitSection
      testId="dashboard-news-digest-section"
      eyebrow="News Digest"
      title="市场资讯"
      state={state}
      onRetry={() => void query.refetch()}
    >
      <div data-testid="dashboard-news-digest-list" style={{ display: "grid", gap: 10 }}>
        {events.map((event) => (
          <article
            key={`${event.event_key}-${event.serial_id}`}
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
              {formatReceivedTime(event.received_at)}
            </span>
            <span
              style={{
                color: shellTokens.colorTextSecondary,
                fontSize: 13,
                lineHeight: 1.6,
              }}
            >
              {summarizeNewsLine(event)}
            </span>
          </article>
        ))}
      </div>
    </DashboardCockpitSection>
  );
}
