import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../api/client";
import type { ResultMeta } from "../../api/contracts";
import { apiQueryKeys } from "../../api/queryKeys";
import { KpiCard } from "../../components/KpiCard";
import { PageDecisionHero } from "../../components/page/PagePrimitives";
import { tableShellStyle, tableStyle, tdStyle, thStyle } from "../../components/page/pageStyles";
import type { CreditSpreadMigrationResponse } from "../bond-analytics/types";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { limitTone, limitToneToKpi, type LimitTone } from "../workbench/components/kpiFormat";
import { displayStr, formatConcentrationPercent, parseRatio } from "./concentrationFormat";

import "./ConcentrationMonitorPage.css";

/** 前端展示用限额常量；与后端口径无关。 */
const LIMITS = {
  issuer_single_max: 0.1,
  issuer_top5_max: 0.4,
  hhi_warning: 0.15,
  below_aa_max: 0.2,
} as const;

const CREDIT_SPREAD_MIGRATION_API = "/api/bond-analytics/credit-spread-migration";

function resultMetaBasisLabel(value: ResultMeta["basis"]): string {
  if (value === "formal") return "正式口径";
  if (value === "scenario") return "情景口径";
  if (value === "analytical") return "分析口径";
  if (value === "mock") return "演示口径";
  return value;
}

function resultMetaQualityLabel(value: ResultMeta["quality_flag"]): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return value;
}

