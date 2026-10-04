import type {
  DecimalLike,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
} from "../../../api/contracts";
import {
  ProductCategoryFormalSelectionContext,
  ProductCategoryFormalTableMobileReadout,
} from "./ProductCategoryFormalTableReadouts";
import {
  formatProductCategoryForeignDisplayValue,
  formatProductCategoryRowDisplayValue,
  formatProductCategoryValue,
  formatProductCategoryYieldValue,
} from "./productCategoryPnlPageModel";

export type ProductCategoryFormalTableDisplayMode = "key" | "full";

type ProductCategoryFormalReportTableProps = {
  reportDate: string;
  selectedView: string;
  scenarioRatePct?: ProductCategoryPnlPayload["scenario_rate_pct"];
  rows: ProductCategoryPnlRow[];
  grandTotal?: ProductCategoryPnlRow | null;
  displayMode: ProductCategoryFormalTableDisplayMode;
  onDisplayModeChange: (mode: ProductCategoryFormalTableDisplayMode) => void;
  attribution: {
    contextAvailable: boolean;
    selectedCategoryId: string | null;
    categoryIds: ReadonlySet<string>;
    onOpenEvidence: (categoryId: string) => void;
  };
};

function formalValueToneClassName(
  value: DecimalLike | null | undefined,
): string {
  if (value === null || value === undefined) {
    return "product-category-formal-table__cell--neutral";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return "product-category-formal-table__cell--neutral";
  }
  if (parsed > 0) {
    return "product-category-formal-table__cell--positive";
  }
  if (parsed < 0) {
    return "product-category-formal-table__cell--negative";
  }
  return "product-category-formal-table__cell--neutral";
}

function formalCategoryIndentClassName(level: number): string {
  const clampedLevel = Math.min(Math.max(Math.trunc(level), 0), 8);
  return `product-category-formal-table__category-indent product-category-formal-table__category-indent--level-${clampedLevel}`;
}

