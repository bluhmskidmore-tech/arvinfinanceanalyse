import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, Statistic, Row, Col, Table, Alert } from "antd";
import { type EChartsOption } from "../../../lib/echarts";
import { useApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import { ChartCard } from "../../../components/charts/ChartCard";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { ConcentrationMetrics, CreditSpreadDetailBondRow } from "../types";
import { designTokens, nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { formatDv01Wan, formatWan, formatYi } from "../utils/formatters";
import { formatMoneyAxisTick } from "../lib/returnDecompositionWaterfallOption";
import {
  DetailEmptyNote,
  DetailLoadErrorAlert,
  DetailPanelSkeleton,
  withNumericColumns,
} from "./BondAnalyticsDetailPrimitives";
import detailStyles from "./BondAnalyticsDetailPrimitives.module.css";
import { SectionHead } from "../../../components/layout";
import {
  buildIssuerConcentrationPieOption,
  concentrationBarOption,
  formatBpOrDash,
  formatPercentile,
  hasAnyConcentrationField,
  issuerConcentrationColumns,
  migrationColumns,
  normalizeClientError,
  spreadColumns,
  spreadDetailColumns,
  spreadTermStructureOption,
} from "./creditSpreadViewSupport";

const dt = designTokens;

interface Props {
  reportDate: string;
  /** Comma-separated bp shocks, e.g. `10,25,50` */
  spreadScenarios?: string;
}

const DEFAULT_SPREAD_SCENARIOS = "10,25,50";
const numericSpreadColumns = withNumericColumns(spreadColumns);
const numericSpreadDetailColumns = withNumericColumns(spreadDetailColumns);
const numericIssuerConcentrationColumns = withNumericColumns(issuerConcentrationColumns);
const numericMigrationColumns = withNumericColumns(migrationColumns);

function renderConcentrationChart(metrics: ConcentrationMetrics | undefined) {
  if (!metrics?.top_items?.length) {
    return <DetailEmptyNote>暂无数据</DetailEmptyNote>;
  }
  const option = nocturneChartTheme.createBaseChartOption({
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const item = params as { name?: string; value?: number; percent?: number };
        const content = document.createElement("div");
        content.append(`${item.name ?? ""}: ${formatYi(item.value)} (${item.percent ?? 0}%)`);
        return content;
      },
    },
    series: [
      {
        type: "pie",
        radius: "55%",
        center: ["50%", "56%"],
        data: metrics.top_items.map((item) => ({
          name: item.name,
          value: bondNumericRaw(item.market_value) ?? undefined,
        })),
      },
    ],
  });
  return (
    <ChartCard
      flat
      title={metrics.dimension}
      question={`HHI ${metrics.hhi.display} · 前五 ${metrics.top5_concentration.display}`}
      ariaLabel={`${metrics.dimension}集中度`}
      option={option}
      height={220}
      legend="none"
    />
  );
}

