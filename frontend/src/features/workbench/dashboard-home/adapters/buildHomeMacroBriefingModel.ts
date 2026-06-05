import macroReleaseCalendarRaw from "../../../../../../config/dashboard_macro_release_calendar_2026.json";
import type { ChoiceNewsEvent } from "../../../../api/contracts";
import {
  dashboardMacroNewsFallbackTopicLabel,
  dashboardMacroNewsTopicLabel,
} from "../../dashboard/dashboardMacroNewsTopics";
import { addDaysToIsoDate } from "../../pages/dashboardPageHelpers";
import {
  hasLeadingHtmlPayload,
  isDisplayableMacroNewsText,
  isMacroRelevantForHomeBriefing,
  isPolicyFundingRelevantForHomeBriefing,
  summarizeMacroNewsEvent,
} from "./macroNewsPresentation";
import type { HomeResearchCalendarModel } from "./buildHomeResearchCalendarModel";

export type HomeMacroReleaseItem = {
  id: string;
  date: string;
  dateLabel: string;
  daysUntilLabel: string;
  region: string;
  title: string;
  category: string;
  importance: string;
  importanceLabel: string;
  timeLabel: string;
  sourceName: string;
  sourceUrl: string;
};

export type HomeMacroNewsItem = {
  id: string;
  timeLabel: string;
  topicLabel: string;
  title: string;
  freshnessLabel: string;
};

export type HomeMacroSupplyItem = {
  id: string;
  label: string;
};

export type HomePolicyFundingChip = {
  id: string;
  label: string;
  tone: "neutral" | "info" | "warning" | "danger";
};

export type HomePolicyFundingNewsGroup = {
  id: string;
  label: string;
  countLabel: string;
  items: readonly HomeMacroNewsItem[];
};

export type HomePolicyFundingDiagnosticMetric = {
  id: string;
  label: string;
  value: string;
  tone: "neutral" | "info" | "warning" | "danger";
};

export type HomePolicyFundingDiagnosticReason = {
  id: string;
  label: string;
  countLabel: string;
  tone: "neutral" | "info" | "warning" | "danger";
};

export type HomePolicyFundingDiagnostics = {
  summary: string;
  emptyHint: string | null;
  metrics: readonly HomePolicyFundingDiagnosticMetric[];
  reasons: readonly HomePolicyFundingDiagnosticReason[];
};

export type HomePolicyFundingSummary = {
  headline: string;
  chips: readonly HomePolicyFundingChip[];
  diagnostics?: HomePolicyFundingDiagnostics;
  groups: readonly HomePolicyFundingNewsGroup[];
};

export type HomeMacroBriefingModel = {
  releaseItems: readonly HomeMacroReleaseItem[];
  releaseWindowLabel: string;
  releaseMessage: string | null;
  newsItems: readonly HomeMacroNewsItem[];
  newsMessage: string | null;
  newsStale: boolean;
  newsFreshnessLabel: string;
  newsSourceLabel: string;
  newsAsOfLabel: string;
  newsStatusLabel: string;
  newsRefreshLabel: string;
  policyFundingSummary: HomePolicyFundingSummary;
  supplyItems: readonly HomeMacroSupplyItem[];
};

type MacroReleaseCalendarRow = {
  id: string;
  date: string;
  time_label: string;
  region: string;
  title: string;
  category: string;
  importance: string;
  source_name: string;
  source_url: string;
};

type MacroNewsItemsResult = Pick<
  HomeMacroBriefingModel,
  "newsItems" | "newsMessage" | "newsStale" | "newsFreshnessLabel" | "newsSourceLabel" | "newsAsOfLabel" | "newsStatusLabel" | "newsRefreshLabel"
> & {
  policyFundingDiagnostics?: HomePolicyFundingDiagnostics;
};

type MacroNewsFilterOptions = {
  requireMacroRelevance: boolean;
  requirePolicyFundingRelevance: boolean;
};

