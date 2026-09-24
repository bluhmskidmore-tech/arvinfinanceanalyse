/**
 * 研报/新闻标题的显示层清洗：去文件扩展名与尾部日期戳、下划线转空格；
 * 传入 `sourcePrefixes`（如来源列的机构名）时，剥离与来源列重复的标题
 * 前缀（如「东吴证券 …」+ 来源列「东吴证券」）。
 * 仅用于可见文本；链接 href 与 title 属性保留原文，不改变任何业务数据。
 */
export function formatResearchTitleDisplay(
  raw: string,
  sourcePrefixes?: readonly (string | null | undefined)[],
): string {
  const trimmed = raw.trim();
  if (!trimmed) return trimmed;
  let value = trimmed.replace(/\.(pdf|docx?|xlsx?|pptx?)\s*$/iu, "");
  // 尾部日期戳（如 _20260715）：发布时间已有独立列，可见标题不重复。
  value = value.replace(/[_\s]*20\d{6}\s*$/u, "");
  value = value.replaceAll("_", " ").replace(/\s{2,}/gu, " ").trim();
  // 前导破折号是来源拼接残留，行首悬着一个「—」会被误读成缺失内容。
  value = value.replace(/^[—–\-·•]+\s*/u, "").trim();
  value = stripSourcePrefix(value, sourcePrefixes) || value;
  return value || trimmed;
}

/** 标题首词与来源列相同（含分隔符或空格边界）时剥离该前缀，长名优先。 */
function stripSourcePrefix(
  value: string,
  sourcePrefixes: readonly (string | null | undefined)[] | undefined,
): string {
  if (!sourcePrefixes?.length) return value;
  const candidates = [...new Set(
    sourcePrefixes
      .map((prefix) => prefix?.trim().replaceAll("_", " ") ?? "")
      .filter((prefix) => prefix.length > 0),
  )].sort((left, right) => right.length - left.length);
  for (const prefix of candidates) {
    if (!value.startsWith(prefix)) continue;
    const remainder = value.slice(prefix.length);
    const boundary = /^(?:\s+|\s*[：:—–\-·•]\s*)(.*)$/su.exec(remainder);
    if (boundary) {
      const stripped = boundary[1].trim();
      if (stripped) return stripped;
    }
  }
  return value;
}
