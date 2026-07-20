/** Avoid treating healthy copy like「无待处理项」as pending because it contains「待」. */
export function isEvidenceBookRowPending(support: string, gap: string): boolean {
  const text = `${support} ${gap}`;
  return /(?:\d+\s*项待处理|待返回|待确认|待复核|待补|待完整|等待|项降级|读取失败|缺失|不可用|延后)/.test(text);
}
