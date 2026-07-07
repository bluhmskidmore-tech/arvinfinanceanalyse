import type { ProductCategoryGovernanceNotice } from "./productCategoryPnlPageModel";
import "./ProductCategoryGovernanceStrip.css";

type ProductCategoryGovernanceStripProps = {
  asOfDateGapText: string;
  notices: ProductCategoryGovernanceNotice[];
  formalScenarioDistinct: string | null;
};

export function ProductCategoryGovernanceStrip(props: ProductCategoryGovernanceStripProps) {
  return (
    <div
      data-testid="product-category-governance-strip"
      className="product-category-governance-strip"
    >
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
  );
}
