import { AlertOutlined, CalculatorOutlined, DatabaseOutlined } from "@ant-design/icons";
import { Card, Typography } from "antd";

import type { KpiFetchTrace, KpiScoreTrace } from "../../../api/contracts";

const { Text } = Typography;

function formatParams(params: Record<string, unknown>): string {
  if (!params || Object.keys(params).length === 0) return "-";
  return Object.entries(params)
    .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
    .join(", ");
}

function FetchTraceContent({ trace }: { trace: KpiFetchTrace }) {
  return (
    <div style={{ display: "grid", gap: 8, fontSize: 13 }}>
      <div>
        <Text type="secondary">抓取方式: </Text>
        {trace.sql_template_id ? (
          <Text strong style={{ color: "#1677ff" }}>
            SQL模板 ({trace.sql_template_id})
          </Text>
        ) : trace.fetch_function ? (
          <Text strong style={{ color: "#52c41a" }}>
            函数注册表 ({trace.fetch_function})
          </Text>
        ) : (
          <Text type="secondary">未知</Text>
        )}
      </div>
      {trace.sql_hash ? (
        <div>
          <Text type="secondary">SQL哈希: </Text>
          <Text code style={{ fontSize: 11 }}>
            {trace.sql_hash}
          </Text>
        </div>
      ) : null}
      <div>
        <Text type="secondary">查询参数: </Text>
        <Text style={{ fontSize: 11, wordBreak: "break-all" }}>{formatParams(trace.params)}</Text>
      </div>
      <div>
        <Text type="secondary">执行信息: </Text>
        <Text>
          耗时 <strong>{trace.execution_time_ms}ms</strong> | 返回{" "}
          <strong>{trace.row_count}</strong> 行
        </Text>
      </div>
      {trace.error ? (
        <div>
          <Text type="secondary">错误: </Text>
          <Text type="danger" style={{ fontSize: 12 }}>
            {trace.error}
          </Text>
        </div>
      ) : null}
      <div>
        <Text type="secondary">抓取时间: </Text>
        <Text style={{ fontSize: 11 }}>{trace.fetched_at}</Text>
      </div>
    </div>
  );
}

function ScoreTraceContent({ trace }: { trace: KpiScoreTrace }) {
  const inputFieldDisplay =
    trace.score_input_field === "completion_ratio"
      ? "完成比率 (completion_ratio)"
      : trace.score_input_field === "progress_pct"
        ? "序时进度 (progress_pct)"
        : trace.score_input_field;

  return (
    <div style={{ display: "grid", gap: 8, fontSize: 13 }}>
      <div>
        <Text type="secondary">评分规则: </Text>
        <Text strong style={{ color: "#1677ff" }}>
          {trace.rule_type}
        </Text>
      </div>
      <div>
        <Text type="secondary">使用口径: </Text>
        <Text strong style={{ color: "#722ed1" }}>
          {inputFieldDisplay}
        </Text>
      </div>
      <div>
        <Text type="secondary">计算公式: </Text>
        <Text code style={{ fontSize: 11 }}>
          {trace.formula}
        </Text>
      </div>
      <div>
        <Text type="secondary">输入值: </Text>
        <div style={{ fontSize: 11 }}>
          {Object.entries(trace.inputs).map(([k, v]) => (
            <div key={k}>
              <Text type="secondary">{k}: </Text>
              <Text code>{v}</Text>
            </div>
          ))}
        </div>
      </div>
      <div>
        <Text type="secondary">舍入规则: </Text>
        <Text code style={{ fontSize: 11 }}>
          {trace.rounding}
        </Text>
      </div>
      <div>
        <Text type="secondary">最终得分: </Text>
        <Text strong style={{ fontSize: 16, color: "#52c41a" }}>
          {trace.final_score}
        </Text>
        {trace.capped ? (
          <Text type="warning" style={{ fontSize: 11, marginLeft: 6 }}>
            (已触发上限)
          </Text>
        ) : null}
      </div>
      {trace.reason ? (
        <div>
          <Text type="secondary">说明: </Text>
          <Text style={{ fontSize: 11 }}>{trace.reason}</Text>
        </div>
      ) : null}
      <div>
        <Text type="secondary">计分时间: </Text>
        <Text style={{ fontSize: 11 }}>{trace.scored_at}</Text>
      </div>
    </div>
  );
}

export type TracePanelProps = {
  fetchTrace?: KpiFetchTrace | null;
  scoreTrace?: KpiScoreTrace | null;
  className?: string;
};

export function TracePanel({ fetchTrace, scoreTrace, className }: TracePanelProps) {
  if (!fetchTrace && !scoreTrace) {
    return (
      <div className={className} style={{ fontSize: 13, color: "#94a3b8" }}>
        <AlertOutlined style={{ marginRight: 8 }} />
        暂无追溯信息
      </div>
    );
  }

  return (
    <div className={className} style={{ display: "grid", gap: 12 }}>
      {fetchTrace ? (
        <Card
          size="small"
          title={
            <span>
              <DatabaseOutlined style={{ marginRight: 8, color: "#1677ff" }} />
              取数追溯
              {fetchTrace.sql_template_id ? (
                <Text code style={{ float: "right", fontSize: 11 }}>
                  {fetchTrace.sql_template_id}
                </Text>
              ) : null}
            </span>
          }
        >
          <FetchTraceContent trace={fetchTrace} />
        </Card>
      ) : null}
      {scoreTrace ? (
        <Card
          size="small"
          title={
            <span>
              <CalculatorOutlined style={{ marginRight: 8, color: "#722ed1" }} />
              计分追溯
              <Text type="secondary" style={{ float: "right", fontSize: 11 }}>
                使用 {scoreTrace.score_input_field}
              </Text>
            </span>
          }
        >
          <ScoreTraceContent trace={scoreTrace} />
        </Card>
      ) : null}
    </div>
  );
}

export default TracePanel;
