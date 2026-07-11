import type { ApiEnvelope, LedgerMoneyValue, LedgerPnlAnalysisPayload } from "../../../api/contracts";

import "./LedgerPnlAnalysisWorkbench.css";

type Props = {
  envelope: ApiEnvelope<LedgerPnlAnalysisPayload> | undefined;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  onRetry: () => void;
  onSelectContributor?: (selection: LedgerPnlContributorSelection) => void;
};

export type LedgerPnlContributorSelection = {
  account_code: string;
  account_name: string;
  tone: "positive" | "negative";
};

function formatMoney(value: LedgerMoneyValue | null | undefined) {
  const yi = String(value?.yi ?? "").trim();
  return yi ? `${yi} 亿元` : "--";
}

function formatBasisMoney(
  value: LedgerMoneyValue | null,
  availability: "ready" | "no_data",
) {
  return availability === "ready" ? formatMoney(value) : "无数据";
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error ?? "");
}

function isForbidden(error: unknown) {
  return /(^|\D)403(\D|$)|forbidden|无权限/i.test(errorMessage(error));
}

const directionCopy: Record<LedgerPnlAnalysisPayload["conclusion"]["direction"], string> = {
  positive: "全量损益为正",
  negative: "全量损益为负",
  flat: "全量损益持平",
  unavailable: "全量损益方向不可用",
};

const otherEffectCopy: Record<LedgerPnlAnalysisPayload["conclusion"]["other_effect"], string> = {
  support: "其他 5* 损益形成支持",
  drag: "其他 5* 损益形成拖累",
  neutral: "其他 5* 损益影响中性",
  unavailable: "其他 5* 损益影响不可用",
};

const periodStatusCopy: Record<LedgerPnlAnalysisPayload["period_comparison"]["status"], string> = {
  available: "上一可用报告期对比",
  no_previous_period: "暂无上一可用报告期",
  current_basis_no_data: "当前账务口径暂无数据",
  previous_basis_no_data: "上一报告期的当前账务口径暂无数据",
};

function SourceStatus({ envelope }: { envelope: ApiEnvelope<LedgerPnlAnalysisPayload> }) {
  const meta = envelope.result_meta;
  const fallback = meta.fallback_mode === "latest_snapshot";
  const stale = meta.quality_flag === "stale" || meta.vendor_status === "vendor_stale";
  if (!fallback && !stale) {
    return null;
  }
  return (
    <div data-testid="ledger-pnl-analysis-source-status" className="ledger-analysis-source-status">
      {fallback ? (
        <div>
          <strong>已回退至最近可用报告日</strong>
          <span>
            请求日 {meta.requested_report_date || "--"} · 解析日 {meta.resolved_report_date || meta.fallback_date || "--"}
          </span>
        </div>
      ) : null}
      {stale ? (
        <div>
          <strong>数据可能已过期</strong>
          <span>截至日 {meta.as_of_date || "--"} · vendor {meta.vendor_status}</span>
        </div>
      ) : null}
    </div>
  );
}

function StateCard(props: {
  tone: "loading" | "warning" | "error";
  title: string;
  detail: string;
  onRetry?: () => void;
}) {
  return (
    <div className={`ledger-analysis-state ledger-analysis-state--${props.tone}`}>
      <strong>{props.title}</strong>
      <span>{props.detail}</span>
      {props.onRetry ? (
        <button type="button" onClick={props.onRetry}>
          重试分析
        </button>
      ) : null}
    </div>
  );
}

function AnalysisHeader({ payload }: { payload: LedgerPnlAnalysisPayload | undefined }) {
  return (
    <header className="ledger-analysis-header">
      <div>
        <span className="ledger-analysis-eyebrow">候选总账读模型</span>
        <h2>总账损益分析工作台</h2>
        <p>回答损益方向、核心与其他 5* 桥接、账务口径差异、上一期变化及科目贡献。</p>
      </div>
      <div className="ledger-analysis-header__badges">
        <span className="ledger-analysis-candidate-badge">候选分析</span>
        {payload ? <span className="ledger-analysis-basis-badge">{payload.currency_basis}</span> : null}
      </div>
    </header>
  );
}

