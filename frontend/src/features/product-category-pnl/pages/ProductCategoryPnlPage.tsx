import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import type {
  DecimalLike,
  ProductCategoryManualAdjustmentRequest,
  ProductCategoryPnlRow,
} from "../../../api/contracts";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import MonthlyOperatingAnalysisBranch from "./MonthlyOperatingAnalysisBranch";

const pageHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: 16,
  padding: 20,
  borderRadius: 18,
  border: "1px solid #d7dfea",
  background: "#fbfcfe",
  marginBottom: 18,
} as const;

const modeBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "8px 12px",
  borderRadius: 999,
  background: "#edf3ff",
  color: "#1f5eff",
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
} as const;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: 6,
  marginBottom: 14,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#8090a8",
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: "#162033",
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 900,
  color: "#5c6b82",
  fontSize: 13,
  lineHeight: 1.7,
} as const;

const DISPLAY_ORDER = [
  "interbank_lending_assets",
  "repo_assets",
  "bond_investment",
  "bond_tpl",
  "bond_ac",
  "bond_ac_other",
  "bond_fvoci",
  "bond_valuation_spread",
  "interest_earning_assets",
  "derivatives",
  "intermediate_business_income",
  "asset_total",
  "interbank_deposits",
  "interbank_borrowings",
  "repo_liabilities",
  "interbank_cds",
  "credit_linked_notes",
  "liability_total",
] as const;

const DISPLAY_ORDER_INDEX = new Map<string, number>(
  DISPLAY_ORDER.map((categoryId, index) => [categoryId, index]),
);

function buildAdjustmentDraft(reportDate: string): ProductCategoryManualAdjustmentRequest {
  return {
    report_date: reportDate,
    operator: "DELTA",
    approval_status: "approved",
    account_code: "",
    currency: "CNX",
    account_name: "",
    beginning_balance: null,
    ending_balance: null,
    monthly_pnl: null,
    daily_avg_balance: null,
    annual_avg_balance: null,
  };
}

function formatNumber(value: DecimalLike | null | undefined, digits = 2) {
  if (value === null || value === undefined) {
    return "-";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return String(value);
  }
  return parsed.toFixed(digits);
}

function formatDisplayValue(
  row: ProductCategoryPnlRow,
  value: DecimalLike | null | undefined,
  digits = 2,
) {
  if (value === null || value === undefined) {
    return "-";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return String(value);
  }
  if (row.side === "liability") {
    return Math.abs(parsed).toFixed(digits);
  }
  return parsed.toFixed(digits);
}

function toneForValue(value: DecimalLike | null | undefined) {
  if (value === null || value === undefined) {
    return "#162033";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return "#162033";
  }
  if (parsed > 0) {
    return "#12723b";
  }
  if (parsed < 0) {
    return "#b42318";
  }
  return "#162033";
}

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
  testId?: string;
}) {
  return (
    <div data-testid={props.testId} style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
  );
}

