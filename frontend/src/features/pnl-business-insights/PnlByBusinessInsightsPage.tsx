import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../api/client";
import type {
  PnlByBusinessConcentrationRow,
  PnlByBusinessConcentrationSummary,
  PnlByBusinessInsightsComponentEvidence,
  PnlByBusinessInsightsPayload,
  PnlByBusinessNegativeFtpPersistenceRow,
  PnlByBusinessShareDriftRow,
} from "../../api/contracts";
import { FilterBar } from "../../components/FilterBar";
import { KpiCard } from "../../components/KpiCard";
import { PageAsyncSection } from "../../components/page/PageAsyncSection";
import {
  DataStatusStrip,
  PageDecisionHero,
  PageFilterTray,
  PageSectionLead,
  PageStateSurface,
  PageV2Shell,
} from "../../components/page/PagePrimitives";
import { tableShellStyle, tableStyle, tdStyle, thStyle } from "../../components/page/pageStyles";
import { CapitalEfficiencyQuadrantPanel } from "./CapitalEfficiencyQuadrantPanel";
import { UntracedReconciliationTrendPanel } from "./UntracedReconciliationTrendPanel";
import { hasApprovedPnlByBusinessInsightsEvidence } from "../pnl/pnlByBusinessInsightsModel";
import "./PnlByBusinessInsightsPage.css";

const RECONCILIATION_NOTE_TEXT =
  "以下为正式数据链路的对账诊断趋势，反映的是追溯完整性，不是业务贡献或拖累结论，不作为资源配置或业务评价依据。";

function toNumber(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatPct(value: string | null | undefined, digits = 2): string {
  const parsed = toNumber(value);
  return parsed === null ? "—" : `${parsed.toFixed(digits)}%`;
}

function formatSignedPp(value: string | null | undefined): string {
  const parsed = toNumber(value);
  if (parsed === null) {
    return "—";
  }
  return `${parsed > 0 ? "+" : ""}${parsed.toFixed(2)}pp`;
}

const YUAN_PER_YI = 100_000_000;

function formatYuanAsYi(value: string | null | undefined): string {
  const parsed = toNumber(value);
  return parsed === null ? "—" : (parsed / YUAN_PER_YI).toFixed(2);
}

function validIsoDate(value: string | null): string | null {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return null;
  }
  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
    ? value
    : null;
}

function initialFilters(searchParams: URLSearchParams): { year: number; asOfDate: string } | null {
  const asOfDate = validIsoDate(searchParams.get("as_of_date"));
  const rawYear = searchParams.get("year");
  const year = /^\d{4}$/.test(rawYear ?? "") ? Number(rawYear) : Number.NaN;
  if (
    asOfDate &&
    Number.isInteger(year) &&
    year >= 2000 &&
    year <= 2100 &&
    asOfDate.startsWith(`${year}-`)
  ) {
    return { year, asOfDate };
  }
  return null;
}

function topConcentrationRows(summary: PnlByBusinessConcentrationSummary) {
  return [...summary.rows]
    .sort((left, right) => (toNumber(right.share_pct) ?? -1) - (toNumber(left.share_pct) ?? -1))
    .slice(0, summary.top_n);
}

function ytdRuleVersions(componentEvidence: PnlByBusinessInsightsComponentEvidence[]) {
  const current = componentEvidence.find((item) => item.component === "current_ytd")?.rule_version ?? null;
  const baseline = componentEvidence.find((item) => item.component === "baseline_ytd")?.rule_version ?? null;
  return {
    current,
    baseline,
    mismatch: Boolean(current && baseline && current !== baseline),
  };
}