type MacroNewsDropReasonId =
  | "source-error"
  | "undisplayable"
  | "not-macro"
  | "not-policy-funding"
  | "duplicate-title"
  | "over-limit";

const RELEASE_WINDOW_DAYS = 45;
const RELEASE_LIMIT = 6;
const NEWS_LIMIT = 6;
const NEWS_STALE_DAYS = 7;
const MACRO_NEWS_CHOICE_SOURCE_LABEL = "来源：Choice 宏观新闻";
const MACRO_NEWS_FALLBACK_SOURCE_LABEL = "来源：Tushare 宏观快讯（Choice 不可用或偏旧兜底）";
const MACRO_NEWS_RELAXED_FALLBACK_SOURCE_LABEL = "来源：Tushare 宏观快讯（Choice 不可用时非严格资金面兜底）";
const MACRO_NEWS_REFRESH_LABEL = "刷新：随页面查询读取已落库数据";
const POLICY_FUNDING_EMPTY_MESSAGE = "政策与资金面：暂无债券相关更新";
const macroReleaseCalendar = macroReleaseCalendarRaw as readonly MacroReleaseCalendarRow[];

const POLICY_FUNDING_GROUP_DEFINITIONS: readonly {
  id: string;
  label: string;
  patterns: readonly RegExp[];
}[] = [
  {
    id: "public-market",
    label: "央行/公开市场",
    patterns: [
      /央行|公开市场|逆回购|MLF|SLF|OMO|DR007|Shibor|银行间|货币市场|净投放|回笼|到期|流动性|资金面/i,
    ],
  },
  {
    id: "rates-bonds",
    label: "利率/债券",
    patterns: [/国债|美债|债券|债市|收益率|利率|基点|BP|长端|短端|期限利差|信用利差/i],
  },
  {
    id: "overseas-macro",
    label: "海外宏观",
    patterns: [/美国|英国|日本|韩国|欧元区|欧洲|海外|美联储|英央行|日央行|欧洲央行|出口|通胀|CPI|PMI/i],
  },
];

const OTHER_POLICY_FUNDING_GROUP = {
  id: "other-macro",
  label: "其他宏观",
};

function importanceLabel(importance: string): string {
  if (importance === "high") {
    return "高优先级";
  }
  if (importance === "medium") {
    return "中优先级";
  }
  if (importance === "low") {
    return "低优先级";
  }
  return importance || "待确认";
}

function dateLabel(date: string): string {
  return date.length >= 10 ? date.slice(5, 10) : date;
}

function dateTimeLabel(value: string): string {
  const normalized = value.trim();
  if (!normalized || normalized === "—") {
    return "时间待核";
  }
  if (normalized.length >= 16) {
    return `${normalized.slice(5, 10)} ${normalized.slice(11, 16)}`;
  }
  return dateLabel(normalized);
}

