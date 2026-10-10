import type { BalanceZqtzConcentrationAnalysis, BalanceZqtzMaturityStructure } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { useState } from "react";
import { MaturityDistributionChart } from "./MaturityDistributionChart";
import { MaturityHoldingDetails } from "./MaturityHoldingDetails";
import {
  finiteMetric,
  formatPct,
  formatYiFixed,
  formatPlainNumber,
  drilldownStatusLabel,
  formatYiCell,
  formatSignedYiCell,
  moveDeltaToneClass,
  concentrationDimensionLabel,
} from "../lib/balanceMovementPresentation";

export type CompactMaturityGroup = {
  key: string;
  label: string;
  currentAmount: number | null;
  deltaAmount: number | null;
  sharePct: number | null;
};

export function FigmaMaturityAndConcentration({
  maturityGroups,
  issuerDimension,
  maturityCoverage,
  unknownMaturityAmount,
}: {
  maturityGroups: CompactMaturityGroup[];
  issuerDimension: BalanceZqtzConcentrationAnalysis["dimensions"][number] | null;
  maturityCoverage: string | number | null | undefined;
  unknownMaturityAmount: string | number | null | undefined;
}) {
  const largestMaturity = maturityGroups.reduce<CompactMaturityGroup | null>(
    (largest, group) => {
      if (group.currentAmount === null) return largest;
      if (largest?.currentAmount === null || largest === null) return group;
      return group.currentAmount > largest.currentAmount ? group : largest;
    },
    null,
  );
  const maturityShareValues = maturityGroups.map((group) => finiteMetric(group.sharePct));
  const maturitySharesAvailable = maturityShareValues.every(
    (value) => value !== null && Number.isFinite(value),
  );
  let maturityOffset = 0;
  const maturitySegments = maturitySharesAvailable
    ? maturityGroups.map((group, index) => {
        const share = Math.max(0, Math.min(maturityShareValues[index] as number, 100));
        const segment = { group, share, offset: maturityOffset };
        maturityOffset += share;
        return segment;
      })
    : [];
  const knownShareValue = finiteMetric(maturityCoverage);
  const knownShare =
    knownShareValue === null ? null : Math.max(0, Math.min(knownShareValue, 100));
  const unmappedShare = knownShare === null ? null : Math.max(0, 100 - knownShare);
  const top5ShareValue = finiteMetric(issuerDimension?.top5_share_pct);
  const top5GaugeShare =
    top5ShareValue === null ? null : Math.max(0, Math.min(top5ShareValue, 100));
  return (
    <section className="balance-movement-analysis-pair" data-testid="balance-movement-analysis-maturity-concentration">
      <article className="balance-movement-compact-panel balance-movement-maturity-compact">
        <header className="balance-movement-section-heading">
          <div>
            <h2>期限结构</h2>
          </div>
          <strong className="balance-movement-section-heading__badge">覆盖率 {formatPct(maturityCoverage)}</strong>
        </header>
        {maturitySharesAvailable ? (
          <svg
            className="balance-movement-maturity-spectrum"
            data-testid="balance-movement-maturity-spectrum"
            data-state="available"
            width="100%"
            height="26"
            role="img"
            aria-label={`期限分布：${maturityGroups
              .map((group) => `${group.label} ${formatPct(group.sharePct)}`)
              .join("，")}`}
          >
            <title>期限分布</title>
            <rect className="balance-movement-band-track" x="0" y="0" width="100%" height="26" />
            {maturitySegments.map(({ group, share, offset }) => (
              <g key={group.key} data-maturity={group.key}>
                <rect x={`${offset}%`} y="0" width={`${share}%`} height="26" />
              </g>
            ))}
          </svg>
        ) : (
          <div
            className="balance-movement-maturity-spectrum balance-movement-band-unavailable"
            data-testid="balance-movement-maturity-spectrum"
            data-state="unavailable"
            role="img"
            aria-label="期限分布：数据不可用"
          >
            <span>{EM_DASH} / 数据不可用</span>
          </div>
        )}
        <div className="balance-movement-maturity-compact__grid">
          {maturityGroups.map((group) => (
            <div
              key={group.key}
              data-largest={group.key === largestMaturity?.key ? "true" : undefined}
              data-maturity={group.key}
            >
              <span>{group.label}</span>
              <strong>{formatPct(group.sharePct)}</strong>
              <small>{formatYiFixed(group.currentAmount)} 亿</small>
            </div>
          ))}
        </div>
        {knownShare !== null && unmappedShare !== null ? (
          <svg
            className="balance-movement-maturity-coverage"
            data-testid="balance-movement-maturity-coverage-band"
            data-state="available"
            width="100%"
            height="34"
            role="img"
            aria-label={`已注明到期日 ${formatPct(knownShare)}，未列有效到期日 ${formatPct(unmappedShare)}`}
          >
            <title>已注明到期日与未列有效到期日期限构成</title>
            <rect className="balance-movement-band-track" x="0" y="0" width="100%" height="34" />
            <g data-coverage="known">
              <rect x="0" y="0" width={`${knownShare}%`} height="34" />
              {knownShare >= 18 ? (
                <text x={`${knownShare / 2}%`} y="22" textAnchor="middle">
                  已注明到期日 · {formatPct(maturityCoverage)}
                </text>
              ) : null}
            </g>
            <g data-coverage="unmapped">
              <rect x={`${knownShare}%`} y="0" width={`${unmappedShare}%`} height="34" />
              {unmappedShare >= 9 ? (
                <text x={`${knownShare + unmappedShare / 2}%`} y="22" textAnchor="middle">
                  {formatPct(unmappedShare)}
                </text>
              ) : null}
            </g>
          </svg>
        ) : (
          <div
            className="balance-movement-maturity-coverage balance-movement-band-unavailable"
            data-testid="balance-movement-maturity-coverage-band"
            data-state="unavailable"
            role="img"
            aria-label="已注明到期日 / 未列有效到期日：数据不可用"
          >
            <span>{EM_DASH} / 数据不可用</span>
          </div>
        )}
        <p className="balance-movement-compact-panel__note">
          未列有效到期日金额（含基金） {formatYiFixed(unknownMaturityAmount)} 亿，已单列，不并入其他期限桶。
        </p>
      </article>
      <article className="balance-movement-compact-panel balance-movement-concentration-compact">
        <header className="balance-movement-section-heading">
          <div>
            <h2>主体集中度</h2>
          </div>
          <strong className="balance-movement-section-heading__badge balance-movement-section-heading__badge--blue">主体覆盖 {formatPct(issuerDimension?.coverage_pct)}</strong>
        </header>
        <div className="balance-movement-concentration-compact__metrics">
          <div className="balance-movement-concentration-compact__hhi">
            <span>HHI</span>
            <strong>{formatPlainNumber(issuerDimension?.hhi, 2)}</strong>
          </div>
          <div
            className="balance-movement-concentration-compact__gauge"
            data-testid="balance-movement-top5-gauge"
            data-state={top5GaugeShare === null ? "unavailable" : "available"}
          >
            <svg
              width="112"
              height="112"
              viewBox="0 0 112 112"
              role="img"
              aria-label={
                top5GaugeShare === null
                  ? "Top5 占比数据不可用"
                  : `Top5 占比 ${formatPct(issuerDimension?.top5_share_pct)}`
              }
            >
              <title>Top5 占比</title>
              <circle className="balance-movement-concentration-compact__gauge-track" cx="56" cy="56" r="42" />
              {top5GaugeShare === null ? null : (
                <circle
                  className="balance-movement-concentration-compact__gauge-value"
                  cx="56"
                  cy="56"
                  r="42"
                  pathLength="100"
                  strokeDasharray={`${top5GaugeShare} ${Math.max(0, 100 - top5GaugeShare)}`}
                />
              )}
            </svg>
            <span>Top5 占比</span>
            <strong>{formatPct(issuerDimension?.top5_share_pct)}</strong>
            {top5GaugeShare === null ? <em>数据不可用</em> : null}
          </div>
        </div>
        <div
          className="balance-movement-concentration-compact__unknown"
          data-testid="balance-movement-concentration-unknown-strip"
        >
          <span title="unknown_total">未知金额</span>
          <strong>{formatYiFixed(issuerDimension?.unknown_total)} 亿</strong>
        </div>
        <p className="balance-movement-compact-panel__note">主体覆盖 {formatPct(issuerDimension?.coverage_pct)}；完整主体、评级与行业明细保留在下方。</p>
      </article>
    </section>
  );
}