function BusinessDecisionBrief({ result }: { result: PnlByBusinessInsightsPayload }) {
  const topRows = topConcentrationRows(result.concentration);
  const driftByRowKey = new Map(result.share_drift.rows.map((row) => [row.row_key, row]));
  const warningRows = result.negative_ftp_persistence.rows
    .filter((row) => row.eligible && row.status === "eligible" && row.warning_triggered)
    .sort(
      (left, right) =>
        (toNumber(right.negative_ftp_month_share_pct) ?? -1) -
        (toNumber(left.negative_ftp_month_share_pct) ?? -1),
    );
  const approvedManualEntriesIncluded = result.component_evidence.some(
    (item) =>
      item.component.startsWith("monthly_") && item.tables_used.includes("pnl_by_business_adjustments"),
  );
  const warningDoesNotCoverEveryMonth = warningRows.some(
    (row) => (toNumber(row.negative_ftp_month_share_pct) ?? 100) < 100,
  );
  const ruleVersions = ytdRuleVersions(result.component_evidence);

  return (
    <section
      className="pnl-by-business-insights-decision-brief"
      data-testid="pnl-by-business-insights-decision-brief"
      aria-labelledby="pnl-by-business-insights-decision-brief-title"
    >
      <div className="pnl-by-business-insights-decision-brief__header">
        <div>
          <span>管理层先看</span>
          <h2 id="pnl-by-business-insights-decision-brief-title">结构、异常与使用顺序</h2>
        </div>
        <span className="pnl-by-business-insights-decision-brief__cutoff">截至 {result.as_of_date}</span>
      </div>

      <div className="pnl-by-business-insights-decision-brief__grid">
        <article>
          <span className="pnl-by-business-insights-decision-brief__label">结构底盘</span>
          <strong>Top{result.concentration.top_n} 占比 {formatPct(result.concentration.top_n_share_pct)}</strong>
          <p>{topRows.length > 0 ? topRows.map((row) => row.business_type).join("、") : "暂无合格父级业务"}</p>
          <small>
            HHI {formatPct(result.concentration.hhi_pct)} 用于观察集中度趋势，不作为单期红黄绿阈值。
          </small>
        </article>

        <article className="pnl-by-business-insights-decision-brief__focus">
          <span className="pnl-by-business-insights-decision-brief__label">FTP后损益为负月份观察</span>
          {warningRows.length > 0 ? (
            <div className="pnl-by-business-insights-decision-brief__signals">
              {warningRows.map((row) => {
                const drift = result.share_drift.available ? driftByRowKey.get(row.row_key) : undefined;
                return (
                  <p key={row.row_key}>
                    <strong>{row.business_type}</strong>
                    ：FTP后损益为负月份占比 {formatPct(row.negative_ftp_month_share_pct)}，最长连续
                    {row.negative_ftp_longest_streak_months ?? "—"}个月
                    {drift?.drift_pp !== null && drift?.drift_pp !== undefined ? (
                      <>
                        ；当前日均份额 {formatPct(drift.current_share_pct)}，较上年同期间 {formatSignedPp(drift.drift_pp)}
                      </>
                    ) : null}
                    。
                  </p>
                );
              })}
            </div>
          ) : (
            <p>当前没有业务达到FTP后损益为负月份占比提示条件。</p>
          )}
          <small>
            {approvedManualEntriesIncluded ? "滚动月度口径已纳入已批准手工补录。" : ""}
            {warningDoesNotCoverEveryMonth
              ? "FTP后损益为负月份占比较高不表示每个月均为负，也不表示业务总损益为负。"
              : ""}
            该交叉观察只组合展示后端正式结果，不新增阈值或配置建议。
          </small>
        </article>

        <article>
          <span className="pnl-by-business-insights-decision-brief__label">怎么使用</span>
          <ol>
            <li>先看 Top{result.concentration.top_n} 与 HHI，确认资源集中在哪些业务。</li>
            <li>再把FTP后损益为负月份频率与份额漂移对照，定位需要解释的业务。</li>
            <li>最后用四象限看相对位置，并下钻资产收益率、FTP率和期限结构。</li>
          </ol>
          <small>当前接口未返回利润影响所需输入，本页不作估算。</small>
        </article>
      </div>

      {ruleVersions.mismatch ? (
        <div
          className="pnl-by-business-insights-rule-warning"
          data-testid="pnl-by-business-insights-cross-period-rule-warning"
          role="note"
        >
          <strong>跨期口径提示</strong>
          <span>
            当前 YTD 使用 {ruleVersions.current}，上年同期间使用 {ruleVersions.baseline}。份额漂移仅表示当前治理口径下的差异，统一口径重算后再形成经营判断。
          </span>
        </div>
      ) : null}
    </section>
  );
}

