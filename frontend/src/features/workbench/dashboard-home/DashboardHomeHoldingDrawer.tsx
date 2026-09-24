import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";

import type {
  HomeHoldingRow,
  HomeTerminalListState,
} from "./dashboardHomeBodyView";
import styles from "./dashboardHomeHoldingDrawer.module.css";

import { EM_DASH } from "../../../utils/format";
type DashboardHomeHoldingDrawerProps = {
  holdingCount: number;
  holdingsState: HomeTerminalListState;
  onClose: () => void;
  reportDate: string;
  row: HomeHoldingRow;
};

type DrawerStatus = {
  label: string;
  response: string;
};

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function buildReportDatePath(path: string, reportDate: string): string {
  const trimmed = reportDate.trim();
  return trimmed && trimmed !== EM_DASH
    ? `${path}?report_date=${encodeURIComponent(trimmed)}`
    : path;
}

function resolveDrawerStatus(state: HomeTerminalListState): DrawerStatus {
  if (state.kind === "ready") {
    return { label: state.label || "已核验", response: "200 OK" };
  }
  if (state.kind === "partial") {
    return { label: state.label || "部分可用", response: "PARTIAL" };
  }
  if (state.kind === "stale") {
    return { label: state.label || "数据偏旧", response: "STALE" };
  }
  if (state.kind === "loading") {
    return { label: state.label || "读取中", response: "PENDING" };
  }
  if (state.kind === "empty") {
    return { label: state.label || "暂无数据", response: "NO DATA" };
  }
  return {
    label: state.label || "接口不可用",
    response: "UNAVAILABLE",
  };
}

function NullSafeValue({ value }: { value: string }) {
  const isNull = value.trim() === EM_DASH;
  return (
    <b title={isNull ? "接口未返回可展示值；不替换为 0" : undefined}>
      {value}
    </b>
  );
}

export function DashboardHomeHoldingDrawer({
  holdingCount,
  holdingsState,
  onClose,
  reportDate,
  row,
}: DashboardHomeHoldingDrawerProps) {
  const titleId = useId();
  const descriptionId = useId();
  const drawerRef = useRef<HTMLElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const status = resolveDrawerStatus(holdingsState);

  useEffect(() => {
    const previouslyFocused = document.activeElement;
    closeButtonRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== "Tab" || !drawerRef.current) {
        return;
      }

      const focusable = Array.from(
        drawerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter((element) => !element.hasAttribute("disabled"));

      if (focusable.length === 0) {
        event.preventDefault();
        drawerRef.current.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (previouslyFocused instanceof HTMLElement && previouslyFocused.isConnected) {
        previouslyFocused.focus();
      }
    };
  }, [onClose]);

  if (typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div
      className={`theme-dh-api ${styles.drawerLayer}`}
      data-moss-theme-scope="dashboard-home"
      data-testid="dashboard-home-holding-drawer"
    >
      <div
        aria-hidden="true"
        className={styles.drawerScrim}
        onMouseDown={onClose}
      />
      <aside
        aria-describedby={descriptionId}
        aria-labelledby={titleId}
        aria-modal="true"
        className={styles.holdingDrawer}
        data-state={holdingsState.kind}
        data-testid="dashboard-home-holding-detail-drawer"
        ref={drawerRef}
        role="dialog"
        tabIndex={-1}
      >
        <header className={styles.drawerHeader}>
          <h2 id={titleId}>重点券详情</h2>
          <span className={styles.drawerHeaderActions}>
            <em>READ ONLY</em>
            <button
              aria-label="关闭重点券详情"
              className={styles.drawerClose}
              onClick={onClose}
            ref={closeButtonRef}
            type="button"
          >
              关闭
          </button>
          </span>
        </header>

        <p className={styles.drawerDescription} id={descriptionId}>
          来自首页重点持仓 · 数据源已落地 {holdingCount} 条
        </p>

        <section className={styles.drawerHoldingCard}>
          <div className={styles.drawerHoldingIdentity}>
            <span>
              <b>{row.code}</b>
              <small>{row.name}</small>
              <span>
                {row.assetClass} · 报告日 {reportDate}
              </span>
            </span>
            <em data-kind={holdingsState.kind}>{status.label}</em>
          </div>
        </section>

        <section className={styles.drawerSection}>
          <div className={styles.drawerSectionHead}>
            <h3>核心指标</h3>
            <span>接口原值</span>
          </div>
          <dl className={styles.drawerMetrics}>
            <div>
              <dt>市值</dt>
              <dd><NullSafeValue value={row.marketValue} /></dd>
            </div>
            <div>
              <dt>占比</dt>
              <dd><NullSafeValue value={row.weight} /></dd>
            </div>
            <div>
              <dt>YTM</dt>
              <dd><NullSafeValue value={row.ytm} /></dd>
            </div>
            <div>
              <dt>久期</dt>
              <dd><NullSafeValue value={row.duration} /></dd>
            </div>
            <div>
              <dt>评级</dt>
              <dd><NullSafeValue value={row.rating} /></dd>
            </div>
            <div>
              <dt>分类</dt>
              <dd><NullSafeValue value={row.assetClass} /></dd>
            </div>
          </dl>
        </section>

        <section className={`${styles.drawerSection} ${styles.drawerAuditSection}`}>
          <div className={styles.drawerSectionHead}>
            <h3>来源与审计</h3>
            <span>{status.response}</span>
          </div>
          <dl className={styles.drawerAuditList}>
            <div>
              <dt>数据源</dt>
              <dd>重点券持仓</dd>
            </div>
            <div>
              <dt>核算口径</dt>
              <dd>top-holdings</dd>
            </div>
            <div>
              <dt>接口状态</dt>
              <dd data-kind={holdingsState.kind}>{status.label}</dd>
            </div>
            <div>
              <dt>数据基准日</dt>
              <dd>{reportDate}</dd>
            </div>
            <div>
              <dt>落地行数</dt>
              <dd>{holdingCount > 0 ? `已落地 ${holdingCount} 条` : "暂无落地行"}</dd>
            </div>
          </dl>
        </section>

        <section className={styles.drawerApiContract}>
          <div>
            <small>GET · {status.response}</small>
            <code>/api/bond-analytics/top-holdings</code>
          </div>
          <p>mapped view fields: code · name · assetClass · marketValue · weight · ytm · duration · rating</p>
          <p>空值保持“—”，不按 0 处理；状态与报告日沿用当前页面上下文。</p>
        </section>

        <nav aria-label="重点券只读下钻" className={styles.drawerLinks}>
          <span className={styles.drawerLinksLabel}>现有只读钻取</span>
          <Link
            className={styles.drawerPrimaryLink}
            to={buildReportDatePath("/positions", reportDate)}
          >
            打开持仓明细 →
          </Link>
          <Link
            className={styles.drawerSecondaryLink}
            to={buildReportDatePath("/bond-analysis", reportDate)}
          >
            查看久期分布
          </Link>
          <Link
            className={styles.drawerSecondaryLink}
            to={buildReportDatePath("/risk-overview", reportDate)}
          >
            查看信用敞口
          </Link>
        </nav>
      </aside>
    </div>,
    document.body,
  );
}
