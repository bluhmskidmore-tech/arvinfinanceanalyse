export interface CompleteMonthOption {
  month: string;
  value: string;
  label: string;
}

const toYearMonth = (value: Date): string => {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
};

export const getCompleteMonthOptions = (
  availableDates: string[],
  referenceDate: Date = new Date(),
): CompleteMonthOption[] => {
  if (!availableDates.length) return [];

  const currentMonth = toYearMonth(referenceDate);
  const sortedDates = [...new Set(availableDates.filter(Boolean))].sort((a, b) =>
    a > b ? -1 : a < b ? 1 : 0,
  );
  const latestDateByMonth = new Map<string, string>();

  for (const reportDate of sortedDates) {
    const month = reportDate.slice(0, 7);
    if (month === currentMonth || latestDateByMonth.has(month)) continue;
    latestDateByMonth.set(month, reportDate);
  }

  return Array.from(latestDateByMonth.entries()).map(([month, value]) => {
    const [year, monthNumber] = month.split("-");
    return { month, value, label: `${year}年${Number(monthNumber)}月` };
  });
};
