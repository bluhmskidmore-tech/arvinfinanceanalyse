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
  diagnosticsDrawerOpen,
  onOpenDiagnostics,
  onCloseDiagnostics,
  showInlineDiagnosticsAction = true,
}: {
  boundaryItems: StockAnalysisEvidenceStatusItem[];
  boundarySummary: StockDataBoundarySummary | null;
  strategyPayload: LivermoreStrategyPayload | null;
  diagnosticsDrawerOpen?: boolean;
  onOpenDiagnostics?: () => void;
  onCloseDiagnostics?: () => void;
  showInlineDiagnosticsAction?: boolean;
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const isControlled = diagnosticsDrawerOpen !== undefined;
  const isDrawerOpen = isControlled ? diagnosticsDrawerOpen : drawerOpen;

  const openDiagnostics = () => {
    if (isControlled) {
      onOpenDiagnostics?.();
      return;
    }

    setDrawerOpen(true);
  };

  const closeDiagnostics = () => {
    if (isControlled) {
      onCloseDiagnostics?.();
      return;
    }

    setDrawerOpen(false);
  };

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
      {showInlineDiagnosticsAction ? (
        <Button
          type="link"
          className="stock-analysis-page__rail-action"
          aria-expanded={isDrawerOpen}
          onClick={openDiagnostics}
        >
          查看完整诊断
        </Button>
      ) : null}
      <Drawer
        title="数据口径诊断"
        open={isDrawerOpen}
        onClose={closeDiagnostics}
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
              {strategyPayload.data_gaps.map((gap) => {
                const familyLabel = dataGapFamilyLabel(gap.input_family);
                const status = stockStatusLabel(gap.status);
                return (
                  <li key={`${gap.input_family}-${gap.status}`}>
                    <span className="sr-only">{familyLabel} {status}</span>
                    <strong>{familyLabel}</strong> {status}:{" "}
                    {localizeStockBackendText(gap.evidence, gap.input_family)}
                  </li>
                );
              })}
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
