import type { ReactNode } from "react";

import type {
  ProductCategoryDataHealth,
  ProductCategoryGovernanceNotice,
} from "./productCategoryPnlPageModel";
import "./ProductCategoryGovernanceStrip.css";

type ProductCategoryGovernanceStripProps = {
  dataHealth: ProductCategoryDataHealth;
  asOfDateGapText: string;
  notices: ProductCategoryGovernanceNotice[];
  formalScenarioDistinct: string | null;
  onRetry: (() => void) | null;
  evidence: ReactNode;
};

export function ProductCategoryGovernanceStrip(props: ProductCategoryGovernanceStripProps) {
  return (
    <div
      id="product-category-governance"
      data-testid="product-category-governance-strip"
      className="product-category-governance-strip"
    >
      <div
        data-testid="product-category-data-health"
        data-health-state={props.dataHealth.state}
        className="product-category-governance-strip__health"
        role={props.dataHealth.judgementState === "blocked" ? "alert" : "status"}
      >
        <span className="product-category-governance-strip__health-marker" aria-hidden="true" />
        <div className="product-category-governance-strip__health-content">
          <div className="product-category-governance-strip__health-copy">
            <strong>{props.dataHealth.title}</strong>
            {props.dataHealth.state === "ready" ? null : (
              <span>{props.dataHealth.description}</span>
            )}
          </div>
          <span
            className="product-category-governance-strip__judgement"
            data-judgement-state={props.dataHealth.judgementState}
            data-testid="product-category-formal-judgement-status"
          >
            {props.dataHealth.judgementLabel}
          </span>
          {props.dataHealth.facts.length > 0 ? (
            <dl className="product-category-governance-strip__facts">
              {props.dataHealth.facts.map((fact) => (
                <div key={fact.label}>
                  <dt>{fact.label} </dt>
                  <dd>{fact.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
        </div>
        {props.onRetry && props.dataHealth.retryTarget ? (
          <button type="button" onClick={props.onRetry}>
            {props.dataHealth.retryTarget === "dates" ? "重试报告月份" : "重试正式基线"}
          </button>
        ) : null}
      </div>
      <details
        data-testid="product-category-governance-evidence"
        className="product-category-governance-strip__evidence"
      >
        <summary>
          <span>治理与证据</span>
          <strong>
            {props.notices.length > 0
              ? `${props.notices.length} 项治理提示 · 3 项认证待完成`
              : "3 项认证待完成"}
          </strong>
        </summary>
        <div className="product-category-governance-strip__evidence-body">
          {props.evidence}
          <p
            data-testid="product-category-as-of-date-gap"
            className="product-category-governance-strip__as-of-date"
          >
            {props.asOfDateGapText}
          </p>
          {props.notices.map((notice) => (
            <p
              key={notice.id}
              data-testid={`product-category-governance-notice-${notice.id}`}
              role="status"
              className="product-category-governance-strip__notice"
            >
              {notice.text}
            </p>
          ))}
          {props.formalScenarioDistinct ? (
            <p
              data-testid="product-category-formal-scenario-meta-distinct"
              className="product-category-governance-strip__formal-scenario-distinct"
            >
              {props.formalScenarioDistinct}
            </p>
          ) : null}
        </div>
      </details>
    </div>
  );
}
