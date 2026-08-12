import {
  BarChartOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  LineChartOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import { Button as AntButton } from "antd";
import {
  StockAnalysisAccordion as Accordion,
  StockAnalysisAccordionItem as AccordionItem,
} from "./StockAnalysisAccordion";
import { StockAnalysisInlineChip as Chip } from "./StockAnalysisStatusPrimitives";

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
  const selected = selectedSectorCode != null && card.sectorCode === selectedSectorCode;

  return (
    <article
      className={`mb-4 w-full bg-white/60 dark:bg-default-100/50 backdrop-blur-md backdrop-saturate-150 border border-default-200/50 ${
        selected ? "ring-2 ring-primary ring-offset-2" : ""
      }`}
      data-selected-sector={selected ? "true" : undefined}
      data-testid={`stock-candidate-${card.stockCode}`}
    >
      <header className="flex flex-col items-start gap-2 px-4 pt-4 pb-2">
        <div className="flex w-full items-start justify-between gap-4">
          <div className="flex gap-3">
            <div className="flex h-8 items-center justify-center rounded-md bg-default-100 px-2 font-mono text-sm font-bold text-default-600">
              #{card.rank}
            </div>
            <div className="min-w-0">
              <h3 className="truncate text-lg font-semibold leading-tight text-foreground">{card.headline}</h3>
              <p className="truncate text-sm text-default-500">
                {card.stockName} · {card.stockCode} · {card.sectorName}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <div className="flex flex-col items-end text-xs text-default-500">
              <span title={card.patternNote}>距 {card.distanceToBreakoutPct}</span>
              <span>{card.primaryEvidence.length + card.supportingEvidence.length} 证据</span>
            </div>
            <AntButton
              size="small"
              icon={<LineChartOutlined />}
              data-testid={`stock-candidate-review-chart-${card.stockCode}`}
              onClick={() => onReviewChart(card)}
            >
              <span className="sr-only">复核 </span>K 线
            </AntButton>
            <Chip size="sm" color="primary" variant="flat">观察</Chip>
          </div>
        </div>
        <p className="text-sm font-medium text-default-700">{card.reviewFocus}</p>
      </header>

      <div className="px-4 py-2 gap-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {visibleEvidence.map((item, index) => (
            <div
              className="flex items-start gap-2 rounded-lg bg-default-50/50 p-2"
              key={item.key}
              title={`${item.label}: ${item.value}`}
            >
              <div className="mt-0.5">
                <StatusIcon tone={index < card.primaryEvidence.length ? "positive" : "neutral"}>
                  {index < card.primaryEvidence.length ? <CheckCircleOutlined /> : <DatabaseOutlined />}
                </StatusIcon>
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-xs text-default-500 truncate">{item.label}</span>
                <strong className="text-sm text-default-700 truncate">{item.value}</strong>
              </div>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {card.liquidityFloorPass === false ? (
            <Chip
              size="sm"
              variant="flat"
              color="warning"
              title={card.dailyAmountLabel ?? "低于 2 亿元日成交门槛"}
            >
              低流动
            </Chip>
          ) : null}
          <Chip size="sm" variant="flat" color="default" startContent={<SafetyCertificateOutlined />}>
            边界 {card.boundaryEvidence.length}
          </Chip>
          <Chip size="sm" variant="flat" color="danger" startContent={<ClockCircleOutlined />} title={card.invalidationFocus} className="max-w-[200px] truncate">
            失效 {compactStockText(card.invalidationFocus, 24)}
          </Chip>
          {hiddenEvidenceCount > 0 ? (
            <Chip size="sm" variant="faded" color="default">
              +{hiddenEvidenceCount} 证据
            </Chip>
          ) : null}
        </div>

        <div className="-mx-4 -mb-2 mt-2">
          <Accordion
            className="w-full"
            itemClasses={{ title: "flex items-center gap-2", content: "pt-0" }}
          >
            <AccordionItem
              key="evidence"
              aria-label="证据明细"
              title={
                  <div className="flex items-center gap-2 text-sm font-medium text-default-600">
                    <SafetyCertificateOutlined aria-hidden="true" />
                    <span aria-hidden="true">证据</span>
                    <span className="sr-only">证据明细</span>
                    <span className="flex h-5 items-center justify-center rounded-full bg-default-200 px-2 text-xs">
                      {card.primaryEvidence.length + card.supportingEvidence.length}
                    </span>
                  </div>
              }
            >
                  <div className="grid grid-cols-1 gap-6 sm:grid-cols-3 pl-6 pr-2 pb-2">
                    <div>
                      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-default-500">进入依据</h4>
                      <ul className="space-y-1 text-sm text-default-700">
                        {[...card.primaryEvidence, ...card.supportingEvidence].map((item) => (
                          <li key={item.key}>
                            <strong className="font-medium text-foreground">{item.label}</strong>：{item.value}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-default-500">边界待补</h4>
                      <ul className="list-inside list-disc space-y-1 text-sm text-default-700">
                        {card.boundaryEvidence.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-default-500">失效条件</h4>
                      <p className="mb-2 border-l-2 border-danger-300 pl-2 text-sm italic text-default-600">{card.invalidationFocus}</p>
                      <ul className="list-inside list-disc space-y-1 text-sm text-default-700">
                        {card.invalidationRules.slice(1).map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
            </AccordionItem>
            <AccordionItem
              key="raw"
              aria-label="指标明细"
              title={
                  <div className="flex items-center gap-2 text-sm font-medium text-default-600">
                    <BarChartOutlined aria-hidden="true" />
                    <span aria-hidden="true">指标</span>
                    <span className="sr-only">指标明细</span>
                    <span className="flex h-5 items-center justify-center rounded-full bg-default-200 px-2 text-xs">
                      {card.rawFields.length}
                    </span>
                  </div>
              }
            >
                  <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 pl-6 pr-2 pb-2">
                    {card.rawFields.map((field) => (
                      <div key={field.key} className="flex flex-col">
                        <dt className="text-xs text-default-500">{field.label}</dt>
                        <dd className="text-sm font-medium text-default-700">{field.value}</dd>
                      </div>
                    ))}
                  </dl>
            </AccordionItem>
          </Accordion>
        </div>
      </div>
    </article>
  );
}
