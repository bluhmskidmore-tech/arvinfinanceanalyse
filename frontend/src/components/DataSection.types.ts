/**
 * Discriminated union describing the rendering state of a ``DataSection``.
 *
 * Only one state is active at a time; adapter / selector layer is responsible
 * for collapsing raw flags (``isLoading`` / ``isError`` / ``result_meta``)
 * into exactly one ``DataSectionState``.
 *
 * See ``docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md`` § 6.
 */
export type DataSectionState =
  | { kind: "loading" }
  | { kind: "error"; message?: string }
  | { kind: "empty"; hint?: string }
  | { kind: "stale"; effective_date?: string; details?: string }
  | { kind: "fallback"; effective_date?: string; details?: string }
  | { kind: "vendor_unavailable"; details?: string }
  | { kind: "explicit_miss"; requested_date?: string; details?: string }
  | { kind: "ok" };

export type DataSectionStateKind = DataSectionState["kind"];
