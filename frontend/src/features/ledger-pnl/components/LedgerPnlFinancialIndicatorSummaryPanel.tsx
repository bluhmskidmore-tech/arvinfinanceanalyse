import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type {
  LedgerPnlIndicatorSummaryPayload,
  LedgerPnlIndicatorSummaryPeriod,
  LedgerPnlIndicatorSummaryRow,
  LedgerPnlIndicatorSummarySection,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import "./LedgerPnlFinancialIndicatorSummaryPanel.css";

type Props = {
  reportMonth: string;
  currency: "CNX" | "CNY";
  /** 视口门控：false 时不发起查询（区块尚未进入视口）。默认 true。 */
  enabled?: boolean;
};

const MONEY_DISPLAY_FORMAT = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const GAP_YUAN_FORMAT = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * 在字符串域先完成 2 位 half-away-from-zero 舍入，再交给现有渲染。
 * `Number("1.005")` 的最近 double 略小于 1.005，直接 toFixed(2) 会把恰好的
 * 十进制半分误舍为 "1.00"；与同页 comparison 模型 `fixedDecimal` 的进位规则
 * 一致（后续统一收敛到共享实现时可替换本函数）。
 * 非规范十进制形态（科学计数法等）返回 null，调用方回退原 Number 路径。
 */
function roundDecimalString(raw: string, digits: number): string | null {
  const match = /^([+-]?)(\d+)(?:\.(\d*))?$/.exec(raw.trim());
  if (!match) return null;
  const [, sign, intPart, fracPart = ""] = match;
  const kept = fracPart.slice(0, digits).padEnd(digits, "0");
  let scaled = BigInt(intPart + kept);
  if (fracPart.charAt(digits) >= "5") scaled += 1n;
  const scaledStr = scaled.toString().padStart(digits + 1, "0");
  const integer = digits ? scaledStr.slice(0, -digits) : scaledStr;
  const fraction = digits ? `.${scaledStr.slice(-digits)}` : "";
  return `${sign === "-" ? "-" : ""}${integer}${fraction}`;
}

function toDisplayNumber(raw: string): number {
  const rounded = roundDecimalString(raw, 2);
  return Number(rounded ?? raw);
}

function displayCellValue(
  raw: string | null,
  valueKind: LedgerPnlIndicatorSummaryRow["value_kind"],
  signed = false,
): string {
  if (raw === null || raw.trim() === "") return EM_DASH;
  const numeric = toDisplayNumber(raw);
  if (!Number.isFinite(numeric)) return EM_DASH;
  const sign = signed && numeric > 0 ? "+" : "";
  if (valueKind === "percent") {
    return `${sign}${numeric.toFixed(2)}%`;
  }
  return `${sign}${MONEY_DISPLAY_FORMAT.format(numeric)}`;
}

function displayDeltaPct(raw: string | null): string {
  if (raw === null || raw.trim() === "") return EM_DASH;
  const numeric = toDisplayNumber(raw);
  if (!Number.isFinite(numeric)) return EM_DASH;
  return `${numeric > 0 ? "+" : ""}${numeric.toFixed(2)}%`;
}

/** `quality_checks[].gap_yuan` 是元；表体金额单位是亿元，两者不可混用，展示时显式标注元。 */
function formatGapYuan(raw: string | null): string {
  if (raw === null || raw.trim() === "") return EM_DASH;
  const numeric = toDisplayNumber(raw);
  if (!Number.isFinite(numeric)) return EM_DASH;
  return `${GAP_YUAN_FORMAT.format(numeric)} 元`;
}

function compareHeaderLabel(basis: "flow" | "point"): string {
  return basis === "flow" ? "上年同期" : "上年末";
}

function periodGroupLabel(
  period: LedgerPnlIndicatorSummaryPeriod,
  basis: "flow" | "point",
): string {
  return basis === "flow" ? period.flow_label : period.point_label;
}

function periodCompareLabel(
  period: LedgerPnlIndicatorSummaryPeriod,
  basis: "flow" | "point",
): string {
  return basis === "flow" ? period.flow_compare_label : period.point_compare_label;
}

function periodCompareAvailable(
  period: LedgerPnlIndicatorSummaryPeriod,
  basis: "flow" | "point",
): boolean {
  return basis === "flow" ? period.flow_compare_available : period.point_compare_available;
}

type RowCounts = { computed: number; unavailable: number; total: number };

function countRowAvailability(rows: LedgerPnlIndicatorSummaryRow[]): RowCounts {
  const computed = rows.filter((row) => row.availability === "ledger_computed").length;
  return { computed, unavailable: rows.length - computed, total: rows.length };
}

function CoverageDot({ tone }: { tone: "ok" | "muted" | "warn" }) {
  return <span className="ledger-indicator-summary__dot" data-tone={tone} aria-hidden="true" />;
}

function CoverageCounts({ counts }: { counts: RowCounts }) {
  return (
    <span className="ledger-indicator-summary__counts">
      <CoverageDot tone="ok" />
      可计算 {counts.computed} / 无系统来源 {counts.unavailable} / 共 {counts.total} 行
    </span>
  );
}

/**
 * 行级"安静标记"：无系统来源原因、口径差异说明、科目取数公式均只在
 * hover/focus 时通过 title 展开，不在正文逐行铺陈整句文案
 * （DESIGN.md §6 状态信息去重 / 溯源标识分层）。
 */
function RowInfoMarker({
  label,
  detail,
  tone,
}: {
  label: string;
  detail: string;
  tone: "unavailable" | "caliber" | "evidence";
}) {
  return (
    <button
      type="button"
      className={`ledger-indicator-summary__row-flag ledger-indicator-summary__row-flag--${tone}`}
      title={detail}
      aria-label={`${label}：${detail}`}
    >
      {label}
    </button>
  );
}

function SummaryHeaderRows({
  periods,
  basis,
  segmentLabel,
}: {
  periods: LedgerPnlIndicatorSummaryPeriod[];
  basis: "flow" | "point";
  segmentLabel: string;
}) {
  return (
    <>
      <tr className="ledger-indicator-summary__group-row">
        <th scope="col" className="ledger-indicator-summary__name-head">
          {segmentLabel}
        </th>
        {periods.map((period) => (
          <th
            key={`${period.period_id}-group`}
            scope="colgroup"
            colSpan={4}
            className="ledger-indicator-summary__period-head"
          >
            {periodGroupLabel(period, basis)}
          </th>
        ))}
      </tr>
      <tr className="ledger-indicator-summary__column-row">
        <th scope="col" aria-label="指标名称" />
        {periods.map((period) => (
          <SummaryColumnHeads
            key={`${period.period_id}-cols`}
            basis={basis}
            period={period}
          />
        ))}
      </tr>
    </>
  );
}

function SummaryColumnHeads({
  basis,
  period,
}: {
  basis: "flow" | "point";
  period: LedgerPnlIndicatorSummaryPeriod;
}) {
  const compareAvailable = periodCompareAvailable(period, basis);
  const compareLabel = periodCompareLabel(period, basis);
  return (
    <>
      <th scope="col">本期</th>
      <th scope="col" title={compareLabel}>
        {compareHeaderLabel(basis)}
        {compareAvailable ? null : (
          <RowInfoMarker
            label="缺源"
            detail={`${compareLabel} 总账来源缺失，本列对比值保持空值`}
            tone="unavailable"
          />
        )}
      </th>
      <th scope="col">增减额</th>
      <th scope="col">增减幅</th>
    </>
  );
}

function SummaryRow({
  row,
  periods,
}: {
  row: LedgerPnlIndicatorSummaryRow;
  periods: LedgerPnlIndicatorSummaryPeriod[];
}) {
  const unavailable = row.availability === "no_system_source";
  const cellsByPeriod = new Map(row.values.map((cell) => [cell.period_id, cell]));
  return (
    <tr
      className="ledger-indicator-summary__row"
      data-availability={row.availability}
      data-testid={`ledger-indicator-summary-row-${row.row_id}`}
    >
      <th scope="row" data-indent={row.indent}>
        <span className="ledger-indicator-summary__row-name">
          {row.name}
          {unavailable ? (
            <RowInfoMarker
              label="无系统来源"
              detail={row.unavailable_reason ?? "无系统来源"}
              tone="unavailable"
            />
          ) : null}
          {row.caliber_note ? (
            <RowInfoMarker label="口径差异" detail={row.caliber_note} tone="caliber" />
          ) : null}
          {row.account_evidence ? (
            <RowInfoMarker label="科目取数" detail={row.account_evidence} tone="evidence" />
          ) : null}
        </span>
      </th>
      {periods.map((period) => {
        const cell = cellsByPeriod.get(period.period_id);
        return (
          <SummaryValueCells
            key={`${row.row_id}-${period.period_id}`}
            row={row}
            current={cell?.current ?? null}
            compare={cell?.compare ?? null}
            delta={cell?.delta ?? null}
            deltaPct={cell?.delta_pct ?? null}
          />
        );
      })}
    </tr>
  );
}

function SummaryValueCells({
  row,
  current,
  compare,
  delta,
  deltaPct,
}: {
  row: LedgerPnlIndicatorSummaryRow;
  current: string | null;
  compare: string | null;
  delta: string | null;
  deltaPct: string | null;
}) {
  return (
    <>
      <td className="ledger-indicator-summary__num">
        {displayCellValue(current, row.value_kind)}
      </td>
      <td className="ledger-indicator-summary__num">
        {displayCellValue(compare, row.value_kind)}
      </td>
      <td className="ledger-indicator-summary__num">
        {displayCellValue(delta, row.value_kind, true)}
      </td>
      <td className="ledger-indicator-summary__num">{displayDeltaPct(deltaPct)}</td>
    </>
  );
}

function splitRowsByBasis(section: LedgerPnlIndicatorSummarySection) {
  const segments: Array<{
    basis: "flow" | "point";
    rows: LedgerPnlIndicatorSummaryRow[];
  }> = [];
  for (const row of section.rows) {
    const lastSegment = segments[segments.length - 1];
    if (lastSegment && lastSegment.basis === row.basis) {
      lastSegment.rows.push(row);
    } else {
      segments.push({ basis: row.basis, rows: [row] });
    }
  }
  return segments;
}

function SummarySection({
  section,
  periods,
  defaultOpen,
}: {
  section: LedgerPnlIndicatorSummarySection;
  periods: LedgerPnlIndicatorSummaryPeriod[];
  defaultOpen: boolean;
}) {
  const segments = splitRowsByBasis(section);
  const counts = countRowAvailability(section.rows);
  return (
    <details
      className="ledger-indicator-summary__section"
      data-testid={`ledger-indicator-summary-section-${section.section_id}`}
      open={defaultOpen}
    >
      <summary className="ledger-indicator-summary__section-summary">
        <span className="ledger-indicator-summary__section-heading">
          <span className="ledger-indicator-summary__section-marker" aria-hidden="true" />
          <h3>{section.title}</h3>
          <small>{section.basis_note}</small>
        </span>
        <CoverageCounts counts={counts} />
      </summary>
      <div className="ledger-indicator-summary__scroller">
        <table className="ledger-indicator-summary__table">
          <thead>
            {segments.length > 0 ? (
              <SummaryHeaderRows
                periods={periods}
                basis={segments[0].basis}
                segmentLabel="项目"
              />
            ) : null}
          </thead>
          {segments.map((segment, index) => (
            <tbody key={`${section.section_id}-${index}`}>
              {index > 0 ? (
                <SummaryHeaderRows
                  periods={periods}
                  basis={segment.basis}
                  segmentLabel="项目"
                />
              ) : null}
              {segment.rows.map((row) => (
                <SummaryRow key={row.row_id} row={row} periods={periods} />
              ))}
            </tbody>
          ))}
        </table>
      </div>
    </details>
  );
}

function PanelStatusStrip({ payload }: { payload: LedgerPnlIndicatorSummaryPayload }) {
  const failed = payload.quality_checks.filter((check) => !check.passed);
  const identityTone = failed.length === 0 ? "ok" : "warn";
  return (
    <div
      className="ledger-indicator-summary__quality"
      data-state={failed.length === 0 ? "ok" : "warning"}
      data-testid="ledger-indicator-summary-quality"
    >
      <span className="ledger-indicator-summary__quality-item">
        <CoverageDot tone={identityTone} />
        恒等校验 {payload.quality_checks.length - failed.length} / {payload.quality_checks.length} 通过
      </span>
      <CoverageCounts counts={countRowAvailability(payload.sections.flatMap((s) => s.rows))} />
      {failed.map((check) => (
        <em
          key={`${check.check_id}-${check.month}`}
          className="ledger-indicator-summary__quality-failure"
        >
          {check.month} {check.message}未闭合（差 {formatGapYuan(check.gap_yuan)}，与表体亿元单位不同）
        </em>
      ))}
    </div>
  );
}

export function LedgerPnlFinancialIndicatorSummaryPanel({
  reportMonth,
  currency,
  enabled = true,
}: Props) {
  const client = useApiClient();
  const normalizedReportMonth = reportMonth.trim();
  const summaryQuery = useQuery({
    queryKey: [
      "ledger-pnl",
      "financial-indicator-summary",
      client.mode,
      normalizedReportMonth,
      currency,
    ] as const,
    queryFn: () => client.getLedgerPnlFinancialIndicatorSummary(normalizedReportMonth, currency),
    enabled: enabled && Boolean(normalizedReportMonth),
    retry: false,
  });
  const payload = summaryQuery.data?.result;

  const renderHeader = (subtitle: string) => (
    <header className="ledger-indicator-summary__header">
      <div>
        <h2>{payload?.title ?? "经营指标情况表（总账口径）"}</h2>
        <p>{subtitle}</p>
      </div>
      <div className="ledger-indicator-summary__header-meta">
        <span>总账口径 · 非正式报表数</span>
        <small>
          {normalizedReportMonth || "未选择报告月"} {currency}（单位：{payload?.unit ?? "亿元"}）
        </small>
      </div>
    </header>
  );

  if (!normalizedReportMonth) {
    return (
      <section className="ledger-indicator-summary" data-testid="ledger-pnl-financial-indicator-summary-panel">
        {renderHeader("对标财务指标工作簿汇总结构，由系统总账科目组合计算。")}
        <div className="ledger-indicator-summary__state" data-state="no_data">
          <strong>未选择报告月</strong>
          <span>选择报告日后按其所在月份读取经营指标情况表。</span>
        </div>
      </section>
    );
  }

  if (summaryQuery.isPending) {
    return (
      <section
        className="ledger-indicator-summary"
        data-testid="ledger-pnl-financial-indicator-summary-panel"
        aria-busy="true"
      >
        {renderHeader("对标财务指标工作簿汇总结构，由系统总账科目组合计算。")}
        <div
          className="ledger-indicator-summary__state"
          data-state="loading"
          data-testid="ledger-indicator-summary-loading"
        >
          <strong>正在计算经营指标情况表…</strong>
          <span>正在读取本年各月与上年同期总账科目余额。</span>
        </div>
      </section>
    );
  }

  if (summaryQuery.isError) {
    return (
      <section className="ledger-indicator-summary" data-testid="ledger-pnl-financial-indicator-summary-panel">
        {renderHeader("对标财务指标工作簿汇总结构，由系统总账科目组合计算。")}
        <div
          className="ledger-indicator-summary__state ledger-indicator-summary__state--error"
          data-state="error"
          data-testid="ledger-indicator-summary-error"
          role="alert"
        >
          <strong>经营指标情况表读取失败</strong>
          <span>
            {summaryQuery.error instanceof Error
              ? summaryQuery.error.message
              : "指标汇总读取失败"}
          </span>
          <button type="button" onClick={() => void summaryQuery.refetch()}>
            重新读取
          </button>
        </div>
      </section>
    );
  }

  if (!payload) {
    return (
      <section className="ledger-indicator-summary" data-testid="ledger-pnl-financial-indicator-summary-panel">
        {renderHeader("对标财务指标工作簿汇总结构，由系统总账科目组合计算。")}
        <div
          className="ledger-indicator-summary__state ledger-indicator-summary__state--error"
          data-state="error"
          role="alert"
        >
          <strong>响应缺少 result</strong>
          <span>已按契约错误阻断展示，不把空结果当作有效数据。</span>
        </div>
      </section>
    );
  }

  if (payload.data_status === "no_data") {
    return (
      <section className="ledger-indicator-summary" data-testid="ledger-pnl-financial-indicator-summary-panel">
        {renderHeader("对标财务指标工作簿汇总结构，由系统总账科目组合计算。")}
        <div
          className="ledger-indicator-summary__state"
          data-state="no_data"
          data-testid="ledger-indicator-summary-no-data"
        >
          <strong>{payload.report_month} 无可计算的总账来源</strong>
          <span>该报告月的总账对账工作簿未登记；缺失月份保持为空，不以 0 值展示。</span>
        </div>
      </section>
    );
  }

  return (
    <section
      className="ledger-indicator-summary"
      data-testid="ledger-pnl-financial-indicator-summary-panel"
    >
      {renderHeader(
        "行结构对标财务指标工作簿汇总表；可计算行由系统总账科目组合得出，无来源行保持空值。",
      )}
      <PanelStatusStrip payload={payload} />
      {payload.sections.map((section) => (
        <SummarySection
          key={section.section_id}
          section={section}
          periods={payload.periods}
          defaultOpen={section.section_id === "financial"}
        />
      ))}
      <footer className="ledger-indicator-summary__footer">
        <details>
          <summary title={`契约版本 ${payload.contract_version}`}>
            口径说明（{payload.notes.length} 条）
          </summary>
          <ul>
            {payload.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </details>
        <details>
          <summary>总账来源文件（{payload.source_files.length} 个月份）</summary>
          <ul>
            {payload.source_files.map((file) => (
              <li key={file.month}>
                <code>{file.month}</code> {file.file_name}
                <span className="ledger-indicator-summary__source-version">
                  {file.source_version}
                </span>
              </li>
            ))}
          </ul>
        </details>
      </footer>
    </section>
  );
}
