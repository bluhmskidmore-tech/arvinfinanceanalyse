import { useMemo } from "react";
import { Button, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { NcdFundingProxyPayload, ResultMeta } from "../../../api/contracts";
import { designTokens } from "../../../theme/designSystem";
import { LiveResultMetaStrip } from "./LiveResultMetaStrip";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

const TENORS = ["1M", "3M", "6M", "9M", "1Y"] as const;

type MatrixRow = Record<"rating" | (typeof TENORS)[number], string | number | null> & {
  key: string;
  quoteCount?: string | null;
};

function formatProxyCell(value: number | string | null | undefined) {
  if (value == null || value === "") {
    return "—";
  }
  if (typeof value === "number") {
    return value.toFixed(3);
  }
  return value;
}

export function NcdMatrix({
  payload,
  resultMeta,
  isLoading = false,
  isError = false,
  onRetry,
}: {
  payload?: NcdFundingProxyPayload;
  resultMeta?: ResultMeta;
  isLoading?: boolean;
  isError?: boolean;
  onRetry?: () => void;
}) {
  const columns: ColumnsType<MatrixRow> = useMemo(
    () => [
      { title: "口径/期限", dataIndex: "rating", key: "rating", fixed: "left", width: 132 },
      ...TENORS.map((t) => ({
        title: t,
        dataIndex: t,
        key: t,
        align: "right" as const,
        width: 72,
        render: (value: number | string | null | undefined) => formatProxyCell(value),
      })),
      {
        title: "样本数",
        dataIndex: "quoteCount",
        key: "quoteCount",
        align: "right" as const,
        width: 84,
      },
    ],
    [],
  );

  const dataSource = useMemo<MatrixRow[]>(
    () =>
      (payload?.rows ?? []).map((row) => ({
        key: row.row_key,
        rating: row.label,
        "1M": row["1M"],
        "3M": row["3M"],
        "6M": row["6M"],
        "9M": row["9M"],
        "1Y": row["1Y"],
        quoteCount: row.quote_count == null ? null : String(row.quote_count),
      })),
    [payload?.rows],
  );

  return (
    <section data-testid="market-data-ncd-matrix" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>同业存单</h2>
      <Space direction="vertical" size={4}>
        <Typography.Text type="secondary">
          {payload?.proxy_label ?? "Tushare Shibor funding proxy"}
        </Typography.Text>
        <Typography.Text type="secondary">
          当前展示的是资金利率 proxy，不是实际同业存单期限×评级矩阵。
          {payload?.as_of_date ? ` 截至 ${payload.as_of_date}。` : ""}
        </Typography.Text>
      </Space>
      <LiveResultMetaStrip
        lead="同业存单 proxy 读面"
        meta={resultMeta}
        testId="market-data-ncd-live-meta"
      />
      {payload?.warnings?.length ? (
        <div
          style={{
            marginBottom: designTokens.space[3],
            color: designTokens.color.warning[700],
            fontSize: designTokens.fontSize[12],
            lineHeight: designTokens.lineHeight.normal,
          }}
        >
          {payload.warnings.join(" ")}
        </div>
      ) : null}
      {isError ? (
        <div
          style={{
            display: "grid",
            gap: designTokens.space[3],
            marginBottom: designTokens.space[3],
          }}
        >
          <div
            style={{
              color: designTokens.color.danger[600],
              fontSize: designTokens.fontSize[12],
            }}
          >
            同业存单 proxy 读面失败。
          </div>
          {onRetry ? (
            <Button size="small" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      ) : null}
      <Table<MatrixRow>
        size="small"
        loading={isLoading}
        pagination={false}
        columns={columns}
        dataSource={dataSource}
        rowKey="key"
        scroll={{ x: true }}
        locale={{
          emptyText: "当前未返回存单 proxy 数据。",
        }}
      />
    </section>
  );
}