export default function ProductCategoryPnlPage() {
  const client = useApiClient();
  const [selectedBranch, setSelectedBranch] = useState<"product_category_pnl" | "monthly_operating_analysis">("product_category_pnl");
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedView, setSelectedView] = useState("monthly");
  const [scenarioRate, setScenarioRate] = useState("1.75");
  const [appliedScenarioRate, setAppliedScenarioRate] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [lastRefreshRunId, setLastRefreshRunId] = useState<string | null>(null);
  const [showManualForm, setShowManualForm] = useState(false);
  const [editingAdjustmentId, setEditingAdjustmentId] = useState<string | null>(null);
  const [isSubmittingAdjustment, setIsSubmittingAdjustment] = useState(false);
  const [adjustmentError, setAdjustmentError] = useState<string | null>(null);
  const [lastAdjustmentId, setLastAdjustmentId] = useState<string | null>(null);
  const [adjustmentDraft, setAdjustmentDraft] = useState<ProductCategoryManualAdjustmentRequest>(
    buildAdjustmentDraft(""),
  );

  const datesQuery = useQuery({
    queryKey: ["product-category-pnl", "dates", client.mode],
    queryFn: () => client.getProductCategoryDates(),
    retry: false,
  });

  useEffect(() => {
    if (!selectedDate && datesQuery.data?.result.report_dates.length) {
      setSelectedDate(datesQuery.data.result.report_dates[0] ?? "");
    }
  }, [datesQuery.data, selectedDate]);

  useEffect(() => {
    setAdjustmentDraft((current) => ({
      ...current,
      report_date: selectedDate,
    }));
  }, [selectedDate]);

  const baselineQuery = useQuery({
    queryKey: ["product-category-pnl", "baseline", client.mode, selectedDate, selectedView],
    queryFn: () =>
      client.getProductCategoryPnl({
        reportDate: selectedDate,
        view: selectedView,
      }),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  const scenarioQuery = useQuery({
    queryKey: [
      "product-category-pnl",
      "scenario",
      client.mode,
      selectedDate,
      selectedView,
      appliedScenarioRate,
    ],
    queryFn: () =>
      client.getProductCategoryPnl({
        reportDate: selectedDate,
        view: selectedView,
        scenarioRatePct: appliedScenarioRate,
      }),
    enabled: Boolean(selectedDate && appliedScenarioRate),
    retry: false,
  });

  const adjustmentsQuery = useQuery({
    queryKey: ["product-category-pnl", "adjustments", client.mode, selectedDate],
    queryFn: () => client.getProductCategoryManualAdjustments(selectedDate),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  const baseline = baselineQuery.data?.result;
  const scenario = scenarioQuery.data?.result;
  const displayedGrandTotal = scenario?.grand_total ?? baseline?.grand_total;
  const baselineRate = baseline?.asset_total.baseline_ftp_rate_pct ?? "1.75";
  const currentSceneRate = scenario?.scenario_rate_pct ?? baselineRate;

  const rowsToRender = useMemo(
    () =>
      (scenario?.rows ?? baseline?.rows ?? [])
        .filter((row) => row.category_id !== "grand_total")
        .sort((left, right) => {
          const leftIndex =
            DISPLAY_ORDER_INDEX.get(left.category_id) ?? Number.MAX_SAFE_INTEGER;
          const rightIndex =
            DISPLAY_ORDER_INDEX.get(right.category_id) ?? Number.MAX_SAFE_INTEGER;
          return leftIndex - rightIndex;
        }),
    [baseline?.rows, scenario?.rows],
  );

  async function runRefreshWorkflow() {
    const payload = await runPollingTask({
      start: () => client.refreshProductCategoryPnl(),
      getStatus: (runId) => client.getProductCategoryRefreshStatus(runId),
    });
    setLastRefreshRunId(payload.run_id);
    if (payload.status !== "completed") {
      throw new Error(payload.detail ?? `刷新任务未完成：${payload.status}`);
    }
    await datesQuery.refetch();
    await baselineQuery.refetch();
    await adjustmentsQuery.refetch();
    if (appliedScenarioRate) {
      await scenarioQuery.refetch();
    }
  }

  async function handleRefresh() {
    setIsRefreshing(true);
    setRefreshError(null);
    try {
      await runRefreshWorkflow();
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "刷新损益数据失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  function updateAdjustmentField<K extends keyof ProductCategoryManualAdjustmentRequest>(
    key: K,
    value: ProductCategoryManualAdjustmentRequest[K],
  ) {
    setAdjustmentDraft((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function handleManualAdjustmentSubmit() {
    setAdjustmentError(null);
    if (!adjustmentDraft.report_date) {
      setAdjustmentError("请选择报表月份。");
      return;
    }
    if (!adjustmentDraft.account_code.trim()) {
      setAdjustmentError("请输入科目代码。");
      return;
    }
    if (
      !adjustmentDraft.beginning_balance &&
      !adjustmentDraft.ending_balance &&
      !adjustmentDraft.monthly_pnl &&
      !adjustmentDraft.daily_avg_balance &&
      !adjustmentDraft.annual_avg_balance
    ) {
      setAdjustmentError("至少填写一个调整数值。");
      return;
    }

    setIsSubmittingAdjustment(true);
    try {
      const payload = editingAdjustmentId
        ? await client.updateProductCategoryManualAdjustment(editingAdjustmentId, adjustmentDraft)
        : await client.createProductCategoryManualAdjustment(adjustmentDraft);
      setLastAdjustmentId(payload.adjustment_id);
      await runRefreshWorkflow();
      setShowManualForm(false);
      setEditingAdjustmentId(null);
      setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
    } catch (error) {
      setAdjustmentError(error instanceof Error ? error.message : "手工录入失败");
    } finally {
      setIsSubmittingAdjustment(false);
    }
  }

  async function handleManualAdjustmentRevoke(adjustmentId: string) {
    setAdjustmentError(null);
    setIsSubmittingAdjustment(true);
    try {
      await client.revokeProductCategoryManualAdjustment(adjustmentId);
      await runRefreshWorkflow();
    } catch (error) {
      setAdjustmentError(error instanceof Error ? error.message : "撤销手工录入失败");
    } finally {
      setIsSubmittingAdjustment(false);
    }
  }

  async function handleManualAdjustmentRestore(adjustmentId: string) {
    setAdjustmentError(null);
    setIsSubmittingAdjustment(true);
    try {
      await client.restoreProductCategoryManualAdjustment(adjustmentId);
      await runRefreshWorkflow();
    } catch (error) {
      setAdjustmentError(error instanceof Error ? error.message : "恢复手工录入失败");
    } finally {
      setIsSubmittingAdjustment(false);
    }
  }

  function handleManualAdjustmentEdit(adjustment: {
    adjustment_id: string;
    report_date: string;
    operator: "ADD" | "DELTA" | "OVERRIDE";
    approval_status: "approved" | "pending" | "rejected";
    account_code: string;
    currency: "CNX" | "CNY";
    account_name?: string;
    beginning_balance?: string | null;
    ending_balance?: string | null;
    monthly_pnl?: string | null;
    daily_avg_balance?: string | null;
    annual_avg_balance?: string | null;
  }) {
    setEditingAdjustmentId(adjustment.adjustment_id);
    setAdjustmentDraft({
      report_date: adjustment.report_date,
      operator: adjustment.operator,
      approval_status: adjustment.approval_status,
      account_code: adjustment.account_code,
      currency: adjustment.currency,
      account_name: adjustment.account_name ?? "",
      beginning_balance: adjustment.beginning_balance ?? null,
      ending_balance: adjustment.ending_balance ?? null,
      monthly_pnl: adjustment.monthly_pnl ?? null,
      daily_avg_balance: adjustment.daily_avg_balance ?? null,
      annual_avg_balance: adjustment.annual_avg_balance ?? null,
    });
    setAdjustmentError(null);
    setShowManualForm(true);
  }

  const reportExtra = baseline ? (
    <div
      data-testid="product-category-summary"
      style={{
        display: "flex",
        gap: 12,
        flexWrap: "wrap",
        justifyContent: "flex-end",
        color: "#5c6b82",
        fontSize: 13,
      }}
    >
      <span>当前场景：{currentSceneRate}%</span>
      <span>基准场景：{baselineRate}%</span>
      <span style={{ color: "#162033", fontWeight: 700 }}>
        合计：{formatNumber(displayedGrandTotal?.business_net_income)}
      </span>
    </div>
  ) : null;
  const ledgerPnlHref = selectedDate
    ? `/ledger-pnl?report_date=${encodeURIComponent(selectedDate)}`
    : "/ledger-pnl";

  if (selectedBranch === "monthly_operating_analysis") {
    return (
      <section data-testid="product-category-page">
        <FilterBar style={{ marginBottom: 16 }}>
          <button
            type="button"
            data-testid="product-category-branch-product-category-pnl"
            aria-pressed="false"
            onClick={() => setSelectedBranch("product_category_pnl")}
          >
            产品分类损益
          </button>
          <button
            type="button"
            data-testid="product-category-branch-monthly-operating-analysis"
            aria-pressed="true"
            onClick={() => setSelectedBranch("monthly_operating_analysis")}
          >
            月度经营分析
          </button>
        </FilterBar>
        <MonthlyOperatingAnalysisBranch />
      </section>
    );
  }

  return (
    <section data-testid="product-category-page">
      <FilterBar style={{ marginBottom: 16 }}>
        <button
          type="button"
          data-testid="product-category-branch-product-category-pnl"
          aria-pressed="true"
          onClick={() => setSelectedBranch("product_category_pnl")}
        >
          产品分类损益
        </button>
        <button
          type="button"
          data-testid="product-category-branch-monthly-operating-analysis"
          aria-pressed="false"
          onClick={() => setSelectedBranch("monthly_operating_analysis")}
        >
          月度经营分析
        </button>
      </FilterBar>
      <div style={pageHeaderStyle}>
        <div>
          <h1
            data-testid="product-category-page-title"
            style={{
              margin: 0,
              fontSize: 28,
              fontWeight: 700,
              letterSpacing: "-0.03em",
            }}
          >
            产品分类损益
          </h1>
          <p
            data-testid="product-category-page-subtitle"
            style={{
              marginTop: 8,
              marginBottom: 0,
              color: "#5c6b82",
              fontSize: 14,
              lineHeight: 1.7,
            }}
          >
            按业务分类查看损益、FTP 和净收入。用于经营分析，不等同于逐笔损益明细。
          </p>
          <p data-testid="product-category-boundary-copy" style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 12 }}>
            系统层经营口径：正式基线来自 formal read model；情景预览仅在显式应用后生效。
          </p>
          {lastRefreshRunId ? (
            <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 12 }}>
              最近刷新任务：{lastRefreshRunId}
            </p>
          ) : null}
          {lastAdjustmentId ? (
            <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 12 }}>
              最近录入调整：{lastAdjustmentId}
            </p>
          ) : null}
          {refreshError ? (
            <p style={{ marginTop: 8, marginBottom: 0, color: "#b42318", fontSize: 12 }}>
              {refreshError}
            </p>
          ) : null}
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <span data-testid="product-category-role-badge" style={modeBadgeStyle}>
            System Layer
          </span>
          <span style={modeBadgeStyle}>
            {client.mode === "real" ? "正式只读链路" : "本地离线契约回放"}
          </span>
          <a data-testid="product-category-audit-link" href="/product-category-pnl/audit">
            查看调整审计
          </a>
          <a data-testid="product-category-ledger-link" href={ledgerPnlHref}>
            Ledger PnL
          </a>
          <button
            type="button"
            data-testid="product-category-manual-button"
            onClick={() => {
              setShowManualForm((current) => !current);
              setEditingAdjustmentId(null);
              setAdjustmentError(null);
              if (showManualForm) {
                setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
              }
            }}
            style={{
              padding: "10px 16px",
              borderRadius: 12,
              border: "1px solid #162033",
              background: "#fbfcfe",
              color: "#162033",
              fontWeight: 600,
            }}
          >
            + 手工录入
          </button>
          <button
            type="button"
            data-testid="product-category-refresh-button"
            onClick={() => void handleRefresh()}
            disabled={isRefreshing}
            style={{
              padding: "10px 16px",
              borderRadius: 12,
              border: "1px solid #162033",
              background: "#fbfcfe",
              color: "#162033",
              fontWeight: 600,
              cursor: isRefreshing ? "progress" : "pointer",
              opacity: isRefreshing ? 0.7 : 1,
            }}
          >
            {isRefreshing ? "刷新中..." : "刷新损益数据"}
          </button>
        </div>
      </div>

      {showManualForm ? (
        <div
          data-testid="product-category-manual-form"
          style={{
            display: "grid",
            gap: 12,
            marginBottom: 18,
            padding: 18,
            borderRadius: 18,
            border: "1px solid #d7dfea",
            background: "#fbfcfe",
          }}
        >
          <div style={{ fontWeight: 600 }}>
            {editingAdjustmentId ? "编辑手工录入" : "手工录入"}
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
              gap: 12,
            }}
          >
            <label style={{ display: "grid", gap: 6 }}>
              报表日期
              <input
                aria-label="手工录入-报表日期"
                value={adjustmentDraft.report_date}
                readOnly
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              操作方式
              <select
                aria-label="手工录入-操作方式"
                value={adjustmentDraft.operator}
                onChange={(event) =>
                  updateAdjustmentField(
                    "operator",
                    event.target.value as "ADD" | "DELTA" | "OVERRIDE",
                  )
                }
              >
                <option value="ADD">ADD</option>
                <option value="DELTA">DELTA</option>
                <option value="OVERRIDE">OVERRIDE</option>
              </select>
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              币种
              <select
                aria-label="手工录入-币种"
                value={adjustmentDraft.currency}
                onChange={(event) =>
                  updateAdjustmentField("currency", event.target.value as "CNX" | "CNY")
                }
              >
                <option value="CNX">CNX</option>
                <option value="CNY">CNY</option>
              </select>
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              科目代码
              <input
                aria-label="手工录入-科目代码"
                value={adjustmentDraft.account_code}
                onChange={(event) => updateAdjustmentField("account_code", event.target.value)}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              科目名称
              <input
                aria-label="手工录入-科目名称"
                value={adjustmentDraft.account_name ?? ""}
                onChange={(event) => updateAdjustmentField("account_name", event.target.value)}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              审批状态
              <select
                aria-label="手工录入-审批状态"
                value={adjustmentDraft.approval_status}
                onChange={(event) =>
                  updateAdjustmentField(
                    "approval_status",
                    event.target.value as "approved" | "pending" | "rejected",
                  )
                }
              >
                <option value="approved">approved</option>
                <option value="pending">pending</option>
                <option value="rejected">rejected</option>
              </select>
            </label>
            {[
              ["beginning_balance", "期初余额"],
              ["ending_balance", "期末余额"],
              ["monthly_pnl", "月度损益"],
              ["daily_avg_balance", "月日均"],
              ["annual_avg_balance", "年日均"],
            ].map(([field, label]) => (
              <label key={field} style={{ display: "grid", gap: 6 }}>
                {label}
                <input
                  aria-label={`手工录入-${label}`}
                  value={(adjustmentDraft as Record<string, string | null | undefined>)[field] ?? ""}
                  onChange={(event) =>
                    updateAdjustmentField(
                      field as keyof ProductCategoryManualAdjustmentRequest,
                      event.target.value || null,
                    )
                  }
                />
              </label>
            ))}
          </div>
          {adjustmentError ? (
            <div style={{ color: "#b42318", fontSize: 12 }}>{adjustmentError}</div>
          ) : null}
          <div style={{ display: "flex", gap: 10 }}>
            <button
              type="button"
              data-testid="product-category-manual-submit"
              onClick={() => void handleManualAdjustmentSubmit()}
              disabled={isSubmittingAdjustment}
            >
              {isSubmittingAdjustment
                ? "提交中..."
                : editingAdjustmentId
                  ? "保存并刷新"
                  : "提交并刷新"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowManualForm(false);
                setEditingAdjustmentId(null);
                setAdjustmentDraft(buildAdjustmentDraft(selectedDate));
              }}
            >
              取消
            </button>
          </div>
        </div>
      ) : null}

      <SectionLead
        eyebrow="Governance"
        title="手工调整与审计"
        description="手工调整仍走既有 create / update / revoke / restore API，完整事件时间线保留在独立审计视图。"
        testId="product-category-adjustment-lead"
      />
      <AsyncSection
        title="手工调整历史"
        isLoading={adjustmentsQuery.isLoading}
        isError={adjustmentsQuery.isError}
        isEmpty={
          !adjustmentsQuery.isLoading &&
          !adjustmentsQuery.isError &&
          (adjustmentsQuery.data?.adjustments.length ?? 0) === 0
        }
        onRetry={() => void adjustmentsQuery.refetch()}
      >
        <div
          data-testid="product-category-adjustment-history"
          style={{ display: "grid", gap: 10 }}
        >
          <div style={{ fontWeight: 600 }}>当前状态</div>
          {(adjustmentsQuery.data?.adjustments ?? []).map((item) => (
            <div
              key={`current-${item.adjustment_id}`}
              style={{
                display: "grid",
                gridTemplateColumns: "1.2fr 0.8fr 0.8fr 0.8fr auto auto auto",
                gap: 12,
                alignItems: "center",
                padding: 12,
                borderRadius: 12,
                border: "1px solid #d7dfea",
              }}
            >
              <div>
                <div style={{ fontWeight: 600 }}>{item.account_code}</div>
                <div style={{ color: "#5c6b82", fontSize: 12 }}>
                  {item.account_name || "未填写科目名称"}
                </div>
                <div style={{ color: "#8090a8", fontSize: 12 }}>
                  最近事件：{item.event_type}
                </div>
              </div>
              <div>{item.currency}</div>
              <div>{item.operator}</div>
              <div>{item.approval_status}</div>
              <button
                type="button"
                data-testid={`product-category-edit-${item.adjustment_id}`}
                disabled={isSubmittingAdjustment}
                onClick={() =>
                  handleManualAdjustmentEdit({
                    adjustment_id: item.adjustment_id,
                    report_date: item.report_date,
                    operator: item.operator as "ADD" | "DELTA" | "OVERRIDE",
                    approval_status: item.approval_status as "approved" | "pending" | "rejected",
                    account_code: item.account_code,
                    currency: item.currency as "CNX" | "CNY",
                    account_name: item.account_name,
                    beginning_balance: item.beginning_balance ?? null,
                    ending_balance: item.ending_balance ?? null,
                    monthly_pnl: item.monthly_pnl ?? null,
                    daily_avg_balance: item.daily_avg_balance ?? null,
                    annual_avg_balance: item.annual_avg_balance ?? null,
                  })
                }
              >
                编辑
              </button>
              <button
                type="button"
                data-testid={`product-category-revoke-${item.adjustment_id}`}
                disabled={item.approval_status !== "approved" || isSubmittingAdjustment}
                onClick={() => void handleManualAdjustmentRevoke(item.adjustment_id)}
              >
                撤销
              </button>
              <button
                type="button"
                data-testid={`product-category-restore-${item.adjustment_id}`}
                disabled={item.approval_status !== "rejected" || isSubmittingAdjustment}
                onClick={() => void handleManualAdjustmentRestore(item.adjustment_id)}
              >
                恢复
              </button>
            </div>
          ))}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 12,
              padding: 12,
              borderRadius: 12,
              border: "1px dashed #d7dfea",
              background: "#fcfdff",
            }}
          >
            <div style={{ display: "grid", gap: 4 }}>
              <div style={{ fontWeight: 600 }}>完整事件时间线已迁移到独立审计视图</div>
              <div style={{ color: "#5c6b82", fontSize: 12 }}>
                当前报表月份共有 {(adjustmentsQuery.data?.events ?? []).length} 条调整事件。
              </div>
            </div>
            <a
              href="/product-category-pnl/audit"
              data-testid="product-category-audit-summary-link"
            >
              查看调整审计
            </a>
          </div>
        </div>
      </AsyncSection>

      <SectionLead
        eyebrow="Scenario"
        title="报告口径与场景预览"
        description="报告月份和视图模式驱动 formal baseline；FTP 场景只有点击应用后才触发 scenario 查询，不覆盖正式结果。"
        testId="product-category-scenario-lead"
      />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.3fr 1.3fr 1.3fr",
          gap: 14,
          marginBottom: 18,
          padding: 18,
          borderRadius: 18,
          border: "1px solid #d7dfea",
          background: "#fbfcfe",
        }}
      >
        <label style={{ display: "grid", gap: 8, fontSize: 13, color: "#5c6b82" }}>
          选择报表月份
          <select
            aria-label="选择报表月份"
            value={selectedDate}
            onChange={(event) => setSelectedDate(event.target.value)}
            style={{ padding: "10px 12px", borderRadius: 12, border: "1px solid #d7dfea" }}
          >
            {(datesQuery.data?.result.report_dates ?? []).map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {reportDate}
              </option>
            ))}
          </select>
        </label>

        <label style={{ display: "grid", gap: 8, fontSize: 13, color: "#5c6b82" }}>
          视图模式
          <div
            role="group"
            aria-label="视图模式"
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 6,
            }}
          >
            <button
              type="button"
              onClick={() => setSelectedView("monthly")}
              style={{
                padding: "10px 12px",
                borderRadius: 12,
                border: "1px solid #d7dfea",
                background: selectedView === "monthly" ? "#162033" : "#fbfcfe",
                color: selectedView === "monthly" ? "#fbfcfe" : "#162033",
                fontWeight: 600,
              }}
            >
              月度视图
            </button>
            <button
              type="button"
              onClick={() => setSelectedView("ytd")}
              style={{
                padding: "10px 12px",
                borderRadius: 12,
                border: "1px solid #d7dfea",
                background: selectedView === "ytd" ? "#162033" : "#fbfcfe",
                color: selectedView === "ytd" ? "#fbfcfe" : "#162033",
                fontWeight: 600,
              }}
            >
              汇总视图
            </button>
          </div>
        </label>

        <label style={{ display: "grid", gap: 8, fontSize: 13, color: "#5c6b82" }}>
          FTP 场景
          <select
            aria-label="FTP 场景"
            value={scenarioRate}
            onChange={(event) => setScenarioRate(event.target.value)}
            style={{ padding: "10px 12px", borderRadius: 12, border: "1px solid #d7dfea" }}
          >
            {["1.75", "2.00", "2.50", "3.00"].map((value) => (
              <option key={value} value={value}>
                {value}%
              </option>
            ))}
          </select>
        </label>
      </div>

      <div style={{ marginBottom: 18 }}>
        <button
          type="button"
          data-testid="product-category-apply-scenario-button"
          onClick={() => setAppliedScenarioRate(scenarioRate.trim())}
          style={{
            padding: "11px 14px",
            borderRadius: 12,
            border: "1px solid #cddcff",
            background: "#e7efff",
            color: "#1f5eff",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          应用场景
        </button>
      </div>

      <SectionLead
        eyebrow="Formal"
        title="正式产品类别损益表"
        description="表格继续展示后端返回的产品类别 read model，资产/负债符号展示、scenario 行为和合计行保持原有逻辑。"
        testId="product-category-formal-table-lead"
      />
      <AsyncSection
        title="产品类别损益分析表（单位：亿元）"
        isLoading={baselineQuery.isLoading}
        isError={baselineQuery.isError}
        isEmpty={!baselineQuery.isLoading && !baselineQuery.isError && rowsToRender.length === 0}
        onRetry={() => void baselineQuery.refetch()}
        extra={reportExtra}
      >
        <div style={{ overflowX: "auto" }}>
          <table
            data-testid="product-category-table"
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 13,
            }}
          >
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid #d7dfea", background: "#eef4fb" }}>
                <th rowSpan={2} style={{ padding: "12px 8px" }}>产品类别</th>
                <th colSpan={3} style={{ padding: "12px 8px", textAlign: "center" }}>规模日均</th>
                <th colSpan={8} style={{ padding: "12px 8px", textAlign: "center" }}>损益</th>
                <th rowSpan={2} style={{ padding: "12px 8px", textAlign: "right" }}>加权收益率</th>
              </tr>
              <tr style={{ textAlign: "left", borderBottom: "1px solid #d7dfea", background: "#eef4fb" }}>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>综本</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>人民币</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>外币</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>综本</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>人民币</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>人民币FTP</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>人民币减收入</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>外币</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>外币FTP</th>
                <th style={{ padding: "12px 8px", textAlign: "right" }}>外币减收入</th>
                <th style={{ padding: "12px 8px", textAlign: "right", background: "#fff8dc" }}>营业减收入</th>
              </tr>
            </thead>
            <tbody>
              {rowsToRender.map((row) => (
                <tr
                  key={row.category_id}
                  style={{
                    borderBottom: "1px solid #edf1f6",
                    background: row.is_total ? "#edf4ff" : "#ffffff",
                    fontWeight: row.is_total ? 700 : 400,
                  }}
                >
                  <td style={{ padding: "12px 8px" }}>
                    <div style={{ paddingLeft: row.level * 18 }}>
                      <div>{row.category_name}</div>
                    </div>
                  </td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatDisplayValue(row, row.cnx_scale)}</td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatDisplayValue(row, row.cny_scale)}</td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatDisplayValue(row, row.foreign_scale)}</td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatDisplayValue(row, row.cnx_cash)}</td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatDisplayValue(row, row.cny_cash)}</td>
                  <td style={{ padding: "12px 8px", textAlign: "right", color: "#1f5eff" }}>{formatDisplayValue(row, row.cny_ftp)}</td>
                  <td style={{ padding: "12px 8px", textAlign: "right", color: toneForValue(row.cny_net) }}>
                    {formatDisplayValue(row, row.cny_net)}
                  </td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatDisplayValue(row, row.foreign_cash)}</td>
                  <td style={{ padding: "12px 8px", textAlign: "right", color: "#1f5eff" }}>{formatDisplayValue(row, row.foreign_ftp)}</td>
                  <td style={{ padding: "12px 8px", textAlign: "right", color: toneForValue(row.foreign_net) }}>
                    {formatDisplayValue(row, row.foreign_net)}
                  </td>
                  <td
                    style={{
                      padding: "12px 8px",
                      textAlign: "right",
                      color: toneForValue(row.business_net_income),
                      background: "#fff8dc",
                    }}
                  >
                    {formatDisplayValue(row, row.business_net_income)}
                  </td>
                  <td style={{ padding: "12px 8px", textAlign: "right" }}>{formatDisplayValue(row, row.weighted_yield)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AsyncSection>

      {displayedGrandTotal ? (
        <div
          data-testid="product-category-footer-total"
          style={{
            marginTop: 16,
            padding: "14px 18px",
            borderRadius: 16,
            background: "#162033",
            color: "#fbfcfe",
            fontWeight: 700,
            textAlign: "center",
          }}
        >
          全部市场科目 + 投资收益合计：{formatNumber(displayedGrandTotal.business_net_income)}
        </div>
      ) : null}
    </section>
  );
}
