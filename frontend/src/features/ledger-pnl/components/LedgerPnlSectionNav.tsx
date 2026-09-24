import { useEffect, useState, type CSSProperties } from "react";

import "./LedgerPnlSectionNav.css";

export type LedgerPnlSectionNavTone = "neutral" | "ok" | "warning" | "danger";

export type LedgerPnlSectionNavItem = {
  /** 目标区块的 DOM id（不含 #） */
  id: string;
  /** 中文短标签，2-6 字 */
  label: string;
  /** 可选状态徽标文字，例如 "3 项待补" */
  badge?: string;
  /** 徽标语义色 */
  tone?: LedgerPnlSectionNavTone;
};

function shouldReduceMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

function focusTarget(target: HTMLElement) {
  if (!target.hasAttribute("tabindex")) {
    target.tabIndex = -1;
  }
  target.focus({ preventScroll: true });
}

export function LedgerPnlSectionNav(props: {
  items: LedgerPnlSectionNavItem[];
  /** 默认 "ledger-pnl-section-nav" */
  testId?: string;
  /** 粘顶偏移量（px），默认 0；页面外壳可能有固定头部 */
  stickyOffset?: number;
  /**
   * 导航即将滚动到目标区块前调用。
   * 用于主动唤醒被视口门控的区块（先加载内容再滚动，避免落在骨架上等待）。
   */
  onBeforeNavigate?: (id: string) => void;
}): JSX.Element | null {
  const {
    items,
    testId = "ledger-pnl-section-nav",
    stickyOffset = 0,
    onBeforeNavigate,
  } = props;
  const [availableIds, setAvailableIds] = useState<Set<string>>(() => new Set());
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    const targets = items.flatMap((item) => {
      const element = document.getElementById(item.id);
      return element instanceof HTMLElement ? [[item.id, element] as const] : [];
    });
    const nextAvailableIds = new Set(targets.map(([id]) => id));

    setAvailableIds(nextAvailableIds);
    setActiveId((current) => (current && nextAvailableIds.has(current) ? current : null));

    if (targets.length === 0 || !("IntersectionObserver" in window)) {
      return undefined;
    }

    const visibleTargets = new Map<string, HTMLElement>();
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        const target = targets.find(([, element]) => element === entry.target);
        if (!target) continue;

        if (entry.isIntersecting) visibleTargets.set(target[0], target[1]);
        else visibleTargets.delete(target[0]);
      }

      const nextActive = [...visibleTargets.entries()]
        .sort(([, first], [, second]) => first.getBoundingClientRect().top - second.getBoundingClientRect().top)
        .at(0)?.[0] ?? null;

      setActiveId(nextActive);
    }, {
      rootMargin: "-1px 0px -60% 0px",
      threshold: [0, 0.01, 1],
    });

    targets.forEach(([, element]) => observer.observe(element));
    return () => observer.disconnect();
  }, [items]);

  if (items.length === 0) return null;

  const navStyle = {
    "--ledger-pnl-section-nav-offset": `${stickyOffset}px`,
  } as CSSProperties;

  return (
    <nav
      className="ledger-pnl-section-nav"
      aria-label="页面章节导航"
      data-testid={testId}
      style={navStyle}
    >
      <div className="ledger-pnl-section-nav__items">
        {items.map((item) => {
          const isAvailable = availableIds.has(item.id);
          const isActive = activeId === item.id;

          return (
            <button
              key={item.id}
              type="button"
              className={`ledger-pnl-section-nav__item${isActive ? " ledger-pnl-section-nav__item--active" : ""}`}
              data-testid={`${testId}-item-${item.id}`}
              aria-current={isActive ? "true" : undefined}
              aria-disabled={!isAvailable}
              disabled={!isAvailable}
              onClick={() => {
                const target = document.getElementById(item.id);
                if (!(target instanceof HTMLElement)) return;

                onBeforeNavigate?.(item.id);
                target.scrollIntoView({
                  block: "start",
                  behavior: shouldReduceMotion() ? "auto" : "smooth",
                });
                focusTarget(target);
              }}
            >
              <span>{item.label}</span>
              {item.badge ? (
                <span
                  className="ledger-pnl-section-nav__badge"
                  data-tone={item.tone ?? "neutral"}
                >
                  {item.badge}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
