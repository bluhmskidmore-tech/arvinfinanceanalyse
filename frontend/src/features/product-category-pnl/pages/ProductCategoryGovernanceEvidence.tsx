import type { ResultMeta } from "../../../api/contracts";

type ProductCategoryGovernanceEvidenceProps = {
  reportDate: string;
  selectedView: string;
  scenarioApplied: boolean;
  resultMeta?: ResultMeta;
};

export function ProductCategoryGovernanceEvidence(
  props: ProductCategoryGovernanceEvidenceProps,
) {
  const scenarioStateLabel = props.scenarioApplied
    ? "已应用情景预览"
    : "正式基线";
  const basisLabel = props.resultMeta?.basis ?? "pending";
  const qualityLabel = props.resultMeta?.quality_flag ?? "pending";
  const vendorLabel = props.resultMeta?.vendor_status ?? "pending";
  const fallbackLabel = props.resultMeta?.fallback_mode ?? "pending";
  const generatedAtLabel = props.resultMeta?.generated_at ?? "pending";
  const traceIdLabel = props.resultMeta?.trace_id ?? "pending";
  const needsDataStateReview =
    props.resultMeta !== undefined &&
    (props.resultMeta.quality_flag !== "ok" ||
      props.resultMeta.vendor_status === "vendor_stale" ||
      props.resultMeta.vendor_status === "vendor_unavailable" ||
      props.resultMeta.fallback_mode !== "none");

  return (
    <div
      data-testid="product-category-certification-blockers"
      className="product-category-governance-evidence"
      aria-label="产品分类损益认证阻断状态"
    >
      <section
        data-testid="product-category-governance-signing-blockers"
        className="product-category-governance-evidence__layer"
      >
        <h3>签署阻断</h3>
        <ProductCategoryOwnerSignableStatus />
      </section>
      <section
        data-testid="product-category-governance-source-version"
        className="product-category-governance-evidence__layer"
      >
        <h3>来源与版本</h3>
        <div
          data-testid="product-category-formal-readiness-status"
          className="product-category-formal-readiness__status-grid"
        >
          <span>report_date={props.reportDate || "pending"}</span>
          <span>view={props.selectedView}</span>
          <span>{scenarioStateLabel}</span>
          <span>basis={basisLabel}</span>
          <span>quality={qualityLabel}</span>
          <span>vendor={vendorLabel}</span>
          <span>fallback={fallbackLabel}</span>
          <span>generated_at={generatedAtLabel}</span>
          <span>trace_id={traceIdLabel}</span>
          {needsDataStateReview ? (
            <span>数据状态待复核</span>
          ) : null}
        </div>
      </section>
      <section
        data-testid="product-category-governance-audit-evidence"
        className="product-category-governance-evidence__layer"
      >
        <h3>审计证据</h3>
        <div className="product-category-formal-readiness__certification-strip">
          <span>签署前需重新运行核算</span>
          <span>单位：亿元</span>
          <span>日期基准：report_date</span>
          <span>数据来源：正式只读模型</span>
        </div>
      </section>
    </div>
  );
}

function ProductCategoryOwnerSignableStatus() {
  return (
    <section
      data-testid="product-category-owner-signable-status"
      className="product-category-owner-signable-status"
      aria-label="产品分类损益签署状态"
    >
      <div className="product-category-owner-signable-status__heading">
        <span>签署状态</span>
        <strong>待认证</strong>
        <small>3项待完成</small>
      </div>
      <div className="product-category-owner-signable-status__fields">
        <span>可签署：否</span>
        <span>已认证：否</span>
        <span>待业主审批</span>
        <span>黄金样本待审批</span>
        <span>人工抽核未完成：已核 10 个单元</span>
      </div>
    </section>
  );
}
