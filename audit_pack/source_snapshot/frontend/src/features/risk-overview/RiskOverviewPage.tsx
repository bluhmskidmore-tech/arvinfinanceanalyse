import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactECharts, { type EChartsOption } from "../../lib/echarts";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../api/client";
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
import { shellTokens } from "../../theme/tokens";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../workbench/components/KpiCard";
import {
  formatRatioAsPercent,
  parseDisplayNumber,
  toneFromSignedDisplayString,
} from "../workbench/components/kpiFormat";

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

const tableShellStyle = {
  overflowX: "auto",
  borderRadius: 16,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: "#ffffff",
  marginTop: 18,
} as const;

const tableStyle = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 13,
} as const;

const thStyle = {
  textAlign: "left" as const,
  padding: "10px 12px",
  borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
  color: designTokens.color.neutral[600],
  fontSize: 13,
};

const tdStyle = {
  padding: "12px",
  borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
  color: designTokens.color.neutral[900],
};

const blockTitleStyle = {
  margin: "24px 0 0",
  fontSize: 16,
  fontWeight: 600,
  color: designTokens.color.neutral[900],
} as const;

const drillDownIntroStyle = {
  margin: "28px 0 12px",
  padding: "14px 16px",
  borderRadius: 14,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.neutral[50],
  color: designTokens.color.neutral[600],
  fontSize: 14,
  lineHeight: 1.65,
} as const;

const drillCardStyle = {
  marginTop: 18,
  padding: 16,
  borderRadius: 16,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: "#ffffff",
} as const;

const drillChipRowStyle = {
  display: "flex",
  flexWrap: "wrap" as const,
  gap: 8,
  marginTop: 12,
} as const;

