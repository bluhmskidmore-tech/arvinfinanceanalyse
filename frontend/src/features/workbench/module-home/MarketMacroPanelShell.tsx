import type { ComponentType, ReactNode } from "react";

import type { MarketVisualAccent } from "./marketEvidenceVisual";
import type { MarketIconProps } from "./marketHomeIcons";
import { formatPanelMetaForHome } from "./moduleHomeModel";
import marketStyles from "./marketHome.module.css";

type MarketMacroPanelShellProps = {
  title: string;
  kicker: string;
  icon: ComponentType<MarketIconProps>;
  accent?: MarketVisualAccent;
  meta?: string;
  /** Strip trade-date segments from meta (home three-column depth zone). */
  hideMetaDate?: boolean;
  statusLabel?: string;
  className?: string;
  testId?: string;
  children: ReactNode;
};

export function MarketMacroPanelShell({
  title,
  kicker,
  icon: Icon,
  accent = "navy",
  meta,
  hideMetaDate = false,
  statusLabel,
  className,
  testId,
  children,
}: MarketMacroPanelShellProps) {
  const displayMeta = hideMetaDate ? formatPanelMetaForHome(meta) : meta;

  return (
    <article
      className={`${marketStyles.marketMosaicPanel} ${marketStyles[`marketAccent_${accent}`]} ${className ?? ""} ${statusLabel ? "" : marketStyles.marketMosaicPanelNoStatus}`}
      data-testid={testId}
    >
      <header className={marketStyles.marketMosaicPanelHead}>
        <span className={marketStyles.marketIconBox}>
          <Icon className={marketStyles.marketIconGlyph} />
        </span>
        <div className={marketStyles.marketMosaicPanelCopy}>
          <span className={marketStyles.marketSummaryKicker}>{kicker}</span>
          <strong className={marketStyles.marketMosaicPanelTitle}>{title}</strong>
          {displayMeta ? <em className={marketStyles.marketMosaicPanelMeta}>{displayMeta}</em> : null}
        </div>
        {statusLabel ? <span className={marketStyles.marketStatusOutline}>{statusLabel}</span> : null}
      </header>
      <div className={marketStyles.marketMosaicPanelBody}>{children}</div>
    </article>
  );
}
