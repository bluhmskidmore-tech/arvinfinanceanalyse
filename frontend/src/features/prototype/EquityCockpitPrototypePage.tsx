import { useMemo } from "react";
import {
  AlertOutlined,
  BellOutlined,
  CalendarOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  DoubleLeftOutlined,
  ExperimentOutlined,
  ExportOutlined,
  FullscreenOutlined,
  FundOutlined,
  LineChartOutlined,
  PieChartOutlined,
  SafetyOutlined,
  SearchOutlined,
  SettingOutlined,
  StockOutlined,
  SwapOutlined,
  ThunderboltOutlined,
  TransactionOutlined,
  UserOutlined,
} from "@ant-design/icons";

import ReactECharts, { type EChartsOption } from "../../lib/echarts";

// 视觉原型占位数据，非正式金融指标，仅用于布局/风格演示

const upColor = "var(--color-danger-600)";
const downColor = "var(--color-success-600)";

const MOCK = {
  dataDate: "2025-05-23",
  dataUpdatedAt: "09:15",
  alertCount: 3,
  kpis: [
    { label: "组合总市值", value: "128.56亿", sub: "股市占比 1.24%", tone: "neutral" as const, sparkline: [120, 122, 121, 125, 127, 128, 128.5] },
    { label: "持仓收益(累计)", value: "+18.42亿", sub: "累计收益率 16.75%", tone: "up" as const, sparkline: [10, 11, 12, 14, 15, 17, 18.4] },
    { label: "今日收益", value: "+0.86亿", sub: "+0.68%", tone: "up" as const, sparkline: [0.2, 0.4, 0.3, 0.5, 0.7, 0.8, 0.86] },
    { label: "仓位", value: "82.35%", sub: "较昨日 1.23pp", tone: "neutral" as const, progress: 82.35 },
    { label: "年化收益率", value: "+14.26%", sub: "", tone: "up" as const, sparkline: [8, 9, 10, 11, 12, 13, 14.2] },
    { label: "最大回撤", value: "-6.18%", sub: "", tone: "down" as const, sparkline: [-2, -3, -4, -5, -5.5, -6, -6.18] },
    { label: "行业集中度", value: "31.40%", sub: "", tone: "neutral" as const },
    { label: "Beta", value: "0.93", sub: "", tone: "neutral" as const },
  ],
  marketOverview: [
    { name: "上证指数", value: "3348.37", change: "+0.42%", tone: "up" as const },
    { name: "深证成指", value: "10186.53", change: "+0.68%", tone: "up" as const },
    { name: "沪深300", value: "3697.45", change: "+0.55%", tone: "up" as const },
    { name: "创业板指", value: "2052.73", change: "-0.12%", tone: "down" as const },
    { name: "中证1000", value: "6114.82", change: "+1.03%", tone: "up" as const },
    { name: "北向资金", value: "+32.16亿", change: "净流入", tone: "up" as const },
    { name: "成交量", value: "8652.31亿", change: "较昨日 +8.2%", tone: "neutral" as const },
    { name: "涨跌比", value: "1823:1017", change: "涨多跌少", tone: "up" as const },
  ],
  holdings: [
    { code: "600519", name: "贵州茅台", industry: "食品饮料", mv: "12,580", weight: "9.78%", cost: "1680.00", price: "1725.30", today: "+1.24%", cum: "+18.6%", rating: "持有" },
    { code: "601318", name: "中国平安", industry: "银行", mv: "9,420", weight: "7.33%", cost: "48.20", price: "51.85", today: "+0.86%", cum: "+12.4%", rating: "增持" },
    { code: "300750", name: "宁德时代", industry: "新能源", mv: "8,760", weight: "6.81%", cost: "185.50", price: "192.40", today: "-0.52%", cum: "+9.8%", rating: "持有" },
    { code: "600036", name: "招商银行", industry: "银行", mv: "7,890", weight: "6.14%", cost: "32.10", price: "34.25", today: "+0.35%", cum: "+11.2%", rating: "持有" },
    { code: "000858", name: "五粮液", industry: "食品饮料", mv: "6,540", weight: "5.09%", cost: "138.00", price: "142.60", today: "+0.92%", cum: "+7.5%", rating: "观望" },
    { code: "688981", name: "中芯国际", industry: "电子", mv: "5,980", weight: "4.65%", cost: "42.80", price: "44.10", today: "+2.15%", cum: "+15.3%", rating: "增持" },
    { code: "601012", name: "隆基绿能", industry: "新能源", mv: "4,320", weight: "3.36%", cost: "22.50", price: "21.80", today: "-1.08%", cum: "-4.2%", rating: "减持" },
    { code: "300760", name: "迈瑞医疗", industry: "医药", mv: "4,150", weight: "3.23%", cost: "285.00", price: "291.50", today: "+0.48%", cum: "+6.9%", rating: "持有" },
  ],
  assetDistribution: [
    { name: "银行", value: 22.53 },
    { name: "医药", value: 18.76 },
    { name: "食品饮料", value: 14.26 },
    { name: "新能源", value: 17.89 },
    { name: "电子", value: 11.75 },
    { name: "其他", value: 14.81 },
  ],
  aiAdvice: {
    thesis: "市场震荡偏强，成长与价值风格均衡配置，关注北向资金持续流入对核心资产的支撑。",
    opportunities: ["银行板块估值修复窗口", "医药创新药政策边际改善", "AI 算力产业链景气延续"],
    risks: ["美联储降息预期反复", "部分新能源产能过剩", "地缘政治扰动"],
    actions: ["维持核心仓位，适度增配低估值金融", "新能源仓位控制在 18% 以内", "关注季报业绩超预期标的"],
    todos: [
      { text: "宁德时代减持计划到期评估", count: 1 },
      { text: "隆基绿能止损线复核", count: 1 },
      { text: "医药板块仓位上限检查", count: 1 },
    ],
  },
  positionChanges: {
    add: [
      { name: "中芯国际", amount: "+1.2亿", tone: "up" as const },
      { name: "招商银行", amount: "+0.8亿", tone: "up" as const },
      { name: "迈瑞医疗", amount: "+0.5亿", tone: "up" as const },
      { name: "中国平安", amount: "+0.4亿", tone: "up" as const },
      { name: "五粮液", amount: "+0.3亿", tone: "up" as const },
    ],
    reduce: [
      { name: "隆基绿能", amount: "-0.9亿", tone: "down" as const },
      { name: "比亚迪", amount: "-0.6亿", tone: "down" as const },
      { name: "药明康德", amount: "-0.4亿", tone: "down" as const },
      { name: "海天味业", amount: "-0.3亿", tone: "down" as const },
      { name: "立讯精密", amount: "-0.2亿", tone: "down" as const },
    ],
  },
  riskMetrics: [
    { label: "波动率(年化)", value: "16.32%" },
    { label: "夏普比率", value: "1.42" },
    { label: "信息比率", value: "0.95" },
    { label: "最大回撤", value: "-6.18%", tone: "down" as const },
    { label: "VaR(95%)", value: "-2.15%", tone: "down" as const },
  ],
  alerts: [
    { level: "高", text: "隆基绿能跌破成本线 5%", time: "08:45" },
    { level: "中", text: "行业集中度超阈值 30%", time: "09:02" },
    { level: "低", text: "宁德时代限售解禁提醒", time: "09:10" },
  ],
  shortcuts: [
    { icon: PieChartOutlined, title: "持仓分析", desc: "明细与结构" },
    { icon: LineChartOutlined, title: "归因分析", desc: "收益拆解" },
    { icon: SafetyOutlined, title: "风险暴露", desc: "因子与行业" },
    { icon: TransactionOutlined, title: "交易流水", desc: "买卖记录" },
    { icon: FundOutlined, title: "研究报告", desc: "内外部研报" },
    { icon: StockOutlined, title: "自选股池", desc: "关注列表" },
  ],
};

