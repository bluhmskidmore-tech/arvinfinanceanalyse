import shellStyles from "./dashboardHomeShell.module.css";
import homeStyles from "./dashboardHome.module.css";

export type DeferredSkeletonVariant = "context-panel" | "work-grid";

type DeferredSkeletonProps = {
  variant: DeferredSkeletonVariant;
};

const CONTEXT_PANEL_WIDE_BARS = 4;
const CONTEXT_PANEL_NARROW_BARS = 3;
const WORK_GRID_TABLE_ROWS = 6;
const WORK_GRID_SIDE_PANEL_A_BARS = 3;
const WORK_GRID_SIDE_PANEL_B_BARS = 2;

function ContextPanelSkeleton() {
  return (
    <div aria-hidden="true" className={shellStyles.dhTerminalDeferredPlaceholder}>
      <div className={shellStyles.dhSkeletonColumn}>
        {Array.from({ length: CONTEXT_PANEL_WIDE_BARS }).map((_, index) => (
          <span key={index} className={shellStyles.dhSkeletonBar} />
        ))}
      </div>
      <div className={`${shellStyles.dhSkeletonColumn} ${shellStyles.dhSkeletonColumnNarrow}`}>
        {Array.from({ length: CONTEXT_PANEL_NARROW_BARS }).map((_, index) => (
          <span key={index} className={shellStyles.dhSkeletonBar} />
        ))}
      </div>
    </div>
  );
}

function WorkGridSkeleton() {
  return (
    <div aria-hidden="true" className={homeStyles.dhTerminalDeferredPlaceholder}>
      <div className={homeStyles.dhSkeletonTable}>
        {Array.from({ length: WORK_GRID_TABLE_ROWS }).map((_, index) => (
          <div key={index} className={homeStyles.dhSkeletonTableRow}>
            <span className={homeStyles.dhSkeletonBar} />
            <span className={homeStyles.dhSkeletonBarShort} />
          </div>
        ))}
      </div>
      <div className={homeStyles.dhSkeletonSideGrid}>
        <div className={homeStyles.dhSkeletonSidePanel}>
          {Array.from({ length: WORK_GRID_SIDE_PANEL_A_BARS }).map((_, index) => (
            <span key={index} className={homeStyles.dhSkeletonBar} />
          ))}
        </div>
        <div className={homeStyles.dhSkeletonSidePanel}>
          {Array.from({ length: WORK_GRID_SIDE_PANEL_B_BARS }).map((_, index) => (
            <span key={index} className={homeStyles.dhSkeletonBar} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function DeferredSkeleton({ variant }: DeferredSkeletonProps) {
  return variant === "work-grid" ? <WorkGridSkeleton /> : <ContextPanelSkeleton />;
}
