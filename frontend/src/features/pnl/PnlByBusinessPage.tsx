import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../api/client";
import type { PnlByBusinessRow, PnlByBusinessYtdItem } from "../../api/contracts";
import { FilterBar } from "../../components/FilterBar";
import { KpiCard } from "../../components/KpiCard";
import { FormalResultMetaPanel } from "../../components/page/FormalResultMetaPanel";
import { SectionLead } from "../../components/page/SectionLead";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { formatAnnualizedYieldPctDisplay, inclusiveCalendarDays } from "./pnlByBusinessAnnualizedYield";
import { resolveAdbAvgYuan } from "./zqtzAdbAvgRollup";
import "./PnlByBusinessPage.css";

function numeric(raw: string | number | null | undefined): number | null {
  if (raw === null || raw === undefined || raw === "") {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

/** 与日均分析页明细表「日均(亿元)」列一致：两位小数，单位写在表头 */
const YUAN_PER_YI = 100_000_000;
const YUAN_PER_WAN = 10_000;

/** 损益金额：接口为元，本页统一按万元展示 */
function formatPnlWan(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return (value / YUAN_PER_WAN).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function formatYuanAsWanUnit(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return `${(value / YUAN_PER_WAN).toLocaleString("zh-CN", { maximumFractionDigits: 2 })} 万元`;
}

function formatAdbAvgYiCell(yuan: number): string {
  return (yuan / YUAN_PER_YI).toFixed(2);
}

function formatRatioPct(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

/** 单日 formal 接口 `yield_pct`：与后端 SQL 一致，为百分数点（如 10.14 表示 10.14%），非 0–1 占比 */
function formatFormalYieldPctPoints(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return `${value.toFixed(2)}%`;
}

function toneFromSigned(raw: string | number | null | undefined): "default" | "positive" | "negative" {
  const value = numeric(raw);
  if (value === null || value === 0) {
    return "default";
  }
  return value > 0 ? "positive" : "negative";
}

/** 与日均分析页默认「年初至今」一致：当年 1 月 1 日 — 所选报表日（含） */
function buildYtdRangeFromReportDate(reportDate: string): { startDate: string; endDate: string } | null {
  if (!reportDate) {
    return null;
  }
  const end = new Date(`${reportDate}T12:00:00`);
  if (Number.isNaN(end.getTime())) {
    return null;
  }
  const start = new Date(end);
  start.setMonth(0, 1);
  const pad = (n: number) => `${n}`.padStart(2, "0");
  return {
    startDate: `${start.getFullYear()}-${pad(start.getMonth() + 1)}-${pad(start.getDate())}`,
    endDate: `${end.getFullYear()}-${pad(end.getMonth() + 1)}-${pad(end.getDate())}`,
  };
}

/** 与后端 ZQTZ 表格一致：排除「其中」细分行，汇总时不与父级重复加总 */
function isParentZqtzBusinessRow(row: PnlByBusinessYtdItem): boolean {
  if (row.business_type.startsWith("其中：")) {
    return false;
  }
  const note = String(row.source_note ?? "");
  return !note.includes("其中项");
}

function BusinessRowsTable({
  rows,
  adbAvgByBusinessType,
  ytdCalendarDays,
}: {
  rows: PnlByBusinessYtdItem[];
  adbAvgByBusinessType: Map<string, number>;
  ytdCalendarDays: number | null;
}) {
  const parentRows = useMemo(() => rows.filter(isParentZqtzBusinessRow), [rows]);

  const parentFooter = useMemo(() => {
    let interest = 0;
    let fairValue = 0;
    let capital = 0;
    let totalPnl = 0;
    let assets = 0;
    let adbSum = 0;
    for (const row of parentRows) {
      interest += numeric(row.interest_income) ?? 0;
      fairValue += numeric(row.fair_value_change) ?? 0;
      capital += numeric(row.capital_gain) ?? 0;
      totalPnl += numeric(row.total_pnl) ?? 0;
      assets += row.assets_count;
      const adb = resolveAdbAvgYuan(row.business_type, adbAvgByBusinessType);
      if (adb !== undefined && adb > 0) {
        adbSum += adb;
      }
    }
    const adbCell = adbSum > 0 ? formatAdbAvgYiCell(adbSum) : "-";
    return {
      interest,
      fairValue,
      capital,
      totalPnl,
      assets,
      adbSum,
      adbCell,
      yieldPct: "—",
    };
  }, [parentRows, adbAvgByBusinessType]);

  return (
    <div className="pnl-by-business-table-shell" data-testid="pnl-by-business-table">
      <table className="pnl-by-business-table">
        <thead>
          <tr>
            <th>业务种类</th>
            <th>日均(亿元)</th>
            <th>利息收入（万元）</th>
            <th>公允价值变动（万元）</th>
            <th>资本利得（万元）</th>
            <th>合计损益（万元）</th>
            <th>年化收益率</th>
            <th>占比</th>
            <th>资产数</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const adbAvg = resolveAdbAvgYuan(row.business_type, adbAvgByBusinessType);
            const avgDisplay =
              adbAvg !== undefined && adbAvg > 0 ? formatAdbAvgYiCell(adbAvg) : "-";
            return (
              <tr key={row.row_key}>
                <td>{row.business_type}</td>
                <td>{avgDisplay}</td>
                <td>{formatPnlWan(row.interest_income)}</td>
                <td>{formatPnlWan(row.fair_value_change)}</td>
                <td>{formatPnlWan(row.capital_gain)}</td>
                <td>{formatPnlWan(row.total_pnl)}</td>
                <td>
                  {formatAnnualizedYieldPctDisplay(numeric(row.total_pnl), adbAvg, ytdCalendarDays)}
                </td>
                <td>{formatRatioPct(row.proportion)}</td>
                <td>{row.assets_count}</td>
              </tr>
            );
          })}
        </tbody>
        {parentRows.length > 0 ? (
          <tfoot>
            <tr data-testid="pnl-by-business-table-parent-footer">
              <td className="pnl-by-business-table-footer-cell">父级汇总</td>
              <td className="pnl-by-business-table-footer-cell">{parentFooter.adbCell}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(parentFooter.interest)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(parentFooter.fairValue)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(parentFooter.capital)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(parentFooter.totalPnl)}</td>
              <td className="pnl-by-business-table-footer-cell">{parentFooter.yieldPct}</td>
              <td className="pnl-by-business-table-footer-cell">—</td>
              <td className="pnl-by-business-table-footer-cell">{parentFooter.assets}</td>
            </tr>
          </tfoot>
        ) : null}
      </table>
    </div>
  );
}

