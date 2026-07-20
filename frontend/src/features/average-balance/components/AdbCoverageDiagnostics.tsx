import { Alert, Collapse, List, Space, Spin, Typography } from "antd";
import type { AdbCoveragePayload } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

import "./AverageBalanceView.css";

const { Text } = Typography;

const MAX_DATES_SHOWN = 120;

type AdbRateCoveragePayload = {
  assetRateCoverageRatio?: number | null;
  liabilityRateCoverageRatio?: number | null;
};

type AdbCoverageDiagnosticsProps = {
  loading: boolean;
  isError: boolean;
  data: AdbCoveragePayload | undefined;
  rateCoverage?: AdbRateCoveragePayload;
};

function formatRatioPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${(value * 100).toFixed(1)}%`;
}

/**
 * 只读：展示 `/api/analysis/adb/coverage` 返回的快照 vs formal 日期缺口。
 */
export default function AdbCoverageDiagnostics({
  loading,
  isError,
  data,
  rateCoverage,
}: AdbCoverageDiagnosticsProps) {
  const hasRateCoverage =
    (rateCoverage?.assetRateCoverageRatio !== undefined && rateCoverage.assetRateCoverageRatio !== null) ||
    (rateCoverage?.liabilityRateCoverageRatio !== undefined && rateCoverage.liabilityRateCoverageRatio !== null);

  return (
    <Collapse
      data-testid="adb-coverage-diagnostics"
      items={[
        {
          key: "coverage",
          label: "快照 vs formal 覆盖诊断（只读）",
          children: (
            <Space direction="vertical" size="small" className="adb-stack">
              {hasRateCoverage ? (
                <Alert
                  data-testid="adb-rate-coverage-diagnostics"
                  type="warning"
                  showIcon
                  message="加权利率覆盖"
                  description={`资产 ${formatRatioPercent(rateCoverage?.assetRateCoverageRatio)} / 负债 ${formatRatioPercent(rateCoverage?.liabilityRateCoverageRatio)}`}
                />
              ) : null}
              {loading ? (
                <Spin />
              ) : isError ? (
                <Alert type="error" showIcon message="覆盖诊断加载失败" />
              ) : data ? (
                <Space direction="vertical" size="small" className="adb-stack">
                  <div className="adb-coverage-lines">
                    <Text type="secondary">
                      区间 {data.start_date}～{data.end_date} · 日历 {data.calendar_days} 天
                    </Text>
                    <Text type="secondary">
                      快照去重 {data.snapshot_date_count} 日 · formal 去重 {data.formal_date_count} 日
                    </Text>
                    <Text type="secondary">
                      缺口 {data.missing_count} 日（formal 相对快照并集约 {data.coverage_pct}%）
                    </Text>
                  </div>
                  {data.missing_dates.length > 0 ? (
                    <div data-testid="adb-coverage-missing-list">
                      <Text strong>缺 formal 的日期（前 {MAX_DATES_SHOWN} 条）</Text>
                      <List
                        size="small"
                        bordered
                        className="adb-coverage-list"
                        dataSource={data.missing_dates.slice(0, MAX_DATES_SHOWN)}
                        renderItem={(item) => (
                          <List.Item className="adb-coverage-list-item">{item}</List.Item>
                        )}
                      />
                      {data.missing_dates.length > MAX_DATES_SHOWN ? (
                        <Text type="secondary" className="adb-aux-label">
                          … 共 {data.missing_dates.length} 条，其余请复制接口 JSON 或缩小区间查看。
                        </Text>
                      ) : null}
                    </div>
                  ) : (
                    <Text className="adb-tone--ok">未发现「快照有、formal 无」的缺口日期。</Text>
                  )}
                </Space>
              ) : (
                <Text type="secondary">无数据</Text>
              )}
            </Space>
          ),
        },
      ]}
    />
  );
}
