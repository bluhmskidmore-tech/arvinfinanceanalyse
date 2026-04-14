export type DashboardMockTask = {
  id: string;
  title: string;
  due: string;
  priority: "high" | "medium" | "low";
};

export type DashboardMockCalendarItem = {
  id: string;
  title: string;
  time: string;
  kind: "macro" | "supply" | "internal";
};

/** Placeholder until executive task / calendar APIs exist. */
export const DASHBOARD_MOCK_TASKS: DashboardMockTask[] = [
  {
    id: "t1",
    title: "复核昨日信用利差跳变较大的行业敞口",
    due: "今日15:00",
    priority: "high",
  },
  {
    id: "t2",
    title: "与司库确认本周同业负债滚续窗口",
    due: "今日 17:00",
    priority: "medium",
  },
  {
    id: "t3",
    title: "更新跨资产观察名单（原油 /汇率）",
    due: "明日 10:00",
    priority: "low",
  },
];

export const DASHBOARD_MOCK_CALENDAR: DashboardMockCalendarItem[] = [
  {
    id: "c1",
    title: "美国 CPI 发布",
    time: "2026-04-15 20:30",
    kind: "macro",
  },
  {
    id: "c2",
    title: "附息国债招标",
    time: "2026-04-16 10:35",
    kind: "supply",
  },
  {
    id: "c3",
    title: "内部 ALM 例会",
    time: "2026-04-16 14:00",
    kind: "internal",
  },
];
