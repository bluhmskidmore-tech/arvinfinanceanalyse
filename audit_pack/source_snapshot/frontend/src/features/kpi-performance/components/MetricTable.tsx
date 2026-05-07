import * as React from "react";
import {
  CheckOutlined,
  CloseOutlined,
  DownOutlined,
  EditOutlined,
  PlusOutlined,
  RightOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { Button, Card, Input, Spin, Tag } from "antd";

import type { KpiDecimalString, KpiMetricWithValue } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";

import { TracePanel } from "./TracePanel";

export type MetricTableProps = {
  metrics: KpiMetricWithValue[];
  loading?: boolean;
  onRefresh?: () => void;
  onAddMetric?: () => void;
  onEditMetricDef?: (metric: KpiMetricWithValue) => void;
  /** 日视图下的 as_of_date；汇总视图无 value行编辑时需传入页面截止日期供 updateValue */
  valueAsOfDate: string;
  /** 打开完整表单编辑（与行内编辑并存） */
  onFullEdit?: (metric: KpiMetricWithValue) => void;
};

type EditableField = "target_value" | "actual_value" | "progress_pct" | "score_value";

type EditingState = {
  metricId: number;
  field: EditableField;
  value: string;
};

function formatDecimal(value: KpiDecimalString, decimals = 2): string {
  if (value === null || value === undefined || value === "") return "-";
  const num = parseFloat(value);
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString("zh-CN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function getScoreColor(score: KpiDecimalString, weight: KpiDecimalString): string {
  if (score === null || score === undefined || weight === null || weight === undefined) {
    return "#94a3b8";
  }
  const scoreNum = parseFloat(score);
  const weightNum = parseFloat(weight);
  if (Number.isNaN(scoreNum) || Number.isNaN(weightNum) || weightNum === 0) return "#94a3b8";
  const ratio = scoreNum / weightNum;
  if (ratio >= 1) return "#16a34a";
  if (ratio >= 0.8) return "#2563eb";
  if (ratio >= 0.6) return "#ca8a04";
  return "#dc2626";
}

export function MetricTable({
  metrics,
  loading = false,
  onRefresh,
  onAddMetric,
  onEditMetricDef,
  valueAsOfDate,
  onFullEdit,
}: MetricTableProps) {
  const client = useApiClient();
  const [expandedMetricId, setExpandedMetricId] = React.useState<number | null>(null);
  const [editing, setEditing] = React.useState<EditingState | null>(null);
  const [saving, setSaving] = React.useState(false);

  const groupedMetrics = React.useMemo(() => {
    const groups: Record<string, KpiMetricWithValue[]> = {};
    metrics.forEach((m) => {
      const key = m.major_category || "其他";
      if (!groups[key]) groups[key] = [];
      groups[key].push(m);
    });
    return groups;
  }, [metrics]);

  const summary = React.useMemo(() => {
    let totalWeight = 0;
    let totalScore = 0;
    metrics.forEach((m) => {
      totalWeight += parseFloat(m.score_weight || "0") || 0;
      totalScore += parseFloat(m.score_value || "0") || 0;
    });
    return { totalWeight, totalScore };
  }, [metrics]);

  const handleSaveEdit = React.useCallback(
    async (metric: KpiMetricWithValue) => {
      if (!editing) return;
      setSaving(true);
      try {
        const updateData: Record<string, string | undefined> = {};
        updateData[editing.field] = editing.value || undefined;
        const asOf = metric.as_of_date || valueAsOfDate;
        await client.updateKpiValue(metric.value_id || 0, metric.metric_id, asOf, updateData);
        setEditing(null);
        onRefresh?.();
      } catch (e) {
        console.error(e);
      } finally {
        setSaving(false);
      }
    },
    [client, editing, onRefresh, valueAsOfDate],
  );

  const renderEditableCell = (
    metric: KpiMetricWithValue,
    field: EditableField,
    displayValue: string,
    suffix?: string,
    scoreColor?: string,
  ) => {
    const isEditing = editing?.metricId === metric.metric_id && editing?.field === field;
    if (isEditing) {
      return (
        <div
          style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 4 }}
          onClick={(e) => e.stopPropagation()}
        >
          <Input
            size="small"
            style={{ width: 88, textAlign: "right" }}
            value={editing.value}
            onChange={(e) => setEditing({ ...editing, value: e.target.value })}
            onPressEnter={() => void handleSaveEdit(metric)}
          />
          <Button
            type="text"
            size="small"
            loading={saving}
            icon={<CheckOutlined />}
            onClick={() => void handleSaveEdit(metric)}
          />
          <Button type="text" size="small" icon={<CloseOutlined />} onClick={() => setEditing(null)} />
        </div>
      );
    }
    return (
      <div
        role="button"
        tabIndex={0}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
          gap: 4,
          cursor: "pointer",
          color: scoreColor,
          fontWeight: field === "score_value" ? 600 : undefined,
        }}
        onClick={(e) => {
          e.stopPropagation();
          setEditing({
            metricId: metric.metric_id,
            field,
            value: String(metric[field] ?? ""),
          });
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            setEditing({
              metricId: metric.metric_id,
              field,
              value: String(metric[field] ?? ""),
            });
          }
        }}
      >
        <span>
          {displayValue}
          {suffix && displayValue !== "-" ? suffix : ""}
        </span>
        <EditOutlined style={{ fontSize: 12, color: "#cbd5e1" }} />
      </div>
    );
  };

  if (loading) {
    return (
      <Card>
        <div style={{ padding: 48, textAlign: "center" }}>
          <Spin />
          <div style={{ marginTop: 12, color: "#64748b" }}>加载指标…</div>
        </div>
      </Card>
    );
  }

  if (metrics.length === 0) {
    return (
      <Card>
        <div style={{ padding: 48, textAlign: "center", color: "#94a3b8" }}>
          <p>暂无指标数据</p>
          {onAddMetric ? (
            <Button type="primary" ghost icon={<PlusOutlined />} onClick={onAddMetric}>
              新增指标
            </Button>
          ) : null}
        </div>
      </Card>
    );
  }

  const th: React.CSSProperties = {
    padding: "12px 10px",
    textAlign: "left",
    fontWeight: 600,
    color: "#334155",
    borderBottom: "1px solid #e2e8f0",
    background: "#f8fafc",
    fontSize: 13,
  };

  return (
    <Card styles={{ body: { padding: 0 } }}>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr>
              <th style={{ ...th, width: 36 }} />
              <th style={th}>指标类别</th>
              <th style={th}>考核指标</th>
              <th style={{ ...th, textAlign: "right", width: 96 }}>目标</th>
              <th style={{ ...th, textAlign: "right", width: 72 }}>分值</th>
              <th style={{ ...th, minWidth: 200 }}>评分标准</th>
              <th style={{ ...th, textAlign: "right", width: 96 }}>完成情况</th>
              <th style={{ ...th, textAlign: "right", width: 96 }}>序时进度</th>
              <th style={{ ...th, textAlign: "right", width: 88 }}>得分</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(groupedMetrics).map(([category, categoryMetrics]) => (
              <React.Fragment key={category}>
                <tr>
                  <td
                    colSpan={9}
                    style={{
                      padding: "10px 12px",
                      background: "#eff6ff",
                      borderBottom: "1px solid #e2e8f0",
                      fontWeight: 600,
                      color: "#1e40af",
                    }}
                  >
                    {category}{" "}
                    <Tag color="blue" style={{ marginLeft: 8 }}>
                      {categoryMetrics.length} 项
                    </Tag>
                  </td>
                </tr>
                {categoryMetrics.map((metric, idx) => {
                  const isExpanded = expandedMetricId === metric.metric_id;
                  const scoreColor = getScoreColor(metric.score_value ?? null, metric.score_weight);
                  const isLast = idx === categoryMetrics.length - 1;
                  return (
                    <React.Fragment key={metric.metric_id}>
                      <tr
                        style={{
                          borderBottom: isLast ? "1px solid #cbd5e1" : "1px solid #f1f5f9",
                          background: isExpanded ? "#f0f9ff" : undefined,
                          cursor: "pointer",
                        }}
                        onClick={() => setExpandedMetricId(isExpanded ? null : metric.metric_id)}
                      >
                        <td style={{ padding: "10px", textAlign: "center", color: "#94a3b8" }}>
                          {isExpanded ? <DownOutlined /> : <RightOutlined />}
                        </td>
                        <td style={{ padding: "10px", color: "#475569" }}>
                          {metric.indicator_category || "-"}
                        </td>
                        <td style={{ padding: "10px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <span style={{ fontWeight: 500, color: "#0f172a" }}>{metric.metric_name}</span>
                            {onEditMetricDef ? (
                              <Button
                                type="text"
                                size="small"
                                icon={<SettingOutlined />}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onEditMetricDef(metric);
                                }}
                              />
                            ) : null}
                          </div>
                        </td>
                        <td style={{ padding: "10px", textAlign: "right", fontFamily: "monospace" }}>
                          {renderEditableCell(metric, "target_value", formatDecimal(metric.target_value))}
                        </td>
                        <td
                          style={{
                            padding: "10px",
                            textAlign: "right",
                            fontFamily: "monospace",
                            color: "#64748b",
                          }}
                        >
                          {formatDecimal(metric.score_weight, 0)}
                        </td>
                        <td style={{ padding: "10px", color: "#64748b", fontSize: 12, maxWidth: 280 }}>
                          <div
                            style={{
                              display: "-webkit-box",
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: "vertical",
                              overflow: "hidden",
                            }}
                            title={metric.scoring_text || ""}
                          >
                            {metric.scoring_text || "-"}
                          </div>
                        </td>
                        <td style={{ padding: "10px", textAlign: "right", fontFamily: "monospace" }}>
                          {renderEditableCell(
                            metric,
                            "actual_value",
                            formatDecimal(metric.actual_value ?? null),
                          )}
                        </td>
                        <td style={{ padding: "10px", textAlign: "right", fontFamily: "monospace" }}>
                          {renderEditableCell(
                            metric,
                            "progress_pct",
                            formatDecimal(metric.progress_pct ?? null, 2),
                            "%",
                          )}
                        </td>
                        <td style={{ padding: "10px", textAlign: "right", fontFamily: "monospace" }}>
                          {renderEditableCell(
                            metric,
                            "score_value",
                            formatDecimal(metric.score_value ?? null, 2),
                            undefined,
                            scoreColor,
                          )}
                        </td>
                      </tr>
                      {isExpanded ? (
                        <tr>
                          <td colSpan={9} style={{ background: "#f8fafc", padding: 16 }}>
                            <div
                              style={{
                                display: "grid",
                                gridTemplateColumns: "1fr 1fr",
                                gap: 24,
                              }}
                            >
                              <div>
                                <div
                                  style={{
                                    fontWeight: 600,
                                    marginBottom: 12,
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 8,
                                  }}
                                >
                                  指标详情
                                  {onEditMetricDef ? (
                                    <Button type="link" size="small" onClick={() => onEditMetricDef(metric)}>
                                      编辑指标
                                    </Button>
                                  ) : null}
                                  {onFullEdit ? (
                                    <Button type="link" size="small" onClick={() => onFullEdit(metric)}>
                                      表单编辑完成情况
                                    </Button>
                                  ) : null}
                                </div>
                                <Card size="small">
                                  <div style={{ fontSize: 13, display: "grid", gap: 8 }}>
                                    <div>
                                      <span style={{ color: "#94a3b8" }}>指标代码 </span>
                                      <code>{metric.metric_code}</code>
                                    </div>
                                    <div>
                                      <span style={{ color: "#94a3b8" }}>数据来源 </span>
                                      {metric.data_source_type === "MANUAL" ? "手工录入" : "自动抓取"}
                                    </div>
                                    <div>
                                      <span style={{ color: "#94a3b8" }}>评分规则 </span>
                                      {metric.scoring_rule_type}
                                    </div>
                                  </div>
                                </Card>
                                {metric.target_text ? (
                                  <div style={{ marginTop: 12 }}>
                                    <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>
                                      目标原文
                                    </div>
                                    <Card size="small">{metric.target_text}</Card>
                                  </div>
                                ) : null}
                                {metric.remarks ? (
                                  <div style={{ marginTop: 12 }}>
                                    <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>
                                      备注/口径说明
                                    </div>
                                    <Card size="small">{metric.remarks}</Card>
                                  </div>
                                ) : null}
                              </div>
                              <TracePanel
                                fetchTrace={metric.fetch_trace}
                                scoreTrace={metric.score_calc_trace}
                              />
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </React.Fragment>
                  );
                })}
              </React.Fragment>
            ))}
            <tr style={{ background: "#f1f5f9", fontWeight: 600 }}>
              <td colSpan={4} style={{ padding: "12px 10px", textAlign: "right", color: "#334155" }}>
                合计
              </td>
              <td style={{ padding: "12px 10px", textAlign: "right", fontFamily: "monospace" }}>
                {summary.totalWeight.toFixed(0)}
              </td>
              <td colSpan={3} />
              <td
                style={{
                  padding: "12px 10px",
                  textAlign: "right",
                  fontFamily: "monospace",
                  color: "#1d4ed8",
                }}
              >
                {summary.totalScore.toFixed(2)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export default MetricTable;
