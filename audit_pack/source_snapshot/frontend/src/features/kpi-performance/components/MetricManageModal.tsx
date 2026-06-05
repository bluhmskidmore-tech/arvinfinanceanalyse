import * as React from "react";
import { DeleteOutlined, PlusOutlined, SaveOutlined } from "@ant-design/icons";
import { Alert, Button, Input, Modal, Select, Space, Typography } from "antd";

import type { KpiMetric, KpiMetricUpsertRequest, KpiOwner } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";

const { Text } = Typography;

const MAJOR_CATEGORIES = ["经营效益类", "规模类", "客群类", "产品类", "其他"];
const INDICATOR_CATEGORIES = [
  "效益类",
  "效益及客群",
  "规模类",
  "客群类",
  "产品类",
  "综合指标",
  "其他",
];
const UNITS = ["亿元", "万元", "%", "BP", "户", "个", "名", ""];

export type MetricManageModalProps = {
  open: boolean;
  onClose: () => void;
  mode: "create" | "edit";
  metric?: KpiMetric | null;
  owner: KpiOwner | null;
  onSuccess: () => void;
};

type FormData = {
  metric_code: string;
  metric_name: string;
  major_category: string;
  indicator_category: string;
  target_value: string;
  target_text: string;
  score_weight: string;
  unit: string;
  scoring_text: string;
  remarks: string;
};

