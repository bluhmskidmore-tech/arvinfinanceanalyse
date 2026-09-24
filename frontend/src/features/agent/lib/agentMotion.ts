const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

export function getAgentScrollBehavior(): ScrollBehavior {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return "smooth";
  }

  return window.matchMedia(REDUCED_MOTION_QUERY).matches ? "auto" : "smooth";
}
