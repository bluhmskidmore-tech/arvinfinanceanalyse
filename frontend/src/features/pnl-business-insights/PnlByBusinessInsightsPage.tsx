import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../api/client";
import type {
  PnlByBusinessConcentrationRow,
  PnlByBusinessNegativeFtpPersistenceRow,
  PnlByBusinessShareDriftRow,
} from "../../api/contracts";
import {
  controlBarStyle,
  summaryGridStyle,
  tableShellStyle,
  tableStyle,
  tdStyle,
  thStyle,
} from "../../components/page/pageStyles";
import { KpiCard } from "../../components/KpiCard";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { designTokens } from "../../theme/designSystem";
import { shellTokens } from "../../theme/tokens";
import { CapitalEfficiencyQuadrantPanel } from "./CapitalEfficiencyQuadrantPanel";
import { UntracedReconciliationTrendPanel } from "./UntracedReconciliationTrendPanel";

const DISCLAIMER_TEXT =
  "本页指标为候选分析（status=candidate），仅供内部参考，不构成正式业务结论；最终审批需业务owner确认后方可用于正式汇报。";

const RECONCILIATION_NOTE_TEXT =
  "以下为formal对账诊断趋势，反映的是数据链路完整性问题，不是业务贡献或拖累结论，不构成资源配置或业务评价依据。";

const NEGATIVE_FTP_WARN_THRESHOLD_PCT = 50;

const controlStyle = {
  minWidth: 140,
  padding: "10px 12px",
  borderRadius: designTokens.radius.md,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: shellTokens.colorBgSurface,
  color: designTokens.color.neutral[900],
} as const;

const disclaimerStyle = {
  margin: "0 0 20px",
  padding: 16,
  borderRadius: designTokens.radius.md,
  border: `1px solid ${designTokens.color.danger[200]}`,
  background: designTokens.color.danger[50],
  color: designTokens.color.neutral[800],
} as const;

const contractStatusStyle = {
  margin: "0 0 20px",
  padding: 14,
  borderRadius: designTokens.radius.md,
  border: `1px solid ${designTokens.color.warning[200]}`,
  background: designTokens.color.warning[50],
  color: designTokens.color.neutral[800],
} as const;

const contractStatusGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "8px 16px",
  marginTop: 10,
  fontSize: 12,
  lineHeight: 1.6,
} as const;

const unapprovedBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 10px",
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 700,
  letterSpacing: "0.02em",
  background: designTokens.color.danger[100],
  color: designTokens.color.danger[700],
} as const;

const blockTitleStyle = {
  margin: "28px 0 4px",
  fontSize: 16,
  fontWeight: 600,
  color: designTokens.color.neutral[900],
} as const;

const blockDescriptionStyle = {
  margin: "0 0 12px",
  fontSize: 13,
  color: designTokens.color.neutral[600],
} as const;

const emptyStateStyle = {
  padding: 16,
  borderRadius: designTokens.radius.md,
  border: `1px dashed ${designTokens.color.neutral[200]}`,
  color: designTokens.color.neutral[600],
  fontSize: 13,
} as const;

// The reconciliation-diagnostics block below is a formal data-lineage
// completeness observation, not a business-analysis conclusion like the
// four blocks above it. Its divider/band/title are intentionally styled in
// plain neutral gray (no danger/warning/KPI accent colors) so it cannot be
// mistaken for a business warning or read together with the business blocks.
const reconciliationDividerStyle = {
  margin: "40px 0 0",
  border: "none",
  borderTop: `1px solid ${designTokens.color.neutral[300]}`,
} as const;

const reconciliationSectionStyle = {
  margin: "24px 0 0",
  padding: 20,
  borderRadius: designTokens.radius.md,
  background: designTokens.color.neutral[50],
  border: `1px solid ${designTokens.color.neutral[200]}`,
} as const;

const reconciliationEyebrowStyle = {
  display: "inline-block",
  margin: "0 0 8px",
  padding: "2px 8px",
  borderRadius: 999,
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: "0.04em",
  color: designTokens.color.neutral[600],
  background: designTokens.color.neutral[100],
  border: `1px solid ${designTokens.color.neutral[200]}`,
} as const;

const reconciliationTitleStyle = {
  margin: "0 0 4px",
  fontSize: 15,
  fontWeight: 600,
  color: designTokens.color.neutral[700],
} as const;

