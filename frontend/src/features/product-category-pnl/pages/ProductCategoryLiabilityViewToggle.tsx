export type ProductCategoryLiabilityView = "monthly" | "ytd";

type ProductCategoryLiabilityViewToggleProps = {
  ariaLabel: string;
  className?: string;
  testId: string;
  value: ProductCategoryLiabilityView;
  onChange: (value: ProductCategoryLiabilityView) => void;
};

export function ProductCategoryLiabilityViewToggle({
  ariaLabel,
  className = "",
  testId,
  value,
  onChange,
}: ProductCategoryLiabilityViewToggleProps) {
  return (
    <div
      className={`product-category-formal-table-controls ${className}`.trim()}
      data-testid={testId}
      role="group"
      aria-label={ariaLabel}
    >
      {([
        ["ytd", "累进值"],
        ["monthly", "单月值"],
      ] as const).map(([option, label]) => (
        <button
          key={option}
          type="button"
          aria-pressed={value === option}
          className={`product-category-formal-table-controls__button ${
            value === option
              ? "product-category-formal-table-controls__button--active"
              : ""
          }`}
          onClick={() => onChange(option)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
