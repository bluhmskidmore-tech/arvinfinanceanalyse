import type { ReactNode } from "react";
import type {
  StockThemeBreakoutCard,
  StockThemeBreakoutReviewItem,
  StockThemeEvidenceStateRow,
} from "../lib/stockAnalysisPageModel";

type StockAnalysisThemeBreakoutPanelProps = {
  cards: StockThemeBreakoutCard[];
  evidenceRows: StockThemeEvidenceStateRow[];
  reviewItems: StockThemeBreakoutReviewItem[];
  emptyMessage: string;
};

function ThemePill({ children, tone = "neutral", className = "" }: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger";
  className?: string;
}) {
  const toneClass =
    tone === "success"
      ? "bg-success/10 text-success border-success/20"
      : tone === "warning"
        ? "bg-warning/10 text-warning border-warning/20"
        : tone === "danger"
          ? "bg-danger/10 text-danger border-danger/20"
          : "bg-default-100 text-default-700 border-default-200";
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold ${toneClass} ${className}`}>
      {children}
    </span>
  );
}

export function StockAnalysisThemeBreakoutPanel({
  cards,
  evidenceRows,
  reviewItems,
  emptyMessage,
}: StockAnalysisThemeBreakoutPanelProps) {
  const evidenceLimited = evidenceRows.some((row) => row.status === "current_overlay");
  return (
    <div className="flex flex-col gap-6">
      {cards.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="stock-analysis-theme-breakout-cards">
          {cards.map((card) => (
            <ThemeBreakoutCard card={card} key={card.themeKey} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-default-500 italic">{emptyMessage}</p>
      )}

      {evidenceRows.length > 0 && (
        <div data-testid="stock-analysis-theme-evidence-state" className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <strong className="text-sm">{evidenceLimited ? "题材证据受限" : "题材证据就绪"}</strong>
            <ThemePill tone={evidenceLimited ? "warning" : "neutral"}>{evidenceRows.length} 项证据</ThemePill>
          </div>
          <div className="bg-background/40 border border-default-100 shadow-sm rounded-lg overflow-hidden">
            <ul className="flex flex-col divide-y divide-default-100">
              {evidenceRows.map((row) => (
                <li key={row.key} className="p-3 flex justify-between items-center hover:bg-default-50/50 transition-colors">
                  <div className="flex flex-col">
                    <strong className="text-sm">{row.label}</strong>
                    <span className="text-xs text-default-500">
                      {row.statusLabel} / {row.rowCountLabel}
                    </span>
                  </div>
                  <span className="text-xs text-default-600">{row.detail}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {reviewItems.length > 0 && (
        <div data-testid="stock-analysis-theme-review-items" className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <strong className="text-sm text-warning">题材未入选复核</strong>
            <ThemePill tone="warning">待排查 {reviewItems.length} 项</ThemePill>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {reviewItems.map((item) => (
              <ThemeReviewItem item={item} key={item.themeKey} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ThemeBreakoutCard({ card }: { card: StockThemeBreakoutCard }) {
  return (
    <article className="bg-background/60 border border-default-200 rounded-lg overflow-hidden">
      <header className="flex flex-row justify-between items-start p-4 pb-2">
        <div className="flex flex-col gap-1">
          <h3 className="text-md font-bold">
            <span className="text-primary mr-1">#{card.rank}</span>
            {card.themeName}
          </h3>
          <p className="text-xs text-default-500">{card.parentSectorLabel}</p>
          {card.summary && (
            <ThemePill className="mt-1">{card.summary}</ThemePill>
          )}
        </div>
        <ThemePill tone={card.sourceKindLabel === "时点概念成分" ? "success" : "warning"}>
          {card.sourceKindLabel ?? "观察"}
        </ThemePill>
      </header>
      <hr className="border-t border-default-200" />
      <div className="p-4 pt-3 flex flex-col gap-3">
        <div className="flex flex-wrap gap-2 text-xs text-default-600">
          <span className="bg-default-100 px-2 py-1 rounded">{card.strongCountLabel}</span>
          <span className="bg-default-100 px-2 py-1 rounded">{card.limitCountLabel}</span>
          <span className="bg-default-100 px-2 py-1 rounded">{card.advanceRatioLabel}</span>
          <span className="bg-default-100 px-2 py-1 rounded">{card.avgPctChangeLabel}</span>
          <span className="bg-default-100 px-2 py-1 rounded">{card.movementLabel}</span>
        </div>

        <div className="flex flex-col gap-1 text-sm text-default-700">
          <p>{card.reason}</p>
          <p>{card.latestEventLabel}</p>
          <p className="text-xs text-warning">{card.boundaryLabel}</p>
        </div>

        <ThemeLeaderList leaders={card.leaders} fallbackTag="观察" />
      </div>
    </article>
  );
}

function ThemeReviewItem({ item }: { item: StockThemeBreakoutReviewItem }) {
  return (
    <article className="bg-default-50 border border-default-200 rounded-lg overflow-hidden">
      <header className="flex flex-row justify-between items-start p-4 pb-2">
        <div className="flex flex-col gap-1">
          <h3 className="text-md font-bold text-default-700">
            复核 #{item.rank} {item.themeName}
          </h3>
          <p className="text-xs text-default-500">{item.parentSectorLabel}</p>
          {item.summary && (
            <ThemePill tone="warning" className="mt-1">{item.summary}</ThemePill>
          )}
        </div>
        <ThemePill tone="warning">{item.sourceKindLabel}</ThemePill>
      </header>
      <hr className="border-t border-default-200" />
      <div className="p-4 pt-3 flex flex-col gap-3">
        <div className="text-xs font-medium text-danger bg-danger/10 px-2 py-1 rounded w-fit">
          {item.failedGateLabel}
        </div>

        <p className="text-sm text-default-700">{item.reason}</p>

        {item.leaders.length > 0 && (
          <ThemeLeaderList leaders={item.leaders} fallbackTag="复核" />
        )}
      </div>
    </article>
  );
}

function ThemeLeaderList({
  leaders,
  fallbackTag,
}: {
  leaders: StockThemeBreakoutCard["leaders"];
  fallbackTag: string;
}) {
  return (
    <div className="mt-2 flex flex-col gap-2">
      {leaders.map((leader) => (
        <div key={leader.stockCode} className="flex justify-between items-center p-2 rounded-lg bg-default-100/50">
          <div className="flex flex-col">
            <strong className="text-sm">{leader.stockName}</strong>
          <span className="text-[10px] text-default-500">
            {leader.stockCode} / {leader.pctChange} / 换手 {leader.turn} / 收盘强度 {leader.closeStrength}
          </span>
          {leader.sourceKindLabel ? (
            <span className="text-[10px] text-default-500">{leader.sourceKindLabel}</span>
          ) : null}
        </div>
          <ThemePill>{leader.tags.join(" / ") || fallbackTag}</ThemePill>
        </div>
      ))}
    </div>
  );
}
