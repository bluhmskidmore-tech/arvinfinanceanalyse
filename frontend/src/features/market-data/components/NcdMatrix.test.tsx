import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { NcdFundingProxyPayload } from "../../../api/contracts";
import { NcdMatrix } from "./NcdMatrix";

const ncdProxyPayload: NcdFundingProxyPayload = {
  as_of_date: "2026-06-09",
  proxy_label: "Choice/Tushare Shibor funding proxy",
  is_actual_ncd_matrix: false,
  formal_ncd_matrix_status: {
    status: "blocked",
    required_shape: "tenor_rating_matrix",
    current_proxy_basis: "shibor_funding_proxy",
    choice_status: "shibor_landed; formal_ncd_matrix_unconfirmed",
    tushare_status: "shibor_landed; formal_ncd_matrix_unconfirmed",
    missing_requirements: ["governed NCD tenor-rating source contract"],
  },
  rows: [
    {
      row_key: "shibor_fixing",
      label: "Shibor fixing",
      "1M": 1.427,
      "3M": 1.4144,
      "6M": 1.4299,
      "9M": 1.45,
      "1Y": 1.43,
      quote_count: null,
    },
  ],
  warnings: ["Proxy only; not actual NCD issuance matrix."],
};

describe("NcdMatrix", () => {
  it("keeps proxy status explicit and does not present the table as a formal NCD matrix", async () => {
    render(<NcdMatrix payload={ncdProxyPayload} showResultMeta={false} embedded />);

    const panel = await screen.findByTestId("market-data-ncd-matrix");
    expect(within(panel).getByText(/Choice\/Tushare Shibor funding proxy/)).toBeInTheDocument();
    expect(within(panel).getByText(/代理口径，非正式发行矩阵/)).toBeInTheDocument();
    expect(within(panel).getByText("Shibor fixing")).toBeInTheDocument();
    expect(within(panel).getByText("1.427")).toBeInTheDocument();
    expect(panel).not.toHaveTextContent("formal NCD matrix");
  });

  it("drops the heatmap view for single-row matrices (no comparison dimension)", async () => {
    render(<NcdMatrix payload={ncdProxyPayload} showResultMeta={false} embedded />);

    const panel = await screen.findByTestId("market-data-ncd-matrix");
    expect(within(panel).queryByTestId("market-data-ncd-view-toggle")).not.toBeInTheDocument();
    expect(panel).not.toHaveTextContent("矩阵热力");
    // 表格形态保留。
    expect(within(panel).getByText("Shibor fixing")).toBeInTheDocument();
  });

  it("keeps the view toggle and heatmap for matrices with at least two rows", async () => {
    const payload: NcdFundingProxyPayload = {
      ...ncdProxyPayload,
      rows: [
        ...ncdProxyPayload.rows,
        {
          row_key: "ncd_aaa",
          label: "NCD AAA",
          "1M": 1.5,
          "3M": 1.52,
          "6M": 1.55,
          "9M": 1.58,
          "1Y": 1.6,
          quote_count: 12,
        },
      ],
    };
    render(<NcdMatrix payload={payload} showResultMeta={false} embedded />);

    const panel = await screen.findByTestId("market-data-ncd-matrix");
    expect(within(panel).getByTestId("market-data-ncd-view-toggle")).toBeInTheDocument();
  });

  it("translates known English proxy warnings and keeps the original text in title", async () => {
    const payload: NcdFundingProxyPayload = {
      ...ncdProxyPayload,
      warnings: ["Using landed Tushare Shibor; quote medians unavailable."],
    };
    render(<NcdMatrix payload={payload} showResultMeta={false} embedded />);

    const warning = await screen.findByText("使用已接入的 Tushare Shibor；报价中位数不可用。");
    expect(warning).toHaveAttribute(
      "title",
      "Using landed Tushare Shibor; quote medians unavailable.",
    );
  });
});
