import type {
  BalanceMovementRow,
  BalanceStructureMigrationAnalysis,
  BalanceDifferenceAttributionWaterfall,
  BalanceBasisMovementDecomposition,
} from "../../../api/contracts";
import { ReconciliationStatusTag } from "./ReconciliationStatusTag";
import { SectionHead } from "../../../components/layout";
import { EM_DASH } from "../../../utils/format";
import {
  formatYiFixed,
  formatSignedYi,
  formatPct,
  formatSignedYiCell,
  formatSignedPercentPoint,
  formatYiCell,
  finiteMetric,
  drilldownStatusLabel,
} from "../lib/balanceMovementPresentation";
import type { BalanceExplanationClosure } from "../lib/balanceMovementDiagnostics";

export function FigmaAccountingBuckets({ rows }: { rows: BalanceMovementRow[] }) {
  return (
    <section className="balance-movement-accounting-buckets" data-testid="balance-movement-analysis-accounting-buckets">
      <header className="balance-movement-section-heading balance-movement-sec-no">
        <div>
          <h2>AC / OCI / TPL 核心对账</h2>
        </div>
      </header>
      <div className="balance-movement-accounting-buckets__scroll">
        <table>
          <thead>
            <tr>
              <th>分类</th>
              <th>期初余额</th>
              <th>期末余额</th>
              <th>变动</th>
              <th>期末占比</th>
              <th>变动贡献</th>
              <th>对账</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.basis_bucket}>
                <th scope="row">{row.basis_bucket}</th>
                <td>{formatYiFixed(row.previous_balance)} 亿</td>
                <td>{formatYiFixed(row.current_balance)} 亿</td>
                <td>{formatSignedYi(row.balance_change)}</td>
                <td>{formatPct(row.current_balance_pct)}</td>
                <td>{formatPct(row.contribution_pct)}</td>
                <td><ReconciliationStatusTag status={row.reconciliation_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function StructureBridgeStage({
  analysis,
  waterfall,
  closure,
}: {
  analysis: BalanceStructureMigrationAnalysis | null;
  waterfall: BalanceDifferenceAttributionWaterfall | null;
  closure: BalanceExplanationClosure | null;
}) {
  if (!analysis && !waterfall && !closure) {
    return null;
  }

  const latestPair = analysis?.pairs[analysis.pairs.length - 1] ?? null;
  const unsupportedComponents = waterfall?.components.filter((component) => !component.is_supported) ?? [];

  return (
    <section
      className="balance-movement-structure-bridge balance-movement-figma-panel"
      data-testid="balance-movement-analysis-structure-bridge"
    >
      <SectionHead
        title="结构迁移与差异归因"
        numbered={{ counter: "bm-section", increment: true }}
        contentGap="flush"
      />

      <div className="balance-movement-structure-bridge__columns">
        <article
          className="balance-movement-structure-bridge__migration"
          data-testid="balance-movement-analysis-structure-migration"
        >
          <span className="balance-movement-sr-only">结构迁移信号</span>
          <header>
            <h3>AC / OCI / TPL 占比迁移</h3>
            <strong>
              {latestPair?.dominant_share_increase_bucket
                ? `${latestPair.dominant_share_increase_bucket} 抬升最明显`
                : "等待可比期间"}
            </strong>
          </header>
          <p>{analysis?.summary ?? "结构迁移分析未返回。"}</p>
          {latestPair ? (
            <p>
              {latestPair.previous_report_date} → {latestPair.current_report_date} · 总余额{" "}
              {formatSignedYiCell(latestPair.total_balance_delta)} 亿
            </p>
          ) : null}
          {latestPair?.buckets.map((bucket) => (
            <div
              key={bucket.basis_bucket}
              className="balance-movement-structure-bridge__bucket"
              data-bucket={bucket.basis_bucket}
            >
              <span>{bucket.basis_bucket}</span>
              <div>
                <strong>{formatSignedYiCell(bucket.balance_delta)} 亿</strong>
                <small>
                  {formatPct(bucket.previous_share_pct)} → {formatPct(bucket.current_share_pct)}
                </small>
              </div>
              <em>{formatSignedPercentPoint(bucket.share_delta_pp)}</em>
            </div>
          ))}
          <aside>
            <strong>解释边界</strong>
            <p>{analysis?.caveat ?? "这是汇总分类桶的结构信号，不代表单只资产分类迁移。"}</p>
            {latestPair ? (
              <small className="balance-movement-structure-bridge__signals">
                {latestPair.fvtpl_volatility_signal} · {latestPair.oci_valuation_signal}
              </small>
            ) : null}
          </aside>
        </article>

        <article
          className="balance-movement-structure-bridge__waterfall"
          data-testid="balance-movement-analysis-difference-waterfall"
        >
          <span className="balance-movement-sr-only">差异归因瀑布</span>
          <header>
            <h3>ZQTZ 明细汇总 → AC / OCI / TPL 合计</h3>
            <strong>
              净差额 {waterfall ? `${formatSignedYiCell(waterfall.net_difference)} 亿` : EM_DASH}
            </strong>
          </header>
          {waterfall ? (
            <>
              <div className="balance-movement-structure-bridge__endpoint">
                <span>起点 · {waterfall.reference_label}</span>
                <strong>{formatYiCell(waterfall.reference_total)} 亿</strong>
              </div>
              {waterfall.components.map((component) => {
                const isUnsupported = component.is_supported === false;
                const className = [
                  "balance-movement-waterfall__component",
                  component.is_residual ? "balance-movement-waterfall__component--residual" : "",
                  isUnsupported ? "balance-movement-waterfall__component--unsupported" : "",
                ]
                  .filter(Boolean)
                  .join(" ");
                return (
                  <div key={component.component_key} className={className}>
                    <div>
                      <span>{component.component_label}</span>
                      <p>{isUnsupported ? `未支持，不反推 · ${component.evidence_note}` : component.evidence_note}</p>
                    </div>
                    <strong>
                      {isUnsupported ? "待拆分" : `${formatSignedYiCell(component.amount)} 亿`}
                    </strong>
                  </div>
                );
              })}
              <div className="balance-movement-structure-bridge__endpoint balance-movement-structure-bridge__endpoint--target">
                <span>终点 · {waterfall.target_label}</span>
                <strong>{formatYiCell(waterfall.target_total)} 亿</strong>
              </div>
              <div
                className="balance-movement-structure-bridge__closure"
                data-testid="balance-movement-analysis-explanation-closure"
              >
                <div>
                  <span>已支持解释项</span>
                  <strong>{closure?.supportedComponents.length ?? waterfall.components.filter((item) => item.is_supported).length} 项</strong>
                </div>
                <div>
                  <span>待补口径</span>
                  <strong>{closure?.unsupportedComponents.length ?? unsupportedComponents.length} 项</strong>
                </div>
                <div>
                  <span>闭合校验</span>
                  <strong>{formatSignedYiCell(waterfall.closing_check)} 亿</strong>
                </div>
                <span className="balance-movement-sr-only">
                  解释闭合度 · 未支持项 · 未分类 / 残差 ·
                  {closure?.unsupportedComponents
                    .map((component) => component.component_label)
                    .join("、")} · 未支持，不反推 ·
                  {closure?.residualRatioPct === null || closure?.residualRatioPct === undefined
                    ? EM_DASH
                    : formatPct(closure.residualRatioPct)} · {closure?.headline} {closure?.note}
                </span>
              </div>
              <div
                className="balance-movement-sr-only"
                data-testid="balance-movement-analysis-residual-closure"
              >
                哪些差异还不能解释：未分类 / 残差；
                {unsupportedComponents.map((component) => component.component_label).join("、")}；
                未支持，不反推。
              </div>
            </>
          ) : (
            <p>difference_attribution_waterfall 未返回，页面不反推差异组件。</p>
          )}
        </article>
      </div>
    </section>
  );
}

export function LiveBasisDecompositionStage({
  decomposition,
  hasCalibration,
}: {
  decomposition: BalanceBasisMovementDecomposition;
  hasCalibration: boolean;
}) {
  const sumBucketMetric = (
    selector: (bucket: BalanceBasisMovementDecomposition["buckets"][number]) => string | number | null | undefined,
  ) => {
    let total = 0;
    for (const bucket of decomposition.buckets) {
      const value = finiteMetric(selector(bucket));
      if (value === null) return null;
      total += value;
    }
    return total;
  };
  const currentTotal = sumBucketMetric((bucket) => bucket.current_balance);
  const residualTotal = sumBucketMetric((bucket) => bucket.residual_amount);
  const closingTotal = sumBucketMetric((bucket) => bucket.closing_check);

  return (
    <section
      id="balance-movement-analysis-basis-anchor"
      className="balance-movement-live-decomposition"
      data-testid="balance-movement-analysis-live-decomposition"
    >
      <div
        className="balance-movement-live-decomposition__content"
        data-testid="balance-movement-analysis-basis-decomposition"
      >
        <span className="balance-movement-sr-only">AC / OCI / TPL 驱动拆解</span>
        <header className="balance-movement-figma-header balance-movement-sec-no">
          <div>
            <h2>会计分类驱动拆解与口径状态</h2>
          </div>
          <p>
            报告日 {decomposition.meta.report_date} / 上期{" "}
            {decomposition.meta.prior_report_date ?? EM_DASH} / {decomposition.meta.currency_basis}
          </p>
        </header>

        <div className="balance-movement-live-decomposition__metrics">
          <article className="balance-movement-live-decomposition__metric balance-movement-live-decomposition__metric--positive">
            <span>覆盖率</span>
            <strong>{formatPct(decomposition.meta.coverage_pct)}</strong>
          </article>
          <article className="balance-movement-live-decomposition__metric">
            <span>期末合计</span>
            <strong>{formatYiCell(currentTotal)} 亿</strong>
          </article>
          <article className="balance-movement-live-decomposition__metric balance-movement-live-decomposition__metric--positive">
            <span>分解残差</span>
            <strong>{formatSignedYiCell(residualTotal)} 亿</strong>
          </article>
          <article className="balance-movement-live-decomposition__metric balance-movement-live-decomposition__metric--positive">
            <span title="closing_check">期末校验</span>
            <strong>{formatSignedYiCell(closingTotal)} 亿</strong>
          </article>
        </div>

        <div className="balance-movement-live-decomposition__buckets">
          {decomposition.buckets.map((bucket) => (
            <article
              key={bucket.basis_bucket}
              className="balance-movement-live-decomposition__bucket"
              data-bucket={bucket.basis_bucket}
            >
              <header>
                <div>
                  <h3>{bucket.basis_bucket}</h3>
                  <small>
                    {formatYiCell(bucket.previous_balance)} → {formatYiCell(bucket.current_balance)} 亿
                  </small>
                </div>
                <strong>{formatSignedYiCell(bucket.balance_change)} 亿</strong>
              </header>
              <span>科目组件 / 变动 / 绝对贡献</span>
              <ul>
                {bucket.rows.map((row) => (
                  <li
                    key={`${bucket.basis_bucket}-${row.component_key}`}
                    className="balance-movement-live-decomposition__component"
                    title={row.source_note}
                  >
                    <span>{row.component_label}</span>
                    <strong>{formatSignedYiCell(row.balance_change)}</strong>
                    <small>{row.is_supported ? formatPct(row.contribution_pct) : "未支持"}</small>
                  </li>
                ))}
              </ul>
              <footer title="residual / closing_check">
                残差 {formatSignedYiCell(bucket.residual_amount)} 亿 · 期末校验{" "}
                {formatSignedYiCell(bucket.closing_check)} 亿
              </footer>
            </article>
          ))}
        </div>

        <div
          className="balance-movement-live-decomposition__availability"
          title={`${decomposition.meta.caveat} / ${decomposition.meta.source_scope} / zqtz_calibration_analysis = ${hasCalibration ? "available" : "null"}`}
        >
          口径状态：{drilldownStatusLabel(decomposition.meta.status)}；数据源与口径原文见本行悬浮提示。
          {hasCalibration
            ? "校准结果已返回，完整核对卡保留在数据治理区。"
            : "本期无校准结果，页面不生成校准结论。"}
        </div>
      </div>
    </section>
  );
}

export function DrilldownUnavailablePanel({
  testId,
  eyebrow,
  title,
  fieldName,
}: {
  testId: string;
  eyebrow: string;
  title: string;
  fieldName: string;
}) {
  return (
    <section
      className="balance-movement-derived-panel balance-movement-derived-panel--unavailable"
      data-testid={testId}
    >
      <div className="balance-movement-derived-panel__header balance-movement-sec-no">
        <div>
          <span>{eyebrow}</span>
          <h2>{title}</h2>
        </div>
        <strong>未返回</strong>
      </div>
      <div className="balance-movement-derived-empty">
        <span>数据状态</span>
        <p>当前接口未返回 {fieldName}，本分析模块已预留位置但暂无可展示明细。</p>
      </div>
    </section>
  );
}
