import { useEffect, useState } from "react";

/** 等待懒加载区块出现的上限；超时后放弃滚动而不是无限观察。 */
const SCROLL_TARGET_MOUNT_TIMEOUT_MS = 5000;

type PendingScrollTarget = { id: string; nonce: number };

function findStockSection(targetId: string): HTMLElement | null {
  return (
    document.getElementById(targetId) ??
    document.querySelector<HTMLElement>(`[data-testid="${targetId}"]`)
  );
}

/** 展开目标所在的全部 <details> 折叠层并滚动到它；目标尚未挂载时返回 false。 */
function revealStockSection(targetId: string): boolean {
  const target = findStockSection(targetId);
  if (!target) return false;
  let disclosure = target.closest("details");
  while (disclosure) {
    disclosure.open = true;
    disclosure = disclosure.parentElement?.closest("details") ?? null;
  }
  target.scrollIntoView?.({ behavior: "smooth", block: "start" });
  return true;
}

/**
 * 页内跳转到股票分析的某个区块（按 id 或 data-testid 定位）。
 * 目标不在 DOM 时先通过回调请求挂载深研区，再等 DOM 出现后滚动。
 */
export function useStockSectionScroll({
  onRequestDeepResearch,
}: {
  onRequestDeepResearch: () => void;
}) {
  const [pendingScrollTarget, setPendingScrollTarget] = useState<PendingScrollTarget | null>(null);

  // 目标区块可能在懒加载的深研区里，先请求挂载，再由 effect 在 DOM 真正出现时滚动。
  function scrollToStockSection(targetId: string) {
    if (!findStockSection(targetId)) {
      onRequestDeepResearch();
    }
    setPendingScrollTarget({ id: targetId, nonce: Date.now() });
  }

  useEffect(() => {
    if (!pendingScrollTarget) return undefined;
    const { id } = pendingScrollTarget;
    if (revealStockSection(id)) {
      setPendingScrollTarget(null);
      return undefined;
    }
    // 懒组件挂载是 Suspense 子树的独立提交，父组件 effect 不会再次触发，
    // 用 MutationObserver 监听 DOM 出现，替代定时轮询。
    const observer = new MutationObserver(() => {
      if (revealStockSection(id)) {
        observer.disconnect();
        setPendingScrollTarget(null);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    const giveUp = window.setTimeout(() => {
      observer.disconnect();
      setPendingScrollTarget(null);
    }, SCROLL_TARGET_MOUNT_TIMEOUT_MS);
    return () => {
      observer.disconnect();
      window.clearTimeout(giveUp);
    };
  }, [pendingScrollTarget]);

  return { scrollToStockSection };
}
