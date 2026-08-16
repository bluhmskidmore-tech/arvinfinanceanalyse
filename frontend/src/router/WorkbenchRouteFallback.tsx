import styles from "./WorkbenchRouteFallback.module.css";

export function WorkbenchRouteFallback() {
  return (
    <div
      className="themed-route-boundary theme-dh-api"
      data-moss-theme="dark"
      data-moss-theme-scope="route-fallback"
    >
      <div className={styles.routeFallback} role="status" aria-live="polite">
        <span className={styles.routeFallbackMark} aria-hidden="true" />
        <span>页面加载中</span>
      </div>
    </div>
  );
}