export function MetricManageModal({
  open,
  onClose,
  mode,
  metric,
  owner,
  onSuccess,
}: MetricManageModalProps) {
  const client = useApiClient();
  const [form, setForm] = React.useState<FormData>({
    metric_code: "",
    metric_name: "",
    major_category: "经营效益类",
    indicator_category: "效益类",
    target_value: "",
    target_text: "",
    score_weight: "10",
    unit: "亿元",
    scoring_text: "",
    remarks: "",
  });
  const [saving, setSaving] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [showDelete, setShowDelete] = React.useState(false);

  React.useEffect(() => {
    if (!open || !owner) return;
    if (mode === "edit" && metric) {
      setForm({
        metric_code: metric.metric_code || "",
        metric_name: metric.metric_name || "",
        major_category: metric.major_category || "经营效益类",
        indicator_category: metric.indicator_category || "效益类",
        target_value: metric.target_value || "",
        target_text: metric.target_text || "",
        score_weight: metric.score_weight || "10",
        unit: metric.unit || "",
        scoring_text: metric.scoring_text || "",
        remarks: metric.remarks || "",
      });
    } else {
      const prefix = owner.owner_name?.substring(0, 2).toUpperCase() || "KPI";
      const timestamp = Date.now().toString().slice(-4);
      setForm({
        metric_code: `${prefix}_${timestamp}`,
        metric_name: "",
        major_category: "经营效益类",
        indicator_category: "效益类",
        target_value: "",
        target_text: "",
        score_weight: "10",
        unit: "亿元",
        scoring_text: "",
        remarks: "",
      });
    }
    setError(null);
    setShowDelete(false);
  }, [open, mode, metric, owner]);

  const setField = (k: keyof FormData, v: string) => {
    setForm((p) => ({ ...p, [k]: v }));
    setError(null);
  };

  const handleSave = React.useCallback(async () => {
    if (!owner) return;
    if (!form.metric_name.trim()) {
      setError("请输入指标名称");
      return;
    }
    if (!form.score_weight.trim()) {
      setError("请输入分值");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const data: KpiMetricUpsertRequest = {
        metric_code: form.metric_code,
        metric_name: form.metric_name,
        major_category: form.major_category,
        indicator_category: form.indicator_category || undefined,
        target_value: form.target_value || undefined,
        target_text: form.target_text || undefined,
        score_weight: form.score_weight,
        unit: form.unit || undefined,
        scoring_text: form.scoring_text || undefined,
        remarks: form.remarks || undefined,
        owner_id: owner.owner_id,
        year: owner.year,
        data_source_type: "MANUAL",
        scoring_rule_type: "MANUAL",
      };
      if (mode === "edit" && metric) {
        await client.updateKpiMetric(metric.metric_id, data);
      } else {
        await client.createKpiMetric(data);
      }
      onSuccess();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }, [client, form, owner, mode, metric, onSuccess]);

  const handleDelete = React.useCallback(async () => {
    if (!metric) return;
    setDeleting(true);
    setError(null);
    try {
      await client.deleteKpiMetric(metric.metric_id);
      onSuccess();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeleting(false);
      setShowDelete(false);
    }
  }, [client, metric, onSuccess]);

  if (!owner) return null;

  return (
    <Modal
      title={mode === "create" ? "新增指标" : "编辑指标"}
      open={open}
      onCancel={onClose}
      width={720}
      footer={
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            {mode === "edit" && !showDelete ? (
              <Button danger icon={<DeleteOutlined />} onClick={() => setShowDelete(true)}>
                删除指标
              </Button>
            ) : null}
          </div>
          <Space>
            <Button onClick={onClose} disabled={saving}>
              取消
            </Button>
            <Button
              type="primary"
              loading={saving}
              icon={mode === "create" ? <PlusOutlined /> : <SaveOutlined />}
              onClick={() => void handleSave()}
            >
              {mode === "create" ? "新增" : "保存"}
            </Button>
          </Space>
        </div>
      }
    >
      <Text type="secondary">
        {owner.owner_name} · {owner.year} 年度
      </Text>
      {showDelete ? (
        <Alert
          type="error"
          showIcon
          style={{ marginTop: 16 }}
          message={`确定删除「${metric?.metric_name}」？`}
          action={
            <div style={{ display: "flex", gap: 8 }}>
              <Button size="small" onClick={() => setShowDelete(false)}>
                取消
              </Button>
              <Button size="small" danger loading={deleting} onClick={() => void handleDelete()}>
                确认删除
              </Button>
            </div>
          }
        />
      ) : null}
      <div style={{ display: "grid", gap: 14, marginTop: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <Text strong>
              指标代码 <Text type="danger">*</Text>
            </Text>
            <Input
              style={{ marginTop: 6 }}
              value={form.metric_code}
              disabled={mode === "edit"}
              onChange={(e) => setField("metric_code", e.target.value)}
            />
          </div>
          <div>
            <Text strong>
              指标名称 <Text type="danger">*</Text>
            </Text>
            <Input style={{ marginTop: 6 }} value={form.metric_name} onChange={(e) => setField("metric_name", e.target.value)} />
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <Text strong>大类</Text>
            <Select
              style={{ width: "100%", marginTop: 6 }}
              value={form.major_category}
              options={MAJOR_CATEGORIES.map((c) => ({ label: c, value: c }))}
              onChange={(v) => setField("major_category", v)}
            />
          </div>
          <div>
            <Text strong>指标类别</Text>
            <Select
              style={{ width: "100%", marginTop: 6 }}
              value={form.indicator_category}
              options={INDICATOR_CATEGORIES.map((c) => ({ label: c, value: c }))}
              onChange={(v) => setField("indicator_category", v)}
            />
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
          <div>
            <Text strong>目标值</Text>
            <Input style={{ marginTop: 6 }} value={form.target_value} onChange={(e) => setField("target_value", e.target.value)} />
          </div>
          <div>
            <Text strong>
              分值 <Text type="danger">*</Text>
            </Text>
            <Input style={{ marginTop: 6 }} value={form.score_weight} onChange={(e) => setField("score_weight", e.target.value)} />
          </div>
          <div>
            <Text strong>单位</Text>
            <Select
              style={{ width: "100%", marginTop: 6 }}
              value={form.unit}
              options={UNITS.map((u) => ({ label: u || "无", value: u }))}
              onChange={(v) => setField("unit", v)}
            />
          </div>
        </div>
        <div>
          <Text strong>目标原文</Text>
          <Input.TextArea
            style={{ marginTop: 6 }}
            rows={2}
            value={form.target_text}
            onChange={(e) => setField("target_text", e.target.value)}
          />
        </div>
        <div>
          <Text strong>评分标准</Text>
          <Input.TextArea
            style={{ marginTop: 6 }}
            rows={2}
            value={form.scoring_text}
            onChange={(e) => setField("scoring_text", e.target.value)}
          />
        </div>
        <div>
          <Text strong>备注/口径说明</Text>
          <Input.TextArea
            style={{ marginTop: 6 }}
            rows={2}
            value={form.remarks}
            onChange={(e) => setField("remarks", e.target.value)}
          />
        </div>
      </div>
      {error ? (
        <Alert type="error" showIcon style={{ marginTop: 16 }} message={error} />
      ) : null}
    </Modal>
  );
}

export default MetricManageModal;
