import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
} from "@ant-design/icons";
import { Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";

import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitIndicator,
} from "../../../api/macroToolkitClient";
import { PageSectionLead } from "../../../components/page/PagePrimitives";
import { EM_DASH } from "../../../utils/format";
import { formatValue } from "../lib/macroToolkitCrisisSupport";
import { formatChange, groupLabel, latestIndicatorDate } from "../lib/macroToolkitDisplayFormat";
import { MetricTile } from "../lib/macroToolkitPanelShared";

export function IndicatorValueCell({ item }: { item: MacroToolkitIndicator }) {
  return (
    <div className="macro-toolkit-number-cell">
      <strong>{formatValue(item.latest_value, item.unit)}</strong>
      <small>{item.row_count.toLocaleString()} 行</small>
    </div>
  );
}

export const INDICATOR_SPARKLINE_WIDTH = 120;
export const INDICATOR_SPARKLINE_HEIGHT = 28;
export const INDICATOR_SPARKLINE_PADDING = 2;

export function IndicatorSparkline({ item }: { item: MacroToolkitIndicator }) {
  const points = item.recent_points ?? [];
  if (points.length < 2) {
    return <span className="macro-toolkit-sparkline__empty">—</span>;
  }
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const innerWidth = INDICATOR_SPARKLINE_WIDTH - INDICATOR_SPARKLINE_PADDING * 2;
  const innerHeight = INDICATOR_SPARKLINE_HEIGHT - INDICATOR_SPARKLINE_PADDING * 2;
  const step = innerWidth / (points.length - 1);
  const coords = points.map((point, index) => {
    const x = INDICATOR_SPARKLINE_PADDING + index * step;
    const y = INDICATOR_SPARKLINE_PADDING + innerHeight * (1 - (point.value - min) / span);
    return [Number(x.toFixed(2)), Number(y.toFixed(2))] as const;
  });
  const [lastX, lastY] = coords[coords.length - 1]!;
  const firstDate = points[0]!.date;
  const lastDate = points[points.length - 1]!.date;
  return (
    <svg
      className="macro-toolkit-sparkline"
      viewBox={`0 0 ${INDICATOR_SPARKLINE_WIDTH} ${INDICATOR_SPARKLINE_HEIGHT}`}
      width={INDICATOR_SPARKLINE_WIDTH}
      height={INDICATOR_SPARKLINE_HEIGHT}
      role="img"
      aria-label={`${item.label} 近 ${points.length} 期走势`}
    >
      <title>{`${firstDate} ~ ${lastDate} · ${points.length} 期`}</title>
      <polyline points={coords.map(([x, y]) => `${x},${y}`).join(" ")} fill="none" strokeWidth="1.5" />
      <circle cx={lastX} cy={lastY} r="2" />
    </svg>
  );
}

