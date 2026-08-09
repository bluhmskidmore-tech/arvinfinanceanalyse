import type {
  BondPositionChangesPayload,
  BondTopHoldingsPayload,
  ChoiceNewsEvent,
  ChoiceNewsEventsPayload,
  IndustryDistPayload,
} from "../../../../api/contracts";
import { dashboardMacroNewsTopicLabel } from "../../dashboard/dashboardMacroNewsTopics";
import { stripHtmlTags } from "./macroNewsPresentation";

export type HomeBondNewsItem = {
  id: string;
  title: string;
  timeLabel: string;
  sourceLabel: string;
  topicLabel: string;
  hitLabel: string | null;
};

export type HomeBondNewsModel = {
  holdingHits: readonly HomeBondNewsItem[];
  marketNews: readonly HomeBondNewsItem[];
  creditAndIssuanceNews: readonly HomeBondNewsItem[];
  holdingMessage: string | null;
  marketMessage: string | null;
  creditMessage: string | null;
  sourceLabel: string;
  asOfLabel: string;
  statusLabel: string;
  refreshLabel: string;
};

type MatchCandidate = {
  value: string;
  hitLabel: string;
  priority: number;
};

type ResolvedEventTimestamp = {
  value: string;
  source: "content" | "received";
  sortValue: number;
};

const BOND_NEWS_SOURCE_LABEL = "后端入库：Choice / Tushare 债券新闻";
const BOND_NEWS_REFRESH_LABEL = "页面读取：每 5 分钟重新读取已落库数据";
const BOND_NEWS_STALE_DAYS = 7;
const HOLDING_HIT_LIMIT = 4;
const MARKET_NEWS_LIMIT = 5;
const CREDIT_NEWS_LIMIT = 4;
const CONTENT_TIMESTAMP_KEYS = [
  "published_at",
  "published_time",
  "publish_time",
  "publish_date",
  "pub_time",
  "pubtime",
  "datetime",
  "trade_date",
  "pub_date",
  "report_date",
  "date",
] as const;

const BOND_MARKET_KEYWORDS = [
  "债券",
  "债市",
  "利率债",
  "信用债",
  "同业存单",
  "国债",
  "地方债",
  "政金债",
  "国开债",
  "公司债",
  "企业债",
  "金融债",
  "主权债",
  "绿色债",
  "可转债",
  "可转换债",
  "可交换债",
  "中票",
  "中期票据",
  "短融",
  "超短融",
  "专项债",
  "永续债",
  "资产支持证券",
  "ABS",
  "收益率",
  "久期",
  "信用利差",
  "逆回购",
  "MLF",
  "DR007",
  "R007",
  "Shibor",
] as const;

const CREDIT_AND_ISSUANCE_KEYWORDS = [
  "评级",
  "违约",
  "展期",
  "兑付",
  "发行",
  "招标",
  "票面利率",
  "中标利率",
  "全场倍数",
  "边际倍数",
] as const;

const NON_BOND_CREDIT_AND_ISSUANCE_CONTEXTS = [
  "股票评级",
  "股票发行",
  "股票",
  "股价",
  "增持",
  "持平",
  "减持",
  "买入",
  "卖出",
  "认股权证",
  "发行股票",
  "发行股份",
  "公共招标",
  "发行商",
  "发行总数",
  "新股",
  "申购",
  "万股",
  "股本",
  "供应协议",
  "合作协议",
  "购买资产",
] as const;

function normalizeToken(value: string | null | undefined): string {
  return value?.trim() ?? "";
}

function dateLabel(value: string): string {
  const normalized = value.trim();
  if (!normalized || normalized === "—") {
    return "时间待核";
  }
  if (normalized.length >= 16) {
    return `${normalized.slice(5, 10)} ${normalized.slice(11, 16)}`;
  }
  if (normalized.length >= 10) {
    return normalized.slice(5, 10);
  }
  return normalized;
}

