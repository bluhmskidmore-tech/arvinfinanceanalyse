import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ProductCategoryManualAdjustmentRequest } from "../../../api/contracts";
import { ProductCategoryManualAdjustmentForm } from "./ProductCategoryManualAdjustmentForm";

function formProps() {
  const draft: ProductCategoryManualAdjustmentRequest = {
    report_date: "2026-02-28",
    operator: "DELTA",
    approval_status: "approved",
    account_code: "13304010001",
    currency: "CNX",
    account_name: "测试科目",
    beginning_balance: "1",
    ending_balance: "1",
    monthly_pnl: "1",
    daily_avg_balance: "1",
    annual_avg_balance: "1",
  };
  return {
    draft,
    editing: false,
    isSubmitting: false,
    error: null as string | null,
    onFieldChange: vi.fn(),
    onSubmit: vi.fn(),
    onCancel: vi.fn(),
  };
}

describe("ProductCategoryManualAdjustmentForm", () => {
  it("keeps all amount edits as strings and reports cleared amounts as null", () => {
    const props = formProps();
    render(<ProductCategoryManualAdjustmentForm {...props} />);

    const exactAmount = "-9007199254740993.001200";
    for (const [field, label] of [
      ["beginning_balance", "期初余额"],
      ["ending_balance", "期末余额"],
      ["monthly_pnl", "月度损益"],
      ["daily_avg_balance", "月日均"],
      ["annual_avg_balance", "年日均"],
    ]) {
      const input = screen.getByRole("textbox", { name: `手工录入-${label}` });
      fireEvent.change(input, { target: { value: exactAmount } });
      expect(props.onFieldChange).toHaveBeenLastCalledWith(field, exactAmount);

      fireEvent.change(input, { target: { value: "0" } });
      expect(props.onFieldChange).toHaveBeenLastCalledWith(field, "0");

      fireEvent.change(input, { target: { value: "" } });
      expect(props.onFieldChange).toHaveBeenLastCalledWith(field, null);
    }
  });

  it("keeps the report date read-only and delegates account and selection edits", async () => {
    const user = userEvent.setup();
    const props = formProps();
    render(<ProductCategoryManualAdjustmentForm {...props} />);

    const date = screen.getByRole("textbox", { name: "手工录入-报表日期" });
    expect(date).toHaveValue("2026-02-28");
    expect(date).toHaveAttribute("readonly");
    await user.type(date, "2026-03-31");
    expect(props.onFieldChange).not.toHaveBeenCalled();

    for (const [label, value, field] of [
      ["操作方式", "OVERRIDE", "operator"],
      ["币种", "CNY", "currency"],
      ["审批状态", "pending", "approval_status"],
    ]) {
      await user.selectOptions(
        screen.getByRole("combobox", { name: `手工录入-${label}` }),
        value!,
      );
      expect(props.onFieldChange).toHaveBeenLastCalledWith(field, value);
    }
    fireEvent.change(screen.getByRole("textbox", { name: "手工录入-科目代码" }), {
      target: { value: "001234" },
    });
    expect(props.onFieldChange).toHaveBeenLastCalledWith("account_code", "001234");
    fireEvent.change(screen.getByRole("textbox", { name: "手工录入-科目名称" }), {
      target: { value: "更新科目" },
    });
    expect(props.onFieldChange).toHaveBeenLastCalledWith("account_name", "更新科目");
  });

  it("reflects parent submission and error state without duplicating submit or cancel actions", async () => {
    const user = userEvent.setup();
    const props = formProps();
    const { rerender } = render(<ProductCategoryManualAdjustmentForm {...props} />);

    await user.click(screen.getByRole("button", { name: "提交并刷新" }));
    expect(props.onSubmit).toHaveBeenCalledTimes(1);
    rerender(<ProductCategoryManualAdjustmentForm {...props} editing />);
    expect(screen.getByText("编辑手工录入")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存并刷新" })).toBeEnabled();

    rerender(<ProductCategoryManualAdjustmentForm {...props} editing isSubmitting />);
    const submitting = screen.getByRole("button", { name: "提交中..." });
    expect(submitting).toBeDisabled();
    await user.click(submitting);
    expect(props.onSubmit).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(props.onCancel).toHaveBeenCalledTimes(1);

    rerender(
      <ProductCategoryManualAdjustmentForm {...props} editing error="手工录入失败" />,
    );
    expect(screen.getByTestId("product-category-manual-error")).toHaveTextContent(
      "手工录入失败",
    );
    expect(screen.getByRole("button", { name: "保存并刷新" })).toBeEnabled();
  });
});
