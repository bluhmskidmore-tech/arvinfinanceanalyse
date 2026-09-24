type BalanceMovementReadStatusProps = {
  tone: "error" | "empty";
  title: string;
  detail: string;
  testId: string;
  isFetching: boolean;
  hasCachedResult?: boolean;
  onRetry: () => void;
};

export function BalanceMovementReadStatus({
  tone,
  title,
  detail,
  testId,
  isFetching,
  hasCachedResult,
  onRetry,
}: BalanceMovementReadStatusProps) {
  return (
    <div
      data-testid={testId}
      className={`balance-movement-date-status balance-movement-date-status--${tone}`}
      role={tone === "error" ? "alert" : "status"}
    >
      <strong>{title}</strong>
      <span>{detail}</span>
      {tone === "error" && hasCachedResult ? (
        <span>当前显示上次成功读取结果，尚未确认本次更新。</span>
      ) : null}
      {tone === "error" ? (
        <button type="button" onClick={onRetry} disabled={isFetching}>
          重试读取
        </button>
      ) : null}
    </div>
  );
}
