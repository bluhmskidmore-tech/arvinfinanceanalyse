import type {
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  ChoiceNewsEventsPayload,
  MarketDataCatalogPayload,
} from "../../../api/contracts";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitIndicator,
} from "../../../api/macroToolkitClient";
import {
  formatChoiceMacroDelta,
  formatChoiceMacroValue,
} from "../../../utils/choiceMacroFormat";
import type {
  ModuleHomeDetailPanel,
  ModuleHomeDetailRow,
  ModuleHomeTone,
} from "./moduleHomeModel";

export type DenseTapeTone = "up" | "down" | "ok" | "muted";

export type DenseTapeMetric = {
  key: string;
  label: string;
  value: string;
  delta: string;
  tone: DenseTapeTone;
  title: string;
  tradeDate?: string;
};

export type DenseLedgerRow = {
  key: string;
  label: string;
  value: string;
  delta: string;
  reportDate: string;
  tone: ModuleHomeTone;
  source: string;
};

export type DenseAuditStats = {
  latest: number;
  formal: number;
  catalog: number;
  macro: number;
  strategies: number;
  news: number;
};

export type DenseMacroPulseRow = {
  key: string;
  label: string;
  previousValue: string;
  latestValue: string;
  change: string;
  changeLabel: "绝对变化" | "百分比变化" | "变化未返回";
  tone: DenseTapeTone;
  latestDate: string;
  source: string;
};

export type DenseNewsDensityCell = {
  key: string;
  count: number;
  intensity: 0 | 1 | 2 | 3 | 4;
};

export type DenseNewsDensityRow = {
  key: string;
  label: string;
  cells: DenseNewsDensityCell[];
};

export type DenseNewsDensity = {
  rows: DenseNewsDensityRow[];
  hourLabels: string[];
  maxCount: number;
  sampledEvents: number;
  startDate: string;
  endDate: string;
};

type DenseOverviewSource = {
  latest?: ChoiceMacroLatestPayload;
  rates?: ChoiceMacroLatestPayload;
  catalog?: MarketDataCatalogPayload;
  news?: ChoiceNewsEventsPayload;
  macroSectionCount?: number;
  strategySectionCount?: number;
};

function pointText(point: ChoiceMacroLatestPoint) {
  return `${point.series_id} ${point.series_name}`.toLowerCase();
}

function findPoint(
  points: readonly ChoiceMacroLatestPoint[],
  predicate: (text: string, point: ChoiceMacroLatestPoint) => boolean,
) {
  return points.find((point) => predicate(pointText(point), point));
}

function compactNumber(value: number) {
  const maximumFractionDigits =
    Math.abs(value) < 10 ? 4 : Math.abs(value) < 1000 ? 2 : 2;
  return value.toLocaleString("zh-CN", {
    maximumFractionDigits,
    minimumFractionDigits: 0,
  });
}

function normalizeDenseUnit(unit: string | null | undefined) {
  const normalized = unit?.trim() ?? "";
  return normalized && normalized.toLowerCase() !== "unknown"
    ? normalized
    : "";
}

function denseUnitSuffix(unit: string | null | undefined) {
  const normalized = normalizeDenseUnit(unit);
  if (!normalized) return "";
  return /^(?:%|‰|bp|bps)$/i.test(normalized)
    ? normalized
    : ` ${normalized}`;
}

function compactPointValue(point: ChoiceMacroLatestPoint) {
  return formatDenseValue(point.value_numeric, point.unit);
}

