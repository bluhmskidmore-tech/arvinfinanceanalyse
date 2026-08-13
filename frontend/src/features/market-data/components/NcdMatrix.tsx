import { useMemo, useState } from "react";
import { Button, Segmented, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { NcdFundingProxyPayload, ResultMeta } from "../../../api/contracts";
import { designTokens } from "../../../theme/designSystem";
import { isMarketDataNarrowViewport } from "../lib/useMarketDataNarrowViewport";
import { LiveResultMetaStrip } from "./LiveResultMetaStrip";
import { MarketDataNcdHeatmap } from "./MarketDataNcdHeatmap";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

function readInitialNcdViewMode(): "both" | "table" | "heatmap" {
  if (typeof window === "undefined") {
    return "both";
  }
  if (isMarketDataNarrowViewport()) {
    return "table";
  }
  return "both";
}

const TENORS = ["1M", "3M", "6M", "9M", "1Y"] as const;

type MatrixRow = Record<"rating" | (typeof TENORS)[number], string | number | null> & {
  key: string;
  quoteCount?: string | null;
};

function NcdNumericCell({ value }: { value: number | string | null | undefined }) {
  return <span className="market-data-ncd-matrix__num">{formatProxyCell(value)}</span>;
}

function formatProxyCell(value: number | string | null | undefined) {
  if (value == null || value === "") {
    return "—";
  }
  if (typeof value === "number") {
    return value.toFixed(3);
  }
  return value;
}

function formatNcdWarning(value: string): string {
  const fallbackMatch = value.match(
    /^Using landed Choice Shibor with Tushare fallback for (.+); fallback date ([^;]+); quote medians unavailable\.$/,
  );
  if (fallbackMatch) {
    return `使用已接入的 Choice Shibor，并以 Tushare 回退补 ${fallbackMatch[1]}；回退日期 ${fallbackMatch[2]}；报价中位数不可用。`;
  }
  if (value === "Proxy only; not actual NCD issuance matrix.") {
    return "仅代理口径；不是真实存单发行矩阵。";
  }
  return value;
}

export function NcdMatrix({
  payload,
  resultMeta,
  isLoading = false,
  isError = false,
  showResultMeta = true,
  onRetry,
  embedded = false,
}: {
  payload?: NcdFundingProxyPayload;
  resultMeta?: ResultMeta;
  isLoading?: boolean;
  isError?: boolean;
  showResultMeta?: boolean;
  onRetry?: () => void;
  embedded?: boolean;
}) {
  const [viewMode, setViewMode] = useState<"both" | "table" | "heatmap">(readInitialNcdViewMode);
  const columns: ColumnsType<MatrixRow> = useMemo(
    () => [
      { title: "口径/期限", dataIndex: "rating", key: "rating", fixed: "left", width: 108 },
      ...TENORS.map((t) => ({
        title: t,
        dataIndex: t,
        key: t,
        align: "right" as const,
        width: 58,
        render: (value: number | string | null | undefined) => <NcdNumericCell value={value} />,
      })),
      {
        title: "样本数",
        dataIndex: "quoteCount",
        key: "quoteCount",
        align: "right" as const,
        width: 64,
        render: (value: string | null | undefined) => <NcdNumericCell value={value} />,
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

  const hasRows = dataSource.length > 0;
  // 0 行成功态收缩为一句话空态（DESIGN §6），不再渲染空表格与空热力占满等高格。
  const hasBody = hasRows || isLoading;

  return (
    <section
      data-testid="market-data-ncd-matrix"
      className={embedded ? "market-data-terminal-embedded" : "market-data-terminal-panel"}
      style={embedded ? undefined : marketDataPanelStyle}
    >
      {!embedded ? <h2 style={marketDataBlockTitleStyle}>同业存单</h2> : null}
      <div className="market-data-ncd-head">
        <p className="market-data-ncd-proxy-note">
          {payload?.proxy_label ?? "Shibor 资金 proxy"}
          {payload?.is_actual_ncd_matrix === false ? " · proxy 非正式发行矩阵" : ""}
          {payload?.as_of_date ? ` · 截至 ${payload.as_of_date}` : ""}
        </p>
        <Segmented
          size="small"
          value={viewMode}
          onChange={(value) => setViewMode(value as "both" | "table" | "heatmap")}
          options={[
            { label: "并列", value: "both" },
            { label: "表格", value: "table" },
            { label: "热力", value: "heatmap" },
          ]}
          data-testid="market-data-ncd-view-toggle"
        />
      </div>
      {showResultMeta ? (
        <LiveResultMetaStrip
          lead="同业存单 proxy 读面"
          meta={resultMeta}
          testId="market-data-ncd-live-meta"
        />
      ) : null}
      {payload?.warnings?.length ? (
        <div className="market-data-ncd-proxy-warning">
          {payload.warnings.map(formatNcdWarning).join(" ")}
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
              color: "var(--dh-api-red)",
              fontSize: designTokens.fontSize[12],
            }}
          >
            同业存单 proxy 读面失败。
          </div>
          {onRetry ? (
            <Button size="small" onClick={onRetry}>
              重试
            </Button>
          ) : null}
        </div>
      ) : null}
      {!isLoading && !isError && !hasRows ? (
        <div data-testid="market-data-ncd-empty" className="market-data-terminal-empty">
          当前未返回存单 proxy 数据。
        </div>
      ) : null}
      {hasBody && (viewMode === "both" || viewMode === "table") ? (
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
      ) : null}
      {hasBody && (viewMode === "both" || viewMode === "heatmap") ? (
        <div className="market-data-rate-quote-chart-block">
          {viewMode === "both" ? <h3 className="market-data-chart-block-title">矩阵热力</h3> : null}
          <MarketDataNcdHeatmap
            payload={payload}
            isLoading={isLoading}
            isError={isError}
            onRetry={onRetry}
          />
        </div>
      ) : null}
    </section>
  );
}