function daysBetween(leftIso: string, rightIso: string): number | null {
  const left = new Date(`${leftIso.slice(0, 10)}T00:00:00Z`);
  const right = new Date(`${rightIso.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(left.getTime()) || Number.isNaN(right.getTime())) {
    return null;
  }
  return Math.floor((left.getTime() - right.getTime()) / 86_400_000);
}

function daysUntilLabel(date: string, todayIsoDate: string): string {
  const days = daysBetween(date, todayIsoDate);
  if (days == null) {
    return "待确认";
  }
  if (days === 0) {
    return "今日";
  }
  if (days === 1) {
    return "明日";
  }
  if (days > 1) {
    return `${days}天后`;
  }
  return `${Math.abs(days)}天前`;
}

function incrementReason(reasons: Map<MacroNewsDropReasonId, number>, id: MacroNewsDropReasonId) {
  reasons.set(id, (reasons.get(id) ?? 0) + 1);
}

function dropReasonLabel(id: MacroNewsDropReasonId): string {
  if (id === "source-error") {
    return "源错误/权限";
  }
  if (id === "undisplayable") {
    return "正文不可展示";
  }
  if (id === "not-macro") {
    return "非宏观";
  }
  if (id === "not-policy-funding") {
    return "非政策/资金面";
  }
  if (id === "duplicate-title") {
    return "重复标题";
  }
  return "超过展示上限";
}

function dropReasonTone(id: MacroNewsDropReasonId): HomePolicyFundingDiagnosticReason["tone"] {
  if (id === "source-error") {
    return "danger";
  }
  if (id === "undisplayable" || id === "not-macro" || id === "not-policy-funding") {
    return "warning";
  }
  return "neutral";
}

function selectedSourceLabel(sourceLabel: string): string {
  const compact = sourceLabel.replace(/^来源：/, "").trim();
  if (compact.includes("Tushare") && compact.includes("兜底")) {
    return compact.includes("非严格") ? "Tushare 宏观兜底" : "Tushare 兜底";
  }
  if (compact.includes("Choice")) {
    return "Choice";
  }
  return compact || "当前源";
}

function describeCount(count: number): string {
  return `${count} 条`;
}

function reasonListText(reasons: readonly HomePolicyFundingDiagnosticReason[]): string {
  return reasons.map((reason) => reason.label).join("、");
}

function analyzeMacroNewsEvents(input: {
  events?: readonly ChoiceNewsEvent[] | null;
  options: MacroNewsFilterOptions;
}): {
  rawCount: number;
  eligibleCount: number;
  uniqueCount: number;
  displayedCount: number;
  displayedEvents: readonly ChoiceNewsEvent[];
  reasons: readonly HomePolicyFundingDiagnosticReason[];
} {
  const reasons = new Map<MacroNewsDropReasonId, number>();
  const eligibleEvents = (input.events ?? []).filter((event) => {
    if (event.error_code !== 0) {
      incrementReason(reasons, "source-error");
      return false;
    }
    if (hasLeadingHtmlPayload(event)) {
      incrementReason(reasons, "undisplayable");
      return false;
    }

    const title = summarizeMacroNewsEvent(event);
    if (!isDisplayableMacroNewsText(title)) {
      incrementReason(reasons, "undisplayable");
      return false;
    }
    if (input.options.requireMacroRelevance && !isMacroRelevantForHomeBriefing(title)) {
      incrementReason(reasons, "not-macro");
      return false;
    }
    if (input.options.requirePolicyFundingRelevance && !isPolicyFundingRelevantForHomeBriefing(title)) {
      incrementReason(reasons, "not-policy-funding");
      return false;
    }
    return true;
  });

  const sortedEligibleEvents = eligibleEvents
    .slice()
    .sort((left, right) => right.received_at.localeCompare(left.received_at));
  const seenTitles = new Set<string>();
  const uniqueEvents = sortedEligibleEvents.filter((event) => {
    const title = summarizeMacroNewsEvent(event);
    const key = title.trim().toLowerCase();
    if (!key || seenTitles.has(key)) {
      incrementReason(reasons, "duplicate-title");
      return false;
    }
    seenTitles.add(key);
    return true;
  });
  const displayedEvents = uniqueEvents.slice(0, NEWS_LIMIT);
  const overLimitCount = Math.max(0, uniqueEvents.length - NEWS_LIMIT);
  if (overLimitCount > 0) {
    reasons.set("over-limit", overLimitCount);
  }

  return {
    rawCount: input.events?.length ?? 0,
    eligibleCount: sortedEligibleEvents.length,
    uniqueCount: uniqueEvents.length,
    displayedCount: displayedEvents.length,
    displayedEvents,
    reasons: Array.from(reasons.entries()).map(([id, count]) => ({
      id,
      label: dropReasonLabel(id),
      countLabel: describeCount(count),
      tone: dropReasonTone(id),
    })),
  };
}

function buildPolicyFundingDiagnostics(input: {
  sourceLabel: string;
  rawCount: number;
  eligibleCount: number;
  uniqueCount: number;
  displayedCount: number;
  reasons: readonly HomePolicyFundingDiagnosticReason[];
}): HomePolicyFundingDiagnostics {
  const source = selectedSourceLabel(input.sourceLabel);
  const metrics: HomePolicyFundingDiagnosticMetric[] = [
    { id: "raw", label: "原始", value: describeCount(input.rawCount), tone: "neutral" },
    { id: "eligible", label: "入选", value: describeCount(input.eligibleCount), tone: "info" },
    { id: "unique", label: "去重后", value: describeCount(input.uniqueCount), tone: "info" },
    { id: "displayed", label: "展示", value: describeCount(input.displayedCount), tone: "info" },
  ];
  const removedCount = Math.max(0, input.rawCount - input.displayedCount);
  const reasonText = reasonListText(input.reasons);

  return {
    summary: `当前源 ${source}：原始 ${input.rawCount} 条，入选 ${input.eligibleCount} 条，去重后 ${input.uniqueCount} 条，展示 ${input.displayedCount} 条。`,
    emptyHint:
      input.displayedCount <= 1 && removedCount > 0 && reasonText
        ? `仅 ${input.displayedCount} 条通过筛选；其余 ${removedCount} 条因${reasonText}未展示。`
        : null,
    metrics,
    reasons: input.reasons,
  };
}

function emptyPolicyFundingDiagnostics(input: {
  sourceLabel: string;
  stateLabel: string;
  rawCount?: number;
}): HomePolicyFundingDiagnostics {
  const rawCount = input.rawCount ?? 0;
  return {
    summary: `当前源 ${selectedSourceLabel(input.sourceLabel)}：${input.stateLabel}，原始 ${rawCount} 条，展示 0 条。`,
    emptyHint: rawCount > 0 ? `当前 ${rawCount} 条原始记录未形成可展示快讯。` : "当前没有可诊断的原始记录。",
    metrics: [
      { id: "raw", label: "原始", value: describeCount(rawCount), tone: "neutral" },
      { id: "eligible", label: "入选", value: "0 条", tone: "warning" },
      { id: "unique", label: "去重后", value: "0 条", tone: "warning" },
      { id: "displayed", label: "展示", value: "0 条", tone: "warning" },
    ],
    reasons: [],
  };
}

function buildReleaseItems(todayIsoDate: string): HomeMacroReleaseItem[] {
  const windowEndDate = addDaysToIsoDate(todayIsoDate, RELEASE_WINDOW_DAYS);
  return macroReleaseCalendar
    .filter((item) => item.date >= todayIsoDate && item.date <= windowEndDate)
    .sort((left, right) => left.date.localeCompare(right.date) || left.title.localeCompare(right.title, "zh-CN"))
    .slice(0, RELEASE_LIMIT)
    .map((item) => ({
      id: item.id,
      date: item.date,
      dateLabel: dateLabel(item.date),
      daysUntilLabel: daysUntilLabel(item.date, todayIsoDate),
      region: item.region,
      title: item.title,
      category: item.category,
      importance: item.importance,
      importanceLabel: importanceLabel(item.importance),
      timeLabel: item.time_label,
      sourceName: item.source_name,
      sourceUrl: item.source_url,
    }));
}

function buildNewsItemsFromEvents(input: {
  events?: readonly ChoiceNewsEvent[] | null;
  todayIsoDate: string;
  topicLabel: (topicCode: string) => string;
  sourceLabel: string;
  emptyMessage: string;
  statusWhenFresh: string;
  statusWhenStale: string;
  statusWhenEmpty: string;
  requireMacroRelevance?: boolean;
  requirePolicyFundingRelevance?: boolean;
}): MacroNewsItemsResult {
  const analysis = analyzeMacroNewsEvents({
    events: input.events,
    options: {
      requireMacroRelevance: Boolean(input.requireMacroRelevance),
      requirePolicyFundingRelevance: Boolean(input.requirePolicyFundingRelevance),
    },
  });
  const newsItems = analysis.displayedEvents.map((event) => {
    const title = summarizeMacroNewsEvent(event);
    const timeLabel = dateTimeLabel(event.received_at);
    return {
      id: event.event_key,
      timeLabel,
      topicLabel: input.topicLabel(event.topic_code),
      title,
      freshnessLabel: `最近更新 ${timeLabel}`,
    };
  });

  const latestDate = analysis.displayedEvents[0]?.received_at.slice(0, 10) ?? "";
  const staleDays = latestDate ? daysBetween(input.todayIsoDate, latestDate) : null;
  const newsStale = staleDays != null && staleDays > NEWS_STALE_DAYS;
  const newsFreshnessLabel = newsItems[0]?.freshnessLabel ?? "暂无更新";
  const newsAsOfLabel = newsItems[0]?.timeLabel ? `数据截至 ${newsItems[0].timeLabel}` : "数据截至：暂无";

  return {
    newsItems,
    newsMessage: newsItems.length > 0 ? null : input.emptyMessage,
    newsStale,
    newsFreshnessLabel,
    newsSourceLabel: input.sourceLabel,
    newsAsOfLabel,
    newsStatusLabel:
      newsItems.length > 0 ? (newsStale ? input.statusWhenStale : input.statusWhenFresh) : input.statusWhenEmpty,
    newsRefreshLabel: MACRO_NEWS_REFRESH_LABEL,
    policyFundingDiagnostics: buildPolicyFundingDiagnostics({
      sourceLabel: input.sourceLabel,
      rawCount: analysis.rawCount,
      eligibleCount: analysis.eligibleCount,
      uniqueCount: analysis.uniqueCount,
      displayedCount: analysis.displayedCount,
      reasons: analysis.reasons,
    }),
  };
}

function latestChoiceSourceError(events?: readonly ChoiceNewsEvent[] | null): ChoiceNewsEvent | null {
  return (events ?? [])
    .filter((event) => event.error_code !== 0)
    .slice()
    .sort((left, right) => right.received_at.localeCompare(left.received_at))[0] ?? null;
}

function isChoicePermissionError(event: ChoiceNewsEvent): boolean {
  const message = event.error_msg.trim().toLowerCase();
  return event.error_code === 10001012 || message.includes("insufficient user access");
}

function buildChoiceSourceErrorResult(event: ChoiceNewsEvent): MacroNewsItemsResult {
  const timeLabel = dateTimeLabel(event.received_at);
  const isPermissionError = isChoicePermissionError(event);
  const errorMessage = event.error_msg.trim();

  return {
    newsItems: [],
    newsMessage: isPermissionError
      ? "Choice 新闻权限不足，请恢复数据源权限后重新采集。"
      : `Choice 新闻源返回错误${errorMessage ? `：${errorMessage}` : ""}。`,
    newsStale: false,
    newsFreshnessLabel: isPermissionError ? "Choice 新闻权限不足" : "新闻源返回错误",
    newsSourceLabel: MACRO_NEWS_CHOICE_SOURCE_LABEL,
    newsAsOfLabel: `数据截至 ${timeLabel}`,
    newsStatusLabel: isPermissionError ? "来源状态：Choice 权限不足" : "来源状态：新闻源错误",
    newsRefreshLabel: MACRO_NEWS_REFRESH_LABEL,
    policyFundingDiagnostics: emptyPolicyFundingDiagnostics({
      sourceLabel: MACRO_NEWS_CHOICE_SOURCE_LABEL,
      stateLabel: isPermissionError ? "Choice 权限不足" : "新闻源错误",
      rawCount: 1,
    }),
  };
}

export function shouldUseMacroNewsFallback(choiceNews: MacroNewsItemsResult): boolean {
  if (choiceNews.newsItems.length === 0) {
    return true;
  }
  return choiceNews.newsStale;
}

export function shouldRequestHomeMacroNewsFallback(input: {
  choiceEvents?: readonly ChoiceNewsEvent[] | null;
  todayIsoDate: string;
}): boolean {
  const choiceNews = buildNewsItemsFromEvents({
    events: input.choiceEvents,
    todayIsoDate: input.todayIsoDate,
    topicLabel: dashboardMacroNewsTopicLabel,
    sourceLabel: MACRO_NEWS_CHOICE_SOURCE_LABEL,
    emptyMessage: POLICY_FUNDING_EMPTY_MESSAGE,
    statusWhenFresh: "source ok",
    statusWhenStale: "source stale",
    statusWhenEmpty: "source empty",
    requirePolicyFundingRelevance: true,
  });

  return shouldUseMacroNewsFallback(choiceNews);
}

export function resolveHomeMacroNewsBriefing(input: {
  choiceEvents?: readonly ChoiceNewsEvent[] | null;
  fallbackEvents?: readonly ChoiceNewsEvent[] | null;
  todayIsoDate: string;
  isLoading: boolean;
  isError: boolean;
}): MacroNewsItemsResult {
  if (input.isError) {
    return {
      newsItems: [],
      newsMessage: "政策与资金面加载失败，请稍后刷新。",
      newsStale: false,
      newsFreshnessLabel: "新闻源异常",
      newsSourceLabel: MACRO_NEWS_CHOICE_SOURCE_LABEL,
      newsAsOfLabel: "数据截至：不可用",
      newsStatusLabel: "来源状态：异常",
      newsRefreshLabel: MACRO_NEWS_REFRESH_LABEL,
      policyFundingDiagnostics: emptyPolicyFundingDiagnostics({
        sourceLabel: MACRO_NEWS_CHOICE_SOURCE_LABEL,
        stateLabel: "查询异常",
      }),
    };
  }
  if (input.isLoading && !input.choiceEvents?.length && !input.fallbackEvents?.length) {
    return {
      newsItems: [],
      newsMessage: "正在加载政策与资金面…",
      newsStale: false,
      newsFreshnessLabel: "加载中",
      newsSourceLabel: MACRO_NEWS_CHOICE_SOURCE_LABEL,
      newsAsOfLabel: "数据截至：加载中",
      newsStatusLabel: "来源状态：加载中",
      newsRefreshLabel: MACRO_NEWS_REFRESH_LABEL,
      policyFundingDiagnostics: emptyPolicyFundingDiagnostics({
        sourceLabel: MACRO_NEWS_CHOICE_SOURCE_LABEL,
        stateLabel: "加载中",
      }),
    };
  }

  const choiceNews = buildNewsItemsFromEvents({
    events: input.choiceEvents,
    todayIsoDate: input.todayIsoDate,
    topicLabel: dashboardMacroNewsTopicLabel,
    sourceLabel: MACRO_NEWS_CHOICE_SOURCE_LABEL,
    emptyMessage: POLICY_FUNDING_EMPTY_MESSAGE,
    statusWhenFresh: "来源状态：正常",
    statusWhenStale: "来源状态：偏旧",
    statusWhenEmpty: "来源状态：暂无数据",
    requirePolicyFundingRelevance: true,
  });

  if (!shouldUseMacroNewsFallback(choiceNews)) {
    return choiceNews;
  }

  if (input.isLoading && !input.fallbackEvents?.length) {
    return {
      newsItems: [],
      newsMessage: "正在加载政策与资金面…",
      newsStale: false,
      newsFreshnessLabel: "加载中",
      newsSourceLabel: MACRO_NEWS_FALLBACK_SOURCE_LABEL,
      newsAsOfLabel: "数据截至：加载中",
      newsStatusLabel: "来源状态：加载中",
      newsRefreshLabel: MACRO_NEWS_REFRESH_LABEL,
      policyFundingDiagnostics: emptyPolicyFundingDiagnostics({
        sourceLabel: MACRO_NEWS_FALLBACK_SOURCE_LABEL,
        stateLabel: "等待兜底源",
        rawCount: input.choiceEvents?.length ?? 0,
      }),
    };
  }

  const fallbackNews = buildNewsItemsFromEvents({
    events: input.fallbackEvents,
    todayIsoDate: input.todayIsoDate,
    topicLabel: dashboardMacroNewsFallbackTopicLabel,
    sourceLabel: MACRO_NEWS_FALLBACK_SOURCE_LABEL,
    emptyMessage: POLICY_FUNDING_EMPTY_MESSAGE,
    statusWhenFresh: "来源状态：Tushare 兜底",
    statusWhenStale: "来源状态：偏旧",
    statusWhenEmpty: "来源状态：暂无数据",
    requirePolicyFundingRelevance: true,
  });

  if (fallbackNews.newsItems.length > 0) {
    return fallbackNews;
  }

  const sourceError = latestChoiceSourceError(input.choiceEvents);
  if (sourceError) {
    const relaxedFallbackNews = buildNewsItemsFromEvents({
      events: input.fallbackEvents,
      todayIsoDate: input.todayIsoDate,
      topicLabel: dashboardMacroNewsFallbackTopicLabel,
      sourceLabel: MACRO_NEWS_RELAXED_FALLBACK_SOURCE_LABEL,
      emptyMessage: POLICY_FUNDING_EMPTY_MESSAGE,
      statusWhenFresh: "来源状态：Tushare 宏观兜底（非严格资金面）",
      statusWhenStale: "来源状态：Tushare 宏观兜底偏旧（非严格资金面）",
      statusWhenEmpty: "来源状态：暂无数据",
      requireMacroRelevance: true,
      requirePolicyFundingRelevance: false,
    });

    if (relaxedFallbackNews.newsItems.length > 0) {
      return relaxedFallbackNews;
    }

    return buildChoiceSourceErrorResult(sourceError);
  }

  return choiceNews;
}

function buildSupplyItems(calendar: HomeResearchCalendarModel): HomeMacroSupplyItem[] {
  if (calendar.status === "loading") {
    return [{ id: "supply-loading", label: "供给/招标：加载中" }];
  }
  if (calendar.status === "error") {
    return [{ id: "supply-error", label: "供给/招标：加载失败" }];
  }
  if (calendar.items.length === 0) {
    return [{ id: "supply-empty", label: "供给/招标：当前窗口无事件" }];
  }
  return calendar.items.slice(0, 2).map((item) => ({
    id: item.id,
    label: `供给/招标：${dateLabel(item.date)} ${item.title}${item.amountLabel !== "—" ? ` · ${item.amountLabel}` : ""}`,
  }));
}

function compactStatusLabel(label: string): string {
  return label.replace(/^来源状态：/, "").trim();
}

function compactAsOfLabel(label: string): string {
  return label.replace(/^数据截至\s*/, "数据截至 ").trim();
}

function pushUniqueChip(chips: HomePolicyFundingChip[], chip: HomePolicyFundingChip) {
  if (!chip.label || chips.some((item) => item.label === chip.label)) {
    return;
  }
  chips.push(chip);
}

function groupForPolicyFundingNews(item: HomeMacroNewsItem): { id: string; label: string } {
  const text = `${item.topicLabel} ${item.title}`;
  const matched = POLICY_FUNDING_GROUP_DEFINITIONS.find((group) =>
    group.patterns.some((pattern) => pattern.test(text)),
  );
  return matched ?? OTHER_POLICY_FUNDING_GROUP;
}

function buildPolicyFundingGroups(newsItems: readonly HomeMacroNewsItem[]): HomePolicyFundingNewsGroup[] {
  const grouped = new Map<string, { label: string; items: HomeMacroNewsItem[] }>();

  newsItems.forEach((item) => {
    const group = groupForPolicyFundingNews(item);
    const current = grouped.get(group.id) ?? { label: group.label, items: [] };
    current.items.push(item);
    grouped.set(group.id, current);
  });

  return Array.from(grouped.entries()).map(([id, group]) => ({
    id,
    label: group.label,
    countLabel: `${group.items.length} 条`,
    items: group.items,
  }));
}

function buildPolicyFundingChips(input: MacroNewsItemsResult): HomePolicyFundingChip[] {
  const chips: HomePolicyFundingChip[] = [];
  const statusLabel = compactStatusLabel(input.newsStatusLabel);
  const sourceLabel = input.newsSourceLabel.replace(/^来源：/, "").trim();

  if (statusLabel.includes("异常") || statusLabel.includes("错误") || statusLabel.includes("权限不足")) {
    pushUniqueChip(chips, { id: "status-error", label: statusLabel, tone: "danger" });
  } else if (input.newsStale || statusLabel.includes("偏旧")) {
    pushUniqueChip(chips, { id: "status-stale", label: "新闻源偏旧", tone: "warning" });
  } else if (statusLabel.includes("加载中")) {
    pushUniqueChip(chips, { id: "status-loading", label: "加载中", tone: "info" });
  } else if (statusLabel.includes("Tushare")) {
    pushUniqueChip(chips, { id: "status-fallback", label: statusLabel, tone: "warning" });
  } else if (statusLabel && !statusLabel.includes("暂无数据")) {
    pushUniqueChip(chips, { id: "status", label: statusLabel, tone: "info" });
  }

  if (!chips.some((chip) => chip.id.startsWith("status")) && sourceLabel) {
    pushUniqueChip(chips, { id: "source", label: sourceLabel, tone: "neutral" });
  }

  pushUniqueChip(chips, { id: "as-of", label: compactAsOfLabel(input.newsAsOfLabel), tone: "neutral" });
  pushUniqueChip(chips, { id: "freshness", label: input.newsFreshnessLabel, tone: "neutral" });

  return chips;
}

export function buildPolicyFundingSummary(input: MacroNewsItemsResult): HomePolicyFundingSummary {
  const groups = buildPolicyFundingGroups(input.newsItems);
  const chips = buildPolicyFundingChips(input);
  if (input.newsItems.length === 0) {
    return {
      headline: "暂无可展示的政策与资金面快讯。",
      chips,
      diagnostics: input.policyFundingDiagnostics,
      groups,
    };
  }

  const focusLabels = groups.slice(0, 2).map((group) => group.label);
  const focusText =
    focusLabels.length > 0 ? `，重点集中在${focusLabels.join("、")}。` : "。";
  return {
    headline: `${input.newsItems.length} 条政策与资金面快讯${focusText}`,
    chips,
    diagnostics: input.policyFundingDiagnostics,
    groups,
  };
}

export function buildHomeMacroBriefingModel(input: {
  todayIsoDate: string;
  newsEvents?: readonly ChoiceNewsEvent[] | null;
  fallbackNewsEvents?: readonly ChoiceNewsEvent[] | null;
  newsLoading: boolean;
  newsError: boolean;
  supplyCalendar: HomeResearchCalendarModel;
}): HomeMacroBriefingModel {
  const releaseItems = buildReleaseItems(input.todayIsoDate);
  const news = resolveHomeMacroNewsBriefing({
    choiceEvents: input.newsEvents,
    fallbackEvents: input.fallbackNewsEvents,
    todayIsoDate: input.todayIsoDate,
    isLoading: input.newsLoading,
    isError: input.newsError,
  });

  return {
    releaseItems,
    releaseWindowLabel:
      releaseItems.length > 0 ? `未来 ${RELEASE_WINDOW_DAYS} 天 · ${releaseItems.length} 项` : `未来 ${RELEASE_WINDOW_DAYS} 天`,
    releaseMessage: releaseItems.length > 0 ? null : "暂无已维护发布日期，请补充配置清单。",
    ...news,
    policyFundingSummary: buildPolicyFundingSummary(news),
    supplyItems: buildSupplyItems(input.supplyCalendar),
  };
}
