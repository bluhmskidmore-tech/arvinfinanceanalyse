import { useEffect, useMemo, useState } from "react";
import ReactECharts from "../../../lib/echarts";
import { Card, Statistic, Row, Col, Table, Alert, Spin, Collapse } from "antd";
import { useApiClient } from "../../../api/client";
import type { ResultMeta } from "../../../api/contracts";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import type {
  BondAnalyticsAccountingClassFilter,
  BondAnalyticsAssetClassFilter,
  PeriodType,
  ReturnDecompositionResponse,
} from "../types";
import {
  bondNumericRaw,
  returnDecompositionWaterfallDisplayStrings,
  returnDecompositionWaterfallRawSteps,
} from "../adapters/bondAnalyticsAdapter";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { formatWan } from "../utils/formatters";
import { SectionLead } from "./SectionLead";

const CN_MARKET_UP = designTokens.color.danger[500];
const CN_MARKET_DOWN = designTokens.color.success[600];
const CHART_ACCENT = designTokens.color.info[500];
const CHART_AXIS = { color: designTokens.color.neutral[700], fontSize: designTokens.fontSize[11] };

const WATERFALL_CATEGORIES = [
  "Carry",
  "Roll-down",
  "鍒╃巼鏁堝簲",
  "鍒╁樊鏁堝簲",
  "FX鏁堝簲",
  "Convexity",
  "浜ゆ槗",
  "鍚堣",
] as const;

const TRANSPARENT_BAR = {
  borderColor: "transparent",
  color: "rgba(0,0,0,0)",
  borderWidth: 0,
} as const;

function describeMetaIssues(meta: ResultMeta | null): string[] {
  if (!meta) return [];
  const issues: string[] = [];
  if (meta.quality_flag !== "ok") issues.push(`quality_flag=${meta.quality_flag}`);
  if (meta.vendor_status !== "ok") issues.push(`vendor_status=${meta.vendor_status}`);
  if (meta.fallback_mode !== "none") issues.push(`fallback_mode=${meta.fallback_mode}`);
  return issues;
}

function buildWaterfallOption(d: ReturnDecompositionResponse) {
  const rawSteps = returnDecompositionWaterfallRawSteps(d);
  const stepValues = rawSteps.slice(0, -1);
  const explained = rawSteps[rawSteps.length - 1] ?? 0;

  const helperRaw: number[] = [];
  const valueRaw: number[] = [];
  const barColors: string[] = [];

  let running = 0;
  for (const v of stepValues) {
    if (v >= 0) {
      helperRaw.push(running);
      valueRaw.push(v);
      barColors.push(CN_MARKET_UP);
      running += v;
    } else {
      helperRaw.push(running + v);
      valueRaw.push(-v);
      barColors.push(CN_MARKET_DOWN);
      running += v;
    }
  }

  helperRaw.push(0);
  valueRaw.push(Number.isFinite(explained) ? explained : 0);
  barColors.push(CHART_ACCENT);

  const displayStrings = returnDecompositionWaterfallDisplayStrings(d);

  return {
    backgroundColor: "transparent",
    textStyle: { color: designTokens.color.neutral[700] },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items: unknown) => {
        const list = Array.isArray(items) ? items : [items];
        const bar = list.find((x: { seriesName?: string }) => x.seriesName === "鏁堝簲");
        const idx = (bar as { dataIndex?: number })?.dataIndex ?? 0;
        const label = WATERFALL_CATEGORIES[idx];
        return `${label}<br/>${displayStrings[idx] ?? "-"}`;
      },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 32, containLabel: true },
    xAxis: {
      type: "category",
      data: [...WATERFALL_CATEGORIES],
      axisLabel: { interval: 0, rotate: 0, ...CHART_AXIS },
      axisLine: { lineStyle: { color: designTokens.color.neutral[200] } },
    },
    yAxis: {
      type: "value",
      axisLabel: CHART_AXIS,
      splitLine: { lineStyle: { color: designTokens.color.neutral[200], type: "dashed" } },
    },
    series: [
      {
        name: "杈呭姪",
        type: "bar",
        stack: "waterfall",
        silent: true,
        itemStyle: TRANSPARENT_BAR,
        emphasis: { itemStyle: TRANSPARENT_BAR },
        data: helperRaw,
      },
      {
        name: "鏁堝簲",
        type: "bar",
        stack: "waterfall",
        data: valueRaw.map((val, i) => ({
          value: val,
          itemStyle: { color: barColors[i] },
        })),
      },
    ],
  };
}

