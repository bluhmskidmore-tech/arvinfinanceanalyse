import type { UseQueryResult } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import type { ApiEnvelope, MacroBondLinkagePayload } from "../../../api/contracts";
import { nonCancellingRefetchOptions } from "../../../app/externalDataRefreshPolicy";
import { EM_DASH } from "../../../utils/format";
import {
  LIQUIDITY_COMPOSITE_POLARITY_NOTE,
  displayLinkageWarning,
  formatRateDirectionLabel,
} from "../lib/marketDataLinkageFormat";

/** 完整联动/策略读面的承接页锚点（cross-asset 侧 id 见 CrossAssetDriversPage）。 */
export const CROSS_ASSET_LINKAGE_PATH = "/cross-asset#cross-asset-zone-linkage";

type MarketDataLinkageSummaryCardProps = {
  macroBondLinkageQuery: UseQueryResult<ApiEnvelope<MacroBondLinkagePayload>, Error>;
  macroBondLinkage: Partial<MacroBondLinkagePayload>;
  macroBondLinkageWarnings: string[];
  hasPortfolioImpact: boolean;
  /** 请求侧报告日（macro latest 派生）；载荷返回后以 result.report_date 为准。 */
  requestedReportDate: string | null;
};

function metricText(value: string | null | undefined): string {
  return value && value.trim() ? value : EM_DASH;
}

/**
 * 宏观-债市联动单行摘要卡（PAGE-MKT-001 §B：选定 report_date 下环境/组合摘要的回答处）。
 * 明细读面已由 /cross-asset 承接，本卡只渲染摘要字段，不再展开相关性矩阵。
 */
export function MarketDataLinkageSummaryCard({
  macroBondLinkageQuery,
  macroBondLinkage,
  macroBondLinkageWarnings,
  hasPortfolioImpact,
  requestedReportDate,
}: MarketDataLinkageSummaryCardProps) {
  const hasPayload = macroBondLinkageQuery.data != null;
  const reportDate = macroBondLinkage.report_date ?? requestedReportDate;
  const compositeScore = macroBondLinkage.environment_score?.composite_score;
  const compositeText =
    compositeScore != null && Number.isFinite(compositeScore)
      ? compositeScore.toFixed(2)
      : EM_DASH;
  const rateDirection = macroBondLinkage.environment_score?.rate_direction;
  const directionText = rateDirection ? formatRateDirectionLabel(rateDirection) : EM_DASH;
  const impactText = hasPayload ? (hasPortfolioImpact ? "有估算" : "无估算") : EM_DASH;

  return (
    <section
      className="market-data-summary-nav-card"
      data-testid="market-data-linkage-summary-card"
      aria-label="宏观-债市联动摘要"
    >
      <div className="market-data-summary-nav-card__row">
        <span className="market-data-summary-nav-card__title">
          宏观-债市联动
          <span className="market-data-summary-nav-card__badge">分析口径</span>
        </span>
        <span
          className="market-data-summary-nav-card__metric market-data-tabular"
          title={LIQUIDITY_COMPOSITE_POLARITY_NOTE}
        >
          环境综合分 <strong data-testid="market-data-linkage-summary-composite">{compositeText}</strong>
        </span>
        <span className="market-data-summary-nav-card__metric">
          利率方向 <strong data-testid="market-data-linkage-summary-direction">{directionText}</strong>
        </span>
        <span className="market-data-summary-nav-card__metric">
          组合影响 <strong data-testid="market-data-linkage-summary-impact">{impactText}</strong>
        </span>
        <span
          className="market-data-summary-nav-card__date market-data-tabular"
          data-testid="market-data-linkage-summary-report-date"
        >
          报告日期 {metricText(reportDate)}
        </span>
        <Link
          className="market-data-summary-nav-card__link"
          to={CROSS_ASSET_LINKAGE_PATH}
          data-testid="market-data-linkage-summary-link"
        >
          完整分析见跨资产驱动页 →
        </Link>
      </div>
      <p className="market-data-summary-nav-card__caveat" data-testid="market-data-linkage-caveat">
        分析口径（非正式口径）：环境评分与组合影响均为分析估算，不代表账本损益（PnL），也不替代正式估值归因。
        {macroBondLinkageWarnings.length > 0 ? (
          <span
            data-testid="market-data-linkage-summary-warnings"
            title={macroBondLinkageWarnings.map(displayLinkageWarning).join("\n")}
          >
            {" "}
            · 方法警示 {macroBondLinkageWarnings.length} 条
          </span>
        ) : null}
      </p>
      {macroBondLinkageQuery.isLoading ? (
        <p className="market-data-summary-nav-card__state" data-testid="market-data-linkage-summary-loading">
          联动摘要加载中…
        </p>
      ) : null}
      {macroBondLinkageQuery.isError ? (
        <p
          className="market-data-summary-nav-card__state"
          data-tone="error"
          data-testid="market-data-linkage-summary-error"
        >
          联动摘要加载失败。
          <button
            type="button"
            onClick={() => void macroBondLinkageQuery.refetch(nonCancellingRefetchOptions)}
          >
            重试
          </button>
        </p>
      ) : null}
    </section>
  );
}
