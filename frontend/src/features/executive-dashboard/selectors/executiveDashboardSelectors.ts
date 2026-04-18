/**
 * Executive Dashboard selectors.
 *
 * These are pure functions that carve adapter view-models into per-component
 * sub-views, with the critical invariant that **cross-component uses share
 * the same Numeric reference** (no copies, no per-component recalculation).
 *
 * Components downstream (W2.5 OverviewSection, W2.6 PnlAttributionSection)
 * MUST call these selectors instead of reading the VM directly. This keeps
 * the ring-chart slices, list bars, and center label all backed by the
 * identical Numeric.raw sequence.
 *
 * Design reference: ``docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md`` § 5.3.
 */
import type {
  DashboardOverviewMetricVM,
  DashboardOverviewVM,
  DashboardPnlAttributionVM,
  DashboardPnlSegmentVM,
} from "../adapters/executiveDashboardAdapter";
import type { Numeric } from "../../../api/contracts";

export function selectOverviewCards(
  vm: DashboardOverviewVM | null,
): DashboardOverviewMetricVM[] {
  if (!vm) return [];
  return vm.metrics;
}

export function selectPnlTotal(
  vm: DashboardPnlAttributionVM | null,
): Numeric | null {
  if (!vm) return null;
  return vm.total;
}

export function selectPnlSegmentsForChart(
  vm: DashboardPnlAttributionVM | null,
): DashboardPnlSegmentVM[] {
  if (!vm) return [];
  return vm.segments;
}

export function selectPnlSegmentsForList(
  vm: DashboardPnlAttributionVM | null,
): DashboardPnlSegmentVM[] {
  if (!vm) return [];
  // Invariant: identical reference as selectPnlSegmentsForChart's output;
  // downstream components share raw numbers without recomputation.
  return vm.segments;
}

export function selectPnlMaxAbsAmount(
  vm: DashboardPnlAttributionVM | null,
): number {
  if (!vm || vm.segments.length === 0) return 0;
  let max = 0;
  for (const segment of vm.segments) {
    const raw = segment.amount.raw;
    if (raw === null) continue;
    const abs = Math.abs(raw);
    if (abs > max) max = abs;
  }
  return max;
}