const SIDEBAR_ITEMS = [
  { icon: DashboardOutlined, label: "经营驾驶舱", active: true },
  { icon: StockOutlined, label: "股票首页", active: false },
  { icon: PieChartOutlined, label: "持仓总览", active: false },
  { icon: ExperimentOutlined, label: "策略研究", active: false },
  { icon: TransactionOutlined, label: "交易管理", active: false },
  { icon: LineChartOutlined, label: "行情中心", active: false },
  { icon: SafetyOutlined, label: "风险管理", active: false },
  { icon: DatabaseOutlined, label: "数据中心", active: false },
  { icon: AlertOutlined, label: "预警中心", active: false },
  { icon: SettingOutlined, label: "系统管理", active: false },
];

function toneClass(tone: "up" | "down" | "neutral") {
  if (tone === "up") return "text-danger-600";
  if (tone === "down") return "text-success-600";
  return "text-neutral-600";
}

function buildSparklineOption(values: number[], color: string): EChartsOption {
  return {
    animation: false,
    grid: { left: 0, right: 0, top: 2, bottom: 2 },
    xAxis: { type: "category", show: false, boundaryGap: false, data: values.map((_, i) => String(i)) },
    yAxis: { type: "value", show: false, scale: true },
    series: [{ type: "line", data: values, smooth: true, symbol: "none", lineStyle: { color, width: 1.5 } }],
  };
}

