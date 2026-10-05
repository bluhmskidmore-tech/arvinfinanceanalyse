import { useEffect, useMemo, useState } from "react";
import type { RiskTensorPayload } from "../../api/contracts";
import type { EChartsOption } from "../../lib/echarts";
import { nocturneChartTheme } from "../../components/charts/chartTheme";
import { chartMagnitudeOrNull, yuanAsWanMagnitudeOrNull } from "./riskTensorDisplay";
import { hasDurationScopeDisclosure, riskTensorScalarIssue } from "./riskTensorQuality";
import { selectDominantRiskTensorRow } from "./riskTensorPageModel";
import { scrollRiskTensorTargetIntoView } from "./riskTensorNavigation";

/** 雷达轴顺序与后端字段一一对应；max 仅用于可视化比例，不做前端金融重算。 */
const RADAR_META = [
  { key: "duration" as const, name: "久期", max: 10 },
  { key: "dv01" as const, name: "面值DV01", max: "dynamic_dv01" as const },
  { key: "convexity" as const, name: "凸性", max: 200 },
  { key: "cs01" as const, name: "CS01", max: "dynamic_cs01" as const },
  { key: "hhi" as const, name: "集中度", max: 1 },
  { key: "liq_ratio" as const, name: "流动性缺口", max: 1 },
] as const;

type RadarKey = (typeof RADAR_META)[number]["key"];

const RADAR_NAVIGATION_TARGETS: Record<RadarKey, string> = {
  duration: "risk-tensor-duration-scope",
  dv01: "risk-tensor-regulatory-dv01-kpi",
  convexity: "risk-tensor-convexity-kpi",
  cs01: "risk-tensor-cs01-kpi",
  hhi: "risk-tensor-issuer-concentration-detail",
  liq_ratio: "risk-tensor-liquidity-gap-detail",
};

const KPI_RADAR_ISSUE_KEYS = new Set(["portfolio_modified_duration", "portfolio_dv01", "portfolio_convexity", "cs01"]);

type KrdChartClickParams = { name?: unknown };

const RADAR_SPLIT_NUMBER = 5;

const KRD_FIELDS = [
  { key: "krd_1y", tenor: "1Y" },
  { key: "krd_3y", tenor: "3Y" },
  { key: "krd_5y", tenor: "5Y" },
  { key: "krd_7y", tenor: "7Y" },
  { key: "krd_10y", tenor: "10Y" },
  { key: "krd_30y", tenor: "30Y" },
] as const;

function dynamicAxisMax(raw: number, fallback: number) {
  const base = Math.abs(raw) * 1.5;
  if (!Number.isFinite(base) || base === 0) {
    return fallback;
  }
  return readableRadarAxisMax(base);
}

function readableRadarAxisMax(max: number) {
  const intervalBase = max / RADAR_SPLIT_NUMBER;
  if (!Number.isFinite(intervalBase) || intervalBase <= 0) {
    return max;
  }
  const magnitude = 10 ** Math.floor(Math.log10(intervalBase));
  const normalized = intervalBase / magnitude;
  const niceNormalized = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 3 ? 3 : normalized <= 5 ? 5 : 10;
  return niceNormalized * magnitude * RADAR_SPLIT_NUMBER;
}

function radarIndicator(name: string, max: number) {
  const readableMax = readableRadarAxisMax(max);
  return { name, min: 0, max: readableMax, interval: readableMax / RADAR_SPLIT_NUMBER };
}

