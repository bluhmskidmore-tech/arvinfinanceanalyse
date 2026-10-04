export function ProductCategoryPublicationHeader(props: {
  focus: "attribution" | "overview";
}) {
  return (
    <div
      className="product-category-publication-header"
      aria-label="论文投稿展示说明"
    >
      <div className="product-category-publication-header__brand">
        <span className="product-category-publication-header__mark">M</span>
        <span>
          <strong>MOSS 金融决策分析平台</strong>
          <small>产品分类损益与经营分析工作台</small>
        </span>
      </div>
      <div className="product-category-publication-header__context">
        <span>仿真数据</span>
        <strong>
          {props.focus === "attribution"
            ? "差异归因与证据复核"
            : "经营结果与利差总览"}
        </strong>
        <small>仅用于展示系统结构与业务流程，不构成正式经营结论</small>
      </div>
    </div>
  );
}
