export function stockGateDecisionTone(
  state: string | null | undefined,
  hasBoundaryIssue: boolean,
): "ok" | "watch" | "negative" {
  const normalized = (state ?? "").trim().toUpperCase();
  if (["NO_DATA", "OFF", "STALE", "OVERHEAT"].includes(normalized)) return "negative";
  if (["HOT", "PENDING_DATA", "UNKNOWN"].includes(normalized) || hasBoundaryIssue) return "watch";
  return "ok";
}

export function stockGateContextTone(tone: "ok" | "watch" | "negative"): "positive" | "watch" | "negative" {
  if (tone === "ok") return "positive";
  return tone;
}

export function stockSourceGateTone({
  isError,
  isLoading,
  quality,
  vendor,
  fallback,
}: {
  isError: boolean;
  isLoading: boolean;
  quality: string | null | undefined;
  vendor: string | null | undefined;
  fallback: string | null | undefined;
}): "positive" | "watch" | "negative" | "neutral" {
  if (isError) return "negative";
  if (isLoading) return "neutral";
  const normalizedQuality = (quality ?? "pending").trim().toLowerCase();
  const normalizedVendor = (vendor ?? "pending").trim().toLowerCase();
  const normalizedFallback = (fallback ?? "none").trim().toLowerCase();
  if (
    ["error", "stale"].includes(normalizedQuality) ||
    ["error", "vendor_unavailable"].includes(normalizedVendor) ||
    normalizedFallback === "mock"
  ) {
    return "negative";
  }
  if (normalizedQuality !== "ok" || normalizedVendor !== "ok" || normalizedFallback !== "none") {
    return "watch";
  }
  return "positive";
}
