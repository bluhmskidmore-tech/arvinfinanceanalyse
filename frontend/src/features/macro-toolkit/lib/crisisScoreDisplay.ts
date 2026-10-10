export type CrisisScoreComponentLike = {
  key: string;
  label?: string | null;
  z_score?: number | null;
};

export function formatCrisisTopContributorSummary(
  components: readonly CrisisScoreComponentLike[],
  limit = 2,
): string | null {
  const ranked = components
    .filter((component) => typeof component.z_score === "number" && Number.isFinite(component.z_score))
    .sort((left, right) => Math.abs(right.z_score!) - Math.abs(left.z_score!))
    .slice(0, limit);

  if (ranked.length === 0) {
    return null;
  }

  return ranked
    .map((component) => `${component.label?.trim() || component.key} z=${component.z_score!.toFixed(2)}`)
    .join(" · ");
}
