export interface FooterProps {
  traceLabel?: string;
  complianceLabel?: string;
}

export function Footer({
  traceLabel = "Traceable analytics foundation",
  complianceLabel = "Fallback/stale states must remain explicit",
}: FooterProps) {
  return (
    <div style={{ display: "flex", gap: 16, justifyContent: "space-between", color: "#475467" }}>
      <span>{traceLabel}</span>
      <span>{complianceLabel}</span>
    </div>
  );
}
