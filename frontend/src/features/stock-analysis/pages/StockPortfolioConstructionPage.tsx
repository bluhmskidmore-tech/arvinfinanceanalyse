import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation, useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/clientContext";
import type { DataTableColumn } from "../../../components/layout";
import {
  DataTable,
  KpiStrip,
  SectionGrid,
  SectionGridItem,
  SectionHead,
  StateSurface,
} from "../../../components/layout";
import type {
  ResultMeta,
  StockPortfolioConstructionIssue,
  StockPortfolioConstructionPayload,
  StockPortfolioConstructionRiskSectorExposure,
  StockPortfolioConstructionTargetItem,
} from "../../../api/contracts";
import {
  AnalysisGrid,
  DataStatusStrip,
  EvidencePanel,
  PageDecisionHero,
  PageV2Shell,
  PageV2SurfacePanel,
} from "../../../components/page/PagePrimitives";
import { EM_DASH, formatPercent } from "../../../utils/format";
import {
  MarketWorkbenchFrame,
  type MarketWorkbenchStatus,
} from "../../workbench/market-shell";
import { StockAnalysisStageNav } from "../components/StockAnalysisStageNav";
import { stockAnalysisReadQueryOptions } from "../lib/stockAnalysisQueryOptions";
import styles from "./StockPortfolioConstructionPage.module.css";

const SHADOW_PORTFOLIO_ID = "SHADOW-STOCK-RESEARCH";

const PORTFOLIO_CODE_LABELS: Record<string, string> = {
  proposal_only: "只读参考预览",
  reference_preview: "参考预览",
  read_only_shadow: "只读影子组合",
  analytical: "分析口径",
  formal: "正式口径",
  ready: "就绪",
  blocked: "阻断",
  complete: "完整返回",
  partial: "部分返回",
  unavailable: "暂不可用",
  error: "异常",
  warning: "需关注",
  stale: "延迟",
  insufficient: "证据不足",
  unsupported: "暂不支持",
  controlled_schema_unavailable: "受控回放数据结构不可用",
  current_rule_cohort_ready: "当前规则组已就绪",
  source_gate_not_ready: "研究回放闭环未就绪",
  blocked_source_gate: "目标权重继续锁定",
  blocked_main_module: "主研究模块未完成映射",
  blocked_no_candidates: "暂无可映射候选",
  main_module_not_ready: "主研究模块未就绪",
  main_module_unavailable: "主研究模块不可用",
  blocked_missing_scoped_positions: "缺少组合级当前持仓",
  blocked_missing_approved_policy: "未接入已批准风险限额",
  missing_approved_policy: "缺少已批准风险政策",
  ignored_unscoped: "未使用：缺少组合归属",
  descriptive_only: "仅作描述性观察",
  vendor_stale: "供应数据延迟",
  latest_snapshot: "最近可用快照",
  empty_target_lines: "暂无可计算的权重行",
  target_line_not_mapping: "权重行结构不可识别",
  missing_stock_code: "缺少股票代码",
  invalid_stock_code: "股票代码格式异常",
  missing_sector_name: "缺少行业归属",
  invalid_sector_name: "行业归属格式异常",
  duplicate_stock_code: "股票代码重复",
  missing_target_weight: "缺少权重",
  invalid_target_weight: "权重格式异常",
  target_weight_out_of_range: "权重超出允许范围",
  total_target_weight_exceeds_one: "权重合计超过 100%",
  weight_and_cash_closure_failed: "权重与现金未闭合",
  sector_exposure_reconciliation_failed: "行业暴露未能闭合",
  zero_invested_weight: "当前投资权重为零",
  hhi_scale_validation_failed: "集中度结果异常",
};

const WEIGHT_BASIS_LABELS: Record<string, string> = {
  "stock_candidates.position_size_hint.items[].equal_weight":
    "研究候选等权提示",
  "position_size_hint.equal_weight": "候选等权提示",
};

const ISSUE_MESSAGE_LABELS: Record<string, string> = {
  source_gate_not_ready: "研究回放闭环尚未就绪，目标权重按阻断规则继续锁定。",
  blocked_source_gate: "当前研究证据未满足组合映射条件，未形成正式目标权重。",
  blocked_main_module: "主研究模块未完成组合映射，目标权重继续锁定。",
  blocked_no_candidates: "当前没有可进入组合映射的研究候选。",
  main_module_not_ready: "主研究模块尚未就绪，当前结果仅供观察。",
  blocked_missing_scoped_positions:
    "缺少组合级当前持仓，暂不展示调仓差额与动作。",
};

