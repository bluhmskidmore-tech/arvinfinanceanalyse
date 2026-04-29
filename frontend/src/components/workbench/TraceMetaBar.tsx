import type { ReactNode } from "react";
import { Tag, Tooltip } from "antd";
import { ClockCircleOutlined, DatabaseOutlined, FieldTimeOutlined, SafetyOutlined } from "@ant-design/icons";
import { isTruthyMeta, pickMeta, renderValue } from "./utils";
import type { ResultMetaLike } from "./types";

export interface TraceMetaBarProps {
  meta?: ResultMetaLike;
  items?: Array<{ key: string; label: ReactNode; value: ReactNode; icon?: ReactNode }>;
  compact?: boolean;
}

function stringify(value: unknown): ReactNode {
  if (value === null || value === undefined || value === "") return "--";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function hasFallback(meta: ResultMetaLike): boolean {
  const fallbackMode = pickMeta(meta, ["fallback_mode", "fallbackMode"]);
  return (
    isTruthyMeta(meta, ["fallback", "is_fallback"]) ||
    (typeof fallbackMode === "string" && fallbackMode !== "none")
  );
}

function hasStale(meta: ResultMetaLike): boolean {
  return (
    isTruthyMeta(meta, ["stale", "is_stale"]) ||
    pickMeta(meta, ["quality_flag", "qualityFlag", "quality"]) === "stale" ||
    pickMeta(meta, ["vendor_status", "vendorStatus"]) === "vendor_stale"
  );
}

export function TraceMetaBar({ meta, items = [], compact }: TraceMetaBarProps) {
  const fallback = hasFallback(meta);
  const stale = hasStale(meta);
  const derivedItems = [
    { key: "report_date", label: "报告日", value: stringify(pickMeta(meta, ["report_date", "reportDate", "date"])), icon: <ClockCircleOutlined /> },
    { key: "effective_date", label: "生效日", value: stringify(pickMeta(meta, ["effective_date", "effectiveDate", "as_of_date"])), icon: <FieldTimeOutlined /> },
    { key: "generated_at", label: "生成", value: stringify(pickMeta(meta, ["generated_at", "generatedAt", "computed_at", "computedAt"])), icon: <ClockCircleOutlined /> },
    { key: "source", label: "来源", value: stringify(pickMeta(meta, ["source", "data_source", "source_version", "sourceVersion", "vendor", "vendor_name"])), icon: <DatabaseOutlined /> },
    { key: "rule", label: "规则", value: stringify(pickMeta(meta, ["rule_version", "ruleVersion"])), icon: <SafetyOutlined /> },
    { key: "quality", label: "质量", value: stringify(pickMeta(meta, ["quality_flag", "qualityFlag", "quality", "quality_status", "basis"])), icon: <SafetyOutlined /> },
  ].filter((item) => item.value !== "--");

  const viewItems = [...derivedItems, ...items];
  if (!viewItems.length && !fallback && !stale) return null;

  return (
    <section className={compact ? "moss-trace-meta moss-trace-meta--compact" : "moss-trace-meta"}>
      {fallback ? <Tag color="orange">Fallback</Tag> : null}
      {stale ? <Tag color="gold">Stale</Tag> : null}
      {viewItems.map((item) => (
        <Tooltip key={item.key} title={`${item.label}: ${typeof item.value === "string" ? item.value : ""}`}>
          <span className="moss-trace-meta__item">
            {item.icon ? <span className="moss-trace-meta__icon">{item.icon}</span> : null}
            <span className="moss-trace-meta__label">{item.label}</span>
            <span className="moss-trace-meta__value">{renderValue(item.value)}</span>
          </span>
        </Tooltip>
      ))}
    </section>
  );
}
