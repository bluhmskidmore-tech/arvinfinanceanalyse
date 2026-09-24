import type { ChoiceMacroLatestPoint, MacroVendorSeries } from "../../../api/contracts";

export type MacroThemeGroupKey =
  | "rates"
  | "monetary"
  | "policy"
  | "inflation"
  | "activity"
  | "equity"
  | "commodity"
  | "credit"
  | "global"
  | "other";

export type MacroThemeGroupDef = {
  key: MacroThemeGroupKey;
  title: string;
  caption: string;
};

export const MACRO_THEME_GROUP_DEFS: readonly MacroThemeGroupDef[] = [
  {
    key: "rates",
    title: "利率与流动性",
    caption: "国债、回购、资金价格与市场利率曲线。",
  },
  {
    key: "monetary",
    title: "货币与社融",
    caption: "M0/M1/M2、社融与货币供应相关读数。",
  },
  {
    key: "policy",
    title: "货币政策",
    caption: "存款准备金率、政策工具利率等官方政策读数。",
  },
  {
    key: "inflation",
    title: "通胀",
    caption: "CPI、PPI 等价格与通胀序列。",
  },
  {
    key: "activity",
    title: "经济增长",
    caption: "GDP、工业增加值等增长与产出读数。",
  },
  {
    key: "equity",
    title: "权益市场",
    caption: "指数、估值、权重集中度等权益读数。",
  },
  {
    key: "commodity",
    title: "大宗商品",
    caption: "能源、金属、期货等商品序列。",
  },
  {
    key: "credit",
    title: "信用与利差",
    caption: "信用债、利差与相关衍生读数。",
  },
  {
    key: "global",
    title: "跨境与全球",
    caption: "美债、外盘等跨资产宏观序列。",
  },
  {
    key: "other",
    title: "其他宏观",
    caption: "暂未归入以上主题的序列。",
  },
] as const;

/** Collapsed preview for isolated card tests and legacy callers. */
export const MACRO_THEME_CARD_DEFAULT_VISIBLE_COUNT = 3;
/** Optional preview cap; supplementary deck defaults to showing all rows with in-card scroll. */
export const MACRO_THEME_SUPPLEMENTARY_VISIBLE_COUNT = 12;
export const MACRO_THEME_CHART_MIN_CHARTABLE_SERIES = 2;
export const MACRO_THEME_CHART_MAX_SERIES = 5;

export type MacroThemeGroupBucket = {
  key: MacroThemeGroupKey;
  title: string;
  caption: string;
  series: ChoiceMacroLatestPoint[];
};

function catalogEntryFor(
  seriesId: string,
  catalogById: ReadonlyMap<string, MacroVendorSeries> | undefined,
): MacroVendorSeries | undefined {
  return catalogById?.get(seriesId);
}

function tagSet(
  point: ChoiceMacroLatestPoint,
  catalogById: ReadonlyMap<string, MacroVendorSeries> | undefined,
): Set<string> {
  const entry = catalogEntryFor(point.series_id, catalogById);
  return new Set([...(entry?.tags ?? []), ...(entry?.theme ? [entry.theme] : [])]);
}

function nameLooksLikeActivity(name: string): boolean {
  return /GDP|工业增加值|工业增/.test(name);
}

function nameLooksLikeInflation(name: string): boolean {
  return /CPI|PPI|通胀/.test(name);
}

function nameLooksLikeMonetary(name: string): boolean {
  return /(?:^|[:\s])M[012](?:[:-\s]|$)|M1-M2|社会融资|广义货币|货币供应|人均存款/.test(name);
}

function nameLooksLikePolicy(name: string): boolean {
  return /存款准备金率|MLF|SLF/.test(name);
}

function nameLooksLikeRates(name: string): boolean {
  return /国债|国开|回购|SHIBOR|DR007|收益率|逆回购|R007|LPR|同业|中间价|掉期/.test(name);
}

function nameLooksLikeEquity(name: string): boolean {
  return /沪深|指数|收盘|权重|市盈率|\bPE\b|成分|上证|深证|创业板|恒生|总市值/.test(name);
}

function nameLooksLikeCommodity(name: string, unit: string): boolean {
  if (unit === "CNY/t" || unit === "USD/bbl" || unit === "元/吨" || unit === "美元/桶") {
    return true;
  }
  return /期货|原油| Brent|铜|铝|螺纹|铁矿|黄金|白银|商品|现货价/.test(name);
}

function nameLooksLikeCredit(name: string): boolean {
  return /信用|利差|中票|城投|MTN|CDS|债务占/.test(name);
}

