import { useQuery } from "@tanstack/react-query";
import { Card, Statistic, Row, Col, Table, Tag, Alert } from "antd";
import { useApiClient } from "../../../api/client";
import type { ApiEnvelope, Numeric, ResultMeta } from "../../../api/contracts";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { bondNumericDisplay, bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { PeriodType, ActionAttributionResponse } from "../types";
import { ACTION_TYPE_NAMES } from "../types";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { formatDv01Wan, formatWan } from "../utils/formatters";
import { bondAnalyticsQueryKeyRoot } from "../lib/bondAnalyticsQueryKeys";
import {
  DetailEmptyNote,
  DetailLoadErrorAlert,
  DetailPanelSkeleton,
  formatDetailComputedAt,
  periodTypeLabel,
  withNumericColumns,
} from "./BondAnalyticsDetailPrimitives";
import detailStyles from "./BondAnalyticsDetailPrimitives.module.css";
import { SectionLead } from "./SectionLead";

interface Props {
  reportDate: string;
  periodType: PeriodType;
}

const ACTION_COLORS: Record<string, string> = {
  ADD_DURATION: nocturneTokens.color.blue,
  REDUCE_DURATION: nocturneTokens.color.amber,
  SWITCH: nocturneTokens.color.inkSoft,
  CREDIT_DOWN: nocturneTokens.color.red,
  CREDIT_UP: nocturneTokens.color.green,
  TIMING_BUY: nocturneTokens.color.accent300,
  TIMING_SELL: nocturneTokens.color.amber,
  HEDGE: nocturneTokens.color.inkMuted,
};

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

/** 读面状态后端 token 中文化；未登记枚举原样透出（ledger-pnl 先例）。 */
function readinessStatusText(value: string): string {
  if (value === "ready") return "可用";
  if (value === "ok") return "正常";
  if (value === "partial") return "部分可用";
  if (value === "blocked") return "阻塞";
  return value;
}

/** KPI 久期读数收敛 2 位小数展示（后端 8 位全精度收进 title），无法解析的输入原样透出；
    四舍五入后的负零归正零（首页负零变动归中性先例）。 */
function durationKpiDisplay(v: Numeric | null | undefined): string {
  const raw = bondNumericRaw(v);
  if (raw === null) return bondNumericDisplay(v);
  const fixed = raw.toFixed(2);
  return fixed === "-0.00" ? "0.00" : fixed;
}

function describeMetaIssues(meta: ResultMeta | null): string[] {
  if (!meta) return [];
  const issues: string[] = [];
  if (meta.quality_flag !== "ok") issues.push(`质量标记=${metaQualityLabel(meta.quality_flag)}`);
  if (meta.vendor_status !== "ok") issues.push(`供应商状态=${metaVendorLabel(meta.vendor_status)}`);
  if (meta.fallback_mode !== "none") issues.push(`降级模式=${metaFallbackLabel(meta.fallback_mode)}`);
  return issues;
}

/* 2026-08-11 全站决议（DESIGN §4）：绿涨红跌。正损益=绿、负损益=红、零值中性不着色。 */
function pnlToneColor(num: number | null): string | undefined {
  if (num === null || num === 0) return undefined;
  return num > 0 ? "var(--dh-api-green)" : "var(--dh-api-red)";
}

function buildDetailColumns(includeOpportunityCost: boolean) {
  const baseColumns = [
    { title: "日期", dataIndex: "action_date", key: "action_date", width: 100 },
    {
      title: "类型",
      dataIndex: "action_type",
      key: "action_type",
      width: 100,
      render: (type: string) => (
        <Tag color={ACTION_COLORS[type] || "default"}>
          {ACTION_TYPE_NAMES[type] || type}
        </Tag>
      ),
    },
    {
      title: "描述",
      dataIndex: "description",
      key: "description",
      /* 无 width 的自适应列在 scroll.x 布局下会被挤到 1 字宽逐字竖排：锁最小可读宽度，全文入行 title。 */
      width: 220,
      ellipsis: true,
      render: (v: string | null | undefined) =>
        v?.trim() ? <span title={v}>{v}</span> : EM_DASH,
    },
    {
      title: "损益贡献",
      dataIndex: "pnl_economic",
      key: "pnl_economic",
      width: 120,
      render: (v: Numeric) => {
        const num = bondNumericRaw(v);
        return <span style={{ color: pnlToneColor(num) }}>{formatWan(v)}</span>;
      },
    },
    {
      title: "Δ久期",
      dataIndex: "delta_duration",
      key: "delta_duration",
      width: 80,
      render: (v: Numeric) => v.display,
    },
    {
      title: "会计损益",
      dataIndex: "pnl_accounting",
      key: "pnl_accounting",
      width: 110,
      render: (v: Numeric) => {
        const num = bondNumericRaw(v);
        return <span style={{ color: pnlToneColor(num) }}>{formatWan(v)}</span>;
      },
    },
    {
      title: "ΔDV01（万元/bp）",
      dataIndex: "delta_dv01",
      key: "delta_dv01",
      width: 100,
      render: (v: Numeric | null) => (v ? formatDv01Wan(v) : "不可用"),
    },
    {
      title: "Δ利差DV01（万元/bp）",
      dataIndex: "delta_spread_dv01",
      key: "delta_spread_dv01",
      width: 110,
      render: (v: Numeric | null) => (v ? formatDv01Wan(v) : "不可用"),
    },
    {
      title: "涉及债券",
      dataIndex: "bonds_involved",
      key: "bonds_involved",
      width: 120,
      render: (codes: string[]) => (codes?.length ? codes.join(", ") : EM_DASH),
    },
  ];
  if (!includeOpportunityCost) {
    return withNumericColumns(baseColumns, [
      "pnl_economic",
      "delta_duration",
      "pnl_accounting",
      "delta_dv01",
      "delta_spread_dv01",
    ]);
  }
  return withNumericColumns(
    [
      ...baseColumns,
      {
        title: "机会成本",
        key: "opportunity_cost",
        width: 100,
        render: (_: unknown, row: { opportunity_cost?: Numeric }) =>
          row.opportunity_cost ? formatWan(row.opportunity_cost) : EM_DASH,
      },
      {
        title: "机会成本口径",
        key: "opportunity_cost_method",
        width: 110,
        ellipsis: true,
        render: (_: unknown, row: { opportunity_cost_method?: string }) =>
          row.opportunity_cost_method?.trim() ? row.opportunity_cost_method : EM_DASH,
      },
    ],
    [
      "pnl_economic",
      "delta_duration",
      "pnl_accounting",
      "delta_dv01",
      "delta_spread_dv01",
      "opportunity_cost",
    ],
  );
}

export function ActionAttributionView({ reportDate, periodType }: Props) {
  const client = useApiClient();
  const query = useQuery({
    queryKey: [...bondAnalyticsQueryKeyRoot, "overview-action-attribution", client.mode, reportDate, periodType],
    queryFn: (): Promise<ApiEnvelope<ActionAttributionResponse>> =>
      client.getBondAnalyticsActionAttribution(reportDate, periodType),
    enabled: Boolean(reportDate),
    retry: false,
  });

  if (!reportDate) return null;
  if (query.isPending) return <DetailPanelSkeleton testId="action-attribution-loading" />;
  if (query.isError)
    return (
      <DetailLoadErrorAlert
        error={query.error instanceof Error ? query.error.message : String(query.error)}
        testId="action-attribution-error"
      />
    );
  const data = query.data?.result;
  const meta = query.data?.result_meta ?? null;
  if (!data) return null;

  const hasReadinessMeta =
    (data.status !== undefined &&
      data.status !== null &&
      data.status !== "" &&
      data.status !== "ok") ||
    (data.available_components?.length ?? 0) > 0 ||
    (data.missing_inputs?.length ?? 0) > 0 ||
    (data.blocked_components?.length ?? 0) > 0;
  const metaIssues = describeMetaIssues(meta);
  /* 机会成本两列整列缺失时不再铺两列 —：隐藏列，缺失原因在表头注记出现一次（DESIGN §6）。 */
  const hasOpportunityCost = data.action_details.some(
    (row) => row.opportunity_cost || row.opportunity_cost_method?.trim(),
  );
  const detailColumns = buildDetailColumns(hasOpportunityCost);

  return (
    <div className={detailStyles.view}>
      <SectionLead
        eyebrow="动作归因"
        title="交易动作归因概览"
        description="读取治理后的动作归因结果，展示动作数量、损益贡献、久期和 DV01，不在前端重复计算。"
        testId="action-attribution-shell-lead"
      />
      <div
        style={{ fontSize: 12, color: "var(--dh-api-muted)", lineHeight: 1.65 }}
        data-testid="action-attribution-meta"
      >
        <span>报告日 {data.report_date}</span>
        <span style={{ margin: "0 0.5em", opacity: 0.45 }}>|</span>
        <span>期间 {periodTypeLabel(data.period_type)}</span>
        <span style={{ margin: "0 0.5em", opacity: 0.45 }}>|</span>
        <span>
          {data.period_start} — {data.period_end}
        </span>
        {data.computed_at ? (
          <>
            <span style={{ margin: "0 0.5em", opacity: 0.45 }}>|</span>
            <span>计算时间 {formatDetailComputedAt(data.computed_at)}</span>
          </>
        ) : null}
      </div>
      {metaIssues.length > 0 ? (
        <Alert
          type="warning"
          showIcon
          message="证据链降级"
          description={metaIssues.join(" | ")}
          data-testid="action-attribution-result-meta-alert"
        />
      ) : null}
      {hasReadinessMeta ? (
        <Alert
          type={data.status && data.status !== "ok" ? "warning" : "info"}
          showIcon
          message={data.status ? `读面状态：${readinessStatusText(data.status)}` : "读面组件信息"}
          description={
            <div style={{ fontSize: 13, lineHeight: 1.65 }}>
              {(data.available_components?.length ?? 0) > 0 ? (
                /* 组件技术名属证据层：正文只报数量，明细收进 title 供复核（DESIGN §6 溯源分层）。 */
                <div title={data.available_components!.join(" / ")}>
                  可用组件 {data.available_components!.length} 项（明细悬停查看）
                </div>
              ) : null}
              {(data.missing_inputs?.length ?? 0) > 0 ? (
                <div title={data.missing_inputs!.join(" / ")}>
                  缺失输入 {data.missing_inputs!.length} 项（明细悬停查看）
                </div>
              ) : null}
              {(data.blocked_components?.length ?? 0) > 0 ? (
                <div title={data.blocked_components!.join(" / ")}>
                  阻塞组件 {data.blocked_components!.length} 项（明细悬停查看）
                </div>
              ) : null}
            </div>
          }
          data-testid="action-attribution-readiness"
        />
      ) : null}
      <Row gutter={[12, 12]} className={detailStyles.kpiGrid}>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small">
            <Statistic title="动作数量" value={data.total_actions} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small">
            <Statistic title="动作贡献损益" value={formatWan(data.total_pnl_from_actions)} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small">
            <span
              title={`全精度：${bondNumericDisplay(data.period_start_duration)} → ${bondNumericDisplay(data.period_end_duration)}（Δ ${bondNumericDisplay(data.duration_change_from_actions)}）`}
            >
              <Statistic
                title="久期变化"
                value={`${durationKpiDisplay(data.period_start_duration)} → ${durationKpiDisplay(data.period_end_duration)}`}
                suffix={`Δ ${durationKpiDisplay(data.duration_change_from_actions)}`}
              />
            </span>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small">
            {data.period_start_dv01 && data.period_end_dv01 ? (
              <Statistic
                title="DV01变化（万元/bp）"
                value={`${formatDv01Wan(data.period_start_dv01)} → ${formatDv01Wan(data.period_end_dv01)}`}
              />
            ) : (
              <Statistic
                title="DV01变化（万元/bp）"
                value="不可用"
                data-testid="action-attribution-dv01-unavailable"
              />
            )}
          </Card>
        </Col>
      </Row>

      <SectionLead
        eyebrow="汇总"
        title="动作汇总"
        description="按动作类型汇总次数和损益，同时保留后端贡献值。"
        testId="action-attribution-summary-lead"
      />
      <Alert
        type="warning"
        showIcon
        message="会计损益不可独立核对"
        description="会计损益当前由经济损益复制派生，不能独立核对；接入独立会计口径前仅作候选展示。"
        data-testid="action-attribution-accounting-derived-note"
      />
      <Card title="按动作类型" size="small">
        {data.by_action_type.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {data.by_action_type.map((item) => {
              const pnl = bondNumericRaw(item.total_pnl_economic);
              const totalPnl = bondNumericRaw(data.total_pnl_from_actions);
              const pct = pnl !== null && totalPnl !== null && totalPnl !== 0 ? (pnl / totalPnl) * 100 : 0;
              const pnlColor = pnl === null ? "var(--dh-api-muted)" : pnlToneColor(pnl);
              return (
                <div key={item.action_type} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <Tag color={ACTION_COLORS[item.action_type] || "default"} style={{ width: 80, textAlign: "center" }}>
                    {item.action_type_name}
                  </Tag>
                  <span style={{ width: 50, textAlign: "right", fontSize: 12, color: "var(--dh-api-muted)" }}>
                    {item.action_count}次
                  </span>
                  <div
                    style={{
                      flex: 1,
                      height: 20,
                      background: "var(--dh-api-panel-2)",
                      borderRadius: 4,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.min(Math.abs(pct), 100)}%`,
                        background: ACTION_COLORS[item.action_type] || nocturneTokens.color.inkMuted,
                        borderRadius: 4,
                      }}
                    />
                  </div>
                  <div
                    style={{
                      width: 200,
                      textAlign: "right",
                      fontSize: 12,
                      color: "var(--dh-api-muted)",
                      lineHeight: 1.4,
                    }}
                  >
                    <div style={{ fontVariantNumeric: "tabular-nums", color: pnlColor }}>
                      经济 {formatWan(item.total_pnl_economic)}
                    </div>
                    <div style={{ fontVariantNumeric: "tabular-nums" }}>
                      会计 {formatWan(item.total_pnl_accounting)}
                    </div>
                    <div style={{ fontVariantNumeric: "tabular-nums" }}>
                      均次 {formatWan(item.avg_pnl_per_action)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <DetailEmptyNote testId="action-attribution-summary-empty">
            暂无动作类型汇总
          </DetailEmptyNote>
        )}
      </Card>

      <SectionLead
        eyebrow="明细"
        title="动作明细"
        description="保留后端动作明细载荷中的类型、说明、损益、久期和 DV01 变动。"
        testId="action-attribution-detail-lead"
      />
      <Card title="动作明细" size="small">
        {data.action_details.length > 0 ? (
          <>
            {!hasOpportunityCost ? (
              <div
                data-testid="action-attribution-opportunity-cost-note"
                style={{ marginBottom: 8, fontSize: 12, color: "var(--dh-api-muted)" }}
              >
                机会成本与机会成本口径本期后端未返回，两列暂不列出。
              </div>
            ) : null}
            <Table
              dataSource={data.action_details}
              columns={detailColumns}
              rowKey="action_id"
              pagination={false}
              size="small"
              scroll={{ x: 960, y: 400 }}
            />
          </>
        ) : (
          <DetailEmptyNote testId="action-attribution-detail-empty">
            暂无动作明细
          </DetailEmptyNote>
        )}
      </Card>
      {data.warnings.length > 0 && (
        /* 技术口径 disclosure（大写代码 + 英文说明）默认折叠（risk-overview 先例），
           展开后原文逐字保留，不改写证据内容。 */
        <details
          className={detailStyles.warningsDisclosure}
          data-testid="action-attribution-warnings-disclosure"
        >
          <summary>口径与启发式提示（{data.warnings.length} 条）</summary>
          <div className={detailStyles.warningsDisclosureBody}>
            {data.warnings.map((w, i) => (
              <div key={i}>{w}</div>
            ))}
          </div>
        </details>
      )}
      <FormalResultMetaPanel
        testId="action-attribution-result-meta"
        title="动作归因证据"
        sections={[
          {
            key: "action-attribution",
            title: "动作归因",
            meta,
          },
        ]}
      />
    </div>
  );
}
