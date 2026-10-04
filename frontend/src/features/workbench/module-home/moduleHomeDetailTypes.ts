export type ModuleHomeTone = "ok" | "watch" | "error" | "muted";

export type ModuleHomeDetailRow = {
  key: string;
  label: string;
  value: string;
  tradeDate: string;
  source: string;
  tone: ModuleHomeTone;
  /** 日变动等补充说明，关键利率表单独占列展示 */
  detail?: string;
  /** 来自 recent_points 的迷你走势，仅展示用途 */
  sparkline?: readonly number[];
  /** portfolio-comparison 分列读数（仅展示，不补算） */
  scaleDisplay?: string;
  durationDisplay?: string;
  ytmDisplay?: string;
  coverageNote?: string;
  dv01Display?: string;
  countDisplay?: string;
};

export type ModuleHomeDetailChart = {
  title: string;
  unit: string;
  orientation: "horizontal" | "vertical";
  categories: string[];
  /** 缺失值保留 null（图表画断点、tooltip 显示 —），不得补 0。 */
  values: Array<number | null>;
};

export type ModuleHomeDetailSection = {
  key: string;
  title: string;
  subtitle?: string;
  rows: ModuleHomeDetailRow[];
  defaultExpanded?: boolean;
};

export type ModuleHomeDetailPanel = {
  key: string;
  title: string;
  meta: string;
  stateLabel: string;
  stateDetail: string;
  rows: ModuleHomeDetailRow[];
  sections?: ModuleHomeDetailSection[];
  tone: ModuleHomeTone;
  chart?: ModuleHomeDetailChart;
};

