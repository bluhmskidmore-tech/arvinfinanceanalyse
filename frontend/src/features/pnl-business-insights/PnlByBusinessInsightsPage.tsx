import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../api/client";
import type {
  PnlByBusinessConcentrationRow,
  PnlByBusinessNegativeFtpPersistenceRow,
  PnlByBusinessShareDriftRow,
} from "../../api/contracts";
import { tableShellStyle, tableStyle, tdStyle, thStyle } from "../../components/page/pageStyles";
import { FilterBar } from "../../components/FilterBar";
import { KpiCard } from "../../components/KpiCard";
import {
  DataStatusStrip,
  PageDecisionHero,
  PageFilterTray,
  PageSectionLead,
  PageStateSurface,
  PageV2Shell,
} from "../../components/page/PagePrimitives";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { designTokens } from "../../theme/designSystem";
import { CapitalEfficiencyQuadrantPanel } from "./CapitalEfficiencyQuadrantPanel";
import { UntracedReconciliationTrendPanel } from "./UntracedReconciliationTrendPanel";
import "./PnlByBusinessInsightsPage.css";

const DISCLAIMER_TEXT =
  "本页指标为候选分析（status=candidate），仅供内部参考，不构成正式业务结论；最终审批需业务owner确认后方可用于正式汇报。";

const RECONCILIATION_NOTE_TEXT =
  "以下为formal对账诊断趋势，反映的是数据链路完整性问题，不是业务贡献或拖累结论，不构成资源配置或业务评价依据。";

const NEGATIVE_FTP_WARN_THRESHOLD_PCT = 50;

