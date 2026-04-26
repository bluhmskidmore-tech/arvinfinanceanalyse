export interface FooterProps {
  traceLabel?: string;
  complianceLabel?: string;
}

export function Footer({
  traceLabel = "可追溯分析底座",
  complianceLabel = "降级与陈旧状态必须显式展示",
}: FooterProps) {
  return (
    <div style={{ display: "flex", gap: 16, justifyContent: "space-between", color: "#475467" }}>
      <span>{traceLabel}</span>
      <span>{complianceLabel}</span>
    </div>
  );
}
