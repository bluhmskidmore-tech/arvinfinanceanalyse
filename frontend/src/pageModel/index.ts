/**
 * Shared page view-model primitives.
 *
 * Every page read model (`*Model.ts` / `*PageModel.ts`) repeats the same
 * vocabulary: labeled display rows, tone words, state-surface items, and
 * "null → em dash" formatting. This module is the single place for that
 * vocabulary so new page models stop re-declaring it.
 *
 * Rules:
 * - Display-only. No official finance calculation lives here.
 * - `textOrDash` / `fixedOrDash` are shared implementations owned here;
 *   `EM_DASH` is re-exported from `utils/format.ts`. Tone helpers delegate
 *   to `utils/tone.ts`. Do not fork their logic.
 * - Keep this module small: only add a type/helper once it is repeated
 *   across several page models, not for a single page's convenience.
 */
import type { Numeric } from "../api/contracts";
import type { PageStateSurfaceVariant } from "../components/page/PagePrimitives";
import { EM_DASH } from "../utils/format";
import { toneFromNumeric, type Tone } from "../utils/tone";

// Re-exported so page models can import the shared display vocabulary from
// one place without re-declaring local copies.
export { EM_DASH } from "../utils/format";
export { toneFromNumeric, toneForStatus } from "../utils/tone";

// ---------------------------------------------------------------------------
// Tone
// ---------------------------------------------------------------------------

/**
 * Semantic tone for a displayed metric. Identical to `utils/tone.ts` `Tone`
 * ("positive" | "neutral" | "warning" | "negative"); page models should use
 * this name instead of declaring local tone unions.
 *
 * Note: component-level tone props with extra members (e.g. KpiCard's
 * "default"/"error") are a different vocabulary and stay on the component.
 */
export type MetricTone = Tone;

/**
 * Sign-based tone for a plain number (delegates to `toneFromNumeric`):
 * positive → "positive", negative → "negative", zero/null/undefined →
 * "neutral". Use for signed deltas; never for absolute-valued metrics.
 */
export function toneFromSignedValue(raw: number | null | undefined): MetricTone {
  return toneFromNumeric({
    raw: raw ?? null,
    unit: "ratio",
    display: "",
    precision: 0,
    sign_aware: true,
  });
}

// ---------------------------------------------------------------------------
// Labeled display values
// ---------------------------------------------------------------------------

/**
 * Landing state of a page section/data lane, as shown in section registries
 * (e.g. dashboard cockpit sections, first-screen readiness models).
 */
export type SectionStatus = "landed" | "stale" | "blocked" | "loading" | "empty" | "error";

/**
 * One labeled display value: the common row shape behind KPI bands, metric
 * rails, ticker items, and overview stats. `value` is a pre-formatted display
 * string — formatting happens in the model, never in the component.
 */
export type LabeledValue = {
  key: string;
  label: string;
  value: string;
  unit?: string;
  detail?: string;
  delta?: string;
  tone?: MetricTone;
  status?: SectionStatus;
  date?: string;
  note?: string;
};

// ---------------------------------------------------------------------------
// State surfaces (query/meta status → explicit on-page evidence)
// ---------------------------------------------------------------------------

/**
 * Variant vocabulary for `PageStateSurface`. Aliased from the component
 * contract so models and the component can never drift apart.
 */
export type StateSurfaceVariant = PageStateSurfaceVariant;

/** One rendered state surface (mock/fallback/stale/… evidence block). */
export type StateSurfaceItem = {
  key: string;
  variant: StateSurfaceVariant;
  title: string;
  description: string;
};

/** A state surface plus the condition under which it should be shown. */
export type StateSurfaceCandidate = StateSurfaceItem & {
  /** Include this surface only when true. */
  when: boolean;
};

/**
 * Assemble the page's state-surface list from declarative candidates.
 *
 * Replaces the repeated `if (…) surfaces.push({…})` chains in page models:
 * keeps candidate order, drops the `when` flag from the emitted items, and
 * optionally emits a single "all clear" fallback when nothing matched.
 */
export function buildStateSurfaces(
  candidates: readonly StateSurfaceCandidate[],
  options?: { emptyFallback?: StateSurfaceItem },
): StateSurfaceItem[] {
  const surfaces = candidates
    .filter((candidate) => candidate.when)
    .map(({ when: _when, ...item }) => item);
  if (surfaces.length === 0 && options?.emptyFallback) {
    return [options.emptyFallback];
  }
  return surfaces;
}

// ---------------------------------------------------------------------------
// Page hero
// ---------------------------------------------------------------------------

/**
 * First-screen decision hero content (layout contract §2): the primary
 * business question plus the current conclusion and report-date evidence.
 * Date fields are optional because not every page carries a requested/served
 * date pair.
 */
export type PageHero = {
  businessQuestion: string;
  conclusionTitle: string;
  conclusionDetail: string;
  reportDateLabel?: string;
  requestedReportDate?: string;
  asOfDate?: string;
  reportDateNote?: string;
};

// ---------------------------------------------------------------------------
// Missing-value display helpers (canonical placeholder: EM_DASH)
// ---------------------------------------------------------------------------

/** Display a string, or `EM_DASH` when it is null/undefined/empty. */
export function textOrDash(value: string | null | undefined): string {
  return value === null || value === undefined || value === "" ? EM_DASH : value;
}

/**
 * `value.toFixed(digits)`, or `EM_DASH` when the value is null/undefined or
 * not a finite number. `digits` is explicit on purpose — precision is part of
 * the metric contract, not a default.
 */
export function fixedOrDash(value: number | null | undefined, digits: number): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return value.toFixed(digits);
}

/**
 * `value.toLocaleString(locale, options)`, or `EM_DASH` when the value is
 * null/undefined or not finite. Locale and formatting options stay explicit
 * so this helper does not introduce business-specific display defaults.
 */
export function localeOrDash(
  value: number | null | undefined,
  locale: string,
  options?: Intl.NumberFormatOptions,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return value.toLocaleString(locale, options);
}

/**
 * `value.toFixed(digits) + "%"`, or `EM_DASH` when the value is null/undefined
 * or not finite. Extracted because the shape repeats across 26+ page models
 * (2026-08-13 audit); adopt only where the local semantics are identical
 * (no `—%` suffix-on-missing variants).
 */
export function pctOrDash(value: number | null | undefined, digits: number): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return `${value.toFixed(digits)}%`;
}

/**
 * Signed `toFixed` display: strictly-positive values get a `+` prefix, zero
 * and negative keep the native sign; `EM_DASH` when missing/not finite.
 */
export function signedFixedOrDash(
  value: number | null | undefined,
  digits: number,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  const fixed = value.toFixed(digits);
  return value > 0 ? `+${fixed}` : fixed;
}

// ---------------------------------------------------------------------------
// Numeric (governed value) helpers
// ---------------------------------------------------------------------------

/** The finite raw of a `Numeric`, or null when absent/NaN/Infinity. */
export function numericRaw(value: Numeric | null | undefined): number | null {
  if (!value || value.raw === null || !Number.isFinite(value.raw)) {
    return null;
  }
  return value.raw;
}

/** Like `numericRaw` but coerces missing values to 0 (chart-safe series). */
export function numericRawOrZero(value: Numeric | null | undefined): number {
  return numericRaw(value) ?? 0;
}