export function CreditSpreadView({ reportDate, spreadScenarios = DEFAULT_SPREAD_SCENARIOS }: Props) {
  const client = useApiClient();
  const summaryQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsCreditSpreadMigration(
      client.mode,
      reportDate,
      spreadScenarios,
    ),
    queryFn: () =>
      spreadScenarios === DEFAULT_SPREAD_SCENARIOS
        ? client.getBondAnalyticsCreditSpreadMigration(reportDate)
        : client.getBondAnalyticsCreditSpreadMigration(reportDate, { spreadScenarios }),
    enabled: Boolean(reportDate),
    retry: false,
  });
  const detailQuery = useQuery({
    queryKey: ["credit-spread-analysis", "detail", client.mode, reportDate],
    queryFn: () => client.getCreditSpreadAnalysisDetail(reportDate),
    enabled: Boolean(reportDate),
    retry: false,
  });

  const data = summaryQuery.data?.result ?? null;
  const detailData = detailQuery.data?.result ?? null;
  const detailMeta = detailQuery.data?.result_meta ?? null;
  const benchmarkUnavailable = detailMeta?.vendor_status === "vendor_unavailable";
  const detailUnavailable = benchmarkUnavailable
    || detailData?.spread_coverage_status === "unavailable"
    || detailData?.spread_coverage_status === "empty";
  // 旧响应的数量/金额是计算样本占位；v3 已明确为全体信用持仓，曲线缺失也可展示。
  const detailHoldingsUnavailable = benchmarkUnavailable && !detailData?.spread_coverage_status;
  const detailError = detailQuery.isError
    ? detailQuery.error instanceof Error
      ? detailQuery.error.message
      : "未知错误"
    : null;

  const spreadChartOption = useMemo((): EChartsOption | null => {
    if (!data?.spread_scenarios?.length) return null;
    const scenarios = data.spread_scenarios;
    return nocturneChartTheme.createBarChartOption({
      grid: {
        left: dt.space[9] + dt.space[1],
        right: dt.space[4],
        top: dt.space[6],
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: unknown) => {
          const list = Array.isArray(params) ? params : [params];
          const p = list[0] as {
            name?: string;
            value?: number | { value: number };
            data?: { value?: number };
          };
          const name = p?.name ?? "";
          const raw = p?.value ?? p?.data?.value;
          const num =
            typeof raw === "object" && raw !== null && "value" in raw
              ? (raw as { value: number }).value
              : Number(raw);
          return `${name}<br/>损益影响：${formatWan(num)}`;
        },
      },
      xAxis: {
        type: "category",
        data: scenarios.map((s) => s.scenario_name),
        axisLabel: { color: nocturneTokens.color.inkMuted, fontSize: dt.fontSize[11], interval: 0, rotate: 15 },
        axisLine: { lineStyle: { color: nocturneTokens.color.lineSoft } },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          ...nocturneChartTheme.axisLabel,
          formatter: formatMoneyAxisTick,
        },
        splitLine: { lineStyle: { color: nocturneTokens.color.lineSoft, type: "dashed", opacity: 0.35 } },
      },
      series: [
        {
          type: "bar",
          name: "损益影响",
          barMaxWidth: dt.space[9],
          data: scenarios.map((s) => {
            const v = bondNumericRaw(s.pnl_impact);
            return {
              value: v,
              itemStyle: {
                // tooltip 口径为「损益影响」：正=profit 绿、负=loss 红。
                // ECharts canvas 读不到 CSS 变量：深色路由用 Nocturne TS 镜像 token。
                color:
                  v === null
                    ? nocturneTokens.color.inkMuted
                    : v >= 0
                      ? nocturneTokens.color.green
                      : nocturneTokens.color.red,
              },
            };
          }),
        },
      ],
    });
  }, [data]);

  const issuerConcentrationPieOption = useMemo((): EChartsOption | null => {
    if (!data?.concentration_by_issuer?.top_items?.length) return null;
    return nocturneChartTheme.createBaseChartOption({
      ...buildIssuerConcentrationPieOption(data.concentration_by_issuer),
    });
  }, [data]);

  const termStructureOption = useMemo(() => {
    const option = spreadTermStructureOption(
      detailUnavailable ? [] : detailData?.spread_term_structure ?? [],
    );
    return option ? nocturneChartTheme.createLineChartOption(option) : null;
  }, [detailData, detailUnavailable]);

  /*
   * 评级 / 期限分布只消费后端 concentration_by_rating / concentration_by_tenor；
   * 前端不持有评级或期限分桶口径（2026-06 审计 P1-11 / 2026-09-02 审计 C2）。
   */
  const creditDistributionView = useMemo(() => {
    if (!data) return { kind: "empty" as const };
    const ratingOpt = concentrationBarOption(data.concentration_by_rating, nocturneTokens.color.blue, "市值占比");
    const tenorOpt = concentrationBarOption(data.concentration_by_tenor, nocturneTokens.color.amber, "市值占比");
    if (ratingOpt || tenorOpt) {
      return {
        kind: "bars" as const,
        ratingOption: ratingOpt
          ? nocturneChartTheme.createBarChartOption(ratingOpt)
          : null,
        tenorOption: tenorOpt
          ? nocturneChartTheme.createBarChartOption(tenorOpt)
          : null,
      };
    }
    return { kind: "empty" as const };
  }, [data]);

  if (summaryQuery.isLoading) return <DetailPanelSkeleton testId="credit-spread-loading" />;
  if (summaryQuery.isError) {
    const message = summaryQuery.error instanceof Error ? summaryQuery.error.message : String(summaryQuery.error);
    return <DetailLoadErrorAlert error={message} testId="credit-spread-error" />;
  }
  if (!data) return null;

  const mergedWarnings = Array.from(
    new Set([
      ...data.warnings,
      ...(detailData?.warnings ?? []),
      ...(benchmarkUnavailable
        ? ["基准曲线不可用，信用利差明细的平均利差及历史分位暂不可用；信用持仓规模与汇总风险数据独立展示。"]
        : []),
      ...(detailError ? [`深度利差明细暂不可用：${normalizeClientError(detailError)}`] : []),
    ]),
  );
  const displayCreditBondCount = detailHoldingsUnavailable
    ? EM_DASH
    : detailData?.credit_bond_count ?? data.credit_bond_count ?? EM_DASH;
  const displayCreditMarketValue = detailHoldingsUnavailable
    ? null
    : detailData?.total_credit_market_value ?? data.credit_market_value;
  const displayWeightedAvgSpread = detailData && !detailUnavailable
    ? formatBpOrDash(detailData.weighted_avg_spread_bps)
    : EM_DASH;
  const historicalContext = benchmarkUnavailable ? undefined : detailData?.historical_context;

  return (
    <div className={detailStyles.view}>
      <SectionHead
        category="信用利差"
        title="信用利差概览"
        note="查看当前报告日的信用利差、DV01、OCI 敏感度及明细。"
        testId="credit-spread-shell-lead"
        numbered={false}
      />
      <Row gutter={[12, 12]} className={detailStyles.kpiGrid}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="信用债数量" value={displayCreditBondCount} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="信用债市值"
              value={formatYi(displayCreditMarketValue)}
              suffix={
                 detailHoldingsUnavailable || bondNumericRaw(data.credit_weight) === null
                  ? undefined
                  : `(${(bondNumericRaw(data.credit_weight)! * 100).toFixed(1)}%)`
              }
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="利差 DV01（万元/bp）" value={formatDv01Wan(data.spread_dv01)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="加权平均利差（个券）" value={displayWeightedAvgSpread} />
          </Card>
        </Col>
      </Row>

      {detailData?.spread_coverage_status && (
        <Alert
          data-testid="credit-spread-coverage"
          type={detailData.spread_coverage_status === "complete" ? "info" : "warning"}
          showIcon
          message="信用利差计算覆盖"
          description={(
            <>
              <div>
                可计算利差 {detailData.spread_bond_count ?? EM_DASH} 只，市值 {formatYi(detailData.spread_market_value)}；
                收益率缺失或无效 {detailData.missing_ytm_count ?? EM_DASH} 只，市值 {formatYi(detailData.missing_ytm_market_value)}。
              </div>
              {detailData.spread_coverage_status === "unavailable" && (
                <div>信用持仓已保留，当前利差及历史分位不可用。</div>
              )}
              {detailData.spread_coverage_status === "partial" && (
                <div>平均利差和分位仅代表可计算样本，未覆盖全部信用持仓。</div>
              )}
              {detailData.spread_coverage_status === "empty" && <div>本期没有信用债持仓。</div>}
            </>
          )}
        />
      )}

      <Card title="OCI敏感度" size="small">
        <Row gutter={[12, 12]} className={detailStyles.kpiGrid}>
          <Col span={8}>
            <Statistic title="OCI信用债敞口" value={formatYi(data.oci_credit_exposure)} />
          </Col>
          <Col span={8}>
            <Statistic title="OCI 利差 DV01（万元/bp）" value={formatDv01Wan(data.oci_spread_dv01)} />
          </Col>
          <Col span={8}>
            <Statistic title="利差走阔25bp影响" value={formatWan(data.oci_sensitivity_25bp)} />
          </Col>
        </Row>
      </Card>

      <SectionHead
        category="场景"
        title="利差冲击与信用分布"
        note="比较利差情景、评级迁徙影响及评级和期限分布。"
        testId="credit-spread-scenario-lead"
        numbered={false}
      />
      {data.spread_scenarios.length > 0 && (
        <Card title="利差情景冲击" size="small">
          {spreadChartOption && (
            <div style={{ marginBottom: dt.space[4] }}>
              <ChartCard
                flat
                ariaLabel="利差情景冲击"
                unit="万元"
                option={spreadChartOption}
                height={280}
                legend="none"
              />
            </div>
          )}
          <Table
            dataSource={data.spread_scenarios}
            columns={numericSpreadColumns}
            rowKey="scenario_name"
            pagination={false}
            size="small"
            scroll={{ y: 400 }}
          />
        </Card>
      )}

      <Card title="信用债分布" size="small">
        {creditDistributionView.kind === "bars" && (
          <Row gutter={16}>
            <Col xs={24} lg={12}>
              <ChartCard
                flat
                question={`${data.concentration_by_rating?.dimension ?? "评级"}（前列市值）`}
                ariaLabel="评级分布"
                unit="%"
                option={creditDistributionView.ratingOption}
                height={280}
                legend="none"
                emptyMessage="暂无评级分布"
              />
            </Col>
            <Col xs={24} lg={12}>
              <ChartCard
                flat
                question={`${data.concentration_by_tenor?.dimension ?? "期限"}（前列市值）`}
                ariaLabel="期限分布"
                unit="%"
                option={creditDistributionView.tenorOption}
                height={280}
                legend="none"
                emptyMessage="暂无期限分布"
              />
            </Col>
          </Row>
        )}
        {creditDistributionView.kind === "empty" && (
          <DetailEmptyNote testId="credit-spread-distribution-empty">
            评级或期限集中度数据暂缺，无法展示分布图
          </DetailEmptyNote>
        )}
      </Card>

      <SectionHead
        category="明细"
        title="期限结构与集中度明细"
        note="查看期限结构、历史分位和高低利差个券；明细暂缺时保留汇总并说明缺口。"
        testId="credit-spread-detail-lead"
        numbered={false}
      />
      {detailQuery.isLoading && !detailData ? (
        <DetailPanelSkeleton testId="credit-spread-detail-loading" />
      ) : null}
      {detailData && (
        <>
          <Card title="利差期限结构" size="small">
            <ChartCard
              flat
              ariaLabel="利差期限结构"
              unit="bp"
              option={termStructureOption}
              height={280}
              emptyMessage="暂无期限结构数据"
              testId="credit-spread-term-structure"
            />
          </Card>

          <Card title="历史分位" size="small">
            <Row gutter={[12, 12]} className={detailStyles.kpiGrid}>
              <Col span={6}>
                <Statistic
                  title="当前利差"
                  value={formatBpOrDash(detailUnavailable ? null : historicalContext?.current_spread_bps)}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="1年历史分位"
                  value={formatPercentile(detailUnavailable ? null : historicalContext?.percentile_1y)}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="3年历史分位"
                  value={formatPercentile(detailUnavailable ? null : historicalContext?.percentile_3y)}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="1年中位数"
                  value={formatBpOrDash(historicalContext?.median_1y)}
                />
              </Col>
            </Row>
          </Card>

          <Row gutter={16}>
            <Col span={12}>
              <Card title="高利差债券" size="small">
                <Table<CreditSpreadDetailBondRow>
                  dataSource={detailUnavailable ? [] : detailData.top_spread_bonds}
                  columns={numericSpreadDetailColumns}
                  rowKey={(row) => `${row.instrument_code}-${row.tenor_bucket}-top`}
                  pagination={false}
                  size="small"
                  scroll={{ y: 400 }}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="低利差债券" size="small">
                <Table<CreditSpreadDetailBondRow>
                  dataSource={detailUnavailable ? [] : detailData.bottom_spread_bonds}
                  columns={numericSpreadDetailColumns}
                  rowKey={(row) => `${row.instrument_code}-${row.tenor_bucket}-bottom`}
                  pagination={false}
                  size="small"
                  scroll={{ y: 400 }}
                />
              </Card>
            </Col>
          </Row>
        </>
      )}

      {hasAnyConcentrationField(data) && (
        <Card title="信用集中度" size="small">
          <Row gutter={[16, 16]}>
            <Col span={12}>
              {data.concentration_by_issuer?.top_items?.length ? (
                <>
                  <Row gutter={16} align="middle">
                    <Col xs={24} md={12}>
                      <Table
                        dataSource={data.concentration_by_issuer.top_items}
                        columns={numericIssuerConcentrationColumns}
                        rowKey={(r) => r.name}
                        pagination={false}
                        size="small"
                        scroll={{ y: 400 }}
                      />
                    </Col>
                    <Col xs={24} md={12}>
                      {issuerConcentrationPieOption && (
                        <div style={{ marginTop: dt.space[4] }}>
                          <ChartCard
                            flat
                            title={data.concentration_by_issuer.dimension}
                            question={`HHI ${data.concentration_by_issuer.hhi.display} · 前五 ${data.concentration_by_issuer.top5_concentration.display}`}
                            ariaLabel="发行人集中度"
                            option={issuerConcentrationPieOption}
                            height={280}
                            legend="none"
                          />
                        </div>
                      )}
                    </Col>
                  </Row>
                </>
              ) : (
                renderConcentrationChart(data.concentration_by_issuer)
              )}
            </Col>
            <Col span={12}>
              {renderConcentrationChart(data.concentration_by_industry)}
            </Col>
            <Col span={12}>
              {renderConcentrationChart(data.concentration_by_rating)}
            </Col>
            <Col span={12}>
              {renderConcentrationChart(data.concentration_by_tenor)}
            </Col>
          </Row>
        </Card>
      )}

      {data.migration_scenarios.length > 0 && (
        <Card title="评级迁徙情景" size="small">
          <Table
            dataSource={data.migration_scenarios}
            columns={numericMigrationColumns}
            rowKey="scenario_name"
            pagination={false}
            size="small"
            scroll={{ y: 400 }}
          />
        </Card>
      )}

      {mergedWarnings.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message="提示"
          description={mergedWarnings.map((w, i) => <div key={i}>{w}</div>)}
        />
      )}
      <FormalResultMetaPanel
        testId="credit-spread-detail-result-meta"
        title="信用利差明细证据"
        sections={[
          {
            key: "detail",
            title: "信用利差明细",
            meta: detailMeta,
          },
        ]}
      />
    </div>
  );
}