function toNumber(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function formatPct(value: string | null | undefined, digits = 2): string {
  const n = toNumber(value);
  if (n === null) {
    return "—";
  }
  return `${n.toFixed(digits)}%`;
}

function formatSignedPp(value: string | null | undefined, digits = 2): string {
  const n = toNumber(value);
  if (n === null) {
    return "—";
  }
  return `${n > 0 ? "+" : ""}${n.toFixed(digits)}pp`;
}

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function sortConcentrationRows(
  rows: PnlByBusinessConcentrationRow[],
): PnlByBusinessConcentrationRow[] {
  return [...rows].sort((left, right) => (toNumber(right.share_pct) ?? -1) - (toNumber(left.share_pct) ?? -1));
}

function sortNegativeFtpRows(
  rows: PnlByBusinessNegativeFtpPersistenceRow[],
): PnlByBusinessNegativeFtpPersistenceRow[] {
  return [...rows].sort(
    (left, right) =>
      (toNumber(right.negative_ftp_month_share_pct) ?? -1) -
      (toNumber(left.negative_ftp_month_share_pct) ?? -1),
  );
}

function sortShareDriftRows(rows: PnlByBusinessShareDriftRow[]): PnlByBusinessShareDriftRow[] {
  return [...rows].sort(
    (left, right) => Math.abs(toNumber(right.drift_pp) ?? 0) - Math.abs(toNumber(left.drift_pp) ?? 0),
  );
}

function ConcentrationTable({ rows }: { rows: PnlByBusinessConcentrationRow[] }) {
  const sorted = useMemo(() => sortConcentrationRows(rows), [rows]);
  return (
    <div style={tableShellStyle} data-testid="pnl-by-business-insights-concentration-table">
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>业务种类</th>
            <th style={thStyle}>占比</th>
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={2} style={{ ...tdStyle, color: designTokens.color.neutral[500] }}>
                暂无集中度明细
              </td>
            </tr>
          ) : (
            sorted.map((row) => (
              <tr key={row.row_key}>
                <td style={tdStyle}>{row.business_type}</td>
                <td style={tdStyle}>{formatPct(row.share_pct)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function NegativeFtpPersistenceTable({
  rows,
}: {
  rows: PnlByBusinessNegativeFtpPersistenceRow[];
}) {
  const sorted = useMemo(() => sortNegativeFtpRows(rows), [rows]);
  return (
    <div style={tableShellStyle} data-testid="pnl-by-business-insights-negative-ftp-table">
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>业务种类</th>
            <th style={thStyle}>负FTP月份占比</th>
            <th style={thStyle}>最长连续负FTP月数</th>
            <th style={thStyle}>覆盖月份数</th>
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={4} style={{ ...tdStyle, color: designTokens.color.neutral[500] }}>
                暂无负FTP持续性明细
              </td>
            </tr>
          ) : (
            sorted.map((row) => {
              const sharePct = toNumber(row.negative_ftp_month_share_pct);
              const warn = sharePct !== null && sharePct >= NEGATIVE_FTP_WARN_THRESHOLD_PCT;
              return (
                <tr key={row.row_key}>
                  <td style={tdStyle}>{row.business_type}</td>
                  <td
                    style={{
                      ...tdStyle,
                      color: warn ? designTokens.color.warning[700] : tdStyle.color,
                      background: warn ? designTokens.color.warning[50] : undefined,
                      fontWeight: warn ? 700 : undefined,
                    }}
                  >
                    {formatPct(row.negative_ftp_month_share_pct)}
                  </td>
                  <td style={tdStyle}>{row.negative_ftp_longest_streak_months}</td>
                  <td style={tdStyle}>{row.months_observed}</td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

function ShareDriftTable({
  rows,
  baselineAvailable,
}: {
  rows: PnlByBusinessShareDriftRow[];
  baselineAvailable: boolean;
}) {
  if (!baselineAvailable) {
    return (
      <PageStateSurface
        variant="empty"
        testId="pnl-by-business-insights-share-drift-empty"
        title="上一年无数据，无法计算漂移。"
      />
    );
  }

  const sorted = sortShareDriftRows(rows);
  return (
    <div style={tableShellStyle} data-testid="pnl-by-business-insights-share-drift-table">
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>业务种类</th>
            <th style={thStyle}>当前份额</th>
            <th style={thStyle}>基准份额（上一年末）</th>
            <th style={thStyle}>漂移</th>
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={4} style={{ ...tdStyle, color: designTokens.color.neutral[500] }}>
                暂无份额漂移明细
              </td>
            </tr>
          ) : (
            sorted.map((row) => (
              <tr key={row.row_key}>
                <td style={tdStyle}>{row.business_type}</td>
                <td style={tdStyle}>{formatPct(row.current_share_pct)}</td>
                <td style={tdStyle}>{formatPct(row.baseline_share_pct)}</td>
                <td style={tdStyle}>{formatSignedPp(row.drift_pp)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function PnlByBusinessInsightsPage() {
  const client = useApiClient();
  const [year, setYear] = useState<number>(() => new Date().getFullYear());
  const [asOfDate, setAsOfDate] = useState<string>(() => todayIsoDate());

  const insightsQuery = useQuery({
    queryKey: ["pnl-by-business-insights", "candidate", client.mode, year, asOfDate],
    queryFn: () => client.getPnlByBusinessCandidateInsights(year, asOfDate),
    enabled: Boolean(year && asOfDate),
    retry: false,
  });

  const ytdQuery = useQuery({
    queryKey: ["pnl-by-business-insights", "ytd", client.mode, year, asOfDate],
    queryFn: () => client.getPnlByBusinessYtd(year, asOfDate),
    enabled: Boolean(year && asOfDate),
    retry: false,
  });
  const ytdItems = ytdQuery.data?.result?.items ?? [];

  const meta = insightsQuery.data?.result_meta;
  const result = insightsQuery.data?.result;
  const concentration = result?.concentration;
  const negativeFtp = result?.negative_ftp_persistence;
  const shareDrift = result?.share_drift;
  const reconciliationDiagnostics = result?.reconciliation_diagnostics;

  const isEmpty =
    insightsQuery.isSuccess &&
    (concentration?.rows.length ?? 0) === 0 &&
    (negativeFtp?.rows.length ?? 0) === 0 &&
    (shareDrift?.rows.length ?? 0) === 0;

  return (
    <section data-testid="pnl-by-business-insights-page" className="pnl-by-business-insights-page">
      <PageV2Shell testId="pnl-by-business-insights-page-shell">
        <PageDecisionHero
          testId="pnl-by-business-insights-hero"
          titleTestId="pnl-by-business-insights-page-title"
          questionTestId="pnl-by-business-insights-page-subtitle"
          eyebrow="组合工作台 · 候选分析"
          title="业务种类候选分析"
          businessQuestion="当前业务结构是否过度集中、哪些业务长期跑不赢FTP、份额相对上一年末漂移了多少？"
        >
          <PageFilterTray testId="pnl-by-business-insights-filter-tray">
            <FilterBar>
              <label className="pnl-by-business-insights-filter-label">
                年份
                <input
                  aria-label="pnl-by-business-insights-year"
                  type="number"
                  value={year}
                  onChange={(event) => setYear(Number(event.target.value) || year)}
                  className="pnl-by-business-insights-control"
                />
              </label>
              <label className="pnl-by-business-insights-filter-label">
                报告日
                <input
                  aria-label="pnl-by-business-insights-as-of-date"
                  type="date"
                  value={asOfDate}
                  onChange={(event) => setAsOfDate(event.target.value)}
                  className="pnl-by-business-insights-control"
                />
              </label>
            </FilterBar>
          </PageFilterTray>
        </PageDecisionHero>

        <PageStateSurface
          variant="definition-pending"
          testId="pnl-by-business-insights-disclaimer"
          title="候选分析免责声明"
          description={DISCLAIMER_TEXT}
        />

        <AsyncSection
          title="业务种类候选分析"
          isLoading={insightsQuery.isLoading}
          isError={insightsQuery.isError}
          isEmpty={isEmpty}
          onRetry={() => void insightsQuery.refetch()}
        >
          {result ? (
            <>
              {meta ? (
                <DataStatusStrip
                  testId="pnl-by-business-insights-contract-status"
                  className="pnl-by-business-insights-data-status-strip"
                >
                  <div className="pnl-by-business-insights-data-status-strip__head">
                    <span>候选指标 · 非正式结论</span>
                    {!meta.formal_use_allowed ? (
                      <span
                        data-testid="pnl-by-business-insights-unapproved-badge"
                        className="pnl-by-business-insights-unapproved-badge"
                      >
                        未审批
                      </span>
                    ) : null}
                  </div>
                  <div className="pnl-by-business-insights-data-status-strip__grid">
                    <span>正式可用: {meta.formal_use_allowed ? "是" : "否"}</span>
                    <span>口径 {meta.basis}</span>
                    <span>数据截至 {meta.resolved_report_date ?? result.as_of_date}</span>
                    <span>结果类型 {meta.result_kind}</span>
                    <span>使用表 {meta.tables_used?.join(", ") || "—"}</span>
                    <span>浏览器端仅做展示与排序，不做正式口径重算</span>
                  </div>
                </DataStatusStrip>
              ) : null}

              <div className="pnl-by-business-insights-summary-grid" data-testid="pnl-by-business-insights-concentration-kpis">
                <KpiCard
                  label="业务种类集中度 HHI"
                  value={formatPct(concentration?.hhi_pct)}
                  detail="来自 concentration.hhi_pct。"
                />
                <KpiCard
                  label={`前${concentration?.top_n ?? "N"}大占比合计`}
                  value={formatPct(concentration?.top_n_share_pct)}
                  detail="来自 concentration.top_n_share_pct。"
                />
              </div>

              <PageSectionLead
                eyebrow="Concentration"
                title="业务种类集中度"
                description="按占比降序列出各业务种类在 YTD 日均规模中的份额。"
              />
              <ConcentrationTable rows={concentration?.rows ?? []} />

              <PageSectionLead
                eyebrow="Negative FTP"
                title="负FTP持续性"
                description={`近 ${negativeFtp?.lookback_months ?? "—"} 个月（${negativeFtp?.window_start_month ?? "—"} 至 ${negativeFtp?.window_end_month ?? "—"}）负FTP月份占比，占比≥${NEGATIVE_FTP_WARN_THRESHOLD_PCT}% 的行已标黄提示。`}
              />
              <NegativeFtpPersistenceTable rows={negativeFtp?.rows ?? []} />

              <PageSectionLead
                eyebrow="Share Drift"
                title="份额漂移"
                description={`对比 ${shareDrift?.baseline_year ?? "上一年"}年末（${shareDrift?.baseline_as_of_date ?? "—"}）基准份额，按漂移绝对值降序排列。`}
              />
              <ShareDriftTable
                rows={shareDrift?.rows ?? []}
                baselineAvailable={shareDrift?.baseline_available ?? false}
              />
            </>
          ) : null}
        </AsyncSection>

        <PageSectionLead
          eyebrow="Capital Efficiency"
          title="资本效率象限"
          description="基于 /api/pnl/by-business-ytd 已有的 proportion / ftp_net_annualized_yield_pct 字段，浏览器端仅做象限归类展示，不重算任何正式口径。"
        />
        <AsyncSection
          title=""
          isLoading={ytdQuery.isLoading}
          isError={ytdQuery.isError}
          isEmpty={false}
          onRetry={() => void ytdQuery.refetch()}
        >
          <CapitalEfficiencyQuadrantPanel items={ytdItems} />
        </AsyncSection>

        {reconciliationDiagnostics ? (
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
              <UntracedReconciliationTrendPanel rows={reconciliationDiagnostics.rows} />
            </div>
          </>
        ) : null}
      </PageV2Shell>
    </section>
  );
}