export function DeltaCell({ change, changePct }: { change: number | null; changePct: number | null }) {
  const direction = changePct ?? change;
  const hasDirection = direction !== null;
  const isPositive = hasDirection && direction > 0;
  const isNegative = hasDirection && direction < 0;

  return (
    <div
      className={[
        "macro-toolkit-delta-cell",
        isPositive ? "macro-toolkit-delta-cell--up" : "",
        isNegative ? "macro-toolkit-delta-cell--down" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {isPositive ? <ArrowUpOutlined /> : null}
      {isNegative ? <ArrowDownOutlined /> : null}
      <span>{formatChange(change, changePct)}</span>
    </div>
  );
}

export function IndicatorObservationSummary({ indicators }: { indicators: MacroToolkitIndicator[] }) {
  const usableIndicators = indicators.filter((indicator) => indicator.quality === "ok");
  const missingIndicators = indicators.length - usableIndicators.length;
  const visibleIndicators = indicators.slice(0, 4);
  return (
    <div className="macro-toolkit-indicator-observation" aria-label="指标证据摘要">
      <div className="macro-toolkit-indicator-observation__head">
        <div>
          <span>指标证据摘要</span>
          <strong>数据源已确认</strong>
        </div>
      </div>
      <div className="macro-toolkit-indicator-observation__grid">
        <MetricTile
          icon={<DatabaseOutlined />}
          label="指标覆盖"
          value={`${usableIndicators.length}/${indicators.length || 0}`}
          detail={missingIndicators ? `${missingIndicators} 个指标待补齐。` : "当前观察指标均可用。"}
          tone={missingIndicators ? "missing" : "neutral"}
          detailMaxLength={40}
        />
        <MetricTile
          icon={<ClockCircleOutlined />}
          label="最新日期"
          value={latestIndicatorDate(indicators)}
          detail=""
          tone="neutral"
          detailMaxLength={40}
        />
      </div>
      <div className="macro-toolkit-indicator-observation__list">
        {visibleIndicators.map((indicator) => (
          <div
            className={[
              "macro-toolkit-indicator-observation__item",
              indicator.quality === "missing" ? "macro-toolkit-indicator-observation__item--missing" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            key={indicator.alias}
          >
            <div>
              <span>
                {groupLabel(indicator.group)} · {indicator.label}
              </span>
              <strong>{formatValue(indicator.latest_value, indicator.unit)}</strong>
            </div>
            <small>
              {formatChange(indicator.change, indicator.change_pct)} ·{" "}
              {indicator.latest_date ?? "日期缺失"}
            </small>
          </div>
        ))}
      </div>
    </div>
  );
}

const indicatorColumns: ColumnsType<MacroToolkitIndicator> = [
  {
    title: "指标",
    dataIndex: "label",
    key: "label",
    render: (_, item) => (
      <div className="macro-toolkit-script-cell">
        <span className="macro-toolkit-script-name">{item.label}</span>
        <span className="macro-toolkit-script-file">{item.alias}</span>
      </div>
    ),
  },
  {
    title: "分组",
    dataIndex: "group",
    key: "group",
    width: 120,
    render: (group: string) => <span className="macro-toolkit-indicator-group">{groupLabel(group)}</span>,
  },
  {
    title: "最新值",
    dataIndex: "latest_value",
    key: "latest_value",
    width: 150,
    render: (_, item) => <IndicatorValueCell item={item} />,
  },
  {
    title: "变化",
    dataIndex: "change_pct",
    key: "change_pct",
    width: 110,
    render: (_, item) => <DeltaCell change={item.change} changePct={item.change_pct} />,
  },
  {
    title: "近期走势",
    key: "recent_points",
    width: 140,
    render: (_, item) => <IndicatorSparkline item={item} />,
  },
  {
    title: "日期",
    dataIndex: "latest_date",
    key: "latest_date",
    width: 120,
    render: (date: string | null, item) => (
      <div className="macro-toolkit-date-cell">
        <span>{date ?? EM_DASH}</span>
        {item.quality === "ok" ? null : <Tag color="red">缺失</Tag>}
      </div>
    ),
  },
  {
    title: "来源",
    dataIndex: "source",
    key: "source",
    width: 120,
    render: (source: string | null, item) => (
      <div className="macro-toolkit-source-cell">
        <span>{source ?? "未命中"}</span>
        <small>{item.series_id ?? item.alias}</small>
      </div>
    ),
  },
];

export function MacroToolkitIndicatorSection({
  showOperations,
  analysis,
}: {
  showOperations: boolean;
  analysis: MacroToolkitAnalysisPayload;
}) {
  return (
    <section id="macro-toolkit-indicator-matrix" className="macro-toolkit-section">
      <PageSectionLead
        eyebrow="指标"
        title="指标矩阵"
        description={
          showOperations
            ? "展示每个宏观指标的最新值、变化、日期和数据来源。"
            : "只展示当前观察需要的指标结论；源表、行数和序列审计留在完整工具页。"
        }
      />
      {!showOperations ? (
        <IndicatorObservationSummary indicators={analysis.indicators} />
      ) : (
        <Table
          className="macro-toolkit-table--wide"
          rowKey="alias"
          size="small"
          columns={indicatorColumns}
          dataSource={analysis.indicators}
          pagination={false}
          tableLayout="fixed"
          scroll={{ x: 920 }}
          rowClassName={(item) => (item.quality === "missing" ? "macro-toolkit-row--missing" : "")}
        />
      )}
    </section>
  );
}
