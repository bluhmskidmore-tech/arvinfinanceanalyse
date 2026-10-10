import { Typography } from "antd";
import type { AdbComparisonResponse } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

import "./AverageBalanceView.css";

const { Text, Paragraph } = Typography;

/** 多行文本，供复制到工单 / 排障记录（与页面展示口径一致，不做重算）。 */
function buildAdbDenominatorCopyText(data: AdbComparisonResponse): string {
  const cov =
    data.coverage_days !== undefined && data.coverage_days !== null
      ? String(data.coverage_days)
      : EM_DASH;
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

  return (
    <div className="adb-embed" data-testid="adb-denominator-summary">
      <div className="adb-lines">
        <div>
          分母={data.adb_denominator_basis} · 日历 {data.calendar_days_inclusive} 天
        </div>
        <div>
          区间 {data.num_days} 天
          {data.coverage_days !== undefined && data.coverage_days !== null
            ? ` · 有数据 ${data.coverage_days} 天`
            : ""}
        </div>
        {data.sample_filled === true ? (
          <div>已按「{data.sample_fill_method ?? "规则"}」将稀疏观察日扩到日历区间</div>
        ) : null}
      </div>
      <Paragraph copyable={{ text: copyText }} className="adb-note adb-copy-hint">
        <Text type="secondary">复制完整口径摘要（运维排障）</Text>
      </Paragraph>
    </div>
  );
}
