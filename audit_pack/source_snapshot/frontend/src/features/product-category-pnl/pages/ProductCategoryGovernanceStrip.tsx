import type { ProductCategoryGovernanceNotice } from "./productCategoryPnlPageModel";

const wrapStyle = {
  marginBottom: 14,
  padding: "12px 16px",
  borderRadius: 14,
  border: "1px solid #d7dfea",
  background: "#f7f9fc",
} as const;

const asOfDateStyle = {
  margin: 0,
  color: "#5c6b82",
  fontSize: 12,
  lineHeight: 1.65,
} as const;

const noticeStyle = {
  margin: "8px 0 0",
  color: "#9a6700",
  fontSize: 12,
  lineHeight: 1.65,
} as const;

const distinctStyle = {
  margin: "8px 0 0",
  color: "#162033",
  fontSize: 12,
  lineHeight: 1.65,
} as const;

type ProductCategoryGovernanceStripProps = {
  asOfDateGapText: string;
  notices: ProductCategoryGovernanceNotice[];
  formalScenarioDistinct: string | null;
};

export function ProductCategoryGovernanceStrip(props: ProductCategoryGovernanceStripProps) {
  return (
    <div data-testid="product-category-governance-strip" style={wrapStyle}>
      <p data-testid="product-category-as-of-date-gap" style={asOfDateStyle}>
        {props.asOfDateGapText}
      </p>
      {props.notices.map((notice) => (
        <p
          key={notice.id}
          data-testid={`product-category-governance-notice-${notice.id}`}
          role="status"
          style={noticeStyle}
        >
          {notice.text}
        </p>
      ))}
      {props.formalScenarioDistinct ? (
        <p
          data-testid="product-category-formal-scenario-meta-distinct"
          style={distinctStyle}
        >
          {props.formalScenarioDistinct}
        </p>
      ) : null}
    </div>
  );
}