const WARNING_MESSAGE_LABELS: Record<string, string> = {
  "Proposal-only projection; it does not create a trading instruction or approval.":
    "当前只展示只读参考预览，不生成交易指令或审批动作。",
  "Rebalance remains blocked until a portfolio-scoped current-position contract is available.":
    "组合级当前持仓接入前，不展示调仓差额与动作。",
  "Source replay closure is not ready; reference rows remain visible but target weights are withheld.":
    "研究回放闭环尚未就绪；参考权重继续可见，目标权重保持留空。",
};

type PageFocus = "portfolio" | "risk";

function formatNullableText(value: string | null | undefined) {
  const normalized = value?.trim();
  return normalized ? normalized : EM_DASH;
}

function localizePortfolioCode(value: string | null | undefined) {
  const normalized = value?.trim();
  if (!normalized) return EM_DASH;
  return PORTFOLIO_CODE_LABELS[normalized] ?? normalized;
}

function localizeWeightBasis(value: string | null | undefined) {
  const normalized = value?.trim();
  if (!normalized) return EM_DASH;
  return WEIGHT_BASIS_LABELS[normalized] ?? localizePortfolioCode(normalized);
}

function traceCodeTitle(value: string | null | undefined) {
  const normalized = value?.trim();
  return normalized ? `追溯代码：${normalized}` : undefined;
}

function sourceGateBusinessLabel(
  payload: StockPortfolioConstructionPayload | null,
) {
  if (!payload) return "状态待返回";
  return payload.source_gate.ready ? "可用于只读映射" : "未满足映射条件";
}

function localizeIssueSeverity(value: string) {
  if (value === "blocking") return "阻断";
  if (value === "warning") return "提醒";
  return localizePortfolioCode(value);
}

function localizeIssueMessage(item: StockPortfolioConstructionIssue) {
  return (
    ISSUE_MESSAGE_LABELS[item.code] ??
    `${localizePortfolioCode(item.code)}，请结合追溯代码和来源复核。`
  );
}

function localizeWarningMessage(value: string) {
  const normalized = value.trim();
  const exact = WARNING_MESSAGE_LABELS[normalized];
  if (exact) return exact;

  const targetStatus = normalized.match(
    /^Target projection is fail-closed:\s*([^.]+)\.?$/i,
  )?.[1];
  if (targetStatus) {
    return `组合映射仍处于阻断状态：${localizePortfolioCode(targetStatus)}。`;
  }
  if (normalized.startsWith("stock_portfolio_risk_builder_failed:")) {
    return "描述性风险计算未完成，请复核风险服务。";
  }
  return localizePortfolioCode(normalized);
}

function rebalanceReasonText(
  payload: StockPortfolioConstructionPayload | null,
) {
  if (!payload) return "调仓边界待返回。";
  if (payload.rebalance.status === "blocked_missing_scoped_positions") {
    return "缺少组合级当前持仓，当前不展示权重差额、调仓数量或交易动作。";
  }
  return `${localizePortfolioCode(payload.rebalance.status)}。`;
}

function formatCount(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("zh-CN")
    : EM_DASH;
}

