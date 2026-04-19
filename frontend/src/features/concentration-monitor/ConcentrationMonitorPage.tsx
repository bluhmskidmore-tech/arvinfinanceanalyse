import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import type { Numeric } from "../../api/contracts";
import { useApiClient } from "../../api/client";
import type { CreditSpreadMigrationResponse } from "../bond-analytics/types";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../workbench/components/KpiCard";
import {
  formatRatioAsPercent,
  limitTone,
  limitToneToKpi,
  type LimitTone,
} from "../workbench/components/kpiFormat";

/** 前端展示用限额常量；与后端口径无关。 */
const LIMITS = {
  issuer_single_max: 0.1,
  issuer_top5_max: 0.4,
  hhi_warning: 0.15,
  below_aa_max: 0.2,
} as const;

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
} as const;

const controlBarStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: 12,
  alignItems: "center",
  marginBottom: 20,
} as const;

const controlStyle = {
  minWidth: 180,
  padding: "10px 12px",
  borderRadius: 12,
  border: "1px solid #d7dfea",
  background: "#ffffff",
  color: "#162033",
} as const;

const tableShellStyle = {
  overflowX: "auto",
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
  marginTop: 0,
} as const;

const tableStyle = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 13,
} as const;

const thStyle = {
  textAlign: "left" as const,
  padding: "10px 12px",
  borderBottom: "1px solid #e4ebf5",
  color: "#5c6b82",
  fontSize: 13,
};

const tdStyle = {
  padding: "12px",
  borderBottom: "1px solid #eef2f7",
  color: "#162033",
};

const blockTitleStyle = {
  margin: "24px 0 0",
  fontSize: 16,
  fontWeight: 600,
  color: "#162033",
} as const;

const grid2x2Style = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: 18,
  marginTop: 16,
} as const;

const panelTitleStyle = {
  margin: "0 0 8px",
  fontSize: 14,
  fontWeight: 600,
  color: "#162033",
} as const;

function displayStr(value: string | Numeric | undefined) {
  if (value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "object" && value !== null && "display" in value) {
    return value.display || "—";
  }
  return String(value);
}

/** 仅用于与展示限额比较，不参与组合指标重算。 */
function parseRatio(value: string | Numeric | undefined): number | null {
  if (value === undefined || value === "") {
    return null;
  }
  if (typeof value === "object" && value !== null && "raw" in value) {
    const r = value.raw;
    return r !== null && Number.isFinite(r) ? r : null;
  }
  const n = Number.parseFloat(value);
  return Number.isFinite(n) ? n : null;
}

function toneColor(tone: LimitTone) {
  if (tone === "breach") {
    return "#b74c45";
  }
  if (tone === "near") {
    return "#c9a227";
  }
  return "#162033";
}

function toneBackground(tone: LimitTone) {
  if (tone === "breach") {
    return "#fff0f0";
  }
  if (tone === "near") {
    return "#fffbeb";
  }
  return "transparent";
}

