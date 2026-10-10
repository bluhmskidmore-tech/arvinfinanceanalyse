import "./StatusPill.css";
import type { ReactNode } from "react";
import { mapRawStatusToBusinessStatus, mapStatusEntry } from "./StatusContract";
import type {
  ActionPriorityStatus,
  BusinessRiskStatus,
  BusinessStatusValue,
  DataQualityStatus,
  DataSourceStatus,
  StatusContractCategory,
  StatusPillStatus,
  SystemAccessStatus,
} from "./StatusContract";

export type {
  ActionPriorityStatus,
  BusinessRiskStatus,
  BusinessStatusValue,
  DataQualityStatus,
  DataSourceStatus,
  StatusContractCategory,
  StatusPillStatus,
  SystemAccessStatus,
} from "./StatusContract";

export type StatusPillProps = {
  status: StatusPillStatus;
  label: ReactNode;
  className?: string;
  testId?: string;
  title?: string;
};

export type StatusContractBadgeProps = {
  raw?: unknown;
  label?: ReactNode;
  className?: string;
  testId?: string;
  title?: string;
};

export type DataQualityPillProps = StatusContractBadgeProps & {
  status?: DataQualityStatus;
};

export type DataSourceBadgeProps = StatusContractBadgeProps & {
  status?: DataSourceStatus;
};

export type RiskBadgeProps = StatusContractBadgeProps & {
  status?: BusinessRiskStatus;
};

export type SystemAccessBadgeProps = StatusContractBadgeProps & {
  status?: SystemAccessStatus;
};

export type ActionPriorityBadgeProps = StatusContractBadgeProps & {
  status?: ActionPriorityStatus;
};

export type DiagnosticDisclosureProps = {
  children: ReactNode;
  summary?: ReactNode;
  className?: string;
  testId?: string;
};

function StatusContractPill({
  category,
  status,
  raw,
  label,
  className,
  testId,
  title,
}: StatusContractBadgeProps & {
  category: StatusContractCategory;
  status?: BusinessStatusValue;
}) {
  const mapped = status ? mapStatusEntry(category, status) : mapRawStatusToBusinessStatus(raw, category);
  return (
    <StatusPill
      status={mapped.tone}
      label={label ?? mapped.label}
      className={className}
      testId={testId}
      title={title ?? mapped.description}
    />
  );
}

export function StatusPill({ status, label, className, testId, title }: StatusPillProps) {
  const classes = ["status-pill", className].filter(Boolean).join(" ");
  return (
    <span className={classes} data-status={status} data-testid={testId} title={title}>
      {label}
    </span>
  );
}

export function DataQualityPill(props: DataQualityPillProps) {
  return <StatusContractPill {...props} category="dataQuality" />;
}

export function DataSourceBadge(props: DataSourceBadgeProps) {
  return <StatusContractPill {...props} category="dataSource" />;
}

export function RiskBadge(props: RiskBadgeProps) {
  return <StatusContractPill {...props} category="risk" />;
}

export function SystemAccessBadge(props: SystemAccessBadgeProps) {
  return <StatusContractPill {...props} category="systemAccess" />;
}

export function ActionPriorityBadge(props: ActionPriorityBadgeProps) {
  return <StatusContractPill {...props} category="actionPriority" />;
}

export function DiagnosticDisclosure({
  children,
  summary = "查看数据诊断",
  className,
  testId,
}: DiagnosticDisclosureProps) {
  const classes = ["diagnostic-disclosure", className].filter(Boolean).join(" ");
  return (
    <details className={classes} data-testid={testId}>
      <summary>{summary}</summary>
      <div className="diagnostic-disclosure__body">{children}</div>
    </details>
  );
}
