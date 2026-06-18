import type { ReactNode } from "react";

export type MarketDataSeriesCategoryTone =
  | "stable"
  | "fallback"
  | "neutral"
  | "formal"
  | "liquidity"
  | "analytical";

type MarketDataSeriesCategoryCardProps = {
  title: string;
  caption?: string;
  count?: number;
  tone?: MarketDataSeriesCategoryTone;
  showLinkTierTag?: boolean;
  testId: string;
  id?: string;
  headerActions?: ReactNode;
  children: ReactNode;
};

const TONE_TAG: Record<MarketDataSeriesCategoryTone, string> = {
  stable: "稳定链路",
  fallback: "降级链路",
  neutral: "分析读数",
  formal: "正式口径",
  liquidity: "资金读数",
  analytical: "分析深度",
};

export function MarketDataSeriesCategoryCard({
  title,
  caption,
  count,
  tone = "neutral",
  showLinkTierTag = true,
  testId,
  id,
  headerActions,
  children,
}: MarketDataSeriesCategoryCardProps) {
  return (
    <article
      id={id}
      className={`market-data-series-category-card market-data-series-category-card--${tone}`}
      data-testid={testId}
    >
      <header className="market-data-series-category-card__head">
        <div className="market-data-series-category-card__titles">
          {showLinkTierTag ? (
            <span className="market-data-pill-tag market-data-pill-tag--info">{TONE_TAG[tone]}</span>
          ) : null}
          <h3 className="market-data-series-category-card__title">{title}</h3>
          {caption ? <p className="market-data-series-category-card__caption">{caption}</p> : null}
        </div>
        <div className="market-data-series-category-card__head-side">
          {headerActions ? (
            <div className="market-data-series-category-card__actions">{headerActions}</div>
          ) : null}
          {typeof count === "number" ? (
            <span className="market-data-series-category-card__count">{count} 条</span>
          ) : null}
        </div>
      </header>
      <div className="market-data-series-category-card__body">{children}</div>
    </article>
  );
}
