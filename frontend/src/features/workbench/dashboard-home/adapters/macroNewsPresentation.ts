import type { ChoiceNewsEvent } from "../../../../api/contracts";

/** 首页宏观新闻兜底（Tushare）允许展示的关键词；Choice 专题不走此过滤。 */
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

export function isMacroRelevantForHomeBriefing(text: string): boolean {
  const normalized = text.trim();
  if (!normalized) {
    return false;
  }
  const normalizedLower = normalized.toLowerCase();
  return HOME_MACRO_NEWS_KEYWORDS.some((keyword) => normalizedLower.includes(keyword.toLowerCase()));
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

export function summarizeMacroNewsEvent(event: ChoiceNewsEvent): string {
  const jsonTitle = extractTitleFromPayloadJson(event.payload_json);
  const payloadText = stripHtmlTags(event.payload_text?.trim() ?? "");
  if (jsonTitle) {
    return jsonTitle;
  }
  if (!payloadText) {
    return "";
  }
  const headline = payloadText.split(" — ")[0]?.trim() ?? payloadText;
  return stripHtmlTags(headline);
}

export function shouldIncludeMacroNewsEvent(
  event: ChoiceNewsEvent,
  options: { requireMacroRelevance: boolean },
): boolean {
  if (event.error_code !== 0) {
    return false;
  }
  const title = summarizeMacroNewsEvent(event);
  if (!isDisplayableMacroNewsText(title)) {
    return false;
  }
  if (options.requireMacroRelevance && !isMacroRelevantForHomeBriefing(title)) {
    return false;
  }
  return true;
}
