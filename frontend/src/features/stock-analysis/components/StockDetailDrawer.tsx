import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Drawer, Segmented, Typography } from "antd";
import type { EChartsOption } from "echarts";
import { useMemo, useState } from "react";

import { useApiClient } from "../../../api/client";
import type { LivermoreStockDetailCandle } from "../../../api/contracts";
import { BaseChart } from "../../../components/charts/BaseChart";
import { designTokens } from "../../../theme/designSystem";
import { stockAnalysisPageCssVars } from "../lib/stockAnalysisTokens";
import "./StockDetailDrawer.css";

const { Text } = Typography;

const LOOKBACK_CHOICES = [30, 60, 120] as const;

function buildCandleVolumeOption(candles: LivermoreStockDetailCandle[]): EChartsOption {
  const dates = candles.map((c) => c.trade_date);
  const ohlc: [number, number, number, number][] = candles.map((c) => {
    const o = c.open_value ?? 0;
    const cl = c.close_value ?? 0;
    const lo = c.low_value ?? 0;
    const hi = c.high_value ?? 0;
    return [o, cl, lo, hi];
  });
  const volumes = candles.map((c) => c.volume ?? 0);
  const up = designTokens.color.semantic.up;
  const down = designTokens.color.semantic.down;
  const muted = designTokens.color.neutral[600];
  const gridLine = designTokens.color.neutral[200];

  return {
    backgroundColor: "transparent",
    animation: false,
    textStyle: { color: muted, fontSize: 11 },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [
      { left: 52, right: 16, top: 28, height: "56%" },
      { left: 52, right: 16, top: "72%", height: "20%" },
    ],
    xAxis: [
      { type: "category", data: dates, gridIndex: 0, axisLabel: { show: false }, boundaryGap: true },
      { type: "category", data: dates, gridIndex: 1, boundaryGap: true },
    ],
    yAxis: [
      {
        type: "value",
        gridIndex: 0,
        scale: true,
        splitLine: { lineStyle: { color: gridLine, type: "dashed" } },
      },
      {
        type: "value",
        gridIndex: 1,
        scale: true,
        splitLine: { lineStyle: { color: gridLine, type: "dashed" } },
      },
    ],
    series: [
      {
        type: "candlestick",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ohlc,
        itemStyle: {
          color: down,
          color0: up,
          borderColor: down,
          borderColor0: up,
        },
      },
      {
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: { color: designTokens.color.neutral[400] },
      },
    ],
  };
}

function formatPePb(value: number | null): string {
  if (value == null || Number.isNaN(value)) return "待补";
  return value.toFixed(2);
}

function formatRoe(value: number | null): string {
  if (value == null || Number.isNaN(value)) return "待补";
  return `${(value * 100).toFixed(2)}%`;
}

function formatDividendYield(value: number | null): string {
  if (value == null || Number.isNaN(value)) return "待补";
  return `${(value * 100).toFixed(2)}%`;
}

export type StockDetailDrawerProps = {
  stockCode: string | null;
  stockName?: string;
  asOfDate?: string;
  onClose: () => void;
};

function formatChoiceNewsReceivedAt(iso: string): string {
  const t = iso.trim();
  if (t.length >= 16) return t.slice(0, 16).replace("T", " ");
  return t || "—";
}

function truncateChoiceNewsText(text: string | null, maxLen: number): string {
  if (text == null || text === "") return "—";
  const s = text.trim();
  if (s.length <= maxLen) return s;
  return `${s.slice(0, maxLen)}…`;
}