interface Props {
  reportDate: string;
  periodType: PeriodType;
  assetClass?: BondAnalyticsAssetClassFilter;
  accountingClass?: BondAnalyticsAccountingClassFilter;
}

const effectColumns = [
  { title: "璧勪骇绫诲埆", dataIndex: "asset_class", key: "asset_class" },
  { title: "Carry锛堢エ鎭級", dataIndex: "carry", key: "carry", render: formatWan },
  { title: "Roll-down锛堥獞涔橈級", dataIndex: "roll_down", key: "roll_down", render: formatWan },
  { title: "鍒╃巼鏁堝簲", dataIndex: "rate_effect", key: "rate_effect", render: formatWan },
  { title: "鍒╁樊鏁堝簲", dataIndex: "spread_effect", key: "spread_effect", render: formatWan },
  {
    title: "Convexity",
    dataIndex: "convexity_effect",
    key: "convexity_effect",
    render: (v: ReturnDecompositionResponse["by_asset_class"][number]["convexity_effect"]) =>
      v ? formatWan(v) : "-",
  },
  { title: "浜ゆ槗", dataIndex: "trading", key: "trading", render: formatWan },
  { title: "鍚堣", dataIndex: "total", key: "total", render: formatWan },
  { title: "Bond Count", dataIndex: "bond_count", key: "bond_count" },
];

const accountingClassEffectColumns = effectColumns.map((col, i) =>
  i === 0 ? { ...col, title: "浼氳鍒嗙被", key: "accounting_slice" } : col,
);

const bondDetailColumns = [
  { title: "鍊哄埜浠ｇ爜", dataIndex: "bond_code", key: "bond_code" },
  {
    title: "Bond Name",
    dataIndex: "bond_name",
    key: "bond_name",
    render: (v: string | null) => v ?? "-",
  },
  { title: "璧勪骇绫诲埆", dataIndex: "asset_class", key: "asset_class" },
  { title: "浼氳鍒嗙被", dataIndex: "accounting_class", key: "accounting_class" },
  { title: "Market Value", dataIndex: "market_value", key: "market_value", render: formatWan },
  { title: "Carry锛堢エ鎭級", dataIndex: "carry", key: "carry", render: formatWan },
  { title: "Roll-down锛堥獞涔橈級", dataIndex: "roll_down", key: "roll_down", render: formatWan },
  { title: "鍒╃巼鏁堝簲", dataIndex: "rate_effect", key: "rate_effect", render: formatWan },
  { title: "鍒╁樊鏁堝簲", dataIndex: "spread_effect", key: "spread_effect", render: formatWan },
  {
    title: "Convexity",
    dataIndex: "convexity_effect",
    key: "convexity_effect",
    render: (v: ReturnDecompositionResponse["bond_details"][number]["convexity_effect"]) =>
      v ? formatWan(v) : "-",
  },
  { title: "浜ゆ槗", dataIndex: "trading", key: "trading", render: formatWan },
  { title: "鍚堣", dataIndex: "total", key: "total", render: formatWan },
  {
    title: "Explained (Recon)",
    dataIndex: "explained_for_recon",
    key: "explained_for_recon",
    render: formatWan,
  },
  {
    title: "Economic-only Effects",
    dataIndex: "economic_only_effects",
    key: "economic_only_effects",
    render: formatWan,
  },
];

