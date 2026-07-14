import { useState } from "react";
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import { Button as AntButton, Drawer as AntDrawer } from "antd";

import type { LivermoreStrategyPayload } from "../../../api/contracts";
import type {
  StockAnalysisEvidenceStatusItem,
  StockEndpointEvidenceItem,
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

const endpointMetadataHiddenStatuses = new Set(["待触发", "读取中", "读取失败"]);

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
  endpointItems = [],
  focusedEndpointKey,
  onEndpointSelect,
  diagnosticsDrawerOpen,
  onOpenDiagnostics,
  onCloseDiagnostics,
  showInlineDiagnosticsAction = true,
}: {
  boundaryItems: StockAnalysisEvidenceStatusItem[];
  boundarySummary: StockDataBoundarySummary | null;
  strategyPayload: LivermoreStrategyPayload | null;
  endpointItems?: StockEndpointEvidenceItem[];
  focusedEndpointKey?: string | null;
  onEndpointSelect?: (key: string) => void;
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
        <AntButton
          type="link"
          className="stock-analysis-page__rail-action"
          aria-expanded={isDrawerOpen}
          onClick={openDiagnostics}
        >
          查看完整诊断
        </AntButton>
      ) : null}
      <AntDrawer
        title="数据口径诊断"
        placement="right"
        width={560}
        rootClassName="stock-analysis-page__diagnostics-drawer"
        open={isDrawerOpen}
        onClose={closeDiagnostics}
      >
        {endpointItems.length > 0 ? (
          <section
            className="stock-analysis-page__endpoint-evidence stock-analysis-page__endpoint-evidence--diagnostics"
            aria-label="端点证据诊断"
          >
            <div className="stock-analysis-page__endpoint-evidence-head">
              <h3>端点证据</h3>
              <span>{endpointItems.length} 项 · 点击按需读取并定位</span>
            </div>
            <ul data-testid="stock-analysis-endpoint-diagnostics-list">
              {endpointItems.map((item) => (
                <li
                  key={item.key}
                  data-tone={item.tone}
                  data-active={focusedEndpointKey === item.key ? "true" : "false"}
                  data-preview="true"
                  data-testid={`stock-analysis-endpoint-diagnostic-${item.key}`}
                >
                  <button
                    type="button"
                    aria-label={`查看${item.label}数据`}
                    aria-current={focusedEndpointKey === item.key ? "true" : undefined}
                    onClick={() => {
                      closeDiagnostics();
                      onEndpointSelect?.(item.key);
                    }}
                  >
                    <div>
                      <span>{item.label}</span>
                      <strong>{item.statusLabel}</strong>
                    </div>
                    <p>{item.detail}</p>
                    {!endpointMetadataHiddenStatuses.has(item.statusLabel) ? (
                      <>
                        {item.dateLabel ? <small>{item.dateLabel}</small> : null}
                        {item.metaLabel ? <small>{item.metaLabel}</small> : null}
                        {item.traceLabel ? <small>{item.traceLabel}</small> : null}
                        {item.issueLabel ? <small>{item.issueLabel}</small> : null}
                      </>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        {strategyPayload ? (
            <>
              <strong className="text-danger">
                严重
              </strong>
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
              <strong className="text-warning">
                警告
              </strong>
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
              <strong className="text-default-500">
                信息
              </strong>
              <ul>
                {strategyPayload.diagnostics
                  .filter((diagnostic) => diagnostic.severity === "info")
                  .map((diagnostic) => (
                    <li key={diagnostic.code}>
                      {localizeStockBackendText(diagnostic.message, diagnostic.input_family)}
                    </li>
                  ))}
              </ul>
              <h5 className="text-md font-semibold mt-4 mb-2">数据缺口</h5>
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
              <h5 className="text-md font-semibold mt-4 mb-2">可用输出</h5>
              <p>{strategyPayload.supported_outputs.map(outputKeyLabel).join("、") || "无"}</p>
              <h5 className="text-md font-semibold mt-4 mb-2">阻断输出</h5>
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
      </AntDrawer>
    </section>
  );
}
