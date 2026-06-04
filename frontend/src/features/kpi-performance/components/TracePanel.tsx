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
    <div className="kpi-trace-panel__content">
      <div>
        <Text type="secondary">抓取方式: </Text>
        {trace.sql_template_id ? (
          <Text strong className="kpi-trace-panel__text--fetch">
            SQL模板 ({trace.sql_template_id})
          </Text>
        ) : trace.fetch_function ? (
          <Text strong className="kpi-trace-panel__text--success">
            函数注册表 ({trace.fetch_function})
          </Text>
        ) : (
          <Text type="secondary">未知</Text>
        )}
      </div>
      {trace.sql_hash ? (
        <div>
          <Text type="secondary">SQL哈希: </Text>
          <Text code className="kpi-trace-panel__text--small">
            {trace.sql_hash}
          </Text>
        </div>
      ) : null}
      <div>
        <Text type="secondary">查询参数: </Text>
        <Text className="kpi-trace-panel__text--small kpi-trace-panel__text--break">
          {formatParams(trace.params)}
        </Text>
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
          <Text type="danger" className="kpi-trace-panel__text--compact">
            {trace.error}
          </Text>
        </div>
      ) : null}
      <div>
        <Text type="secondary">抓取时间: </Text>
        <Text className="kpi-trace-panel__text--small">{trace.fetched_at}</Text>
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
    <div className="kpi-trace-panel__content">
      <div>
        <Text type="secondary">评分规则: </Text>
        <Text strong className="kpi-trace-panel__text--fetch">
          {trace.rule_type}
        </Text>
      </div>
      <div>
        <Text type="secondary">使用口径: </Text>
        <Text strong className="kpi-trace-panel__text--score">
          {inputFieldDisplay}
        </Text>
      </div>
      <div>
        <Text type="secondary">计算公式: </Text>
        <Text code className="kpi-trace-panel__text--small">
          {trace.formula}
        </Text>
      </div>
      <div>
        <Text type="secondary">输入值: </Text>
        <div className="kpi-trace-panel__text--small">
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
        <Text code className="kpi-trace-panel__text--small">
          {trace.rounding}
        </Text>
      </div>
      <div>
        <Text type="secondary">最终得分: </Text>
        <Text strong className="kpi-trace-panel__final-score">
          {trace.final_score}
        </Text>
        {trace.capped ? (
          <Text type="warning" className="kpi-trace-panel__cap-note">
            (已触发上限)
          </Text>
        ) : null}
      </div>
      {trace.reason ? (
        <div>
          <Text type="secondary">说明: </Text>
          <Text className="kpi-trace-panel__text--small">{trace.reason}</Text>
        </div>
      ) : null}
      <div>
        <Text type="secondary">计分时间: </Text>
        <Text className="kpi-trace-panel__text--small">{trace.scored_at}</Text>
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
      <div className={["kpi-trace-panel__empty", className].filter(Boolean).join(" ")}>
        <AlertOutlined className="kpi-trace-panel__empty-icon" />
        暂无追溯信息
      </div>
    );
  }

  return (
    <div className={["kpi-trace-panel", className].filter(Boolean).join(" ")}>
      {fetchTrace ? (
        <Card
          size="small"
          title={
            <span>
              <DatabaseOutlined className="kpi-trace-panel__title-icon kpi-trace-panel__title-icon--fetch" />
              取数追溯
              {fetchTrace.sql_template_id ? (
                <Text code className="kpi-trace-panel__title-meta">
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
              <CalculatorOutlined className="kpi-trace-panel__title-icon kpi-trace-panel__title-icon--score" />
              计分追溯
              <Text type="secondary" className="kpi-trace-panel__title-meta">
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