export function useRiskTensorCharts(result: RiskTensorPayload | undefined) {
  const [selectedTenor, setSelectedTenor] = useState<string>("");

  const krdChartOption = useMemo((): EChartsOption | null => {
    if (!result) {
      return null;
    }
    const labels = KRD_FIELDS.map((item) => item.tenor);
    const data = KRD_FIELDS.map((item) => yuanAsWanMagnitudeOrNull(result[item.key]));
    return nocturneChartTheme.createBarChartOption({
      grid: { left: 52, right: 16, top: 36 },
      xAxis: {
        type: "category",
        data: labels,
      },
      yAxis: {
        type: "value",
      },
      series: [
        {
          type: "bar",
          data,
          itemStyle: { color: nocturneChartTheme.palette[0] },
        },
      ],
    });
  }, [result]);

  const tenorRows = useMemo(() => {
    if (!result) {
      return [];
    }
    return KRD_FIELDS.map((item) => ({
      key: item.key,
      tenor: item.tenor,
      value: result[item.key],
      magnitude: yuanAsWanMagnitudeOrNull(result[item.key]),
    }));
  }, [result]);

  const invalidKrdRows = useMemo(() => tenorRows.filter((row) => row.magnitude === null), [tenorRows]);

  const invalidRadarRows = useMemo(() => {
    if (!result) {
      return [];
    }
    return [
      { key: "portfolio_modified_duration", issue: riskTensorScalarIssue(result.portfolio_modified_duration) },
      { key: "portfolio_dv01", issue: riskTensorScalarIssue(result.portfolio_dv01) },
      { key: "portfolio_convexity", issue: riskTensorScalarIssue(result.portfolio_convexity) },
      { key: "cs01", issue: riskTensorScalarIssue(result.cs01) },
      { key: "issuer_concentration_hhi", issue: riskTensorScalarIssue(result.issuer_concentration_hhi) },
      { key: "liquidity_gap_30d_ratio", issue: riskTensorScalarIssue(result.liquidity_gap_30d_ratio) },
    ].filter((item): item is { key: string; issue: string } => Boolean(item.issue));
  }, [result]);

  const issuerConcentrationIssue = result ? riskTensorScalarIssue(result.issuer_concentration_hhi) : null;

  const liquidityGapRatioIssue = result ? riskTensorScalarIssue(result.liquidity_gap_30d_ratio) : null;

  const durationRadarIssue = result ? riskTensorScalarIssue(result.portfolio_modified_duration) : null;

  const kpiRadarIssues = invalidRadarRows.filter((row) => KPI_RADAR_ISSUE_KEYS.has(row.key));

  const dominantTenorRow = useMemo(() => {
    return selectDominantRiskTensorRow(tenorRows);
  }, [tenorRows]);

  useEffect(() => {
    if (tenorRows.length === 0) {
      setSelectedTenor("");
      return;
    }
    const defaultTenor = dominantTenorRow?.tenor ?? tenorRows.find((row) => row.magnitude !== null)?.tenor ?? "";
    const selectedRow = tenorRows.find((row) => row.tenor === selectedTenor);
    if (!selectedTenor || !selectedRow || selectedRow.magnitude === null) {
      setSelectedTenor(defaultTenor);
    }
  }, [dominantTenorRow?.tenor, selectedTenor, tenorRows]);

  const selectedTenorRow =
    tenorRows.find((row) => row.tenor === selectedTenor && row.magnitude !== null) ??
    dominantTenorRow ??
    tenorRows.find((row) => row.magnitude !== null);

  const showDurationScope = result ? hasDurationScopeDisclosure(result) : false;

  const radarNavigationItems = result
    ? RADAR_META.map((item) => {
        const targetTestId =
          item.key === "duration" && !showDurationScope
            ? "risk-tensor-duration-kpi"
            : RADAR_NAVIGATION_TARGETS[item.key];
        return {
          key: item.key,
          name: item.name,
          targetTestId,
        };
      })
    : [];

  const handlePrimaryTenorDrill = () => {
    if (!dominantTenorRow) {
      scrollRiskTensorTargetIntoView(
        document.querySelector<HTMLElement>('[data-testid="risk-tensor-krd-quality-note"]'),
      );
      return;
    }
    setSelectedTenor(dominantTenorRow.tenor);
    scrollRiskTensorTargetIntoView(
      document.querySelector<HTMLElement>('[data-testid="risk-tensor-tenor-drill"]'),
    );
  };

  const handleKrdTenorSelect = (row: (typeof tenorRows)[number], options?: { scrollToDrill?: boolean }) => {
    if (row.magnitude === null) {
      scrollRiskTensorTargetIntoView(
        document.querySelector<HTMLElement>('[data-testid="risk-tensor-krd-quality-note"]'),
      );
      return;
    }
    setSelectedTenor(row.tenor);
    if (options?.scrollToDrill) {
      scrollRiskTensorTargetIntoView(
        document.querySelector<HTMLElement>('[data-testid="risk-tensor-tenor-drill"]'),
      );
    }
  };

  const handleKrdChartClick = (params: KrdChartClickParams) => {
    const tenor = typeof params.name === "string" ? params.name : "";
    const row = tenorRows.find((item) => item.tenor === tenor);
    if (!row) {
      return;
    }
    handleKrdTenorSelect(row, { scrollToDrill: true });
  };

  const radarChartOption = useMemo((): EChartsOption | null => {
    if (!result) {
      return null;
    }
    const duration = chartMagnitudeOrNull(result.portfolio_modified_duration);
    const dv01 = yuanAsWanMagnitudeOrNull(result.portfolio_dv01);
    const convexity = chartMagnitudeOrNull(result.portfolio_convexity);
    const cs01 = yuanAsWanMagnitudeOrNull(result.cs01);
    const hhi = chartMagnitudeOrNull(result.issuer_concentration_hhi);
    const liqRatio = chartMagnitudeOrNull(result.liquidity_gap_30d_ratio);

    const dv01Max = dynamicAxisMax(dv01 ?? 0, 1);
    const cs01Max = dynamicAxisMax(cs01 ?? 0, 1);

    const indicator = RADAR_META.map((m) => {
      if (m.max === "dynamic_dv01") {
        return radarIndicator(m.name, dv01Max);
      }
      if (m.max === "dynamic_cs01") {
        return radarIndicator(m.name, cs01Max);
      }
      return radarIndicator(m.name, m.max);
    });

    const radarValues = [duration, dv01, convexity, cs01, hhi, liqRatio];

    return nocturneChartTheme.createBaseChartOption({
      grid: undefined,
      tooltip: {
        trigger: "item",
      },
      radar: {
        indicator,
        radius: "66%",
        center: ["50%", "54%"],
        axisName: {
          color: nocturneChartTheme.axisLabel.color,
          fontSize: 12,
        },
        splitLine: {
          lineStyle: { color: nocturneChartTheme.splitLine.lineStyle.color },
        },
        splitArea: { show: false },
        axisLine: { lineStyle: { color: nocturneChartTheme.axisLine.lineStyle.color } },
      },
      series: [
        {
          type: "radar",
          symbolSize: 5,
          lineStyle: { width: 1.5, color: nocturneChartTheme.palette[0] },
          areaStyle: {
            color: nocturneChartTheme.palette[0],
            opacity: 0.15,
          },
          itemStyle: {
            color: nocturneChartTheme.palette[0],
            borderColor: nocturneChartTheme.palette[0],
          },
          data: [
            {
              value: radarValues,
              name: "组合",
            },
          ],
        },
      ],
    });
  }, [result]);

  return {
    selectedTenor,
    krdChartOption,
    tenorRows,
    invalidKrdRows,
    invalidRadarRows,
    issuerConcentrationIssue,
    liquidityGapRatioIssue,
    durationRadarIssue,
    kpiRadarIssues,
    dominantTenorRow,
    selectedTenorRow,
    showDurationScope,
    radarNavigationItems,
    handlePrimaryTenorDrill,
    handleKrdTenorSelect,
    handleKrdChartClick,
    radarChartOption,
  };
}
