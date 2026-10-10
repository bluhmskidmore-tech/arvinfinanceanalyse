import { type ReactNode, useEffect, useRef, useState } from "react";

type CrossAssetDecisionAppendixStage = 0 | 1 | 2 | 3 | 4;

const CROSS_ASSET_DECISION_APPENDIX_FINAL_STAGE = 4;

function clampAppendixStage(value: number): CrossAssetDecisionAppendixStage {
  return Math.max(
    0,
    Math.min(CROSS_ASSET_DECISION_APPENDIX_FINAL_STAGE, value),
  ) as CrossAssetDecisionAppendixStage;
}

export function CrossAssetDecisionAppendix({
  enabled,
  forceMaterialize,
  statusGroup,
  confluenceGroup,
  sectorRankGroup,
  finalGroup,
}: {
  enabled: boolean;
  forceMaterialize: boolean;
  statusGroup: ReactNode;
  confluenceGroup: ReactNode;
  sectorRankGroup: ReactNode;
  finalGroup: ReactNode;
}) {
  const [stage, setStage] = useState<CrossAssetDecisionAppendixStage>(0);
  const pendingFrameRef = useRef<number | null>(null);

  const requestAnimationFrameUnavailable =
    typeof window === "undefined" || typeof window.requestAnimationFrame !== "function";
  const effectiveStage =
    forceMaterialize || (enabled && requestAnimationFrameUnavailable)
      ? CROSS_ASSET_DECISION_APPENDIX_FINAL_STAGE
      : stage;

  useEffect(() => {
    if (
      pendingFrameRef.current != null &&
      typeof window !== "undefined" &&
      typeof window.cancelAnimationFrame === "function"
    ) {
      window.cancelAnimationFrame(pendingFrameRef.current);
      pendingFrameRef.current = null;
    }

    if (forceMaterialize || (enabled && requestAnimationFrameUnavailable)) {
      setStage((currentStage) =>
        Math.max(
          currentStage,
          CROSS_ASSET_DECISION_APPENDIX_FINAL_STAGE,
        ) as CrossAssetDecisionAppendixStage,
      );
      return undefined;
    }

    if (!enabled || stage >= CROSS_ASSET_DECISION_APPENDIX_FINAL_STAGE) {
      return undefined;
    }

    const nextStage = clampAppendixStage(stage + 1);
    pendingFrameRef.current = window.requestAnimationFrame(() => {
      pendingFrameRef.current = null;
      setStage((currentStage) =>
        Math.max(currentStage, nextStage) as CrossAssetDecisionAppendixStage,
      );
    });

    return () => {
      if (
        pendingFrameRef.current != null &&
        typeof window !== "undefined" &&
        typeof window.cancelAnimationFrame === "function"
      ) {
        window.cancelAnimationFrame(pendingFrameRef.current);
        pendingFrameRef.current = null;
      }
    };
  }, [enabled, forceMaterialize, requestAnimationFrameUnavailable, stage]);

  return effectiveStage >= 1 ? (
    <div className="cross-asset-decision-appendix__body">
      {statusGroup}
      {effectiveStage >= 2 ? confluenceGroup : null}
      {effectiveStage >= 3 ? sectorRankGroup : null}
      {effectiveStage >= 4 ? finalGroup : null}
    </div>
  ) : null;
}