function parsePayloadJson(payloadJson: string | null | undefined): Record<string, unknown> | null {
  const raw = payloadJson?.trim();
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function normalizeTimestampCandidate(value: unknown): string {
  if (typeof value !== "string" && typeof value !== "number") {
    return "";
  }
  const raw = String(value).trim();
  if (!raw) {
    return "";
  }
  const compactDateTime = raw.match(
    /^(\d{4})(\d{2})(\d{2})[ T]?(\d{2})(\d{2})(\d{2})$/,
  );
  if (compactDateTime) {
    const [, year, month, day, hour, minute, second] = compactDateTime;
    return `${year}-${month}-${day}T${hour}:${minute}:${second}`;
  }
  const compactDate = raw.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (compactDate) {
    const [, year, month, day] = compactDate;
    return `${year}-${month}-${day}`;
  }
  const normalized = raw.replaceAll("/", "-").replace(" ", "T");
  if (!/^\d{4}-\d{2}-\d{2}/.test(normalized)) {
    return "";
  }
  return Number.isNaN(new Date(normalized).getTime()) ? "" : normalized;
}

function timestampSortValue(value: string): number {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime();
}

function resolveEventTimestamp(event: ChoiceNewsEvent): ResolvedEventTimestamp {
  const payload = parsePayloadJson(event.payload_json);
  if (payload) {
    for (const key of CONTENT_TIMESTAMP_KEYS) {
      const value = normalizeTimestampCandidate(payload[key]);
      if (value) {
        return {
          value,
          source: "content",
          sortValue: timestampSortValue(value),
        };
      }
    }
  }
  const receivedAt = normalizeTimestampCandidate(event.received_at) || event.received_at.trim();
  return {
    value: receivedAt,
    source: "received",
    sortValue: timestampSortValue(receivedAt),
  };
}

function daysBetween(leftIso: string, rightIso: string): number | null {
  const left = new Date(`${leftIso.slice(0, 10)}T00:00:00Z`);
  const right = new Date(`${rightIso.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(left.getTime()) || Number.isNaN(right.getTime())) {
    return null;
  }
  return Math.floor((left.getTime() - right.getTime()) / 86_400_000);
}

function latestChoiceNewsPayloadAsOfDate(
  payloads: readonly ChoiceNewsEventsPayload[] | null | undefined,
): string {
  return (payloads ?? [])
    .map((payload) => payload.as_of_date?.trim() ?? "")
    .filter(Boolean)
    .sort()
    .at(-1) ?? "";
}

function excludedFutureRowsTotal(
  payloads: readonly ChoiceNewsEventsPayload[] | null | undefined,
): number {
  return (payloads ?? []).reduce(
    (total, payload) => total + payload.excluded_future_rows,
    0,
  );
}

function eventText(event: ChoiceNewsEvent): string {
  return `${event.payload_text ?? ""} ${event.payload_json ?? ""}`;
}

function extractTitleFromPayloadJson(payloadJson: string | null | undefined): string {
  const parsed = parsePayloadJson(payloadJson);
  if (!parsed) {
    return "";
  }
  const headline = typeof parsed.headline === "string" ? parsed.headline.trim() : "";
  const title = typeof parsed.title === "string" ? parsed.title.trim() : "";
  return stripHtmlTags(headline || title);
}

function summarizeBondNewsEvent(event: ChoiceNewsEvent): string {
  const jsonTitle = extractTitleFromPayloadJson(event.payload_json);
  const payloadText = stripHtmlTags(event.payload_text?.trim() ?? "");
  if (jsonTitle) {
    return jsonTitle;
  }
  return stripHtmlTags(payloadText.split(" — ")[0]?.trim() ?? payloadText);
}

function addCandidate(
  candidates: MatchCandidate[],
  seen: Set<string>,
  value: string | null | undefined,
  hitLabel: string,
  priority: number,
): void {
  const normalized = normalizeToken(value);
  if (!normalized || normalized === "—" || normalized.length < 3) {
    return;
  }
  const key = normalized.toLowerCase();
  if (seen.has(key)) {
    return;
  }
  seen.add(key);
  candidates.push({ value: normalized, hitLabel, priority });
}

function buildMatchCandidates(input: {
  topHoldings?: BondTopHoldingsPayload | null;
  positionChanges?: BondPositionChangesPayload | null;
}): MatchCandidate[] {
  const candidates: MatchCandidate[] = [];
  const seen = new Set<string>();

  for (const item of input.topHoldings?.items ?? []) {
    addCandidate(candidates, seen, item.instrument_code, `命中持仓：${item.instrument_code}`, 4);
    addCandidate(candidates, seen, item.instrument_name, `命中持仓：${item.instrument_name}`, 3);
    addCandidate(candidates, seen, item.issuer_name, `命中发行人：${item.issuer_name}`, 2);
  }
  for (const item of input.positionChanges?.items ?? []) {
    addCandidate(candidates, seen, item.instrument_code, `命中持仓：${item.instrument_code}`, 4);
    addCandidate(candidates, seen, item.instrument_name, `命中持仓：${item.instrument_name}`, 3);
    addCandidate(candidates, seen, item.issuer_name, `命中发行人：${item.issuer_name}`, 2);
  }
  return candidates.sort(
    (left, right) => right.priority - left.priority || right.value.length - left.value.length,
  );
}

function findHoldingHit(text: string, candidates: readonly MatchCandidate[]): string | null {
  const normalizedText = text.toLowerCase();
  for (const candidate of candidates) {
    if (normalizedText.includes(candidate.value.toLowerCase())) {
      return candidate.hitLabel;
    }
  }
  return null;
}

function includesAnyKeyword(text: string, keywords: readonly string[]): boolean {
  const normalizedText = text.toLowerCase();
  return keywords.some((keyword) => normalizedText.includes(keyword.toLowerCase()));
}

function isBondCreditOrIssuanceNews(text: string): boolean {
  if (!includesAnyKeyword(text, CREDIT_AND_ISSUANCE_KEYWORDS)) {
    return false;
  }
  const hasBondMarketContext = includesAnyKeyword(text, BOND_MARKET_KEYWORDS);
  if (!hasBondMarketContext) {
    return false;
  }
  return !includesAnyKeyword(text, NON_BOND_CREDIT_AND_ISSUANCE_CONTEXTS);
}

function toBondNewsItem(
  event: ChoiceNewsEvent,
  title: string,
  topicLabel: string,
  hitLabel: string | null,
): HomeBondNewsItem {
  return {
    id: event.event_key,
    title,
    timeLabel: dateLabel(resolveEventTimestamp(event).value),
    sourceLabel: dashboardMacroNewsTopicLabel(event.topic_code, event.group_id),
    topicLabel,
    hitLabel,
  };
}

export function buildHomeBondNewsModel(input: {
  events?: readonly ChoiceNewsEvent[] | null;
  choiceNewsPayloads?: readonly ChoiceNewsEventsPayload[] | null;
  todayIsoDate: string;
  topHoldings?: BondTopHoldingsPayload | null;
  positionChanges?: BondPositionChangesPayload | null;
  industryDistribution?: IndustryDistPayload | null;
}): HomeBondNewsModel {
  const seenTitles = new Set<string>();
  const candidates = buildMatchCandidates(input);
  const sortedEvents = (input.events ?? [])
    .filter((event) => event.error_code === 0)
    .map((event) => ({ event, timestamp: resolveEventTimestamp(event) }))
    .slice()
    .sort(
      (left, right) =>
        right.timestamp.sortValue - left.timestamp.sortValue ||
        right.event.received_at.localeCompare(left.event.received_at),
    );
  const holdingHits: HomeBondNewsItem[] = [];
  const marketNews: HomeBondNewsItem[] = [];
  const creditAndIssuanceNews: HomeBondNewsItem[] = [];
  let latestIncludedTimestamp: ResolvedEventTimestamp | null = null;

  for (const { event, timestamp } of sortedEvents) {
    const title = summarizeBondNewsEvent(event);
    if (title.length < 6) {
      continue;
    }
    const dedupeKey = title.toLowerCase();
    if (seenTitles.has(dedupeKey)) {
      continue;
    }
    const text = `${title} ${eventText(event)}`;
    const holdingHit = findHoldingHit(text, candidates);
    const isCreditOrIssuance = isBondCreditOrIssuanceNews(text);
    const isBondMarket = includesAnyKeyword(text, BOND_MARKET_KEYWORDS);
    if (!holdingHit && !isCreditOrIssuance && !isBondMarket) {
      continue;
    }

    seenTitles.add(dedupeKey);
    if (!latestIncludedTimestamp) {
      latestIncludedTimestamp = timestamp;
    }
    if (holdingHit) {
      holdingHits.push(toBondNewsItem(event, title, "持仓命中", holdingHit));
    } else if (isCreditOrIssuance) {
      creditAndIssuanceNews.push(toBondNewsItem(event, title, "发行/评级", null));
    } else {
      marketNews.push(toBondNewsItem(event, title, "债券市场", null));
    }
  }

  const latestDate = latestIncludedTimestamp?.value.slice(0, 10) ?? "";
  const staleDays = latestDate ? daysBetween(input.todayIsoDate, latestDate) : null;
  const isStale = staleDays != null && staleDays > BOND_NEWS_STALE_DAYS;
  const latestTimeLabel = latestIncludedTimestamp
    ? dateLabel(latestIncludedTimestamp.value)
    : "";
  const latestQueriedTimestamp = sortedEvents[0]?.timestamp;
  const latestQueriedTimeLabel = latestQueriedTimestamp
    ? dateLabel(latestQueriedTimestamp.value)
    : "";
  const includedNewsCount =
    holdingHits.length + marketNews.length + creditAndIssuanceNews.length;
  const queriedNewsCount = sortedEvents.length;
  const noBondNewsButQueried = includedNewsCount === 0 && queriedNewsCount > 0;
  const payloadAsOfDate = latestChoiceNewsPayloadAsOfDate(input.choiceNewsPayloads);
  const excludedFutureRows = excludedFutureRowsTotal(input.choiceNewsPayloads);
  const excludedFutureRowsSuffix =
    excludedFutureRows > 0 ? ` · 已剔除未来 ${excludedFutureRows} 条` : "";
  const payloadAsOfLabel = payloadAsOfDate
    ? `查询日期 ${payloadAsOfDate}${excludedFutureRowsSuffix}`
    : "";

  return {
    holdingHits: holdingHits.slice(0, HOLDING_HIT_LIMIT),
    marketNews: marketNews.slice(0, MARKET_NEWS_LIMIT),
    creditAndIssuanceNews: creditAndIssuanceNews.slice(0, CREDIT_NEWS_LIMIT),
    holdingMessage:
      holdingHits.length > 0
        ? null
        : noBondNewsButQueried
          ? `持仓命中：已查询 ${queriedNewsCount} 条新闻，未命中当前持仓或发行人。`
          : "持仓命中：当前无相关新闻",
    marketMessage:
      marketNews.length > 0
        ? null
        : noBondNewsButQueried
          ? `债券市场：已查询 ${queriedNewsCount} 条新闻，未筛出债券市场相关内容。`
          : "债券市场：暂无相关新闻",
    creditMessage:
      creditAndIssuanceNews.length > 0
        ? null
        : noBondNewsButQueried
          ? `发行/评级：已查询 ${queriedNewsCount} 条新闻，未筛出债券发行或评级内容。`
          : "发行/评级：暂无相关新闻",
    sourceLabel: BOND_NEWS_SOURCE_LABEL,
    asOfLabel:
      latestTimeLabel
        ? latestIncludedTimestamp?.source === "content"
          ? `最新内容 ${latestTimeLabel}${excludedFutureRowsSuffix}`
          : `最新事件 ${latestTimeLabel}${excludedFutureRowsSuffix}`
        : latestQueriedTimeLabel
          ? latestQueriedTimestamp?.source === "content"
            ? `已查询内容至 ${latestQueriedTimeLabel}${excludedFutureRowsSuffix}`
            : `已查询事件至 ${latestQueriedTimeLabel}${excludedFutureRowsSuffix}`
          : payloadAsOfLabel || "最新内容：暂无",
    statusLabel:
      includedNewsCount > 0
        ? isStale
          ? "来源状态：偏旧"
          : "来源状态：正常"
        : noBondNewsButQueried
          ? "来源状态：未命中债券相关内容"
        : "来源状态：暂无数据",
    refreshLabel: BOND_NEWS_REFRESH_LABEL,
  };
}