export function ProductCategoryFormalReportTable({
  reportDate,
  selectedView,
  scenarioRatePct,
  rows,
  grandTotal,
  displayMode,
  onDisplayModeChange,
  attribution,
}: ProductCategoryFormalReportTableProps) {
  const selectedFormalRow =
    rows.find(
      (row) =>
        !row.is_total &&
        row.category_id === attribution.selectedCategoryId,
    ) ?? null;

  return (
    <>
      {selectedFormalRow ? (
        <ProductCategoryFormalSelectionContext
          reportDate={reportDate}
          selectedView={selectedView}
          sourceLabel={
            scenarioRatePct == null
              ? "正式基线归因定位"
              : `FTP ${String(scenarioRatePct)}% 场景（正式基线归因定位）`
          }
          row={selectedFormalRow}
          onOpenAttributionEvidence={
            attribution.contextAvailable
              ? attribution.onOpenEvidence
              : undefined
          }
        />
      ) : null}
      <ProductCategoryFormalTableMobileReadout
        reportDate={reportDate}
        selectedView={selectedView}
        selectedCategoryId={attribution.selectedCategoryId}
        grandTotal={grandTotal}
        rows={rows}
        onOpenAttributionEvidence={
          attribution.contextAvailable
            ? attribution.onOpenEvidence
            : undefined
        }
      />
      <div
        className="product-category-formal-table-controls"
        data-testid="product-category-formal-table-display-mode"
        role="group"
        aria-label="报表列展示"
      >
        <button
          type="button"
          aria-pressed={displayMode === "key"}
          className={`product-category-formal-table-controls__button ${
            displayMode === "key"
              ? "product-category-formal-table-controls__button--active"
              : ""
          }`}
          onClick={() => onDisplayModeChange("key")}
        >
          关键读数
        </button>
        <button
          type="button"
          aria-pressed={displayMode === "full"}
          className={`product-category-formal-table-controls__button ${
            displayMode === "full"
              ? "product-category-formal-table-controls__button--active"
              : ""
          }`}
          onClick={() => onDisplayModeChange("full")}
        >
          完整口径
        </button>
      </div>
      {displayMode === "full" ? (
        <p className="product-category-formal-table-scroll-hint">
          横向滚动查看完整字段，产品类别列保持可见。
        </p>
      ) : null}
      <div
        data-testid="product-category-formal-table-raw-grid"
        className="product-category-formal-table-wrap"
      >
        <table
          data-testid="product-category-table"
          className={`product-category-formal-table product-category-formal-table--${displayMode}`}
        >
          <colgroup>
            <col className="product-category-formal-table__col--category" />
            <col className="product-category-formal-table__col--scale" />
            {displayMode === "full" ? (
              <>
                <col className="product-category-formal-table__col--scale" />
                <col className="product-category-formal-table__col--scale-foreign" />
                <col className="product-category-formal-table__col--pnl" />
                <col className="product-category-formal-table__col--pnl" />
                <col className="product-category-formal-table__col--pnl-ftp" />
              </>
            ) : null}
            <col className="product-category-formal-table__col--pnl-net" />
            {displayMode === "full" ? (
              <>
                <col className="product-category-formal-table__col--pnl-foreign" />
                <col className="product-category-formal-table__col--pnl-ftp" />
              </>
            ) : null}
            <col className="product-category-formal-table__col--pnl-net" />
            <col className="product-category-formal-table__col--business-net" />
            <col className="product-category-formal-table__col--yield" />
          </colgroup>
          <thead>
            {displayMode === "key" ? (
              <>
                <tr className="product-category-formal-table__header-row">
                  <th
                    rowSpan={2}
                    className="product-category-formal-table__head product-category-formal-table__head--category"
                  >
                    产品类别
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--group">
                    规模日均
                  </th>
                  <th
                    colSpan={3}
                    className="product-category-formal-table__head product-category-formal-table__head--group"
                  >
                    净收入
                  </th>
                  <th
                    rowSpan={2}
                    className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--yield"
                  >
                    加权收益率
                  </th>
                </tr>
                <tr className="product-category-formal-table__header-row product-category-formal-table__header-row--metrics">
                  <th className="product-category-formal-table__head product-category-formal-table__head--number">
                    综本规模
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--group-start">
                    人民币净收入
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--number">
                    外币净收入
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--highlight">
                    营业净收入
                  </th>
                </tr>
              </>
            ) : (
              <>
                <tr className="product-category-formal-table__header-row">
                  <th
                    rowSpan={2}
                    className="product-category-formal-table__head product-category-formal-table__head--category"
                  >
                    产品类别
                  </th>
                  <th
                    colSpan={3}
                    className="product-category-formal-table__head product-category-formal-table__head--group"
                  >
                    规模日均
                  </th>
                  <th
                    colSpan={8}
                    className="product-category-formal-table__head product-category-formal-table__head--group"
                  >
                    损益
                  </th>
                  <th
                    rowSpan={2}
                    className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--yield"
                  >
                    加权收益率
                  </th>
                </tr>
                <tr className="product-category-formal-table__header-row product-category-formal-table__header-row--metrics">
                  <th className="product-category-formal-table__head product-category-formal-table__head--number">
                    综本
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--number">
                    人民币
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--number">
                    外币
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--group-start">
                    综本
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--number">
                    人民币
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--number">
                    人民币FTP
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--number">
                    人民币净收入
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--number">
                    外币
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--number">
                    外币FTP
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--number">
                    外币净收入
                  </th>
                  <th className="product-category-formal-table__head product-category-formal-table__head--number product-category-formal-table__head--highlight">
                    营业净收入
                  </th>
                </tr>
              </>
            )}
          </thead>
          <tbody>
            {rows.map((row) => {
              const isSelectedFormalRow =
                !row.is_total &&
                row.category_id === attribution.selectedCategoryId;
              const canOpenAttributionEvidence =
                !row.is_total &&
                attribution.categoryIds.has(row.category_id);
              return (
                <tr
                  data-selected={isSelectedFormalRow ? "true" : undefined}
                  data-row-level={row.level}
                  data-testid={`product-category-formal-row-${row.category_id}`}
                  id={`product-category-formal-row-${row.category_id}`}
                  key={row.category_id}
                  className={[
                    "product-category-formal-table__row",
                    row.is_total
                      ? "product-category-formal-table__row--total"
                      : "",
                    !row.is_total && row.level === 0
                      ? "product-category-formal-table__row--parent"
                      : "",
                    !row.is_total && row.level > 0
                      ? "product-category-formal-table__row--child"
                      : "",
                    isSelectedFormalRow
                      ? "product-category-formal-table__row--selected"
                      : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <td className="product-category-formal-table__cell product-category-formal-table__cell--category">
                    <div className={formalCategoryIndentClassName(row.level)}>
                      {canOpenAttributionEvidence ? (
                        <button
                          aria-label={`查看 ${row.category_name} 归因证据`}
                          aria-pressed={isSelectedFormalRow}
                          className="product-category-formal-table__category-button"
                          data-product-category-formal-row-action
                          onClick={() =>
                            attribution.onOpenEvidence(row.category_id)
                          }
                          type="button"
                        >
                          {row.category_name}
                        </button>
                      ) : (
                        <div>{row.category_name}</div>
                      )}
                    </div>
                  </td>
                  <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                    {formatProductCategoryRowDisplayValue(row, row.cnx_scale)}
                  </td>
                  {displayMode === "full" ? (
                    <>
                      <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                        {formatProductCategoryRowDisplayValue(
                          row,
                          row.cny_scale,
                        )}
                      </td>
                      <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                        {formatProductCategoryForeignDisplayValue(
                          row,
                          row.foreign_scale,
                        )}
                      </td>
                      <td className="product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--group-start">
                        {formatProductCategoryRowDisplayValue(
                          row,
                          row.cnx_cash,
                        )}
                      </td>
                      <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                        {formatProductCategoryRowDisplayValue(
                          row,
                          row.cny_cash,
                        )}
                      </td>
                      <td className="product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--ftp">
                        {formatProductCategoryRowDisplayValue(
                          row,
                          row.cny_ftp,
                        )}
                      </td>
                    </>
                  ) : null}
                  <td
                    className={[
                      "product-category-formal-table__cell product-category-formal-table__cell--number",
                      displayMode === "key"
                        ? "product-category-formal-table__cell--group-start"
                        : "",
                      formalValueToneClassName(row.cny_net),
                    ].join(" ")}
                  >
                    {formatProductCategoryValue(row.cny_net)}
                  </td>
                  {displayMode === "full" ? (
                    <>
                      <td className="product-category-formal-table__cell product-category-formal-table__cell--number">
                        {formatProductCategoryForeignDisplayValue(
                          row,
                          row.foreign_cash,
                        )}
                      </td>
                      <td className="product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--ftp">
                        {formatProductCategoryForeignDisplayValue(
                          row,
                          row.foreign_ftp,
                        )}
                      </td>
                    </>
                  ) : null}
                  <td
                    className={[
                      "product-category-formal-table__cell product-category-formal-table__cell--number",
                      formalValueToneClassName(row.foreign_net),
                    ].join(" ")}
                  >
                    {formatProductCategoryValue(row.foreign_net)}
                  </td>
                  <td
                    className={[
                      "product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--highlight",
                      formalValueToneClassName(row.business_net_income),
                    ].join(" ")}
                  >
                    {formatProductCategoryValue(row.business_net_income)}
                  </td>
                  <td className="product-category-formal-table__cell product-category-formal-table__cell--number product-category-formal-table__cell--yield">
                    {formatProductCategoryYieldValue(row.weighted_yield)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