export function ReturnDecompositionView({
  reportDate,
  periodType,
  assetClass = "all",
  accountingClass = "all",
}: Props) {
  const client = useApiClient();
  const [data, setData] = useState<ReturnDecompositionResponse | null>(null);
  const [meta, setMeta] = useState<ResultMeta | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      setMeta(null);
      try {
        const envelope =
          assetClass === "all" && accountingClass === "all"
            ? await client.getBondAnalyticsReturnDecomposition(reportDate, periodType)
            : await client.getBondAnalyticsReturnDecomposition(reportDate, periodType, {
                ...(assetClass !== "all" ? { assetClass } : {}),
                ...(accountingClass !== "all" ? { accountingClass } : {}),
              });
        if (!cancelled) {
          setData(envelope.result);
          setMeta(envelope.result_meta);
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setError((e as Error).message);
          setData(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    if (reportDate) fetchData();
    return () => {
      cancelled = true;
    };
  }, [accountingClass, assetClass, client, periodType, reportDate]);

  const waterfallOption = useMemo(
    () => (data ? buildWaterfallOption(data) : null),
    [data],
  );

  if (loading) return <Spin style={{ display: "block", margin: `${designTokens.space[8]}px auto` }} />;
  if (error) return <Alert type="error" message={`鍔犺浇澶辫触锛?{error}`} />;
  if (!data) return null;

  const metaIssues = describeMetaIssues(meta);
  const periodLabel = `${data.period_type} 路 ${data.period_start} 鈥?${data.period_end}`;

  const effects = [
    { label: "Carry锛堢エ鎭級", value: data.carry },
    { label: "Roll-down锛堥獞涔橈級", value: data.roll_down },
    { label: "鍒╃巼鏁堝簲", value: data.rate_effect },
    { label: "鍒╁樊鏁堝簲", value: data.spread_effect },
    { label: "FX鏁堝簲", value: data.fx_effect },
    { label: "Convexity", value: data.convexity_effect },
    { label: "浜ゆ槗", value: data.trading },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: designTokens.space[4] }}>
      <SectionLead
        eyebrow="Return Decomposition"
        title="鏀剁泭鍒嗚В姒傝"
        description="Reads the governed return-decomposition payload and shows economic, accounting, and OCI effects without front-end recomputation."
        testId="return-decomposition-shell-lead"
      />
      <Card size="small" title="鎶ュ憡鏈熼棿" data-testid="return-decomposition-period">
        <div style={{ fontSize: designTokens.fontSize[13], color: designTokens.color.neutral[700] }}>{periodLabel}</div>
        {data.computed_at ? (
          <div
            style={{
              fontSize: designTokens.fontSize[12],
              color: designTokens.color.neutral[600],
              marginTop: designTokens.space[2],
            }}
            data-testid="return-decomposition-computed-at"
          >
            {data.computed_at}
          </div>
        ) : null}
      </Card>
      {metaIssues.length > 0 ? (
        <Alert
          type="warning"
          showIcon
          message="Provenance degraded"
          description={metaIssues.join(" | ")}
          data-testid="return-decomposition-result-meta-alert"
        />
      ) : null}
      <Row gutter={16}>
        <Col span={8}>
          <Card size="small">
            <Statistic title="缁忔祹鍙ｅ緞鍚堣" value={formatWan(data.explained_pnl_economic ?? data.explained_pnl)} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="OCI Reserve Impact" value={formatWan(data.oci_reserve_impact)} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="Accounting PnL" value={formatWan(data.explained_pnl_accounting ?? data.explained_pnl)} />
          </Card>
        </Col>
      </Row>
      <Row gutter={16}>
        <Col span={12}>
          <Card size="small" data-testid="return-decomposition-bond-count">
            <Statistic title="鍊哄埜鍙暟锛堥《灞傦級" value={data.bond_count} />
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" data-testid="return-decomposition-total-mv">
            <Statistic title="Total Market Value" value={formatWan(data.total_market_value)} />
          </Card>
        </Col>
      </Row>

      <SectionLead
        eyebrow="Effects"
        title="鏀剁泭鏁堟灉鐎戝竷"
        description="Visualizes carry, roll-down, rate, spread, FX, convexity, and trading effects from the backend payload."
        testId="return-decomposition-effects-lead"
      />
      <Card title="鏀剁泭鏁堝簲鍒嗚В" size="small">
        <div style={{ display: "flex", gap: designTokens.space[3], flexWrap: "wrap" }}>
          {effects.map((e) => {
            const num = bondNumericRaw(e.value);
            const color = num >= 0 ? CN_MARKET_UP : CN_MARKET_DOWN;
            return (
              <div key={e.label} style={{ textAlign: "center", minWidth: 100 }}>
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[600] }}>{e.label}</div>
                <div style={{ fontSize: designTokens.fontSize[18], fontWeight: 600, color, ...tabularNumsStyle }}>
                  {formatWan(e.value)}
                </div>
              </div>
            );
          })}
        </div>
        {waterfallOption && (
          <div style={{ marginTop: designTokens.space[4] }}>
            <ReactECharts
              option={waterfallOption}
              style={{ height: 380, width: "100%" }}
              opts={{ renderer: "canvas" }}
            />
          </div>
        )}
      </Card>

      {data.by_asset_class && data.by_asset_class.length > 0 && (
        <Card title="By Asset Class" size="small">
          <Table
            dataSource={data.by_asset_class}
            columns={effectColumns}
            rowKey="asset_class"
            pagination={false}
            size="small"
          />
        </Card>
      )}

      {data.by_accounting_class && data.by_accounting_class.length > 0 && (
        <Card title="By Accounting Class" size="small" data-testid="return-decomposition-by-accounting-class">
          <Table
            dataSource={data.by_accounting_class}
            columns={accountingClassEffectColumns}
            rowKey={(row) => `${row.asset_class}`}
            pagination={false}
            size="small"
          />
        </Card>
      )}

      {data.bond_details && data.bond_details.length > 0 && (
        <Collapse
          bordered={false}
          data-testid="return-decomposition-bond-details-collapse"
          items={[
            {
              key: "bond-details",
              label: "鍒哥骇鎷嗚В锛堟寜鍒告槑缁嗭級",
              children: (
                <Table
                  data-testid="return-decomposition-bond-details-table"
                  dataSource={data.bond_details}
                  columns={bondDetailColumns}
                  rowKey={(row) => row.bond_code}
                  pagination={false}
                  size="small"
                  scroll={{ x: "max-content" }}
                />
              ),
            },
          ]}
        />
      )}
      <SectionLead
        eyebrow="Reconciliation"
        title="收益分解对账"
        description="Keeps reconciliation totals and residuals aligned with backend semantics without front-end adjustment."
        testId="return-decomposition-recon-lead"
      />
      <Card title="损益对账" size="small">
        <Row gutter={16}>
          <Col span={8}>
            <Statistic title="Explained PnL" value={formatWan(data.explained_pnl)} />
          </Col>
          <Col span={8}>
            <Statistic title="Actual PnL" value={formatWan(data.actual_pnl)} />
          </Col>
          <Col span={8}>
            <Statistic
              title="Recon Error"
              value={formatWan(data.recon_error)}
              suffix={data.recon_error_pct ? `(${data.recon_error_pct.display})` : ""}
            />
          </Col>
        </Row>
      </Card>

      {data.warnings.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message="鎻愮ず"
          description={data.warnings.map((w, i) => <div key={i}>{w}</div>)}
        />
      )}
      <FormalResultMetaPanel
        testId="return-decomposition-result-meta"
        title="Return Decomposition Provenance"
        sections={[
          {
            key: "return-decomposition",
            title: "Return decomposition",
            meta,
          },
        ]}
      />
    </div>
  );
}

