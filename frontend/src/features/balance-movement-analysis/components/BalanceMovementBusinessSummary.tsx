import { formatSignedPointNullable } from "../lib/balanceMovementShareModel";
import {
  type BusinessMomMove,
  numericValue,
  accountingBasisNarrativeLabel,
  type BalanceMovementDriver,
} from "../lib/balanceMovementBusinessModel";
import {
  sourceKindLabel,
  sourceNotePreview,
  formatPlainNumber,
  moveDeltaToneClass,
  formatSignedYiNumber,
  formatPct,
  movementDirection,
  formatYiFixed,
} from "../lib/balanceMovementPresentation";
import type { BalanceMovementViewModel } from "../hooks/useBalanceMovementViewModel";

function BusinessMoverPanel({
  moves,
  testId,
  title,
  subtitle,
}: {
  moves: BusinessMomMove[];
  testId: string;
  title: string;
  subtitle: string;
}) {
  const maxDelta = Math.max(0, ...moves.map((move) => Math.abs(move.deltaYuan)));
  return (
    <article className="balance-movement-mover-panel">
      <div className="balance-movement-mover-panel__header">
        <h3>{title}</h3>
        <div><span>{subtitle}</span><small>同一零轴 · 单位亿元</small></div>
      </div>
      <div data-testid={testId} className="balance-movement-mover-panel__rows" role="list">
        {moves.map((item, index) => (
          <div
            key={`${item.rowKey}-${item.side}-${testId}-${index}`}
            className="balance-movement-mover-row"
            role="listitem"
            title={`${sourceKindLabel(item.sourceKind)} · ${sourceNotePreview(item.sourceNote)}`}
          >
            <div className="balance-movement-mover-row__label">
              <strong>{item.label}</strong>
              <span>{formatPlainNumber(item.previousYuan / 100000000)} → {formatPlainNumber(item.currentYuan / 100000000)}</span>
              <span data-testid="balance-movement-analysis-business-top-moves-source" className="balance-movement-sr-only">
                {sourceKindLabel(item.sourceKind)} {sourceNotePreview(item.sourceNote)}
              </span>
            </div>
            <div className="balance-movement-mover-axis" aria-hidden>
              <i />
              <progress
                className={item.deltaYuan >= 0 ? "balance-movement-mover-axis__bar balance-movement-mover-axis__bar--up" : "balance-movement-mover-axis__bar balance-movement-mover-axis__bar--down"}
                max={maxDelta || 1}
                value={Math.abs(item.deltaYuan)}
              />
            </div>
            <strong className={moveDeltaToneClass(item.deltaYuan)}>{formatSignedYiNumber(item.deltaYuan / 100000000)}</strong>
          </div>
        ))}
      </div>
    </article>
  );
}

type BalanceMovementBusinessSummaryProps = Pick<
  BalanceMovementViewModel,
    "businessMatrixMonths"
  | "hasBalanceChangeTotal"
  | "balanceChangeTotal"
  | "structureDriverHint"
  | "rowByBucket"
  | "movementDriverByBucket"
  | "businessTopMomMoves"
  | "businessTopSixMonthMoves"
  | "movementDrivers"
> & { topMovementDriver: BalanceMovementDriver };

