import {
  DatabaseOutlined,
  LineChartOutlined,
  SafetyCertificateOutlined,
  StockOutlined,
} from "@ant-design/icons";

import "./StockAnalysisBoundaryWorkbenches.css";

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
      className="stock-analysis-boundary-workbench stock-analysis-boundary-workbench--loading"
      data-testid="stock-analysis-loading-workbench"
      aria-label={"\u80a1\u7968\u5206\u6790\u52a0\u8f7d\u6001"}
    >
      <div
        className="stock-analysis-boundary-workbench__loading-primary"
        aria-hidden="true"
      >
        <span className="stock-analysis-boundary-workbench__skeleton-accent" />
        <span className="stock-analysis-boundary-workbench__skeleton-line stock-analysis-boundary-workbench__skeleton-line--title" />
        <div className="stock-analysis-boundary-workbench__skeleton-chip-row">
          <span className="stock-analysis-boundary-workbench__skeleton-chip" />
          <span className="stock-analysis-boundary-workbench__skeleton-chip stock-analysis-boundary-workbench__skeleton-chip--medium" />
          <span className="stock-analysis-boundary-workbench__skeleton-chip stock-analysis-boundary-workbench__skeleton-chip--wide" />
        </div>
        <div className="stock-analysis-boundary-workbench__skeleton-metrics">
          <span className="stock-analysis-boundary-workbench__skeleton-metric" />
          <span className="stock-analysis-boundary-workbench__skeleton-metric" />
          <span className="stock-analysis-boundary-workbench__skeleton-metric" />
          <span className="stock-analysis-boundary-workbench__skeleton-metric" />
        </div>
      </div>
      <aside
        className="stock-analysis-boundary-workbench__loading-rail"
        aria-hidden="true"
      >
        <span className="stock-analysis-boundary-workbench__skeleton-accent" />
        <span className="stock-analysis-boundary-workbench__skeleton-line stock-analysis-boundary-workbench__skeleton-line--rail" />
        <div className="stock-analysis-boundary-workbench__loading-rail-grid">
          {LOADING_RAIL_LABELS.map((label) => (
            <span
              key={label}
              className="stock-analysis-boundary-workbench__skeleton-rail-item"
            />
          ))}
        </div>
      </aside>
      <div
        className="stock-analysis-boundary-workbench__loading-kpis"
        aria-hidden="true"
      >
        {LOADING_KPI_LABELS.map((label) => (
          <span
            key={label}
            className="stock-analysis-boundary-workbench__skeleton-kpi"
          />
        ))}
      </div>
      <div
        className="stock-analysis-boundary-workbench__loading-panel"
        aria-hidden="true"
      >
        <span className="stock-analysis-boundary-workbench__skeleton-accent" />
        <span className="stock-analysis-boundary-workbench__skeleton-chart" />
      </div>
      <p
        className="stock-analysis-boundary-workbench__visually-hidden"
        role="status"
      >
        {"\u80a1\u7968\u5206\u6790\u52a0\u8f7d\u4e2d"}
      </p>
    </section>
  );
}

