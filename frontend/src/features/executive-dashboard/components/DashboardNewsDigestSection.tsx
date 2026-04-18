import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ChoiceNewsEvent } from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";

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
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) {
      return iso.slice(11, 16) || "—";
    }
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
  } catch {
    return "—";
  }
}

function toState(isLoading: boolean, isError: boolean, count: number): DataSectionState {
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
    <div data-testid="dashboard-news-digest-section">
      <DataSection title="市场资讯（Choice）" state={state} onRetry={() => void query.refetch()}>
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
          {events.map((e) => (
            <li key={`${e.event_key}-${e.serial_id}`}>
              <span
                style={{
                  fontVariantNumeric: "tabular-nums",
                  color: "#5c6b82",
                  marginRight: 8,
                }}
              >
                {formatReceivedTime(e.received_at)}
              </span>
              {summarizeNewsLine(e)}
            </li>
          ))}
        </ul>
      </DataSection>
    </div>
  );
}
