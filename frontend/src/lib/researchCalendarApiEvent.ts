import type { ResearchCalendarApiEventRow, ResearchCalendarEvent } from "../api/contracts";

function formatResearchCalendarAmountValue(amount: number): string {
  if (!Number.isFinite(amount)) {
    return String(amount);
  }
  if (Number.isInteger(amount)) {
    return String(amount);
  }
  const rounded = Math.round(amount * 1e6) / 1e6;
  return Number.isInteger(rounded) ? String(Math.trunc(rounded)) : String(amount);
}

function formatResearchCalendarAmountLabel(event: ResearchCalendarApiEventRow): string | null {
  if (event.amount == null) {
    return null;
  }
  const unit = event.amount_unit?.trim();
  const numText = formatResearchCalendarAmountValue(event.amount);
  if (!unit) {
    return numText;
  }
  return `${numText} ${unit}`.replace(/\s+/g, " ").trim();
}

function researchCalendarStatusZh(status: string | undefined | null): string {
  const s = String(status ?? "")
    .trim()
    .toLowerCase();
  if (s === "scheduled") {
    return "已排期";
  }
  if (s === "completed") {
    return "已结束";
  }
  if (s === "cancelled") {
    return "已取消";
  }
  if (s === "unknown") {
    return "状态未知";
  }
  return String(status ?? "").trim();
}

function researchCalendarMarketZh(market: string | undefined | null): string {
  const m = String(market ?? "")
    .trim()
    .toLowerCase();
  if (m === "interbank") {
    return "银行间";
  }
  return String(market ?? "").trim();
}

function researchCalendarInstrumentZh(raw: string | undefined | null): string {
  if (!raw?.trim()) {
    return "";
  }
  const k = raw.trim();
  const lower = k.toLowerCase();
  if (lower === "treasury_bond" || lower === "treasury") {
    return "国债";
  }
  if (lower === "policy_bank_bond") {
    return "政金债";
  }
  if (lower === "local_gov_bond") {
    return "地方债";
  }
  if (/[\u4e00-\u9fff]/.test(k)) {
    return k;
  }
  return k;
}

function researchCalendarSourceLabelFromUrl(url: string): string {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    if (host.includes("chinabond.com.cn")) {
      return "中国债券信息网";
    }
    if (host.includes("mof.gov.cn")) {
      return "财政部";
    }
    return host;
  } catch {
    return "来源页面";
  }
}

function buildResearchCalendarEventNoteShort(event: ResearchCalendarApiEventRow): string | null {
  const parts: string[] = [];
  const term = event.term_label?.trim();
  if (term) {
    parts.push(term);
  }
  const st = researchCalendarStatusZh(event.status);
  if (st) {
    parts.push(st);
  }
  const headline = event.headline_text?.trim();
  if (headline) {
    parts.push(headline);
  }
  const inst = researchCalendarInstrumentZh(event.instrument_type);
  if (inst) {
    parts.push(inst);
  }
  const mkt = event.market?.trim();
  if (mkt) {
    const zh = researchCalendarMarketZh(mkt);
    if (zh) {
      parts.push(`市场 ${zh}`);
    }
  }
  const cur = event.currency?.trim();
  if (cur) {
    parts.push(`币种 ${cur}`);
  }
  if (event.headline_published_at?.trim() && !headline) {
    parts.push(`披露 ${event.headline_published_at.trim()}`);
  }
  if (parts.length > 0) {
    return parts.join(" · ");
  }
  return [researchCalendarInstrumentZh(event.instrument_type), term]
    .filter((s) => Boolean(s && String(s).length > 0))
    .join(" · ") || null;
}

function stableResearchCalendarEventId(event: ResearchCalendarApiEventRow): string {
  const raw = event.event_id?.trim();
  if (raw) {
    return raw;
  }
  return [event.series_id, event.event_date, event.event_kind, event.title]
    .map((s) => String(s).trim())
    .join("::");
}

export function mapResearchCalendarApiEvent(event: ResearchCalendarApiEventRow): ResearchCalendarEvent {
  const sourceUrl = event.headline_url?.trim() || null;
  return {
    id: stableResearchCalendarEventId(event),
    date: event.event_date,
    title: event.title,
    kind: event.event_kind,
    severity: event.severity,
    amount_label: formatResearchCalendarAmountLabel(event),
    issuer: event.issuer?.trim() || null,
    note: buildResearchCalendarEventNoteShort(event),
    source_url: sourceUrl,
    source_label: sourceUrl ? researchCalendarSourceLabelFromUrl(sourceUrl) : null,
  };
}