function parseDecimalValue(value: unknown) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === "string") {
    const normalized = value.trim();
    if (!normalized) return null;
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function formatPlainNumber(value: unknown, digits = 0) {
  const parsed = parseDecimalValue(value);
  if (parsed == null) return EM_DASH;
  return parsed.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatWeight(value: unknown) {
  return formatPercent(parseDecimalValue(value), false);
}

function localizeSignalKind(value: string | null | undefined) {
  if (!value) return EM_DASH;
  const labels: Record<string, string> = {
    stock_candidate: "主候选",
    factor_screen: "因子初筛",
    uptrend_momentum: "趋势扩展",
  };
  return labels[value] ?? value;
}

function localizeIssueSource(value: string | null | undefined) {
  if (!value) return EM_DASH;
  const labels: Record<string, string> = {
    replay_closure: "回放闭环",
    stock_candidates: "候选集",
    "workbench.main": "主研究模块",
    portfolio_scope: "组合持仓口径",
  };
  return labels[value] ?? value;
}

function issueTone(payload: StockPortfolioConstructionPayload | null) {
  if (!payload) return "neutral";
  return payload.issues.some((item) => item.severity === "blocking")
    ? "warning"
    : "neutral";
}

function isResultStale(resultMeta: ResultMeta | null) {
  return (
    resultMeta?.vendor_status === "vendor_stale" ||
    resultMeta?.fallback_mode === "latest_snapshot" ||
    resultMeta?.quality_flag === "stale"
  );
}

function isProposalReady(payload: StockPortfolioConstructionPayload | null) {
  return Boolean(
    payload?.source_gate.ready &&
    !payload.target.blocked &&
    payload.proposal_status === "reference_preview",
  );
}

function frameStatus(
  payload: StockPortfolioConstructionPayload | null,
  resultMeta: ResultMeta | null,
  isLoading: boolean,
  isError: boolean,
): MarketWorkbenchStatus {
  if (isLoading) {
    return { label: "读取中", tone: "muted", detail: "只读参考预览" };
  }
  if (isError) {
    return { label: "读取失败", tone: "error", detail: "只读参考预览" };
  }
  if (isResultStale(resultMeta)) {
    return { label: "延迟快照", tone: "watch", detail: "仅供观察" };
  }
  if (isProposalReady(payload)) {
    return { label: "只读参考", tone: "watch", detail: "不可交易" };
  }
  return {
    label: payload?.source_gate.ready ? "组合映射受限" : "研究门控未满足",
    tone: "watch",
    detail: "目标权重锁定",
  };
}

function sourceGateLabel(payload: StockPortfolioConstructionPayload | null) {
  if (!payload) return "研究门控待返回";
  return payload.source_gate.ready
    ? "研究候选源可用于只读映射"
    : "研究候选源未满足映射条件";
}

function proposalStatusLabel(
  payload: StockPortfolioConstructionPayload | null,
) {
  if (!payload) return "组合映射待返回";
  if (isProposalReady(payload)) return "只读参考预览已返回";
  if (payload.proposal_status === "blocked_source_gate")
    return "候选参考可见，目标权重锁定";
  return localizePortfolioCode(payload.proposal_status);
}

function riskStatusLabel(
  payload: StockPortfolioConstructionPayload | null,
  resultMeta: ResultMeta | null,
) {
  if (!payload) return "风险快照待返回";
  const dataStatus =
    payload.risk_snapshot.data_status ??
    payload.risk_snapshot.status ??
    "unknown";
  if (dataStatus === "complete") {
    return isResultStale(resultMeta)
      ? "描述性风险为延迟快照"
      : "描述性风险已返回";
  }
  return `风险状态 ${localizePortfolioCode(dataStatus)}`;
}

function issueSummaryText(payload: StockPortfolioConstructionPayload | null) {
  if (!payload) return "阻断待返回";
  const blockingCount = payload.issues.filter(
    (item) => item.severity === "blocking",
  ).length;
  if (blockingCount > 0) return `${blockingCount} 项阻断待解除`;
  if (payload.issues.length > 0) return `${payload.issues.length} 项注意事项`;
  return "当前未见新增阻断";
}

function conclusionText(
  payload: StockPortfolioConstructionPayload | null,
  resultMeta: ResultMeta | null,
  focus: PageFocus,
) {
  if (!payload) {
    return "股票候选、影子权重和描述性风险仍在读取，当前页不会生成交易指令。";
  }
  if (isResultStale(resultMeta)) {
    return "当前展示的是延迟快照，只能用于观察候选、参考权重和描述性风险；目标权重、调仓与执行继续锁定。";
  }
  if (isProposalReady(payload)) {
    return focus === "risk"
      ? "研究候选已经映射为只读参考权重，当前可先看暴露和集中度，但仍不能形成调仓或执行指令。"
      : "研究候选已经映射为只读参考权重，当前可以先看候选、参考权重和描述性风险，不会生成交易或审批动作。";
  }
  if (payload.source_gate.ready) {
    return `研究候选源可用于只读映射，但${localizePortfolioCode(payload.target.block_reason ?? payload.target.status)}；目标权重、调仓与执行继续锁定。`;
  }
  return "研究回放闭环尚未满足只读映射条件，因此页面只展示参考权重和描述性风险预览；目标权重与调仓结果继续锁定。";
}

function pageQuestion(focus: PageFocus) {
  return focus === "risk"
    ? "在当前研究候选下，暴露、现金和集中度各落在哪里，哪些阻断还没解除？"
    : "当前研究候选能映射出怎样的只读影子组合，哪些权重只是参考、哪些动作仍被阻断？";
}

function riskMetricCards(payload: StockPortfolioConstructionPayload | null) {
  const snapshot = payload?.risk_snapshot;
  return [
    {
      key: "exposure",
      label: "参考暴露",
      value: formatWeight(snapshot?.gross_exposure_ratio),
      note:
        snapshot?.measurement_basis === "reference_preview"
          ? "基于参考权重，不是可执行目标。"
          : "等待后端返回。",
    },
    {
      key: "cash",
      label: "现金预留",
      value: formatWeight(snapshot?.cash_ratio),
      note: "按后端风险快照直接展示，不在前端重算。",
    },
    {
      key: "hhi",
      label: "集中度 HHI",
      value: formatPlainNumber(snapshot?.hhi_index, 0),
      note: "同一值域下读取集中度强弱，未附正式阈值。",
    },
    {
      key: "residual",
      label: "闭合残差",
      value: formatWeight(snapshot?.closure_residual_ratio),
      note: "用于确认权重闭合，不代表执行偏差。",
    },
  ];
}

function buildTargetColumns(
  hasBlockedTargetWeight: boolean,
): DataTableColumn<StockPortfolioConstructionTargetItem>[] {
  return [
    {
      key: "rank",
      title: "序号",
      align: "numeric",
      width: 52,
      render: (row) => formatPlainNumber(row.rank ?? null, 0),
    },
    {
      key: "stock_name",
      title: "标的",
      width: 137,
      render: (row) => (
        <div className={styles.tableName}>
          <strong>
            {formatNullableText(row.stock_name ?? row.stock_code)}
          </strong>
          <span>
            {row.stock_code}
            {row.signal_kind ? ` · ${localizeSignalKind(row.signal_kind)}` : ""}
          </span>
        </div>
      ),
    },
    {
      key: "sector_name",
      title: "行业",
      width: 82,
      ellipsis: true,
      render: (row) => formatNullableText(row.sector_name),
    },
    {
      key: "reference_weight",
      title: "参考权重",
      align: "numeric",
      width: 80,
      headerWrap: true,
      render: (row) => formatWeight(row.reference_weight),
    },
    {
      key: "target_weight",
      title: "目标权重",
      align: "numeric",
      width: 80,
      headerWrap: true,
      note: hasBlockedTargetWeight ? "研究门控未满足时继续留空。" : undefined,
      render: (row) => formatWeight(row.target_weight),
    },
    {
      key: "target_block_reason",
      title: "状态",
      width: 129,
      render: (row) => {
        const rawStatus = row.target_block_reason ?? row.status;
        return (
          <span title={traceCodeTitle(rawStatus)}>
            {row.target_weight == null
              ? localizePortfolioCode(rawStatus)
              : "参考预览可见"}
          </span>
        );
      },
    },
  ];
}

function renderSectorExposureList(
  sectors: StockPortfolioConstructionRiskSectorExposure[] | null | undefined,
) {
  if (!sectors?.length) return null;
  return (
    <ul
      className={styles.sectorList}
      data-testid="stock-analysis-portfolio-sector-exposures"
    >
      {sectors.map((item) => (
        <li key={item.sector_name} className={styles.sectorItem}>
          <span className={styles.eyebrow}>行业暴露</span>
          <strong>{item.sector_name}</strong>
          <span>{formatWeight(item.exposure_ratio)}</span>
        </li>
      ))}
    </ul>
  );
}

function renderIssueList(items: StockPortfolioConstructionIssue[]) {
  if (items.length === 0) {
    return <p className={styles.conclusion}>当前页未返回额外问题项。</p>;
  }
  return (
    <ul
      className={styles.issueList}
      data-testid="stock-analysis-portfolio-issues"
    >
      {items.map((item) => (
        <li
          key={`${item.code}-${item.source ?? "unknown"}`}
          className={styles.issueItem}
          data-testid={`stock-analysis-portfolio-issue-${item.code}`}
          title={`原始返回：${item.message}`}
        >
          <span className={styles.issueSeverity} data-severity={item.severity}>
            {localizeIssueSeverity(item.severity)}
          </span>
          <div className={styles.issueMessage}>
            {localizeIssueMessage(item)}
          </div>
          <div className={styles.issueMeta}>
            <span>来源：{localizeIssueSource(item.source)}</span>
            <span>
              问题代码：<code className={styles.traceCode}>{item.code}</code>
            </span>
            {item.blocker ? (
              <span>
                阻断代码：
                <code className={styles.traceCode}>{item.blocker}</code>
              </span>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

function renderWarningList(items: string[]) {
  if (items.length === 0) {
    return <p className={styles.conclusion}>当前页未返回额外提示。</p>;
  }
  return (
    <ul
      className={styles.warningList}
      data-testid="stock-analysis-portfolio-warnings"
    >
      {items.map((item, index) => (
        <li
          key={`${item}-${index}`}
          className={styles.warningItem}
          title={`原始返回：${item}`}
        >
          {localizeWarningMessage(item)}
        </li>
      ))}
    </ul>
  );
}

function renderReasonList(items: string[] | undefined) {
  if (!items?.length) {
    return <p className={styles.conclusion}>当前没有返回额外原因代码。</p>;
  }
  return (
    <ul className={styles.reasonList}>
      {items.map((item) => (
        <li key={item} className={styles.reasonItem}>
          <span className={styles.reasonText}>
            {localizePortfolioCode(item)}
          </span>
          <code className={styles.traceCode}>{item}</code>
        </li>
      ))}
    </ul>
  );
}

function renderRiskSurface(
  payload: StockPortfolioConstructionPayload | null,
  resultMeta: ResultMeta | null,
  focus: PageFocus,
  isPageLoading: boolean,
  isPageError: boolean,
) {
  const snapshot = payload?.risk_snapshot;
  const riskReady = (snapshot?.data_status ?? snapshot?.status) === "complete";
  const riskState =
    snapshot == null
      ? isPageError
        ? "error"
        : isPageLoading
          ? "loading"
          : "empty"
      : riskReady
        ? isResultStale(resultMeta)
          ? "stale"
          : isProposalReady(payload)
            ? "ready"
            : "partial"
        : snapshot.data_status === "unavailable" ||
            snapshot.status === "unavailable"
          ? "empty"
          : snapshot.status === "error"
            ? "error"
            : "partial";

  return (
    <PageV2SurfacePanel
      testId="stock-analysis-portfolio-risk-surface"
      style={{ padding: 0, background: "transparent", border: "none" }}
    >
      <div className={styles.surface}>
        <SectionHead
          numbered={false}
          category="描述性风险"
          title={focus === "risk" ? "暴露与集中度读面" : "风险快照"}
          note="只读影子组合，不形成交易动作。"
          meta={[
            {
              label: "组合口径",
              value: localizePortfolioCode(snapshot?.basis),
              title: traceCodeTitle(snapshot?.basis),
            },
            {
              label: "测算基准",
              value: localizePortfolioCode(snapshot?.measurement_basis),
              title: traceCodeTitle(snapshot?.measurement_basis),
            },
            {
              label: "数据质量",
              value: localizePortfolioCode(resultMeta?.quality_flag),
              title: traceCodeTitle(resultMeta?.quality_flag),
            },
          ]}
        />
        <div className={styles.metricList}>
          {riskMetricCards(payload).map((item) => (
            <article key={item.key} className={styles.metricCard}>
              <span className={styles.metricLabel}>{item.label}</span>
              <strong className={styles.metricValue}>{item.value}</strong>
              <span className={styles.metricNote}>{item.note}</span>
            </article>
          ))}
        </div>
        <StateSurface
          status={riskState}
          testId="stock-analysis-portfolio-risk-state"
          density="compact"
          message={formatNullableText(
            snapshot?.headline ??
              (riskReady ? "参考权重下的描述性风险已返回" : "风险快照待返回"),
          )}
          reason={
            !riskReady && snapshot?.reason_codes?.length
              ? `原因：${snapshot.reason_codes.map(localizePortfolioCode).join("；")}`
              : isResultStale(resultMeta)
                ? `当前使用${localizePortfolioCode(resultMeta?.fallback_mode)}，不可视为实时风险。`
                : isProposalReady(payload)
                  ? "风险快照仍处于分析边界内。"
                  : "组合尚未形成正式目标，且未接入已批准风险限额；当前只显示参考权重下的描述性暴露。"
          }
        >
          {riskReady
            ? renderSectorExposureList(snapshot?.sector_exposures)
            : null}
        </StateSurface>
        <div className={styles.inlineMeta}>
          <span
            className={styles.metaChip}
            title={
              snapshot?.limit_gate?.status
                ? `追溯代码：${snapshot.limit_gate.status}${snapshot.limit_gate.reason_code ? `；原因代码：${snapshot.limit_gate.reason_code}` : ""}`
                : undefined
            }
          >
            限额政策{" "}
            {snapshot?.limit_gate?.approved_policy_present
              ? "已接入"
              : "尚未接入"}
          </span>
          <span className={styles.metaChip}>
            风险用途{" "}
            {snapshot?.observation_only === true ? "仅供观察" : "待确认"}
          </span>
          <span className={styles.metaChip}>
            正式使用 {snapshot?.formal_use_allowed === true ? "允许" : "不允许"}
          </span>
          <span className={styles.metaChip}>
            问题项 {issueSummaryText(payload)}
          </span>
        </div>
      </div>
    </PageV2SurfacePanel>
  );
}

export default function StockPortfolioConstructionPage() {
  const client = useApiClient();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const focus: PageFocus = location.pathname.endsWith("/risk")
    ? "risk"
    : "portfolio";
  const requestedAsOfDate = searchParams.get("as_of_date")?.trim() || undefined;

  const pageQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "portfolio-construction",
      SHADOW_PORTFOLIO_ID,
      requestedAsOfDate,
      client.mode,
    ],
    queryFn: () =>
      client.getStockAnalysisPortfolioConstruction({
        portfolioId: SHADOW_PORTFOLIO_ID,
        asOfDate: requestedAsOfDate,
      }),
    retry: false,
    ...stockAnalysisReadQueryOptions,
  });

  const payload = pageQuery.data?.result ?? null;
  const resultMeta = pageQuery.data?.result_meta ?? null;
  const resolvedAsOfDate =
    payload?.resolved_as_of_date ?? requestedAsOfDate ?? null;
  const targetItems = payload?.target.items;
  const hasBlockedTargetWeight = Boolean(
    targetItems?.some((item) => item.target_weight == null),
  );
  const targetColumns = useMemo(
    () => buildTargetColumns(hasBlockedTargetWeight),
    [hasBlockedTargetWeight],
  );
  const targetStatus = pageQuery.isLoading
    ? "loading"
    : pageQuery.isError
      ? "error"
      : targetItems && targetItems.length > 0
        ? isResultStale(resultMeta)
          ? "stale"
          : isProposalReady(payload)
            ? "ready"
            : "partial"
        : "empty";

  return (
    <MarketWorkbenchFrame
      pageKey="stock-analysis"
      chrome="body-only"
      themeScope="stock-analysis"
      title="股票分析"
      question="股票策略舱 / 影子组合与描述性风险"
      status={frameStatus(
        payload,
        resultMeta,
        pageQuery.isLoading,
        pageQuery.isError,
      )}
      metaItems={[
        { label: "观察日", value: formatNullableText(resolvedAsOfDate) },
        { label: "组合", value: SHADOW_PORTFOLIO_ID },
        {
          label: "口径",
          value: localizePortfolioCode(
            payload?.contract_status ?? "proposal_only",
          ),
        },
      ]}
    >
      <PageV2Shell
        testId={`stock-analysis-${focus}-page-v2-shell`}
        themeScope="stock-analysis"
      >
        <section
          className={[styles.page, "theme-dh-api"].join(" ")}
          data-testid={`stock-analysis-${focus}-page`}
          data-focus={focus}
          data-moss-theme-scope="stock-analysis"
        >
          <PageDecisionHero
            testId="stock-analysis-portfolio-hero"
            title="股票策略舱"
            eyebrow={focus === "risk" ? "风险页" : "组合页"}
            businessQuestion={pageQuestion(focus)}
            reportDateSlot={
              <span className={styles.metaChip}>
                观察日 {formatNullableText(resolvedAsOfDate)} · 组合{" "}
                {SHADOW_PORTFOLIO_ID}
              </span>
            }
            actions={
              <span
                className={styles.metaChip}
                title={traceCodeTitle(
                  payload?.contract_status ?? "proposal_only",
                )}
              >
                {localizePortfolioCode(
                  payload?.contract_status ?? "proposal_only",
                )}{" "}
                · 禁止交易/审批
              </span>
            }
          >
            <div className={styles.hero}>
              <DataStatusStrip
                testId="stock-analysis-portfolio-status-strip"
                className={styles.statusStrip}
              >
                <span
                  className={styles.statusChip}
                  data-tone={
                    payload?.source_gate.ready ? "positive" : "warning"
                  }
                  title={traceCodeTitle(
                    payload?.source_gate.ready
                      ? payload.source_gate.status
                      : (payload?.source_gate.primary_blocker_code ??
                          payload?.source_gate.status),
                  )}
                >
                  {sourceGateLabel(payload)}
                </span>
                <span
                  className={styles.statusChip}
                  data-tone={isProposalReady(payload) ? "neutral" : "warning"}
                  title={traceCodeTitle(payload?.proposal_status)}
                >
                  {proposalStatusLabel(payload)}
                </span>
                <span
                  className={styles.statusChip}
                  data-tone={issueTone(payload)}
                >
                  {issueSummaryText(payload)}
                </span>
                <span
                  className={styles.statusChip}
                  data-tone="neutral"
                  title={traceCodeTitle(
                    isResultStale(resultMeta)
                      ? (resultMeta?.fallback_mode ?? resultMeta?.vendor_status)
                      : (payload?.risk_snapshot.data_status ??
                          payload?.risk_snapshot.status),
                  )}
                >
                  {riskStatusLabel(payload, resultMeta)}
                </span>
                <span
                  className={styles.statusChip}
                  data-tone="warning"
                  title={traceCodeTitle(payload?.rebalance.status)}
                >
                  调仓继续锁定
                </span>
              </DataStatusStrip>
              <p className={styles.conclusion}>
                {conclusionText(payload, resultMeta, focus)}
              </p>
            </div>
          </PageDecisionHero>

          <StockAnalysisStageNav />

          {pageQuery.isError ? (
            <StateSurface
              status="error"
              density="compact"
              testId="stock-analysis-portfolio-page-error"
              message="股票影子组合读取失败"
              reason={
                pageQuery.error instanceof Error
                  ? pageQuery.error.message
                  : "接口没有返回可识别的错误信息。"
              }
              actions={
                <button
                  className={styles.retryButton}
                  type="button"
                  onClick={() => void pageQuery.refetch()}
                >
                  重新读取
                </button>
              }
            />
          ) : null}

          <KpiStrip
            testId="stock-analysis-portfolio-kpis"
            size="hero"
            cols={{ base: 2, md: 2, lg: 4, xl: 4 }}
            loading={pageQuery.isLoading}
            cells={[
              {
                key: "reference-exposure",
                label: "参考暴露",
                value: formatWeight(
                  payload?.risk_snapshot.gross_exposure_ratio,
                ),
                note:
                  payload?.risk_snapshot.measurement_basis ===
                  "reference_preview"
                    ? "只读参考权重"
                    : "等待返回",
              },
              {
                key: "cash-ratio",
                label: "现金预留",
                value: formatWeight(payload?.risk_snapshot.cash_ratio),
                note: "后端直接返回，不在前端补算。",
              },
              {
                key: "candidate-count",
                label: "候选数量",
                value: formatCount(payload?.target.candidate_count),
                note: "当前研究候选进入影子组合映射的数量。",
              },
              {
                key: "source-gate",
                label: "研究门控",
                value: sourceGateBusinessLabel(payload),
                valueVariant: "text",
                note: payload?.source_gate.ready
                  ? "仅代表候选源可用于只读映射。"
                  : localizePortfolioCode(
                      payload?.source_gate.primary_blocker_code,
                    ),
              },
            ]}
          />

          <AnalysisGrid columns={1} testId="stock-analysis-portfolio-content">
            <div className={styles.stack}>
              <SectionGrid
                cols={{ base: 1, lg: [1.7, 1] }}
                gap={16}
                align="start"
              >
                <SectionGridItem testId="stock-analysis-portfolio-primary-column">
                  <div className={styles.columnStack}>
                    <PageV2SurfacePanel
                      testId="stock-analysis-portfolio-target-surface"
                      style={{
                        padding: 0,
                        background: "transparent",
                        border: "none",
                      }}
                    >
                      <div className={styles.surface}>
                        <SectionHead
                          numbered={false}
                          category="影子组合"
                          title="候选与权重预览"
                          note="参考权重可见；目标权重受研究门控和组合映射约束，未满足时保持留空。"
                          meta={[
                            {
                              label: "组合状态",
                              value: localizePortfolioCode(
                                payload?.proposal_status,
                              ),
                              title: traceCodeTitle(payload?.proposal_status),
                            },
                            {
                              label: "权重来源",
                              value: localizeWeightBasis(
                                payload?.target.weight_basis,
                              ),
                              title: traceCodeTitle(
                                payload?.target.weight_basis,
                              ),
                            },
                            {
                              label: "研究门控",
                              value: sourceGateBusinessLabel(payload),
                              title: traceCodeTitle(
                                payload?.source_gate_status,
                              ),
                            },
                          ]}
                        />
                        <DataTable
                          testId="stock-analysis-portfolio-target-table"
                          ariaLabel="股票影子组合候选表"
                          rows={targetItems}
                          rowKey={(row) => row.stock_code}
                          rowHeaderKey="stock_name"
                          columns={targetColumns}
                          status={targetStatus}
                          emptyMessage="当前没有可映射到影子组合的候选。"
                          errorMessage={
                            pageQuery.error instanceof Error
                              ? pageQuery.error.message
                              : "股票组合页读取失败。"
                          }
                          summaryRow={{
                            stock_name: "后端快照合计",
                            reference_weight: formatWeight(
                              payload?.risk_snapshot.target_weight_sum_ratio,
                            ),
                            target_weight: payload?.target.blocked
                              ? EM_DASH
                              : formatWeight(
                                  payload?.risk_snapshot
                                    .target_weight_sum_ratio,
                                ),
                            target_block_reason: hasBlockedTargetWeight
                              ? "目标权重继续锁定"
                              : "参考预览",
                          }}
                          rowTestId={(row) =>
                            `stock-analysis-portfolio-row-${row.stock_code}`
                          }
                        />
                      </div>
                    </PageV2SurfacePanel>

                    <EvidencePanel
                      heading="阻断与边界"
                      testId="stock-analysis-portfolio-blockers"
                      className={styles.surface}
                    >
                      <span className={styles.eyebrow}>当前边界</span>
                      <div className={styles.inlineMeta}>
                        <span
                          className={styles.metaChip}
                          title={traceCodeTitle(payload?.source_gate.status)}
                        >
                          研究门控 {sourceGateBusinessLabel(payload)}
                        </span>
                        <span
                          className={styles.metaChip}
                          title={traceCodeTitle(payload?.rebalance.status)}
                        >
                          调仓状态 继续锁定
                        </span>
                        <span className={styles.metaChip}>
                          组合级持仓{" "}
                          {payload?.rebalance.scoped_positions_available
                            ? "已接入"
                            : "未接入"}
                        </span>
                      </div>
                      <p
                        className={styles.conclusion}
                        title={
                          payload?.rebalance.reason
                            ? `原始返回：${payload.rebalance.reason}`
                            : undefined
                        }
                      >
                        {rebalanceReasonText(payload)}
                      </p>
                      {renderReasonList(payload?.source_gate.reason_codes)}
                      {payload ? renderIssueList(payload.issues) : null}
                    </EvidencePanel>
                  </div>
                </SectionGridItem>

                <SectionGridItem testId="stock-analysis-portfolio-risk-column">
                  <div className={styles.columnStack}>
                    {renderRiskSurface(
                      payload,
                      resultMeta,
                      focus,
                      pageQuery.isLoading,
                      pageQuery.isError,
                    )}

                    <EvidencePanel
                      heading="提示与契约"
                      testId="stock-analysis-portfolio-warnings-surface"
                      className={styles.surface}
                    >
                      <div className={styles.inlineMeta}>
                        <span className={styles.metaChip}>
                          页面契约 {formatNullableText(payload?.page_id)}
                        </span>
                        <span className={styles.metaChip}>
                          路由 {formatNullableText(payload?.route)}
                        </span>
                        <span className={styles.metaChip}>
                          正式使用{" "}
                          {payload?.formal_use_allowed ? "允许" : "不允许"}
                        </span>
                      </div>
                      {renderWarningList(payload?.warnings ?? [])}
                    </EvidencePanel>
                  </div>
                </SectionGridItem>
              </SectionGrid>
            </div>
          </AnalysisGrid>
        </section>
      </PageV2Shell>
    </MarketWorkbenchFrame>
  );
}
