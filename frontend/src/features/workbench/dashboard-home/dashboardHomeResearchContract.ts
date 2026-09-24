const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

export function normalizeHomeResearchPublishedDate(
  value: string | null | undefined,
): string | null {
  const candidate = value?.trim().slice(0, 10) ?? "";
  const match = ISO_DATE_PATTERN.exec(candidate);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    return null;
  }
  return candidate;
}

export function normalizeHomeResearchLink(
  value: string | null | undefined,
): string | null {
  const candidate = value?.trim() ?? "";
  if (!candidate) return null;

  try {
    const parsed = new URL(candidate);
    return parsed.protocol === "http:" || parsed.protocol === "https:"
      ? candidate
      : null;
  } catch {
    return null;
  }
}
