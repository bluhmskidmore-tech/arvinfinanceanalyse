import * as React from "react";
import { InboxOutlined, UploadOutlined } from "@ant-design/icons";
import { Alert, Button, Input, Modal, Table, Tag, Typography } from "antd";

import type { KpiMetricWithValue, KpiOwner } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { observeKpiWrite, type KpiPendingWriteProps, type PendingKpiWrite } from "./pendingKpiWrite";
import { EM_DASH } from "../../../utils/format";

const { Paragraph, Text } = Typography;

/** 单次批量粘贴的最大导入行数；超限拒绝解析，提示分批导入。 */
export const BATCH_PASTE_MAX_ROWS = 500;
/** 预览表分页大小，避免一次渲染全部行。 */
const PREVIEW_PAGE_SIZE = 50;

export type BatchPasteModalProps = KpiPendingWriteProps & {
  open: boolean;
  onClose: () => void;
  owner: KpiOwner | null;
  asOfDate: string;
  metrics: KpiMetricWithValue[];
  onSuccess: () => void;
};

type ParsedRow = {
  rowIndex: number;
  metricCode: string;
  actualValue: string;
  progressPct: string;
  metric?: KpiMetricWithValue;
  error?: string;
  status: "pending" | "valid" | "invalid";
};

export function BatchPasteModal({
  open,
  onClose,
  owner,
  asOfDate,
  metrics,
  onSuccess,
  writePending = false,
  onUnconfirmedWrite,
}: BatchPasteModalProps) {
  const client = useApiClient();
  const [pasteText, setPasteText] = React.useState("");
  const [parsedRows, setParsedRows] = React.useState<ParsedRow[]>([]);
  const [parseError, setParseError] = React.useState<string | null>(null);
  const [importing, setImporting] = React.useState(false);
  const [importResult, setImportResult] = React.useState<{
    success: number;
    failed: number;
    errors: string[];
    unconfirmed?: boolean;
  } | null>(null);
  const requestSeq = React.useRef(0);
  const pending = React.useRef(false);
  const pendingWrite = React.useRef<PendingKpiWrite | null>(null);
  const successTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => {
    requestSeq.current += 1;
    pending.current = false;
    pendingWrite.current = null;
    setImporting(false);
    setPasteText("");
    setParsedRows([]);
    setParseError(null);
    setImportResult(null);
    return () => {
      requestSeq.current += 1;
      if (successTimer.current !== null) clearTimeout(successTimer.current);
      successTimer.current = null;
    };
  }, [open, owner?.owner_id, owner?.year, asOfDate]);

  // A readback can replace the list while a newer draft or a write is open.
  // Discard the old mapping, but preserve the text and the request's lifetime.
  React.useEffect(() => {
    setParsedRows([]);
  }, [metrics]);

  const metricCodeMap = React.useMemo(() => {
    const map = new Map<string, KpiMetricWithValue>();
    metrics.forEach((m) => {
      if (owner && m.owner_id === owner.owner_id && m.year === owner.year) {
        map.set(m.metric_code.toLowerCase(), m);
      }
    });
    return map;
  }, [metrics, owner]);

  const handleParse = React.useCallback(() => {
    if (!pasteText.trim()) {
      setParsedRows([]);
      setParseError(null);
      return;
    }
    const lines = pasteText.trim().split("\n");
    const nonEmptyLineCount = lines.filter((line) => line.trim()).length;
    if (nonEmptyLineCount > BATCH_PASTE_MAX_ROWS) {
      setParsedRows([]);
      setImportResult(null);
      setParseError(
        `共 ${nonEmptyLineCount} 行，超出单次最大导入 ${BATCH_PASTE_MAX_ROWS} 行，请分批粘贴导入。`,
      );
      return;
    }
    setParseError(null);
    const rows: ParsedRow[] = [];
    lines.forEach((line, index) => {
      const trimmedLine = line.trim();
      if (!trimmedLine) return;
      const parts = trimmedLine.split(/\t+|\s{2,}/);
      if (parts.length < 2) {
        rows.push({
          rowIndex: index + 1,
          metricCode: parts[0] || "",
          actualValue: "",
          progressPct: "",
          error: "格式错误：至少需要指标代码和实际值",
          status: "invalid",
        });
        return;
      }
      const metricCode = parts[0].trim();
      const actualValue = parts[1]?.trim() || "";
      const progressPct = parts[2]?.trim() || "";
      const metric = metricCodeMap.get(metricCode.toLowerCase());
      if (!metric) {
        rows.push({
          rowIndex: index + 1,
          metricCode,
          actualValue,
          progressPct,
          error: `未找到指标代码: ${metricCode}`,
          status: "invalid",
        });
        return;
      }
      if (actualValue && Number.isNaN(parseFloat(actualValue))) {
        rows.push({
          rowIndex: index + 1,
          metricCode,
          actualValue,
          progressPct,
          metric,
          error: "实际值格式错误",
          status: "invalid",
        });
        return;
      }
      if (progressPct && Number.isNaN(parseFloat(progressPct))) {
        rows.push({
          rowIndex: index + 1,
          metricCode,
          actualValue,
          progressPct,
          metric,
          error: "序时进度格式错误",
          status: "invalid",
        });
        return;
      }
      rows.push({
        rowIndex: index + 1,
        metricCode,
        actualValue,
        progressPct,
        metric,
        status: "valid",
      });
    });
    setParsedRows(rows);
    setImportResult(null);
  }, [pasteText, metricCodeMap]);

  const handleImport = React.useCallback(async () => {
    if (!open || !owner || pending.current || writePending) return;
    const validRows = parsedRows.filter((r) => r.status === "valid" && r.metric);
    if (validRows.length === 0) return;
    if (validRows.some((row) => metricCodeMap.get(row.metricCode.toLowerCase())?.metric_id !== row.metric?.metric_id)) {
      setParsedRows([]);
      setParseError("指标已变更，请重新解析后导入");
      return;
    }
    pending.current = true;
    const requestId = ++requestSeq.current;
    setImporting(true);
    setImportResult(null);
    try {
      const items = validRows.map((row) => ({
        metric_id: row.metric!.metric_id,
        actual_value: row.actualValue || undefined,
        progress_pct: row.progressPct || undefined,
      }));
      const operation = client.batchUpdateKpiValues(asOfDate, items);
      pendingWrite.current = observeKpiWrite(operation, (result) => ({
        changed: result.success_count > 0,
        confirmed: true,
        error: result.failed_count > 0 ? `成功 ${result.success_count} 条，未成功 ${result.failed_count} 条：${(result.errors || []).join("；")}` : undefined,
      }));
      const response = await operation;
      if (requestId !== requestSeq.current) return;
      setImportResult({
        success: response.success_count,
        failed: response.failed_count,
        errors: response.errors || [],
      });
      if (response.success_count > 0) {
        setParsedRows([]);
        successTimer.current = setTimeout(() => {
          if (requestId === requestSeq.current) {
            successTimer.current = null;
            pending.current = false;
            setImporting(false);
            onSuccess();
          }
        }, 1200);
      }
    } catch (err: unknown) {
      if (requestId !== requestSeq.current) return;
      if (pendingWrite.current) onUnconfirmedWrite?.(pendingWrite.current);
      const msg = err instanceof Error ? err.message : "导入结果尚未确认";
      setImportResult({
        success: 0,
        failed: 0,
        errors: [msg],
        unconfirmed: true,
      });
    } finally {
      if (requestId === requestSeq.current && successTimer.current === null) {
        pending.current = false;
        setImporting(false);
      }
    }
  }, [client, parsedRows, asOfDate, onSuccess, open, owner, metricCodeMap, writePending, onUnconfirmedWrite]);

  const handleClear = React.useCallback(() => {
    setPasteText("");
    setParsedRows([]);
    setParseError(null);
    setImportResult(null);
  }, []);

  const stats = React.useMemo(() => {
    const valid = parsedRows.filter((r) => r.status === "valid").length;
    const invalid = parsedRows.filter((r) => r.status === "invalid").length;
    return { valid, invalid, total: parsedRows.length };
  }, [parsedRows]);

  const stopWaiting = () => {
    const write = pendingWrite.current;
    if (!write || !onUnconfirmedWrite) return;
    pendingWrite.current = null;
    requestSeq.current += 1;
    onUnconfirmedWrite(write);
    onClose();
  };

  if (!owner) return null;

  return (
    <Modal
      rootClassName="kpi-modal-v2 kpi-modal-v2--batch"
      /* portal 主题逃逸：同 MetricEditModal，modalRender 包 Nocturne scope 容器。 */
      modalRender={(node) => (
        <div className="theme-dh-api" data-moss-theme-scope="kpi">
          {node}
        </div>
      )}
      title={
        <span className="kpi-modal-v2__title-inline">
          <InboxOutlined className="kpi-modal-v2__title-icon" />
          批量导入
        </span>
      }
      open={open}
      closable={!importing}
      maskClosable={!importing}
      keyboard={!importing}
      onCancel={() => { if (!pending.current) onClose(); }}
      width={880}
      footer={[
        importing && onUnconfirmedWrite ? <Button key="stop" onClick={stopWaiting}>停止等待</Button> : null,
        <Button key="cancel" onClick={onClose} disabled={importing}>
          取消
        </Button>,
        <Button
          key="import"
          type="primary"
          loading={importing}
          icon={<UploadOutlined />}
          disabled={stats.valid === 0 || writePending}
          onClick={() => void handleImport()}
        >
          导入（{stats.valid} 条）
        </Button>,
      ]}
    >
      {((importing) && onUnconfirmedWrite) || writePending ? (
        <Alert type="warning" showIcon message={writePending
          ? "前一笔写入结果尚未确认，请关闭窗口后刷新核实，勿重复提交。"
          : "停止等待只关闭窗口，不会取消服务端写入；结果仍需核实。"} />
      ) : null}
      <Paragraph type="secondary" className="kpi-modal-v2__subtitle">
        {owner.owner_name} · {asOfDate}
      </Paragraph>
      <Alert
        type="info"
        showIcon
        className="kpi-modal-v2__alert kpi-modal-v2__alert--intro"
        message="使用说明"
        description={
          <ul className="kpi-modal-v2__help-list">
            <li>从 Excel 复制后粘贴到文本框</li>
            <li>
              格式：<Text code>指标代码 [Tab] 实际值 [Tab] 序时进度</Text>（序时进度可选）
            </li>
            <li>点击「解析」预览，再「导入」；单次最多 {BATCH_PASTE_MAX_ROWS} 行</li>
          </ul>
        }
      />
      <div className="kpi-modal-v2__field-label">
        <Text strong>粘贴数据</Text>
      </div>
      <Input.TextArea
        className="kpi-modal-v2__paste-area"
        value={pasteText}
        disabled={importing}
        onChange={(e) => {
          setPasteText(e.target.value);
          setParsedRows([]);
          setParseError(null);
          setImportResult(null);
        }}
        placeholder="从 Excel 粘贴…"
        rows={6}
      />
      <div className="kpi-modal-v2__toolbar">
        <Text type="secondary">当前共 {metrics.length} 个指标</Text>
        <div className="kpi-modal-v2__toolbar-actions">
          <Button onClick={handleClear} disabled={importing}>清空</Button>
          <Button type="primary" onClick={handleParse} disabled={importing}>
            解析
          </Button>
        </div>
      </div>
      {parseError ? (
        <Alert
          type="error"
          showIcon
          className="kpi-modal-v2__alert"
          message={parseError.includes("超出单次最大导入") ? "超出导入行数上限" : "请重新解析"}
          description={parseError}
        />
      ) : null}
      {parsedRows.length > 0 ? (
        <>
          <div className="kpi-modal-v2__preview-header">
            <Text strong>预览</Text>
            <Text>
              <Text type="success">有效 {stats.valid}</Text>
              {" · "}
              <Text type="danger">无效 {stats.invalid}</Text>
              {" · "}共 {stats.total}
            </Text>
          </div>
          <Table
            className="kpi-modal-v2__table"
            size="small"
            pagination={{
              pageSize: PREVIEW_PAGE_SIZE,
              hideOnSinglePage: true,
              showSizeChanger: false,
            }}
            scroll={{ y: 220 }}
            dataSource={parsedRows.map((r, i) => ({ ...r, key: i }))}
            columns={[
              { title: "#", dataIndex: "rowIndex", width: 48 },
              { title: "指标代码", dataIndex: "metricCode", render: (t: string) => <code>{t}</code> },
              {
                title: "指标名称",
                dataIndex: "metric",
                render: (_: unknown, row: ParsedRow) => row.metric?.metric_name || EM_DASH,
              },
              {
                title: "实际值",
                dataIndex: "actualValue",
                align: "right",
                render: (t: string) => t || EM_DASH,
              },
              {
                title: "序时进度",
                dataIndex: "progressPct",
                align: "right",
                render: (t: string) => (t ? `${t}%` : EM_DASH),
              },
              {
                title: "状态",
                dataIndex: "status",
                width: 88,
                align: "center",
                render: (s: string, row: ParsedRow) =>
                  s === "valid" ? (
                    <Tag color="success">有效</Tag>
                  ) : (
                    <Tag color="error" title={row.error}>
                      无效
                    </Tag>
                  ),
              },
            ]}
          />
          {stats.invalid > 0 ? (
            <Alert
              type="error"
              showIcon
              className="kpi-modal-v2__alert"
              message="以下行将被跳过"
              description={
                <ul className="kpi-modal-v2__help-list">
                  {parsedRows
                    .filter((r) => r.status === "invalid")
                    .slice(0, 5)
                    .map((r) => (
                      <li key={r.rowIndex}>
                        行 {r.rowIndex}: {r.error}
                      </li>
                    ))}
                  {stats.invalid > 5 ? <li>… 另有 {stats.invalid - 5} 条</li> : null}
                </ul>
              }
            />
          ) : null}
        </>
      ) : null}
      {importResult ? (
        <Alert
          type={!importResult.unconfirmed && importResult.failed === 0 ? "success" : "warning"}
          showIcon
          className="kpi-modal-v2__alert"
          message={importResult.unconfirmed ? "导入结果尚未确认" : "导入结果"}
          description={
            <>
              {!importResult.unconfirmed ? <div>
                成功 {importResult.success} 条，失败 {importResult.failed} 条
              </div> : null}
              {importResult.errors.length > 0 ? (
                <ul className="kpi-modal-v2__help-list kpi-modal-v2__help-list--stacked">
                  {importResult.errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              ) : null}
            </>
          }
        />
      ) : null}
    </Modal>
  );
}

export default BatchPasteModal;
