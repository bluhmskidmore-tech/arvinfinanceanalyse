import type { ProductCategoryDiagnosticsSurface } from "./productCategoryPnlPageModel";

function diagnosticsToneClassName(
  tone: "neutral" | "positive" | "negative",
): string {
  if (tone === "positive") {
    return "product-category-diagnostics__value--positive";
  }
  if (tone === "negative") {
    return "product-category-diagnostics__value--negative";
  }
  return "";
}

export function ProductCategoryDiagnosticsPanel({
  surface,
}: {
  surface: ProductCategoryDiagnosticsSurface;
}) {
  return (
  <div
    className="product-category-diagnostics"
    data-testid="product-category-diagnostics-surface"
  >
    <article
      className="product-category-diagnostics__card"
      data-testid="product-category-diagnostics-matrix"
    >
      <div className="product-category-diagnostics__header">
        <div className="product-category-diagnostics__intro">
          <h3 className="product-category-diagnostics__title">
            产品经营诊断矩阵
          </h3>
          <p className="product-category-diagnostics__description">
            逐行回看规模、营业净收入、收益率和双币净收入拆分，行身份仅取自
            `category_id/category_name/side`。
          </p>
        </div>
        {surface.headlineTotalLabel ? (
          <span
            className="product-category-diagnostics__summary"
            data-testid="product-category-diagnostics-summary"
          >
            当前FTP后经营净收入 {surface.headlineTotalLabel}
          </span>
        ) : null}
      </div>
      {surface.matrixEmptyCopy ? (
        <div
          data-testid="product-category-diagnostics-matrix-empty"
          className="product-category-diagnostics__empty"
        >
          {surface.matrixEmptyCopy}
        </div>
      ) : (
        <div className="product-category-diagnostics__table-wrap">
          <table className="product-category-diagnostics__table">
            <thead>
              <tr>
                <th className="product-category-diagnostics__table-head">
                  产品行
                </th>
                <th className="product-category-diagnostics__table-head">
                  端别
                </th>
                <th className="product-category-diagnostics__table-head">
                  规模
                </th>
                <th className="product-category-diagnostics__table-head">
                  营业净收入
                </th>
                <th className="product-category-diagnostics__table-head">
                  收益率
                </th>
                <th className="product-category-diagnostics__table-head">
                  人民币净收入
                </th>
                <th className="product-category-diagnostics__table-head">
                  外币净收入
                </th>
                <th className="product-category-diagnostics__table-head">
                  驱动提示
                </th>
              </tr>
            </thead>
            <tbody>
              {surface.matrixRows.map((item) => (
                <tr key={item.categoryId}>
                  <td className="product-category-diagnostics__table-cell">
                    {item.categoryLabel}
                  </td>
                  <td className="product-category-diagnostics__table-cell">
                    {item.sideLabel}
                  </td>
                  <td className="product-category-diagnostics__table-cell">
                    {item.scaleLabel}
                  </td>
                  <td
                    className={`product-category-diagnostics__table-cell ${diagnosticsToneClassName(item.businessNetIncomeTone)}`}
                  >
                    {item.businessNetIncomeLabel}
                  </td>
                  <td className="product-category-diagnostics__table-cell">
                    {item.yieldLabel}
                  </td>
                  <td
                    className={`product-category-diagnostics__table-cell ${diagnosticsToneClassName(item.cnyNetTone)}`}
                  >
                    {item.cnyNetLabel}
                  </td>
                  <td
                    className={`product-category-diagnostics__table-cell ${diagnosticsToneClassName(item.foreignNetTone)}`}
                  >
                    {item.foreignNetLabel}
                  </td>
                  <td className="product-category-diagnostics__table-cell">
                    {item.driverHint}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>

    <article
      className="product-category-diagnostics__card"
      data-testid="product-category-diagnostics-watchlist"
    >
      <div className="product-category-diagnostics__intro">
        <h3 className="product-category-diagnostics__title">
          负贡献观察名单
        </h3>
        <p className="product-category-diagnostics__description">
          仅列出 `business_net_income &lt; 0`
          的行，并按亏损幅度排序；缺失规模或收益率会显式标注。
        </p>
      </div>
      {surface.negativeWatchlistEmptyCopy ? (
        <div
          data-testid="product-category-diagnostics-watchlist-empty"
          className="product-category-diagnostics__empty"
        >
          {surface.negativeWatchlistEmptyCopy}
        </div>
      ) : (
        <div className="product-category-diagnostics__watchlist">
          {surface.negativeWatchlistRows.map((item) => (
            <div
              key={item.categoryId}
              className="product-category-diagnostics__watchlist-row"
              data-testid={`product-category-diagnostics-watchlist-row-${item.categoryId}`}
            >
              <div className="product-category-diagnostics__watchlist-primary">
                <div className="product-category-diagnostics__metric-value product-category-diagnostics__metric-value--primary">
                  {item.categoryLabel}
                </div>
                <div className="product-category-diagnostics__metric-detail">
                  {item.sideLabel}
                </div>
              </div>
              <div className="product-category-diagnostics__metric">
                <span className="product-category-diagnostics__metric-label">
                  亏损
                </span>
                <span className="product-category-diagnostics__metric-value product-category-diagnostics__value--negative">
                  {item.lossLabel}
                </span>
              </div>
              <div className="product-category-diagnostics__metric">
                <span className="product-category-diagnostics__metric-label">
                  规模
                </span>
                <span className="product-category-diagnostics__metric-value">
                  {item.scaleLabel}
                </span>
              </div>
              <div className="product-category-diagnostics__metric">
                <span className="product-category-diagnostics__metric-label">
                  收益率
                </span>
                <span className="product-category-diagnostics__metric-value">
                  {item.yieldLabel}
                </span>
              </div>
              <div className="product-category-diagnostics__metric">
                <span className="product-category-diagnostics__metric-label">
                  缺口提示
                </span>
                <span className="product-category-diagnostics__metric-value">
                  {[
                    item.scaleMissing ? "规模缺失" : null,
                    item.yieldMissing ? "收益率缺失" : null,
                  ]
                    .filter(Boolean)
                    .join(" / ") || "字段齐全"}
                </span>
              </div>
              <div className="product-category-diagnostics__metric">
                <span className="product-category-diagnostics__metric-label">
                  驱动提示
                </span>
                <span className="product-category-diagnostics__metric-detail">
                  {item.driverHint}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </article>

    <article
      className="product-category-diagnostics__card"
      data-testid="product-category-diagnostics-spread"
    >
      <div className="product-category-diagnostics__intro">
        <h3 className="product-category-diagnostics__title">
          利差变动归因
        </h3>
        <p className="product-category-diagnostics__description">
          使用后端返回的资产收益率、负债收益率和利差字段；字段缺失时保留缺口提示。
        </p>
      </div>
      <div className="product-category-diagnostics__spread-grid">
        <div className="product-category-diagnostics__spread-card">
          <span className="product-category-diagnostics__spread-caption">
            {surface.spreadAttribution.currentLabel}
          </span>
          <span className="product-category-diagnostics__spread-value">
            {
              surface.spreadAttribution
                .currentSpreadLabel
            }
          </span>
          <span className="product-category-diagnostics__spread-detail">
            资产{" "}
            {
              surface.spreadAttribution
                .currentAssetYieldLabel
            }{" "}
            / 负债{" "}
            {
              surface.spreadAttribution
                .currentLiabilityYieldLabel
            }
          </span>
        </div>
        <div className="product-category-diagnostics__spread-card">
          <span className="product-category-diagnostics__spread-caption">
            {surface.spreadAttribution.priorLabel}
          </span>
          <span className="product-category-diagnostics__spread-value">
            {surface.spreadAttribution.priorSpreadLabel}
          </span>
          <span className="product-category-diagnostics__spread-detail">
            资产变动{" "}
            {
              surface.spreadAttribution
                .assetYieldDeltaLabel
            }{" "}
            / 负债变动{" "}
            {
              surface.spreadAttribution
                .liabilityYieldDeltaLabel
            }
          </span>
        </div>
        <div className="product-category-diagnostics__spread-card">
          <span className="product-category-diagnostics__spread-caption">
            归因结论
          </span>
          <span className="product-category-diagnostics__spread-value">
            {surface.spreadAttribution.spreadDeltaLabel}
          </span>
          <span className="product-category-diagnostics__spread-detail">
            {surface.spreadAttribution.driverHint}
          </span>
        </div>
      </div>
      {surface.spreadAttribution.state ===
      "incomplete" ? (
        <div
          data-testid="product-category-diagnostics-spread-incomplete"
          className="product-category-diagnostics__empty"
        >
          {surface.spreadAttribution.reason}
        </div>
      ) : null}
    </article>
  </div>
  );
}