export function StockAnalysisErrorWorkbench({
  message,
  onRetry,
  isRetrying = false,
}: {
  message: string;
  onRetry?: () => void;
  isRetrying?: boolean;
}) {
  return (
    <section
      className="stock-analysis-boundary-workbench stock-analysis-boundary-workbench--error"
      data-testid="stock-analysis-error-workbench"
      aria-label={"\u80a1\u7968\u5206\u6790\u9519\u8bef\u6001"}
      role="alert"
    >
      <div className="stock-analysis-boundary-workbench__error-header">
        <span
          className="stock-analysis-boundary-workbench__error-icon"
          aria-hidden="true"
        >
          <SafetyCertificateOutlined />
        </span>
        <div className="stock-analysis-boundary-workbench__error-copy">
          <p className="stock-analysis-boundary-workbench__eyebrow">
            {"\u590d\u6838\u963b\u65ad"}
          </p>
          <h2 className="stock-analysis-boundary-workbench__error-title">
            {"\u80a1\u7968\u5206\u6790\u6682\u4e0d\u53ef\u7528"}
          </h2>
          <p className="stock-analysis-boundary-workbench__error-message">
            {message}
          </p>
          {onRetry ? (
            <button
              type="button"
              className="stock-analysis-boundary-workbench__retry-button"
              onClick={onRetry}
              disabled={isRetrying}
            >
              {isRetrying ? "读取中" : "重新读取"}
            </button>
          ) : null}
        </div>
      </div>
      <div
        className="stock-analysis-boundary-workbench__decision-panel"
        data-testid="stock-analysis-error-decision-panel"
      >
        <div className="stock-analysis-boundary-workbench__decision-card stock-analysis-boundary-workbench__decision-card--primary">
          <p className="stock-analysis-boundary-workbench__eyebrow">
            第一屏结论
          </p>
          <h3 className="stock-analysis-boundary-workbench__decision-title">
            后端供数没通，今天先不做个股复核
          </h3>
          <p className="stock-analysis-boundary-workbench__decision-copy">
            设计和页面入口已经在这里；现在卡住的是策略复核主接口。先确认供数、规则版本和 trace，再回到候选队列复核。
          </p>
        </div>
        <div className="stock-analysis-boundary-workbench__decision-card stock-analysis-boundary-workbench__decision-card--boundary">
          <p className="stock-analysis-boundary-workbench__eyebrow stock-analysis-boundary-workbench__eyebrow--boundary">
            当前能判断什么
          </p>
          <div className="stock-analysis-boundary-workbench__decision-list">
            {ERROR_DECISION_ITEMS.map((item) => (
              <span
                key={item}
                className="stock-analysis-boundary-workbench__decision-item"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
      <div
        className="stock-analysis-boundary-workbench__status-summary"
        aria-label={"\u9519\u8bef\u6001\u72b6\u6001\u6458\u8981"}
      >
        <span className="stock-analysis-boundary-workbench__status-item stock-analysis-boundary-workbench__status-item--warning">
          <DatabaseOutlined
            className="stock-analysis-boundary-workbench__status-icon"
            aria-hidden="true"
          />
          <small className="stock-analysis-boundary-workbench__status-label">
            {"\u4f9b\u6570"}
          </small>
          <strong className="stock-analysis-boundary-workbench__status-value">
            {"\u5f85\u6062\u590d"}
          </strong>
        </span>
        <span className="stock-analysis-boundary-workbench__status-item stock-analysis-boundary-workbench__status-item--error">
          <SafetyCertificateOutlined
            className="stock-analysis-boundary-workbench__status-icon"
            aria-hidden="true"
          />
          <small className="stock-analysis-boundary-workbench__status-label">
            {"\u7ed3\u8bba"}
          </small>
          <strong className="stock-analysis-boundary-workbench__status-value">
            {"\u6682\u505c"}
          </strong>
        </span>
        <span className="stock-analysis-boundary-workbench__status-item stock-analysis-boundary-workbench__status-item--error">
          <StockOutlined
            className="stock-analysis-boundary-workbench__status-icon"
            aria-hidden="true"
          />
          <small className="stock-analysis-boundary-workbench__status-label">
            {"\u590d\u6838"}
          </small>
          <strong className="stock-analysis-boundary-workbench__status-value">
            {"\u4e0d\u53ef\u7528"}
          </strong>
        </span>
      </div>
      <div
        className="stock-analysis-boundary-workbench__supplement"
        data-testid="stock-analysis-error-supplement"
        aria-label="错误态补充信息"
      >
        {ERROR_SUPPLEMENT_ITEMS.map((item) => (
          <div
            key={item.key}
            className="stock-analysis-boundary-workbench__supplement-item"
          >
            <span className="stock-analysis-boundary-workbench__supplement-icon">
              {item.key === "api" ? (
                <DatabaseOutlined aria-hidden="true" />
              ) : item.key === "boundary" ? (
                <SafetyCertificateOutlined aria-hidden="true" />
              ) : (
                <LineChartOutlined aria-hidden="true" />
              )}
            </span>
            <span className="stock-analysis-boundary-workbench__supplement-label">
              {item.label}
            </span>
            <strong className="stock-analysis-boundary-workbench__supplement-value">
              {item.value}
            </strong>
            <small className="stock-analysis-boundary-workbench__supplement-detail">
              {item.detail}
            </small>
          </div>
        ))}
      </div>
    </section>
  );
}
