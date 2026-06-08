import {
  BarChartOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  LineChartOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import { Button, Collapse } from "antd";

import type { StockCandidateReviewQueueItem } from "../lib/stockAnalysisPageModel";
import { compactStockText } from "../lib/stockAnalysisPageCopy";
import { StatusIcon } from "./StockAnalysisStatusPrimitives";

export function StockAnalysisReviewCandidateCard({
  card,
  selectedSectorCode,
  onReviewChart,
}: {
  card: StockCandidateReviewQueueItem;
  selectedSectorCode: string | null;
  onReviewChart: (card: StockCandidateReviewQueueItem) => void;
}) {
  const visibleEvidence = [...card.primaryEvidence, ...card.supportingEvidence].slice(0, 4);
  const hiddenEvidenceCount =
    card.primaryEvidence.length + card.supportingEvidence.length - visibleEvidence.length;

  return (
    <article
      className="stock-analysis-page__review-candidate-card grid gap-2 rounded-md border border-neutral-200 bg-white px-3 py-2.5 transition-shadow hover:border-primary-200 hover:shadow-[0_0_0_1px_theme(colors.primary.200)]"
      data-testid={`stock-candidate-${card.stockCode}`}
      data-selected-sector={
        selectedSectorCode != null && card.sectorCode === selectedSectorCode ? "true" : undefined
      }
    >
      <div className="stock-analysis-page__review-row-head">
        <strong className="stock-analysis-page__review-row-rank stock-analysis-page__tabular">#{card.rank}</strong>
        <div className="min-w-0">
          <h3 className="m-0 text-sm font-semibold text-neutral-900">{card.headline}</h3>
          <p className="mt-0.5 text-[11px] text-neutral-500">
            {card.stockName} · {card.stockCode} · {card.sectorName}
          </p>
        </div>
        <div className="stock-analysis-page__review-row-metrics">
          <span title={card.patternNote}>距 {card.distanceToBreakoutPct}</span>
          <span>{card.primaryEvidence.length + card.supportingEvidence.length} 证据</span>
          <Button
            type="default"
            size="small"
            icon={<LineChartOutlined />}
            data-testid={`stock-candidate-review-chart-${card.stockCode}`}
            onClick={() => onReviewChart(card)}
          >
            <span className="sr-only">复核 </span>K 线
          </Button>
          <span className="rounded-full border border-primary-200 bg-primary-50 px-2 py-0.5 text-xs font-semibold text-primary-700">
            观察
          </span>
        </div>
      </div>
      <p className="m-0 border-l-2 border-primary-500 pl-2 text-xs font-semibold leading-relaxed text-neutral-900">
        {card.reviewFocus}
      </p>
      <div className="stock-analysis-page__review-candidate-evidence grid gap-1.5 sm:grid-cols-2">
        {visibleEvidence.map((item, index) => (
          <div
            className="flex min-w-0 items-center gap-2 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1.5"
            key={item.key}
            title={`${item.label}: ${item.value}`}
          >
            <StatusIcon tone={index < card.primaryEvidence.length ? "positive" : "neutral"}>
              {index < card.primaryEvidence.length ? <CheckCircleOutlined /> : <DatabaseOutlined />}
            </StatusIcon>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[10px] font-medium text-neutral-500">{item.label}</span>
              <strong className="block truncate text-xs font-semibold text-neutral-900">{item.value}</strong>
            </span>
          </div>
        ))}
      </div>
      <div className="stock-analysis-page__review-candidate-chips flex flex-wrap gap-1 text-xs">
        <span className="inline-flex items-center gap-1 rounded-full border border-neutral-200 bg-white px-2 py-0.5 font-semibold text-neutral-600">
          <SafetyCertificateOutlined aria-hidden="true" /> 边界 {card.boundaryEvidence.length}
        </span>
        <span
          className="inline-flex min-w-0 max-w-full items-center gap-1 rounded-full border border-danger-100 bg-danger-50 px-2 py-0.5 font-semibold text-danger-700"
          title={card.invalidationFocus}
        >
          <ClockCircleOutlined aria-hidden="true" />
          <span className="truncate">失效 {compactStockText(card.invalidationFocus, 24)}</span>
        </span>
        {hiddenEvidenceCount > 0 ? (
          <span className="inline-flex items-center rounded-full border border-neutral-200 bg-neutral-50 px-2 py-0.5 font-semibold text-neutral-500">
            +{hiddenEvidenceCount} 证据
          </span>
        ) : null}
      </div>
      <Collapse
        ghost
        bordered={false}
        destroyOnHidden
        className="stock-analysis-page__candidate-collapse"
        items={[
          {
            key: "evidence",
            label: (
              <span className="inline-flex items-center gap-1">
                <SafetyCertificateOutlined aria-hidden="true" />
                <span aria-hidden="true">证据</span>
                <span className="sr-only">证据明细</span>
                <span className="rounded border border-neutral-200 bg-neutral-50 px-1 text-[10px] text-neutral-500">
                  {card.primaryEvidence.length + card.supportingEvidence.length}
                </span>
              </span>
            ),
            children: (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <div>
                  <h4 className="mb-2 text-sm font-semibold text-neutral-900">进入依据</h4>
                  <ul className="m-0 grid list-none gap-1 p-0 text-sm text-neutral-600">
                    {[...card.primaryEvidence, ...card.supportingEvidence].map((item) => (
                      <li key={item.key}>
                        <strong className="text-neutral-900">{item.label}</strong>：{item.value}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="mb-2 text-sm font-semibold text-neutral-900">边界待补</h4>
                  <ul className="m-0 grid list-none gap-1 p-0 text-sm text-neutral-600">
                    {card.boundaryEvidence.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="mb-2 text-sm font-semibold text-neutral-900">失效条件</h4>
                  <p className="border-l-[3px] border-primary-500 pl-2.5 text-sm font-semibold text-neutral-900">
                    {card.invalidationFocus}
                  </p>
                  <ul className="m-0 mt-1 grid list-none gap-1 p-0 text-sm text-neutral-600">
                    {card.invalidationRules.slice(1).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ),
          },
          {
            key: "raw",
            label: (
              <span className="inline-flex items-center gap-1">
                <BarChartOutlined aria-hidden="true" />
                <span aria-hidden="true">指标</span>
                <span className="sr-only">指标明细</span>
                <span className="rounded border border-neutral-200 bg-neutral-50 px-1 text-[10px] text-neutral-500">
                  {card.rawFields.length}
                </span>
              </span>
            ),
            children: (
              <dl className="stock-analysis-page__raw-grid">
                {card.rawFields.map((field) => (
                  <div key={field.key}>
                    <dt>{field.label}</dt>
                    <dd>{field.value}</dd>
                  </div>
                ))}
              </dl>
            ),
          },
        ]}
      />
    </article>
  );
}
