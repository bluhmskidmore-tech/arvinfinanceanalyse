import {
  CheckCircleOutlined,
  DatabaseOutlined,
  FireOutlined,
  SafetyCertificateOutlined,
  StockOutlined,
} from "@ant-design/icons";
import {
  StockAnalysisAccordion as Accordion,
  StockAnalysisAccordionItem as AccordionItem,
} from "./StockAnalysisAccordion";

import type {
  StockClosedLoopSummary,
  StockClosedLoopTone,
} from "../lib/stockAnalysisPageModel";
import {
  SA_CARD_TITLE,
  SA_FIRST_CARD,
  SA_SECTION_HEAD,
} from "../lib/stockAnalysisPageChrome";
import {
  tonePillClass,
  toneTextClass,
} from "../lib/stockAnalysisPageCopy";
import { closedLoopRailIcon } from "./stockAnalysisClosedLoopRailIcons";

export function StockAnalysisClosedLoopSummaryRail({
  summary,
  riskTone,
  riskTriggeredCount,
  boundaryIssueCount,
  reviewQueueCount,
  nextActionLabel,
  nextActionFullLabel,
}: {
  summary: StockClosedLoopSummary;
  riskTone: Extract<StockClosedLoopTone, "positive" | "warning" | "negative">;
  riskTriggeredCount: number;
  boundaryIssueCount: number;
  reviewQueueCount: number;
  nextActionLabel: string;
  nextActionFullLabel: string;
}) {
  return (
    <section
      className={`${SA_FIRST_CARD} bg-background/40 border-default-100 shadow-sm backdrop-blur-md`}
      data-testid="stock-analysis-closed-loop-summary"
      aria-label="闭环摘要"
    >
      <header className={`${SA_SECTION_HEAD} flex justify-between items-center px-4 py-3 border-b border-default-100`}>
        <h2 className={`${SA_CARD_TITLE} text-lg font-bold`}>闭环摘要</h2>
        <span className={tonePillClass(summary.referenceRating.tone)}>
          {summary.referenceRating.label}
        </span>
      </header>

      <div className="flex flex-col gap-5 px-4 py-4">
        <div
          className="flex flex-col gap-3 p-4 rounded-xl bg-default-50/50 border border-default-100"
          data-testid="stock-analysis-closed-loop-verdict"
          data-tone={summary.verdict.tone}
        >
          <span className="text-2xl" aria-hidden="true">
            {summary.verdict.tone === "positive" ? (
              <CheckCircleOutlined className="text-success" />
            ) : (
              <SafetyCertificateOutlined className="text-warning" />
            )}
          </span>
          <div className="flex flex-col gap-1">
            <span className={`text-sm font-medium ${toneTextClass(summary.verdict.tone)}`}>
              {summary.verdict.label}
            </span>
            <strong className="text-base text-default-900">{summary.verdict.headline}</strong>
          </div>
          <div className="flex flex-row gap-6 mt-2">
            <div className="flex flex-col">
              <span className="text-xs text-default-500">边界</span>
              <strong className="text-sm text-default-900">{summary.boundaryCount}</strong>
            </div>
            <div className="flex flex-col">
              <span className="text-xs text-default-500">依据</span>
              <strong className="text-sm text-default-900">{summary.verdict.evidence.length}</strong>
            </div>
          </div>
          <Accordion
            className="mt-2 -mx-4 px-4"
          >
            <AccordionItem
              key="closed-loop-verdict-detail"
              aria-label="依据明细"
              title={<span className="text-sm text-default-500">依据明细</span>}
            >
              <div className="text-sm text-default-500 flex flex-col gap-2">
                <p>{summary.verdict.primaryReason}</p>
                <ul aria-label="闭环结论证据" className="list-disc pl-5">
                  {summary.verdict.evidence.map((item) => (
                    <li key={item} title={item}>
                      {item}
                    </li>
                  ))}
                </ul>
                <p className="text-xs text-default-400 mt-2">{summary.verdict.nextStep}</p>
              </div>
            </AccordionItem>
          </Accordion>
        </div>

        <div className="grid grid-cols-2 gap-3" aria-label="首屏决策指标">
          <div className="flex items-center gap-3 p-3 rounded-lg border border-default-100 bg-background/50" data-tone={summary.referenceRating.tone}>
            <span className="text-lg text-default-500" aria-hidden="true">
              <SafetyCertificateOutlined />
            </span>
            <span className="flex flex-col">
              <span className="text-xs text-default-500">闭环</span>
              <strong className="text-sm text-default-900">{summary.referenceRating.label}</strong>
            </span>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg border border-default-100 bg-background/50" data-tone={riskTone}>
            <span className="text-lg text-danger" aria-hidden="true">
              <FireOutlined />
            </span>
            <span className="flex flex-col">
              <span className="text-xs text-default-500">风险</span>
              <strong className="text-sm text-default-900">{riskTriggeredCount} 触发</strong>
            </span>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg border border-default-100 bg-background/50" data-tone={boundaryIssueCount > 0 ? "warning" : "positive"}>
            <span className="text-lg text-warning" aria-hidden="true">
              <DatabaseOutlined />
            </span>
            <span className="flex flex-col">
              <span className="text-xs text-default-500">边界</span>
              <strong className="text-sm text-default-900">{boundaryIssueCount}</strong>
            </span>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg border border-default-100 bg-background/50" data-tone={reviewQueueCount > 0 ? "positive" : "warning"}>
            <span className="text-lg text-primary" aria-hidden="true">
              <StockOutlined />
            </span>
            <span className="flex flex-col">
              <span className="text-xs text-default-500">复核</span>
              <strong className="text-sm text-default-900">{reviewQueueCount}</strong>
            </span>
          </div>
        </div>

        <p className="flex items-center gap-2 text-sm font-medium text-primary-500 p-3 bg-primary-50/30 rounded-lg border border-primary-100/50" title={nextActionFullLabel}>
          <StockOutlined aria-hidden="true" />
          <span>{nextActionLabel}</span>
        </p>

        <ul
          className="flex flex-col gap-1 mt-2"
          aria-label="闭环检查项"
          data-testid="stock-analysis-rail-check-matrix"
        >
          {summary.items.map((item) => (
            <li
              key={item.key}
              className="flex flex-col py-2 border-b border-default-100 last:border-0"
              data-tone={item.tone}
              data-testid={
                item.key === "replay" ? "stock-analysis-replay-status" : `stock-analysis-closed-loop-${item.key}`
              }
            >
              <div className="flex flex-row justify-between items-center text-sm">
                <span className="flex items-center gap-2 text-default-700">
                  <span className="text-default-500" aria-hidden="true">
                    {closedLoopRailIcon(item.key)}
                  </span>
                  <span>{item.label}</span>
                </span>
                <strong className={toneTextClass(item.tone)}>{item.statusLabel}</strong>
              </div>
              {(item.key === "replay" || (item.key === "adversarial_gate" && item.tone !== "positive")) &&
              item.detail ? (
                <Accordion
                  className="mt-1 -mx-4 px-4"
                >
                  <AccordionItem
                    key={`${item.key}-detail`}
                    aria-label="明细"
                    title={<span className="text-xs text-default-500">明细</span>}
                  >
                    <p className="text-xs text-default-500">{item.detail}</p>
                  </AccordionItem>
                </Accordion>
              ) : null}
              {item.badges?.map((badge) => (
                <span className="sr-only" key={badge}>
                  {badge}
                </span>
              ))}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
