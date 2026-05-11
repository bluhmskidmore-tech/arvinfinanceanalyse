export function dashboardBondHeadlineQueryKey(mode: string, reportDate: string) {
  return ["dashboard", "bond-headline-kpis", mode, reportDate] as const;
}
