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
        {badgeLabel ? <span className="stock-analysis-page__dh-pill">{badgeLabel}</span> : null}
      </header>

      {summary ? (
        <StrategyPanelKpiGrid
          stats={summary.stats}
          testId={summaryTestId}
          maxItems={4}
          className="stock-analysis-strategy-module-card__kpi-grid"
        />
      ) : null}

      {summary?.headline ? (
        <p className="stock-analysis-strategy-module-card__headline">{summary.headline}</p>
      ) : null}
      {summary?.detail ? (
        <p className="stock-analysis-strategy-module-card__detail-line">{summary.detail}</p>
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
              {children}
            </div>
          ) : expanded ? (
            <div
              className="stock-analysis-strategy-module-card__detail"
              data-testid={`stock-analysis-strategy-card-${id}-detail`}
            >
              {children}
            </div>
          ) : null}
        </>
      ) : null}
    </article>
  );
}
