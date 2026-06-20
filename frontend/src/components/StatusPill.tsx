import "./StatusPill.css";

export type StatusPillStatus = "normal" | "caution" | "warning" | "danger";

export type StatusPillProps = {
  status: StatusPillStatus;
  label: string;
};

export function StatusPill({ status, label }: StatusPillProps) {
  return (
    <span className="status-pill" data-status={status}>
      {label}
    </span>
  );
}