function MiniSparkline({ values, tone }: { values: number[]; tone?: "up" | "down" | "neutral" }) {
  const color = tone === "down" ? downColor : tone === "up" ? upColor : "var(--color-primary-600)";
  const option = useMemo(() => buildSparklineOption(values, color), [values, color]);
  return (
    <div className="h-8 w-16 shrink-0">
      <ReactECharts option={option} className="h-full w-full" opts={{ renderer: "canvas" }} />
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  tone,
  sparkline,
  progress,
}: {
  label: string;
  value: string;
  sub: string;
  tone: "up" | "down" | "neutral";
  sparkline?: number[];
  progress?: number;
}) {
  return (
    <article className="flex flex-col gap-1.5 rounded-md border border-neutral-200 bg-white p-3 shadow-sm">
      <header className="flex items-start justify-between gap-1">
        <span className="text-xs text-neutral-600">{label}</span>
        {sparkline ? <MiniSparkline values={sparkline} tone={tone} /> : null}
      </header>
      <p className={`font-mono text-lg font-semibold tabular-nums leading-tight ${tone === "up" ? "text-danger-600" : tone === "down" ? "text-success-600" : "text-neutral-900"}`}>
        {value}
      </p>
      {progress !== undefined ? (
        <div className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-neutral-100">
          <div className="h-full rounded-full bg-primary-600" style={{ width: `${progress}%` }} />
        </div>
      ) : null}
      {sub ? <p className={`text-xs ${toneClass(tone === "neutral" && sub.includes("pp") ? "neutral" : tone)}`}>{sub}</p> : null}
    </article>
  );
}

