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
      className="stock-analysis-page__review-candidate-card"
      data-testid={`stock-candidate-${card.stockCode}`}
      data-selected-sector={
        selectedSectorCode != null && card.sectorCode === selectedSectorCode ? "true" : undefined
      }
    >
      <div className="stock-analysis-page__review-row-head">
        <strong className="stock-analysis-page__review-row-rank stock-analysis-page__tabular">#{card.rank}</strong>
        <div className="stock-analysis-page__min-w-0">
          <h3 className="stock-analysis-page__review-card-headline">{card.headline}</h3>
          <p className="stock-analysis-page__review-card-subtitle">
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
          <span className="stock-analysis-page__review-chip stock-analysis-page__review-chip--accent">观察</span>
        </div>
      </div>
      <p className="stock-analysis-page__review-focus">{card.reviewFocus}</p>
      <div className="stock-analysis-page__review-candidate-evidence">
        {visibleEvidence.map((item, index) => (
          <div
            className="stock-analysis-page__review-evidence-item"
            key={item.key}
            title={`${item.label}: ${item.value}`}
          >
            <StatusIcon tone={index < card.primaryEvidence.length ? "positive" : "neutral"}>
              {index < card.primaryEvidence.length ? <CheckCircleOutlined /> : <DatabaseOutlined />}
            </StatusIcon>
            <span className="stock-analysis-page__review-evidence-copy">
              <span className="stock-analysis-page__review-evidence-label">{item.label}</span>
              <strong className="stock-analysis-page__review-evidence-value">{item.value}</strong>
            </span>
          </div>
        ))}
      </div>
      <div className="stock-analysis-page__review-candidate-chips">
        <span className="stock-analysis-page__review-chip">
          <SafetyCertificateOutlined aria-hidden="true" /> 边界 {card.boundaryEvidence.length}
        </span>
        <span
          className="stock-analysis-page__review-chip stock-analysis-page__review-chip--danger stock-analysis-page__review-chip--truncate"
          title={card.invalidationFocus}
        >
          <ClockCircleOutlined aria-hidden="true" />
          <span className="stock-analysis-page__review-chip--truncate">失效 {compactStockText(card.invalidationFocus, 24)}</span>
        </span>
        {hiddenEvidenceCount > 0 ? (
          <span className="stock-analysis-page__review-chip stock-analysis-page__review-chip--muted">
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
              <span className="stock-analysis-page__collapse-label">
                <SafetyCertificateOutlined aria-hidden="true" />
                <span aria-hidden="true">证据</span>
                <span className="sr-only">证据明细</span>
                <span className="stock-analysis-page__collapse-count">
                  {card.primaryEvidence.length + card.supportingEvidence.length}
                </span>
              </span>
            ),
            children: (
              <div className="stock-analysis-page__evidence-grid">
                <div>
                  <h4 className="stock-analysis-page__evidence-section-title">进入依据</h4>
                  <ul className="stock-analysis-page__evidence-list">
                    {[...card.primaryEvidence, ...card.supportingEvidence].map((item) => (
                      <li key={item.key}>
                        <strong>{item.label}</strong>：{item.value}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="stock-analysis-page__evidence-section-title">边界待补</h4>
                  <ul className="stock-analysis-page__evidence-list">
                    {card.boundaryEvidence.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="stock-analysis-page__evidence-section-title">失效条件</h4>
                  <p className="stock-analysis-page__invalidation-quote">{card.invalidationFocus}</p>
                  <ul className="stock-analysis-page__evidence-list">
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
              <span className="stock-analysis-page__collapse-label">
                <BarChartOutlined aria-hidden="true" />
                <span aria-hidden="true">指标</span>
                <span className="sr-only">指标明细</span>
                <span className="stock-analysis-page__collapse-count">{card.rawFields.length}</span>
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
