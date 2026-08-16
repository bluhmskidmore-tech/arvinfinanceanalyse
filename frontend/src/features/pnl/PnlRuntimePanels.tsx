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
