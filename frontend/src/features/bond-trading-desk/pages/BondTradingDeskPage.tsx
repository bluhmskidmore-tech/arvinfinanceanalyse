import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, DatePicker, Input, Space, Spin, Tag } from "antd";
import dayjs from "dayjs";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { PageHeader, PageV2Shell } from "../../../components/page/PagePrimitives";
import { BondTradingDeskComposeStrip } from "../components/BondTradingDeskComposeStrip";
import { BondTradingDeskDecisionRail } from "../components/BondTradingDeskDecisionRail";
import { BondTradingDeskIdentityStrip } from "../components/BondTradingDeskIdentityStrip";
import styles from "../BondTradingDeskPage.module.css";
import {
  buildBondTradingDeskComposeResult,
  buildBondTradingDeskPageModel,
  normalizeBondCode,
} from "../lib/bondTradingDeskPageModel";

export default function BondTradingDeskPage() {
  const client = useApiClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const urlBondCode = searchParams.get("bond_code") ?? "";
  const urlReportDate = searchParams.get("report_date") ?? "";

  const [bondCodeInput, setBondCodeInput] = useState(urlBondCode);
  const [reportDate, setReportDate] = useState<string>(urlReportDate);

  const datesQuery = useQuery({
    queryKey: [client.mode, "bond-trading-desk", "dates"],
    queryFn: () => client.getBondAnalyticsDates(),
    retry: false,
  });

  useEffect(() => {
    const dates = datesQuery.data?.result.report_dates ?? [];
    if (!reportDate && dates.length > 0) {
      setReportDate(dates[0]);
    }
  }, [datesQuery.data, reportDate]);

  useEffect(() => {
    setBondCodeInput(urlBondCode);
  }, [urlBondCode]);

  useEffect(() => {
    if (urlReportDate) {
      setReportDate(urlReportDate);
    }
  }, [urlReportDate]);

  const normalizedBondCode = normalizeBondCode(bondCodeInput || urlBondCode);
  const effectiveReportDate = reportDate || urlReportDate;

  const composeQuery = useQuery({
    queryKey: [
      client.mode,
      "bond-trading-desk",
      "compose",
      effectiveReportDate,
      normalizedBondCode,
    ],
    enabled: Boolean(effectiveReportDate && normalizedBondCode),
    retry: false,
    queryFn: async () => {
      const [topHoldingsSettled, positionsSettled, creditSpreadSettled, changesSettled] =
        await Promise.allSettled([
          client.getBondAnalyticsTopHoldings(effectiveReportDate, 500),
          client.getPositionsBondsList({
            reportDate: effectiveReportDate,
            page: 1,
            pageSize: 500,
          }),
          client.getCreditSpreadAnalysisDetail(effectiveReportDate),
          client.getBondAnalyticsPositionChanges(effectiveReportDate, 100),
        ]);

      const topHoldings =
        topHoldingsSettled.status === "fulfilled"
          ? (topHoldingsSettled.value.result.items ?? [])
          : [];
      const positions =
        positionsSettled.status === "fulfilled"
          ? (positionsSettled.value.result.items ?? [])
          : [];
      const creditRows =
        creditSpreadSettled.status === "fulfilled"
          ? [
              ...(creditSpreadSettled.value.result.top_spread_bonds ?? []),
              ...(creditSpreadSettled.value.result.bottom_spread_bonds ?? []),
            ]
          : [];
      const positionChanges =
        changesSettled.status === "fulfilled"
          ? (changesSettled.value.result.items ?? [])
          : [];

      return buildBondTradingDeskComposeResult({
        bondCode: normalizedBondCode,
        reportDate: effectiveReportDate,
        topHoldings,
        positions,
        creditSpreadRows: creditRows,
        positionChanges,
        sourceSettled: {
          topHoldings: topHoldingsSettled,
          positions: positionsSettled,
          creditSpread: creditSpreadSettled,
          positionChanges: changesSettled,
        },
      });
    },
  });

  const composeResult = composeQuery.data;
  const pageModel = useMemo(() => {
    if (composeResult) {
      return composeResult.model;
    }
    if (
      composeQuery.isError &&
      normalizedBondCode &&
      effectiveReportDate &&
      !composeQuery.isPending
    ) {
      return buildBondTradingDeskPageModel({
        bondCode: normalizedBondCode,
        reportDate: effectiveReportDate,
        topHoldings: [],
        positions: [],
        creditSpreadRows: [],
        positionChanges: [],
      });
    }
    return null;
  }, [
    composeResult,
    composeQuery.isError,
    composeQuery.isPending,
    effectiveReportDate,
    normalizedBondCode,
  ]);

  const dates = datesQuery.data?.result.report_dates ?? [];
  const hasDates = dates.length > 0;

  const pageError = useMemo(() => {
    if (datesQuery.isError) return "报告日列表加载失败。";
    if (composeQuery.isError) return "单券拼装读面全部失败，以下为空态占位。";
    if (composeResult?.partialFailure) return "部分拼装来源失败，已用可用读面继续展示。";
    return null;
  }, [composeQuery.isError, composeResult?.partialFailure, datesQuery.isError]);

  const applyBondCode = () => {
    const next = new URLSearchParams(searchParams);
    const code = bondCodeInput.trim();
    if (code) {
      next.set("bond_code", code);
    } else {
      next.delete("bond_code");
    }
    if (effectiveReportDate) {
      next.set("report_date", effectiveReportDate);
    }
    setSearchParams(next, { replace: true });
  };

  const onReportDateChange = (value: dayjs.Dayjs | null) => {
    const nextDate = value ? value.format("YYYY-MM-DD") : "";
    setReportDate(nextDate);
    const next = new URLSearchParams(searchParams);
    if (nextDate) {
      next.set("report_date", nextDate);
    } else {
      next.delete("report_date");
    }
    if (normalizedBondCode) {
      next.set("bond_code", normalizedBondCode);
    }
    setSearchParams(next, { replace: true });
  };

  return (
    <PageV2Shell
      testId="bond-trading-desk-page"
      themeScope="bond-trading-desk"
      style={{ paddingBottom: 24 }}
    >
      <PageHeader
        testId="bond-trading-desk-header"
        eyebrow="组合工作台"
        title="单券交易分析台"
        description="只读拼装既有重仓券、持仓与利差列表；盘口、约束与相似券等待后端契约。"
        badgeLabel="契约对齐 MVP"
        badgeTone="accent"
        actions={
          <Space wrap>
            <DatePicker
              data-testid="bond-trading-desk-report-date"
              value={effectiveReportDate ? dayjs(effectiveReportDate) : null}
              onChange={onReportDateChange}
              disabled={!hasDates}
              allowClear={false}
            />
            <Input
              data-testid="bond-trading-desk-bond-code"
              placeholder="bond_code，如 230210.IB"
              value={bondCodeInput}
              onChange={(event) => setBondCodeInput(event.target.value)}
              onPressEnter={applyBondCode}
              style={{ width: 220 }}
            />
            <Button data-testid="bond-trading-desk-apply-bond" onClick={applyBondCode}>
              查询
            </Button>
          </Space>
        }
      />

      {pageError ? (
        <Alert
          type={composeResult?.partialFailure ? "warning" : "error"}
          showIcon
          message={pageError}
          data-testid="bond-trading-desk-error"
        />
      ) : null}

      {!normalizedBondCode ? (
        <Alert
          type="info"
          showIcon
          data-testid="bond-trading-desk-missing-bond"
          message="请提供 bond_code"
          description="可从债券分析「重仓券」行点击「单券台」深钻进入，或手动输入代码。"
        />
      ) : null}

      {normalizedBondCode && composeQuery.isPending ? (
        <div data-testid="bond-trading-desk-loading">
          <Spin />
        </div>
      ) : null}

      {pageModel ? (
        <div className={styles.pageShell}>
          <BondTradingDeskIdentityStrip bondCode={pageModel.bondCode} snapshot={pageModel.snapshot} />

          {composeResult ? (
            <BondTradingDeskComposeStrip
              statuses={composeResult.sourceStatuses}
              partialFailure={composeResult.partialFailure}
            />
          ) : null}

          <p className={styles.scopeNote} data-testid="bond-trading-desk-scope-note">
            {pageModel.lookupScopeNote}
          </p>

          <div className={styles.heroGrid}>
            <div className={styles.pageShell}>
              <section
                data-testid="bond-trading-desk-conclusion"
                className={styles.conclusionCard}
              >
                <div className={styles.conclusionTitle}>{pageModel.conclusion.title}</div>
                <div className={styles.conclusionBody}>{pageModel.conclusion.body}</div>
                <div className={styles.conclusionDetail}>{pageModel.conclusion.detail}</div>
              </section>

              <section
                data-testid="bond-trading-desk-metrics"
                className={styles.sectionBlock}
              >
                <div className={styles.sectionTitle}>单券读数</div>
                <div className={styles.metricGrid}>
                  {pageModel.metricTiles.map((tile) => (
                    <div key={tile.key} className={styles.metricTile} data-testid={`bond-trading-desk-metric-${tile.key}`}>
                      <div className={styles.metricLabel}>{tile.label}</div>
                      <div className={styles.metricValue}>{tile.value}</div>
                      {tile.caption ? <div className={styles.metricCaption}>{tile.caption}</div> : null}
                    </div>
                  ))}
                </div>
              </section>

              {pageModel.positionChange ? (
                <Alert
                  type="info"
                  showIcon
                  data-testid="bond-trading-desk-position-change"
                  message="持仓变动（top 列表命中）"
                  description={`方向 ${pageModel.positionChange.direction}；变动市值 ${pageModel.positionChange.change_market_value.display}；原因 ${pageModel.positionChange.reason_label}`}
                />
              ) : null}

              <section
                data-testid="bond-trading-desk-gaps"
                className={styles.sectionBlock}
              >
                <div className={styles.sectionTitle}>待返回模块</div>
                <div className={styles.gapList}>
                  {pageModel.gapSections.map((gap) => (
                    <div key={gap.key} className={styles.gapItem}>
                      <div className={styles.gapLabel}>
                        {gap.label}{" "}
                        <Tag color={gap.status === "api_pending" ? "orange" : "default"}>
                          {gap.status === "api_pending" ? "API 待返回" : "未命中持仓"}
                        </Tag>
                      </div>
                      <div className={styles.gapReason}>{gap.reason}</div>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            <BondTradingDeskDecisionRail items={pageModel.decisionItems} />
          </div>
        </div>
      ) : null}
    </PageV2Shell>
  );
}
