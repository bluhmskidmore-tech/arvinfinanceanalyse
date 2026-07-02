import {
  DatabaseOutlined,
  LineChartOutlined,
  SafetyCertificateOutlined,
  StockOutlined,
} from "@ant-design/icons";

const LOADING_KPI_LABELS = [
  "\u5e02\u573a\u72b6\u6001",
  "\u590d\u6838\u961f\u5217",
  "\u677f\u5757\u5f3a\u5f31",
  "\u6570\u636e\u8fb9\u754c",
  "\u98ce\u9669\u89c2\u5bdf",
  "\u95ed\u73af\u72b6\u6001",
];

const LOADING_RAIL_LABELS = [
  "\u95ed\u73af",
  "\u98ce\u9669",
  "\u8fb9\u754c",
  "\u590d\u6838",
];

const ERROR_SUPPLEMENT_ITEMS = [
  {
    key: "api",
    label: "接口",
    value: "策略复核主接口",
    detail: "先确认后端供数与代理链路",
  },
  {
    key: "boundary",
    label: "页面边界",
    value: "GAP-STOCK-ANALYSIS-PAGE",
    detail: "观察性复核，不生成交易指令",
  },
  {
    key: "next",
    label: "下一步",
    value: "恢复供数后复核",
    detail: "检查 result_meta、缺口、规则版本与 trace",
  },
];

const ERROR_DECISION_ITEMS = [
  "策略复核主接口没有返回可用数据，页面先暂停给出个股复核结论。",
  "当前不会生成买入、卖出、调仓这类交易动作。",
  "恢复供数后，第一屏会自动回到候选队列、证据闭环和链路核验。",
];

export function StockAnalysisLoadingWorkbench() {
  return (
    <section
      className="grid grid-cols-1 md:grid-cols-12 gap-6 p-6 animate-pulse bg-zinc-50 dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800"
      data-testid="stock-analysis-loading-workbench"
      aria-label={"\u80a1\u7968\u5206\u6790\u52a0\u8f7d\u6001"}
    >
      <div className="col-span-1 md:col-span-8 flex flex-col gap-6" aria-hidden="true">
        <span className="w-12 h-1 bg-zinc-200 dark:bg-zinc-800 rounded-full" />
        <span className="w-3/4 h-8 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
        <div className="flex gap-2">
          <span className="w-16 h-6 bg-zinc-200 dark:bg-zinc-800 rounded-full" />
          <span className="w-20 h-6 bg-zinc-200 dark:bg-zinc-800 rounded-full" />
          <span className="w-24 h-6 bg-zinc-200 dark:bg-zinc-800 rounded-full" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <span className="h-16 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
          <span className="h-16 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
          <span className="h-16 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
          <span className="h-16 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
        </div>
      </div>
      <aside className="col-span-1 md:col-span-4 flex flex-col gap-6 border-t md:border-t-0 md:border-l border-zinc-200 dark:border-zinc-800 pt-6 md:pt-0 md:pl-6" aria-hidden="true">
        <span className="w-12 h-1 bg-zinc-200 dark:bg-zinc-800 rounded-full" />
        <span className="w-1/2 h-6 bg-zinc-200 dark:bg-zinc-800 rounded-md" />
        <div className="grid grid-cols-2 gap-4">
          {LOADING_RAIL_LABELS.map((label) => (
            <span key={label} className="h-10 bg-zinc-200 dark:bg-zinc-800 rounded-md" />
          ))}
        </div>
      </aside>
      <div className="col-span-1 md:col-span-12 grid grid-cols-3 md:grid-cols-6 gap-4 border-t border-zinc-200 dark:border-zinc-800 pt-6" aria-hidden="true">
        {LOADING_KPI_LABELS.map((label) => (
          <span key={label} className="h-12 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
        ))}
      </div>
      <div className="col-span-1 md:col-span-12 flex flex-col gap-4" aria-hidden="true">
        <span className="w-12 h-1 bg-zinc-200 dark:bg-zinc-800 rounded-full" />
        <span className="w-full h-48 bg-zinc-200 dark:bg-zinc-800 rounded-xl" />
      </div>
      <p className="sr-only" role="status">
        {"\u80a1\u7968\u5206\u6790\u52a0\u8f7d\u4e2d"}
      </p>
    </section>
  );
}

