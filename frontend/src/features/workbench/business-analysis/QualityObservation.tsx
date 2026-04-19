import { SectionCard } from "../../../components/SectionCard";
import { StatusPill, type StatusPillStatus } from "../../../components/StatusPill";

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
      label: "Formal FX 覆盖",
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
    <SectionCard title="经营质量观察">
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {rows.map((row) => (
          <div
            key={row.label}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              padding: "10px 0",
              borderBottom: "1px solid #eef2f7",
            }}
          >
            <span style={{ fontSize: 14, color: "#31425b", fontWeight: 600 }}>{row.label}</span>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  fontSize: 14,
                  fontVariantNumeric: "tabular-nums",
                  color: "#162033",
                  fontWeight: 600,
                }}
              >
                {row.value}
              </span>
              <StatusPill status={row.status} label={row.pill} />
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
