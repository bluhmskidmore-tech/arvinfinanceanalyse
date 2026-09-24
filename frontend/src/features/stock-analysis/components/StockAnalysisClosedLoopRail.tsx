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
  SA_SECTION_HEAD,
} from "../lib/stockAnalysisPageChrome";
import {
  tonePillClass,
  toneTextClass,
  riskExitBlockedSummary,
} from "../lib/stockAnalysisPageCopy";
import type { LivermoreUnsupportedOutput } from "../../../api/contracts";
import { closedLoopRailIcon } from "./stockAnalysisClosedLoopRailIcons";

export function StockAnalysisClosedLoopSummaryRail({
  summary,
  riskTone,
  riskTriggeredCount,
  riskUnsupportedOutput,
  boundaryIssueCount,
  reviewQueueCount,
  nextActionLabel,
  nextActionFullLabel,
}: {
  summary: StockClosedLoopSummary;
  riskTone: Extract<StockClosedLoopTone, "positive" | "warning" | "negative">;
  riskTriggeredCount: number;
  riskUnsupportedOutput?: LivermoreUnsupportedOutput | null;
  boundaryIssueCount: number;
  reviewQueueCount: number;
  nextActionLabel: string;
  nextActionFullLabel: string;
}) {
  const riskBlockedLabel = riskUnsupportedOutput
    ? riskExitBlockedSummary(riskUnsupportedOutput.reason)
    : null;

  return (
    <section
      data-testid="stock-analysis-closed-loop-summary"
      aria-label="闭环摘要"
    >
      <div className={SA_SECTION_HEAD}>
        <h2 className={SA_CARD_TITLE}>闭环摘要</h2>
        <span className={tonePillClass(summary.referenceRating.tone)}>
          {summary.referenceRating.label}
        </span>
      </div>

      <div data-testid="stock-analysis-closed-loop-verdict" data-tone={summary.verdict.tone}>
        <div className="stock-analysis-page__boundary-summary">
          <span>
            <small>
              <span aria-hidden="true">
                {summary.verdict.tone === "positive" ? (
                  <CheckCircleOutlined />
                ) : (
                  <SafetyCertificateOutlined />
                )}
              </span>
              <span className={toneTextClass(summary.verdict.tone)}>
                {summary.verdict.label}
              </span>
            </small>
            <strong>{summary.verdict.headline}</strong>
          </span>
          <span>
            <small>边界</small>
            <strong>{summary.boundaryCount}</strong>
          </span>
          <span>
            <small>依据</small>
            <strong>{summary.verdict.evidence.length}</strong>
          </span>
        </div>
        <Accordion className="stock-analysis-page__candidate-collapse stock-analysis-page__rail-collapse">
          <AccordionItem
            key="closed-loop-verdict-detail"
            aria-label="依据明细"
            title={<span>依据明细</span>}
          >
            <div>
              <p>{summary.verdict.primaryReason}</p>
              <ul aria-label="闭环结论证据">
                {summary.verdict.evidence.map((item) => (
                  <li key={item} title={item}>
                    {item}
                  </li>
                ))}
              </ul>
              <p>{summary.verdict.nextStep}</p>
            </div>
          </AccordionItem>
        </Accordion>
      </div>

      <div aria-label="首屏决策指标">
        <div data-tone={summary.referenceRating.tone}>
          <span aria-hidden="true">
            <SafetyCertificateOutlined />
          </span>
          <span>
            <span>闭环</span>
            <strong>{summary.referenceRating.label}</strong>
          </span>
        </div>
        <div
          data-testid="stock-analysis-closed-loop-risk"
          data-tone={riskBlockedLabel ? "negative" : riskTone}
        >
          <span aria-hidden="true">
            <FireOutlined />
          </span>
          <span>
            <span>风险</span>
            <strong>
              {riskBlockedLabel ? "阻断" : `${riskTriggeredCount} 触发`}
            </strong>
            {riskBlockedLabel ? <small>{riskBlockedLabel}</small> : null}
          </span>
        </div>
        <div data-tone={boundaryIssueCount > 0 ? "warning" : "positive"}>
          <span aria-hidden="true">
            <DatabaseOutlined />
          </span>
          <span>
            <span>边界</span>
            <strong>{boundaryIssueCount}</strong>
          </span>
        </div>
        <div data-tone={reviewQueueCount > 0 ? "positive" : "warning"}>
          <span aria-hidden="true">
            <StockOutlined />
          </span>
          <span>
            <span>复核</span>
            <strong>{reviewQueueCount}</strong>
          </span>
        </div>
      </div>

      <p
        className="stock-analysis-page__ev-next-action"
        title={nextActionFullLabel}
      >
        <StockOutlined aria-hidden="true" />
        <span>{nextActionLabel}</span>
      </p>

      <ul
        aria-label="闭环检查项"
        data-testid="stock-analysis-rail-check-matrix"
      >
        {summary.items.map((item) => (
          <li
            key={item.key}
            data-tone={item.tone}
            data-testid={
              item.key === "replay" ? "stock-analysis-replay-status" : `stock-analysis-closed-loop-${item.key}`
            }
            >
            <div className="stock-analysis-page__rail-risk-main">
              <span>
                <span aria-hidden="true">
                  {closedLoopRailIcon(item.key)}
                </span>
                <span>{item.label}</span>
              </span>
              <strong className={toneTextClass(item.tone)}>{item.statusLabel}</strong>
            </div>
            {(item.key === "replay" || (item.key === "adversarial_gate" && item.tone !== "positive")) &&
            item.detail ? (
              <Accordion className="stock-analysis-page__candidate-collapse stock-analysis-page__rail-collapse">
                <AccordionItem
                  key={`${item.key}-detail`}
                  aria-label="明细"
                  title={<span>明细</span>}
                >
                  <p>{item.detail}</p>
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
    </section>
  );
}
