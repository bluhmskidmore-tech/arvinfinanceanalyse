import { shellTokens as t } from "../../../theme/tokens";

type AgentEvidencePanelProps = {
  tablesUsed: string[];
  filtersApplied: Record<string, unknown>;
  evidenceRows: number;
  qualityFlag: string;
};

export function AgentEvidencePanel({
  tablesUsed,
  filtersApplied,
  evidenceRows,
  qualityFlag,
}: AgentEvidencePanelProps) {
  return (
    <div
      style={{
        marginTop: 18,
        padding: 16,
        borderRadius: 14,
        border: `1px solid ${t.colorBorderSoft}`,
        background: t.colorBgSurface,
      }}
    >
      <div
        style={{
          color: t.colorTextMuted,
          fontSize: 12,
          marginBottom: 8,
        }}
      >
        证据链
      </div>
      <div
        style={{
          fontSize: 13,
          color: t.colorTextSecondary,
          lineHeight: 1.7,
        }}
      >
        tables: {tablesUsed.join(", ")}
        <br />
        filters: {JSON.stringify(filtersApplied)}
        <br />
        rows: {evidenceRows}
        <br />
        quality: {qualityFlag}
      </div>
    </div>
  );
}