export function BalanceMovementBusinessSummary({
  topMovementDriver,
  businessMatrixMonths,
  hasBalanceChangeTotal,
  balanceChangeTotal,
  structureDriverHint,
  rowByBucket,
  movementDriverByBucket,
  businessTopMomMoves,
  businessTopSixMonthMoves,
  movementDrivers,
}: BalanceMovementBusinessSummaryProps) {
  return (
    <section
      id="balance-movement-analysis-business-summary-anchor"
      data-testid="balance-movement-analysis-business-summary"
      className="balance-movement-figma-panel balance-movement-business-panel"
    >
      <header className="balance-movement-figma-header balance-movement-sec-no">
        <div>
          <h2 title="business_trend_months">业务行 Top 变动与余额驱动</h2>
        </div>
        <p>覆盖近 {businessMatrixMonths.length} 个月</p>
      </header>

      <div className="balance-movement-business-lead">
        <div className="balance-movement-business-lead__decision">
          <span>本期主结论</span>
          <strong>
            {hasBalanceChangeTotal ? (
              <>{topMovementDriver.bucket} {formatSignedYiNumber(topMovementDriver.balanceChangeYi)} 亿 · 贡献 {formatPct(topMovementDriver.contributionPct)}</>
            ) : (
              "总变动缺失，暂不判断方向"
            )}
          </strong>
          <p>
            {hasBalanceChangeTotal
              ? `本月总余额${movementDirection(balanceChangeTotal)} ${formatYiFixed(Math.abs(numericValue(balanceChangeTotal)))} 亿；单桶贡献集中，同时带动 ${accountingBasisNarrativeLabel(topMovementDriver.bucket)} 占比至 ${formatPct(topMovementDriver.currentBalancePct)}，较期初 ${formatSignedPointNullable(topMovementDriver.shareDelta)}`
              : "等待完整余额变动口径后再判断主导方向。"}
          </p>
          {structureDriverHint ? (
            <span data-testid="balance-movement-analysis-structure-driver-hint" className="balance-movement-sr-only">
              {structureDriverHint}
            </span>
          ) : null}
        </div>
        <div className="balance-movement-business-lead__stability" aria-label="结构稳定器">
          <div>
            <span>AC 稳定器</span>
            <strong>{formatPct(rowByBucket.get("AC")?.current_balance_pct)}</strong>
            <small>{formatSignedPointNullable(movementDriverByBucket.get("AC")?.shareDelta)}</small>
          </div>
          <div>
            <span>OCI 压舱石</span>
            <strong>{formatPct(rowByBucket.get("OCI")?.current_balance_pct)}</strong>
            <small>{formatSignedPointNullable(movementDriverByBucket.get("OCI")?.shareDelta)}</small>
          </div>
        </div>
      </div>

      {businessTopMomMoves.length > 0 ? (
        <div data-testid="balance-movement-analysis-business-top-moves" className="balance-movement-business-charts">
          <BusinessMoverPanel
            moves={businessTopMomMoves}
            testId="balance-movement-analysis-business-top-moves-mom"
            title="本月变动 · 发散视图"
            subtitle="本月对上月"
          />
          {businessTopSixMonthMoves.length > 0 ? (
            <BusinessMoverPanel
              moves={businessTopSixMonthMoves}
              testId="balance-movement-analysis-business-top-moves-sixmonth"
              title={`近 ${businessMatrixMonths.length} 月变动`}
              subtitle="首月对本月"
            />
          ) : null}
        </div>
      ) : null}

      <div data-testid="balance-movement-analysis-driver-chart" className="balance-movement-contribution">
        <div className="balance-movement-contribution__header">
          <h3>变动贡献构成</h3>
        </div>
        <div className="balance-movement-contribution__band" aria-label="余额变动贡献带">
          {movementDrivers.map((driver) => (
            <span
              key={driver.bucket}
              className={`balance-movement-contribution__segment balance-movement-contribution__segment--${driver.bucket.toLowerCase()}`}
              style={{ flexGrow: Math.abs(driver.balanceChangeYi) || 0.001 }}
            />
          ))}
        </div>
        <div data-testid="balance-movement-analysis-driver-ranking" className="balance-movement-contribution__labels">
          {movementDrivers.map((driver) => (
            <div className={`balance-movement-contribution__label--${driver.bucket.toLowerCase()}`} key={driver.bucket}>
              <span>{driver.bucket}</span>
              <strong>{formatSignedYiNumber(driver.balanceChangeYi)} 亿 · {formatPct(driver.contributionPct)}</strong>
              <small>占比 {formatPct(driver.currentBalancePct)} · {formatSignedPointNullable(driver.shareDelta)}</small>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
