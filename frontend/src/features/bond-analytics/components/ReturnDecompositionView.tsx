import { useEffect, useMemo, useState } from "react";
import { Card, Statistic, Row, Col, Table, Alert, Collapse } from "antd";
import { useApiClient } from "../../../api/client";
import type { ResultMeta } from "../../../api/contracts";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import type {
  BondAnalyticsAccountingClassFilter,
  BondAnalyticsAssetClassFilter,
  PeriodType,
  ReturnDecompositionResponse,
} from "../types";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import { designTokens, nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { formatWan, formatYi } from "../utils/formatters";
import { buildReturnDecompositionWaterfallOption } from "../lib/returnDecompositionWaterfallOption";
import {
  DetailEmptyNote,
  DetailLoadErrorAlert,
  DetailPanelSkeleton,
  periodTypeLabel,
  withNumericColumns,
} from "./BondAnalyticsDetailPrimitives";
import detailStyles from "./BondAnalyticsDetailPrimitives.module.css";
import { SectionLead } from "./SectionLead";
import { ReturnDecompositionWaterfallChart } from "./ReturnDecompositionWaterfallChart";

/* 2026-08-11 全站决议（DESIGN §4）：绿涨红跌。正效应=绿、负效应=红；
   色值收敛到 Nocturne 去饱和语义常量（§2.2）。 */
const POSITIVE_CONTRIBUTION = nocturneTokens.color.green;
const NEGATIVE_CONTRIBUTION = nocturneTokens.color.red;

/**
 * 收益分解「计算时间」：解析 ISO 后取 UTC 分钟（截秒，不四舍五入），
 * 不依赖机器本地时区。无法解析的输入原样透出。
 */
// eslint-disable-next-line react-refresh/only-export-components
export function formatReturnDecompositionComputedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  const hours = String(date.getUTCHours()).padStart(2, "0");
  const minutes = String(date.getUTCMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

function metaQualityLabel(value: ResultMeta["quality_flag"]): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return value;
}

function metaVendorLabel(value: ResultMeta["vendor_status"]): string {
  if (value === "ok") return "正常";
  if (value === "vendor_stale") return "供应商数据陈旧";
  if (value === "vendor_unavailable") return "供应商不可用";
  return value;
}

function metaFallbackLabel(value: ResultMeta["fallback_mode"]): string {
  if (value === "none") return "未降级";
  if (value === "latest_snapshot") return "最新快照降级";
  return value;
}

function describeMetaIssues(meta: ResultMeta | null): string[] {
  if (!meta) return [];
  const issues: string[] = [];
  if (meta.quality_flag !== "ok") issues.push(`质量标记=${metaQualityLabel(meta.quality_flag)}`);
  if (meta.vendor_status !== "ok") issues.push(`供应商状态=${metaVendorLabel(meta.vendor_status)}`);
  if (meta.fallback_mode !== "none") issues.push(`降级模式=${metaFallbackLabel(meta.fallback_mode)}`);
  return issues;
}

interface Props {
  reportDate: string;
  periodType: PeriodType;
  assetClass?: BondAnalyticsAssetClassFilter;
  accountingClass?: BondAnalyticsAccountingClassFilter;
}

const effectColumns = withNumericColumns(
  [
    { title: "资产类别", dataIndex: "asset_class", key: "asset_class" },
    { title: "票息", dataIndex: "carry", key: "carry", render: formatWan },
    { title: "骑乘", dataIndex: "roll_down", key: "roll_down", render: formatWan },
    { title: "利率效应", dataIndex: "rate_effect", key: "rate_effect", render: formatWan },
    { title: "利差效应", dataIndex: "spread_effect", key: "spread_effect", render: formatWan },
    {
      title: "凸性",
      dataIndex: "convexity_effect",
      key: "convexity_effect",
      render: (v: ReturnDecompositionResponse["by_asset_class"][number]["convexity_effect"]) =>
        v ? formatWan(v) : EM_DASH,
    },
    { title: "交易", dataIndex: "trading", key: "trading", render: formatWan },
    { title: "合计", dataIndex: "total", key: "total", render: formatWan },
    { title: "债券只数", dataIndex: "bond_count", key: "bond_count" },
  ],
  [
    "carry",
    "roll_down",
    "rate_effect",
    "spread_effect",
    "convexity_effect",
    "trading",
    "total",
    "bond_count",
  ],
);

const accountingClassEffectColumns = effectColumns.map((col, i) =>
  i === 0 ? { ...col, title: "会计分类", key: "accounting_slice" } : col,
);

const bondDetailColumns = withNumericColumns(
  [
    { title: "债券代码", dataIndex: "bond_code", key: "bond_code" },
    {
      title: "债券名称",
      dataIndex: "bond_name",
      key: "bond_name",
      render: (v: string | null) => v ?? EM_DASH,
    },
    { title: "资产类别", dataIndex: "asset_class", key: "asset_class" },
    { title: "会计分类", dataIndex: "accounting_class", key: "accounting_class" },
    { title: "市值", dataIndex: "market_value", key: "market_value", render: formatYi },
    { title: "票息", dataIndex: "carry", key: "carry", render: formatWan },
    { title: "骑乘", dataIndex: "roll_down", key: "roll_down", render: formatWan },
    { title: "利率效应", dataIndex: "rate_effect", key: "rate_effect", render: formatWan },
    { title: "利差效应", dataIndex: "spread_effect", key: "spread_effect", render: formatWan },
    {
      title: "凸性",
      dataIndex: "convexity_effect",
      key: "convexity_effect",
      render: (v: ReturnDecompositionResponse["bond_details"][number]["convexity_effect"]) =>
        v ? formatWan(v) : EM_DASH,
    },
    { title: "交易", dataIndex: "trading", key: "trading", render: formatWan },
    { title: "合计", dataIndex: "total", key: "total", render: formatWan },
    {
      title: "解释项（对账）",
      dataIndex: "explained_for_recon",
      key: "explained_for_recon",
      render: formatWan,
    },
    {
      title: "仅经济口径效应",
      dataIndex: "economic_only_effects",
      key: "economic_only_effects",
      render: formatWan,
    },
  ],
  [
    "market_value",
    "carry",
    "roll_down",
    "rate_effect",
    "spread_effect",
    "convexity_effect",
    "trading",
    "total",
    "explained_for_recon",
    "economic_only_effects",
  ],
);

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
    () => {
      if (!data) return null;
      const hasSeries = [
        data.carry,
        data.roll_down,
        data.rate_effect,
        data.spread_effect,
        data.fx_effect,
        data.convexity_effect,
        data.trading,
      ].some((value) => bondNumericRaw(value) !== null);
      return hasSeries
        ? nocturneChartTheme.createBarChartOption(
            buildReturnDecompositionWaterfallOption(data),
          )
        : null;
    },
    [data],
  );

  if (loading) return <DetailPanelSkeleton testId="return-decomposition-loading" />;
  if (error) return <DetailLoadErrorAlert error={error} testId="return-decomposition-error" />;
  if (!data) return null;

  const metaIssues = describeMetaIssues(meta);
  const periodLabel = `${periodTypeLabel(data.period_type)} · ${data.period_start} 至 ${data.period_end}`;

  const effects = [
    { label: "票息", value: data.carry },
    { label: "骑乘", value: data.roll_down },
    { label: "利率效应", value: data.rate_effect },
    { label: "利差效应", value: data.spread_effect },
    { label: "外汇效应", value: data.fx_effect },
    { label: "凸性", value: data.convexity_effect },
    { label: "交易", value: data.trading },
  ];
  /* 缺失效应不补 0 进瀑布：区头披露 partial，图上对应柱断开（合计柱缺失同样披露）。 */
  const missingEffects = effects
    .filter((e) => bondNumericRaw(e.value) === null)
    .map((e) => e.label);
  if (bondNumericRaw(data.explained_pnl) === null) {
    missingEffects.push("合计（解释损益）");
  }

  return (
    <div className={detailStyles.view}>
      <SectionLead
        eyebrow="收益分解"
        title="收益分解概览"
        description="读取治理后的收益分解结果，展示经济、会计和 OCI 影响，不在前端重复计算。"
        testId="return-decomposition-shell-lead"
      />
      <Card size="small" title="报告期间" data-testid="return-decomposition-period">
        <div style={{ fontSize: designTokens.fontSize[13], color: "var(--dh-api-soft)" }}>{periodLabel}</div>
        {data.computed_at ? (
          <div
            style={{
              fontSize: designTokens.fontSize[12],
              color: "var(--dh-api-muted)",
              marginTop: designTokens.space[2],
            }}
            data-testid="return-decomposition-computed-at"
          >
            计算时间 {formatReturnDecompositionComputedAt(data.computed_at)}
          </div>
        ) : null}
      </Card>
      {metaIssues.length > 0 ? (
        <Alert
          type="warning"
          showIcon
          message="证据链降级"
          description={metaIssues.join(" | ")}
          data-testid="return-decomposition-result-meta-alert"
        />
      ) : null}
      <Row gutter={[12, 12]} className={detailStyles.kpiGrid}>
        <Col span={8}>
          <Card size="small">
            <Statistic title="经济口径合计" value={formatWan(data.explained_pnl_economic ?? data.explained_pnl)} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="OCI 储备影响" value={formatWan(data.oci_reserve_impact)} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="会计损益" value={formatWan(data.explained_pnl_accounting ?? data.explained_pnl)} />
          </Card>
        </Col>
      </Row>
      <Row gutter={[12, 12]} className={detailStyles.kpiGrid}>
        <Col span={12}>
          <Card size="small" data-testid="return-decomposition-bond-count">
            <Statistic title="债券只数（顶层）" value={data.bond_count} />
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" data-testid="return-decomposition-total-mv">
            <Statistic title="总市值" value={formatYi(data.total_market_value)} />
          </Card>
        </Col>
      </Row>

      <SectionLead
        eyebrow="效应"
        title="收益效应瀑布"
        description="按后端结果展示票息、骑乘、利率、利差、外汇、凸性和交易效应。"
        testId="return-decomposition-effects-lead"
      />
      {missingEffects.length > 0 ? (
        <div
          data-testid="return-decomposition-partial-note"
          style={{ fontSize: designTokens.fontSize[12], color: "var(--dh-api-amber)" }}
        >
          归因部分缺失：{missingEffects.join(" / ")} 未返回，瀑布图对应柱断开，不补 0。
        </div>
      ) : null}
      <Card title="收益效应分解" size="small">
        <div className={detailStyles.effectGrid}>
          {effects.map((e) => {
            const num = bondNumericRaw(e.value);
            const color =
              num === null ? nocturneTokens.color.ink : num >= 0 ? POSITIVE_CONTRIBUTION : NEGATIVE_CONTRIBUTION;
            return (
              <div key={e.label} className={detailStyles.effectMetric}>
                <div className={detailStyles.effectLabel}>{e.label}</div>
                <div className={detailStyles.effectValue} style={{ color }}>
                  {formatWan(e.value)}
                </div>
              </div>
            );
          })}
        </div>
        {waterfallOption ? (
          <div className={detailStyles.chartStage}>
            <ReturnDecompositionWaterfallChart option={waterfallOption} height={380} />
          </div>
        ) : (
          <DetailEmptyNote testId="return-decomposition-chart-empty">
            暂无收益效应序列
          </DetailEmptyNote>
        )}
      </Card>

      {data.by_asset_class && data.by_asset_class.length > 0 && (
        <Card title="按资产类别" size="small">
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
        <Card title="按会计分类" size="small" data-testid="return-decomposition-by-accounting-class">
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
              label: "券级拆解（按券明细）",
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
        eyebrow="对账"
        title="收益分解对账"
        description="保持对账合计与残差遵循后端语义，不在前端做调整。"
        testId="return-decomposition-recon-lead"
      />
      <Card title="损益对账" size="small">
        <Row gutter={[12, 12]} className={detailStyles.kpiGrid}>
          <Col span={8}>
            <Statistic title="解释损益" value={formatWan(data.explained_pnl)} />
          </Col>
          <Col span={8}>
            <Statistic title="实际损益" value={formatWan(data.actual_pnl)} />
          </Col>
          <Col span={8}>
            <Statistic
              title="对账差异"
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
          message="提示"
          description={data.warnings.map((w, i) => <div key={i}>{w}</div>)}
        />
      )}
      <FormalResultMetaPanel
        testId="return-decomposition-result-meta"
        title="收益分解证据"
        sections={[
          {
            key: "return-decomposition",
            title: "收益分解",
            meta,
          },
        ]}
      />
    </div>
  );
}