function drillChipStyle(active: boolean) {
  return {
    padding: "8px 12px",
    borderRadius: 999,
    border: active ? `1px solid ${designTokens.color.primary[600]}` : `1px solid ${shellTokens.colorBorderSoft}`,
    background: active ? designTokens.color.primary[50] : "#ffffff",
    color: active ? designTokens.color.primary[600] : designTokens.color.neutral[900],
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  } as const;
}

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
    queryKey: ["risk-overview", "credit-spread-migration", reportDate],
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
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{
            margin: 0,
            fontSize: 32,
            fontWeight: 600,
            letterSpacing: "-0.03em",
          }}
        >
          风险总览
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
          主指标来自正式风险张量接口{" "}
          <code style={{ fontSize: 13 }}>/api/risk/tensor</code>
          （与「风险张量」页同一主链）。下方债券分析物化结果为下钻与补充视图，不在浏览器端做金融重算。
        </p>
      </div>

      <div style={controlBarStyle}>
        <div
          style={{
            padding: "10px 12px",
            borderRadius: 12,
            border: "1px solid #d7dfea",
            background: "#ffffff",
            color: designTokens.color.neutral[900],
            fontSize: 14,
          }}
        >
          {datesEmpty ? (
            <span>后端未返回可用风险报告日。</span>
          ) : datesBlockingError ? (
            <span>风险报告日载入失败。</span>
          ) : (
            <>
              报告日：<strong>{reportDate}</strong>
              <span style={{ marginLeft: 8, color: "#8090a8", fontSize: 13 }}>
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

      <div style={{ marginTop: 8 }}>
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
              <div data-testid="risk-overview-kpi-grid" style={summaryGridStyle}>
                <KpiCard
                  title="组合 DV01"
                  value={bondNumericDisplay(tensorResult.portfolio_dv01)}
                  detail="portfolio_dv01，后端字符串口径。"
                  tone={toneFromSignedDisplayString(bondNumericDisplay(tensorResult.portfolio_dv01))}
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

              <h2
                style={{
                  margin: "24px 0 12px",
                  fontSize: 16,
                  fontWeight: 600,
                  color: designTokens.color.neutral[900],
                }}
              >
                KRD 分桶（DV01）
              </h2>
              {krdChartOption ? (
                <ReactECharts option={krdChartOption} style={{ height: 320 }} />
              ) : null}

              <h2
                style={{
                  margin: "24px 0 12px",
                  fontSize: 16,
                  fontWeight: 600,
                  color: designTokens.color.neutral[900],
                }}
              >
                集中度
              </h2>
              <div style={summaryGridStyle}>
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

              <h2
                style={{
                  margin: "24px 0 12px",
                  fontSize: 16,
                  fontWeight: 600,
                  color: designTokens.color.neutral[900],
                }}
              >
                流动性缺口（市值）
              </h2>
              <div style={summaryGridStyle}>
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
                style={{
                  marginTop: 20,
                  padding: 12,
                  borderRadius: 12,
                  border:
                    tensorResult.quality_flag === "ok"
                      ? "1px solid #d7dfea"
                      : "1px solid #e8d9a8",
                  background:
                    tensorResult.quality_flag === "ok" ? "#f6f9fc" : "#fffbeb",
                  color: designTokens.color.neutral[900],
                  fontSize: 14,
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 8 }}>
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
                  <div style={{ color: designTokens.color.neutral[600] }}>无预警。</div>
                ) : (
                  <ul style={{ margin: 0, paddingLeft: 20, color: designTokens.color.neutral[600] }}>
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

      <div style={drillDownIntroStyle}>
        <strong style={{ color: designTokens.color.neutral[900] }}>债券分析下钻与补充</strong>
        ：以下接口来自{" "}
        <code style={{ fontSize: 12 }}>/api/bond-analytics/krd-curve-risk</code> 与{" "}
        <code style={{ fontSize: 12 }}>/api/bond-analytics/credit-spread-migration</code>
        ，用于曲线/KRD 明细与信用利差迁移等物化视角，与主链风险张量并存时可对照阅读。
      </div>

      <div style={{ marginTop: 8 }}>
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
          <div data-testid="risk-overview-bond-krd-kpi-grid" style={summaryGridStyle}>
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
              title="DV01"
              value={cellText(krd?.portfolio_dv01)}
              detail="portfolio_dv01。"
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
            <div
              style={{
                marginTop: 16,
                padding: 12,
                borderRadius: 12,
                border: "1px solid #e8d9a8",
                background: "#fffbeb",
                color: "#7a5c1a",
                fontSize: 13,
              }}
            >
              {krd.warnings.map((w, i) => (
                <div key={i}>{w}</div>
              ))}
            </div>
          )}

          {selectedTenorRow ? (
            <div data-testid="risk-overview-tenor-drill" style={drillCardStyle}>
              <div style={{ color: designTokens.color.neutral[900], fontSize: 15, fontWeight: 600 }}>期限桶下钻</div>
              <div style={{ color: designTokens.color.neutral[600], fontSize: 13, marginTop: 6 }}>
                使用债券分析的 `krd_buckets` 读面，先聚焦当前最敏感的期限桶。
              </div>
              <div style={drillChipRowStyle}>
                {tenorRows.map((row) => (
                  <button
                    key={row.tenor}
                    type="button"
                    style={drillChipStyle(row.tenor === selectedTenor)}
                    onClick={() => setSelectedTenor(row.tenor)}
                  >
                    {row.tenor}
                  </button>
                ))}
              </div>
              <div style={{ marginTop: 12, color: designTokens.color.neutral[900], fontSize: 14 }}>
                当前桶：<strong>{selectedTenorRow.tenor}</strong>
              </div>
              <div style={{ marginTop: 8, color: designTokens.color.neutral[600], fontSize: 13 }}>
                KRD：{selectedTenorRow.krd.display} · DV01：{selectedTenorRow.dv01.display} · 市值权重：
                {selectedTenorRow.market_value_weight.display}
              </div>
            </div>
          ) : null}

          <h2 style={blockTitleStyle}>KRD 分桶</h2>
          <div style={tableShellStyle}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {["期限", "KRD", "DV01", "市值权重"].map((label) => (
                    <th key={label} style={thStyle}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(krd?.krd_buckets ?? []).map((row) => (
                  <tr key={row.tenor}>
                    <td style={tdStyle}>{row.tenor}</td>
                    <td style={tdStyle}>{row.krd.display}</td>
                    <td style={tdStyle}>{row.dv01.display}</td>
                    <td style={tdStyle}>{row.market_value_weight.display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 style={blockTitleStyle}>情景分析</h2>
          <div style={tableShellStyle}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {["情景名称", "情景说明", "经济口径损益", "OCI", "TPL"].map((label) => (
                    <th key={label} style={thStyle}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(krd?.scenarios ?? []).map((row) => (
                  <tr key={row.scenario_name}>
                    <td style={tdStyle}>{row.scenario_name}</td>
                    <td style={tdStyle}>{row.scenario_description}</td>
                    <td style={tdStyle}>{row.pnl_economic.display}</td>
                    <td style={tdStyle}>{row.pnl_oci.display}</td>
                    <td style={tdStyle}>{row.pnl_tpl.display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 style={blockTitleStyle}>资产类别风险汇总</h2>
          <div style={tableShellStyle}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {["资产类别", "市值", "久期", "DV01", "权重"].map((label) => (
                    <th key={label} style={thStyle}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(krd?.by_asset_class ?? []).map((row) => (
                  <tr key={row.asset_class}>
                    <td style={tdStyle}>{row.asset_class}</td>
                    <td style={tdStyle}>{row.market_value.display}</td>
                    <td style={tdStyle}>{row.duration.display}</td>
                    <td style={tdStyle}>{row.dv01.display}</td>
                    <td style={tdStyle}>{row.weight.display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {krd?.computed_at && (
            <p style={{ marginTop: 16, marginBottom: 0, color: "#8090a8", fontSize: 12 }}>
              computed_at: {krd.computed_at}
            </p>
          )}
        </AsyncSection>
      </div>

      <div style={{ marginTop: 24 }}>
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
          <div style={summaryGridStyle}>
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
            <div
              style={{
                marginTop: 16,
                padding: 12,
                borderRadius: 12,
                border: "1px solid #e8d9a8",
                background: "#fffbeb",
                color: "#7a5c1a",
                fontSize: 13,
              }}
            >
              {credit.warnings.map((w, i) => (
                <div key={i}>{w}</div>
              ))}
            </div>
          )}

          {selectedIssuerRow ? (
            <div data-testid="risk-overview-issuer-drill" style={drillCardStyle}>
              <div style={{ color: designTokens.color.neutral[900], fontSize: 15, fontWeight: 600 }}>发行人维度下钻</div>
              <div style={{ color: designTokens.color.neutral[600], fontSize: 13, marginTop: 6 }}>
                使用信用利差迁移读面的 `concentration_by_issuer.top_items` 作为 issuer drill。
              </div>
              <div style={drillChipRowStyle}>
                {issuerRows.map((row) => (
                  <button
                    key={row.name}
                    type="button"
                    style={drillChipStyle(row.name === selectedIssuer)}
                    onClick={() => setSelectedIssuer(row.name)}
                  >
                    {row.name}
                  </button>
                ))}
              </div>
              <div style={{ marginTop: 12, color: designTokens.color.neutral[900], fontSize: 14 }}>
                当前发行人：<strong>{selectedIssuerRow.name}</strong>
              </div>
              <div style={{ marginTop: 8, color: designTokens.color.neutral[600], fontSize: 13 }}>
                权重：{selectedIssuerRow.weight.display} · 市值：{selectedIssuerRow.market_value.display}
              </div>
            </div>
          ) : null}

          <h2 style={blockTitleStyle}>利差情景</h2>
          <div style={tableShellStyle}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {["情景", "利差变动 (bp)", "损益影响", "OCI", "TPL"].map((label) => (
                    <th key={label} style={thStyle}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(credit?.spread_scenarios ?? []).map((row) => (
                  <tr key={row.scenario_name}>
                    <td style={tdStyle}>{row.scenario_name}</td>
                    <td style={tdStyle}>{cellText(row.spread_change_bp)}</td>
                    <td style={tdStyle}>{row.pnl_impact.display}</td>
                    <td style={tdStyle}>{row.oci_impact.display}</td>
                    <td style={tdStyle}>{row.tpl_impact.display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {credit?.computed_at && (
            <p style={{ marginTop: 16, marginBottom: 0, color: "#8090a8", fontSize: 12 }}>
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
