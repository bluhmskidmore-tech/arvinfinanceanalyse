import { Alert } from "antd";

import type { AdbInsightsResponse } from "../../../api/contracts";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import AdbConcentrationPanel from "./AdbConcentrationPanel";
import AdbNimAttributionPanel from "./AdbNimAttributionPanel";
import AdbScaleAttributionPanel from "./AdbScaleAttributionPanel";
import AdbSectionHead from "./AdbSectionHead";
import AdbVolatilityPanel from "./AdbVolatilityPanel";

import "./AverageBalanceView.css";

type AdbDeepAnalysisSectionProps = {
  data: AdbInsightsResponse | undefined;
  isLoading: boolean;
  isError: boolean;
};

/**
 * 深度分析容器：规模归因 / NIM 量价归因 / 波动异常 / 结构集中度四个子面板。
 * 只负责编排与加载态；数值全部来自 `GET /api/analysis/adb/insights`，
 * 前端不重算任何正式金融口径。结论列表（insights）在页面「区间结论与警示」区渲染，不在本容器内重复。
 */
export default function AdbDeepAnalysisSection({ data, isLoading, isError }: AdbDeepAnalysisSectionProps) {
  if (isError) {
    return (
      <section className="adb-sec" data-testid="adb-deep-analysis-section">
        <AdbSectionHead title="深度分析" />
        <p className="adb-note">深度分析暂不可用，请查看上方「区间结论与警示」区的提示。</p>
      </section>
    );
  }

  if (isLoading || !data) {
    return (
      <section className="adb-sec" data-testid="adb-deep-analysis-section">
        <AdbSectionHead title="深度分析" />
        <div className="adb-skeleton" aria-busy="true">
          <span>深度分析数据读取中…</span>
        </div>
      </section>
    );
  }

  const resultMetaPanel = (
    <FormalResultMetaPanel
      testId="adb-insights-result-meta"
      title="深度分析口径与证据"
      sections={[{ key: "insights", title: "ADB 深度分析", meta: data.result_meta }]}
    />
  );

  if (data.insufficient_window) {
    return (
      <>
        <section className="adb-sec" data-testid="adb-deep-analysis-section">
          <AdbSectionHead title="深度分析" />
          <Alert type="info" showIcon message="区间过短，无法计算深度分析" />
        </section>
        {resultMetaPanel}
      </>
    );
  }

  if (!data.windows.current.available) {
    return (
      <>
        <section className="adb-sec" data-testid="adb-deep-analysis-section">
          <AdbSectionHead title="深度分析" />
          <Alert type="info" showIcon message="本期无有效余额，无法计算深度分析" />
        </section>
        {resultMetaPanel}
      </>
    );
  }

  return (
    <>
      <AdbScaleAttributionPanel
        qoq={data.scale_attribution.qoq}
        yoy={data.scale_attribution.yoy}
        qoqWindow={data.windows.qoq}
        yoyWindow={data.windows.yoy}
      />
      <AdbNimAttributionPanel
        nim={data.nim_attribution}
        reason={data.nim_attribution_unavailable_reason}
        qoqWindow={data.windows.qoq}
      />
      <AdbVolatilityPanel volatility={data.volatility} />
      <AdbConcentrationPanel concentration={data.concentration} />
      {resultMetaPanel}
    </>
  );
}