function ConclusionPanel({ payload }: { payload: LedgerPnlAnalysisPayload }) {
  return (
    <section data-testid="ledger-pnl-analysis-conclusion" className="ledger-analysis-conclusion">
      <div className="ledger-analysis-conclusion__statement">
        <span>当期判断</span>
        <strong data-tone={payload.conclusion.direction}>{directionCopy[payload.conclusion.direction]}</strong>
        <p data-tone={payload.conclusion.other_effect}>{otherEffectCopy[payload.conclusion.other_effect]}</p>
      </div>
      <div className="ledger-analysis-metric-grid">
        <article>
          <span>核心损益</span>
          <strong>{formatMoney(payload.conclusion.core_pnl)}</strong>
        </article>
        <article>
          <span>其他 5* 损益</span>
          <strong>{formatMoney(payload.conclusion.other_5_pnl)}</strong>
        </article>
        <article data-tone={payload.conclusion.direction}>
          <span>全量损益</span>
          <strong>{formatMoney(payload.conclusion.all_pnl)}</strong>
        </article>
      </div>
    </section>
  );
}

function BridgePanel({ payload }: { payload: LedgerPnlAnalysisPayload }) {
  return (
    <section data-testid="ledger-pnl-analysis-bridge" className="ledger-analysis-card">
      <div className="ledger-analysis-card__header">
        <div>
          <span>闭环</span>
          <h3>核心 + 其他 5* = 全量</h3>
        </div>
        <span className="ledger-analysis-card__unit">亿元</span>
      </div>
      <div className="ledger-analysis-bridge">
        {payload.pnl_bridge.components.map((component, index) => (
          <div key={component.metric_key} className="ledger-analysis-bridge__term">
            {index > 0 ? <span aria-hidden className="ledger-analysis-bridge__operator">+</span> : null}
            <span>{component.metric_name}</span>
            <strong>{formatMoney(component.amount)}</strong>
          </div>
        ))}
        <span aria-hidden className="ledger-analysis-bridge__operator">=</span>
        <div className="ledger-analysis-bridge__term ledger-analysis-bridge__term--total">
          <span>全量损益</span>
          <strong>{formatMoney(payload.pnl_bridge.total)}</strong>
        </div>
      </div>
      <div className="ledger-analysis-residual">
        <span>闭环残差</span>
        <strong>{formatMoney(payload.pnl_bridge.residual)}</strong>
        <small>金额由后端返回，前端不复算。</small>
      </div>
    </section>
  );
}

