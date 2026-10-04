import type { ProductCategoryManualAdjustmentRequest } from "../../../api/contracts";

type ProductCategoryManualAdjustmentFormProps = {
  draft: ProductCategoryManualAdjustmentRequest;
  editing: boolean;
  isSubmitting: boolean;
  error: string | null;
  onFieldChange: <K extends keyof ProductCategoryManualAdjustmentRequest>(
    key: K,
    value: ProductCategoryManualAdjustmentRequest[K],
  ) => void;
  onSubmit: () => void;
  onCancel: () => void;
};

const AMOUNT_FIELDS = [
  ["beginning_balance", "期初余额"],
  ["ending_balance", "期末余额"],
  ["monthly_pnl", "月度损益"],
  ["daily_avg_balance", "月日均"],
  ["annual_avg_balance", "年日均"],
] as const;

export function ProductCategoryManualAdjustmentForm({
  draft,
  editing,
  isSubmitting,
  error,
  onFieldChange,
  onSubmit,
  onCancel,
}: ProductCategoryManualAdjustmentFormProps) {
  return (
    <div
      id="product-category-manual-adjustment-form"
      data-testid="product-category-manual-form"
      className="product-category-manual-form"
    >
      <div className="product-category-manual-form__title">
        {editing ? "编辑手工录入" : "手工录入"}
      </div>
      <div className="product-category-manual-form__grid">
        <label className="product-category-manual-form__field">
          报表日期
          <input
            aria-label="手工录入-报表日期"
            value={draft.report_date}
            readOnly
          />
        </label>
        <label className="product-category-manual-form__field">
          操作方式
          <select
            aria-label="手工录入-操作方式"
            value={draft.operator}
            onChange={(event) =>
              onFieldChange(
                "operator",
                event.target.value as "ADD" | "DELTA" | "OVERRIDE",
              )
            }
          >
            <option value="ADD">新增</option>
            <option value="DELTA">差额调整</option>
            <option value="OVERRIDE">覆盖</option>
          </select>
        </label>
        <label className="product-category-manual-form__field">
          币种
          <select
            aria-label="手工录入-币种"
            value={draft.currency}
            onChange={(event) =>
              onFieldChange("currency", event.target.value as "CNX" | "CNY")
            }
          >
            <option value="CNX">CNX</option>
            <option value="CNY">CNY</option>
          </select>
        </label>
        <label className="product-category-manual-form__field">
          科目代码
          <input
            aria-label="手工录入-科目代码"
            value={draft.account_code}
            onChange={(event) =>
              onFieldChange("account_code", event.target.value)
            }
          />
        </label>
        <label className="product-category-manual-form__field">
          科目名称
          <input
            aria-label="手工录入-科目名称"
            value={draft.account_name ?? ""}
            onChange={(event) =>
              onFieldChange("account_name", event.target.value)
            }
          />
        </label>
        <label className="product-category-manual-form__field">
          审批状态
          <select
            aria-label="手工录入-审批状态"
            value={draft.approval_status}
            onChange={(event) =>
              onFieldChange(
                "approval_status",
                event.target.value as "approved" | "pending" | "rejected",
              )
            }
          >
            <option value="approved">已通过</option>
            <option value="pending">待审批</option>
            <option value="rejected">已拒绝</option>
          </select>
        </label>
        {AMOUNT_FIELDS.map(([field, label]) => (
          <label key={field} className="product-category-manual-form__field">
            {label}
            <input
              aria-label={`手工录入-${label}`}
              value={draft[field] ?? ""}
              onChange={(event) =>
                onFieldChange(field, event.target.value || null)
              }
            />
          </label>
        ))}
      </div>
      {error ? (
        <div
          data-testid="product-category-manual-error"
          className="product-category-manual-form__error"
        >
          {error}
        </div>
      ) : null}
      <div className="product-category-manual-form__actions">
        <button
          type="button"
          data-testid="product-category-manual-submit"
          onClick={onSubmit}
          disabled={isSubmitting}
        >
          {isSubmitting
            ? "提交中..."
            : editing
              ? "保存并刷新"
              : "提交并刷新"}
        </button>
        <button type="button" onClick={onCancel}>
          取消
        </button>
      </div>
    </div>
  );
}
