import { useCallback, useMemo, useState, type CSSProperties, type ReactNode } from "react";

import styles from "./StateSurface.module.css";
import {
  STATE_SURFACE_DEDUPE_LIMIT,
  StateSurfaceQuotaContext,
  useDedupeRegistration,
  type StateSurfaceQuotaContextValue,
} from "./stateSurfaceQuota";
import { SURFACE_STATUS_LABEL } from "./statusBridge";

/**
 * Rendering layer for a single data block's own five-state evidence (DESIGN.md
 * §6 "状态即内容"). This is deliberately narrower than `pageModel`'s
 * `StateSurfaceItem` / `buildStateSurfaces`: those describe a *page-wide list*
 * of evidence banners (mock/fallback/stale/definition-pending) rendered
 * through the existing `PageStateSurface` (see
 * `src/components/page/PagePrimitives.tsx`); this component instead answers
 * "is *this* card/grid-cell's own content ready right now", with two
 * mechanical guarantees neither `PageStateSurface` nor
 * `PageAsyncSection`/`PageDataSection` currently provide:
 *  - a loading skeleton with a real backdrop and a real min-height (§11.10
 *    anti-reflow), as opposed to `SkeletonBarStack`'s unbounded-height bars;
 *  - an opposite, *shrinking* empty box (§5 "空态收缩"), plus a cross-page
 *    dedupe quota for repeated status facts (§6 "状态信息去重").
 * See the component-level report for the full boundary write-up.
 */
export type SurfaceStatus = "ready" | "loading" | "empty" | "error" | "stale" | "partial";

/**
 * Density for the childless `error`/`stale`/`partial` standalone case only.
 *
 * - `"roomy"` (default): reuses the same anti-reflow backdrop as `loading`
 *   (`.backdropBox` + `minHeight`) with the compact 120px default.
 *   Explicit loading minHeight still preserves the caller's anti-reflow floor.
 * - `"compact"`: renders just the inline status line at its own content
 *   height, with no forced floor. For a one-line page notice or a slim risk
 *   panel, the 120px backdrop reads as an oversized empty box; `"compact"`
 *   fixes that without touching `loading`'s or `empty`'s box.
 *
 * Deliberately orthogonal to `loading` (always the backdrop, §11.10) and to
 * `empty` (always `.shrinkBox`, §5) — those two are opposite guarantees, so
 * this density only ever applies to the third, unrelated case: `error` /
 * `stale` / `partial` *without* `children`. It is a no-op for every other
 * combination (`ready`, `loading`, `empty`, or any status *with* `children`).
 */
export type StateSurfaceDensity = "roomy" | "compact";

export type StateSurfaceProps = {
  status: SurfaceStatus;
  /** Overrides the default per-status headline. */
  message?: string;
  /** Secondary cause line (why it's empty/error/stale/partial). */
  reason?: string;
  /**
   * Anti-reflow floor for `loading` (and for `error`/`stale`/`partial` when
   * rendered without `children`, unless `density="compact"` — see below).
   * `"match"` asks the surface to fill its layout context
   * (`min-height: max(120px, 100%)`) — this only stretches to match a sibling
   * panel when an ancestor actually provides a height (e.g. a `SectionGrid`
   * with `align="stretch"`); otherwise it falls back to the same 120px floor
   * as a plain number. Despite the name, `"match"` is not guaranteed to match
   * anything — it is a best-effort stretch, still floored at 120px. `empty`
   * always ignores this prop — see the "撑满防重排 vs 收缩" note below.
   */
  minHeight?: number | "match";
  /**
   * Standalone-box density for childless `error`/`stale`/`partial` (see
   * `StateSurfaceDensity`). Defaults to `"roomy"` with the standard 120px floor.
   * Ignored for `ready`/`loading`/`empty` and for any status rendered with
   * `children`.
   */
  density?: StateSurfaceDensity;
  /** Registers this instance with `StateSurfaceQuotaProvider` for §6 dedupe. */
  dedupeKey?: string;
  /** Rendered only when `status` is `"ready"`, or alongside a status line for `"stale"`/`"partial"`/`"error"`. */
  children?: ReactNode;
  /**
   * The way *out* of a contentless state — a retry button, a "widen the filter"
   * hint. Rendered for `empty`, and for the childless standalone box of
   * `error`/`stale`/`partial`; never for `loading` (nothing to act on while a
   * request is in flight) or `ready` (the content is there).
   *
   * Deliberately not `children`: in this component `children` always means *the
   * data*, which is why `empty` drops them. Folding actions into `children`
   * would make the same slot mean two different things depending on `status`.
   * Without this slot a page needing a retry has to hand-roll the whole empty
   * box, and its empty state then drifts from every other page's.
   */
  actions?: ReactNode;
  testId?: string;
};

