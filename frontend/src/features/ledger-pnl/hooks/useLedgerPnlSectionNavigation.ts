import { useEffect, useMemo, useState } from "react";
import type { LedgerPnlSectionNavItem } from "../components/LedgerPnlSectionNav";
import { LEDGER_PNL_SECTION_IDS } from "../models/ledgerPnlPageConstants";

type DeferredSectionNavigation = { seen: boolean; markSeen: () => void };

/** 唤醒导航目标上方的门控内容，并在查询与布局提交后校准仍持焦点的锚点。 */
export function useLedgerPnlSectionNavigation({
  indicatorsSection,
  candidateSection,
  reconciliationSection,
  ledgerPnlFetchingCount,
}: {
  indicatorsSection: DeferredSectionNavigation;
  candidateSection: DeferredSectionNavigation;
  reconciliationSection: DeferredSectionNavigation;
  ledgerPnlFetchingCount: number;
}) {
  const [pendingSectionNavigation, setPendingSectionNavigation] = useState<string | null>(null);
  const sectionNavItems = useMemo<LedgerPnlSectionNavItem[]>(
    () => [
      { id: LEDGER_PNL_SECTION_IDS.verdict, label: "当日结论" },
      { id: LEDGER_PNL_SECTION_IDS.summary, label: "账面总览" },
      { id: LEDGER_PNL_SECTION_IDS.analysis, label: "损益分析" },
      { id: LEDGER_PNL_SECTION_IDS.indicators, label: "经营指标" },
      { id: LEDGER_PNL_SECTION_IDS.candidate, label: "候选指标" },
      { id: LEDGER_PNL_SECTION_IDS.reconciliation, label: "对账与日均" },
      { id: LEDGER_PNL_SECTION_IDS.accounts, label: "科目汇总" },
      { id: LEDGER_PNL_SECTION_IDS.detail, label: "科目明细" },
      { id: LEDGER_PNL_SECTION_IDS.evidence, label: "证据与元信息" },
    ],
    [],
  );

  /**
   * 章节导航直达前，唤醒目标及其上方全部门控区块：
   * 只唤醒目标会让滚动途中的骨架在 IO 触发后才加载，
   * 上方内容高度随后变化，目标锚点被推移（锚点漂移）。
   */
  const wakeSectionsForNavigate = (targetId: string) => {
    const gatedSections = [
      {
        id: LEDGER_PNL_SECTION_IDS.indicators,
        seen: indicatorsSection.seen,
        markSeen: indicatorsSection.markSeen,
      },
      {
        id: LEDGER_PNL_SECTION_IDS.candidate,
        seen: candidateSection.seen,
        markSeen: candidateSection.markSeen,
      },
      {
        id: LEDGER_PNL_SECTION_IDS.reconciliation,
        seen: reconciliationSection.seen,
        markSeen: reconciliationSection.markSeen,
      },
    ];
    const navOrder = sectionNavItems.map((item) => item.id);
    const targetIndex = navOrder.indexOf(targetId);
    if (targetIndex < 0) {
      return;
    }
    let wakesDeferredContent = false;
    for (const gated of gatedSections) {
      const gatedIndex = navOrder.indexOf(gated.id);
      if (gatedIndex >= 0 && gatedIndex <= targetIndex) {
        wakesDeferredContent ||= !gated.seen;
        gated.markSeen();
      }
    }
    if (wakesDeferredContent) {
      setPendingSectionNavigation(targetId);
    }
  };

  /*
   * 章节导航会先滚到仍是骨架高度的目标。门控查询完成后，上方区块可能长数千像素，
   * 因此在本页相关请求归零且最终布局提交后，再把仍持有焦点的目标校准回视口顶部。
   * 若用户已把焦点移到别处，则视为主动接管滚动，不再把页面拉回旧目标。
   */
  useEffect(() => {
    if (!pendingSectionNavigation) {
      return undefined;
    }

    const target = document.getElementById(pendingSectionNavigation);
    const pageRoot = target?.closest(".ledger-pnl-page");
    const ResizeObserverImpl = globalThis.ResizeObserver;
    if (
      !(target instanceof HTMLElement) ||
      !(pageRoot instanceof HTMLElement) ||
      !ResizeObserverImpl
    ) {
      return undefined;
    }

    let alignmentFrame = 0;
    const observer = new ResizeObserverImpl(() => {
      window.cancelAnimationFrame(alignmentFrame);
      alignmentFrame = window.requestAnimationFrame(() => {
        if (document.activeElement === target) {
          target.scrollIntoView({ block: "start", behavior: "auto" });
        }
      });
    });
    observer.observe(pageRoot);

    return () => {
      observer.disconnect();
      window.cancelAnimationFrame(alignmentFrame);
    };
  }, [pendingSectionNavigation]);

  useEffect(() => {
    if (!pendingSectionNavigation || ledgerPnlFetchingCount > 0) {
      return undefined;
    }

    let secondFrame = 0;
    const firstFrame = window.requestAnimationFrame(() => {
      secondFrame = window.requestAnimationFrame(() => {
        const target = document.getElementById(pendingSectionNavigation);
        if (target instanceof HTMLElement && document.activeElement === target) {
          target.scrollIntoView({ block: "start", behavior: "auto" });
        }
        setPendingSectionNavigation((current) =>
          current === pendingSectionNavigation ? null : current,
        );
      });
    });

    return () => {
      window.cancelAnimationFrame(firstFrame);
      if (secondFrame) {
        window.cancelAnimationFrame(secondFrame);
      }
    };
  }, [ledgerPnlFetchingCount, pendingSectionNavigation]);

  return { sectionNavItems, wakeSectionsForNavigate };
}
