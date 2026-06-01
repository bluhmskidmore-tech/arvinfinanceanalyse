import { Alert, Collapse, List, Space, Spin, Typography } from "antd";
import type { AdbCoveragePayload } from "../../../api/contracts";

const { Text } = Typography;

const MAX_DATES_SHOWN = 120;

type AdbCoverageDiagnosticsProps = {
  loading: boolean;
  isError: boolean;
  data: AdbCoveragePayload | undefined;
};

/**
 * 只读：展示 `/api/analysis/adb/coverage` 返回的快照 vs formal 日期缺口。
 */
export default function AdbCoverageDiagnostics({
  loading,
  isError,
  data,
}: AdbCoverageDiagnosticsProps) {
  return (
    <Collapse
      data-testid="adb-coverage-diagnostics"
      items={[
        {
          key: "coverage",
          label: "快照 vs formal 覆盖诊断（只读）",
          children: (
            <div>
              {loading ? (
                <Spin />
              ) : isError ? (
                <Alert type="error" showIcon message="覆盖诊断加载失败" />
              ) : data ? (
                <Space direction="vertical" size="small" style={{ width: "100%" }}>
                  <Text type="secondary">
                    区间 {data.start_date}～{data.end_date}：日历 {data.calendar_days} 天 · 快照去重{" "}
                    {data.snapshot_date_count} 日 · formal 去重 {data.formal_date_count} 日 · 缺口{" "}
                    {data.missing_count} 日（formal 相对快照并集约 {data.coverage_pct}%）
                  </Text>
                  {data.missing_dates.length > 0 ? (
                    <div data-testid="adb-coverage-missing-list">
                      <Text strong>缺 formal 的日期（前 {MAX_DATES_SHOWN} 条）</Text>
                      <List
                        size="small"
                        bordered
                        dataSource={data.missing_dates.slice(0, MAX_DATES_SHOWN)}
                        renderItem={(item) => <List.Item style={{ padding: "4px 8px" }}>{item}</List.Item>}
                        style={{ marginTop: 8, maxHeight: 280, overflow: "auto" }}
                      />
                      {data.missing_dates.length > MAX_DATES_SHOWN ? (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          … 共 {data.missing_dates.length} 条，其余请复制接口 JSON 或缩小区间查看。
                        </Text>
                      ) : null}
                    </div>
                  ) : (
                    <Text type="success">未发现「快照有、formal 无」的缺口日期。</Text>
                  )}
                </Space>
              ) : (
                <Text type="secondary">无数据</Text>
              )}
            </div>
          ),
        },
      ]}
    />
  );
}