function PeriodPanel({ payload }: { payload: LedgerPnlAnalysisPayload }) {
  const comparison = payload.period_comparison;
  const allPnlChange = comparison.rows.find((row) => row.metric_key === "all_pnl");
  const otherPnlChange = comparison.rows.find((row) => row.metric_key === "other_5_pnl");
  return (
    <section data-testid="ledger-pnl-analysis-period" className="ledger-analysis-card">
      <div className="ledger-analysis-card__header">
        <div>
          <span>时序</span>
          <h3>{periodStatusCopy[comparison.status]}</h3>
        </div>
        {comparison.previous_report_date ? (
          <span className="ledger-analysis-card__date">{comparison.previous_report_date}</span>
        ) : null}
      </div>
      {comparison.status === "available" ? (
        <>
          <div className="ledger-analysis-period-highlights">
            {allPnlChange ? <span>全量变化 <strong>{formatMoney(allPnlChange.change)}</strong></span> : null}
            {otherPnlChange ? <span>其他 5* 变化 <strong>{formatMoney(otherPnlChange.change)}</strong></span> : null}
          </div>
          <div className="ledger-analysis-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>指标</th>
                  <th>本期</th>
                  <th>上期</th>
                  <th>变化</th>
                </tr>
              </thead>
              <tbody>
                {comparison.rows.map((row) => (
                  <tr key={row.metric_key}>
                    <td>{row.metric_name}</td>
                    <td>{formatMoney(row.current)}</td>
                    <td>{formatMoney(row.previous)}</td>
                    <td>{formatMoney(row.change)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="ledger-analysis-empty">{periodStatusCopy[comparison.status]}，不以 0 补齐。</p>
      )}
    </section>
  );
}

function BasisPanel({ payload }: { payload: LedgerPnlAnalysisPayload }) {
  const complete = payload.basis_availability.CNX === "ready" && payload.basis_availability.CNY === "ready";
  return (
    <section data-testid="ledger-pnl-analysis-basis" className="ledger-analysis-card ledger-analysis-card--wide">
      <div className="ledger-analysis-card__header">
        <div>
          <span>账务口径</span>
          <h3>CNX / CNY / CNX - CNY</h3>
        </div>
        <span className="ledger-analysis-card__unit">不可相加，也不是 FX PnL</span>
      </div>
      {!complete ? (
        <div className="ledger-analysis-basis-warning">
          <strong>对比口径数据不完整</strong>
          <span>CNX {payload.basis_availability.CNX} · CNY {payload.basis_availability.CNY}</span>
          <small>损益口径不完整；逐指标仍按自身证据展示，缺失值不按 0 处理。</small>
        </div>
      ) : null}
      <div className="ledger-analysis-table-wrap">
        <table>
          <thead>
            <tr>
              <th>指标</th>
              <th>CNX（综本）</th>
              <th>CNY（人民币账）</th>
              <th>CNX - CNY</th>
            </tr>
          </thead>
          <tbody>
            {payload.basis_comparison.map((row) => (
              <tr key={row.metric_key}>
                <td>{row.metric_name}</td>
                <td title={`证据 ${row.evidence_rows.CNX} 行`}>
                  {formatBasisMoney(row.cnx, row.availability.CNX)}
                </td>
                <td title={`证据 ${row.evidence_rows.CNY} 行`}>
                  {formatBasisMoney(row.cny, row.availability.CNY)}
                </td>
                <td>
                  {row.availability.CNX === "ready" && row.availability.CNY === "ready"
                    ? formatMoney(row.cnx_minus_cny)
                    : "不可比"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ContributorList(props: {
  title: string;
  rows: LedgerPnlAnalysisPayload["contributors"]["top_positive"];
  emptyLabel: string;
  tone: "positive" | "negative";
  onSelect?: (selection: LedgerPnlContributorSelection) => void;
}) {
  return (
    <div className="ledger-analysis-contributor-list" data-tone={props.tone}>
      <h4>{props.title}</h4>
      {props.rows.length > 0 ? (
        <ol>
          {props.rows.map((row) => (
            <li key={`${row.rank}-${row.account_code}`}>
              <button
                type="button"
                aria-haspopup="dialog"
                aria-label={`查看科目穿透 ${row.account_code} ${row.account_name}`}
                onClick={() => props.onSelect?.({
                  account_code: row.account_code,
                  account_name: row.account_name,
                  tone: props.tone,
                })}
              >
                <span className="ledger-analysis-contributor-rank">{row.rank}</span>
                <span className="ledger-analysis-contributor-name">
                  <strong>{row.account_code} {row.account_name}</strong>
                  <small>{row.count} 行</small>
                </span>
                <strong>{formatMoney(row.amount)}</strong>
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <p className="ledger-analysis-empty">{props.emptyLabel}</p>
      )}
    </div>
  );
}

function ContributorsPanel(props: {
  payload: LedgerPnlAnalysisPayload;
  onSelectContributor?: (selection: LedgerPnlContributorSelection) => void;
}) {
  const { payload } = props;
  return (
    <section data-testid="ledger-pnl-analysis-contributors" className="ledger-analysis-card ledger-analysis-card--wide">
      <div className="ledger-analysis-card__header">
        <div>
          <span>科目贡献</span>
          <h3>Top 正贡献与拖累</h3>
        </div>
        <span className="ledger-analysis-card__unit">后端排名</span>
      </div>
      <div className="ledger-analysis-contributor-totals">
        <span>正贡献 <strong>{formatMoney(payload.contributors.positive_total)}</strong></span>
        <span>负贡献 <strong>{formatMoney(payload.contributors.negative_total)}</strong></span>
        <span>净额 <strong>{formatMoney(payload.contributors.net_total)}</strong></span>
      </div>
      <div className="ledger-analysis-contributor-grid">
        <ContributorList
          title="正贡献"
          rows={payload.contributors.top_positive}
          emptyLabel="暂无正贡献科目"
          tone="positive"
          onSelect={props.onSelectContributor}
        />
        <ContributorList
          title="拖累"
          rows={payload.contributors.top_negative}
          emptyLabel="暂无拖累科目"
          tone="negative"
          onSelect={props.onSelectContributor}
        />
      </div>
    </section>
  );
}

function CalculationBasis({ payload }: { payload: LedgerPnlAnalysisPayload }) {
  const basis = payload.calculation_basis;
  return (
    <footer className="ledger-analysis-calculation-basis">
      <strong>计算口径</strong>
      <span>核心前缀 {basis.core_pnl_prefixes.join(" / ") || "--"}</span>
      <span>全量前缀 {basis.all_pnl_prefixes.join(" / ") || "--"}</span>
      <span title={`${basis.other_5_pnl_formula} · ${basis.other_5_pnl_boundary}`}>其他 5* = 全量 - 核心（算术残差）</span>
      <span title={basis.basis_difference_formula}>差额 = CNX - CNY</span>
      <span title={basis.previous_period_rule}>上一期 = 最近可用报告日</span>
      <span title={basis.basis_boundary}>CNX / CNY 不可相加且非 FX PnL</span>
      <span title={basis.basis_availability_boundary}>各指标按自身证据判定，缺失不补 0</span>
      <span title={basis.metric_boundary}>候选非正式</span>
    </footer>
  );
}

export function LedgerPnlAnalysisWorkbench(props: Props) {
  const payload = props.envelope?.result;
  const hasBasisEvidence = Boolean(
    payload?.basis_comparison.some(
      (row) => row.availability.CNX === "ready" || row.availability.CNY === "ready",
    ),
  );
  const dataState = props.isLoading
    ? "loading"
    : props.isError
      ? "error"
      : payload?.analysis_status ?? "no_data";

  return (
    <section
      data-testid="ledger-pnl-analysis-workbench"
      data-state={dataState}
      className="ledger-analysis-workbench"
    >
      <AnalysisHeader payload={payload} />

      {props.isLoading ? (
        <StateCard tone="loading" title="总账分析读取中" detail="正在读取候选结论、桥接、账务口径与期间对比。" />
      ) : props.isError ? (
        <StateCard
          tone="error"
          title={isForbidden(props.error) ? "无权限读取总账损益分析" : "总账损益分析读取失败"}
          detail={isForbidden(props.error) ? "当前用户缺少 ledger_pnl 读取权限。" : errorMessage(props.error) || "请重试分析读取。"}
          onRetry={props.onRetry}
        />
      ) : !props.envelope || !payload ? (
        <StateCard tone="warning" title="暂无分析响应" detail="未收到候选总账分析结果，不以 0 补齐。" onRetry={props.onRetry} />
      ) : props.envelope.result_meta.vendor_status === "vendor_unavailable" ? (
        <StateCard tone="warning" title="总账分析上游数据不可用" detail="当前不能形成候选分析结论。" onRetry={props.onRetry} />
      ) : payload.analysis_status === "no_data" ? (
        <>
          <SourceStatus envelope={props.envelope} />
          <StateCard tone="warning" title="当前报告日与账务口径暂无损益分析数据" detail="无数据不等于损益为 0；若余额指标有证据，仍在下方按逐指标口径展示。" />
          {hasBasisEvidence ? (
            <div className="ledger-analysis-work-grid ledger-analysis-work-grid--partial">
              <BasisPanel payload={payload} />
            </div>
          ) : null}
          <CalculationBasis payload={payload} />
        </>
      ) : (
        <>
          <SourceStatus envelope={props.envelope} />
          <ConclusionPanel payload={payload} />
          <div className="ledger-analysis-work-grid">
            <BridgePanel payload={payload} />
            <PeriodPanel payload={payload} />
            <BasisPanel payload={payload} />
            <ContributorsPanel payload={payload} onSelectContributor={props.onSelectContributor} />
          </div>
          <CalculationBasis payload={payload} />
        </>
      )}
    </section>
  );
}
