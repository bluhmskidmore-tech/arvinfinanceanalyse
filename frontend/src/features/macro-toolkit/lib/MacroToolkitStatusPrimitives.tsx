import type { ReactNode } from "react";
import { InfoCircleOutlined } from "@ant-design/icons";

import type { MacroToolkitSignalCard } from "../../../api/macroToolkitClient";
import { compactText } from "./macroToolkitPanelShared";

function macroStatusIconTone(tone: MacroToolkitSignalCard["tone"] | "positive" | "neutral" | "missing") {
  if (tone === "positive") return "positive";
  if (tone === "negative") return "negative";
  if (tone === "missing") return "missing";
  return "neutral";
}

export function MacroStatusIcon({
  tone = "neutral",
  children,
}: {
  tone?: MacroToolkitSignalCard["tone"] | "positive" | "neutral" | "missing";
  children: ReactNode;
}) {
  return (
    <span className={`macro-toolkit-status-icon macro-toolkit-status-icon--${macroStatusIconTone(tone)}`}>
      {children}
    </span>
  );
}

export function MetricTile({
  icon,
  label,
  value,
  detail,
  detailTitle,
  tone = "neutral",
  testId,
  detailMaxLength = 26,
}: {
  icon?: ReactNode;
  label: string;
  value: string | number;
  detail: string;
  detailTitle?: string;
  tone?: "neutral" | "positive" | "missing";
  testId?: string;
  detailMaxLength?: number;
}) {
  return (
    <div className={`macro-toolkit-metric macro-toolkit-metric--${tone}`} data-testid={testId}>
      <span>
        <MacroStatusIcon tone={tone}>{icon ?? <InfoCircleOutlined />}</MacroStatusIcon>
        {label}
      </span>
      <strong>{value}</strong>
      <small title={detailTitle ?? detail}>{compactText(detail, detailMaxLength)}</small>
    </div>
  );
}
