import "./PnlRuntimePanels.css";

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
      className={error ? "pnl-refresh-status pnl-refresh-status--error" : "pnl-refresh-status"}
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
    <details data-testid={testId} className="pnl-debug-panel">
      <summary>结果元信息 / 调试</summary>
      <div className="pnl-debug-panel__body">
        <pre className="pnl-debug-panel__pre">{JSON.stringify(snapshot, null, 2)}</pre>
      </div>
    </details>
  );
}