export function StockAnalysisErrorWorkbench({ message }: { message: string }) {
  return (
    <section
      className="flex flex-col gap-8 p-8 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/50 rounded-2xl"
      data-testid="stock-analysis-error-workbench"
      aria-label={"\u80a1\u7968\u5206\u6790\u9519\u8bef\u6001"}
      role="alert"
    >
      <div className="flex items-start gap-4">
        <span className="flex-shrink-0 flex items-center justify-center w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400 text-xl" aria-hidden="true">
          <SafetyCertificateOutlined />
        </span>
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold tracking-wider text-red-600/80 dark:text-red-400/80 uppercase">
            {"\u590d\u6838\u963b\u65ad"}
          </p>
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
            {"\u80a1\u7968\u5206\u6790\u6682\u4e0d\u53ef\u7528"}
          </h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">{message}</p>
        </div>
      </div>
      <div
        className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.35fr)_minmax(260px,0.65fr)] gap-4"
        data-testid="stock-analysis-error-decision-panel"
      >
        <div className="flex flex-col gap-3 rounded-xl border border-red-200 dark:border-red-900/50 bg-white dark:bg-zinc-950/70 p-5">
          <p className="text-xs font-semibold tracking-wider text-red-600/80 dark:text-red-400/80 uppercase">
            第一屏结论
          </p>
          <h3 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50">
            后端供数没通，今天先不做个股复核
          </h3>
          <p className="text-sm leading-6 text-zinc-600 dark:text-zinc-300">
            设计和页面入口已经在这里；现在卡住的是策略复核主接口。先确认供数、规则版本和 trace，再回到候选队列复核。
          </p>
        </div>
        <div className="flex flex-col gap-2 rounded-xl border border-red-200 dark:border-red-900/50 bg-red-100/70 dark:bg-red-950/30 p-5">
          <p className="text-xs font-semibold tracking-wider text-red-700 dark:text-red-300 uppercase">
            当前能判断什么
          </p>
          {ERROR_DECISION_ITEMS.map((item) => (
            <span key={item} className="text-sm leading-6 text-zinc-700 dark:text-zinc-200">
              {item}
            </span>
          ))}
        </div>
      </div>
      <div
        className="grid grid-cols-1 md:grid-cols-3 gap-4"
        aria-label={"\u9519\u8bef\u6001\u72b6\u6001\u6458\u8981"}
      >
        <span className="flex flex-col gap-1 p-4 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm">
          <DatabaseOutlined className="text-zinc-400 dark:text-zinc-500 mb-1 text-lg" aria-hidden="true" />
          <small className="text-xs text-zinc-500 dark:text-zinc-400">{"\u4f9b\u6570"}</small>
          <strong className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{"\u5f85\u6062\u590d"}</strong>
        </span>
        <span className="flex flex-col gap-1 p-4 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm">
          <SafetyCertificateOutlined className="text-zinc-400 dark:text-zinc-500 mb-1 text-lg" aria-hidden="true" />
          <small className="text-xs text-zinc-500 dark:text-zinc-400">{"\u7ed3\u8bba"}</small>
          <strong className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{"\u6682\u505c"}</strong>
        </span>
        <span className="flex flex-col gap-1 p-4 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm">
          <StockOutlined className="text-zinc-400 dark:text-zinc-500 mb-1 text-lg" aria-hidden="true" />
          <small className="text-xs text-zinc-500 dark:text-zinc-400">{"\u590d\u6838"}</small>
          <strong className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{"\u4e0d\u53ef\u7528"}</strong>
        </span>
      </div>
      <div
        className="flex flex-col gap-3 mt-2 border-t border-red-200 dark:border-red-900/50 pt-6"
        data-testid="stock-analysis-error-supplement"
        aria-label="错误态补充信息"
      >
        {ERROR_SUPPLEMENT_ITEMS.map((item) => (
          <div key={item.key} className="flex items-center gap-3 text-sm">
            <span className="flex items-center justify-center w-6 h-6 rounded bg-red-100 dark:bg-red-900/30 text-red-500 dark:text-red-400 text-xs">
              {item.key === "api" ? (
                <DatabaseOutlined aria-hidden="true" />
              ) : item.key === "boundary" ? (
                <SafetyCertificateOutlined aria-hidden="true" />
              ) : (
                <LineChartOutlined aria-hidden="true" />
              )}
            </span>
            <span className="text-zinc-600 dark:text-zinc-400 w-16">{item.label}</span>
            <strong className="text-zinc-900 dark:text-zinc-100 font-medium">{item.value}</strong>
            <small className="text-zinc-500 dark:text-zinc-500 hidden md:inline ml-auto">{item.detail}</small>
          </div>
        ))}
      </div>
    </section>
  );
}