type PnlByBusinessViewMode = "ytd" | "formal";

function FormalBusinessRowsTable({ rows }: { rows: PnlByBusinessRow[] }) {
  const footer = useMemo(() => {
    let interest = 0;
    let fairValue = 0;
    let capital = 0;
    let manual = 0;
    let totalPnl = 0;
    let scale = 0;
    let pnlRows = 0;
    for (const row of rows) {
      interest += numeric(row.interest_income_514) ?? 0;
      fairValue += numeric(row.fair_value_change_516) ?? 0;
      capital += numeric(row.capital_gain_517) ?? 0;
      manual += numeric(row.manual_adjustment) ?? 0;
      totalPnl += numeric(row.total_pnl) ?? 0;
      scale += numeric(row.scale_amount) ?? 0;
      pnlRows += row.pnl_row_count;
    }
    return { interest, fairValue, capital, manual, totalPnl, scale, pnlRows };
  }, [rows]);

  return (
    <div className="pnl-by-business-table-shell" data-testid="pnl-by-business-formal-table">
      <table className="pnl-by-business-table">
        <thead>
          <tr>
            <th>业务种类（primary）</th>
            <th>币种</th>
            <th>规模(亿元)</th>
            <th>利息收入（万元）</th>
            <th>公允价值变动（万元）</th>
            <th>资本利得（万元）</th>
            <th>手工调整（万元）</th>
            <th>合计损益（万元）</th>
            <th>表内收益率</th>
            <th>损益行数</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.report_date}-${row.business_type_primary}-${row.currency_basis}`}>
              <td>{row.business_type_primary}</td>
              <td>{row.currency_basis}</td>
              <td>{formatAdbAvgYiCell(numeric(row.scale_amount) ?? 0)}</td>
              <td>{formatPnlWan(row.interest_income_514)}</td>
              <td>{formatPnlWan(row.fair_value_change_516)}</td>
              <td>{formatPnlWan(row.capital_gain_517)}</td>
              <td>{formatPnlWan(row.manual_adjustment)}</td>
              <td>{formatPnlWan(row.total_pnl)}</td>
              <td>{formatFormalYieldPctPoints(row.yield_pct)}</td>
              <td>{row.pnl_row_count}</td>
            </tr>
          ))}
        </tbody>
        {rows.length > 0 ? (
          <tfoot>
            <tr data-testid="pnl-by-business-formal-table-footer">
              <td className="pnl-by-business-table-footer-cell">全表合计</td>
              <td className="pnl-by-business-table-footer-cell">—</td>
              <td className="pnl-by-business-table-footer-cell">{formatAdbAvgYiCell(footer.scale)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(footer.interest)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(footer.fairValue)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(footer.capital)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(footer.manual)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(footer.totalPnl)}</td>
              <td className="pnl-by-business-table-footer-cell">—</td>
              <td className="pnl-by-business-table-footer-cell">{footer.pnlRows}</td>
            </tr>
          </tfoot>
        ) : null}
      </table>
    </div>
  );
}

export default function PnlByBusinessPage() {
  const client = useApiClient();
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [viewMode, setViewMode] = useState<PnlByBusinessViewMode>("ytd");

  const datesQuery = useQuery({
    queryKey: ["pnl-by-business", "dates", client.mode],
    queryFn: () => client.getFormalPnlDates("formal"),
    retry: false,
  });

  const reportDates = useMemo(
    () => datesQuery.data?.result.formal_fi_report_dates ?? datesQuery.data?.result.report_dates ?? [],
    [datesQuery.data?.result.formal_fi_report_dates, datesQuery.data?.result.report_dates],
  );

  useEffect(() => {
    const firstDate = reportDates[0];
    if (!firstDate) {
      return;
    }
    if (!selectedReportDate || !reportDates.includes(selectedReportDate)) {
      setSelectedReportDate(firstDate);
    }
  }, [reportDates, selectedReportDate]);

  const selectedYear = selectedReportDate ? Number(selectedReportDate.slice(0, 4)) : new Date().getFullYear();
  const businessQuery = useQuery({
    queryKey: ["pnl-by-business", "ytd", client.mode, selectedYear, selectedReportDate],
    enabled: Boolean(selectedReportDate && selectedYear && viewMode === "ytd"),
    queryFn: () => client.getPnlByBusinessYtd(selectedYear, selectedReportDate),
    retry: false,
  });

  const formalBusinessQuery = useQuery({
    queryKey: ["pnl-by-business", "formal", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate && viewMode === "formal"),
    queryFn: () => client.getPnlByBusiness(selectedReportDate),
    retry: false,
  });

  const ytdRange = useMemo(() => buildYtdRangeFromReportDate(selectedReportDate), [selectedReportDate]);

  const ytdCalendarDays = useMemo(() => {
    if (!ytdRange?.startDate || !ytdRange?.endDate) {
      return null;
    }
    return inclusiveCalendarDays(ytdRange.startDate, ytdRange.endDate);
  }, [ytdRange?.startDate, ytdRange?.endDate]);

  const adbComparisonQuery = useQuery({
    queryKey: ["pnl-by-business", "adb-comparison-ytd", client.mode, ytdRange?.startDate, ytdRange?.endDate],
    enabled: Boolean(ytdRange?.startDate && ytdRange?.endDate && viewMode === "ytd"),
    queryFn: () =>
      client.getAdbComparison(ytdRange!.startDate, ytdRange!.endDate, {
        topN: 200,
      }),
    retry: false,
  });

  const adbAvgByBusinessType = useMemo(() => {
    const map = new Map<string, number>();
    for (const item of adbComparisonQuery.data?.assets_breakdown ?? []) {
      const label = item.category?.trim();
      if (label) {
        map.set(label, item.avg_balance);
      }
    }
    return map;
  }, [adbComparisonQuery.data?.assets_breakdown]);

  const ytdResult = businessQuery.data?.result;
  const ytdRows = ytdResult?.items ?? [];
  const formalResult = formalBusinessQuery.data?.result;
  const formalRows = formalResult?.rows ?? [];

  const topYtdRow = ytdRows.reduce<PnlByBusinessYtdItem | undefined>((current, row) => {
    if (!current) {
      return row;
    }
    return Math.abs(numeric(row.total_pnl) ?? 0) > Math.abs(numeric(current.total_pnl) ?? 0) ? row : current;
  }, undefined);
  const ytdAssetCount = ytdRows.reduce((total, row) => total + row.assets_count, 0);

  const topFormalRow = formalRows.reduce<PnlByBusinessRow | undefined>((current, row) => {
    if (!current) {
      return row;
    }
    return Math.abs(numeric(row.total_pnl) ?? 0) > Math.abs(numeric(current.total_pnl) ?? 0) ? row : current;
  }, undefined);

  const loading =
    datesQuery.isLoading ||
    (viewMode === "ytd" && businessQuery.isLoading) ||
    (viewMode === "formal" && formalBusinessQuery.isLoading);
  const error =
    datesQuery.isError || (viewMode === "ytd" && businessQuery.isError) || (viewMode === "formal" && formalBusinessQuery.isError);
  const empty =
    !loading &&
    !error &&
    (!selectedReportDate ||
      (viewMode === "ytd" && ytdRows.length === 0) ||
      (viewMode === "formal" && formalRows.length === 0));

  return (
    <main data-testid="pnl-by-business-page">
      <div className="pnl-by-business-page-header">
        <div>
          <h1 className="pnl-by-business-title">业务种类损益</h1>
          <p className="pnl-by-business-subtitle">
            {viewMode === "ytd"
              ? "按年度累计口径汇总业务种类损益，拆分利息收入、公允价值变动和资本利得。"
              : "按所选报表日读取 formal 物化事实（GET /api/pnl/by-business），便于与 V1 单日口径对照；与「年累计」视图数字可能不同。"}
          </p>
        </div>
      </div>

      <FilterBar className="pnl-by-business-filter">
        <label className="pnl-by-business-filter-label">
          报表日
          <select
            aria-label="pnl-by-business-report-date"
            value={selectedReportDate}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            className="pnl-by-business-control"
          >
            {reportDates.map((date) => (
              <option key={date} value={date}>
                {date}
              </option>
            ))}
          </select>
        </label>
        <label className="pnl-by-business-filter-label">
          视图口径
          <select
            aria-label="pnl-by-business-view-mode"
            value={viewMode}
            onChange={(event) => setViewMode(event.target.value as PnlByBusinessViewMode)}
            className="pnl-by-business-control"
          >
            <option value="ytd">年累计（YTD）</option>
            <option value="formal">报表日 formal（/api/pnl/by-business）</option>
          </select>
        </label>
      </FilterBar>

      <AsyncSection
        title="业务种类损益"
        isLoading={loading}
        isError={error}
        isEmpty={empty}
        fillHeight={false}
        onRetry={() => {
          const chain = [datesQuery.refetch(), businessQuery.refetch(), formalBusinessQuery.refetch(), adbComparisonQuery.refetch()];
          void Promise.all(chain);
        }}
      >
        <section className="pnl-by-business-content">
          <div className="pnl-by-business-summary-grid" data-testid="pnl-by-business-summary-cards">
            {viewMode === "ytd" ? (
              <>
                <KpiCard
                  label="年度累计损益"
                  value={formatYuanAsWanUnit(ytdResult?.total_pnl)}
                  detail={ytdResult?.period_label ?? `${selectedYear} 年累计`}
                  tone={toneFromSigned(ytdResult?.total_pnl)}
                />
                <KpiCard
                  label="业务种类"
                  value={`${ytdRows.length}`}
                  detail={`${ytdAssetCount} 个归类命中`}
                />
                <KpiCard
                  label="最大损益业务"
                  value={topYtdRow?.business_type ?? "-"}
                  detail={topYtdRow ? formatYuanAsWanUnit(topYtdRow.total_pnl) : "无明细"}
                  valueVariant="text"
                  tone={toneFromSigned(topYtdRow?.total_pnl)}
                />
                <KpiCard
                  label="最大占比"
                  value={formatRatioPct(topYtdRow?.proportion)}
                  detail={topYtdRow?.business_type ?? "无明细"}
                />
              </>
            ) : (
              <>
                <KpiCard
                  label="报表日合计损益"
                  value={formatYuanAsWanUnit(formalResult?.summary.total_pnl)}
                  detail={`${formalResult?.report_date ?? selectedReportDate} · formal`}
                  tone={toneFromSigned(formalResult?.summary.total_pnl)}
                />
                <KpiCard
                  label="业务种类行数"
                  value={`${formalRows.length}`}
                  detail={`已追溯损益行 ${formalResult?.summary.traced_pnl_row_count ?? 0}`}
                />
                <KpiCard
                  label="最大损益（行）"
                  value={topFormalRow?.business_type_primary ?? "-"}
                  detail={topFormalRow ? formatYuanAsWanUnit(topFormalRow.total_pnl) : "无明细"}
                  valueVariant="text"
                  tone={toneFromSigned(topFormalRow?.total_pnl)}
                />
                <KpiCard
                  label="未追溯 PnL 行"
                  value={`${formalResult?.summary.untraced_pnl_row_count ?? 0}`}
                  detail="与余额 join 未命中时计数"
                />
              </>
            )}
          </div>

          {viewMode === "ytd" && businessQuery.data ? (
            <FormalResultMetaPanel
              testId="pnl-by-business-result-meta-panel"
              sections={[
                { key: "by-business-ytd", title: "业务种类损益", meta: businessQuery.data.result_meta },
              ]}
            />
          ) : null}
          {viewMode === "formal" && formalBusinessQuery.data ? (
            <FormalResultMetaPanel
              testId="pnl-by-business-result-meta-panel"
              sections={[
                { key: "by-business-formal", title: "业务种类损益（formal）", meta: formalBusinessQuery.data.result_meta },
              ]}
            />
          ) : null}

          {viewMode === "ytd" ? (
            <>
              <SectionLead
                eyebrow="Business Type"
                title={`${selectedYear} 年累计明细`}
                description="表中利息至合计损益为万元（接口为元÷1万）；日均(亿元)与日均分析同源（区间年初至今）；「非底层投资资产」父级日均由下列细类目相加。年化收益率为（累计损益÷同区间日均余额）×（365÷自然日数，含首尾），与日均列同源；无日均或区间不可算时显示「-」。口径提示：同一资产在 ZQTZ 规则下可同时命中父类「非底层投资资产」与「其中」细类（如证券业资管计划、本币专户/市值法、外币委外、结构化融资（券商）等），故多行损益金额可能重叠展示——核对「证券业资管」量级时宜看该行及同前缀下的细分行，勿与父级简单相加以免重复。表末「父级汇总」仅对父级行求和（排除「其中」细分），占比与收益率列不宜相加故置「—」。"
              />
              <BusinessRowsTable
                rows={ytdRows}
                adbAvgByBusinessType={adbAvgByBusinessType}
                ytdCalendarDays={ytdCalendarDays}
              />
            </>
          ) : (
            <>
              <SectionLead
                eyebrow="Business Type"
                title={`${selectedReportDate} 单日 formal 明细`}
                description="与 GET /api/pnl/by-business 一致：来自 fact_formal_pnl_fi / fact_nonstd_pnl_bridge 与 fact_formal_zqtz_balance_daily 的 join 聚合。规模列为当日余额合计（亿元）；表内收益率为后端 total_pnl/scale×100（百分数点）。与「年累计（YTD）」视图的拆桶与累加方式不同，勿混读。"
              />
              <FormalBusinessRowsTable rows={formalRows} />
            </>
          )}
        </section>
      </AsyncSection>
    </main>
  );
}