function nameLooksLikeGlobal(name: string, tags: Set<string>): boolean {
  if (tags.has("us_treasury") || tags.has("global") || tags.has("cross_asset")) {
    if (
      nameLooksLikeRates(name) ||
      nameLooksLikeEquity(name) ||
      nameLooksLikeCommodity(name, "") ||
      nameLooksLikeInflation(name)
    ) {
      return false;
    }
    return /美债|美国|Fed|联邦基金|美元|离岸|全球|Brent|WTI/.test(name) || tags.has("us_treasury");
  }
  return false;
}

function hasSpecificMacroTag(tags: Set<string>, key: MacroThemeGroupKey): boolean {
  switch (key) {
    case "activity":
      return tags.has("activity") || tags.has("growth");
    case "inflation":
      return tags.has("inflation");
    case "monetary":
      return tags.has("money_supply") || tags.has("monetary") || tags.has("money");
    case "policy":
      return tags.has("policy");
    case "rates":
      return tags.has("chinabond") || (tags.has("rates") && tags.has("liquidity"));
    case "equity":
      return tags.has("equity") || tags.has("csi300") || tags.has("valuation");
    case "commodity":
      return tags.has("commodity");
    case "credit":
      return tags.has("credit") || tags.has("spreads");
    case "global":
      return tags.has("global") || tags.has("cross_asset") || tags.has("us_treasury");
    default:
      return false;
  }
}

export function classifyMacroThemeGroup(
  point: ChoiceMacroLatestPoint,
  catalogById?: ReadonlyMap<string, MacroVendorSeries>,
): MacroThemeGroupKey {
  const tags = tagSet(point, catalogById);
  const name = point.series_name;
  const unit = point.unit ?? "";

  if (nameLooksLikeInflation(name) || hasSpecificMacroTag(tags, "inflation")) {
    return "inflation";
  }
  if (nameLooksLikeActivity(name) || hasSpecificMacroTag(tags, "activity")) {
    return "activity";
  }
  if (nameLooksLikePolicy(name) || hasSpecificMacroTag(tags, "policy")) {
    return "policy";
  }
  if (nameLooksLikeMonetary(name) || hasSpecificMacroTag(tags, "monetary")) {
    return "monetary";
  }
  if (nameLooksLikeRates(name) || hasSpecificMacroTag(tags, "rates")) {
    return "rates";
  }
  if (nameLooksLikeEquity(name) || hasSpecificMacroTag(tags, "equity")) {
    return "equity";
  }
  if (nameLooksLikeCommodity(name, unit) || hasSpecificMacroTag(tags, "commodity")) {
    return "commodity";
  }
  if (nameLooksLikeCredit(name) || hasSpecificMacroTag(tags, "credit")) {
    return "credit";
  }
  if (nameLooksLikeGlobal(name, tags) || hasSpecificMacroTag(tags, "global")) {
    return "global";
  }
  if (tags.has("liquidity") && !tags.has("macro_market")) {
    return "monetary";
  }
  return "other";
}

export function groupMacroSeriesByTheme(
  series: readonly ChoiceMacroLatestPoint[],
  catalog?: readonly MacroVendorSeries[],
): MacroThemeGroupBucket[] {
  const catalogById = new Map((catalog ?? []).map((entry) => [entry.series_id, entry]));
  const buckets = new Map<MacroThemeGroupKey, ChoiceMacroLatestPoint[]>();

  for (const point of series) {
    const key = classifyMacroThemeGroup(point, catalogById);
    const list = buckets.get(key) ?? [];
    list.push(point);
    buckets.set(key, list);
  }

  return MACRO_THEME_GROUP_DEFS.flatMap((def) => {
    const grouped = buckets.get(def.key);
    if (!grouped || grouped.length === 0) {
      return [];
    }
    return [
      {
        key: def.key,
        title: def.title,
        caption: def.caption,
        series: grouped,
      },
    ];
  });
}

export function buildMacroCatalogById(
  catalog: readonly MacroVendorSeries[] | undefined,
): Map<string, MacroVendorSeries> {
  return new Map((catalog ?? []).map((entry) => [entry.series_id, entry]));
}

function chartableSeriesCount(series: readonly ChoiceMacroLatestPoint[]): number {
  return series.filter((point) => (point.recent_points?.length ?? 0) >= 2).length;
}

export function canRenderMacroThemeChart(series: readonly ChoiceMacroLatestPoint[]): boolean {
  return chartableSeriesCount(series) >= MACRO_THEME_CHART_MIN_CHARTABLE_SERIES;
}
