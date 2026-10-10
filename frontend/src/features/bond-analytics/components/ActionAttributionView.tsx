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
import styles from "./ActionAttributionView.module.css";
import { SectionHead } from "../../../components/layout";

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
      <SectionHead
        category="动作归因"
        title="交易动作归因概览"
        note="查看交易动作对损益、久期和 DV01 的影响。"
        testId="action-attribution-shell-lead"
        numbered={false}
      />
      <div className={styles.metaLine} data-testid="action-attribution-meta">
        <span>报告日 {data.report_date}</span>
        <span className={styles.metaSeparator}>|</span>
        <span>期间 {periodTypeLabel(data.period_type)}</span>
        <span className={styles.metaSeparator}>|</span>
        <span>
          {data.period_start} — {data.period_end}
        </span>
        {data.computed_at ? (
          <>
            <span className={styles.metaSeparator}>|</span>
            <span>计算时间 {formatDetailComputedAt(data.computed_at)}</span>
          </>
        ) : null}
      </div>
      {data.snapshot_window ? (
        <Alert type="info" showIcon message="持仓比较实际日期" data-testid="action-attribution-snapshot-window"
          description={<span>请求期初 {data.snapshot_window.requested_start}；实际期初 {data.snapshot_window.resolved_start ?? EM_DASH}，
            与请求期初相隔 {data.snapshot_window.start_gap_days ?? EM_DASH} 天；实际期末 {data.snapshot_window.resolved_end ?? EM_DASH}。
            可接受陈旧天数待确认；缺少期初时无法识别新增动作。</span>} />
      ) : null}
      {data.pnl_coverage ? (
        <Alert type={data.pnl_coverage.status === "partial" ? "warning" : "info"} showIcon
          message="期间损益分配范围" data-testid="action-attribution-pnl-coverage"
          description={<span>完整输入 {formatWan(data.pnl_coverage.input_pnl)}（{data.pnl_coverage.input_key_count} 个键），
            已识别动作 {formatWan(data.pnl_coverage.identified_pnl)}，未分配 {formatWan(data.pnl_coverage.unallocated_pnl)}
            （{data.pnl_coverage.unallocated_key_count} 个键、绝对金额 {formatWan(data.pnl_coverage.unallocated_absolute_pnl)}）。
            两端无持仓的损益 {formatWan(data.pnl_coverage.pnl_only_pnl)}（{data.pnl_coverage.pnl_only_key_count} 个键、
            绝对金额 {formatWan(data.pnl_coverage.pnl_only_absolute_pnl)}）；金额闭合差异 {formatWan(data.pnl_coverage.reconciliation_difference)}。
            {data.pnl_coverage.missing_months?.length ? `月度输入不完整，缺少 ${data.pnl_coverage.missing_months.join("、")}；未以零值或更早月份补齐。` : null}
            未分配键不计入已识别动作数量。</span>} />
      ) : null}
      {metaIssues.length > 0 ? (
        <Alert
          type="warning"
          showIcon
          message="数据使用限制"
          description={metaIssues.join(" | ")}
          data-testid="action-attribution-result-meta-alert"
        />
      ) : null}
      {hasReadinessMeta ? (
        <Alert
          type={data.status && data.status !== "ok" ? "warning" : "info"}
          showIcon
          message={data.status ? `分析状态：${readinessStatusText(data.status)}` : "分析数据范围"}
          description={
            <div className={styles.readinessBody}>
              {(data.available_components?.length ?? 0) > 0 ? (
                <div>
                  可用分析 {data.available_components!.length} 项
                </div>
              ) : null}
              {(data.missing_inputs?.length ?? 0) > 0 ? (
                <div>
                  缺少分析所需数据 {data.missing_inputs!.length} 项
                </div>
              ) : null}
              {(data.blocked_components?.length ?? 0) > 0 ? (
                <div>
                  暂不可用分析 {data.blocked_components!.length} 项
                </div>
              ) : null}
              <details data-testid="action-attribution-readiness-diagnostics">
                <summary>技术诊断</summary>
                <div>available_components：{data.available_components?.join(" / ") || EM_DASH}</div>
                <div>missing_inputs：{data.missing_inputs?.join(" / ") || EM_DASH}</div>
                <div>blocked_components：{data.blocked_components?.join(" / ") || EM_DASH}</div>
              </details>
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
            <Statistic title="期间损益（含未分配）" value={formatWan(data.total_pnl_from_actions)} />
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

      <SectionHead
        category="汇总"
        title="动作汇总"
        note="按动作类型比较次数和损益贡献。"
        testId="action-attribution-summary-lead"
        numbered={false}
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
          <div className={styles.summaryList}>
            {data.by_action_type.map((item) => {
              const pnl = bondNumericRaw(item.total_pnl_economic);
              const totalPnl = bondNumericRaw(data.total_pnl_from_actions);
              const pct = pnl !== null && totalPnl !== null && totalPnl !== 0 ? (pnl / totalPnl) * 100 : 0;
              const pnlColor = pnl === null ? "var(--dh-api-muted)" : pnlToneColor(pnl);
              return (
                <div key={item.action_type} className={styles.summaryRow}>
                  <Tag color={ACTION_COLORS[item.action_type] || "default"} className={styles.typeTag}>
                    {item.action_type_name}
                  </Tag>
                  <span className={styles.summaryCount}>
                    {item.action_count}{item.action_type === "UNALLOCATED" ? "个键" : "次"}
                  </span>
                  <div className={styles.summaryTrack} style={{ borderRadius: 4 }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.min(Math.abs(pct), 100)}%`,
                        background: ACTION_COLORS[item.action_type] || nocturneTokens.color.inkMuted,
                        borderRadius: 4,
                      }}
                    />
                  </div>
                  <div className={styles.summaryPnl}>
                    <div style={{ fontVariantNumeric: "tabular-nums", color: pnlColor }}>
                      经济 {formatWan(item.total_pnl_economic)}
                    </div>
                    <div className={styles.tabularNums}>
                      会计 {formatWan(item.total_pnl_accounting)}
                    </div>
                    <div className={styles.tabularNums}>
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

      <SectionHead
        category="明细"
        title="动作明细"
        note="查看每项动作的说明、损益及久期和 DV01 变动。"
        testId="action-attribution-detail-lead"
        numbered={false}
      />
      <Card title="动作明细" size="small">
        {data.action_details.length > 0 ? (
          <>
            {!hasOpportunityCost ? (
              <div
                data-testid="action-attribution-opportunity-cost-note"
                className={styles.opportunityCostNote}
              >
                本期缺少机会成本及其计算口径，暂不展示这两列。
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
