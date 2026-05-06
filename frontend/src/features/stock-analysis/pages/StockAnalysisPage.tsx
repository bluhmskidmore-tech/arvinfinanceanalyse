import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { LivermoreSignalConfluencePayload } from "../../../api/contracts";
import {
  buildCandidateEvidenceCards,
  buildDataBoundaryNotes,
  buildMarketStateCard,
  buildRiskExitRows,
  buildSectorRows,
} from "../lib/stockAnalysisPageModel";
import "./StockAnalysisPage.css";

function errorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pass: "通过",
    fail: "未通过",
    missing: "缺数据",
    stale: "已陈旧",
  };
  return labels[status] ?? status;
}

function riskStatusLabel(status: "triggered" | "watch") {
  return status === "triggered" ? "触发复核" : "观察中";
}

export default function StockAnalysisPage() {
  const client = useApiClient();

  const strategyQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-strategy"],
    queryFn: () => client.getLivermoreStrategy(),
  });

  const strategyPayload = strategyQuery.data?.result ?? null;
  const asOfDate = strategyPayload?.as_of_date ?? undefined;

  const confluenceQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-signal-confluence", asOfDate],
    queryFn: () => client.getLivermoreSignalConfluence({ asOfDate }),
    enabled: Boolean(asOfDate),
  });

  const confluencePayload: LivermoreSignalConfluencePayload | null =
    confluenceQuery.data?.result ?? null;

  const marketState = useMemo(
    () => (strategyPayload ? buildMarketStateCard(strategyPayload) : null),
    [strategyPayload],
  );
  const sectorRows = useMemo(
    () => (strategyPayload ? buildSectorRows(strategyPayload) : []),
    [strategyPayload],
  );
  const candidateCards = useMemo(
    () => (strategyPayload ? buildCandidateEvidenceCards(strategyPayload) : []),
    [strategyPayload],
  );
  const riskRows = useMemo(
    () => (strategyPayload ? buildRiskExitRows(strategyPayload, confluencePayload) : []),
    [strategyPayload, confluencePayload],
  );
  const boundaryNotes = useMemo(
    () => (strategyPayload ? buildDataBoundaryNotes(strategyPayload) : []),
    [strategyPayload],
  );

  return (
    <main className="stock-analysis-page" data-testid="stock-analysis-page">
      <header className="stock-analysis-page__header">
        <p className="stock-analysis-page__eyebrow">A股观察 / Evidence first</p>
        <div className="stock-analysis-page__header-main">
          <div>
            <h1>股票分析</h1>
            <p>
              复用 Livermore 与 Choice 股票只读链路，展示市场状态、行业强弱、候选股证据和风险观察；仅供研究复核，不构成交易指令。
            </p>
          </div>
          <div className="stock-analysis-page__badge">仅观察 / 复核 / 研究</div>
        </div>
      </header>

      {strategyQuery.isLoading ? (
        <section className="stock-analysis-page__panel">
          <p className="stock-analysis-page__state">正在加载股票分析结果。</p>
        </section>
      ) : null}

      {strategyQuery.isError ? (
        <section className="stock-analysis-page__panel stock-analysis-page__panel--error">
          <h2>股票分析结果加载失败。</h2>
          <p>{errorMessage(strategyQuery.error)}</p>
        </section>
      ) : null}

      {marketState ? (
        <>
          <section className="stock-analysis-page__panel">
            <div className="stock-analysis-page__section-head">
              <div>
                <h2>{marketState.title}</h2>
                <p>先看市场门控，再看行业与个股证据。</p>
              </div>
              <span className="stock-analysis-page__pill">{marketState.basisLabel}</span>
            </div>
            <div className="stock-analysis-page__kpis">
              <div className="stock-analysis-page__kpi">
                <span>状态</span>
                <strong>{marketState.state}</strong>
              </div>
              <div className="stock-analysis-page__kpi">
                <span>观察暴露</span>
                <strong>{marketState.exposureLabel}</strong>
              </div>
              <div className="stock-analysis-page__kpi">
                <span>门控确认</span>
                <strong>{marketState.passedLabel}</strong>
              </div>
            </div>
            <div className="stock-analysis-page__split">
              <div>
                <h3>门控条件</h3>
                <ul className="stock-analysis-page__list">
                  {marketState.conditions.map((condition) => (
                    <li key={condition.key}>
                      <span>
                        <strong>{condition.label}</strong>
                        <small>{condition.evidence}</small>
                      </span>
                      <em>{statusLabel(condition.status)}</em>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h3>需关注边界</h3>
                {marketState.warnings.length > 0 ? (
                  <ul className="stock-analysis-page__notes">
                    {marketState.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="stock-analysis-page__empty">当前无诊断预警。</p>
                )}
              </div>
            </div>
          </section>

          <section className="stock-analysis-page__panel">
            <div className="stock-analysis-page__section-head">
              <div>
                <h2>行业强弱</h2>
                <p>来自 Livermore sector_rank，仅显示后端已提供的观察排序。</p>
              </div>
              <span className="stock-analysis-page__pill">
                {strategyPayload?.sector_rank?.formula_version ?? "formula 待补"}
              </span>
            </div>
            {sectorRows.length > 0 ? (
              <div className="stock-analysis-page__table-wrap">
                <table className="stock-analysis-page__table">
                  <thead>
                    <tr>
                      <th>排名</th>
                      <th>行业</th>
                      <th>分数</th>
                      <th>涨跌幅</th>
                      <th>换手</th>
                      <th>振幅</th>
                      <th>成分数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sectorRows.map((row) => (
                      <tr key={row.sectorCode}>
                        <td>#{row.rank}</td>
                        <td>
                          {row.sectorName}
                          <small>{row.sectorCode}</small>
                        </td>
                        <td>{row.score}</td>
                        <td>{row.pctChange}</td>
                        <td>{row.turnover}</td>
                        <td>{row.amplitude}</td>
                        <td>{row.constituentCount}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="stock-analysis-page__empty">
                当前行业强弱不可用，请检查 Choice 股票目录和当日股票落地覆盖。
              </p>
            )}
          </section>

          <section
            className="stock-analysis-page__panel"
            data-testid="stock-analysis-candidates-section"
          >
            <div className="stock-analysis-page__section-head">
              <div>
                <h2>候选股证据卡</h2>
                <p>说明为什么进入观察、反证与待补证据，以及失效条件。</p>
              </div>
              <span className="stock-analysis-page__pill">候选 / 复核</span>
            </div>
            {candidateCards.length > 0 ? (
              <div className="stock-analysis-page__candidate-grid">
                {candidateCards.map((card) => (
                  <article
                    className="stock-analysis-page__candidate"
                    data-testid={`stock-candidate-${card.stockCode}`}
                    key={card.stockCode}
                  >
                    <div className="stock-analysis-page__candidate-head">
                      <div>
                        <h3>{card.headline}</h3>
                        <p>
                          {card.stockCode} · {card.stockName} · {card.sectorName}
                        </p>
                      </div>
                      <span>观察</span>
                    </div>
                    <h4>入选证据</h4>
                    <ul>
                      {card.evidence.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                    <h4>反证 / 待补证据</h4>
                    <ul>
                      {card.counterEvidence.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                    <h4>失效条件</h4>
                    <ul>
                      {card.invalidationRules.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            ) : (
              <p className="stock-analysis-page__empty">当前无候选股证据卡。</p>
            )}
          </section>

          <section className="stock-analysis-page__panel">
            <div className="stock-analysis-page__section-head">
              <div>
                <h2>风险退出观察</h2>
                <p>展示风险退出项、观察项与可用的联动观察，不使用交易动作标签。</p>
              </div>
              <span className="stock-analysis-page__pill">退出观察价</span>
            </div>
            {confluenceQuery.isError ? (
              <p className="stock-analysis-page__notice">联动观察暂不可用。</p>
            ) : null}
            {riskRows.length > 0 ? (
              <div className="stock-analysis-page__table-wrap">
                <table className="stock-analysis-page__table">
                  <thead>
                    <tr>
                      <th>股票</th>
                      <th>状态</th>
                      <th>最新收盘</th>
                      <th>退出观察价</th>
                      <th>原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {riskRows.map((row) => (
                      <tr key={`${row.stockCode}:${row.status}:${row.reason}`}>
                        <td>
                          {row.stockName}
                          <small>{row.stockCode}</small>
                        </td>
                        <td>{riskStatusLabel(row.status)}</td>
                        <td>{row.latestClose}</td>
                        <td>{row.exitWatchPrice}</td>
                        <td>{row.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="stock-analysis-page__empty">当前无风险退出观察项。</p>
            )}
          </section>

          <section className="stock-analysis-page__panel stock-analysis-page__panel--pending">
            <div className="stock-analysis-page__section-head">
              <div>
                <h2>银行股专题待补证据</h2>
                <p>不伪造银行股基本面数据，只保留后续接入字段入口。</p>
              </div>
              <span className="stock-analysis-page__pill">待补</span>
            </div>
            <p>
              PB / ROE / 分红率 / NIM / 不良率 / 拨备覆盖率 / 资本充足率 / 金融市场业务收益敏感性。
              当前仅展示待补字段，不参与候选排序；后续接入正式或可追溯数据后再进入证据卡。
            </p>
          </section>

          <section className="stock-analysis-page__panel">
            <div className="stock-analysis-page__section-head">
              <div>
                <h2>数据口径与边界</h2>
                <p>保留来源、规则版本、缺口、支持输出与不支持输出的审计线索。</p>
              </div>
              <span className="stock-analysis-page__pill">只读链路</span>
            </div>
            <ul className="stock-analysis-page__notes">
              {boundaryNotes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
            {strategyQuery.data?.result_meta ? (
              <div className="stock-analysis-page__meta-grid">
                <span>quality_flag: {strategyQuery.data.result_meta.quality_flag}</span>
                <span>vendor_status: {strategyQuery.data.result_meta.vendor_status}</span>
                <span>source_version: {strategyQuery.data.result_meta.source_version}</span>
                <span>rule_version: {strategyQuery.data.result_meta.rule_version}</span>
                <span>
                  tables_used: {strategyQuery.data.result_meta.tables_used?.join(", ") || "待补"}
                </span>
              </div>
            ) : null}
          </section>
        </>
      ) : null}
    </main>
  );
}