const DEFAULT_MIN_HEIGHT_PX = 120;

type MinHeightStyle = CSSProperties & { "--ss-min-height"?: string };

function minHeightStyle(minHeight: number | "match" | undefined): MinHeightStyle {
  if (minHeight === "match") {
    return { "--ss-min-height": `max(${DEFAULT_MIN_HEIGHT_PX}px, 100%)` };
  }
  const px = typeof minHeight === "number" && minHeight > 0 ? minHeight : DEFAULT_MIN_HEIGHT_PX;
  return { "--ss-min-height": `${px}px` };
}

function StatusDot({ status }: { status: SurfaceStatus }) {
  return (
    <span className={styles.dot} data-status={status} data-role="status-dot" aria-hidden="true" />
  );
}

// ---------------------------------------------------------------------------
// Dedupe quota (DESIGN.md §6: 同一事实全页最多出现两处)
// ---------------------------------------------------------------------------

type StateSurfaceQuotaCounts = Record<string, number>;

/**
 * Collects `dedupeKey` registrations from every mounted `StateSurface` on the
 * page. Optional: a `StateSurface` without a wrapping provider still renders
 * normally and simply skips dedupe bookkeeping (fail-open, per §6 "不能静默
 * 吞态" — the content itself is never gated by this mechanism).
 */
