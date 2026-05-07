import { Card, Space, Typography } from "antd";
import type { AdbComparisonResponse } from "../../../api/contracts";

const { Text, Paragraph } = Typography;

/** 多行文本，供复制到工单 / 排障记录（与页面展示口径一致，不做重算）。 */
export function buildAdbDenominatorCopyText(data: AdbComparisonResponse): string {
  const cov =
    data.coverage_days !== undefined && data.coverage_days !== null
      ? String(data.coverage_days)
      : "—";
  const filled = data.sample_filled === true;
  return [
    `adb_denominator_basis=${data.adb_denominator_basis}`,
    `calendar_days_inclusive=${data.calendar_days_inclusive}`,
    `num_days=${data.num_days}`,
    `coverage_days=${cov}`,
    `sample_filled=${filled}`,
    `sample_fill_method=${data.sample_fill_method ?? "none"}`,
    `simulated=${data.simulated}`,
    `end_date=${data.end_date}`,
  ].join("\n");
}

type AdbDenominatorSummaryProps = {
  data: AdbComparisonResponse;
};

/**
 * 日均分母与补全规则摘要（后端已返回字段的只读展示）。
 */
export default function AdbDenominatorSummary({ data }: AdbDenominatorSummaryProps) {
  const copyText = buildAdbDenominatorCopyText(data);
  const coveragePart =
    data.coverage_days !== undefined && data.coverage_days !== null
      ? ` · 有数据 ${data.coverage_days} 天`
      : "";
  const fillPart =
    data.sample_filled === true
      ? ` · 已按「${data.sample_fill_method ?? "规则"}」将稀疏观察日扩到日历区间`
      : "";
  const oneLine = `分母=${data.adb_denominator_basis} · 日历 ${data.calendar_days_inclusive} 天 · 区间 ${data.num_days} 天${coveragePart}${fillPart}`;

  return (
    <Card size="small" data-testid="adb-denominator-summary">
      <Space direction="vertical" size={4} style={{ width: "100%" }}>
        <Text type="secondary">{oneLine}</Text>
        <Paragraph copyable={{ text: copyText }} style={{ marginBottom: 0, fontSize: 12 }}>
          <Text type="secondary">复制完整口径摘要（运维排障）</Text>
        </Paragraph>
      </Space>
    </Card>
  );
}
