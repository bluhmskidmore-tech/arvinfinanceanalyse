import {
  CheckCircleOutlined,
  DatabaseOutlined,
  FireOutlined,
  SafetyCertificateOutlined,
  StockOutlined,
} from "@ant-design/icons";
import { Collapse } from "antd";

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
      className={SA_FIRST_CARD}
      data-testid="stock-analysis-closed-loop-summary"
      aria-label="闭环摘要"
    >
      <div className={SA_SECTION_HEAD}>
        <h2 className={SA_CARD_TITLE}>闭环摘要</h2>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${tonePillClass(summary.referenceRating.tone)}`}
        >
          {summary.referenceRating.label}
        </span>
      </div>

      <div
        className="stock-analysis-page__rail-verdict"
        data-testid="stock-analysis-closed-loop-verdict"
        data-tone={summary.verdict.tone}
      >
        <span className="stock-analysis-page__rail-verdict-icon" aria-hidden="true">
          {summary.verdict.tone === "positive" ? (
            <CheckCircleOutlined />
          ) : (
            <SafetyCertificateOutlined />
          )}
        </span>
        <div className="stock-analysis-page__rail-verdict-body">
          <span className={`stock-analysis-page__rail-verdict-label ${toneTextClass(summary.verdict.tone)}`}>
            {summary.verdict.label}
          </span>
          <strong>{summary.verdict.headline}</strong>
        </div>
        <div className="stock-analysis-page__rail-verdict-kpis">
          <div className="stock-analysis-page__rail-kpi">
            <span>边界</span>
            <strong>{summary.boundaryCount}</strong>
          </div>
          <div className="stock-analysis-page__rail-kpi">
            <span>依据</span>
            <strong>{summary.verdict.evidence.length}</strong>
          </div>
        </div>
        <Collapse
          ghost
          bordered={false}
          destroyOnHidden
          className="stock-analysis-page__candidate-collapse stock-analysis-page__rail-collapse"
          items={[
            {
              key: "closed-loop-verdict-detail",
              label: "依据明细",
              children: (
                <div className="text-xs text-neutral-600">
                  <p className="m-0">{summary.verdict.primaryReason}</p>
                  <ul className="mt-2 space-y-1 pl-4" aria-label="闭环结论证据">
                    {summary.verdict.evidence.map((item) => (
                      <li key={item} className="list-disc" title={item}>
                        {item}
                      </li>
                    ))}
                  </ul>
                  <p className="m-0 mt-2 text-neutral-500">{summary.verdict.nextStep}</p>
                </div>
              ),
            },
          ]}
        />
      </div>

      <div className="stock-analysis-page__rail-metric-grid" aria-label="首屏决策指标">
        <div data-tone={summary.referenceRating.tone}>
          <span className="stock-analysis-page__rail-stat-icon" aria-hidden="true">
            <SafetyCertificateOutlined />
          </span>
          <span>
            <span>闭环</span>
            <strong>{summary.referenceRating.label}</strong>
          </span>
        </div>
        <div data-tone={riskTone}>
          <span className="stock-analysis-page__rail-stat-icon" aria-hidden="true">
            <FireOutlined />
          </span>
          <span>
            <span>风险</span>
            <strong>{riskTriggeredCount} 触发</strong>
          </span>
        </div>
        <div data-tone={boundaryIssueCount > 0 ? "warning" : "positive"}>
          <span className="stock-analysis-page__rail-stat-icon" aria-hidden="true">
            <DatabaseOutlined />
          </span>
          <span>
            <span>边界</span>
            <strong>{boundaryIssueCount}</strong>
          </span>
        </div>
        <div data-tone={reviewQueueCount > 0 ? "positive" : "warning"}>
          <span className="stock-analysis-page__rail-stat-icon" aria-hidden="true">
            <StockOutlined />
          </span>
          <span>
            <span>复核</span>
            <strong>{reviewQueueCount}</strong>
          </span>
        </div>
      </div>

      <p className="stock-analysis-page__rail-next-action" title={nextActionFullLabel}>
        <StockOutlined aria-hidden="true" />
        <span>{nextActionLabel}</span>
      </p>

      <ul
        className="stock-analysis-page__rail-check-list"
        aria-label="闭环检查项"
        data-testid="stock-analysis-rail-check-matrix"
      >
        {summary.items.map((item) => (
          <li
            key={item.key}
            className="stock-analysis-page__rail-check-row"
            data-tone={item.tone}
            data-testid={
              item.key === "replay" ? "stock-analysis-replay-status" : `stock-analysis-closed-loop-${item.key}`
            }
          >
            <div className="stock-analysis-page__rail-check-main">
              <span>
                <span className="stock-analysis-page__rail-check-icon" aria-hidden="true">
                  {closedLoopRailIcon(item.key)}
                </span>
                <span>{item.label}</span>
              </span>
              <strong className={toneTextClass(item.tone)}>{item.statusLabel}</strong>
            </div>
            {(item.key === "replay" || (item.key === "adversarial_gate" && item.tone !== "positive")) &&
            item.detail ? (
              <Collapse
                ghost
                bordered={false}
                destroyOnHidden
                className="stock-analysis-page__candidate-collapse stock-analysis-page__rail-collapse"
                items={[
                  {
                    key: `${item.key}-detail`,
                    label: "明细",
                    children: (
                      <p className="m-0 text-[11px] leading-snug text-neutral-500">{item.detail}</p>
                    ),
                  },
                ]}
              />
            ) : null}
            {item.badges?.map((badge) => (
              <span className="stock-analysis-page__visually-hidden" key={badge}>
                {badge}
              </span>
            ))}
          </li>
        ))}
      </ul>
    </section>
  );
}