export function StateSurfaceQuotaProvider({ children }: { children: ReactNode }) {
  const [counts, setCounts] = useState<StateSurfaceQuotaCounts>({});

  const register = useCallback((key: string) => {
    setCounts((prev) => {
      const next = { ...prev, [key]: (prev[key] ?? 0) + 1 };
      if (import.meta.env.DEV && next[key] > STATE_SURFACE_DEDUPE_LIMIT) {
        console.warn(
          `[StateSurface] dedupeKey "${key}" 在当前页面同时出现第 ${next[key]} 次，` +
            `超过 DESIGN.md §6 规定的全页配额上限 ${STATE_SURFACE_DEDUPE_LIMIT} 处。` +
            "生产环境不受影响，仅开发环境提示；请收敛为区块头部/汇总处的单一事实来源。",
        );
      }
      return next;
    });
  }, []);

  const unregister = useCallback((key: string) => {
    setCounts((prev) => {
      if (!(key in prev)) return prev;
      const remaining = (prev[key] ?? 0) - 1;
      const next = { ...prev };
      if (remaining <= 0) {
        delete next[key];
      } else {
        next[key] = remaining;
      }
      return next;
    });
  }, []);

  const value = useMemo<StateSurfaceQuotaContextValue>(
    () => ({ counts, register, unregister }),
    [counts, register, unregister],
  );

  return (
    <StateSurfaceQuotaContext.Provider value={value}>{children}</StateSurfaceQuotaContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StateSurface({
  status,
  message,
  reason,
  minHeight,
  density = "roomy",
  dedupeKey,
  children,
  actions,
  testId,
}: StateSurfaceProps) {
  useDedupeRegistration(dedupeKey);

  const resolvedMessage = message ?? SURFACE_STATUS_LABEL[status];
  const hasChildren = children !== undefined && children !== null && children !== false;

  if (status === "ready") {
    return (
      <div className={styles.ready} data-testid={testId} data-status={status}>
        {children}
      </div>
    );
  }

  if (status === "loading") {
    return (
      <div
        className={styles.backdropBox}
        style={minHeightStyle(minHeight)}
        data-testid={testId}
        data-status={status}
        role="status"
        aria-live="polite"
      >
        <div className={styles.backdropHead}>
          <StatusDot status={status} />
          <span className={styles.backdropLabel} data-status={status}>
            {resolvedMessage}
          </span>
        </div>
        <div className={styles.skeletonBlock} aria-hidden="true">
          <span className={styles.skeletonLine} data-width="wide" />
          <span className={styles.skeletonLine} data-width="full" />
          <span className={styles.skeletonLine} data-width="short" />
        </div>
      </div>
    );
  }

  if (status === "empty") {
    // §5 空态收缩: a small, self-sized message box — never the loading
    // anti-reflow min-height. `minHeight` is intentionally not consumed here.
    //
    // `children` stay unrendered here on purpose (see the prop's doc): in this
    // component `children` always means *the data*, and an empty state has
    // none. The way out of the empty state goes in `actions` instead.
    const emptyStatusContent = (
      <>
        <StatusDot status={status} />
        <p className={styles.emptyMessage}>
          {resolvedMessage}
          {reason ? <span className={styles.emptyReason}>{reason}</span> : null}
        </p>
      </>
    );

    if (actions) {
      return (
        <div
          className={`${styles.shrinkBox} ${styles.shrinkBoxWithActions}`}
          data-testid={testId}
          data-status={status}
        >
          <div className={styles.emptyStatusRegion} role="status">
            {emptyStatusContent}
          </div>
          <div className={styles.emptyActions}>{actions}</div>
        </div>
      );
    }

    return (
      <div className={styles.shrinkBox} data-testid={testId} data-status={status} role="status">
        {emptyStatusContent}
      </div>
    );
  }

  // error / stale / partial: an inline status line, never a mask — content
  // already on screen (children) keeps rendering alongside it (§6 "不能静默
  // 吞态"). Only when there is no content yet does the surface by default take
  // on the same anti-reflow min-height as `loading` ("roomy", see below),
  // because it is then the only thing occupying that space.
  const statusRole = status === "error" ? "alert" : "status";
  const renderStatusMessage = () => (
    <>
      <StatusDot status={status} />
      <span className={styles.statusText}>
        {resolvedMessage}
        {reason ? <span className={styles.statusReason}>{reason}</span> : null}
      </span>
    </>
  );
  const renderStatusLine = (lineTestId?: string) => (
    <div
      className={styles.statusLine}
      data-testid={lineTestId}
      data-status={status}
      role={statusRole}
    >
      {renderStatusMessage()}
    </div>
  );

  if (hasChildren) {
    return (
      <div className={styles.wrap} data-testid={testId} data-status={status}>
        {renderStatusLine()}
        <div className={styles.content}>{children}</div>
      </div>
    );
  }

  // Childless standalone case: "roomy" (default) keeps a
  // 120px-floor backdrop; "compact" renders just the status line
  // at its own content height for slim blocks (a one-line page notice, a
  // risk-indicator panel) where the 120px floor reads as oversized. Neither
  // branch touches `loading`'s backdrop or `empty`'s shrink box above.
  if (density === "compact") {
    if (!actions) return renderStatusLine(testId);
    return (
      <div
        className={`${styles.statusLine} ${styles.compactActionsSurface}`}
        data-testid={testId}
        data-status={status}
      >
        <div className={styles.compactStatusRegion} role={statusRole}>
          {renderStatusMessage()}
        </div>
        <div className={styles.emptyActions}>{actions}</div>
      </div>
    );
  }

  return (
    <div
      className={styles.backdropBox}
      style={minHeightStyle(minHeight)}
      data-testid={testId}
      data-status={status}
    >
      {renderStatusLine()}
      {actions ? <div className={styles.emptyActions}>{actions}</div> : null}
    </div>
  );
}