function formatDenseValue(value: number | null, unit: string) {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${compactNumber(value)}${denseUnitSuffix(unit)}`;
}

function indicatorSearchText(indicator: MacroToolkitIndicator) {
  return `${indicator.key} ${indicator.alias} ${indicator.label} ${indicator.series_id ?? ""}`;
}

const MACRO_PULSE_PREFERENCES = [
  /\bcpi\b|居民消费价格/i,
  /\bppi\b|工业生产者价格/i,
  /\bpmi\b|采购经理/i,
  /社会融资|社融/i,
] as const;

export function buildDenseMacroPulseRows(
  macro:
    | Pick<MacroToolkitAnalysisPayload, "as_of_date" | "indicators">
    | undefined,
  limit = 4,
): DenseMacroPulseRow[] {
  const candidates = macro?.indicators ?? [];
  const selected: MacroToolkitIndicator[] = [];
  const used = new Set<string>();
  for (const preference of MACRO_PULSE_PREFERENCES) {
    const match = candidates.find(
      (indicator) =>
        !used.has(indicator.key) &&
        preference.test(indicatorSearchText(indicator)),
    );
    if (match) {
      selected.push(match);
      used.add(match.key);
    }
  }
  for (const indicator of candidates) {
    if (selected.length >= limit) break;
    if (
      !used.has(indicator.key) &&
      indicator.latest_value != null &&
      Number.isFinite(indicator.latest_value)
    ) {
      selected.push(indicator);
      used.add(indicator.key);
    }
  }
  return selected.slice(0, limit).map((indicator) => {
    const hasAbsoluteChange =
      indicator.change != null && Number.isFinite(indicator.change);
    const hasPercentageChange =
      indicator.change_pct != null && Number.isFinite(indicator.change_pct);
    const changeValue = hasAbsoluteChange
      ? indicator.change
      : hasPercentageChange
        ? indicator.change_pct
        : null;
    return {
      key: indicator.key,
      label: indicator.label,
      previousValue: formatDenseValue(indicator.previous_value, indicator.unit),
      latestValue: formatDenseValue(indicator.latest_value, indicator.unit),
      change:
        changeValue == null || !Number.isFinite(changeValue)
          ? "—"
          : `${changeValue > 0 ? "+" : ""}${compactNumber(changeValue)}${denseUnitSuffix(
              hasAbsoluteChange ? indicator.unit : "%",
            )}`,
      changeLabel: hasAbsoluteChange
        ? "绝对变化"
        : hasPercentageChange
          ? "百分比变化"
          : "变化未返回",
      tone: directionTone(changeValue),
      latestDate: indicator.latest_date || macro?.as_of_date || "—",
      source: indicator.source || indicator.series_id || "来源未返回",
    };
  });
}

function newsTopicKey(topicCode: string, groupId: string) {
  return topicCode.trim() || groupId.trim() || "未分类";
}

const FRIENDLY_NEWS_TOPIC_LABELS: Readonly<Record<string, string>> = {
  "major news": "主要新闻",
  sina: "新浪",
  "tushare.major_news": "主要新闻",
  tushare_major: "主要新闻",
  "tushare.news.sina": "新浪",
  tushare_news: "新浪",
};

// 形如 tushare.research_report.20260712_20260715 的研报主题按族归并展示。
const RESEARCH_REPORT_TOPIC_PATTERN = /^tushare\.research_report(?:[._-]|$)/i;

export function formatDenseNewsTopicLabel(value: string) {
  const rawValue = value.trim() || "未分类";
  const friendly = FRIENDLY_NEWS_TOPIC_LABELS[rawValue.toLowerCase()];
  if (friendly) return friendly;
  if (RESEARCH_REPORT_TOPIC_PATTERN.test(rawValue)) return "研究报告";
  return rawValue;
}

function bucketableNewsTime(receivedAt: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T?(\d{2})/.exec(receivedAt);
  if (!match) return null;
  const [, yearText, monthText, dayText, hourText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const hour = Number(hourText);
  if (hour < 0 || hour > 23) return null;
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }
  return { date: receivedAt.slice(0, 10), hour };
}

export function buildDenseNewsDensity(
  news: ChoiceNewsEventsPayload | undefined,
  topicCount = 7,
): DenseNewsDensity {
  const validEvents = (news?.events ?? []).flatMap((event) => {
    const receivedTime = bucketableNewsTime(event.received_at);
    return receivedTime ? [{ event, receivedTime }] : [];
  });
  const sampledDates = validEvents.map(({ receivedTime }) => receivedTime.date).sort();
  const topicTotals = new Map<string, number>();
  const counts = new Map<string, number>();
  for (const { event, receivedTime } of validEvents) {
    const { hour } = receivedTime;
    const topic = newsTopicKey(event.topic_code, event.group_id);
    const bucket = Math.floor(hour / 2);
    const key = `${topic}-${bucket}`;
    topicTotals.set(topic, (topicTotals.get(topic) ?? 0) + 1);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const topics = [...topicTotals.entries()]
    .sort(
      ([leftTopic, leftCount], [rightTopic, rightCount]) =>
        rightCount - leftCount || leftTopic.localeCompare(rightTopic),
    )
    .slice(0, topicCount)
    .map(([topic]) => topic);
  const maxCount = Math.max(0, ...counts.values());
  const rows = topics.map((topic) => ({
    key: topic,
    label: formatDenseNewsTopicLabel(topic),
    cells: Array.from({ length: 12 }, (_, bucket) => {
      const key = `${topic}-${bucket}`;
      const count = counts.get(key) ?? 0;
      const intensity: DenseNewsDensityCell["intensity"] =
        count === 0 || maxCount === 0
          ? 0
          : (Math.min(
              4,
              Math.max(1, Math.ceil((count / maxCount) * 4)),
            ) as DenseNewsDensityCell["intensity"]);
      return { key, count, intensity };
    }),
  }));
  return {
    rows,
    hourLabels: Array.from({ length: 12 }, (_, bucket) =>
      String(bucket * 2).padStart(2, "0"),
    ),
    maxCount,
    sampledEvents: validEvents.length,
    startDate: sampledDates.at(0) ?? news?.as_of_date ?? "",
    endDate: sampledDates.at(-1) ?? news?.as_of_date ?? "",
  };
}

function directionTone(value: number | null | undefined): DenseTapeTone {
  if (value == null || value === 0) return "muted";
  return value > 0 ? "up" : "down";
}

const TEN_YEAR_HINT = /10\s*(?:y|yr|year)|10\s*\u5e74/i;
const CHINA_SOVEREIGN_HINT =
  /\b(?:china|cgb)\b|\u4e2d\u56fd|\u4e2d\u503a|\u56fd\u503a/i;
const FOREIGN_SOVEREIGN_HINT =
  /\b(?:us|u\.s\.|usa|uk|u\.k\.|gbr|jp|jpn|japan|treasury|gilt|jgb)\b|\u7f8e\u56fd|\u82f1\u56fd|\u65e5\u672c/i;

function isChinaTenYearPoint(point: ChoiceMacroLatestPoint) {
  const searchText = `${point.series_id} ${point.series_name}`;
  if (!TEN_YEAR_HINT.test(searchText)) return false;
  if (FOREIGN_SOVEREIGN_HINT.test(searchText)) return false;
  return /^cn[._-]/i.test(point.series_id) || CHINA_SOVEREIGN_HINT.test(searchText);
}

function pointMetric({
  key,
  label,
  point,
  changePoint,
}: {
  key: string;
  label: string;
  point: ChoiceMacroLatestPoint | undefined;
  changePoint?: ChoiceMacroLatestPoint;
}): DenseTapeMetric {
  if (!point) {
    return {
      key,
      label,
      value: "—",
      delta: "未返回",
      tone: "muted",
      title: `${label}：后端未返回匹配序列`,
    };
  }
  const directChange = changePoint
    ? formatChoiceMacroValue(changePoint, { spaceBeforeUnit: false })
    : null;
  return {
    key,
    label,
    value: compactPointValue(point),
    delta:
      directChange ??
      formatChoiceMacroDelta(point, {
        spaceBeforeUnit: false,
        emptyDisplay: "无前值",
      }),
    tone: directionTone(
      changePoint?.value_numeric ?? point.latest_change,
    ),
    title: `${point.series_name} · ${formatChoiceMacroValue(point)} · ${point.trade_date}`,
    tradeDate: point.trade_date,
  };
}

export function buildDenseTapeMetrics({
  latest,
  rates,
}: DenseOverviewSource): DenseTapeMetric[] {
  const latestPoints = latest?.series ?? [];
  const ratePoints = rates?.series ?? [];
  const merged = [...ratePoints, ...latestPoints];
  const tenYear = merged.find(isChinaTenYearPoint);
  const dr007 = findPoint(merged, (text) => /dr\s*0?07/i.test(text));
  const csiClose = findPoint(
    latestPoints,
    (text) => /沪深\s*300|csi\s*300|hs300/i.test(text) && /收盘|close/i.test(text),
  );
  const csiChange = findPoint(
    latestPoints,
    (text) => /沪深\s*300|csi\s*300|hs300/i.test(text) && /涨跌幅|pct.?chg|change/i.test(text),
  );
  const brent = findPoint(latestPoints, (text) => /brent|布伦特/i.test(text));
  const usdCny = findPoint(
    latestPoints,
    (text) => /usd\s*\/?\s*cny|美元兑人民币|usdcny/i.test(text),
  );
  const reverseRepo7d = findPoint(
    merged,
    (text, point) =>
      point.series_id === "EMM00088132" ||
      (/逆回购/.test(text) && /7\s*天|7d/i.test(text)),
  );
  const shibor3m = findPoint(
    merged,
    (text, point) =>
      point.series_id === "NCD.SHIBOR.3M" ||
      (/shibor/i.test(text) && /3\s*m|3\s*月/i.test(text)),
  );
  const copper = findPoint(
    latestPoints,
    (text, point) =>
      point.series_id === "CA.COPPER" || /铜.*(收盘|期货)|copper/i.test(text),
  );

  return [
    pointMetric({ key: "gov-10y", label: "10Y国债", point: tenYear }),
    pointMetric({ key: "dr007", label: "DR007", point: dr007 }),
    pointMetric({
      key: "reverse-repo-7d",
      label: "7D逆回购",
      point: reverseRepo7d,
    }),
    pointMetric({
      key: "shibor-3m",
      label: "SHIBOR 3M",
      point: shibor3m,
    }),
    pointMetric({
      key: "csi300",
      label: "沪深300",
      point: csiClose,
      changePoint: csiChange,
    }),
    pointMetric({ key: "brent", label: "Brent原油", point: brent }),
    pointMetric({ key: "usd-cny", label: "USD/CNY", point: usdCny }),
    pointMetric({ key: "copper", label: "铜主力", point: copper }),
  ];
}

const LEDGER_PANEL_ORDER = [
  "key-rate-snapshot",
  "latest-macro-snapshot",
  "macro-toolkit-indicators",
  "macro-toolkit-a-share-risk",
  "yield-curve-quotes",
] as const;

const LEDGER_PREFERENCES = [
  /10y|10年|十年/i,
  /dr\s*0?07/i,
  /逆回购|r007/i,
  /沪深\s*300|csi\s*300/i,
  /brent|原油/i,
  /usd\s*\/?\s*cny|美元兑人民币/i,
  /黄金|comex|gold/i,
  /信用利差/i,
  /\bcpi\b|居民消费价格/i,
  /\bppi\b|工业生产者/i,
  /\bpmi\b|采购经理/i,
  /社会融资|社融/i,
] as const;

function rowSearchText(row: ModuleHomeDetailRow) {
  return `${row.key} ${row.label} ${row.source}`;
}

function toDenseLedgerRow(row: ModuleHomeDetailRow): DenseLedgerRow {
  return {
    key: row.key,
    label: row.label,
    value: row.value,
    delta: row.detail?.split(/\s+\/\s+/)[0] ?? "—",
    reportDate: row.tradeDate || "—",
    tone: row.tone,
    source: row.source,
  };
}

export function buildDenseLedgerRows(
  panels: readonly ModuleHomeDetailPanel[] | undefined,
  limit = 12,
): DenseLedgerRow[] {
  const byKey = new Map((panels ?? []).map((panel) => [panel.key, panel]));
  const orderedPanels = [
    ...LEDGER_PANEL_ORDER.map((key) => byKey.get(key)).filter(
      (panel): panel is ModuleHomeDetailPanel => Boolean(panel),
    ),
    ...(panels ?? []).filter(
      (panel) => !LEDGER_PANEL_ORDER.some((panelKey) => panelKey === panel.key),
    ),
  ];
  const candidates = orderedPanels
    .flatMap((panel) => panel.rows)
    .filter(
      (row) =>
        !row.key.startsWith("news-event-") &&
        row.key !== "news-events-total",
    );
  const selected: ModuleHomeDetailRow[] = [];
  const used = new Set<string>();

  for (const preference of LEDGER_PREFERENCES) {
    const row = candidates.find(
      (candidate) =>
        !used.has(candidate.key) && preference.test(rowSearchText(candidate)),
    );
    if (row) {
      selected.push(row);
      used.add(row.key);
    }
  }
  for (const row of candidates) {
    if (selected.length >= limit) break;
    if (!used.has(row.key)) {
      selected.push(row);
      used.add(row.key);
    }
  }
  return selected.slice(0, limit).map(toDenseLedgerRow);
}

export function buildDenseAuditStats({
  latest,
  rates,
  catalog,
  news,
  macroSectionCount = 0,
  strategySectionCount = 0,
}: DenseOverviewSource): DenseAuditStats {
  return {
    latest: latest?.series.length ?? 0,
    formal: rates?.series.length ?? 0,
    catalog: catalog?.series.length ?? 0,
    macro: macroSectionCount,
    strategies: strategySectionCount,
    news: news?.total_rows ?? 0,
  };
}
