import { useEffect, useState } from "react";
import { Card, Statistic, Row, Col, Table, Tag, Alert, Spin } from "antd";
import { useApiClient } from "../../../api/client";
import type { Numeric, ResultMeta } from "../../../api/contracts";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { PeriodType, ActionAttributionResponse } from "../types";
import { ACTION_TYPE_NAMES } from "../types";
import { formatWan } from "../utils/formatters";
import { SectionLead } from "./SectionLead";

interface Props {
  reportDate: string;
  periodType: PeriodType;
}

const ACTION_COLORS: Record<string, string> = {
  ADD_DURATION: "#1890ff",
  REDUCE_DURATION: "#faad14",
  SWITCH: "#722ed1",
  CREDIT_DOWN: "#eb2f96",
  CREDIT_UP: "#52c41a",
  TIMING_BUY: "#13c2c2",
  TIMING_SELL: "#fa541c",
  HEDGE: "#8c8c8c",
};

function describeMetaIssues(meta: ResultMeta | null): string[] {
  if (!meta) return [];
  const issues: string[] = [];
  if (meta.quality_flag !== "ok") issues.push(`质量标记=${meta.quality_flag}`);
  if (meta.vendor_status !== "ok") issues.push(`供应商状态=${meta.vendor_status}`);
  if (meta.fallback_mode !== "none") issues.push(`降级模式=${meta.fallback_mode}`);
  return issues;
}

const detailColumns = [
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
  { title: "描述", dataIndex: "description", key: "description", ellipsis: true },
  {
    title: "损益贡献",
    dataIndex: "pnl_economic",
    key: "pnl_economic",
    width: 120,
    render: (v: Numeric) => {
      const num = bondNumericRaw(v);
      const color = num >= 0 ? "#cf1322" : "#3f8600";
      return <span style={{ color, fontVariantNumeric: "tabular-nums" }}>{formatWan(v)}</span>;
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
      const color = num >= 0 ? "#cf1322" : "#3f8600";
      return <span style={{ color, fontVariantNumeric: "tabular-nums" }}>{formatWan(v)}</span>;
    },
  },
  {
    title: "ΔDV01",
    dataIndex: "delta_dv01",
    key: "delta_dv01",
    width: 100,
    render: (v: Numeric) => v.display,
  },
  {
    title: "Δ利差DV01",
    dataIndex: "delta_spread_dv01",
    key: "delta_spread_dv01",
    width: 110,
    render: (v: Numeric) => v.display,
  },
  {
    title: "涉及债券",
    dataIndex: "bonds_involved",
    key: "bonds_involved",
    width: 120,
    render: (codes: string[]) => (codes?.length ? codes.join(", ") : "-"),
  },
  {
    title: "机会成本",
    key: "opportunity_cost",
    width: 100,
    render: (_: unknown, row: { opportunity_cost?: Numeric }) =>
      row.opportunity_cost ? formatWan(row.opportunity_cost) : "-",
  },
  {
    title: "机会成本口径",
    key: "opportunity_cost_method",
    width: 110,
    ellipsis: true,
    render: (_: unknown, row: { opportunity_cost_method?: string }) =>
      row.opportunity_cost_method?.trim() ? row.opportunity_cost_method : "-",
  },
];