const reconciliationNoteStyle = {
  margin: "0 0 16px",
  fontSize: 13,
  color: designTokens.color.neutral[600],
  lineHeight: 1.6,
} as const;

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
      <div style={emptyStateStyle} data-testid="pnl-by-business-insights-share-drift-empty">
        上一年无数据，无法计算漂移。
      </div>
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
    <section>
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{
            margin: 0,
            fontSize: 32,
            fontWeight: 600,
            letterSpacing: "-0.03em",
          }}
        >
          业务种类候选分析
        </h1>
        <p
          style={{
            marginTop: 10,
            marginBottom: 0,
            maxWidth: 860,
            color: designTokens.color.neutral[600],
            fontSize: 15,
            lineHeight: 1.75,
          }}
        >
          集中度、负FTP持续性与份额漂移来自{" "}
          <code style={{ fontSize: 13 }}>/api/pnl/by-business-candidate-insights</code>
          ；这是对 <code style={{ fontSize: 13 }}>pnl.by_business_ytd</code> /{" "}
          <code style={{ fontSize: 13 }}>pnl.by_business_monthly</code> 的候选再聚合，浏览器端只做展示与排序，不做正式口径重算。
        </p>
      </div>

      <div style={disclaimerStyle} data-testid="pnl-by-business-insights-disclaimer">
        {DISCLAIMER_TEXT}
      </div>

      <div style={controlBarStyle}>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: designTokens.color.neutral[600] }}>年份</span>
          <input
            aria-label="pnl-by-business-insights-year"
            type="number"
            value={year}
            onChange={(event) => setYear(Number(event.target.value) || year)}
            style={controlStyle}
          />
        </label>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: designTokens.color.neutral[600] }}>报告日</span>
          <input
            aria-label="pnl-by-business-insights-as-of-date"
            type="date"
            value={asOfDate}
            onChange={(event) => setAsOfDate(event.target.value)}
            style={controlStyle}
          />
        </label>
      </div>

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
              <div data-testid="pnl-by-business-insights-contract-status" style={contractStatusStyle}>
                <div style={{ fontSize: 13, fontWeight: 600, display: "flex", alignItems: "center", gap: 10 }}>
                  <span>候选指标 · 非正式结论</span>
                  {!meta.formal_use_allowed ? (
                    <span data-testid="pnl-by-business-insights-unapproved-badge" style={unapprovedBadgeStyle}>
                      未审批
                    </span>
                  ) : null}
                </div>
                <div style={contractStatusGridStyle}>
                  <span>正式可用: {meta.formal_use_allowed ? "是" : "否"}</span>
                  <span>口径 {meta.basis}</span>
                  <span>数据截至 {meta.resolved_report_date ?? result.as_of_date}</span>
                  <span>结果类型 {meta.result_kind}</span>
                  <span>使用表 {meta.tables_used?.join(", ") || "—"}</span>
                </div>
              </div>
            ) : null}

            <div data-testid="pnl-by-business-insights-concentration-kpis" style={summaryGridStyle}>
              <KpiCard
                title="业务种类集中度 HHI"
                value={formatPct(concentration?.hhi_pct)}
                detail="来自 concentration.hhi_pct。"
              />
              <KpiCard
                title={`前${concentration?.top_n ?? "N"}大占比合计`}
                value={formatPct(concentration?.top_n_share_pct)}
                detail="来自 concentration.top_n_share_pct。"
              />
            </div>

            <h2 style={blockTitleStyle}>业务种类集中度</h2>
            <p style={blockDescriptionStyle}>按占比降序列出各业务种类在 YTD 日均规模中的份额。</p>
            <ConcentrationTable rows={concentration?.rows ?? []} />

            <h2 style={blockTitleStyle}>负FTP持续性</h2>
            <p style={blockDescriptionStyle}>
              近 {negativeFtp?.lookback_months ?? "—"} 个月（
              {negativeFtp?.window_start_month ?? "—"} 至 {negativeFtp?.window_end_month ?? "—"}）负FTP月份占比，占比≥
              {NEGATIVE_FTP_WARN_THRESHOLD_PCT}% 的行已标黄提示。
            </p>
            <NegativeFtpPersistenceTable rows={negativeFtp?.rows ?? []} />

            <h2 style={blockTitleStyle}>份额漂移</h2>
            <p style={blockDescriptionStyle}>
              对比 {shareDrift?.baseline_year ?? "上一年"}年末（{shareDrift?.baseline_as_of_date ?? "—"}）基准份额，按漂移绝对值降序排列。
            </p>
            <ShareDriftTable
              rows={shareDrift?.rows ?? []}
              baselineAvailable={shareDrift?.baseline_available ?? false}
            />
          </>
        ) : null}
      </AsyncSection>

      <h2 style={blockTitleStyle}>资本效率象限</h2>
      <p style={blockDescriptionStyle}>
        基于 <code style={{ fontSize: 13 }}>/api/pnl/by-business-ytd</code> 已有的 proportion /
        ftp_net_annualized_yield_pct 字段，浏览器端仅做象限归类展示，不重算任何正式口径。
      </p>
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
          <hr style={reconciliationDividerStyle} data-testid="pnl-by-business-insights-reconciliation-divider" />
          <div
            style={reconciliationSectionStyle}
            data-testid="pnl-by-business-insights-reconciliation-section"
          >
            <span style={reconciliationEyebrowStyle}>非业务分析 · 数据链路诊断</span>
            <h2 style={reconciliationTitleStyle}>对账健康度诊断（非业务结论）</h2>
            <p style={reconciliationNoteStyle}>{RECONCILIATION_NOTE_TEXT}</p>
            <UntracedReconciliationTrendPanel rows={reconciliationDiagnostics.rows} />
          </div>
        </>
      ) : null}
    </section>
  );
}
