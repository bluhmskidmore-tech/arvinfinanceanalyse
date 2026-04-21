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
  if (meta.quality_flag !== "ok") issues.push(`quality_flag=${meta.quality_flag}`);
  if (meta.vendor_status !== "ok") issues.push(`vendor_status=${meta.vendor_status}`);
  if (meta.fallback_mode !== "none") issues.push(`fallback_mode=${meta.fallback_mode}`);
  return issues;
}

const detailColumns = [
  { title: "鏃ユ湡", dataIndex: "action_date", key: "action_date", width: 100 },
  {
    title: "绫诲瀷",
    dataIndex: "action_type",
    key: "action_type",
    width: 100,
    render: (type: string) => (
      <Tag color={ACTION_COLORS[type] || "default"}>
        {ACTION_TYPE_NAMES[type] || type}
      </Tag>
    ),
  },
  { title: "鎻忚堪", dataIndex: "description", key: "description", ellipsis: true },
  {
    title: "鎹熺泭璐＄尞",
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
    title: "螖涔呮湡",
    dataIndex: "delta_duration",
    key: "delta_duration",
    width: 80,
    render: (v: Numeric) => v.display,
  },
  {
    title: "浼氳鎹熺泭",
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
    title: "螖DV01",
    dataIndex: "delta_dv01",
    key: "delta_dv01",
    width: 100,
    render: (v: Numeric) => v.display,
  },
  {
    title: "螖鍒╁樊DV01",
    dataIndex: "delta_spread_dv01",
    key: "delta_spread_dv01",
    width: 110,
    render: (v: Numeric) => v.display,
  },
  {
    title: "娑夊強鍊哄埜",
    dataIndex: "bonds_involved",
    key: "bonds_involved",
    width: 120,
    render: (codes: string[]) => (codes?.length ? codes.join(", ") : "-"),
  },
  {
    title: "鏈轰細鎴愭湰",
    key: "opportunity_cost",
    width: 100,
    render: (_: unknown, row: { opportunity_cost?: Numeric }) =>
      row.opportunity_cost ? formatWan(row.opportunity_cost) : "-",
  },
  {
    title: "鏈轰細鎴愭湰鍙ｅ緞",
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
  if (error) return <Alert type="error" message={`鍔犺浇澶辫触锛?{error}`} />;
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
        eyebrow="Action Attribution"
        title="浜ゆ槗鍔ㄤ綔褰掑洜姒傝"
        description="Reads the governed action-attribution payload and renders counts, PnL contribution, duration, and DV01 without front-end recomputation."
        testId="action-attribution-shell-lead"
      />
      <div
        style={{ fontSize: 12, color: "#8090a8", lineHeight: 1.65 }}
        data-testid="action-attribution-meta"
      >
        <span>鎶ュ憡鏃?{data.report_date}</span>
        <span style={{ margin: "0 0.5em", opacity: 0.45 }}>|</span>
        <span>鏈熼棿 {data.period_type}</span>
        <span style={{ margin: "0 0.5em", opacity: 0.45 }}>|</span>
        <span>
          {data.period_start} 鈥?{data.period_end}
        </span>
        {data.computed_at ? (
          <>
            <span style={{ margin: "0 0.5em", opacity: 0.45 }}>|</span>
            <span>璁＄畻鏃堕棿 {data.computed_at}</span>
          </>
        ) : null}
      </div>
      {metaIssues.length > 0 ? (
        <Alert
          type="warning"
          showIcon
          message="Provenance degraded"
          description={metaIssues.join(" | ")}
          data-testid="action-attribution-result-meta-alert"
        />
      ) : null}
      {hasReadinessMeta ? (
        <Alert
          type={data.status && data.status !== "ok" ? "warning" : "info"}
          showIcon
          message={data.status ? `璇婚潰鐘舵€侊細${data.status}` : "璇婚潰缁勪欢淇℃伅"}
          description={
            <div style={{ fontSize: 13, lineHeight: 1.65 }}>
              {(data.available_components?.length ?? 0) > 0 ? (
                <div>Available: {data.available_components!.join(" / ")}</div>
              ) : null}
              {(data.missing_inputs?.length ?? 0) > 0 ? (
                <div>Missing inputs: {data.missing_inputs!.join(" / ")}</div>
              ) : null}
              {(data.blocked_components?.length ?? 0) > 0 ? (
                <div>Blocked: {data.blocked_components!.join(" / ")}</div>
              ) : null}
            </div>
          }
          data-testid="action-attribution-readiness"
        />
      ) : null}
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="鍔ㄤ綔鏁伴噺" value={data.total_actions} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="鍔ㄤ綔璐＄尞鎹熺泭" value={formatWan(data.total_pnl_from_actions)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="涔呮湡鍙樺寲"
              value={`${data.period_start_duration.display} 鈫?${data.period_end_duration.display}`}
              suffix={`螖 ${data.duration_change_from_actions.display}`}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="DV01鍙樺寲"
              value={`${formatWan(data.period_start_dv01)} 鈫?${formatWan(data.period_end_dv01)}`}
            />
          </Card>
        </Col>
      </Row>

      <SectionLead
        eyebrow="Summary"
        title="Action Summary"
        description="Summarizes counts and PnL by action type while preserving the backend contribution values."
        testId="action-attribution-summary-lead"
      />
      {data.by_action_type.length > 0 && (
        <Card title="By Action Type" size="small">
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
                    {item.action_count}娆?                  </span>
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
                      缁忔祹 {formatWan(item.total_pnl_economic)}
                    </div>
                    <div style={{ fontVariantNumeric: "tabular-nums" }}>
                      浼氳 {formatWan(item.total_pnl_accounting)}
                    </div>
                    <div style={{ fontVariantNumeric: "tabular-nums" }}>
                      鍧囨 {formatWan(item.avg_pnl_per_action)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      <SectionLead
        eyebrow="Details"
        title="鍔ㄤ綔鏄庣粏"
        description="Keeps the backend action_details payload visible with type, description, PnL, duration, and DV01 deltas."
        testId="action-attribution-detail-lead"
      />
      {data.action_details.length > 0 && (
        <Card title="鍔ㄤ綔鏄庣粏" size="small">
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
          message="鎻愮ず"
          description={data.warnings.map((w, i) => <div key={i}>{w}</div>)}
        />
      )}
      <FormalResultMetaPanel
        testId="action-attribution-result-meta"
        title="Action Attribution Provenance"
        sections={[
          {
            key: "action-attribution",
            title: "Action attribution",
            meta,
          },
        ]}
      />
    </div>
  );
}