export function ZqtzMaturityStructurePanel({
  structure,
}: {
  structure: BalanceZqtzMaturityStructure;
}) {
  const [selectedKey, setSelectedKey] = useState("overdue_or_matured");
  const selectedBucket = structure.buckets.find((bucket) => bucket.maturity_bucket === selectedKey);
  const selectBucket = (key: string) => setSelectedKey(key);
  const fundBucket = structure.buckets.find((bucket) => bucket.maturity_bucket === "fund_no_maturity");
  const isUnknownBucket = (bucket: BalanceZqtzMaturityStructure["buckets"][number]) =>
    bucket.maturity_bucket.toLowerCase().includes("unknown") || bucket.bucket_label === "未列有效到期日";
  const largestMappedBucket = [...structure.buckets]
    .filter((bucket) => !isUnknownBucket(bucket) && bucket.maturity_bucket !== "fund_no_maturity")
    .sort(
      (left, right) =>
        Math.abs(finiteMetric(right.current_amount) ?? 0) -
        Math.abs(finiteMetric(left.current_amount) ?? 0),
    )[0];
  const unknownBucket = structure.buckets.find(isUnknownBucket);

  return (
    <section
      id="balance-movement-analysis-coverage-anchor"
      className="balance-movement-figma-panel balance-movement-maturity-panel"
      data-testid="balance-movement-analysis-zqtz-maturity"
    >
      <div className="balance-movement-figma-panel__header balance-movement-sec-no">
        <div>
          <h2 title="zqtz_maturity_structure">期限 / 到期结构完整明细</h2>
        </div>
        <p>
          报告日 {structure.meta.report_date}
          {structure.meta.prior_report_date ? ` / 上期 ${structure.meta.prior_report_date}` : ""}
        </p>
      </div>

      <div className="balance-movement-maturity-kpis" aria-label="到期结构关键指标">
        <div>
          <span>有效到期日覆盖率</span>
          <strong className="balance-movement-tone--positive">{formatPct(structure.meta.coverage_pct)}</strong>
          <small>{structure.meta.status === "supported" ? "占全部投资余额" : drilldownStatusLabel(structure.meta.status)}</small>
        </div>
        <div>
          <span>到期日缺失</span>
          <strong className={(finiteMetric(unknownBucket?.current_amount) ?? 0) > 0 ? "balance-movement-tone--warning" : undefined}>{formatYiCell(unknownBucket?.current_amount)} 亿</strong>
          <small>{formatPct(unknownBucket?.share_pct)} · {unknownBucket?.item_count ?? 0} 笔</small>
        </div>
        <div>
          <span>基金未列到期日</span>
          <strong>{formatYiCell(fundBucket?.current_amount)} 亿</strong>
          <small>{fundBucket ? `${fundBucket.item_count} 笔，不据此认定数据异常` : "当前接口未单列"}</small>
        </div>
        <div>
          <span>最大期限桶</span>
          <strong className="balance-movement-tone--warning">{largestMappedBucket?.bucket_label ?? EM_DASH}</strong>
          <small>{formatPct(largestMappedBucket?.share_pct)} · {formatYiCell(largestMappedBucket?.current_amount)} 亿</small>
        </div>
        <div>
          <span>口径</span>
          <strong>{structure.meta.currency_basis === "CNX" ? "本外币折人民币" : structure.meta.currency_basis}</strong>
          <small>单位：亿元；折算基准日 {structure.meta.report_date}</small>
        </div>
      </div>

      <div className="balance-movement-maturity-ladder" data-testid="balance-movement-analysis-maturity-ladder">
        <div className="balance-movement-maturity-ladder__heading">
          <div>
            <strong>期限分布</strong>
            <span>
              {largestMappedBucket?.bucket_label ?? EM_DASH}为最大期限桶（{formatYiCell(largestMappedBucket?.current_amount)} 亿 · {formatPct(largestMappedBucket?.share_pct)}）
            </span>
          </div>
          <p>期末余额（亿元）；点击柱形或下表期限桶查看持仓</p>
        </div>
        {structure.meta.status === "no_data" ? <p>暂无期限结构数据</p> : (
          <MaturityDistributionChart structure={structure} onSelect={selectBucket} />
        )}
      </div>

      <p className="balance-movement-figma-callout">
        <span>口径</span>余额净变化包含自然期限迁移，不等于新增投资，也不代表风险改善。{structure.meta.caveat}
      </p>
      <div className="balance-movement-derived-table-wrap">
        <table className="balance-movement-figma-table">
          <thead>
            <tr>
              <th>期限桶</th>
              <th>期末</th>
              <th>上期</th>
              <th>余额净变化</th>
              <th>占比</th>
              <th>笔数</th>
            </tr>
          </thead>
          <tbody>
            {structure.buckets.map((bucket) => (
              <tr key={bucket.maturity_bucket} className={isUnknownBucket(bucket) && (finiteMetric(bucket.current_amount) ?? 0) > 0 ? "balance-movement-figma-table__row--unknown" : undefined}>
                <th scope="row"><button type="button" className="balance-movement-maturity-filter" aria-pressed={selectedKey === bucket.maturity_bucket} onClick={() => selectBucket(bucket.maturity_bucket)}>{bucket.bucket_label}</button></th>
                <td>{formatYiCell(bucket.current_amount)} 亿</td>
                <td>{formatYiCell(bucket.prior_amount)} 亿</td>
                <td className={finiteMetric(bucket.delta_amount) === null ? undefined : "balance-movement-top-moves-table__delta"}>{formatSignedYiCell(bucket.delta_amount)} 亿</td>
                <td>{formatPct(bucket.share_pct)}</td>
                <td>{bucket.item_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="balance-movement-maturity-footer">
        <span title="eligible_total">投资余额合计 {formatYiCell(structure.meta.eligible_total)} 亿</span>
        <span className="balance-movement-tone--positive" title="covered_total">已注明有效到期日 {formatYiCell(structure.meta.covered_total)} 亿</span>
        <span className="balance-movement-tone--warning" title="unknown_total">未列有效到期日 {formatYiCell(structure.meta.unknown_total)} 亿</span>
      </div>
      <MaturityHoldingDetails key={`${structure.meta.report_date}:${selectedKey}`} bucket={selectedBucket} reportDate={structure.meta.report_date} />
    </section>
  );
}

type ConcentrationDimension = BalanceZqtzConcentrationAnalysis["dimensions"][number];

type ConcentrationItem = ConcentrationDimension["items"][number];

function ConcentrationRow({
  item,
  compact = false,
}: {
  item: ConcentrationItem;
  compact?: boolean;
}) {
  const share = Math.abs(finiteMetric(item.share_pct) ?? 0);
  return (
    <div
      className={`balance-movement-concentration-row balance-movement-concentration-row--${item.item_kind}${compact ? " balance-movement-concentration-row--compact" : ""}`}
    >
      <span className="balance-movement-concentration-row__rank">
        {item.rank > 0 ? item.rank : item.item_kind === "unknown" ? EM_DASH : "–"}
      </span>
      <strong title={item.dimension_value}>{item.dimension_value}</strong>
      <progress max={100} value={share} aria-label={`${item.dimension_value} ${formatPct(item.share_pct)}`} />
      <span>{formatYiCell(item.current_amount)}</span>
      <em className={moveDeltaToneClass(finiteMetric(item.delta_amount))}>
        {formatSignedYiCell(item.delta_amount)}
      </em>
      <span>{formatPct(item.share_pct)}</span>
    </div>
  );
}

function ConcentrationDistribution({
  dimension,
  variant,
  sharedCaveat,
}: {
  dimension: ConcentrationDimension;
  variant: "issuer" | "rating" | "industry";
  sharedCaveat?: string | null;
}) {
  const isIssuer = variant === "issuer";
  return (
    <article className={`balance-movement-concentration-card balance-movement-concentration-card--${variant}`}>
      <div className="balance-movement-concentration-card__header">
        <div>
          <h3>{concentrationDimensionLabel(dimension.dimension)}</h3>
          {isIssuer ? <p>Top 10 以本期金额排序；Other 与 Unknown 独立保留。</p> : null}
        </div>
        <strong>{drilldownStatusLabel(dimension.status)} · {isIssuer ? `覆盖 ${formatPct(dimension.coverage_pct)}` : variant === "rating" ? `${dimension.items.length} 档` : `Top ${dimension.items.filter((item) => item.rank > 0).length}`}</strong>
      </div>
      {isIssuer ? (
        <div className="balance-movement-concentration-card__metrics">
          <span>HHI <strong>{formatPlainNumber(dimension.hhi)}</strong></span>
          <span>Top5 <strong>{formatPct(dimension.top5_share_pct)}</strong></span>
          <span>Other <strong>{formatPct(dimension.items.find((item) => item.item_kind === "other")?.share_pct)}</strong></span>
        </div>
      ) : (
        <p className="balance-movement-concentration-card__meta">
          覆盖 {formatPct(dimension.coverage_pct)} / HHI {formatPlainNumber(dimension.hhi)} / Top5 {formatPct(dimension.top5_share_pct)}
        </p>
      )}
      {dimension.items.length > 0 ? (
        <div className="balance-movement-concentration-rows">
          {dimension.items.map((item) => (
            <ConcentrationRow
              key={`${dimension.dimension}-${item.item_kind}-${item.rank}-${item.dimension_value}`}
              item={item}
              compact={!isIssuer}
            />
          ))}
        </div>
      ) : (
        <div className="balance-movement-concentration-empty">当前维度无可展示排名</div>
      )}
      {dimension.caveat && dimension.caveat !== sharedCaveat ? (
        <p className="balance-movement-concentration-card__caveat">{dimension.caveat}</p>
      ) : null}
    </article>
  );
}

export function ZqtzConcentrationAnalysisPanel({
  analysis,
}: {
  analysis: BalanceZqtzConcentrationAnalysis;
}) {
  const issuer = analysis.dimensions.find((dimension) => dimension.dimension === "issuer_name");
  const rating = analysis.dimensions.find((dimension) => dimension.dimension === "rating");
  const industry = analysis.dimensions.find((dimension) => dimension.dimension === "industry_name");
  const coverageText = analysis.meta.coverage_pct === null || analysis.meta.coverage_pct === undefined
    ? "各维度见分区"
    : formatPct(analysis.meta.coverage_pct);
  // 三个维度返回同一句口径提示时只在区头保留一次；任一差异则各卡原文保留（fail-closed）。
  const dimensionCaveats = analysis.dimensions
    .map((dimension) => dimension.caveat)
    .filter((caveat): caveat is string => Boolean(caveat && caveat.trim()));
  const sharedCaveat =
    dimensionCaveats.length === analysis.dimensions.length &&
    dimensionCaveats.length > 1 &&
    dimensionCaveats.every((caveat) => caveat === dimensionCaveats[0])
      ? dimensionCaveats[0]
      : null;

  return (
    <section
      className="balance-movement-figma-panel balance-movement-concentration-panel"
      data-testid="balance-movement-analysis-zqtz-concentration"
    >
      <div className="balance-movement-figma-panel__header balance-movement-sec-no">
        <div>
          <h2 title="zqtz_concentration_analysis">主体 / 评级 / 行业集中度完整视图</h2>
        </div>
        <p>报告日 {analysis.meta.report_date} / Top 10 / Other 与 Unknown 分列</p>
      </div>
      <div className="balance-movement-concentration-signal" aria-label="集中度关键指标">
        <div><span>最低维度覆盖</span><strong className="balance-movement-tone--warning">{coverageText}</strong></div>
        <div><span>期末合计</span><strong>{formatYiCell(analysis.meta.eligible_total)} 亿</strong></div>
        <div><span>未知维度金额</span><strong className="balance-movement-tone--warning">{formatYiCell(analysis.meta.unknown_total)} 亿</strong></div>
        <div><span>数据日期</span><strong>{analysis.meta.report_date}</strong></div>
      </div>
      {sharedCaveat ? (
        <p className="balance-movement-concentration-shared-caveat">各维度共同口径提示：{sharedCaveat}</p>
      ) : null}
      <div className="balance-movement-concentration-layout">
        {issuer ? <ConcentrationDistribution dimension={issuer} variant="issuer" sharedCaveat={sharedCaveat} /> : null}
        <div className="balance-movement-concentration-layout__secondary">
          {rating ? <ConcentrationDistribution dimension={rating} variant="rating" sharedCaveat={sharedCaveat} /> : null}
          {industry ? <ConcentrationDistribution dimension={industry} variant="industry" sharedCaveat={sharedCaveat} /> : null}
        </div>
      </div>
      <p className="balance-movement-concentration-governance">
        <span>口径</span>{analysis.meta.caveat} 接口返回 HHI 数值；页面不自行定义风险等级，未知维度必须显式保留。
      </p>
    </section>
  );
}