function limitStatusText(tone: LimitTone, missing: boolean): string {
  if (missing) {
    return "暂无数据";
  }
  if (tone === "breach") {
    return "超限";
  }
  if (tone === "near") {
    return "接近限额";
  }
  return "正常";
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
      <h3 className="concentration-monitor-page__panel-title">{title}</h3>
      {m ? (
        <p className="concentration-monitor-page__panel-meta concentration-monitor-page__tabular">
          HHI {displayStr(m.hhi)} · 前五 {displayStr(m.top5_concentration)}
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
                <td colSpan={3} style={tdStyle} className="concentration-monitor-page__empty-cell">
                  暂无明细
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={`${metricsKey}-${row.name}`}>
                  <td style={tdStyle}>{row.name}</td>
                  <td style={tdStyle} className="concentration-monitor-page__tabular">
                    {displayStr(row.weight)}
                  </td>
                  <td style={tdStyle} className="concentration-monitor-page__tabular">
                    {displayStr(row.market_value)}
                  </td>
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
    queryKey: apiQueryKeys.bondAnalyticsCreditSpreadMigration(client.mode, reportDate),
    queryFn: () => client.getBondAnalyticsCreditSpreadMigration(reportDate),
    enabled: Boolean(reportDate),
    retry: false,
  });

  const credit = creditQuery.data?.result;
  const creditMeta = creditQuery.data?.result_meta;
  const issuer = credit?.concentration_by_issuer;
  const maxSingleWeight = parseRatio(issuer?.top_items?.[0]?.weight);
  const top5 = parseRatio(issuer?.top5_concentration);
  const hhi = parseRatio(issuer?.hhi);
  const belowAa = parseRatio(credit?.rating_aa_and_below_weight);
  const belowAaMissing = belowAa === null;

  const limitRows = useMemo(() => {
    const top1w = issuer?.top_items?.[0]?.weight;
    return [
      {
        label: "单一发行人占比",
        currentDisplay: top1w ? formatConcentrationPercent(top1w) : "—",
        currentNum: maxSingleWeight,
        limitDisplay: String(LIMITS.issuer_single_max),
        tone: limitTone(maxSingleWeight, LIMITS.issuer_single_max),
      },
      {
        label: "发行人前五集中度",
        currentDisplay: formatConcentrationPercent(issuer?.top5_concentration),
        currentNum: top5,
        limitDisplay: String(LIMITS.issuer_top5_max),
        tone: limitTone(top5, LIMITS.issuer_top5_max),
      },
      {
        label: "发行人 HHI",
        currentDisplay: formatConcentrationPercent(issuer?.hhi),
        currentNum: hhi,
        limitDisplay: String(LIMITS.hhi_warning),
        tone: limitTone(hhi, LIMITS.hhi_warning),
      },
      {
        label: "评级 AA 及以下占比",
        currentDisplay:
          credit?.rating_aa_and_below_weight !== undefined && credit.rating_aa_and_below_weight != null
            ? formatConcentrationPercent(credit.rating_aa_and_below_weight)
            : "—",
        currentNum: belowAa,
        limitDisplay: String(LIMITS.below_aa_max),
        tone: belowAaMissing ? ("ok" as const) : limitTone(belowAa, LIMITS.below_aa_max),
        missingData: belowAaMissing,
      },
    ];
  }, [
    belowAa,
    belowAaMissing,
    credit?.rating_aa_and_below_weight,
    hhi,
    issuer?.hhi,
    issuer?.top5_concentration,
    issuer?.top_items,
    maxSingleWeight,
    top5,
  ]);

  return (
    <section className="concentration-monitor-page" data-testid="concentration-monitor-page">
      <PageDecisionHero
        testId="concentration-monitor-hero"
        titleTestId="concentration-monitor-page-title"
        questionTestId="concentration-monitor-page-subtitle"
        title="持仓集中度监控"
        eyebrow="风险"
        className="concentration-monitor-page__hero"
        reportDateSlot={
          reportDate ? (
            <span>
              报告日 <strong className="concentration-monitor-page__tabular">{reportDate}</strong>
            </span>
          ) : null
        }
        businessQuestion="集中展示信用债发行人、行业、评级与期限的分项集中度，并对照本页展示用限额阈值；浏览器端仅做展示对照，不做组合层面金融重算。"
      />

      <div className="concentration-monitor-page__control-bar">
        <label>
          <span className="concentration-monitor-page__control-label">报告日</span>
          <select
            aria-label="concentration-monitor-report-date"
            value={reportDate}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            className="concentration-monitor-page__control-select"
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
          <span className="concentration-monitor-page__url-hint">
            已由 URL 参数固定报告日
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
            {creditMeta ? (
              <div
                data-testid="concentration-monitor-contract-status"
                className="concentration-monitor-page__contract-status"
                title={`${CREDIT_SPREAD_MIGRATION_API} · ${creditMeta.result_kind}`}
              >
                <div className="concentration-monitor-page__contract-title">候选指标</div>
                <strong className="concentration-monitor-page__contract-code">
                  PAGE-CONTRACT-PENDING:/concentration-monitor
                </strong>
                <div className="concentration-monitor-page__contract-grid">
                  <span>正式可用：{creditMeta.formal_use_allowed ? "是" : "否"}</span>
                  <span>口径：{resultMetaBasisLabel(creditMeta.basis)}</span>
                  <span>质量：{resultMetaQualityLabel(creditMeta.quality_flag)}</span>
                  <span>结果类型：{creditMeta.result_kind}</span>
                  <span>日期基准：{creditMeta.date_basis ?? "—"}</span>
                  <span>使用表：{creditMeta.tables_used?.join(", ") || "—"}</span>
                  <span>证据行：{creditMeta.evidence_rows ?? "—"}</span>
                </div>
              </div>
            ) : null}

            {belowAaMissing ? (
              <p className="concentration-monitor-page__limit-lead">
                评级 AA 及以下占比暂未返回，限额对照行仅展示阈值。
              </p>
            ) : null}

            <div data-testid="concentration-monitor-kpi-grid" className="concentration-monitor-page__summary-grid">
              <KpiCard
                title="发行人 HHI 指数"
                value={formatConcentrationPercent(issuer?.hhi)}
                detail="concentration_by_issuer.hhi"
                tone={limitToneToKpi(limitTone(parseRatio(issuer?.hhi), LIMITS.hhi_warning))}
              />
              <KpiCard
                title="发行人前五集中度"
                value={formatConcentrationPercent(issuer?.top5_concentration)}
                detail="concentration_by_issuer.top5_concentration"
                tone={limitToneToKpi(limitTone(parseRatio(issuer?.top5_concentration), LIMITS.issuer_top5_max))}
              />
              <KpiCard
                title="信用债占比"
                value={formatConcentrationPercent(credit.credit_weight)}
                detail="credit_weight"
                tone={limitToneToKpi(limitTone(parseRatio(credit.credit_weight), 0.85))}
              />
              <KpiCard
                title="评级 AA 及以下占比"
                value={formatConcentrationPercent(credit.rating_aa_and_below_weight)}
                detail="rating_aa_and_below_weight"
                tone={limitToneToKpi(
                  belowAaMissing ? "ok" : limitTone(belowAa, LIMITS.below_aa_max),
                )}
              />
            </div>

            <h2 className="concentration-monitor-page__block-title">分项集中度（前列市值）</h2>
            <div className="concentration-monitor-page__grid-2x2">
              <ConcentrationTable title="发行人集中度" metricsKey="concentration_by_issuer" data={credit} />
              <ConcentrationTable title="行业集中度" metricsKey="concentration_by_industry" data={credit} />
              <ConcentrationTable title="评级分布" metricsKey="concentration_by_rating" data={credit} />
              <ConcentrationTable title="期限分布" metricsKey="concentration_by_tenor" data={credit} />
            </div>

            <h2 className="concentration-monitor-page__block-title">限额预警（展示对照）</h2>
            <p className="concentration-monitor-page__limit-lead">
              超限标红，达到限额 80% 以上未超限标黄。阈值为本页常量，非后端下发。
            </p>
            <div style={tableShellStyle} className="concentration-monitor-page__limit-table-shell">
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
                    const statusText = limitStatusText(row.tone, Boolean(missing));
                    return (
                      <tr key={row.label}>
                        <td style={tdStyle}>{row.label}</td>
                        <td
                          style={tdStyle}
                          className="concentration-monitor-page__limit-cell concentration-monitor-page__tabular"
                          data-tone={missing ? undefined : row.tone}
                          data-missing={missing ? "true" : undefined}
                        >
                          {row.currentDisplay}
                        </td>
                        <td style={tdStyle} className="concentration-monitor-page__tabular">
                          {row.limitDisplay}
                        </td>
                        <td
                          style={tdStyle}
                          className="concentration-monitor-page__limit-status"
                          data-tone={missing ? undefined : row.tone}
                          data-missing={missing ? "true" : undefined}
                        >
                          {statusText}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <footer
              className="concentration-monitor-page__evidence-footer"
              title={CREDIT_SPREAD_MIGRATION_API}
              data-testid="concentration-monitor-evidence-footer"
            >
              接口路径 {CREDIT_SPREAD_MIGRATION_API}
            </footer>
          </>
        ) : null}
      </AsyncSection>
    </section>
  );
}
