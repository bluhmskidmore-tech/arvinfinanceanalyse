import { SectionCard } from "../../../components/SectionCard";
import { StatusPill, type StatusPillStatus } from "../../../components/StatusPill";

type Row = { label: string; value: string; status: StatusPillStatus; pill: string };

const ROWS: Row[] = [
  { label: "资产/负债比", value: "1.94x", status: "normal", pill: "正常" },
  { label: "发行负债集中度", value: "81.8%", status: "caution", pill: "关注" },
  { label: "短期负债占比", value: "72.6%", status: "warning", pill: "预警" },
  { label: "1年内缺口/负债", value: "20.5%", status: "caution", pill: "关注" },
  { label: "异常资产占比", value: "0.21%", status: "normal", pill: "正常" },
];

export function QualityObservation() {
  return (
    <SectionCard title="经营质量观察">
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {ROWS.map((row) => (
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
