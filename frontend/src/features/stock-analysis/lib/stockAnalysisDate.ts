const ISO_CALENDAR_DATE_PATTERN = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/;

function parseIsoCalendarDate(value: string | null | undefined): Date | null {
  const normalized = value?.trim();
  if (!normalized) return null;

  const match = normalized.match(ISO_CALENDAR_DATE_PATTERN);
  if (!match) return null;

  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (year < 1) return null;

  const parsed = new Date(0);
  parsed.setUTCHours(0, 0, 0, 0);
  parsed.setUTCFullYear(year, month - 1, day);

  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    return null;
  }

  return parsed;
}

function formatIsoCalendarDate(value: Date): string {
  const year = String(value.getUTCFullYear()).padStart(4, "0");
  const month = String(value.getUTCMonth() + 1).padStart(2, "0");
  const day = String(value.getUTCDate()).padStart(2, "0");
  return year + "-" + month + "-" + day;
}

export function normalizeIsoCalendarDate(value: string | null | undefined): string | null {
  const parsed = parseIsoCalendarDate(value);
  return parsed ? formatIsoCalendarDate(parsed) : null;
}

export function subtractIsoCalendarDays(
  value: string | null | undefined,
  days: number,
): string | null {
  const parsed = parseIsoCalendarDate(value);
  if (!parsed || !Number.isSafeInteger(days) || days < 0) return null;

  parsed.setUTCDate(parsed.getUTCDate() - days);
  return formatIsoCalendarDate(parsed);
}