function ConcentrationTable({ rows }: { rows: PnlByBusinessConcentrationRow[] }) {
  const sortedRows = [...rows].sort(
    (left, right) => (toNumber(right.share_pct) ?? -1) - (toNumber(left.share_pct) ?? -1),
  );
  return (
    <div style={tableShellStyle} data-testid="pnl-by-business-insights-concentration-table">
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>业务种类</th>
            <th style={thStyle}>YTD日均（亿元）</th>
            <th style={thStyle}>日均份额</th>
          </tr>
        </thead>
        <tbody>
          {sortedRows.length === 0 ? (
            <tr><td colSpan={3} style={tdStyle}>暂无集中度明细</td></tr>
          ) : (
            sortedRows.map((row) => (
              <tr key={row.row_key}>
                <td style={tdStyle}>{row.business_type}</td>
                <td style={tdStyle}>{formatYuanAsYi(row.avg_balance)}</td>
                <td style={tdStyle}>{formatPct(row.share_pct)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function NegativeFtpTable({ rows }: { rows: PnlByBusinessNegativeFtpPersistenceRow[] }) {
  const sortedRows = [...rows].sort(
    (left, right) =>
      Number(right.warning_triggered) - Number(left.warning_triggered) ||
      (toNumber(right.negative_ftp_month_share_pct) ?? -1) -
        (toNumber(left.negative_ftp_month_share_pct) ?? -1),
  );
  return (
    <div style={tableShellStyle} data-testid="pnl-by-business-insights-negative-ftp-table">
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>业务种类</th>
            <th style={thStyle}>FTP后损益为负月份占比</th>
            <th style={thStyle}>最长连续负值</th>
            <th style={thStyle}>已观测月份</th>
            <th style={thStyle}>状态</th>
          </tr>
        </thead>
        <tbody>
          {sortedRows.length === 0 ? (
            <tr><td colSpan={5} style={tdStyle}>暂无持续性明细</td></tr>
          ) : (
            sortedRows.map((row) => (
              <tr key={row.row_key}>
                <td style={tdStyle}>{row.business_type}</td>
                <td
                  data-warning={row.warning_triggered ? "true" : undefined}
                  style={{
                    ...tdStyle,
                    fontWeight: row.warning_triggered ? 700 : undefined,
                  }}
                >
                  {row.eligible && row.status === "eligible"
                    ? formatPct(row.negative_ftp_month_share_pct)
                    : "—"}
                </td>
                <td style={tdStyle}>
                  {row.eligible && row.status === "eligible" && row.negative_ftp_longest_streak_months !== null
                    ? `${row.negative_ftp_longest_streak_months} 个月`
                    : "—"}
                </td>
                <td style={tdStyle}>{row.months_observed}</td>
                <td style={tdStyle}>
                  {!row.eligible || row.status === "insufficient_observations"
                    ? "观察不足"
                    : row.warning_triggered
                      ? "达到提示条件"
                      : "观察"}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function ShareDriftTable({
  rows,
  baselineAvailable,
  available,
  availabilityReason,
}: {
  rows: PnlByBusinessShareDriftRow[];
  baselineAvailable: boolean;
  available: boolean;
  availabilityReason: "baseline_missing" | "current_total_non_positive" | "baseline_total_non_positive" | null;
}) {
  if (!available || !baselineAvailable) {
    const reason =
      availabilityReason === "current_total_non_positive" ||
      availabilityReason === "baseline_total_non_positive"
        ? "当前期或上年同期间日均余额分母不可用，暂不计算份额漂移"
        : "上年同期间基准不可用，暂不计算份额漂移";
    return (
      <PageStateSurface
        variant="empty"
        testId="pnl-by-business-insights-share-drift-empty"
        title={reason}
      />
    );
  }
  const sortedRows = [...rows].sort(
    (left, right) => Math.abs(toNumber(right.drift_pp) ?? 0) - Math.abs(toNumber(left.drift_pp) ?? 0),
  );
  const lifecycleLabel = { continued: "持续", new: "新进", exited: "退出", unavailable: "不可用" } as const;
  return (
    <div style={tableShellStyle} data-testid="pnl-by-business-insights-share-drift-table">
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>业务种类</th>
            <th style={thStyle}>当前份额</th>
            <th style={thStyle}>上年同期间份额</th>
            <th style={thStyle}>漂移</th>
            <th style={thStyle}>状态</th>
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row) => (
            <tr key={row.row_key}>
              <td style={tdStyle}>{row.business_type}</td>
              <td style={tdStyle}>{formatPct(row.current_share_pct)}</td>
              <td style={tdStyle}>{formatPct(row.baseline_share_pct)}</td>
              <td style={tdStyle}>{formatSignedPp(row.drift_pp)}</td>
              <td style={tdStyle}>{lifecycleLabel[row.lifecycle_status]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PnlByBusinessInsightsPage() {
  const client = useApiClient();
  const [searchParams] = useSearchParams();
  const [initial] = useState(() => initialFilters(searchParams));
  const [year, setYear] = useState(initial?.year ?? 0);
  const [asOfDate, setAsOfDate] = useState(initial?.asOfDate ?? "");

  const datesQuery = useQuery({
    queryKey: ["pnl-by-business-insights", "dates", client.mode],
    queryFn: () => client.getFormalPnlDates("formal"),
    retry: false,
  });
  const reportDates = useMemo(
    () => datesQuery.data?.result.formal_fi_report_dates ?? datesQuery.data?.result.report_dates ?? [],
    [datesQuery.data?.result.formal_fi_report_dates, datesQuery.data?.result.report_dates],
  );
  const availableYears = useMemo(
    () => Array.from(new Set(reportDates.map((reportDate) => Number(reportDate.slice(0, 4))))),
    [reportDates],
  );
  const yearReportDates = useMemo(
    () => reportDates.filter((reportDate) => reportDate.startsWith(`${year}-`)),
    [reportDates, year],
  );

  useEffect(() => {
    if (reportDates.length === 0) {
      return;
    }
    const selectionIsAvailable =
      reportDates.includes(asOfDate) && asOfDate.startsWith(`${year}-`);
    if (selectionIsAvailable) {
      return;
    }
    const initialDate = initial?.asOfDate;
    const nextDate = initialDate && reportDates.includes(initialDate) ? initialDate : reportDates[0];
    setAsOfDate(nextDate);
    setYear(Number(nextDate.slice(0, 4)));
  }, [asOfDate, initial, reportDates, year]);

  const selectedDateIsAvailable =
    reportDates.includes(asOfDate) && asOfDate.startsWith(`${year}-`);

  const insightsQuery = useQuery({
    queryKey: ["pnl-by-business-insights", "formal", client.mode, year, asOfDate],
    queryFn: () => client.getPnlByBusinessInsights(year, asOfDate),
    enabled: datesQuery.isSuccess && selectedDateIsAvailable,
    retry: false,
  });

  const meta = insightsQuery.data?.result_meta;
  const result = insightsQuery.data?.result;
  const contractReady = Boolean(
    meta?.basis === "formal" &&
      meta.formal_use_allowed &&
      meta.result_kind === "pnl.by_business_insights" &&
      (meta.quality_flag === "ok" || meta.quality_flag === "warning") &&
      meta.vendor_status === "ok" &&
      !meta.scenario_flag &&
      meta.fallback_mode === "none" &&
      !meta.fallback_date &&
      meta.requested_report_date === asOfDate &&
      meta.resolved_report_date === asOfDate &&
      result?.result_version === "v2" &&
      hasApprovedPnlByBusinessInsightsEvidence(result) &&
      result?.as_of_date === asOfDate,
  );
  const isEmpty =
    (datesQuery.isSuccess && reportDates.length === 0) ||
    (insightsQuery.isSuccess &&
      contractReady &&
      (result?.concentration.rows.length ?? 0) === 0 &&
      (result?.negative_ftp_persistence.rows.length ?? 0) === 0 &&
      (result?.share_drift.rows.length ?? 0) === 0);

  return (
    <section
      data-testid="pnl-by-business-insights-page"
      data-moss-theme-scope="pnl-by-business-insights"
      className="pnl-by-business-insights-page"
    >
      <PageV2Shell testId="pnl-by-business-insights-page-shell">
        <PageDecisionHero
          testId="pnl-by-business-insights-hero"
          titleTestId="pnl-by-business-insights-page-title"
          questionTestId="pnl-by-business-insights-page-subtitle"
          eyebrow="组合工作台 · 正式结构分析"
          title="业务结构与FTP后收益分析"
          businessQuestion="业务结构是否集中、哪些业务频繁或连续未覆盖FTP成本、日均份额同比如何变化、规模与FTP后收益处于什么相对位置？"
        >
          <PageFilterTray testId="pnl-by-business-insights-filter-tray">
            <FilterBar>
              <label className="pnl-by-business-insights-filter-label">
                年份
                <select
                  aria-label="pnl-by-business-insights-year"
                  value={year || ""}
                  disabled={datesQuery.isLoading || availableYears.length === 0}
                  onChange={(event) => {
                    const nextYear = Number(event.target.value);
                    const nextDate = reportDates.find((reportDate) => reportDate.startsWith(`${nextYear}-`));
                    if (nextDate) {
                      setYear(nextYear);
                      setAsOfDate(nextDate);
                    }
                  }}
                  className="pnl-by-business-insights-control"
                >
                  {availableYears.map((availableYear) => (
                    <option key={availableYear} value={availableYear}>{availableYear}</option>
                  ))}
                </select>
              </label>
              <label className="pnl-by-business-insights-filter-label">
                截止日
                <select
                  aria-label="pnl-by-business-insights-as-of-date"
                  value={asOfDate}
                  disabled={datesQuery.isLoading || yearReportDates.length === 0}
                  onChange={(event) => {
                    const nextDate = event.target.value;
                    setAsOfDate(nextDate);
                    setYear(Number(nextDate.slice(0, 4)));
                  }}
                  className="pnl-by-business-insights-control"
                >
                  {yearReportDates.map((reportDate) => (
                    <option key={reportDate} value={reportDate}>{reportDate}</option>
                  ))}
                </select>
              </label>
            </FilterBar>
          </PageFilterTray>
        </PageDecisionHero>

        <PageAsyncSection
          title="正式结构分析"
          isLoading={datesQuery.isLoading || insightsQuery.isLoading}
          isError={datesQuery.isError || insightsQuery.isError}
          isEmpty={isEmpty}
          fillHeight={false}
          onRetry={() => {
            if (datesQuery.isError) {
              void datesQuery.refetch();
              return;
            }
            void insightsQuery.refetch();
          }}
        >
          {result && meta ? (
            <>
              <DataStatusStrip
                testId="pnl-by-business-insights-contract-status"
                className="pnl-by-business-insights-data-status-strip"
              >
                <span><strong>正式口径</strong> {meta.formal_use_allowed ? "已批准" : "待确认"}</span>
                <span><strong>质量</strong> {meta.quality_flag}</span>
                <span><strong>截止</strong> {meta.resolved_report_date ?? result.as_of_date}</span>
                <span><strong>降级</strong> {meta.fallback_mode}</span>
                <span><strong>供应商</strong> {meta.vendor_status}</span>
                <span><strong>生成</strong> {meta.generated_at ?? "—"}</span>
                <span><strong>Trace</strong> {meta.trace_id}</span>
              </DataStatusStrip>

              {!contractReady ? (
                <PageStateSurface
                  variant="definition-pending"
                  testId="pnl-by-business-insights-contract-review"
                  title="结构分析待复核"
                  description="正式状态、响应版本、截止日、质量、供应商或降级状态未通过门禁，页面不将其作为正式汇报结论。"
                />
              ) : (
                <>
              <BusinessDecisionBrief result={result} />

              <div
                className="pnl-by-business-insights-summary-grid"
                data-testid="pnl-by-business-insights-concentration-kpis"
              >
                <KpiCard
                  label={`Top${result.concentration.top_n} 日均份额`}
                  value={formatPct(result.concentration.top_n_share_pct)}
                  detail={topConcentrationRows(result.concentration).map((row) => row.business_type).join("、") || "暂无合格父级业务"}
                />
                <KpiCard
                  label="总日均余额"
                  value={`${formatYuanAsYi(result.concentration.total_avg_balance)} 亿元`}
                  detail="YTD日均余额、人民币等值、父级业务"
                />
                <KpiCard
                  label="HHI（趋势观察）"
                  value={formatPct(result.concentration.hhi_pct)}
                  detail="辅助观察集中度变化，不设单期阈值"
                />
              </div>

              <PageSectionLead
                eyebrow="结构集中"
                title="业务集中度"
                description="按YTD日均余额份额降序展示；HHI以百分比形式返回，不与传统HHI点数混用。"
              />
              <ConcentrationTable rows={result.concentration.rows} />

              <PageSectionLead
                eyebrow="持续性观察"
                title="FTP后损益为负月份频率与最长连续期"
                description={`滚动 ${result.negative_ftp_persistence.lookback_months} 个自然月；至少 ${result.negative_ftp_persistence.minimum_observed_months} 个已观测月份且负值月份占比达到 ${formatPct(result.negative_ftp_persistence.warning_threshold_pct)} 才提示，缺失月份不进分母并打断连续期。`}
              />
              <NegativeFtpTable rows={result.negative_ftp_persistence.rows} />

              <PageSectionLead
                eyebrow="跨期结构"
                title="日均份额同比漂移"
                description={`当前YTD与上年同期间 ${result.share_drift.baseline_as_of_date ?? "—"} 对比；新进及退出业务缺失侧按0处理。`}
              />
              <ShareDriftTable
                rows={result.share_drift.rows}
                baselineAvailable={result.share_drift.baseline_available}
                available={result.share_drift.available}
                availabilityReason={result.share_drift.availability_reason}
              />

              <PageSectionLead
                eyebrow="相对位置"
                title="规模—FTP后收益相对象限"
                description="规模轴使用日均余额份额，收益轴使用FTP后年化收益率；按当期中位数作描述性相对比较，不生成增配或压降建议。"
              />
              <CapitalEfficiencyQuadrantPanel summary={result.scale_yield_quadrant} />
                </>
              )}
            </>
          ) : null}
        </PageAsyncSection>

        {contractReady && result?.reconciliation_diagnostics ? (
          <>
            <hr
              className="pnl-by-business-insights-reconciliation-divider"
              data-testid="pnl-by-business-insights-reconciliation-divider"
            />
            <div
              className="pnl-by-business-insights-reconciliation-section"
              data-testid="pnl-by-business-insights-reconciliation-section"
            >
              <span className="pnl-by-business-insights-reconciliation-eyebrow">非业务分析 · 数据链路诊断</span>
              <h2 className="pnl-by-business-insights-reconciliation-title">对账健康度诊断（非业务结论）</h2>
              <p className="pnl-by-business-insights-reconciliation-note">{RECONCILIATION_NOTE_TEXT}</p>
              {result.reconciliation_diagnostics.available ? (
                <UntracedReconciliationTrendPanel rows={result.reconciliation_diagnostics.rows} />
              ) : (
                <PageStateSurface
                  variant="empty"
                  testId="pnl-by-business-insights-reconciliation-unavailable"
                  title={
                    result.reconciliation_diagnostics.availability_reason === "source_unavailable"
                      ? "诊断源暂不可用，当前不能判断未追溯趋势"
                      : "当前窗口没有可用于诊断的正式 FI 观测"
                  }
                />
              )}
            </div>
          </>
        ) : null}
      </PageV2Shell>
    </section>
  );
}
