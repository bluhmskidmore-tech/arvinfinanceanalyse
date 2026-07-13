import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import {
  buildCandidatePeriodComparisonViewModel,
  type CandidatePeriodComparisonViewModel,
} from "../models/candidatePeriodComparisonModel";
import "./LedgerPnlCandidatePeriodComparison.css";

type Props = {
  reportMonth: string;
};

function readableComparisonError(error: unknown): string {
  return error instanceof Error ? error.message : "跨期变化接口返回未知错误。";
}

type NetInterestBridgeModel = Extract<
  CandidatePeriodComparisonViewModel,
  { status: "ready" }
>["netInterestBridge"];

function NetInterestComponentBridge({ bridge }: { bridge: NetInterestBridgeModel }) {
  if (bridge.status === "not_evaluable") {
    return (
      <section
        className="candidate-period-comparison__interest-bridge candidate-period-comparison__interest-bridge--quiet"
        aria-label="净利息收入算术贡献"
        data-state="not-evaluable"
      >
        <h4>净利息收入算术贡献暂不可用</h4>
        <p>后端未能形成完整四项贡献，未展示伪贡献；外层七项跨期结果不受影响。</p>
      </section>
    );
  }

  if (bridge.status === "failed") {
    return (
      <section
        className="candidate-period-comparison__interest-bridge candidate-period-comparison__interest-bridge--failed"
        aria-label="净利息收入算术贡献"
        data-state="failed"
      >
        <h4>净利息收入算术贡献勾稽失败</h4>
        <p>
          后端勾稽差额：<strong>{bridge.reconciliationDisplay} 亿元</strong>；
          四项结果不作为有效解释展示。
        </p>
      </section>
    );
  }

  return (
    <section
      className="candidate-period-comparison__interest-bridge"
      aria-labelledby="candidate-net-interest-bridge-title"
      data-state="available"
    >
      <header className="candidate-period-comparison__interest-bridge-header">
        <div>
          <h4 id="candidate-net-interest-bridge-title">净利息收入算术贡献</h4>
          <p>后端固定四项公式 · 自然月单月对比</p>
        </div>
        <div className="candidate-period-comparison__interest-bridge-result">
          <strong>净息变动 {bridge.netDeltaDisplay} 亿元</strong>
          <span>{bridge.footLabel}</span>
        </div>
      </header>
      <div className="candidate-period-comparison__interest-bridge-table-wrap">
        <table aria-label="净利息收入四项算术贡献">
          <thead>
            <tr>
              <th scope="col">构成项</th>
              <th scope="col">本月</th>
              <th scope="col">上月</th>
              <th scope="col">构成项变动</th>
              <th scope="col">对净息贡献</th>
            </tr>
          </thead>
          <tbody>
            {bridge.rows.map((row) => (
              <tr key={row.metricId}>
                <th scope="row">
                  <strong>{row.metricName}</strong>
                  <code>{row.metricId}</code>
                </th>
                <td>{row.currentDisplay}</td>
                <td>{row.previousDisplay}</td>
                <td>{row.componentDeltaDisplay}</td>
                <td>{row.contributionDisplay}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="candidate-period-comparison__interest-bridge-note">
        后端按固定公式生成的算术贡献，不代表规模、利率或业务原因归因。
      </p>
    </section>
  );
}

export function LedgerPnlCandidatePeriodComparison({
  reportMonth,
}: Props) {
  const client = useApiClient();
  const normalizedReportMonth = reportMonth.trim();
  const comparisonQuery = useQuery({
    queryKey: [
      "ledger-pnl",
      "candidate-financial-indicators",
      client.mode,
      normalizedReportMonth,
      "period-comparison",
    ] as const,
    queryFn: ({ signal }) => client.getLedgerPnlCandidateFinancialIndicatorPeriodComparison(
      normalizedReportMonth,
      { signal },
    ),
    enabled: Boolean(normalizedReportMonth),
    retry: false,
  });

  if (!normalizedReportMonth) {
    return (
      <section
        className="candidate-period-comparison"
        aria-label="候选财务指标跨期变化"
        data-testid="candidate-period-comparison-no-data"
        data-state="no-data"
      >
        <div className="candidate-period-comparison__state">
          <strong>未选择跨期比较月份</strong>
          <span>选择报告月份后再读取候选跨期变化；缺失月份不会按零处理。</span>
        </div>
      </section>
    );
  }

  if (comparisonQuery.isPending) {
    return (
      <section
        className="candidate-period-comparison"
        aria-label="候选财务指标跨期变化"
        aria-busy="true"
      >
        <div
          className="candidate-period-comparison__state"
          data-testid="candidate-period-comparison-loading"
          data-state="loading"
        >
          <strong>正在读取跨期变化…</strong>
          <span>正在核对连续月份、指标状态与历史来源锁定证据。</span>
        </div>
      </section>
    );
  }

  if (comparisonQuery.isError) {
    return (
      <section className="candidate-period-comparison" aria-label="候选财务指标跨期变化">
        <div
          className="candidate-period-comparison__state candidate-period-comparison__state--error"
          data-testid="candidate-period-comparison-error"
          data-state="error"
          role="alert"
        >
          <strong>跨期变化读取失败</strong>
          <span>{readableComparisonError(comparisonQuery.error)}</span>
          <button type="button" onClick={() => void comparisonQuery.refetch()}>
            重新读取跨期变化
          </button>
        </div>
      </section>
    );
  }

  const model = buildCandidatePeriodComparisonViewModel(
    comparisonQuery.data,
    normalizedReportMonth,
  );
  if (model.status === "invalid_contract") {
    return (
      <section className="candidate-period-comparison" aria-label="候选财务指标跨期变化">
        <div
          className="candidate-period-comparison__state candidate-period-comparison__state--error"
          data-testid="candidate-period-comparison-contract-error"
          data-state="contract-error"
          role="alert"
        >
          <strong>跨期变化契约校验失败</strong>
          <span>{model.message}</span>
          <button type="button" onClick={() => void comparisonQuery.refetch()}>
            重新读取跨期变化
          </button>
        </div>
      </section>
    );
  }

  const { payload } = model;
  return (
    <section
      className="candidate-period-comparison"
      aria-labelledby="candidate-period-comparison-title"
      data-testid="candidate-period-comparison"
      data-state={payload.overall_status}
    >
      <header className="candidate-period-comparison__header">
        <div>
          <span>跨期变化</span>
          <h3 id="candidate-period-comparison-title">{model.headline}</h3>
          <p>
            {payload.report_month} 对比 {payload.comparison_month}；
            仅展示后端返回的变化值与比率，不在前端重算。
          </p>
        </div>
        <div className="candidate-period-comparison__boundary">
          <strong>候选分析 · 禁止正式使用</strong>
          <small>变化驱动尚不明确，不生成归因判断</small>
        </div>
      </header>

      {model.hasUnlockedHistoricalSource ? (
        <div className="candidate-period-comparison__source-warning" role="note">
          <strong>历史源未锁 · 降级候选</strong>
          <span>上期或上上期总账未登记锁定哈希；可比结果不得替代正式财务口径。</span>
        </div>
      ) : null}

      {payload.full_scope_status === "unavailable" ? (
        <div className="candidate-period-comparison__scope-gap" data-state="unavailable">
          <div>
            <strong>完整 186 项对比不可用</strong>
            <p>{payload.full_scope_detail}</p>
          </div>
          <ul aria-label="完整指标跨期对比缺口">
            {model.fullScopeGaps.map((gap) => (
              <li key={`${gap.month}-${gap.sourceLabel}-${gap.reasonLabel}`}>
                <span>{gap.month} · {gap.sourceLabel}</span>
                <strong>{gap.reasonLabel}</strong>
              </li>
            ))}
          </ul>
          <small>当前只展示固定关键指标；不绘制伪趋势，也不把缺失值解释为零。</small>
        </div>
      ) : (
        <div className="candidate-period-comparison__scope-ready" role="note">
          <strong>{payload.full_scope_detail}</strong>
          <span>上期完整来源 186 项重放校验可用</span>
          <small>本区仍仅展示固定七项关键候选指标。</small>
        </div>
      )}

      <NetInterestComponentBridge bridge={model.netInterestBridge} />

      <div className="candidate-period-comparison__table-wrap">
        <table aria-label="候选财务指标跨期变化明细">
          <thead>
            <tr>
              <th scope="col">指标</th>
              <th scope="col">比较口径</th>
              <th scope="col">本期</th>
              <th scope="col">上期</th>
              <th scope="col">变动</th>
              <th scope="col">环比</th>
              <th scope="col">候选状态</th>
            </tr>
          </thead>
          <tbody>
            {model.rows.map((row) => (
              <tr key={row.metricId} data-comparison-status={row.comparisonStatus}>
                <th scope="row">
                  <strong>{row.metricName}</strong>
                  <code>{row.metricId}</code>
                  {row.reason ? <small>{row.reason}</small> : null}
                </th>
                <td>{row.basisLabel}</td>
                <td className="candidate-period-comparison__number">{row.currentDisplay}</td>
                <td className="candidate-period-comparison__number">{row.previousDisplay}</td>
                <td className="candidate-period-comparison__number candidate-period-comparison__delta">
                  {row.deltaDisplay}
                </td>
                <td className="candidate-period-comparison__number">{row.rateDisplay}</td>
                <td>
                  <strong>{row.comparisonStatus === "comparable" ? "可比" : "暂不可比"}</strong>
                  <small>{row.qualityLabel}</small>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <footer className="candidate-period-comparison__footer">
        <span>金额单位：亿元</span>
        <span>规则：{payload.rule_version}</span>
        <span>正式化效力：无</span>
      </footer>
    </section>
  );
}
