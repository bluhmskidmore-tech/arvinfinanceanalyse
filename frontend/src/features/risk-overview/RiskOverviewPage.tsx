import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactECharts, { type EChartsOption } from "../../lib/echarts";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../api/client";
import { apiQueryKeys } from "../../api/queryKeys";
import { FormalResultMetaPanel } from "../../components/page/FormalResultMetaPanel";
import {
  bondChartMagnitude,
  bondNumericDisplay,
  bondNumericRaw,
} from "../bond-analytics/adapters/bondAnalyticsAdapter";
import type {
  CreditSpreadMigrationResponse,
  KRDCurveRiskResponse,
} from "../bond-analytics/types";
import { designTokens } from "../../theme/designSystem";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../../components/KpiCard";
import type { RiskTensorPayload } from "../../api/contracts";
import {
  formatRatioAsPercent,
  parseDisplayNumber,
  toneFromSignedDisplayString,
} from "../workbench/components/kpiFormat";
import "./RiskOverviewPage.css";

function cellText(value: unknown) {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "object" && value !== null && "display" in value) {
    return bondNumericDisplay(value as Parameters<typeof bondNumericDisplay>[0]);
  }
  return String(value);
}

/** 仅用于 ECharts 轴值解析，不做组合层面的金融重算。 */
function chartMagnitude(value: Parameters<typeof bondChartMagnitude>[0]) {
  return bondChartMagnitude(value);
}

function regulatoryDv01Display(value: RiskTensorPayload["regulatory_dv01"]) {
  if (value === null || value === undefined) {
    return "待接入";
  }
  return bondNumericDisplay(value);
}

function regulatoryDv01Tone(value: RiskTensorPayload["regulatory_dv01"]) {
  if (value === null || value === undefined) {
    return "warning";
  }
  return toneFromSignedDisplayString(bondNumericDisplay(value));
}

