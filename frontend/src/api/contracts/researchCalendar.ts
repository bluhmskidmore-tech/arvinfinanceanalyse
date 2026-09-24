/** Research calendar (`/ui/calendar/*`) contracts. */

export type ResearchCalendarEventKind = "macro" | "supply" | "auction" | "internal";

export type ResearchCalendarEvent = {
  id: string;
  date: string;
  title: string;
  kind: ResearchCalendarEventKind;
  severity: "high" | "medium" | "low";
  amount_label?: string | null;
  /** 发行人/主体；与主标题分开展示。 */
  issuer?: string | null;
  /** 短句元信息，不含整段 URL、不含 `issuer` 重复；原文见 `source_url`。 */
  note?: string | null;
  /** 公告/披露原文链接 */
  source_url?: string | null;
  /** 链接展示名，如「中国债券信息网」 */
  source_label?: string | null;
};

/** Raw supply/auction row from `GET /ui/calendar/supply-auctions` (`ResearchCalendarEvent` in backend). */
export type ResearchCalendarApiEventRow = {
  event_id: string;
  series_id: string;
  event_date: string;
  event_kind: "auction" | "supply";
  title: string;
  source_family: string;
  severity: "high" | "medium" | "low";
  issuer?: string | null;
  market?: string | null;
  instrument_type?: string | null;
  term_label?: string | null;
  amount?: number | null;
  amount_unit?: string | null;
  currency?: string | null;
  status?: "scheduled" | "completed" | "cancelled" | "unknown";
  headline_text?: string | null;
  headline_url?: string | null;
  headline_published_at?: string | null;
};

export type ResearchCalendarResultPayload = {
  series_id: string;
  total_rows: number;
  limit: number;
  offset: number;
  events: ResearchCalendarApiEventRow[];
};