export function ActionAttributionView({ reportDate, periodType }: Props) {
  const client = useApiClient();
  const [data, setData] = useState<ActionAttributionResponse | null>(null);
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
        const envelope = await client.getBondAnalyticsActionAttribution(reportDate, periodType);
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
  }, [client, reportDate, periodType]);

  if (loading) return <Spin style={{ display: "block", margin: "40px auto" }} />;
  if (error) return <Alert type="error" message={`加载失败：${error}`} />;
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

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SectionLead
        eyebrow="动作归因"
        title="交易动作归因概览"
        description="读取治理后的动作归因结果，展示动作数量、损益贡献、久期和 DV01，不在前端重复计算。"
        testId="action-attribution-shell-lead"
      />
      <div
        style={{ fontSize: 12, color: "#8090a8", lineHeight: 1.65 }}
        data-testid="action-attribution-meta"
      >
        <span>报告日 {data.report_date}</span>
        <span style={{ margin: "0 0.5em", opacity: 0.45 }}>|</span>
        <span>期间 {data.period_type}</span>
        <span style={{ margin: "0 0.5em", opacity: 0.45 }}>|</span>
        <span>
          {data.period_start} — {data.period_end}
        </span>
        {data.computed_at ? (
          <>
            <span style={{ margin: "0 0.5em", opacity: 0.45 }}>|</span>
            <span>计算时间 {data.computed_at}</span>
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
          message={data.status ? `读面状态：${data.status}` : "读面组件信息"}
          description={
            <div style={{ fontSize: 13, lineHeight: 1.65 }}>
              {(data.available_components?.length ?? 0) > 0 ? (
                <div>可用组件：{data.available_components!.join(" / ")}</div>
              ) : null}
              {(data.missing_inputs?.length ?? 0) > 0 ? (
                <div>缺失输入：{data.missing_inputs!.join(" / ")}</div>
              ) : null}
              {(data.blocked_components?.length ?? 0) > 0 ? (
                <div>阻塞组件：{data.blocked_components!.join(" / ")}</div>
              ) : null}
            </div>
          }
          data-testid="action-attribution-readiness"
        />
      ) : null}
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="动作数量" value={data.total_actions} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="动作贡献损益" value={formatWan(data.total_pnl_from_actions)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="久期变化"
              value={`${data.period_start_duration.display} → ${data.period_end_duration.display}`}
              suffix={`Δ ${data.duration_change_from_actions.display}`}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="DV01变化"
              value={`${formatWan(data.period_start_dv01)} → ${formatWan(data.period_end_dv01)}`}
            />
          </Card>
        </Col>
      </Row>

      <SectionLead
        eyebrow="汇总"
        title="动作汇总"
        description="按动作类型汇总次数和损益，同时保留后端贡献值。"
        testId="action-attribution-summary-lead"
      />
      {data.by_action_type.length > 0 && (
        <Card title="按动作类型" size="small">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {data.by_action_type.map((item) => {
              const pnl = bondNumericRaw(item.total_pnl_economic);
              const totalPnl = bondNumericRaw(data.total_pnl_from_actions);
              const pct = totalPnl !== 0 ? (pnl / totalPnl) * 100 : 0;
              return (
                <div key={item.action_type} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <Tag color={ACTION_COLORS[item.action_type] || "default"} style={{ width: 80, textAlign: "center" }}>
                    {item.action_type_name}
                  </Tag>
                  <span style={{ width: 50, textAlign: "right", fontSize: 12, color: "#5c6b82" }}>
                    {item.action_count}次
                  </span>
                  <div style={{ flex: 1, height: 20, background: "#f0f0f0", borderRadius: 4, overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.min(Math.abs(pct), 100)}%`,
                        background: ACTION_COLORS[item.action_type] || "#8c8c8c",
                        borderRadius: 4,
                      }}
                    />
                  </div>
                  <div
                    style={{
                      width: 200,
                      textAlign: "right",
                      fontSize: 12,
                      color: "#5c6b82",
                      lineHeight: 1.4,
                    }}
                  >
                    <div style={{ fontVariantNumeric: "tabular-nums", color: pnl >= 0 ? "#cf1322" : "#3f8600" }}>
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
        </Card>
      )}

      <SectionLead
        eyebrow="明细"
        title="动作明细"
        description="保留后端动作明细载荷中的类型、说明、损益、久期和 DV01 变动。"
        testId="action-attribution-detail-lead"
      />
      {data.action_details.length > 0 && (
        <Card title="动作明细" size="small">
          <Table
            dataSource={data.action_details}
            columns={detailColumns}
            rowKey="action_id"
            pagination={false}
            size="small"
            scroll={{ y: 400 }}
          />
        </Card>
      )}
      {data.warnings.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message="提示"
          description={data.warnings.map((w, i) => <div key={i}>{w}</div>)}
        />
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