export default function RiskOverviewPage() {
  const client = useApiClient();
  const [searchParams] = useSearchParams();
  const explicitReportDate = searchParams.get("report_date")?.trim() || "";
  const [selectedTenor, setSelectedTenor] = useState<string>("");
  const [selectedIssuer, setSelectedIssuer] = useState<string>("");

  const datesQuery = useQuery({
    queryKey: ["risk-overview", "risk-tensor-dates", client.mode],
    queryFn: () => client.getRiskTensorDates(),
    retry: false,
  });

  const blockedReportDates = datesQuery.data?.result.blocked_report_dates ?? [];
  const selectedBlockedReportDate = explicitReportDate
    ? blockedReportDates.find((entry) => entry.report_date === explicitReportDate)
    : undefined;
  const latestBlockedReportDate = [...blockedReportDates].sort((a, b) => b.report_date.localeCompare(a.report_date))[0];
  const highlightedBlockedReportDate = selectedBlockedReportDate ?? latestBlockedReportDate;

  const reportDate = useMemo(() => {
    if (explicitReportDate) {
      return explicitReportDate;
    }
    return datesQuery.data?.result.report_dates[0] ?? "";
  }, [datesQuery.data?.result.report_dates, explicitReportDate]);

  const datesBlockingError = datesQuery.isError && !reportDate;
  const datesEmpty =
    !explicitReportDate &&
    !datesQuery.isLoading &&
    !datesBlockingError &&
    (datesQuery.data?.result.report_dates.length ?? 0) === 0;

  const tensorQuery = useQuery({
    queryKey: ["risk-overview", "risk-tensor", reportDate],
    queryFn: () => client.getRiskTensor(reportDate),
    enabled: Boolean(reportDate),
    retry: false,
  });

  const krdQuery = useQuery({
    queryKey: ["risk-overview", "krd-curve-risk", reportDate],
    queryFn: () => client.getBondAnalyticsKrdCurveRisk(reportDate),
    enabled: Boolean(reportDate),
    retry: false,
  });

  const creditQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsCreditSpreadMigration(client.mode, reportDate),
    queryFn: () => client.getBondAnalyticsCreditSpreadMigration(reportDate),
    enabled: Boolean(reportDate),
    retry: false,
  });

  const tensorResult = tensorQuery.data?.result;
  const tensorEmpty =
    !tensorQuery.isLoading &&
    !tensorQuery.isError &&
    tensorResult !== undefined &&
    tensorResult.bond_count === 0;

  const krd = krdQuery.data?.result as KRDCurveRiskResponse | undefined;
  const credit = creditQuery.data?.result as CreditSpreadMigrationResponse | undefined;

  const krdChartOption = useMemo((): EChartsOption | null => {
    if (!tensorResult) {
      return null;
    }
    const labels = ["1Y", "3Y", "5Y", "7Y", "10Y", "30Y"];
    const keys = [
      "krd_1y",
      "krd_3y",
      "krd_5y",
      "krd_7y",
      "krd_10y",
      "krd_30y",
    ] as const;
    const data = keys.map((k) => chartMagnitude(tensorResult[k]));
    return {
      grid: { left: 52, right: 16, top: 36, bottom: 28 },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
      },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: { color: designTokens.color.neutral[600] },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: designTokens.color.neutral[600] },
        splitLine: { lineStyle: { color: "#eef2f7" } },
      },
      series: [
        {
          type: "bar",
          data,
          itemStyle: { color: designTokens.color.primary[600], borderRadius: [6, 6, 0, 0] },
        },
      ],
    };
  }, [tensorResult]);

  const tenorRows = useMemo(() => krd?.krd_buckets ?? [], [krd?.krd_buckets]);
  const issuerRows = useMemo(
    () => credit?.concentration_by_issuer?.top_items ?? [],
    [credit?.concentration_by_issuer?.top_items],
  );

  useEffect(() => {
    if (tenorRows.length === 0) {
      setSelectedTenor("");
      return;
    }
    const strongest = [...tenorRows].sort(
      (left, right) => chartMagnitude(right.krd) - chartMagnitude(left.krd),
    )[0]?.tenor;
    if (!selectedTenor || !tenorRows.some((row) => row.tenor === selectedTenor)) {
      setSelectedTenor(strongest ?? tenorRows[0]!.tenor);
    }
  }, [selectedTenor, tenorRows]);

  useEffect(() => {
    if (issuerRows.length === 0) {
      setSelectedIssuer("");
      return;
    }
    if (!selectedIssuer || !issuerRows.some((row) => row.name === selectedIssuer)) {
      setSelectedIssuer(issuerRows[0]!.name);
    }
  }, [issuerRows, selectedIssuer]);

  const selectedTenorRow = tenorRows.find((row) => row.tenor === selectedTenor) ?? tenorRows[0];
  const selectedIssuerRow =
    issuerRows.find((row) => row.name === selectedIssuer) ?? issuerRows[0];

  return (
    <section>
      <div className="risk-overview-hero">
        <h1 className="risk-overview-title">
          风险总览
        </h1>
        <p className="risk-overview-description">
          主指标来自正式风险张量接口{" "}
          <code className="risk-overview-api-code">/api/risk/tensor</code>
          （与「风险张量」页同一主链）。下方债券分析物化结果为下钻与补充视图，不在浏览器端做金融重算。
        </p>
      </div>

      <div className="risk-overview-control-bar">
        <div className="risk-overview-report-date-card">
          {datesEmpty ? (
            <span>后端未返回可用风险报告日。</span>
          ) : datesBlockingError ? (
            <span>风险报告日载入失败。</span>
          ) : (
            <>
              报告日：<strong>{reportDate}</strong>
              <span className="risk-overview-report-date-hint">
                （可通过地址栏报告日参数指定）
              </span>
            </>
          )}
          {highlightedBlockedReportDate ? (
            <>
              <br />
              <span data-testid="risk-overview-blocked-dates">
                后端拦截陈旧日期：{blockedReportDates.length} 个。当前提示日期：{" "}
                <strong>{highlightedBlockedReportDate.report_date}</strong>
                {highlightedBlockedReportDate.reason
                  ? ` (${highlightedBlockedReportDate.reason})`
                  : null}
                {selectedBlockedReportDate
                  ? " 当前选择的报告日已被新鲜度校验拦截。"
                  : null}
              </span>
            </>
          ) : null}
        </div>
      </div>

      <div className="risk-overview-section-gap-sm">
        <AsyncSection
          title="正式风险张量（主数据）"
          isLoading={datesQuery.isLoading || tensorQuery.isLoading}
          isError={datesBlockingError || tensorQuery.isError}
          isEmpty={datesEmpty || (!datesBlockingError && tensorEmpty)}
          onRetry={() => {
            void datesQuery.refetch();
            void tensorQuery.refetch();
          }}
        >
          {tensorResult && (
            <>
              <div data-testid="risk-overview-kpi-grid" className="risk-overview-summary-grid">
                <KpiCard
                  title="估值口径 DV01"
                  value={bondNumericDisplay(tensorResult.portfolio_dv01)}
                  detail="portfolio_dv01，持仓估值敏感性口径，非监管限额口径。"
                  tone={toneFromSignedDisplayString(bondNumericDisplay(tensorResult.portfolio_dv01))}
                />
                <KpiCard
                  title="监管口径 DV01"
                  value={regulatoryDv01Display(tensorResult.regulatory_dv01)}
                  detail="后端监管/限额口径字段；不得用估值 DV01 替代。"
                  tone={regulatoryDv01Tone(tensorResult.regulatory_dv01)}
                />
                <KpiCard
                  title="修正久期"
                  value={bondNumericDisplay(tensorResult.portfolio_modified_duration)}
                  detail="portfolio_modified_duration。"
                  unit="年"
                />
                <KpiCard
                  title="CS01"
                  value={bondNumericDisplay(tensorResult.cs01)}
                  detail="cs01（信用 spread 敏感度聚合）。"
                  tone={toneFromSignedDisplayString(bondNumericDisplay(tensorResult.cs01))}
                />
                <KpiCard
                  title="组合凸性"
                  value={bondNumericDisplay(tensorResult.portfolio_convexity)}
                  detail="portfolio_convexity。"
                  tone={toneFromSignedDisplayString(bondNumericDisplay(tensorResult.portfolio_convexity))}
                />
                <KpiCard
                  title="债券只数"
                  value={String(tensorResult.bond_count)}
                  detail="bond_count。"
                  unit="只"
                />
                <KpiCard
                  title="总市值"
                  value={bondNumericDisplay(tensorResult.total_market_value)}
                  detail="total_market_value。"
                  unit="亿"
                  tone={toneFromSignedDisplayString(bondNumericDisplay(tensorResult.total_market_value))}
                />
              </div>

              <h2 className="risk-overview-section-title">
                KRD 分桶（估值 DV01）
              </h2>
              {krdChartOption ? (
                <ReactECharts className="risk-overview-krd-chart" option={krdChartOption} />
              ) : null}

              <h2 className="risk-overview-section-title">
                集中度
              </h2>
              <div className="risk-overview-summary-grid">
                <KpiCard
                  title="发行人 HHI"
                  value={bondNumericDisplay(tensorResult.issuer_concentration_hhi)}
                  detail="issuer_concentration_hhi。"
                  tone={
                    (() => {
                      const n = parseDisplayNumber(bondNumericDisplay(tensorResult.issuer_concentration_hhi));
                      return n != null && n > 0.15 ? "warning" : "default";
                    })()
                  }
                />
                <KpiCard
                  title="前五大权重"
                  value={formatRatioAsPercent(
                    String(bondNumericRaw(tensorResult.issuer_top5_weight)),
                    bondNumericDisplay(tensorResult.issuer_top5_weight),
                  )}
                  detail="issuer_top5_weight。"
                />
              </div>

              <h2 className="risk-overview-section-title">
                流动性缺口（市值）
              </h2>
              <div className="risk-overview-summary-grid">
                <KpiCard
                  title="30 日内到期市值"
                  value={bondNumericDisplay(tensorResult.liquidity_gap_30d)}
                  detail="liquidity_gap_30d。"
                  tone={toneFromSignedDisplayString(bondNumericDisplay(tensorResult.liquidity_gap_30d))}
                />
                <KpiCard
                  title="90 日内到期市值"
                  value={bondNumericDisplay(tensorResult.liquidity_gap_90d)}
                  detail="liquidity_gap_90d。"
                  tone={toneFromSignedDisplayString(bondNumericDisplay(tensorResult.liquidity_gap_90d))}
                />
                <KpiCard
                  title="30 日流动性缺口占比"
                  value={formatRatioAsPercent(
                    String(bondNumericRaw(tensorResult.liquidity_gap_30d_ratio)),
                    bondNumericDisplay(tensorResult.liquidity_gap_30d_ratio),
                  )}
                  detail="liquidity_gap_30d_ratio。"
                  tone={(() => {
                    const n = parseDisplayNumber(bondNumericDisplay(tensorResult.liquidity_gap_30d_ratio));
                    if (n == null) {
                      return "default";
                    }
                    if (n > 0.45) {
                      return "error";
                    }
                    if (n > 0.25) {
                      return "warning";
                    }
                    return "default";
                  })()}
                />
              </div>

              <div
                className={`risk-overview-quality-panel ${
                  tensorResult.quality_flag === "ok" ? "is-ok" : "is-warning"
                }`}
              >
                <div className="risk-overview-quality-title">
                  质量标记：
                  {tensorResult.quality_flag === "ok"
                    ? "正常"
                    : tensorResult.quality_flag === "warning"
                      ? "预警"
                      : tensorResult.quality_flag === "error"
                        ? "错误"
                        : tensorResult.quality_flag === "stale"
                          ? "陈旧"
                          : tensorResult.quality_flag}
                </div>
                {tensorResult.warnings.length === 0 ? (
                  <div className="risk-overview-muted-text">无预警。</div>
                ) : (
                  <ul className="risk-overview-warning-list">
                    {tensorResult.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          )}
        </AsyncSection>
      </div>

      <div className="risk-overview-drill-intro">
        <strong className="risk-overview-strong-text">债券分析下钻与补充</strong>
        ：以下接口来自{" "}
        <code className="risk-overview-api-code risk-overview-api-code--compact">/api/bond-analytics/krd-curve-risk</code> 与{" "}
        <code className="risk-overview-api-code risk-overview-api-code--compact">/api/bond-analytics/credit-spread-migration</code>
        ，用于曲线/KRD 明细与信用利差迁移等物化视角，与主链风险张量并存时可对照阅读。
      </div>

      <div className="risk-overview-section-gap-sm">
        <AsyncSection
          title="利率曲线与 KRD 风险（物化下钻）"
          isLoading={datesQuery.isLoading || krdQuery.isLoading}
          isError={datesBlockingError || krdQuery.isError}
          isEmpty={datesEmpty}
          onRetry={() => {
            void datesQuery.refetch();
            void krdQuery.refetch();
          }}
        >
          <div data-testid="risk-overview-bond-krd-kpi-grid" className="risk-overview-summary-grid">
            <KpiCard
              title="组合久期"
              value={cellText(krd?.portfolio_duration)}
              detail="portfolio_duration，债券分析物化口径。"
              tone={toneFromSignedDisplayString(cellText(krd?.portfolio_duration))}
            />
            <KpiCard
              title="修正久期"
              value={cellText(krd?.portfolio_modified_duration)}
              detail="portfolio_modified_duration。"
              unit="年"
            />
            <KpiCard
              title="估值口径 DV01"
              value={cellText(krd?.portfolio_dv01)}
              detail="portfolio_dv01，债券分析物化口径，非监管限额口径。"
              tone={toneFromSignedDisplayString(cellText(krd?.portfolio_dv01))}
            />
            <KpiCard
              title="凸性"
              value={cellText(krd?.portfolio_convexity)}
              detail="portfolio_convexity。"
              tone={toneFromSignedDisplayString(cellText(krd?.portfolio_convexity))}
            />
          </div>

          {krd && krd.warnings.length > 0 && (
            <div className="risk-overview-warning-panel">
              {krd.warnings.map((w, i) => (
                <div key={i}>{w}</div>
              ))}
            </div>
          )}

          {selectedTenorRow ? (
            <div data-testid="risk-overview-tenor-drill" className="risk-overview-drill-card">
              <div className="risk-overview-drill-title">期限桶下钻</div>
              <div className="risk-overview-drill-description">
                使用债券分析的 `krd_buckets` 读面，先聚焦当前最敏感的期限桶。
              </div>
              <div className="risk-overview-drill-chip-row">
                {tenorRows.map((row) => (
                  <button
                    key={row.tenor}
                    type="button"
                    className="risk-overview-drill-chip"
                    aria-pressed={row.tenor === selectedTenor}
                    onClick={() => setSelectedTenor(row.tenor)}
                  >
                    {row.tenor}
                  </button>
                ))}
              </div>
              <div className="risk-overview-drill-current">
                当前桶：<strong>{selectedTenorRow.tenor}</strong>
              </div>
              <div className="risk-overview-drill-detail">
                KRD：{selectedTenorRow.krd.display} · 估值DV01：{selectedTenorRow.dv01.display} · 市值权重：
                {selectedTenorRow.market_value_weight.display}
              </div>
            </div>
          ) : null}

          <h2 className="risk-overview-block-title">KRD 分桶</h2>
          <div className="risk-overview-table-shell">
            <table className="risk-overview-table">
              <thead>
                <tr>
                  {["期限", "KRD", "DV01（估值）", "市值权重"].map((label) => (
                    <th key={label} className="risk-overview-table-header">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(krd?.krd_buckets ?? []).map((row) => (
                  <tr key={row.tenor}>
                    <td className="risk-overview-table-cell">{row.tenor}</td>
                    <td className="risk-overview-table-cell">{row.krd.display}</td>
                    <td className="risk-overview-table-cell">{row.dv01.display}</td>
                    <td className="risk-overview-table-cell">{row.market_value_weight.display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 className="risk-overview-block-title">情景分析</h2>
          <div className="risk-overview-table-shell">
            <table className="risk-overview-table">
              <thead>
                <tr>
                  {["情景名称", "情景说明", "经济口径损益", "OCI", "TPL"].map((label) => (
                    <th key={label} className="risk-overview-table-header">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(krd?.scenarios ?? []).map((row) => (
                  <tr key={row.scenario_name}>
                    <td className="risk-overview-table-cell">{row.scenario_name}</td>
                    <td className="risk-overview-table-cell">{row.scenario_description}</td>
                    <td className="risk-overview-table-cell">{row.pnl_economic.display}</td>
                    <td className="risk-overview-table-cell">{row.pnl_oci.display}</td>
                    <td className="risk-overview-table-cell">{row.pnl_tpl.display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 className="risk-overview-block-title">资产类别风险汇总</h2>
          <div className="risk-overview-table-shell">
            <table className="risk-overview-table">
              <thead>
                <tr>
                  {["资产类别", "市值", "久期", "DV01（估值）", "权重"].map((label) => (
                    <th key={label} className="risk-overview-table-header">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(krd?.by_asset_class ?? []).map((row) => (
                  <tr key={row.asset_class}>
                    <td className="risk-overview-table-cell">{row.asset_class}</td>
                    <td className="risk-overview-table-cell">{row.market_value.display}</td>
                    <td className="risk-overview-table-cell">{row.duration.display}</td>
                    <td className="risk-overview-table-cell">{row.dv01.display}</td>
                    <td className="risk-overview-table-cell">{row.weight.display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {krd?.computed_at && (
            <p className="risk-overview-computed-at">
              computed_at: {krd.computed_at}
            </p>
          )}
        </AsyncSection>
      </div>

      <div className="risk-overview-section-gap-lg">
        <AsyncSection
          title="信用利差迁移（物化下钻）"
          isLoading={datesQuery.isLoading || creditQuery.isLoading}
          isError={datesBlockingError || creditQuery.isError}
          isEmpty={datesEmpty}
          onRetry={() => {
            void datesQuery.refetch();
            void creditQuery.refetch();
          }}
        >
          <div className="risk-overview-summary-grid">
            <KpiCard
              title="信用债数量"
              value={cellText(credit?.credit_bond_count)}
              detail="credit_bond_count。"
              unit="只"
            />
            <KpiCard
              title="信用债市值"
              value={cellText(credit?.credit_market_value)}
              detail="credit_market_value。"
              tone={toneFromSignedDisplayString(cellText(credit?.credit_market_value))}
            />
            <KpiCard
              title="利差 DV01"
              value={cellText(credit?.spread_dv01)}
              detail="spread_dv01。"
              tone={toneFromSignedDisplayString(cellText(credit?.spread_dv01))}
            />
          </div>

          {credit && credit.warnings.length > 0 && (
            <div className="risk-overview-warning-panel">
              {credit.warnings.map((w, i) => (
                <div key={i}>{w}</div>
              ))}
            </div>
          )}

          {selectedIssuerRow ? (
            <div data-testid="risk-overview-issuer-drill" className="risk-overview-drill-card">
              <div className="risk-overview-drill-title">发行人维度下钻</div>
              <div className="risk-overview-drill-description">
                使用信用利差迁移读面的 `concentration_by_issuer.top_items` 作为 issuer drill。
              </div>
              <div className="risk-overview-drill-chip-row">
                {issuerRows.map((row) => (
                  <button
                    key={row.name}
                    type="button"
                    className="risk-overview-drill-chip"
                    aria-pressed={row.name === selectedIssuer}
                    onClick={() => setSelectedIssuer(row.name)}
                  >
                    {row.name}
                  </button>
                ))}
              </div>
              <div className="risk-overview-drill-current">
                当前发行人：<strong>{selectedIssuerRow.name}</strong>
              </div>
              <div className="risk-overview-drill-detail">
                权重：{selectedIssuerRow.weight.display} · 市值：{selectedIssuerRow.market_value.display}
              </div>
            </div>
          ) : null}

          <h2 className="risk-overview-block-title">利差情景</h2>
          <div className="risk-overview-table-shell">
            <table className="risk-overview-table">
              <thead>
                <tr>
                  {["情景", "利差变动 (bp)", "损益影响", "OCI", "TPL"].map((label) => (
                    <th key={label} className="risk-overview-table-header">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(credit?.spread_scenarios ?? []).map((row) => (
                  <tr key={row.scenario_name}>
                    <td className="risk-overview-table-cell">{row.scenario_name}</td>
                    <td className="risk-overview-table-cell">{cellText(row.spread_change_bp)}</td>
                    <td className="risk-overview-table-cell">{row.pnl_impact.display}</td>
                    <td className="risk-overview-table-cell">{row.oci_impact.display}</td>
                    <td className="risk-overview-table-cell">{row.tpl_impact.display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {credit?.computed_at && (
            <p className="risk-overview-computed-at">
              computed_at: {credit.computed_at}
            </p>
          )}
        </AsyncSection>
      </div>

      <FormalResultMetaPanel
        testId="risk-overview-result-meta-panel"
        sections={[
          { key: "dates", title: "风险报告日列表", meta: datesQuery.data?.result_meta },
          { key: "tensor", title: "风险张量主读面", meta: tensorQuery.data?.result_meta },
          { key: "krd", title: "KRD 物化下钻", meta: krdQuery.data?.result_meta },
          { key: "issuer", title: "发行人集中度下钻", meta: creditQuery.data?.result_meta },
        ]}
      />
    </section>
  );
}
