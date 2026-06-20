import type { ChoiceNewsEvent } from "../../../../api/contracts";

/** 首页宏观新闻兜底（Tushare）允许展示的关键词；保留给非首页债券新闻场景。 */
export const HOME_MACRO_NEWS_KEYWORDS = [
  "债券",
  "债市",
  "利率",
  "收益率",
  "国债",
  "地方债",
  "信用债",
  "政金债",
  "存单",
  "央行",
  "货币政策",
  "降准",
  "降息",
  "LPR",
  "MLF",
  "逆回购",
  "Shibor",
  "DR007",
  "R007",
  "财政",
  "国务院",
  "政策",
  "监管",
  "证监会",
  "金监",
  "GDP",
  "PMI",
  "CPI",
  "PPI",
  "通胀",
  "就业",
  "失业",
  "人民币",
  "汇率",
  "美元",
  "美联储",
  "欧央行",
  "加息",
  "原油",
  "金价",
  "黄金",
  "油价",
  "大宗",
  "A股",
  "沪深",
  "股指",
  "期货",
  "外汇",
  "房地产",
  "地产",
  "基建",
  "消费",
  "出口",
  "进口",
  "贸易",
  "关税",
  "银行",
  "金融",
  "信贷",
  "融资",
  "流动性",
  "资金面",
  "招标",
  "发行",
  "违约",
  "评级",
  "宏观",
  "经济",
  "数据",
  "国际",
  "地缘",
  "中东",
  "乌克兰",
  "台湾",
  "港股",
  "美股",
  "纳指",
  "标普",
] as const;

export const HOME_POLICY_FUNDING_NEWS_KEYWORDS = [
  "央行",
  "公开市场",
  "逆回购",
  "MLF",
  "DR007",
  "Shibor",
  "国债收益率",
  "地方债",
  "政金债",
  "货币政策",
] as const;

const HOME_POLICY_FUNDING_CONTEXT_PATTERNS = [
  /财政(?:政策|部|发力|支出|收入|赤字|预算|债务|扩张|收支|贴息|补贴|资金)/,
  /(?:地方|中央|积极|扩张性|紧缩性)财政/,
  /(?:国债|美债|英债|日债|地方债|政金债|利率债|债市).{0,18}(?:收益率|利率|基点|bp|BP|长端|短端)/,
  /(?:收益率|利率|基点|bp|BP|长端|短端).{0,18}(?:国债|美债|英债|日债|地方债|政金债|利率债|债市)/,
  /(?:央行|公开市场|银行间|债市|货币市场|流动性|逆回购|MLF|DR007|Shibor).{0,24}资金面/,
  /资金面.{0,24}(?:央行|公开市场|银行间|债市|货币市场|流动性|逆回购|MLF|DR007|Shibor|平稳|宽松|收紧|紧张)/,
  /(?:市场|银行间|资金|债市|货币|央行|公开市场|跨季|跨月)流动性/,
  /流动性(?:投放|回笼|充裕|宽松|收紧|紧张|缺口|管理|支持|工具)/,
] as const;

export function stripHtmlTags(raw: string): string {
  return raw
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\s+/g, " ")
    .trim();
}

export function isDisplayableMacroNewsText(text: string): boolean {
  const normalized = text.trim();
  if (normalized.length < 6) {
    return false;
  }
  if (/<\/?[a-z][^>]*>/i.test(normalized)) {
    return false;
  }
  return true;
}

export function hasLeadingHtmlPayload(event: ChoiceNewsEvent): boolean {
  return /^\s*<\/?[a-z][^>]*>/i.test(event.payload_text?.trim() ?? "");
}

export function isMacroRelevantForHomeBriefing(text: string): boolean {
  const normalized = text.trim();
  if (!normalized) {
    return false;
  }
  const normalizedLower = normalized.toLowerCase();
  return HOME_MACRO_NEWS_KEYWORDS.some((keyword) => normalizedLower.includes(keyword.toLowerCase()));
}

export function isPolicyFundingRelevantForHomeBriefing(text: string): boolean {
  const normalized = text.trim();
  if (!normalized) {
    return false;
  }
  const normalizedLower = normalized.toLowerCase();
  return (
    HOME_POLICY_FUNDING_NEWS_KEYWORDS.some((keyword) =>
      normalizedLower.includes(keyword.toLowerCase()),
    ) || HOME_POLICY_FUNDING_CONTEXT_PATTERNS.some((pattern) => pattern.test(normalized))
  );
}

function extractTitleFromPayloadJson(payloadJson: string | null | undefined): string {
  const raw = payloadJson?.trim();
  if (!raw) {
    return "";
  }
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const title = typeof parsed.title === "string" ? parsed.title.trim() : "";
    const headline = typeof parsed.headline === "string" ? parsed.headline.trim() : "";
    return stripHtmlTags(headline || title);
  } catch {
    return "";
  }
}

export function hasDisplayableMacroNewsJsonTitle(event: ChoiceNewsEvent): boolean {
  return isDisplayableMacroNewsText(extractTitleFromPayloadJson(event.payload_json));
}

function trimLeadingNewsSeparator(text: string): string {
  return text.replace(/^[\s—-]+/, "").trim();
}

export function summarizeMacroNewsEvent(event: ChoiceNewsEvent): string {
  const jsonTitle = extractTitleFromPayloadJson(event.payload_json);
  const payloadText = stripHtmlTags(event.payload_text?.trim() ?? "");
  if (jsonTitle) {
    return trimLeadingNewsSeparator(jsonTitle);
  }
  if (!payloadText) {
    return "";
  }
  const normalizedPayload = trimLeadingNewsSeparator(payloadText);
  const headline = normalizedPayload.split(" — ")[0]?.trim() ?? normalizedPayload;
  return trimLeadingNewsSeparator(stripHtmlTags(headline));
}

export function shouldIncludeMacroNewsEvent(
  event: ChoiceNewsEvent,
  options: { requireMacroRelevance: boolean; requirePolicyFundingRelevance?: boolean },
): boolean {
  if (event.error_code !== 0) {
    return false;
  }
  const title = summarizeMacroNewsEvent(event);
  if (hasLeadingHtmlPayload(event) && !hasDisplayableMacroNewsJsonTitle(event)) {
    return false;
  }
  if (!isDisplayableMacroNewsText(title)) {
    return false;
  }
  if (options.requireMacroRelevance && !isMacroRelevantForHomeBriefing(title)) {
    return false;
  }
  if (options.requirePolicyFundingRelevance && !isPolicyFundingRelevantForHomeBriefing(title)) {
    return false;
  }
  return true;
}
