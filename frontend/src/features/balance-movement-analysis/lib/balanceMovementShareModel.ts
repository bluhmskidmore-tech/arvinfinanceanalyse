export function nullableNumber(value: string | number | null | undefined): number | null {
  if (
    value === null
    || value === undefined
    || (typeof value === "string" && value.trim() === "")
  ) {
    return null;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/** The governed backend share is authoritative; missing stays missing. */
export function resolveBucketSharePct(
  backendPct: string | number | null | undefined,
): number | null {
  return nullableNumber(backendPct);
}
