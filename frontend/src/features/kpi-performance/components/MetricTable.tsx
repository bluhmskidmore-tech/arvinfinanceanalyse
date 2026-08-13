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
import { PageStateSurface } from "../../../components/page/PagePrimitives";
import { EM_DASH } from "../../../utils/format";

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

type ScoreTone = "muted" | "positive" | "neutral" | "warning" | "negative";

function formatDecimal(value: KpiDecimalString, decimals = 2): string {
  if (value === null || value === undefined || value === "") return EM_DASH;
  const num = parseFloat(value);
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString("zh-CN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function getScoreTone(score: KpiDecimalString, weight: KpiDecimalString): ScoreTone {
  if (score === null || score === undefined || weight === null || weight === undefined) {
    return "muted";
  }
  const scoreNum = parseFloat(score);
  const weightNum = parseFloat(weight);
  if (Number.isNaN(scoreNum) || Number.isNaN(weightNum) || weightNum === 0) return "muted";
  const ratio = scoreNum / weightNum;
  if (ratio >= 1) return "positive";
  if (ratio >= 0.8) return "neutral";
  if (ratio >= 0.6) return "warning";
  return "negative";
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
    scoreTone?: ScoreTone,
  ) => {
    const isEditing = editing?.metricId === metric.metric_id && editing?.field === field;
    if (isEditing) {
      return (
        <div className="kpi-metric-table__editable-cell" onClick={(e) => e.stopPropagation()}>
          <Input
            size="small"
            className="kpi-metric-table__edit-input"
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
    const cellClassName = [
      "kpi-metric-table__editable-cell",
      "kpi-metric-table__editable-cell--button",
      field === "score_value" ? "kpi-metric-table__editable-cell--score" : null,
      scoreTone ? `kpi-metric-table__editable-cell--score-${scoreTone}` : null,
    ]
      .filter(Boolean)
      .join(" ");
    return (
      <div
        role="button"
        tabIndex={0}
        className={cellClassName}
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
          {suffix && displayValue !== EM_DASH ? suffix : ""}
        </span>
        <EditOutlined className="kpi-metric-table__edit-icon" />
      </div>
    );
  };

  if (loading) {
    return (
      <PageStateSurface
        variant="loading"
        testId="kpi-metric-table-panel"
        className="kpi-metric-table-card kpi-metric-table-card--state kpi-metric-table__state"
      >
        <Spin />
        <div className="kpi-metric-table__loading-text">加载指标…</div>
      </PageStateSurface>
    );
  }

  if (metrics.length === 0) {
    return (
      <PageStateSurface
        variant="empty"
        testId="kpi-metric-table-panel"
        className="kpi-metric-table-card kpi-metric-table-card--state kpi-metric-table__state kpi-metric-table__state--empty"
        title="暂无指标数据"
        description="当前考核对象暂无可展示指标"
        actions={
          onAddMetric ? (
            <Button type="primary" ghost icon={<PlusOutlined />} onClick={onAddMetric}>
              新增指标
            </Button>
          ) : null
        }
      />
    );
  }

  return (
    <section className="kpi-metric-table-card" data-testid="kpi-metric-table-panel">
      <div className="kpi-metric-table-card__header">
        <div>
          <span className="kpi-metric-table-card__eyebrow">METRICS</span>
          <h2 className="kpi-metric-table-card__title">指标明细</h2>
        </div>
        <span className="kpi-metric-table-card__count">{metrics.length} 项</span>
      </div>
      <div className="kpi-metric-table__scroll">
        <table className="kpi-metric-table">
          <thead>
            <tr>
              <th className="kpi-metric-table__head-cell kpi-metric-table__head-cell--toggle" />
              <th className="kpi-metric-table__head-cell">指标类别</th>
              <th className="kpi-metric-table__head-cell">考核指标</th>
              <th className="kpi-metric-table__head-cell kpi-metric-table__head-cell--number kpi-metric-table__head-cell--target">
                目标
              </th>
              <th className="kpi-metric-table__head-cell kpi-metric-table__head-cell--number kpi-metric-table__head-cell--weight">
                分值
              </th>
              <th className="kpi-metric-table__head-cell kpi-metric-table__head-cell--scoring">
                评分标准
              </th>
              <th className="kpi-metric-table__head-cell kpi-metric-table__head-cell--number kpi-metric-table__head-cell--target">
                完成情况
              </th>
              <th className="kpi-metric-table__head-cell kpi-metric-table__head-cell--number kpi-metric-table__head-cell--target">
                序时进度
              </th>
              <th className="kpi-metric-table__head-cell kpi-metric-table__head-cell--number kpi-metric-table__head-cell--score">
                得分
              </th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(groupedMetrics).map(([category, categoryMetrics]) => (
              <React.Fragment key={category}>
                <tr>
                  <td
                    colSpan={9}
                    className="kpi-metric-table__category-row-cell"
                  >
                    {category}{" "}
                    <Tag color="blue" className="kpi-metric-table__category-tag">
                      {categoryMetrics.length} 项
                    </Tag>
                  </td>
                </tr>
                {categoryMetrics.map((metric, idx) => {
                  const isExpanded = expandedMetricId === metric.metric_id;
                  const scoreTone = getScoreTone(metric.score_value ?? null, metric.score_weight);
                  const isLast = idx === categoryMetrics.length - 1;
                  const rowClassName = [
                    "kpi-metric-table__row",
                    isExpanded ? "kpi-metric-table__row--expanded" : null,
                    isLast ? "kpi-metric-table__row--last" : null,
                  ]
                    .filter(Boolean)
                    .join(" ");
                  return (
                    <React.Fragment key={metric.metric_id}>
                      <tr
                        className={rowClassName}
                        onClick={() => setExpandedMetricId(isExpanded ? null : metric.metric_id)}
                      >
                        <td className="kpi-metric-table__cell kpi-metric-table__cell--toggle">
                          {isExpanded ? <DownOutlined /> : <RightOutlined />}
                        </td>
                        <td className="kpi-metric-table__cell kpi-metric-table__cell--indicator">
                          {metric.indicator_category || EM_DASH}
                        </td>
                        <td className="kpi-metric-table__cell">
                          <div className="kpi-metric-table__metric-name-wrap">
                            <span className="kpi-metric-table__metric-name">{metric.metric_name}</span>
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
                        <td className="kpi-metric-table__cell kpi-metric-table__cell--number">
                          {renderEditableCell(metric, "target_value", formatDecimal(metric.target_value))}
                        </td>
                        <td className="kpi-metric-table__cell kpi-metric-table__cell--number kpi-metric-table__cell--muted">
                          {formatDecimal(metric.score_weight, 0)}
                        </td>
                        <td className="kpi-metric-table__cell kpi-metric-table__cell--scoring">
                          <div
                            className="kpi-metric-table__scoring-text"
                            title={metric.scoring_text || ""}
                          >
                            {metric.scoring_text || EM_DASH}
                          </div>
                        </td>
                        <td className="kpi-metric-table__cell kpi-metric-table__cell--number">
                          {renderEditableCell(
                            metric,
                            "actual_value",
                            formatDecimal(metric.actual_value ?? null),
                          )}
                        </td>
                        <td className="kpi-metric-table__cell kpi-metric-table__cell--number">
                          {renderEditableCell(
                            metric,
                            "progress_pct",
                            formatDecimal(metric.progress_pct ?? null, 2),
                            "%",
                          )}
                        </td>
                        <td className="kpi-metric-table__cell kpi-metric-table__cell--number">
                          {renderEditableCell(
                            metric,
                            "score_value",
                            formatDecimal(metric.score_value ?? null, 2),
                            undefined,
                            scoreTone,
                          )}
                        </td>
                      </tr>
                      {isExpanded ? (
                        <tr>
                          <td colSpan={9} className="kpi-metric-table__expanded-cell">
                            <div className="kpi-metric-table__expanded-grid">
                              <div>
                                <div className="kpi-metric-table__expanded-title">
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
                                  <div className="kpi-metric-table__detail-list">
                                    <div>
                                      <span className="kpi-metric-table__detail-label">指标代码 </span>
                                      <code>{metric.metric_code}</code>
                                    </div>
                                    <div>
                                      <span className="kpi-metric-table__detail-label">数据来源 </span>
                                      {metric.data_source_type === "MANUAL" ? "手工录入" : "自动抓取"}
                                    </div>
                                    <div>
                                      <span className="kpi-metric-table__detail-label">评分规则 </span>
                                      {metric.scoring_rule_type}
                                    </div>
                                  </div>
                                </Card>
                                {metric.target_text ? (
                                  <div className="kpi-metric-table__detail-section">
                                    <div className="kpi-metric-table__detail-section-title">
                                      目标原文
                                    </div>
                                    <Card size="small">{metric.target_text}</Card>
                                  </div>
                                ) : null}
                                {metric.remarks ? (
                                  <div className="kpi-metric-table__detail-section">
                                    <div className="kpi-metric-table__detail-section-title">
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
            <tr className="kpi-metric-table__summary-row">
              <td colSpan={4} className="kpi-metric-table__summary-label">
                合计（前端本地加总·非官方口径）
              </td>
              <td className="kpi-metric-table__summary-number">
                {summary.totalWeight.toFixed(0)}
              </td>
              <td colSpan={3} />
              <td className="kpi-metric-table__summary-number kpi-metric-table__summary-number--score">
                {summary.totalScore.toFixed(2)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default MetricTable;
