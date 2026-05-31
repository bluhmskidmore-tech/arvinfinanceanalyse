import type { ReactNode, Ref } from "react";
import { Button } from "antd";
import { DownOutlined, UpOutlined } from "@ant-design/icons";
import type { StockStrategyPanelResultSummary } from "../lib/stockAnalysisPageModel";
import { StrategyPanelKpiGrid } from "./StrategyPanelResultStrip";

export type StrategyModuleCardProps = {
  id: string;
  title: string;
  subtitle?: string;
  badgeLabel?: string;
  summary: StockStrategyPanelResultSummary | null;
  summaryTestId?: string;
  expanded: boolean;
  onToggleExpand: () => void;
  /** 为懒加载 / 测试在折叠时仍挂载明细 DOM */
  mountDetail?: boolean;
  sectionRef?: Ref<HTMLElement>;
  sectionTestId?: string;
  children?: ReactNode;
  className?: string;
};

export function StrategyModuleCard({
  id,
  title,
  subtitle,
  badgeLabel,
  summary,
  summaryTestId,
  expanded,
  onToggleExpand,
  mountDetail = false,
  sectionRef,
  sectionTestId,
  children,
  className,
}: StrategyModuleCardProps) {
  const toneClass = summary?.tone ? ` stock-analysis-strategy-module-card--${summary.tone}` : "";
  const statusPill = badgeLabel ?? summary?.badgeLabel;
  const isLoading = summary?.loading === true;
  const overflowStats = summary && summary.stats.length > 2 ? summary.stats.slice(2) : [];

  return (
    <article
      ref={sectionRef}
      className={`stock-analysis-strategy-module-card stock-analysis-page__dh-card${toneClass}${className ? ` ${className}` : ""}`}
      data-testid={sectionTestId ?? `stock-analysis-strategy-card-${id}`}
    >
      <header className="stock-analysis-strategy-module-card__header">
        <div className="stock-analysis-strategy-module-card__title-block">
          <h3 className="stock-analysis-strategy-module-card__title">{title}</h3>
          {subtitle ? <p className="stock-analysis-strategy-module-card__subtitle">{subtitle}</p> : null}
        </div>
        {statusPill ? (
          <span className="stock-analysis-strategy-module-card__status-pill">{statusPill}</span>
        ) : null}
      </header>

      {isLoading ? (
        <div
          className="stock-analysis-strategy-module-card__loading"
          data-testid={summaryTestId ? `${summaryTestId}-loading` : undefined}
        >
          <p className="stock-analysis-strategy-module-card__loading-label">加载中…</p>
          <div className="stock-analysis-strategy-module-card__loading-skeleton" aria-hidden="true">
            <span />
            <span />
          </div>
        </div>
      ) : summary ? (
        <>
          {summary.headline ? (
            <p className="stock-analysis-strategy-module-card__headline">{summary.headline}</p>
          ) : null}
          <StrategyPanelKpiGrid
            stats={summary.stats}
            testId={summaryTestId}
            maxItems={2}
            className="stock-analysis-strategy-module-card__kpi-grid"
          />
        </>
      ) : null}

      {children ? (
        <>
          <div className="stock-analysis-strategy-module-card__actions">
            <Button
              type="default"
              size="small"
              className="stock-analysis-strategy-module-card__toggle"
              data-testid={`stock-analysis-strategy-card-${id}-toggle`}
              aria-expanded={expanded}
              aria-label={expanded ? "收起明细" : "查看明细"}
              onClick={onToggleExpand}
              icon={expanded ? <UpOutlined /> : <DownOutlined />}
            >
              {expanded ? "收起明细" : "查看明细"}
            </Button>
          </div>
          {mountDetail ? (
            <div
              className={`stock-analysis-strategy-module-card__detail${expanded ? "" : " stock-analysis-strategy-module-card__detail--collapsed"}`}
              hidden={!expanded}
              data-testid={`stock-analysis-strategy-card-${id}-detail`}
            >
              {summary?.detail ? (
                <p className="stock-analysis-strategy-module-card__detail-line">{summary.detail}</p>
              ) : null}
              {overflowStats.length > 0 ? (
                <StrategyPanelKpiGrid
                  stats={overflowStats}
                  testId={summaryTestId ? `${summaryTestId}-overflow` : undefined}
                  className="stock-analysis-strategy-module-card__kpi-grid stock-analysis-strategy-module-card__kpi-grid--overflow"
                />
              ) : null}
              {children}
            </div>
          ) : expanded ? (
            <div
              className="stock-analysis-strategy-module-card__detail"
              data-testid={`stock-analysis-strategy-card-${id}-detail`}
            >
              {summary?.detail ? (
                <p className="stock-analysis-strategy-module-card__detail-line">{summary.detail}</p>
              ) : null}
              {overflowStats.length > 0 ? (
                <StrategyPanelKpiGrid
                  stats={overflowStats}
                  testId={summaryTestId ? `${summaryTestId}-overflow` : undefined}
                  className="stock-analysis-strategy-module-card__kpi-grid stock-analysis-strategy-module-card__kpi-grid--overflow"
                />
              ) : null}
              {children}
            </div>
          ) : null}
        </>
      ) : null}
    </article>
  );
}
