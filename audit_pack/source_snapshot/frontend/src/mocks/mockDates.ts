/**
 * Mock date utilities — generate dates relative to "today" so mock data
 * never becomes stale.  Used exclusively by mock client factories.
 *
 * Test files should NOT use these helpers; tests need deterministic dates.
 */

/** Today's date as YYYY-MM-DD. */
export function mockToday(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Last day of the month that is `monthsAgo` months before today. */
export function mockMonthEnd(monthsAgo = 0): string {
  const d = new Date();
  d.setMonth(d.getMonth() - monthsAgo);
  // Set to last day of that month
  d.setMonth(d.getMonth() + 1, 0);
  return d.toISOString().slice(0, 10);
}

/** Array of month-end dates, most recent first. */
export function mockReportDates(count = 3): string[] {
  return Array.from({ length: count }, (_, i) => mockMonthEnd(i));
}

/**
 * Most recent business day `daysAgo` calendar days before today.
 * Skips weekends (Sat/Sun).
 */
export function mockTradeDate(daysAgo = 1): string {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  const day = d.getDay();
  if (day === 0) d.setDate(d.getDate() - 2);
  if (day === 6) d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

/** ISO-8601 timestamp for `generated_at` / `computed_at` fields. */
export function mockGeneratedAt(): string {
  return new Date().toISOString();
}
