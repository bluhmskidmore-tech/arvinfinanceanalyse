import { shellTokens } from "../../theme/tokens";

export function PnlRefreshStatus({
  testId,
  status,
  error,
}: {
  testId: string;
  status: string | null;
  error: string | null;
}) {
  if (!status && !error) {
    return null;
  }

  return (
    <div
      data-testid={testId}
      style={{
        marginBottom: 16,
        padding: 14,
        borderRadius: 14,
        border: "1px solid #e4ebf5",
        background: error ? "#fff2f0" : "#f7f9fc",
        color: error ? "#c83b3b" : "#5c6b82",
      }}
    >
      {error ?? status}
    </div>
  );
}

export function PnlDebugPanel({
  testId,
  snapshot,
}: {
  testId: string;
  snapshot: unknown;
}) {
  return (
    <details
      data-testid={testId}
      style={{
        marginTop: 24,
        padding: 16,
        borderRadius: 16,
        border: `1px solid ${shellTokens.colorBorderSoft}`,
        background: "#ffffff",
      }}
    >
      <summary style={{ cursor: "pointer", fontWeight: 600, color: shellTokens.colorText }}>
        result_meta / 调试
      </summary>
      <div style={{ marginTop: 12 }}>
        <pre
          style={{
            margin: 0,
            padding: 16,
            overflowX: "auto",
            borderRadius: 12,
            background: shellTokens.colorBgMuted,
            color: shellTokens.colorText,
            fontSize: 12,
            lineHeight: 1.6,
          }}
        >
          {JSON.stringify(snapshot, null, 2)}
        </pre>
      </div>
    </details>
  );
}
