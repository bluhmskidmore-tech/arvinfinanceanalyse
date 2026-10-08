import * as React from "react";
import { DeleteOutlined, PlusOutlined, SaveOutlined } from "@ant-design/icons";
import { Alert, Button, Input, Modal, Select, Space, Typography } from "antd";

import type { KpiMetric, KpiMetricUpsertRequest, KpiOwner } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { observeKpiWrite, type KpiPendingWriteProps, type PendingKpiWrite } from "./pendingKpiWrite";

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

/** 下拉弹层挂在弹窗内的字段容器（不挂 body），保持 Nocturne scope 命中。 */
function resolveModalPopupContainer(trigger: HTMLElement): HTMLElement {
  return trigger.parentElement ?? document.body;
}

export type MetricManageModalProps = KpiPendingWriteProps & {
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
  writePending = false,
  onUnconfirmedWrite,
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
  const requestSeq = React.useRef(0);
  const pending = React.useRef(false);
  const pendingWrite = React.useRef<PendingKpiWrite | null>(null);

  React.useEffect(() => {
    requestSeq.current += 1;
    pending.current = false;
    pendingWrite.current = null;
    setSaving(false);
    setDeleting(false);
    return () => { requestSeq.current += 1; };
  }, [open, mode, metric, owner]);

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
    if (!open || !owner || pending.current || writePending) return;
    if (mode === "edit" && (!metric || metric.owner_id !== owner.owner_id || metric.year !== owner.year)) {
      setError("指标与当前考核对象不一致，请重新打开编辑");
      return;
    }
    if (!form.metric_name.trim()) {
      setError("请输入指标名称");
      return;
    }
    if (!form.score_weight.trim()) {
      setError("请输入分值");
      return;
    }
    pending.current = true;
    const requestId = ++requestSeq.current;
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
        data_source_type: mode === "edit" && metric ? metric.data_source_type : "MANUAL",
        scoring_rule_type: mode === "edit" && metric ? metric.scoring_rule_type : "MANUAL",
      };
      const operation = mode === "edit" && metric
        ? client.updateKpiMetric(metric.metric_id, data)
        : client.createKpiMetric(data);
      pendingWrite.current = observeKpiWrite(operation);
      await operation;
      if (requestId === requestSeq.current) onSuccess();
    } catch (err: unknown) {
      if (requestId === requestSeq.current) {
        if (pendingWrite.current) onUnconfirmedWrite?.(pendingWrite.current,
          mode === "create" ? "请核对是否已创建同名或同代码指标，避免重复新增。" : undefined);
        setError(err instanceof Error ? err.message : "保存结果尚未确认");
      }
    } finally {
      if (requestId === requestSeq.current) {
        pending.current = false;
        setSaving(false);
      }
    }
  }, [client, form, owner, mode, metric, onSuccess, open, writePending, onUnconfirmedWrite]);

  const handleDelete = React.useCallback(async () => {
    if (!open || !metric || pending.current || writePending) return;
    pending.current = true;
    const requestId = ++requestSeq.current;
    setDeleting(true);
    setError(null);
    try {
      const operation = client.deleteKpiMetric(metric.metric_id);
      pendingWrite.current = observeKpiWrite(operation);
      await operation;
      if (requestId === requestSeq.current) onSuccess();
    } catch (err: unknown) {
      if (requestId === requestSeq.current) {
        if (pendingWrite.current) onUnconfirmedWrite?.(pendingWrite.current);
        setError(err instanceof Error ? err.message : "删除结果尚未确认");
      }
    } finally {
      if (requestId === requestSeq.current) {
        pending.current = false;
        setDeleting(false);
        setShowDelete(false);
      }
    }
  }, [client, metric, onSuccess, open, writePending, onUnconfirmedWrite]);

  const stopWaiting = () => {
    const write = pendingWrite.current;
    if (!write || !onUnconfirmedWrite) return;
    pendingWrite.current = null;
    requestSeq.current += 1;
    onUnconfirmedWrite(write, mode === "create" ? "请核对是否已创建同名或同代码指标，避免重复新增。" : undefined);
    onClose();
  };

  if (!owner) return null;

  return (
    <Modal
      rootClassName="kpi-modal-v2 kpi-modal-v2--manage"
      /* portal 主题逃逸：同 MetricEditModal，modalRender 包 Nocturne scope 容器。 */
      modalRender={(node) => (
        <div className="theme-dh-api" data-moss-theme-scope="kpi">
          {node}
        </div>
      )}
      title={mode === "create" ? "新增指标" : "编辑指标"}
      open={open}
      closable={!saving && !deleting}
      maskClosable={!saving && !deleting}
      keyboard={!saving && !deleting}
      onCancel={() => { if (!pending.current) onClose(); }}
      width={720}
      footer={
        <div className="kpi-modal-v2__footer">
          <div>
            {mode === "edit" && !showDelete ? (
              <Button danger disabled={writePending || saving || deleting} icon={<DeleteOutlined />} onClick={() => setShowDelete(true)}>
                删除指标
              </Button>
            ) : null}
          </div>
          <Space>
            {(saving || deleting) && onUnconfirmedWrite ? <Button onClick={stopWaiting}>停止等待</Button> : null}
            <Button onClick={onClose} disabled={saving || deleting}>
              取消
            </Button>
            <Button
              type="primary"
              loading={saving}
              disabled={writePending || deleting}
              icon={mode === "create" ? <PlusOutlined /> : <SaveOutlined />}
              onClick={() => void handleSave()}
            >
              {mode === "create" ? "新增" : "保存"}
            </Button>
          </Space>
        </div>
      }
    >
      {((saving || deleting) && onUnconfirmedWrite) || writePending ? (
        <Alert type="warning" showIcon message={writePending
          ? "前一笔写入结果尚未确认，请关闭窗口后刷新核实，勿重复提交。"
          : "停止等待只关闭窗口，不会取消服务端写入；结果仍需核实。"} />
      ) : null}
      <Text type="secondary" className="kpi-modal-v2__subtitle">
        {owner.owner_name} · {owner.year} 年度
      </Text>
      {showDelete ? (
        <Alert
          type="error"
          showIcon
          className="kpi-modal-v2__alert"
          message={`确定删除「${metric?.metric_name}」？`}
          action={
            <div className="kpi-modal-v2__inline-actions">
              <Button size="small" onClick={() => setShowDelete(false)}>
                取消
              </Button>
              <Button size="small" danger disabled={writePending || saving} loading={deleting} onClick={() => void handleDelete()}>
                确认删除
              </Button>
            </div>
          }
        />
      ) : null}
      <div className="kpi-modal-v2__form">
        <div className="kpi-modal-v2__form-grid kpi-modal-v2__form-grid--two">
          <div className="kpi-modal-v2__field">
            <Text strong>
              指标代码 <Text type="danger">*</Text>
            </Text>
            <Input
              className="kpi-modal-v2__control"
              value={form.metric_code}
              disabled={mode === "edit"}
              onChange={(e) => setField("metric_code", e.target.value)}
            />
          </div>
          <div className="kpi-modal-v2__field">
            <Text strong>
              指标名称 <Text type="danger">*</Text>
            </Text>
            <Input className="kpi-modal-v2__control" value={form.metric_name} onChange={(e) => setField("metric_name", e.target.value)} />
          </div>
        </div>
        <div className="kpi-modal-v2__form-grid kpi-modal-v2__form-grid--two">
          <div className="kpi-modal-v2__field">
            <Text strong>大类</Text>
            <Select
              className="kpi-modal-v2__control"
              getPopupContainer={resolveModalPopupContainer}
              value={form.major_category}
              options={MAJOR_CATEGORIES.map((c) => ({ label: c, value: c }))}
              onChange={(v) => setField("major_category", v)}
            />
          </div>
          <div className="kpi-modal-v2__field">
            <Text strong>指标类别</Text>
            <Select
              className="kpi-modal-v2__control"
              getPopupContainer={resolveModalPopupContainer}
              value={form.indicator_category}
              options={INDICATOR_CATEGORIES.map((c) => ({ label: c, value: c }))}
              onChange={(v) => setField("indicator_category", v)}
            />
          </div>
        </div>
        <div className="kpi-modal-v2__form-grid kpi-modal-v2__form-grid--three">
          <div className="kpi-modal-v2__field">
            <Text strong>目标值</Text>
            <Input className="kpi-modal-v2__control" value={form.target_value} onChange={(e) => setField("target_value", e.target.value)} />
          </div>
          <div className="kpi-modal-v2__field">
            <Text strong>
              分值 <Text type="danger">*</Text>
            </Text>
            <Input className="kpi-modal-v2__control" value={form.score_weight} onChange={(e) => setField("score_weight", e.target.value)} />
          </div>
          <div className="kpi-modal-v2__field">
            <Text strong>单位</Text>
            <Select
              className="kpi-modal-v2__control"
              getPopupContainer={resolveModalPopupContainer}
              value={form.unit}
              options={UNITS.map((u) => ({ label: u || "无", value: u }))}
              onChange={(v) => setField("unit", v)}
            />
          </div>
        </div>
        <div className="kpi-modal-v2__field">
          <Text strong>目标原文</Text>
          <Input.TextArea
            className="kpi-modal-v2__control"
            rows={2}
            value={form.target_text}
            onChange={(e) => setField("target_text", e.target.value)}
          />
        </div>
        <div className="kpi-modal-v2__field">
          <Text strong>评分标准</Text>
          <Input.TextArea
            className="kpi-modal-v2__control"
            rows={2}
            value={form.scoring_text}
            onChange={(e) => setField("scoring_text", e.target.value)}
          />
        </div>
        <div className="kpi-modal-v2__field">
          <Text strong>备注/口径说明</Text>
          <Input.TextArea
            className="kpi-modal-v2__control"
            rows={2}
            value={form.remarks}
            onChange={(e) => setField("remarks", e.target.value)}
          />
        </div>
      </div>
      {error ? (
        <Alert type="error" showIcon className="kpi-modal-v2__alert" message={error} />
      ) : null}
    </Modal>
  );
}

export default MetricManageModal;
