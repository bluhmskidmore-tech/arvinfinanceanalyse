import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";
import { flushSync } from "react-dom";

import {
  MACRO_TOOLKIT_DEFERRED_CONTENT_ROOT_MARGIN,
  MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE,
  governanceFocusFromEvidenceHref,
  macroToolkitDeferredContentStageForHref,
} from "../lib/macroToolkitPageModel";
import type {
  MacroToolkitDeferredContentStage,
  MacroToolkitGovernanceFocusKey,
} from "../lib/macroToolkitPageModel";

// 宏观工具页（toolkit 模式）的渐进披露状态机：从 MacroToolkitPage 纯搬移，
// 行为与文案不变。observation 模式下所有效果保持原有的 showOperations 早退。
export function useMacroToolkitDeferredContent({
  showOperations,
  selectedEvidenceHref,
  selectedExecutionHref,
  setSelectedEvidenceHref,
  setSelectedExecutionHref,
  setSelectedGovernanceFocus,
}: {
  showOperations: boolean;
  selectedEvidenceHref: string | null;
  selectedExecutionHref: string | null;
  setSelectedEvidenceHref: (href: string | null) => void;
  setSelectedExecutionHref: (href: string | null) => void;
  setSelectedGovernanceFocus: (focus: MacroToolkitGovernanceFocusKey) => void;
}) {
  const deferredContentSentinelRef = useRef<HTMLDivElement | null>(null);
  const [deferredContentStage, setDeferredContentStage] =
    useState<MacroToolkitDeferredContentStage>(() =>
      !showOperations
        ? MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE
        : typeof window !== "undefined"
          ? (macroToolkitDeferredContentStageForHref(window.location.hash) ?? 0)
          : 0,
  );
  const [pendingDeferredHashTarget, setPendingDeferredHashTarget] = useState<
    string | null
  >(() =>
    showOperations &&
    typeof window !== "undefined" &&
    macroToolkitDeferredContentStageForHref(window.location.hash) !== null
      ? window.location.hash
      : null,
  );
  const [receiptTechnicalDetailsExpanded, setReceiptTechnicalDetailsExpanded] = useState(
    () =>
      showOperations &&
      typeof window !== "undefined" &&
      window.location.hash === "#macro-toolkit-script-artifact-detail",
  );

  const revealAllDeferredContent = useCallback(() => {
    if (!showOperations) {
      return;
    }
    setDeferredContentStage(MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE);
    setReceiptTechnicalDetailsExpanded(true);
  }, [showOperations]);

  useEffect(() => {
    if (!showOperations) {
      return undefined;
    }
    const handleBeforePrint = () => {
      flushSync(revealAllDeferredContent);
    };
    window.addEventListener("beforeprint", handleBeforePrint);
    return () => window.removeEventListener("beforeprint", handleBeforePrint);
  }, [revealAllDeferredContent, showOperations]);

  useEffect(() => {
    if (
      !showOperations ||
      deferredContentStage >= MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE
    ) {
      return undefined;
    }

    const sentinel = deferredContentSentinelRef.current;
    if (typeof window.IntersectionObserver === "undefined" || !sentinel) {
      setDeferredContentStage(MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE);
      return undefined;
    }

    const nextStage = (deferredContentStage + 1) as MacroToolkitDeferredContentStage;
    const observer = new window.IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting || entry.intersectionRatio > 0)) {
          setDeferredContentStage((currentStage) =>
            Math.max(currentStage, nextStage) as MacroToolkitDeferredContentStage,
          );
          observer.disconnect();
        }
      },
      {
        rootMargin:
          deferredContentStage === MACRO_TOOLKIT_FINAL_DEFERRED_CONTENT_STAGE - 1
            ? "0px"
            : MACRO_TOOLKIT_DEFERRED_CONTENT_ROOT_MARGIN,
        threshold: 0.01,
      },
    );
    observer.observe(sentinel);

    return () => observer.disconnect();
  }, [deferredContentStage, showOperations]);

  const revealDeferredContentForHref = useCallback(
    (href: string | null) => {
      if (!showOperations || !href) {
        return;
      }
      const requestedStage = macroToolkitDeferredContentStageForHref(href);
      if (requestedStage === null) {
        return;
      }
      if (href === "#macro-toolkit-script-artifact-detail") {
        setReceiptTechnicalDetailsExpanded(true);
      }
      setDeferredContentStage((currentStage) =>
        Math.max(currentStage, requestedStage) as MacroToolkitDeferredContentStage,
      );
    },
    [showOperations],
  );

  const syncDeferredContentSelectionForHref = useCallback((href: string) => {
    if (macroToolkitDeferredContentStageForHref(href) === null) {
      return;
    }
    if (
      href === "#macro-toolkit-operations-actions" ||
      href === "#macro-toolkit-operations-console"
    ) {
      setSelectedExecutionHref(href);
    } else {
      setSelectedEvidenceHref(href);
    }
    setSelectedGovernanceFocus(governanceFocusFromEvidenceHref(href));
  }, [setSelectedEvidenceHref, setSelectedExecutionHref, setSelectedGovernanceFocus]);

  useEffect(() => {
    revealDeferredContentForHref(selectedExecutionHref);
    revealDeferredContentForHref(selectedEvidenceHref);
  }, [
    revealDeferredContentForHref,
    selectedEvidenceHref,
    selectedExecutionHref,
  ]);

  useEffect(() => {
    if (!showOperations) {
      return undefined;
    }
    const revealHashTarget = () => {
      const href = window.location.hash;
      setPendingDeferredHashTarget(
        macroToolkitDeferredContentStageForHref(href) !== null ? href : null,
      );
      syncDeferredContentSelectionForHref(href);
      revealDeferredContentForHref(href);
    };
    revealHashTarget();
    window.addEventListener("hashchange", revealHashTarget);
    return () => window.removeEventListener("hashchange", revealHashTarget);
  }, [
    revealDeferredContentForHref,
    showOperations,
    syncDeferredContentSelectionForHref,
  ]);

  useEffect(() => {
    if (
      !showOperations ||
      !pendingDeferredHashTarget?.startsWith("#macro-toolkit-")
    ) {
      return undefined;
    }
    const requestedStage = macroToolkitDeferredContentStageForHref(
      pendingDeferredHashTarget,
    );
    if (
      requestedStage === null ||
      deferredContentStage < requestedStage ||
      (pendingDeferredHashTarget === "#macro-toolkit-script-artifact-detail" &&
        !receiptTechnicalDetailsExpanded)
    ) {
      return undefined;
    }

    let frame: number | null = null;
    const scrollToHashTarget = () => {
      const target = document.getElementById(pendingDeferredHashTarget.slice(1));
      if (typeof target?.scrollIntoView !== "function") {
        return false;
      }
      target.scrollIntoView({ block: "start", inline: "nearest" });
      setPendingDeferredHashTarget((currentTarget) =>
        currentTarget === pendingDeferredHashTarget ? null : currentTarget,
      );
      return true;
    };
    const scheduleScroll = () => {
      if (typeof window.requestAnimationFrame === "function") {
        frame = window.requestAnimationFrame(() => {
          scrollToHashTarget();
        });
        return;
      }
      scrollToHashTarget();
    };
    if (document.getElementById(pendingDeferredHashTarget.slice(1))) {
      scheduleScroll();
      return () => {
        if (frame !== null) {
          window.cancelAnimationFrame(frame);
        }
      };
    }
    if (typeof window.MutationObserver === "undefined") {
      scheduleScroll();
      return undefined;
    }
    const observer = new window.MutationObserver(() => {
      if (!document.getElementById(pendingDeferredHashTarget.slice(1))) {
        return;
      }
      observer.disconnect();
      scheduleScroll();
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      if (frame !== null) {
        window.cancelAnimationFrame(frame);
      }
    };
  }, [
    deferredContentStage,
    pendingDeferredHashTarget,
    receiptTechnicalDetailsExpanded,
    showOperations,
  ]);

  const handleDeferredContentLinkClick = useCallback(
    (event: ReactMouseEvent<HTMLElement>) => {
      if (!showOperations) {
        return;
      }
      const target = event.target;
      const anchor =
        target instanceof Element
          ? target.closest<HTMLAnchorElement>('a[href^="#macro-toolkit-"]')
          : null;
      if (anchor) {
        const href = anchor.getAttribute("href");
        if (!href || macroToolkitDeferredContentStageForHref(href) === null) {
          return;
        }
        setPendingDeferredHashTarget(href);
        syncDeferredContentSelectionForHref(href);
        revealDeferredContentForHref(href);
      }
    },
    [
      revealDeferredContentForHref,
      showOperations,
      syncDeferredContentSelectionForHref,
    ],
  );

  useEffect(() => {
    if (selectedEvidenceHref === "#macro-toolkit-script-artifact-detail") {
      setReceiptTechnicalDetailsExpanded(true);
    }
  }, [selectedEvidenceHref]);

  return {
    deferredContentSentinelRef,
    deferredContentStage,
    handleDeferredContentLinkClick,
    receiptTechnicalDetailsExpanded,
    revealAllDeferredContent,
    setReceiptTechnicalDetailsExpanded,
  };
}

export type MacroToolkitDeferredContentModel = ReturnType<
  typeof useMacroToolkitDeferredContent
>;
