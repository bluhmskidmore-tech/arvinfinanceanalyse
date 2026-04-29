import type { LivermoreStrategyModel } from "../lib/livermoreStrategyModel";
import "./LivermoreStrategyPanel.css";

type Props = {
  model: LivermoreStrategyModel | null;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
};

function statusClass(status: string) {
  return `livermore-strategy-panel__status livermore-strategy-panel__status--${status}`;
}

export function LivermoreStrategyPanel({
  model,
  isLoading,
  isError,
  onRetry,
}: Props) {
  if (isLoading) {
    return (
      <section className="livermore-strategy-panel" data-testid="market-data-livermore-panel">
        <div className="livermore-strategy-panel__state">正在加载 Livermore 分析结果。</div>
      </section>
    );
  }

  if (isError) {
    return (
      <section className="livermore-strategy-panel" data-testid="market-data-livermore-panel">
        <div className="livermore-strategy-panel__state livermore-strategy-panel__state--error">
          <div>Livermore 分析结果加载失败。</div>
          <button
            className="livermore-strategy-panel__retry"
            onClick={onRetry}
            type="button"
          >
            重试
          </button>
        </div>
      </section>
    );
  }

  if (!model) {
    return (
      <section className="livermore-strategy-panel" data-testid="market-data-livermore-panel">
        <div className="livermore-strategy-panel__state">当前暂无 Livermore 结果。</div>
      </section>
    );
  }

  const noData = model.marketGate.state === "NO_DATA";

  return (
    <section className="livermore-strategy-panel" data-testid="market-data-livermore-panel">
      <div className="livermore-strategy-panel__header">
        <div className="livermore-strategy-panel__title">
          <h2 className="livermore-strategy-panel__name">{model.strategyName}</h2>
          <div className="livermore-strategy-panel__meta">
            {model.asOfDate
              ? `结果日期 ${model.asOfDate}${model.requestedAsOfDate ? ` · 请求 ${model.requestedAsOfDate}` : ""}`
              : "结果日期待定"}
          </div>
        </div>
        <span className="livermore-strategy-panel__badge">分析口径 · 不生成交易指令</span>
      </div>

      {model.statusNotes.length > 0 ? (
        <div
          className="livermore-strategy-panel__notes"
          data-testid="livermore-status-notes"
        >
          {model.statusNotes.map((note) => (
            <div key={note}>{note}</div>
          ))}
        </div>
      ) : null}

      <div className="livermore-strategy-panel__metrics">
        <div className="livermore-strategy-panel__metric" data-testid="livermore-market-state">
          <div className="livermore-strategy-panel__metric-label">市场门控</div>
          <div className="livermore-strategy-panel__metric-value">{model.marketGate.state}</div>
          <div className="livermore-strategy-panel__metric-detail">
            需要至少 {model.marketGate.requiredConditions} 条通过
          </div>
        </div>
        <div className="livermore-strategy-panel__metric" data-testid="livermore-exposure">
          <div className="livermore-strategy-panel__metric-label">仓位系数</div>
          <div className="livermore-strategy-panel__metric-value">
            {model.marketGate.exposureDisplay}
          </div>
          <div className="livermore-strategy-panel__metric-detail">由后端结果直接提供</div>
        </div>
        <div className="livermore-strategy-panel__metric" data-testid="livermore-gate-count">
          <div className="livermore-strategy-panel__metric-label">门控确认</div>
          <div className="livermore-strategy-panel__metric-value">
            {model.marketGate.passedConditions} / {model.marketGate.availableConditions}
          </div>
          <div className="livermore-strategy-panel__metric-detail">
            可计算 {model.marketGate.availableConditions} 条
          </div>
        </div>
        <div className="livermore-strategy-panel__metric">
          <div className="livermore-strategy-panel__metric-label">已支持输出</div>
          <div className="livermore-strategy-panel__metric-value">
            {model.supportedOutputs.length}
          </div>
          <div className="livermore-strategy-panel__metric-detail">
            {model.supportedOutputs.map((item) => item.label).join("、") || "暂无"}
          </div>
        </div>
      </div>

      {noData ? (
        <div className="livermore-strategy-panel__state">暂无可用 Livermore 输入。</div>
      ) : null}

      <div className="livermore-strategy-panel__grid">
        <div className="livermore-strategy-panel__block">
          <h3 className="livermore-strategy-panel__block-title">市场门控条件</h3>
          <ul className="livermore-strategy-panel__list">
            {model.marketGate.conditions.map((condition) => (
              <li className="livermore-strategy-panel__row" key={condition.key}>
                <span className="livermore-strategy-panel__row-main">
                  <span className="livermore-strategy-panel__row-title">{condition.label}</span>
                  <span className="livermore-strategy-panel__row-detail">
                    {condition.evidence}
                  </span>
                </span>
                <span className={statusClass(condition.status)}>{condition.statusLabel}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="livermore-strategy-panel__block" data-testid="livermore-rule-readiness">
          <h3 className="livermore-strategy-panel__block-title">规则就绪度</h3>
          <ul className="livermore-strategy-panel__list">
            {model.ruleBlocks.map((block) => (
              <li className="livermore-strategy-panel__row" key={block.key}>
                <span className="livermore-strategy-panel__row-main">
                  <span className="livermore-strategy-panel__row-title">{block.title}</span>
                  <span className="livermore-strategy-panel__row-detail">{block.summary}</span>
                </span>
                <span className={statusClass(block.status)}>{block.statusLabel}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="livermore-strategy-panel__grid">
        <div className="livermore-strategy-panel__block" data-testid="livermore-data-gaps">
          <h3 className="livermore-strategy-panel__block-title">数据缺口</h3>
          <ul className="livermore-strategy-panel__list">
            {model.dataGaps.map((gap) => (
              <li className="livermore-strategy-panel__row" key={gap.inputFamily}>
                <span className="livermore-strategy-panel__row-main">
                  <span className="livermore-strategy-panel__row-title">{gap.inputFamily}</span>
                  <span className="livermore-strategy-panel__row-detail">{gap.evidence}</span>
                </span>
                <span className={statusClass(gap.status)}>{gap.statusLabel}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="livermore-strategy-panel__block" data-testid="livermore-diagnostics">
          <h3 className="livermore-strategy-panel__block-title">诊断</h3>
          <ul className="livermore-strategy-panel__list">
            {model.diagnostics.map((item) => (
              <li className="livermore-strategy-panel__row" key={`${item.severity}:${item.code}`}>
                <span className="livermore-strategy-panel__row-main">
                  <span className="livermore-strategy-panel__row-title">{item.code}</span>
                  <span className="livermore-strategy-panel__row-detail">{item.message}</span>
                </span>
                <span className={statusClass(item.severity)}>{item.severityLabel}</span>
              </li>
            ))}
          </ul>
        </div>

        <div
          className="livermore-strategy-panel__block"
          data-testid="livermore-unsupported-outputs"
        >
          <h3 className="livermore-strategy-panel__block-title">未开放输出</h3>
          <ul className="livermore-strategy-panel__list">
            {model.unsupportedOutputs.map((item) => (
              <li className="livermore-strategy-panel__row" key={item.key}>
                <span className="livermore-strategy-panel__row-main">
                  <span className="livermore-strategy-panel__row-title">{item.label}</span>
                  <span className="livermore-strategy-panel__row-detail">{item.reason}</span>
                </span>
                <span className={statusClass("missing")}>未开放</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
