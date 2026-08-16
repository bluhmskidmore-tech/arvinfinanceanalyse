import { EvidencePanel } from "../../../components/page/PagePrimitives";
import { StatusPill, type StatusPillStatus } from "../../../components/StatusPill";
import styles from "./QualityObservation.module.css";

type QualityObservationProps = {
  sourceCount?: number;
  macroCount?: number;
  newsCount?: number;
  fxMaterializedCount?: number;
  fxCandidateCount?: number;
  missingFxCount?: number;
};

type Row = {
  label: string;
  value: string;
  status: StatusPillStatus;
  pill: string;
};

function buildRows(props: QualityObservationProps): Row[] {
  return [
    {
      label: "源批次数",
      value: String(props.sourceCount ?? 0),
      status: (props.sourceCount ?? 0) > 0 ? "normal" : "caution",
      pill: (props.sourceCount ?? 0) > 0 ? "已到位" : "待确认",
    },
    {
      label: "宏观最新点位",
      value: String(props.macroCount ?? 0),
      status: (props.macroCount ?? 0) > 0 ? "normal" : "caution",
      pill: (props.macroCount ?? 0) > 0 ? "已到位" : "待确认",
    },
    {
      label: "新闻事件",
      value: String(props.newsCount ?? 0),
      status: (props.newsCount ?? 0) > 0 ? "normal" : "caution",
      pill: (props.newsCount ?? 0) > 0 ? "可读" : "空白",
    },
    {
      label: "正式外汇覆盖",
      value: `${props.fxMaterializedCount ?? 0}/${props.fxCandidateCount ?? 0}`,
      status:
        (props.fxCandidateCount ?? 0) > 0 &&
        (props.fxMaterializedCount ?? 0) === (props.fxCandidateCount ?? 0)
          ? "normal"
          : "warning",
      pill:
        (props.fxCandidateCount ?? 0) > 0 &&
        (props.fxMaterializedCount ?? 0) === (props.fxCandidateCount ?? 0)
          ? "完整"
          : "关注",
    },
    {
      label: "缺失货币对",
      value: String(props.missingFxCount ?? 0),
      status: (props.missingFxCount ?? 0) > 0 ? "danger" : "normal",
      pill: (props.missingFxCount ?? 0) > 0 ? "预警" : "正常",
    },
  ];
}

export function QualityObservation(props: QualityObservationProps) {
  const rows = buildRows(props);

  return (
    <EvidencePanel heading="经营质量观察">
      <div className={styles.list}>
        {rows.map((row) => (
          <div key={row.label} className={styles.row}>
            <span className={styles.label}>{row.label}</span>
            <div className={styles.valueGroup}>
              <span className={styles.value}>{row.value}</span>
              <StatusPill status={row.status} label={row.pill} />
            </div>
          </div>
        ))}
      </div>
    </EvidencePanel>
  );
}
