import type { ApiQuality, ResultMeta } from "../../api/contracts";
import "./DataQualityBanner.css";

type BannerLevel = "ok" | "partial" | "degraded";

export interface DataQualityBannerProps {
  resultMeta: ResultMeta | null | undefined;
  warnings?: string[];
  /** 额外的降级原因（如 incompleteReasons） */
  degradedReasons?: string[];
}

const LEVEL_CONFIG: Record<
  BannerLevel,
  { className: string; label: string }
> = {
  ok: { className: "", label: "" },
  partial: {
    className: "data-quality-banner--partial",
    label: "部分数据使用回退值",
  },
  degraded: {
    className: "data-quality-banner--degraded",
    label: "数据质量异常，仅供参考",
  },
};

function deriveLevel(
  qualityFlag: ApiQuality | undefined,
  warnings: string[],
  degradedReasons: string[],
): BannerLevel {
  if (qualityFlag === "error" || qualityFlag === "stale") return "degraded";
  if (qualityFlag === "warning" || degradedReasons.length > 0) return "partial";
  if (warnings.length > 0) return "partial";
  return "ok";
}

export function DataQualityBanner({
  resultMeta,
  warnings = [],
  degradedReasons = [],
}: DataQualityBannerProps) {
  const level = deriveLevel(resultMeta?.quality_flag, warnings, degradedReasons);

  if (level === "ok") return null;

  const config = LEVEL_CONFIG[level];
  const allReasons = [...degradedReasons, ...warnings];

  return (
    <div
      className={`data-quality-banner ${config.className}`}
      role="alert"
      aria-live="polite"
    >
      <span className="data-quality-banner__label">{config.label}</span>
      {allReasons.length > 0 ? (
        <details className="data-quality-banner__details">
          <summary>详情（{allReasons.length} 项）</summary>
          <ul className="data-quality-banner__list">
            {allReasons.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
