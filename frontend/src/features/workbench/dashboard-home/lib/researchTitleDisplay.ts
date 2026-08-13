/**
 * 研报/新闻标题的显示层清洗：去文件扩展名与尾部日期戳、下划线转空格。
 * 仅用于可见文本；链接 href 与 title 属性保留原文，不改变任何业务数据。
 */
export function formatResearchTitleDisplay(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return trimmed;
  let value = trimmed.replace(/\.(pdf|docx?|xlsx?|pptx?)\s*$/iu, "");
  // 尾部日期戳（如 _20260715）：发布时间已有独立列，可见标题不重复。
  value = value.replace(/[_\s]*20\d{6}\s*$/u, "");
  value = value.replaceAll("_", " ").replace(/\s{2,}/gu, " ").trim();
  return value || trimmed;
}
