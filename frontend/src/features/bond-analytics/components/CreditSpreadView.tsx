import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, Statistic, Row, Col, Table, Alert, Spin } from "antd";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { useApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { CreditSpreadDetailBondRow } from "../types";
import { designTokens, nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { formatDv01Wan, formatWan, formatYi, formatBp } from "../utils/formatters";
import { SectionLead } from "./SectionLead";
import { ConcentrationPieCell } from "./ConcentrationPieCell";
import {
  buildIssuerConcentrationPieOption,
  buildRatingTenorHeatmapData,
  concentrationBarOption,
  formatBpOrDash,
  formatPercentile,
  hasAnyConcentrationField,
  issuerConcentrationColumns,
  migrationColumns,
  normalizeClientError,
  ratingTenorHeatmapOption,
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
  const detailError = detailQuery.isError
    ? detailQuery.error instanceof Error
      ? detailQuery.error.message
      : "未知错误"
    : null;

  const spreadChartOption = useMemo((): EChartsOption | null => {
    if (!data?.spread_scenarios?.length) return null;
    const scenarios = data.spread_scenarios;
    return {
      grid: {
        left: dt.space[9] + dt.space[1],
        right: dt.space[4],
        top: dt.space[6],
        bottom: dt.space[6] + dt.space[1],
        containLabel: false,
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
        axisLabel: { color: nocturneTokens.color.inkMuted, fontSize: dt.fontSize[11] },
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
    };
  }, [data]);

  const issuerConcentrationPieOption = useMemo((): EChartsOption | null => {
    if (!data?.concentration_by_issuer?.top_items?.length) return null;
    return buildIssuerConcentrationPieOption(data.concentration_by_issuer);
  }, [data]);

  const termStructureOption = useMemo(
    () => spreadTermStructureOption(detailData?.spread_term_structure ?? []),
    [detailData],
  );

  const creditDistributionView = useMemo(() => {
    if (!data) return { kind: "empty" as const };
    const heat =
      data.bond_details && data.bond_details.length > 0
        ? buildRatingTenorHeatmapData(data.bond_details, data.credit_market_value)
        : null;
    if (heat) {
      return {
        kind: "heatmap" as const,
        option: ratingTenorHeatmapOption(heat.seriesData, heat.maxPct),
      };
    }
    const ratingOpt = concentrationBarOption(data.concentration_by_rating, nocturneTokens.color.blue, "市值占比");
    const tenorOpt = concentrationBarOption(data.concentration_by_tenor, nocturneTokens.color.amber, "市值占比");
    if (ratingOpt || tenorOpt) {
      return { kind: "bars" as const, ratingOption: ratingOpt, tenorOption: tenorOpt };
    }
    return { kind: "empty" as const };
  }, [data]);

  if (summaryQuery.isLoading) return <Spin style={{ display: "block", margin: `${dt.space[8]}px auto` }} />;
  if (summaryQuery.isError) {
    const message = summaryQuery.error instanceof Error ? summaryQuery.error.message : String(summaryQuery.error);
    return <Alert type="error" message={`加载失败：${message}`} />;
  }
  if (!data) return null;

  const mergedWarnings = Array.from(
    new Set([
      ...data.warnings,
      ...(detailData?.warnings ?? []),
          ...(detailError ? [`深度利差明细暂不可用：${normalizeClientError(detailError)}`] : []),
        ]),
      );
  const displayCreditBondCount = detailData?.credit_bond_count ?? data.credit_bond_count;
  const displayCreditMarketValue = detailData?.total_credit_market_value ?? data.credit_market_value;
  const displayWeightedAvgSpread = detailData
    ? formatBp(detailData.weighted_avg_spread_bps)
    : EM_DASH;
  const historicalContext = detailData?.historical_context;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: dt.space[4] }}>
      <SectionLead
        eyebrow="信用利差"
        title="信用利差概览"
        description="按报告日读取后端信用利差读模型；页面只展示利差、DV01、OCI 敏感度与明细，不在前端补算正式风险指标。"
        testId="credit-spread-shell-lead"
      />
      <Row gutter={16}>
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
                bondNumericRaw(data.credit_weight) === null
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

      <Card title="OCI敏感度" size="small">
        <Row gutter={16}>
          <Col span={8}>
            <Statistic title="OCI信用债敞口" value={formatYi(data.oci_credit_exposure)} />
          </Col>
          <Col span={8}>
            <Statistic title="OCI 利差 DV01" value={formatDv01Wan(data.oci_spread_dv01)} />
          </Col>
          <Col span={8}>
            <Statistic title="利差走阔25bp影响" value={formatWan(data.oci_sensitivity_25bp)} />
          </Col>
        </Row>
      </Card>

      <SectionLead
        eyebrow="场景"
        title="利差冲击与信用分布"
        description="利差情景、评级迁徙和评级/期限分布沿用后端返回字段，前端只负责图表化展示。"
        testId="credit-spread-scenario-lead"
      />
      {data.spread_scenarios.length > 0 && (
        <Card title="利差情景冲击" size="small">
          {spreadChartOption && (
            <div style={{ marginBottom: dt.space[4] }}>
              <ReactECharts
                option={spreadChartOption}
                style={{ height: 280, width: "100%" }}
                opts={{ renderer: "canvas" }}
              />
            </div>
          )}
          <Table
            dataSource={data.spread_scenarios}
            columns={spreadColumns}
            rowKey="scenario_name"
            pagination={false}
            size="small"
            scroll={{ y: 400 }}
          />
        </Card>
      )}

      <Card title="信用债分布" size="small">
        {creditDistributionView.kind === "heatmap" && (
          <ReactECharts
            option={creditDistributionView.option}
            style={{ height: 400, width: "100%" }}
            opts={{ renderer: "canvas" }}
          />
        )}
        {creditDistributionView.kind === "bars" && (
          <Row gutter={16}>
            <Col xs={24} lg={12}>
              <div
                style={{
                  marginBottom: dt.space[2],
                  fontSize: dt.fontSize[12],
                  color: "var(--dh-api-soft)",
                  textAlign: "center",
                }}
              >
                {data.concentration_by_rating?.dimension ?? "评级"}（前列市值）
              </div>
              {creditDistributionView.ratingOption ? (
                <ReactECharts
                  option={creditDistributionView.ratingOption}
                  style={{ height: 300, width: "100%" }}
                  opts={{ renderer: "canvas" }}
                />
              ) : (
                <div
                  style={{
                    height: 300,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--dh-api-muted)",
                  }}
                >
                  暂无评级分布
                </div>
              )}
            </Col>
            <Col xs={24} lg={12}>
              <div
                style={{
                  marginBottom: dt.space[2],
                  fontSize: dt.fontSize[12],
                  color: "var(--dh-api-soft)",
                  textAlign: "center",
                }}
              >
                {data.concentration_by_tenor?.dimension ?? "期限"}（前列市值）
              </div>
              {creditDistributionView.tenorOption ? (
                <ReactECharts
                  option={creditDistributionView.tenorOption}
                  style={{ height: 300, width: "100%" }}
                  opts={{ renderer: "canvas" }}
                />
              ) : (
                <div
                  style={{
                    height: 300,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--dh-api-muted)",
                  }}
                >
                  暂无期限分布
                </div>
              )}
            </Col>
          </Row>
        )}
        {creditDistributionView.kind === "empty" && (
          <div
            style={{
              minHeight: 120,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--dh-api-muted)",
            }}
          >
            暂无评级×期限明细或集中度数据，无法展示分布图
          </div>
        )}
      </Card>

      <SectionLead
        eyebrow="明细"
        title="期限结构与集中度明细"
        description="深度明细端点可用时展示期限结构、历史分位和高低利差个券；不可用时保留汇总并显示提示。"
        testId="credit-spread-detail-lead"
      />
      {detailData && (
        <>
          <Card title="利差期限结构" size="small">
            {termStructureOption ? (
              <ReactECharts
                option={termStructureOption}
                style={{ height: 320, width: "100%" }}
                opts={{ renderer: "canvas" }}
              />
            ) : (
              <div
                style={{
                  minHeight: 120,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--dh-api-muted)",
                }}
              >
                暂无期限结构数据
              </div>
            )}
          </Card>

          <Card title="历史分位" size="small">
            <Row gutter={16}>
              <Col span={6}>
                <Statistic
                  title="当前利差"
                  value={formatBpOrDash(historicalContext?.current_spread_bps)}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="1年历史分位"
                  value={formatPercentile(historicalContext?.percentile_1y)}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="3年历史分位"
                  value={formatPercentile(historicalContext?.percentile_3y)}
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
                  dataSource={detailData.top_spread_bonds}
                  columns={spreadDetailColumns}
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
                  dataSource={detailData.bottom_spread_bonds}
                  columns={spreadDetailColumns}
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
                  <div
                    style={{
                      marginBottom: dt.space[2],
                      fontSize: dt.fontSize[12],
                      color: "var(--dh-api-soft)",
                      textAlign: "center",
                    }}
                  >
                    {data.concentration_by_issuer.dimension} HHI {data.concentration_by_issuer.hhi.display} 前五{" "}
                    {data.concentration_by_issuer.top5_concentration.display}
                  </div>
                  <Row gutter={16} align="middle">
                    <Col xs={24} md={12}>
                      <Table
                        dataSource={data.concentration_by_issuer.top_items}
                        columns={issuerConcentrationColumns}
                        rowKey={(r) => r.name}
                        pagination={false}
                        size="small"
                        scroll={{ y: 400 }}
                      />
                    </Col>
                    <Col xs={24} md={12}>
                      {issuerConcentrationPieOption && (
                        <div style={{ marginTop: dt.space[4] }}>
                          <ReactECharts
                            option={issuerConcentrationPieOption}
                            style={{ height: 280, width: "100%" }}
                            opts={{ renderer: "canvas" }}
                          />
                        </div>
                      )}
                    </Col>
                  </Row>
                </>
              ) : (
                <ConcentrationPieCell metrics={data.concentration_by_issuer} />
              )}
            </Col>
            <Col span={12}>
              <ConcentrationPieCell metrics={data.concentration_by_industry} />
            </Col>
            <Col span={12}>
              <ConcentrationPieCell metrics={data.concentration_by_rating} />
            </Col>
            <Col span={12}>
              <ConcentrationPieCell metrics={data.concentration_by_tenor} />
            </Col>
          </Row>
        </Card>
      )}

      {data.migration_scenarios.length > 0 && (
        <Card title="评级迁徙情景" size="small">
          <Table
            dataSource={data.migration_scenarios}
            columns={migrationColumns}
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
