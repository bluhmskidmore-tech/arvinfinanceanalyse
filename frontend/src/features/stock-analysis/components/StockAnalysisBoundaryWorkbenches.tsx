import {
  DatabaseOutlined,
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

export function StockAnalysisLoadingWorkbench() {
  return (
    <section
      className="stock-analysis-page__loading-workbench"
      data-testid="stock-analysis-loading-workbench"
      aria-label={"\u80a1\u7968\u5206\u6790\u52a0\u8f7d\u6001"}
    >
      <div className="stock-analysis-page__loading-hero" aria-hidden="true">
        <span className="stock-analysis-page__loading-line stock-analysis-page__loading-line--short" />
        <span className="stock-analysis-page__loading-line stock-analysis-page__loading-line--title" />
        <div className="stock-analysis-page__loading-chip-row">
          <span />
          <span />
          <span />
        </div>
        <div className="stock-analysis-page__loading-meta-grid">
          <span />
          <span />
          <span />
          <span />
        </div>
      </div>
      <aside className="stock-analysis-page__loading-rail" aria-hidden="true">
        <span className="stock-analysis-page__loading-line stock-analysis-page__loading-line--short" />
        <span className="stock-analysis-page__loading-verdict" />
        <div className="stock-analysis-page__loading-rail-grid">
          {LOADING_RAIL_LABELS.map((label) => (
            <span key={label} />
          ))}
        </div>
      </aside>
      <div className="stock-analysis-page__loading-kpi-grid" aria-hidden="true">
        {LOADING_KPI_LABELS.map((label) => (
          <span key={label} />
        ))}
      </div>
      <div className="stock-analysis-page__loading-panel" aria-hidden="true">
        <span className="stock-analysis-page__loading-line stock-analysis-page__loading-line--short" />
        <span className="stock-analysis-page__loading-chart" />
      </div>
      <p className="stock-analysis-page__visually-hidden" role="status">
        {"\u80a1\u7968\u5206\u6790\u52a0\u8f7d\u4e2d"}
      </p>
    </section>
  );
}

export function StockAnalysisErrorWorkbench({ message }: { message: string }) {
  return (
    <section
      className="stock-analysis-page__error-workbench"
      data-testid="stock-analysis-error-workbench"
      aria-label={"\u80a1\u7968\u5206\u6790\u9519\u8bef\u6001"}
      role="alert"
    >
      <div className="stock-analysis-page__error-hero">
        <span className="stock-analysis-page__error-icon" aria-hidden="true">
          <SafetyCertificateOutlined />
        </span>
        <div>
          <p className="stock-analysis-page__dh-purpose-eyebrow">{"\u590d\u6838\u963b\u65ad"}</p>
          <h2>{"\u80a1\u7968\u5206\u6790\u6682\u4e0d\u53ef\u7528"}</h2>
          <p>{message}</p>
        </div>
      </div>
      <div
        className="stock-analysis-page__error-grid"
        aria-label={"\u9519\u8bef\u6001\u72b6\u6001\u6458\u8981"}
      >
        <span>
          <DatabaseOutlined aria-hidden="true" />
          <small>{"\u4f9b\u6570"}</small>
          <strong>{"\u5f85\u6062\u590d"}</strong>
        </span>
        <span>
          <SafetyCertificateOutlined aria-hidden="true" />
          <small>{"\u7ed3\u8bba"}</small>
          <strong>{"\u6682\u505c"}</strong>
        </span>
        <span>
          <StockOutlined aria-hidden="true" />
          <small>{"\u590d\u6838"}</small>
          <strong>{"\u4e0d\u53ef\u7528"}</strong>
        </span>
      </div>
    </section>
  );
}
