import { useState } from "react";
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Typography } from "antd";

import type { LivermoreStrategyPayload } from "../../../api/contracts";
import type {
  StockAnalysisEvidenceStatusItem,
  StockDataBoundarySummary,
} from "../lib/stockAnalysisPageModel";
import { localizeStockBackendText } from "../lib/stockAnalysisPageModel";
import {
  SA_CARD_TITLE,
  SA_FIRST_CARD,
  SA_SECTION_HEAD,
} from "../lib/stockAnalysisPageChrome";
import {
  dataGapFamilyLabel,
  outputKeyLabel,
} from "../lib/stockAnalysisPageLabels";
import { stockStatusLabel } from "../lib/stockAnalysisPageCopy";

const { Text } = Typography;

function boundaryRailIcon(key: StockAnalysisEvidenceStatusItem["key"]) {
  if (key === "as-of-date") return <ClockCircleOutlined />;
  if (key === "rule-version") return <SafetyCertificateOutlined />;
  if (key === "quality") return <CheckCircleOutlined />;
  return <DatabaseOutlined />;
}

export function StockAnalysisBoundaryRail({
  boundaryItems,
  boundarySummary,
  strategyPayload,
}: {
  boundaryItems: StockAnalysisEvidenceStatusItem[];
  boundarySummary: StockDataBoundarySummary | null;
  strategyPayload: LivermoreStrategyPayload | null;
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <section className={SA_FIRST_CARD} data-testid="stock-analysis-boundary-rail">
      <div className={SA_SECTION_HEAD}>
        <h2 className={SA_CARD_TITLE}>数据口径与边界</h2>
      </div>
      <div className="stock-analysis-page__boundary-compact-grid">
        {boundaryItems.map((item) => (
          <div key={item.key} data-tone={item.tone}>
            <span aria-hidden="true">{boundaryRailIcon(item.key)}</span>
            <div>
              <small>{item.label}</small>
              <strong className="stock-analysis-page__tabular">{item.statusLabel}</strong>
            </div>
          </div>
        ))}
      </div>
      {boundarySummary ? (
        <div
          className="stock-analysis-page__boundary-summary"
          data-testid="stock-analysis-boundary-summary"
        >
          <span data-tone={boundarySummary.boundaryCount > 0 ? "warning" : "positive"}>
            <small>边界</small>
            <strong>{boundarySummary.summaryLabel}</strong>
          </span>
          <span data-tone={boundarySummary.boundaryCount > 0 ? "warning" : "positive"}>
            <small>拆分</small>
            <strong>{boundarySummary.detailLabel}</strong>
          </span>
        </div>
      ) : null}
      <Button
        type="link"
        className="stock-analysis-page__rail-action"
        aria-expanded={drawerOpen}
        onClick={() => setDrawerOpen(true)}
      >
        查看完整诊断
      </Button>
      <Drawer
        title="数据口径诊断"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        destroyOnClose
        width={480}
      >
        {strategyPayload ? (
          <>
            <Text strong type="danger">
              严重
            </Text>
            <ul>
              {strategyPayload.diagnostics
                .filter((diagnostic) => diagnostic.severity === "error")
                .map((diagnostic) => (
                  <li key={diagnostic.code}>
                    {localizeStockBackendText(diagnostic.message, diagnostic.input_family)}
                  </li>
                ))}
              {strategyPayload.diagnostics.filter((diagnostic) => diagnostic.severity === "error").length === 0 ? (
                <li>暂无</li>
              ) : null}
            </ul>
            <Text strong type="warning">
              警告
            </Text>
            <ul>
              {strategyPayload.diagnostics
                .filter((diagnostic) => diagnostic.severity === "warning")
                .map((diagnostic) => (
                  <li key={diagnostic.code}>
                    {localizeStockBackendText(diagnostic.message, diagnostic.input_family)}
                  </li>
                ))}
              {strategyPayload.diagnostics.filter((diagnostic) => diagnostic.severity === "warning").length === 0 ? (
                <li>暂无</li>
              ) : null}
            </ul>
            <Text strong type="secondary">
              信息
            </Text>
            <ul>
              {strategyPayload.diagnostics
                .filter((diagnostic) => diagnostic.severity === "info")
                .map((diagnostic) => (
                  <li key={diagnostic.code}>
                    {localizeStockBackendText(diagnostic.message, diagnostic.input_family)}
                  </li>
                ))}
            </ul>
            <Typography.Title level={5}>数据缺口</Typography.Title>
            <ul>
              {strategyPayload.data_gaps.map((gap) => (
                <li key={`${gap.input_family}-${gap.status}`}>
                  <strong>{dataGapFamilyLabel(gap.input_family)}</strong> {stockStatusLabel(gap.status)}:{" "}
                  {localizeStockBackendText(gap.evidence, gap.input_family)}
                </li>
              ))}
            </ul>
            <Typography.Title level={5}>可用输出</Typography.Title>
            <p>{strategyPayload.supported_outputs.map(outputKeyLabel).join("、") || "无"}</p>
            <Typography.Title level={5}>阻断输出</Typography.Title>
            <ul>
              {strategyPayload.unsupported_outputs.map((unsupported) => (
                <li key={unsupported.key}>
                  <strong>{outputKeyLabel(unsupported.key)}</strong>:{" "}
                  {localizeStockBackendText(unsupported.reason, unsupported.key)}
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </Drawer>
    </section>
  );
}