function SectionCard({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-md border border-neutral-200 bg-white p-4 shadow-sm ${className}`}>
      <h3 className="mb-3 text-sm font-medium text-neutral-900">{title}</h3>
      {children}
    </section>
  );
}

export default function EquityCockpitPrototypePage() {
  const doughnutOption: EChartsOption = useMemo(
    () => ({
      tooltip: { trigger: "item", formatter: "{b}: {c}%" },
      series: [
        {
          type: "pie",
          radius: ["58%", "78%"],
          center: ["38%", "50%"],
          avoidLabelOverlap: false,
          label: { show: false },
          data: MOCK.assetDistribution.map((d) => ({ name: d.name, value: d.value })),
          color: ["#2563eb", "#7c3aed", "#db2777", "#059669", "#d97706", "#64748b"],
        },
      ],
      graphic: [
        {
          type: "text",
          left: "28%",
          top: "42%",
          style: { text: "128.56亿", fill: "#111827", fontSize: 14, fontWeight: 600, textAlign: "center" },
        },
        {
          type: "text",
          left: "28%",
          top: "52%",
          style: { text: "总市值", fill: "#6b7280", fontSize: 11, textAlign: "center" },
        },
      ],
    }),
    [],
  );

  const trendOption: EChartsOption = useMemo(
    () => ({
      tooltip: { trigger: "axis" },
      legend: { data: ["本组合", "沪深300", "超额收益"], bottom: 0, textStyle: { fontSize: 11 } },
      grid: { left: 48, right: 16, top: 24, bottom: 40 },
      xAxis: { type: "category", data: ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"], axisLabel: { fontSize: 10 } },
      yAxis: { type: "value", axisLabel: { fontSize: 10, formatter: "{value}%" } },
      series: [
        { name: "本组合", type: "line", smooth: true, data: [0, 2.1, 3.5, 5.2, 7.8, 9.1, 10.5, 12.3, 13.8, 14.5, 15.2, 16.75], lineStyle: { color: upColor, width: 2 }, symbol: "none" },
        { name: "沪深300", type: "line", smooth: true, data: [0, 1.2, 2.0, 2.8, 4.1, 4.5, 5.2, 6.0, 6.8, 7.2, 7.5, 8.1], lineStyle: { color: "#64748b", width: 1.5 }, symbol: "none" },
        { name: "超额收益", type: "line", smooth: true, data: [0, 0.9, 1.5, 2.4, 3.7, 4.6, 5.3, 6.3, 7.0, 7.3, 7.7, 8.65], lineStyle: { color: "var(--color-primary-600)", width: 1.5, type: "dashed" }, symbol: "none" },
      ],
    }),
    [],
  );

  const industryBarOption: EChartsOption = useMemo(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 72, right: 24, top: 8, bottom: 8 },
      xAxis: { type: "value", axisLabel: { fontSize: 10, formatter: "{value}%" } },
      yAxis: { type: "category", data: ["电子", "新能源", "医药", "银行", "食品饮料"], axisLabel: { fontSize: 10 } },
      series: [
        {
          type: "bar",
          data: [
            { value: 3.2, itemStyle: { color: upColor } },
            { value: 2.8, itemStyle: { color: upColor } },
            { value: 1.5, itemStyle: { color: upColor } },
            { value: 0.9, itemStyle: { color: upColor } },
            { value: -0.4, itemStyle: { color: downColor } },
          ],
          barWidth: 12,
        },
      ],
    }),
    [],
  );

  return (
    <div className="flex min-h-screen bg-neutral-50">
      {/* 深色侧栏 */}
      <aside className="flex w-[200px] shrink-0 flex-col bg-[#0f2544] text-neutral-200">
        <div className="flex items-center gap-2 border-b border-white/10 px-4 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-primary-600 text-sm font-bold text-white">M</div>
          <div>
            <p className="text-sm font-semibold text-white">MOSS</p>
            <p className="text-[10px] text-neutral-400">股票管理系统</p>
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto px-2 py-3">
          <p className="mb-2 px-2 text-[10px] uppercase tracking-wider text-neutral-500">工作台</p>
          <ul className="space-y-0.5">
            {SIDEBAR_ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.label}>
                  <button
                    type="button"
                    className={`flex w-full items-center gap-2 rounded px-2 py-2 text-left text-xs transition-colors ${
                      item.active
                        ? "border-l-2 border-primary-400 bg-primary-600/20 text-white"
                        : "border-l-2 border-transparent text-neutral-300 hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    <Icon className="text-sm" />
                    {item.label}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
        <button type="button" className="flex items-center gap-1 border-t border-white/10 px-4 py-3 text-xs text-neutral-400 hover:text-white">
          <DoubleLeftOutlined />
          收起
        </button>
      </aside>

      {/* 主区 */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* 顶栏 */}
        <header className="flex items-center justify-between border-b border-neutral-200 bg-white px-4 py-3">
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold text-neutral-900">经营驾驶舱</h1>
            <span className="rounded bg-primary-600/10 px-2 py-0.5 text-xs text-primary-700">首页东扩</span>
            <span className="text-[10px] text-neutral-400">视觉原型 · 数据为占位演示</span>
          </div>
          <div className="flex items-center gap-3 text-xs text-neutral-600">
            <span className="flex items-center gap-1">
              <SwapOutlined />
              数据更新 {MOCK.dataUpdatedAt}
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-success-600" />
              行情已同步
            </span>
            <span className="flex items-center gap-1">
              <AlertOutlined className="text-warning-600" />
              预警待处理
              <span className="rounded-full bg-warning-600 px-1.5 py-0.5 text-[10px] font-medium text-white">{MOCK.alertCount}</span>
            </span>
            <button type="button" className="flex items-center gap-1 hover:text-primary-700">
              <ExportOutlined />
              导出
            </button>
            <button type="button" className="hover:text-primary-700">自定义视图</button>
            <button type="button" className="hover:text-primary-700" aria-label="全屏">
              <FullscreenOutlined />
            </button>
            <button type="button" className="hover:text-primary-700" aria-label="通知">
              <BellOutlined />
            </button>
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary-600 text-white">
              <UserOutlined className="text-xs" />
            </span>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-4">
          <div
            data-testid="equity-prototype-ribbon"
            className="mb-3 rounded-md border border-warning-300 bg-warning-50 px-4 py-3 text-sm text-warning-900 shadow-sm"
          >
            <p className="font-semibold uppercase tracking-wide">
              Prototype / Mock only
            </p>
            <p className="mt-1 text-xs text-warning-800">
              This page uses mock data and experimental UI. Not for business decisions or external presentation.
            </p>
          </div>
          {/* 筛选行 */}
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 rounded-md border border-neutral-200 bg-white px-3 py-1.5 text-xs text-neutral-700">
              <CalendarOutlined className="text-neutral-400" />
              数据日期 {MOCK.dataDate}
            </label>
            <div className="flex flex-1 items-center gap-2 rounded-md border border-neutral-200 bg-white px-3 py-1.5 text-xs text-neutral-400 min-w-[200px] max-w-md">
              <SearchOutlined />
              搜索 股票代码/名称/行业/策略
            </div>
          </div>

          {/* KPI 横带 */}
          <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
            {MOCK.kpis.map((kpi) => (
              <KpiCard key={kpi.label} {...kpi} />
            ))}
          </div>

          {/* 中段三栏 */}
          <div className="mb-3 grid grid-cols-1 gap-3 xl:grid-cols-12">
            {/* 左中 */}
            <div className="space-y-3 xl:col-span-8">
              <SectionCard title="市场总览 / 指数与资金概览">
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
                  {MOCK.marketOverview.map((item) => (
                    <div key={item.name} className="rounded border border-neutral-100 bg-neutral-50 p-2">
                      <p className="text-[10px] text-neutral-500">{item.name}</p>
                      <p className="font-mono text-sm font-semibold tabular-nums text-neutral-900">{item.value}</p>
                      <p className={`text-[10px] ${toneClass(item.tone)}`}>{item.change}</p>
                    </div>
                  ))}
                </div>
              </SectionCard>

              <SectionCard title="持仓明细">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-xs">
                    <thead>
                      <tr className="border-b border-neutral-200 text-neutral-500">
                        <th className="pb-2 pr-2 font-medium">代码</th>
                        <th className="pb-2 pr-2 font-medium">名称</th>
                        <th className="pb-2 pr-2 font-medium">行业</th>
                        <th className="pb-2 pr-2 font-medium text-right">持仓市值(万)</th>
                        <th className="pb-2 pr-2 font-medium text-right">权重</th>
                        <th className="pb-2 pr-2 font-medium text-right">成本价</th>
                        <th className="pb-2 pr-2 font-medium text-right">现价</th>
                        <th className="pb-2 pr-2 font-medium text-right">今日涨跌</th>
                        <th className="pb-2 pr-2 font-medium text-right">累计收益</th>
                        <th className="pb-2 font-medium">评级</th>
                      </tr>
                    </thead>
                    <tbody>
                      {MOCK.holdings.map((row) => {
                        const todayUp = row.today.startsWith("+");
                        const cumUp = row.cum.startsWith("+");
                        return (
                          <tr key={row.code} className="border-b border-neutral-100 hover:bg-neutral-50">
                            <td className="py-2 pr-2 font-mono text-neutral-700">{row.code}</td>
                            <td className="py-2 pr-2 font-medium text-neutral-900">{row.name}</td>
                            <td className="py-2 pr-2 text-neutral-600">{row.industry}</td>
                            <td className="py-2 pr-2 text-right font-mono tabular-nums">{row.mv}</td>
                            <td className="py-2 pr-2 text-right font-mono tabular-nums">{row.weight}</td>
                            <td className="py-2 pr-2 text-right font-mono tabular-nums">{row.cost}</td>
                            <td className="py-2 pr-2 text-right font-mono tabular-nums">{row.price}</td>
                            <td className={`py-2 pr-2 text-right font-mono tabular-nums ${todayUp ? "text-danger-600" : "text-success-600"}`}>{row.today}</td>
                            <td className={`py-2 pr-2 text-right font-mono tabular-nums ${cumUp ? "text-danger-600" : "text-success-600"}`}>{row.cum}</td>
                            <td className="py-2">
                              <span className={`rounded px-1.5 py-0.5 text-[10px] ${row.rating === "增持" ? "bg-danger-600/10 text-danger-600" : row.rating === "减持" ? "bg-success-600/10 text-success-600" : "bg-neutral-100 text-neutral-600"}`}>
                                {row.rating}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <button type="button" className="mt-2 text-xs text-primary-700 hover:underline">
                  查看全部持仓(共 58 只) →
                </button>
              </SectionCard>
            </div>

            {/* 右上 + 右侧 AI 列 */}
            <div className="space-y-3 xl:col-span-4">
              <SectionCard title="资产分布">
                <div className="flex gap-3">
                  <div className="h-40 w-40 shrink-0">
                    <ReactECharts option={doughnutOption} className="h-full w-full" />
                  </div>
                  <ul className="flex flex-1 flex-col justify-center gap-1 text-xs">
                    {MOCK.assetDistribution.map((d) => (
                      <li key={d.name} className="flex justify-between text-neutral-600">
                        <span>{d.name}</span>
                        <span className="font-mono tabular-nums text-neutral-900">{d.value}%</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </SectionCard>

              <section className="rounded-md bg-gradient-to-b from-[#0f2544] to-[#0b1f3a] p-4 text-neutral-100 shadow-sm">
                <div className="mb-3 flex items-center gap-2">
                  <ThunderboltOutlined className="text-primary-400" />
                  <h3 className="text-sm font-medium text-white">AI 投资建议</h3>
                </div>
                <div className="space-y-3 text-xs leading-relaxed">
                  <div>
                    <p className="mb-1 text-neutral-400">今日论点</p>
                    <p className="text-neutral-200">{MOCK.aiAdvice.thesis}</p>
                  </div>
                  <div>
                    <p className="mb-1 text-neutral-400">主要机会</p>
                    <ul className="list-inside list-disc space-y-0.5 text-neutral-200">
                      {MOCK.aiAdvice.opportunities.map((o) => (
                        <li key={o}>{o}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="mb-1 text-neutral-400">关键风险</p>
                    <ul className="list-inside list-disc space-y-0.5 text-warning-400">
                      {MOCK.aiAdvice.risks.map((r) => (
                        <li key={r}>{r}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="mb-1 text-neutral-400">建议动作</p>
                    <ul className="list-inside list-disc space-y-0.5 text-neutral-200">
                      {MOCK.aiAdvice.actions.map((a) => (
                        <li key={a}>{a}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="mb-1 text-neutral-400">待处理事项</p>
                    <ul className="space-y-1">
                      {MOCK.aiAdvice.todos.map((t) => (
                        <li key={t.text} className="flex items-center justify-between rounded bg-white/5 px-2 py-1">
                          <span>{t.text}</span>
                          <span className="rounded-full bg-warning-600 px-1.5 text-[10px] text-white">{t.count}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                <button type="button" className="mt-4 w-full rounded bg-primary-600 py-2 text-xs font-medium text-white hover:bg-primary-700">
                  生成完整投资报告 →
                </button>
              </section>
            </div>
          </div>

          {/* 底部多卡 */}
          <div className="mb-3 grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
            <SectionCard title="持仓收益趋势">
              <div className="h-52">
                <ReactECharts option={trendOption} className="h-full w-full" />
              </div>
            </SectionCard>

            <SectionCard title="持仓变动">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="mb-2 text-xs font-medium text-danger-600">加仓 TOP5</p>
                  <ul className="space-y-1.5 text-xs">
                    {MOCK.positionChanges.add.map((item) => (
                      <li key={item.name} className="flex justify-between">
                        <span className="text-neutral-700">{item.name}</span>
                        <span className="font-mono tabular-nums text-danger-600">{item.amount}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="mb-2 text-xs font-medium text-success-600">减仓 TOP5</p>
                  <ul className="space-y-1.5 text-xs">
                    {MOCK.positionChanges.reduce.map((item) => (
                      <li key={item.name} className="flex justify-between">
                        <span className="text-neutral-700">{item.name}</span>
                        <span className="font-mono tabular-nums text-success-600">{item.amount}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </SectionCard>

            <SectionCard title="行业收益贡献">
              <div className="h-44">
                <ReactECharts option={industryBarOption} className="h-full w-full" />
              </div>
            </SectionCard>

            <SectionCard title="风险指标">
              <ul className="space-y-2 text-xs">
                {MOCK.riskMetrics.map((m) => (
                  <li key={m.label} className="flex justify-between border-b border-neutral-100 pb-1.5">
                    <span className="text-neutral-600">{m.label}</span>
                    <span className={`font-mono tabular-nums ${m.tone ? toneClass(m.tone) : "text-neutral-900"}`}>{m.value}</span>
                  </li>
                ))}
              </ul>
            </SectionCard>

            <SectionCard title="预警清单">
              <div className="mb-2 flex items-center gap-2">
                <span className="text-xs text-neutral-600">待处理</span>
                <span className="rounded-full bg-warning-600 px-2 py-0.5 text-[10px] font-medium text-white">{MOCK.alertCount}</span>
              </div>
              <ul className="space-y-2 text-xs">
                {MOCK.alerts.map((a) => (
                  <li key={a.text} className="flex items-start gap-2 rounded border border-neutral-100 bg-neutral-50 p-2">
                    <span className={`shrink-0 rounded px-1 py-0.5 text-[10px] ${a.level === "高" ? "bg-danger-600/10 text-danger-600" : a.level === "中" ? "bg-warning-600/10 text-warning-600" : "bg-neutral-200 text-neutral-600"}`}>
                      {a.level}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-neutral-800">{a.text}</p>
                      <p className="text-[10px] text-neutral-400">{a.time}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </SectionCard>
          </div>

          {/* 快捷入口 */}
          <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
            {MOCK.shortcuts.map((s) => {
              const Icon = s.icon;
              return (
                <button
                  key={s.title}
                  type="button"
                  className="flex flex-col items-center gap-1 rounded-md border border-neutral-200 bg-white p-3 text-center shadow-sm transition-shadow hover:shadow-md"
                >
                  <Icon className="text-lg text-primary-600" />
                  <span className="text-xs font-medium text-neutral-900">{s.title}</span>
                  <span className="text-[10px] text-neutral-500">{s.desc}</span>
                </button>
              );
            })}
          </div>
        </main>
      </div>
    </div>
  );
}
