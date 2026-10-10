import type { BalanceMovementReadState } from "../hooks/useBalanceMovementAnalysis";
import type { BalanceMovementPayload, BalanceMovementDatesPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { formatSignedPointNullable } from "../lib/balanceMovementShareModel";
import {
  type BalanceMovementDriver,
  accountingBasisNarrativeLabel,
} from "../lib/balanceMovementBusinessModel";
import {
  finiteMetric,
  formatPct,
  formatSignedYiNumber,
  formatYiFixed,
  formatSignedYi,
  formatPlainNumber,
} from "../lib/balanceMovementPresentation";
import { FreshnessStrip } from "./BalanceMovementTrust";

export function FigmaDecisionHero({
  balanceChangePct,
  balanceChangeTotal,
  topDriver,
  movementDrivers,
  dates,
  readStatus,
  selectedDate,
  reconciliationLabel,
  currencyBasis,
}: {
  balanceChangePct: number | null;
  balanceChangeTotal: BalanceMovementPayload["summary"]["balance_change_total"];
  topDriver: BalanceMovementDriver;
  movementDrivers: BalanceMovementDriver[];
  dates: BalanceMovementDatesPayload;
  readStatus: BalanceMovementReadState;
  selectedDate: string;
  reconciliationLabel: string;
  currencyBasis: string;
}) {
  const balanceChangeValue = finiteMetric(balanceChangeTotal);
  const direction =
    balanceChangeValue === null ? EM_DASH : balanceChangeValue > 0 ? "上升" : balanceChangeValue < 0 ? "下降" : "持平";
  const structureDirection = (topDriver.shareDelta ?? 0) >= 0 ? "抬升" : "回落";
  const tplDriver = movementDrivers.find((driver) => driver.bucket === "TPL");
  const ociDriver = movementDrivers.find((driver) => driver.bucket === "OCI");
  const reconciliationHeadline =
    reconciliationLabel === "三桶一致" ? "对账完整" : reconciliationLabel;
  return (
    <section
      className="balance-movement-decision-layout"
      data-testid="balance-movement-analysis-decision-hero"
    >
      <article className="balance-movement-decision-hero" data-testid="balance-movement-analysis-conclusion">
        <header>
          <span>决策信号</span>
          <strong>{reconciliationLabel === "三桶一致" ? `${topDriver.bucket} 结构${structureDirection}` : reconciliationHeadline}</strong>
        </header>
        <h2>
          余额{direction}
          {balanceChangePct === null ? "" : ` ${Math.abs(balanceChangePct).toFixed(2)}%`}，主要由 {topDriver.bucket} 驱动；
          {reconciliationHeadline}，{accountingBasisNarrativeLabel(topDriver.bucket)} 结构占比{structureDirection}。
        </h2>
        <p>
          TPL 贡献 {formatPct(tplDriver?.contributionPct)}，OCI 贡献 {formatPct(ociDriver?.contributionPct)}。
          这表示损益与估值波动暴露上升，并不等同于已实现损益结论。
        </p>
        <div className="balance-movement-decision-hero__chips" aria-label="会计分类变动贡献">
          {movementDrivers.map((driver) => (
            <span key={driver.bucket} data-bucket={driver.bucket.toLowerCase()}>
              {driver.bucket} <strong>{formatSignedYiNumber(driver.balanceChangeYi)} 亿</strong>
            </span>
          ))}
        </div>
      </article>
      <FreshnessStrip
        dates={dates}
        readStatus={readStatus}
        selectedDate={selectedDate}
        reconciliationLabel={reconciliationLabel}
        currencyBasis={currencyBasis}
      />
    </section>
  );
}

export function FigmaEmptyHero({
  dates,
  readStatus,
  selectedDate,
  reconciliationLabel,
  currencyBasis,
}: {
  dates: BalanceMovementDatesPayload;
  readStatus: BalanceMovementReadState;
  selectedDate: string;
  reconciliationLabel: string;
  currencyBasis: string;
}) {
  return (
    <section
      className="balance-movement-decision-layout"
      data-testid="balance-movement-analysis-decision-hero"
    >
      <article
        className="balance-movement-decision-hero balance-movement-decision-hero--empty"
        data-testid="balance-movement-analysis-conclusion"
      >
        <header>
          <span>决策信号</span>
          <strong>等待物化</strong>
        </header>
        <h2>当前没有可发布的余额变动读模型，首屏仅保留状态与证据说明。</h2>
        <p>先确认报告日是否已物化，再决定是否刷新或回溯上游控制账；在数据到位前，不展示推断性的业务结论。</p>
      </article>
      <FreshnessStrip
        dates={dates}
        readStatus={readStatus}
        selectedDate={selectedDate}
        reconciliationLabel={reconciliationLabel}
        currencyBasis={currencyBasis}
      />
    </section>
  );
}

export function FigmaLoadingHero({
  dates,
  readStatus,
  selectedDate,
  reconciliationLabel,
  currencyBasis,
}: {
  dates: BalanceMovementDatesPayload;
  readStatus: BalanceMovementReadState;
  selectedDate: string;
  reconciliationLabel: string;
  currencyBasis: string;
}) {
  return (
    <section
      className="balance-movement-decision-layout"
      data-testid="balance-movement-analysis-loading-hero"
      aria-busy="true"
      aria-live="polite"
    >
      <article
        className="balance-movement-decision-hero balance-movement-decision-hero--loading"
        role="status"
      >
        <header>
          <span>决策信号</span>
          <strong>读取中</strong>
        </header>
        <h2>正在读取余额变动分析</h2>
        <p>
          正在装载 {selectedDate || "最新报告日"} 的余额、会计分类与对账证据；完成前不展示空数据结论。
        </p>
        <div className="balance-movement-decision-hero__chips" aria-hidden="true">
          <span>余额口径</span>
          <span>会计分类</span>
          <span>对账证据</span>
        </div>
      </article>
      <FreshnessStrip
        dates={dates}
        readStatus={readStatus}
        selectedDate={selectedDate}
        reconciliationLabel={reconciliationLabel}
        currencyBasis={currencyBasis}
      />
    </section>
  );
}

export function FigmaKpiRibbon({
  summary,
  topDriver,
  hasBalanceChangeTotal,
  reconciliationLabel,
  balanceChangePct,
}: {
  summary: BalanceMovementPayload["summary"];
  topDriver: BalanceMovementDriver;
  hasBalanceChangeTotal: boolean;
  reconciliationLabel: string;
  balanceChangePct: number | null;
}) {
  const balanceChangePctAvailable =
    balanceChangePct !== null && Number.isFinite(balanceChangePct);
  const topDriverContributionValue = finiteMetric(topDriver.contributionPct);
  // 方向色按数值符号取向：负值不得渲染 up 绿（余额下降不是利好）。
  const balanceChangeValue = finiteMetric(summary.balance_change_total);
  const changeTone =
    balanceChangeValue === null || balanceChangeValue === 0
      ? undefined
      : balanceChangeValue > 0
        ? "green"
        : "red";
  const reconciliationState =
    reconciliationLabel === "三桶一致"
      ? "matched"
      : reconciliationLabel === "待数据"
        ? "unavailable"
        : "review";
  const reconciliationTone =
    reconciliationState === "matched" ? "green" : reconciliationState === "review" ? "amber" : undefined;
  return (
    <section className="balance-movement-kpi-ribbon" data-testid="balance-movement-analysis-summary">
      <article>
        <span>期末余额</span>
        <strong>{formatYiFixed(summary.current_balance_total)} 亿</strong>
        <small>上期 {formatYiFixed(summary.previous_balance_total)} 亿</small>
      </article>
      <article data-accent={changeTone}>
        <span>本月净增</span>
        <strong>{hasBalanceChangeTotal ? formatSignedYi(summary.balance_change_total) : EM_DASH}</strong>
        <small>环比 {balanceChangePct === null ? EM_DASH : `${balanceChangePct > 0 ? "+" : ""}${balanceChangePct.toFixed(2)}%`}</small>
        <div
          className="balance-movement-kpi-ribbon__signal"
          data-direction="trailing"
          data-state={balanceChangePctAvailable ? "available" : "unavailable"}
          data-tone={changeTone}
          data-testid="balance-movement-kpi-signal"
          title="信号条长度为环比变动幅度绝对值（上限 100%）"
          role="img"
          aria-label={balanceChangePctAvailable ? "环比变动信号可用" : "环比变动信号数据不可用"}
        >
          {balanceChangePctAvailable ? (
            <progress max={100} value={Math.min(Math.abs(balanceChangePct), 100)} />
          ) : (
            <span>{EM_DASH} / 数据不可用</span>
          )}
        </div>
      </article>
      <article data-accent="amber">
        <span>最大驱动</span>
        <strong>{topDriver.bucket} · {formatPct(topDriver.contributionPct)}</strong>
        <small>本月 {formatSignedYiNumber(topDriver.balanceChangeYi)} 亿</small>
        <div
          className="balance-movement-kpi-ribbon__signal"
          data-state={topDriverContributionValue === null ? "unavailable" : "available"}
          data-tone="amber"
          data-testid="balance-movement-kpi-signal"
          title="信号条长度为最大驱动贡献占比（上限 100%）"
          role="img"
          aria-label={
            topDriverContributionValue === null
              ? "最大驱动贡献信号数据不可用"
              : `最大驱动贡献 ${formatPct(topDriverContributionValue)}`
          }
        >
          {topDriverContributionValue === null ? (
            <span>{EM_DASH} / 数据不可用</span>
          ) : (
            <progress max={100} value={Math.min(Math.abs(topDriverContributionValue), 100)} />
          )}
        </div>
      </article>
      <article data-accent={reconciliationTone}>
        <span>对账状态</span>
        <strong>{reconciliationLabel === "三桶一致" ? "3 / 3 匹配" : reconciliationLabel}</strong>
        <small>差异 {formatPlainNumber(summary.reconciliation_diff_total, 2)} 元</small>
        <div
          className="balance-movement-kpi-ribbon__signal balance-movement-kpi-ribbon__signal--reconciliation"
          data-state={reconciliationState}
          data-testid="balance-movement-kpi-signal"
          title="三格对应 AC / OCI / TPL 三桶对账状态：绿=全部一致，琥珀=存在待关注项"
          role="img"
          aria-label={
            reconciliationState === "matched"
              ? "三项对账全部匹配"
              : reconciliationState === "review"
                ? "对账存在不匹配项"
                : "对账状态数据不可用"
          }
        >
          {reconciliationState === "unavailable" ? (
            <span>{EM_DASH} / 数据不可用</span>
          ) : (
            <>
              <i />
              <i />
              <i />
            </>
          )}
        </div>
      </article>
    </section>
  );
}

export function FigmaDriversAndStructure({ drivers }: { drivers: BalanceMovementDriver[] }) {
  const maxChange = Math.max(...drivers.map((driver) => Math.abs(driver.balanceChangeYi)), 1);
  const contributionValues = drivers.map((driver) => finiteMetric(driver.contributionPct));
  const contributionsAvailable = contributionValues.every(
    (value) => value !== null && Number.isFinite(value),
  );
  const totalContribution = contributionsAvailable
    ? contributionValues.reduce<number>((total, value) => total + (value ?? 0), 0)
    : null;
  let contributionOffset = 0;
  const contributionSegments = contributionsAvailable
    ? drivers.map((driver, index) => {
        const share = Math.max(0, Math.min(contributionValues[index] as number, 100));
        const segment = { driver, share, offset: contributionOffset };
        contributionOffset += share;
        return segment;
      })
    : [];
  const structureDrivers = [...drivers].sort(
    (left, right) =>
      ["AC", "OCI", "TPL"].indexOf(left.bucket) - ["AC", "OCI", "TPL"].indexOf(right.bucket),
  );
  const structureValues = structureDrivers.map((driver) =>
    finiteMetric(driver.currentBalancePct),
  );
  const structureAvailable = structureValues.every(
    (value) => value !== null && Number.isFinite(value),
  );
  let structureOffset = 0;
  const structureSegments = structureAvailable
    ? structureDrivers.map((driver, index) => {
        const share = Math.max(0, Math.min(structureValues[index] as number, 100));
        const segment = { driver, share, offset: structureOffset };
        structureOffset += share;
        return segment;
      })
    : [];
  return (
    <section className="balance-movement-analysis-pair" data-testid="balance-movement-analysis-drivers-structure">
      <article className="balance-movement-compact-panel balance-movement-driver-panel">
        <header className="balance-movement-section-heading">
          <div>
            <h2>本月变动驱动</h2>
          </div>
          <p>单位：亿元 / 贡献率</p>
        </header>
        {/*
         * 2026-09-02 曾按结论 13 撤掉行内 progress、只留下方 SVG 贡献带；业主判定面板反而更空。
         * 恢复原样（行内条表达变动量级，贡献带表达构成比例），结论 13 的适用边界留待决议 D3。
         */}
        <div className="balance-movement-driver-list">
          {drivers.map((driver) => (
            <div key={driver.bucket} data-bucket={driver.bucket.toLowerCase()}>
              <span>{driver.bucket}</span>
              <progress max={maxChange} value={Math.abs(driver.balanceChangeYi)}>
                {Math.abs(driver.balanceChangeYi)}
              </progress>
              <strong>{formatSignedYiNumber(driver.balanceChangeYi)} 亿</strong>
              <small>{formatPct(driver.contributionPct)}</small>
            </div>
          ))}
        </div>
        <p className="balance-movement-compact-panel__note">
          三类桶合计贡献 {formatPct(totalContribution)}，最大单一驱动为 {drivers[0]?.bucket ?? EM_DASH}。
        </p>
        {contributionsAvailable ? (
          <svg
            className="balance-movement-driver-composition"
            data-testid="balance-movement-driver-composition-band"
            data-state="available"
            width="100%"
            height="28"
            role="img"
            aria-label={`变动贡献构成：${drivers
              .map((driver) => `${driver.bucket} ${formatPct(driver.contributionPct)}`)
              .join("，")}`}
          >
            <title>变动贡献构成</title>
            <rect className="balance-movement-band-track" x="0" y="0" width="100%" height="28" />
            {contributionSegments.map(({ driver, share, offset }) => (
              <g key={driver.bucket} data-bucket={driver.bucket.toLowerCase()}>
                <rect x={`${offset}%`} y="0" width={`${share}%`} height="28" />
                {share >= 6 ? (
                  <text x={`${offset + share / 2}%`} y="18" textAnchor="middle">
                    {driver.bucket}{share >= 14 ? ` · ${formatPct(driver.contributionPct)}` : ""}
                  </text>
                ) : null}
              </g>
            ))}
          </svg>
        ) : (
          <div
            className="balance-movement-driver-composition balance-movement-band-unavailable"
            data-testid="balance-movement-driver-composition-band"
            data-state="unavailable"
            role="img"
            aria-label="变动贡献构成：数据不可用"
          >
            <span>{EM_DASH} / 数据不可用</span>
          </div>
        )}
      </article>
      <article className="balance-movement-compact-panel balance-movement-structure-panel">
        <header className="balance-movement-section-heading">
          <div>
            <h2>会计分类结构</h2>
          </div>
          <p>本期 / 较上期</p>
        </header>
        {structureAvailable ? (
          <svg
            className="balance-movement-structure-mix"
            data-testid="balance-movement-structure-mix-band"
            data-state="available"
            width="100%"
            height="34"
            role="img"
            aria-label={`会计分类结构：${structureDrivers
              .map((driver) => `${driver.bucket} ${formatPct(driver.currentBalancePct)}`)
              .join("，")}`}
          >
            <title>会计分类结构占比</title>
            <rect className="balance-movement-band-track" x="0" y="0" width="100%" height="34" />
            {structureSegments.map(({ driver, share, offset }) => (
              <g key={driver.bucket} data-bucket={driver.bucket.toLowerCase()}>
                <rect x={`${offset}%`} y="0" width={`${share}%`} height="34" />
                {share >= 12 ? (
                  <text x={`${offset + share / 2}%`} y="22" textAnchor="middle">
                    {driver.bucket} {formatPct(driver.currentBalancePct)}
                  </text>
                ) : null}
              </g>
            ))}
          </svg>
        ) : (
          <div
            className="balance-movement-structure-mix balance-movement-band-unavailable"
            data-testid="balance-movement-structure-mix-band"
            data-state="unavailable"
            role="img"
            aria-label="会计分类结构：数据不可用"
          >
            <span>{EM_DASH} / 数据不可用</span>
          </div>
        )}
        <div className="balance-movement-structure-list">
          {structureDrivers.map((driver) => (
            <div key={driver.bucket} data-bucket={driver.bucket.toLowerCase()}>
              <span>{driver.bucket}</span>
              <strong>{formatPct(driver.currentBalancePct)}</strong>
              <small>{formatSignedPointNullable(driver.shareDelta)}</small>
            </div>
          ))}
        </div>
        <p className="balance-movement-compact-panel__note">结构信号不等同于单只资产已完成会计分类迁移。</p>
      </article>
    </section>
  );
}
