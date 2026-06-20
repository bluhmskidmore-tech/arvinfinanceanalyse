import type { ResultMeta } from "../../../api/contracts";

export function buildReviewEvidenceLabel(input: {
  domainsEffectiveDate: Record<string, string>;
  overviewMeta: ResultMeta | null;
  attributionMeta: ResultMeta | null;
}): string {
  const dates = Object.entries(input.domainsEffectiveDate)
    .map(([domain, date]) => `${domain}=${date}`)
    .join(" / ");
  if (dates) {
    return dates;
  }
  const meta = input.overviewMeta ?? input.attributionMeta;
  if (meta) {
    return [meta.source_version, meta.rule_version, meta.cache_version]
      .filter((part) => part && part !== "unknown")
      .join(" / ");
  }
  return "首页快照返回后展示来源版本与有效日期";
}

export function addDaysToIsoDate(date: string, days: number): string {
  const trimmed = date.trim();
  if (!trimmed) {
    return "";
  }
  const parsed = new Date(`${trimmed}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return trimmed;
  }
  parsed.setUTCDate(parsed.getUTCDate() + days);
  return parsed.toISOString().slice(0, 10);
}

export function todayIsoDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function reportDateMismatch(expected: string, actual: string | undefined): boolean {
  const expectedTrimmed = expected.trim();
  const actualTrimmed = actual?.trim() ?? "";
  return expectedTrimmed.length > 0 && actualTrimmed.length > 0 && expectedTrimmed !== actualTrimmed;
}

function readErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return "unknown error";
}

export function isNetworkUnavailableError(error: unknown): boolean {
  const message = readErrorMessage(error).toLowerCase();
  return [
    "failed to fetch",
    "fetch failed",
    "networkerror",
    "network request failed",
    "err_connection_refused",
    "connection refused",
    "network unavailable",
    "load failed",
  ].some((part) => message.includes(part));
}