function ConcentrationTable({
  title,
  metricsKey,
  data,
}: {
  title: string;
  metricsKey: keyof Pick<
    CreditSpreadMigrationResponse,
    | "concentration_by_issuer"
    | "concentration_by_industry"
    | "concentration_by_rating"
    | "concentration_by_tenor"
  >;
  data: CreditSpreadMigrationResponse | undefined;
}) {
  const m = data?.[metricsKey];
  const rows = m?.top_items ?? [];

  return (
    <div>
      <h3 style={panelTitleStyle}>{title}</h3>
      {m ? (
        <p style={{ margin: "0 0 8px", fontSize: 12, color: "#8090a8" }}>
          HHI {displayStr(m.hhi)} · Top5 {displayStr(m.top5_concentration)}
        </p>
      ) : null}
      <div style={tableShellStyle}>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>名称</th>
              <th style={thStyle}>权重</th>
              <th style={thStyle}>市值</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={3} style={{ ...tdStyle, color: "#8090a8" }}>
                  暂无明细
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={`${metricsKey}-${row.name}`}>
                  <td style={tdStyle}>{row.name}</td>
                  <td style={tdStyle}>{displayStr(row.weight)}</td>
                  <td style={tdStyle}>{displayStr(row.market_value)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ConcentrationMonitorPage() {
  const client = useApiClient();
  const [searchParams] = useSearchParams();
  const explicitReportDate = searchParams.get("report_date")?.trim() || "";

  const datesQuery = useQuery({
    queryKey: ["concentration-monitor", "bond-analytics-dates", client.mode],
    queryFn: () => client.getBondAnalyticsDates(),
    retry: false,
  });

  const resolvedFromApi = datesQuery.data?.result.report_dates[0] ?? "";
  const dateOptions = useMemo(() => {
    const reportDates = datesQuery.data?.result.report_dates ?? [];
    const opts = [...reportDates];
    if (explicitReportDate && !opts.includes(explicitReportDate)) {
      return [explicitReportDate, ...opts];
    }
    return opts;
  }, [datesQuery.data?.result.report_dates, explicitReportDate]);

  const [selectedReportDate, setSelectedReportDate] = useState("");

  const reportDate = useMemo(() => {
    if (explicitReportDate) {
      return explicitReportDate;
    }
    return selectedReportDate || resolvedFromApi;
  }, [explicitReportDate, resolvedFromApi, selectedReportDate]);

  const datesBlockingError = datesQuery.isError && !reportDate;
  const datesEmpty =
    !explicitReportDate &&
    !datesQuery.isLoading &&
    !datesBlockingError &&
    (datesQuery.data?.result.report_dates.length ?? 0) === 0;

  const creditQuery = useQuery({
    queryKey: ["concentration-monitor", "credit-spread-migration", reportDate],
    queryFn: async (): Promise<CreditSpreadMigrationResponse> => {
      const envelope = await client.getBondAnalyticsCreditSpreadMigration(reportDate);
      return envelope.result;
    },
    enabled: Boolean(reportDate),
    retry: false,
  });

  const credit = creditQuery.data;
  const issuer = credit?.concentration_by_issuer;
  const maxSingleWeight = parseRatio(issuer?.top_items?.[0]?.weight);
  const top5 = parseRatio(issuer?.top5_concentration);
  const hhi = parseRatio(issuer?.hhi);
  const belowAa = parseRatio(credit?.rating_aa_and_below_weight);

  const limitRows = useMemo(() => {
    const top1w = issuer?.top_items?.[0]?.weight;
    return [
      {
        label: "单一发行人占比",
        currentDisplay: top1w ? displayStr(top1w) : "—",
        currentNum: maxSingleWeight,
        limitDisplay: String(LIMITS.issuer_single_max),
        tone: limitTone(maxSingleWeight, LIMITS.issuer_single_max),
      },
      {
        label: "发行人 Top5 集中度",
        currentDisplay: displayStr(issuer?.top5_concentration),
        currentNum: top5,
        limitDisplay: String(LIMITS.issuer_top5_max),
        tone: limitTone(top5, LIMITS.issuer_top5_max),
      },
      {
        label: "发行人 HHI",
        currentDisplay: displayStr(issuer?.hhi),
        currentNum: hhi,
        limitDisplay: String(LIMITS.hhi_warning),
        tone: limitTone(hhi, LIMITS.hhi_warning),
      },
      {
        label: "评级 AA 及以下占比",
        currentDisplay:
          credit?.rating_aa_and_below_weight !== undefined && credit.rating_aa_and_below_weight != null
            ? displayStr(credit.rating_aa_and_below_weight)
            : "—",
        currentNum: belowAa,
        limitDisplay: String(LIMITS.below_aa_max),
        tone:
          belowAa === null
            ? ("ok" as const)
            : limitTone(belowAa, LIMITS.below_aa_max),
        missingData: belowAa === null,
        note:
          belowAa === null
            ? "后端未返回 rating_aa_and_below_weight，仅展示限额阈值。"
            : undefined,
      },
    ];
  }, [
    belowAa,
    credit?.rating_aa_and_below_weight,
    hhi,
    issuer?.hhi,
    issuer?.top5_concentration,
    issuer?.top_items,
    maxSingleWeight,
    top5,
  ]);

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
          持仓集中度监控
        </h1>
        <p
          style={{
            marginTop: 10,
            marginBottom: 0,
            maxWidth: 860,
            color: "#5c6b82",
            fontSize: 15,
            lineHeight: 1.75,
          }}
        >
          集中度与分项明细来自{" "}
          <code style={{ fontSize: 13 }}>/api/bond-analytics/credit-spread-migration</code>
          ；浏览器端只做展示与限额对照，不做组合层面的金融重算。
        </p>
      </div>

      <div style={controlBarStyle}>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: "#5c6b82" }}>报告日</span>
          <select
            aria-label="concentration-monitor-report-date"
            value={reportDate}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            style={controlStyle}
            disabled={Boolean(explicitReportDate)}
          >
            {dateOptions.length === 0 ? (
              <option value="">—</option>
            ) : (
              dateOptions.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))
            )}
          </select>
        </label>
        {explicitReportDate ? (
          <span style={{ alignSelf: "flex-end", color: "#8090a8", fontSize: 13 }}>
            已由 URL <code style={{ fontSize: 12 }}>?report_date=</code> 固定
          </span>
        ) : null}
      </div>

      <AsyncSection
        title="集中度与限额"
        isLoading={datesQuery.isLoading || creditQuery.isLoading}
        isError={datesBlockingError || creditQuery.isError}
        isEmpty={datesEmpty}
        onRetry={() => {
          void datesQuery.refetch();
          void creditQuery.refetch();
        }}
      >
        {credit ? (
          <>
            <div data-testid="concentration-monitor-kpi-grid" style={summaryGridStyle}>
              <KpiCard
                title="发行人 HHI 指数"
                value={formatRatioAsPercent(displayStr(issuer?.hhi))}
                detail="来自 concentration_by_issuer.hhi。"
                tone={limitToneToKpi(limitTone(parseRatio(issuer?.hhi), LIMITS.hhi_warning))}
              />
              <KpiCard
                title="发行人 Top5 集中度"
                value={formatRatioAsPercent(displayStr(issuer?.top5_concentration))}
                detail="来自 concentration_by_issuer.top5_concentration。"
                tone={limitToneToKpi(limitTone(parseRatio(issuer?.top5_concentration), LIMITS.issuer_top5_max))}
              />
              <KpiCard
                title="信用债占比"
                value={formatRatioAsPercent(displayStr(credit.credit_weight))}
                detail="来自 credit_weight（信用子集相对组合的权重）。"
                tone={limitToneToKpi(limitTone(parseRatio(credit.credit_weight), 0.85))}
              />
              <KpiCard
                title="评级 AA 及以下占比"
                value={formatRatioAsPercent(displayStr(credit.rating_aa_and_below_weight))}
                detail="rating_aa_and_below_weight（信用债 AA 及以下市值 / 组合总市值）。"
                tone={limitToneToKpi(
                  belowAa === null ? "ok" : limitTone(belowAa, LIMITS.below_aa_max),
                )}
              />
            </div>

            <h2 style={blockTitleStyle}>分项集中度（Top 市值）</h2>
            <div style={grid2x2Style}>
              <ConcentrationTable title="发行人集中度" metricsKey="concentration_by_issuer" data={credit} />
              <ConcentrationTable title="行业集中度" metricsKey="concentration_by_industry" data={credit} />
              <ConcentrationTable title="评级分布" metricsKey="concentration_by_rating" data={credit} />
              <ConcentrationTable title="期限分布" metricsKey="concentration_by_tenor" data={credit} />
            </div>

            <h2 style={blockTitleStyle}>限额预警（展示对照）</h2>
            <p style={{ margin: "8px 0 0", fontSize: 13, color: "#5c6b82" }}>
              超限标红，达到限额 80% 以上未超限标黄。阈值为本页常量 LIMITS，非后端下发。
            </p>
            <div style={{ ...tableShellStyle, marginTop: 12 }}>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={thStyle}>指标</th>
                    <th style={thStyle}>当前值</th>
                    <th style={thStyle}>限额</th>
                    <th style={thStyle}>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {limitRows.map((row) => {
                    const missing = "missingData" in row && row.missingData;
                    const statusText = missing
                      ? "暂无数据"
                      : row.tone === "breach"
                        ? "超限"
                        : row.tone === "near"
                          ? "接近限额"
                          : "正常";
                    const cellColor = missing ? "#5c6b82" : toneColor(row.tone);
                    const cellBg = missing ? "#f6f9fc" : toneBackground(row.tone);
                    return (
                      <tr key={row.label}>
                        <td style={tdStyle}>{row.label}</td>
                        <td
                          style={{
                            ...tdStyle,
                            color: cellColor,
                            background: cellBg,
                            fontWeight: !missing && row.tone === "breach" ? 600 : 400,
                          }}
                        >
                          {row.currentDisplay}
                          {"note" in row && row.note ? (
                            <span style={{ display: "block", fontSize: 11, color: "#8090a8" }}>
                              {row.note}
                            </span>
                          ) : null}
                        </td>
                        <td style={tdStyle}>{row.limitDisplay}</td>
                        <td style={{ ...tdStyle, color: cellColor }}>{statusText}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </AsyncSection>
    </section>
  );
}
