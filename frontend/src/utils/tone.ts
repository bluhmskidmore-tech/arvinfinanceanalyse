/**
 * Single source of truth for tone (semantic color) across governed pages.
 *
 * Components MUST NOT define local tone/color maps. Pages that need a custom
 * palette must add it here under a new exported const, never inline inside a
 * component file.
 */
import type { Numeric } from "../api/contracts";

export type Tone = "positive" | "neutral" | "warning" | "negative";

export const TONE_COLOR: Record<Tone, string> = {
  positive: "#2f8f63",
  neutral: "#6d7f99",
  warning: "#b35a16",
  negative: "#c1554b",
};

/**
 * Derive a tone from a Numeric's sign. Returns ``neutral`` for ``raw=null``,
 * zero, or ``sign_aware=false`` values (the latter are absolute-valued by
 * design and must not be colored by sign).
 */
export function toneFromNumeric(n: Numeric): Tone {
  if (!n.sign_aware) return "neutral";
  if (n.raw === null) return "neutral";
  if (n.raw > 0) return "positive";
  if (n.raw < 0) return "negative";
  return "neutral";
}

const STATUS_TONE: Record<string, Tone> = {
  ok: "positive",
  stable: "positive",
  warning: "warning",
  watch: "warning",
  stale: "warning",
  vendor_stale: "warning",
  error: "negative",
  vendor_unavailable: "negative",
  explicit_miss: "negative",
};

/**
 * Map an arbitrary governance / UI status string to a tone. Unknown strings
 * resolve to ``neutral``; callers should not branch on the string themselves.
 */
export function toneForStatus(status: string): Tone {
  return STATUS_TONE[status] ?? "neutral";
}
