import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, DatePicker, Input, Space } from "antd";
import dayjs from "dayjs";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import {
  KpiStrip,
  SectionGrid,
  SectionHead,
  StateSurface,
  StateSurfaceQuotaProvider,
  type KpiCell,
  type SectionState,
} from "../../../components/layout";
import { PageHeader, PageV2Shell } from "../../../components/page/PagePrimitives";
import { BondTradingDeskComposeStrip } from "../components/BondTradingDeskComposeStrip";
import { BondTradingDeskDecisionRail } from "../components/BondTradingDeskDecisionRail";
import { BondTradingDeskIdentityStrip } from "../components/BondTradingDeskIdentityStrip";
import styles from "../BondTradingDeskPage.module.css";
import {
  buildBondTradingDeskComposeResult,
  buildBondTradingDeskPageModel,
  normalizeBondCode,
  type BondTradingDeskGapSection,
  type BondTradingDeskMetricTile,
} from "../lib/bondTradingDeskPageModel";

/**
 * 六格读数横带：三列，720 以下折两列。原 `.metricGrid` 的折列点在 960px，
 * KpiStrip 只开放 720/1024/1280 三档，折列点因此上移到 720——桌面档（本页几何锁
 * 覆盖的 1440/1728/1920）与移动档（390）两端行为不变，只有 721-960 这一段由两列
 * 变三列。
 */
const METRIC_COLS = { base: 2, md: 3, lg: 3, xl: 3 } as const;

/**
 * 待返回模块的状态徽标：原为 gap 卡片内的 antd `Tag`（api_pending 橙 /
 * not_in_portfolio 默认灰），迁到分区头的状态位后文案逐字不变，颜色由原语的
 * partial（琥珀）/ empty（中性）承担，页面不再自带状态色。
 */
const GAP_STATE: Record<BondTradingDeskGapSection["status"], SectionState> = {
  api_pending: { label: "API 待返回", tone: "partial" },
  not_in_portfolio: { label: "未命中持仓", tone: "empty" },
};

/** 读数格：`caption` 是来源/口径小注，落到原语的 note 槽；空串不渲染，不占版面。 */
function toKpiCells(tiles: BondTradingDeskMetricTile[]): KpiCell[] {
  return tiles.map((tile) => ({
    key: tile.key,
    label: tile.label,
    value: tile.value,
    note: tile.caption || null,
  }));
}

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

  const retryFailedReads = () => {
    if (datesQuery.isError) {
      void datesQuery.refetch();
    }
    if (composeQuery.isError || composeResult?.partialFailure) {
      void composeQuery.refetch();
    }
  };
  const isRetryingReads = datesQuery.isFetching || composeQuery.isFetching;

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

  const gapStatus = pageModel?.gapSections[0]?.status ?? null;

  return (
    <StateSurfaceQuotaProvider>
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
      />

      <div className={styles.toolbarRow}>
        <Space wrap>
          <DatePicker
            data-testid="bond-trading-desk-report-date"
            placeholder="选择报告日"
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
      </div>

      {/*
       * 读取失败/部分失败：整包失败走 error（红），部分来源失败走 partial（琥珀），
       * 与迁移前 Alert 的 error / warning 两档逐档同色。重试按钮走 children，
       * 状态行不遮罩它（§6 不能静默吞态）。
       */}
      {pageError ? (
        <StateSurface
          testId="bond-trading-desk-error"
          status={composeResult?.partialFailure ? "partial" : "error"}
          message={pageError}
          dedupeKey="bond-trading-desk-read-availability"
        >
          <Button
            size="small"
            data-testid="bond-trading-desk-retry"
            loading={isRetryingReads}
            onClick={retryFailedReads}
          >
            重试
          </Button>
        </StateSurface>
      ) : null}

      {!normalizedBondCode ? (
        <StateSurface
          testId="bond-trading-desk-missing-bond"
          status="empty"
          message="请提供 bond_code"
          reason="可从债券分析「重仓券」行点击「单券台」深钻进入，或手动输入代码。"
        />
      ) : null}

      {/* 拼装在途：骨架背板按下方读面高度占位，信封到达时不再从 48px 弹到整屏。 */}
      {normalizedBondCode && effectiveReportDate && composeQuery.isPending ? (
        <StateSurface testId="bond-trading-desk-loading" status="loading" minHeight={120} />
      ) : null}

      {normalizedBondCode && !effectiveReportDate && !datesQuery.isLoading ? (
        <p className={styles.scopeNote} data-testid="bond-trading-desk-waiting-date">
          报告日不可用，暂无法拼装单券读面；请重试报告日列表或手动指定日期。
        </p>
      ) : null}

      {pageModel ? (
        <SectionGrid gap={16}>
          <BondTradingDeskIdentityStrip bondCode={pageModel.bondCode} snapshot={pageModel.snapshot} />

          {composeResult ? (
            <BondTradingDeskComposeStrip
              statuses={composeResult.sourceStatuses}
              partialFailure={composeResult.partialFailure}
            />
          ) : null}

          <p
            className={styles.scopeNote}
            data-testid="bond-trading-desk-scope-note"
            title={pageModel.lookupScopeDetail}
          >
            {pageModel.lookupScopeNote}
          </p>

          <div className={styles.heroGrid}>
            <SectionGrid gap={16}>
              <section
                data-testid="bond-trading-desk-conclusion"
                className={styles.conclusionCard}
              >
                {/* 结论卡的 kicker 迁到分区头标题位：原 `.conclusionTitle` 的大写
                    宽字距装饰已被 DESIGN.md §3 收回给状态/口径徽标，且大写变换在
                    中文标题上本来就无效。 */}
                <SectionHead
                  title={pageModel.conclusion.title}
                  numbered={false}
                  contentGap="tight"
                />
                <div className={styles.conclusionBody}>{pageModel.conclusion.body}</div>
                <div className={styles.conclusionDetail}>{pageModel.conclusion.detail}</div>
              </section>

              <section data-testid="bond-trading-desk-metrics">
                <SectionHead title="单券读数" numbered={false} />
                <KpiStrip
                  cells={toKpiCells(pageModel.metricTiles)}
                  cols={METRIC_COLS}
                  cellTestIdPrefix="bond-trading-desk-metric"
                />
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

              <section data-testid="bond-trading-desk-gaps">
                {/* 五个模块共用同一等待原因：模块名合并进一条空态消息，原因只出现
                    一次（§6 状态信息去重），等待状态收到分区头的状态位上。 */}
                <SectionHead
                  title="待返回模块"
                  numbered={false}
                  state={gapStatus ? GAP_STATE[gapStatus] : null}
                />
                <StateSurface
                  status="empty"
                  message={pageModel.gapSections.map((gap) => gap.label).join("、")}
                  reason={pageModel.gapSections[0]?.reason}
                />
              </section>
            </SectionGrid>

            <BondTradingDeskDecisionRail items={pageModel.decisionItems} />
          </div>
        </SectionGrid>
      ) : null}
    </PageV2Shell>
    </StateSurfaceQuotaProvider>
  );
}