export function StockDetailDrawer({ stockCode, stockName, asOfDate, onClose }: StockDetailDrawerProps) {
  const client = useApiClient();
  const [lookback, setLookback] = useState<number>(60);

  const open = stockCode != null && stockCode.trim() !== "";

  const detailQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-stock-detail", stockCode, asOfDate ?? null, lookback] as const,
    queryFn: () =>
      client.getLivermoreStockDetail({
        stockCode: stockCode ?? "",
        asOfDate,
        lookback,
      }),
    enabled: open,
  });

  const choiceNewsQuery = useQuery({
    queryKey: ["stock-analysis", "choice-news-latest-global", open ? 10 : 0] as const,
    queryFn: () => client.getChoiceNewsEvents({ limit: 10, offset: 0 }),
    enabled: open,
  });

  const chartOption = useMemo(() => {
    const candles = detailQuery.data?.result?.candles ?? [];
    if (!candles.length) return { series: [] } as EChartsOption;
    return buildCandleVolumeOption(candles);
  }, [detailQuery.data?.result?.candles]);

  const factor = detailQuery.data?.result?.factor;
  const meta = detailQuery.data?.result_meta;

  return (
    <Drawer
      title="个股复核"
      placement="right"
      width={720}
      open={open}
      onClose={onClose}
      destroyOnClose
      className="stock-detail-drawer"
      data-testid="stock-detail-drawer"
      extra={
        <Button type="default" onClick={onClose} aria-label="关闭抽屉">
          关闭
        </Button>
      }
    >
      {open ? (
        <div className="stock-detail-drawer__body" style={stockAnalysisPageCssVars}>
          <header className="stock-detail-drawer__header">
            <div>
              <Text strong className="stock-detail-drawer__tabular">
                {stockCode}
              </Text>
              {stockName ? (
                <Text type="secondary" className="stock-detail-drawer__name">
                  {" "}
                  {stockName}
                </Text>
              ) : null}
              <div className="stock-detail-drawer__meta-line">
                <Text type="secondary">截至日 {asOfDate ?? detailQuery.data?.result?.as_of_date ?? "—"}</Text>
              </div>
            </div>
            <div className="stock-detail-drawer__lookback">
              <Text type="secondary">回看交易日</Text>
              <Segmented
                size="small"
                value={lookback}
                onChange={(v) => setLookback(Number(v))}
                options={LOOKBACK_CHOICES.map((n) => ({ label: String(n), value: n }))}
              />
            </div>
          </header>

          {detailQuery.isError ? (
            <Alert
              type="error"
              showIcon
              message="加载个股复核数据失败"
              description={detailQuery.error instanceof Error ? detailQuery.error.message : String(detailQuery.error)}
              data-testid="stock-detail-error"
            />
          ) : null}

          {detailQuery.isLoading && !detailQuery.isError ? (
            <p className="stock-detail-drawer__loading">加载中…</p>
          ) : null}

          {!detailQuery.isError ? (
            <section className="stock-detail-drawer__chart" aria-label="K 线与成交量" data-testid="stock-detail-chart">
              <Text strong>价格与成交量（复核）</Text>
              <BaseChart option={chartOption} height={360} loading={detailQuery.isLoading} />
            </section>
          ) : null}

          {!detailQuery.isError ? (
            <section className="stock-detail-drawer__factors" data-testid="stock-detail-factors">
              <Text strong>因子快照</Text>
              <div className="stock-detail-drawer__factor-grid">
                <div data-testid="stock-detail-factor-pe">
                  <div className="stock-detail-drawer__factor-label">PE</div>
                  <div className="stock-detail-drawer__factor-value stock-detail-drawer__tabular">
                    {formatPePb(factor?.pe ?? null)}
                  </div>
                </div>
                <div data-testid="stock-detail-factor-pb">
                  <div className="stock-detail-drawer__factor-label">PB</div>
                  <div className="stock-detail-drawer__factor-value stock-detail-drawer__tabular">
                    {formatPePb(factor?.pb ?? null)}
                  </div>
                </div>
                <div data-testid="stock-detail-factor-roe">
                  <div className="stock-detail-drawer__factor-label">ROE</div>
                  <div className="stock-detail-drawer__factor-value stock-detail-drawer__tabular">
                    {formatRoe(factor?.roe ?? null)}
                  </div>
                </div>
                <div data-testid="stock-detail-factor-dividend">
                  <div className="stock-detail-drawer__factor-label">股息率</div>
                  <div className="stock-detail-drawer__factor-value stock-detail-drawer__tabular">
                    {formatDividendYield(factor?.dividend_yield ?? null)}
                  </div>
                </div>
              </div>
            </section>
          ) : null}

          {!detailQuery.isError ? (
            <section className="stock-detail-drawer__market-events" aria-label="市场最近事件" data-testid="stock-detail-market-events">
              <Text strong>市场最近事件</Text>
              <div
                className="stock-detail-drawer__market-events-banner"
                role="note"
                data-testid="stock-detail-market-events-banner"
              >
                当前为全市场最新事件，未按本股过滤（按股过滤需后端补 payload 解析）
              </div>
              {choiceNewsQuery.isLoading ? (
                <p className="stock-detail-drawer__market-events-loading" data-testid="stock-detail-market-events-loading">
                  市场事件加载中…
                </p>
              ) : null}
              {choiceNewsQuery.isError ? (
                <Alert
                  type="warning"
                  showIcon
                  message="市场事件加载失败"
                  description={
                    choiceNewsQuery.error instanceof Error
                      ? choiceNewsQuery.error.message
                      : String(choiceNewsQuery.error)
                  }
                  data-testid="stock-detail-market-events-error"
                />
              ) : null}
              {choiceNewsQuery.isSuccess && !choiceNewsQuery.data?.result?.events?.length ? (
                <p className="stock-detail-drawer__market-events-empty" data-testid="stock-detail-market-events-empty">
                  暂无市场事件数据（或库表尚无写入）
                </p>
              ) : null}
              {choiceNewsQuery.isSuccess && (choiceNewsQuery.data?.result?.events?.length ?? 0) > 0 ? (
                <ul className="stock-detail-drawer__market-events-list" data-testid="stock-detail-market-events-list">
                  {(choiceNewsQuery.data?.result?.events ?? []).map((ev) => (
                    <li key={ev.event_key} className="stock-detail-drawer__market-events-item">
                      <span className="stock-detail-drawer__market-events-time stock-detail-drawer__tabular">
                        {formatChoiceNewsReceivedAt(ev.received_at)}
                      </span>
                      <span className="stock-detail-drawer__market-events-topic">{ev.topic_code}</span>
                      <span className="stock-detail-drawer__market-events-text">
                        {truncateChoiceNewsText(ev.payload_text, 100)}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}

          {!detailQuery.isError && meta ? (
            <footer className="stock-detail-drawer__footer-meta" data-testid="stock-detail-footer-meta">
              <Text type="secondary">
                source_version {meta.source_version} · rule_version {meta.rule_version} · quality_flag{" "}
                {meta.quality_flag} · vendor_status {meta.vendor_status}
              </Text>
            </footer>
          ) : null}
        </div>
      ) : null}
    </Drawer>
  );
}
