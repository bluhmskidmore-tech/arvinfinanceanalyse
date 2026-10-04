import type { AccountingBasisStackedSharePoint } from "../../../components/charts/AccountingBasisStackedShareChart";
import { SectionHead } from "../../../components/layout";
import { EM_DASH } from "../../../utils/format";
import {
  formatSignedPointNullable,
  nullableDelta,
  type BalanceStructureEvolutionModel,
} from "../lib/balanceMovementShareModel";

function formatShareEvolutionPct(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return `${value.toFixed(2)}%`;
}

function formatShareEvolutionYi(value: number | undefined) {
  if (value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return `${value.toFixed(2)} 亿`;
}

/** 用于同比：返回 report_month 的上年同月 `YYYY-MM` */
function priorYearSameMonth(reportMonth: string): string {
  const [y, m] = reportMonth.split("-").map(Number);
  if (!Number.isFinite(y) || !Number.isFinite(m)) {
    return "";
  }
  return `${y - 1}-${String(m).padStart(2, "0")}`;
}

function formatSignedYiDelta(
  current: number | undefined,
  base: number | undefined,
): string {
  if (
    current === undefined ||
    base === undefined ||
    !Number.isFinite(current) ||
    !Number.isFinite(base)
  ) {
    return EM_DASH;
  }
  const d = current - base;
  const sign = d > 0 ? "+" : "";
  return `${sign}${d.toFixed(2)} 亿`;
}

export function SixMonthStructurePanel({
  chartRows,
  balanceStructureInsight,
}: {
  chartRows: AccountingBasisStackedSharePoint[];
  balanceStructureInsight: string | null;
}) {
  const matrixRows = [
    { label: "AC", value: (point: AccountingBasisStackedSharePoint) => point.acValueYi },
    { label: "OCI", value: (point: AccountingBasisStackedSharePoint) => point.ociValueYi },
    { label: "TPL", value: (point: AccountingBasisStackedSharePoint) => point.tplValueYi },
    { label: "AC / OCI / TPL 合计", value: (point: AccountingBasisStackedSharePoint) => point.totalValueYi },
  ];

  return (
    <section
      className="balance-movement-six-month balance-movement-figma-panel"
      data-testid="balance-movement-analysis-six-month-structure"
    >
      <SectionHead
        title="六个月会计分类矩阵与结构演变"
        numbered={{ counter: "bm-section", increment: true }}
        contentGap="flush"
      />

      <div className="balance-movement-six-month__matrix">
        <table aria-label="六个月会计分类余额矩阵">
          <thead>
            <tr>
              <th scope="col">分类</th>
              {chartRows.map((point) => (
                <th key={point.monthLabel} scope="col">{point.monthLabel}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrixRows.map((row) => (
              <tr key={row.label}>
                <th scope="row">{row.label}</th>
                {chartRows.map((point) => (
                  <td key={point.monthLabel}>{formatShareEvolutionYi(row.value(point))}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div
        className="balance-movement-six-month__timeline balance-movement-structure-chart"
        data-testid="balance-movement-analysis-structure-chart"
      >
        <div>
          <h3>金融投资账户结构演变 · 余额口径</h3>
          {chartRows.length > 0 ? (
            <div className="balance-movement-six-month__bars" aria-label="AC OCI TPL 六个月结构演变">
              {chartRows.map((point) => {
                const segments = [
                  { key: "AC" as const, value: point.AC },
                  { key: "OCI" as const, value: point.OCI },
                  { key: "TPL" as const, value: point.TPL },
                ];
                return (
                  <article key={point.monthLabel} className="balance-movement-six-month__bar">
                    <div>
                      {segments.map((segment) => (
                        <span
                          key={segment.key}
                          className="balance-movement-six-month__segment"
                          data-bucket={segment.key}
                          style={{ height: `${Math.max(0, Math.min(segment.value, 100))}%` }}
                          title={`${segment.key} ${formatShareEvolutionPct(segment.value)}`}
                        >
                          {segment.value >= 12 ? formatShareEvolutionPct(segment.value) : null}
                        </span>
                      ))}
                    </div>
                    <span>{point.monthLabel}</span>
                  </article>
                );
              })}
            </div>
          ) : (
            <p className="balance-movement-share-evolution-table__note">
              占比数据缺失，结构图暂不可比
            </p>
          )}
        </div>
        <aside
          className="balance-movement-six-month__insight balance-movement-structure-chart__insight"
          data-testid="balance-movement-analysis-structure-insight"
        >
          <h3>本期结构结论</h3>
          <p>{balanceStructureInsight ?? "结构占比数据不足，暂不生成比较结论。"}</p>
          <small>占比使用后端正式 current_balance_pct；页面不补算缺失值。</small>
        </aside>
      </div>
    </section>
  );
}

export function StructureShareDetailTable({
  structureShareTableRows,
  shareRowByReportMonth,
}: Pick<BalanceStructureEvolutionModel, "structureShareTableRows" | "shareRowByReportMonth">) {
  if (structureShareTableRows.length === 0) {
    return null;
  }

  return (
    <div className="balance-movement-structure-share-detail">
      <p
        className="balance-movement-share-evolution-table__title"
        data-testid="balance-movement-analysis-structure-share-table-title"
      >
        结构占比明细 · 完整口径（与六个月结构图一致）
      </p>
      <p className="balance-movement-share-evolution-table__note">
        环比为相对上一行月份的变动；同比为相对上年同月；较首月用于识别六个月结构迁移。
      </p>
      <div
        className="balance-movement-share-evolution-table-scroll"
        data-testid="balance-movement-analysis-structure-share-table"
      >
        <table className="balance-movement-share-evolution-table">
          <thead>
            <tr>
              <th scope="col">月份</th>
              <th scope="col">AC(%)</th>
              <th scope="col">OCI(%)</th>
              <th scope="col">TPL(%)</th>
              <th scope="col">合计(亿)</th>
              <th scope="col">AC(亿)</th>
              <th scope="col">OCI(亿)</th>
              <th scope="col">TPL(亿)</th>
              <th scope="col">环比·AC</th>
              <th scope="col">环比·OCI</th>
              <th scope="col">环比·TPL</th>
              <th scope="col">环比·合计</th>
              <th scope="col">同比·AC</th>
              <th scope="col">同比·OCI</th>
              <th scope="col">同比·TPL</th>
              <th scope="col">同比·合计</th>
              {structureShareTableRows.length > 1 ? (
                <>
                  <th scope="col">较首月·AC</th>
                  <th scope="col">较首月·OCI</th>
                  <th scope="col">较首月·TPL</th>
                </>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {structureShareTableRows.map((item, index) => {
              const { point, reportMonth } = item;
              const first = structureShareTableRows[0];
              const prev = index > 0 ? structureShareTableRows[index - 1] : null;
              const yoyKey = priorYearSameMonth(reportMonth);
              const yoy = yoyKey ? shareRowByReportMonth.get(yoyKey) : undefined;
              const showFirstDelta = structureShareTableRows.length > 1 && first !== undefined;
              return (
                <tr key={point.monthLabel}>
                  <th scope="row">{point.monthLabel}</th>
                  <td>{formatShareEvolutionPct(point.AC)}</td>
                  <td>{formatShareEvolutionPct(point.OCI)}</td>
                  <td>{formatShareEvolutionPct(point.TPL)}</td>
                  <td>{formatShareEvolutionYi(point.totalValueYi)}</td>
                  <td>{formatShareEvolutionYi(point.acValueYi)}</td>
                  <td>{formatShareEvolutionYi(point.ociValueYi)}</td>
                  <td>{formatShareEvolutionYi(point.tplValueYi)}</td>
                  <td>{prev ? formatSignedPointNullable(nullableDelta(point.AC, prev.point.AC)) : EM_DASH}</td>
                  <td>{prev ? formatSignedPointNullable(nullableDelta(point.OCI, prev.point.OCI)) : EM_DASH}</td>
                  <td>{prev ? formatSignedPointNullable(nullableDelta(point.TPL, prev.point.TPL)) : EM_DASH}</td>
                  <td>{formatSignedYiDelta(point.totalValueYi, prev?.point.totalValueYi)}</td>
                  <td>{yoy ? formatSignedPointNullable(nullableDelta(point.AC, yoy.point.AC)) : EM_DASH}</td>
                  <td>{yoy ? formatSignedPointNullable(nullableDelta(point.OCI, yoy.point.OCI)) : EM_DASH}</td>
                  <td>{yoy ? formatSignedPointNullable(nullableDelta(point.TPL, yoy.point.TPL)) : EM_DASH}</td>
                  <td>{formatSignedYiDelta(point.totalValueYi, yoy?.point.totalValueYi)}</td>
                  {showFirstDelta ? (
                    <>
                      <td>{formatSignedPointNullable(nullableDelta(point.AC, first.point.AC))}</td>
                      <td>{formatSignedPointNullable(nullableDelta(point.OCI, first.point.OCI))}</td>
                      <td>{formatSignedPointNullable(nullableDelta(point.TPL, first.point.TPL))}</td>
                    </>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
